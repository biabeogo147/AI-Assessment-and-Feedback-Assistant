# Plan 3c — Document agent: Jev dựng cây ba cấp, gpt-4o-mini tóm tắt, chip chờ cây

## Goal

Đọc bản thô mà plan 3b đã ghi vào Mongo (`aiafa_content.documents` + `pages`), dựng **cây mục lục ba
cấp** kiểu PageIndex bằng Jev, tóm tắt từng nút bằng `gpt-4o-mini`, cắt chunk, và ghi tất cả ngược
lại Mongo -- **trước** khi tài liệu được báo *sẵn sàng*. Đây là cổng của 3c trong plan ô: *một cuốn
sách thật ra đủ chương*.

Người dùng chốt ngày 11/10/2026:

1. Chỉ tập trung vào **Jev và OCR** -- nới đúng một chỗ sau phép đo của Task 1: tên chương đọc
   bằng `gpt-5.6-luna` trên ảnh banner (D9, người dùng chọn).
2. **Chip *sẵn sàng* chờ cây** -- READY chỉ đi sau khi cây đã nằm trong Mongo.
3. Agent chạy **trong `services/document`**, là agent riêng, không phải Kriky (`services/agent`).
4. **`gpt-4o-mini` tóm tắt.** Cây có **đúng 3 cấp**: cấp 1 (chương / phần I hoặc A/B/C) → cấp 2 (A.I
   hoặc I.1, tuỳ PDF) → cấp 3 (A.I.1 hoặc I.1.1). Bậc sâu hơn **không thành nút**, gộp vào cha -- nhờ
   vậy số lời gọi `gpt-4o-mini` giảm hẳn.
5. **Tên chương: OCR thêm vùng banner**, lùi về *"Chương N"* khi không ra chữ. OCR không đọc nổi
   chữ trang trí (Status), nên người dùng chọn tiếp: *"sử dụng gpt luna 5.6 xem thế nào"* -- OCR
   giữ chữ *CHƯƠNG* làm cổng, luna đọc tên (D9).
6. **PDF có text layer và `.txt`/`.md` cũng đi qua Jev.**

## Scope

**Trong:** cây ba cấp, tóm tắt, chunk, nhãn từng ứng viên, worker dựng cây, đổi đường READY, giữ chữ
banner trong đường OCR, đọc tên chương bằng `gpt-5.6-luna` ở trang qua cổng, cây vàng và bộ đo cho
một cuốn.

**Ngoài:** ba tool đọc (`list_chapters` / `get_chapter` / `get_chunk`) và nội dung vào prompt (plan
5); phân loại công thức (3d); hiển thị tiến độ trên chip (cần Figma); một chặng crop OCR riêng cho
banner (nếu Task 1 cho thấy cần thì dừng và hỏi); cây vàng cho cuốn khác.

## Dữ liệu thật đổi thiết kế

Soi bản thô của SGK Lớp 6 tập 1 (125 trang, OCR ở plan 3b) trong Mongo, 11/10/2026:

- **Tên chương không có trong chữ.** Banner chương là một khối `image`; trang 6 còn đúng một
  `paragraph_title` rỗng. Số chương chỉ lộ ở `doc_title` *"BÀI TẬP CUỐI CHƯƠNG II/III/IV/V"*.
- **Số bài bị đọc vỡ** vào khối `header` (*"BÀ 9"*, *"B2"*, *"Ba"*). Tên bài nằm ở `doc_title`
  (*"CÁCH GHI SỐ TỰ NHIÊN"*), nhưng không đủ: Bài 1 *"Tập hợp"* chỉ là một `paragraph_title`.
- **Cấp 3 là *"1. HỆ THẬP PHÂN"*** (`paragraph_title`). Nhãn hoạt động -- *Ví dụ, Luyện tập 1, HĐ1,
  Vận dụng, Giải, Chú ý, EM CÓ BIẾT?, KHÁI NIỆM, THUẬT NGỮ* -- **không phải mục**, gộp vào cha.
- **Bẫy số thứ tự:** *"1.1. Cho hai tập hợp"* là **bài tập**, không phải mục 1.1.
- **Không có trang mục lục in.** Có `number` (số trang in) và *"BẢNG TRA CỨU THUẬT NGỮ"*.
- **`ocr/page.py` đã nhận dạng mọi dòng của trang, kể cả dòng nằm trong ảnh** -- `_fill` chỉ vứt
  chữ của khối `IMAGE`/`TABLE` (`_WITHOUT_TEXT`). Nên chữ banner có thể đã được đọc mà không tốn
  thêm giây nào. Task 1 đo điều ấy trước khi sửa gì.

## Khảo sát Jev

Nguồn: [API](https://docs.typesafe.ai/api.md), [state](https://docs.typesafe.ai/concepts/state.md),
[async client](https://docs.typesafe.ai/sdk/python/api/clients/async.md),
[jaggedness 1.13](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md); hai hướng dẫn bên thứ ba
([flaviocopes](https://flaviocopes.com/jev/),
[dev.to](https://dev.to/valyuai/how-to-use-jev-a-practical-guide-to-typesafes-system-one-model-g5e)).

- **Hợp đồng:** `POST https://api.typesafe.ai/v1/systemone` `{model, state, questions}`. Câu hỏi
  `noul` / `choice` (≤ 255 lựa chọn) / `score` (2–10 mức), mỗi câu có `instructions` + `criteria`.
  `choice` trả `choice`, `probabilities`, `confidence`; `usage` đếm token. Python SDK `typesafe-sdk`:
  `AsyncTypeSafeClient(api_key=, model=, retry=, timeout=)`, `await system_one(state, questions)`;
  SDK tự retry 429/529; ghim được phiên bản (`jev-1.13.0`).
- **Giới hạn:** ~64k token cho state + mọi câu hỏi, ~32k cho state + câu dài nhất. Không có endpoint
  batch -- nhiều câu hỏi **trong một lời gọi** chạy song song, độc lập. $0,042 / triệu token vào,
  token ra miễn phí. Rate limit: tài liệu chính thức không ghi; bên thứ ba ghi 1 200 req/phút hoặc
  80 req/s (lệch nhau).
- **Điểm yếu đo được của 1.13, và quyết định mỗi cái kéo theo:**
  - *Không đếm, không làm toán, kém với số* → mọi so sánh số thứ tự (*Bài 3 sau Bài 2*, *I.1.1 sâu
    hơn I.1*) làm bằng **code**.
  - *State to và không liên quan làm giảm độ đúng* → state là **một khối + ngữ cảnh hẹp**, không phải
    cả trang.
  - *Nghiêng về lựa chọn đầu tiên* → đặt lựa chọn **an toàn** lên đầu (*không phải mục*): bỏ sót một
    mục chỉ gộp nội dung vào cha, còn một mục giả làm rách cây.
  - *Kém hơn với ngôn ngữ không phải tiếng Anh* → chữ khối giữ tiếng Việt, nhưng `instructions` /
    `criteria` viết **tiếng Anh**, và khoá lựa chọn là định danh tiếng Anh.
- **Ý kiến:** Jev hợp vai **"xác nhận và xếp cấp"** một ứng viên -- hai câu `choice` trong một lời
  gọi -- chứ không hợp vai dựng cây trọn. Ngưỡng `confidence` phải **hiệu chỉnh trên cây vàng**, không
  lấy một con số có sẵn. Khoá `JEV_API_KEY` đọc qua `Settings` rồi **truyền vào** client -- đúng bài
  học ở `agent/llm.py`.
- **Rủi ro ngoài:** TypeSafe tạm ngưng đăng ký mới từ 22/09/2026 (tài khoản cũ vẫn chạy). Jev hỏng
  thì cây đi đường luật (D5), tài liệu không kẹt.

## Decision Records

### D1. Jev phân loại, code dựng cây

**options considered:** (a) Jev trả quan hệ với heading liền trước (cao hơn / cùng / con / không
phải heading) -- bản trong `backlog.md` · (b) **Jev trả cấp tuyệt đối**, code dựng cây bằng ngăn xếp.

**selected option:** (b). Mỗi ứng viên **một lời gọi**, hai câu `choice`:
`role` = `not_heading` → `activity_label` → `numbered_exercise` → `running_header` → `book_section`
(thứ tự cố ý), và `level` = `deeper` → `level_3` → `level_2` → `level_1` -- lựa chọn an toàn đứng
đầu ở **cả hai** câu, vì Jev 1.13 nghiêng về lựa chọn đầu tiên. State nhỏ:
`{block: {text, ocr_label, position, repeated}, numbering, open_path: {level_1, level_2, level_3},
next_text, page}` -- `position` và `repeated` là chữ do code tính; `open_path` dựng từ quyết định
**tạm** của luật, vì các lời gọi Jev chạy song song.

**reason:** người dùng đã ghim **đúng 3 cấp**, nên cấp tuyệt đối là câu hỏi đóng tự nhiên; câu hỏi
tương đối thì một lần sai kéo sai cả chuỗi phía sau. `assemble` (thuần) gộp `deeper` vào cha, không
cho nhảy từ cấp 1 xuống thẳng cấp 3 (nâng lên cấp 2), và dùng luật (D5) khi `confidence` dưới
ngưỡng. Bản đầu của D1 hứa thêm *"dùng luật khi số thứ tự đi lùi"* -- **chưa làm** (review Task 3);
ghi nợ ở `backlog.md`.

### D2. Chữ của khối ảnh được giữ; pipeline `text1` → `text2`

`_fill` thôi vứt chữ của các dòng nằm trong khối `IMAGE` (`TABLE` giữ như cũ). Không thêm chặng OCR
nào -- dòng đã được detect và đọc rồi. Đổi tên pipeline để mọi bản thô cũ **biết mình cũ**; local thì
xoá DB rồi đọc lại (người dùng đã cho phép). **Đo trước khi sửa:** chữ banner không lọt vào detector
thì cần một chặng crop mới -- vượt phạm vi, dừng và nói ra.

Đây là **đổi nghĩa** `RawBlock.text`, nên `contracts.content.SCHEMA_VERSION` lên **2** (luật của
`packages/contracts/AGENTS.md`). Bên đọc canh nó là bên dựng cây: chữ khối hình **chỉ** dùng làm cổng
D9, khối hình **không bao giờ** là ứng viên heading (hộp layout chồng nhau nên một dòng có thể nằm ở
cả khối hình lẫn khối chữ), và bản thô số 1 chỉ đơn giản là không mở cổng nào. `RawPage.text` không
đổi nghĩa: nó vẫn bỏ khối hình, và bộ đo OCR (`_score_page`) cũng bỏ chữ ấy trước khi chấm.

### D9. Tên chương đọc bằng `gpt-5.6-luna` trên ảnh banner, chỉ ở trang qua cổng OCR

Thêm 11/10/2026 sau phép đo của Task 1 (Status). **Cổng:** một khối `image` mà chữ OCR (D2) chứa
*CHƯƠNG* hoặc *PHẦN*. **Đọc:** cắt phần trên của trang (byte lấy từ MinIO, dựng ảnh qua `pdf.py`),
gửi `gpt-5.6-luna`, nhận JSON `{la_mo_dau, loai, so, ten}`. Nút cấp 1 lấy `numbering` + `title` từ
đó, `title_source = "banner"`. Luna hỏng hoặc trả `null` thì lùi về *"Chương N"* (D6). Lời gọi đi qua
`index/llm.py` như tóm tắt. Phạm vi *"chỉ Jev và OCR"* được người dùng nới đúng cho việc này.

### D3. Chip chờ cây

Hai chỗ đang gửi `DocumentProbed(READY)` -- nhánh tệp có chữ trong `probe_document` và lô OCR cuối --
đổi thành **enqueue `index_document`**. Worker dựng cây ghi cây vào Mongo **trước**, rồi mới gửi
`DocumentProbed(READY, page_count)` (*"chunk trước, `state` sau"*), và gửi `DocumentProgress` ở mỗi
chặng để `progress_at` không trôi quá ngưỡng 300 s. `NO_TEXT_LAYER` và `FAILED` không đổi đường.

### D4. Worker arq thứ hai trong `services/document`

`document.index_worker` tiêu thụ queue riêng `aiafa:document-index`, `max_jobs = 4`, **không nạp
model OCR**. Lý do: worker OCR chạy `max_jobs = 1` vì OCR ăn hết CPU, còn dựng cây là việc **chờ
mạng**; xếp nó sau các lô OCR là bắt Jev chờ OCR. `dev.ps1 index` khởi động nó. Kriky không bị đụng.

### D5. Đường luật là lưới, không phải đường chính

`rules.py` (thuần) suy cấp từ nhãn OCR + mẫu số thứ tự (`CHƯƠNG|PHẦN [IVX]+`, `[A-E]\.`, `BÀI \d+`,
`^\d+\.\s`, `[IVX]+\.\d+`) + *"BÀI TẬP CUỐI CHƯƠNG N"* (suy số chương). Dùng khi (a) `confidence`
của Jev thấp, (b) Jev không với tới được sau retry của SDK -- `IndexHeader.method = "rules"`, tài liệu
vẫn READY, (c) làm đường so trong bộ đo.

### D6. Tóm tắt bằng `gpt-4o-mini`, từ dưới lên, một lời gọi mỗi nút

Cấp 3 từ chữ của chính nó (cắt ở trần ký tự); cấp 2 từ tóm tắt các con + đoạn chữ mở đầu; cấp 1 từ
tóm tắt cấp 2. Song song qua semaphore. Mọi lời gọi qua **một** module, `document/index/llm.py`.
Banner không ra chữ thì tên là *"Chương N"*, `title_source = "numbering"` -- **không model nào bịa
tên**; luna (D9) chỉ đọc tên in trên ảnh.

### D7. Đọc lại thì cây chết

`ContentStore.begin` xoá thêm `nodes`, `chunks`, `block_labels` của tài liệu.
`IndexHeader.raw_started_at` phải bằng `RawDocument.started_at`; lệch là cây cũ.

### D8. Text layer và `.txt`/`.md` cũng qua Jev

Text layer: mọi khối mang nhãn `text`, nên `features` tự lọc ứng viên (ngắn, một dòng, có mẫu số
hoặc viết hoa). `.txt`/`.md`: khối duy nhất tách thành dòng **trong bộ nhớ** -- bản thô không bị sửa
(D6 của 3b); dòng có `#` mang `markdown_level` vào state.

## Hình dạng đầu ra

`packages/contracts/src/contracts/index.py`, `SCHEMA_VERSION = 1`, cùng lệ `contracts.content`:
Mongo là nơi lưu, không phải nơi định nghĩa.

- **`indexes`** (`IndexHeader`), `_id = document_id`: `raw_started_at`, `raw_pipeline`, `method`
  (`jev` | `rules`), `jev_model`, `summary_model`, `node_count`, `chunk_count`, `low_confidence`,
  `page_offset` (trang PDF − trang in phổ biến nhất), `jev_tokens`, `summary_tokens`, `built_at`,
  `schema_version`.
- **`nodes`** (`IndexNode`), `_id = node_key(doc, ordinal)` = `"<doc>:n<ordinal>"`: `document_id`,
  `ordinal` (preorder), `parent_ordinal` (`None` ở cấp 1), `level` (1–3), `numbering`, `title`,
  `title_source` (`text` | `banner` | `numbering`), `anchor` (`BlockRef`), `page_start`,
  `page_end`, `printed_start`, `printed_end`, `summary`, `confidence`. Trỏ cha bằng **ordinal**
  chứ không bằng `_id`: khoá dựng lại được bằng `node_key`, và tìm cha đi đúng index duy nhất
  `(document_id, ordinal)` (review Task 2).
- **`chunks`** (`IndexChunk`), `_id = "<doc>:c<ordinal>"`: `document_id`, `ordinal`, `node_ordinal`
  (nút sâu nhất chứa nó, `None` với phần trước nút đầu), `blocks` (`BlockRef`), `text`,
  `page_start`, `page_end`, `char_count`.
- **`block_labels`** (`BlockLabel`), một mỗi ứng viên, `_id = "<doc>:<page>:<block>[:<line>]"`:
  `ref` (`BlockRef`), `ocr_kind`, `text`, `numbering`, `role` + `role_probabilities`, `level` +
  `level_probabilities`, `confidence`, `decided_by` (`jev` | `rules`). Để gỡ lỗi và để đo.
- **`BlockRef`** = `{page, block, line}` -- `line` chỉ có ở tệp văn bản thuần (D8), nơi cả tệp là
  một khối.
- **Message:** `DocumentIndexRequested(document_id, storage_key, filename, page_count)` (khoá MinIO
  cho D9), `INDEX_DOCUMENT_TASK`.
  Kết quả đi về bằng `DocumentProbed` đã có.

## Files

| File | Việc |
|---|---|
| `packages/contracts/src/contracts/index.py` (mới), `__init__.py` | model, task, message ở trên |
| `services/document/src/document/ocr/page.py` | `_fill` giữ chữ khối `IMAGE` (D2) |
| `services/document/src/document/ocr_handlers.py` | `_OCR_PIPELINE = "text2"`; READY → enqueue dựng cây (D3) |
| `services/document/src/document/content_store.py` | đọc bản thô bằng model; `put_index` ghi đè trọn; `begin` xoá cây (D7); index cho collection mới |
| `services/document/src/document/index/` (mới) | `features`, `rules`, `assemble`, `chunks` (thuần); `jev.py` (module duy nhất import `typesafe_sdk`); `llm.py` (module duy nhất import `langchain`, khuôn của `agent/llm.py`); `graph.py` (LangGraph) |
| `services/document/src/document/index_worker.py`, `index_handlers.py` (mới) | worker D4, `index_document`; đọc byte từ MinIO (`storage.py`) và dựng ảnh banner qua `pdf.py` cho D9 |
| `services/document/src/document/config.py`, `pyproject.toml` | khoá Jev / OpenAI, model tóm tắt, `banner_model = "gpt-5.6-luna"`, độ song song, ngưỡng, tên queue; `typesafe-sdk`, `langgraph`, `langchain[openai]` |
| `.env.example`, `dev.ps1` | khoá mới; lệnh `index` |
| `tools/check_contract.py` | seam `typesafe_sdk` → `jev.py`; seam `langchain` trong `document` → `llm.py` |
| bộ đo cây (`services/document/scripts/`) | so với cây vàng, ghi `data/results/run-<n>/hierarchy-<model>/` |
| `docs/overview/architecture.md`, `data-model.md`, `docs/local-development.md`, `services/document/AGENTS.md`, plan ô, `backlog.md` | |

## Ordered Tasks

Mỗi task xong → subagent review → task kế (luật người dùng, 11/10/2026). Không commit khi người dùng
chưa nói.

- [x] **0. File plan vào repo**; plan ô (dòng 3c) trỏ tới đây; `backlog.md` sửa mục Jev cho khớp D1.
- [x] **1. Chữ banner (D2).** Đo trước: chạy `PageReader` trên trang 6, 30, 58, 78, 99 của Lớp 6
      tập 1, in chữ các dòng nằm trong khối `IMAGE`. Tên chương không ra (dừng, báo) → người dùng chọn
      luna (D9); chữ *CHƯƠNG* thì ra ở 5/5 trang, nên vẫn sửa `_fill` để nó làm cổng: pipeline
      `text2`, `SCHEMA_VERSION` 2, test, OCR lại cả cuốn.
- [x] **2. Hợp đồng và kho.** `contracts/index.py`, đọc/ghi của `ContentStore`, `begin` xoá cây; test
      thuần document ↔ model. **Cây vàng** `data/gold/tree/L6T1.json` (không vào git), soạn tay từ
      OCR + ảnh trang: cấp, số, tên, trang đầu mỗi nút.
- [x] **3. Phân loại.** `features`, `rules`, `jev`, `assemble` + test thuần (Jev giả). Bộ đo trên cây
      vàng, ba đường: chỉ luật / Jev / Jev + lưới luật -- precision, recall theo cấp, khớp
      `page_start`, số lời gọi, token, giây. Chọn `jev_min_confidence` từ phép đo. Ước tính ~500 ứng
      viên × 400 token ≈ 0,2 M token ≈ **$0,01 / lượt**; báo số thật trước lượt thứ hai.
- [x] **4. Tóm tắt, chunk, graph, worker, chip chờ cây.** `llm`, `chunks`, `graph`, `index_worker`,
      đổi READY (D3), check seam, `dev.ps1 index`. Ước tính ~100 nút × 1,5k token ≈ **$0,02 / cuốn**.
      Test: graph với Jev và LLM giả; READY chỉ sau `put_index`; Jev hỏng → `rules`; tiến độ mỗi chặng.
- [x] **5. Text layer và `.txt`/`.md` qua Jev (D8)** + test. Thử `docs/report/report.pdf` (45 heading
      thật, đo ở `backlog.md`) và một `.md`.
- [x] **6. Tài liệu và đóng plan.** Status có số đo thật; nợ về `backlog.md`.

## Validation Checks

- `.\dev.ps1 check`, `test`, `typecheck` xanh sau mỗi task; `ruff format --check` sạch.
- Đột biến, mỗi cái làm một test hay check đỏ: import `typesafe_sdk` trong `graph.py`; gửi READY
  trước `put_index`; bỏ bước gộp `deeper`; đảo thứ tự lựa chọn `role`; `begin` không xoá cây; bỏ cổng
  D9 (hỏi luna ở mọi trang); cho khối hình làm ứng viên heading.
- Bộ đo Task 3: bảng precision / recall theo cấp trên cây vàng L6T1, luật so với Jev.
- Đầu-cuối: `infra-up`, BE, ingest, `document`, `index` chạy. Tải Lớp 6 tập 1 qua màn hình giáo
  viên: chip *đang xử lý* → *sẵn sàng*, không qua *xử lý hỏng*; `mongosh` đếm `nodes` theo cấp -- 5
  chương, số bài khớp cây vàng, mọi nút có `summary`. Tải `report.pdf` và một `.md`: về *sẵn sàng*,
  có cây.

## Status

Viết ngày 11/10/2026, sau khi người dùng chốt sáu điểm ở `Goal` và duyệt thiết kế. Task 0 xong (file
này, plan ô, `backlog.md`).

**Task 1 dừng ở bước đo, đúng điều kiện dừng của D2.** Chạy `PageReader` (easyocr, 4 luồng) với
`_WITHOUT_TEXT` chỉ còn `TABLE`, trên năm trang mở chương của Lớp 6 tập 1 (6, 30, 58, 78, 99) và trang
112. Detector **có** thấy dòng trong banner, nhưng tên chương in kiểu chữ trang trí -- chữ đỏ viền
trắng trên nền ảnh -- nên bộ nhận dạng đọc ra rác:

| Trang | Tên thật (nhìn ảnh) | Chữ OCR trong khối `image` |
|---|---|---|
| 6 | CHƯƠNG I — TẬP HỢP CÁC SỐ TỰ NHIÊN | `CHƯƠNG sấ HỌc 0 5 CaoooraORCTNTTTSMY` |
| 30 | CHƯƠNG II — TÍNH CHIA HẾT … | `CHƯƠNG sấ HỌc n n TÍNH CHIA HẾT TRONG` (một nửa) |
| 58 | CHƯƠNG III — SỐ NGUYÊN | `CHƯƠNG sấ HỌc 7rr nn GRmienvêng S@NsurEn` |
| 78 | CHƯƠNG IV — MỘT SỐ HÌNH PHẲNG … | `kinh HQC CHƯƠNG TrVC quan n5 PASGKmiinomima` |
| 99 | CHƯƠNG V — TÍNH ĐỐI XỨNG … | `hinh HQC CHƯƠNG TrVC qurn ' ĩngPổnXúNOCuA` |

Một trên năm tên đọc được một nửa; **số La Mã của chương không đọc được ở trang nào**. Thứ đọc được
chắc chắn là chữ *"CHƯƠNG"* -- một tín hiệu tốt cho *"trang này mở một chương"*, nhưng không phải một
cái tên.

**Người dùng chọn: *"sử dụng gpt luna 5.6 xem thế nào"*** → D9. Thử ngay (scratchpad, 150 DPI, 40%
trên của trang, `reasoning_effort=low`, cùng cấu hình phép đo VLM của plan 3a): **5/5 chương đúng cả
số lẫn tên**, 1,8–4,0 s mỗi ảnh, 7 035 token vào / 349 ra = **$0,0018** cho 7 ảnh. Đối chứng: trang
112 (*Hoạt động thực hành trải nghiệm*) trả `la_mo_dau: false` -- đúng; nhưng trang 7 (trang bài
thường) bị nhận là *"phần"* mở đầu -- **sai**. Nên luna không được hỏi trên mọi trang: chữ *"CHƯƠNG"*
mà OCR đọc được trong khối ảnh là **cổng** (D2 vẫn cần), luna chỉ đọc tên ở trang qua cổng.

**Task 1 xong về code** sau đó: `_fill` giữ chữ khối hình, `raw_ocr_page` và bộ đo OCR bỏ chữ ấy,
pipeline `text2`, `contracts.content.SCHEMA_VERSION` 2, test cho cả ba. Review subagent: không lỗi
chặn; sáu phát hiện -- docstring cũ (`content.py`, `ocr/model.py`, `data-model.md`), đổi nghĩa field
mà không bump, thiếu test cho `_score_page`, plan tự mâu thuẫn -- đã sửa hết. Worker `document` khởi
động lại trên code mới và cuốn Lớp 6 tập 1 được tải lại qua BE để OCR bằng `text2` (125 trang, về
*sẵn sàng* theo đường cũ vì Task 4 chưa đổi READY).

**Task 2 xong.** `contracts/index.py` (bốn model, `BlockRef` có `line` cho tệp thuần, ba hàm khoá),
`DocumentIndexRequested`, `ContentStore.raw` / `pages` / `put_index`, `begin` xoá cây. **Cây vàng**
`data/gold/tree/L6T1.json`: 91 nút (6 cấp 1, 37 cấp 2, 48 cấp 3), đối chiếu bằng mắt trên ảnh trang.
Hai mục của Bài 21 (trang 100, 101) **OCR bỏ sót hoàn toàn** -- dải đỏ không thành khối nào -- nên
recall cấp 3 có trần dưới 100% với bất kỳ người quyết nào. Jev chạy được bằng khoá trong `.env`
(`jev-1.13.0`, 359 token cho một câu hỏi nhỏ); `typesafe-sdk==0.7.4`. Review subagent: không lỗi
chặn; đã sửa (1) cây tự mâu thuẫn thành `ValueError` trước khi chạm Mongo (`check_index`) -- trước
đó khoá trùng thành `PyMongoError` rồi thành *"Mongo không với tới được"* và arq chạy lại vô ích;
(2) `put_index` từ chối cây dựng trên bản thô đã bị đọc lại (`RawChanged`), hỏi ngay trước khi ghi
đầu mục; (3) docstring, `data-model.md`, lời plan về `parent_ordinal` / `node_ordinal`; (4) test cho
`raw`, `pages`, nhãn qua BSON; `as_document` dùng chung `_bare`.

**Task 3 xong -- và số đo không ủng hộ Jev trên cuốn này.** `hierarchy/features.py`, `rules.py`,
`assemble.py`, `jev.py`, `llm.py` (luna đọc banner, kéo lên từ Task 4 vì bộ đo cần nó),
`pdf.render(top=)`, bộ đo `tools/hierarchy_bench/` (`score`, `run`, `banners`), test. Luna đọc lại
banner với prompt mới qua đúng `llm.py`: **5/5 chương và 5/5 tên bài đầu chương** đúng, 9 723 token.
Bộ đo (`data/results/run-6/hierarchy-jev-1.13.0/`, 492 ứng viên, 91 nút vàng):

| Đường | Nút | Cấp 1 P / R | Cấp 2 P / R | Cấp 3 P / R |
|---|---|---|---|---|
| chỉ luật | 86 | 100 / 83,3 | 100 / 97,3 | 100 / 93,5 |
| Jev thuần (`jev@0`) | 138 | 45,5 / 83,3 | 73,3 / 89,2 | 56,0 / 91,3 |
| Jev, luật dưới 0,6 | 97 | 83,3 / 83,3 | 94,7 / 97,3 | 89,6 / 93,5 |
| Jev, luật dưới 0,8 | 87 | 100 / 83,3 | 97,3 / 97,3 | 100 / 93,5 |

Jev: 492 lời gọi, 626 495 token vào, **$0,0263** (gấp 2,6 lần ước tính $0,01), 7,6 s với 16 lời gọi
song song. Lỗi chính của Jev: **tiêu đề con không đánh số, chữ thường** (*"Cách viết số La Mã"*) bị
xếp cấp 3, 2 hay 1 thay vì `deeper` -- 44 trên 59 lần bất đồng với luật (cấp 3: 30, cấp 2: 11,
cấp 1: 3); thêm 8 ca luật nói *không phải tiêu đề* mà Jev xếp cấp 3; 39 trong 59 ca có `confidence`
dưới 0,4 (đếm lại bởi review Task 3). Từ ngưỡng 0,5–0,6 trở lên, recall hụt ở đâu thì mọi đường hụt
như nhau, vì OCR không ra chữ: tên Bài 10 (trang 39), hai mục Bài 21 (trang 100–101), *Hoạt động
thực hành trải nghiệm* (banner không có chữ CHƯƠNG). Jev thuần còn hụt thêm 3 nút cấp 2 và 1 nút
cấp 3. Giá thật ~1 270 token mỗi lời gọi (ước tính 400): phần lớn là `instructions` + `criteria`
gửi lại mỗi lời gọi.

**Hai điều phải nói thẳng.** (1) Luật được chỉnh **trên chính cuốn dùng để chấm**, nên cột *chỉ luật*
lạc quan; so Jev với luật cho công bằng cần cây vàng của một cuốn khác -- nợ. (2)
`jev_min_confidence` đặt **0,8**, và phải nói đúng nó nghĩa là gì: trong 59 ca Jev và luật bất đồng,
`confidence` cao nhất của Jev là 0,83, nên ở 0,8 **Jev thắng đúng một ca -- và ca ấy sai** (trang 26,
nút thừa của dòng *0,8*). `jev@0.9` trùng khít đường luật. Tức trên cuốn này, cây hiện nay **là cây
của luật**; Jev chưa thay đổi được gì, và ngưỡng cũng được chọn trên chính cuốn dùng để chấm. Người
dùng muốn Jev là chính; số đo nói trên SGK nó chưa hơn luật.

**Lượt Jev thứ hai chưa chạy** -- plan hứa báo số thật trước lượt ấy. Review Task 3 đề xuất một thiết
kế câu hỏi cụ thể cho lượt ấy: bỏ số khỏi state (`page` thành *đầu / giữa / cuối sách*; `numbering`
thành `numbering_kind` kể bằng lời), thêm `letter_case` (*all capitals* / *sentence case*, do code
tính), `level_3` chỉ nhận tiêu đề có một số đơn **và** viết hoa toàn bộ, rút gọn `criteria` để hạ
token. Code giữ nguyên **đúng như lúc đo**, để bảng trên vẫn là bảng của code đang chạy.

Review Task 3 cũng sửa: dependency (`typesafe-sdk==0.7.4`, `langgraph`, `langchain[openai]`) chưa
khai trong `pyproject.toml`; lỗi parse câu trả lời Jev và `usage` rỗng giờ thành `JevUnavailable`
(đường luật) thay vì làm hỏng job; `TaskGroup` huỷ các lời gọi Jev còn bay khi một lời gọi hỏng;
cổng banner khớp nhầm *CHUNG* và *PHÂN*; tên nút không còn giữ `#` hay rác OCR (*"BÀI TẬP CUỐI
CHƯƠNG I"* dựng từ nhãn); NFC trong `units()`; `isdecimal` cho số trang in; mẫu *"BÀl 9"*. Đường luật
đo lại sau các sửa: không đổi (86 nút, cùng bảng).

**Task 4 và 5 xong.** `hierarchy/chunks.py`, `hierarchy/graph.py` (LangGraph, bảy bước thẳng),
`index_handlers.py`, `index_worker.py` (queue `aiafa:document-index`, `max_jobs = 4`, không nạp model
OCR), `handlers._settle` (`READY` thành một job dựng cây, id cố định `index:<doc>`),
`ContentStore.indexed`, ba seam mới trong `tools/check_contract.py`, `dev.ps1 index`, `.env.example`.
Task 5 lộ ra ở thử đầu-cuối: `report.pdf` (text layer) lần đầu chỉ ra **6 nút** cho ~45 tiêu đề, vì
PyMuPDF xếp *"1.1\nBối cảnh"* thành một khối hai dòng và bộ lọc đòi một dòng, và vì *"Chương 1"*
tách khỏi tên chương. Sửa: khối tối đa hai dòng, tên chương lấy từ khối kế nếu ngắn và không mang
nhãn số, *"1.1"* chỉ là bài tập khi tài liệu đi qua OCR. Lần hai: **42 nút**, đủ ba cấp.

**Thử đầu-cuối, 11/10/2026** (BE, ingest, `document`, `index`, FE chạy; tải qua API của BE):

| Tài liệu | Từ tải lên tới *sẵn sàng* | Cây |
|---|---|---|
| `bai.md` (tự viết, 4 tiêu đề `#`) | vài giây | 4 nút, đúng cả ba cấp, có tóm tắt |
| `docs/report/report.pdf` (text layer, 31 trang) | ~10 s | 42 nút (6 chương), 52 chunk |
| SGK Lớp 6 tập 1 (scan, 125 trang) | **9 phút 33 giây**, không qua *xử lý hỏng* | 87 nút, 149 chunk; dựng cây **39 s** |

Cây của cuốn SGK **đọc thẳng từ Mongo** chấm với cây vàng: cấp 1 P 100% / R 83,3%, cấp 2 P 97,3% /
R 97,3%, cấp 3 P 100% / R 93,5% -- đúng dòng `jev@0.8` của bộ đo, tức đường thật và bộ đo cho cùng
một cây. Cả 87 nút có tóm tắt. Một cuốn tốn ~626 nghìn token Jev (**$0,026**) và ~104 nghìn token
OpenAI (tóm tắt `gpt-4o-mini` cộng ~10 nghìn token luna).

**Đột biến, 8/8 bị giết:** `READY` gửi trước khi dựng cây; bỏ bước gộp `deeper`; đảo thứ tự lựa
chọn `role`; `begin` không xoá cây; bỏ cổng D9; khối hình làm ứng viên; lỗi lạ không gửi `FAILED`;
dựng cây trên bản thô đọc dở -- mỗi cái làm test đỏ. Import `typesafe_sdk` trong `graph.py` làm check
`sync-sdk-seam` đỏ.

**Review Task 4–5** (subagent): thứ tự `READY` đúng ở mọi đường. Đã sửa: (1) **mức cao** -- job dựng
cây chết im với lỗi lạ hay khi chạm `job_timeout` (arq không chạy lại) → bắt mọi lỗi còn lại, gửi
`FAILED` kèm *"Đã đọc được chữ nhưng chưa dựng được mục lục"*, và tự cắt ở 540 s trước trần 600 s;
(2) `RawChanged` khi lần đọc mới **đã xong** thì chạy lại thay vì bỏ -- id cố định đã từ chối job của
lần đọc mới; (3) không dựng cây trên bản thô đọc dở (`finished_at`), kể cả ở `_already_indexed`; (4)
nhịp tim sau mỗi banner và mỗi lượt tóm tắt, luna gọi song song; (5) luna nói rõ *không phải trang
mở đầu* thì bỏ cổng, nhãn *"Chương N"* chỉ đếm cổng được giữ; (6) không tóm tắt nút chỉ có tiêu đề;
semaphore Jev chung cả worker; khoá cho `pdf.render`; seam bắt cả `from google import genai`; tài
liệu (`local-development.md` sáu process và chẩn đoán `index`, `architecture.md`,
`services/document/AGENTS.md` viết gọn lại cho vừa trần 25 dòng, dòng `services/document` trong bảng
của `AGENTS.md`, `README.md`, docstring `pages_read`). Gốc `AGENTS.md` đã ở đúng trần 182 dòng nên
**không** thêm dòng bất biến mới -- luật *"BE và `ingest` không import SDK model"* được canh bằng
check, ghi ở `architecture.md` và `check_contract.py`.

**Cổng:** `.\dev.ps1 check` 20/20, `lint-imports` 3 KEPT, `ruff format --check` sạch, pytest **679
passed** (test BE chập chờn `test_a_turn_that_outlived_its_lock...` lần này qua). Nợ về `backlog.md`,
mục *Nợ của plan 3c*.

**Đóng 11/10/2026** theo lời người dùng. Lượt Jev thứ hai **không chạy** trong plan này: cây hiện
nay trên SGK là cây của luật, và việc kế tiếp là nối cây vào BE chứ chưa phải làm Jev tốt hơn --
thiết kế câu hỏi mới nằm ở `backlog.md`, mục *Nợ của plan 3c*. Cổng của plan ô đạt **một nửa**:
một cuốn sách thật ra đủ chương (5/5, có tên); `get_chapter` trả metadata thì chưa, vì ba tool đọc
thuộc plan 5.

**Đổi tên theo yêu cầu người dùng, 11/10/2026, sau Task 6:** `handlers.py` → `ocr_handlers.py`,
`worker.py` → `ocr_worker.py` (lệnh `.\dev.ps1 document` chạy `document.ocr_worker`), gói
`hierarchy/` → `index/`; test đổi theo (`test_ocr_handlers.py`, `test_ocr_worker.py`,
`test_index.py`). Các đoạn Status phía trên giữ tên cũ vì chúng ghi lại lúc ấy.
