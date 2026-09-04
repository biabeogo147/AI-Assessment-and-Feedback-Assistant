/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Vite configuration for the FE dev server.
 *
 * The `/api` proxy is what keeps the browser on a single origin: without it the
 * app would call BE cross-origin and need CORS on the server. Proxying is the
 * cheaper of the two and keeps BE free of frontend-specific configuration.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [],
  },
});
