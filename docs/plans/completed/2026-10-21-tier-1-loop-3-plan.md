# Plan — Tier 1, vòng 3: ba dòng thử tay và review vòng 2 để lại

- **Mở:** 21/10/2026 · **Đóng:** 21/10/2026

## Context

Vòng 2 (`completed/2026-10-21-tier-1-loop-2-plan.md`) để lại ba dòng Tier 1. Cả ba đều có từ trước;
người dùng đã chốt *code theo Figma* cho thẻ sửa câu (21/10/2026).

| # | Việc | Hướng |
|---|---|---|
| 1 | Thanh kéo kẹt nếu bị gỡ khỏi DOM giữa cú kéo: `lostpointercapture` rơi vào `document`, `dragging` còn `true` | `onPointerMove`: `event.buttons === 0` thì kết thúc cú kéo. TDD |
| 2 | Thẻ câu cao hơn Figma: `.qcard .top` min-height 23, Figma 16 (thẻ đang sửa) và 19 (thẻ đọc); nút *Huỷ / Lưu* 28, Figma 24 | CSS theo Figma, đo lại ở panel đề và 22b |
| 3 | Tầng *Cách giải*: nhãn trường in hoa, đặt cạnh ô; Figma viết thường, nhãn nằm trên ô. Figma vẽ *Xoá* ở đúng 2 cách giải, trái ADR-18 | Code theo Figma cho chữ và bố cục; Figma theo ADR-18 cho nút *Xoá* |

Ràng buộc thường trực như hai vòng trước.

## Pha 1 — thanh kéo (TDD)

- Test: bấm, rê, rồi một `pointermove` với `buttons: 0` (nút đã nhả ở chỗ React không nghe được).
  Cú kéo kết thúc, chiều cao được ghi, và lần rê sau không đổi gì.
- Sửa `Rail.tsx`: đầu `onPointerMove`, `buttons === 0` thì gọi `endDrag`, rồi thoát.

## Pha 2 — chiều cao hàng đầu và hàng nút

- Đọc CSS của `.qcard .top`, `.edit-actions` và các nút trong đó. Xem vì sao có 23 và 28 (comment,
  lịch sử).
- Đặt theo số Figma: thẻ đang sửa 16, thẻ đọc 19, nút 24 với đệm 11 × 5.
- Đo trên trình duyệt ở panel đề (thẻ đọc, thẻ đang sửa) và ở 22b.

## Pha 3 — tầng Cách giải

- Đọc `Field` và CSS của `.edit-method`. Đổi nhãn trường sang viết thường, đặt **trên** ô, theo
  `method` của component `531:181`.
- Figma: ẩn nút *Xoá* trong 22b và trong component khi có đúng 2 cách giải. Vẽ thêm một trạng thái
  có 3 cách, nếu component chưa có.
- Đo và chụp ảnh ở 22b và ở panel đề.

## Cuối vòng

- Subagent review code và ảnh.
- Gỡ các dòng đã xong khỏi backlog md và artifact, rồi đóng plan.
- Check và test xanh, rồi commit.
- Dừng sau vòng 4 nếu Tier 1 vẫn còn.

## Kết quả (21/10/2026)

- **Pha 1:** `onPointerMove` gặp `buttons === 0` thì kết thúc cú kéo. Thêm một effect dọn cú kéo khi
  thanh rời DOM: review chỉ ra rằng giữ chuột từ chỗ khác rồi rê qua thanh mới cho `buttons` 1. Hai
  test mới đỏ với code cũ. Các test kéo cũ thêm `buttons: 1`, vì chuột thật luôn bấm khi kéo. Kéo bằng
  chuột thật vẫn đúng: 207 → 247.
- **Pha 2:** đo trên trình duyệt, khớp Figma 14 và 22b.
  - Thẻ đọc: `top` 19.
  - Thẻ đang sửa: `top` ở 15/17 và cao 16. Đệm 14/16, vì Figma tính viền vào layout.
  - Nút 24.
  - Ô nhập: một dòng 28, hai dòng 42 (dòng 14).
- **Pha 3:** nhãn trường viết thường, như mọi nhãn của component. *Tên cách giải N* nằm trên ô.
  - Số đo của `method` khớp 22b: nhãn 6, ô 24, nhãn lời giải 56, ô 74.
  - Figma ẩn nút *Xoá* ở 2 cách giải (ADR-18).
  - Bước vẽ variant 3 cách giải **chưa làm**, đã chuyển sang vòng 4.
- **Tái hiện được lỗi Vite bản cũ (Tier 3 P8):** hai lần sửa `teacher.css` gửi song song thì module
  Vite thiếu lần sửa thứ hai, `?direct` thì đủ. Lỗi về lại Tier 1 cho vòng 4.
- **Review của subagent:**
  - thiếu variant 3 cách giải: vòng 4;
  - câu chữ dòng Vite trong backlog tự mâu thuẫn: đã sửa;
  - sàn `.qcard .top` cũng đổi thẻ ô câu màn 17: comment đã sửa, việc đo chuyển sang vòng 4;
  - khe kẹt khi thanh rời DOM: đã sửa kèm test.
  - Thêm: gỡ một quy tắc `.qcard.editing .top` trùng lặp, mang comment sai.
- **Kiểm:** vitest 352 xanh, tsc xanh.
