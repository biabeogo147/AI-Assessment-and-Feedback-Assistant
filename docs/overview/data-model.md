# Data model

## Mục đích tài liệu

Tài liệu này mô tả **hình dạng dữ liệu BE lưu**: có những bảng nào, mỗi bảng trả lời câu hỏi nghiệp
vụ nào, và vì sao ranh giới giữa chúng nằm ở đó. Nó không mô tả API — API thuộc về
[Architecture](architecture.md) — và không mô tả luật — luật thuộc về `docs/decisions/`.

Nguồn sự thật của schema là `services/be/src/be/models.py`. Tài liệu này giải thích nó; khi hai bên
lệch nhau, code đúng và tài liệu phải sửa.

Được viết **sau** khi schema chạy thật, không phải trước. Một tài liệu schema viết trước khi có bảng
nào là thứ `AGENTS.md` cấm tạo: nó mô tả một hệ thống chưa ai kiểm được.

## Vì sao có database

[ADR-21](../decisions/adr-21-trang-thai-bai-lam-la-ben.md). Hạn pha 2 do giáo viên đặt, tính bằng giờ
hoặc ngày, nên trạng thái bài làm không sống được trong một chỗ có TTL một giờ. Postgres thuộc về BE
và chỉ BE; AGENT không có credential nào và không bao giờ có.

## Mười ba bảng, bốn nhóm

### Nhóm 1 — người và lớp

| Bảng | Giữ gì | Ghi chú |
| --- | --- | --- |
| `classes` | một lớp giáo viên tạo, `teacher_id`, tên | [ADR-13](../decisions/adr-13-lop-va-tai-khoan-hoc-sinh.md) và [ADR-22](../decisions/adr-22-de-co-tac-gia.md): lớp thuộc giáo viên, không thuộc nhà trường. **`name` không unique** — tên lớp không phải định danh |
| `students` | họ tên, mã học sinh, thuộc lớp nào | `student_code` là khoá con người dùng; **không có cột mật khẩu** |
| `teachers` | họ tên, mã giáo viên | |

Chưa có bảng nào cho mật khẩu hay phiên đăng nhập: đợt này dùng header `X-Actor` thay cho đăng nhập,
và lỗ ADR-13 về mật khẩu ban đầu **vẫn nguyên**.

### Nhóm 2 — nội dung đề

| Bảng | Giữ gì | Ghi chú |
| --- | --- | --- |
| `assessments` | `teacher_id`, tiêu đề, môn, khối, `state` | `state` là vòng đời ADR-01 với **bốn** giá trị: `empty` → `has_questions` → `approved` → `published`. `teacher_id` là tác giả (ADR-22) |
| `questions` | đề bài, thứ tự, mục tiêu học tập | `order_index` là số câu học sinh nhìn thấy |
| `options` | nhãn, nội dung, `is_correct`, `error_label` | `error_label` là ánh xạ nhiễu→lỗi của ADR-18, `null` ở đúng một dòng mỗi câu |
| `methods` | các cách giải | ADR-18 đòi nhiều hơn một |
| `publications` | sáu tham số phát hành | **một dòng mỗi đề**: hai bộ hạn cùng sống cho một đề là trạng thái không giải thích được cho học sinh |

Khoá nội dung khi duyệt là một `state` trên `assessments`, không phải một cờ trên từng câu — vì nó là
một thao tác trên cả đề.

Cột `state` là một `Enum` có check constraint, không phải chuỗi tự do, và cạnh giữa các trạng thái nằm
trong `services/be/src/be/assessment_state.py`. `advance()` ở đó là **cửa duy nhất** đổi trạng thái:
một lần chuyển viết rời ở chỗ khác là một cạnh thứ năm không ai tìm được, và thứ mất trước tiên sẽ là
cổng duyệt, vì phát hành thẳng từ bản nháp chỉ cách một phép gán.

Trạng thái `empty` tồn tại vì nó là thứ **chặn phát hành** một đề chưa có câu nào — ADR-01 dành cho nó
một luật riêng, nên nó là một trạng thái chứ không phải một câu truy vấn đếm.

### Nhóm 3 — bài làm và điểm

| Bảng | Giữ gì | Ghi chú |
| --- | --- | --- |
| `attempts` | một học sinh làm một đề, `started_at`, `ends_at`, `submitted_at` | `submitted_at` kết thúc **pha 1**, không kết thúc bài (ADR-14) |
| `answers` | lựa chọn của pha 1 | ghi mỗi lần bấm, không gom tới lúc nộp: mất mạng thì mất một cú bấm |
| `question_outcomes` | **sổ điểm**: `mark`, `reason`, `rounds_used`, `closed` | `mark` chỉ đi lên (ADR-16); `rounds_used` là bộ đếm ADR-17 chặn ở ba |

`question_outcomes` là bảng quan trọng nhất của mô hình này. Nó tách **điểm** khỏi **câu trả lời**:
một câu có một câu trả lời ở pha 1 và nhiều lượt ở pha 2, nhưng chỉ có **một** kết luận.

### Nhóm 4 — pha 2

| Bảng | Giữ gì | Ghi chú |
| --- | --- | --- |
| `rounds` | một lượt làm lại, `ends_at` | `ends_at` đã cắt xuống hạn pha 2 nếu ngân sách vượt (ADR-15) |
| `round_items` | câu agent sinh cho lượt đó, kèm `options`/`methods` dạng JSON | giữ cả đáp án đúng ở đây là thứ cho phép BE tự chấm lượt (ADR-20) |
| `chat_messages` | từng lượt hội thoại, `sequence` | lưu **trước** khi phát ra SSE |
| `reports` | báo cáo *giải thích khó hiểu*, gắn với `attempt` | không gắn với một tin nhắn: đơn vị là cả đoạn chat (ADR-19) |

### Nhóm 5 — hội thoại của giáo viên

| Bảng | Giữ gì | Ghi chú |
| --- | --- | --- |
| `teacher_conversations` | một mạch hội thoại của một giáo viên | một bảng riêng chứ không phải một id trần, để sau này mở mạch mới mà lượt cũ không đi theo |
| `teacher_turns` | từng **bước** một lượt: lời nói, hoặc tool đã chạy | `UniqueConstraint(conversation_id, sequence)`; commit theo từng bước |

Hai bảng này **không** dùng lại `chat_messages`, và lý do là cơ học chứ không phải khẩu vị:
`chat_messages.attempt_id` là khoá ngoại tới `attempts`, mà hội thoại của giáo viên không có bài làm
nào.

Bảng `teacher_turns` giữ nhiều hơn chữ, vì một lượt của giáo viên có thể là *"đã tạo đề nháp 10 câu
cho 12A1"* — và thứ đáng lưu là **đề nào**, không phải câu thông báo. `entity_kind` + `entity_id`
chở chủ thể ấy, và là thứ sẽ cho giao diện chọn đúng variant `Action result card`.

**Hiện chỉ một tool sinh ra chủ thể**: `find_class` trả `class_id`. Bảy variant của `Action result
card` đều là hành động **ghi**, mà đợt này không có tool ghi nào — nên hai cột ấy là cấu trúc đã
dựng, chưa phải dữ liệu đã có.

`model_tokens` và `duration_ms` làm bảng này thành **trace** cùng lúc với transcript. Một hệ trace
riêng sẽ là cùng những dòng ấy ghi hai lần, và với một agent tự chọn bước thì câu *"nó đã làm gì"*
không trả lời được chỉ bằng lời nói. Đọc trace là một câu `SELECT`.

## Ba quyết định về hình dạng, và lý do

**Câu của một lượt nằm trong JSON, không nằm trong `questions`.** Nó thuộc về đúng một lượt và không
bao giờ bị truy vấn xuyên dòng. Đưa nó lên bảng `questions` nghĩa là mọi truy vấn đọc đề đã duyệt
phải học cách bỏ qua một loại câu hỏi thứ hai.

**Khoá chính là chuỗi UUID, không phải kiểu UUID gốc.** Nhờ vậy cùng một model chạy trên Postgres lúc
phát triển và trên SQLite lúc test, không cần nhánh theo dialect. Cái giá là vài byte mỗi dòng.

**Không có bảng nào cho `confidence` hay `misconception_code`.** Đó không phải thiếu sót:
[ADR-08](../decisions/adr-08-bon-loai-nghi-ngo.md) thu hẹp chẩn đoán khỏi luồng học sinh, và
[ADR-20](../decisions/adr-20-cham-trac-nghiem-thuoc-be.md) làm việc chấm thành một phép so. Khi hàng
đợi review của giáo viên được thiết kế, nó sẽ mang theo hình dạng dữ liệu của riêng nó.

## Bảng được tạo thế nào

`be/db.py` gọi `Base.metadata.create_all` lúc khởi động. **Chưa có công cụ migration**, và đó là một
món nợ có chủ đích: schema hiện có đúng một người dùng và chưa có dữ liệu thật nào. Ngày có dữ liệu
thật, đánh đổi ấy lật ngược — và ADR-21 đã ghi migration là chi phí dự án này nhận.

Hệ quả cần biết ngay: `create_all` **chỉ tạo bảng còn thiếu**. Đổi kiểu một cột rồi khởi động lại thì
không có gì xảy ra và cũng không có lỗi nào. Trong lúc chưa có migration, cách đúng là xoá volume
`aiafa-pgdata` và để dữ liệu mẫu sinh lại.

## Dữ liệu mẫu

`be/seed.py` tạo lớp 12A, ba học sinh, và bài *Kiểm tra 15 phút — Hàm số* sáu câu đã phát hành — đúng
câu chuyện mà mười hai artboard trong Figma kể. Nó chỉ chạy khi database chưa có lớp nào.
