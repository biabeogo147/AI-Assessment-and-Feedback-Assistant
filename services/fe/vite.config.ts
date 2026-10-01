/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Cấu hình Vite cho dev server của FE.
 *
 * Proxy `/api` là thứ giữ browser ở đúng một origin: không có nó thì app sẽ gọi
 * BE cross-origin và server phải bật CORS. Proxy là phương án rẻ hơn trong hai
 * cách, và giữ cho BE không phải chứa cấu hình riêng của frontend.
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
