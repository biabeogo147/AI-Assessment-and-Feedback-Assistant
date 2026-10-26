# Plan — Công thức trong sách đọc bằng Haiku khi lượt chat cần tới

- **Mở:** 26/10/2026 · Một phần của B10 (đợt `doc-pdf-vao-ngu-canh`, phần VLM của plan 3d; sympy để sau)

## Goal

Hôm nay `read_section` trả chữ OCR và tự nói *"công thức và hình không có"*, nên công thức trong dàn ý
là của Kriky chứ không của sách. Plan này cho `read_section` thêm **công thức đọc từ ảnh trang**, chỉ
ở trang có khối `formula` (nhãn PP-DocLayout lúc upload) và chỉ khi một lượt chat đọc tới trang ấy.
VLM là **Claude Haiku 5.5, tắt thinking, effort `low`**: đo 26/10/2026 trên 5 trang `run-5` sai 1/19,
`gpt-4.1-mini` sai 3/19, cùng 3,4 s/trang, rẻ khoảng 3 lần. Kết quả cache theo trang; lần đọc sau
không gọi model.

## Scope

- Trong: task `read_formulas` của `services/document`, cache Mongo `page_formulas`, BE chờ có trần
  trong `_read_section`, chữ công thức vào kết quả đọc, prompt AGENT nói công thức có thể từ sách,
  thước đo công thức vào `tools/ocr_bench`, hậu ký ADR-29 và ADR-27.
- Ngoài: sympy và vòng sửa (3d phần sau); hỏi đáp tài liệu (`ask-the-document`); pha 2
  (`retry-sees-its-outline-item`); FE.

## Decision Records

### Decision: VLM chạy trong `document`, do BE gọi và chờ

**options considered:** (a) `document` đọc mọi trang `formula` lúc dựng cây; (b) BE đẩy job sang
`document` lúc `read_section`, chờ có trần, cache theo trang; (c) AGENT gọi VLM, byte ảnh đi
`document` → AGENT.

**selected option:** (b).

**reason:** người dùng chốt 26/10 *chỉ dùng VLM khi giáo viên hỏi hay soạn đề thuộc phần có công
thức*, nên (a) loại. (c) là hướng cũ của plan 3a (`agent/vision.py`, OpenAI); nó bắt ảnh đi qua hai
hop và AGENT không có MinIO. `document` đã có dựng ảnh (`pdf.py`), byte MinIO (`storage.py`) và model
client (`index/llm.py`, mẫu `read_banner`). BE không gọi model (`MODEL_SDK_IMPORT` cấm `be`).

### Decision: chờ bằng kết quả job arq, cache bằng Mongo

**options considered:** (a) BE poll Mongo tới khi có hàng; (b) BE chờ kết quả job như
`agent_gateway.run_task`, `document` vẫn ghi cache.

**selected option:** (b).

**reason:** một lỗi của job (model từ chối, ảnh không dựng được) chỉ đi về được qua kết quả job;
poll Mongo thì lỗi trông y hệt chậm. `keep_result` đặt riêng cho task này nên hai task kia của
`index_worker` vẫn không giữ kết quả.

## Files

- `packages/contracts/src/contracts/documents.py`, `index.py` (task, payload, `PageFormulas`, `formula_key`)
- `services/document/src/document/index/llm.py`, `latex_escapes.py` (mới, bản chép), handler + `index_worker.py`, `content_store.py`, `config.py`, `.env.example`
- `services/be/src/be/content_reader.py`, `agent_gateway.py`/`queue.py`, `teacher_tools.py`, `teacher_chat.py`, `config.py`
- `services/agent/src/agent/graphs/propose/prompt.py` (không stage dòng TODO)
- `tools/ocr_bench/score.py`, `tools/ocr_bench/vision.py` (mới), `tools/check_contract.py`
- `docs/decisions/adr-29-*.md`, `adr-27-*.md`, `docs/plans/backlog.md`, `docs/testing/cases/17-cong-thuc-tu-sach.md`

## Ordered Tasks

- [x] Pha 1 — hậu ký ADR-29/27; thước công thức (chuẩn hoá lỏng, ô vàng tách/gộp) vào `score.py` có
      test. Review subagent.
- [x] Pha 2 — `document`: contracts, `latex_escapes` bản chép + test giống hệt, `read_formulas`, handler,
      cache, xoá khi đọc lại, config; check escape-repair quét `document/index`. `tools/ocr_bench/vision.py`
      gọi chính `read_formulas`: đo prompt có dòng `\vdots` trên 5 trang `run-5`, rồi mọi trang vàng có
      khối `formula`. Review subagent.
- [x] Pha 3 — BE: đọc trang có công thức và cache, đẩy job và chờ có trần, ghép vào `read_section`,
      ngân sách lượt. Review subagent.
- [x] Pha 4 — AGENT: mô tả tool, `CORE`/`BOOK_PROCEDURE`, test khoá chữ. Review subagent.
- [x] Pha 5 — thử tay: case 04, 06, case mới 17; biên bản. Review subagent.

## Validation Checks

- `.\dev.ps1 check` và `.\dev.ps1 test` xanh; check escape-repair đỏ khi bẻ lời gọi sửa ở `document`.
- `tools/ocr_bench/vision.py`: sai/thiếu ≤ 1/19 trên `run-5`.
- Trình duyệt: lần đọc đầu có khối *Công thức đọc từ ảnh*; lần hai không có job `read_formulas` mới.

## Status

Mở và đóng ngày 26/10/2026. Trong ba cổng:

- `check` (26/26) và `test` (1926 pytest + 368 vitest) xanh;
- trên trình duyệt: lần đọc đầu có khối công thức, lần hai không có job mới;
- `vision.py` ra 2/19 theo thước mới, xem dưới.

**Pha 1, thước đo** (`tools/ocr_bench/score.py`, `formula_verdicts`, nhãn `khop/tach/gan/lech/thieu`):

- 5 trang `run-5` (19 công thức vàng), prompt có dòng dặn `\vdots`: 13 khớp, 4 tách, 1 lệch (một chuỗi
  trang 17 bị tách dòng), 1 thiếu (*"Nếu…thì"* bị tách). Thước mới chặt hơn thước của lần đo trước
  plan (1/19), nên lệch + thiếu là **2/19**: cổng ≤ 1/19 **chưa đạt** đúng chữ. Cả hai là chỗ tách
  dòng, không sai nội dung; người dùng xem số này khi duyệt. `⋮` nay đọc đúng thành `\vdots`.
- 24 trang vàng có khối `formula` (58 công thức), ở
  `data/results/run-102/vision-claude-haiku-5-5-product/`: 35 khớp, 12 tách, 8 lệch, 3 thiếu; trung vị
  2,8 s mỗi trang; tổng 72 937 token.
- Phần lớn chỗ lệch là khác cách ghi: bỏ đơn vị *(người)*, `BC` không bọc `\text`, tách dòng.
- Lỗi nội dung thật có hai: trang 38 thiếu dòng `\underbrace`, trang 50 đọc `B(6)` thiếu số 6. Cả hai
  vào `backlog.md`.

**Pha 2–4, code.** Có thêm:

- task `read_formulas` trên `aiafa:document-index` (`timeout` 90 s, `keep_result` 20 s, `max_tries` 1);
- cache `page_formulas`, xoá khi tài liệu đọc lại;
- BE `queue.run_job`, dùng chung với `agent_gateway.run_task`, chờ có trần 15 s;
- giờ chờ cộng vào lượt, trần `MOST_FORMULA_WAITS` × 15 s, đã tính vào test khoá lượt;
- khối công thức chung một trần 3000 ký tự cho cả phần đọc, cắt ở ranh giới công thức;
- prompt `CORE` và bước 4 `BOOK_PROCEDURE` nói công thức có thể chép từ sách.

Mỗi pha có subagent review, và mọi điểm đều đã sửa, trừ những điểm ghi vào backlog. Những điểm đã sửa:

- review pha 2: escape JSON hợp lệ như `\neq`, `\rho` bị đọc thành ký tự điều khiển; ghi từng trang
  ngay khi đọc xong; bắt `PdfUnreadable` theo từng trang;
- review pha 3: lỗi Redis làm mất chữ của phần đọc; `keep_result` 120 s chặn xin lại; giờ chờ không
  có trần; khối công thức không có trần tổng;
- review pha 4: `formulas_pending` không dặn model đừng đọc lại; comment ghi rõ chữ prompt chưa đo.

**Pha 5, thử tay** (`docs/testing/ket-qua/2026-10-26-dc9035e-claude-haiku-5-5.md`):

- Case 17 **đạt tiêu chí 2–5, không đạt tiêu chí 1** (nguồn bài không gọi tên bài): lần đầu đọc ảnh ba trang, mỗi trang một job khoảng 3 s; dàn ý chép đúng
  $a^m \cdot a^n = a^{m+n}$ và $a^m : a^n = a^{m-n}$; đoạn chat thứ hai không có job mới.
- Case 06 **đạt**.
- Case 04 đạt phần sách và soạn câu, **không đạt** ở lượt 2: `brief` rỗng nên `oke` ra dàn ý mới
  thay vì plan. Lỗi có từ trước plan này (mục backlog *Dàn ý lưu `brief` rỗng…*).
- Chi phí 0,20–0,28 USD, **vượt** mức ước ≤ 0,05 USD; phần VLM chỉ khoảng 0,005 USD.

**Chưa làm, đã ghi ở `backlog.md`** (mục *Lộ ra khi làm plan công thức đọc bằng Haiku khi cần*):

- chưa đo bench prompt mới;
- job công thức chạy chung `max_jobs` với job dựng cây;
- trang 21 không có đoạn chữ nào phủ tới;
- Haiku đọc cả số thường thành công thức.

sympy là phần còn lại của 3d.
