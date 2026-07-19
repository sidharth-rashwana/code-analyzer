import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxies to the code-analyzer FastAPI backend (uvicorn api:app,
      // default port 8000). Sidesteps CORS entirely in dev — the browser
      // only ever talks to same-origin /api/*, Vite forwards it server-side.
      // In production, set VITE_API_BASE_URL instead (see src/utils/api.js).
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
