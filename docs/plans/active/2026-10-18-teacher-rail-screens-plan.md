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
| `services/fe/index.html` (font), `src/api.ts`, `App.tsx`, `screens/teacher/Chat.tsx` (khe `view`), `Rail.tsx`, `Editing.tsx` (prop `title`) | khung, route, rail |
| `services/fe/src/screens/teacher/Board.tsx`, `Classes.tsx`, `ClassDetail.tsx`, `ClassResults.tsx`, `StudentWork.tsx`, `Papers.tsx`, `Bank.tsx` (mới), `teacher.css` | phần chung của các màn, sáu màn |
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
- [x] 4. `Chat` nhận `view`: có `view` thì cột giữa vẽ màn ấy, không tải lượt chat, không composer;
  rail giữ nguyên. Rail: bốn mục là nút, mục khớp route sáng lên (`Rail destination` *đang chọn*).
- [x] 5. Route: `/teacher/theo-doi`, `/teacher/lop`, `/teacher/lop/{id}`, `/teacher/lop/{id}/de/{aid}`,
  `/teacher/lop/{id}/de/{aid}/hs/{sid}`, `/teacher/de-kiem-tra`, `/teacher/ngan-hang`,
  `/teacher/ngan-hang/{bid}`.
- [x] 6. Màn 9 (bảng lớp, ba cột tiến độ có popover theo đề, lớp không đề đang mở ghi *"—"*) và
  màn 10 (hai bảng; không có cột tên đăng nhập, nút thêm học sinh, đặt lại mật khẩu). Đo so với
  artboard, chụp, subagent chấm.

### Pha 3 — màn 21 và 11
- [x] 7. Màn 21: bảng đề, nhãn trạng thái, lớp, mốc giờ hai dòng, nút *Xem kết quả* / *Mở đoạn chat*.
  *Xem kết quả* của đề phát hành cho nhiều lớp mở lớp đầu đã qua giờ mở (Decision 4).
- [x] 8. Màn 11: bốn thẻ số, biểu đồ cột phân bố, bảng bài làm (sắp theo điểm giảm dần), không nút
  xuất (việc 20).

### Pha 4 — màn 23, 22, 22b
- [x] 9. Màn 23: bốn thẻ số, bảng câu.
- [x] 10. Màn 22: bảng ngân hàng; màn 22b: panel phải sửa một câu ngân hàng (ba tầng thu gọn như thẻ
  đang sửa), *Huỷ* / *Lưu*, dòng chú thích chân panel.
- [x] 11. Vitest cho từng màn; chụp, đo, subagent chấm.

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
- Pha 2: rail dẫn đi thật; `Chat` có khe `view`; màn 9 và 10. Đo trên Chrome headless: tiêu đề
  (300, 32), bảng y 111,8 (Figma 112), đầu bảng 50,8 (50), hàng 44,6 (44 + vạch), popover (769, 202)
  300 × 68 (Figma 770, 201, 300 × 70). Thời điểm in theo `moment()` của app (*"16:20 · 17/10"*), không
  theo chữ *"hôm nay"* của Figma. Font IBM Plex Mono cho mã học sinh nạp thêm từ Google Fonts. Figma
  artboard 10: dòng phụ bỏ *năm học* (`I183:923;175:756`), *Đã đóng* → *Đã kết thúc* (`184:966`).
- Pha 2, 3, 4 gộp làm **một commit FE** (review pha 2): `boardFor` ban đầu chỉ bắt hai route, nên ba
  đích đến của rail và hàng đề trên màn 10 dẫn vào đoạn chat mới nhất. Các màn 11, 21, 22, 22b, 23 đã
  viết xong lúc ấy, nên gắn đủ route một lần thay vì để nút dẫn vào một màn sai. *Bảng theo dõi* tới
  việc 19 chỉ có đầu trang. Sửa thêm theo review: đích đến có hover; `Chat` không tô hay kéo về một
  đoạn chat khi một lượt chạy xong lúc giáo viên đã sang màn rail (`viewingNow`); lỗi của rail hiện ở
  màn rail; đầu bảng canh đáy; `›` canh phải; số trong popover 14; popover mở cả bằng focus; tên lớp
  theo khối có chữ *Lớp*, tên tự đặt giữ nguyên (*"Ôn thi HSG 12"*); crumb cách tiêu đề 8, tiêu đề mục
  cách bảng 8; cột mã học sinh đứng đúng chỗ Figma.
- Màn 11, 22b, 23 đo trên Chrome headless, dữ liệu dev thật: bốn thẻ số (300, 138) 244 × 90, biểu đồ
  (828, 138) 572 × 196, panel 22b x 1020 rộng 420 -- đúng Figma. Dòng phụ màn 11 thêm *"thang N điểm"*
  (ADR-16: điểm là tổng trên số câu, không trên 10); Figma chưa có chữ này.
- Review FE cuối, sửa: lượt chạy xong khi giáo viên đã sang màn rail chỉ đọc lại danh sách đoạn chat,
  không đánh dấu *đã tải* (trước đó quay lại đoạn ấy ra màn trắng); class `cell-muted`/`cell-faint`
  thay `.muted`/`.faint` của `tokens.css` (ô *"—"* từng in cỡ caption); BE gửi **mã chặng** `phase`
  cạnh nhãn, FE tô màu và ẩn *"chữa tới"* theo mã; đề chưa tới giờ mở trên màn 10 không bấm được;
  `distribution` còn N ô như artboard 11; chênh lệch trung bình – trung vị tính từ hai số đang in;
  màn 23 dùng `note` của BE (cùng bảng với màn 11), bỏ bảng chữ riêng ở FE; số 0 trên biểu đồ không
  in; bảng cuối kéo tới đáy; tên đề màn 21 cắt một dòng; popover bóng 0 8 24 / 14%; crumb hai dấu
  cách. Panel 22b dùng **chung bề rộng** với panel đề (420): cố ý, một câu sửa ở hai nơi theo cùng
  một khung. Figma: artboard 10 cột trạng thái rộng 150 cho thẳng đầu cột (`184:952`, `184:959`,
  `184:966`); 11 dòng phụ thêm *"thang 10 điểm"* (`I205:1049;175:756`); 22b đầu các tầng in hoa
  (`I666:6091;531:141/146/152`), hàng danh sách ôm nội dung; 23 dòng phụ *"đã chữa xong"*
  (`I656:4142;175:762`), component `Answer row` (`656:4080`) ôm nội dung, bỏ `›`.
- Chấm ảnh sau review: chữ in hoa của đầu bảng, nhãn thẻ số, đầu biểu đồ, đầu popover giãn 4% như
  Figma; hàng 45 (màn 9, 10, 11), 47 (21, 22), 62 (23), đầu bảng dòng 15 -- `min-height` tính cả viền
  trên nên 44 từng ra 44,6, và Figma dùng dòng 1,5; hàng màn 21 có ô *"Mở … / chữa tới …"* vẫn 47 (đệm
  dọc 4, như artboard), thử bằng dữ liệu chặn qua CDP vì DB dev không có ca này; cột biểu đồ bo đủ bốn
  góc; dấu sắp xếp về *"▾"*. Figma: artboard 10 đầu bảng đề 40 → 35 (`197:1000`), component popover
  (`665:62`) ghi *"HỌC SINH CHƯA NỘP BÀI"* như artboard. **Chưa sửa, để hỏi:** thẻ sửa ba tầng dùng
  chung với panel đề lệch Figma `531:181` (gap 8 / đầu tầng 17, Figma 6 / 15) -- có từ trước việc 18,
  sửa thì panel đề đổi theo.
- Chấm ảnh lượt hai: 35/50 của đầu bảng Figma gồm viền trong của thẻ, nên đệm trên 9; hàng ngân hàng
  dòng 1,5 (hai dòng 67 như 22b); chữ đầu cột lấn 10 vào khe cột về phía không canh, vì trình duyệt
  dựng *"HỌC SINH NỘP BÀI"* rộng 110,4 trong cột 110 (Figma 108). Figma: đầu popover giãn 4%, component
  `665:63` về cỡ 11 như bản dùng.
