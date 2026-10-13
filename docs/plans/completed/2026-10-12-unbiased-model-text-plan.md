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

**Sửa 13/10/2026 (người dùng chốt sau thử tay T5):** "Khác" là **lối để giáo viên tự ghi**, không
phải một lựa chọn -- bấm nó mở một ô ngay trong thẻ, và câu ghi mới là câu trả lời. FE tự vẽ lối ấy,
BE thôi nối "Khác" vào nút. Lý do: gửi chữ *"Khác"* bắt Kriky tốn một lượt chỉ để hỏi lại *"khác là
gì?"*, và lời dặn *"hỏi câu mở"* không giữ được (model bày *"Chương 1/2/3"*). Lần này **có** đổi giao
diện: Figma `Clarify request` thêm hàng "Khác…" và variant `ghi khác`, artboard `3b`.

### Decision: luật thứ tự đọc bằng code, không bằng chữ

**options considered:** (a) tiếp tục đổi chữ trong `soan-de` và `_BOOK_PROCEDURE` · (b) **luật trong
AGENT thay một đề nghị đúng việc mà sai bước bằng một lời gọi tool đọc** · (c) BE tự gọi tool đọc.

**selected option:** (b) -- `_reads_first`, `_picked_book_first`, `_misfiled_read`, `_toc_first`,
`_library_first`, cộng `_which_book` sửa chữ câu hỏi (plan 4c T5).

**reason:** đổi chữ thua ở chính các chỗ này nhiều lần (T2b, T3; T5 run-84..86 không quá 8/24), và
mỗi câu chữ kéo một ca khác -- câu chữa ca logarit kéo `tai-lieu-khong-dinh` 24 → 16/24. Luật nằm cạnh
chỗ đề nghị được dựng; mỗi luật chỉ biến đề nghị thành một lời **đọc**, không bao giờ thành một lời
ghi, và tự kiểm *đã đọc chưa* để không lặp tới trần của BE. (c) bị loại: BE không thấy model đang
nghĩ gì, và chọn tool là việc của pha lên plan. Giá: việc chọn skill của Jev nay bật cả luật code
(`_opens_library`), nên nạp thừa `soan-de` không còn vô hại.

### Decision: tên bền không mang mã task của plan

**options considered:** (a) để nguyên, giải nghĩa mã trong plan · (b) **luật trong `AGENTS.md`,
kèm chỗ thi hành bằng code** · (c) chỉ dặn bằng lời, không kiểm.

**selected option:** (b) -- người dùng chốt 13/10/2026.

**reason:** id ca đo, nhãn lượt đo, thư mục kết quả sống lâu hơn plan đặt ra chúng; khi plan sang
`completed/`, *"t5-sau-list-documents"* hay *"t3e-khop24"* không còn ai giải được. `AGENTS.md` nói
một luật không có nơi thi hành chỉ là ý tưởng, nên kèm `task_code_in`, một test quét id ca và một
lần kiểm `--label` ở bộ đo. Mã task vẫn được dùng trong chính plan, ghi chú của nó và commit message.
Luật tốn hai dòng `AGENTS.md` (trần 182 → 184): một Repo-Specific Trap, một hàng Invariants -- bản
đầu là một đoạn bảy dòng, vượt trần, được viết gọn lại.

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
| `AGENTS.md`, `packages/contracts/src/contracts/teacher_chat.py` | hàng Invariants và docstring `choices` theo hậu ký ADR-23 (T3) |
| `services/fe/src/screens/teacher/Chat.tsx`, `teacher.css`, `teacher.test.tsx`; Figma `Clarify request` (`64:23`), artboard `3b` (`585:3061`); `docs/overview/teacher-surface.md` | lối "Khác" thành ô gõ trong thẻ (sau T5) |
| `tools/{propose,pageindex,ocr,skill}_bench/run.py`, tài liệu nhắc `data/run-*` | kết quả đo dời vào `data/results/` (sau T5) |
| `tools/pageindex_bench/` (đổi từ `hierarchy_bench`), `tools/tests/test_pageindex_score.py` | T6 |
| `AGENTS.md`, `tools/check_contract.py`, `tools/ocr_bench/run.py` (`task_code_in`), `tools/tests/test_run.py`, `tools/propose_bench/{run.py,cases.json}`, `tools/tests/test_propose_bench.py` | T7: tên bền không mang mã task |

## Ordered Tasks

Mỗi task: xong → subagent review → sửa → task kế. Đo trên model thật, chi phí ước ở mỗi task.

- [x] T1. Bộ đo: `propose_bench` + đa dạng hoá `skill_bench` + test *câu đo ngoài prompt*. Chạy
      **baseline** trên prompt hiện tại (~$0,05).
      **Baseline** (`data/results/run-12/model-text-baseline`, gpt-4o-mini, 6 lần/ca, sau review T1): propose
      **41/108**. Chín ca soạn đề **đủ bốn mục, khác chương**: **9/54** -- model hỏi lại *phạm vi* dù
      giáo viên đã nói chủ đề (nhiều nhất), hỏi *"có tài liệu nào không"* (bước tài liệu đứng đầu
      `soan-de` từ 4b), gọi `list_class` vì câu có tên lớp. Hai ca tra lớp: **0/12** điền đúng tham số
      -- model đặt tên lớp vào chỗ **tên** tham số (`{'9A2': ''}`), lỗi có từ trước, nghi `_Argument.name`
      trùng tham số `name`. Soạn câu 12/12 qua ADR-18; đặt tên 8/8. Router (`data/results/run-9`, 49 ca): recall
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
      (đã kiểm: DB lưu xuống dòng + `eq`, KaTeX nhận đúng chuỗi hỏng ấy); đề lấy câu ngân hàng
      trùng câu mới cùng bài; lời kể *"đã hoàn thành 8 câu"* khi còn câu chưa kiểm; gợi ý trên màn
      chat trống có *"chương Hàm số"* (FE, không phải text model đọc).
- [x] T2b. Hỏi thừa khi đủ bốn mục (thêm 13/10/2026, người dùng duyệt thứ tự: lỗi còn lại của T2,
      thấy cả ở thử tay). Bộ đo ghi `known` của từng lượt và nhận `--only` để đo lặp một nhóm ca.
      **Đã làm:** `soan-de` bắt ghi vào `known` **giá trị** bốn mục theo khuôn
      `subject=<giá trị> «<chữ>»; …`, mỗi giá trị kèm chữ của giáo viên, đọc không ra thì `?`, chỉ
      mục `?` mới được hỏi; tham số plan chép từ `known`; môn khác Toán chỉ khi giáo viên gọi thẳng
      tên một môn học; chữ trích cho khối phải là cụm *"lớp …"*, *"khối …"* hay một tên lớp -- số
      câu không phải khối, chủ đề không cho biết khối. AGENT hỏi lại model một lần khi plan thiếu
      tham số bắt buộc (`_IncompletePlan`, luật của `vet_plan` trừ `document_id` khi đoạn chat gắn
      sách -- `bind_book` điền nó); lần hỏi lại hỏng kiểu gì cũng giữ plan lần đầu, nên không bao
      giờ tệ hơn trước T2b. Dòng mở thư viện rời skill thành `propose._LIBRARY`, điền vào chỗ trống
      `{thư viện}` của `soan-de` chỉ ở lượt không chip, chưa đọc sách; `_BOOK_PROCEDURE` thêm *"mục
      KHỚP lời giáo viên, không phải một mục khác thay vào"* và *"document_id đã có … thì không gọi
      list_documents"*. Bộ đo thêm hai ca *có số câu, không khối* và đếm lượt phải hỏi lại model.
      **Đo** (gpt-4o-mini). 8 ca `du-*` × 24 lần: mốc run-21 (prompt run-20) **95/192**, 80 lượt hỏi
      lại → run-38 **185/192**, 0 lượt phải hỏi lại model. Hai ca có số câu không khối × 24: bản đã
      commit **35/48** (`data/results/ab-8b02fd7/run-4`) → run-37 **48/48**. Cả bộ 6 lần/ca (22 ca): run-39
      **120/132**; trên 20 ca của run-20: **109/120** (run-20: 90/120). Hai ca tài liệu × 24 (run-33,
      trước khi sửa khối): không chip 24/24, có chip chưa đọc 24/24. A/B 24 lần với bản đã commit
      (`8b02fd7`, worktree, dữ liệu chép về `data/results/ab-8b02fd7/`): `tai-lieu-chua-doc` 22 → 24
      (run-2 → run-33), `tra-lop-ket-qua` 10 → 13 và `du-xac-suat-10` 14 → 17 (run-3 → run-34).
      **Đường đi, vì mỗi bước đo ra một lỗi mới:** khuôn giá trị một mình (run-22) → plan thiếu tham
      số 1 → 17/192 (run-21 → run-23); thêm hỏi lại khi thiếu → 175/192 (run-24), nhưng model
      **bịa** khối và số câu (`thieu-khoi-va-so-cau` 2/6, run-27; nhắc sách không chip ghi khối 8–11,
      run-25) và lấy một chương khác thay chương không có (`tai-lieu-khong-khop` 0/6, run-25). Kèm
      chữ trích «» → không bịa ở ca thiếu cả hai (6/6, run-28), nhưng model bịa luôn cả chữ trích
      (`grade=9 «9»`). Kiểm chữ trích bằng code thì báo nhầm 68/120 lượt đúng (model trích «Toán» khi
      suy môn; đếm trên run-31), nên bỏ. Vị trí dòng mở thư viện chữa **việc chọn** ở ca nhắc sách:
      giữa các nhánh quyết định (6/6 không chip, 2–3/6 có chip, run-27..29), thành đoạn riêng (0/6,
      6/6, run-31); chỗ trống điền theo lượt giữ được cả hai -- nhưng nó **không** chữa việc bịa:
      run-33 vẫn ghi khối bịa 24/24 lượt ở ca nhắc sách, chỉ là `list_documents` chạy trước. Review
      T2b nghi đúng chỗ ấy với ca *có số câu, không khối*: run-36 **0/48**, model đọc *"12 câu"*
      thành `grade=12 «12»`. Luật chữ trích cho khối chữa nó (run-37).
      **Đánh đổi chưa đo:** ẩn dòng mở thư viện ở lượt có chip, cộng câu *"không gọi
      list_documents"*, làm luồng *đoạn chat gắn sách, giáo viên nhắc một cuốn khác trong thư viện*
      gần như mất đường đi -- BE vẫn đỡ luồng ấy (`_read_other_books`). Lần hỏi lại thứ hai của
      `propose` có từ trước (`_NothingToSay`); khi có model dự phòng, ca xấu nhất vượt
      `AGENT_JOB_TIMEOUT` mà `timeout-order` không tính hai lần chạy graph -- T2b chỉ làm lần ấy hay
      xảy ra hơn (run-38: 0/192 lượt).
      **Còn lại:** subject *"Xác suất thống kê"* ở 1 ca (có từ baseline); plan thiếu
      `start_drafting` ~3/192; `tra-lop-ket-qua` nêu plan với `list_class` (có từ trước, 10/24 ở
      bản đã commit).
- [x] T3. ≥ 3 lựa chọn: `_Proposal.choices` (mô tả: ≥ 3, không đánh dấu nên chọn), AGENT hỏi
      lại một lần khi thiếu; BE khớp đúng nhãn với câu hỏi thực thể, thêm "Khác"; hậu ký ADR-23.
      **Đã làm.** AGENT: `_Proposal.choices` (mô tả: ít nhất 3 câu trả lời -- một giá trị, không phải
      tên mục hay câu hỏi; hỏi về lớp, tài liệu, mục thì chép đúng tên trong kết quả tool);
      `completed` chở nó theo `ask_clarify`; `_FewChoices` hỏi lại model một lần khi ít hơn
      `_choices_wanted` -- 3, hay số dòng `candidates` khi ít hơn 3, hay 0 ngay sau *"Khác"*; lựa
      chọn kết bằng `?` bị bỏ trước khi đếm. `_IncompletePlan` và `_FewChoices` chung lớp `_Flawed`:
      lần hỏi lại hỏng thì giữ đề nghị lần đầu. BE: `_named` + `_choices` -- câu hỏi về một dòng giữ
      nhãn BE, chữ model chỉ sống khi khớp đúng một tên (hai lớp trùng tên không chọn được), khớp
      đủ `min(3, số dòng)` thì bày đúng những dòng model chọn, không thì mọi nhãn; câu hỏi về tham số
      lấy chữ model, gộp trùng, trần 6; luôn thêm `OTHER_CHOICE = "Khác"`. Text: `_CORE` (hỏi kèm ít
      nhất 3 lựa chọn, *"Khác"* thì hỏi câu mở), `lop-va-ket-qua` (choices chép đúng name),
      `_BOOK_PROCEDURE` (choices chép đúng label), `soan-de` (choices là giá trị cho một mục `?`).
      Hậu ký ADR-23, hàng Invariants `AGENTS.md`, docstring `NextStepCompleted`. Bộ đo đòi
      `min_choices: 3` ở 6 ca hỏi lại, ghi nút BE thật bày (`be_buttons`, qua đúng `_choices`).
      **Ba lỗi lộ ra khi đo, sửa trong T3:** (1) thiếu cả bốn mục thì model bày tên mục hay câu hỏi
      làm nút (*"Môn học là gì?"*, 3/6, run-41) -- bỏ lựa chọn kết bằng `?`, mô tả field dặn giá trị.
      (2) `du-xac-suat-10` 8/24 (run-42): `known` ghi *"Xác suất thống kê"* làm môn rồi hỏi phạm vi
      -- đưa `topic_scope` lên **đầu** khuôn, chép phạm vi rồi mới suy môn: 23/24 (run-43). (3) Khi
      model thôi bịa khối (T2b), nhánh *còn ? → hỏi lại* thắng dòng mở thư viện: `tai-lieu-khong-dinh`
      11--14/24 (run-43, run-44), hỏi khối rồi soạn đề không sách -- dời chỗ trống lên **đầu** các
      nhánh, chỉ điền khi câu giáo viên nhắc sách/tệp (`_BOOK_WORDS`, bỏ *"danh sách"*, NFC): 21--23/24.
      Thủ tục sách thì ở lượt có chip, chữ trích của khối là tên tài liệu, và *"không label nào nói
      về điều ấy thì topic_scope=?"* -- câu *"chưa khớp được mục nào thì ?"* làm model ghi ? trước khi
      đối chiếu (`tai-lieu-khop-chuong` 7/24, run-49), bỏ hẳn thì nó thay chương (`tai-lieu-khong-khop`
      2/24, run-50); câu mới 23 và 24/24 (run-51). Thử *"khối từ tên tệp đính kèm"* trong skill: ca
      không chip tụt 21 → 8/24 (run-48), trả về.
      **Đo** (gpt-4o-mini): cả bộ 6 lần/ca (22 ca) run-52 **123/132**, soạn câu 12/12, tên 8/8; 6 ca
      hỏi lại đều 6/6 với `min_choices: 3`. 24 lần (run-53): 8 ca đủ mục **182/192** (T2b run-38: 185),
      5 ca hỏi lại **119/120**; 4 ca tài liệu (run-51) **94/96**. Trên run-52 + run-53: 158 câu hỏi lại,
      138 có 3 nút thật, 19 có 4, 1 có 2; không nút nào là câu hỏi; hỏi lại model 4/444 lượt.
      *(Ghi chú trước review, sai một số: "tên mục làm nút 3/30" -- đếm lại là **15/30**, và lỗi (1)
      chỉ đổi dạng câu hỏi có `?` sang dạng tên mục, tỉ lệ không giảm; bộ đo che nó vì chấm
      `min_choices` trên `choices` thô.)*
      **Review T3** (1 chặn, 7 nên sửa). *Sửa:* (chặn) câu hỏi về dòng kéo sang lượt sau -- bấm
      "Khác" rồi model hỏi tiếp không gọi tool, kèm *"12A (45 học sinh)"*, *"12A-1"*, *"11C"* -- thì
      BE coi là câu hỏi về tham số và bày đúng ba chuỗi ADR-23 đo là rò; nay `_rows_in_play` đọc nút
      đã lưu của câu hỏi lại gần nhất: bày đúng nhãn BE và giáo viên chưa bấm nhãn nào thì câu hỏi
      vẫn về các dòng ấy (test e2e hai lượt). Tập con model chọn **không** còn giấu dòng: chữ model
      chỉ đưa dòng khớp lên đầu, mọi nhãn BE vẫn bày (ADR-23 *"trả về tất cả"*). AGENT: `_answers`
      bỏ câu hỏi, "Khác" model tự viết (58/158 câu có), và tên mục -- không chữ số mà nằm nguyên trong
      câu hỏi; `_choices_wanted` đếm `candidates` từ plan gần nhất, qua các câu giáo viên; hai lần
      đều thiếu thì giữ lần nhiều lựa chọn hơn. `_mentions_book` đọc mọi câu giáo viên từ plan gần
      nhất, thêm *giáo án, đề cương, bài giảng, cuốn, quyển, docx, slide*. `_CORE`: *"hỏi về một tên
      -- lớp, tài liệu, mục -- thì chỉ đưa lựa chọn có trong dữ liệu"* thay câu cấm mọi con số. Không
      lựa chọn thật nào thì không nút nào -- thẻ chỉ có "Khác" mời bấm lại câu vừa gửi. Bộ đo chấm
      `min_choices` trên nút BE thật và đếm câu hỏi có nút là tên mục. Docstring BE/FE, hậu ký
      ADR-23 viết lại theo luật đã sửa. *Thêm khi đo lại:* tham số plan có ký tự điều khiển
      (*"tỉ lệ th\x13"*, *"th\x1c"*, run-53, run-54) thì hỏi lại model (`_garbled`); mọi chữ model
      viết chuẩn hoá NFC (run-57: "ứ" phân rã không khớp). Thử *"không lấy môn làm lựa chọn"* trong
      nhánh *còn ?*: ca nhắc sách 23 → 7/24 (run-58), bỏ đi 18/24 (run-59); dời lên mục subject thì
      21/24 nhưng không giảm nút môn khác (18/50, run-60) -- bỏ hẳn.
      **Đo chốt** (sau review): cả bộ run-61 **123/132**, câu hỏi có nút là tên mục 1, soạn câu 12/12,
      tên 8/8; `tai-lieu-khong-dinh` 24 lần **21/24**, `du-ti-le-thuc-7` **24/24** (run-62). Ca hỏi
      lại × 24 trước hai sửa cuối (run-55): 162/184 câu có 3 nút thật, tên mục 1/30 ở `thieu-het`.
      **Còn lại:** khi chưa có phạm vi, model hay đưa môn khác Toán (*"Ngữ văn"*, *"Tiếng Anh"*) làm
      lựa chọn (18/50 câu hỏi ở hai ca thiếu phạm vi, run-60) -- đổi chữ không chặn được, và chặn bằng
      code là quyết định sản phẩm (hệ thống có hứa soạn môn khác không), chờ người dùng; vài lượt bày
      *"Chương 1/2/3"* khi không có sách; câu hỏi về tham số đến sau một danh sách `candidates` còn mở
      thì nút là nhãn dòng (có từ trước, ghi ở hậu ký ADR-23); `tra-lop-ket-qua` như trước; nguồn của
      ký tự điều khiển và chữ sai (*"tỉ lệ thước"*) trong `topic_scope` chưa rõ. FE: thẻ hỏi lại
      không dựng toán qua `MathText`, và từ T3 mọi câu hỏi lại có lựa chọn đều thành thẻ -- dữ liệu
      đổi, code màn hình không đổi.
- [x] T4. Document: tiêu chí Jev, prompt banner và tóm tắt. `pageindex_bench` trên cây vàng L6T1
      không tụt (~$0,03), cộng dựng cây một cuốn Toán khác và đọc tay.
      **Đã làm** (13/10/2026): tiêu chí Jev bỏ ví dụ nội dung -- *"1.1. Cho hai tập hợp"* →
      *"1.1. Cho ..."*, *"1. HỆ THẬP PHÂN"*, *"2. SỐ LA MÃ"* → *"1. <TITLE IN CAPITALS>"*, *"Cách ghi
      số tự nhiên trong hệ thập phân"* → *"an unnumbered heading in sentence case under a numbered
      section"*; nhãn hoạt động (*"Ví dụ 1"*, *"Luyện tập 2"*…) và ví dụ định dạng của hai prompt
      `llm.py` (*"BÀI 8"*, *"I, II, 3"*) giữ -- định dạng, không gắn chương.
      `test_document_agent_text_names_no_math_topic` bỏ `xfail`, xanh.
      **Đo** (Mongo đã reset nên hai cuốn được tải lại qua BE và OCR lại: Lớp 6 tập 1 `cfe084c2`,
      Lớp 10 tập 1 `09d3f938`). A/B trên cùng bản thô và cùng banner (`state` trùng 492/492 và
      213/213), mốc là worktree `8b02fd7` (bản ghi chép về `data/results/ab-8b02fd7/run-7..10`).
      *L6T1, cây vàng, banner đọc sẵn, mỗi bản một lượt mới:* `jev@0.8` (ngưỡng thật) cũ 87 nút,
      L1/L2/L3 F 90,9/97,3/96,6 % (run-7) → mới 86 nút, 90,9/98,6/96,6 % (run-67). Cổng *"không
      tụt"* thoả **một cách hiển nhiên**: cây mới trùng `tree-rules` từng nút -- Jev giờ thắng luật
      0 ca, trước thắng 1 ca và ca ấy sai (*"Thứ tự thực hiện các phép tính…"* tr. 26, 0,81--0,83 →
      0,73). Số có thông tin là Jev thuần `jev@0`: 137 → 120 nút, L3 F 68,9 → 75,9 %, L2 P 73,3 →
      80,0 % nhưng L2 R 89,2 → 86,5 % (hai bài xuống `deeper` với độ tin thấp). Chính tiêu đề con
      vừa gỡ khỏi ví dụ (*"Cách ghi số tự nhiên…"*, tr. 10) lật từ `deeper` sang `level_3` -- Jev
      từng bám nguyên văn ví dụ. 26/492 quyết định đổi; hai lượt cùng tiêu chí cũ (run-6, run-7) chỉ
      đổi 6, |Δ độ tin| trung bình 0,019, tối đa 0,15.
      *L10T1, không cây vàng, không banner đọc sẵn, 3 lượt mỗi bản:* nhiễu trong cùng bản 6--13/213
      quyết định, |Δ| trung bình ~0,03, tối đa 0,24; cũ so mới 8--15/213, |Δ| ~0,07. Cũ 66 nút cả ba
      lượt, mới 68--69. Jev mới **chắc hơn hẳn trên mục thật của cuốn không phải nguồn ví dụ cũ**:
      28 ứng viên luật gọi cấp 3 tăng ≥ 0,1, một giảm (*"1. ĐỊNH LÍ CÔSIN"* 0,70 → 0,91, *"2 ĐỊNH LÍ
      SIN"* 0,58 → 0,87) -- nhưng ở đó luật vốn đúng nên cây không đổi. Cây đổi ở bốn chỗ, đều do
      tiêu chí: *"1. KHÁI NIỆM VECTƠ"* luật gọi nhãn hoạt động, Jev mới 0,79--0,81 lật thành mục cấp 3
      (**đúng**, 2/3 lượt; cây thật 0,88); *"2. Mệnh để"* -- OCR đọc nhầm mục con *"a. Mệnh đề"* --
      0,64 → 0,83 thành mục cấp 3 (**sai**, có trên cây thật); *"HOẠT ĐỘNG THỰC HÀNH TRẢI NGHIỆM"*
      trên trang mục lục 0,80--0,82 → 0,77--0,79, luật đặt nó thành nút cấp 2 (**sai**, nhỏ nhưng có
      hệ thống); mở đầu Chương IV 0,85 → 0,72--0,75, luật hạ xuống cấp 2 và cả chương lồng dưới
      Chương III (**sai, chỉ trên bộ đo**: bộ đo không có banner nên `open_path` là chữ giữ chỗ;
      cây thật giữ cấp 1 ở 0,84, cách ngưỡng 0,04, một mẫu). **Không sửa tiêu chí** (review T4): sửa
      *"2. Mệnh để"* bằng chữ là trói cấp 3 vào kiểu chữ của một bộ sách và chỉnh theo một mục của
      một cuốn -- đúng kiểu bám mà plan này gỡ; hướng đúng là `letter_case` do code tính, trong
      lượt Jev thứ hai ở backlog. Tốn ~$0,12 cho bộ đo (2 × 0,026 + 6 × 0,011), chưa kể hai lượt
      dựng cây thật (Jev, luna, tóm tắt). `usage` Jev bằng nhau trước và sau đổi tiêu chí -- nó chỉ
      đếm `state`.
      **Đọc tay cây L10T1** (đường thật, tiêu chí mới, 69 nút / 144 chunk): hai nút do tiêu chí như
      trên (*"2. Mệnh để"* cấp 3, *HOẠT ĐỘNG…* cấp 2); các lỗi nặng **có từ trước** và không do tiêu
      chí -- trang mục lục (tr. 5) thành ba chương cấp 1, *"Chương IV VECTƠ"* phủ tr. 5--23 nuốt cả
      Chương I (không có nút *Mệnh đề và tập hợp* nào); tiêu đề OCR rác ở mở đầu chương và vài bài
      (chữ trang trí); chỉ 2/5 cổng banner; *"Bài 6. Hệ thức lượng trong tam giác"* lên cấp 1, trùng
      tên Chương III; bài không mang nhãn *"Bài N"*; hoạt động *"2. Thuế thu nhập cá nhân"* nằm dưới
      Bài 15.
      **Review T4** (0 chặn): sửa đoạn này (L6T1 trùng cây luật, bốn chỗ đổi của L10T1, nhiễu, chi
      phí), docstring `jev_min_confidence` (`document/config.py`) và hai dòng backlog còn ghi *"thắng
      đúng một ca"*, comment `jev.py`. Ghi chú không sửa: `_TOPICS` là danh sách chặn -- một ví dụ
      chương khác (*"Cho tam giác ABC"*) sẽ lọt; quét thêm ~26 từ chủ đề trên text model đọc ra 0.
- [x] T5. Thử tay trên trình duyệt với câu **không** có trong prompt; đóng plan.
      **Thử tay** (13/10/2026, gpt-4o-mini, Chrome, sáu service; agent khởi động lại trước mỗi lượt;
      Mongo reset nên hai cuốn được tải lại ở T4). Câu không có trong prompt hay bộ đo; lỗi lộ ra
      được dựng thành ca, đo 24 lần (tệp ca tạm, wrapper `t5_bench*.py` ở scratchpad; bản
      `documents=True` dựng catalog như BE sau khi đoạn chat đã đọc tài liệu).
      1. *"Giúp mình soạn 6 câu về đạo hàm của hàm hợp, lớp 11B2 nhé"* → plan ngay, Toán / 11 /
         *"đạo hàm của hàm hợp"* / 6.
      2. *"Mình muốn kiểm tra nhanh phần logarit"* → hỏi khối kèm nút. Đáp *"lớp 11, 10 câu"* → plan
         Toán / 11 / *"phần logarit"* / 10 (sau sửa (a)). Bấm nút *"Lớp 11"* → hỏng, có từ trước.
      3. Chip Lớp 6 tập 1, *"Ra 6 câu về ước chung lớn nhất trong sách này"* → plan cả chương II,
         2/6 câu về ƯCLN. Có từ trước, nặng hơn (backlog).
      4. Không chip, *"Lấy cuốn Toán 10 mình mới tải lên, ra 8 câu phần mệnh đề / vectơ"* → trước
         sửa BE từ chối plan; sau sửa `list_documents` → hỏi cuốn → bấm → `list_chapters` → plan →
         soạn. Cây Lớp 10 dựng sai nên *"vectơ"* ra 8 câu mệnh đề -- có từ trước (backlog).
      5. *"Cho mình 10 câu kiểm tra lớp 8"* → hỏi phạm vi → "Khác" → trước sửa (d) model bày
         *"Chương 1/2/3"*; sau sửa câu mở không nút → *"hằng đẳng thức đáng nhớ"* → plan lớp 8.
      **Mốc A/B.** Bản đã commit (`data/results/ab-8b02fd7/run-5..15`) cho mọi ca. Bản đã stage
      (T2b+T3, worktree áp `git diff --cached`, `data/results/ab-staged/run-1..3`) chỉ ba nhóm:
      `thieu-het`, `tra-si-so`, `tai-lieu-khong-dinh`; `du-ti-le-thuc-7`; bước sau `list_documents`.
      Ngoài ba nhóm ấy, *"bản stage"* dưới đây là bản hiện tại đo **trước** khi có sửa nào của T5.
      Nhiễu lớn: cùng bản đã commit, cùng ca, cùng wrapper ra 17 rồi 10/24 (ab run-14, run-15).
      **Hồi quy do T2b/T3, đã sửa:**
      (a) Cụm dùng để suy môn bị coi là đã dùng hết -- *"kiểm tra nhanh phần logarit"* → *"lớp 11,
      10 câu"*: `topic_scope=? «phần logarit»`, hỏi lại dù đủ bốn mục. Bản đã commit 19/24, bản
      stage 5/24 (run-64). `soan-de`: *"cụm suy ra môn vẫn là phạm vi"* → 24/24 (run-79), 21/24
      (run-80). Riêng *"Một phần, …"*: 13/24 (run-78).
      (b) Nhắc sách không chip, đủ bốn mục → plan `list_documents → create_draft → …`, BE từ chối:
      bản đã commit gọi tool 12/24; bản hiện tại 4/24 (run-73 -- đo sau bản đầu của câu (a), nên lẫn
      với nó). `_reads_first` → 21/24 (run-74); cộng `_library_first` → 24/24 (run-80, run-89).
      (c) Câu (a) kéo `tai-lieu-khong-dinh` 24/24 (stage, ab-staged run-1) → 19, 15, 16/24 (run-76,
      77, 79): suy được môn thì chỉ còn thiếu khối, nhánh *"còn ? → hỏi lại"* thắng dòng mở thư
      viện. `_library_first` → 24/24 (run-80, run-89).
      (d) Sau "Khác" model vẫn bày lựa chọn. `_after_other` bỏ chúng -- thành code chết khi nút
      "Khác" thành ô gõ (việc kế tiếp, người dùng chốt).
      (e) Không chip, sau `list_documents`: gọi `list_chapters` đúng cuốn -- bản đã commit 17 và
      10/24, bản stage 4/24 (ab-staged run-3), hiện tại 1--4/24 (run-83, run-87). Câu hỏi ở bước ấy
      hỏi chương, mục mà nút BE là tên tệp: 17/20 câu hỏi ở run-83, 5/22 ở run-87. Sau khi giáo
      viên bấm tên cuốn: model tự gọi `list_chapters` 0/24 (run-87); 4/24 nêu plan với `nodes`
      **bịa** (*"1,2,3"*, *"5"*) mà BE nhận -- không chip thì `nodes` tuỳ chọn. Đổi chữ ba cách thua
      (≤ 8/24, run-84..86). Sửa bằng code: `_toc_first` (plan tạo đề theo tài liệu **chưa đọc mục
      lục** → đọc), `_picked_book_first` (giáo viên chọn đúng một nhãn tài liệu → đọc mục lục của
      nó), `_misfiled_read` (câu hỏi ngay sau `list_documents` mang `list_chapters` của một tài liệu
      trong danh sách: 16/24 lượt ở run-88 -- model đã chọn sách, nộp nhầm `kind`), `_which_book`
      (câu hỏi ở bước ấy hỏi *"Bạn soạn theo tài liệu nào?"* cho khớp nút). Kết quả: sau
      `list_documents` 17/24 gọi `list_chapters` đúng cuốn, 6/24 hỏi câu cố định, 1/24 `call_tool`
      với tên tool `ask_clarify` (run-90); sau khi bấm tên cuốn 24/24 (run-88, run-90). Hướng (i)
      của review -- một tài liệu thì đọc luôn -- là chọn hộ, chưa duyệt.
      **Review T5** (1 chặn, 6 nên sửa), đã sửa:
      - (chặn) `_toc_first` bản đầu chỉ bắt plan thiếu `nodes` -- plan có `nodes` bịa lọt. Nay điều
        kiện là *chưa đọc mục lục* tài liệu ấy (`_tables_read`, đọc lượt `tool_call`).
      - Không luật nào gọi lại một lần đọc đã có từ plan gần nhất (`_called_since_plan`,
        `_tables_read`) -- trước đó lặp tới trần `max_tool_steps` của BE rồi báo lỗi.
      - `_library_first` chỉ thay câu hỏi lại và plan mở đề không `document_id`; `say`, plan
        `start_drafting` (*"soạn thêm 5 câu, bám sát sách giáo khoa"*) để nguyên.
      - Comment, docstring sai (`_LIBRARY`, `_reads_first`, `_toc_first`, `_choose`, D4 của
        `skill_router`); ADR-27 thêm nơi thi hành; mục backlog viết lại (số đọc ngược nghĩa, ca
        ƯCLN chấm sai kiểu số -- bản đã commit 3/24, *"Chương 1/2/3"* là hệ quả của T3, hồi quy còn
        mở được ghi).
      - Test: bốn đột biến review thấy còn sống (tham số của lời đọc, `model_tokens`, kiểm catalog
        của `_toc_first`, nhánh `plannable` của `_reads_first`) cùng cổng skill, chặn lặp, ba luật
        mới -- 11 đột biến, mỗi cái làm ít nhất một test đỏ (`mut_t5b.py` ở scratchpad). Ca âm:
        chip đang xử lý / hỏng, *"soạn thêm"*, *"file Word"*, đã đọc mục lục, tài liệu không có
        trong danh sách.
      **Có từ trước** -- `backlog.md`, mục *"Soạn đề: lỗi lộ ra khi thử tay plan 4c T5"*: lời đáp
      ngắn làm model quên lượt trước (và từ T3 nó chỉ cách một cú bấm); phạm vi là một bài thì đề rải
      cả chương; cây Lớp 10 tập 1 sai cấu trúc. Hai lần BE kẹt khi `--reload` (đã có trong backlog).
      **Đo cả bộ:** run-81 (6 lần/ca, trước các luật của (e) và review): propose 120/132 (run-61:
      123), soạn câu 12/12, đặt tên 8/8 -- không ca nào của bộ đo làm `_toc_first`,
      `_picked_book_first`, `_misfiled_read`, `_which_book` bắn (ca không chip không có
      `list_chapters` trong catalog). Ca nghi đo lại 24 lần: `tai-lieu-khong-khop` 23/24,
      `du-ti-le-thuc-7` 20/24 (bản stage 22/24, chữ hỏng *"tỉ lệ thẃc"* có từ T3), `thieu-het` 17
      và `tra-si-so` 18/24 (bản stage 19 và 20/24). Đo lại cả bộ sau phần "Khác" (đổi `_CORE`).
      **Chi phí:** đếm từ `model_tokens` của bản ghi, ~8,7 triệu token vào (~$1,3 theo giá vào
      gpt-4o-mini) -- thấp hơn thực: `model_tokens` chỉ tính lần gọi cuối của mỗi lượt, không tính
      lần hỏi lại, token ra hay Jev.
      **Sau review T5, người dùng chốt ba việc (13/10/2026)** -- làm theo thứ tự (1) → (3), một review
      chung ở cuối:
      (1) Kết quả đo dời vào `data/results/`: 87 `run-*`, `ab-8b02fd7`, `ab-staged` (chép thêm hai bản
      ghi còn nằm trong scratchpad: `ab-8b02fd7/run-14`, `ab-staged/run-3`). `data/cache/` giữ chỗ cũ
      -- đầu vào của `ocr_bench`, không phải kết quả. Bốn bộ đo ghi vào `data/results/run-<n>/`
      (`_RUNS`, kèm kiểm thư mục chưa có); mọi đường dẫn `data/run-*`, `data/ab-*` trong code, tài
      liệu và ba plan đã đóng đổi theo.
      (2) Sửa theo review T5 -- như trên.
      (3) Lối "Khác" thành ô gõ. Figma: variant `chờ trả lời` thêm hàng "Khác…" (`ink/muted`) và bỏ
      dòng *"Trả lời bằng câu của bạn ở ô nhập bên dưới"*; variant mới `ghi khác` (`585:23`) theo khuôn
      `Composer`; component set đặt mode `Density = Teacher`; artboard mới `3b` (`585:3061`). FE:
      `Clarify` vẽ "Khác…", bấm mở ô (`autoFocus`, Esc đóng, `Gửi` tắt thật khi trống), `questionIn`
      lọc "Khác" của đoạn chat cũ. BE: `_choices` thôi nối "Khác". AGENT: `_after_other` và các nhánh
      của nó thành code chết. Câu *"vừa chọn Khác thì hỏi lại bằng một câu mở"* trong `_CORE` không
      còn bắn nhưng **giữ nguyên văn**: bỏ nó thì ca logarit (*"lớp 11, 10 câu"*) tụt 23 → 6/24, thay
      bằng một câu đúng với hành vi mới thì 0/24 (run-92..94) -- prompt nhạy đúng chỗ ấy. Bộ đo chấm
      *"nút thật"* bằng cách trừ cứng nút "Khác" cuối; BE thôi nối nó nên run-91, run-92 đếm thiếu một
      nút ở mọi câu hỏi -- sửa thành đếm mọi nút trừ chữ "Khác". Test: ba vitest, test
      BE theo nút mới, `test_agent_be_and_fe_agree_on_the_other_choice` kiểm cả hằng `OTHER` của FE.
      **Số đo** Figma ↔ trình duyệt khớp từng số (ghi ở `teacher-surface.md`); hàng ô gõ trên Figma từng
      cao 59 vì `strokesIncludedInLayout` -- tắt cho khớp `Composer` (57). Thử tay: *"Cho mình 10 câu
      kiểm tra lớp 8"* → thẻ ba lựa chọn + "Khác…" → ghi *"hằng đẳng thức đáng nhớ"* → plan, soạn 10 câu.
      **Đo chốt sau ba việc** (gpt-4o-mini): cả bộ run-95 propose **127/132** (run-61: 123; run-81:
      120), soạn câu 12/12, đặt tên 8/8. Ca T5 × 24 (run-96): logarit *"lớp 11, 10 câu"* 21/24, nhắc
      sách đủ mục 24/24, `tai-lieu-khong-dinh` 23/24, góc nội tiếp 24/24, *"Soạn đề phần logarit"* →
      *"Khối 11"* 23/24; hai ca lỗi có từ trước (bản đã commit 0/24) vẫn thấp: *"Khối 11"* sau
      *"kiểm tra nhanh"* 3/24, nút *"Lớp 11"* 4/24 (run-80: 13/24 -- dao động lớn, Jev nạp
      `lop-va-ket-qua`). Không chip: sau `list_documents` 17/24 đọc mục lục đúng cuốn, sau bấm tên
      cuốn 24/24 (run-90).
      **Review chung sau ba việc** (0 chặn, 4 nên sửa), đã sửa: `_which_book` đè **mọi** câu hỏi
      cho tới khi đọc mục lục -- nay chỉ câu hỏi **ngay sau** danh sách tài liệu, chưa câu nào của giáo
      viên chen vào (bản cũ đổi câu hỏi khối thành câu hỏi tài liệu sau khi giáo viên ghi *"thôi, không
      dùng sách"*); dòng backlog hồi quy viết lại theo số mới; năm ca dựa lưng cho luật code chép từ
      scratchpad vào `tools/propose_bench/cases.json` (`dap-khoi-va-so-cau-sau-hoi`, `dap-khoi-sau-hoi`,
      `nhac-sach-du-muc`, `tai-lieu-sau-thu-vien`, `tai-lieu-bam-ten-cuon`) -- bộ đo dựng catalog như
      BE sau khi đoạn chat đã đọc tài liệu; × 24 (run-97): **118/120**, sau `list_documents` 22/24;
      test thêm ca chip cho `_picked_book_first`, `_misfiled_read`, `_which_book` (bỏ guard chip của
      từng luật làm test đỏ) và chi phí của `_misfiled_read`. Ghi chú đã sửa: `_misfiled_read` chặn
      `document_id` rỗng, `_toc_first` bỏ qua tham chiếu `{1.document_id}`, docstring đúng số run-88,
      chữ cũ *"BE thêm Khác"* còn sót; Figma thêm variant `ghi khác — trống` (`588:20`) -- trạng thái
      giáo viên thấy đầu tiên. **Chưa sửa, chờ người dùng:** (a) luật *"đọc mục lục trước khi mở đề
      theo tài liệu"* (ADR-27) chỉ thi hành ở AGENT, BE vẫn nhận `nodes` bịa nếu một đề nghị đi vòng qua
      `_choose`; (b) giáo viên nhắc một cuốn không có trong thư viện thì câu của model bị `_which_book`
      thay -- chưa đo; (c) ba plan đã đóng bị sửa đường dẫn (người dùng chốt), trái luật *không sửa plan
      đã đóng* -- ghi lý do vào commit; (d) gửi từ ô "Khác…" xoá cả bản nháp ở ô nhập chính (`send`
      gọi `setText("")`), như mọi nút lựa chọn từ trước; (e) master `chờ trả lời` trên Figma còn tiêu
      đề 16 không gắn biến và phương án hai dòng -- có từ trước, artboard ghi đè nên khớp code.
- [x] T6. Đổi tên bộ đo `tools/hierarchy_bench` → `tools/pageindex_bench` (người dùng dặn
      13/10/2026): package, import, tên thư mục bản ghi `hierarchy-<model>` trong
      `data/results/run-*`, test `tools/tests/test_hierarchy_score.py`, mọi chỗ nhắc trong code và
      tài liệu (kể cả plan đã đóng). Làm sau phần nút "Khác".
      **Đã làm:** `git mv` package và test (`test_pageindex_score.py`); bản ghi mới ghi vào
      `pageindex-<model>`; chín thư mục `hierarchy-jev-1.13.0` cũ (run-6, run-67..70, `ab-8b02fd7`
      run-7..10) đổi tên, `data/cache/hierarchy/` thành `data/cache/pageindex/` cùng đường trong
      `config.json` của các bản ghi; docstring `jev.py`, `config.py`, `skill_bench`, backlog, plan
      3c (đã đóng -- chỉ đổi tên bộ đo và đường dẫn). Đoạn mô tả task này giữ tên cũ có chủ ý.
- [x] T7. Luật đặt tên: tên bền không mang mã task của plan (người dùng chốt 13/10/2026: id ca đo,
      nhãn lượt đo *"t5-…"*, *"t3e-…"* người ngoài đọc không hiểu).
      **Đã làm:** `AGENTS.md` -- một dòng *Repo-Specific Traps* và một hàng *Invariants*; trần
      `AGENTS_MD_MAX_LINES` nâng 182 → 184 (`tools/check_contract.py`, kèm lý do). Nơi thi
      hành: `ocr_bench.run.task_code_in` (một đoạn tên khớp chữ cái + chữ số + tuỳ một chữ cái:
      `t5`, `T2b`, `a1`; `L6T1` không khớp); `test_bench_case_ids_carry_no_task_code` quét id ca
      của `propose_bench` và `skill_bench`; `propose_bench` từ chối `--label` mang mã task. Năm id
      ca đổi tên: `dap-khoi-va-so-cau-sau-hoi`, `dap-khoi-sau-hoi`, `nhac-sach-du-muc`,
      `tai-lieu-sau-thu-vien`, `tai-lieu-bam-ten-cuon`; bốn id chỉ có trong bản ghi cũng đổi
      (`dap-khoi-sau-hoi-kiem-tra-nhanh`, `dap-khoi-sau-hoi-soan-de`, `bam-nut-lop-sau-hoi-khoi`,
      `tai-lieu-bai-trong-chuong`). 85 thư mục `model-text-<nhãn>` trong `data/results/` đặt lại
      nhãn theo việc chúng đo -- số run giữ nguyên, nên mọi chỗ plan, backlog dẫn *"run-N"* vẫn
      đúng; id cũ bên trong `answers.jsonl`, `report.txt` đổi theo. Bảng tên cũ → mới (85 nhãn, 9
      id) nằm cạnh bản ghi: `data/results/doi-ten-2026-10-13.json` -- plan này và commit cũ còn nhắc
      nhãn cũ (*"run-19, t2g"*) và id cũ (*"t5-logarit-lop"*). Ghi chú: tệp cache của `ocr_bench`
      (`L6T1_p001_200_easyocr_t4.json`) có `t4` là **số luồng**, không phải mã task -- `data/cache/`
      giữ nguyên theo lời người dùng; 50 tệp ấy là cache mồ côi (code nay nối `_text2` vào tên).
      **Review T6/T7** (0 chặn, 4 nên sửa), đã sửa: test khoá việc `propose_bench` từ chối nhãn
      **trước** mọi lời gọi model; id `tai-lieu-khong-dinh-du-muc` va chạm tiền tố với
      `tai-lieu-khong-dinh` ở `--only` (đo lại 24 lần một ca thành 48 lần hai ca) -- đổi thành
      `nhac-sach-du-muc`, thêm test không id nào là tiền tố của id khác; bảng đổi tên ra khỏi
      scratchpad; bảng Files. Thêm: `task_code_in` tách theo mọi ký tự không phải chữ hay số (bắt
      `(t5)`, `t5,list`), tha tên model `o3`, `o4-mini`, bắt `v2` có chủ ý (ghim trong test); hai
      nhãn sai nghĩa đặt lại (run-81 `ca-bo-sau-luat-doc-truoc`, run-97
      `dap-sau-hoi-va-tai-lieu-cases-json`); cột báo cáo canh theo id dài nhất. Không sửa: khoảng 100
      comment dạng *"(review T2b)"* trong `services/` -- luật nói về **tên**, comment là lời dẫn.

## Validation Checks

- Bộ đo T1: tổng gộp không tụt, không ca nào tụt ≥ 3/6 so baseline; tham số model điền
  (`subject`, `grade`, `topic_scope`) đúng trên ca **khác chương** với mọi ví dụ cũ. Một ca tụt
  ≥ 3/6 ở 6 lần chỉ là **nghi**: đo lại ca ấy 24 lần rồi mới kết luận (review T2: cùng một prompt
  ra 5/6 rồi 0/6).
- Grep: không còn tên chương, tên bài, hay biểu thức gắn một chương Toán trong text model đọc.
- `.\dev.ps1 check`, `test`, `typecheck` xanh.

## Status

Viết 12/10/2026. 4b đã commit (`b5b6d98`). Người dùng chốt hướng *≥ 3 lựa chọn* cùng ngày.

**Đóng 13/10/2026.** T1--T7 xong, mỗi task qua review của subagent và đã sửa theo review. Text model
đọc không còn ví dụ nội dung gắn một chương Toán (Kriky lẫn document agent); Kriky không hỏi thừa
khi đủ bốn mục; câu hỏi lại có ít nhất ba lựa chọn, lối "Khác" là ô để giáo viên ghi rõ; luồng soạn
đề theo tài liệu không chip đọc mục lục trước khi mở đề (luật thứ tự đọc bằng code). Đo chốt
(gpt-4o-mini): `propose_bench` cả bộ 127/132 (baseline 41/108 trên 18 ca chung, T1); năm ca thử tay
× 24 118/120; soạn câu 12/12, đặt tên 8/8; cây Lớp 6 tập 1 ở ngưỡng thật không tụt. Bộ đo đổi tên
thành `pageindex_bench`, kết quả đo nằm ở `data/results/`, tên bền không mang mã task (luật mới của
`AGENTS.md`). Commit: `5b80c2b`..`8d68e21`.

**Chuyển sang backlog** (`docs/plans/backlog.md`): mục *"Soạn đề: lỗi lộ ra khi thử tay plan 4c
T5"* -- lời đáp ngắn làm model quên lượt trước, phạm vi là một bài thì đề rải cả chương, nút gợi môn
khác Toán, *"Chương 1/2/3"* khi không có sách, ca cuốn không có trong thư viện, cây Lớp 10 tập 1; và
mục *"Còn treo khi đóng plan 4c"* -- BE tự kiểm *"đã đọc mục lục"*, đọc mục lục luôn khi chỉ một tài
liệu hợp, luật đặt tên cho comment, tên cache `_t4` của `ocr_bench`, bản nháp ô nhập chính bị xoá
khi gửi từ thẻ hỏi lại, hai chỗ Figma lệch code có từ trước.
