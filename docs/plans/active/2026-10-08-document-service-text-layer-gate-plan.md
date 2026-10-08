# Plan 2a — `services/document` ra đời, và cổng text layer

## Context

Plan 1 đã đẩy byte tài liệu sang MinIO (`a1d481f`). Nay có một chỗ cất mà **chưa ai đọc nó**:
`documents` giữ một khoá, và không gì trong repo mở tệp ra bao giờ. ADR-27 đòi hai thứ mà việc
mở tệp mới trả được — *"một tệp không đọc được chữ thì không bao giờ dùng được"*, và bốn trạng
thái mà màn hình phải nói được — còn `models.Document` hiện tự thừa nhận món nợ: *"Không có
`page_count`, và không có cờ 'đọc được chữ'. Chúng đòi mở file ra đọc."*

Plan này mở tệp. Nó đẻ ra **service thứ tư** (`services/document`), cho BE **process thứ hai**
(một worker arq), và nối một vòng việc: BE nhận tệp → đẩy job → `document` đọc từ MinIO bằng
PyMuPDF → đẩy kết quả về → BE ghi Postgres. Mã **C2** và **C11**.

**Đợt việc đi từ năm plan lên sáu.** Ô của đợt gộp cả chip bốn trạng thái vào plan 2, nhưng
đường rạch giữa *vòng việc chạy được* và *chip nói ra được* rất sạch, và nửa sau kéo theo Figma.
Nên plan 2 tách làm hai, và file này là **2a**: nó **không chạm FE, không chạm Figma**. Chip hôm
nay không nói trạng thái; 2a không làm nó nói dối thêm, nó chỉ chưa nói.

**Kết quả mong đợi:** tải một PDF chữ lên, vài giây sau `GET /api/teacher/documents` trả
`state: "ready"` kèm `page_count` đúng. Tải một PDF scan lên, trả `state: "no_text_layer"` kèm
một lý do bằng lời giáo viên hiểu.

## Scope

**Trong:** service `services/document`; worker của BE; hai queue mới; ba cột mới trên
`documents`; ba field mới trên `DocumentRead`; cổng text layer; `pymupdf` được khai; nới hai
repo check sang service mới; nâng cap `AGENTS.md`; tài liệu và sơ đồ.

**Ngoài:** mục lục, chương, chunk, Mongo (plan 3); Jev, skill (plan 4); nội dung vào prompt
(plan 5); **chip bốn trạng thái, FE, Figma (plan 2b)**.

**Không đổi tên `aiafa:grading`.** Tên ấy sai sẵn — nó chở bảy task không cái nào là chấm bài —
nhưng đổi nó là một refactor không thuộc phạm vi này, và `AGENTS.md` cấm refactor kèm. Plan này
chỉ **không chất thêm** lên nó.

## Decision Records

### Decision: `services/document` chỉ có worker, không có cổng HTTP

**options considered:** (a) FastAPI + worker, cổng 8100 theo quy ước · (b) **chỉ worker arq.**

**selected option:** (b).

**reason:** `architecture.md:162` cấp cho service thứ tư cổng **8100**, nhưng một cổng chỉ đáng
mở khi có ai gọi vào — mà Decision Record *"`document` đẩy job cho BE qua arq"* đã **loại** mũi
HTTP giữa hai service, vì nó cần xác thực service-to-service chưa tồn tại, và `grep -rn
'httpx|requests|aiohttp' services/` vẫn rỗng. Một cổng không ai gọi là một bề mặt tấn công và
một process nữa phải trông. Quy ước cổng vẫn giữ nguyên trong `architecture.md` cho service sau,
và **8100 ghi là đã dành** để không ai cấp lại nó.

### Decision: queue đặt tên theo **bên tiêu thụ** — `aiafa:document` và `aiafa:be`

**options considered:**

- (a) Đặt theo công việc: `aiafa:probe` và `aiafa:ingest`.
- (b) **Đặt theo bên tiêu thụ: `aiafa:document` và `aiafa:be`.**

**selected option:** (b).

**reason:** (a) là **đúng cái cách `aiafa:grading` mục ruỗng**. Tên ấy đặt theo công việc, rồi
`worker.py:88-104` chất lên nó bảy task — soạn câu, sinh lại, giải thích, đặt tên đoạn, chat
giáo viên, báo cáo, chấm bài — và sáu cái không phải chấm bài. Tên nói về *việc* thì hết đúng
ngay lần thêm việc thứ hai; tên nói về *ai tiêu thụ* thì không bao giờ hết đúng, vì một queue
chỉ có một worker đứng sau. Và queue `aiafa:be` **chắc chắn** sẽ nhận việc thứ hai: plan 3 đẩy
chunk về cùng đường ấy.

### Decision: BE có process thứ hai, không nhúng worker vào uvicorn

**options considered:**

- (a) Chạy một worker arq như một `asyncio.Task` trong `lifespan` của BE.
- (b) **`be/worker.py` riêng, chạy bằng `.\dev.ps1 be-worker`.**

**selected option:** (b).

**reason:** (a) nghe rẻ hơn — không process nào phải khởi thêm — nhưng nó buộc đường ingest vào
vòng đời của API, và `dev.ps1 be` chạy uvicorn với `--reload`: mỗi lần sửa một file Python là
một lần worker bị cắt ngang giữa job. Nó cũng làm `--workers N` ngày sau thành N worker cùng
tiêu thụ một queue mà không ai chủ ý. (b) tốn một cửa sổ terminal nữa ở local — **năm process**
thay vì bốn, và đó là cái giá thật, nói ra ở `local-development.md` — đổi lại ingest sống và
chết độc lập với API, đúng hình dạng mà `services/agent` đã chạy cả đời.

### Decision: "đọc được chữ" = **≥10% số trang có ≥100 ký tự**

**options considered:**

- (a) Toàn tài liệu có ít nhất một ký tự.
- (b) Trung bình ký tự mỗi trang ≥ một ngưỡng.
- (c) **≥10% số trang có ≥100 ký tự.**

**selected option:** (c), và `.txt`/`.md` thì là "có ký tự không-trắng".

**reason:** **đo ngày 08/10/2026**, bằng PyMuPDF 1.28.2, trên hai đầu của thang:

| | trang | tổng ký tự | trang ≥100 ký tự | tỉ lệ |
|---|---|---|---|---|
| `docs/report/report.pdf` (PDF chữ thật, tiếng Việt) | 29 | 32 455 | 27 | **93%** |
| PDF scan (render trang trên thành ảnh rồi nhúng lại) | 1 | **0** | 0 | **0%** |

(a) vỡ vì một bản scan có một trang bìa chữ, hoặc một watermark, là có "ít nhất một ký tự".
(b) vỡ ở ca cụ thể và rất thật: một cuốn 400 trang scan kèm **một** trang mục lục 50 000 ký tự
cho trung bình 125 ký tự/trang và **qua cổng**, trong khi 399 trang kia không đọc được chữ nào.
(c) không vỡ theo hình dạng ấy, vì nó đếm **trang**, không cộng ký tự.

Phân bố đo được trên `report.pdf` nói vì sao ngưỡng mỗi trang là 100 chứ không phải 1: trang
mỏng nhất có **39** ký tự (một trang bìa), nên một luật *"mọi trang phải có chữ"* sẽ từ chối một
tài liệu đọc được hoàn toàn. Khoảng cách 93% ↔ 0% rộng gấp chín lần ngưỡng, nên con số 10% không
phải một chỗ cân bằng mong manh.

**Vẫn phải nói ra cái chưa đo:** chưa ai cân một bản SGK scan **có lớp OCR mỏng**. Đó là ca duy
nhất nằm giữa hai cột trên, và nếu con số phải sửa thì nó sửa vì ca ấy. Hai hằng số nằm cạnh
nhau trong một module, kèm bảng đo này trong docstring.

### Decision: *xử lý hỏng* vì job chết được **suy ra lúc đọc**, không phải một sweeper

**options considered:**

- (a) Một process quét định kỳ, `UPDATE` những hàng đứng quá lâu.
- (b) **Suy ra lúc đọc:** `state == processing` mà `uploaded_at` cũ hơn `DOCUMENT_STALE_AFTER_SECONDS` thì trả về `failed`.
- (c) Chỉ dựa vào `job_timeout` của arq.

**selected option:** (b), cộng (c) cho ca thường.

**reason:** ADR-27 nói thẳng rằng *"một chip đứng mãi ở đang xử lý vì job đã chết cũng là một
chip nói dối, nên ca ấy phải có tên riêng"*. (c) một mình **không** đủ: `job_timeout` bắt được
một handler treo, nhưng một process bị giết — Ctrl+C trên Windows thì arq còn không tắt êm được,
đúng như `agent/AGENTS.md` ghi — thì **không ai** còn sống để ghi `failed`. (a) trả lời được,
nhưng nó là process **thứ ba** của BE, và một sweeper cũng chết được y như cái nó đi canh.

(b) không chết được, vì nó không chạy: nó là một phép so lúc đọc. Và repo này đã có **đúng hình
dạng ấy** cho một luật khác — `architecture.md`: *"Ngưỡng được áp lúc đọc kết quả chứ không lưu
kèm"*. Hệ quả hợp ý: một job về muộn vẫn thắng, vì lần đọc sau thấy `ready` thật trong cột.

Ngưỡng **300 giây**, và nó rộng có lý do đo được: quét 29 trang mất **31 ms**, ngoại suy 400
trang ≈ **0,4 giây**, nên năm phút không phải để chờ việc — nó để phủ một worker khởi động nguội
và một hàng job đang dồn.

### Decision: `page_count` nullable, và dòng meta của chip in **kích thước · số trang**

**options considered:** (a) `page_count = 0` cho `.txt`/`.md` · (b) **nullable, để NULL**.

**selected option:** (b). Dòng meta: `2,4 MB · 184 trang`.

**reason, phần cột:** `.txt` và `.md` **không có trang**. Một số `0` trong cột là một con số
hợp lệ về kiểu và sai về nghĩa, và `teacher_documents.py` đã ghi sẵn luật cho đúng ca này: *"một
con số trang bịa ra thì tệ hơn hẳn việc không có nó: giáo viên sẽ tin."* NULL thì không nói gì,
và không nói gì là sự thật ở đây. Cùng lý do ấy áp cho một tài liệu **chưa probe xong**: nó mang
NULL cho tới khi có câu trả lời thật, nên đường API không bao giờ chở một con số chưa đo.

**reason, phần dòng meta** — plan 1 vừa chốt là **chỉ kích thước**, và lý do của nó là *"con số
duy nhất biết được mà không cần parse"*. Lý do ấy tan ở đúng plan này. Nay chọn **in cả hai**,
vì ba điều:

1. **Số trang là thứ giáo viên nhận ra cuốn sách bằng nó; kích thước thì không.** `2,4 MB` không
   nói được đây là cả bộ SGK hay một chương chụp lại. `184 trang` nói được ngay. Thiết kế gốc in
   số trang là vì vậy, và plan 1 bỏ nó đi **không phải vì nó sai** mà vì chưa đo được.
2. **Kích thước ở lại, không bị thay.** Nó là con số duy nhất đúng cho **mọi** loại tệp, kể cả
   `.txt`/`.md` vốn không có trang. Thay thế thì dòng meta của một tệp văn bản trống trơn.
3. **ADR-27 đã gọi đây là hệ quả của chính đợt này:** *"số trang và cờ đọc được chữ trở thành
   đo được — hai thứ mà `teacher_documents.py` cố ý bỏ đi."*

Ba hình dạng của dòng meta, và không có hình thứ tư:

| Tài liệu | Dòng meta |
|---|---|
| PDF đã probe xong | `2,4 MB · 184 trang` |
| `.txt`/`.md`, hoặc PDF chưa probe / probe hỏng | `2,4 MB` |

Dấu phân cách là ` · `, đúng cái `ActionCard` đang dùng; số dùng `weight()` đã có trong
`Rail.tsx`, không viết hàm định dạng thứ hai.

**Quyết định này ghi ở 2a nhưng thi hành ở 2b.** Nó ở đây vì nó **là lý do** `page_count` phải
ra tới API trong plan này; không có nó thì cột ấy chỉ cần nằm trong database.

### Decision: `pymupdf` chỉ được import trong một module, như `minio`

**options considered:** (a) import ở đâu cần · (b) **gom vào `document/probe.py`, kèm một check.**

**selected option:** (b).

**reason:** cùng hình dạng, cùng lý do như seam `minio` của plan 1, và ở đây còn gắt hơn một
chút. PyMuPDF là **sync và CPU-bound**, còn arq chạy tới `max_jobs` job đồng thời trên một event
loop — nên một lời gọi quên `asyncio.to_thread` chặn **cả chín job kia**, và nó không ném gì cả.
Luật *"nhớ bọc to_thread"* không grep được; luật *"nhớ đừng import"* thì grep được. Check mới
dùng lại đúng khuôn `check_only_the_storage_module_talks_to_minio`, và hai luật về sau về chung
một hàm.

**Một cái bẫy đã gặp lúc đo:** `import fitz` **đã deprecated** và in cảnh báo. Dùng
`import pymupdf`.

### Decision: nâng cap `AGENTS.md` 181 → 182

**options considered:** (a) nâng lên 190 cho rộng · (b) **182** · (c) cắt một dòng khác để đổi.

**selected option:** (b).

**reason:** cap là **phép đo gián tiếp duy nhất** cho luật *"đừng kể lại file gốc"*, đúng như
docstring của `check_contract_files_stay_short` nói: *"một file đã sát cap thì không còn chỗ để
chép một luật từ AGENTS.md sang."* Nâng tám dòng cho một dòng cần dùng là tự cho mình bảy dòng
chưa có lý do — và cái cap ấy chỉ còn nghĩa khi mỗi dòng mới phải trả giá bằng một lần sửa hằng
số kèm một decision record. (c) nghe gọn nhưng là xoá một luật đang canh để lấy chỗ cho một luật
mới, tức trả bằng tiền của người khác.

Plan này tiêu **đúng một** dòng: hàng `services/document` trong bảng ownership. Luật *"AGENT
holds no database credentials"* nới thành *"AGENT and `document`"* — cùng một dòng. Seam
`pymupdf` về `services/document/AGENTS.md`, giữ đối xứng với seam `minio` vốn ở
`services/be/AGENTS.md`, không ở gốc.

## Files

| File | Việc |
| --- | --- |
| `services/document/pyproject.toml` *(mới)* | `aiafa-document`, deps `aiafa-contracts` + `arq` + `pymupdf` + `minio` + `pydantic-settings`; extras `test` |
| `services/document/src/document/__init__.py` *(mới)* | rỗng, theo khuôn `agent` |
| `services/document/src/document/config.py` *(mới)* | khuôn `agent/config.py`: `_ENV_FILE` neo gốc repo, `lru_cache`. **Không** trường database nào |
| `services/document/src/document/storage.py` *(mới)* | đọc object từ MinIO. Chỉ `get`, không `put` — nó không bao giờ ghi |
| `services/document/src/document/probe.py` *(mới)* | module **duy nhất** import `pymupdf`. Hai hằng số ngưỡng + bảng đo trong docstring |
| `services/document/src/document/worker.py` *(mới)* | `WorkerSettings`, `queue_name` từ settings, `on_startup` nói ra tên queue (khuôn `agent/worker.py:56-78`) |
| `services/document/src/document/handlers.py` *(mới)* | `probe_document`: đọc byte → `asyncio.to_thread(probe)` → enqueue `DocumentProbed` về `aiafa:be` |
| `services/document/AGENTS.md` *(mới)* | constraint only, ≤25 dòng: không credential database, `pymupdf` một module, không `import be`/`import agent` |
| `services/document/tests/` *(mới)* | test `probe.py` trên hai PDF **sinh lúc chạy** |
| `packages/contracts/src/contracts/documents.py` *(mới)* | `PROBE_DOCUMENT_TASK`, `DOCUMENT_PROBED_TASK`, `DocumentProbeRequested`, `DocumentProbed`, `DocumentState` |
| `packages/contracts/src/contracts/__init__.py` | re-export + `__all__` |
| `services/be/src/be/worker.py` *(mới)* | process thứ hai của BE. `on_startup`: `create_engine` + `check_schema` + `bind_sessions`. **Không** `prepare_schema` — schema là việc của API |
| `services/be/src/be/ingest.py` *(mới)* | handler ghi kết quả probe vào `documents`. Hàng không tồn tại thì log rồi bỏ |
| `services/be/src/be/queue.py` | `enqueue_probe` |
| `services/be/src/be/models.py` | `Document` + `state`, `page_count` (nullable), `fault` |
| `services/be/src/be/teacher_documents.py` | enqueue sau commit; enqueue hỏng → `UPDATE` sang `failed`; `DocumentRead` + `state` + `page_count` + `fault`; suy ra `failed` lúc đọc |
| `services/be/src/be/config.py` | `document_queue_name`, `be_queue_name`, `document_stale_after_seconds` |
| `services/be/tests/test_documents.py` | viết lại `test_nothing_claims_a_page_count`; thêm ca enqueue hỏng và ca suy-ra-failed |
| `services/be/tests/test_ingest.py` *(mới)* | handler ghi đúng ba cột, và bỏ qua một `document_id` lạ |
| `.env.example` | `DOCUMENT_QUEUE_NAME`, `BE_QUEUE_NAME`, `DOCUMENT_STALE_AFTER_SECONDS` |
| `pyproject.toml` | `ruff.src`, `pytest.testpaths`, `importlinter.root_packages` + hai contract nới sang `document` |
| `dev.ps1` | `install document`; task `document` và `be-worker`; `ValidateSet`; khối help |
| `tools/check_contract.py` | `check_env_example_has_no_orphans` đọc thêm `document.config`; `check_agent_holds_no_database_credentials` quét thêm `services/document`; seam `minio` nới sang `document/storage.py`; seam `pymupdf` mới; `AGENTS_MD_MAX_LINES` → 182; `CHILD_AGENTS_FILES` + một |
| `AGENTS.md` | hàng `services/document`; nới dòng invariant credential |
| `CLAUDE.md` | *"Four exist"* → **năm** — nếu không thì hai file nói ngược nhau |
| `docs/overview/architecture.md` | sơ đồ đường giao tiếp; danh sách service; mục *Ranh giới dữ liệu* (document đọc MinIO, không có credential database); ghi 8100 là **đã dành** |
| `docs/overview/data-model.md` | hàng `documents` + ba cột, và vì sao `page_count` nullable |
| `docs/local-development.md` | **năm process**; hai task mới; chẩn đoán "chip đứng ở đang xử lý" |
| `docs/kich-ban-thu-tay-giao-vien.md` | ca mới: PDF scan, và `page_count` của PDF chữ |
| `docs/plans/active/2026-10-07-doc-pdf-vao-ngu-canh-plan.md` | **năm plan → sáu**; bảng cổng |
| `docs/diagrams/system-architecture.drawio` + `docs/report/figures/` | service thứ tư, hai queue, re-export, `sources.json` |
| `docs/plans/active/2026-10-08-document-bytes-to-minio-plan.md` | → `docs/plans/completed/` |

## Ordered Tasks

- [x] **0. Đóng plan 1.** Chuyển file plan 1 sang `docs/plans/completed/`. Một commit riêng,
      exempt theo `AGENTS.md`.
- [x] **1. `contracts` trước, vì cả hai bên nói nó.** `documents.py` + re-export. `DocumentState`
      là `StrEnum` bốn giá trị — `processing`, `ready`, `no_text_layer`, `failed` — đặt cạnh
      `ReviewReason` về mặt khuôn mẫu. Test contracts: bốn giá trị, và round-trip
      `model_dump(mode="json")`.
- [x] **2. Bộ xương service, chưa có logic.** Thư mục, `pyproject.toml`, `config.py`,
      `AGENTS.md`, `__init__.py`. Rồi **ngay lập tức** nối tooling: `root pyproject` (ruff src,
      testpaths, importlinter), `dev.ps1 install document`, `tools/check_contract.py`
      (`CHILD_AGENTS_FILES`, cap 182, hai check nới). `.\dev.ps1 install` rồi `.\dev.ps1 check`.
      Task này xong khi `check` xanh **với một service rỗng** — nếu nó không xanh ở đây thì nó
      sẽ không xanh ở bất cứ task nào sau.
- [x] **3. `probe.py` một mình, test một mình.** Hàm thuần: `bytes` + `filename` → `(state,
      page_count, fault)`. Hai PDF fixture **sinh lúc chạy** bằng chính `pymupdf`, không file
      nhị phân nào vào git (xem *Validation*). Bảng đo vào docstring.
- [x] **4. `document/storage.py`,** chỉ `get`. Dùng lại đúng khuôn `be/storage.py` — `Protocol`,
      `run_in_threadpool`, một `StorageUnavailable` — nhưng **không** `bind`/`get` toàn cục: một
      worker arq dựng client một lần trong `on_startup` và cất vào `ctx`, nên seam kiểu `Depends`
      không có chỗ dùng.
- [x] **5. `document/handlers.py` + `worker.py`.** `probe_document` đọc byte, `asyncio.to_thread`
      sang `probe`, rồi `enqueue_job(DOCUMENT_PROBED_TASK, ..., _queue_name=be_queue_name)`.
      Mọi exception bắt lại thành `state=failed` kèm `fault` — một job chết im lặng là chip nói
      dối.
- [x] **6. Ba cột mới.** `models.Document`: `state` (`String(16)`, default `processing`),
      `page_count` (`Integer`, **nullable**), `fault` (`String(120)`, default `""`). Docstring
      viết lại: đoạn *"Không có `page_count`"* nay sai. `.\dev.ps1 db-reset` (BE tắt).
- [x] **7. BE tiêu thụ: `be/ingest.py` + `be/worker.py`.** `on_startup` dựng engine,
      `check_schema`, `bind_sessions`. Handler `UPDATE` ba cột theo `document_id`.
- [x] **8. BE đẩy: `enqueue_probe` + endpoint.** Sau `session.commit()`. `queue_pool is None`
      hoặc enqueue ném → `UPDATE` sang `failed`, `fault="chưa giao được việc xử lý"`. **Không**
      rollback hàng và **không** xoá object: tệp đã cất rồi, và một lần thử lại sau này cần nó.
- [x] **9. `DocumentRead` + suy ra `failed`.** Ba field mới. Phép suy đặt trong `_as_read`,
      cạnh chỗ duy nhất dựng bản đọc.
- [x] **10. Test.** Hai file, danh sách ở *Validation*.
- [x] **11. Tài liệu.** Tám file ở bảng trên, gồm `CLAUDE.md` và file đợt việc.
- [x] **12. Sơ đồ, làm cuối.** `.drawio`, re-export, `sources.json`.

## Validation Checks

**Cổng của plan này — đo trên hệ thật, không chỉ trên test.** Năm process lên
(`infra-up`, `be`, `be-worker`, `document`, không cần `fe`), rồi:

1. `curl -F` một PDF chữ lên → đọc lại danh sách → `state: "ready"`, `page_count` **khớp số
   trang thật** của tệp ấy.
2. `curl -F` một PDF scan lên → `state: "no_text_layer"`, `fault` là một câu tiếng Việt.
3. Dừng worker `document`, tải một tệp lên, chờ qua `DOCUMENT_STALE_AFTER_SECONDS` (hạ tạm
   xuống vài giây) → `state: "failed"`, **và cột trong database vẫn là `processing`** — đó là
   bằng chứng phép suy chạy lúc đọc chứ không ghi gì.

**Fixture sinh lúc chạy, không commit nhị phân.** Đo được ngày 08/10/2026 rằng `pymupdf` tự
dựng được cả hai đầu của thang: một trang `insert_text` → **16 ký tự**; render chính trang ấy
thành pixmap rồi `insert_image` vào một PDF mới → **0 ký tự**. Nên test không cần một bản scan
thật trong git, và nó không phụ thuộc vào một tệp ai đó có thể thay.

Test phải có:

- **`probe` trả `ready` + số trang đúng** cho PDF chữ sinh ra.
- **`probe` trả `no_text_layer`** cho PDF scan sinh ra.
- **PDF hỏng** (byte rác mang đuôi `.pdf`) → `failed`, không ném ra ngoài.
- **`.txt` có chữ → `ready`, `page_count is None`**; `.txt` chỉ khoảng trắng → `no_text_layer`.
- **Ca nghịch của luật ngưỡng:** một PDF 20 trang, **một** trang dày chữ, 19 trang trắng →
  `no_text_layer`. Đây là ca mà luật "trung bình ký tự mỗi trang" sẽ cho qua.
- **Handler ingest ghi đúng ba cột**, và **bỏ qua** một `document_id` không có hàng nào.
- **Enqueue hỏng thì hàng mang `failed`**, không mang `processing`.
- **Hàng `processing` quá cũ đọc ra `failed`**, và hàng `processing` còn mới thì không.
- **`DocumentRead` đúng tám khoá** — thay `test_nothing_claims_a_page_count`. Tám chứ không
  bảy như bản duyệt của plan này nói: `fault` phải ra tới API, vì ADR-27 đòi *lý do nói bằng lời
  giáo viên hiểu* và hai lý do khác nhau cùng dẫn tới *không đọc được chữ* — một bản scan, và một
  PDF không có trang nào. Chính mục Context của plan này đã hứa đúng điều đó (*trả
  `state: "no_text_layer"` kèm một lý do*), nên con số bảy là chỗ plan tự nói ngược với mình. Luật đổi hình, nên
  test đổi tên: từ *"không claim gì"* sang *"chỉ claim thứ đã đo"*. Nó vẫn phải khẳng định một
  tài liệu **chưa probe xong** trả `page_count: null`.

**Đột biến** (mỗi luật mới đỏ đúng test của nó):

- Hạ ngưỡng 10% về 0% → chỉ ca `no_text_layer` đỏ.
- Hạ ngưỡng 100 ký tự/trang về 1 → chỉ ca 19-trang-trắng đỏ.
- Bỏ `asyncio.to_thread` quanh `probe` → seam check đỏ **nếu** đồng thời dời `import pymupdf`;
  một mình nó thì không có lưới nào, và điều đó phải nói ra chứ không giả vờ có.
- `import pymupdf` trong `handlers.py` → seam check đỏ.
- Đổi `page_count` thành `0` cho `.txt` → ca `page_count is None` đỏ.
- `import be` trong `document/worker.py` → `lint-imports` đỏ (**boundary probe**, bắt buộc vì
  cấu hình import-linter đổi).

**Cổng chung:** `.\dev.ps1 check` · `test` · `typecheck`. `check` vẫn **17/17**, không phải 18:
hai luật SDK sync về chung một hàm, đúng như Decision Record về seam `pymupdf` đã nói. Một con số
tăng lên ở đây sẽ là dấu hiệu luật thứ hai được viết thành một hàm thứ hai.

## Cạm bẫy đã biết

- **`check_env_example_has_no_orphans` chỉ import `be.config` và `agent.config`.** Khai
  `DOCUMENT_QUEUE_NAME` mà không sửa hàm ấy là `check` đỏ ngay — nhưng chiều ngược lại
  **không** có lưới: một trường trong `document/config.py` mà `.env.example` không khai thì
  không gì kêu. Đó là chỗ drift, nên task 2 gom cả hai lại.
- **`DB_CREDENTIAL_PATTERN` khớp case-insensitive trên `PASSWORD|POSTGRES|MONGO|DATABASE_URL|
  DSN|psycopg|sqlalchemy|motor|pymongo`**, và nó **chỉ bỏ qua dòng bắt đầu bằng `#`** — docstring
  thì không được bỏ qua. Nên `document/config.py` không được viết chữ `DATABASE_URL` ngay cả để
  giải thích rằng nó không có. Diễn đạt bằng tiếng Việt, như `agent/config.py` đang làm.
- **`import fitz` đã deprecated** và in cảnh báo ra stderr. Dùng `import pymupdf`.
- **arq chạy nhiều job đồng thời** (`max_jobs` mặc định 10). `probe` là sync và CPU-bound, nên
  thiếu `asyncio.to_thread` là một job chặn chín job kia — và không có exception nào.
- **`be/worker.py` không được gọi `prepare_schema`.** Hai process cùng `create_all` thì chạy
  được nhưng sai sở hữu: API dựng schema, worker chỉ được **kiểm**. Thiếu `check_schema` thì
  worker chạy êm trên schema lệch rồi hỏng ở lần `UPDATE` đầu.
- **`lint-imports` có hai cách chết im lặng**, và cấu hình nó đổi ở plan này, nên **boundary
  probe là bắt buộc**, không phải tuỳ chọn (`AGENTS.md`, mục *Validation Before Completion*).
- **`check_named_dev_tasks_exist`** đọc `ValidateSet` của `dev.ps1` và so với tên task mà
  `AGENTS.md` nêu. Thêm task thì an toàn; nhưng khối `help` và `ValidateSet` là **hai** chỗ phải
  sửa, và không lưới nào canh khối `help`.
- **`check_every_figure_matches_the_diagram_it_came_from` so sha256** của `.drawio` với
  `sources.json`. Đổi sơ đồ mà không re-export là `check` đỏ. `sources.json` **là CRLF** — ghi
  LF lên nó biến một dòng sửa thành một diff 26 dòng.
- **Trích xuất tiếng Việt mất dấu cách** — `"Nghiệp vụcủa hệthống"`, 164 chỗ / 32 484 ký tự, cả
  ba đường trích xuất cùng con số. **Không thuộc plan này**: cổng text layer chỉ đếm ký tự, mà
  thiếu dấu cách thì ký tự vẫn đủ. Nó là việc của plan 3, và ghi lại đây để đừng ai "sửa" nó
  trong `probe.py`.
- **`.\dev.ps1 report` không phải dựng lại.** `system-architecture.pdf` không chương nào của báo
  cáo nhúng; nó tồn tại chỉ để thoả check hình-khớp-sơ-đồ.

## Status

**Xong cả mười ba việc, chưa commit.** Cổng: `check` **17/17** · `pytest` **452** ·
`vitest` **178** · `tsc` sạch.

### Đo trên hệ thật, năm process cùng chạy

`infra-up` · `be` · `be-worker` · `document`, rồi tải ba tệp lên qua HTTP. Ngay sau `POST` cả ba
mang `state=processing` và `page_count=null`. **Một phẩy hai giây** sau:

```text
sach-co-chu.pdf     ready          pages=29   (report.pdf thật — đếm tay cũng 29)
sach-chup-lai.pdf   no_text_layer  pages=2    "Tệp này là ảnh scan, chưa đọc được chữ."
ghi-chu.txt         ready          pages=None
```

**Trạng thái thứ tư, và bằng chứng nó không ghi gì.** Tắt worker `document`, tải một tệp lên,
đẩy `uploaded_at` lui 400 giây:

```text
API đọc ra    : state=failed   "Xử lý tài liệu này đã dừng giữa đường. Thử tải lại."
cột trong db  : processing
```

Rồi **bật `document` lại**: job vẫn nằm trong queue, nó chạy, và cột đổi sang `failed` kèm lý do
**thật** — *"Không mở được tệp PDF này."* — thay cho câu suy ra. Đó là phép chứng minh cho câu
*"một job về muộn vẫn thắng"* trong Decision Record, và nó là thứ một test không nói được.

### Năm đột biến, và một lỗ chúng tìm ra

Bốn cái đỏ ngay đúng test của nó: hạ tỉ lệ 10% về 0%; `page_count = 0` cho tệp văn bản thuần;
`import pymupdf` ngoài `probe.py`; `import be` trong `document/worker.py` (**boundary probe**,
bắt buộc vì cấu hình import-linter đổi — `lint-imports` báo `BROKEN` rồi hoàn tác).

Cái thứ năm **xanh**, và đó là một lỗ thật: hạ `_MIN_CHARS_PER_PAGE` từ 100 về 1 chạy qua toàn
bộ suite mà không một test nào đỏ. Lý do nằm ở chính fixture: mọi trang "trắng" trong chúng mang
**0** ký tự, nên không ngưỡng nào giữa 1 và 100 phân biệt được gì. Vá bằng
`test_a_scan_with_only_page_numbers_on_every_page_is_not_readable` — hai mươi trang, mỗi trang
khoảng hai mươi ký tự. Nó không phải một ca bày ra cho test: đó là một bản SGK chụp lại có lớp
OCR mỏng, in được số trang mà không đọc được một đoạn nào. Chạy lại: đỏ.

### Bốn chỗ khác plan, và vì sao

- **`DocumentRead` tám khoá, không bảy.** `fault` phải ra tới API: ADR-27 đòi *lý do nói bằng
  lời giáo viên hiểu*, và hai lý do khác nhau cùng dẫn tới *không đọc được chữ* — một bản scan,
  và một PDF không có trang nào. Mục Context của chính plan này đã hứa đúng điều đó, nên con số
  bảy là chỗ plan tự nói ngược với mình.
- **`check` vẫn 17, không lên 18.** Hai luật SDK sync về chung một hàm, đúng như Decision Record
  về seam `pymupdf` nói. Con số 18 trong bản duyệt là một lỗi số học của chính plan.
- **Check seam không quét `tests/`.** `test_probe.py` **phải** import `pymupdf` để dựng cả PDF
  chữ lẫn PDF scan lúc chạy. Không phải một lỗ: luật nói về việc chặn một event loop, mà một
  test thì sync và không có loop nào để chặn.
- **Sơ đồ xếp hai hàng, không một hàng.** Bản một hàng đã render ra rồi nhìn: bốn hộp rộng 240
  trong bề ngang 1280 chỉ còn khe 60, nên nhãn cạnh `be → redis` đè thẳng lên chữ của hộp
  `document`, và bốn nhãn queue chen nhau trong cùng một dải. Hai hàng thì mọi thứ dưới
  host-boundary phải tụt xuống 160 — đắt hơn, nhưng đọc được. Xem hình ba lần trước khi chốt.

### Còn nợ, ghi để không mất

- **Nhãn `HTTP /api, qua Vite proxy...` trên sơ đồ đè lên cả hai hộp `fe` và `be`.** Lỗi có sẵn
  từ trước plan này, không phải do nó. Không sửa ở đây vì `AGENTS.md` cấm refactor kèm.
- **Chiều "`config.py` đọc một biến mà `.env.example` không khai" vẫn không có lưới.**
  `dev_identity_header` đã sống như vậy từ lâu, và nay `document/config.py` cũng có cùng rủi ro.
- **`aiafa:grading` vẫn mang cái tên sai** — nó chở bảy task, sáu cái không phải chấm bài. Đổi
  tên là một refactor riêng, không thuộc plan này.
- **Một job `probe` bị arq thử lại không có trần riêng** ngoài `max_tries` mặc định của arq.
  Chưa đo xem con số ấy có hợp với `DOCUMENT_STALE_AFTER_SECONDS` không.
- **Plan 2b chưa có file**: chip bốn trạng thái, Figma trước rồi FE.
