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
    /*
     * `127.0.0.1` chứ không để mặc định.
     *
     * Mặc định của Vite là `localhost`, và trên Node 17+ chuỗi ấy được phân giải theo thứ
     * tự DNS của hệ điều hành — ở máy này nó ra `[::1]` và server **chỉ** bind IPv6. Trình
     * duyệt thì phân giải `localhost` ra `127.0.0.1` trước, nên nó nhận
     * `ERR_CONNECTION_REFUSED` trong khi `curl` từ shell trả 200 ở đúng cái URL ấy. Mất
     * bốn lượt thử ngày 06/10/2026 mới đọc ra, vì triệu chứng đọc như dev server đang chết.
     *
     * Không dùng `host: true`: nó bind mọi địa chỉ, tức mở dev server ra cả mạng LAN. Chỗ
     * này chỉ cần loopback, và một IPv4 loopback thì mọi trình duyệt đều với tới được.
     */
    host: "127.0.0.1",
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
