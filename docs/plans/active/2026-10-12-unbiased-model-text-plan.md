# Plan 4c — text model đọc không bám một chương Toán nào, và câu hỏi lại có đủ lựa chọn

Plan con của `2026-10-07-doc-pdf-vao-ngu-canh-plan.md`, sau 4a và 4b.

## Goal

Hai bản rà ngày 12/10/2026 (một cho `services/agent`, một cho BE + `services/document`) và một
lượt phản biện tìm ra: text mà model đọc -- prompt, skill, mô tả tool, tiêu chí Jev, câu từ chối --
mang **ví dụ nội dung** của vài chương Toán cụ thể: *"Hàm số"*, *"tích phân"*, `$y = x^3 - 3x$`,
`$\int_0^1 …$`, `error_label` *"đọc ngược chiều biến thiên"*, *"căn bậc 3 của x^2"*, *"1. HỆ THẬP
PHÂN"*, *"Cho hai tập hợp"*, *"Cách ghi số tự nhiên"*. Repo đã đo một lần gpt-4o-mini **chép chữ**
từ ví dụ (`agent/graphs/naming.py`), và hai câu thử tay **trùng nguyên văn** ví dụ trong prompt --
nên *"đạt"* không chứng minh model khái quát được.

Người dùng chốt 12/10/2026:
- Trước mắt **chỉ môn Toán**, nhưng không text nào được bám **một chương / một mảng kiến thức Toán**.
- Phạm vi: **cả Kriky lẫn document agent**. Được đo lại trên model thật.
- **Suy môn từ phạm vi** là cần thiết -- giữ, viết lại không ví dụ chương.
- `ask_clarify` phải có **ít nhất 3 lựa chọn** cho giáo viên.

## Scope

Trong: mọi text model đọc ở `services/agent` (`_CORE`, ba skill, `authoring`, `explain`,
`reporting`, `naming`, `skill_router`), ToolSpec và câu từ chối ở `services/be`, tiêu chí Jev và hai
prompt của `services/document/index/llm.py`; bộ đo trước-sau; luật *≥ 3 lựa chọn*. Ngoài: đa môn và
ADR-18 cho môn không tính toán; sửa `rules.py` dựng cây (là code, không phải text model đọc -- chỉ ghi
lại những chỗ bám KNTT); cây vàng thứ hai soạn tay.

## Decision Records

### Decision: ba loại ví dụ, ba cách xử lý

**options considered:** (a) bỏ mọi ví dụ · (b) **phân loại rồi xử lý theo loại** · (c) giữ, chỉ thêm
ví dụ khác chương.

**selected option:** (b).

**reason:** bản phản biện chỉ ra ví dụ **định dạng** đang chịu lực -- `{1.assessment_id}` là cú pháp
plan; `$\frac…$` là đúng chuỗi từng làm hỏng escape (ADR-26) -- còn ví dụ **nội dung** đứng một mình
là thứ model chép. Nên: nội dung → luật trừu tượng hoặc chỗ trống (`<tên mục>`); định dạng → giữ,
nhưng ký hiệu chung không gắn chương (`$\frac{a}{b}$`, `$x^{2}$`, `$\sqrt{x}$`, `$a \le b$`); ví dụ
được thêm sau một lỗi **đã đo** → giữ **ý**, đổi chữ, đo lại -- test đang khoá nguyên văn chuyển sang
khoá ý.

### Decision: đo trước khi sửa

**options considered:** (a) sửa rồi thử tay · (b) **dựng bộ đo Toán đa dạng, chạy trên prompt hiện
tại, sửa, chạy lại**.

**selected option:** (b).

**reason:** plan 4a đo được đổi chữ ít khi giúp mà có lúc phá (phần intent mới của `soan-de` làm
ca tra lớp tụt còn 1/6). Mọi thước đo hiện có một miền: 15/15 ca soạn đề của `skill_bench` là Toán
*"12A"*-hoá, thử tay một cuốn, cây vàng một cuốn. Không đo thì một lần tụt không ai thấy.

### Decision: ≥ 3 lựa chọn do model đề xuất, cộng "Khác"

**options considered:** (a) BE dựng mọi phương án, đúng ADR-23 nguyên văn · (b) **model đề xuất ít
nhất 3 phương án, BE luôn thêm "Khác"** · (c) đếm ô trả lời tự do là một lựa chọn.

**selected option:** (b) -- người dùng chốt 12/10/2026.

**reason:** hôm nay câu hỏi về **tham số** (số câu, khối, phạm vi khi chưa có tài liệu) không có nút
nào, vì ADR-23 bỏ mọi chữ model viết -- giáo viên phải gõ lại cả câu. Model đề xuất được những phương
án hợp ngữ cảnh mà một bảng mức cố định không có.

**Giữ phần ADR-23 đo được là đúng:** bản lọc đầu rò hai chiều (*"12A-1"* lọt nhờ *"12A"*). Nên với
câu hỏi về **thực thể** (lớp, tài liệu, mục -- tức có `candidates` trong kết quả tool), BE chỉ giữ
phương án model viết **khớp đúng** một nhãn BE đã dựng (không khớp mờ); khớp không được cái nào thì
lùi về nhãn của BE như hôm nay. Hệ quả nói thẳng: dữ liệu ít hơn 3 thực thể thì câu hỏi có ít hơn 3
phương án thật -- BE không bịa thực thể cho đủ số. "Khác" luôn là phương án cuối, do BE thêm; bấm nó
là gửi chữ *"Khác"*, Kriky hỏi lại bằng câu mở. Không đổi giao diện (nút đã có). Hậu ký ADR-23.

## Files

| File | Việc |
|---|---|
| `tools/propose_bench/` (mới) | ca Toán đa dạng (khối 6--12; số và đại số, hình học và đo lường, thống kê và xác suất; tên lớp lạ), gọi thẳng `propose`, chấm `kind` **và** tham số model điền; chấm câu soạn ra qua kiểm của BE |
| `tools/skill_bench/cases.json` | đa dạng hoá ca Toán |
| `services/agent/tests/` | test *câu đo không bao giờ nằm trong prompt*; test khoá ý thay khoá nguyên văn |
| `services/agent/src/agent/graphs/{propose,authoring,explain,reporting,naming}.py`, `skills/*.md` | bỏ ví dụ nội dung, ví dụ định dạng không gắn chương |
| `services/be/src/be/teacher_tools.py`, `teacher_chat.py` | ToolSpec có dấu, không ví dụ nội dung; câu từ chối; luật ≥ 3 lựa chọn |
| `services/document/src/document/index/{jev,llm}.py` | tiêu chí Jev và hai prompt không ví dụ chương |
| `docs/decisions/adr-23-…md` | hậu ký *≥ 3 lựa chọn* |

## Ordered Tasks

Mỗi task: xong → subagent review → sửa → task kế. Đo trên model thật, chi phí ước ở mỗi task.

- [x] T1. Bộ đo: `propose_bench` + đa dạng hoá `skill_bench` + test *câu đo ngoài prompt*. Chạy
      **baseline** trên prompt hiện tại (~$0,05).
      **Baseline** (`data/run-12/model-text-baseline`, gpt-4o-mini, 6 lần/ca, sau review T1): propose
      **41/108**. Chín ca soạn đề **đủ bốn mục, khác chương**: **9/54** -- model hỏi lại *phạm vi* dù
      giáo viên đã nói chủ đề (nhiều nhất), hỏi *"có tài liệu nào không"* (bước tài liệu đứng đầu
      `soan-de` từ 4b), gọi `list_class` vì câu có tên lớp. Hai ca tra lớp: **0/12** điền đúng tham số
      -- model đặt tên lớp vào chỗ **tên** tham số (`{'9A2': ''}`), lỗi có từ trước, nghi `_Argument.name`
      trùng tham số `name`. Soạn câu 12/12 qua ADR-18; đặt tên 8/8. Router (`data/run-9`, 49 ca): recall
      100%. Dao động giữa hai lượt cùng prompt tới ±3/6 một ca (run-10 so run-11), nên so **tổng gộp**
      và chỉ coi một ca tụt khi tụt ≥ 3/6. Review T1 sửa thước: kiểm tham số tool, cấm *"tài liệu"* khi
      không có chip, chữ chỉ việc không tính là chép, ghi skill Jev đã chọn, `_model_text` gồm cả schema
      structured output và câu BE ghi vào lịch sử.
- [x] T2. Kriky: `_CORE`, skill, `authoring`, `explain`, `reporting`, `naming`, ToolSpec, câu từ
      chối. Chạy lại bộ đo, so baseline.
      **Đã làm:** ví dụ nội dung thay bằng khuôn chung (luật viết Toán, tiêu đề bước, `naming`,
      `error_label`, `SolutionMethod`); ToolSpec có dấu, chỉ nói *làm gì + tham số*; `_Argument.name`
      → `param` (sửa lỗi điền tên lớp vào chỗ tên tham số); `soan-de` viết lại: môn suy từ phạm vi,
      khối là con số đầu tên lớp, chủ đề hay chương đã là phạm vi đủ dùng, không tự viết câu hỏi ra
      lời. **Thủ tục sách rời skill** sang `propose._BOOK_PROCEDURE`, chỉ chèn ở lượt có sách (chip
      sẵn sàng, hoặc `list_chapters` trong catalog); skill chỉ còn một dòng mở thư viện, kích bởi lời
      giáo viên. Thêm ca `tai-lieu-khong-dinh` (nhắc sách, không chip → `list_documents`).
      **Đo** (gpt-4o-mini, 6 lần/ca, 108 lượt trên 18 ca chung): run-12 baseline **41** → run-13 **80**
      → run-14 **77** → run-15 **75**. So baseline không ca nào tụt; tham số tra lớp 0/12 → 8/12. Hỏi
      *"có tài liệu nào không"*: ~7 lượt (run-13) → **0** (run-14, run-15) sau khi thủ tục rời skill;
      `tai-lieu-khop-chuong` 3/6 → 5–6/6. Soạn câu 11–12/12 qua ADR-18, đặt tên 8/8. Giữa
      run-13..15 chênh trong dao động; riêng `du-vecto-10` (3 → 0 → 0) và `du-ti-le-thuc-7` (3 → 1 → 1)
      thấp hơn run-13 hai lần liền.
      **Hỏi lại môn học là lỗi T2 sinh ra, không có từ baseline** (sửa ghi chú cũ, review T2): đếm
      lượt `ask_clarify` có chữ *"môn"* ở 8 ca `du-*` -- run-12 **2**, run-13 **3**, rồi run-14 **18**
      (câu *"tên MÔN HỌC, không phải phân môn"* đứng đầu mục), run-15 **10** và run-19 **15** (câu
      *"Ghi tên môn, không ghi tên phân môn"* cuối mục). Câu ấy cũng không chặn được thứ nó nhắm:
      run-19 vẫn có subject *"xác suất thống kê"*. Bỏ ở run-20.
      **Còn lại, có từ baseline:** model đòi thu hẹp phạm vi dù đủ bốn mục; `list_class` khi câu soạn
      đề có tên lớp. Đổi chữ không gỡ được -- giống 4a, cần một phép sửa cấu trúc (đề xuất để người
      dùng chốt, không làm trong T2).
      **Review T2** (`/code-review xhigh` người dùng chạy, 15 phát hiện, kiểm từng cái trên code và
      số đo). *Sửa:* `_BOOK_PROCEDURE` chèn theo **sự kiện** trong lịch sử (`_book_in_view`: chip
      sẵn sàng, hoặc kết quả tool đọc tài liệu chưa có plan nào nêu sau nó), không theo catalog --
      BE để `list_chapters` trong catalog cả đoạn chat sau một lần đọc (#1, #12); `nodes` ghi lại
      *"bắt buộc khi có document_id"* (#9); comment `teacher_tools` về nơi giữ thủ tục (#12); bộ đo
      chấm plan qua `vet_plan` của BE, bắt tiêu đề dính `<>`, thêm ca `tai-lieu-chua-doc` (#15, #11);
      test khối khoá nguyên cụm (#15). *Thử, đo ra tụt, trả về bản run-15:* mở thư viện ở bước 1
      của `soan-de` (#2) -- run-16 61/120, model hỏi lại *"có tài liệu không"*; *"đủ bốn mục vẫn
      CHƯA nêu plan"* rồi *"Mở đề mới…"* ở thủ tục sách (#4) -- `tai-lieu-khop-chuong` 0–1/6; mô tả
      `topic_scope` riêng cho lượt có sách (#5) -- 18/24 → 9/24 (đo 24 lần, tách riêng); bỏ *"chép
      đúng lời giáo viên"*, bỏ chữ *"tùy chọn"* lặp (#13), viết lại câu tra lớp (#14) -- đo chung với
      các thay đổi trên, không tách được. *Ngoài T2, có từ trước, chờ người dùng chốt:* #3 plan bị
      `vet_plan` từ chối là ngõ cụt; #6 `_faults` yếu hơn `validate_question`; #7 đề nghị sai cấu
      trúc lùi về mock; #8 lượt `plan` hiện thành lời giáo viên; #10 docstring cho dev đi vào
      schema structured output. *Không theo:* #13 đưa luật trùng tên lớp về mô tả tool -- trái quyết
      định *cách dùng nằm trong skill*; Jev hỏng thì nạp mọi skill, và lõi có luật hỏi lại khi một
      tên trỏ nhiều thứ.
      **Đo trạng thái chốt** (run-19, t2g): propose **81/120**; 19 ca chung với run-15 **76/114**
      (run-15: 78). `tai-lieu-chua-doc` 5/6, `tai-lieu-khong-dinh` 5/6. Đo 24 lần cho thấy một ca ở 6
      lần dao động **hơn** ±3/6: `du-pt-bac-hai-9` 9/24 với prompt trùng từng chữ run-15 (khi ấy 5/6),
      nên ca nghi tụt phải đo lại 24 lần trước khi kết luận (Validation sửa theo).
      **Sau review, đo lại** (run-20, t2h): bỏ dòng *"Ghi tên môn, không ghi tên phân môn"*; sửa comment
      lỗi thời về luật nối mục `;` ở `propose.py` (không chữ nào model đọc còn mang luật ấy); thêm
      test giữ `_DOCUMENT_READS` của AGENT và BE là một bộ; baseline T1 9/54 chứ không phải 11/54.
      propose **90/120**; 18 ca chung **79/108** (run-19: 71, run-15: 75, run-13: 80); `du-*` **26/48**
      (run-19: 19); hỏi môn **8** (run-19: 15); nhắc *"tài liệu"* ở ca không sách **0**; subject sai
      **0**. So baseline không ca nào tụt; so run-19 không ca nào tụt ≥ 3/6. Soạn câu 12/12, tên 8/8.
      **Thử tay** (trình duyệt, gpt-4o-mini, AGENT và BE khởi động lại trên code này, câu không có
      trong prompt hay bộ đo): đủ bốn mục *"6 câu… hệ thức lượng trong tam giác vuông cho lớp 9B"* --
      **trượt**, hỏi môn, phạm vi và xác nhận số câu; `known` ghi *"Cần xác định môn học, khối,
      phạm vi kiến thức và số câu"*, tức model chép tên bốn mục chứ không đọc giá trị (đúng lỗi còn
      lại ở trên). Thiếu số câu (*"bất phương trình bậc nhất một ẩn cho khối 10"*) -- **đạt**, chỉ hỏi
      số câu; trả lời *"8 câu"* thì plan hai bước, đề 8 câu Toán khối 10. Chip sách + *"4 câu về phép
      nhân và phép chia số tự nhiên theo tài liệu này"* -- **đạt**: `list_chapters` → `get_chapter`
      → plan, đề mang tên bài, 4 câu đúng bài, đáp án đúng. *Thấy thêm, có từ trước, ngoài T2:*
      `\neq` hiện thành *"xeq"*, cả ở câu lấy từ ngân hàng -- JSON đọc `\n` thành xuống dòng, và
      `latex_escapes` cố ý bỏ qua lệnh dưới 4 chữ sau một xuống dòng (`_MIN_LENGTH_AFTER_NEWLINE`,
      chống nhầm với xuống dòng thật trước `ne`, `to`), nên `neq` 3 chữ không bao giờ được dựng lại
      (đã kiểm: DB lưu xuống dòng + `eq`, KaTeX nhận đúng chuỗi hỏng ấy); đề lấy câu ngân hàng trùng câu mới cùng bài; lời kể *"đã hoàn thành 8 câu"* khi còn câu
      chưa kiểm; gợi ý trên màn chat trống có *"chương Hàm số"* (FE, không phải text model đọc).
- [ ] T3. ≥ 3 lựa chọn: `_Proposal.choices` (mô tả: ≥ 3, không đánh dấu nên chọn), AGENT hỏi
      lại một lần khi thiếu; BE khớp đúng nhãn với câu hỏi thực thể, thêm "Khác"; hậu ký ADR-23.
- [ ] T4. Document: tiêu chí Jev, prompt banner và tóm tắt. `hierarchy_bench` trên cây vàng L6T1
      không tụt (~$0,03), cộng dựng cây một cuốn Toán khác và đọc tay.
- [ ] T5. Thử tay trên trình duyệt với câu **không** có trong prompt; đóng plan.

## Validation Checks

- Bộ đo T1: tổng gộp không tụt, không ca nào tụt ≥ 3/6 so baseline; tham số model điền
  (`subject`, `grade`, `topic_scope`) đúng trên ca **khác chương** với mọi ví dụ cũ. Một ca tụt
  ≥ 3/6 ở 6 lần chỉ là **nghi**: đo lại ca ấy 24 lần rồi mới kết luận (review T2: cùng một prompt
  ra 5/6 rồi 0/6).
- Grep: không còn tên chương, tên bài, hay biểu thức gắn một chương Toán trong text model đọc.
- `.\dev.ps1 check`, `test`, `typecheck` xanh.

## Status

Viết 12/10/2026. 4b đã commit (`b5b6d98`). Người dùng chốt hướng *≥ 3 lựa chọn* cùng ngày.
