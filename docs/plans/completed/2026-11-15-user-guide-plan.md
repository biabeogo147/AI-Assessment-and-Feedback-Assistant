# Hướng dẫn sử dụng Kriky (user-guide)

## Goal

Một cuốn PDF hướng dẫn sử dụng cho người dùng cuối, viết bằng LaTeX ở `docs/user-guide/`. Người dùng
tự gửi nó cho giáo viên và học sinh thật đang dùng lab. Cuốn sách có hai phần: Phần I cho giáo viên,
Phần II cho học sinh. Nhận diện lấy từ Kriky (chú dế, màu và phông của app), không theo khuôn báo cáo.
Văn phong ngắn và đơn giản, ưu tiên ảnh chụp có đánh số, bảng và sơ đồ.

## Scope

- Đọc trên màn hình: A4 đứng, có màu, link bấm được.
- Ảnh chụp lại toàn bộ từ app hiện tại, dùng dữ liệu mẫu hư cấu.
- Sơ đồ drawio đặt ở `docs/diagrams/user-guide/`, xuất ra `docs/user-guide/figures/`; check hình canh
  cả cặp này.
- Không đụng tới `docs/report/`.

## Files

- `docs/user-guide/`:
  - `user-guide.tex`, `style.tex`, `config.tex`, `rules.md`;
  - `parts/*.tex`;
  - `screenshots/`;
  - `figures/` kèm `sources.json`;
  - `fonts/` (Be Vietnam Pro, OFL);
  - `user-guide.pdf`.
- `docs/diagrams/user-guide/*.drawio`
- `dev.ps1` (lệnh `user-guide`), `.gitignore`
- `tools/check_contract.py`, `tools/tests/` (check hình canh thêm cặp của hướng dẫn)
- `AGENTS.md` (ownership, luật drawio)

## Ordered Tasks

- [x] Pha 1: kiểm kê màn hình, chốt dàn bài, viết `rules.md`; subagent review
- [x] Pha 2: khung và nhận diện (phông, `style.tex`, bìa, build, check, `AGENTS.md`), trang mẫu;
      subagent review
- [x] Pha 3: dữ liệu mẫu và chụp ảnh; subagent review
- [x] Pha 4: ba sơ đồ, bìa, *Đọc tài liệu này thế nào*, *Làm quen với Kriky*; subagent review
- [x] Pha 5: Phần I, giáo viên; subagent review
- [x] Pha 6: Phần II học sinh, *Tra nhanh*, hoàn thiện; subagent review

## Validation Checks

- `.\dev.ps1 user-guide` sạch: không có `Undefined reference`, `Overfull` hay `Float too large`.
- `.\dev.ps1 check` xanh. Sửa một `.drawio` của hướng dẫn mà không xuất lại thì check phải đỏ.
- Chuyển mọi trang thành PNG rồi xem bằng mắt: số trên ảnh đúng chỗ, chữ ≥ 9pt, không tràn lề.
- Đi lại bằng tay trên app: một việc của giáo viên (soạn đề tới phát hành) và một việc của học sinh
  (làm bài tới chữa bài), theo đúng chữ trong sách.

## Status

Xong 15/11/2026. Mỗi pha đều có một subagent review và đã sửa theo review. Sách dài 61 trang:
`.\dev.ps1 user-guide` sạch (không `Undefined`, `Overfull`, `Missing character`), `.\dev.ps1 check` xanh.
Thử sửa `trang-thai-de.drawio` mà không xuất lại thì check đỏ.

- **Khung:**
  - phông Be Vietnam Pro (OFL) nằm trong `fonts/`;
  - `style.tex` (bìa, trang phần, ô mẹo, ảnh có chấm số, bảng tra), `config.tex`, `rules.md`.
  - Lệnh `.\dev.ps1 user-guide`. Check hình canh thêm cặp `docs/diagrams/user-guide/` ↔ `figures/`,
    kèm 9 test.
- **Ảnh:**
  - 52 ảnh chụp từ app chạy thật với dữ liệu mẫu hư cấu: giáo viên Nguyễn Thu Hà, lớp 12A có 23 em,
    đề "Kiểm tra 15 phút: Đơn điệu và cực trị".
  - Màn học sinh chụp ở cửa sổ 1100px.
  - AGENT chạy trên `gpt-6-luna` theo lựa chọn của người dùng, vì `gpt-4o-mini` treo ở lượt lập dàn ý.
- **Sơ đồ:** ba sơ đồ drawio: vòng đời bài kiểm tra, trạng thái của đề, vòng chữa bài.
- **Nội dung:**
  - đầu sách (đọc thế nào, làm quen);
  - Phần I, 9 chương;
  - Phần II, 5 chương;
  - Tra nhanh.
- **Lộ ra khi làm** (ghi ở `backlog.md` và artifact backlog):
  - lượt soạn đề treo trên `gpt-4o-mini`;
  - đề kẹt khi xoá đoạn chat;
  - lời hứa *thu hồi* mà không có nút;
  - chữ *ADR-18* hiện ra trên màn hình;
  - *Xem kết quả* chỉ mở lớp đầu tiên;
  - cây sách Lớp 12 tập 1 hỏng;
  - chất lượng đề bài model viết;
  - `create_draft` không nhận tên đề;
  - hai chữ *vòng* và *lượt* cho cùng một việc;
  - bài lần đầu không tự nộp;
  - nhãn *Hết hạn làm lại* không hiện;
  - câu *"30 ngày"* trên màn hình mà BE chưa lọc.
- **Chờ người dùng trước khi gửi sách:**
  - tên bản trên bìa và ảnh (`lab-2026.0.4`, chưa có tag);
  - hai địa chỉ lab: `config.tex` còn in đỏ *[cần điền: …]*.
