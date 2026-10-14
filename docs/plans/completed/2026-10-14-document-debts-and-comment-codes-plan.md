# Plan — sáu quyết định treo của plan 4c, nợ của kho nội dung và document agent, mã trong comment

## Goal

`backlog.md` có ba mục chờ người dùng: *"Còn treo khi đóng plan 4c"* (sáu quyết định), *"Nợ của plan
3b"*, *"Nợ của plan 3c"*. Người dùng chốt ngày 14/10/2026:

- BE tự kiểm *"đã đọc mục lục"*: **chưa làm** khi chưa có lỗi thật. Dòng nợ ở lại, kèm lý do.
- Đọc mục lục luôn khi chỉ một tài liệu hợp: **giữ nguyên** -- agent quyết, kể cả khi nó hỏi lại.
- Luật tên bền áp cả cho **lời dẫn trong comment**: mã task, nhãn ô đợt (*"plan 3c"*), mã quyết định
  (*"D9"*), mã pipeline (*"B10"*) phải đi kèm tên plan.
- Cache của `ocr_bench` đổi khuôn tên `_t4` → `_threads4`; cache mồ côi bị xoá.
- Chọn một nút hay gửi ô *"Khác"* trên thẻ hỏi lại **không** xoá chữ đang gõ ở ô nhập chính.
- Figma lệch code ở ô nhập và thẻ hỏi lại: **theo code**.
- Nợ kho nội dung: làm tiến độ trên chip, chạy lại lô không OCR lại trang đã có, `pages_read` không
  lùi, ghi trang theo lô, lần thử cuối gửi `FAILED`. Còn lại giữ nợ.
- Nợ document agent: chip *"đang dựng mục lục"*, `FAILED` khi graph ném lỗi lạ, tách token banner.
  Còn lại giữ nợ.

## Scope

Trong: `tools/ocr_bench`; `Chat.tsx` và `Rail.tsx`; Figma `Clarify request`, artboard `3`, `Document
chip`; `services/document` (kho nội dung, hai handler); `services/ingest` (tiến độ); `packages/contracts`
(`IndexHeader`); `services/be` (`DocumentRead`); `tools/check_contract.py` và `AGENTS.md`; comment và
docstring trong `services/`, `packages/`, `tools/`; `backlog.md`.

Ngoài: mọi dòng nợ người dùng không chọn; lưới thứ hai ở BE cho *"đã đọc mục lục"*.

**Phát hiện khi đọc code:** dòng nợ *"job dựng cây hỏng vì lỗi lập trình thì chip chờ 300 s"* đã cũ.
`index_handlers.index_document` bắt `Exception` và gửi `FAILED` qua `_give_up` từ commit `b0dc342`, có
`test_an_unexpected_failure_still_tells_the_teacher`. Plan này chỉ xoá dòng ấy.

## Decision Records

### Decision: mã trong comment đi kèm slug plan

**options considered:** (a) chỉ mã task · (b) mã task + mã quyết định · (c) **cả bốn dạng: mã task,
nhãn ô đợt, mã quyết định, mã pipeline**.

**selected option:** (c), người dùng chốt 14/10/2026.

**reason:** người ngoài không giải được *"T4"*, mà *"plan 3c"* và *"D9"* cũng chỉ giải được khi đã
biết ô đợt nào. Slug là tên file plan bỏ ngày và `-plan` (`document-agent-hierarchy`), vì tên file là
thứ duy nhất bền khi plan rời `active/`. Cách viết:

- nhãn ô đợt **thay bằng** slug: *"(plan 3c, D3)"* → *"(`document-agent-hierarchy`, D3)"*;
- mã task, mã quyết định **giữ**, thêm slug cạnh nó;
- plan chưa có file (*"plan 5"*, *"plan 3d"*) → slug ô đợt `doc-pdf-vao-ngu-canh` cạnh nhãn;
- mã pipeline → slug plan đã đóng nó, theo bảng của ô đợt;
- mã trần không rõ của plan nào → `git blame` dòng ấy, đọc trailer `Plan:` của commit.

`AGENTS.md` đang 184/184 dòng, nên luật không thêm dòng: hàng invariant về mã task và dòng trap tương
ứng được mở rộng sang comment, và hàng ấy trỏ tới check tự động mới.

### Decision: tiến độ trên chip là chữ, không phải trạng thái thứ năm

**options considered:** (a) thêm `DocumentState` `indexing` · (b) **một trạng thái `processing`, ba
câu theo `pages_read`**.

**selected option:** (b).

**reason:** bốn trạng thái là từ vựng của ADR-27 và `check_contract` so chúng giữa hai ngôn ngữ; tiến
độ là một chi tiết của *đang xử lý*, không phải một phán quyết. Job dựng cây đã báo tiến độ với
`pages_read = page_count`, nên dữ liệu phân biệt được hai chặng: `pages_read < page_count` → *"Đang
đọc 37/200 trang…"*, bằng nhau → *"Đang dựng mục lục…"*, chưa có tiến độ → *"Đang xử lý…"*. Dòng meta
**không** in số trang khi đang xử lý: số trang trên chip vẫn là bằng chứng đã đọc xong.

### Decision: lần thử cuối nói ra

**options considered:** (a) để arq hết lượt, chờ lưới 300 s của BE · (b) **lần thử cuối gửi `FAILED`**.

**selected option:** (b).

**reason:** hỏng hạ tầng ở lần thử thứ năm vẫn thường là Mongo, không phải Redis -- nên còn đường để
nói. Gửi không được (Redis chết) thì log rồi thôi; lưới 300 s của BE vẫn là tầng cuối.

### Decision: tách token banner thì nâng `contracts.index.SCHEMA_VERSION` lên 2

**options considered:** (a) **nâng lên 2** · (b) giữ 1, ghi ngày đổi trong docstring.

**selected option:** (a).

**reason:** `summary_tokens` **đổi nghĩa** (thôi gồm token đọc banner), và `packages/contracts/AGENTS.md`
đòi nâng số khi đổi nghĩa một trường. Chỉ ngày thì mơ hồ: `banner_model = None` vừa là cây cũ dựng có
khoá, vừa là cây mới dựng không khoá. **Reader kiểm số ấy: chưa có** -- không code nào đọc
`summary_tokens`; số ấy để người đọc dữ liệu Mongo biết cách cộng.

## Files

| File | Việc |
|---|---|
| `tools/ocr_bench/run.py`, `tools/tests/test_run.py` | khuôn tên cache |
| `services/fe/src/screens/teacher/Chat.tsx`, `teacher.test.tsx` | thẻ hỏi lại giữ chữ ô chính |
| Figma `mOe2ZmrqOq1Uix45v6PNGD`: artboard `3`, `Clarify request` (`64:23`), `Document chip` (`84:25`) | theo code; tiến độ |
| `services/document/src/document/content_store.py`, `ocr_handlers.py`, `index_handlers.py`, `index/graph.py` | ghi theo lô, bỏ trang đã có, lần thử cuối, token banner |
| `packages/contracts/src/contracts/index.py` | `IndexHeader.banner_tokens` |
| `services/ingest/src/ingest/handlers.py`, `packages/schema/src/schema/models.py` | tiến độ không lùi, có tổng, có hích |
| `services/be/src/be/teacher_documents.py`, `services/fe/src/api.ts`, `Rail.tsx` | chip nói tiến độ |
| `tools/check_contract.py`, `AGENTS.md`; comment trong `services/`, `packages/`, `tools/` | mã kèm slug |
| `docs/plans/backlog.md` | dòng đã xong, dòng giữ |

## Ordered Tasks

Mỗi task: làm → `.\dev.ps1 check` xanh → subagent review → sửa → commit.

- [x] **1. Khuôn tên cache `ocr_bench`.** `_t{threads}` → `_threads{threads}`; test tag không mang mã
      task; xoá 155 tệp `data/cache/L6T1_p*.json` mồ côi, giữ `data/cache/pageindex/`.
- [x] **2. Thẻ hỏi lại giữ chữ ô chính.** `send` biết câu đến từ đâu; từ thẻ thì không xoá ô chính, lượt
      hỏng trả lại thẻ, câu *"Khác"* về ô *"Khác"*.
- [x] **3. Figma theo code.** Placeholder artboard `3`; master `Clarify request` / `chờ trả lời`. Đo bằng số.
- [x] **4. Ghi trang theo lô** (`bulk_write`) cho đường có text layer.
- [x] **5. Chạy lại lô không OCR lại trang đã có.**
- [x] **6. Lần thử cuối gửi `FAILED`** ở cả lần dò, lô OCR, job dựng cây.
- [x] **7. Tách `banner_tokens` khỏi `summary_tokens`.**
- [x] **8. `pages_read` không lùi; tiến độ ghi tổng và hích màn hình.**
- [x] **9. Chip nói tiến độ.** Figma trước, rồi BE + FE; đo Figma = FE bằng số.
- [x] **10. Mã trong comment kèm slug.** Check mới, `AGENTS.md`, rồi sửa comment, chia commit theo service.
- [x] **11. Backlog, rồi đóng plan.**

## Validation Checks

- `.\dev.ps1 check`, `test`, `typecheck` xanh sau mỗi task.
- Check mới của task 10 đỏ dưới một đột biến một dòng.
- Thẻ hỏi lại: thử trên trình duyệt (gpt-4o-mini), gõ dở ô chính rồi bấm một nút -- chữ còn.
- Chip: một PDF scan tải lên đi *đang đọc x/y trang* → *đang dựng mục lục* → sẵn sàng.
- Figma: số đo node khớp CSS.

## Status

Mở và **đóng 14/10/2026**. Task 1--11 đã commit, mỗi task qua một lượt subagent review trước khi commit.

**Sửa sau review, đáng nhớ:**

- Task 8: bản đầu hích màn hình ở **mọi** tiếng báo, gồm nhịp tim từng chặng của job dựng cây --
  vài chục lần đọc lại thư viện cho một cuốn. Nay chỉ hích khi `pages_read` tăng.
- Task 7: `summary_tokens` đổi nghĩa nên `contracts.index.SCHEMA_VERSION` lên 2 (Decision Record
  trên), theo `packages/contracts/AGENTS.md`.
- Task 9 commit mà làm đỏ `check_the_document_chip_draws_every_state_the_backend_can_send`: `say`
  và `measure` so `state` trực tiếp. Lộ ra khi task 10 chạy `.\dev.ps1 check`; sửa ở `1d6d241` bằng
  hai cờ trong bảng `CHIP`. Bài học: chạy `check`, không chỉ `test` và `typecheck`, trước mỗi commit
  -- pre-commit không chạy `check_contract.py`.
- Task 10 làm lại hai lần từ HEAD. Bản đầu (check theo **dòng**, cửa sổ ±1) bị review chặn: script
  trộn code chết trong comment vào văn xuôi, vỡ mục Args và bullet, gán slug sai cho vài lời dẫn của
  3b vì commit chung 3a/3b, và check quét cả prompt gửi model. Bản cuối: check theo **khối** comment
  (docstring thật đọc bằng `ast`, khoảng trắng được gộp trước khi so), một slug mỗi khối, không đụng
  dòng sau nhãn `[CODE CHẾT`, reflow cả đoạn giữ thụt lề treo; review lần hai còn ~20 chỗ chữ, sửa
  tay. Kiểm bằng máy: code và mọi chuỗi không phải docstring giống HEAD từng nút AST; từng dòng code
  chết còn nguyên, đúng thứ tự. Một lần chạy trung gian từng dồn một dòng ghi chú xem-lại của người
  dùng (không commit) vào đoạn bên dưới -- đã tách lại, và script coi dòng ghi chú ấy là ranh giới.

**Thử trên trình duyệt, 14/10/2026, gpt-4o-mini:**

- Thẻ hỏi lại: gõ dở *"nhớ thêm câu về hàm số mũ"* ở ô chính, bấm nút *"khối 11"* rồi gửi ô
  *"Khác"* với *"8 câu"* -- cả hai câu đi, ô chính giữ nguyên chữ sau mỗi lượt. Đạt.
- Chip: PDF scan 24 trang (SGK Lớp 6 tập 1, tr. 6--28) đi *"Đang xử lý…"* (0 s) → *"Đang đọc 9/24
  trang…"* (43 s; lô đầu chạm ngân sách 90 s ở trang 9) → *"Đang đọc 18/24 trang…"* (140 s) →
  *"Đang dựng mục lục…"* (175 s) → sẵn sàng, *"4,8 MB · 24 trang"* (185 s). Lúc đang xử lý, dòng meta
  chỉ có kích thước. Đạt.
- Đầu mục cây trong Mongo: `summary_tokens` 22 677 (`gpt-4o-mini`), `banner_tokens` 1 901
  (`gpt-5.6-luna`), `schema_version` 2.

Lúc thử, `docker-compose.infra.yml` trong working tree có một chữ lạc ở dòng 1 (thay đổi chưa commit
của người dùng) nên `infra-up` hỏng; container có sẵn được bật bằng `docker start`, không đụng file.

`dev.ps1 test`: `test_a_turn_that_outlived_its_lock_does_not_wipe_the_next_ones` hỏng chập chờn -- nợ
đã ghi ở `backlog.md` (đồng hồ Windows 15,6 ms), có từ trước plan này; chạy lại thì 1090/1090.

Task 11: `backlog.md` đã gỡ mọi dòng đã làm và ghi lý do cho dòng giữ lại.
