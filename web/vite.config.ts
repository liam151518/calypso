import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const FLASK_HOST = process.env.CALYPSO_FLASK_URL ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: FLASK_HOST, changeOrigin: true },
      "/static": { target: FLASK_HOST, changeOrigin: true },
      "/outputs": { target: FLASK_HOST, changeOrigin: true },
      "/references/file": { target: FLASK_HOST, changeOrigin: true },
      "/generate": { target: FLASK_HOST, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
    target: "es2022",
  },
});
