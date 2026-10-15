# Plan 5a — dàn ý đề: Kriky đọc tài liệu, đề xuất, giáo viên duyệt bằng chat

Plan con của `2026-10-07-doc-pdf-vao-ngu-canh-plan.md`, tách từ plan 5: phần *Kriky đọc nội dung tài
liệu* làm ở đây vì dàn ý cần nó; phần *Kriky trả lời câu hỏi tự do về tài liệu* và quyết định cho pha
2 vẫn ở plan 5.

## Goal

Hôm nay `drafting.fire` chia câu bằng `coverage.assign` rồi bắn **chữ OCR thô** (`focus_text`, cắt ở
4 000 ký tự) vào từng job soạn câu. Đo trên SGK Lớp 6 tập 1 ngày 14/10/2026: 7–12% ký tự nằm trên dòng
rác hay công thức đọc lệch; hình và bảng bị bỏ không để dấu; 12/82 đơn vị chỉ có bài tập; 5/82 đơn vị
dài hơn trần nên mất đuôi. Giáo viên không thấy gì cho tới khi câu đã ra, và plan Kriky nêu thì BE chạy
luôn -- không có bước nào giáo viên duyệt *câu nào hỏi gì*.

Sau plan này, mọi đề (có hay không có tài liệu) đi qua một **dàn ý**: Kriky đọc phạm vi, đề xuất từng
mục -- kiến thức, công thức sẽ dùng, phương án làm bài, bài nguồn --, BE lưu và in đúng dàn ý ấy ra
chat, giáo viên duyệt hay sửa bằng chat, và mỗi job chỉ nhận đúng mục của nó. Không chữ tài liệu thô
nào tới job.

Người dùng chốt 14–15/10/2026:

- Job **chỉ nhận kiến thức Kriky viết**; mục dàn ý phải có công thức và phương án làm bài, không dừng
  ở *"câu 1 về hàm hằng"*.
- Giáo viên duyệt **bằng chat**; **BE dựng chữ dàn ý** từ dàn ý đã lưu.
- Bỏ `coverage.assign`. Áp cho **mọi đề**.
- Một mục dàn ý phủ **k câu** (*"câu 2 và 3…"*).
- Sau khi soạn: *"thay câu 1 bằng…"* thay đúng câu ấy; *"soạn thêm 3 câu"* qua dàn ý bổ sung rồi mới
  soạn; giáo viên không nói thì không đổi gì.
- Ngân sách đọc **theo số câu**: xin N câu thì phạm vi gộp (không tách nút) thành tối đa N phần đọc;
  ít nút hơn N thì vài câu chung một đoạn nhưng khác cách làm, hướng hay công thức.
- Trần **10 câu mỗi lần xin** (thay 50); tổng một đề vẫn tới 50 qua nhiều lần soạn thêm.
- **Không gọi model thật tuỳ tiện**: bench và thử tay chỉ chạy khi phần offline đã xanh; mỗi lần báo
  trước số ca và ước tính chi phí, chờ người dùng đồng ý.

## Scope

Trong: `packages/contracts` (`teacher_chat`, `authoring`), `packages/schema` (`DraftBrief`,
`DraftItem`), `services/be` (`teacher_chat`, `teacher_tools`, `drafting`, `coverage`, `outline` mới,
`config`), `services/agent` (`propose`, `authoring`, skill `soan-de`, mock), `services/fe` (một dòng
`spoken()`, nhãn bước), `tools/check_contract.py`, `tools/propose_bench`, `tools/skill_bench`, ADR-29,
hậu ký ADR-27, `docs/overview/`.

Ngoài: VLM đọc công thức (plan 3d); Kriky trả lời câu hỏi tự do về tài liệu (plan 5, dùng lại
`read_section`); thẻ dàn ý sửa trực tiếp trên UI; pha 2 (không nhận tài liệu, như cũ).

## Decision Records

### Decision: dàn ý đi AGENT→BE bằng kind `outline`, không bằng tool

**options considered:** (a) **kind thứ năm `outline`, trường typed `outline` trong `_Proposal`** · (b)
một tool `propose_outline` · (c) dàn ý chở trong tham số của `create_draft`.

**selected option:** (a).

**reason:** tham số tool là chuỗi phẳng (`_Argument{param, value: str}`, `propose.py:743`) vì structured
output chặt không nhận object mở -- (b) và (c) bắt model viết JSON trong một chuỗi. `steps` đã chứng
minh một tuple object đóng đi qua được. `call_tool` lại không kết thúc lượt, mà dàn ý **phải** kết thúc
lượt để giáo viên đọc. Mục dàn ý: `questions`, `knowledge`, `formulas`, `approach`, `source_nodes` --
không có `difficulty` theo mục, vì tên ấy trùng mẫu cấm của `test_no_routing_decision.py:57`.

### Decision: dàn ý sống ở một lượt chat, BE in ra đúng chữ ấy

**options considered:** (a) **hàng `TeacherTurn(kind="outline")`: `text` là chữ BE dựng, `tool_result`
là `{version, items, total, document_id}`** · (b) bảng mới · (c) `DraftBrief`.

**selected option:** (a).

**reason:** lúc dàn ý hiện ra chưa có đề nào, nên (c) không có hàng để ghi; (b) là một bảng cho thứ đã
là một lượt chat. BE dựng chữ từ các mục đã lưu (`be/outline.render`) nên chữ giáo viên đọc và mục job
nhận là một -- cùng tinh thần invariant *phương án hỏi lại do BE viết từ hàng nó đọc*. Chữ đi qua
`TurnEvent(say)` có sẵn và `MathText`, nên giao diện không đổi.

### Decision: cổng duyệt suy từ thứ tự lượt

**options considered:** (a) **plan soạn chỉ chạy khi có dàn ý hiện ở một lượt *trước* lượt này, chưa
dùng, tổng câu khớp** · (b) nút duyệt · (c) tin model.

**selected option:** (a).

**reason:** người dùng chọn duyệt bằng chat, nên không có nút (b); (c) là lời dặn, thứ repo đã đo là
không giữ được model. (a) chứng minh được giáo viên **đã được cho xem**, không chứng minh được *"oke"*
nghĩa là đồng ý -- đọc nhầm thì sửa được bằng thay câu hay xoá câu, và cổng duyệt đề (ADR-05) vẫn
đứng trước học sinh. ADR-29 ghi nhận giới hạn ấy.

### Decision: ngân sách đọc gộp theo số câu

**options considered:** (a) chỉ đọc bài cần dùng, giữ 8 bước · (b) nâng trần bước cố định · (c) phần
đọc to hơn · (d) **người dùng: trần động theo số câu, gộp nút không tách**.

**selected option:** (d).

**reason:** `read_section(document_id, nodes, questions, part)`: BE gộp các đơn vị của phạm vi thành
`P = min(questions, số đơn vị)` phần **liên tiếp**, cân theo độ dài, không chặt một nút; trả phần
`part`. Trần bước của lượt là `cơ sở + P` (P ≤ 10 vì trần 10 câu mỗi lần xin), và ngân sách thời gian
lượt cộng `read_step_seconds` mỗi phần. `agent_job_timeout` **không** đổi: mỗi bước vẫn là một job,
và `check_model_call_fits_inside_the_job_waiting_for_it` so đúng một job với độ kiên nhẫn của BE --
P không đụng tới phép so ấy (review đợt 2). Thứ P đụng tới là độ dài cả lượt, nên một test thay cho
check: lượt đọc dài nhất cộng một job vẫn ngắn hơn `turn_lock_stale_seconds`.

### Decision: lịch sử không phình

**options considered:** (a) **BE thu gọn lúc dựng lịch sử: đọc cũ thành dòng tóm, dàn ý cũ thành
`superseded`** · (b) AGENT cắt trong `_describe_result` · (c) không lưu kết quả đọc.

**selected option:** (a). `_as_records` (`teacher_chat.py`) bỏ chữ của mọi `read_section` **đã thành
dàn ý** (đứng trước dàn ý mới nhất), giữ `{part, parts, nodes, labels, elided}`; chữ đọc **chưa** thành
dàn ý (đọc rồi hỏi lại giáo viên) ở lại, tối đa mười phần mới nhất (sửa sau review đợt 2: bản đầu bỏ
cả chữ ấy, và lượt sau phải đọc lại); dàn ý đã bị thay thành `{version, superseded}`; chỉ dàn ý mới
nhất giữ đủ mục. Chữ đọc trong lượt đang chạy giữ nguyên.

**reason:** `_describe_result` (`propose.py:940`) phát lại nguyên kết quả tool vào mọi lượt sau; sáu
nghìn ký tự mỗi phần đọc nhân mười phần nhân bốn mươi lượt là prompt không ai trả nổi. (b) để BE vẫn
gửi cả khối chữ qua Redis rồi AGENT mới vứt; (c) làm mất dấu *đã đọc gì* mà lượt sau cần để sửa dàn ý.

### Decision: thay một câu giữ câu cũ cho tới khi câu mới về

**options considered:** (a) xoá trước rồi soạn · (b) **giữ câu cũ, `harvest` tráo khi câu mới qua
ADR-18**.

**selected option:** (b).

**reason:** job có thể hỏng; với (a) ô ấy trống và giáo viên mất một câu đang tốt. Bản ngân hàng (ADR-28)
theo đúng luật xoá: câu bị thay thôi trỏ về đề, bản trong ngân hàng ở lại.

### Decision: không chữ tài liệu nào tới job

**options considered:** (a) **job chỉ nhận mục dàn ý; một check cấm `drafting.py` đọc kho** · (b) gửi
mục dàn ý kèm đoạn trích nguyên văn Kriky chỉ ra · (c) gửi cả mục lẫn chunk thô.

**selected option:** (a), người dùng chốt 14/10/2026. `DraftQuestionRequested` thêm `item_knowledge`, `item_formulas`, `item_approach`,
`item_part`, `item_parts`, `other_items`; `focus_*` thành `[CODE CHẾT]`. Check
`check_drafting_reads_no_document_text`: `drafting.py` không gọi `get_reader` hay `.chunks(`. Pha 2 vẫn
không có trường nào trong số ấy.

**reason:** luật *job nhận đúng thứ giáo viên đã thấy* chỉ đứng được khi đường đọc kho bị cắt bằng cấu
trúc, không bằng lời hứa. (b) và (c) đưa lại đúng thứ chữ OCR bẩn mà plan này dựng ra để tránh, ở chỗ
giáo viên không thấy. `focus_*` chỉ thành code chết ở task 10, cùng lúc `fire` thôi điền chúng.

### Decision: dọn `coverage.py`, cột cũ thành code chết

**options considered:** (a) **chuyển hai hàm còn dùng, phần còn lại comment `[CODE CHẾT]`** · (b) xoá
hẳn · (c) giữ `coverage.assign` làm đường lùi khi Kriky lỗi.

**selected option:** (a); (c) người dùng loại 14/10/2026, (b) trái luật repo về code chết.
`heading` và `scope_of` chuyển sang module thuần mới `be/toc.py` (sửa khi làm task 4: đặt ở
`teacher_tools.py` như bản đầu thì `drafting.py` -- còn cần `scope_of` tới task 10 -- phải import
`teacher_tools`, vốn đã import `drafting`: vòng import);
phần còn lại của `coverage.py` và `test_coverage.py` comment `[CODE CHẾT 2026-10-15 …]`. Thêm
`DraftBrief.outline` (JSON, mỗi mục gắn version dàn ý), `DraftItem.outline_item`, `DraftItem.item_part`,
`DraftItem.replacing` (task 3). Cột `DraftItem.node_ordinal`/`chunk_ordinals` chỉ thành code chết ở
task 10, cùng lúc `drafting.py` thôi đọc chúng -- làm sớm hơn thì code đang chạy gãy giữa hai task.
BE ghi; ingest chỉ kiểm schema (`check_schema`).

**reason:** `heading` và `scope_of` là hai hàm duy nhất còn người dùng (`teacher_tools.py` dựng nhãn
và `read_section` gom cây con, cùng phép gộp `toc.parts`); để chúng lại trong một module đã chết là giữ một import sống trỏ vào
code chết. **Từ task 3, BE và ingest khởi động lại trên DB dev cũ sẽ chết vì `check_schema`** (thiếu
bốn cột mới); tiến trình đang chạy thì không sao. `db-reset` chạy trước lần khởi động lại BE hay
ingest đầu tiên sau task 3 -- lệnh xoá dữ liệu dev, test không cần nó, nên không chạy sớm hơn.

### Decision: BE điền hộ khi model quên

**options considered:** (a) **BE điền từ thứ nó đã biết** · (b) từ chối rồi để model thử lại.

**selected option:** (a), như `bind_book`: `assessment_id` của `start_drafting`/`replace_question` lấy từ đề
mới nhất của đoạn chat khi model bỏ trống; `create_draft.nodes` lấy hợp `source_nodes` của dàn ý khi
model bỏ trống.

**reason:** đo ở plan 4b: ~1/5 lần gpt-4o-mini quên tham số đã có trong lượt trước, và (b) tiêu một
lượt của giáo viên cho một thứ BE không phải đoán.

## Files

| Việc | File |
|---|---|
| Nghiệp vụ | `docs/decisions/adr-29-dan-y-de-truoc-khi-soan.md`, hậu ký `adr-27-…`, `docs/decisions/README.md` |
| Contracts | `packages/contracts/src/contracts/teacher_chat.py`, `authoring.py`, tests |
| Schema | `packages/schema/src/schema/models.py`, `docs/overview/data-model.md` |
| Đọc sách | `services/be/src/be/toc.py` (mới), `teacher_tools.py`, `teacher_chat.py`, `config.py`, `coverage.py` |
| Dàn ý | `services/be/src/be/outline.py` (mới), `teacher_chat.py`, `drafting.py` |
| Kriky | `services/agent/src/agent/graphs/propose.py`, `skills/soan-de.md`, `handlers.py` (mock), `skill_router.py` |
| Job | `services/agent/src/agent/graphs/authoring.py` |
| FE | `services/fe/src/screens/teacher/Chat.tsx` |
| Check, bench | `tools/check_contract.py`, `tools/propose_bench/`, `tools/skill_bench/`, `tools/tests/` |
| Tài liệu | `AGENTS.md`, `docs/overview/teacher-surface.md`, `docs/kich-ban-thu-tay-giao-vien.md`, `docs/plans/backlog.md` |

## Ordered Tasks

Mỗi task: làm → `.\dev.ps1 check`, `test`, `typecheck` xanh. Hết mỗi đợt: một subagent review code
thật của cả đợt → sửa → commit theo task. Không gọi model thật ở đợt 1–3 và 5.

**Đợt 1 — quyết định và hình dạng dữ liệu**

- [x] 1. Plan này, ADR-29 (`đã chốt, chưa thi hành`), hậu ký ADR-27, `docs/decisions/README.md`,
      dòng plan 5a trong plan ô.
- [x] 2. Contracts: `OutlineItem`; `NextStepCompleted.kind` thêm `outline` cùng trường `outline` (bắt
      buộc với `outline`, cấm ở kind khác); `TurnRecord.kind` thêm `outline`; các trường `item_*`
      của `DraftQuestionRequested`; pha 2 cấm `item_*`.
- [x] 3. Schema: cột mới (`outline`, `outline_item`, `item_part`, `replacing`), `data-model.md`.

**Đợt 2 — Kriky đọc được sách**

- [x] 4. `read_section` gộp theo số câu; `heading`/`scope_of` chuyển chỗ; hai tập `_DOCUMENT_READS`;
      catalog 10.
- [x] 5. Trần bước và ngân sách thời gian lượt theo P; test lượt dài nhất thay cho đổi check.
- [x] 6. Lịch sử gọn: đọc cũ thành dòng tóm, dàn ý cũ thành `superseded`.

**Đợt 3 — BE: lượt dàn ý, cổng duyệt, đóng băng, job**

- [x] 7. `be/outline.py`: `validate` và `render`.
- [x] 8. Nhánh `outline` trong vòng lượt; FE `spoken()` nhận `outline`.
- [x] 9. Cổng duyệt `_shown_outline`, `Running.outline`, điền hộ `assessment_id`/`nodes`.
- [x] 10. `fire`/`_refire` theo dàn ý; payload `item_*`; `coverage.assign` và cột
      `node_ordinal`/`chunk_ordinals` thành code chết; check
      `check_drafting_reads_no_document_text`; `draft_brief` nhánh dàn ý.

**Đợt 4 — Kriky đề xuất dàn ý**

- [x] 11. `_Proposal.outline`, `completed`, `_unmangled` sửa cả ba trường chữ, hỏi lại một lần khi dàn
      ý thiếu, `_compose` phát lại dàn ý mới nhất, mock nêu dàn ý rồi plan. Lượt dàn ý chở
      `tool_args` `for` (`new`/`more`/`replace`) và `question` khi thay câu -- thiếu chúng thì mọi dàn
      ý là `for=new` và cổng chặn soạn thêm, thay câu (review đợt 3).
- [x] 12. Prompt: `_CORE`, `soan-de.md`, `_BOOK_PROCEDURE`, router `state_of`.
- [x] 13. Bench offline (ca `plan` → `outline`, ca duyệt/sửa/plan khi chưa có dàn ý, ca routing);
      chạy thật một lần **khi người dùng cho phép**.

**Đợt 5 — sửa sau khi soạn**

- [x] 14. Lõi xoá câu tách từ `teacher_routes.delete_question` sang `drafting.py`.
- [x] 15. `replace_question`: từ chối khi đề khoá, có job chờ, có bài làm, câu không có; `harvest`
      tráo; catalog 11; FE nhãn bước. Cùng lúc mới dạy model `for=replace` + `question` (`_CORE`)
      và thêm *"thay một câu"* vào mô tả skill `soan-de` -- gỡ ra ở review đợt 4 vì dạy một việc chưa
      có tool là mời giáo viên duyệt một dàn ý không chạy được.
- [x] 16. Soạn thêm: `start_drafting` trên đề có sẵn nối mục dàn ý; prompt và ca bench offline.

**Đợt 6 — tài liệu và thử đầu-cuối**

- [ ] 16b. **Xoá toàn bộ khối `[CODE CHẾT]`** (người dùng dặn 15/10/2026: thêm vào pha cuối, trước
      khi cập nhật tài liệu) -- comment code chết trong `services/`, `packages/`, `tools/`, cả file chết
      (`coverage.py`, `test_coverage.py`). Rồi rà lại tài liệu nhắc tới chúng (task 17).
- [x] 17. ADR-29 `đã chốt` cùng bảng nơi thi hành; `AGENTS.md`; `teacher-surface.md`; kịch bản thử
      tay; `backlog.md`.
- [ ] 18. Thử trình duyệt **một đợt** (người dùng dặn 15/10/2026: plan không đóng khi chưa thử tay;
      gpt-4o-mini, **xin phép trước**): dàn ý có công thức → sửa → duyệt → câu
      bám dàn ý; thay câu 1; soạn thêm 3 câu; một đề không tài liệu; F5; log không payload nào có
      chữ chunk. `db-reset` trước khi bật service (Decision *dọn `coverage.py`*). Đóng plan.

## Validation Checks

- Mỗi task: `.\dev.ps1 check`, `test`, `typecheck` xanh; mỗi check hay test mới đỏ dưới một đột biến
  một dòng.
- `test_the_outline_shown_is_what_be_rendered_from_stored_items` và
  `test_a_job_receives_exactly_its_outline_item` xanh; `check_drafting_reads_no_document_text` xanh.
- Cuối đợt 4: số đo `propose_bench` và `skill_bench` (khi người dùng cho chạy thật).
- Cuối plan: kịch bản task 18; `DraftBrief.outline` khớp chữ đã hiện; mỗi `DraftItem` trỏ đúng mục.

## Completion Criteria

- Một đề có tài liệu và một đề không tài liệu đều đi: yêu cầu → dàn ý BE in → sửa → duyệt → câu bám
  dàn ý, trên trình duyệt với gpt-4o-mini.
- Không job nào nhận chữ tài liệu thô: check `check_drafting_reads_no_document_text` xanh, và log
  worker của lượt thử không có payload nào mang `focus_text`.
- Thay một câu và soạn thêm câu chạy được, câu cũ không đổi khi không được nhắc.
- ADR-29 sang `đã chốt` với bảng nơi thi hành trỏ đúng code; `propose_bench` không tụt dưới số đo
  trước plan trên các ca không liên quan dàn ý.

## Status

Mở 15/10/2026.

**Đợt 1 xong 15/10/2026** (task 1–3): ADR-29 và hậu ký ADR-27 (`9789d1f`), contracts (`422c991`),
schema. Review đợt 1: không lỗi runtime; sửa docstring nói sai về hiện tại (`focus_*` chỉ chết ở task
10), luật *công thức là của Kriky* có chỗ thi hành (`outline.render`), cổng 3 nói rõ dàn ý không đi
qua `ask_clarify`, `item_part ≤ item_parts` thành validator, Decision Records đủ phương án và lý do.
`check` 22/22, pytest 1109, vitest 208, `typecheck` xanh. **DB dev chưa `db-reset`**: BE hay ingest
khởi động lại sẽ chết vì `check_schema` cho tới khi chạy nó.

**Đợt 2 xong 15/10/2026** (task 4–6): `read_section` và `be/toc.py`; trần bước động; lịch sử gọn.
Review đợt 2: không lỗi chặn; sửa `nodes` viết cách nhau bằng dấu cách (*"1 2"* từng thành nút 12),
sàn cắt mỗi đơn vị không còn đẩy một phần quá trần, chữ đọc chưa thành dàn ý được giữ, `drafting.py`
import `scope_of` từ `toc`. Ngoài phạm vi, chưa sửa: `_document_scope` của `create_draft` có đúng lỗi
*"1 2"* ấy từ plan 4b. Dòng `deadline += …` chưa có test riêng (đột biến bỏ dòng ấy vẫn xanh).

**Đợt 3 xong 15/10/2026** (task 7–10): `outline.py` (`cddab3b`); lượt dàn ý, cổng duyệt, `fire` theo dàn ý. Đổi so với bản đầu, đều ghi ở đây:
- Dàn ý nói nó dành cho việc gì bằng `tool_args["for"]` của lượt dàn ý -- `new`, `more`, `replace`
  (kèm `question`) --, không cần đổi contract; BE tính số câu đầu (*"Câu 11–13"* khi soạn thêm).
- Dàn ý bị BE từ chối và plan bị cổng chặn đều về với model như một kết quả tool **không lưu**:
  giáo viên chưa thấy gì, nên không có bước nào để vẽ lại sau F5.
- Số câu: trống thì BE điền tổng của dàn ý; một con số khác tổng là lời từ chối (Decision 3); chữ
  không đọc được thì tool từ chối như mọi tham số.
- Lời dặn *"bám đúng kiến thức, công thức và cách làm"* nằm trong brief của câu có mục, không trong
  `_SYSTEM` -- chỉ câu có mục mới cần nó.
- `coverage.py`, `test_coverage.py`, đường đọc sách của `drafting.py` (`_open_book`, `_focus`,
  `BookUnavailable`) và hai cột `node_ordinal`/`chunk_ordinals` thành `[CODE CHẾT]`. Hai file chết mang
  `# ruff: noqa: E501`: comment lại làm mỗi dòng dài thêm hai ký tự.
- Task 9 và 10 chung một commit: `start_drafting` từ chối khi không có dàn ý thì mọi test soạn câu cũ
  cần `fire` biết dàn ý cùng lúc.
- Test cũ không nói về cổng duyệt được cấp sẵn một dàn ý đã xem (`_outline_shown` trong
  `test_teacher_chat.py`, `execute` bọc trong `test_write_tools.py`).

Review đợt 3: đảm bảo cốt lõi đứng (không soạn từ dàn ý cùng lượt, của đoạn chat khác, hay hai lần).
Đã sửa: một plan chỉ một bước soạn; tài liệu của `create_draft` phải là tài liệu của dàn ý;
`_outline_book` theo luật `_read_other_books` (nay gồm cả `read_section`); dàn ý `more`/`replace`
mang `assessment_id` của nó và cổng so plan với đúng đề ấy; `_latest_draft` chỉ đọc kết quả mở/soạn
đề, không đọc dòng duyệt/phát hành; số câu đầu theo ô cao nhất như `fire`, không theo số câu; job
không bị dặn né chính kiến thức của nó; `start_drafting` từ chối số câu khác tổng dàn ý ở mọi đường
gọi; lời từ chối khi quên `create_draft` nói đúng việc; check bắt cả import `content_reader`. Chưa
sửa, ghi nhận: một `IntegrityError` ở commit đầu của `fire` cuộn lại `brief.outline` mà ô sau vẫn
trỏ mục (cùng lỗ đã có với `question_count`); dàn ý và plan bị từ chối không ghi `model_tokens`;
một lượt dàn ý không đóng câu hỏi lại đang mở trước nó (`_rows_in_play`). Check không bắt được khoá
dict `"focus_text"` (`_code_only` xoá chuỗi) -- ghi trong docstring của check.

**Đợt 4, phần offline xong 15/10/2026** (task 11, 12, 13 trừ lần chạy thật). Kriky nêu được kind
`outline` (`_OutlineItem`, `_NoOutline`, `_describe_outline`), mock nêu dàn ý rồi plan khi giáo viên
đồng ý, prompt `_CORE` có việc thứ năm, `soan-de` nêu dàn ý ngay khi đủ mục, `_BOOK_PROCEDURE` đọc
bằng `read_section`, bộ chọn skill thấy lượt dàn ý. Bench: ca đủ mục chấm dàn ý; ca đổi đầu vào mang
tên mới (`du-luong-giac-chuyen-9-cau`, `du-xac-suat-10-cau`, `dap-so-cau-sau-hoi-6`,
`vuot-tran-12-cau`) nên **không so được** với số đo cũ dưới tên cũ; thêm ca duyệt (ba ca mang lại
khối và phạm vi), sửa dàn ý, đọc xong sách, hai ca định tuyến.
Review đợt 4: sửa -- dàn ý hỏng hai lần nói câu trung tính thay vì lùi về mock (mock bịa dàn ý); dàn
ý không bài nguồn ở lượt nhắc sách mở thư viện (`_library_first`); dàn ý ở lượt có sách mà chưa đọc
chữ thành lời gọi `read_section` (`_read_before_outline`); gỡ `replace` khỏi prompt tới task 15; xin
quá 10 câu thì nói ra; mô tả `question_count` của `start_drafting` nói *"đúng tổng của dàn ý"*.
Ghi nhận, chưa sửa: bench `be_refuses` chỉ chạy `vet_plan`, không chạy cổng duyệt; quên `for=more`
khi soạn thêm thì lời từ chối của BE dẫn model mở đề thứ hai (cần một ca đo ở task 16); máy dev
không key có chip sách thì mock lặp tới trần bước (ghi trong comment).

**Đợt 5 xong 15/10/2026** (task 14–16, một commit: `drafting.py` mang cả lõi gỡ câu lẫn phép thay).
`drop_question` dùng chung cho xoá câu và tráo câu; `replace_question` soạn lại một câu, câu cũ ở lại
tới khi câu mới qua ADR-18; soạn thêm không cần code mới (dàn ý `for=more` + `start_drafting`), chỉ
thêm ca bench. Review đợt 5: sửa -- thay câu không đạt thì bước nói *"câu N giữ nguyên"* và hỏng,
không báo là đã thay (`_replacement_outcome`, FE `replaced()` cùng chữ); route sửa câu từ chối câu
đang được thay; cổng chặn plan mở đề rồi thay câu; cột `replaces_question_id` để hai lần thu không
tráo một câu hai lần; ô thay luôn nằm trong `question_count`; lời từ chối không còn đổ cho hàng đợi.
Ghi nhận, chưa sửa: mục dàn ý của câu đã bị thay vẫn nằm trong `brief.outline` và vẫn đi vào
`other_items` (có trần); thẻ kết quả của bước thay câu dùng đầu đề *"Đã tạo đề"* của nấc
`drafted`.

**Đo trên model thật một lần, sau đợt 5** (người dùng chọn gộp; gpt-4o-mini, 6 lần/ca):
- `skill_bench` (`data/results/run-99`): `soan-de` và `lop-va-ket-qua` recall 100% ở mọi ngưỡng,
  kể cả hai ca *"oke"* và *"câu 3 đổi"*; chi phí ~0,0015 USD.
- `propose_bench` (`data/results/run-98`, nhãn `dan-y`): **152/204**, hỏi lại model 38 lần. So với
  `run-95` trước plan (127/132, ca đủ mục 6/6), ca đủ mục **tụt**: `du-hinh-khong-gian-11` 0/6 và
  `du-so-nguyen-to-6` 0/6 (model hỏi xác nhận dù đủ bốn mục), `du-phan-so-lop-la` 3/6,
  `du-vecto-10` 3/6 (tổng câu lệch số xin, hay dàn ý hỏng hai lần thành câu trung tính).
  `tai-lieu-doc-xong` 0/6 (dàn ý 2 mục cho 6 câu, hay hỏng); `dan-y-thay-cau` 2/6 (nêu lại cả đề);
  `dan-y-soan-them` 3/6; `dan-y-duyet-khong-gian` 1/6 (`topic_scope` chép từ dàn ý thay lời giáo
  viên). Giữ vững: định tuyến sách, đọc mục lục, hỏi khi thiếu mục, ca duyệt dàn ý khác 6/6.
- Sửa offline sau lần đo: `_miscounted` -- tổng câu của dàn ý phải bằng `question_count` model ghi
  trong `known`, dàn ý thay câu đúng một mục một câu; lệch thì hỏi lại model một lần
  (`_UncountedOutline`); mô tả trường `outline` nói rõ luật ấy. **Chưa đo lại** -- chờ người dùng
  cho phép. Kiểu trượt *"hỏi xác nhận dù đủ mục"* chưa có cách sửa bằng code.
- **Đo lại một lần** (người dùng cho phép; `data/results/run-100`, nhãn `dan-y-dem-cau`): **169/204**.
  Ca đủ mục về lại 6/6 trừ `du-ti-le-thuc-7` 4/6; `dan-y-sua-mot-muc` 6/6. Còn yếu: `dan-y-thay-cau`
  1/6 và `dan-y-soan-them` 3/6 (dàn ý `for=new`) -- đo **trước** `_right_purpose`; `tai-lieu-doc-xong`
  2/6 (dàn ý không bài nguồn, sai tổng); `tra-lop-ket-qua` 2/6 (trước plan 6/6: `call_tool` không tên
  tool -- theo dõi); `vuot-tran-12-cau` 1/6.

**Thử trình duyệt, lượt một 15/10/2026** (gpt-4o-mini; `db-reset`; BE, AGENT, ba worker, FE chạy code
mới): H1 đạt -- dàn ý hiện như lời Kriky, không bước nào chạy; H2 đạt -- *"bản 2"*, câu 2 đổi đúng,
công thức dựng toán; *"oke"* → 5 câu, `draft_briefs.outline` 5 mục bản 2, ô 1–5 trỏ mục 0–4, câu 2 là
bài chia tiền; F5 giữ hai bản dàn ý, khối bước và thẻ. Chất lượng: dàn ý lượt đầu ghi mỗi mục
*"tỉ lệ thức"*, không công thức, nên câu 1, 3, 4 cùng một dạng. H4 trượt: *"thay câu 3"* ra dàn ý cả
đề `for=new` -- sửa bằng `_right_purpose` (rút đúng mục chứa câu N, `for=replace`; *"soạn thêm"* trên
đoạn chat đã có đề thành `for=more`); thử lại sau khi khởi động lại AGENT (người dùng cho phép): AGENT
đúng, BE từ chối vì chip sách tự đính lúc tải lên làm dàn ý thay câu của một đề không sách bị đòi bài
nguồn -- sửa: dàn ý `more`/`replace` theo sách **của đề**. H3: model hỏi lại chương mà chưa đọc mục lục
(lỗi có từ trước, `backlog.md`), rồi chọn `outline` mà để trống mục hai lần → câu trung tính. **Chưa thử
lại** H3, H4, soạn thêm sau hai bản sửa: cần khởi động lại BE và AGENT.

**Thử trình duyệt, lượt hai** (BE, AGENT khởi động lại, người dùng cho phép): H4 **đạt** -- dàn ý
*"Câu 3 · …"* một mục (bản 4), *"oke"* → bước *Thay một câu*, câu 3 đổi, bốn câu kia giữ nguyên, một
đề duy nhất, `replaced=true`. H3 **đạt** -- đọc mục lục, `read_section`, dàn ý có *"Theo: Bài 1. TẬP
HỢP (tr. 5–9)"*, *"oke"* → 5 câu bám dàn ý; 11 payload job trong Redis đều `focus_text` rỗng. Lộ thêm,
đã sửa bằng code: đọc phần 1/5 rồi viết dàn ý (nay đọc tiếp khi còn `more`); soạn thêm 2 câu ra hai
bước `start_drafting` cho cùng đề (nay cổng gộp); sau *"oke"* model mất phạm vi rồi hỏi lại khối (nay
lượt dàn ý giữ môn, khối, phạm vi và *"oke"* ngay sau dàn ý thành plan dựng từ chính dàn ý --
`_approved_plan`); `outline` để trống mục (nay đứng ngay sau `text` trong schema).
- **Đo lần ba** (`data/results/run-101`, nhãn `dan-y-dung-viec`, sau schema và `_right_purpose`, trước
  `_approved_plan`): **182/204**, hỏi lại 14 lần. Ca đủ mục 6/6; `tai-lieu-doc-xong` 6/6;
  `dan-y-soan-them` 6/6; `dan-y-thay-cau` 5/6. Còn: `tra-lop-ket-qua` **2/6** (trước plan 6/6;
  `call_tool` không mang tham số -- hồi quy ngoài luồng dàn ý, theo dõi ở `backlog.md`);
  `dan-y-duyet-khong-gian` 2/6 (đo trước `_approved_plan`); `vuot-tran-12-cau` 0/6 (model nêu dàn ý
  10 câu thay vì nói trần; BE vẫn chặn quá 10).
