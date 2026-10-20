# Plan — BE không đụng vào lời dàn ý của Kriky

- **Mở:** 20/10/2026 · **Đóng:** 20/10/2026
- **Quyết định:** hậu ký 20/10/2026 của ADR-29 và ADR-30.

## Context

Bốn vòng thử tay đầu-cuối 20/10/2026 (`docs/testing/ket-qua/2026-10-20-48919a3-dau-cuoi-claude-haiku-5-5.md`)
trả về 59 dàn ý, cả 59 do hai luật của BE: hình dạng công thức (`outline.validate`, 50 lần) và phép đối
chiếu lời với các mục (`outline.check_message`, 9 lần). 21 lượt dừng ở thông báo hệ thống, một vòng
không qua được bước soạn đề. Người dùng: lời lên khung chat hoàn toàn do Kriky quyết định.

## Việc

- [x] 1. `be/outline.py`: gỡ `check_message` và luật *đúng một cặp `$`*; giữ các luật canh job soạn câu.
- [x] 2. `teacher_chat.outline_turn`: chỉ kiểm các mục; lời trống vẫn trả về.
- [x] 3. Test: gỡ test `check_message` và test công thức lỏng; thêm test lời lệch lên nguyên vẹn, lời
  trống trả về, công thức có chữ được nhận; các test trả về dùng lý do còn sống.
- [x] 4. Hậu ký ADR-29, ADR-30; README `docs/decisions`; `teacher-surface.md`; docstring contracts.
- [x] 5. Thử dàn ý thật trên chương Hàm số (V5–V7, 20/10/2026): hai lượt tới dàn ý, cả hai qua ngay lần
  đầu, 0 lần trả về; mục có công thức kèm chữ, 6/6 câu soạn xong.
- [x] 6. AGENT: prompt dàn ý và mô tả `formulas` thôi đòi *đúng một cặp `$`*, chỉ dặn toán trong cặp
  `$`; comment `propose._unmangled` và `handlers.next_step` thôi nhắc `check_message`.

## Verification

- `.\dev.ps1 check` xanh.
