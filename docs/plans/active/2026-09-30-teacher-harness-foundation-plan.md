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

**Trong scope:** schema, máy trạng thái, vòng lặp tool ở BE, task AGENT thứ tư, giải nghĩa thực thể,
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
| `services/agent/src/agent/worker.py` | đăng ký task thứ tư |
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
- [ ] **Hoãn sang Việc 2** — xoá và seed lại DB dev. `prepare_schema` chỉ `create_all`, và docstring
      của nó nói thẳng là nó "never rescues a column that changed shape", nên DB dev hiện **không
      tương thích** schema mới (`teacher_id` NOT NULL, `state` thành Enum). Việc 1 không cần tới nó:
      test chạy trên SQLite in-memory. Hoãn vì xoá lúc này là phá dữ liệu phiên thử 4 tiếng ngay
      trước lúc review, mà cái giá đó chưa cần trả cho tới khi có gì để `curl`

### Việc 2 — Vòng lặp tool ở BE

- [ ] `contracts/teacher_chat.py`: `PROPOSE_NEXT_STEP_TASK`, `ToolSpec`, `TurnRecord`,
      `NextStepRequested`, `NextStepCompleted` với `kind: say | call_tool | ask_clarify`
- [ ] **Kiểm giả thuyết trước khi xây lên nó**: một test rẻ chứng minh `with_structured_output` +
      `GenericFakeChatModel` trả được `NextStepCompleted`. Nếu không được thì mới cần fake mới
- [ ] `graphs/propose.py` + handler `propose_next_step` + mock khi `llm.enabled()` là false
- [ ] `worker.py`: đăng ký task thứ tư
- [ ] `teacher_tools.py`: danh mục dựng **theo từng request** từ quyền của giáo viên; `execute()`
      **kiểm lại** quyền sở hữu. Hai tầng, vì tầng thứ nhất do model đọc và model đọc sai được
- [ ] Hai tool chỉ-đọc: `find_class`, `class_assessment_summary`. Trả **tóm tắt đã gộp ở BE**, không
      trả hàng — "lớp 11B hôm qua thế nào" là 40 học sinh × 10 câu
- [ ] `teacher_chat.py`: vòng lặp `for _ in range(max_tool_steps)`, nhánh `else` nói thật với giáo
      viên khi chạm trần thay vì im lặng
- [ ] **Từ review Việc 1**: test rằng **đường HTTP** phát hành từ chối đề chưa duyệt. Hôm nay
      `test_teacher_approves_an_assessment_before_release` khoá hàm `advance()` mà chưa caller nào
      gọi, nên dòng invariant trong `AGENTS.md` đúng về chữ và mỏng về tinh thần cho tới khi có test
      này. Không gì buộc một tool đi qua `advance()`; một phép gán `state = PUBLISHED` viết rời vẫn
      qua mặt được
- [ ] **Từ review Việc 1**: bất biến giữa `state` và số câu hỏi. `advance(..., APPROVED)` hiện không
      đếm `assessment.questions`, nên một đề `has_questions` với **0 câu** duyệt và phát hành trôi
      chảy. Chưa sửa ở Việc 1 vì đọc `.questions` trong ngữ cảnh async sẽ lazy-load và nổ
      `MissingGreenlet`; chỗ đúng để kiểm là endpoint duyệt, nơi đã có sẵn session để đếm
- [ ] `config.py` + `.env.example`: `MAX_TOOL_STEPS`. Mọi biến trong `.env.example` phải được một
      `Settings` đọc, nếu không `dev.ps1 check` đỏ
- [ ] Test: chạm trần thì dừng; vòng lặp thực thi được tool đọc; `execute()` từ chối tool của lớp
      người khác kể cả khi model xin; đường mock chạy không cần model
- [ ] `backlog.md`: check timeout nói dối, kèm số cụ thể và vì sao chưa sửa

### Việc 3 — Giải nghĩa thực thể

- [ ] `adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md`: không đoán; lựa chọn đến **từ DB**, không do model
      bịa. Ghi rõ rằng phần *cấm đánh dấu nên chọn* của ADR-05 áp ở đây, còn phần *mỗi lựa chọn tự nêu
      cái giá* thì không — luật đó viết cho quyết định sư phạm, còn phân định tên lớp không có giá nào
      để nêu
- [ ] `resolve.py`: `resolve_class()` → `Resolved | Ambiguous | NotFound`, tìm **chỉ trong lớp của
      giáo viên đó**, chuẩn hoá hoa/thường và khoảng trắng
- [ ] Nối vào executor: `Ambiguous`/`NotFound` về vòng lặp như **kết quả tool có cấu trúc** mang ứng
      viên thật, không phải exception
- [ ] Test: khớp đúng; hai lớp cùng tên → `Ambiguous` đủ hai ứng viên; không có → `NotFound` kèm danh
      sách lớp của giáo viên; lớp của giáo viên khác → **cùng đáp án với không tồn tại**

### Việc 4 — Bảng hội thoại giáo viên

- [ ] `models.py`: `TeacherTurn` với `UniqueConstraint(conversation_id, sequence)` — sao chép có ý
      thức từ `ChatMessage`, vì StrictMode mở stream hai lần *theo thiết kế* và một lần kiểm rồi chèn
      là hai câu lệnh có khe ở giữa
- [ ] Trường: `kind` (`teacher|assistant|tool_call|tool_result|clarify`), `text`, `tool_name`,
      `tool_args`, `tool_result`, `entity_kind`, `entity_id`, `model_tokens`, `duration_ms`
- [ ] `entity_kind`/`entity_id` phải đủ để render đúng variant `Action result card` của Figma
      (`tạo-đề-trống`, `thêm-câu-hỏi`, `đã-duyệt`, `bỏ-duyệt`, `đã-phát-hành`, `phát-hành-thất-bại`,
      `tạo-lớp`) sau khi tải lại trang
- [ ] Vòng lặp ghi hàng **trước** khi phát streaming — streaming là chất xúc tác cho cảm giác, không
      phải nguồn sự thật
- [ ] `model_tokens` mỗi lượt: transcript gửi lại mỗi vòng làm token phình theo bình phương số vòng,
      nên "có tốn nhiều không" phải là một phép đo
- [ ] Test: lượt sống qua reload; ghi trùng `sequence` bị chặn; trace đọc được bằng một `SELECT`
- [ ] `data-model.md`

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

selected option: A, và kiểm bằng một test rẻ trước khi xây phần còn lại lên nó.

reason: `conftest.py` đã cắm `GenericFakeChatModel` autouse cho cả suite, và `authoring.py` đã dùng
structured output — nên A mở rộng hạt giống test sẵn có gần như miễn phí, chỉ cần xếp sẵn vài chuỗi
JSON. B đòi một fake mới biết phát tool call. Quan trọng hơn: cả mục tiêu adapter lẫn dây fallback
Gemini đều nói nên tránh chỗ phụ thuộc provider. Chưa chạy thử nên **đây là giả thuyết**, và task đầu
của Việc 2 là kiểm nó, không phải tin nó.

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

- [x] `.\dev.ps1 test` — sau Việc 1: 96 pytest và 11 vitest xanh (trước Việc 1 là 85 pytest)
- [x] `.\dev.ps1 check` — 5 check tầng repo, trong đó `agent-no-db` và `env-example`. Chạy lại ở mỗi việc
- [ ] `.\dev.ps1 typecheck` — chỉ nếu có file frontend bị chạm (dự kiến: không)
- [ ] `packages/contracts` bị đổi ⇒ chạy **cả hai** theo bảng Validation của `AGENTS.md`
- [ ] Vòng lặp chạy đầu-cuối bằng mock: `curl` một câu vào endpoint chat giáo viên, đọc `TeacherTurn`
      bằng SQL, thấy đủ chuỗi `teacher → tool_call → tool_result → assistant`
- [ ] Một lượt trên model thật (`gpt-4o-mini`) ở cuối mỗi việc, để xác nhận việc đó đã thông
- [ ] **Luật Figma không áp lần này** — plan không chạm màn hình nào. Ghi ra để sự im lặng không bị
      đọc thành bỏ sót
- [ ] Mỗi commit mang trailer `Plan: 2026-09-30-teacher-harness-foundation-plan.md`

## Completion Criteria

Giáo viên gõ một câu vào endpoint chat, vòng lặp ở BE gọi AGENT, AGENT đề xuất một tool đọc, BE thực
thi với quyền của đúng giáo viên đó, kết quả quay lại vòng lặp, AGENT nói thành câu — và toàn bộ chuỗi
đó đọc lại được từ `TeacherTurn` sau khi restart. Tên lớp mơ hồ thì được hỏi lại bằng ứng viên thật từ
DB. Đề đã duyệt thì không sửa được, và có test chứng minh.

Không có màn hình nào. Đó là việc của đợt sau.

## Status

**Việc 1 xong**, đã qua một vòng subagent review và sửa hết phát hiện. Đang chờ bạn review trước khi
sang Việc 2.

Review Việc 1 bắt được ba thứ đáng ghi lại, vì cả ba đều là lỗi *tôi tin là mình đã làm đúng*:

- `Enum(native_enum=False)` **không** sinh check constraint — `create_constraint` và
  `validate_strings` đều mặc định `False` từ SQLAlchemy 1.4. Docstring và hai trang tài liệu đã
  quảng cáo một hàng rào không tồn tại, và chế độ hỏng còn tệ hơn không có hàng rào: ghi im lặng,
  `LookupError` nổ ở lần đọc sau, trong một route không liên quan. Đã bật cả hai cờ và có test.
- `test_a_published_assessment_has_no_way_back` khẳng định **mọi** cạnh ra khỏi `published` là bất
  hợp pháp, kể cả `→ approved`. Nhưng ADR-02 chốt *"Thu hồi đưa đề về đã duyệt"*, nên test đang
  khoá cứng một cạnh đã được quyết. Đã thu hẹp vòng lặp về đúng thứ ADR-01 cấm.
- Test sở hữu cũ tạo một giáo viên **không có hàng nào** rồi assert query rỗng — nó xanh kể cả khi
  `teacher_id` gán bừa hoặc `WHERE` lọc nhầm cột. Đã viết lại cho người lạ có lớp và đề riêng, assert
  cả hai chiều.

Và một chỗ tôi xử lý sai thủ tục: khi `AGENTS.md` chạm cap 171 dòng, tôi bỏ dòng invariant vừa thêm.
Comment ngay trên hằng số đó viết *"Cutting real rules to satisfy an invented number is the wrong
trade"* và mô tả đúng cách làm — nâng cap kèm decision record. Tôi đã làm đúng cái nó cấm. Đường ra
đã chọn: đặt luật vào `services/be/AGENTS.md` (16/25 dòng, còn chỗ), đúng nơi một ràng buộc của BE
thuộc về, nên không cần tiêu một dòng của file gốc.
