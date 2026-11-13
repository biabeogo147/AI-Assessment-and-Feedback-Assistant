# Dàn ý Markdown, agent tự chia job

- **Mở:** 13/11/2026 · người dùng dừng bench `agent-split-bench` và chốt đưa hướng *agent tự chia
  job* vào hệ thống thật: BE đang kiểm soát kết quả của agent quá chặt ở hai bước -- kiểm các mục
  dàn ý có cấu trúc, và chia mục thành ô (`place_items`).

## Goal

Xoá hoàn toàn đường dàn ý có mục cấu trúc (`OutlineItem`, `be/outline.validate` kiểu mục,
`place_items`). Dàn ý chỉ là lời Markdown kèm **một con số số câu** (và các bài nguồn khi có sách);
BE chỉ kiểm con số ấy. Giáo viên đồng ý thì **AGENT tự chia** dàn ý thành job, mỗi job một câu, và lời
chia việc hiện trên chat như một khối *thinking*: mở sẵn khi đang soạn, thu gọn khi đề soạn xong.

## Scope

Người dùng chốt (13/11/2026):

1. Xoá hoàn toàn đường cũ; không cờ chuyển, không đường dự phòng.
2. Giữ một con số *số câu* trong lượt dàn ý; BE kiểm trần 10 câu mỗi lần, 50 câu mỗi đề.
3. Mỗi job một câu (job nhiều câu: chưa làm).
4. Khối chia việc mở sẵn trong lúc soạn, thu gọn khi đề soạn xong.
5. `.env` dev trở lại `gpt-4o-mini` (đã đổi trước plan này).
6. Hỏi người dùng trước mỗi lượt benchmark.

Không đụng schema Postgres: `DraftBrief.outline` (JSON) và `DraftItem.outline_item` vẫn giữ, nay mỗi
phần tử là một job (`questions=1`).

## Files

- `packages/contracts/src/contracts/teacher_chat.py`, `__init__.py`, test.
- `services/agent/src/agent/graphs/propose/` (`proposal`, `prompt`, `compose`, `outline`,
  `read_order`, `choose`, `ask_again`, `graph`, `split` mới), `handlers.py`, test.
- `services/be/src/be/` (`outline`, `teacher_chat`, `drafting`), test; chú thích
  `packages/schema/src/schema/models.py` (`DraftBrief.outline`, không đổi DDL).
- `services/fe/src/` (`api.ts`, `screens/teacher/Chat.tsx`, `teacher.css`), test; Figma.
- `tools/` (`exam_bench`, `propose_bench`, test).
- `docs/decisions/adr-38-*.md`, hậu ký `adr-29` và `adr-30`, README decisions, `AGENTS.md`,
  `architecture.md`, `data-model.md`, `teacher-surface.md`, `grading-design.md`, `backlog.md`.

## Ordered Tasks

### Pha 1 -- contracts và AGENT

- [x] Contracts: bỏ `OutlineItem`; `Split`, `SplitJob`; `NextStepCompleted.outline_questions`,
      `outline_nodes`, `split`. (`TurnEvent.split` nằm ở BE, làm ở pha 2.)
- [x] AGENT propose: proposal, prompt, `soan-de.md`, compose (`_outline_facts`), outline, read_order,
      choose, ask_again theo con số.
- [x] `propose/split.py`, gọi ở cuối `propose()` (không phải node graph: để cả plan giữ lại sau một
      lần hỏi lại hỏng cũng được chia); mock `_mock_split` trong `handlers.py`.
- [x] Test AGENT và contracts; subagent review pha 1. Sửa theo review: chọn dàn ý theo cùng luật
      *ngay trước* với BE; thay câu thừa job thì không cắt (job đầu là câu 1) mà trả lại, lời trả lại
      nhắc câu N; thừa job ở đề mới cắt ngay; job trống thì trả lại, không chữ giữ chỗ; lời giáo
      viên gộp từ plan gần nhất; `right_purpose` nhận dàn ý một câu; khoá ghi chú trùng tên trường;
      prompt dặn dàn ý thay câu ghi **Câu N**; `NoOutline` có lời nhắc. Mục 12–13 (chữ *mục* trong
      `authoring/brief.py`, `propose_bench`) để pha 4.

### Pha 2 -- BE

- [x] `outline.py`, `teacher_chat.py` (outline_turn, guard_drafting đòi `split` đúng số câu, plan lưu
      và phát `split`), `drafting.py` (bỏ `place_items`, job thứ k cho câu mới thứ k).
      `teacher_tools.py` không cần đổi.
- [x] Test BE; check 26/26, test 2121 + 395 xanh (một lần `dev.ps1 test` đỏ không lặp lại được).
- [x] Subagent review pha 2. Sửa theo review: lời từ chối *thay câu* không suy từ trần (soạn thêm
      khi đề còn một chỗ cũng có trần 1); `SplitJob.part` để câu anh em cùng phần không bị dặn né
      kiến thức của nhau (chỉ khi cùng bản có từ hai nhãn); `fire`/`replace` không soạn khi số job
      lệch; lời chia việc không về lại model ở lượt sau (`_shrunk`); test job riêng từng câu, đường
      đề cũ (mục nhiều câu), số job lệch, lịch sử plan.

### Pha 3 -- FE, Figma, thử tay

- [x] `api.ts`, `Chat.tsx` (`drafting`), `JobSplit.tsx`, CSS; vitest (`job-split.test.tsx`).
- [x] Figma: component `Chia việc` (`832:5931`, thu gọn / mở), artboard **4b** `832:5932` (đang soạn,
      mở) và **5b** `832:6086` (soạn xong, thu gọn); `teacher-surface.md`.
- [x] Thử tay dev với `gpt-4o-mini` (13/11/2026, đoạn chat *Soạn đề tập hợp lớp 6*):
  - đề mới 5 câu: dàn ý Markdown; *"oke"* → khối *Kriky chia việc: 5 câu* mở trong lúc soạn, tự thu
    khi soạn xong; F5 thu gọn, bấm mở lại được;
  - soạn thêm 2 câu → *2 câu*, đề lên 7 câu; thay câu 3 → *1 câu*, ô 3 trỏ về job thay câu (bản 3)
    trong DB;
  - lời chia việc của `gpt-4o-mini` lần đầu chung chung và dùng chữ *job* với giáo viên; prompt sửa
    (*nói từng câu lo phần nào, không dùng chữ job*; `differs` rỗng khi phần một câu), lần sau cụ
    thể hơn. Đề có sách chưa thử (cần document/index worker và Mongo có sách).
- [x] test, typecheck xanh.
- [x] Subagent review pha 3 (so ảnh với Figma). Sửa theo review: đáy thân khối mở dư 6px (margin
      đoạn cuối) -- nay 12 như Figma; chữ thân bắt đầu ở 40 (padding trên 1); chú thích *x=32*;
      test đường F5 (thứ tự câu mở → khối chia việc → khối bước, thu gọn, bấm mở), bước tra cứu
      hỏng không làm khối thu, giáo viên tự đóng thì không mở lại, header không số câu. Hai con số
      *2 câu* / *5/7 câu* đứng cạnh nhau: backlog.

### Pha 4 -- tools, tài liệu, đóng

- [x] `exam_bench` (nhánh `agent` chia việc bằng `split_outline` của AGENT; bỏ `agent-md`,
      `split.py`, `--split-from`, Q1 so cặp), `propose_bench` (chấm số câu và nút; bốn ca có lượt dàn
      ý dạng cũ đổi sang `total`/`nodes`); không chạy bench.
- [x] ADR-38, hậu ký ADR-29, README decisions, `AGENTS.md` (dòng invariant ADR-29),
      `architecture.md`, `grading-design.md`, `teacher-surface.md`, `authoring/brief.py` (lời dặn),
      backlog md. Doc *Backlog theo tier*: cuối plan.
- [x] Subagent review pha 4. Sửa theo review: bench chia job bằng đúng hàm của BE
      (`drafting.split_items`, có `part`); lịch sử đồng ý của bench giữ lượt hỏi lại; đề chia hỏng
      vẫn mang `split`, lỗi hạ tầng thành chưa chấm; `--from-run` trên lượt `agent-md` cũ không vỡ;
      Q1 lõi in ra báo cáo; `propose_bench` chấm `split` của plan soạn; ADR-29 (bảng thi hành,
      dòng *Sửa*), hậu ký ADR-30, README, `data-model.md`, chú thích schema, `teacher-surface.md`,
      `grading-design.md` sửa theo. Lưu ý commit: `tools/tests/test_propose_bench.py` (đã track)
      import `exam_bench`, nên phải commit cùng `tools/exam_bench/`.
- [x] check 26/26, test 2117 + 404, typecheck xanh; doc *Backlog theo tier* thêm dòng Tier 4 (rev 252); đóng plan.

## Validation Checks

- `.\dev.ps1 check`, `.\dev.ps1 test` mỗi pha; `.\dev.ps1 typecheck` từ pha 3.
- Grep cuối: không còn `OutlineItem`, `place_items`, `source_nodes` của mục, `_outline_items` của
  AGENT (`be/student_routes._outline_items` -- câu làm lại pha 2 đọc `brief.outline` -- là tên hợp lệ).
- Thử tay đầu cuối trên dev với `gpt-4o-mini`.

## Decision Records

### Decision: Chia việc chạy trong lượt `propose`, không qua một task queue mới

options considered: BE gọi một task AGENT mới (`split_outline`) lúc chạy `start_drafting`; AGENT chia
ngay khi dựng plan từ lời đồng ý (`approved_plan`) và gửi job kèm plan.
selected option: chia trong lượt `propose`.
reason: lời chia việc phải hiện **cùng lúc** với plan (khối *thinking* đứng trước khối bước), không
thêm tên task queue hay một vòng chờ thứ hai, và BE chỉ việc kiểm số job với con số của dàn ý đã xem.

### Decision: Job đi vào `brief.outline` như mục một câu

options considered: bảng hay cột mới cho job; giữ `DraftBrief.outline` và `DraftItem.outline_item`,
mỗi phần tử là một job `questions=1`.
selected option: giữ hai cột cũ.
reason: thay câu, nút *Thử lại* ô hỏng và câu làm lại ở pha 2 đã đọc đúng hai cột ấy; không cần
migration, và mỗi ô vẫn trỏ về đúng brief job của nó.

### Decision: Sửa dòng invariant ADR-29 của `AGENTS.md`

options considered: giữ chữ *"a drafting job gets its outline item"* (nay sai nghĩa); sửa thành job
AGENT chia và thêm test canh cổng `split`.
selected option: sửa.
reason: dòng ấy là chỉ mục thi hành; nói *mục dàn ý* khi không còn mục nào là chỉ sai chỗ. Luật
*job không nhận chữ tài liệu thô* không đổi; thêm `test_a_drafting_plan_must_carry_a_split_of_exactly_the_outline_s_count`
vì cổng mới là chỗ luật ADR-38 sống. `CLAUDE.md` và các `AGENTS.md` con không nhắc dàn ý: không gì
phải quét theo.

## Status

Xong 13/11/2026. Chưa commit: chờ người dùng duyệt cách chia commit.
