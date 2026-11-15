# Bench đo được trên cả `claude-haiku-5-5` và `gpt-6-luna`

- **Mở:** 15/11/2026 · người dùng: *"lên plan để thực hiện refactor benchmark, tôi dự kiến dễ bench
  trên cả haiku 5.5 và gpt 6 luna nhé"*.

## Goal

`exam_bench` và `propose_bench` chọn model bằng cờ `--model provider:model`, không còn khoá cứng Haiku
và không phải sửa `.env`. Mọi số đo gắn với model và cấu hình đã sinh ra nó. AGENT tắt được suy luận
của model OpenAI (`LLM_REASONING_EFFORT`), như tắt thinking của Claude. Sau đó đo cả hai model trên
cùng phiên bản code, rồi ghi số vào docs.

## Scope

Người dùng chốt (15/11/2026):

- Sinh đề mới cho cả hai model. Ba rater Claude giữ nguyên.
- Luna chạy `reasoning_effort` `none`.
- Không làm lệnh so model; bảng so ghép tay.

`skill_bench` đo Jev nên không đổi. Mỗi lượt gọi model thật phải xin phép riêng, kèm ước chi phí.

**Đổi hướng (15/11/2026, sau khi dò Stali).**

Tài khoản Anthropic hết credit, nên người dùng thêm cổng Stali (`STALI_API_KEY`, `STALI_ENDPOINT`).
Dò bằng mã đánh dấu, mỗi lời gọi vài trăm đồng:

- Opus và Sonnet 5.5 qua Stali chạy trong vai Kiro, bị chèn khoảng 4.700 token.
- Opus 4.8 nhận là Claude Code, bị chèn khoảng 1.000 token.
- Kênh `req/` có dấu hiệu làm rơi system prompt.
- Haiku kênh thường và luna (khi có system prompt) thì sạch.

Người dùng chốt:

- *"chỉ gọi api để sử dụng haiku và luna"*.
- Rater là **3 subagent Sonnet, effort `medium`**, chạy trong phiên Claude Code thay cho panel API,
  để tiết kiệm quota.
- Có gọi Haiku qua Stali hay không thì người dùng còn cân nhắc: chuẩn bị cả hai đường (`--via`), không
  gọi API nào trong lúc chuẩn bị.

## Files

- `services/agent/src/agent/config.py`, `services/agent/src/agent/llm.py` và test của chúng;
  `.env.example`, `docs/local-development.md`.
- `tools/bench_model.py` (mới), `tools/exam_bench/run.py`, `tools/exam_bench/rate.py`,
  `tools/propose_bench/run.py`, `tools/tests/`.
- Sau khi đo: `docs/overview/grading-design.md`, `docs/plans/backlog.md`, mục *Agent Benchmark* của
  báo cáo chương 7.

## Ordered Tasks

- [x] Pha 1: `LLM_REASONING_EFFORT` cho provider `openai` (config, `_build`, test, `.env.example`, docs);
  `.env` dev chuyển sang `gpt-6-luna` / `none`.
- [x] Pha 2: `tools/bench_model.py` (`pin`); cờ `--model` bắt buộc; slug model trong tên thư mục kết quả.
- [x] Pha 3: `exam_bench`:
  - bỏ `GENERATOR`;
  - nhánh `naive` đi qua LangChain;
  - `Spend` đọc `usage_metadata` và có giá luna;
  - đếm token nhánh `agent`;
  - báo độ trễ và số lỗi hạ tầng.
- [x] Pha 4: `propose_bench`: `--model`, dòng cấu hình, độ trễ.
- [x] Pha 5: test, `ruff`, `.\dev.ps1 check`; subagent review.
- [x] Pha 5b: chuẩn bị chạy không cần credit Anthropic (chưa gọi API nào):
  - `--via stali` cho model sinh đề, kèm lời thử đầu lượt: dừng nếu token vào dư quá ngưỡng (bị
    chèn);
  - nhánh `naive` ép tool ở cả hai model (Stali không giữ JSON schema của Haiku);
  - `exam_bench --rate-with export|import`: xuất tác vụ chấm (đợt giải mù tách khỏi đợt có khoá),
    rồi nhập phiếu của 3 subagent, kiểm bằng schema của `rate.py`;
  - lời dặn subagent trong `tools/exam_bench/subagent_rater.md`;
  - kiểm offline: phiếu cache của `run-130` giả làm phiếu subagent phải ra lại đúng số cũ;
  - review.
- [x] Pha 6a (luna, người dùng cho chạy 15/11/2026):
  - `propose_bench --model openai:gpt-6-luna`;
  - `exam_bench --rate-with export`;
  - 3 subagent Sonnet chấm;
  - `--rate-with import`.
- [ ] Pha 6b (Haiku, khi có credit): làm y hệt pha 6a (*"sau đó chỉ cần làm tương tự với haiku là
  được"*).
- [ ] Pha 6 (kế hoạch gốc, thay bằng 6a và 6b): chạy thật, mỗi lượt xin phép: `propose_bench` ×2, `exam_bench` khói, rồi `exam_bench`
  ×2.
- [ ] Pha 7: `grading-design.md`, backlog, báo cáo (báo trước câu đổi); đóng plan.

## Validation Checks

| Check | Lệnh |
| --- | --- |
| Test | `pytest tools/tests services/agent/tests` |
| Hợp đồng repo | `.\dev.ps1 check` |
| Không tiêu tiền khi cache thiếu | `exam_bench --from-run … --cap 0` dừng trước lời gọi rater |
| Worker chạy đúng model | log `AGENT worker ready … model=openai/gpt-6-luna` |

## Status

Mở 15/11/2026. Pha 1–5 xong, cùng ngày.

- **Pha 1.** `LLM_REASONING_EFFORT` (OpenAI), `openai_options`. Thêm `agent.llm.standalone`: chỉ bench
  dùng, cho một lời gọi ra cả đề. `.env` dev: `gpt-6-luna` / `none`. Worker AGENT đang chạy là của
  phiên `user-guide` (bật với `LLM_MODEL=gpt-6-luna` đặt ngay trong lệnh), nên chưa khởi động lại.
  Bench không cần worker.
- **Pha 2–4.** `tools/bench_model.py`; `--model` bắt buộc ở hai bench; thư mục `…-<slug model>`; dòng
  cấu hình đầu `report.txt`. Nhánh `naive` đi qua LangChain với `method="json_schema"`: đúng
  `output_config.format` mà `messages.parse` gửi trước đây.
- **Review pha 5**, đã sửa cả bảy điểm:
  - lượt `--from-run` cũ không ghi model thì coi là Haiku;
  - nhánh `naive` trên Haiku ép `json_schema`;
  - thiếu key Claude của panel thì dừng trước khi sinh đề;
  - `_waits` không còn gọi một bước dài là hết giờ;
  - chi phí ghi cache theo khoá `ephemeral_*`;
  - dòng chi phí của lượt chỉ chấm;
  - dòng trần của nhánh `naive`.
- **Kiểm không tốn tiền.** `--from-run run-134 --cap 0` trên Haiku đọc 993 lời chấm từ cache, ra lại
  đúng số pilot (Q1 65% 69/106, 70% 37/53), 0 USD. Riêng đề `agent-md` của `run-134` không có trong
  cache, nên dừng ở trần 0. `--model openai:gpt-6-luna` trên đề Haiku cũ bị chặn trước mọi lời gọi.

Pha 5b xong 15/11/2026, chưa gọi API nào.

- `--via stali`: lời thử đầu lượt; chặn `--via` đi cùng panel API.
- Nhánh `naive` ép tool.
- `exam_bench --rate-with export|import`, với `tools/exam_bench/subagent.py` và lời dặn
  `subagent_rater.md`.
- Kiểm offline: phiếu cache của `run-130` giả làm phiếu subagent ra **giống hệt** đường panel API trên
  cùng code (56 dòng chỉ số, đồng thuận, câu bất đồng; nhận đủ 975 phiếu).
- Review (subagent Sonnet), đã sửa 7 điểm:
  - chặn `--via` + `api`;
  - lời thử nâng `max_tokens`, không có usage thì dừng;
  - `import` không dựng client;
  - phiếu thiếu đếm theo phạm vi, phiếu trùng đếm riêng;
  - dòng không phải object là phiếu hỏng;
  - chặn model sinh đề theo tên thật của rater.

  Bỏ qua 3 điểm:
  - thứ tự hai đợt: mỗi subagent là một lượt không trí nhớ;
  - gộp tác vụ trùng: đúng như review xác nhận;
  - chi phí lời thử: vài chục token.

Pha 6a xong 15/11/2026 (luna, gọi thẳng OpenAI):

- `propose_bench` (`run-136`): 258/276, soạn câu 12/12, đặt tên 8/8. Một bước: trung vị 2,5 s, lâu
  nhất 10,2 s, không lần nào hết giờ. Hỏng 6/6 ở ba ca thiếu tin (hỏi lại không kèm nút; một ca không
  hỏi khối).
- `exam_bench` (`run-135`): 24 đề, 0,06 USD.
  - Chấm: 18 lượt subagent (6 lượt `blind`, 12 lượt `keyed`), nhận đủ 1.050 phiếu.
  - `agent`: Q1 65% (69/106), P1 0,67, P2 68%, S1 92%, S2 100%, đề sạch 1/16.
  - `naive`: Q1 75% (40/53), đề sạch 2/8.
  - AC1 từ 0,78 trở lên ở mọi tiêu chí.
- Lộ ra (đã ghi backlog):
  - luna thoát sai `\` trong LaTeX ở 12/106 câu nhánh `agent` (lần đếm đầu 8/106 bỏ sót lời
    giải), BE không bắt;
  - schema lời duyệt thiếu mục *khoá sai*;
  - rater hiểu dấu phẩy khác nhau;
  - luna hỏi lại không kèm nút.
- Một subagent để lại `D:/tmp_w` và `D:/tmp_b.txt` ngoài repo (hệ thống chặn nó tự xoá): người dùng
  tự xoá.

Pha 6b, lượt đầu (15/11/2026, Haiku qua Stali, `--via stali`):

- **Lời thử đầu lượt sạch:** 134 token vào, Haiku làm theo system prompt.
- **`exam_bench --rate-with export` đổ cả lượt.** Một lời gọi ra dàn ý quá trần 20 s, và lỗi ấy làm
  hỏng `gather`, nên không đề nào được ghi. Đã sửa:
  - lời gọi `propose` lúc ra dàn ý được thử lại khi gặp lỗi hạ tầng, tối đa `LLM_MAX_ATTEMPTS`, như
    AGENT;
  - một đề hỏng không còn làm mất cả lượt.
- **`propose_bench` (`run-137`) KHÔNG DÙNG ĐƯỢC.** Ví Stali cạn giữa chừng: 167/296 lượt hỏng vì
  `402 insufficient_balance`. Đã sửa: hết tiền ở provider hay cổng thì cả hai bench dừng hẳn.
- **Tín hiệu từ phần chạy được, chưa kết luận được:** trên cùng 21 ca đủ 6 lượt, Haiku qua Stali
  75/126 so với luna 108/126. Haiku hay hỏi lại khi đã đủ tin, và có lượt ra *"tool name None"*.
  Stali đã bỏ qua JSON schema của Haiku, nên có thể nó cũng bỏ qua `tool_choice`. Khi ấy đây là lỗi
  của cổng, không phải của model. Phải thử riêng trước khi tin số Haiku qua Stali.

Pha 7 (một phần, 15/11/2026): người dùng dặn *"tạm thời dùng những kết quả đã có sẵn"* để cập nhật
docs và báo cáo.

- **`grading-design.md`:**
  - mục *Đọc các chỉ số thế nào*;
  - kết quả luna (`run-135`);
  - `propose_bench` luna (`run-136`);
  - lượt Haiku chưa có số (`run-137` hỏng).
- **Báo cáo chương 7, mục *Agent Benchmark*:**
  - bảng ba benchmark: cột *lần đo gần nhất*;
  - đoạn `propose_bench`: số luna thay cho câu *"chưa được chạy lại"*;
  - đoạn và bảng `tab:exam-bench-luna`;
  - câu giới hạn cuối mục: thay câu *"`gpt-4o-mini` chưa được đo"*.
- **Backlog:**
  - gốc lỗi ký tự điều khiển (`LATEX_COMMANDS` thiếu `boxed`, `bar`);
  - Stali có thể bỏ `tool_choice`;
  - hai dòng `propose_bench` / P1-P2 cập nhật.
- **Build:** `.\dev.ps1 report` xanh; cảnh báo như trước (một `Float too large` cũ, `Infinite glue` 6
  dòng như HEAD lần trước).

Pha 6b, lượt hai (15/11/2026, Haiku qua OpenRouter, `--via openrouter`; thêm `propose_bench --resume`):

- **Lời thử qua OpenRouter sạch:** 77 token vào, Haiku làm theo system prompt.
- **`propose_bench --resume run-137` → `run-138`.**
  - Giữ 129 lượt Stali, chỉ chạy lại 167 lượt hỏng vì hết tiền.
  - Tài khoản OpenRouter có 0 USD credit (gói miễn phí; hạn mức 100 USD chỉ là trần của key), nên
    sau 89 lời gọi thật thì bị chặn: `402 billing_error`.
  - Phép dừng khi hết tiền chưa biết chữ này, nên không dừng, và 78 lượt hỏng vì hết tiền được ghi.
    Đã thêm `billing_error` và *"exceed your available credits"* vào phép ấy.
- **Chạy nốt `--resume run-138`:** giữ 218 lượt, còn `propose` 61, soạn câu 10, đặt tên 7 (khoảng
  0,1 USD).
- **`exam_bench` cho Haiku chưa có đề nào:** khoảng 0,17 USD.

**Thử `tool_choice` qua Stali (15/11/2026, thử thô, 200 đ):** câu mời trả chữ thường, ép tool `ghi_buoc`; Haiku gọi đúng tool (`stop_reason: tool_use`). Stali **giữ** ép tool. Nghi ngờ ở lượt đầu là sai; khoảng cách Haiku 75/126 so với luna 108/126 nhiều khả năng là của Haiku.
