# Plan 4a — Kriky chọn skill bằng Jev, prompt gốc gọn lại

Plan con của `2026-10-07-doc-pdf-vao-ngu-canh-plan.md`. Người dùng chốt ngày 12/10/2026: plan 4
chia làm **4a** (plan này) và **4b** (soạn đề theo tài liệu, viết file khi 4a xong).

## Goal

`_SYSTEM` của `services/agent/src/agent/graphs/propose.py` (7 319 ký tự) ôm mọi trường hợp trong
một prompt. Đo theo khối: danh tính + 4 việc 15,9% · cơ chế plan 13,5% · ADR-05 13,0% · tra lớp
17,1% · soạn đề 30,8% · không duyệt/phát hành 3,5% · cách viết 6,1%.

Tách nó thành một **lõi** luôn nạp và ba **skill**. Jev (TypeSafe) **trong AGENT** đọc vài lượt
chữ gần nhất rồi chọn skill nào được nạp cho lượt này.

| Skill | Khi nào |
|---|---|
| `tro-chuyen-chung` | Bao quát, mặc định: câu hỏi không cần quy trình (*"căn bậc 3 của x² viết vào đề thế nào"*) |
| `lop-va-ket-qua` | Hỏi về lớp, về kết quả một bài kiểm tra |
| `soan-de` | Mở đề, soạn câu |

## Decision Records

### Decision: lõi giữ mọi luật an toàn, skill chỉ giữ một quy trình

**options considered:** (a) skill mang cả luật an toàn của việc nó lo · (b) **luật an toàn ở lõi,
luôn nạp; skill chỉ là quy trình**.

**selected option:** (b).

**reason:** Jev chọn sai thì một skill vắng mặt, nên một luật mà vắng nó là nguy hiểm không được nằm
trong skill. Lõi giữ danh tính, bốn việc, phần chung của cơ chế plan, bốn điều ADR-05, *không duyệt /
không phát hành*, cách viết và `$`; `test_the_core_carries_every_safety_rule_on_its_own` canh.

### Decision: mỗi skill một câu có/không, "yes" đứng đầu, ngưỡng thấp

**options considered:** (a) một câu `choice` chọn một skill · (b) **mỗi skill chuyên biệt một câu
`choice` yes/no, song song trong một lời gọi**.

**selected option:** (b), nạp khi P(yes) ≥ `SKILL_MIN_YES`; không skill nào qua thì chỉ
`tro-chuyen-chung`.

**reason:** một tin nhắn có thể cần hai skill (*"xem kết quả lớp 12A rồi soạn đề ôn"*). Lỗi bất đối
xứng: nạp thừa một skill chỉ là prompt cũ, thiếu `soan-de` là plan bị BE từ chối. Jev 1.13 nghiêng
về lựa chọn đầu (plan 3c), nên *yes* đứng đầu.

### Decision: state của Jev là chữ, không có kết quả tool

**options considered:** (a) cả lịch sử, gồm kết quả tool · (b) **tối đa 4 lượt teacher/assistant gần
nhất**.

**selected option:** (b), cache trong process theo state.

**reason:** state to làm Jev lạc (plan 3c). Trong vòng tool ≤ 8 bước của BE các lượt chữ không đổi,
nên mọi bước chọn cùng skill mà không phải lưu gì; lời đáp ngắn (*"10 câu"*) vẫn đi đúng skill vì câu
`ask_clarify` ngay trước nằm trong state.

### Decision: Jev hỏng thì nạp cả ba

**options considered:** (a) hỏng thì chỉ skill bao quát · (b) **hỏng thì mọi skill**.

**selected option:** (b). Kết quả chọn chỉ ghi log, không trả về BE -- không đổi contract.

**reason:** mọi skill đúng bằng prompt trước 4a, nên Jev hỏng không bao giờ làm Kriky tệ hơn hôm
qua. Thời gian Jev cộng vào ngân sách job propose, nên `timeout-order` cộng
`SKILL_ROUTER_TIMEOUT_SECONDS`.

### Decision: `known` đứng trước `kind`

**options considered:** (a) đổi chữ ở skill, lõi, mô tả tool · (b) **thêm field `known` đầu schema
`_Proposal`**.

**selected option:** (b) -- người dùng duyệt 12/10/2026.

**reason:** (a) đo ra 0/6 ở mọi biến thể; (b) 4/6. Model sinh JSON từ trái sang phải, nên field đầu
là quyết định đầu. Chi tiết ở Status.

## Files

| File | Việc |
|---|---|
| `services/agent/src/agent/graphs/propose.py` | `_SYSTEM` → `_CORE`; `_compose` chèn skill |
| `services/agent/src/agent/skills/*.md`, `skills.py` | ba skill + bộ nạp frontmatter |
| `services/agent/src/agent/skill_router.py` | Jev chọn skill, đường lùi |
| `services/agent/src/agent/config.py`, `.env.example` | `JEV_*` cho AGENT, `SKILL_MIN_YES`, `SKILL_ROUTER_TIMEOUT_SECONDS` |
| `services/agent/pyproject.toml` | khai `typesafe-sdk`, gói kèm `skills/*.md` |
| `tools/check_contract.py` | cửa `typesafe_sdk` thứ hai; `timeout-order` cộng thời gian Jev |
| `services/agent/tests/` | test lõi, router, đường lùi (`test_skills.py`) |
| `tools/skill_bench/` | bộ nhãn 38 ca + bộ đo quét ngưỡng; test của thước ở `tools/tests/test_skill_bench.py` |
| plan ô | record Jev + record skill viết lại; bảng plan 4 → 4a/4b |

## Ordered Tasks

- [x] Bộ nhãn tiếng Việt cho router (câu đơn, nhiều lượt, duyệt/phát hành, hai skill, câu bao quát).
- [x] Lõi + ba skill + bộ nạp; test lõi luôn mang luật an toàn.
- [x] `skill_router.py`, config, hai chỗ sửa `check_contract`; test đường lùi, ngưỡng, cache.
- [x] Đo router bằng Jev thật trên bộ nhãn (xin phép), hiệu chỉnh `SKILL_MIN_YES`.
- [x] Sửa plan ô; review subagent; thử tay trên trình duyệt.

## Validation Checks

- Bộ nhãn: recall của `soan-de` và `lop-va-ket-qua` bằng 100%.
- `.\dev.ps1 check`, `test`, `typecheck` xanh; gỡ một luật ADR-05 khỏi lõi thì test đỏ.
- Trình duyệt, gpt-4o-mini, Rerun `agent` trước: câu *"căn bậc 3…"* trả lời thẳng; *"tạo đề 10 câu
  chương Hàm số lớp 12A"* nêu plan ngay; *"lớp 12A làm bài 15 phút thế nào"* tra đúng lớp.

## Status

Bắt đầu 12/10/2026. Sau khi skill viết lại thành quy trình: lõi 3 691 ký tự (50% `_SYSTEM` cũ 7 318);
thân skill `soan-de` 1 225, `lop-va-ket-qua` 1 265, `tro-chuyen-chung` 398. Một lượt bất kỳ còn
~4 000--5 000 ký tự prompt trước phần tool, thay cho 7 318.

**Validation:** `.\dev.ps1 check` xanh (20 repo check), pytest 724 qua, vitest 190 qua, `typecheck`
xanh. Đột biến: gỡ một luật ADR-05 khỏi `_CORE` đỏ `test_the_core_carries_every_safety_rule_on_its_own`
(test kiểm từng cụm trong lõi); `>` thay `>=` và gỡ câu trùng tên lớp đều đỏ.

**Review subagent:** tách đầu tiên làm rơi 3 luật tra lớp (trùng tên lớp, *"KHÔNG nhận tên lớp"*,
*"get_class cũng cần id"*) -- trả lại nguyên văn, và `test_no_rule_of_the_old_prompt_fell_between_core_and_skills`
canh từ nay; bộ đo hỏng cả lượt khi một ca timeout -- nay client riêng, ca hỏng ghi lại. Thêm test
đúng ngưỡng (`>=`), lõi đứng trước skill, lịch sử chưa có câu giáo viên. Hai đột biến (`>` thay
`>=`; gỡ câu trùng tên lớp) đều đỏ.

**Bộ đo** (`data/run-7/skill-routing-jev-1.13.0/`): 38/38 ca, 25 185 token, ~$0,0011, trung vị
0,24 s / lời gọi. Recall 100% cho cả hai skill ở **mọi** ngưỡng 0,1--0,5; ở 0,3 precision
`lop-va-ket-qua` 100%, `soan-de` 88% -- hai ca thừa là *"duyệt đề"* (0,35) và *"phát hành đề"*
(0,57), vô hại vì luật của chúng ở lõi. `soan-de` thấp nhất khi cần 0,78, `lop-va-ket-qua` 0,54. Giữ
`SKILL_MIN_YES = 0,3`.

**Thử tay** (gpt-4o-mini), cộng A/B gọi thẳng `propose` với `_SYSTEM` cũ:
- *"căn bậc 3 của x^2…"* → `tro-chuyen-chung`, `say` đúng `$\sqrt[3]{x^2}$`.
- *"lớp 12A làm bài 15 phút thế nào"* → lần đầu Jev nạp cả hai skill và Kriky hiểu thành soạn đề
  (A/B: 5/6 lần, prompt cũ 0/6) -- **hồi quy do phần intent mới của `soan-de`**. Thêm dòng *hỏi một
  lớp ĐÃ làm bài là hỏi KẾT QUẢ*: A/B 6/6 `list_class`; trên trình duyệt Jev chọn `lop-va-ket-qua`,
  3 tool rồi `say` đúng số liệu, Jev được hỏi một lần cho cả 4 bước.
- *"Tạo đề kiểm tra 15 phút chương Hàm số cho lớp 12A, 10 câu trắc nghiệm"* → `soan-de`, nhưng Kriky
  hỏi lại môn. **Không phải hồi quy:** A/B prompt cũ hỏi lại 8/8, prompt mới 8/8; thêm *"môn Toán"*
  thì cũ 6/6 hỏi lại, mới 4/6.

**Skill viết lại thành quy trình** (người dùng, 12/10/2026): mỗi bước một tool, param lấy từ đâu;
mô tả tool phía BE vẫn là *làm gì + param*. Đổi chữ -- ở skill, lõi, hay mô tả tool -- **không**
chữa được ca soạn đề (0/6 ở mọi biến thể). Thứ chữa được là **cấu trúc**: field `known` đứng trước
`kind` trong `_Proposal`, model ghi ra thứ đã biết rồi mới chọn việc.

- Đo (gọi thẳng `propose`, gpt-4o-mini): đủ bốn mục 4/6 và 4/8 nêu plan (trước 0/8); thiếu số câu
  6/6 hỏi lại với `text` có chữ; tra lớp 8/8 rồi 7/8 (một lần nêu plan bằng tool tra cứu).
- Lỗi phụ đo được: model viết câu hỏi vào `known`, để `text` rỗng. Mô tả hai field trong schema, và
  `text` rỗng với `say`/`ask_clarify` thì `propose` hỏi lại một lần, rồi nói *"bạn nói lại giúp"* --
  **không** lùi về mock, vì mock đoán *"ra đề Toán lớp 10…"* thành *"bạn muốn xem lớp nào?"* (review).
- Review A1: thêm hai điểm dừng cho skill tra lớp (`more` thu hẹp rồi vẫn còn; danh sách rỗng), nếu
  không model gọi `list_class` lặp tới trần BE; test ADR-23 kiểm từng cụm luật thay cho `"more" in`.
- Trình duyệt (agent và BE chạy code mới): soạn đề *nêu plan ngay*, 2 bước, đề 10 câu; tra lớp
  `call_tool` ×2 rồi `say` đúng số liệu; câu *"căn bậc 3"* trả lời thẳng, nhưng một lần model viết
  `\root{3}{x^2}` -- LaTeX sai của gpt-4o-mini, không phải lỗi escape.

**Còn lại, ghi nhận:** soạn đề đủ mục mới đạt ~4/6--4/8, không phải 100%; một lượt tra lớp thỉnh
thoảng thành plan tra cứu và BE từ chối nó.

**Một lỗi môi trường đo được, ngoài phạm vi** -- ghi ở `backlog.md`: `dev.ps1 be` chạy `--reload`,
và một file sửa bất kỳ làm uvicorn kẹt ở *"Waiting for connections to close"* vì kênh SSE tài liệu.

**Xong 12/10/2026.**

