# Plan — kịch bản thử tay đầu-cuối, lặp tới khi suôn

## Goal

Một kịch bản thử tay trên trình duyệt đi **toàn bộ luồng**: giáo viên đăng nhập, tạo học sinh, soạn và
phát hành đề với Kriky, học sinh làm hai pha, giáo viên đọc bảng điểm của cả lớp. Kịch bản được chạy
thật và sửa lặp lại tới khi một vòng đi hết mà không phải sửa chữ nào. Kết quả ở một file riêng trong
`docs/testing/ket-qua/`.

## Scope

- Database dev **giữ nguyên**, không `db-reset`; mỗi vòng mang một mã vòng (`V1`, `V2`…) gắn vào tên
  học sinh và tên đề.
- Kriky chạy **model thật** (`claude-haiku-5-5`) mọi vòng; chi phí ghi trong biên bản.
- Ngoài: `docs/report/`, `services/agent`, `services/document`; sửa code sản phẩm (lỗi tìm thấy ghi
  lại, lỗi chặn luồng thì hỏi người dùng).

## Files

- Viết lại `docs/testing/kich-ban-thu-tay-giao-vien.md`.
- Dời biên bản cũ trong file ấy sang `docs/testing/ket-qua/2026-10-06-kich-ban-giao-vien.md` và
  `2026-10-07-kich-ban-giao-vien.md`.
- Mới `docs/testing/ket-qua/2026-10-20-<commit>-dau-cuoi-claude-haiku-5-5.md`.
- Sửa `docs/testing/huong-dan.md`, `docs/plans/backlog.md`.

## Ordered Tasks

- [ ] Dời biên bản cũ; viết bản 1 của kịch bản theo code.
- [ ] Khởi động `be`, `agent` (model thật), `fe`.
- [ ] Vòng 1…n: chạy trên trình duyệt, xếp mỗi chỗ vấp (kịch bản / sản phẩm / Figma), sửa kịch bản.
- [ ] Vòng cuối đi hết không sửa; subagent review; sửa theo review.
- [ ] Biên bản kết quả; `huong-dan.md`; backlog.

## Validation Checks

- Vòng cuối: tám chặng, từ đăng nhập tới bảng điểm của đề có đủ học sinh của vòng.
- `.xlsx` bảng điểm khớp màn kết quả.
- `.\dev.ps1 check` xanh.

## Status

Đang làm, từ 20/10/2026.
