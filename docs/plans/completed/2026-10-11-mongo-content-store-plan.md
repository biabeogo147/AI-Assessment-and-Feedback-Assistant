# Plan 3b — MongoDB làm kho nội dung, và OCR nối vào luồng upload

## Context

Người dùng chia lại đợt *Đọc PDF vào ngữ cảnh ra đề* (11/10/2026), vì 3b cũ quá rộng (vừa dựng
Mongo vừa thiết kế Jev):

| Plan | Nội dung |
|---|---|
| 3a | OCR ra chữ — **đã đóng** |
| **3b** | **Dựng MongoDB, lưu bản thô của mọi tài liệu ngay sau khi đọc**, chuẩn bị cho 3c |
| 3c (mới) | *Document agent* dùng Jev: đọc bản thô từ Mongo, dựng cây/chunk, **ghi ngược lại** Mongo |
| 3d | sympy kiểm công thức (3c cũ) |

Lời người dùng: *"sau bước ocr, cần lưu raw vào mongo kể cả khi chưa có pageindex. Sau này
document agent sẽ lấy data từ mongodb để xử lí tiếp, và inject lại vào mongodb."*

Ba quyết định người dùng chốt qua câu hỏi (11/10/2026):

1. **Nối OCR vào luồng upload thật** — PDF scan không dừng ở *"không đọc được chữ"* nữa.
2. **Mongo là kho nội dung, như MinIO** — `document` (và document agent ở 3c) được giữ khoá Mongo.
3. **Lưu bản thô cho mọi tài liệu** — PDF scan (OCR), PDF có text layer, `.txt`/`.md`, cùng một
   hình dạng.

Bốn sự thật của code hiện tại mà plan phải sống cùng:

- `services/document/src/document/handlers.py::probe_document` chỉ phán *có chữ / không*;
  OCR (`document/ocr/page.py::PageReader`) chưa được gọi từ đâu cả.
- `services/document/src/document/worker.py`: `_JOB_TIMEOUT_SECONDS = 120`. BE suy ra `FAILED`
  khi hàng đứng `processing` quá `document_stale_after_seconds = 300` tính từ `uploaded_at`
  (`services/be/src/be/teacher_documents.py::_as_read`). Một cuốn 200 trang × 4,5 s ≈ 15 phút.
- `tools/check_contract.py::check_agent_and_document_hold_no_database_credentials` dùng
  `DB_CREDENTIAL_PATTERN` khớp **`MONGO`** và **`pymongo`**. Tiền lệ: khoá MinIO không tính, vì
  *"object storage là nơi byte nằm, không phải nơi sự thật nằm"*.
- `pymongo` chưa cài. Bản ≥ 4.13 có `AsyncMongoClient` async thuần — không cần bọc thread.

## Decision Records

**D1. Mongo là kho nội dung, Postgres vẫn là kho sự thật.** Mongo giữ *thứ đọc được từ tệp* (bản
thô, và ở 3c là cây/chunk). Trạng thái tài liệu (`documents.state`) vẫn **chỉ** ở Postgres, chỉ
`ingest` ghi. Nên check `agent-no-db` được sửa **có chủ đích**: cho phép `MONGO_*` và `pymongo`
trong `services/document` (3c sẽ mở cho AGENT), bằng đúng lập luận đã cho MinIO, viết vào docstring
của check. Không ai ngoài BE/ingest đọc hay ghi Postgres — luật ấy không đổi.

**D2. Một module duy nhất chạm `pymongo` trong mỗi service.** `document/content_store.py`, cùng lệ
`storage.py` (MinIO) và `pdf.py` (pymupdf). Thêm check grep được: chỉ file ấy import `pymongo`.

**D3. OCR một cuốn sách = chuỗi job theo lô trang, nối đuôi nhau.** Mỗi job đọc `ocr_pages_per_job`
trang (mặc định 10 ≈ 45 s, dưới trần 120 s), ghi từng trang vào Mongo, báo tiến độ, rồi **tự
enqueue lô kế tiếp**. Nối đuôi chứ không song song: OCR ăn hết CPU, VPS chỉ có 4 vCPU, và hai lô
chạy cùng lúc chỉ tranh luồng (bài học 3a). Lô cuối gửi kết quả cuối.

**D4. Tiến độ là thứ giữ tài liệu khỏi bị coi là chết.** Thêm vào `documents` hai cột
`pages_read` và `progress_at`. Message tiến độ mới từ `document` → `ingest` cập nhật chúng. BE đổi
phép suy *đứng quá lâu* sang đo từ `max(uploaded_at, progress_at)`. Một lô chết thật (hết lượt thử
của arq) thì sau 300 s không tiến độ, chip vẫn ra *xử lý hỏng* — lưới cũ còn nguyên. Không có
migration: repo dựng schema bằng `create_all`, và người dùng đã cho phép xoá DB local dựng lại.

**D5. Không đổi FE, không đổi Figma.** Bốn trạng thái giữ nguyên. Thứ đổi là *đường đi*: PDF scan
đi `processing` → `ready` (khi OCR ra chữ) thay vì `processing` → `no_text_layer`. `no_text_layer`
còn nghĩa khi OCR xong mà **cả cuốn không ra chữ nào**. Hiển thị tiến độ *"đang đọc 37/200 trang"*
cần FE + Figma → ghi nợ, không làm ở đây.

**D6. Bản thô là bất biến; 3c ghi vào chỗ khác.** Collection `pages` chỉ được ghi bởi đường đọc
của 3b (upsert theo `_id`, nên arq chạy lại một lô không nhân đôi). Document agent ở 3c **không sửa
`pages`**: nó ghi vào collection của riêng nó (`toc`, `chunks` — 3c chốt), trỏ về
`document_id` + số trang. Đọc lại một tài liệu là ghi đè `pages` của nó, và 3c phải dựng lại từ đó.

**D7. Hình dạng của thứ nằm trong Mongo sống ở `packages/contracts`.** Bổ sung lúc vào Task 0,
11/10/2026: Decision Record *"byte sang MinIO, chunk sang MongoDB"* của plan ô có điều kiện *"không
thương lượng"* rằng *"`packages/contracts` giữ hình dạng của một chunk. Mongo là nơi lưu, không phải
nơi định nghĩa"*. Plan duyệt chưa nói hình dạng đặt ở đâu, nên theo luật đã có: `contracts/content.py`
khai `RawBlock`, `RawPage`, `RawDocument` (pydantic, frozen). `content_store.py` ghi chúng bằng
`model_dump`, document agent ở 3c đọc chúng bằng `model_validate` -- hai bên không thể lệch nhau.
Điều kiện thứ hai của Decision Record ấy -- *"BE là service duy nhất ghi Mongo"* -- bị **thay thế**
bởi D1, và plan ô đã ghi việc thay thế ngay tại chỗ.

## Hình dạng dữ liệu trong Mongo (database `aiafa_content`)

`documents` — một document mỗi tài liệu:
```
{ _id: document_id, source: "ocr" | "text_layer" | "plain",
  page_count, pipeline: "text1" | null, reader: "easyocr" | null,
  started_at, finished_at | null }
```
(Bản đầu của khối này có `pages_read`; review Task 1 chỉ ra nó trùng với cột Postgres của D4 --
tiến độ là chuyện *đã nghe được gì*, nên nó sống ở kho sự thật, không ở kho nội dung. Đã bỏ.)
`pages` — một document mỗi trang:
```
{ _id: "<document_id>:<page>", document_id, page (từ 1), source,
  width, height,                       # null với .txt/.md
  blocks: [ { kind, box: [l,t,r,b] | null, text } ],   # theo thứ tự đọc
  text,                                # nối mọi khối có chữ, cho 3c đọc nhanh
  seconds: { render, layout, ... } | null, read_at }
```
- PDF scan: `blocks` từ `PageReader.read_page` (nhãn layout thật — `formula`, `paragraph_title`,
  `number`… — là tín hiệu 3c cần).
- PDF có text layer: `blocks` từ `page.get_text("blocks")` của PyMuPDF (có hộp), `kind` = `text`.
- `.txt` / `.md`: một trang, một khối, `box` null.
- Index: `pages(document_id, page)` duy nhất.

## Luồng mới

```
BE upload ─ DocumentProbeRequested ─▶ document.probe_document
   ├─ .txt/.md, PDF có chữ: ghi pages (+documents) vào Mongo ─▶ DocumentProbed(READY) ─▶ ingest
   ├─ tệp hỏng: DocumentProbed(FAILED) như cũ
   └─ PDF scan: ghi documents{source:"ocr"} ─▶ enqueue ocr_pages(trang 1..10) trên chính queue
                                                (KHÔNG gửi NO_TEXT_LAYER như trước)
document.ocr_pages(lô k)
   ├─ đọc byte từ MinIO, PageReader.read_page cho từng trang, upsert pages
   ├─ DocumentProgress(pages_read, page_count) ─▶ ingest: UPDATE pages_read, progress_at
   ├─ còn trang: enqueue lô k+1
   └─ lô cuối: tổng chữ > 0 ? DocumentProbed(READY, page_count) : DocumentProbed(NO_TEXT_LAYER)
```
`PageReader` nạp một lần trong `on_startup` của worker `document` (5–6 s, đo ở 3a).

## Files

| File | Việc |
|---|---|
| `docker-compose.infra.yml` | service `mongo` (`mongo:7`), port 27017, volume `aiafa-mongodata`, healthcheck `mongosh --eval ping` |
| `.env.example` | `MONGO_URL`, `MONGO_DATABASE` (đọc bởi `document.config.Settings` → check `env-example` đạt) |
| `services/document/pyproject.toml` | `pymongo>=4.13` |
| `services/document/src/document/config.py` | `mongo_url`, `mongo_database`, `ocr_pages_per_job=10`, `ocr_reader="easyocr"`, `ocr_threads=4` |
| `services/document/src/document/content_store.py` | **mới.** Module duy nhất import `pymongo`: `ContentStore.begin(header: RawDocument)`, `.put_page(...)`, `.finish(...)`, `.characters(document_id)`, tạo index |
| `services/document/src/document/pdf.py` | `PdfPages.page_text(index)` (text layer có hộp) — vẫn là module duy nhất chạm pymupdf |
| `services/document/src/document/probe.py` | giữ chính sách; thêm hàm thuần dựng bản thô cho `.txt/.md` và PDF có chữ |
| `services/document/src/document/handlers.py` | `probe_document` rẽ ba nhánh như sơ đồ; `ocr_pages` mới. *(Khi làm: nhánh cũ *PDF scan → `NO_TEXT_LAYER`* không phải một khối code riêng -- nó là đường gửi chung của mọi phán quyết -- nên không có gì để comment `# [CODE CHẾT]`; `probe_document` chỉ rẽ phán quyết ấy sang OCR.)* |
| `services/document/src/document/worker.py` | đăng ký `ocr_pages`; `on_startup` nạp `PageReader` và mở `ContentStore` |
| `packages/contracts/src/contracts/documents.py` | `OCR_PAGES_TASK`, `DocumentPagesRequested(document_id, storage_key, filename, first, page_count)`; `DOCUMENT_PROGRESS_TASK`, `DocumentProgress(document_id, pages_read, page_count)` |
| `services/ingest/src/ingest/handlers.py` + `worker.py` | `document_progress`: `UPDATE documents SET pages_read, progress_at`; không announce (FE không vẽ tiến độ) |
| `packages/schema/src/schema/models.py` | `Document.pages_read: int | None`, `Document.progress_at: datetime | None` + docstring |
| `services/be/src/be/teacher_documents.py` | `_as_read` đo *đứng quá lâu* từ `max(uploaded_at, progress_at)` |
| `tools/check_contract.py` | sửa `agent-no-db` (D1); thêm check *chỉ `content_store.py` import `pymongo`* (D2) |
| `dev.ps1` | `db-reset` xoá thêm database Mongo |
| `docs/overview/architecture.md`, `docs/overview/data-model.md` | Mongo là kho nội dung; hai collection; luật bất biến của `pages` (D6) |
| `services/document/AGENTS.md` | một dòng: khoá Mongo được phép, chỉ qua `content_store.py` |
| `docs/plans/active/2026-10-11-mongo-content-store-plan.md` | **mới**, chính plan này |
| `docs/plans/active/2026-10-07-doc-pdf-vao-ngu-canh-plan.md`, `docs/plans/backlog.md` | bảng chín plan → mười (3b/3c/3d mới); mục Jev → 3c; mục sympy → 3d |

## Ordered Tasks

0. [x] **Hỏi người dùng commit plan 3a trước** (lệ: commit khi bắt đầu bước kế). Rồi viết file plan
   3b vào repo, cập nhật plan ô + backlog (chia 3b/3c/3d).
1. [x] **Mongo lên được.** compose + `.env.example` + `pymongo` + `config.py` + `content_store.py` +
   check D2 + sửa check D1. Test thuần cho phần dựng document (không cần Mongo chạy); một lệnh thử
   tay `infra-up` rồi ghi/đọc một trang. → subagent review.
2. [x] **Bản thô cho tài liệu có chữ.** `pdf.page_text`, nhánh `.txt/.md` + PDF có chữ trong
   `probe_document`. Thử tay: tải `docs/report/report.pdf` (có text layer) qua BE → `pages` đủ số
   trang. → subagent review.
3. [x] **OCR theo lô cho PDF scan + tiến độ.** contracts, `ocr_pages`, `DocumentProgress`, ingest,
   hai cột schema, BE stale. Test: chuỗi lô (lô cuối, lô giữa, cả cuốn không chữ → `NO_TEXT_LAYER`),
   stale đo từ `progress_at`. Thử tay: tải một cuốn SGK scan, xem `pages` lớn dần, chip đi
   `processing` → `ready`, không bị `failed` giữa đường. → subagent review.
4. [x] **Tài liệu + đóng plan.** architecture/data-model/AGENTS, Status có số đo thật (giây/trang trong
   worker, tổng thời gian một cuốn), nợ.

## Verification

- `.\dev.ps1 check` (check D1 đã sửa, check D2 mới, `env-example`), `test`, `typecheck` xanh sau
  mỗi task; `ruff format --check` sạch.
- Đột biến: thêm `import pymongo` vào `handlers.py` → check D2 đỏ; bỏ `progress_at` khỏi phép suy
  stale → test đỏ; bỏ bước enqueue lô kế → test đỏ.
- Đầu-cuối (máy này, `infra-up`, BE + ingest + document chạy): tải một PDF có chữ và một cuốn SGK
  scan qua màn hình giáo viên; `docker exec aiafa-mongo mongosh` đếm `pages` khớp `page_count`;
  chip cuốn scan về `ready` sau ~15 phút mà không qua `failed`. Thử tay trên trình duyệt theo lệ
  (`gpt-4o-mini` không liên quan ở đây vì không gọi model).

## Ngoài phạm vi

Document agent / Jev / cây mục lục / chunk (3c); sympy (3d); đọc công thức bằng VLM (backlog);
hiển thị tiến độ trên chip (cần Figma); xoá bản thô khi giáo viên xoá tài liệu (BE không có khoá
Mongo — ghi nợ); chạy OCR trong container.

## Đóng lượt

Không commit khi người dùng chưa nói. `data/` không vào git. Không in giá trị `.env`. Subagent
review sau mỗi task (đã ghi trong Ordered Tasks).

## Status

**Task 0** 11/10/2026: người dùng chọn **chưa commit plan 3a** -- tự review rồi commit sau. Nên
thay đổi của 3a và 3b nằm chung trong cây làm việc chưa commit; Status của mỗi plan là chỗ phân
biệt cái nào của plan nào. Plan ô và `backlog.md` chia lại 3b / 3c / 3d.

**Task 1** 11/10/2026: xong. Mongo (`mongo:7`) lên healthy; thử tay qua `ContentStore` trên Mongo
thật: ghi 3 lần vào 2 trang ra 2 trang (upsert theo `_id`), `characters` đúng, `begin` lại xoá
sạch trang cũ, giờ đi về có múi giờ, cắt tới mili giây. Review Task 1 bắt 22 file CRLF (script
Python trên Windows), mốc thời gian mất micro giây qua BSON, seam `pymongo` chỉ quét
`document` -- đã sửa cả ba. Thử tay bắt thêm một lỗ: `finish` không qua `_to_bson_time`, nên giờ
không múi vẫn lọt -- đã bịt.

**Task 2** 11/10/2026: xong code + thử tay + review. `pdf.PdfPages.page_text`, `probe.raw_pages`
(NFC), `handlers._keep_raw` ghi kho **trước** `READY`; worker mở kho lúc khởi động và **chết** nếu
Mongo không với tới. `RawDocument.pipeline` thành `None` khi không qua OCR (như `reader`). Đầu-cuối:
tải `docs/report/report.pdf` qua BE → `ready` sau 0,14 s, Mongo có **31/31** trang, 0 trang rỗng,
35 354 ký tự, hộp theo điểm của trang (595 × 842). Đột biến: bỏ nhánh ghi kho, bỏ trang trắng,
bỏ NFC -- test đỏ cả ba. Bộ lọc khối ảnh sống sót đột biến vì cờ mặc định của PyMuPDF vốn không trả
khối ảnh: bỏ bộ lọc, thay bằng test canh chính mặc định ấy.

Review Task 2 (subagent, 11/10/2026), đã sửa: đường PDF không có test NFC / strip / nối khối (đột
biến sống) -- thêm test bằng `open_pdf` giả, vì PyMuPDF không dựng nổi PDF có dấu; nhánh
`PdfUnreadable` của `_keep_raw`, `startup`/`shutdown` của worker và luật thời gian của `finish`
(tách thành hàm thuần `finished`) không ai canh -- thêm test; nhật ký thứ tự thiếu `begin`; tên
`page_blocks` trong plan lệch code. Bảy đột biến từng sống giờ đều đỏ.

Hai phát hiện vượt phạm vi Task 2, người dùng chốt 11/10/2026:
- **arq không tự thử lại** khi job ném một lỗi thường -- chỉ khi gặp `arq.Retry` (đọc
  `arq/worker.py` 0.28). Docstring có từ trước 3b nói *"ném để arq thử lại"* là sai: Mongo hay
  Redis chập chờn một nhịp làm job hỏng hẳn, chip chờ 300 s mới ra *xử lý hỏng*. Chọn **thử lại
  thật**: `content_store` dịch lỗi `pymongo` thành `ContentStoreUnavailable`, `_hand_back` dịch lỗi
  Redis / lời từ chối của arq thành `HandBackFailed`, `handlers` đổi cả hai thành
  `Retry(defer=lần thử × 5 s)`; `max_tries = 5` → tổng chờ 50 s, dưới ngưỡng 300 s. Task 3 (lô OCR)
  dựa vào cùng cơ chế này.
- **Tệp `.txt`/`.md` không phải UTF-8** từng ra `READY` với `�` / NUL -- từ 3b là đóng băng rác
  vào bản thô. Chọn **đọc đúng hoặc từ chối**: UTF-8 (bỏ BOM), UTF-16 có BOM; còn lại `FAILED` với
  câu *"Tệp không lưu ở dạng UTF-8..."*. `probe` và `raw_pages` dùng chung `_decode_plain_text`.

Nợ ghi lại, không làm ở 3b:
- **PDF lai qua cổng 10%** (vd. 40/400 trang có lớp chữ mỏng) ra `READY` / `text_layer` với 360
  trang rỗng, và không bao giờ đi OCR. 3c dựng cây trên một bản thô thủng. Hướng: trang dưới
  `_MIN_CHARS_PER_PAGE` đi OCR -- cần đo trên một bản scan có lớp OCR mỏng thật.
- **Bản thô mồ côi**: kho ghi xong nhưng `_hand_back` hỏng thì Postgres không bao giờ `READY`;
  giáo viên tải lại là `document_id` mới. Gộp vào nợ *xoá bản thô khi xoá tài liệu*.
- Mỗi trang một `replace_one`: 2000 trang ≈ 1 s với Mongo local; Mongo ở xa (RTT ~20 ms) ≈ 40 s,
  vẫn dưới trần 120 s -- `bulk_write` khi cần.

**Đóng 11/10/2026 sau Task 2**, theo lời người dùng (*"đóng được plan rồi đấy"*). Plan 3a và 3b
commit chung một lần, vì thay đổi của hai plan đan nhau trong cùng file (`config.py`,
`pyproject.toml`, `check_contract.py`). Thứ đã có: Mongo trong hạ tầng, `contracts.content`,
`ContentStore`, bản thô của PDF có chữ và `.txt`/`.md` ghi trước `READY`, `arq.Retry` cho kho và
queue chập chờn, từ chối tệp thuần không phải UTF-8. Tài liệu: `architecture.md`, `data-model.md`,
`AGENTS.md` gốc và của `services/document`.

**Cổng của plan chưa đạt**: *"một cuốn SGK scan ... ra đủ trang trong Mongo"* cần Task 3. Task 3 và
bốn món nợ của review Task 2 nằm ở mục *OCR theo lô cho PDF scan — việc còn lại của plan 3b* trong
`backlog.md`, chép xuống trước khi file này rời `active/`.

Kiểm cuối: `.\dev.ps1 check` 20/20; pytest của `document`, `packages`, `tools` xanh; ruff sạch;
không file CRLF; 15 đột biến của Task 2 đều đỏ.

**Mở lại 11/10/2026** theo lời người dùng (*"mở lại rồi làm toàn bộ task 3b đi"*): đóng sau Task 2
là dừng sớm -- cổng của plan cần Task 3. File về lại `active/`; mục nợ trong `backlog.md` đổi thành
*Nợ của plan 3b*.

**Task 3** 11/10/2026: xong code + review + thử tay.

- `contracts`: `OCR_PAGES_TASK` / `DocumentPagesRequested` (`first`, `page_count` ≥ 1),
  `DOCUMENT_PROGRESS_TASK` / `DocumentProgress` (không mang `state`).
- `probe_document`: phán quyết `NO_TEXT_LAYER` cho một PDF **có trang** rẽ sang OCR -- `begin` đầu
  mục (`source=ocr`, `reader`, `pipeline=text1`) **rồi** giao lô 1 trên chính queue `document`;
  không gì về BE. PDF 0 trang và tệp thuần rỗng vẫn là phán quyết cuối. Không có khối code nào để
  comment `# [CODE CHẾT]`: nhánh cũ là đường gửi chung của mọi phán quyết.
- `ocr_pages`: đọc tới `ocr_pages_per_job` trang (dừng sớm khi quá ngân sách 90 s), ghi từng trang,
  báo tiến độ, giao lô kế với id cố định `ocr:<doc>:<first>`; lô cuối `finish` → `characters` →
  `READY` / `NO_TEXT_LAYER`. Lỗi đọc trang **bất kỳ** → `FAILED` nói số trang; kho / Redis chập
  chờn → `Retry`; object storage hụt giữa chuỗi → `Retry`, chỉ lần thử cuối mới `FAILED`.
- Worker: `PageReader` nạp ở `startup` (≈ 8 s cả import), `max_jobs = 1`, `max_tries = MAX_TRIES`.
- `ingest.document_progress`: ghi `pages_read`, `progress_at` (giờ của ingest), chỉ khi hàng còn
  `processing`; không hích màn hình. `schema`: hai cột mới -- cần `.\dev.ps1 db-reset`.
- BE `_as_read`: *đứng quá lâu* đo từ `max(uploaded_at, progress_at)`.

**Thử tay đầu-cuối** (máy này, Windows, 4 luồng, Mongo/Redis/Postgres/MinIO trong Docker; BE,
ingest, document chạy thật; tải qua `POST /api/teacher/documents`):

| Tệp | Trang | Tải lên → `ready` | OCR / trang (trung bình, chậm nhất) | Ký tự | Trang rỗng |
| --- | --- | --- | --- | --- | --- |
| SGK Kết nối tri thức Lớp 6 tập 1 (scan thuần) | 125 | **9 phút 1 s** | 4,26 s, 5,8 s | 153 740 | 0 |
| 25 trang đầu Lớp 7 tập 1, code sau review | 25 | 1 phút 51 s | -- | -- | -- |

Chip đi `processing` → `ready`, **không qua `failed`** dù cuốn 125 trang đứng `processing` gần gấp
đôi ngưỡng 300 s: `progress_at` nhích mỗi ~41-45 s (13 lô, mỗi lô 10 trang ≈ 41 s, dưới trần 120 s).
Mongo đếm **125/125** trang khớp `page_count`; 3 309 khối mang nhãn layout thật (`text` 1 760,
`image` 486, `paragraph_title` 465, `formula` 256, `number` 122, ...). Cuốn 125 trang chạy trên
worker bản trước review; worker được khởi động lại rồi chạy bản 25 trang trên code cuối.
**Không thử trên trình duyệt**: hai Chrome cùng nối vào, công cụ đòi hỏi người dùng chọn một, và
người dùng đã dặn không dừng giữa chừng. Màn hình không đổi gì trong plan này (D5); trạng thái mà
nó vẽ đã kiểm qua chính API nó gọi.

Đột biến (16, đều đỏ): bỏ `progress_at` khỏi phép suy stale; bỏ giao lô kế; bỏ báo tiến độ; bỏ id
cố định; `characters > 0` thành luôn đúng; bỏ điều kiện *PDF có trang*; bỏ lọc `processing` ở
ingest; `max_jobs` 10; bỏ nạp `PageReader`; nối cả khối rỗng vào `text`; bỏ `HandBackFailed` khỏi
lô cuối; `except Exception` thành `PdfUnreadable`; bỏ ngân sách giờ; điều kiện lần thử cuối luôn
sai / luôn đúng; bỏ `last = page`.

Review Task 3 (subagent, 11/10/2026) không thấy lỗi trong chuỗi lô (khoảng trang, thứ tự `begin` →
lô 1, tiến độ → lô kế, `finish` → kết quả, id cố định với `keep_result = 0`). Đã sửa theo nó: lỗi
OCR không phải `PdfUnreadable` và lô chạm `job_timeout` từng giết chuỗi lô **im** (arq không chạy
lại cả hai) -- thêm `except Exception` và ngân sách 90 s; object storage hụt giữa chuỗi từng đánh hỏng
cả cuốn -- giờ `Retry`; hai nhánh `Retry` của `ocr_pages` thiếu test; chú thích tổng thời gian thử
lại sai với lô OCR; `ocr_pages_per_job = 0` hay `first = 0` làm chuỗi dừng im -- `ge=1`. Không sửa,
ghi nợ: **nhiều cuốn scan cùng lúc** (`max_jobs = 1` cho khoảng tiến độ `k` × 45 s, vượt 300 s từ
`k` ≈ 7); chạy lại đọc lại cả lô; id cố định chỉ đủ với một process; `pages_read` dừng ở lô áp chót.

**Task 4** 11/10/2026: `architecture.md` (đường OCR theo lô, `max_jobs = 1`, đoạn `to_thread` cũ nói
*"chín job kia"* đã sai), `data-model.md` (hai cột), `local-development.md` (scan mất nhiều phút,
cách xem tiến độ, stale đo từ tin cuối), `backlog.md`. `services/document/AGENTS.md` không đổi --
24/25 dòng, và luật của nó (`Retry`, `to_thread`, thất bại đọc tệp là kết quả) phủ đường mới.

**Đóng 11/10/2026.** Cổng đạt: một cuốn SGK scan tải lên qua BE ra đủ trang trong Mongo, chip về
*sẵn sàng* không qua *xử lý hỏng*.
