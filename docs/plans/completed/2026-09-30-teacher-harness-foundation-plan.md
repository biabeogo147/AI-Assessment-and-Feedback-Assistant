# Nền móng harness cho platform giáo viên

Plan bắt buộc theo `AGENTS.md`: thay đổi này chạm `packages/contracts`, một tên task queue, một
endpoint, một biến `.env.example` và chính `AGENTS.md`.

## Context

Platform học sinh đã chạy thật end-to-end. Platform giáo viên khác về bản chất: **mọi thứ xuất phát từ
khung chat**, nên agent phải tự chọn việc cần làm thay vì thi hành một việc BE đã quyết. Thứ quyết định
thành bại là harness, không phải prompt.

Bốn việc trong plan này là **nền móng**, xếp theo thứ tự phụ thuộc chứ không theo thứ tự quan trọng.
Chúng được chọn sau một vòng debate với subagent, trong đó năm khẳng định của tôi bị bắt sai và đã
kiểm chứng lại bằng file:

- `draft_assessment` đã tồn tại nhưng **không caller nào ở BE** — task đầu tiên của platform giáo viên
  đang là code chết (`worker.py:79`; `grep DRAFT_ASSESSMENT_TASK services/be` không ra gì).
- Vòng lặp trong AGENT **đã có** (`graphs/authoring.py` write→check→write). Cái chưa có là vòng lặp *tool*.
- `SchoolClass` có đúng `id` + `name`; `Assessment` **không có tác giả**; `classes.name` **không unique**.
  ADR-13 chốt "lớp thuộc về giáo viên" và không dòng code nào thi hành.
- `ChatMessage` có FK tới `attempts` + `UniqueConstraint(attempt_id, sequence)` → hội thoại giáo viên
  không dùng lại được bảng đó.
- `check_model_call_fits_inside_the_job_waiting_for_it` **đang nói dối**: nó nhân
  `llm_timeout_seconds × llm_max_attempts` = 60 < 70, nhưng `draft_assessment` gọi
  `question_count × llm_max_attempts` lần, mà `question_count` tới 50 (`contracts/authoring.py:97`).

## Scope

**Trong scope:** schema, máy trạng thái, vòng lặp tool ở BE, task AGENT mới (thứ năm trong worker), giải nghĩa thực thể,
bảng hội thoại giáo viên. Hai tool chỉ-đọc để chứng minh vòng lặp chạy.

**Ngoài scope, có chủ đích:**

- **Không có FE.** Plan này không chạm màn hình nào, nên **luật Figma không kích hoạt** lần này.
  Kiểm chứng bằng pytest và `curl`, không bằng trình duyệt.
- **Không có tool phát hành.** Cách tuân thủ ADR-05 rẻ nhất ở v1 là không có hành động bất khả hồi nào
  để mà cần cổng. Phát hành cần 6 tham số và ADR-03 dành cả một tài liệu để ngăn đúng một hiểu nhầm
  ("giờ đóng là hạn *vào*, không phải hạn *nộp*"); một model điền 6 mốc thời gian từ chữ "chiều mai"
  sẽ tái tạo chính xác hiểu nhầm đó.
- **Không sửa check timeout đang nói dối.** Sửa nó cho đúng sẽ làm nó **đỏ** (50 × 3 × 20s = 3000s so
  với 70s), và đường ra là một câu hỏi thiết kế thật về ngân sách job của `draft_assessment`, không
  phải một dòng sửa. Ghi vào `backlog.md` kèm bằng chứng trong Việc 2.
- Không idempotency (đường ghi duy nhất là tạo đề nháp; một đề nháp trùng là phiền, không phải thiệt hại).
- Không cắt ngữ cảnh, không huỷ lượt, không eval.

## Ngân sách model

Cả bốn việc chạy sạch bằng mock. `LLM_ENABLED=false` là mặc định và `conftest.py` cắm fake autouse cho
cả suite. **Gọi model thật đúng một lượt ở cuối mỗi việc**, chỉ để xác nhận việc đó đã thông, và chỉ
bằng `gpt-4o-mini`.

## Files

| File | Việc |
| --- | --- |
| `docs/plans/active/2026-09-30-teacher-harness-foundation-plan.md` | **mới** — chính file này |
| `docs/decisions/adr-22-de-co-tac-gia.md` | **mới** — đề có tác giả, quyền xem đi theo tác giả |
| `docs/decisions/adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md` | **mới** — ADR-05 cổng ba, thi hành thật |
| `services/be/src/be/models.py` | `teacher_id` trên `classes`/`assessments`; `state` thành Enum bốn giá trị; bảng `TeacherTurn` |
| `services/be/src/be/assessment_state.py` | **mới** — bảng cạnh ADR-01, `advance()`, `assert_editable()` |
| `services/be/src/be/resolve.py` | **mới** — `resolve_class()` trả ba kết quả |
| `services/be/src/be/teacher_tools.py` | **mới** — danh mục tool theo giáo viên, executor kiểm lại quyền |
| `services/be/src/be/teacher_chat.py` | **mới** — vòng lặp tool, endpoint chat giáo viên |
| `services/be/src/be/seed.py` | gán lớp và đề cho `GV-001` |
| `services/be/src/be/config.py` | `max_tool_steps` |
| `packages/contracts/src/contracts/teacher_chat.py` | **mới** — `PROPOSE_NEXT_STEP_TASK` và các kiểu |
| `services/agent/src/agent/graphs/propose.py` | **mới** — một lượt suy nghĩ |
| `services/agent/src/agent/handlers.py` | handler `propose_next_step` + mock |
| `services/agent/src/agent/worker.py` | đăng ký task thứ năm |
| `services/agent/tests/conftest.py` | fake trả JSON theo schema |
| `.env.example` | `MAX_TOOL_STEPS` |
| `AGENTS.md` | dòng invariant "Teacher approves an assessment before release" → check tự động |
| `docs/overview/data-model.md` | chủ sở hữu tài liệu schema — cập nhật cùng change set |
| `docs/plans/backlog.md` | check timeout nói dối; mục thống kê điểm đã cũ |

## Ordered Tasks

Mỗi việc kết thúc bằng: `.\dev.ps1 test` + `.\dev.ps1 check` xanh → **gọi 1 subagent review** → sửa hết
phát hiện → **dừng cho bạn review** → mới sang việc sau.

### Việc 1 — Cạnh sở hữu và máy trạng thái đề

- [x] Ghi plan này vào `docs/plans/active/`
- [x] `adr-22-de-co-tac-gia.md`: đề có tác giả; giáo viên chỉ thấy đề của mình; lớp không tìm thấy và
      lớp của người khác trả về **cùng một câu trả lời**, để không tiết lộ sự tồn tại
- [x] `models.py`: `teacher_id` FK trên `SchoolClass` và `Assessment` + relationship hai chiều
- [x] `models.py`: `state` từ `String(16)` sang Enum bốn giá trị ADR-01 (`EMPTY`, `HAS_QUESTIONS`,
      `APPROVED`, `PUBLISHED`). Docstring hiện nói **ba** trạng thái — nó đã lệch ADR-01 từ trước
- [x] `assessment_state.py`: bảng cạnh cho phép, `advance()` raise 409 tiếng Việt khi cạnh không tồn
      tại, `assert_editable()` cho mọi đường sửa câu hỏi
- [x] `seed.py`: gán lớp và đề cho `GV-001`
- [x] Test: một test mỗi cạnh hợp lệ; một cạnh bất hợp lệ; sửa câu hỏi trên đề `APPROVED` bị từ chối;
      giáo viên khác không thấy lớp/đề
- [x] `AGENTS.md`: chuyển dòng "Teacher approves an assessment before release" từ *chưa enforce* sang
      *automatic*, trỏ tới test mới. Sweep bốn `AGENTS.md` con và `CLAUDE.md` cùng change set
- [x] Cập nhật mục "Nơi luật này đang được thi hành" của ADR-01 và ADR-13 — cả hai đang ghi
      "Chưa có ở backend", và câu đó sắp thành sai
- [x] `data-model.md`
- [x] **Làm ở Việc 2, và làm khác kế hoạch: không xoá gì cả.** `prepare_schema` chỉ `create_all` nên
      DB dev cũ không tương thích schema mới. Kế hoạch ghi "xoá và seed lại", nhưng
      `DROP SCHEMA public CASCADE` là xoá sạch một database có dữ liệu thật và **đã bị chặn** — chặn
      đúng. Đường an toàn hơn và đáng ra tôi nên chọn ngay từ đầu: tạo database **mới**
      `aiafa_teacher` rồi trỏ `DATABASE_URL` vào đó. Database `aiafa` cũ còn nguyên, và quyết định
      chuyển hay bỏ nó là của bạn

### Việc 2 — Vòng lặp tool ở BE

- [x] `contracts/teacher_chat.py`: `PROPOSE_NEXT_STEP_TASK`, `ToolSpec`, `TurnRecord`,
      `NextStepRequested`, `NextStepCompleted` với `kind: say | call_tool | ask_clarify`
- [x] **Kiểm giả thuyết trước khi xây lên nó — kết quả: KHÔNG được.** Probe cho thấy `with_structured_output` +
      `GenericFakeChatModel` ném `NotImplementedError`, nên đường đó không có. Đã viết fake riêng
      theo khuôn `Scripted` của `test_authoring_graph.py`
- [x] `graphs/propose.py` + handler `propose_next_step` + mock khi `llm.enabled()` là false
- [x] `worker.py`: đăng ký task thứ năm (`draft`, `retry`, `explain`, `grade_submission` legacy, rồi `propose`)
- [x] `teacher_tools.py`: danh mục dựng **theo từng request** từ quyền của giáo viên; `execute()`
      **kiểm lại** quyền sở hữu. Hai tầng, vì tầng thứ nhất do model đọc và model đọc sai được
- [x] Hai tool chỉ-đọc: `find_class`, `class_assessment_summary`. Trả **tóm tắt đã gộp ở BE**, không
      trả hàng — "lớp 11B hôm qua thế nào" là 40 học sinh × 10 câu
- [x] `teacher_chat.py`: vòng lặp `for _ in range(max_tool_steps)`, nhánh `else` nói thật với giáo
      viên khi chạm trần thay vì im lặng
- [→] **Chuyển sang `backlog.md`.** Tick sai ở lần đầu: tôi tick cả khối Việc 2 bằng một phép
      thay thế hàng loạt, nên hai ô việc *tương lai* cũng bị tick theo. Không có endpoint phát hành
      nào trong repo, nên không thể có test cho nó. Test rằng **đường HTTP** phát hành từ chối đề
      chưa duyệt. Hôm nay
      `test_teacher_approves_an_assessment_before_release` khoá hàm `advance()` mà chưa caller nào
      gọi, nên dòng invariant trong `AGENTS.md` đúng về chữ và mỏng về tinh thần cho tới khi có test
      này. Không gì buộc một tool đi qua `advance()`; một phép gán `state = PUBLISHED` viết rời vẫn
      qua mặt được
- [→] **Chuyển sang `backlog.md`**, cùng lý do tick sai như ô trên. Bất biến giữa `state` và số câu hỏi. `advance(..., APPROVED)` hiện không
      đếm `assessment.questions`, nên một đề `has_questions` với **0 câu** duyệt và phát hành trôi
      chảy. Chưa sửa ở Việc 1 vì đọc `.questions` trong ngữ cảnh async sẽ lazy-load và nổ
      `MissingGreenlet`; chỗ đúng để kiểm là endpoint duyệt, nơi đã có sẵn session để đếm
- [x] `config.py` + `.env.example`: `MAX_TOOL_STEPS`. Mọi biến trong `.env.example` phải được một
      `Settings` đọc, nếu không `dev.ps1 check` đỏ
- [x] Test: chạm trần thì dừng; vòng lặp thực thi được tool đọc; `execute()` từ chối tool của lớp
      người khác kể cả khi model xin; đường mock chạy không cần model
- [x] `backlog.md`: check timeout nói dối, kèm số cụ thể và vì sao chưa sửa

### Việc 3 — Giải nghĩa thực thể

- [x] `adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md`: không đoán; lựa chọn đến **từ DB**, không do model
      bịa. Ghi rõ rằng phần *cấm đánh dấu nên chọn* của ADR-05 áp ở đây, còn phần *mỗi lựa chọn tự nêu
      cái giá* thì không — luật đó viết cho quyết định sư phạm, còn phân định tên lớp không có giá nào
      để nêu
- [x] `resolve.py`: `resolve_class()` → `Resolved | Ambiguous | NotFound`, tìm **chỉ trong lớp của
      giáo viên đó**, chuẩn hoá hoa/thường và khoảng trắng
- [x] Nối vào executor: `Ambiguous`/`NotFound` về vòng lặp như **kết quả tool có cấu trúc** mang ứng
      viên thật, không phải exception
- [x] Test: khớp đúng; hai lớp cùng tên → `Ambiguous` đủ hai ứng viên; không có → `NotFound` kèm danh
      sách lớp của giáo viên; lớp của giáo viên khác → **cùng đáp án với không tồn tại**

### Việc 4 — Bảng hội thoại giáo viên

- [x] `models.py`: `TeacherTurn` với `UniqueConstraint(conversation_id, sequence)` — sao chép có ý
      thức từ `ChatMessage`, vì StrictMode mở stream hai lần *theo thiết kế* và một lần kiểm rồi chèn
      là hai câu lệnh có khe ở giữa
- [x] Trường: `kind` (`teacher|assistant|tool_call|tool_result` — **bốn**, không năm: `ask_clarify`
      lưu là `assistant`, vì nó *là* một lượt trợ lý nói; cái phân biệt nó nằm ở `Answered.kind` của
      lượt đó, không phải ở hàng), `text`, `tool_name`, `tool_args`, `tool_result`, `entity_kind`,
      `entity_id`, `model_tokens`, `duration_ms`
- [→] **Chuyển sang `backlog.md`. Cấu trúc có, dữ liệu chưa.** `entity_kind`/`entity_id` tồn tại và có đường ra API qua `Turn`,
      nhưng hiện chỉ một tool sinh ra subject (`find_class` → `class`). Bảy variant `Action result
      card` mà ô này từng tuyên bố — `tạo-đề-trống`, `thêm-câu-hỏi`, `đã-duyệt`, `bỏ-duyệt`,
      `đã-phát-hành`, `phát-hành-thất-bại`, `tạo-lớp` — đều là **hành động ghi**, mà Scope của plan
      nói rõ đợt này không có tool ghi nào. Ô này tick được khi có tool ghi đầu tiên. Nhánh
      `assessment_id` từng nằm trong `_ENTITY_KEYS` đã bị bỏ: không tool nào trả về nó, nên đó là một
      nhánh không input nào chạm tới
- [x] Vòng lặp ghi hàng **trước** khi trả lời, và commit theo **từng bước** — worker chết giữa lượt
      thì mất bước đang làm, không mất cả hội thoại. Việc ghi-trước-khi-stream thì **chưa áp được**:
      đường giáo viên chưa có streaming nào, vì `stream_channel` đã bị bỏ khỏi `NextStepRequested` ở
      Việc 2 (một lượt là nhiều lần gọi model, chỉ lần cuối sinh chữ). Luật vẫn đúng, chỉ chưa có
      chỗ để thi hành
- [x] `model_tokens` mỗi lượt — và **không "gần như miễn phí"** như decision record của tôi viết.
      `with_structured_output` trả về object đã parse và bỏ mất response chở báo cáo usage, nên phải
      thêm `include_raw=True` cùng một field trong contract. Chỗ đọc là `_spent()` trong `propose.py`,
      và nó có test cho **cả hai** hình dạng response, vì đây đúng là loại khẳng định về thư viện mà
      tôi đã sai ba lần trong plan này
- [x] Test: lượt sống qua reload; ghi trùng `sequence` bị chặn; trace đọc được bằng một `SELECT`
- [x] `data-model.md`

## Decision Records

### Decision: Vòng lặp tool nằm ở BE, không ở AGENT

options considered:

- **A. Vòng lặp ở BE; AGENT nhận task "một lượt suy nghĩ".** Mỗi vòng = một arq job = một lần gọi model.
- **B. Vòng lặp ở AGENT; mỗi tool là một chuyến khứ hồi ngược về BE.** Dùng được agent executor sẵn có
  của framework, ít code hơn.

selected option: A.

reason: bốn thứ, thứ nhất là cụ thể nhất. `check_contract.py:46-49` quét **mọi dòng `.py`** trong
`services/agent` tìm `POSTGRES|MONGO|DATABASE_URL|DSN|PASSWORD|sqlalchemy|...`; ADR-13 có thao tác đặt
lại mật khẩu học sinh, nên một tool tên `reset_password` — kể cả chỉ là tên trong danh mục hay một chữ
trong docstring — **làm đỏ build** nếu ở AGENT. Danh mục tool không sống được ở AGENT. Thứ hai, authz
chạy trong đúng process đang giữ session và `current_teacher`, nên giới hạn theo giáo viên là *cấu
trúc* chứ không phải *lời hứa*; phương án B đòi forward identity vào AGENT, một cơ chế mới thuộc đúng
loại dễ sai. Thứ ba, một job = một lần gọi nên invariant timeout **trở lại có nghĩa** với đường mới;
phương án B biến một job thành N lần gọi model cộng N lần gọi BE và buộc `agent_job_timeout_seconds`
lên phút, làm chậm luôn việc phát hiện worker chết thật. Thứ tư, AGENT không được ghi DB, nên B mà
worker chết giữa vòng thứ ba là mất cả lượt **không để lại bản ghi**; A thì mỗi bước đã nằm trong DB
trước khi bước sau bắt đầu. Giá phải trả của A, ghi ra để không ai tưởng nó miễn phí: payload chở lại
cả transcript mỗi vòng, và `_POLL_SECONDS = 0.2` (`agent_gateway.py:28`) cộng ~0,2–0,4s phí thuần mỗi
vòng — năm vòng là khoảng hai giây trả cho riêng việc xếp hàng.

Kèm một luật để không phải tranh lại: **vòng lặp nội dung ở AGENT, vòng lặp tool ở BE.**
`authoring.py` write→check→write ở lại AGENT; nó không cần tool và không cần DB.

### Decision: `propose_next_step` dùng structured output, không dùng tool-calling nguyên bản

options considered:

- **A. `with_structured_output(NextStepCompleted)`** — model trả JSON; `kind` phân biệt nói / gọi tool
  / hỏi lại.
- **B. Tool-calling nguyên bản của provider** — hành vi tốt hơn, nhưng phụ thuộc provider.

selected option: A. Giữ nguyên sau khi đo, nhưng **lý do ban đầu của tôi sai**.

reason: A thắng vì `authoring.py` đã dùng structured output nên đây là pattern sẵn có, và vì cả mục
tiêu adapter lẫn dây fallback Gemini đều nói nên tránh chỗ phụ thuộc provider. B đòi một fake mới
biết phát tool call.

**Chỗ tôi đoán sai, đã đo:** tôi viết rằng A "mở rộng hạt giống test sẵn có gần như miễn phí, chỉ cần
xếp sẵn vài chuỗi JSON" vào `GenericFakeChatModel` của `conftest.py`. Chạy thử thì
`GenericFakeChatModel.with_structured_output` ném `NotImplementedError: with_structured_output is not
implemented for this model`. Không có đường nào nạp JSON vào nó.

Đường đúng đã có sẵn trong repo và tôi không nhìn ra khi viết plan: `test_authoring_graph.py` tự viết
một fake `Scripted` có `with_structured_output` trả `RunnableLambda`. Test của graph mới dùng đúng
khuôn đó.

Hệ quả phụ, tốt hơn tôi tưởng: fake autouse trong `conftest.py` **không** che được đường structured
output — nên một test lỡ chạm đường model thật sẽ nổ `NotImplementedError` to và rõ, thay vì im lặng
gọi provider. Lưới ấy chặt hơn tôi nghĩ, chỉ là chặt theo cách khác.

### Decision: Bảng mới cho hội thoại giáo viên, và trace ở luôn trong đó

options considered:

- **A. Bảng `TeacherTurn` mới, chở cả args/kết quả/thời lượng/token.**
- **B. Mở rộng `ChatMessage`.**
- **C. Bảng hội thoại riêng + hệ trace riêng.**

selected option: A.

reason: B không khả thi về kỹ thuật, không phải về khẩu vị — `ChatMessage.attempt_id` là FK tới
`attempts` với `UniqueConstraint(attempt_id, sequence)`, mà hội thoại giáo viên không có attempt nào.
C là làm hai lần một việc: nếu hàng đã chở args, kết quả, thời lượng và token thì trace là một câu
`SELECT`. Và với một agent gần như toàn năng thì không có trace là không debug được — giáo viên chỉ
báo "nó làm sai", còn chuỗi mười bước dẫn tới đó thì không ai thấy. ADR-01 còn đòi thẳng: *"Bỏ duyệt
phải để lại bằng chứng trong luồng chat như mọi thao tác khác"* — bảng này **là** cái bằng chứng đó.

### Decision: Lựa chọn của câu hỏi hỏi lại do BE dựng, không lọc chữ của model

options considered:

- **A. BE dựng lựa chọn** từ `candidates` của kết quả tool; `choices` model trả về bị **bỏ qua**.
- **B. Lọc `choices` của model**, giữ lại cái nào đối chiếu được với hàng BE đã đọc.
- **C. Tin model**, chỉ nhắc trong prompt.

selected option: A. Ban đầu tôi làm B.

reason: B **rò cả hai chiều**, và đo được chứ không phải đoán. Với lớp thật duy nhất là `12A`:
`12A-1`, `12A.1`, `12A_1`, `12A, 11C` và `12A (45 học sinh)` đều **lọt**, trong khi `12A 3 học sinh`,
`12A ban D` và `11C hoặc 12A` bị **bỏ oan**. Ca tệ nhất là `12A-1`: một tên lớp Việt Nam hoàn toàn
hợp lý, lệch tên thật đúng một dấu gạch — tức là cái tên giáo viên sẽ không bao giờ đặt câu hỏi.
Và sĩ số thì **không** đi qua phép lọc nào cả, nên `12A (45 học sinh)` qua được trong khi lớp thật
có 3 em, làm hỏng chính thứ ADR-23 dựa vào để phân biệt hai lớp cùng tên.

Chiều bỏ oan cũng nguy hiểm theo cách riêng: format duy nhất chắc chắn qua được phép lọc lại đúng là
format mock sinh ra, nên bản demo sẽ xanh trong khi model thật rơi vào nhánh `choices` rỗng — một
câu hỏi không có lựa chọn nào, và chỉ một dòng log nói vì sao.

A làm cả lớp lỗi ấy biến mất cùng lúc, vì **không còn chữ tự do nào để kiểm**: model viết câu hỏi,
BE viết các đáp án. Nó cũng làm `more` thành thứ có người đọc — `Answered.more_choices` — thay vì
một field khai rồi không dùng.

### Decision: Nâng cap `AGENTS.md` lên 172 dòng

options considered:

- **A. Nâng 171 → 172** kèm decision record, cho một hàng invariant mới.
- **B. Không thêm hàng**, để luật sống trong ADR-23 và `services/be/AGENTS.md`.

selected option: A.

reason: comment trên `AGENTS_MD_MAX_LINES` mô tả đúng thủ tục — *"raise it only alongside a decision
record explaining what new rule justified the growth"* — và luật này đạt tiêu chuẩn đó: nó là loại
luật một thay đổi sau sẽ **vô tình dựng lại**, vì bản làm đầu tiên của chính tôi đã đi vào đúng cái
bẫy (lọc chữ model viết) và rò hai chiều. Bảng Invariants tồn tại cho đúng loại luật ấy.

Ghi thêm cho thật: ở Việc 1 tôi gặp cùng tình huống và làm **ngược** — bỏ hàng invariant vừa thêm để
giữ con số, đúng cái mà comment ấy gọi là "the wrong trade". Lần này làm theo thủ tục.

### Decision: Trần vòng lặp là một số nguyên, không dựng accounting token

options considered:

- **A. `MAX_TOOL_STEPS` + ghi `model_tokens` mỗi lượt vào `TeacherTurn`.**
- **B. Hệ ngân sách token theo phiên, có ngưỡng và cắt.**

selected option: A.

reason: công tắc đã có (`LLM_ENABLED=false`, đang là mặc định) và trần cho vòng lặp nội dung đã có
(`llm_max_attempts`). B đòi một hệ accounting mà repo chưa có dòng nào. Nhưng chỉ bỏ hẳn phần đo thì
sai theo chiều khác: transcript gửi lại mỗi vòng làm token phình theo bình phương số vòng, nên ghi
`model_tokens` vào hàng ta **đang ghi sẵn** là gần như miễn phí và biến "có tốn nhiều không" thành một
phép đo chứ không phải một cảm giác.

## Validation Checks

- [x] `.\dev.ps1 test` — sau Việc 4: 138 pytest và 11 vitest xanh (85 → 96 → 111 → 129 → 138)
- [x] `.\dev.ps1 check` — 5 check tầng repo, trong đó `agent-no-db` và `env-example`. Chạy lại ở mỗi việc
- [x] `.\dev.ps1 typecheck` — **không cần chạy**: không file frontend nào bị chạm
- [x] `packages/contracts` bị đổi ⇒ đã chạy **cả hai** theo bảng Validation của `AGENTS.md`
- [x] Vòng lặp chạy đầu-cuối bằng mock qua **queue thật và Postgres thật**, không phải stub:
      `teacher → tool_call → tool_result → assistant`, hai lượt hỏi AGENT, một tool chạy. Bốn nhánh
      kiểm trực tiếp: không nêu tên lớp → `ask_clarify`; lớp không tồn tại → đúng câu not-found của
      ADR-22; `teacher:GV-999` → 401; học sinh gọi route giáo viên → 403. (Đọc `TeacherTurn` bằng
      SQL là việc của Việc 4 — bảng chưa tồn tại)
- [x] Model thật (`gpt-4o-mini`): ba lượt ở cuối, sau khi cả bốn việc chạy sạch bằng mock. Xem mục
      Status — lượt đầu tiên bắt một lỗi chí tử mà không mock nào lộ ra được
- [x] **Luật Figma không áp lần này** — plan không chạm màn hình nào. Ghi ra để sự im lặng không bị
      đọc thành bỏ sót
- [x] Mỗi commit mang trailer `Plan: ...` — kiểm cả 5 commit, đủ cả 5

## Completion Criteria

Giáo viên gõ một câu vào endpoint chat, vòng lặp ở BE gọi AGENT, AGENT đề xuất một tool đọc, BE thực
thi với quyền của đúng giáo viên đó, kết quả quay lại vòng lặp, AGENT nói thành câu — và toàn bộ chuỗi
đó đọc lại được từ `TeacherTurn` sau khi restart. Tên lớp mơ hồ thì được hỏi lại bằng ứng viên thật từ
DB. Đề đã duyệt thì không sửa được, và có test chứng minh.

Không có màn hình nào. Đó là việc của đợt sau.

## Status

**XONG.** Năm commit, mỗi cái mang trailer của plan này: `9a37864`, `beca4c3`, `34873b1`, `7ebe9ab`,
`05cbd8b`. Ba ô `[→]` là việc cố ý để lại, đã chuyển sang `docs/plans/backlog.md` kèm lý do bị chặn —
để một ô chưa làm nằm lại trong `completed/` là để một việc không ai sửa được và không ai tìm thấy.


**Cả bốn việc xong.** Việc 1 `9a37864`, Việc 2 `beca4c3`, Việc 3 `34873b1`. Việc 4 đang chờ review.

### Việc 4 — bảng hội thoại giáo viên

Hai bảng mới, và thứ chúng mở ra quan trọng hơn việc lưu: **`ask_clarify` nay trả lời được.** Trước
đó endpoint nhận một câu và quên nó, nên giáo viên trả lời câu hỏi của chính trợ lý mà câu trả lời
tới không mang theo câu hỏi — cổng đầu vào của ADR-05 tồn tại mà không có nửa sau.

Trace là một câu `SELECT`, đọc thật trên Postgres:

```
sequence | kind        | tool_name  | duration_ms
       0 | teacher     |            |           0
       1 | tool_call   | find_class |         422
       2 | tool_result | find_class |           0
       3 | assistant   |            |         625
       4 | teacher     |            |           0
       5 | tool_call   | find_class |         437
```

Hai thứ chỉ lộ ra khi chạy thật:

- **Lượt 2 không gọi tool nào cả.** Mock tìm "có `tool_result` nào chưa?" trên *toàn bộ* lịch sử —
  vốn vô hại khi lịch sử chỉ có một lượt, nhưng nay lịch sử là bền, nên nó thấy kết quả của lượt
  trước và không bao giờ tra lại nữa: trợ lý lặp lại câu cuối mãi mãi. Việc 4 đổi hành vi của mock
  mà không sửa một dòng nào của nó. Phát hiện bằng cách **đọc bảng** sau hai tin nhắn, không test
  nào bắt. Sửa: chỉ xét từ tin nhắn cuối của giáo viên trở đi.
- **Một hàng ORM bị expire giữa các bước**, nên lượt sau đọc `conversation.id` là IO lười ở chỗ
  không được phép. Luật rút ra vẫn đúng và đã ghi vào docstring: vòng lặp làm việc với **giá trị**,
  không với hàng ORM. Nhưng **lý do tôi ghi lần đầu thì sai** — tôi viết là `commit()` gây expire,
  trong khi `bind_sessions` dựng session với `expire_on_commit=False`. Thứ thật sự expire là
  `rollback()` giữa các bước tool, vốn bỏ qua cờ đó. Review bắt chỗ này, và nó đáng sửa vì một bài
  học ghi sai nguyên nhân sẽ được áp sai chỗ lần sau.

Và một chỗ decision record của tôi nói sai: ghi `model_tokens` **không** "gần như miễn phí".
`with_structured_output` bỏ mất response chở báo cáo usage, nên cần `include_raw=True` cộng một field
trong contract — và cần một test cho cả hai hình dạng response, vì đây đúng là loại khẳng định về thư
viện mà tôi đã sai ba lần trong plan này.

### Review Việc 4 bắt gì

Bốn thứ nghiêm trọng, và chủ đề chung là **tôi sao chép nửa bài học**:

- **Không ai bắt `IntegrityError`.** Comment của tôi trên `UniqueConstraint` viết là "sao chép có ý
  thức từ `ChatMessage`", nhưng bài học ở đó gồm **cả** constraint lẫn cách xử lý:
  `student_routes.py:1759` bắt lỗi, rollback, đọc lại hàng của kẻ thắng và phát lại. Tôi sao chép
  nửa đầu, nên một cú double-click thành 500 không có tiếng Việt nào — đúng cái docstring của endpoint
  tuyên bố không xảy ra. Và docstring `_record` gọi một traceback là "loudly", tức mô tả một bug như
  thể một tính năng.
- **Không gì ngăn hai `TeacherConversation`,** và `order_by(started_at.desc())` không có khoá phụ nên
  hai hàng cùng tick sẽ trả về bất định — lịch sử nhảy qua lại giữa hai mạch, loại bug không bao giờ
  reproduce được. Sửa: `UniqueConstraint("teacher_id")` nói ra luật một-mạch-mỗi-giáo-viên, cộng khoá
  phụ `id` cho thứ tự tất định.
- **Test token không thể đỏ.** Nó assert `model_tokens >= 0` trên một fake không bao giờ set giá trị,
  và cột thì default 0 — xoá cả field trong contract đi test vẫn xanh. Nó mua cảm giác an toàn mà
  không bán lại gì.
- **Test phân quyền test mã không tồn tại.** `GV-404` bị `current_teacher` chặn 401 **trước khi**
  endpoint chạy, nên xoá hết mệnh đề lọc theo chủ đi test vẫn xanh.

Cộng `parsed` có thể là `None` khi parse lỗi — `include_raw` biến một `OutputParserException` có kèm
output xấu thành `AttributeError` trên None, tức đổi một thông báo có thông tin lấy một thông báo
không có gì.

### Một chỗ tôi phải bỏ, vì nó đo bàn thử chứ không đo code

Tôi viết một test bắn hai request đồng thời. Nó đỏ, và lý do hoá ra không nằm ở code: SQLite
in-memory chạy trên `StaticPool` — **một connection dùng chung cho mọi session** — nên hai request
đồng thời không có cô lập transaction. Kết quả đo được: chỉ 3 trong 4 hàng tồn tại, và hai
conversation cùng sống dù `UNIQUE (teacher_id)` có trong DDL.

Nên ca đua thật **vẫn chưa được chứng minh** ở đây, và nói khác đi là nói quá. Thay bằng test nhắm
hai lần vào cùng một vị trí, tất định, đi đúng nhánh hồi phục ấy. Và chính nó phát hiện một lỗ nữa
trong nhánh của tôi: người thắng mới `flush()` chứ chưa `commit()`, nên người thua đọc lại không thấy
gì rồi ném tiếp — nhánh hồi phục tồn tại mà không bao giờ chạy được.

## Lượt gọi model thật, và hai lỗi chỉ nó lộ ra được

Cả bốn việc chạy sạch bằng mock trước khi tốn một đồng nào. Rồi ba lượt trên `gpt-4o-mini`.

**Lượt đầu tiên: mọi lời gọi model thật đều 400, và rơi về mock trong im lặng.**

```
400 Invalid schema for response_format 'NextStepCompleted':
In context=('properties', 'tool_args'),
'additionalProperties' is required to be supplied and to be false.
```

Structured output chế độ strict của OpenAI **không nhận object tự do**, mà `tool_args: dict[str,
object]` sinh ra đúng thứ đó. Nghĩa là platform giáo viên **không thể dùng model thật** — và không
gì nổi lên mặt: độ trễ 3,5 giây trông như thật, câu trả lời đọc hợp lý, `model_tokens` bằng 0 là
thứ duy nhất tố giác. Không mock nào lộ ra được lỗi này, vì mock không nói chuyện với provider.

Sửa đúng bằng món nợ tôi vừa ghi vào `backlog.md` một commit trước đó — nay bị bắt buộc: cho model
một schema **hẹp** (`_Proposal`) chỉ gồm những gì nó quyết được, với `tool_args` là danh sách cặp
tên-giá-trị thay vì một map tự do, và mọi object đều `extra="forbid"`. AGENT dựng
`NextStepCompleted` từ đó. Hai field model không thể biết — `request_id` và `model_tokens` — nay nó
**không thể khai**, mạnh hơn việc bị ghi đè.

Test hồi quy là một phép kiểm máy móc trên chính JSON schema: mọi object phải tự đóng, và không
được hỏi model thứ nó không trả lời được.

**Lượt thứ hai: model bịa bốn lớp không tồn tại.** `class_assessment_summary` trả
`{"found": false, "reason": ...}` **không kèm danh sách nào**, và gpt-4o-mini lấp chỗ trống bằng
"12A1, 12A2, 12B1, 12B2" — bốn lớp không có trong DB, nói với giáo viên kèm thẩm quyền của hệ thống.

ADR-23 đã có nguyên tắc cho chuyện này ở `find_class`: lời từ chối chở danh sách thật. Tôi không áp
nó cho tool thứ hai. Nay áp, và nó đóng luôn một lỗ khác mà cùng lượt ấy phơi ra: không tool nào
cấp `assessment_id`, nên model buộc phải đoán một cái.

**Lượt thứ ba: không còn bịa.** Model gọi `find_class`, gọi `class_assessment_summary` với
`assessment_id` rỗng đúng như description dạy, nhận đúng danh sách đề — rồi trả lời "mình không tìm
thấy" thay vì gọi lại với id vừa được trao. Đó là chất lượng model, không phải harness; ghi vào
`backlog.md`.

Đo được của một lượt: **3 lần gọi model, 4.697 token, 6,5 giây**. Nối tool đúng thứ tự mà không ai
dạy thứ tự — chỉ có description nói `find_class` phải gọi trước.
