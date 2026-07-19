export function shortName(path) {
  if (!path) return "";
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1];
}

/**
 * A file's entry in `graph` can be either:
 *   - the current backend shape: { hash, imports: [ {resolved_file, ...} ] }
 *   - an older saved snapshot's shape: [ "target/file.py", ... ]
 * This normalizes either into a flat array of per-import detail objects,
 * so the rest of buildElements doesn't need to know which shape it got.
 */
function normalizeImports(fileEntry) {
  if (Array.isArray(fileEntry)) {
    return fileEntry.map((target) => ({ resolved_file: target }));
  }
  if (fileEntry && Array.isArray(fileEntry.imports)) {
    return fileEntry.imports;
  }
  return [];
}

function getHash(fileEntry) {
  return Array.isArray(fileEntry) ? undefined : fileEntry?.hash;
}

/**
 * Not every "unresolved" entry means something is wrong. Most of them are
 * `import json` / `import os` — completely expected, since stdlib and
 * third-party packages aren't part of the project and were never going
 * to resolve to a project file. Only entries the resolver flagged for a
 * reason *other than* "this is stdlib/third-party" represent something a
 * human might actually want to look at (a dynamic import, a name that
 * genuinely doesn't exist in its target module, etc).
 *
 * This is the single fix that matters most for signal-to-noise: without
 * it, every file in a typical project lights up as "has a problem"
 * because every file imports something from the standard library.
 */
export function isExpectedUnresolved(entry) {
  return /stdlib|third-party/i.test(entry?.reason || "");
}

export function classifyUnresolved(unresolved) {
  const attention = [];
  const expected = [];
  unresolved.forEach((u) => (isExpectedUnresolved(u) ? expected : attention).push(u));
  return { attention, expected };
}

/**
 * Longest common leading-directory prefix across all file paths, used to
 * display paths relative to the project root instead of full absolute
 * paths, and to build the sidebar's folder tree.
 */
function commonDirPrefix(files) {
  if (files.length === 0) return "";
  const split = files.map((f) => f.split(/[\\/]/));
  const first = split[0];
  let prefixLen = first.length - 1; // exclude the filename itself
  for (let i = 1; i < split.length; i++) {
    const other = split[i];
    let j = 0;
    while (j < prefixLen && j < other.length - 1 && other[j] === first[j]) j++;
    prefixLen = Math.min(prefixLen, j);
  }
  return first.slice(0, prefixLen).join("/");
}

export function relativePath(file, prefix) {
  if (!prefix) return file;
  return file.startsWith(prefix + "/") ? file.slice(prefix.length + 1) : file;
}

/**
 * Nested { folders: Map<name, node>, files: [{id, name}] } tree, built
 * from each file's path relative to the common project-root prefix, so
 * the sidebar can show a real directory structure instead of a flat
 * alphabetical dump of every file in the repo.
 */
function buildFileTree(files, prefix) {
  const root = { folders: new Map(), files: [] };
  files.forEach((f) => {
    const rel = relativePath(f, prefix);
    const segments = rel.split("/");
    let node = root;
    for (let i = 0; i < segments.length - 1; i++) {
      const seg = segments[i];
      if (!node.folders.has(seg)) {
        node.folders.set(seg, { folders: new Map(), files: [] });
      }
      node = node.folders.get(seg);
    }
    node.files.push({ id: f, name: segments[segments.length - 1] });
  });
  return root;
}

/**
 * Transforms a raw { graph, unresolved, function_edges } payload (as
 * produced by build_module_graph() in the Python pipeline, either via
 * file upload or the /graph, /unresolved, /function-edges API endpoints)
 * into the shape the UI components need: node list, edge list, lookup
 * maps for incoming/outgoing dependencies, a folder tree, and unresolved
 * imports split into "needs attention" vs "expected" (see
 * isExpectedUnresolved).
 */
export function buildElements(rawData) {
  const graph = rawData?.graph || {};
  const unresolved = rawData?.unresolved || [];
  const functionEdges = rawData?.function_edges || [];
  const files = Object.keys(graph);

  const { attention, expected } = classifyUnresolved(unresolved);

  const attentionByFile = {};
  attention.forEach((u) => {
    if (!u.file) return;
    attentionByFile[u.file] = (attentionByFile[u.file] || 0) + 1;
  });
  const expectedByFile = {};
  expected.forEach((u) => {
    if (!u.file) return;
    expectedByFile[u.file] = (expectedByFile[u.file] || 0) + 1;
  });

  // Dedupe edges (a file can import multiple names from the same target,
  // which would otherwise draw overlapping lines) and skip entries with
  // no resolved_file (those are unresolved imports, tracked separately).
  const edgeKeys = new Set();
  const edges = [];
  const outgoingMap = {};

  files.forEach((f) => {
    const targets = new Set();
    normalizeImports(graph[f]).forEach((imp) => {
      const target = imp.resolved_file;
      if (!target) return;
      targets.add(target);
      const key = `${f}\u0000${target}`;
      if (!edgeKeys.has(key)) {
        edgeKeys.add(key);
        edges.push({ source: f, target });
      }
    });
    outgoingMap[f] = Array.from(targets);
  });

  const incomingMap = {};
  files.forEach((f) => {
    (outgoingMap[f] || []).forEach((target) => {
      if (!incomingMap[target]) incomingMap[target] = [];
      incomingMap[target].push(f);
    });
  });

  const nodes = files.map((f) => {
    const outDegree = (outgoingMap[f] || []).length;
    const inDegree = (incomingMap[f] || []).length;
    return {
      id: f,
      label: shortName(f),
      hasUnresolved: Boolean(attentionByFile[f]),
      attentionCount: attentionByFile[f] || 0,
      expectedCount: expectedByFile[f] || 0,
      hash: getHash(graph[f]),
      inDegree,
      outDegree,
      degree: inDegree + outDegree,
    };
  });

  const commonPrefix = commonDirPrefix(files);
  const fileTree = buildFileTree(files, commonPrefix);

  const maxDegree = nodes.reduce((m, n) => Math.max(m, n.degree), 0);
  const hubs = [...nodes]
    .filter((n) => n.degree > 0)
    .sort((a, b) => b.degree - a.degree)
    .slice(0, 5);

  return {
    files,
    nodes,
    edges,
    incomingMap,
    outgoingMap,
    unresolvedByFile: attentionByFile, // kept for compatibility; attention-only, not total
    unresolvedAttention: attention,
    unresolvedExpected: expected,
    functionEdges,
    commonPrefix,
    fileTree,
    maxDegree,
    hubs,
  };
}

/** Validates a parsed JSON payload has the shape we expect before using it. */
export function validateGraphPayload(parsed) {
  if (typeof parsed !== "object" || parsed === null) {
    throw new Error("Expected a JSON object.");
  }
  if (typeof parsed.graph !== "object" || parsed.graph === null) {
    throw new Error('Expected a JSON object with a "graph" key.');
  }
  return true;
}
