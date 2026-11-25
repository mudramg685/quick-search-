import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Vite server proxies /api to FastAPI, so the browser talks to one
// origin. In production FastAPI serves the built files itself (see backend main.py).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
