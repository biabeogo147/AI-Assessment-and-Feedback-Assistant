# Đợt việc — Đọc PDF vào ngữ cảnh ra đề

## Goal

Thi hành [ADR-27](../../decisions/adr-27-tai-lieu-di-vao-ngu-canh-ra-de.md): nội dung tài liệu
giáo viên tải lên đi vào prompt soạn đề, **như phạm vi, không như nguồn**. `backlog.md` ghi
món này bằng lời từ 06/09/2026 — *"nội dung tài liệu chưa đi vào prompt của AGENT"* — và nó
mang mã **B10** trong artifact theo dõi pipeline.

**File này là cái ô của cả đợt, không phải một plan thi hành.** Nó giữ những **quyết định dùng
chung** mà nhiều plan con cùng dựa vào, và danh sách các plan con cùng cổng của chúng. Mỗi plan
con có file riêng với `Ordered Tasks` và `Status` của nó.

Đợt này chia **năm plan** vì một plan không chở nổi: nó đẻ ra một service, một process mới cho
BE, hai kho lưu mới, và một bộ định tuyến. Thứ tự **bị ép bởi phụ thuộc**, không bởi sở thích.

## Năm plan, và cổng giữa chúng

| # | Plan | Cổng mở sang plan sau | Model? |
|---|---|---|---|
| 1 | [`2026-10-08-document-bytes-to-minio-plan.md`](2026-10-08-document-bytes-to-minio-plan.md) | tải một PDF lên rồi đọc lại từ MinIO, **khớp từng byte** | không |
| 2 | `services/document` ra đời, cổng text layer — *chưa viết* | một PDF scan làm chip đứng ở *không đọc được chữ*; một PDF chữ cho `page_count` đúng | không |
| 3 | Mục lục, chương, chunk, Mongo — *chưa viết* | một cuốn sách thật ra đủ chương, `get_chapter` trả metadata | **có** |
| 4 | Jev và skill — *chưa viết* | một đoạn bài tập được gán đúng nhãn | **có** |
| 5 | Nội dung vào prompt — *chưa viết* | **không payload nào rời BE mang chunk nhãn bài tập** | có |

Bốn plan sau **cố ý chưa có file**: `AGENTS.md` cấm tạo file rỗng hoặc chỉ có heading, và thiết
kế chi tiết của chúng chưa xong. Mỗi file được viết khi tới lượt nó.

**Plan 1 và 2 không có một lời gọi model nào.** Đó là nửa đợt việc đo được bằng test thường, và
là nửa chứa mọi giả định nguy hiểm — nếu có gì sụp, nó sụp ở đó, trước khi ta xây gì lên trên.

## Decision Records

Đây là những quyết định **nhiều plan cùng dựa vào**. Quyết định chỉ một plan dùng thì nằm trong
file của plan ấy.

### Decision: PyMuPDF, và từ chối tệp không có text layer

**options considered:**

- (a) `pypdf` thuần Python, BSD.
- (b) **PyMuPDF** — có `get_toc()`, có cỡ chữ từng span, đọc nhanh.
- (c) Docling hoặc Marker — pipeline ML, dựng lại cấu trúc tốt hơn, nặng hơn hẳn.

**selected option:** (b).

**reason:** đo ngày 07/10/2026 trên một PDF tiếng Việt 29 trang: mở file **1,4 ms**, quét toàn
bộ **28 ms** (ngoại suy 400 trang ≈ **0,4 giây**), `get_toc()` trả **43 mục có cấp**. (c) giải
bài toán ta không có — ta không cần dựng lại bảng biểu, ta cần mục lục và chữ. PyMuPDF **đã có
sẵn trong env**, nên (b) còn không thêm một lần cài.

**Một phép đo cảnh báo, ghi lại để đừng quên:** trích xuất tiếng Việt **mất dấu cách** —
`"Nghiệp vụcủa hệthống"`, **164 chỗ / 32.484 ký tự**, và **cả ba đường trích xuất cho cùng con
số**. Nên pipeline cần một bước sửa, và phép đo ấy làm trên PDF do LaTeX sinh — sách giáo khoa
thật có thể khác.

**Một món nợ phải trả ở plan 2:** `pymupdf 1.28.2` có trong conda env nhưng **không
`pyproject.toml` nào khai nó**. Nó là một dependency ma; plan nào dùng tới nó phải khai nó.

### Decision: `services/document` là service thứ tư, và nó đọc tệp

**options considered:**

- (a) Xử lý trong AGENT hiện có.
- (b) Xử lý trong BE.
- (c) **Một service mới, `services/document`.**

**selected option:** (c).

**reason:** **boundary.** Nó là một agent mới — prompt riêng, model riêng, quy trình riêng.
(b) cho BE sinh chữ, phá ranh giới đáng giữ nhất của repo: `be/config.py` hiện **không có một
trường credential model nào**. (a) bắt một graph phân đoạn sách dùng chung ngân sách thời gian,
prompt catalog và tên queue với một lượt chat của giáo viên — hai việc không giống nhau ở bất
kỳ chiều nào ngoài chuyện cùng gọi model.

**Lý do cũ đã hết đúng, ghi lại để không ai viện lại nó:** bản trước của Decision Record này
nói service thứ tư tồn tại vì *"nó đọc cả cuốn sách, không chia nổi ngân sách thời gian với một
lượt chat — chỗ chỉ dư 10 giây"*. Lý do ấy tan khi **một job là một chương** và không ai chờ nó
đồng bộ. Boundary mới là lý do thật, và nó không phụ thuộc vào một phép đo nào.

**Tên theo `architecture.md` mục *Quy ước đặt tên service mới***: thư mục chữ thường theo
**domain** (`services/document`), package `src/document/`, distribution `aiafa-document`, biến
môi trường `DOCUMENT_*`, cổng **8100** (BE + 100).

**Cái giá, nói ra:** một hàng trong bảng service của `AGENTS.md` — mà file ấy đang **181/181
dòng**, đúng cap cứng của `check_contract_files_stay_short`, nên plan 2 phải nâng cap kèm một
decision record. Cộng một tầng `lint-imports`, một `AGENTS.md` con, một `pyproject.toml`.

### Decision: byte tài liệu sang MinIO, chunk sang MongoDB

**options considered:**

- (a) Giữ tất cả trong Postgres.
- (b) **Byte sang MinIO; chunk sang MongoDB; `documents` giữ một khoá.**

**selected option:** (b).

**reason:** hai nửa, hai lý do khác nhau.

**Byte phải rời Postgres** vì `services/document` **không có credential database** và byte đang
nằm trong một cột. Ba đường thay thế đều phá một luật: FE gọi thẳng service mới thì mất *"BE là
service duy nhất FE gọi"*; cho nó đọc Postgres thì mất *"BE sở hữu mọi database"*; nhét file
vào payload arq thì Redis chở cả cuốn sách. `models.py:696-697` đã hẹn trước đúng lần chuyển
này.

**Chunk vào Mongo** vì cây mục lục **rách** — 43 mục có cấp trên một PDF 29 trang — mà Postgres
chỉ có adjacency + recursive CTE, `ltree`, hoặc JSONB, không đường nào đẹp; vì metadata chunk
còn đổi hình nhiều, mà `create_all` *"không bao giờ cứu được một cột đã đổi hình dạng"*
(`db.py:48-49`); và vì PageIndex **không dùng vector**, nên `pgvector` — thứ hấp dẫn nhất của
Postgres cho RAG — không liên quan.

**Hai điều kiện kèm theo, không thương lượng:**

1. **`packages/contracts` giữ hình dạng của một chunk.** Mongo là *nơi lưu*, không phải *nơi
   định nghĩa*. Thiếu điều này, ranh giới `document` → BE đang có kiểu sẽ âm thầm thành không
   kiểu — thứ duy nhất ở đây thật sự gây đau.
2. **BE là service duy nhất ghi Mongo**, nên dòng `AGENTS.md:15` *"all databases"* vẫn đúng
   từng chữ, không phải nới.

### Decision: `document` đẩy job cho BE qua arq, trên một queue riêng

**options considered:**

- (a) `document` gọi HTTP vào BE để BE ghi.
- (b) BE poll kết quả job qua arq result store, như `read_job` đang làm.
- (c) **`document` đẩy một job `ingest` lên queue riêng; BE tiêu thụ nó.**

**selected option:** (c).

**reason:** (a) là **mũi HTTP đầu tiên giữa hai service** trong repo này — grep `httpx|requests|
aiohttp` trong `services/` trả về rỗng — và nó cần một thứ chưa tồn tại: xác thực
service-to-service. (b) chết vì `worker.py:108` đặt `keep_result = job_result_ttl_seconds`:
**kết quả job hết hạn**, đúng cái bẫy `drafting.py` đã ghi lại.

(c) làm BE có **process thứ hai** — hôm nay `be/queue.py` chỉ có `enqueue_grading` và
`read_job`, không một handler nào. Đổi lại, job tự mang dữ liệu đi và không ai chờ kết quả của
nó, nên TTL hết là mối đe doạ.

**Bản trước của Decision Record này chọn *"một service mới, tiêu thụ cùng queue arq"*** — sai ở
hai chữ *cùng queue*. `aiafa:grading` đang chở **bảy task** (`worker.py:88-104`: soạn câu, sinh
lại, giải thích kèm học, đặt tên đoạn, chat giáo viên, báo cáo, chấm bài). Tên ấy đã sai từ
trước; đợt này tách tên cho đúng thay vì chất thêm lên nó.

### Decision: thứ tự ghi giữa hai kho — chunk trước, `state` sau

**options considered:** (a) bật `state` rồi ghi chunk · (b) **ghi chunk rồi mới bật `state`**.

**selected option:** (b).

**reason:** Postgres và Mongo **không commit cùng nhau**, nên phải chọn hình dạng hỏng nào rẻ
hơn. (a) để lại một tài liệu mang nhãn *sẵn sàng* mà không có chunk nào — **một chip nói dối**,
đúng thứ ADR-27 cấm. (b) để lại chunk mồ côi — rác, không ai thấy, dọn được. `state` ở Postgres
là **nguồn sự thật duy nhất**; Mongo không bao giờ được hỏi *"đã xong chưa"*.

Cùng luật ấy áp cho MinIO ở plan 1: ghi object trước, INSERT hàng sau.

### Decision: ba tool đọc, không có `search_document`

**options considered:**

- (a) Một tool `search_document(query)` trả các đoạn khớp.
- (b) **Ba tool lần xuống**: `list_chapters` → `get_chapter` → `get_chunk`.

**selected option:** (b).

**reason:** hình dạng này là [PageIndex](https://pageindex.ai/blog/pageindex-intro) — *vectorless,
reasoning-based RAG*: dựng cây mục lục rồi để model đánh giá từng nút qua **tiêu đề + tóm tắt**.
Đạt **98,7%** trên FinanceBench. `search_document` thừa vì tóm tắt chương đã đủ để lần xuống, và
một tool thừa không miễn phí: độ chính xác chọn tool tụt rõ khi vượt **10–15 tool**, và catalog
đi từ 6 lên **9**.

Cả ba là tool **đọc**, nên chúng về **pha 1** của ADR-25 — vòng lặp `for _ in range(max_tool_steps)`
(`teacher_chat.py:1354`, trần **8**) đã có sẵn và không phải sửa.

**Điều kiện kèm theo:** PDF không nhúng outline thì `services/document` **phải tự dựng mục lục**.
Cây rỗng thì cả thiết kế sụp.

### Decision: Jev làm bộ định tuyến, gọi từ `services/document`

**options considered:**

- (a) Ánh xạ cứng tool → skill, BE tra bảng.
- (b) Kriky tự chọn skill từ một danh mục mô tả, như Claude làm.
- (c) **Jev** (TypeSafe AI) — mô hình trả **quyết định có kiểu** kèm xác suất.

**selected option:** (c), gọi từ `services/document`, với (a) làm đường lùi khi Jev hỏng.

**reason:** (a) không giải được ý định ngữ nghĩa — *"phân tích điểm số khối 12"* không có tool
nào đứng sau cho tới khi plan đã lập. (b) đặt thêm một danh mục vào đúng chỗ **~40% lỗi agent**
rơi vào: Berkeley Function Calling Leaderboard đo **43% → 2%** khi đi từ 4 lên 51 tool.

(c) tách quyết định ấy **ra khỏi** prompt chính, nên cơ chế hỏng kia không áp. `POST /v1/systemone`
nhận `state` + một **map** câu hỏi; `choice` trả lựa chọn + phân phối xác suất + `confidence`.
**$0,042 / triệu token vào, 70–500 ms**, và nhiều câu hỏi chạy **song song trên cùng một state**.

**Bản trước đặt nó ở BE, và lý do ấy sai.** Nó viện invariant `AGENTS.md:43` *"AGENT emits no
routing decision"*. Nhưng lưới canh dòng ấy — `test_agent_emits_no_routing_decision`
(`services/agent/tests/test_handlers.py:32-36`) — chỉ khẳng định **kết quả chấm không mang
`needs_teacher_review` và `review_reason`**, và docstring của chính nó nói luật thật: *"Cổng
teacher-in-the-loop phải nằm ngoài service AI."* Jev chọn skill không phải một cổng
teacher-in-the-loop. Tên invariant rộng hơn luật nó canh, nên **đổi tên nó** là việc của plan 4.

Và lý do đặt Jev **ra khỏi BE** mạnh hơn lý do cũ đặt nó vào: Jev là một lời gọi model, còn
`be/config.py` hiện **không có một trường credential model nào**. Giữ nguyên ranh giới ấy đáng
hơn hẳn sự tiện tay.

**Phải thêm một dòng invariant chưa từng có:** *"chỉ `agent` và `document` gọi model provider"*,
kèm một lưới glob `services/be` tìm tên provider và `api_key`. Không có nó, lần sau ai đặt một
lời gọi model vào BE sẽ không có gì kêu.

**`choice` buộc phải chọn**, nên tập skill phải có một lựa chọn **"không dùng skill nào"**.

### Decision: skill là file Markdown, `description` kiêm `criteria`

**options considered:**

- (a) Giữ hướng dẫn trong prompt Python như hiện nay.
- (b) **File Markdown có frontmatter `name` + `description`**, nạp theo quyết định của Jev.

**selected option:** (b).

**reason:** khảo sát ghi *"smaller models running with curated skills could match larger models
running without them"* và *"focused skills with 2 to 3 modules consistently outperformed
comprehensive documentation"* — mà repo này thử tay bằng `gpt-4o-mini`. Và `description` **chính
là** `criteria` mà Jev đọc, nên câu *"khi nào skill này áp dụng"* có **một** nguồn sự thật, không
có bản sao thứ hai trong code để lệch nhau.

Hai skill đầu: `tim-trong-tai-lieu.md` (Kriky duyệt tài liệu) và `phan-doan-tai-lieu.md` (việc của
`services/document`). **Không** gộp skill *"tạo đề hai pha"* vào đợt này — đó là refactor thuần,
làm sau khi cơ chế đã chứng minh được.

### Decision: gán chunk cho câu được đóng băng vào database

**options considered:**

- (a) Hàm thuần `partition(pages, n, seed)`, tính lại mỗi lần.
- (b) **Ghi xuống `DraftItem`** trước khi `fire` đẩy job nào.

**selected option:** (b).

**reason:** cơ học, không phải sở thích. `fire` (`drafting.py:296-306`) tính
`total = max(rows) + wanted`, nên **`of_total` đổi** khi giáo viên soạn thêm câu — một hàm thuần
theo `(ordinal, of_total)` sẽ **xáo lại chunk của mọi ô đã xong**. Và `fire` **bắn lại** ô đang
`retry`, nên một chunk tính lại cho lần thử hai làm `last_fault` mất giá trị chẩn đoán.

## Files

Đợt này không tự sửa file nào. Mỗi plan con mang bảng `Files` của nó.

## Ordered Tasks

- [ ] **Plan 1 — byte sang MinIO** (mã **C9**)
- [ ] **Plan 2 — `services/document` và cổng text layer** (mã **C2**, **C11**, một nửa **C10**)
- [ ] **Plan 3 — mục lục, chương, chunk, Mongo** (mã **C3**, **C10**)
- [ ] **Plan 4 — Jev và skill** (mã **C4**)
- [ ] **Plan 5 — nội dung vào prompt** (đóng **B10**)

## Validation Checks

Cổng của từng plan nằm ở bảng đầu file và trong `Validation Checks` của plan ấy. Cổng của **cả
đợt** là luật nặng nhất của ADR-27, và nó phải có một lưới chạy được, không phải một câu hứa:

> **Không payload nào rời BE mang một chunk nhãn *bài tập*.** Một repo check trong
> `tools/check_contract.py`. Đây là nơi thi hành ADR-04 — một luật không có chỗ canh là một ý
> tưởng.

Cộng: `.\dev.ps1 check` · `test` · `typecheck` xanh sau mỗi plan, và mỗi luật mới đỏ **đúng**
test của nó dưới một đột biến một dòng.

## Status

**Plan 1 đang làm.** ADR-27 đã viết và đã sửa ngày 08/10/2026 (cổng text layer thành bất đồng
bộ). Bốn plan sau chưa có file.

Ba Decision Record trong file này đã bị **viết lại** ngày 08/10/2026, vì bản đầu nói ngược với
thiết kế đã chốt: Jev chuyển từ BE sang `services/document`; lý do service thứ tư đổi từ ngân
sách thời gian sang boundary; và service mới dùng **queue riêng** chứ không *"tiêu thụ cùng
queue arq"*. Hai Decision Record mới được thêm: MinIO + Mongo, và thứ tự ghi giữa hai kho.
