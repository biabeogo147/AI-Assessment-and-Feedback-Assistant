# Plan — Tier 1, vòng 4 (vòng cuối): ba dòng vòng 3 để lại

- **Mở:** 21/10/2026 · **Đóng:** 21/10/2026

## Context

Vòng 3 (`completed/2026-10-21-tier-1-loop-3-plan.md`) để lại ba dòng Tier 1. Đây là vòng cuối mà luật
chặn của vòng lặp cho phép: còn gì sau vòng này thì dừng và báo người dùng.

| # | Việc | Hướng |
|---|---|---|
| 1 | Vite phục vụ bản cũ: hai lần sửa `teacher.css` gửi song song thì module thiếu lần sửa thứ hai | Theo `systematic-debugging`: tái hiện trước, sửa sau |
| 2 | Figma không còn chỗ vẽ nút *Xoá* của một cách giải | Thêm variant 3 cách giải vào `531:182` |
| 3 | Thẻ ô câu soạn hỏng (màn 17) chưa đo lại sau khi hạ sàn `.qcard .top` | Đo hai trạng thái, so Figma `652:3611` / `652:3623` |

Ràng buộc thường trực như các vòng trước.

## Pha 1 — Vite

- Script ở scratchpad. Ghi hai lần liền vào **cùng** một file CSS nhỏ dưới `services/fe/src`, mỗi lần
  thêm một dấu khác nhau, cách nhau 0–5 ms. Sau đó hỏi lại module bằng `?t=` mới. Lặp N lần, đếm
  số lần thiếu dấu thứ hai.
  - Không cần tab mở trước. Không ra thì lặp lại khi một tab đang mở trang ấy (HMR có client).
  - Không ra sau ~50 lần cho mỗi cách thì ghi số liệu rồi dừng, không sửa mò.
- Ra lỗi thì thử `server.watch.awaitWriteFinish` (hay một sửa khác, theo cái đo được) ở
  `vite.config.ts`, rồi chạy lại script để chứng minh.
- Ghi vào `docs/local-development.md`.

## Pha 2 — variant 3 cách giải trên Figma

- Nhân variant `Tầng=cách giải`, thêm một khối `method` thứ ba và hiện ba nút *Xoá*.
- Đặt property cho variant set sao cho tên variant nói rõ số cách giải. Không làm vỡ các instance
  đang có.

## Pha 3 — thẻ ô câu màn 17

- Dựng hai trạng thái (*Chưa soạn được*, *Đang soạn lại*) bằng dữ liệu mẫu chặn `fetch`. Đo hàng đầu
  và cả thẻ, so Figma. Lệch thì sửa CSS.

## Cuối vòng

- Subagent review code và ảnh. Gỡ dòng đã xong, đóng plan, chạy check và test, commit.
- Tier 1 còn dòng thì **dừng và báo người dùng** (đã hết bốn vòng).

## Kết quả (21/10/2026)

- **Pha 1, Vite.** Tái hiện trên `teacher.css` (file nằm trong module graph) khi có một tab mở: ghi
  đôi cách 3, 10, 30 ms thì 7/40, 39/40, 40/40 lần bản cũ.
  - Mỗi lần ghi đôi chỉ cho một dòng `hmr update`, và bản cũ còn nguyên sau 20 s.
  - Gốc: chokidar 3 bỏ `change` lặp trong 50 ms (`_throttle(EV_CHANGE, path, 50)`), không phát bù.
    Thăm dò 150 lần ngày 21/10 trước đó dùng một file ngoài module graph và hỏi sau khi chờ, nên
    không ra.
  - Sửa: `server.watch.awaitWriteFinish` (100 ms). Sau khi sửa: 0/140, bản đúng về sau 0,12–0,24 s.
  - Thêm một mục chẩn đoán ở `docs/local-development.md`.
- **Pha 2, Figma.** Component set `531:182` thêm property `Số cách giải`. Variant `774:96` có 3 cách
  giải, ba nút *Xoá* hiện; ba variant cũ mang `Số cách giải=2`. Code đã vẽ đúng trạng thái này.
- **Pha 3, thẻ ô câu màn 17.** Đệm 14/16 (Figma tính viền vào layout); chip dòng 14; lời và nút dòng
  20. Khớp artboard 17 từng số: hàng đầu 15/20, lời 43/40, nút 91/40, thẻ 146 (trước 142,3).
- **Review của subagent:** không có lỗi chặn. Comment và tài liệu được sửa cho đúng cơ chế (bộ chặn
  50 ms của chokidar, không riêng Windows), đúng số đo, và có thêm lệnh PowerShell thay cho `touch`.
- **Kiểm:** vitest 352 xanh, tsc xanh.
- **Tier 1 rỗng sau vòng này.**
