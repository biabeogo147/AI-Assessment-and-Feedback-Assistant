# Hai pha một lượt chat — plan thi hành ADR-25

**Spec:** `docs/decisions/adr-25-hai-pha-mot-luot-chat.md`

## Context

Một lượt chat của giáo viên hiện là một vòng lặp phẳng trộn đọc với ghi, kết thúc ngay khi model
nói một câu. Ba chỗ vỡ ra từ đó, và cả ba đang nhìn thấy được trên màn hình:

- Artboard 4 in `bước 3/5` — một con số **không tính được** từ vòng lặp tự do, vì không ai biết
  trước có bao nhiêu bước.
- Model được phép ghi rồi mới hỏi lại. Database đang có một đề rỗng sinh ra đúng theo đường đó.
- Không ai báo cáo kết quả: lượt kết thúc bằng *"đang soạn"*, việc soạn chạy tiếp trong hàng đợi,
  và câu kết của artboard 5 không có chỗ nào sinh ra.

ADR-25 chốt: pha 1 lên plan (chỉ tool đọc, được hỏi lại), pha 2 thực hiện plan (chỉ tool ghi), rồi
một lời gọi model riêng để báo cáo. Tiến độ chảy AGENT → Redis → BE → SSE → FE. Màn hình vẽ theo
đúng thứ tự nhận được.

**Kết quả mong muốn:** giáo viên gõ *"tạo đề 10 câu về tích phân cho 12A"* và thấy: Kriky nói, khối
bước hiện dần với `bước k/n` chạy thật, số câu tăng dần, rồi câu báo cáo và **một** thẻ kết quả ghi
số câu thật. Không thẻ "đề trống", không bước `✕` cho một câu hỏi lại.

## Architecture

Một hàm sinh sự kiện duy nhất, hai cửa ra. `run_turn()` là async generator: pha 1 hỏi model tới khi
có `say` / `ask_clarify` / `plan`; pha 2 chạy từng bước của plan; rồi gọi model lần nữa để báo cáo.
`POST /teacher/chat/messages` **drain** generator ấy rồi trả `Answered` như hiện nay; đường SSE forward
từng sự kiện. Một bản cài đặt, hai cửa — không có nhánh thứ hai để trôi dạt.

Mọi sự kiện vẫn ghi xuống `teacher_turns` trước khi phát đi. SSE là chất tăng tốc; F5 dựng lại màn
hình từ database.

## Global Constraints

- AGENT **không** có credential database và **không** có cổng HTTP. Tiến độ đi qua Redis pub/sub.
- Bất biến *một job = một lần gọi model* (`tools/check_contract.py`). Báo cáo là **task riêng**.
- Pha 1 **không có tool ghi** trong catalog. Pha 2 chỉ chạy tool ghi, trong một plan.
- FE không quyết luật: `k/n`, trạng thái bước, số câu đều do BE gửi.
- Tiếng Việt cho mọi chuỗi ra màn hình, comment và docs; identifier và log tiếng Anh.
- Figma và code đổi cùng một change set; chứng minh bằng đo, không bằng mắt.
- **Sau mỗi pha: `.\dev.ps1 check` + `.\dev.ps1 test` + test FE xanh → gọi subagent review → xin
  phép commit.** Không commit khi chưa được cho phép.

## Review Focus

Năm ca ADR ngụ ý mà đường đi hạnh phúc không chạm tới. Mỗi ca một test, nằm ở task sở hữu nó:

1. **Bước sau cần id của bước trước** — `start_drafting` cần `assessment_id` mà `create_draft` mới
   sinh ra. Plan tĩnh phải diễn tả được chuyện đó (Task 2).
2. **Plan cũ đi giữa lúc dựng và lúc chạy** — tab khác duyệt đề trong khe ấy → bước ghi gặp đề đã
   khoá → dừng plan, báo cáo vẫn chạy (Task 4).
3. **Model trả một plan chứa tool không có trong catalog pha 2**, hoặc args thiếu → từ chối cả plan
   trước khi chạy bước nào, không chạy nửa chừng (Task 3).
4. **Không ai mở SSE lúc AGENT phát tiến độ** — tin pub/sub không bền. Câu hỏi vẫn phải vào đề
   (Task 5).
5. **Giáo viên đóng tab giữa pha 2** — lượt vẫn chạy hết và ghi đủ; mở lại thấy đúng trạng thái
   (Task 6).

---

## Pha A — Hợp đồng và ranh giới catalog

### Task 1: Kiểu của một plan và task báo cáo

**Files:** `packages/contracts/src/contracts/teacher_chat.py`, `packages/contracts/src/contracts/__init__.py`

`PlanStep(tool_name: str, args: dict[str, str], title: str)` — `title` là câu tiếng Việt hiện trên
khối bước. Plan **không** là một message riêng: `kind="plan"` và `steps` là hình dạng thứ tư của
`NextStepCompleted`, vì một lượt suy nghĩ trả về một thứ chứ không hai. `REPORT_PLAN_TASK`,
`PlanReportRequested(schema_version, request_id, said, outcomes)`, `StepOutcome(title, ok, detail)`,
`PlanReportCompleted(schema_version, request_id, text)`. Tất cả `frozen=True`, mở đầu bằng
`schema_version` + `request_id`, thêm vào import block **và** `__all__`.

Hai luật đối xứng trong một validator: `plan` phải có ít nhất một bước, và **chỉ** `plan` được chở
`steps` — nếu không thì mọi nhánh của vòng lặp phải nhớ bỏ qua chúng, và một luật phải nhớ là một
luật sẽ quên.

Test: `packages/contracts/tests/test_teacher_plan.py` — gán thật rồi bắt `ValidationError` (đọc
`model_config` là đọc cái cờ, không phải hành vi), payload báo cáo không có field nào kết thúc bằng
`_id` ngoài `request_id`, và `say` kèm `steps` bị từ chối.

### Task 2: Catalog chia theo pha, và tham chiếu `$prev`

**Files:** `services/be/src/be/teacher_tools.py`, `services/be/tests/test_write_tools.py`

- `catalog_for(asking, phase)` — pha 1 trả `find_class`, `class_assessment_summary`,
  `draft_progress`; pha 2 trả `create_draft`, `start_drafting`.
- **`draft_progress` bỏ `harvest`.** Hôm nay nó khai `writes=False` (`teacher_tools.py:664-673`)
  nhưng thân nó ghi `Question` và đẩy state sang `HAS_QUESTIONS` (`drafting.py:452`) — tức câu *"pha
  1 không ghi gì"* sai ở chính tool đầu tiên nếu không sửa. Thu hoạch chuyển về đường nghe chuông
  (Task 7) và cổng duyệt (đã có sẵn). Cờ `writes` của nó sửa cho đúng cùng lúc.
- `resolve_args(args, done)` — giá trị `"{k.tên_field}"` lấy `tên_field` trong kết quả của **bước
  thứ k** (đếm từ 1). Dùng số bước chứ không dùng "bước trước" vì một plan ba bước có thể tham chiếu
  ngược hai bước. Model chỉ trả về được chuỗi phẳng (`_Argument{name, value}` —
  `propose.py:84-124`), nên một chuỗi như thế là thứ duy nhất đi lọt qua structured output.

`resolve_args` giải cho **một bước**, ngay trước khi bước ấy chạy. Một chuỗi *trông như* tham
chiếu mà sai khuôn (`{0.x}`, `{1.x} thêm chữ`, `{ 1.x }`) là lỗi của model chứ không phải chữ của
giáo viên, nên nó cũng `Unresolvable`; để nó đi tiếp nguyên văn là đưa một id rác tới tay một tool
ghi. Một field có mặt mà rỗng, hoặc không phải giá trị đơn, cũng vậy.

Phép kiểm **trọn gói** một plan trước khi chạy bước nào là chuyện của Task 3: nó tĩnh, nên nó kiểm
được `k < số thứ tự bước` mà không cần kết quả thật.

Test: `test_a_plan_step_reads_the_id_the_step_before_it_made`,
`test_a_reference_that_cannot_be_resolved_stops_the_step` (năm ca),
`test_a_reference_to_an_empty_field_is_refused`, `test_reading_progress_does_not_write_anything`,
`test_a_read_tool_asked_for_while_working_is_refused`.

**Cổng qua pha:** bốn đột biến, mỗi cái phải làm đỏ ít nhất một test: cho tool ghi vào pha lên
plan; cho `{0.x}` lọt; bỏ phép kiểm "trông như tham chiếu"; bỏ luật chỉ-plan-mới-chở-steps.

**Một món nợ Pha A tự tạo ra, và Pha D trả.** Bỏ `harvest` khỏi `draft_progress` nghĩa là giữa một
lượt không còn đường thu hoạch nào: `still_drafting` không giảm và `written` rỗng cho tới khi giáo
viên bấm duyệt hoặc soạn thêm. Vì vậy **Pha A tới Pha D ra cùng một lần release**, không deploy
riêng Pha A. Dòng `draft_progress` trong `docs/overview/teacher-surface.md` cũng chỉ đúng trở lại
khi Pha D xong.

---

## Pha B — BE: hai pha trong một generator

### Task 3: `run_turn()` và việc nhận một plan

**Files:** `services/be/src/be/teacher_chat.py`, `services/be/tests/test_teacher_chat.py`

`async def run_turn(...) -> AsyncIterator[TurnEvent]` phát: `say`, `clarify`, `plan_ready`,
`step_started`, `step_done`, `step_failed`, `progress`, `report`, `done`. Pha 1 giữ nguyên
`max_tool_steps = 8` và `turn_budget_seconds = 90`.

Plan bị **từ chối trọn gói** trước khi chạy bước nào khi: tool không thuộc catalog pha 2, args thiếu
trường bắt buộc, hoặc `{k.field}` trỏ vào thứ không tồn tại. Từ chối thì lượt kết thúc bằng một câu
nói, không phải một bước hỏng.

Plan **được lưu** như một lượt trong `teacher_turns` — không lưu thì một lần F5 làm mất nó trong khi
màn hình hứa dựng lại được. Một `kind` mới, và `_rendered` phải trả nó về cho FE.

`POST /teacher/chat/messages` drain generator và trả `Answered` y như cũ — **sáu test hiện có không
được sửa một dòng nào**. Đó là bằng chứng hai cửa dùng chung một bản cài đặt.

### Task 4: Chạy plan, dừng đúng chỗ, rồi báo cáo

**Files:** `services/be/src/be/teacher_chat.py`, `services/be/tests/test_teacher_chat.py`

Chạy tuần tự; một bước hỏng → `step_failed` → **không chạy bước sau** → vẫn gọi báo cáo. Báo cáo là
`run_task(REPORT_PLAN_TASK, ...)`, nuốt `AgentError` và lùi về một câu do BE viết — một lượt không
bao giờ chết vì phần kể lại.

Test: `test_a_failed_step_stops_the_plan_and_still_reports`,
`test_an_approved_assessment_met_mid_plan_stops_instead_of_writing`.

**Cổng qua pha:** `.\dev.ps1 test` xanh; break-to-test ba chỗ; **subagent review code BE**.

---

## Pha C — AGENT: prompt pha 1, và lời báo cáo

### Task 5: Model trả về một plan

**Files:** `services/agent/src/agent/graphs/propose.py`, `services/agent/tests/`

`_SYSTEM` viết lại: pha 1 chỉ tra cứu và hỏi lại; khi đủ dữ kiện thì **nêu plan** gồm các bước ghi,
mỗi bước một câu tiếng Việt. Bỏ hẳn lời dặn *"Sau create_draft thì gọi start_drafting"* — nó mô tả
một thế giới không còn.

### Task 6: Task báo cáo

**Files:** `services/agent/src/agent/graphs/reporting.py` (mới), `handlers.py`, `worker.py`

Theo đúng khuôn năm bước của bốn handler hiện có: validate → `if not llm.enabled(): return mock` →
`try: await graph(...)` → `except: logger.exception` → lùi về mock. Mock: ghép từ `outcomes`, không
gọi model.

**Cổng qua pha:** test AGENT không gọi model thật; `check_contract` vẫn 7/7; **subagent review**.

---

## Pha D — Tiến độ chảy về

### Task 7: AGENT phát, BE nghe

**Files:** `services/agent/src/agent/handlers.py`, `services/be/src/be/drafting.py`

AGENT `publish` một **cái chuông** lên kênh của lượt sau khi viết xong một câu — dùng chính
`ctx["redis"]` arq đã cấp, đúng như đường kèm học của học sinh đã làm (`handlers.py:773-779`). Kênh
do **BE sinh cho một lượt** và BE `subscribe` **trước khi `fire` đẩy job**, theo khuôn
`agent_gateway.py:100-104` và `student_routes.py:1712+`. Mỗi tiếng chuông thì `harvest` rồi phát
`progress`.

Chuông chở **một con số, không chở câu hỏi**: câu hỏi vẫn đọc từ result store của arq
(`drafting.py:402`). Tin pub/sub không bền, nên không ai nghe thì **không mất gì** — thu hoạch ở lần
quan sát sau vẫn đưa đủ câu vào đề. **BE vẫn không có worker chạy nền**; chuông chỉ cắt độ trễ cho
một người đang nhìn. Test: `test_a_question_lands_even_when_nobody_listened`.

**Cổng qua pha:** test BE xanh; **subagent review** đường pub/sub.

---

## Pha E — SSE và FE

### Task 8: Cửa SSE

**Files:** `services/be/src/be/teacher_chat.py`, `services/be/tests/test_stream_task.py`

`POST /api/teacher/chat/messages/stream` trả `text/event-stream`, forward từng sự kiện của
`run_turn()`. Mọi sự kiện **đã ghi** trước khi phát. Mất kết nối không dừng lượt: generator chạy tới
hết.

### Task 9: FE đọc stream và vẽ theo thứ tự nhận được

**Files:** `services/fe/src/api.ts`, `Chat.tsx`, `Steps.tsx`, `ActionCard.tsx`, `teacher.test.tsx`

`fetch` + đọc body stream (không `EventSource`: lượt gửi bằng POST). Một lượt là **một dãy đoạn**
theo thứ tự tới: lời nói, cụm bước, thẻ hỏi lại, thẻ kết quả. Bước liên tiếp gộp một khối `Thinking`;
một câu nói chen vào thì đóng khối. Khối `Thinking` sống: `bước k/n`, dấu `○` cho bước đang chạy,
số câu tăng dần. Thẻ chỉ mọc cho kết quả **còn đứng vững tới cuối lượt**.

Test: `test_cac_doan_hien_dung_thu_tu_nhan_duoc`, `test_khoi_buoc_thu_lai_khi_luot_xong`,
`test_khong_co_the_cho_de_trong_khi_plan_con_buoc_sau`.

**Cổng qua pha:** test FE xanh; **subagent review trên browser thật**, đo đối chiếu artboard 2/3/4/5.

---

## Pha F — Figma và tài liệu

### Task 10: Figma nói đúng ý tưởng

- Ghi chú trên page `Screen — Teacher`: thread là **dãy khối theo thứ tự agent trả về**; artboard là
  ảnh chụp một trường hợp, không phải kịch bản.
- Mô tả component `Thinking` (`83:76`): cập nhật liên tục trong pha 2; `k/n` lấy từ số bước của plan.
- Artboard 4: thêm dòng tiến độ số câu (`đã soạn 4/10 câu`) nếu đo cho thấy FE cần một chỗ đặt nó.

**Đã làm trước Pha F** (cùng lúc viết lại hội thoại mẫu): artboard 4 và 5 nay chụp đúng một plan hai
bước — `bước 2/2`, `Tạo đề trống` ✓, `Soạn 10 câu hỏi` ○ kèm dòng `— đã soạn 4/10 câu`; artboard 5 đổi
`Đã làm 5 bước` → `Đã làm 2 bước`, câu kết và thẻ bỏ hết chữ về ngân hàng câu hỏi. Mô tả component
`Thinking` (`83:76`) thêm ba luật: hai con số hai chỗ đứng, khối sống trong pha 2, và artboard là ảnh
chụp. Đo lại: `đang chạy` 820×154 cho hai bước hai dòng, `đã xong` 820×40 — khớp `teacher.css`.

### Task 11: Tài liệu kể đúng hiện trạng

`docs/overview/teacher-surface.md` viết lại phần luồng theo hai pha; `adr-25` đổi trạng thái sang
*đang thi hành* kèm mục **Nơi luật này đang được thi hành** trỏ tới file thật; `backlog.md` xoá món
*"BE không có worker chạy nền"* nếu Pha D đã trả nó.

**Cổng cuối:** `.\dev.ps1 check` 7/7, toàn bộ test xanh, **một subagent review cả nhánh**, rồi xin
phép commit.

---

## Verification

- Một lượt thật qua giao diện với `gpt-4o-mini`: gõ *"tạo đề 10 câu về tích phân cho 12A"*, xem khối
  bước chạy, số câu tăng, thẻ kết quả ghi đúng 10 câu, câu báo cáo do model viết.
- Thiếu dữ kiện: gõ *"tạo cho tôi một đề"* → ra câu hỏi lại, **không** bước `✕`, **không** thẻ, và
  database **không** có đề rỗng nào mới.
- Đóng tab giữa pha 2, mở lại → đúng trạng thái, không mất bước nào.
- Đo khối `Thinking` khi đang chạy và khi đã xong, đối chiếu artboard 4 và 5.

### Task 12: Mua một check cho luật mới

**Files:** `tools/check_contract.py`, `AGENTS.md`

Luật *"báo cáo là một job riêng"* hiện **không check nào bắt được**: check gần nhất là
`check_model_call_fits_inside_the_job_waiting_for_it`, và nó chỉ canh thứ tự timeout — docstring của
chính nó đã nhận là không thấy được một vòng lặp mới (`check_contract.py:187-189`). Một luật không có
nơi thi hành là một ý định. Check mới: `report_plan` phải có tên task riêng trong `worker.py` và
`teacher_chat.py` không được gọi model báo cáo trong cùng vòng lặp của pha 1.

## Rủi ro đã biết

Phản biện ADR-25 đã về và ADR đã sửa theo nó. Ba chỗ còn là rủi ro thật:

- ~~**Hai con số `k/n`.**~~ Đã giải: dòng kết quả của bước đang chạy là chỗ đặt số câu, artboard 4 đã
  có sẵn nó, nên không hàng nào phải thêm và hai sự thật không bị gộp.
- **Đóng tab giữa lúc soạn.** Các bước plan chạy trong request (dưới một giây mỗi bước), việc soạn
  câu sống trong arq và không phụ thuộc request. Câu báo cáo khi đó được viết ở **lần quan sát kế
  tiếp**. Task 4 phải có test cho đường ấy.
- **Hai tab cùng một đoạn chat.** Chưa có khoá nào cho *"đoạn chat này đang chạy một plan"*. Task 3
  phải quyết: một plan thứ hai bị từ chối, hay hai plan chạy song song.

Review Pha C bổ sung bốn món nợ, tất cả đáo hạn ở Pha D/E:

- **Luật "đang soạn" đang là một câu trong prompt, phải thành dữ liệu.** `reporting.py:_SYSTEM` dặn
  cứng *"nói là 'đang soạn' chứ không nói 'đã soạn xong'"*. Nó đúng **chỉ vì** hôm nay báo cáo chạy
  ngay sau bước cuối, lúc arq còn đang soạn. Pha D làm pha 2 xong **sau khi** hết câu đang soạn, và
  đúng lúc đó dòng prompt này biến thành máy sinh lời nói sai chiều ngược lại. Task 7 phải chuyển nó
  vào `PlanReportRequested` (còn bao nhiêu câu đang soạn), rồi xoá khỏi prompt.
- **`StepOutcome` không có chỗ cho con số thật.** `detail` của `start_drafting` mãi là *"10 câu bắt
  đầu soạn"*. Câu kết của artboard 5 — *"8 câu lấy từ ngân hàng, 2 câu tôi soạn thêm"* — **không có
  field nào để đi qua**. Quyết ngay ở Task 7 trong lúc hợp đồng chưa deploy, nếu không là một lần
  bump `SCHEMA_VERSION` nữa.
- **Không có cờ "lượt này đã báo cáo chưa".** ADR nói đóng tab giữa lúc soạn thì câu kết viết ở lần
  quan sát kế tiếp; `_report` hôm nay chạy đúng một lần và lượt được ghi `kind="assistant"` ngay sau
  đó. Task 8 phải phân biệt được hai trạng thái ấy trong `teacher_turns` — hiện không có chỗ.
- **Lời gọi báo cáo không nằm trong ngân sách nào.** Nó là lời gọi model thứ hai (thứ ba nếu tính
  đặt tên) trong cùng một request POST, **sau** `turn_budget_seconds = 90` của pha 1, chỉ bị chặn bởi
  job timeout. Vô hại khi Pha E mở SSE; chừng nào `POST` còn rút cạn generator thì p99 của endpoint
  là `90s + report + naming`.
