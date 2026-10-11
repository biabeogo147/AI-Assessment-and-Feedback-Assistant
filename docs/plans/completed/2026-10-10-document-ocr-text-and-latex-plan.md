# Plan 3a — OCR: từ ảnh scan ra chữ và LaTeX

## Context

Đợt [*Đọc PDF vào ngữ cảnh ra đề*](2026-10-07-doc-pdf-vao-ngu-canh-plan.md) còn bốn plan chưa
viết. Plan 3 của nó — *"Mục lục, chương, chunk, Mongo"* — vừa **vỡ làm ba** sau một lượt
đo, và lý do thì không thương lượng được:

**Cả 14 cuốn SGK trong `data/` là ảnh scan thuần.** Đo ngày 10/10/2026: mỗi trang của mỗi cuốn là
đúng một ảnh toàn trang, **0 ký tự**, `drawings=0`, ~1190×1667 px trên khổ A4 ≈ 144 DPI. Producer là
`3-Heights™ PDF Optimization Shell 6.3.1.5` và `Adobe Acrobat 21.1 Image Conversion Plug-in`. Bốn
cuốn còn báo `toc == page_count` vì máy quét ghi **một bookmark mỗi trang**
(`[1, 'TOÁN 11 - KNTT - TẬP 01_Page_001', 1]`) — một mục lục giả.

Hệ quả: `probe.py` xếp cả 14 cuốn vào `NO_TEXT_LAYER`, và **mọi tín hiệu dựa trên font** của lượt
khảo sát đầu — cỡ chữ, in đậm, font Computer Modern cho công thức — **không tồn tại**. OCR thành
bước bắt buộc đầu tiên, và plan này là bước ấy.

Chia ba theo người dùng chốt (10/10/2026): **3a** OCR ra chữ + LaTeX · **3b** Jev dựng hierarchy ·
**3c** sympy kiểm công thức. Đánh số `a/b/c` chứ không đánh lại 1/2/3, vì plan 1 và 2a–2c của đợt
này đã commit và được trỏ tới từ nhiều chỗ.

Hai plan còn lại của bộ ba — **3b** Jev dựng hierarchy, **3c** sympy kiểm công thức — đã được ghi
nợ đầy đủ ở hai mục cuối của [`backlog.md`](../backlog.md), kèm bốn phép đo mà người làm sau không
phải đo lại.

## Phạm vi của 3a, và nó dừng ở đâu

Người dùng chốt: **module + benchmark, chưa nối đường chạy.**

- Đẻ ra `document/ocr/*`: một hàm thuần `read_page(raw, index) -> PageRead`.
- Đẻ ra một bộ benchmark chạy trên `data/`, có nhãn vàng và có số.
- **Không** chạm arq, **không** chạm message nào, **không** dựng Mongo.

Vì sao dừng ở đó: Mongo chưa có trong `docker-compose.infra.yml`, `document/storage.py` **cố ý chỉ
đọc** (docstring của nó nói thẳng *"một `put` ở đây sẽ là đường thứ hai để byte vào bucket"*), và
**hình dạng cái được lưu do cây mục lục quyết** — tức do 3b. Nối đường ghi bây giờ là trả lời câu
*lưu gì* trước khi biết câu trả lời. File ô của đợt cũng cấm: *"một plan mang hai cổng là một plan
không biết nó xong khi nào"*.

Cổng của 3a vì thế là **một con số**, không phải một cái chip.

## Decision: paddle lo layout và công thức, VietOCR lo chữ

**options considered:**

- (a) PaddleOCR trọn gói (`lang=vi`).
- (b) EasyOCR trọn gói.
- (c) **PP-DocLayout + PP-OCRv5 detector + PP-FormulaNet, nhưng chữ do VietOCR nhận dạng.**

**selected option:** (c). Người dùng chốt 10/10/2026.

**reason:** bốn engine đã đo trên cùng một trang (`L6T1 p5`, 1 139 ký tự gõ tay làm nhãn), cùng máy,
CPU, `enable_mkldnn=False`:

| Engine | CER | s/trang | Công thức | Layout |
|---|---|---|---|---|
| RapidOCR (model mặc định) | 28,5% | 4,0 | vỡ | không |
| PaddleOCR v6 medium `vi` | 14,1% | 24,5 | vỡ | không |
| PaddleOCR v5 `latin` | 13,0% | 32,4 | vỡ | không |
| EasyOCR `vi` | 9,4% | 4,9 | không | không |
| PP-StructureV3 | (lỗi dict) | 37,4 – 149 | **đúng** | **đúng** |

Hai lỗi **khác loại nhau**, nên chúng bù được cho nhau:

- PaddleOCR thủng **từ điển ký tự**, không thủng phần nhìn. Kiểm ở mức byte: nó phát ra ă ũ ồ ư ê ô
  ơ đ nhưng **không bao giờ** phát ra tổ hợp hai dấu (ế ố ộ ớ ứ ợ), nên `Kết nối tri thức với cuộc
  sống` ra `Kt ni tri thc vi cuc sng`. `vi` chỉ là một thành viên của `LATIN_LANGS`.
- EasyOCR đọc **đúng dấu** nhưng **cắt dòng sai**: nó xé `Trên | tay các em là cuốn` và đánh rơi chữ
  cuối dòng. 9,4% kia gần như toàn bộ là lỗi phân đoạn, không phải lỗi đọc.

Nên lấy **detector của paddle** (phần mạnh) ghép **recognizer tiếng Việt** (phần paddle không có).
VietOCR thay EasyOCR vì nó là model huấn luyện riêng cho tiếng Việt và nhận **một dòng một lần** —
đúng hình dạng mà một detector tốt cung cấp.

Và PP-StructureV3 giải đúng hai thứ không engine dòng nào giải được:

```
OCR dòng (p40):   "lap-100="  …  "（x-27000),hayp-100="      <- phân số bị xé làm hai dòng
PP-FormulaNet:    p-100=\frac{100-90}{27\;000-30\;000}(x-27\;000)
                  R(p)=px=p(-300p+57\ 000)=-300p^{2}+57\ 000p.
                  y=f(x)=x^{3}-3x^{2}+2x+1
                  (-\infty;-1),(1;+\infty)
```

PP-DocLayout trả nhãn `doc_title`, `paragraph_title`, `text`, `formula`, `image`, `number` kèm bbox —
tức **tín hiệu hierarchy sống sót** dù metadata font đã chết. `number` chính là số trang in, mảnh để
nối trang PDF với trang in trong sách.

**Cái giá, nói ra:** `services/document/pyproject.toml` hiện có **5 dependency**. Plan này thêm
`paddlepaddle` + `paddleocr` + `paddlex[ocr]` (~1 GB) và `vietocr` kéo theo `torch` (~0,9 GB). Gần
**2 GB** cho một service từng nhẹ. Không có đường rẻ hơn đã đo được; đường ONNX thuần
(`onnxruntime` ~60 MB) người dùng đã gạt, và nó chưa đo một lần nào.

## Decision: `document/pdf.py` thành module duy nhất import pymupdf

`tools/check_contract.py:1589` cho phép **đúng một** file import pymupdf:
`services/document/src/document/probe.py`. OCR cần một hàm `render_page` — và nhét nó vào `probe.py`
là cho một module chính sách gánh một việc dựng ảnh.

Nên: **tách `document/pdf.py`** giữ mọi thứ chạm pymupdf -- `open_pdf` mở tệp, `PdfPages` đếm
trang, đọc chữ và **dựng một trang thành PNG** -- còn `probe.py` giữ **chính sách** — hai ngưỡng `_MIN_CHARS_PER_PAGE = 100`,
`_MIN_READABLE_PAGE_RATIO = 0.10`, và `Finding`. Seam check đổi **một đường dẫn**, `AGENTS.md` của
service đổi **một dòng**.

Không nới seam thành hai file: luật *"đúng một module được import"* grep được, luật *"một danh sách
ngắn được import"* thì mục dần.

## Decision: nhãn vàng và `data/` đều không commit

Nhãn vàng là **50 trang Lớp 6 tập 1**, do **ba subagent đánh song song** (người dùng chốt
10/10/2026 — đây là lời xin phép gọi subagent đã được trả lời trước).

Nhãn **không commit**, và `data/` vào `.gitignore`. Lý do dứt điểm: nhãn vàng **vô dụng khi không có
`data/`**, mà `data/` thì sẽ không bao giờ commit — 14 cuốn SGK có bản quyền, 1 561 trang ảnh. Nên
một bộ nhãn trong git chỉ là 75 KB chữ nguyên văn SGK nằm trong repo mà không ai chạy lại được bằng
nó. Thứ **commit** là: mã benchmark, mã thước đo, test của thước đo, và **bảng số** trong `Status`
của plan này.

Hệ quả phải nhận: `.\dev.ps1 check` **không** chạy benchmark. Lưới trong `check` là test của thước
đo — chúng dùng dữ liệu tự dựng và không cần `data/`.

## Files

| File | Việc |
|---|---|
| `docs/plans/backlog.md` | hai mục nợ mới: 3b (Jev → hierarchy) và 3c (sympy) |
| `docs/plans/active/2026-10-07-doc-pdf-vao-ngu-canh-plan.md` | bảng *Bảy plan* thành **chín**: hàng 3 vỡ làm 3a/3b/3c, kèm một dòng nói vì sao |
| `.gitignore` | thêm `data/` |
| `services/document/src/document/pdf.py` | **mới.** Module duy nhất import pymupdf; `open_pdf`, `PdfPages.text_lengths`, `PdfPages.render`, `PdfUnreadable` |
| `services/document/src/document/probe.py` | bỏ `import pymupdf`, gọi `pdf.py`; hai ngưỡng và `Finding` ở lại |
| `services/document/src/document/ocr/model.py` | **mới.** `BlockKind`, `BBox`, `PageBlock`, `PageRead` |
| `services/document/src/document/ocr/layout.py` | **mới.** PP-DocLayout → khối + nhãn + bbox + thứ tự đọc |
| `services/document/src/document/ocr/textline.py` | **mới.** PP-OCRv5 detector → hộp từng dòng trong một khối |
| `services/document/src/document/ocr/recognize.py` | **mới.** VietOCR trên từng crop dòng |
| `services/document/src/document/ocr/formula.py` | **mới.** PP-FormulaNet → LaTeX |
| `services/document/src/document/ocr/page.py` | **mới.** Ghép: render → layout → (dòng \| công thức) → `PageRead` |
| `services/document/src/document/config.py` | thêm `ocr_model_dir`, `ocr_dpi`, `ocr_use_mkldnn` |
| `services/document/pyproject.toml` | khai bốn dependency mới |
| `services/document/AGENTS.md` | một dòng: seam pymupdf đổi chủ; một dòng: model tải sẵn, không tải lúc chạy job |
| `tools/check_contract.py` | seam pymupdf trỏ `pdf.py` |
| `tools/ocr_bench/score.py` | **mới.** CER, WER, tỉ lệ lỗi dấu (dóng từng ký tự), chuẩn hoá + so LaTeX, nhãn khối, nghịch thế thứ tự đọc |
| `tools/ocr_bench/gold.py` | **mới.** Đọc và **kiểm** một file nhãn; nhãn méo thì đỏ chứ không âm thầm bỏ qua |
| `tools/ocr_bench/run.py` | **mới.** Chạy 50 trang, cache, in bảng, ghi báo cáo |
| `tools/tests/test_score.py` | **mới.** Lưới của thước đo, chạy trong `check`, không cần `data/` |
| `tools/tests/test_gold.py` | **mới.** Lưới của bộ kiểm nhãn |
| `pyproject.toml` | thêm `tools/tests` vào `testpaths`, `tools` vào `[tool.ruff] src` và vào `pythonpath` |
| `services/document/tests/test_layout.py` | **mới.** Lưới cho gỡ trùng và thứ tự đọc |
| `dev.ps1` | một task `ocr-bench` |

Nhãn vàng và cache nằm ngoài git: `data/gold/L6T1_p###.json`, `data/gold/img/`, `data/cache/`.

## Ordered Tasks

- [x] **Task 0 — ghi nợ 3b và 3c vào `backlog.md`**, và vỡ hàng 3 của file ô thành ba. Không chạm
      code; nó đi trước mọi thứ khác để hai thiết kế vừa bàn không phải dựng lại từ đầu.
- [x] **Task 1 — `document/pdf.py` và `PdfPages.render`.** Tách pymupdf khỏi `probe.py`; đổi seam
      check; đổi một dòng `AGENTS.md`. Test đo ở **72 DPI** chứ không 200 như bản đầu của plan:
      ở 72 thì một điểm của PDF thành đúng một điểm ảnh, nên kích thước ảnh **là** khổ trang theo
      điểm -- phép kiểm trực tiếp nhất cho việc `dpi` được hiểu là *điểm ảnh mỗi inch*. Một test
      thứ hai nhân đôi DPI để ghim tỉ lệ thuận, vì một bản cài `dpi` thành hệ số phóng cố định
      vẫn qua được test kia.
- [x] **Task 2 — bộ nhãn vàng, 50 trang.** Render 50 trang đầu `Kết nối tri thức Lớp 6 tập 1.pdf` ra
      PNG 2× vào `data/gold/img/`; **ba subagent** đánh nhãn song song, mỗi con một lát; `gold.py`
      kiểm từng file. Hình dạng một file nhãn:
      ```json
      {"book": "L6T1", "page": 5,
       "blocks": [{"kind": "doc_title", "text": "TOÁN 6"},
                  {"kind": "text", "text": "Trên tay các em là cuốn..."},
                  {"kind": "formula", "latex": "\\frac{1}{2}+\\frac{1}{3}"},
                  {"kind": "number", "text": "5"}]}
      ```
      **Không đòi bbox.** Người đánh nhãn cho **nhãn + thứ tự đọc + nội dung**; IoU không nằm trong
      bộ đo, và nói ra điều đó ở đây để không ai đi tìm nó sau.
- [x] **Task 3 — thước đo, và test của nó.** `score.py`: chuẩn hoá NFC trước mọi phép so (nếu không
      thì `ế` dựng sẵn và `ế` tổ hợp đếm thành hai ký tự khác nhau), CER + WER bằng Levenshtein,
      **tỉ lệ lỗi dấu** tính riêng (chính phép đo đã lột được lỗ từ điển của paddle), LaTeX chuẩn hoá
      trước khi so (bỏ `\;` `\ ` `{}` dư, gom khoảng trắng), nhãn khối so bằng chuỗi nhãn, thứ tự đọc
      đếm số nghịch thế. Test đi trước mã, dữ liệu tự dựng.
- [x] **Task 4 — `ocr/layout.py`.** PP-DocLayout: ảnh → `list[PageBlock]` có nhãn, bbox, thứ tự đọc.
      **Một lời hứa của bản đầu đã bị rút**, chứ không phải đã làm: *"model đọc từ `ocr_model_dir`,
      không tải lúc chạy"*. Hoá ra PaddleX có cache riêng của nó (`~/.paddlex/official_models/`) và
      VietOCR cũng vậy, nên một `ocr_model_dir` của ta chỉ là một lớp vỏ thứ hai trên một cơ chế đã
      có. Việc **thật** đằng sau lời hứa ấy -- nạp sẵn model lúc khởi động thay vì tải giữa một job
      -- là việc của `on_startup` của worker, và plan 3a cố ý chưa nối đường job nào. Nó đi cùng
      plan 3b.
- [x] **Task 5 — `ocr/textline.py` + `ocr/recognize.py`.** Detector paddle cho hộp từng dòng bên
      trong một khối `text`; VietOCR đọc từng crop; ghép lại theo thứ tự trên-xuống.
- [x] **Task 6 — `ocr/formula.py`.** PP-FormulaNet trên khối `formula` → LaTeX.
- [x] **Task 7 — `ocr/page.py` và `PageRead`.** Ghép cả bốn bước; một `PageRead` mang
      `page`, `blocks`, và `seconds` tách theo chặng (render / layout / detect / recognize / formula).
- [x] **Task 8 — bộ chạy benchmark.** `run.py` chạy 50 trang, **cache kết quả engine thô** xuống
      `data/cache/` để một lượt tính điểm lại là tức thì; in bảng; ghi báo cáo. `dev.ps1 ocr-bench`.
- [ ] **Task 9 — KHÔNG CHẠY.** Đích chạy thật là VPS chỉ có CPU (người dùng chốt 11/10/2026), và
      oneDNN chỉ cứu 29% thời gian thuộc ba chặng paddle, không chạm 71% của VietOCR. Xem `Status`.
      ~~Một container dùng một lần, cùng 6 trang mẫu, `enable_mkldnn=True`. Đây là biến duy nhất
      đang quyết đường local sống hay chết, và nó chưa được đo trên đúng nền.~~
- [x] **Task 10 — chốt số cổng, ghi `Status`.** Bảng số thật vào plan; cái nào trượt ngưỡng thì nói
      ra và ghi nợ, không hạ ngưỡng cho khớp.

## Validation Checks

Cổng của 3a, đề nghị — **số này chốt trước khi đo**, không phải sau:

| Thước | Ngưỡng |
|---|---|
| CER chữ Việt, trung vị trên 50 trang | **≤ 5%** |
| CER, p90 | **≤ 10%** |
| Tỉ lệ lỗi dấu | **≤ 2%** (lỗ từ điển paddle nằm ở đây; nó phải chết hẳn) |
| Công thức khớp đúng từng ký tự | **≥ 60%** |
| Công thức, khoảng cách sửa chuẩn hoá, trung vị | **≤ 0,15** |
| Nhãn khối đúng | **≥ 90%** |
| Giây/trang, trung vị, máy này, oneDNN tắt | **≤ 10** |
| Giây/trang trên Linux, oneDNN bật | **đo và ghi lại** — chưa đặt ngưỡng vì chưa có số |

Cộng: `.\dev.ps1 check` · `test` · `typecheck` xanh. Seam check mới phải **đỏ** khi thêm một dòng
`import pymupdf` vào `ocr/page.py` — thử một đột biến một dòng rồi hoàn lại.

**1 561 trang là 4–16 giờ** ở nhịp hiện tại. Con số ấy **không phải cổng của 3a** — 3a chỉ phải trả
lời *đọc đúng tới đâu và nhanh tới đâu*. Nó là dữ kiện cho một quyết định ở 3b: OCR cả bộ một lần rồi
cache, hay OCR theo yêu cầu từng chương.

## Review Focus

Năm hình thế mà không task nào ở trên tự nhiên chạm tới, và mỗi cái đã được gắn vào task sở hữu nó:

1. **Một trang chỉ có ảnh, không chữ nào.** Bìa, trang phụ bản. `read_page` phải trả `blocks` rỗng
   hoặc một khối `image`, **không được ném**. → test ở Task 7.
2. **Layout trả 0 khối.** Trang nhiễu, trang trắng. Đường đi tiếp phải là một `PageRead` rỗng có
   `seconds`, không phải một `IndexError` ở vòng lặp sau. → test ở Task 4.
3. **Detector gộp hai dòng vào một hộp.** VietOCR nhận một dòng; cho nó hai dòng thì nó trả rác mà
   không báo. Cần một chốt theo chiều cao hộp so với chiều cao dòng trung vị của trang. → test ở
   Task 5.
4. **PP-FormulaNet trả LaTeX rỗng, hoặc trả chữ thường thay vì toán.** Khối vẫn phải ở lại
   `PageRead` với `latex=None` và chữ OCR dự phòng, vì 3c cần biết **có một công thức ở đây mà chưa
   đọc được** — khác hẳn *không có công thức nào*. → test ở Task 6.
5. **`data/` không có mặt.** Trên một máy sạch `run.py` phải chết bằng một câu người đọc hiểu được và
   mã thoát khác 0; `check` thì **không được** nhắc tới nó. → test ở Task 8.

Một thứ nữa, đã đo và không phải suy đoán: **PP-FormulaNet đọc sai `P(x)=R(x)-C(x)` thành
`P(x)=P(x)-C(x)`**. Đây là ca mà 3c **không bắt được bằng sympy**, vì nó là một *định nghĩa*, không
phải một đẳng thức đúng. Nó không thuộc phạm vi 3a; nó đã được ghi vào nợ 3c ở `backlog.md` để lưới
cho nó được thiết kế đúng chỗ — so với **ảnh**, không so với **toán**.

## Ngoài phạm vi, và vì sao

- **Nối OCR vào arq, và Mongo.** Người dùng chốt để sang 3b. Hình dạng cái được lưu do cây quyết.
- **`document/storage.py` thêm `put`.** Không. Nó chỉ đọc có chủ ý, và 3a không cần ghi gì.
- **Đường ONNX thuần** (`onnxruntime` + model ONNX, nhẹ hơn 30 lần). Người dùng đã gạt; chưa đo lần
  nào, và nửa đường phát hiện PP-FormulaNet không có bản ONNX là một lượt làm lại.
- **Sửa dấu cách tiếng Việt bị mất** khi trích xuất text layer (`"Nghiệp vụcủa hệthống"`, 164 chỗ /
  32 484 ký tự). Đó là lỗi của **đường text layer**, mà 14 cuốn SGK không có text layer, nên nó không
  chạm đợt này. Nợ ấy vẫn nằm trong Decision Record của file ô.
- **Dọn hai venv thử nghiệm** ở `C:\Users\Admin\AppData\Local\Temp\ocrprobe` (984 MB) và `...\ocrvi`
  (~900 MB). Sẽ xoá khi `pyproject.toml` của service cài được và benchmark chạy xanh; giữ tới lúc ấy
  để khỏi cài lại. Không file nào của repo bị đụng.
- **Đổi `aiafa:grading` cho đúng tên**, nâng cap dòng `AGENTS.md`, và mọi món nợ cũ của `backlog.md`.
  Không mở trong lượt này.

## Status

**Task 0** xong 10/10/2026: `backlog.md` nhận hai mục nợ mới (3b và 3c), bảng của file ô thành
**chín plan**, `data/` vào `.gitignore`.

**Task 1** xong 10/10/2026, và review của nó bắt được một **hồi quy thật** -- đáng ghi lại vì hình
dạng của nó sẽ quay lại. Bản đầu của `text_lengths` gọi `len(self)` ngay trong `except` của chính
nó, tức gọi lại đúng phép toán vừa hỏng; exception mới thay chỗ exception cũ, `PdfUnreadable`
không bao giờ được dựng, và `probe()` **ném ra ngoài** -- phá hợp đồng *"không bao giờ ném"* mà ba
chỗ cùng hứa, nên chip đứng mãi ở *đang xử lý* qua hết lượt thử lại của arq. Tệp kích hoạt nó là
một PDF có `/Pages` khai `Count 5` trong khi `Kids` rỗng, đúng hình dạng một dây chuyền máy quét
để lại -- cùng loại máy đã sinh ra 14 cuốn trong `data/`.

Bài học, và nó rộng hơn bản vá: **một dòng log trong `except` là code chạy được**, nên nó phải
chịu cùng một câu hỏi *"cái này có ném không"* như mọi dòng khác. Nó trông vô hại vì nó chỉ ghi
chữ.

Cùng lượt ấy vá thêm ba lỗ cùng loại -- một thứ sai mà trông như một thứ đúng: `len()` trên tài
liệu đã đóng ném `ValueError` thô thay vì lỗi có kiểu; `render(-1)` âm thầm dựng **trang cuối**
vì `pymupdf` nhận chỉ số âm; `render(dpi=0)` và `dpi` âm trả về một ảnh sai mà không kêu gì.

Sáu đột biến một dòng, sáu cái cùng chết: bỏ `book.close()`, bỏ chặn chỉ số âm, bỏ chặn `dpi`, và
bỏ từng nhánh dịch lỗi trong `__len__` / `text_lengths` / `render`. Trước lượt review thì bốn
trong sáu cái ấy **sống sót**.

Cổng sau Task 1: `check` 20/20, `test` xanh (`services/document` + `tools/tests` = 44), `typecheck`
xanh.

**Task 2** xong 10/10/2026. Ba subagent đánh nhãn song song ba lát (1–17, 18–34, 35–50), **50
trang, 1 339 khối**. Hai phép đo đi ra từ chính bộ nhãn, và cả hai là dữ kiện cho plan 3b:

- **Số trang in lệch số trang PDF đúng 1, ở cả 48 trang có số.** Hai trang đầu -- bìa và trang tên
  sách -- thật sự không in số. Nên nhãn `number` của PP-DocLayout là một tín hiệu dùng được để nối
  trang tệp với trang sách, không phải một phỏng đoán.
- **Ba người đánh ba lát thì lệch quy ước nhau**, và họ tự báo trước khi đo xác nhận. Ba chỗ, đã
  chuẩn hoá về một: tiêu đề bài (huy hiệu tròn `BÀI 5` và tên bài là **hai vùng** riêng trên giấy
  -- soi ảnh p018 -- nên 9 khối gộp được tách, kèm một dấu chấm không in trên giấy bị gỡ); `BÀI TẬP`
  là `paragraph_title` chứ không `doc_title` (4 khối); và 20 glyph đầu dòng trang trí (`•`, `▪`)
  bị gỡ cho khớp hai lát kia.

**Bài học đáng giữ cho mọi lần đánh nhãn song song sau này:** chia việc cho nhiều người thì phải
chốt quy ước **trước**, và phải có một phép soi chạy được sau đó -- vì một bộ nhãn lệch với chính
nó mang theo nhiễu nằm đúng ở chỗ ta muốn đo.

**Task 3** xong 10/10/2026, và lưới của nó bác một giả định của chính nó. Bản đầu của thước đo lỗi
dấu lấy **hiệu** của CER và CER-sau-khi-gỡ-dấu, dựa trên giả định rằng một engine thủng từ điển sẽ
nhả ra chữ trần. Test đỏ ngay: PaddleOCR **xoá hẳn** nguyên âm có dấu -- `Kết nối` ra `Kt ni`, không
phải `Ket noi` -- nên gỡ dấu ở cả hai phía không làm hai chuỗi gần nhau, và hiệu ấy bằng **0** ở đúng
ca nó sinh ra để bắt. Bản thay thế dóng từng ký tự, không giả định gì.

Con số biện hộ cho việc thước này tồn tại: một engine đánh rơi **toàn bộ** dấu chỉ ăn **CER 0,20** --
trông như *"hơi kém"* -- trong khi tỉ lệ lỗi dấu là **1,00**. Một trang tiếng Việt chỉ có chừng một
phần tư ký tự mang dấu, nên CER một mình không bao giờ kêu to được về chiều hỏng này.

Cổng sau Task 3: `check` 20/20, 64 test của `services/document` + `tools` xanh.

**Review Task 2+3** (10/10/2026) tìm ra một lỗi mà bộ đo **tự tay cho điểm tối đa cho một bản
đọc sai**: regex gỡ `\left`/`\right` không neo ranh giới lệnh, nên nó cắt cả `\leftarrow` và
`\rightarrow` thành `arrow` -- hai mũi tên **ngược chiều nhau** khớp nhau hoàn toàn, và nó đang nổ
trên chính nhãn vàng (`L6T1_p026`, khối 27). Ba lỗi đo sai khác cùng lượt: khoảng trắng kép trong
nhãn bắt một engine đọc đúng tuyệt đối trả một CER **sàn** (lát B 0,42%, gấp ba mươi lần lát C,
nên mọi so sánh giữa ba lát là so cách gõ của ba người); `match_blocks` lấy mẫu số là độ dài nhãn
nên khối một hai ký tự không chịu nổi một phép sửa nào, và **cả 48 khối `number`** -- chính thứ
dùng để nối trang PDF với trang in -- rơi khỏi mọi phép ghép mà không ô nào nói ra; và thước lỗi
dấu mù với dấu **thêm vào**, nên `"Toan hoc"` đọc thành `"Toán học"` ăn 0,0.

Review cũng chạy 18 đột biến và **8 sống sót**. Ba cái đáng kể đã có lưới: hằng số ngưỡng ghép khối
(test cũ mang tên *một nửa* mà đo một chuỗi chỉ rụng dấu, giống nhau trên 0,9); `align` thiếu NFC;
và mẫu số của `wer`. Cộng hai chỗ nhãn vàng còn lệch -- huy hiệu `HĐn` (7 khối lát A) và `...` với
`…` (9 chỗ) -- đã chuẩn hoá, và hai chuỗi phân số ở `p048` chép thành `18 : 6/30 : 6`, đọc ra một
biểu thức **khác hẳn** thứ in trên giấy, đã sửa thành `(18 : 6)/(30 : 6)`.

**Một chỗ cố ý chưa sửa, nói ra để không ai tưởng nó đã xong:** lát C không bao giờ dựng khối
`formula` cho những dòng phân số xếp tầng, trong khi lát A và B thì có. Sửa nó đòi đánh nhãn lại 16
trang, và cái giá ấy chỉ đáng trả khi bộ đo đã chạy và cho biết nó thật sự đổi con số bao nhiêu.

**Task 4** xong 10/10/2026. PP-DocLayout chạy **4,5 giây một trang** với oneDNN tắt -- so với 37
giây của PP-StructureV3, vì nó không kéo theo OCR. Nhưng nó không làm hai việc, và cả hai đo được
trên trang 18:

- **Hộp trả về sắp theo điểm tin cậy, không theo thứ tự đọc.** Thứ tự đọc là thứ plan 3b dựa vào,
  nên nó phải được dựng ở đây. Bản đầu gom theo hàng và **sai**: hai hộp *KHÁI NIỆM* và *KIẾN THỨC*
  đặt cạnh nhau bị đọc đan xen từng dòng, mà hình dạng ấy mở đầu **mọi** bài trong sách. Thay bằng
  **XY-cut** cắt theo khe trắng rộng nhất: trong vùng hai hộp, khe dọc giữa hai cột là 66 điểm ảnh
  còn khe ngang rộng nhất giữa hai dòng là 19, nên nó cắt dọc và đọc hết hộp trái trước.
- **Hộp trùng nhau mang hai nhãn khác nhau.** Đúng hình chữ nhật `[322, 1130, 777, 1164]` ra hai
  lần: một `text` 0,63 và một `formula` 0,56.

Và một ràng buộc runtime phải ghi lại vì nó không có trong tài liệu nào: **torch phải nạp trước
paddle.** `import torch, paddle` chạy; `import paddle, torch` ném `OSError [WinError 127]` ở
`shm.dll`. Dòng `import torch` nằm ở `document/ocr/__init__.py` -- chỗ duy nhất chắc chắn chạy
trước mọi module con -- và có một test canh nó.

Cổng sau Task 4: `check` 20/20, `test` 524 pytest + 186 vitest xanh.

**Task 5–8** xong 10/10/2026: `textline.py` + `recognize.py` + `formula.py` + `page.py` + bộ chạy
`tools/ocr_bench/run.py`. Review của lượt ấy bắt bốn chỗ, cả bốn là *một thứ sai trông như một thứ
đúng*: ngưỡng điểm 0,60 cắt mất **chữ thật** (*"Giải"* 0,550, *"Vì 18 ⋮ 6 nên ta có"* 0,521) mà
không chặn được khối rác nào trên mười trang, nên hạ về 0,50; phép gỡ trùng một chiều **xoá khối
`formula` lồng trong khối `text`** của câu chứa nó, tức hạ cấp công thức thành chữ **trước khi**
chặng đọc công thức được gọi, nên `latex=None` mà plan 3c dựa vào không bao giờ xuất hiện; số trang
bị XY-cut coi là một cột và đọc ra giữa trang; và 1 200 hộp xếp bậc thang làm vỡ stack.

Hai test của chính tôi **không canh gì cả**, và review chứng minh bằng đột biến: test gỡ trùng dùng
điểm 0,63/0,56 mà 0,56 dưới ngưỡng, nên hộp thứ hai bị loại từ trước và chưa bao giờ tới được phép
gỡ trùng -- đặt `_COVERED` thành 1,01 hay 0,05 thì cả mười test vẫn xanh; và test thứ tự nạp torch
khẳng định `"torch" in sys.modules`, điều mà `paddleocr` tự làm đúng, nên xoá hẳn dòng cần canh thì
test vẫn xanh. Bản thay thế đọc **cây cú pháp** của `__init__.py`.

### Bảng số thật, 50 trang Lớp 6 tập 1 (Task 10, đo 11/10/2026)

Máy này, CPU, oneDNN tắt, 200 DPI, `vgg_transformer`. **Cả bảy cổng trượt.**

| Thước | Ngưỡng | Đo được | |
|---|---|---|---|
| CER trung vị | ≤ 5% | **22,0%** | trượt 4,4× |
| CER p90 | ≤ 10% | **36,9%** | trượt 3,7× |
| Lỗi dấu | ≤ 2% | **16,2%** | trượt 8,1× |
| Công thức khớp đúng | ≥ 60% | **8,9%** | trượt 6,7× |
| Công thức, khoảng cách sửa, trung vị | ≤ 0,15 | **0,722** | trượt 4,8× |
| Nhãn khối đúng | ≥ 90% | **70,7%** | trượt |
| Giây/trang, trung vị | ≤ 10 | **128,6** | trượt 12,9× |

Cộng: WER trung vị 0,334 · p90 0,509 · 13 công thức nhãn vàng có mà engine không trả về khối nào ·
tổng 6 083 giây cho 50 trang.

Phân rã theo chặng, và nó chỉ đúng **một** chỗ tốn tiền:

| Chặng | s/trang | Phần |
|---|---|---|
| recognize (VietOCR) | **87,2** | **71%** |
| detect (PaddleOCR) | 26,1 | 21% |
| formula | 1,9 | 5% |
| layout | 3,7 | 3% |
| render | 0,2 | 0% |

**Không hạ ngưỡng nào cho khớp.** Bảy cổng ấy ở lại nguyên số, và phần dưới là chẩn đoán vì sao
trượt, vì *trượt* và *trượt vì cái gì* là hai câu khác nhau.

### Bốn nguyên nhân, và ba trong bốn là lỗi code chứ không phải giới hạn engine

**1. Tốc độ: đo trên cấu hình sai.** `torch==2.14.1` và `paddlepaddle==3.3.1` đều là wheel **CPU**,
trong khi máy có RTX 4060 Ti 16 GB (driver 595.79): `torch.version.cuda` là `None`,
`paddle.is_compiled_with_cuda()` là `False`. Và 71% thời gian nằm ở `vgg_transformer` -- giải mã
**tự hồi quy từng token**, tức vòng lặp tuần tự thuần, hình dạng tệ nhất cho CPU.

**2. Định tuyến sai, và nó âm thầm.** Engine trả **121** khối `formula`; nhãn vàng có **58**. 63
khối bị gửi sang PP-FormulaNet thay vì VietOCR, và chữ của chúng rơi khỏi bảng điểm. `latex=None`
xuất hiện **0 lần** trên 121 khối, nên không gì báo động -- PP-FormulaNet luôn trả về một chuỗi
trông hợp lệ cho một câu văn. Bỏ các khối định tuyến sai ra thì CER tụt **22,0% → 13,2%** và lỗi dấu
**16,2% → 7,1%** (621 khối `text`↔`text` ghép được).

Hai lệch nhãn cùng loại: nhãn vàng có 49 khối `aside_text` và 8 khối `table_title`, engine trả về
**0** cái nào của cả hai.

**3. Crop cắt mất dấu.** `recognize.py` cắt đúng hộp detector, **không đệm một điểm ảnh nào** --
trong khi dấu tiếng Việt nằm **ngoài** thân chữ (dấu thanh trên, dấu nặng dưới, râu ư/ơ bên). Và
`split_tall_lines` chia hộp hai dòng thành hai dải **bằng nhau**, tức cắt ngang đúng vùng dấu. Đo
11/10/2026 trên ba trang (18, 33, 46), cùng layout cùng detect, chỉ đổi phần đệm:

| Đệm | CER trung vị | Lỗi dấu trung vị |
|---|---|---|
| 0% | 0,111 | 0,083 |
| **15%** | **0,054** | **0,023** |
| 30% | 0,049 | 0,029 |

Đệm 15% **cắt một nửa CER và gần ba phần tư lỗi dấu**, bằng một thay đổi hai dòng, và nó đưa cả hai
về gần đúng cổng (≤5% và ≤2%). 30% thì CER nhích thêm nhưng lỗi dấu xấu lại, nên 15% là chỗ tối ưu.

Kết luận quan trọng nhất của cả lượt đo: **VietOCR không phải thứ sai.** Nó đọc tốt; code của tôi
đưa cho nó ảnh đã bị cắt mất dấu. Quyết định *paddle + VietOCR* đứng được về **độ chính xác**.

**4. Mù hẳn với hai lớp trang.** Trang mục lục (p005): nhãn vàng 15 khối (`table_title` + `table`
xen kẽ), engine trả về **đúng một khối `number`** -- CER 0,996 là thật, engine không đọc được gì.
Trang bìa (p001): nhãn vàng `text`/`doc_title`/`image`, engine gán `header`/`header`/`image`/
`footer`/`footer`, sai hết. Đây đúng là món nợ *"PP-DocLayout mù với trang mục lục, và không gì báo
động"* đã ghi ở `backlog.md`, nay có số.

### Một chỗ bộ đo tự nó đang đo lẫn hai thứ

`label_accuracy` tính khoảng cách sửa trên **dãy nhãn**, nên nó đo **phân đoạn** lẫn với **gán
nhãn**. p048 có 24 khối nhãn vàng và 45 khối engine; chỉ riêng chênh lệch độ dài đã ăn hết điểm, và
0,000 ở đó là thật nhưng không nói được engine gán nhãn sai bao nhiêu. Cần hai thước riêng. Ghi
thành nợ, **không** sửa thước giữa lúc đang báo cáo số của chính nó.

### Task 9 không chạy, và plan 3a dừng ở đây

Người dùng chốt 11/10/2026, sau khi đọc bảng trên, hai điều:

- **Đích chạy thật là VPS chỉ có CPU.** Nên đường GPU không được mở, và Task 9 -- đo oneDNN trên
  Linux -- mất phần lớn ý nghĩa: oneDNN chỉ cứu ba chặng paddle (29% thời gian), không chạm 71% của
  VietOCR vì nó chạy trên torch. Máy này có 20 luồng; một VPS rẻ có 2–4, nên 128,6 giây/trang trên
  đó sẽ **xấu hơn**, không tốt hơn.
- **Dừng 3a, xem lại cả lựa chọn engine.** Không sửa thêm gì.

Nên lý do thật để xem lại engine là **tốc độ trên CPU**, không phải độ chính xác -- phép đo đệm crop
ở trên đã loại độ chính xác khỏi danh sách nghi vấn.

### Nợ của 3a, để lượt sau không phải đo lại

1. **Đệm crop 15%** trong `recognize.py` và `formula.py`. Đã đo, chưa implement. Hai dòng, cắt một
   nửa CER.
2. **`split_tall_lines` cắt giữa vùng dấu.** Chia bằng nhau là sai; chỗ cắt phải tìm theo hình chiếu
   ngang của nét mực, không theo trung điểm.
3. **Định tuyến `formula` quá rộng, gấp hơn hai lần.** Và nó mất **im lặng** vì PP-FormulaNet luôn
   trả về chuỗi. Khối `formula` phải **cũng** được VietOCR đọc, rồi một phép so quyết cái nào giữ --
   không phải một nhánh `if/else` loại trừ nhau như hiện tại.
4. **`aside_text` và `table_title` không bao giờ được trả về.** 57 khối nhãn vàng không có đối ứng.
5. **Trang mục lục và trang bìa trả về gần như rỗng**, và không gì báo động. Cần một chốt kiểu *một
   trang có nhiều dòng detect được mà layout chỉ ra một khối thì đó là một lỗi, không phải một kết
   quả*.
6. **`label_accuracy` đo lẫn phân đoạn với gán nhãn.** Tách thành hai thước.
7. **Lát C của nhãn vàng không dựng khối `formula` cho phân số xếp tầng**, trong khi lát A và B có.
   16 trang. Giờ đã có số để biết nó đáng sửa: phần công thức trượt cổng 6,7×, nên nhiễu nhãn ở đúng
   chiều ấy không còn là chuyện nhỏ.
8. **Hai venv thử nghiệm** còn ở `C:\Users\Admin\AppData\Local\Temp\ocrprobe` (984 MB) và `...\ocrvi`
   (~900 MB).

Cổng kỹ thuật trước khi dừng: `.\dev.ps1 check` 20/20, `test` 537 pytest + 186 vitest, `typecheck`
xanh. Chưa commit gì.

### 3a mở lại, 11/10/2026: ưu tiên tốc độ, và hai lựa chọn nhận dạng chữ

Người dùng đổi ưu tiên sau khi xem bảng trên: *"thứ chúng ta ưu tiên là tốc độ hơn, vì sau này
context sẽ được đưa vào LLM, một vài chữ sai sẽ không ảnh hưởng nhiều"*, trên **VPS chỉ có CPU**.
Rồi chốt ba điều: **giữ paddle** (layout sẽ cần), **vẫn OCR ra LaTeX** (sympy thì chưa), và
**EasyOCR đứng cạnh VietOCR làm hai lựa chọn**, không thay nó.

**Thước mới cho câu hỏi mới.** CER phạt thứ tự đọc, mà LLM thì không cần thứ tự từng chữ. Nên
thước chính là **thiếu từ**: tỉ lệ từ của nhãn vàng không có mặt nguyên dạng trong bản đọc, túi từ
có đếm, giữ dấu (`score.missing_words`). Ngưỡng làm việc: **≤ 10%**. Đo mô phỏng VPS ở **4 luồng**.

**Đo 11/10/2026 trên 10 trang** (5, 7, 12, 18, 24, 29, 33, 38, 42, 46), cùng detector paddle, đệm
15%:

| Chặng / lựa chọn | Kết quả |
|---|---|
| Nhận dạng `easyocr` | thiếu từ 8,9%, thừa/sai 13,0% |
| Nhận dạng `vietocr` `vgg_seq2seq` | thiếu từ 7,3%, thừa/sai 17,9% |
| Nhận dạng `vietocr` `vgg_transformer` | thiếu từ 9,2% -- vừa chậm hơn vừa sai hơn seq2seq |
| Detector `PP-OCRv5_mobile_det` / `PP-OCRv6_medium_det` | 0,5 / 4,0 s, thiếu từ 7,3% / 7,1% |
| Layout `PP-DocLayout_plus-L` | 1,8 s. Bản `-M` / `-S` nhanh hơn nhưng gần như **không tìm ra công thức** |
| Công thức `PP-FormulaNet_plus-S` / `plus-M` | 0,4 / 1,4 s; khớp đúng 24% / 6%, khoảng cách 0,297 / 0,595 (17 công thức) |

**Vì sao VietOCR thua EasyOCR ở thiếu từ**, đo chứ không đoán. Hai giả thuyết đầu **bị bác**:
hộp dính hai dòng (0–1 hộp mỗi trang, cắt hay không cho cùng một số) và dòng dài bị bóp ngang
(dòng tỉ lệ 31:1 đọc gần hoàn hảo, cắt đôi còn tệ hơn vì xẻ ngang chữ). Thủ phạm thật: **số và ký
hiệu toán nằm trong dòng chữ** -- `Ư(18)`, `ƯCLN(24, 60)`, dãy `1, 3, 9`. Danh sách từ *chỉ
VietOCR thiếu* trên p046 và p038 gần như toàn là số và toán, và các dòng lặp (`1,3 1,3 1,3 …`,
`… nha nha nha`) đều là dòng có toán. VietOCR là bộ giải mã tự hồi quy huấn luyện trên văn xuôi;
EasyOCR là CTC nên về cấu trúc không lặp được. Đổi lại VietOCR giữ dấu tốt hơn. Hai kiểu hỏng
khác nhau -- đó là lý do giữ cả hai.

**Bẫy số luồng, và nó làm sai mọi số giây nhận dạng trước đó.** Torch và paddle dùng chung
OpenMP, và **mỗi lời `predict` của paddle ép torch về một luồng** (`torch.get_num_threads()`: 4 sau
`set_num_threads(4)`, 4 sau khi nạp predictor, **1** ngay sau `predict` đầu tiên). Detect chạy ngay
trước nhận dạng, nên bộ nhận dạng **luôn** chạy đơn luồng. Đo có đối chứng -- cùng trang, cùng hộp,
chỉ đặt lại luồng trước khi đọc: VietOCR p018 / p046 6,6 / 5,7 s → **2,2 / 2,5 s**; EasyOCR 3,8 /
4,6 s → **2,4 / 3,3 s**. Hệ quả cho bảng trên: số giây nhận dạng của VietOCR ở lượt so sánh đầu đo
**ở 1 luồng**, còn EasyOCR chạy trong venv không có paddle nên được đủ 4 -- tức *"EasyOCR nhanh
gấp ba"* phần lớn là lỗi đo. Sửa đúng thì hai bên gần ngang nhau. Độ chính xác không bị ảnh hưởng.

Phần lớn 128,6 s/trang của bảng Task 10 cũng rơi vào bẫy này. Bảng ấy ở lại nguyên số vì nó là
phép đo của cấu hình lúc đó, nhưng **không còn nói gì về tốc độ của engine**.

**Đã implement** (chưa benchmark 50 trang):

- `recognize.py`: `EasyOcrReader` cạnh `VietnameseReader`, chung giao diện `LineReader.read_lines`,
  chọn bằng `make_line_reader(name)` -- tên sai thì ném **trước khi** nạp model. `padded()` đệm 15%
  cho cả hai. Cả hai **đặt lại số luồng torch ở đầu `read_lines`**. EasyOCR đọc **từng hộp một** với
  ảnh xám chuyển một lần (`reformat=False`), vì `recognize` của nó lặng lẽ bỏ hộp rỗng khỏi kết quả
  và làm lệch vị trí. VietOCR mặc định chuyển sang `vgg_seq2seq`.
- `page.py`: `PageReader(reader="easyocr" | "vietocr", threads=4)`. Mặc định `easyocr` vì ưu tiên
  tốc độ.
- `layout.py`, `textline.py`, `formula.py`: tên model **tường minh** (trước đây dùng mặc định ẩn của
  thư viện) và `cpu_threads`. Detector `PP-OCRv5_mobile_det`, công thức `PP-FormulaNet_plus-S`, layout
  giữ `plus-L`.
- `score.missing_words` + cột *thiếu* trong bảng của `run.py`; `run.py` nhận `--reader`, `--threads`,
  và tên reader nằm trong **khoá cache** để hai lựa chọn không đọc nhầm cache của nhau.
- `pyproject.toml`: `easyocr==1.7.2` (chỉ kéo thêm `ninja`; không đổi phiên bản nào của paddle).
- Test: đệm, kẹp biên, tên reader sai, **giữ vị trí** khi EasyOCR bỏ hộp, **đặt lại số luồng**
  -- hai cái sau dùng model giả cắm vào reader thật. Đột biến: bỏ đặt lại luồng ở từng reader, bỏ
  đệm, gom cả lô rồi tin độ dài -- cả bốn bị bắt. Một đột biến sống là đột biến tương đương.

Cổng sau implement: `check` 20/20, `test` 547 pytest + 186 vitest, `typecheck` xanh.

**Thứ tự còn lại, người dùng chốt:** một subagent review **tính đúng đắn** trước, *"tránh lúc
benchmark thì phát hiện lỗi sai"* -- một lượt 50 trang tốn chừng nửa giờ cho mỗi lựa chọn, và một
lỗi tìm ra sau đó là trả giá hai lần. Rồi benchmark 50 trang cho **cả hai** lựa chọn, ghi bảng số
vào đây.

**Review tính đúng đắn, 11/10/2026, trước benchmark.** Subagent chạy thật cả hai reader trên p018
và p046, đọc mã nguồn EasyOCR 1.7.2 / paddleocr 3.7.0 / VietOCR. **Không lỗi nào chặn benchmark.**
Xác nhận đúng: định dạng hộp và ảnh xám của `recognize`; mỗi hộp đúng một chuỗi; `predict_batch`
của VietOCR giữ thứ tự; paddleocr **ném** với tham số lạ nên `model_name`/`cpu_threads` không bị
nuốt im, và cả ba predictor báo `cpu_threads: 4`; torch ở 4 luồng trong 50/50 lời gọi EasyOCR và
lời gọi lô của VietOCR, về 1 sau mỗi `read_page`; khoá cache không đụng nhau. Bốn phát hiện:

1. **Số giây 2,4 / 3,3 s của EasyOCR không lặp lại được** -- reviewer đo 4,2 s cùng trang, cùng
   model; hai process chênh nhau tới 1,7 lần trên máy này. Đã gỡ cặp số khỏi docstring. Hai lượt
   benchmark chạy **liền nhau**, và cột giây đọc như chỉ dấu, không như hằng số.
2. **Ảnh xám khác đường mặc định của EasyOCR**: nó coi mảng 3 kênh là BGR, ta chuyển bằng PIL đúng
   trọng số RGB. Ta đúng hơn, 4/50 dòng p018 đọc khác. Hệ quả: 8,9% của script thử sẽ không lặp lại
   chính xác; benchmark là số chuẩn.
3. **Docstring nêu sai lý do** đọc từng hộp: EasyOCR không bỏ hộp (với `too_small` chặn trước), mà
   **sắp lại kết quả theo trục y** khi nhận nhiều hộp. Code đúng; docstring và test đã sửa lời.
4. **Dòng nằm trong hai khối lồng nhau bị đếm hai lần** (`_text_inside` gán theo tâm, mà tâm nằm
   trong cả khối cha lẫn khối con): 2/320 dòng. Giống nhau ở cả hai lựa chọn, nên phép so đứng
   được. Thành nợ.

Nợ còn mở từ danh sách trên: định tuyến `formula` quá rộng (3), `aside_text`/`table_title` (4), trang
mục lục và trang bìa (5), `label_accuracy` đo lẫn (6), lát C nhãn công thức (7), hai venv (8). Nợ (1)
đệm crop đã trả; nợ (2) `split_tall_lines` **đóng** -- đo cho thấy gần như không có hộp dính dòng.
Nợ mới: (9) một dòng thuộc hai khối lồng nhau -- review phát hiện 4; (10) khoá cache của `run.py`
chưa mang tên model layout / detector / công thức hay `mkldnn`, nên đổi một model sau này sẽ âm
thầm đọc lại cache cũ.

### Quy ước: mỗi lượt benchmark để lại bản ghi ở `data/run-<n>/<model>/`

Người dùng chốt 11/10/2026. `run.py` ghi `report.txt` (đúng bảng in ra), `config.json` (tham số,
và **trang nào đọc mới, trang nào lấy từ cache** -- trang từ cache mang số giây của lượt cũ), và
`pages/` (kết quả engine từng trang). `<model>` là `easyocr` hoặc `vietocr-<cấu hình>`; hai lựa
chọn chạy cùng lượt thì dùng chung `--run <n>`. Bỏ `--run` thì lấy số lớn nhất cộng một, không lấp
chỗ trống. Thư mục đã có thì **dừng trước khi đọc trang nào**, không ghi đè. Nằm trong `data/`,
nên ngoài git như sách và nhãn.

`run-1` là hai lượt ngay dưới đây, ghi lại từ cache vài phút sau khi chạy -- `config.json` của nó
báo cả 50 trang *từ cache*, và đúng là vậy.

### Bảng số 50 trang, hai lựa chọn (`data/run-1`, 11/10/2026)

Chạy liền nhau trên máy rảnh, 4 luồng, 200 DPI, cùng layout / detector / công thức. Trung vị theo
trang (p90 trong ngoặc):

| Thước | Ngưỡng cũ | Task 10 (cấu hình cũ) | `easyocr` | `vietocr` `vgg_seq2seq` |
|---|---|---|---|---|
| **Thiếu từ** (thước chính) | ≤ 10% (mới) | -- | **9,3%** (16,6%) | **9,3%** (18,3%) |
| CER | ≤ 5% | 22,0% | 11,9% (30,5%) | 15,7% (36,8%) |
| WER | -- | 33,4% | 26,5% (43,3%) | 29,3% (64,8%) |
| Lỗi dấu | ≤ 2% | 16,2% | 9,8% | 12,9% |
| Nhãn khối đúng | ≥ 90% | 70,7% | 70,7% | 70,7% |
| Công thức khớp đúng | ≥ 60% | 8,9% | 6,7% | 6,7% |
| Công thức, khoảng cách | ≤ 0,15 | 0,722 | 0,766 | 0,766 |
| **Giây/trang** | ≤ 10 | 128,6 | **4,5** | **4,7** |

Phân rã giây của `easyocr`: render 0,1 · layout 1,8 · detect 0,5 · recognize 1,7 · formula 0,3.
`vietocr` giống hệt trừ recognize 2,0. **Layout giờ là chặng đắt nhất**, không còn là nhận dạng.

Đọc bảng:

- **Tốc độ đạt**, cách ngưỡng 10 s/trang hơn hai lần, nhanh gấp ~28 lần lượt Task 10. 1 561 trang
  cỡ 2 giờ trên 4 luồng.
- **Thiếu từ đạt ngưỡng làm việc ở trung vị**, nhưng p90 16–18% -- một trang trên mười mất hơn một
  phần sáu số từ. Trang tệ nhất vẫn là p005 (mục lục, 0,981), nợ (5).
- **EasyOCR bằng hoặc hơn VietOCR ở mọi thước**, nên nó là mặc định.
- **Nhãn khối và công thức** không đổi vì chúng thuộc layout và PP-FormulaNet, không thuộc phần vừa
  sửa. Cả hai vẫn trượt ngưỡng xa, và công thức là phần yếu nhất của cả đường.

**Hai nhận định của chính lượt này bị số 50 trang bác**, ghi ra để không ai dựa vào chúng:

1. *"VietOCR giữ dấu tốt hơn"* -- chưa từng được đo đối đầu; 50 trang cho VietOCR 12,9% lỗi dấu
   so với 9,8% của EasyOCR. Docstring của `recognize.py` và `pyproject.toml` đã sửa.
2. *"`plus-S` chính xác hơn `plus-M`"* -- rút từ 17 công thức trên 10 trang. Đo **đối đầu** 50 trang,
   cùng hộp layout, 58 công thức, ghép gần nhất: `plus-S` khớp 10,3% / khoảng cách 0,644, `plus-M`
   13,8% / 0,608, và `plus-M` **chậm hơn 3,7 lần** (156 s so với 42 s). Ghép theo thứ tự như `run.py`
   cho cùng chiều: 6,7% so với 8,9%. Giữ `plus-S` làm mặc định **vì tốc độ**, và docstring giờ nói
   đúng như thế. Đây là chỗ người dùng có thể muốn quyết khác.

Nợ mới: (11) **công thức là phần yếu nhất của đường**, khớp đúng dưới 14% với cả hai model. Chưa
chẩn đoán: có thể là định tuyến (nợ 3), có thể là thước ghép theo thứ tự của `run.py`, có thể là
model. Cần làm rõ trước khi plan 3c dựa vào LaTeX.

### Chẩn đoán công thức: lỗi của ai (11/10/2026)

Nợ (11) được chẩn đoán bằng một trang review dựng từ kết quả 50 trang (`data/run-1/formulas/`,
ngoài git vì là ảnh SGK), sau hai lượt subagent đọc ảnh chụp. 58 công thức nhãn vàng:

| Kết luận | Số | Lỗi của ai |
|---|---|---|
| Model đọc sai phần toán | 18 | PP-FormulaNet |
| Toán đúng, chỉ sai chữ Việt | 3 | PP-FormulaNet -- không có chữ Việt trong từ điển |
| Khung cắt sai (thiếu, hoặc gộp nhiều công thức) | 9 | layout |
| Không có khối | 15 | layout |
| Cần nhìn ảnh / có thể ghép nhầm | 4 | chưa rõ |
| Đúng (kể cả chỉ lệch cách viết) | 9 | -- |

**Layout làm hỏng nhiều hơn model** (24 so với 21): 15 công thức không bao giờ tới được model công
thức. Nên không đổi model PP-FormulaNet nào cứu được, và `plus-M` chỉ hơn `plus-S` 13 so với 9 trên
40 cặp. Bài học về chính thước đo: bản đầu của trang review nhận cặp lệch tới 0,9, nên mười thẻ đỏ
đầu là **ghép nhầm hai công thức khác nhau** -- có thẻ model đọc đúng mà bị tô sai.

### Đổi hướng (người dùng chốt 11/10/2026): upload chỉ đọc chữ, công thức đọc bằng VLM lúc ra đề

> *"thay vì đọc công thức toán học và text thường cùng một lúc. chúng ta chỉ cần đọc text lúc upload
> lên. khi ra đề, tài liệu reference đến công thức nào thì sử dụng model tốt cho công thức toán nằm
> trong phần đó thôi. và để công thức toán ổn định, chúng ta dùng vlm và gọi api thay vì dùng cpu
> tự host."*

**Decision: đường upload chỉ đọc chữ.** PP-FormulaNet rời đường upload. Theo luật người dùng đặt --
*"những vị trí nào thành code chết thì dùng # để comment lại, sau này không nhầm lẫn"* -- mọi chỗ
chết được **comment, không xoá**, cùng một nhãn grep được `# [CODE CHẾT 2026-10-11]`:
`ocr/formula.py` (toàn bộ, kèm đoạn đầu file nói vì sao), `ocr/page.py` (import, `self._math`, nhánh
`FORMULA` của `_fill`, chặng `formula`), `ocr/model.py` (`PageBlock.latex`), `ocr/layout.py`,
`tools/ocr_bench/run.py` (payload `latex`, phần chấm công thức), hai file test. Khối `FORMULA` ở lại:
nó nhận chữ OCR như khối chữ, và nhãn của nó là gợi ý *trang này có toán*. `_fill` thành hàm thuần
ở cấp module (tham số `image` và `self._math` đã chết), có test. Phiên bản đường đọc vào tên cache
của `run.py` (`_PIPELINE = "text1"`) để cache của đường cũ không bị đọc lại âm thầm.

Hệ quả đo được: nạp model **24,2 s → 5–6 s**; benchmark chữ 50 trang từ cache khớp `run-1` từng số;
chạy thật vài trang thì chặng `formula` biến mất, `assign` tốn 0,0 s. Subagent review: không gì
sống bị gãy, 9 điểm nhỏ (docstring cũ, khoá cache, tham số chết, thiếu test cho `_fill`) đã sửa.

**Decision: công thức đọc bằng VLM của OpenAI, lúc ra đề, trên cả ảnh trang.** Cả ảnh trang chứ
không khung layout cắt, vì 24/58 lỗi nằm ở chính khung ấy. Lời gọi nằm ở **AGENT** (`architecture.md`:
AGENT là service gọi model; `agent/llm.py` là *"module duy nhất trong AGENT biết model của ai đang
trả lời"*), nhận byte PNG; render vẫn ở `document/pdf.py`.

### Chi phí GPT vision (11/10/2026)

Người dùng chốt: *"chỉ benchmark trên text thôi. báo cáo cho tôi chi phí gpt vision của các model
khi nào được cho phép mới benchmark trên phương trình / công thức"*. Giá lấy từ trang giá chính thức
(standard tier). Token ảnh đo bằng một **ảnh tự vẽ đúng kích thước một trang SGK ở 150 DPI**
(1140×1600) -- số token ảnh chỉ phụ thuộc kích thước, nên không phải gửi trang sách nào đi.

| Model | Token vào / trang | Token ra | $/trang | 50 trang | 1 561 trang |
|---|---|---|---|---|---|
| `gpt-6-luna` | 2 215 | 329 | 0,00039 | 0,02 | 0,60 |
| `gpt-4.1-nano` | 3 791 | 164 | 0,00044 | 0,02 | 0,69 |
| `gpt-5-nano` | 2 754 | 965 | 0,00052 | 0,03 | 0,82 |
| `gpt-5.4-nano` | 2 215 | 315 | 0,00084 | 0,04 | 1,31 |
| `gpt-5.6-luna` | 2 215 | 352 | 0,00087 | 0,04 | 1,35 |
| `gpt-4.1-mini` | 2 516 | 151 | 0,00125 | 0,06 | 1,95 |
| `gpt-5-mini` | 2 215 | 692 | 0,00194 | 0,10 | 3,02 |
| `gpt-5.4-mini` | 2 215 | 381 | 0,00338 | 0,17 | 5,27 |
| `gpt-4.1` | 1 160 | 153 | 0,00354 | 0,18 | 5,53 |
| `gpt-6-sol` | 2 215 | 110 | 0,00553 | 0,28 | 8,63 |
| `gpt-4o-mini` | **36 890** | 133 | 0,00561 | 0,28 | 8,76 |

`gpt-4o-mini` -- model chat đang dùng -- đắt nhất cho ảnh dù giá token rẻ nhất: nó tính ảnh gấp ~15
lần. Họ `gpt-5.x`/`6`/`-luna` tính cả token suy luận vào token ra. Token ra ước thấp (ảnh thử chỉ 6
công thức).

### Khảo sát 6 model trên 5 trang (`data/run-5`, 11/10/2026)

Người dùng cho phép khảo sát từ `gpt-6-luna` tới `gpt-4.1-mini` trong bảng giá, trên *"một vài công
thức"*. Năm trang gom đủ kiểu đã làm PP-FormulaNet hỏng: 8 (tập hợp, `\mathbb{N}`, chữ Việt), 17
(nhiều dòng), 23 (`\underbrace`), 26 (ngoặc lồng), 46 (`ƯCLN`, `⋮`). Cả ảnh trang, 150 DPI, structured
output. 19 công thức vàng, tổng chi phí **$0,029**.

Chấm lại công bằng -- dấu chấm nhân của sách `\,.\,` coi là `\cdot`, và một ô nhãn vàng gộp nhiều
công thức được tính *đủ* khi các mảnh model tách ra phủ đủ nó; đọc tận mắt mọi ca sai của hai model
đầu:

| Model | Đúng | Đúng, tách nhỏ | Gần | **Sai / thiếu** | Giây/trang |
|---|---|---|---|---|---|
| `gpt-5.6-luna` | 12 | 4 | 1 | **2** | 8,8 |
| `gpt-4.1-mini` | 13 | 2 | 0 | **4** | **3,4** |
| `gpt-5.4-nano` | 8 | 4 | 1 | 6 | 5,7 |
| `gpt-6-luna` | 7 | 4 | 1 | 7 | 7,8 |
| `gpt-4.1-nano` | 2 | 0 | 0 | 17 | 2,9 |
| `gpt-5-nano` | 1 | 0 | 2 | 16 | 6,7 |

Ba phát hiện quan trọng hơn bảng điểm:

1. **Không model nào đọc đúng `⋮` (chia hết).** Ba model biến nó thành `:` -- **đổi nghĩa** câu
   *"Nếu a ⋮ b thì ƯCLN(a, b) = b"* -- ba model bỏ cả công thức.
2. **Không model nào giữ `\underbrace{a·a·…·a}_{n \text{ thừa số}}`.**
3. **`gpt-4.1-nano` hỏng chuỗi JSON**: `\text` không thoát dấu `\`, nên `\t` thành ký tự tab. Cùng bẫy
   ấy biến `\frac`, `\neq` thành ký tự điều khiển. Repo đã có bước sửa thoát ký tự cho chữ model trả về
   (`check_the_model_text_passes_through_the_escape_repair`); đường VLM phải đi qua nó.

### Decision: ba model vision được dùng (người dùng chốt 11/10/2026)

> *"Đưa gpt 5.6 luna, gpt 4.1 mini và gpt 6 luna vào option sử dụng. Sau này có thêm sympy và bước tự
> dựng lại của llm, kết quả sẽ cải thiện."*

| Lựa chọn | Khi nào hợp | Đo trên 5 trang |
|---|---|---|
| `gpt-4.1-mini` | mặc định: nhanh nhất, `\mathbb{N}` đúng chuẩn | sai 4/19, 3,4 s, $0,0014/trang |
| `gpt-5.6-luna` | cần chính xác hơn, chịu chậm | sai 2/19, 8,8 s, $0,0013/trang |
| `gpt-6-luna` | rẻ nhất | sai 7/19, 7,8 s, $0,0006/trang |

Hai model `nano` cũ (`gpt-4.1-nano`, `gpt-5-nano`) bị loại: bỏ sót gần hết công thức. Mẫu chỉ 19 công
thức, nên thứ tự giữa ba lựa chọn chưa phải kết luận; sympy và bước LLM tự dựng lại (plan 3c) là thứ
được kỳ vọng kéo cả ba lên.

### Plan 3a đóng ở đây (11/10/2026)

Người dùng: *"Trước mắt, plan này đã xong."* Thứ đã giao: đường upload đọc **chữ** (EasyOCR mặc
định, VietOCR là lựa chọn), 4,5 s/trang, thiếu từ 9,3% trên 50 trang; bộ đo có nhãn vàng và bản ghi
`data/run-<n>/<model>/`; chẩn đoán vì sao công thức không đọc được trên CPU; báo cáo chi phí và khảo
sát VLM; quyết định ba model vision.

**Thứ chưa làm, và nó là việc của plan sau** -- đã chuyển sang `backlog.md`:

- **`agent/vision.py` chưa viết.** Hướng đã chốt ở plan duyệt 11/10/2026: `config.py` thêm
  `vision_provider` / `vision_model` (ba giá trị hợp lệ ở bảng trên); `llm.py` thêm `vision_model()`
  dựng bằng `_build` có sẵn; `vision.py` nhận byte PNG, structured output `{formulas: [str]}`, đi qua
  bước sửa thoát ký tự, gỡ phần bọc (```` ```latex ````, `\[ \]`, `\( \)`); test không gọi mạng.
- **Prompt cho `⋮` và `\underbrace`**, đo lại 5 trang (dưới 1 cent).
- **Thước đo công thức chuẩn hoá mạnh** (`normalise_latex_loose`, ghép phủ-đủ cho ô nhãn vàng gộp) vào
  `score.py` có test -- hiện chỉ nằm trong script khảo sát ngoài repo.
- **Benchmark 50 trang cho ba lựa chọn** (≈ $0,13), khi người dùng cho phép.
- **Nối đường lúc ra đề**: cần chunk của plan 3b → dải trang; message mới; cách byte ảnh đi
  `document` → AGENT; cache theo trang.

Nợ cũ của plan này, trạng thái mới: (3) định tuyến `formula` và (11) công thức yếu -- **đóng**, vì công
thức không còn đọc lúc upload; (7) lát C nhãn công thức -- vẫn mở, giờ là nợ của benchmark VLM; (4)
`aside_text`/`table_title`, (5) trang mục lục, (6) `label_accuracy`, (8) hai venv, (9) dòng thuộc hai
khối, (10) khoá cache thiếu tên model -- vẫn mở.

Cổng khi đóng: `.\dev.ps1 check` 20/20, test `services/document` + `tools` xanh, ruff sạch. Chưa commit.
