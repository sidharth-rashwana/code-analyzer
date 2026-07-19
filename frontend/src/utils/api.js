/**
 * Client for the code-analyzer FastAPI backend (api.py).
 *
 * Base URL resolution: defaults to "/api" (proxied to the backend by
 * vite.config.js's dev server proxy — no CORS needed in dev). Override
 * with VITE_API_BASE_URL for production, where there's no Vite dev
 * server to proxy through (point it directly at wherever uvicorn is
 * running, e.g. "https://api.example.com").
 */
const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

async function safeErrorMessage(res) {
  try {
    const body = await res.json();
    return body?.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

async function fetchJson(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await safeErrorMessage(res));
  return res.json();
}

/** POST /scan {path} -> {job_id} */
export async function postScan(path, baseUrl = DEFAULT_BASE_URL) {
  return fetchJson(`${baseUrl}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
}

/** GET /jobs/{job_id} -> {job_id, status, path, error, stats} */
export async function getJob(jobId, baseUrl = DEFAULT_BASE_URL) {
  return fetchJson(`${baseUrl}/jobs/${jobId}`);
}

/**
 * Polls GET /jobs/{job_id} until status is "done" or "error", calling
 * onStatus with each poll's result along the way (for progress UI).
 * Throws on "error" status or if timeoutMs is exceeded.
 */
export async function pollJob(
  jobId,
  { baseUrl = DEFAULT_BASE_URL, intervalMs = 400, timeoutMs = 120000, onStatus } = {}
) {
  const start = Date.now();
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const status = await getJob(jobId, baseUrl);
    onStatus?.(status);
    if (status.status === "done") return status;
    if (status.status === "error") {
      throw new Error(status.error || "Scan failed.");
    }
    if (Date.now() - start > timeoutMs) {
      throw new Error("Scan timed out — the backend may still be running it.");
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

/**
 * End-to-end: kick off a scan, wait for it to finish, then fetch and
 * merge /graph + /unresolved + /function-edges into the same
 * { graph, unresolved, function_edges } shape a file-upload payload
 * has — so buildElements() and validateGraphPayload() work identically
 * regardless of which path the data came from.
 */
export async function scanAndFetch(
  path,
  { baseUrl = DEFAULT_BASE_URL, onStatus } = {}
) {
  const { job_id } = await postScan(path, baseUrl);
  onStatus?.({ status: "queued", job_id });
  await pollJob(job_id, { baseUrl, onStatus });

  const [graph, unresolvedRes, functionEdgesRes] = await Promise.all([
    fetchJson(`${baseUrl}/graph?job_id=${job_id}`),
    fetchJson(`${baseUrl}/unresolved?job_id=${job_id}`),
    fetchJson(`${baseUrl}/function-edges?job_id=${job_id}`),
  ]);

  return {
    graph,
    unresolved: unresolvedRes.unresolved,
    function_edges: functionEdgesRes.function_edges,
  };
}

export { DEFAULT_BASE_URL };
