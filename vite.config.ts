import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command }) => ({
  plugins: [react()],
  root: "frontend",
  base: command === "build" ? "/static/" : "/",
  publicDir: "public",
  build: {
    outDir: "../app/static",
    emptyOutDir: true,
    assetsDir: "assets",
    assetsInlineLimit: 0,
    target: "es2022",
  },
  server: {
    host: "127.0.0.1",
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/v1": "http://127.0.0.1:8000",
    },
  },
}));
