# Bench nhánh `agent-md`: agent tự chia job từ dàn ý Markdown

- **Mở:** 13/11/2026 · người dùng hỏi có nên nới phần BE kiểm soát kết quả của agent khi ra đề không:
  dàn ý chỉ là Markdown, giáo viên đồng ý thì agent tự chia job và cho giáo viên thấy nó chia thế
  nào. Người dùng chốt: bỏ phép chia của BE, **mỗi job vẫn một câu**, **đo bằng `exam_bench`
  trước** rồi mới sửa hệ thống.

## Goal

Trả lời bằng số: nếu agent đọc **lời dàn ý Markdown giáo viên đã thấy** rồi tự viết brief riêng cho
từng câu (thay `be.drafting.place_items` + `item_fields`), thì

1. đề lần đầu có tốt hơn đường BE chia hiện nay không (Q1 so cặp trên cùng dàn ý);
2. agent có chia trung thành với dàn ý không (S1, S2) -- rủi ro mới, vì ADR-29 nói thứ giáo viên
   đọc phải là thứ job nhận.

Plan này không sửa `services/`, `packages/` hay FE.

## Scope

- Dùng lại 16 dàn ý của pilot `run-130` (nhánh `agent`), không sinh dàn ý mới: nhánh mới và nhánh
  cũ chạy trên **cùng một dàn ý**.
- Nhánh `agent-md`: chỉ đọc lời Markdown (`said`) của lượt dàn ý, không đọc `items`; một lời gọi
  *phân việc* tới cùng model sinh đề ra `note` (lời cho giáo viên) và một job mỗi câu; soạn và thu
  câu y như nhánh `agent`.
- Chấm bằng panel cũ, prompt cũ (đề cũ trúng cache); thêm một lời chấm `split`.

## Files

- `tools/exam_bench/split.py` (mới): prompt và schema phân việc, `split_jobs`, `job_fields`.
- `tools/exam_bench/run.py`: `_draft_and_harvest` dùng chung, `agent_md_paper`, cờ `--split-from`,
  nhánh thứ ba trong `rate_paper`, `summarise`, `report`.
- `tools/exam_bench/rate.py`: `SPLIT_SYSTEM`, `SplitVerdict`, `split_prompt`.
- `tools/tests/test_exam_bench.py`, `tools/tests/test_propose_bench.py`.
- `docs/overview/grading-design.md`, `docs/plans/backlog.md`.

## Ordered Tasks

### Pha 1 -- code, test, chạy khói

- [x] `split.py`: prompt phân việc, `Split`/`Job`, một lần trả lại khi số job lệch số câu dàn ý,
      `job_fields` map vào `DraftQuestionRequested` như `item_fields`.
- [x] `run.py`: tách `_draft_and_harvest` khỏi `agent_paper`; `agent_md_paper`; `--split-from`.
- [x] `rate.py` + `run.py`: lời chấm `split`; mục của câu `agent-md` là job.
- [x] `summarise`/`report`: nhánh thứ ba, S1, S2, số job đúng, Q1 so cặp, khoá sai và nhiều đáp án
      đúng từng nhánh, hai `note` mẫu.
- [x] Test thuần (10 test mới); prompt phân việc vào luật *câu đo không nằm trong prompt*.
- [x] Chạy khói 1 ca (`run-131` sinh, `run-132` chấm lại vì trần 3 USD chạm khoảng dự phòng 2,7
      USD): phân việc đúng số job 2/2, S1 10/10, S2 2/2; Q1 `agent-md` 9/10 so với `agent` 4/10
      trên cùng dàn ý -- một ca, chưa nói gì. Đề cũ trúng cache 100% (0 USD). Lời Markdown của
      `tap-hop-6` có đủ mọi phần dàn ý; job viết chi tiết hơn mục (bước giải, có khi tính sẵn).
      Chi phí khói 0,95 USD.
- [x] `.\dev.ps1 check` 26/26, `.\dev.ps1 test` 2096 + 395 xanh; subagent review pha 1.
- [x] Sửa theo review pha 1:
  - **Luật `phuong-an-trung` bắt nhầm** `6` với `\{6\}`: cả 3 lần bắt ở `run-130` là bắt nhầm.
    `_plain` giữ ngoặc thoát. Số `agent` của `run-130` đổi theo (`grading-design.md` sửa ở pha 2).
  - **Prompt phân việc để lọt job tả hai câu** (khói `#2`: job 1 = job 2, job 4 = job 5) và tự
    thêm công thức. Thêm luật *mỗi job chỉ nói về đúng câu của nó*, *formulas chỉ gồm công thức dàn
    ý nêu*. Lời chấm `split` thêm `single`, `distinct` (S1b), bỏ câu dẫn dắt dễ dãi; đếm job trùng
    lời dặn bằng code.
  - **Lỗi hạ tầng ở bước phân việc** tính là đề chưa đo, không phải đề hỏng; lần trả lại hỏng thì
    giữ cách chia đầu.
  - **Job cùng phần không vào danh sách *đừng hỏi sang***, chỉ khi nhãn `part` thật sự chia đề
    (khói 2: model ghi tên bài cho mọi job).
  - **Q1 lõi so cặp** (giải mù + luật code), vì rater duyệt câu `agent-md` với job làm mục, câu
    `agent` với mục dàn ý. Ghi cấu hình sinh đề vào từng đề `agent-md`.
  - Test: 20 test cho nhánh mới, gồm nhiều đợt soạn, lỗi hạ tầng, `rate_paper`, bootstrap tất
    định.
  - `items` cũ vẫn được đọc, nhưng **chỉ để biết số câu** của dàn ý; model chỉ đọc lời Markdown.
- [x] Khói 2 (`run-133`, 1,00 USD): job trùng 0, S1 10/10, S1b 9/10, S2 2/2; Q1 so cặp **+0**
      (so với +50 ở khói 1 trên cùng dàn ý) -- nhiễu của bước soạn một ca lớn, đúng như dự đoán.
- [x] Check 26/26, test xanh sau khi sửa.

### Pha 2 -- pilot 16 dàn ý

- [ ] `--split-from run-130`, 8 ca, trần 20 USD. **Dừng giữa chừng: tài khoản API hết credit**
      (`run-134`, 6,28 USD). 16/16 đề `agent-md` đã sinh; 9/16 chấm đủ (4 ca đầu, cộng
      `bat-phuong-trinh-hai-an-10` #1), 7 đề phiếu trống. Trên 9 cặp đủ phiếu: Q1 so cặp +1,8 điểm
      [−3,1; +10,8], S1 49/50 trên 4 ca đầu. Bốn ca còn lại, gồm `don-dieu-cuc-tri-12` nơi khoá
      sai dồn nhiều nhất, chưa chấm: **chưa có kết luận**. Nạp credit rồi chạy
      `--from-run data/results/run-134/exam-chia-pilot`: lời chấm đã có lấy từ cache, chỉ gọi phần
      thiếu (ước 5–6 USD).
- [x] Lỗi bench lộ ra: đề mà lời chấm trống hết bị tính là đề có câu hỏng (lượt này ra −26 điểm
      giả). Nay lời chấm có từ hai phiếu trống trở lên thì đề tính là chưa chấm; có test.
- [ ] Subagent review pha 2: tính lại số từ `ratings.jsonl`, đọc tay job bị chấm không trung thành.
- [ ] `grading-design.md`, backlog (md và doc *Backlog theo tier*).

## Validation Checks

- `.\dev.ps1 check`, `.\dev.ps1 test` xanh.
- Số `agent`/`naive` trong báo cáo pilot khớp `run-130`; tiền chấm phần cũ là 0 (cache trúng).
- Tổng chi phí không vượt trần.

## Decision Records

### Decision: Thí nghiệm so cặp trên dàn ý cũ

options considered: sinh dàn ý mới bằng prompt *chỉ Markdown*; dùng lại dàn ý của `run-130`, chỉ
đọc lời Markdown.
selected option: dùng lại dàn ý của `run-130`.
reason: chỉ bước chia job khác nhau giữa hai nhánh, nên chênh lệch quy được về bước ấy; nhiễu của
lượt dàn ý bị loại; không tốn tiền sinh dàn ý; và sửa prompt dàn ý của Kriky là sửa AGENT, ngoài
phạm vi *bench trước*. Cái giá: lời Markdown ở đây được viết **kèm** `items`, nên chưa đo được dàn ý
viết khi không có `items`.

### Decision: Ngưỡng đọc kết quả chốt trước khi chạy

options considered: đọc số rồi mới quyết; chốt ngưỡng trước.
selected option: chốt trước -- *đáng làm thật* khi Q1 so cặp ≥ +10 điểm, khoảng bootstrap theo ca
không chứa 0, và S1 ≥ 90%; *không hơn* khi khoảng chứa 0; *không tin được* khi S1 < 90%.
reason: pilot nhỏ (khoảng 106 câu mỗi nhánh); ngưỡng chốt sau khi thấy số thì dễ chiều theo số.

## Status

**Dừng theo quyết định người dùng, 13/11/2026.** Pha 1 xong. Pha 2 dừng giữa lượt chấm pilot vì
tài khoản API hết credit (9/16 đề `agent-md` chấm đủ; Q1 so cặp +1,8 điểm [−3,1; +10,8] trên 9
cặp, S1 49/50 trên 4 ca). Người dùng thấy chất lượng đủ để đưa hướng *agent tự chia job* vào hệ
thống thật, nên không chạy nốt; `grading-design.md` và backlog không được cập nhật với kết quả
nhánh `agent-md` vì kết quả chưa đủ. Hai sửa thước đo của plan này (luật `phuong-an-trung`, đề có
phiếu trống tính là chưa chấm) vẫn ở lại trong `tools/exam_bench`. Việc thiết kế lại chuyển sang
plan kế tiếp.
