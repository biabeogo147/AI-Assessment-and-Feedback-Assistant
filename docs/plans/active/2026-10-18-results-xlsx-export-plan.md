# Đợt 4, cụm 5 — xuất bảng điểm ra `.xlsx` (việc 20)

## Goal

Làm việc 20 của `2026-10-18-deterministic-batch-master-plan.md`: trên màn 11 (*Kết quả bài kiểm tra
trong lớp*), nút *Xuất bảng điểm (.xlsx)* tải về **một tệp** gồm mã học sinh, họ tên, điểm từng câu và
tổng. Chỉ giáo viên tác giả của đề mới xuất được. Khớp mẫu vnEdu/SMAS khi có tệp mẫu thật; tới lúc ấy
dùng một bảng phẳng một dòng đầu.

## Scope

- **Trong phạm vi:**
  - phụ thuộc `openpyxl` trong `services/be/pyproject.toml`;
  - `be/results_export.py`: dựng workbook từ dữ liệu, hàm thuần;
  - `GET /api/teacher/classes/{class_id}/assessments/{assessment_id}/results.xlsx` trong
    `be/teacher_reads.py`, dùng chung cửa `_paper_in_class` (tác giả đề, chủ lớp, lần phát hành chưa
    thu hồi);
  - FE: nút trên đầu màn 11, tải tệp qua `fetch` vì header actor không đi theo một link thường;
  - test BE đọc lại tệp bằng `openpyxl`; vitest cho nút;
  - hậu ký ADR-22 (*chỉ tác giả xuất*).
- **Ngoài phạm vi:** khớp đúng mẫu vnEdu/SMAS: chưa có tệp mẫu thật.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `services/be/pyproject.toml` | `openpyxl` |
| `services/be/src/be/results_export.py` (mới), `teacher_reads.py` | dựng tệp, route |
| `services/be/tests/test_results_export.py` (mới) | test BE |
| `services/fe/src/api.ts`, `screens/teacher/ClassResults.tsx`, `teacher.css`, `teacher.test.tsx` | FE |
| `docs/decisions/adr-22-*`, `docs/overview/teacher-surface.md` | tài liệu |

## Ordered Tasks

### Pha 1 — BE
- [x] 1. `openpyxl>=3.1` vào `dependencies` của BE.
- [x] 2. Tệp có một trang tính, mang tên lớp. Dòng 1 là đầu cột: *Mã học sinh*, *Họ tên*, *Câu 1*…*Câu N*,
  *Tổng*. Mỗi học sinh của lớp một dòng, theo mã học sinh:
  - em chưa nộp thì các ô điểm **để trống**, không ghi 0: trống và 0 là hai sự thật khác nhau;
  - điểm là số (1 / 0,5 / 0, ADR-16), tổng là tổng trên số câu.
  Tên tệp ghi tên đề và tên lớp; `Content-Disposition` có `filename*` UTF-8.
- [x] 3. Test: đủ cột; đúng điểm; em chưa nộp để trống; người khác 404; lần phát hành đã thu hồi 404.

### Pha 2 — FE
- [x] 4. Nút *Xuất bảng điểm (.xlsx)* trên đầu màn 11, theo artboard 11 (`205:1000`). Tải xong thì trình
  duyệt lưu tệp; lỗi thì câu của BE hiện dưới đầu màn.
- [x] 5. Vitest; chụp, đo so với artboard 11; subagent chấm.

### Pha 3 — đóng
- [x] 6. Hậu ký ADR-22, `teacher-surface.md`; roadmap việc 20 *Xong*; tick plan tổng; plan sang
  `completed/`.

## Decision Records

### Decision 1: em chưa nộp để trống, không ghi 0
options considered: bỏ dòng; ghi 0; để trống.
selected option: một dòng mỗi học sinh của lớp, ô điểm để trống khi em chưa nộp.
reason: bảng điểm của một lớp phải đủ tên để giáo viên nhập lên sổ; ghi 0 là nói em ấy làm bài và
sai hết, một điều không xảy ra.

## Validation Checks

| Kiểm | Lệnh |
| --- | --- |
| Python, repo checks | `.\dev.ps1 test`, `.\dev.ps1 check` |
| Postgres | `pytest services/be/tests --postgres-url=…/aiafa_test` |
| FE | `.\dev.ps1 typecheck`, vitest; Chrome headless + subagent chấm |
| Tệp thật | mở tệp tải về bằng `openpyxl`, soát từng ô |

## Status

- 18/10/2026: plan mở.
- Pha 1: `be/results_export.py` (hàm thuần), route `results_xlsx` trong `teacher_reads.py`. Review pha 1,
  sửa:
  - **chèn công thức**: họ tên hay mã mở đầu bằng `=`, `+`, `-`, `@` ghi thành chữ có dấu nháy ẩn,
    vì openpyxl ghi `"=…"` thành công thức;
  - tên tệp ASCII bỏ dấu và thay ký tự lạ (một `"` hay xuống dòng trong tên đề từng phá header), và
    `filename*` mã hoá cả `/`;
  - câu không có dòng sổ điểm để trống, không 0;
  - tên trang tính bỏ dấu nháy ở hai đầu.

  8 test, xanh trên sqlite và `aiafa_test`; có test thứ tự theo mã thật sự, và test người có lớp
  riêng vẫn 404.
- Pha 2: nút trên đầu màn 11 (179 × 40 ở (1221, 66), Figma 180 × 40 ở (1220, 66)); `api.download` tải
  qua `fetch` có header actor. Review FE, sửa:
  - `download` đặt sau `silent`, không chen giữa JSDoc của `formHeaders`;
  - phần đọc lỗi gộp thành `refusal()` cho `call`, `silent`, `download`;
  - thu hồi URL của blob sau một nhịp;
  - giải mã tên hỏng thì dùng tên dự phòng;
  - lời từ chối có kiểu (`.board > .refused`, 11, `answer/incorrect`).

  Figma: artboard mới `11b · Xuất bảng điểm bị từ chối` (`705:4950`). Tệp thật tải từ DB dev, đọc
  lại bằng `openpyxl`: đủ đầu cột, điểm từng câu, tổng, hai em chưa nộp để trống. Vite từng phục vụ
  `teacher.css` cũ hơn đĩa một lần sửa (watcher bỏ lỡ một lần ghi); chạm file thì đọc lại. 3 vitest.
- Pha 3, đóng plan 18/10/2026: hậu ký ADR-22, `teacher-surface.md`; roadmap việc 20 *Xong*.
