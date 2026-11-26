import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Vite server proxies /api to FastAPI, so the browser talks to one
// origin. In production FastAPI serves the built files itself (see backend main.py).
export default defineConfig({
  // GitHub Pages serves the static build from /<repo>/. VITE_BASE is the bare repo name
  // (no slashes – Git Bash on Windows would rewrite "/name/" into a filesystem path).
  base: process.env.VITE_BASE ? `/${process.env.VITE_BASE.replace(/^\/+|\/+$/g, "")}/` : "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
