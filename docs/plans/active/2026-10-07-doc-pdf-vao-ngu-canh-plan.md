# Plan — Đọc PDF vào ngữ cảnh ra đề

## Goal

Thi hành [ADR-27](../../decisions/adr-27-tai-lieu-di-vao-ngu-canh-ra-de.md): nội dung tài liệu
giáo viên tải lên đi vào prompt soạn đề, **như phạm vi, không như nguồn**. `backlog.md` ghi
món này bằng lời từ 06/09/2026 — *"nội dung tài liệu chưa đi vào prompt của AGENT"* — và nó
mang mã **B10** trong artifact theo dõi pipeline. `backlog.md` tự nó **không đánh số**.

**Chưa bắt đầu.** File này tồn tại trước phần code vì `AGENTS.md` nói một thay đổi sinh ra
decision record thì cần một plan, và vì `docs/decisions/README.md` nói quyết định **kỹ thuật**
không được nằm trong ADR — chúng sống ở đây.

## Decision Records

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

**Điều kiện kèm theo:** PDF không nhúng outline thì agent xử lý **phải tự dựng mục lục**. Cây
rỗng thì cả thiết kế sụp.

### Decision: Jev làm bộ định tuyến, gọi từ BE

**options considered:**

- (a) Ánh xạ cứng tool → skill, BE tra bảng.
- (b) Kriky tự chọn skill từ một danh mục mô tả, như Claude làm.
- (c) **Jev** (TypeSafe AI) — mô hình trả **quyết định có kiểu** kèm xác suất.

**selected option:** (c), với (a) làm đường lùi khi Jev hỏng.

**reason:** (a) không giải được ý định ngữ nghĩa — *"phân tích điểm số khối 12"* không có tool
nào đứng sau cho tới khi plan đã lập. (b) đặt thêm một danh mục vào đúng chỗ **~40% lỗi agent**
rơi vào: Berkeley Function Calling Leaderboard đo **43% → 2%** khi đi từ 4 lên 51 tool.

(c) tách quyết định ấy **ra khỏi** prompt chính, nên cơ chế hỏng kia không áp. `POST /v1/systemone`
nhận `state` + một **map** câu hỏi; `choice` trả lựa chọn + phân phối xác suất + `confidence`.
**$0,042 / triệu token vào, 70–500 ms**, và nhiều câu hỏi chạy **song song trên cùng một state**.

Đặt ở **BE** vì invariant `AGENTS.md` *"AGENT emits no routing decision"*. Và vì Jev trả **nhãn có
kiểu chứ không sinh chữ**, nó không thể đẻ ra một cách diễn đạt thứ hai cho các câu luật mà ADR-03
buộc phải *"giống hệt nhau từng chữ"* ở cả ba nơi.

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
agent xử lý). **Không** gộp skill *"tạo đề hai pha"* vào đợt này — đó là refactor thuần, làm sau
khi cơ chế đã chứng minh được.

### Decision: gán chunk cho câu được đóng băng vào database

**options considered:**

- (a) Hàm thuần `partition(pages, n, seed)`, tính lại mỗi lần.
- (b) **Ghi xuống `DraftItem`** trước khi `fire` đẩy job nào.

**selected option:** (b).

**reason:** cơ học, không phải sở thích. `fire` (`drafting.py:296-306`) tính
`total = max(rows) + wanted`, nên **`of_total` đổi** khi giáo viên soạn thêm câu — một hàm thuần
theo `(ordinal, of_total)` sẽ **xáo lại chunk của mọi ô đã xong**. Và `fire` **bắn lại** ô đang
`retry`, nên một chunk tính lại cho lần thử hai làm `last_fault` mất giá trị chẩn đoán.

### Decision: agent xử lý là service thứ tư

**options considered:**

- (a) Xử lý trong AGENT hiện có.
- (b) **Một service mới**, tiêu thụ cùng queue arq.

**selected option:** (b).

**reason:** nó đọc **cả cuốn sách**, không chia nổi ngân sách thời gian với một lượt chat — chỗ
chỉ dư **10 giây** (`LLM_TIMEOUT_SECONDS=20 × LLM_MAX_ATTEMPTS=3 = 60` so với
`AGENT_JOB_TIMEOUT_SECONDS=70`, canh bởi `check_contract.py:229`).

**Cái giá, nói ra:** một hàng trong bảng service của `AGENTS.md`, một tầng `lint-imports`, một
`AGENTS.md` riêng, và tên theo `architecture.md` mục *"Quy ước đặt tên service mới"*.

## Files

| File | Việc |
|---|---|
| `docs/decisions/adr-27-*.md` | **đã viết** — luật nghiệp vụ |
| `services/be/src/be/teacher_documents.py` | mở file lúc upload, từ chối tệp không có chữ, đẩy job |
| `services/be/src/be/models.py` | trạng thái `Document`; bảng trang/chương/chunk; cột chunk trên `DraftItem` |
| `services/<tên mới>/` | agent xử lý — service thứ tư |
| `services/be/src/be/teacher_tools.py` | ba tool đọc, vào catalog pha 1 |
| `packages/contracts` | `source_excerpt` + `source_pages` trên `DraftQuestionRequested` |
| `services/be/src/be/jev.py` *(mới)* | bộ định tuyến có kiểu, cộng đường lùi |
| `docs/skills/*.md` *(mới)* | hai skill đầu |
| `services/fe/src/screens/teacher/Rail.tsx` | ba trạng thái của chip |
| `tools/check_contract.py` | check mới: bài tập không rời BE; skill không mồ côi |
| Figma `mOe2ZmrqOq1Uix45v6PNGD` | chip ba trạng thái; artboard 1 và 2 |

## Ordered Tasks

Chưa chia pha. Thứ tự **bị ép bởi phụ thuộc**, không phải bởi sở thích — xem hình *Roadmap* trong
artifact: không có text layer thì không có chunk; không có nhãn thì không lọc được bài tập; không
đóng băng thì mười job soạn mười kiểu.

- [ ] Nhận file: mở, kiểm text layer, từ chối, đẩy queue, ba trạng thái trên chip
- [ ] Agent xử lý: mục lục (tự dựng khi thiếu), chương, chunk, metadata, nhãn loại, sửa dấu cách
- [ ] Jev: `jev.py`, phân loại chunk, đường lùi khi hỏng
- [ ] Ba tool đọc vào catalog pha 1
- [ ] Hai skill, và cơ chế nạp
- [ ] Đóng băng chunk cho câu; `source_excerpt` vào payload
- [ ] Cổng, đo trên trình duyệt, Figma ↔ FE bằng số

## Validation Checks

- **Cổng:** `.\dev.ps1 check` · `test` · `typecheck`.
- **Đột biến:** mỗi luật mới đỏ **đúng** test của nó dưới một đột biến một dòng.
- **Luật nặng nhất phải có lưới chạy được:** không payload nào rời BE mang một chunk nhãn
  *bài tập*. Đây là nơi thi hành ADR-04 — một luật không có chỗ canh là một ý tưởng.
- **Figma ↔ FE** so bằng số.

## Status

**Chưa bắt đầu.** ADR-27 đã viết; file này giữ phần kỹ thuật của cùng bộ quyết định.

**Ba thứ phải trả lời trước khi gõ dòng code đầu tiên:**

1. **`_MAX_BYTES = 10 MB`** (`teacher_documents.py:37`) có thể loại phần lớn bản SGK scan thật.
   Người dùng chọn **không đo trước**, nên đây là **rủi ro đã nhận**. Nếu nó bật ra là đúng thì
   `Document.content` phải rời database trước mọi việc khác — `models.py:696` đã báo trước điều đó.
2. **BE gọi Jev là đặt một lời gọi model đồng bộ lên đường request của BE.** Chưa ai viết ra đây là
   một ngoại lệ hay một định nghĩa lại ranh giới. `check_model_call_fits_inside_the_job_waiting_for_it`
   canh ngân sách ấy cho AGENT, không cho BE.
3. **`confidence` của Jev chưa ai đo trên tiếng Việt**, mà ta sắp đặt ngưỡng lên nó.
