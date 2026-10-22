# Plan — Gộp báo cáo cuối lượt vào propose, tool `last_plan`, thử tay không cần db-reset

- **Mở:** 22/10/2026

## Context

- `services/agent/src/agent/graphs/` mới có `propose/` là package; bốn file còn lại nằm phẳng:
  `authoring.py` 456 dòng, `reporting.py` 199, `explain.py` 191, `naming.py` 121.
- Người dùng muốn hai việc, mỗi việc một plan:
  1. Tách các graph còn lại thành package như `propose/`.
  2. Bỏ bước báo cáo cứng cuối lượt (ADR-25).
     - Lượt đã chạy plan thì BE gọi `propose` thêm một lần, có thêm một **tool đọc mới**: tool này kể
       gọn plan vừa chạy, bước nào xong, bước nào hỏng, bước nào không chạy.
     - Quy trình kể lại nằm ở **bước 6 của `soan-de.md`**. Model xử lý mềm theo tình huống, không bắt
       buộc phải nói.
- Sau plan 2, chạy lại toàn bộ thử tay trên trình duyệt: 16 ca ở `docs/testing/cases/` và kịch bản
  `docs/testing/kich-ban-thu-tay-giao-vien.md`.
  - Người dùng chốt: **thiết kế lại để không phải `db-reset`** mỗi lần thử.
  - Dòng `# TODO: Cần xem lại` ở `reporting.py` được xoá cùng file.

## Ràng buộc chung

- Không đụng `docs/report/` và `deploy/`.
- Hai dòng TODO ở `propose/prompt.py` và `propose/compose.py` giữ nguyên, không stage. Sửa
  `compose.py` thì stage bằng blob đã bỏ dòng ấy.
- Trước mỗi commit chạy `.\dev.ps1 check` và `.\dev.ps1 test`. Đuôi commit có `Plan:`, Co-Authored-By
  và Claude-Session. Người dùng đã cho commit sau mỗi plan.
- Sau mỗi pha, subagent review code thật. Mọi đổi FE thì chụp ảnh và so Figma.
- LLM thật chỉ dùng ở pha thử tay của plan 2, model `claude-haiku-5-5` (`.env` dev). Báo chi phí ước
  lượng trước.

## Plan này

Thứ tự bắt buộc (backlog, mục *Lời gọi báo cáo cuối lượt*): **ADR trước, rồi check, rồi code.**

### Pha 1: luật

ADR-25 hậu ký 22/10/2026:

- Bỏ "pha 2 xong thì model báo cáo trong một lời gọi riêng".
- Thay bằng: lượt có chạy plan thì BE gọi `propose` **thêm một lượt kể lại**.
  - Catalog chỉ có tool đọc, gồm cả `last_plan`; `plannable` rỗng.
  - Model nói một câu kết hay không là theo skill.
  - Lỗi của lượt kể lại không làm hỏng lượt chat.
- Sửa ADR-30 dòng 94, `architecture.md` dòng 127, `local-development.md` dòng 193 (danh sách hàm của
  worker).

### Pha 2: tool đọc `last_plan` (BE)

- Đặt ở `services/be/src/be/teacher_tools.py`, theo mẫu `_list_documents` (dòng 990-1015). Đăng ký
  trong `_TOOLS` với `writes=False`, dùng `Running.conversation_id`.
- **Đọc gì:** các dòng `tool_call` / `tool_result` sau dòng `plan` gần nhất của đoạn chat.
- **Trả gì:**
  - `steps`: mỗi bước có `title`, trạng thái `xong` / `hỏng` / `không chạy`, và `detail` ngắn;
  - `progress`: `written`, `asked_for`, `still_drafting`;
  - `found=False` khi đoạn chat chưa có plan nào.
- **Ghi cả bước hỏng `Unresolvable`:** hôm nay bước ấy không để lại dòng nào (`teacher_chat.py:2855-2873`).
  Ghi một dòng `tool_result` `{error, said}` để `last_plan` thấy nó.
- **Dời helper:** `_said_about`, `_went_wrong`, `_how_many` và `_count_questions` sang module mới
  `be/plan_outcomes.py`. `teacher_tools` không import ngược được `teacher_chat` (vòng import).
- **Test:** sửa `test_write_tools.py:669` và `:819` (bộ tool pha 1 và hình dạng kết quả). Thêm test
  `last_plan` cho bốn ca: plan đủ, hỏng giữa chừng, hỏng `Unresolvable`, chưa có plan.

### Pha 3: lượt kể lại (BE) thay `_report`

- **Chỗ sửa:** `teacher_chat.py:3008-3038`. Thay `_report` bằng một vòng `_ask_agent` ngắn:
  - catalog = tool pha 1 cộng `last_plan`, `plannable=()`, trần 2 bước đọc;
  - `say` / `ask_clarify`: ghi dòng `assistant` và phát event **`report`**. FE (`Chat.tsx` `live.report`,
    `spoken()`) không phải đổi;
  - `call_tool` đọc: chạy rồi hỏi tiếp, trong trần;
  - `plan`, `outline`, hay `say` rỗng: không có câu kết, không thông báo. Model được phép im;
  - lỗi model: notice `REPORT_MISSING` như nay.
- **Gỡ:** `_report`, chỗ import `REPORT_PLAN_TASK` / `PlanReportRequested` / `StepOutcome`. Danh sách
  `outcomes` trong bộ nhớ chỉ giữ nếu còn dùng cho event `step_failed`.
- **Test `services/be/tests/test_teacher_chat.py`:** `ScriptedAgent` (dòng 78-114) bỏ nhánh
  `REPORT_PLAN_TASK`; kịch bản thêm bước kể lại. Sửa các test ở dòng 1030, 1056, 1063, 1140, 1165,
  1197, 1427, 1523 theo luồng mới. Thêm hai test: model im thì không có câu kết; model gọi `last_plan`
  rồi nói.

### Pha 4: AGENT, contracts, check

- **`soan-de.md` bước 6**, viết lại từ luật của `reporting._SYSTEM`:
  - sau khi plan đã chạy, gọi `last_plan` nếu cần;
  - nói 2–3 câu đúng điều kết quả nói;
  - còn câu đang soạn thì nói *đang soạn*; đủ câu thì mời xem panel; dừng thiếu câu thì không mời
    duyệt;
  - bước hỏng thì nói thẳng dừng ở đâu;
  - mềm theo tình huống.
- **Mock `next_step`** (`handlers.py:720-876`): lượt kể lại (lịch sử có `plan` cùng kết quả pha 2,
  `plannable` rỗng) nói câu như `plan_report` cũ (dòng 1139-1162), không đổ JSON thô. Máy dev không key
  vẫn có câu kết.
- **Gỡ:**
  - `graphs/reporting.py`, cùng dòng TODO;
  - `report_plan` và `plan_report` (`handlers.py:1139-1199`);
  - đăng ký ở `worker.py:109-112`;
  - `REPORT_PLAN_TASK`, `PlanReportRequested`, `PlanReportCompleted` trong `contracts/teacher_chat.py`
    và `__init__`. `StepOutcome` dời sang BE nếu còn dùng;
  - `SCHEMA_VERSION` của `teacher_chat` lên 2.
- **Test gỡ theo:** `test_reporting.py`, `test_no_routing_decision.py:151`,
  `packages/contracts/tests/test_teacher_plan.py:13-15, 65-85, 97`. Thêm test mock kể lại.
- **`tools/check_contract.py`:**
  - gỡ `check_the_report_is_a_job_of_its_own` (dòng 617-711, `CHECKS` dòng 2491);
  - `_KRIKY_KINDS` bỏ `PlanReportCompleted`; `_MOCK_SPEAKERS` bỏ `plan_report`;
  - `check_kriky_says_nothing_fixed` bỏ `reporting.py` và `report_plan` (dòng 2271-2272);
  - sửa `tools/tests/test_kriky_says_nothing_fixed.py` (dòng 43, 50, 80) và `test_propose_bench.py`
    (dòng 105, 122, 152).
- **backlog:** dòng 390, 413, 414, 781. Đóng tab giữa lượt nay chỉ mất lượt kể lại.

### Pha 5: thử tay không cần `db-reset`, rồi chạy hết

- **Thiết kế lại** `docs/testing/huong-dan.md` và các ca cần dữ liệu sạch, theo cách kịch bản đầu-cuối
  đã làm (mã vòng `Vn`, chạy trên DB đang có):
  - mỗi ca mở đoạn chat mới; tên đề, tên lớp và tên học sinh mang mã vòng;
  - lớp 12B thêm bằng câu `INSERT … ON CONFLICT DO NOTHING`, chạy lại vô hại;
  - ca 16 (học sinh): giáo viên tạo học sinh mới mang mã vòng qua *Thêm học sinh* và phát hành một đề
    mới, thay cho `db-reset` cùng `anhnm`;
  - ca nào đọc "dữ liệu seed" (ca 12) thì đổi sang "lớp và đề của vòng này";
  - sửa luôn chỗ cũ ở bước 3.3 của kịch bản: dàn ý không còn bị bắt hình dạng công thức.
- **Chạy:**
  - 16 ca theo thứ tự `huong-dan` (01–08, 11, 12, 09, 10, 13–16), rồi kịch bản Chặng 0–8, một vòng mã mới;
  - Claude chạy qua Chrome "PC", model `claude-haiku-5-5`;
  - ước lượng lần trước: bộ ca $0,06–0,20, một vòng kịch bản $0,05–0,15. Báo con số này trước khi chạy;
  - cần `ingest`, `document`, `index` cho ca 04, 06, 13–15, cùng hai tệp PDF trong `data/`.
- **Ghi:**
  - biên bản `docs/testing/ket-qua/2026-10-2x-<sha>-claude-haiku-5-5.md` theo mẫu cũ;
  - so riêng **câu kết sau plan**: có hay không, có đúng tiến độ không, có gọi `last_plan` không;
  - lỗi mới ghi vào backlog và artifact.

### Kiểm và đóng

- Thử bẻ một lần cho mỗi luật mới:
  - xoá `last_plan` khỏi catalog kể lại thì test đỏ;
  - để BE nhận `plan` ở lượt kể lại thì test đỏ.
- `check` và `test` xanh. Subagent review sau mỗi pha; review ảnh câu kết so với artboard 5 (`12:46`).
- Commit theo pha (docs luật, BE, AGENT + contracts + check, docs thử tay + biên bản). Đóng plan, cập
  nhật artifact *Backlog theo tier* (Tier 3 P4: bỏ bước báo cáo cứng) và roadmap.
