# Đợt 4, cụm 2 — các màn của rail giáo viên (việc 18)

## Goal

Làm việc 18 của `2026-10-18-deterministic-batch-master-plan.md`: bốn mục của rail (*Bảng theo dõi*,
*Danh sách lớp học*, *Các bài kiểm tra*, *Ngân hàng câu hỏi*) dẫn tới màn thật, cùng các màn con: kết
quả một đề trong một lớp, bài làm của một học sinh, sửa một câu trong ngân hàng. Figma đã duyệt
18/10/2026, trang `Screen — Teacher` `12:2`:
- `9 · Danh sách lớp học` `180:753` (có `Class progress popover` `665:62`);
- `10 · Chi tiết lớp` `183:874`;
- `11 · Kết quả bài kiểm tra trong lớp` `205:1000`;
- `21 · Các bài kiểm tra` `655:4929`;
- `22 · Ngân hàng câu hỏi` `655:5226`, `22b · Ngân hàng câu hỏi — sửa một câu` `666:5816`;
- `23 · Bài làm của một học sinh` `656:4089`.

## Scope

- **Trong phạm vi:**
  - BE: một module đọc mới `be/teacher_reads.py` (lớp, chi tiết lớp, danh sách đề, kết quả một đề
    trong một lớp, bài làm một học sinh, ngân hàng) và đường sửa một câu ngân hàng;
  - FE: rail dẫn đi đâu thật, mục đang mở sáng lên; sáu màn trên; route cho từng màn;
  - *Bảng theo dõi*: route và đầu trang; phần thống kê và hàng đợi là việc 19.
- **Ngoài phạm vi** (ghi rõ để không ai tưởng là sót):
  - cột *Tên đăng nhập*, nút *Đặt lại mật khẩu*, *Thêm học sinh* trên màn 10 — việc 22;
  - nút *Xuất bảng điểm (.xlsx)* trên màn 11 — việc 20;
  - nút *Tạo lớp* trên màn 9 — chưa việc nào nhận; ghi backlog;
  - *Thêm câu từ ngân hàng* vào đề — việc 17.
- Không đổi schema.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `services/be/src/be/teacher_reads.py` (mới), `main.py`, `remediation.py` (nhận `attempt_state`), `student_routes.py`, `question_bank.py` | BE đọc, sửa câu ngân hàng |
| `services/be/tests/test_teacher_rail_reads.py` (mới) | test BE |
| `services/fe/src/api.ts`, `App.tsx`, `screens/teacher/Chat.tsx` (khe `view`), `Rail.tsx` | khung, route, rail |
| `services/fe/src/screens/teacher/Classes.tsx`, `ClassDetail.tsx`, `ClassResults.tsx`, `StudentWork.tsx`, `Papers.tsx`, `Bank.tsx` (mới), `teacher.css` | sáu màn |
| `services/fe/src/teacher.test.tsx` | vitest |
| `docs/overview/teacher-surface.md`, `docs/overview/data-model.md` (nếu cần), ADR hậu ký | tài liệu |

## Ordered Tasks

### Pha 1 — BE đọc và sửa câu ngân hàng
- [x] 1. `attempt_state` (nay `student_routes._attempt_state`) dời sang `be/remediation.py`, public;
  `student_routes` dùng lại nó. Không đổi hành vi.
- [x] 2. `be/teacher_reads.py`, mọi route lọc theo giáo viên đang hỏi (ADR-22: của người khác là 404):
  - `GET /teacher/classes`: mỗi lớp tên, sĩ số, *khối / môn* (Decision 1), số đề đang mở (Decision
    2), và ba con số tiến độ cộng trên mọi đề đang mở, kèm số theo từng đề cho popover;
  - `GET /teacher/classes/{id}`: tên, sĩ số, khối / môn, các đề đã phát hành cho lớp (tên, trạng
    thái theo giờ BE, mở lúc, đóng lúc, đã nộp / sĩ số), danh sách học sinh (họ tên, mã);
  - `GET /teacher/assessments`: mọi đề của giáo viên, trạng thái theo nhãn của artboard 21 (Decision
    3), các lớp đang giữ, mốc mở và hạn chữa, đường mở (`kết quả` hay `đoạn chat`);
  - `GET /teacher/classes/{cid}/assessments/{aid}/results`: cao nhất, trung bình, trung vị, thấp
    nhất, phân bố điểm (theo từng mức điểm nguyên), và mỗi bài đã nộp một dòng: họ tên, điểm, số câu
    đúng ngay, thời gian làm, nộp lúc, ghi chú (bài đang ở đâu của giai đoạn 2: *Còn câu chữa*, *Đã
    chữa xong*, *Hết hạn chữa* -- Figma để trống cột này);
  - `GET /teacher/classes/{cid}/assessments/{aid}/students/{sid}`: điểm, đúng ngay lần đầu, lượt
    chữa đã làm, số báo cáo *giải thích chưa rõ*, và mỗi câu: đề, em chọn, đáp án, điểm;
  - `GET /teacher/bank`: mỗi câu đề bài, mục kiến thức (`learning_objective`), khối / môn (của đề gốc);
    `GET /teacher/bank/{id}`: đủ phương án và lời giải;
  - `PATCH /teacher/bank/{id}`: sửa bản trong ngân hàng (đề, phương án, lời giải), kiểm ADR-18 như
    đường sửa câu trong đề. Câu trong đề đã phát hành không đổi (người dùng chốt 18/10, mục 2).
- [x] 3. Test BE cho từng route: số đúng, lọc theo giáo viên, lớp của người khác 404, sửa ngân hàng
  không đụng câu trong đề.

### Pha 2 — khung, rail, màn 9 và 10
- [ ] 4. `Chat` nhận `view`: có `view` thì cột giữa vẽ màn ấy, không tải lượt chat, không composer;
  rail giữ nguyên. Rail: bốn mục là nút, mục khớp route sáng lên (`Rail destination` *đang chọn*).
- [ ] 5. Route: `/teacher/theo-doi`, `/teacher/lop`, `/teacher/lop/{id}`, `/teacher/lop/{id}/de/{aid}`,
  `/teacher/lop/{id}/de/{aid}/hs/{sid}`, `/teacher/de-kiem-tra`, `/teacher/ngan-hang`,
  `/teacher/ngan-hang/{bid}`.
- [ ] 6. Màn 9 (bảng lớp, ba cột tiến độ có popover theo đề, lớp không đề đang mở ghi *"—"*) và
  màn 10 (hai bảng; không có cột tên đăng nhập, nút thêm học sinh, đặt lại mật khẩu). Đo so với
  artboard, chụp, subagent chấm.

### Pha 3 — màn 21 và 11
- [ ] 7. Màn 21: bảng đề, nhãn trạng thái, lớp, mốc giờ hai dòng, nút *Xem kết quả* / *Mở đoạn chat*.
  *Xem kết quả* của đề phát hành cho nhiều lớp mở lớp đầu đã qua giờ mở (Decision 4).
- [ ] 8. Màn 11: bốn thẻ số, biểu đồ cột phân bố, bảng bài làm (sắp theo điểm giảm dần), không nút
  xuất (việc 20).

### Pha 4 — màn 23, 22, 22b
- [ ] 9. Màn 23: bốn thẻ số, bảng câu.
- [ ] 10. Màn 22: bảng ngân hàng; màn 22b: panel phải sửa một câu ngân hàng (ba tầng thu gọn như thẻ
  đang sửa), *Huỷ* / *Lưu*, dòng chú thích chân panel.
- [ ] 11. Vitest cho từng màn; chụp, đo, subagent chấm.

### Pha 5 — đóng
- [ ] 12. `teacher-surface.md` có mục cho các màn rail. Roadmap việc 18 *Xong*; backlog (nút *Tạo
  lớp*); tick plan tổng; plan sang `completed/`.

## Decision Records

### Decision 1: *khối / môn* của một lớp suy từ các đề đã phát hành cho lớp
options considered: thêm cột `grade`, `subject` vào `classes`; suy từ tên lớp (*"12A"* → 12); suy từ
các đề đã phát hành cho lớp; bỏ cột.
selected option: suy từ các đề đã phát hành (chưa thu hồi): các cặp *môn khối* khác nhau, nối bằng
dấu phẩy; lớp chưa nhận đề nào ghi *"—"*.
reason: không đổi schema, không đoán. Tên lớp không chở khối một cách tin được (*"Ôn thi HSG 12"*).
Thêm cột là một ALTER cộng một chỗ nhập liệu mà chưa màn nào có. *Năm học* trên màn 10 không có dữ
liệu nào để suy, nên bỏ, và Figma bỏ cùng.

### Decision 2: *đề đang mở* và ba cột tiến độ
options considered: đề đã phát hành chưa thu hồi; đề đã tới giờ mở và chưa hết hạn chữa.
selected option: đề phát hành cho lớp, chưa thu hồi, đã tới giờ mở và chưa qua hạn chữa. Ba cột cộng
trên các đề ấy, mỗi học sinh một lần mỗi đề: *chưa nộp bài* (không có bài đã nộp), *đã nộp giai đoạn 1*
(đã nộp, `attempt_state` là `cần-chữa`), *xong giai đoạn 2* (`đã-hoàn-thành`). Không đề nào thì ba ô
ghi *"—"*.
reason: đề chưa tới giờ mở thì chưa ai làm được, và đề đã qua hạn chữa thì không còn ai đang làm;
đếm chúng làm cột *chưa nộp bài* phình lên bằng những em không có gì để nộp. `attempt_state` là phép
màn kết quả của học sinh đã dùng, nên hai bên nói cùng một trạng thái.

### Decision 3: nhãn trạng thái của màn 21 do BE dựng
options considered: FE suy nhãn từ `state` và các mốc giờ; BE trả nhãn.
selected option: BE trả nhãn (*Đề trống*, *Đang soạn*, *Chưa duyệt*, *Đã duyệt*, *Chưa tới giờ mở*,
*Đang mở*, *Đang chữa bài*, *Đã kết thúc*) cùng hành động (*kết quả* hay *đoạn chat*).
reason: nhãn phụ thuộc giờ BE so với các mốc phát hành, và luật FE là không màn hình nào quyết một luật
(`services/fe/AGENTS.md`). Đề *đang soạn* là đề còn ô `pending`/`retry`. Một bộ nhãn chặng cho cả màn
10 và 21: màn 10 trên Figma ghi *Đã đóng*, nay là *Đã kết thúc* như màn 21; đề phát hành cho nhiều
lớp lấy chặng đang diễn ra nhất.

### Decision 4: đề phát hành cho nhiều lớp, *Xem kết quả* mở lớp đầu
options considered: một trang chọn lớp; mở lớp đầu theo tên; một dòng mỗi (đề, lớp).
selected option: mở lớp đầu theo tên trong số lớp đã qua giờ mở; màn 11 có link quay về lớp.
reason: artboard 21 vẽ một dòng mỗi đề với *"12A, 12B"*; một trang chọn lớp là một màn chưa thiết kế.

## Validation Checks

| Kiểm | Lệnh |
| --- | --- |
| Python, repo checks | `.\dev.ps1 test`, `.\dev.ps1 check` |
| Postgres | `pytest services/be/tests --postgres-url=…/aiafa_test` cho `test_teacher_reads.py` |
| FE | `.\dev.ps1 typecheck`, vitest |
| Trình duyệt | Chrome headless (CDP) trên dữ liệu seed, subagent chấm ảnh |

## Status

- 18/10/2026: plan mở.
- Pha 1: `be/teacher_reads.py`, 7 test, xanh trên sqlite và `aiafa_test`.
- Subagent review pha 1: tôi đã **ghi đè nhầm** `tests/test_teacher_reads.py` (12 test có sẵn của
  ba đường đọc cũ) -- đã dựng lại nguyên văn từ HEAD, test mới sang `test_teacher_rail_reads.py`. Sửa
  thêm: bài làm lọc theo `Attempt.class_id`; *Xem kết quả* mở lớp đầu đã qua giờ mở; docstring
  `question_bank`; 6 test ca biên. Hai việc chờ người dùng: bản sửa ở ngân hàng mất khi đề gốc được
  bỏ duyệt rồi duyệt lại (`file_approved` ghi đè theo `question_id`); nút *Tạo lớp*.
