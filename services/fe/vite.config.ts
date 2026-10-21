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
    /*
     * Chờ file **đứng yên** rồi mới báo đổi.
     *
     * chokidar 3 (Vite 5 đóng gói sẵn) bỏ mọi `change` đến trong 50 ms sau sự kiện trước của cùng
     * file (`_throttle(EV_CHANGE, path, 50)`), và không phát bù khi hết 50 ms. Nên hai lần ghi cách
     * nhau dưới 50 ms (hai lần sửa liền, hay một công cụ ghi hai nhịp) chỉ cho **một** sự kiện. Tab
     * đang mở đã hỏi lại module ngay sau sự kiện ấy, nên Vite giữ bản transform của lần ghi thứ nhất
     * cho tới lần đổi file kế -- màn chạy CSS cũ, hay thiếu một export vừa thêm. Đo 21/10/2026 trên
     * `teacher.css` với một tab mở: ghi đôi cách 3, 10, 30 ms thì 7/40, 39/40, 40/40 lần bản cũ, một
     * dòng `hmr update` cho mỗi lần ghi đôi; 8/8 lần bản cũ còn nguyên sau 20 s. Sau khi đặt dòng
     * dưới: 0/140.
     * `awaitWriteFinish` đi một nhánh trước bộ chặn ấy: nó poll `stat` tới khi kích thước đứng yên
     * `stabilityThreshold` ms, và mọi sự kiện thô đến trong lúc chờ (kể cả lần ghi giữ nguyên kích
     * thước, hay `touch`) đặt lại mốc chờ; rồi báo một lần, đọc bản cuối. Cái giá là HMR chậm thêm
     * chừng ấy. `vitest run` không mở watcher nên không chịu.
     */
    watch: {
      awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 20 },
    },
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
    // Giờ Việt Nam, ghim cứng: test so giờ địa phương mà máy chạy ở UTC thì một bản in giờ UTC
    // cũng xanh (review code pha 5, plan `backlog-tier-1`).
    env: { TZ: "Asia/Ho_Chi_Minh" },
  },
});
