# Plan — Bench chất lượng ra đề: dàn ý và đề lần đầu

- **Mở:** 12/11/2026 · Plan 2 của đợt người dùng giao ngày 12/11/2026 (sau plan `tier-1`)

## Goal

Đo agent ra đề tốt tới đâu ở hai điểm giáo viên quyết định: **dàn ý có duyệt được không** và **đề
lần đầu có phát hành được mà không sửa không**. `tools/propose_bench` chỉ đo hành vi (loại việc, tham
số); bench này đo nội dung. Lần này là **pilot 8 ca**: mục đích chính là biết **thước có tin được
không**, con số chất lượng là phụ.

## Scope

- Trong: `tools/exam_bench/` (chạy, chấm, báo cáo); 8 ca SGK Kết nối tri thức, không đính kèm tài
  liệu; ba rater LLM làm nhãn vàng; hai nhánh `agent` và `naive`; phần đánh giá của
  `docs/overview/grading-design.md`.
- Ngoài: ca có tài liệu (đường đọc sách cần Mongo); ablation *bỏ dàn ý*; độ khó, độ phân biệt câu và
  học sinh mô phỏng; sửa prompt của agent theo kết quả (việc của plan sau).

## Files

- `tools/exam_bench/__init__.py`, `run.py`, `rate.py`, `score.py`, `cases.json`
- `tools/tests/test_exam_bench.py`; `tools/tests/test_propose_bench.py` (câu đo của ca mới vào luật
  *câu đo không nằm trong prompt*)
- `docs/overview/grading-design.md` (mới, phần đánh giá), `AGENTS.md` (dòng *Reserved* thành một
  hàng sở hữu)
- `docs/plans/backlog.md`, artifact *Backlog theo tier*

## Ordered Tasks

Pha 3 — thước, ca, rater:

- [x] Vàng độ phủ: chép khung *KIẾN THỨC, KĨ NĂNG* của 8 bài vào `cases.json` từ ảnh trang SGK
  (lớp 6, 8, 10, 12; một ca hai bài -- Toán 8 bài 6 và 7). Trường `source` ghi sách, bài, trang.
- [x] `score.py`: đa số phiếu, độ phủ, Fleiss' kappa, Gwet AC1, đồng thuận thô, kappa từng cặp,
  luật lỗi viết câu bằng code.
- [x] `run.py`: nhánh `agent` và nhánh `naive`; gộp chỉ số; báo cáo.
- [x] `rate.py`: panel ba rater, structured output, cache theo hash, cộng chi phí, trần cứng.
- [x] Test các hàm thuần; câu ca và câu trả lời hỏi lại vào luật câu đo.
- [x] Chạy khói `menh-de-10` (`run-124`…`run-128`). Lộ ra và đã sửa: *"toán 10"* không được đọc là
  lớp 10 (câu ca nói *"lớp 10"*; Kriky hỏi lại thì giáo viên giả trả lời một lần); `max_tokens`
  32000 không streaming bị SDK từ chối; prompt naive thiếu luật hai cách giải nên hỏng 6/6 câu ở cổng
  ADR-18 -- không công bằng, đã cho naive đủ luật hình dạng.
- [x] Subagent review pha 3. Thước sai ở nhiều chỗ, sửa hết trước pilot:
  - mẫu số Q1/P1 bỏ đề trượt cổng và câu naive không trả (đề hỏng càng nhiều, Q1 càng đẹp) → Q1
    tính trên mọi câu được xin, P1 tính dàn ý trượt cổng là 0; `clean` sai khi số ô khác số câu xin;
  - luật code bắt nhầm *"Tất cả học sinh … đều"* (phương án nhiễu kinh điển của phủ định ∀) và `?`
    trong chữ trích → chỉ bắt cụm nói về các phương án, bỏ chữ trong ngoặc kép, thêm luật *đề chép
    phương án*;
  - đường dàn ý khắt khe hơn BE → lý do từ chối về lại model, tối đa `_MOST_OUTLINE_REFUSALS`;
    câu trả lời hỏi lại thiếu môn; brief lấp từ ca được đếm;
  - Q1d (bám mục) chỉ áp nhánh agent → Q1 chính không gồm Q1d, Q1+ báo riêng; rater được biết câu
    chỉ kiểm một phần của mục;
  - kappa sụp ở tiêu chí lệch một phía → thêm AC1, đồng thuận thô, `n` là hàng đủ phiếu, cờ cho
    giá trị không xác định, bảng riêng cho từng loại lỗi nặng;
  - `answer` và `options` của lời giải mù có thể mâu thuẫn → chỉ đọc `options`;
  - soạn câu lệch BE (không truyền `banned`, stem đã casefold, soạn lại từng ô) → soạn theo đợt,
    `banned` là stem thô, lỗi hạ tầng không tính một lần soạn;
  - trần chưa cứng, đề chưa chấm bị tính là hỏng, cache key thiếu schema → trần trừ khoảng dự phòng,
    kiểm trước mỗi lần thử, đề chưa chấm loại khỏi chỉ số, phiếu trống được đếm, khoá gồm schema và
    tham số gọi; giá đọc cache đúng từng model;
  - prompt rater: D1, D4, Q2 viết lại cho rõ, bỏ *"chấm khắt khe"* và *"do trợ lý AI soạn"*; Q2 chỉ
    đo câu có khoá đúng;
  - naive đọc `LLM_THINKING`/`LLM_EFFORT` từ `.env`; câu hỏng được giữ (`rejected`) để chẩn đoán.
  Chạy khói lại (`run-128`): AC1 ≥ 0,7 ở mọi tiêu chí.

Pha 4 — pilot:

- [x] `agent` 8 ca × 2 lượt, `naive` 8 ca × 1 lượt; panel chấm tất cả (`run-129`, 1 408 s, 15,31 USD).
- [x] Đồng thuận từng tiêu chí: AC1 ≥ 0,75 ở mọi tiêu chí, nên không sửa prompt chấm. Một lỗi của
  thước lộ ra: Sonnet có lúc ghi nhãn kèm chữ (*"B. 5"*) thành phiếu trống → `label()` chuẩn hoá về
  một chữ cái, gộp lại từ cache 0 USD (`run-130`). Câu panel giải ra khác nhau từ 9 còn 5.
- [x] Báo cáo: chỉ số theo nhánh, độ dao động giữa hai lượt, các câu panel bất đồng.
- [x] `grading-design.md` (phần đánh giá) + dòng `AGENTS.md`; backlog (mục *Lộ ra khi làm bench chất
  lượng ra đề*) và artifact (Tier 4, Tier 2 câu 3 và 24).
- [x] Subagent review pha 4: tính lại độc lập từ `ratings.jsonl` -- mọi con số khớp. Đọc tay 14/17
  câu khoá sai: panel đúng cả 14. Sửa lời theo review: *"hai phương án tương đương là lỗi nặng hay
  gặp nhất"* không đứng được (cả 11 câu đã trượt vì khoá sai hay nhiều đáp án đúng, chỉ 3 câu tương
  đương thật -- danh mục lỗi thiếu mã *nhiều đáp án đúng*); *"khoá sai gấp ba, rõ"* nói quá (2,8 lần,
  Fisher p ≈ 0,08) → *nghiêng về agent, chưa khẳng định*; khoảng cách Q1 dẫn bằng khoảng tin cậy
  bootstrap thay cho ví dụ một ca; ghi lỗi nặng và phương án nhiễu là bất đồng thật ở mức vừa;
  chi phí panel 15,29 USD (0,02 USD là Haiku của `naive`); giới hạn thêm bốn điều.

## Validation Checks

- `.\dev.ps1 check`, `.\dev.ps1 test` sau mỗi pha.
- Test thuần: kappa trên bảng số biết trước, độ phủ, đa số phiếu, luật lỗi.
- Chạy khói ra đủ `outlines.jsonl`, `questions.jsonl`, `ratings.jsonl`, `report.txt`.
- Tổng chi phí panel không vượt trần.

## Decision Records

### Decision: panel ba rater Claude, không có nhãn tay

**options considered:** nhãn tay của người dùng; một judge; ba rater khác họ.
**selected option:** ba rater `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-opus-4-8`, đa số phiếu
là nhãn vàng.
**reason:** người dùng chốt nhãn vàng bằng ba LLM (12/11/2026) và đưa khoá Claude. Ba model khác hạng
và khác thế hệ để lỗi ít tương quan; không model nào là `claude-haiku-5-5` (model sinh đề). Giới hạn:
cùng họ Claude với model sinh đề -- bù bằng việc tiêu chí nặng nhất (đáp án đúng) chấm bằng **giải
mù**, không bằng cảm nhận.

### Decision: không bật `fallbacks` của API cho rater

**selected option:** gọi thẳng, một lời từ chối (`stop_reason: refusal`) thành một phiếu trống.
**reason:** fallback đổi model giữa chừng, tức đổi rater mà bảng đồng thuận không biết. Phiếu trống
được đếm và báo.

### Decision: vàng độ phủ là khung *KIẾN THỨC, KĨ NĂNG* của SGK

**reason:** sách đã viết sẵn yêu cầu cần đạt từng bài -- không phải tiêu chí tự nghĩ. SGK trong
`data/` là ảnh scan không lớp chữ, nên chép tay từ ảnh trang, một lần.

### Decision: pilot không có ca đính kèm tài liệu

**reason:** đường đọc sách gọi `read_section` qua BE và Mongo; dựng nó trong bench là một việc riêng.
Ca không tài liệu vẫn đo đủ hai giai đoạn. Ghi backlog.

### Decision: AC1, không kappa, là ngưỡng tin của một tiêu chí

**options considered:** Fleiss' kappa ≥ 0,6 (như plan viết lúc đầu); Gwet AC1 ≥ 0,6; đồng thuận thô.
**selected option:** AC1 ≥ 0,6 là ngưỡng, kappa và đồng thuận thô in kèm.
**reason:** chạy khói và pilot cho thấy nhiều tiêu chí ≥ 95% một phía (D2, D4, *bám mục*, từng mã
lỗi); ở đó kappa thấp hay âm dù ba rater gần như nhất trí (nghịch lý tỉ lệ), nên sửa prompt theo
kappa là sửa nhầm tiêu chí (review pha 3). AC1 không sụp như vậy; kappa vẫn chỉ ra cặp rater lệch.

### Decision: `grading-design.md` thành một hàng sở hữu của `AGENTS.md`

**options considered:** giữ dòng *Reserved*, ghi phương pháp trong docstring của bench và trong plan;
viết `grading-design.md` và đổi dòng giữ chỗ thành một hàng của bảng sở hữu.
**selected option:** viết phần đánh giá của `grading-design.md`, đổi dòng *Reserved* thành hàng sở
hữu. Prompt và lựa chọn model chưa chuyển vào đó.
**reason:** `AGENTS.md` giữ tên này cho đúng việc đánh giá; giờ có nội dung thật (phương pháp, rubric,
kết quả pilot) và nó sống lâu hơn plan này, mà `completed/` thì không ai được sửa. Một dòng *Reserved*
nói *chưa viết* khi file đã có là luật tự mâu thuẫn. `CLAUDE.md` và các `AGENTS.md` con không nhắc
tới dòng ấy, nên không có gì phải quét theo; số dòng `AGENTS.md` giảm 185 → 184, trần không đổi.

## Status

Xong 12/11/2026. Thước tin được ở mức pilot (AC1 ≥ 0,75 mọi tiêu chí; số liệu tính lại độc lập
khớp). Dàn ý phần lớn duyệt được (P1 0,80; P2 82%); đề lần đầu chưa hơn một lời gọi thẳng (Q1 63% với
70%, không có ý nghĩa thống kê); khoá sai nghiêng về agent (16% với 6%, p ≈ 0,08). Chi tiết ở
`docs/overview/grading-design.md`. Không commit: người dùng review sau cả hai plan.
