# Core hai pha — ranh giới service và hợp đồng giao tiếp

## Goal

Luồng nghiệp vụ chính chạy được thật, từ lúc giáo viên phát hành đề tới lúc một câu sai chốt ở 1 /
0,5 / 0 — với ranh giới ba service rõ tới mức kiểm được bằng máy, và mọi interface giữa chúng được
định nghĩa từng trường trước khi có dòng code nào.

Mười hai artboard học sinh và mười hai artboard giáo viên là **đặc tả đầu vào** của đợt này. Plan
này không thêm màn nào; nó trả lời câu hỏi *ai làm gì, và nói chuyện với nhau bằng cái gì*.

## Scope

**Trong:** ranh giới FE / BE / AGENT; schema Postgres cho trạng thái bài làm; REST FE↔BE cho luồng
học sinh và các bước giáo viên mà luồng đó cần; ba task queue BE→AGENT; kênh SSE cho chat pha 2;
danh tính tạm bằng token dev; gỡ chấm bài khỏi AGENT.

**Mock, không phải model thật.** Chưa có LLM nào trong đợt này: ba handler của AGENT trả nội dung
soạn sẵn, tất định, đủ để luồng chạy đầu-cuối và để test lặp lại được. Ranh giới, hợp đồng và hình
dạng dữ liệu là **thật**; chỉ phần sinh nội dung là giả. Đổi sang model thật sau này không được phép
đụng tới một endpoint nào.

**Ngoài:** màn đăng nhập thật và chỗ bắt đổi mật khẩu (lỗ ADR-13 **vẫn nguyên** sau đợt này); hàng
đợi review của giáo viên (UC-05) và số phận cuối cùng của `GradingRequested`/`GradingCompleted`; chỗ
giáo viên đọc báo cáo *giải thích khó hiểu*; màn `Bảng theo dõi`; prompt và lựa chọn model —
`docs/overview/grading-design.md` đã được giữ chỗ cho việc đó.

## Ranh giới ba service

| Việc | Ai | Luật buộc nó nằm ở đó |
| --- | --- | --- |
| Vẽ màn, thu lựa chọn, đếm ngược trên màn | FE | Đồng hồ trên màn là trang trí; hạn thật do BE giữ |
| Danh tính, phân quyền, học sinh chỉ thấy bài của mình | BE | [ADR-13](../../decisions/adr-13-lop-va-tai-khoan-hoc-sinh.md) |
| Vòng đời đề, khoá nội dung khi duyệt, cửa sổ thu hồi | BE | [ADR-01](../../decisions/adr-01-vong-doi-de-kiem-tra.md), [ADR-02](../../decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md) |
| Chấm trắc nghiệm | BE | [ADR-20](../../decisions/adr-20-cham-trac-nghiem-thuoc-be.md) |
| Ba mức điểm, điểm pha 1 là sàn | BE | [ADR-16](../../decisions/adr-16-thang-diem-ba-muc.md) |
| Đếm vòng, trần ba vòng mỗi câu | BE | [ADR-17](../../decisions/adr-17-ba-vong-moi-cau.md) |
| Ngân sách lượt, DỪNG lượt khi hết hạn | BE | [ADR-15](../../decisions/adr-15-thoi-gian-pha-hai.md) |
| Lọc `confidence` / `misconception` khỏi mọi response của học sinh | BE | [ADR-08](../../decisions/adr-08-bon-loai-nghi-ngo.md) |
| Soạn đề nháp kèm lời giải và ánh xạ nhiễu→lỗi | AGENT | [ADR-18](../../decisions/adr-18-cau-hoi-phai-kem-loi-giai.md) |
| Sinh câu cho một lượt làm lại | AGENT | [ADR-17](../../decisions/adr-17-ba-vong-moi-cau.md) |
| Một lượt trả lời trong chat pha 2 | AGENT | [ADR-18](../../decisions/adr-18-cau-hoi-phai-kem-loi-giai.md) |

Hai quy tắc giữ ranh giới, và cả hai kiểm được:

1. **Job phải tự chứa.** Không id nào trong payload cần tra database mới hiểu được, vì AGENT không có
   credential ([architecture.md](../../overview/architecture.md)).
2. **AGENT không trả quyết định.** Không điểm, không hạn, không `needs_review`, không *đủ ba vòng
   chưa*. Nó trả nội dung; BE kết luận.

## Interface FE ↔ BE

Danh tính lấy từ session ở mọi endpoint, nên không endpoint nào nhận `student_id` trong body — một
client không được phép tự khai mình là ai.

### Học sinh

**`GET /api/me/assignments`** — màn `13`.

Ra: `items[]` với `assignment_id`, `title`, `subject`, `question_count`, `phase1_minutes`,
`opens_at`, `closes_at`, `remediation_deadline`, `status`, `wrong_count`, `actions[]`.

- `status` là **enum tám giá trị** khớp đúng `Assignment status` trong Figma. BE tính nó từ đồng hồ
  server. FE **không** được suy trạng thái từ `opens_at`/`closes_at`: hai máy lệch giờ sẽ ra hai
  trạng thái khác nhau cho cùng một bài.
- `wrong_count` chỉ khác `null` khi bài đã nộp — đó là con số chip *Cần làm lại n câu* đọc.
- `actions[]` là enum (`start`, `continue`, `result`, `remediate`), **không** phải nhãn nút. Nhãn nằm
  ở FE, nên đổi chữ không phải đổi API. Một hàng ở pha 2 trả về `["result", "remediate"]` — đúng hai
  nút mà variant `Hành động=hai` dựng sẵn.

**`POST /api/assignments/{id}/attempts`** — nút *Bắt đầu*, mở màn `14`.

Vào: rỗng. Ra: `attempt_id`, `started_at`, `ends_at`, `questions[]`.

- `ends_at` là **mốc tuyệt đối kèm offset**, không phải số phút còn lại. Gửi số phút thì đồng hồ chạy
  lệch theo độ trễ mạng và theo lúc học sinh tải lại trang.
- `questions[].options[]` có `option_id`, `label`, `text` và **không có** `is_correct`. Đáp án đúng
  không rời khỏi BE trước khi bài được nộp.
- 409 khi chưa tới giờ mở, đã quá `closes_at`, hoặc đã có lần làm bài đã nộp.

**`PUT /api/attempts/{id}/answers/{question_id}`** — mỗi lần chọn một phương án.

Vào: `option_id`. Ra: `saved_at`.

- Lưu từng câu chứ không gom tới lúc nộp, để mất mạng giữa chừng không mất bài.
- BE từ chối sau `ends_at`; đó là chỗ duy nhất hạn pha 1 được thi hành.

**`POST /api/attempts/{id}/submit`** — màn `14` → `15`. Đây là **điểm kết thúc pha 1**, không phải
điểm kết thúc bài ([ADR-14](../../decisions/adr-14-hai-pha-lam-bai.md)).

Ra: `submitted_at`, `phase1_score`, `question_count`, `wrong_question_ids[]`.

- Chấm chạy **đồng bộ ngay trong request này** ([ADR-20](../../decisions/adr-20-cham-trac-nghiem-thuoc-be.md)),
  nên không có trạng thái *đang chấm* giữa hai màn.
- 409 nếu đã nộp. Nộp hai lần là một cửa một chiều bị bấm hai lần, không phải một phép idempotent.

**`GET /api/attempts/{id}/result`** — màn `15` và `22`.

Ra: `state`, `total_score`, `question_count`, `remediation_deadline`, `items[]`.

- `state` phân biệt *đã nộp, cần chữa* / *đã hoàn thành* / *hết hạn chữa*. Đây là thứ chọn giữa hai
  artboard, và [ADR-14](../../decisions/adr-14-hai-pha-lam-bai.md) nói chúng là hai hình dạng dữ
  liệu khác nhau chứ không phải một hình dạng với vài trường rỗng.
- `items[].mark` là `1` / `0.5` / `0`; `items[].mark_reason` là **enum** (`đúng-ngay`, `chữa-được`,
  `chưa-chữa`, `hết-vòng`). Câu chữ hover sống ở FE — [ADR-16](../../decisions/adr-16-thang-diem-ba-muc.md)
  đòi hai chuỗi khác nhau cho mức 0 tuỳ pha 2 còn hạn hay không, và `mark_reason` cộng
  `remediation_deadline` đủ để FE chọn đúng chuỗi.
- `items[].rounds[]` mang `index`, `stem`, `outcome` — **đề của từng lượt**, không chỉ kết quả. Mảng
  rỗng khi câu chưa được chữa, nên màn `15` không bày một danh sách trống.

**`GET /api/attempts/{id}/remediation`** — panel màn `17`.

Ra: `deadline`, `minutes_per_question`, `round_budget_minutes`, `can_start_round`, `warn_cut`,
`remaining[]`.

- `remaining[]` có `question_id`, `stem`, `chosen{label,text}`, `correct{label,text}`, `rounds_used`,
  `rounds_max`. Đáp án đúng **được** trả ở đây vì bài đã nộp: học sinh sắp làm một câu khác cùng
  dạng, giấu đáp án câu cũ không bảo vệ điều gì.
- Panel **không** nhận tên lỗi và không nhận cách giải — chúng nằm sau một cú bấm, ở endpoint lời
  giải. Đây là quyết định thiết kế đã chốt ở vòng bốn.
- `warn_cut` do **BE** tính: `round_budget_minutes` lớn hơn thời gian còn lại tới `deadline`. Nó là
  thứ chọn giữa màn `19` và màn `20`. FE tự so hai mốc giờ là đưa một luật của
  [ADR-15](../../decisions/adr-15-thoi-gian-pha-hai.md) ra khỏi BE.

**`GET /api/questions/{id}/solution`** — màn `18`.

Ra: `stem`, `methods[]{title, body}`, `options[]{label, text, is_correct, error_label}`.

- `error_label` chính là ánh xạ nhiễu→lỗi soạn sẵn ([ADR-18](../../decisions/adr-18-cau-hoi-phai-kem-loi-giai.md));
  `null` ở phương án đúng.
- BE **chặn** endpoint này khi lần làm bài của chính học sinh đó chưa nộp. Cùng một hộp thoại, hai
  người xem ở hai thời điểm khác nhau: giáo viên lúc duyệt, học sinh lúc chữa.

**`POST /api/attempts/{id}/chat/messages`** — màn `17`, `19`, `20`.

Vào: `text`. Ra: `202` với `message_id`, `stream_url`.

- BE lưu lượt của học sinh, dựng context rồi đẩy job cho agent. FE **không bao giờ** gửi lời giải hay
  đáp án lên — nếu client cầm được những thứ đó thì cửa duyệt của giáo viên vô nghĩa.

**`GET /api/attempts/{id}/chat/stream/{message_id}`** — SSE, chữ hiện dần.

Sự kiện `chunk{text}`, rồi `done{message_id}`, hoặc `error{code}`. Mất kết nối thì gọi lại
`GET /api/attempts/{id}/chat` để lấy lịch sử đầy đủ — SSE là kênh **tăng tốc cảm giác**, không phải
nguồn sự thật.

**`GET /api/attempts/{id}/chat`** — lịch sử, dùng cho màn `24`.

Ra: `messages[]{role, text, created_at}`, `locked` (đúng khi bài đã kết thúc). `locked` là thứ khoá ô
nhập và bỏ nút *Làm bài mới* trên màn `24`.

**`POST /api/attempts/{id}/rounds`** — cổng ở màn `19`/`20`, mở màn `21`.

Ra: `round_id`, `ends_at`, `items[]{round_item_id, origin_question_id, order, stem, options[]}`.

- BE gọi agent sinh một câu cho **từng** câu còn dở, lưu cả đáp án đúng và lời giải, rồi chỉ trả phần
  học sinh được thấy.
- `ends_at` = giờ hiện tại + `round_budget_minutes`, **cắt xuống** `remediation_deadline` nếu vượt.
  Đây là chỗ *"lượt đang làm bị DỪNG"* thành một con số.
- 409 khi quá hạn pha 2, khi không còn câu nào, hoặc khi đã có một lượt đang mở — một học sinh mở hai
  tab không được có hai đồng hồ.

**`PUT /api/rounds/{id}/answers/{round_item_id}`** và **`POST /api/rounds/{id}/submit`** — màn `21`.

Ra của submit: `per_question[]{question_id, outcome, new_mark, rounds_used, rounds_left}`,
`attempt_state`.

- Đúng thì câu gốc lên **0,5** và đóng lại; sai thì `rounds_used` tăng, và chạm 3 thì câu chốt **0**.
- Điểm chỉ đi lên, không bao giờ đi xuống — điểm pha 1 là sàn.

**`POST /api/attempts/{id}/reports`** — nút ở chân màn `19`, `20`, `24`.

Vào: `note` (tuỳ chọn). Ra: `report_id`.

- Không có `message_id` trong body: đơn vị báo cáo là **cả đoạn chat của bài này**
  ([ADR-19](../../decisions/adr-19-bao-cao-giai-thich-chua-ro.md)). BE tự đính kèm đoạn chat và danh
  sách câu sai.

### Giáo viên

`POST /api/chat` (dòng lệnh trợ lý), `GET /api/assessments/{id}`,
`POST /api/assessments/{id}/approve` và `/unapprove`, `POST /api/assessments/{id}/publish`,
`POST /api/assessments/{id}/recall`, `GET /api/classes`, `POST /api/classes/{id}/roster` (CSV),
`GET /api/assessments/{id}/results`.

`publish` nhận đúng **sáu** tham số mà `Publish settings` dựng: `class_id`, `opens_at`, `closes_at`,
`phase1_minutes`, `phase2_minutes_per_question`, `remediation_deadline`. BE kiểm thứ tự các mốc và
**chỉ nhận khi đề đã duyệt** — đó là cổng của [ADR-02](../../decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md)
ở dạng code.

## Interface BE → AGENT (arq trên Redis)

| Task | Vào | Ra |
| --- | --- | --- |
| `draft_assessment` | `schema_version`, `request_id`, `subject`, `grade`, `topic_scope`, `question_count`, `source`, `bank_questions[]?` | `questions[]{stem, options[]{label,text,is_correct,error_label}, methods[]{title,body}, learning_objective}` |
| `generate_retry_question` | `schema_version`, `request_id`, `origin_question{stem,options,methods,learning_objective}`, `wrong_option_label`, `error_label`, `round_index`, `previous_variants[]{stem}` | `stem`, `options[]`, `methods[]` |
| `explain_turn` | `schema_version`, `request_id`, `question{stem,options,methods}`, `chosen_option_label`, `error_label`, `history[]{role,text}`, `student_text` | `text` (và các chunk qua pub/sub khi stream) |

- `previous_variants[]` tồn tại vì một lỗi thật: lượt 2 của câu mẫu từng có **đáp án trùng câu gốc**,
  nên học sinh nhớ máy vẫn qua được — đúng thứ [ADR-17](../../decisions/adr-17-ba-vong-moi-cau.md)
  muốn chặn.
- `error_label` đi **vào** `explain_turn` chứ không do agent nghĩ ra: chẩn đoán là **tra cứu**, không
  phải suy đoán.
- Không task nào nhận `attempt_id` hay `student_id` làm dữ liệu để tra; định danh chỉ đi kèm để ghi
  log.

## Files

| Node / file | Việc |
| --- | --- |
| `packages/contracts` | Ba message mới cho ba task; `GRADE_SUBMISSION_TASK` chuyển sang legacy |
| `services/be/src/be/models/` | Schema Postgres mới, migration đầu tiên |
| `services/be/src/be/scoring.py` | Chấm trắc nghiệm và ba mức điểm — mới |
| `services/be/src/be/remediation.py` | Đếm vòng, ngân sách lượt, DỪNG khi hết hạn — mới |
| `services/be/src/be/routes.py` | Toàn bộ endpoint ở trên |
| `services/agent/src/agent/handlers.py` | Bỏ `grade`; thêm ba handler mới |
| `services/fe/src/` | Mười hai màn học sinh; client SSE |
| `docs/overview/architecture.md` | Mục *Đường giao tiếp* và *Ranh giới dữ liệu* sau khi có DB |
| `docs/overview/data-model.md` | Tạo mới khi schema chốt — tên đã được `AGENTS.md` giữ chỗ |
| `AGENTS.md` | Sửa dòng invariant về câu luyện tập cho khớp ADR-17 |
| `.env.example` | DSN Postgres; `JOB_RESULT_TTL_SECONDS` giữ nguyên, đổi chú thích |

## Ordered Tasks

- [x] Chốt schema Postgres, rồi viết `docs/overview/data-model.md`. **Đổi thứ tự có chủ đích**:
      schema sống trong `be/models.py` với lý do viết ngay tại chỗ, còn tài liệu viết **sau** khi nó
      chạy — một tài liệu schema viết trước khi có bảng nào là đúng thứ `AGENTS.md` cấm tạo.
- [x] Danh tính tạm: `be/identity.py` đọc header `X-Actor`, phân quyền hai vai là thật.
- [ ] Vòng đời đề ở BE: nháp → duyệt → phát hành, kèm cổng *chỉ giáo viên phát hành*. **Chưa làm** —
      dữ liệu mẫu tạo sẵn một đề đã phát hành, nên luồng học sinh chạy được mà chưa cần bề mặt này.
- [x] Pha 1 đầu-cuối: bắt đầu, lưu từng câu, nộp, chấm, màn kết quả.
- [x] Gỡ `grade_submission` khỏi luồng; dời sang `agent/legacy_grading.py` và ghi rõ là legacy.
- [x] Pha 2: remediation, chat (job + SSE), lượt, chấm lượt, chốt ba mức điểm.
- [x] Báo cáo *giải thích khó hiểu*: lưu được; **chỗ giáo viên đọc thì chưa có** (ngoài phạm vi).
- [x] Kiểm đầu ra agent ở BE; test cho cả ba luật của ADR-18.
- [x] Mười hai màn học sinh ở FE, thay cho màn demo cũ.
- [x] Cập nhật `architecture.md`, `local-development.md`, `services/fe/AGENTS.md`, và bốn ADR trích
      dẫn màn demo vừa bị thay.
- [ ] Chuyển hai dòng invariant sang nhóm tự động. **Chưa làm** — chúng thuộc UC-05, vẫn ngoài phạm vi.
- [x] **Gọi 1 subagent review** — UI tôi tự đi bằng mắt (vòng subagent đầu chết vì hết hạn mức);
      vòng sau review mã nguồn và tài liệu, và bắt được một lỗi **chặn**: xem *Status*.
- [ ] **Gọi 1 subagent review** — ba mặt, không chỉ code: (a) code và test, (b) tài liệu có còn khớp
      không sau khi code chạy, (c) **UI thật trên trình duyệt**, mở `http://localhost:5173` và đi
      hết luồng chứ không chỉ đọc JSX. Sửa theo phát hiện, hoặc phản bác có lý do.

## Validation Checks

Mọi test dưới đây chạy với AGENT mock. Một test **không** được phép phụ thuộc vào câu chữ agent sinh
ra — nó kiểm hình dạng và luật, vì đó là thứ sống sót khi model thật thay chỗ.


- `.\dev.ps1 check` và `.\dev.ps1 test` xanh; boundary probe chạy lại vì contract đổi.
- Test *AGENT không trả điểm*: đầu ra của cả ba handler mới không có trường điểm nào.
- Test *job tự chứa*: payload của cả ba task không mang id nào mà agent phải tra mới hiểu.
- Test *học sinh không thấy chẩn đoán*: response của mọi endpoint học sinh không chứa `confidence`,
  `misconception_code`, `review_reason`.
- Test *đáp án đúng không rời BE trước khi nộp*: `POST /attempts` và `GET /rounds` không trả
  `is_correct`.
- Test *trần ba vòng*: vòng thứ tư bị từ chối, câu chốt 0.
- Test *điểm là sàn*: không đường nào hạ `mark` của một câu.
- Test *hạn pha 2*: mở lượt sau `remediation_deadline` trả 409; lượt vượt hạn bị cắt `ends_at`.
- Test *một lượt đang mở*: mở lượt thứ hai trả 409.

## Decision Records

### Decision: Chat pha 2 dùng SSE, không dùng poll

options considered: giữ đúng cơ chế job + poll như luồng chấm hiện tại; thêm SSE cho riêng chat.

selected option: SSE — **người dùng chốt**.

reason: poll đưa được câu trả lời về, nhưng nó đưa về **một lần, sau vài giây im lặng**. Ở pha 1 điều
đó chấp nhận được vì học sinh chờ một con số. Ở pha 2 thứ đang diễn ra là **dạy lại**, và im lặng vài
giây sau khi hỏi làm người ta tưởng hỏng. Cái giá là một cơ chế mới: agent đẩy chunk qua Redis
pub/sub, BE giữ kết nối SSE. Để cái giá đó không lan ra chỗ khác, SSE **không phải nguồn sự thật** —
mất kết nối thì đọc lại lịch sử bằng REST, và mọi lượt chat đều đã nằm trong Postgres trước khi chunk
đầu tiên rời đi.

### Decision: Danh tính tạm bằng token dev, đăng nhập để sau

options considered: dựng màn đăng nhập thật ngay trong đợt core; header token chỉ bật ở môi trường
dev.

selected option: token dev — **người dùng chốt**.

reason: [ADR-10](../../decisions/adr-10-pham-vi-dot-dau.md) cố ý bỏ màn đăng nhập, nhưng mọi endpoint
học sinh đều phải biết ai đang gọi — *học sinh chỉ thấy bài của mình* là một luật, không phải một
tiện nghi. Tách hai thứ ra: **phân quyền** viết đầy đủ ngay từ đầu và không bao giờ phải viết lại;
**cách chứng minh danh tính** tạm là một header. Điều kiện để cái tạm không thành cái vĩnh viễn: nó
chỉ bật khi biến môi trường dev bật, và mặc định tắt ở mọi chỗ khác.

Nợ phải nói rõ: lỗ [ADR-13](../../decisions/adr-13-lop-va-tai-khoan-hoc-sinh.md) — mật khẩu ban đầu
đi trên giấy in và không có chỗ bắt đổi — **không nhỏ đi** sau đợt này.

### Decision: BE kiểm đầu ra của agent trước khi lưu

options considered: tin đầu ra của agent vì prompt đã yêu cầu đúng; kiểm ở BE và từ chối job sai
luật.

selected option: kiểm ở BE.

reason: [ADR-18](../../decisions/adr-18-cau-hoi-phai-kem-loi-giai.md) là luật nghiệp vụ — đúng một
đáp án đúng, mọi nhiễu gắn một lỗi, ít nhất hai cách giải — và luật nghiệp vụ không được thi hành
bằng lời nhắc trong prompt. Vòng review ngày 2026-09-11 bắt được một câu mẫu **hai đáp án đúng** do
chính tôi soạn tay; một model sinh hàng trăm câu sẽ tạo ra lỗi ấy thường xuyên hơn. Một câu hỏi hai
đáp án đúng còn kéo theo hệ quả nặng hơn: ánh xạ nhiễu→lỗi của nó **không viết được**, nên pha 2 của
câu đó hỏng chứ không chỉ pha 1.

### Decision: Sửa dòng invariant trong `AGENTS.md` về câu luyện tập

options considered: để nguyên vì nó vẫn "gần đúng"; sửa cho khớp ADR-17.

selected option: sửa — dòng nay đọc *a retry question is a variant of the same question, not merely
the same objective*.

reason: `AGENTS.md` đòi mọi thay đổi của chính nó phải có plan và decision record; dòng này đã được
sửa trước khi plan tồn tại, và đây là chỗ trả nợ đó. Bản cũ ghi *practice questions keep the same
learning objective* — đúng bằng câu mà [ADR-17](../../decisions/adr-17-ba-vong-moi-cau.md) **bác bỏ**
trong mục *Quyết định*: một câu khác cùng learning objective có thể hỏng ở bước khác và không chạm
tới lỗi vừa mắc. Một bảng invariant ghi lại đúng thứ đã bị bác là tệ hơn không ghi.

## Rủi ro

**Đây là đợt đầu tiên có database.** Migration, backup và hình dạng dữ liệu là chi phí vận hành thật
mà ba giai đoạn trước cố ý chưa trả. Trả vì pha 2 không có đường khác
([ADR-21](../../decisions/adr-21-trang-thai-bai-lam-la-ben.md)), không phải vì database là bước tiến
tự nhiên.

**Hai đường chấm cùng tồn tại một thời gian.** Luồng core chấm ở BE; đường demo cũ vẫn đẩy job sang
agent. Ai đọc code trong giai đoạn đó sẽ thấy hai câu trả lời cho cùng một câu hỏi. Giảm rủi ro bằng
cách đánh dấu legacy ngay tại `contracts` và ghi nợ, chứ không bằng việc nhớ.

**SSE là cơ chế thứ hai để một câu trả lời đi từ agent về người dùng.** Nếu nó âm thầm phân kỳ với
bản lưu trong Postgres thì học sinh đọc một đằng, giáo viên đọc một nẻo. Ràng buộc chặn việc đó: lượt
chat được lưu **trước** khi chunk đầu tiên rời BE.

**Mười hai màn là đặc tả, nhưng chúng là dữ liệu mẫu.** Không con số nào trên đó là thật, và vòng
review vừa rồi đã bắt ba mâu thuẫn dữ liệu giữa các màn. Khi code chạy với dữ liệu thật, những chỗ
lệch còn lại sẽ lộ ra ở đây trước.

## Status

**Đã dựng xong và chạy thật** trên Redis + Postgres trong Docker, với AGENT mock. Luồng lõi đi hết
được từ danh sách bài tới điểm chốt ba mức, cả bằng API lẫn bằng tay trên trình duyệt.

Đi bằng mắt trên trình duyệt bắt được **ba lỗi mà 46 test không bắt**, và đó là phần đáng ghi nhất
của đợt này:

1. Màn làm bài nhận `attempt_id` nhưng gọi endpoint cần `assignment_id` — bấm *Bắt đầu* là rơi thẳng
   vào lỗi. Sửa bằng `GET /api/attempts/{id}`: POST để **tạo**, GET để **quay lại**, và lẫn hai thứ
   đó chính là lỗi này.
2. Trợ lý chào hai lần. Nguyên nhân ở FE, cách sửa ở BE: một lượt trả lời chỉ sinh khi tới lượt trợ
   lý. Client gọi hai lần thì nhận lại đúng lượt đã lưu.
3. Trợ lý gọi sai số câu — *"em sai câu 1, câu 2"* trong khi bài sai câu 5 và câu 6 — vì payload
   không mang số câu. Màn lượt làm lại cũng vậy.

Chạy thật bằng API trước đó bắt thêm một lỗi nữa: câu ngoài bank của mock nhận lại **chính đề pha 1**
cho lượt làm lại. Sửa ở BE bằng `validate_retry`, vì đó là luật ADR-17 chứ không phải khuyết điểm
của mock.

**Chưa làm, và cố ý:** bề mặt giáo viên cho vòng đời đề (dữ liệu mẫu tạo sẵn một đề đã phát hành);
chỗ giáo viên đọc báo cáo; đăng nhập thật; hai dòng invariant thuộc UC-05.

Một việc ngoài phạm vi đã làm và cần biết: **BE khởi động được khi Redis chết**. Pha 1 không đụng
AGENT, và ADR-16 gọi điểm pha 1 là sàn — một cái sàn cần service thứ hai mới đứng được thì không
phải sàn. Pha 2 trả 503 thay vì làm cả BE chết lúc khởi động.

**Vòng review bắt một lỗi chặn mà cả 46 test lẫn mắt tôi đều bỏ sót**: mở hai tab thì mở được **hai
lượt cùng lúc**. Route kiểm *"đã có lượt nào đang mở chưa"* rồi mới ghi — hai request bắn cùng lúc
thì cả hai đều qua được phép kiểm. Reviewer tái hiện bằng hai `POST /rounds` đồng thời và nhận **hai
201**.

Đáng chú ý là test cũ (`test_only_one_round_may_be_open`) **xanh** suốt: nó gọi tuần tự, nên không
bao giờ chạm vào khe hở. Một phép kiểm không bao giờ chạm tới thứ nó canh thì không phải phép kiểm.

Sửa ở tầng database chứ không ở tầng route: partial unique index trên `rounds(attempt_id)` với
`WHERE submitted_at IS NULL`, và route biến `IntegrityError` thành 409. Kiểm lại trên Postgres thật:
hai request đồng thời cho ra `[201, 409]`, còn đúng một lượt mở. Hai chỗ nữa đi cùng gốc ấy:
`start_attempt` nay bắt `IntegrityError` để hai tab bấm *Bắt đầu* không thành 500, và `submit_round`
bỏ qua câu đã đóng thay vì mở lại nó.

Một chi tiết nhỏ nhưng đúng: các chỗ đọc *"lượt đang mở"* đổi từ `scalar()` sang `one_or_none()`.
`scalar()` im lặng lấy dòng đầu khi có nhiều dòng — tức là nếu luật này hỏng lần nữa, hệ thống sẽ
**giấu** thay vì kêu.

Reviewer xác nhận bằng API thật: không luật nào rò ra FE, `confidence`/`misconception_code` không có
ở luồng học sinh, học sinh khác nhận 404, trần ba vòng đóng đúng lúc, payload gửi AGENT tự chứa, và
`packages/contracts` không lọt logic nào. Ranh giới và interface đã chốt; bốn ngã rẽ đã được người dùng chọn
(chấm ở BE, token dev, SSE, thu hẹp ADR-09). Chờ duyệt để bắt đầu task đầu tiên — schema và
`data-model.md`.
