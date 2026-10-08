# Plan — Byte tài liệu rời Postgres, vào MinIO

Plan **1 trong 5** của đợt [đọc PDF vào ngữ cảnh ra đề](2026-10-07-doc-pdf-vao-ngu-canh-plan.md).
Quyết định dùng chung cho cả đợt nằm ở file ấy; đây chỉ giữ phần của riêng plan này.

## Goal

Chuyển byte tài liệu giáo viên từ cột `Document.content` (`LargeBinary`, Postgres) sang
**MinIO**, để `services/document` ở plan 2 đọc được tệp mà không cần credential database.

`models.py:696-697` đã hẹn trước đúng lần chuyển này từ ngày nó được viết: *"Khi nội dung thật
sự đi vào prompt của AGENT thì cột này đổi thành một khoá tới nơi lưu thật — một cột, một lần
chuyển."*

Mã **C9**. **Không một lời gọi model nào** — thuần là chuyển nơi lưu byte, đo được bằng test
thường. Đây là nửa đợt việc chứa mọi giả định nguy hiểm; nếu có gì sụp, nó phải sụp ở đây.

**Kết quả mong đợi:** giáo viên tải lên và dùng tài liệu y như cũ — nhưng byte nằm trong MinIO
và `documents` chỉ còn giữ một khoá.

## Scope

**Trong:** MinIO vào hạ tầng; byte chuyển nơi lưu; giới hạn 100 MB; thu hẹp đuôi file; tài liệu
và sơ đồ đi kèm.

**Ngoài:** PyMuPDF, cổng text layer, `page_count`, cột trạng thái, chip bốn trạng thái,
`services/document`, Mongo, Jev, skill. Plan 2 trở đi.

**FE chạm đúng một dòng**, và nó không có mặt nào trên Figma. `Chat.tsx:586` đang khai
`accept=".pdf,.docx,.doc,.txt,.md"` trên một `<input type="file">` **ẩn**; thu hẹp `_ALLOWED`
mà để nguyên dòng ấy là mời giáo viên chọn một tệp rồi ném cho họ một 400. Hộp chọn tệp là của
hệ điều hành, không phải của ta, nên luật *Figma trước* không có gì để áp.

`DocumentRead` giữ **nguyên năm field**, và repo đã có lưới canh đúng điều đó
(`test_documents.py:164` `test_nothing_claims_a_page_count`). `storage_key` là **cột bảng, không
phải field API**. Phần còn lại của FE không đổi một dòng: `Rail.tsx:263-276` chỉ đọc bốn trong
năm field ấy.

## Decision Records

### Decision: client `minio` gọi qua threadpool, không `boto3`, không `aioboto3`

**options considered:**

- (a) `boto3` — chuẩn S3, nhưng kéo `botocore` với thư mục `data/` mô tả ~400 service AWS.
- (b) **`minio`** — SDK chính chủ, pure-python, phụ thuộc `certifi` / `urllib3` / `argon2-cffi`
      / `pycryptodome`.
- (c) `aioboto3` / `aiobotocore` — async thật.

**selected option:** (b), bọc trong `starlette.concurrency.run_in_threadpool`.

**reason:** dự án dùng đúng ba lời gọi S3, nên (a) trả hàng chục MB cho một thứ không dùng. (c)
bị loại vì `aiobotocore` ghim `botocore==x.y.z` **chính xác**, và cái nó mua lại — bỏ được
threadpool — chỉ đáng trên đường nóng, mà đây là một lời gọi chặn mỗi lần giáo viên tải lên một
cuốn sách.

Và API của (b) khớp đúng hình dạng ta cần: `put_object(bucket, key, data, length, content_type)`
nhận một file-like **cộng `length` tường minh**, tức chính là thứ `seek/tell` sinh ra. `boto3`
muốn `upload_fileobj` tự chia multipart và **không nhận `length`**, nên con số vừa đo không còn
đường đi vào lời gọi.

Chuyện sync-trong-async **không phải lý do chọn SDK** — cả hai chặn như nhau. Bảo hiểm nằm ở
seam: `be/storage.py` là module duy nhất biết `minio` tồn tại, mọi method của nó là `async def`
bọc một `run_in_threadpool`. Ngày đổi sang S3 thật, phạm vi sửa là một file.

### Decision: seam sao đúng khuôn `be/db.py`

**options considered:**

- (a) Một client toàn cục tạo lúc import.
- (b) **`bind_store()` + `get_store()`** — đúng hình dạng `bind_sessions()` / `get_session()`
      của `be/db.py:145-200`.
- (c) Truyền client qua `app.state` rồi đọc từ `Request`.

**selected option:** (b).

**reason:** test BE dựng một `FastAPI()` rỗng chỉ gắn `document_router` trên sqlite in-memory
(`test_documents.py:29-49`), **không** qua `be.main` — nên không có MinIO nào sống trong test.
(a) không có chỗ nào thay được. (c) buộc mọi route phải cầm `Request`, mà `teacher_documents.py`
hiện không cầm. (b) để fixture gọi `bind_store(MemoryObjectStore())` y hệt cách nó đã gọi
`bind_sessions(engine)`, và teardown đặt lại `None` y hệt dòng `db_module._SESSION_MAKER = None`
đang có. Không một ý niệm mới nào cho người đọc sau.

`get_store()` là hàm **sync thường**, không phải async generator: `get_session` là generator vì
session sống theo request, còn object store sống theo process. FastAPI nhận cả hai dạng.

**`MemoryObjectStore` nằm trong `storage.py`, không trong `tests/`.** Một `Protocol` chỉ có một
implementor là một class trá hình. Tiền lệ: nhánh `else` sqlite trong `db.reset_schema` cũng chỉ
có test đi qua, và nó nằm trong `db.py`.

### Decision: `storage_key` là một cột, không phải thứ suy ra từ `id`

**options considered:**

- (a) Không thêm cột; dựng khoá từ `Document.id` mỗi lần cần.
- (b) **Một cột `storage_key`.**

**selected option:** (b).

**reason:** (a) rẻ hơn một cột nhưng **khoá sơ đồ đặt tên vào code vĩnh viễn** — đổi tiền tố là
làm mọi hàng cũ nói dối, và không có cách nào biết hàng nào theo sơ đồ nào. (b) thì đổi tiền tố
là một `UPDATE`. Và `models.py:697` nói thẳng *"một cột, một lần chuyển"* — cột ấy là cột này.

Hình dạng khoá: `documents/{teacher_id}/{document_id}{ext}`. Tiền tố theo giáo viên để console
MinIO đọc được, và để *"xoá hết của người này"* sau này là một lần xoá prefix. **Không nhét
`filename` vào khoá** — `"SGK Giải tích 12.pdf"` là Unicode, có khoảng trắng, và là chuỗi client
khai; `ext` thì lấy từ `_ALLOWED` nên đã qua kiểm.

### Decision: `content_type` đi vào MinIO suy ra từ đuôi, không lấy lời khai của client

**options considered:** (a) dùng `file.content_type` · (b) **suy từ đuôi file**.

**selected option:** (b).

**reason:** `content_type` cất vào cột DB là lời khai và vô hại ở đó. Nhưng cái gắn vào object
metadata là `Content-Type` mà MinIO **trả về** ở lần `GET` đầu tiên — tức một stored-XSS nằm
sẵn, chờ ngày có endpoint download. Đuôi file thì đã được `_ALLOWED` kiểm, nên nó là thứ duy
nhất ở đây không phải lời khai. Cùng một lập luận `teacher_documents.py:48-51` đã dùng để chọn
lọc theo đuôi thay vì theo content-type.

### Decision: ghi object trước, INSERT hàng sau — nhưng xoá thì ngược lại

**options considered:** (a) INSERT trước rồi ghi object · (b) **ghi object trước rồi INSERT**.

**selected option:** (b) trên đường ghi, và **hàng trước, object sau** trên đường xoá.

**reason:** hai kho không commit cùng nhau, nên phải chọn hình dạng hỏng nào rẻ hơn. (a) để lại
**một hàng trỏ vào hư không** — chip hiện trên rail, giáo viên tin là có. (b) để lại **một object
mồ côi** — rác, không ai thấy, dọn được.

Trên đường xoá, **cùng một ưu tiên ấy lật ngược thứ tự**: xoá hàng trước rồi mới xoá object, vì
hỏng giữa chừng thì còn lại rác chứ không phải một bảng `documents` trỏ vào bucket đã sạch. Đây
là chỗ dễ làm sai nhất của plan này.

Và vì ca phổ biến (INSERT đỏ vì `IntegrityError`) **không đáng phải trả giá**, đường ghi dọn rác
chủ động: `try` quanh `add`/`commit`, `except` thì `remove(key)` best-effort, **log khoá** rồi
ném lại. Rác còn lại chỉ là ca process bị giết — đúng đánh đổi đã chọn, và nó grep được.

## Files

| File | Việc |
| --- | --- |
| `docker-compose.infra.yml` | service `minio`, named volume `aiafa-miniodata`, cổng 9000/9001 |
| `.env.example` | năm biến `MINIO_*` sau `DATABASE_URL` (`:29`); sửa câu *"Redis là hạ tầng duy nhất"* (`:8`) vốn đã sai từ khi có Postgres |
| `services/be/src/be/config.py` | năm trường tương ứng |
| `services/be/src/be/storage.py` *(mới)* | `ObjectStore` Protocol, `MinioObjectStore`, `MemoryObjectStore`, `bind_store`/`get_store`/`create_store`, `document_key`, `content_type_for`, `StorageUnavailable` |
| `services/be/src/be/main.py` | lifespan: `create_store` → `ensure_ready` → `bind_store`, đặt sau `bind_sessions` (`:87`) |
| `services/be/src/be/models.py` | `content: LargeBinary` → `storage_key: String(255)`; gỡ import `LargeBinary` (`:32`); viết lại docstring `:693-697` |
| `services/be/src/be/teacher_documents.py` | ghi qua store; `_MAX_BYTES` → 100 MB; `_ALLOWED` → `.pdf .txt .md`; `detail` (`:148`) bỏ chữ *Word*; sửa comment `:34-37` và docstring module |
| `services/be/src/be/reset_db.py` | `ensure_ready` + `clear()` **sau** `reset_schema` |
| `services/be/pyproject.toml` | `minio` vào `dependencies`, **không** vào `[test]` — `be.main` và `test_documents.py` đều kéo `be.storage` vào |
| `services/be/AGENTS.md` | hai dòng invariant (file đang **20/25**, còn chỗ) |
| `services/fe/src/screens/teacher/Chat.tsx` | `accept` (`:586`) thu hẹp theo `_ALLOWED` |
| `services/be/tests/test_documents.py` | fixture `:29-49`; round-trip `:91-94`; cap `:151-161`; đuôi file `:134` |
| `tools/check_contract.py` | check mới: chỉ `storage.py` được import `minio` |
| `dev.ps1` | ba chuỗi *"redis and postgres"* (`:75`, `:79`, `:153`) |
| `docs/local-development.md` | `:15`, bảng cổng `:75-80`, xác minh `:87`, **`:205`**, chẩn đoán `:284-307`, `:260` |
| `docs/overview/architecture.md` | sơ đồ ASCII `:31-36`; *Ranh giới dữ liệu* `:90` |
| `docs/overview/data-model.md` | **thêm hàng `documents`** — `:25` tự ghi nhận đó là món nợ |
| `docs/kich-ban-thu-tay-giao-vien.md` | ca `G4` (`:469`) đang nói *"trên 10 MB"* |
| `docs/plans/backlog.md` | gạch món nợ *"byte nằm trong database"* nếu nó có dòng riêng |
| `docs/diagrams/system-architecture.drawio` + `docs/report/figures/` | thêm Postgres **và** MinIO, re-export, `sources.json` |

## Ordered Tasks

- [x] **1. Hạ tầng, chưa đụng code.** `minio` vào compose; bucket **`aiafa-documents`** (tên phải
      DNS-compatible: chữ thường, 3–63 ký tự, **không gạch dưới**, nếu không `make_bucket` ném).
      Named volume, không bind-mount — header của compose nói rõ vì sao. `.\dev.ps1 infra-up`,
      xác nhận container lên. Sửa ba chuỗi trong `dev.ps1`.
- [x] **2. Năm biến, hai nơi, cùng một lượt.** `.env.example` + `be/config.py`. Phải cùng lượt vì
      `check_env_example_has_no_orphans` đỏ nếu `.env.example` khai mà `Settings` không đọc.
      `MINIO_ENDPOINT=127.0.0.1:9000` (**không** `localhost`, `AGENTS.md:180`), `MINIO_ACCESS_KEY`,
      `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE=false`. SDK `minio` muốn `host:port`
      **không scheme** + `secure: bool`, và phép chuyển đổi chỉ sống trong `create_store`.
      **Khai ở BE, không khai ở AGENT** — AGENT không giữ credential của kho byte, cùng lý do nó
      không giữ credential DB.
- [x] **3. `be/storage.py` + hai implementor.** `MemoryObjectStore` trước, `MinioObjectStore` sau.
      Test riêng cho chính module này. Chưa ai gọi nó.
- [x] **4. `main.py` lifespan, và fixture test.** `ensure_ready()` **chết ngay** nếu không với
      tới — khác khối queue, vì queue chỉ đỡ pha 2 còn MinIO **là** nơi ở duy nhất của tài liệu.
      Chuỗi lỗi nói ra lệnh, hình dạng giống `SchemaDrifted`. Fixture: thêm
      `bind_store(MemoryObjectStore())` cạnh `bind_sessions`, và một dòng teardown
      `storage_module._STORE = None`. Giữ `yield http, maker` nguyên 2-tuple — tám chỗ
      `client, _ = stack` không phải sửa.
- [x] **5. Đổi cột.** `models.py`, rồi `.\dev.ps1 db-reset` (BE phải tắt).
- [x] **6. `teacher_documents.py` ghi qua store.** Thứ tự kiểm giữ nguyên: đuôi → rỗng → quá cỡ,
      **tất cả trước khi chạm MinIO**. `file.file.seek(0, 2)` / `tell()` / `seek(0)` gọi **thẳng,
      không qua threadpool** — nó là một `lseek` trên `SpooledTemporaryFile`, micro giây, và đẩy
      nó vào thread thì mất đúng cái thứ tự vừa nói. Rồi `await store.put(...)`, rồi INSERT, với
      `try/except` dọn rác. `put` hỏng → **503**, không 500.
- [x] **7. `reset_db.py`:** `ensure_ready()` rồi `clear()`, **sau** `reset_schema`.
      `Minio.remove_objects()` trả một **generator lazy** — không iterate thì **không gì bị xoá**.
- [x] **8. Test.** Hai chỗ vỡ + bốn ca mới (dưới).
- [x] **9. Check mới + `services/be/AGENTS.md`.** Grep `^\s*(from|import)\s+minio` trên
      `services/be/**/*.py`, loại trừ `storage.py`. Đây là thứ duy nhất giữ cho seam không rò.
- [x] **10. Tài liệu.** Bảy file ở bảng trên.
- [x] **11. Sơ đồ, làm cuối.** `system-architecture.drawio`, re-export, `sources.json`,
      `.\dev.ps1 report`.

## Validation Checks

**Cổng của plan này:** tải một PDF lên, đọc lại object từ MinIO, **khớp từng byte** — và
`documents` không còn cột nào giữ byte.

Test phải có:

- **Round-trip**, thay `test_documents.py:91-94`: `assert row.storage_key` rồi
  `assert await get_store().read(row.storage_key) == body`. Bản cũ chỉ so **độ dài**; bản này so
  **nội dung**, nên nó bắt được cả một `seek(0)` bị quên (object cụt đầu) lẫn một `length` sai
  (object cụt đuôi) — đúng hai lỗi duy nhất đường stream này sinh ra được.
- **Một tệp bị từ chối không bao giờ chạm storage**: sau một 400 và một 413,
  `get_store().objects == {}`. Đây là test **duy nhất** khẳng định được thứ tự ở task 6; đảo
  `put` lên trước lớp kiểm thì không có gì khác đỏ.
- **MinIO chết thì upload trả 503 và không để lại hàng nào** trong `documents`.
- **Quá cỡ bị từ chối và câu từ chối nói ra con số.** Đừng dựng 101 MB trong test — cộng cả bản
  encode multipart của httpx là vài trăm MB RAM. `monkeypatch.setattr(teacher_documents,
  "_MAX_BYTES", 1024 * 1024)` rồi gửi ~1,1 MB: vẫn đỏ đúng chỗ, **và** đi qua đúng nhánh
  `SpooledTemporaryFile` đã tràn ra đĩa — nhánh production thật sự chạy.
- **`.docx` và `.doc` nay bị từ chối 400** — hai ca mới trong parametrize ở `:134`. Lưu ý test
  hiện chỉ assert `"PDF" in detail`, nên nó **vẫn xanh** dù `detail` còn chữ *Word*; phải sửa
  `detail` bằng mắt chứ đừng trông vào lưới.
- `test_nothing_claims_a_page_count` (`:164`) **phải vẫn xanh không sửa một chữ** — đó là bằng
  chứng `DocumentRead` không đổi.

**Đột biến** (mỗi luật mới đỏ **đúng** test của nó):

- `_MAX_BYTES` về 10 MB → chỉ ca quá cỡ đỏ.
- Bỏ `.docx` khỏi danh sách bị từ chối → chỉ ca 400 đỏ.
- Đảo *ghi object* ↔ *INSERT* → chỉ ca "MinIO chết" đỏ.
- Chuyển `put` lên trước lớp kiểm → chỉ ca "không chạm storage" đỏ.
- Thêm `import minio` vào `teacher_documents.py` → chỉ check seam đỏ.

**Cổng chung:** `.\dev.ps1 check` · `test` · `typecheck`. `check` phải **17/17** sau khi thêm
check seam.

**Thử tay một lượt:** `infra-up` → `db-reset` → `be` → `fe` → tải một PDF thật lên → chip hiện
đúng tên và kích thước → xác nhận object có thật trong bucket.

## Cạm bẫy đã biết

- **Healthcheck cho MinIO: đừng cố.** Image `minio/minio` mới không có `curl` lẫn `mc`, nên mọi
  công thức chép trên mạng đều hoặc đỏ hoặc là `CMD-SHELL` giả. Mà compose hiện **không có
  `depends_on` nào**, nên healthcheck ở đây không mua gì: `ensure_ready()` lúc startup chính là
  cổng readiness, và nó có chuỗi lỗi tốt hơn. Kiểm image trước khi viết; không có thì bỏ hẳn.
- **Hai giá trị phải khớp bằng tay.** Image MinIO đòi `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`
  (tên do image quy định), còn `.env.example` dùng `MINIO_SECRET_KEY`. Y như
  `POSTGRES_PASSWORD` vs `DATABASE_URL` đang khớp bằng tay hôm nay. Chữ `PASSWORD` trong compose
  vô hại — `check_agent_holds_no_database_credentials` chỉ glob `services/agent/**/*.py`.
- **Đừng thêm init-container `mc mb` để tạo bucket.** `ensure_ready()` đã làm; hai chủ cho câu
  *"bucket có tồn tại"* là một chủ quá nhiều.
- **Không lưới nào canh `docker-compose.infra.yml`.** Thêm service mà quên `.env.example`, quên
  `config.py`, quên tài liệu — `check` vẫn xanh hết. Đây là chỗ drift cao nhất, nên task 1 và 2
  đi liền nhau.
- **Chiều *"`config.py` đọc một biến mà `.env.example` không khai"* không được kiểm.** Chỉ chiều
  ngược lại có lưới.
- **`docker compose down -v` nay xoá cả volume MinIO**, không chỉ Postgres —
  `local-development.md:296-307` đang dạy đúng lệnh ấy để chữa `UndefinedColumn`.
- **RAM mỗi upload không phải 0.** `put_object` với `length` biết trước vẫn đọc theo **part** vào
  bộ nhớ (5–16 MiB). Tức ~5–16 MB × số upload đồng thời, không phải 100 MB — nhưng cũng không
  phải hằng số nhỏ. Đáng một dòng comment.
- **Không được còn một `await file.read()` nào trên đường này.** Đó là con bug 100-MB-vào-RAM
  quay lại, và lần này nó kéo theo một `length` lệch → object cụt mà **không lỗi nào bắn ra**.
  Lớp kiểm `len(content) == 0` cũ phải thành `size == 0`.
- **`.env` thật của người dùng đang lệch `.env.example`** — thiếu `DATABASE_URL` và bảy biến
  khác. Mặc định trong `config.py` phải chạy được với compose mà không cần ai sửa `.env`.
- **`system-architecture.drawio` đã lạc hậu sẵn**: tiêu đề ghi *"ba service chạy native, **Redis**
  chạy trong Docker"* và trong hình **không có Postgres**. Và
  `check_every_figure_matches_the_diagram_it_came_from` so **sha256** của `.drawio` với
  `sources.json`, nên đổi sơ đồ mà không re-export là `check` đỏ. `drawio.exe` có ở
  `%LOCALAPPDATA%\Programs\draw.io\`, latexmk có trên PATH — làm được, nhưng đây là task rủi ro
  nhất và cố ý xếp cuối.
- **Để sau, không thuộc plan này:** FE chưa có lớp kiểm kích thước nào, nên một file 200 MB sẽ
  được đẩy lên hết rồi mới nhận 413. Và ngày đứng sau nginx thì `client_max_body_size` mặc định
  1 MB sẽ chặn trước khi BE thấy request.

## Hai phép kiểm đã làm, để khỏi ai phải lo lại

**1. 100 MB đi qua được tầng multipart của starlette.** `starlette 1.6.0` đặt
`spool_max_size = 1 MB` **và** `max_part_size = 1 MB`, và con số thứ hai nghe như một bức tường.
Nhưng `MultiPartParser.on_part_data` chỉ áp nó khi `self._current_part.file is None`, tức chỉ cho
part **không phải file**. Part là file đi thẳng vào một `SpooledTemporaryFile` không giới hạn,
tràn ra đĩa sau 1 MB. Nên 100 MB qua được, và nó không bao giờ nằm trọn trong RAM — đó chính là
thứ cho phép đo kích thước bằng `seek`/`tell` thay vì `await file.read()`.

**2. Cột `content` bị bỏ lại trong một database dev cũ KHÔNG phải một mìn im lặng.** Lo ngại tự
nhiên là: `create_all` không `DROP COLUMN`, `check_schema` theo thiết kế chỉ bắt cột **thiếu**
(`db.py:98-101`), nên một DB cũ còn `documents.content NOT NULL` sẽ cho BE khởi động sạch rồi đỏ
ở lần upload đầu bằng một `IntegrityError` không nói gì. **Nó không xảy ra**, vì cùng lần sửa ấy
thêm `storage_key` — một cột **model có, DB cũ không có** — nên `check_schema` ném `SchemaDrifted`
và chặn startup, kèm đúng lệnh `.\dev.ps1 db-reset`. Lưới đã có; không cần mở rộng `check_schema`
trong plan này.

## Status

**Xong cả mười một việc, chưa commit.** Cổng: `check` **17/17** · `pytest` **420** ·
`vitest` **178** · `tsc` sạch.

**Đo trên hệ thật, không chỉ trên test.** Tải `report.pdf` (677 920 byte) lên qua HTTP, rồi đọc
object từ MinIO ra: **sha256 khớp** (`5d564468…`). `information_schema` xác nhận `documents` nay
có `byte_size, content_type, filename, id, storage_key, teacher_id, uploaded_at` — **không còn
`content`**. `.docx` bị từ chối 400 đúng câu mới. Dừng hẳn container MinIO rồi tải lên: **503**,
câu tiếng Việt, và thư viện **vẫn đúng một hàng** — không có hàng nào trỏ vào hư không.

### Bốn đột biến, và một lỗ chúng tìm ra

Ba đột biến đỏ ngay đúng test của nó: nhận lại `.doc`/`.docx`; chuyển `put` lên trước mọi lớp
kiểm; `import minio` ngoài `storage.py`.

Cái thứ tư **xanh**, và đó là một lỗ thật: hạ `_MAX_BYTES` từ 100 MB về 10 MB chạy qua toàn bộ
suite mà không một test nào đỏ. Lý do là chính phép sửa ở task 8 — test trần `monkeypatch` hằng số
xuống 1 MB để khỏi dựng vài trăm MB trong RAM, và làm vậy thì **giá trị thật không còn lưới nào
chạm tới**. Vá bằng `test_the_cap_is_a_hundred_megabytes`, một test khẳng định hằng số — thường là
thứ vô dụng, ở đây thì không, và docstring của nó nói rõ vì sao. Chạy lại: đỏ.

### Ba chỗ khác plan, và vì sao

- **`minio/minio` không kéo được.** Ảnh chính chủ đã rời Docker Hub (`repository does not exist`)
  và quay.io của họ đòi đăng nhập. Dùng `chainguard/minio:latest` — cùng binary, cùng cờ dòng
  lệnh, chạy bằng uid 65532 nên compose phải khai `user`. Log container xác nhận
  `RELEASE.2026-09-22T19-25-18Z`.
- **Ba container xếp dọc, không ngang.** Bản ngang làm mỗi hộp rộng 146px và nhãn bị cắt
  (`po…s`), cộng nhãn cạnh đè lên hộp. Đã xem hình render ba lần trước khi chốt.
- **`.\dev.ps1 report` không phải dựng lại.** `system-architecture.pdf` **không chương nào của báo
  cáo nhúng** — nó tồn tại chỉ để thoả `check_every_figure_matches_the_diagram_it_came_from`, vốn
  đòi mỗi `.drawio` có một hình xuất ra. Nên `report.pdf` không hề cũ.

### Còn nợ, ghi để không mất

- **`services/document` sẽ không được lưới nào canh.** `check_agent_holds_no_database_credentials`
  chỉ glob `services/agent`, và check seam mới chỉ glob `services/be`. Plan 2 phải nới cả hai.
- **`AGENTS.md` gốc vẫn 181/181 dòng.** Plan này không chạm nó (MinIO là hạ tầng, không phải
  service); plan 2 thì phải, và lúc ấy phải nâng cap kèm một decision record.
- **FE chưa kiểm kích thước**, nên một file 200 MB vẫn được đẩy hết lên rồi mới nhận 413.
- **`pymupdf` vẫn là dependency ma** — có trong env, không `pyproject.toml` nào khai.
