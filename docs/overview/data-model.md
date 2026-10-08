# Data model

## Mục đích tài liệu

Tài liệu này mô tả **hình dạng dữ liệu BE lưu**: có những bảng nào, mỗi bảng trả lời câu hỏi nghiệp
vụ nào, và vì sao ranh giới giữa chúng nằm ở đó. Nó không mô tả API — API thuộc về
[Architecture](architecture.md) — và không mô tả luật — luật thuộc về `docs/decisions/`.

Nguồn sự thật của schema là `packages/schema/src/schema/models.py` — một **package dùng
chung**, không một service, vì `services/be` và `services/ingest` cùng ghi vào database này
và một định nghĩa bảng sống trong một service thì service kia không với tới được. Tài liệu này giải thích nó; khi hai bên
lệch nhau, code đúng và tài liệu phải sửa.

Được viết **sau** khi schema chạy thật, không phải trước. Một tài liệu schema viết trước khi có bảng
nào là thứ `AGENTS.md` cấm tạo: nó mô tả một hệ thống chưa ai kiểm được.

## Vì sao có database

[ADR-21](../decisions/adr-21-trang-thai-bai-lam-la-ben.md). Hạn pha 2 do giáo viên đặt, tính bằng giờ
hoặc ngày, nên trạng thái bài làm không sống được trong một chỗ có TTL một giờ. Postgres thuộc về BE
và chỉ BE; AGENT không có credential nào và không bao giờ có.

## Các bảng, theo nhóm

> **Con số trong tiêu đề cũ đã lệch.** `models.py` có **21** `__tablename__`; tài liệu này từng nói
> mười ba. Đợt 06/10/2026 chỉ bổ sung hai bảng nháp bên dưới — những bảng còn thiếu
> (`pregenerated_items`, `question_outcomes`, …) là món nợ của một đợt rà soát riêng, ghi ra đây
> để nó không nằm im. `documents` đã được trả ngày 08/10/2026, vì đợt ấy đổi hình dạng của nó.

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
| `publications` | sáu tham số phát hành | **một dòng mỗi (đề, lớp)** — khoá chính kép, nên thu hồi được **từng lớp một**. Từ 06/10/2026 một lần phát hành chỉ có **một** khung giờ cho mọi lớp trong lần đó; muốn hai lớp hai đồng hồ thì phát hành hai lần, và bảng vẫn chở được (ADR-02, sửa đổi) |
| `draft_briefs` | yêu cầu soạn của một đề: môn, khối, phạm vi, `question_count`, `version` | `question_count` là **tổng** đã xin, không phải con số khai lúc tạo đề — `fire()` ghi nó, `harvest()` đọc nó để biết ô nào đã cũ. `version` tăng mỗi lần đổi brief, nên một job của brief cũ về muộn thì nhận ra được |
| `documents` | tài liệu giáo viên tải lên: `teacher_id`, `filename`, `content_type`, `byte_size`, `storage_key`, `state`, `page_count`, `fault`, `uploaded_at` | **Không giữ byte nào.** `storage_key` trỏ tới một object trong MinIO, dạng `documents/<giáo viên>/<tài liệu><đuôi>`. Byte rời cột `LargeBinary` ngày 08/10/2026 vì `services/document` không có credential database. `byte_size` ở lại dù byte đã đi: chip trên rail in nó, và một lời gọi mạng chỉ để biết một con số đã biết sẵn là một lời gọi thừa. `state` là **nguồn sự thật duy nhất** về việc tài liệu đã xử lý xong chưa, từ vựng lấy ở `contracts.DocumentState`; `page_count` **nullable**, và `None` nghĩa là con số không tồn tại (`.txt`, `.md`) hoặc chưa đo được, không bao giờ là `0`; `fault` là một câu tiếng Việt đi thẳng lên chip. Thuộc về **giáo viên**, không thuộc về đề (ADR-04) |
| `draft_items` | một ô cho mỗi câu đang soạn: `ordinal`, `job_id`, `status`, `attempts`, `last_fault` | `status` là `pending`/`ready`/`retry`/`failed`; `attempts` chặn vòng thử lại ở `_MOST_ATTEMPTS`. **`last_fault`** chở lý do một câu bị loại: một `retry` không nói vì sao là một dấu vết không dùng được, và nó chính là thứ từng biến một đề 2/3 câu thành "không ai truy được" |

Khoá nội dung khi duyệt là một `state` trên `assessments`, không phải một cờ trên từng câu — vì nó là
một thao tác trên cả đề.

Cột `state` là một `Enum` có check constraint, không phải chuỗi tự do, và cạnh giữa các trạng thái nằm
trong `services/be/src/be/assessment_state.py`. `advance()` ở đó là **cửa duy nhất** đổi trạng thái:
một lần chuyển viết rời ở chỗ khác là một cạnh thứ năm không ai tìm được, và thứ mất trước tiên sẽ là
cổng duyệt, vì phát hành thẳng từ đề nháp chỉ cách một phép gán. Từ Pha 5 có **hai** chỗ gán
`state`, không một: `withdraw()` là thao tác có tên đi vòng qua bảng cạnh, vì cạnh *đã phát hành → đã
duyệt* có **điều kiện** và một hàng vô điều kiện trong bảng sẽ cho bất kỳ caller nào quên kiểm giờ thu
hồi được một bài học sinh đang ngồi làm.

Trạng thái `empty` tồn tại vì nó là thứ **chặn phát hành** một đề chưa có câu nào — ADR-01 dành cho nó
một luật riêng, nên nó là một trạng thái chứ không phải một câu truy vấn đếm.

Nhưng một trạng thái thì không tự canh được số câu hỏi: `state` và số dòng `questions` là hai thứ, và
không constraint nào buộc chúng khớp nhau. Nên bất biến ấy được thi hành ở **endpoint duyệt**
(`teacher_routes.py`), nơi đã có session để đếm — `advance()` thì thuần trên một hàng, và đọc
`assessment.questions` bên trong nó sẽ là một lazy-load trong ngữ cảnh async. Hệ quả: *"`advance()` là
cửa duy nhất"* vẫn đúng về cú pháp nhưng chưa đủ để giữ bất biến, vì cửa đó không biết **ai** đang xin
đi cạnh nào. Caller nào biết nó đang ở cạnh nào thì phải tự nêu tiền đề của mình.

### Nhóm 3 — bài làm và điểm

| Bảng | Giữ gì | Ghi chú |
| --- | --- | --- |
| `attempts` | một học sinh làm một đề, `class_id`, `started_at`, `ends_at`, `submitted_at` | `submitted_at` kết thúc **pha 1**, không kết thúc bài (ADR-14). `class_id` ghi lớp **lúc bắt đầu**, nên chuyển lớp không đổi hạn của bài đã làm |
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
| `teacher_conversations` | một mạch hội thoại của một giáo viên | một bảng riêng chứ không phải một id trần, để sau này mở mạch mới mà lượt cũ không đi theo. `title` do model đặt sau lượt đầu, giáo viên sửa được; `deleted_at` là **xoá mềm** |
| `teacher_turns` | từng **bước** một lượt: lời nói, hoặc tool đã chạy | `UniqueConstraint(conversation_id, sequence)`; commit theo từng bước. `choices` + `more_choices` giữ các phương án của một câu hỏi lại |

Hai bảng này **không** dùng lại `chat_messages`, và lý do là cơ học chứ không phải khẩu vị:
`chat_messages.attempt_id` là khoá ngoại tới `attempts`, mà hội thoại của giáo viên không có bài làm
nào.

Bảng `teacher_turns` giữ nhiều hơn chữ, vì một lượt của giáo viên có thể là *"đã tạo đề nháp 10 câu
cho 12A1"* — và thứ đáng lưu là **đề nào**, không phải câu thông báo. `entity_kind` + `entity_id`
chở chủ thể ấy, và là thứ sẽ cho giao diện chọn đúng variant `Action result card`.

**Chủ thể đọc ra từ các cờ của kết quả, không từ tên tool**: `found` cho một lần tra cứu
(`get_class`), `created` cho một đề nháp mới, `started` cho một vòng sinh câu hỏi,
`approved`/`unapproved`/`published` cho ba quyết định của giáo viên. Liệt kê các cờ thì hơn đi soi
tên tool, vì cái tên không phải thứ mang theo id.

`list_class` **không** sinh ra chủ thể, và đó là chủ ý: nó trả về một danh sách, mà một bước nói về
nhiều lớp thì không nói về lớp nào cả. Chủ thể của nó là lựa chọn giáo viên sắp đưa ra.

**`deleted_at` là xoá mềm, và đó là một quyết định** (ADR-24): giáo viên muốn một đoạn gõ nhầm
biến khỏi mắt mình, còn ADR-24 đòi biên bản duyệt đề giữ được — mà biên bản ấy là một row
`teacher_turns` của chính đoạn đó. Nên đoạn đã xoá đọc ra y như một đoạn không tồn tại, và các lượt
của nó nằm nguyên trong bảng. Không có cột nào nói *ai* xoá: chỉ chủ sở hữu xoá được, nên câu trả
lời đã nằm trong `teacher_id`.

**`choices` và `more_choices` là nhu cầu của màn hình, không phải của model.** Chúng không có trong
`TurnRecord` — payload đi sang AGENT — vì model không dùng được chúng; chúng ở đây vì màn hình hứa
dựng lại được từ database, và không lưu thì một lần F5 lấy mất các nút của một câu hỏi lại. Chỉ bước
**cuối** của một đoạn còn bày chúng ra, và chỉ một bước `ask_clarify` mới được ghi chúng: một lời
thông báo mang theo nút bấm là mời giáo viên trả lời một câu không ai hỏi.

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
