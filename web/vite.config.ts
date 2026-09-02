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
    rollupOptions: {
      output: {
        // Split heavy vendors into dedicated chunks so the initial bundle
        // stays under 500 KB. Konva is ~250 KB on its own, so we isolate it.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("konva") || id.includes("react-konva") || id.includes("use-gesture")) {
            return "vendor-konva";
          }
          if (id.includes("@tanstack")) {
            return "vendor-react-query";
          }
          if (id.includes("framer-motion") || id.includes("motion")) {
            return "vendor-motion";
          }
          if (id.includes("react-dnd") || id.includes("dnd-core")) {
            return "vendor-dnd";
          }
          if (id.includes("react") || id.includes("scheduler")) {
            return "vendor-react";
          }
          return undefined;
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
});
