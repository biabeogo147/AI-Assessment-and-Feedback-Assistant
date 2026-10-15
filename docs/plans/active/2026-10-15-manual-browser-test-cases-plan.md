# Bộ ca thử tay cố định trên trình duyệt

## Goal

Mỗi lần thử tay tới nay là một ca mới gõ ngẫu hứng: không so được chất lượng giữa hai lần chạy, và
không có gì cố định để cho người khác thấy độ tốt của dự án. Plan này dựng `docs/testing/`: một bộ
**14 case cố định**, mỗi trường hợp đúng một case, lời chat như giáo viên thật, nhánh rẽ lường trước,
tiêu chí đạt quan sát được trên màn hình -- rồi chạy một vòng làm mốc.

Người dùng chốt 15/10/2026: thư mục `docs/testing/`, file kịch bản cũ dời vào đó (AGENTS.md cấm hai
tài liệu song song cho một chủ đề); mỗi case một subagent viết để lời chat tự nhiên nhất; phủ bốn
nhóm -- ra đề bằng chat, duyệt và phát hành, tra lớp và kết quả, tài liệu và độ bền; viết xong chạy
một vòng trên trình duyệt (gpt-4o-mini) rồi mới đóng plan.

## Scope

Chỉ tài liệu. Lỗi **sản phẩm** lộ ra lúc chạy mốc được ghi biên bản và `backlog.md`, không sửa code
trong plan này. Lỗi của **case** (tiêu chí sai, lời chat dẫn sai) thì sửa case.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `docs/testing/huong-dan.md` | Chuẩn bị, luật soi mọi lượt Kriky, mẫu case, cách ghi kết quả |
| `docs/testing/kich-ban-thu-tay-giao-vien.md` | File cũ (dời từ `docs/`), giữ vai soi lỗi giao diện |
| `docs/testing/cases/NN-<slug>.md` | 14 case |
| `docs/testing/ket-qua/<ngày>-<commit>.md` | Biên bản lần chạy mốc |
| `AGENTS.md` | Hàng ownership trỏ `docs/testing/` (sửa tại chỗ, không thêm dòng) |
| `docs/plans/backlog.md` | Lỗi sản phẩm lộ ra lúc chạy mốc |

Tên `README.md` bị loại: AGENTS.md bắt README tiếng Anh, còn tài liệu `docs/` là tiếng Việt.

## Ordered Tasks

### Đợt 1 -- khung
- [x] 1. Plan vào repo; `git mv` file kịch bản cũ vào `docs/testing/`; hàng ownership trong
      `AGENTS.md`. Comment lịch sử trong `tools/check_contract.py` và các plan đã đóng giữ nguyên.
- [x] 2. `docs/testing/huong-dan.md`: chuẩn bị (db-reset, seed, lớp 12B, tệp SGK, tệp scan), bảy luật
      và hai luật khối bước (dời từ file cũ), mẫu case bảy mục, cách ghi `ket-qua/`.

### Đợt 2 -- viết case
- [x] 3. 14 subagent, mỗi case một con, hai đợt 7 song song; mỗi con chỉ ghi file case của nó.
- [x] 4. Đọc cả bộ: thống nhất mẫu, bỏ trùng, sửa tiêu chí sai so với code; mục A3, B2, B3, H của file
      cũ thành một dòng trỏ sang case mới.
- [x] 5. Một subagent review cả bộ đối chiếu code thật; sửa; commit.

### Đợt 3 -- chạy mốc
- [ ] 6. Báo số lượt model và chi phí ước tính; xin phép `db-reset`, khởi động lại BE/AGENT, gọi
      gpt-4o-mini.
- [ ] 7. Chạy 14 case trên Chrome, gõ đúng nguyên văn; ghi biên bản `ket-qua/`.
- [ ] 8. Đóng plan.

## Validation Checks

- `.\dev.ps1 check` xanh -- `check_no_document_repeats_itself` quét cả `docs/testing/`.
- Không còn chỗ nào trỏ `docs/kich-ban-thu-tay-giao-vien.md` ngoài plan đã đóng và comment lịch sử.
- Đủ 14 file case, mỗi file đủ bảy mục của mẫu.
- Biên bản mốc có đủ 14 dòng kết quả, kèm nguyên văn câu Kriky.

## Status

Mở 15/10/2026.

**Đợt 1–2 xong.** 14 case viết bởi 14 subagent. Đọc chéo: tên bước chấm theo tên **khi lượt xong**
(FE đọc lại database và đặt tên theo `STEP_TITLE`; bước đọc sách thành `Một bước nữa`) — ghi một lần
ở `huong-dan.md`. Case 13 đổi kỳ vọng: PDF chụp lại có chữ được OCR và lên *sẵn sàng*; *Không đọc
được chữ* chỉ còn cho trang không chữ (G8 của file cũ sửa theo). Review: bỏ cụm *"ko cần sách"* ở
case 02, 08 (chữ "sách" mở thư viện dù phủ định); nhãn `Theo:` so với `labels` thật chứ không với tên
in sách; case 05, 10 tìm đề theo tên chứ không theo "đề mới nhất"; 11, 12 chạy trước 09–10 vì bản
phát hành đã thu hồi vẫn được `list_assessment` liệt kê. Lỗ sản phẩm subagent đọc ra từ code — plan
soạn model tự nêu sau một lời xin sửa dàn ý vẫn qua cổng với dàn ý cũ; `list_assessment` không lọc
bản đã thu hồi; lý do của bước ✕ lộ tên tool; một `call_tool` không tên làm lượt lùi về mock (nghi là
gốc của `tra-lop-ket-qua` 2/6) — chờ đối chiếu ở lượt chạy mốc rồi mới vào `backlog.md`.
