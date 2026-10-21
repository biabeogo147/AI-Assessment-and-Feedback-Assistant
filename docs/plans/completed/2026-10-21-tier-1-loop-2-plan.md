# Plan — Tier 1, vòng 2: hai dòng còn lại sau vòng 1

- **Mở:** 21/10/2026 · **Đóng:** 21/10/2026

## Context

Vòng 1 (`completed/2026-10-21-tier-1-loop-1-plan.md`) xong chín dòng. Review của vòng ấy để lại hai
dòng Tier 1, đều có từ trước:

| # | Việc | Hướng |
|---|---|---|
| 1 | Thanh kéo `.split-handle` kẹt ở trạng thái đang kéo khi pointer bị huỷ. `Rail.tsx` không có `onPointerCancel` / `onLostPointerCapture`, nên sau một cử chỉ hệ thống hay khi mất focus thì `dragging` còn `true`, và lần rê chuột sau, không bấm, vẫn đổi chiều cao | Làm ngay |
| 2 | Tên tầng của thẻ sửa in hoa (`text-transform: uppercase`), Figma 14 và 22b viết thường. Nhãn *Câu N* trên Figma cũng to và đậm hơn | Cần người dùng chọn bên: dừng và hỏi |

Ràng buộc thường trực như vòng 1: không đụng `docs/report/`; không stage hai dòng
`# TODO: Cần xem lại`; mọi đổi FE thì chụp ảnh trình duyệt và subagent so với Figma; chạy
`.\dev.ps1 check` và `test` trước commit; commit sau vòng.

## Pha 1 — split-handle khi pointer bị huỷ (TDD)

- Test trước, trong `teacher.test.tsx` cạnh test *"bấm thanh kéo mà chưa rê…"*:
  - bấm, rồi `pointercancel`, rồi rê mà không bấm: chiều cao không đổi;
  - cùng ca đó với `lostpointercapture`.
- Sửa `Rail.tsx`: một hàm kết thúc cú kéo, dùng chung cho `pointerup`, `pointercancel` và
  `lostpointercapture`. Hàm ghi chiều cao đang có (`wanted`) như `pointerup` vẫn ghi. Cú kéo bị huỷ
  giữa chừng thì giữ chỗ đã kéo tới, không bật về.
- Thử tay: kéo bằng chuột thật vẫn đúng như vòng 1.

## Pha 2 — tên tầng in hoa

- Hỏi người dùng bên nào đúng.
- Làm theo câu trả lời, ở cả code lẫn Figma. Đo lại ở panel đề và 22b.

## Cuối vòng

- Subagent review code và ảnh.
- Gỡ hai dòng khỏi backlog md và artifact, rồi đóng plan.
- Check và test xanh, rồi commit.

## Kết quả (21/10/2026)

- **Pha 1:** `Rail.tsx` có một `endDrag` dùng chung cho `pointerup`, `pointercancel` và
  `lostpointercapture`. Test `it.each` đỏ với code cũ, xanh với code mới. Trên trình duyệt thật:
  - huỷ giữa cú kéo thì ngăn dừng ở 248 và lưu 248, rê thêm 100px không đổi gì;
  - kéo bằng chuột thật vẫn đúng: 248 → 207, lưu 207.
- **Pha 2:** người dùng chọn *code theo Figma*.
  - Component `531:181` viết thường tên tầng. Artboard 22b có một ghi đè `UPPER`, đã gỡ trên Figma.
  - Code bỏ `text-transform: uppercase`. *Câu N* của thẻ đang sửa nay cỡ 13, đậm 600, màu `ink`,
    như Figma 14.
  - Kịch bản thử tay giáo viên và `teacher-surface.md` đổi tên tầng theo.
- **Thử tay lộ thêm hai lệch có từ trước**, ghi Tier 1 cho vòng 3:
  - hàng đầu thẻ cao 23 (Figma 16 hay 19), nút *Huỷ / Lưu* cao 28 (Figma 24);
  - tầng *Cách giải*: nhãn trường in hoa và đặt cạnh ô; Figma vẽ nút *Xoá* ở đúng 2 cách giải, trái
    ADR-18.
- **Review của subagent:**
  - tài liệu còn ghi tên tầng in hoa: đã sửa;
  - một stub `hasPointerCapture` thừa: đã bỏ;
  - thanh kéo còn kẹt nếu bị gỡ khỏi DOM giữa cú kéo: Tier 1, vòng 3.
