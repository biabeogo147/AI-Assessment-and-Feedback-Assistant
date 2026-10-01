# Đường ghi đầu tiên của platform giáo viên

Plan bắt buộc theo `AGENTS.md`: thay đổi này chạm `packages/contracts`, tên task queue, nhiều endpoint,
schema, và bảng Invariants.

## Context

Platform giáo viên hiện **chỉ đọc**. Hai tool `find_class` và `class_assessment_summary` chứng minh
vòng lặp chạy, nhưng agent chưa tạo ra được gì. Ba thứ đang treo vì cùng một lý do:

- `advance()` là cửa duy nhất đổi trạng thái đề và **chưa caller nào gọi nó** — cửa đã dựng, chưa ai
  đi qua. Dòng invariant *"Teacher approves an assessment before release"* trong `AGENTS.md` vì thế
  đúng về chữ và mỏng về tinh thần: hôm nay không đường HTTP nào phát hành được đề chưa duyệt, vì
  không đường HTTP nào phát hành cả.
- `assert_editable()` cũng chưa có caller, nên luật ADR-01 *duyệt khoá nội dung* chưa thi hành ở đâu.
- `entity_kind`/`entity_id` trong `teacher_turns` chỉ nhận được `class`, vì bảy variant
  `Action result card` đều là hành động **ghi** và chưa có hành động nào.

Đợt này mở đường ghi: **soạn đề nháp → duyệt → phát hành cho nhiều lớp**. Không có màn hình nào; Figma
đã có `Publish settings` (`67:41`), `Consequence dialog` (`11:41`), `Action result card` (`10:63`) và
`Question card` (`267:30`) với thuộc tính `Sửa được`, nên việc của đợt này là sản xuất đúng dữ liệu mà
bốn thứ đó cần.

## Luật tổ chức toàn bộ đợt

**Agent viết nội dung; giáo viên quyết trạng thái.**

| Việc | Ai làm | Vì sao |
| --- | --- | --- |
| Tạo đề nháp trống, soạn/thay câu hỏi | **tool** | Đảo ngược được khi đề chưa duyệt |
| Duyệt, bỏ duyệt | endpoint của giáo viên | ADR-01: duyệt là lúc giáo viên **nhận trách nhiệm** |
| Phát hành, thu hồi | biểu mẫu + hộp xác nhận | ADR-02: sáu tham số, không thu hồi được sau giờ mở |

Kiểm được bằng máy: một check mới rằng `advance(` và `withdraw(` **không xuất hiện** trong
`teacher_tools.py`. Cổng thứ nhất của ADR-05 thành bất biến chứ không phải một dòng nhắc trong prompt.

## Scope

**Trong:** `Publication` thành một hàng mỗi (đề, lớp); `Attempt.class_id`; task soạn một-câu; brief
khoá; bảng theo dõi job nháp; hai tool ghi; endpoint duyệt/bỏ duyệt; biểu mẫu phát hành nhiều lớp;
thu hồi; một hằng số cho ba nơi của ADR-03.

**Ngoài, có chủ ý:**

- **Không có FE.** Luật Figma không kích hoạt. Kiểm bằng pytest và `curl`.
- **Không trộn đề.** Bộ 50 câu → mỗi học sinh 10 câu ngẫu nhiên là chức năng sau; ghi nợ ở Pha 1.
- Không sửa từng câu hỏi bằng chat ("sửa câu 4 khó hơn"). Đường ghi đầu tiên là *soạn cả bộ*; sửa lẻ
  cần một tool khác và một vòng thiết kế riêng.
- Không có `assessment_id` trong tool đọc (mục nợ cũ). Pha 2 cấp nó qua đường khác.

## Ngân sách model

Cả năm pha chạy sạch bằng mock. Gọi model thật **một lượt ở cuối mỗi pha có dính AGENT** (Pha 2 và 3),
bằng `gpt-4o-mini`. Pha 1, 4, 5 không cần model.

## Năm pha — mỗi pha bạn review rồi tôi mới commit

### Pha 1 — `Publication` thành một hàng mỗi (đề, lớp)

Đi trước vì nó là pha duy nhất chạm **đường học sinh**, tức rủi ro cao nhất.

- [x] `models.py`: khoá chính `Publication` thành `(assessment_id, class_id)`. Sửa docstring — lý do
      cũ *"hai bộ hạn cùng sống cho một đề là trạng thái không giải thích được cho học sinh"* nay
      **sai**: hai bộ hạn cho **hai lớp khác nhau** giải thích được hoàn hảo, vì mỗi học sinh chỉ thấy
      bộ của lớp mình. 12A học sáng thì mở sáng, 12B học chiều thì mở chiều.
- [x] `models.py`: `Attempt.class_id` — ghi lại lớp lúc bắt đầu làm bài. Cần vì một đề nay có nhiều
      bộ hạn, nên phải biết bộ nào chi phối bài làm này. Nó cũng sửa một lỗi đã có: học sinh chuyển
      lớp thì hạn của bài làm cũ **không** được đổi theo.
- [x] `student_routes.py`: `_publication(session, assessment_id, class_id)` thay cho
      `session.get(Publication, assessment_id)` — tra theo khoá chính một cột nay không còn đúng. Sáu
      call site; năm cái có `attempt` trong tay nên dùng `attempt.class_id`.
- [x] `seed.py`: **không cần sửa** — seed không tạo `Attempt` nào.
- [x] `teacher_tools.py`: `_assessments_of` và `_class_assessment_summary` đã lọc theo cả hai cột,
      kiểm lại là đủ.
- [x] Test: hai lớp cùng một đề với **hai giờ mở khác nhau**, mỗi học sinh chỉ thấy bộ của lớp mình;
      chuyển lớp **không khoá** học sinh khỏi bài đang làm; hạn pha 2 đi theo bài làm chứ không theo
      lớp hiện tại. Năm test.
- [x] `docs/overview/data-model.md` và mục thi hành của ADR-02 — kèm gỡ dòng *"Chưa có ở backend cho
      toàn bộ ADR này"*, nay tự mâu thuẫn với bốn gạch đầu dòng backend ngay phía trên nó.
- [x] `docs/local-development.md`: `create_all` không migrate, nên đổi schema đòi `down -v`. Không
      chỗ nào nói điều đó trước đây, và triệu chứng là `UndefinedColumn` trên mọi lần bắt đầu làm bài.
- [x] `backlog.md`: ghi nợ **trộn đề** — bộ 50 câu, mỗi học sinh 10 câu ngẫu nhiên. Đây là thứ làm
      cho việc nhiều lớp mở lệch giờ không thành lỗ lộ đề, nên nó là nợ **có liên quan**, không phải
      một ý tưởng rời.

### Pha 2 — Soạn nháp: một job một câu, và brief bị khoá

- [x] **Khai tử `draft_assessment`.** Task đó nhận `question_count` tới 50 và gọi model một lần mỗi
      câu, nên một job là tới 3000s so với 70s kiên nhẫn của BE. Invariant timeout đang nói dối đúng
      về nó. Nó là code chết từ ngày được viết nên không phải migrate gì.
- [x] `contracts`: task mới **một câu một job** — `WRITE_DRAFT_QUESTION_TASK`, nhận một `DraftBrief`
      và số thứ tự câu, trả một `GeneratedQuestion`. `llm_timeout × llm_max_attempts` = 60 < 70, nên
      đây là hình dạng **duy nhất** thoả check hiện có.
- [x] `models.py`: `DraftBrief` lưu **trên đề** (môn, khối, phạm vi, số câu, mức độ). Đây là chỗ thi
      hành luật của bạn: cả N job mang **cùng một brief**, nên tính đồng nhất ngữ cảnh được bảo đảm
      *bằng cấu trúc*, không bằng thời điểm.
- [x] `models.py`: bảng `DraftItem` (`assessment_id`, `ordinal`, `job_id`, `status`) — cùng hình dạng
      `PregeneratedItem` của phía học sinh, sinh ra vì đúng lý do đó: model chậm và con người không
      nên chờ.
- [x] `be/drafting.py` **mới**: bắn N job, và `harvest()` đọc kết quả job đã xong rồi ghi `Question`
      + `AnswerOption` + `Method`. AGENT **không** ghi DB; BE thu hoạch. Validate ADR-18 tại lúc thu
      hoạch, không tin nội dung chỉ vì nó là của mình.
- [x] Đề đi từ `EMPTY` sang `HAS_QUESTIONS` ở câu đầu tiên thu hoạch được — qua `advance()`, tức
      caller đầu tiên của nó.
- [x] Test: N job mang brief giống hệt nhau; thu hoạch ghi đúng thứ tự `ordinal`; câu sai shape
      ADR-18 bị từ chối và `DraftItem` ghi `failed` thay vì ghi câu hỏng vào đề.
- [x] Một lượt model thật.

### Pha 3 — Hai tool ghi, và cổng "đủ ngữ cảnh mới được sinh"

- [x] `teacher_tools.py`: `create_draft(subject, grade, topic_scope, question_count)`. **Thiếu trường
      nào thì từ chối** kèm tên trường còn thiếu — đúng khuôn lời-từ-chối-có-ích của ADR-23. Nghĩa là
      model *không thể* bắt đầu soạn khi chưa đủ ngữ cảnh, và lời từ chối dạy nó phải hỏi gì. Luật
      của bạn thành **cấu trúc**, không phải một câu trong prompt.
- [x] `teacher_tools.py`: `start_drafting(assessment_id)` — bắn N job. Từ chối nếu brief chưa đủ,
      nếu đề đã duyệt, hoặc nếu **còn `DraftItem` đang pending**: không bao giờ có hai đợt sinh chồng
      nhau cho một đề.
- [x] Một khi đã bắn, brief **đóng băng**. Giáo viên nói "cho khó hơn" là một brief **mới**, tức một
      đợt sinh mới — không phải một thay đổi giữa dòng. Ghi rõ trong docstring vì đây là chỗ dễ bị
      "sửa cho tiện" nhất.
- [x] `tools/check_contract.py`: check mới — `advance(`, `withdraw(` **và phép gán `.state =`**
      không được xuất hiện trong `teacher_tools.py`. Cộng một dòng trong bảng Invariants của
      `AGENTS.md`, và cap lên 173. Phép gán do review bắt: cửa chỉ có nghĩa khi không ai trèo tường.
- [x] `graphs/propose.py`: prompt biết ba hình dạng từ chối mới, và biết rằng nó **không** được tự
      quyết duyệt hay phát hành.
- [x] Test: brief thiếu → từ chối kèm tên trường; bắn hai lần không nhân đôi job; tool không có đường
      nào chạm `advance`; và — do review bắt — một câu job sinh ra **vào được** đề qua `draft_progress`.
- [ ] Một lượt model thật — **chưa chạy**, Docker Desktop tắt giữa pha. Xem Status.

### Pha 3.5 — Comment trong code viết bằng tiếng Việt

Chen vào giữa Pha 3 và Pha 4 vì nó là một đợt **sửa chữ, không sửa hành vi**, nên nó phải nằm giữa hai
pha chứ không nằm trong một pha nào: trộn nó vào Pha 4 thì diff của Pha 4 sẽ toàn comment và không ai
review nổi phần logic.

- [x] `AGENTS.md § Documentation Rules` sửa **trước** khi chạm một dòng code nào, vì hôm trước luật của
      repo nói ngược lại điều ta sắp làm, và đổi code trước là tự tay tạo ra một file nói dối. Câu mới
      vừa đúng **ba dòng** nên cap 173 không bị chạm — không phải may: bản viết đầu dài bốn dòng và
      `check_contract.py` đỏ ngay, nên tôi viết lại cho vừa thay vì nâng cap. Decision record kèm theo.
- [x] Sweep bốn `AGENTS.md` con và `CLAUDE.md` theo `## Amending This Contract`: grep `English` /
      `Vietnamese` / `tiếng Anh` / `tiếng Việt` cho thấy **không file nào khác** nhắc tới ngôn ngữ của
      comment, nên không có mâu thuẫn phải dọn.
- [x] Phạm vi chốt: comment dòng, docstring, JSDoc. **Không** đổi identifier, thông báo log, message
      của exception, chuỗi hiển thị, tên section (`Args:`/`Returns:`/`Raises:`/`Side effects:`), tên
      tham số trong `Args:`, và mọi chuỗi mà một check hay test so khớp.
- [x] Đo trước khi làm: 54 file Python (4508 dòng docstring + 626 dòng comment) cộng 10 file FE.
- [x] `services/be/src/be` — 19 file, ~286 khối, chia hai nhóm: tầng nghiệp vụ
      (`assessment_state`, `drafting`, `teacher_tools`, `teacher_chat`, `resolve`, `review_policy`,
      `scoring`, `remediation`) và tầng hạ tầng + HTTP (`models`, `student_routes`, `routes`,
      `agent_gateway`, `db`, `config`, `queue`, `identity`, `seed`, `main`, `__init__`).
- [x] `services/agent` — 18 file, ~118 khối. Ba hằng số prompt `_SYSTEM` giữ nguyên **từng byte**, đo
      bằng sha256 trước/sau chứ không bằng mắt.
- [x] `packages/contracts` — 5 file. Tên field tuyệt đối nguyên vẹn; chỉ phần giải thích đổi.
- [x] `services/fe/src` — 9 file, 53 khối. `main.tsx` không có comment nào nên không sửa.
- [x] `services/be/tests` (11 file, 183 khối), `services/agent/tests` (8 file) và
      `tools/check_contract.py`. Docstring test là nơi lý do được ghi dày nhất trong cả repo.
- [x] Thuật ngữ tiếng Anh giữ nguyên như `docs/` vẫn làm. Dịch một thuật ngữ mà code vẫn gọi nó bằng
      tên cũ là cách chắc chắn nhất để một comment thôi khớp với thứ nó mô tả.
- [x] Hai chỗ comment **là dữ liệu** đều đã kiểm: `check_no_tool_changes_an_assessment_state` chỉ bỏ
      qua dòng bắt đầu bằng `#` hay `"`, nên một dòng **giữa** docstring viết `advance(` sẽ làm nó đỏ —
      mọi comment trong `services/be/src/be/*.py` vì thế viết `advance` và `withdraw` **không dấu
      ngoặc**, và grep chính regex của check lên các file đó không khớp dòng nào.
      `check_env_example_has_no_orphans` không bị ảnh hưởng vì `.env.example` không bị chạm.
- [x] `.\dev.ps1 check` xanh (ruff, 2 import contract, 6 repo check), `.\dev.ps1 test` xanh
      (172 pytest, 11 vitest), `.\dev.ps1 typecheck` xanh. Không một dòng đỏ, đúng như một đợt sửa
      chữ phải thế.
- [x] Gọi subagent review phần vừa dịch trước khi sang Pha 4.

**Bằng chứng mạnh hơn mọi phép đếm, và là thứ đáng giữ lại cho lần sau:** một script so **AST** giữa
`HEAD` và bản làm việc của cả 54 file Python — parse cả hai, bỏ docstring, so `ast.dump`. Comment thì
không bao giờ đi vào cây, nên hai cây giống nhau nghĩa là **chỉ có văn xuôi đổi**. Cả 54 file đều
giống. Đọc diff bằng mắt không cho được bảo đảm đó: một biến bị đổi tên hay một string literal bị sửa
một ký tự trông y như một dòng comment trong một diff dài 1600 dòng.

Và một audit ngược: tìm những dòng prose **còn** tiếng Anh. Còn 8 dòng, cả 8 đều đúng là nên giữ —
thông báo lỗi 400 của OpenAI trích nguyên văn (hai chỗ), một comment chỉ gồm tên field, hai tên file
plan, một dòng tiếp của câu Việt mà từ nào cũng là identifier. Nghĩa là không khối nào bị bỏ sót.

Tám chỗ **comment gốc vốn đã nói sai so với code** do năm agent báo lại; sáu chỗ sửa luôn ở đợt này,
vì một comment sai mà được dịch thì còn vô ích hơn lúc chưa dịch — nó vẫn sai, và nay sai bằng hai thứ
tiếng. Đáng kể nhất: docstring package của AGENT vẫn nói nó **chấm bài**, đúng cái niềm tin mà
`legacy_grading.py` tồn tại để dập (ADR-20 chuyển việc chấm sang BE); và `Publication` đếm "sáu tham
số" trong khi tham số thứ nhất của ADR-02 **là lớp**, tức một hàng chở lớp cộng năm cài đặt — cùng lỗi
đếm ấy nằm luôn trong mục thi hành của ADR-02, một dòng tôi tự viết ở Pha 1.

### Pha 4 — Duyệt, bỏ duyệt, và bất biến `state` ↔ số câu hỏi

- [ ] `be/teacher_routes.py` **mới**: `POST /assessments/{id}/approve`, `POST .../unapprove`. Đây là
      caller thật đầu tiên của `advance()` trên đường HTTP.
- [ ] Duyệt từ chối đề **0 câu**, và từ chối khi còn `DraftItem` pending — không duyệt một bộ đề đang
      soạn nửa. Đây là mục nợ *bất biến `state` ↔ số câu hỏi*, và chỗ đúng để đếm là endpoint, nơi đã
      có session (đọc `.questions` trong `advance()` sẽ lazy-load và nổ `MissingGreenlet`).
- [ ] Bỏ duyệt gọi `advance(APPROVED → HAS_QUESTIONS)`, và để lại **bằng chứng** trong `teacher_turns`
      — ADR-01 đòi thẳng điều đó, vì nó là thao tác duy nhất hạ cấp trạng thái.
- [ ] Mọi đường ghi câu hỏi gọi `assert_editable()` trước. Caller đầu tiên của nó.
- [ ] Test: duyệt đề 0 câu bị từ chối; duyệt khi còn pending bị từ chối; sửa câu trên đề đã duyệt bị
      từ chối; bỏ duyệt mở lại được và có hàng `teacher_turns` ghi lại.

### Pha 5 — Phát hành nhiều lớp, xác nhận, thu hồi

- [ ] `POST /assessments/{id}/publications`: sáu tham số **mỗi lớp**, nhiều lớp một lần. Kiểm giờ mở
      ở tương lai và trước giờ đóng (ADR-02).
- [ ] **Từ chối phát hành đề chưa duyệt** — và đây là chỗ dòng invariant của `AGENTS.md` chuyển từ
      đúng-về-chữ sang đúng-về-tinh-thần. Test ở tầng HTTP, không chỉ ở tầng hàm.
- [ ] Thất bại một phần: một lớp nhận được, lớp khác không. ADR-02 cho phép **và nay biểu diễn
      được** — trước Pha 1 thì không. Trả về kết quả từng lớp.
- [ ] `be/publication_wording.py` **mới**: một hằng số cho chuỗi luật pha 1 và một cho pha 2. BE trả
      chúng trong **cả ba** payload — lúc mở biểu mẫu, lúc xác nhận, và trong biên bản sau khi phát
      hành. ADR-03 đòi ba nơi giống hệt nhau từng chữ, và *"ba cách diễn đạt cho một luật là ba
      luật"*; để FE tự viết là ba bản sao chờ lệch nhau.
- [ ] `assessment_state.py`: `may_withdraw(opens_at, now)` và `withdraw(...)`. Xem Decision Record.
- [ ] Thu hồi **một lớp**: đặt `recalled_at` trên hàng của lớp đó, **không xoá hàng** — xem Status,
      `teacher_tools` đã có nhánh đọc trường ấy và xoá hàng sẽ làm nó thành code chết. Đề chỉ về
      `APPROVED` khi **không lớp nào còn giữ** nó — vì nó vẫn đang phát hành cho các lớp còn lại.
- [ ] Sửa lỗi có sẵn: `_publication` ở `student_routes` chưa kiểm `recalled_at`, nên một publication
      đã thu hồi vẫn phục vụ học sinh.
- [ ] Test: ba chuỗi payload giống hệt nhau; phát hành đề chưa duyệt bị từ chối ở HTTP; giờ mở quá
      khứ bị từ chối; thu hồi sau giờ mở bị từ chối; thu hồi lớp cuối cùng đưa đề về `APPROVED`, thu
      hồi lớp không-cuối thì không.

## Decision Records

### Decision: `advance()` giữ nguyên độ thuần; thu hồi là một **thao tác có tên**, không phải một cạnh trong bảng

options considered:

- **A. `_ALLOWED[PUBLISHED]` vẫn rỗng. Thu hồi là `withdraw(...)` trong cùng module, tự chứa cả cạnh
  lẫn điều kiện giờ, nhận **giá trị** (`opens_at`, `now`) chứ không nhận hàng ORM.**
- **B. Thêm cạnh `published → approved` vào `_ALLOWED` vô điều kiện, để endpoint kiểm giờ trước khi
  gọi `advance`.** Đây là thứ tôi đề xuất trong báo cáo trước.
- **C. Cho `advance()` đọc `Publication` và đồng hồ.**

selected option: A.

reason: câu hỏi của bạn làm lộ ra rằng **B yếu hơn chỗ nó tưởng là mạnh**, và tôi diễn đạt nó lẫn.
Nếu `_ALLOWED` cho phép `published → approved` vô điều kiện, thì cửa duy nhất thôi canh đúng cái đáng
canh: bất kỳ caller tương lai nào quên kiểm giờ đều thu hồi được một bài học sinh **đang ngồi làm**,
và `advance()` sẽ vui vẻ đồng ý. Bảng cạnh khi đó nói "đi được", còn "đi được lúc nào" nằm rải rác ở
chỗ khác.

C thì mất độ thuần: `advance()` sẽ cần session, và đọc `assessment.publication` trong ngữ cảnh async
là lazy-load — đúng cái bẫy `MissingGreenlet` đã cắn ba lần trong plan trước.

A giữ một luật đọc được: **bảng `_ALLOWED` chứa các cạnh vô điều kiện; cạnh có điều kiện là một thao
tác có tên, tự chở điều kiện của nó.** Cụ thể `advance()` trả lời *"ADR-01 có cạnh này không"*, còn
`withdraw()` trả lời *"thu hồi được lúc này không"* — và không ai tới `APPROVED` từ `PUBLISHED` mà
không đi qua `withdraw()`, vì bảng không có cạnh đó.

Trả lời trực tiếp câu *"advance hoạt động thế nào khi thu hồi"*: **nó không tham gia.** `withdraw()`
kiểm `now <= opens_at`, gỡ hàng `Publication` của lớp đó, rồi — chỉ khi không lớp nào còn giữ đề —
tự đặt `state = APPROVED` kèm comment giải thích vì sao nó được đi vòng qua `_ALLOWED`. Cả hai hàm ở
cùng một file, nên "cửa" vẫn là một chỗ để đọc.

### Decision: Brief bị khoá trước khi bắn job, và tool từ chối khi brief chưa đủ

options considered:

- **A. `create_draft` đòi đủ trường; thiếu thì từ chối kèm tên trường còn thiếu. Brief lưu trên đề và
  đóng băng khi đợt sinh bắt đầu.**
- **B. Nhắc trong prompt rằng phải hỏi cho đủ trước khi sinh.**

selected option: A.

reason: luật của bạn — *phải thu thập đủ ngữ cảnh trước khi tạo câu hỏi, không được đang tạo thì quay
lại hỏi* — là một luật về **tính đồng nhất của bộ đề**, nên nó phải được bảo đảm bằng cấu trúc. B là
một lời nhắc, và lời nhắc thì model quên được; hậu quả của lần quên đó là một bộ đề mà câu 1..4 sinh
từ một ngữ cảnh và câu 5..10 sinh từ ngữ cảnh khác — một lỗi **không nhìn ra được** khi đọc từng câu,
chỉ thấy khi đọc cả bộ.

A làm điều đó thành bất khả: một brief thiếu trường thì không có job nào được bắn, và lời từ chối nói
đúng trường nào thiếu nên model biết phải hỏi gì. Cả N job đọc **cùng một hàng brief**, nên tính đồng
nhất không phụ thuộc vào việc model có đổi ý giữa đường hay không. Và "cho khó hơn" thành một brief
mới — một đợt sinh mới — chứ không phải một sửa đổi giữa dòng.

### Decision: Cổng thứ nhất của ADR-05 là một check của repo, và `AGENTS.md` được nâng cap lên 173

options considered:

- **A. Một check mới trong `tools/check_contract.py`: `teacher_tools.py` không được chứa `advance(`,
  `withdraw(`, hay `.state =`. Thêm một dòng vào bảng Invariants, tức `AGENTS.md` dài thêm một dòng
  và cap đi từ 172 lên 173.**
- **B. Giữ luật trong prompt của `propose.py` và trong docstring của catalog.**
- **C. Chỉ cấm hai tên hàm, không cấm phép gán `.state =`.**

selected option: A.

reason: luật *"agent viết nội dung, giáo viên quyết trạng thái"* phải đúng với **mọi tool tương lai**,
không chỉ với năm tool hôm nay — nên nó không thể sống trong một prompt (B): prompt là lời nhắc cho
model, còn người thêm tool thứ sáu là tôi hoặc bạn, và không ai đọc prompt trước khi viết một hàm.

C là phiên bản tôi viết trước, và nó hở đúng ở chỗ nguy hiểm nhất. `advance()` là cửa, nhưng cửa chỉ
có nghĩa khi không ai trèo tường: `assessment.state = AssessmentState.APPROVED` trong một tool đạt
đúng kết quả mà ADR-01 cấm, **và né được cả bảng `_ALLOWED`**. Đó lại là dòng mà một bản sửa "cho
nhanh" dễ viết hơn hẳn so với việc đi tìm `advance`. Nên pattern bắt cả phép gán, và tha `==` vì đọc
trạng thái chính là cách một tool quyết định từ chối.

Về cap: `AGENTS_MD_MAX_LINES` lên 173 cho **một** dòng — dòng Invariants mới. Comment của chính hằng
số đó nói cap tồn tại để chặn drift, và chỉ được nâng kèm một decision record nói rõ luật mới nào
biện minh cho nó. Luật mới ở đây là *"No agent tool changes an assessment's state"*, và nó có nơi thi
hành bằng máy, nên nó là một dòng Invariants đúng nghĩa chứ không phải một câu nhắc.

### Decision: Comment và docstring viết bằng tiếng Việt; identifier và chuỗi-máy-đọc giữ tiếng Anh

options considered:

- **A. Comment dòng và docstring sang tiếng Việt, giữ nguyên thuật ngữ tiếng Anh như `docs/` vẫn làm.
  Tên biến/hàm/class, thông báo log, chuỗi exception và mọi chuỗi mà một check hay test so khớp vẫn
  tiếng Anh. `AGENTS.md`, `CLAUDE.md`, `README.md` vẫn tiếng Anh.**
- **B. Mọi thứ sang tiếng Việt, kể cả tên hàm và thông báo log.**
- **C. Giữ nguyên tiếng Anh; comment là cho máy đọc code, không phải cho người đọc sản phẩm.**

selected option: A.

reason: C là trạng thái cũ, và nó dựa trên một giả định sai về người đọc. Người đọc code này và người
đọc đề nó sinh ra là **cùng một người**: Kriky hướng tới người dùng Việt, mọi đề làm ra bằng tiếng
Việt, và phần đáng giá nhất trong các comment ở repo này là *lý do* — nó giải thích nghiệp vụ dạy học
chứ không giải thích cú pháp. Một codebase bàn về phân phối câu hỏi cho lớp 12A bằng tiếng Anh buộc
người đọc dịch hai lượt, và lượt dịch ấy chính là chỗ lý do bị mất.

B thì phá thứ khác. Tên hàm và thông báo log là **giao diện máy đọc**: `tools/check_contract.py` so
`\b(advance|withdraw)\s*\(` theo tên hàm, `lint-imports` so theo tên module, `check_env_example_has_no_orphans`
so tên biến môi trường với `model_fields`. Dịch chúng là đổi hợp đồng chứ không đổi lời giải thích.
Thông báo log còn bị grep bởi con người lúc sự cố, và `docs/local-development.md` dạy người ta đối
chiếu đúng mấy dòng đó.

A cũng không phải luật mới mà là **mở rộng luật đã có**: `docs/` từ đầu đã là "tiếng Việt, thuật ngữ
tiếng Anh giữ nguyên". Nay comment theo cùng quy ước đó, nên không có quy ước thứ hai để lệch nhau.
Giữ nguyên thuật ngữ là phần quan trọng nhất của A: dịch `Distractor` thành "phương án gây nhiễu"
trong comment mà code vẫn gọi nó `Distractor` là cách chắc chắn nhất để một comment thôi khớp với thứ
nó mô tả.

Phạm vi sửa `AGENTS.md`: một đoạn trong `## Documentation Rules`, không đổi số dòng nên cap 173 không
bị chạm. Sweep bốn `AGENTS.md` con và `CLAUDE.md` theo đúng `## Amending This Contract` — grep cho
thấy **không file nào khác** nhắc tới ngôn ngữ của comment, nên không có mâu thuẫn nào phải dọn. Câu
mới nói *"every `AGENTS.md`"* chứ không nói *"this file"*: repo có **năm** file tên đó, và một câu chỉ
miễn trừ file gốc sẽ để bốn hợp đồng con lơ lửng giữa đúng và vi phạm.

phạm vi trong code: **mọi** file có comment, không chỉ code Python. Review bắt đúng chỗ tôi định dừng
sớm — `.env.example` chở đúng lập luận `LLM_TIMEOUT_SECONDS × LLM_MAX_ATTEMPTS` mà
`check_contract.py` nay đã kể bằng tiếng Việt, nên bỏ nó lại là tạo ra **một sự thật sống hai thứ
tiếng ở hai file**, đúng bề mặt drift mà bảng Invariants tồn tại để chặn. Nên không có ngoại lệ nào
được viết vào `AGENTS.md`: `.env.example`, `dev.ps1`, `pyproject.toml`, `.pre-commit-config.yaml`,
`docker-compose.infra.yml`, `tokens.css`, `vite.config.ts` và `packages/contracts/tests` đều đi theo.
Một luật có ngoại lệ không ghi ở đâu là một luật người sau sẽ đoán.

hệ quả, và đây là phần tôi thiếu ở bản đầu: record này dùng cái bẫy regex của
`check_no_tool_changes_an_assessment_state` làm **bằng chứng** cho lựa chọn A, mà không ghi rằng A
**làm cái bẫy đó dễ nổ hơn**. Trước đợt này `teacher_tools.py` có **0** dòng văn xuôi nhắc
`advance`/`withdraw`; nay có 2, và cả file đã được viết lại. Mọi đợt sửa comment sau này đều đi qua bề
mặt đó. Nên đợt này sửa luôn cái gốc thay vì ghi thêm một lời nhắc: check nay lọc bằng `tokenize` —
xoá trắng mọi token `COMMENT` và `STRING` rồi mới grep phần còn lại — nên luật **khớp với lời hứa mà
comment của chính nó đã nói suốt từ đầu** (*"comment và docstring được phép nhắc tên luật"*), điều mà
cách lọc theo tiền tố dòng chưa bao giờ làm được: một dòng ở **giữa** docstring không bắt đầu bằng dấu
nháy nào. Kiểm lại cả hai chiều: vẫn đỏ với `advance(` và với `.state =` trong code, và thôi đỏ với
`advance()` viết trong một docstring. Một đợt sửa chữ đáng lẽ không được làm đỏ một invariant, và nay
nó không thể.

### Decision: `dev.ps1` nhận BOM, và cái bẫy `.ps1` thành một dòng trong `AGENTS.md` (cap 174)

options considered:

- **A. Thêm BOM UTF-8 vào `dev.ps1`, và ghi cái bẫy thành một dòng `## Repo-Specific Traps`. Cap
  173 → 174.**
- **B. Trả comment của `dev.ps1` về tiếng Anh, vì đó là file duy nhất bị.**
- **C. Thêm BOM, không ghi gì: sửa rồi là xong.**

selected option: A.

reason: lỗi này là **hệ quả trực tiếp** của luật ngôn ngữ vừa chốt, và nó thuộc loại tệ nhất — im
lặng ở mọi phép kiểm. `.\dev.ps1 check`, `typecheck`, `help` đều chạy đúng; `check_named_dev_tasks_exist`
xanh vì nó đọc file bằng `encoding="utf-8"` trong Python. Chỉ `Get-Help .\dev.ps1` — đúng cái đường
chính thức để đọc khối `.SYNOPSIS`/`.DESCRIPTION` mà file ấy có — in ra `Má»™t cá»­a duy nháº¥t…`,
vì Windows PowerShell 5.1 đọc một `.ps1` không BOM theo cp1252 chứ không theo UTF-8.

B sai chiều: nó chữa triệu chứng bằng cách lùi luật, và lùi ở đúng file mà một người mới đọc đầu tiên
để biết chạy dự án thế nào.

C là chỗ tôi định dừng, và nó sai vì cái bẫy **không** chỉ thuộc về `dev.ps1`. Nó thuộc về mọi `.ps1`
viết sau này, và nó không có phép kiểm nào canh: không gì trong repo đỏ lên khi một file `.ps1` mất
BOM. `## Repo-Specific Traps` đã chứa đúng một dòng cùng họ — `REDIS_URL` trỏ `localhost` thì resolve
ra `::1` ở máy này — và lý do hai dòng đó cùng tồn tại là như nhau: một hành vi riêng của nền tảng
này, không suy ra được, và không có check nào bắt.

Cap lên 174 cho đúng **một** dòng. Comment của chính hằng số cap đòi một decision record nói rõ luật
mới nào biện minh cho phần dài thêm; luật mới ở đây là *"một `.ps1` cần BOM UTF-8"*, và nơi thi hành
của nó là con mắt người đọc — nên nó là một `Trap` chứ không phải một dòng `Invariant`. Đó cũng là
điểm khác biệt đáng giữ giữa hai bảng: bảng Invariants đòi một nơi thi hành bằng máy, bảng Traps thu
những thứ **không** có.

### Decision: Agent không điền hộ biểu mẫu phát hành

options considered:

- **A. Agent nói "mở biểu mẫu phát hành"; biểu mẫu trống, chuỗi giải thích do BE sở hữu.**
- **B. Agent điền sẵn sáu tham số từ câu nói của giáo viên ("chiều mai"), giáo viên chỉ sửa và xác nhận.**

selected option: A.

reason: ADR-03 dành cả một tài liệu để ngăn **đúng một** hiểu nhầm — giờ đóng là hạn **vào**, không
phải hạn **nộp** — và ghi rõ hiểu nhầm đó gây hại theo chiều ngược: giáo viên muốn bài nộp xong trước
18:00 sẽ đặt giờ đóng 17:45 để bù, tức tự cắt mười lăm phút của cả lớp mà không biết.

Một model điền sáu mốc thời gian từ chữ "chiều mai" **tái tạo chính xác** hiểu nhầm ấy, và giáo viên
sẽ bấm xác nhận vì con số trông hợp lý. ADR-05 cũng đã chốt rằng câu *"phát hành cho lớp nào?"* phải
đi qua biểu mẫu và hộp xác nhận, không qua chat.

## Files

| File | Việc |
| --- | --- |
| `services/be/src/be/models.py` | PK `Publication` kép; `Attempt.class_id`; `DraftBrief`; `DraftItem` |
| `services/be/src/be/student_routes.py` | `_publication` nhận `class_id`; sáu call site |
| `services/be/src/be/assessment_state.py` | `may_withdraw()`, `withdraw()` |
| `services/be/src/be/drafting.py` | **mới** — bắn job, `harvest()`, validate ADR-18 |
| `services/be/src/be/teacher_routes.py` | **mới** — duyệt, bỏ duyệt, phát hành, thu hồi |
| `services/be/src/be/publication_wording.py` | **mới** — một hằng số cho ba nơi của ADR-03 |
| `services/be/src/be/teacher_tools.py` | `create_draft`, `draft_questions` |
| `packages/contracts/.../authoring.py` | khai tử `draft_assessment`; thêm task một-câu |
| `services/agent/src/agent/handlers.py`, `worker.py` | handler mới, bỏ handler cũ |
| `services/agent/src/agent/graphs/propose.py` | prompt biết ba hình dạng từ chối mới |
| `tools/check_contract.py` | check `advance(`/`withdraw(` không ở trong `teacher_tools.py` |
| `AGENTS.md` | một dòng Invariants mới; dòng *Teacher approves* trỏ tới test HTTP |
| `docs/overview/data-model.md` | Nhóm 2 và Nhóm 5 |
| `docs/decisions/adr-01`, `adr-02`, `adr-03`, `adr-18` | mục *Nơi luật này đang được thi hành* |
| `docs/plans/backlog.md` | trộn đề; sửa câu lẻ bằng chat |

## Validation Checks

- [ ] `.\dev.ps1 test` và `.\dev.ps1 check` sau **mỗi** pha
- [ ] `packages/contracts` bị đổi ⇒ chạy cả hai theo bảng Validation của `AGENTS.md`
- [ ] Pha 1: SQL kiểm hai hàng `publications` cho một đề với hai `opens_at` khác nhau
- [ ] Pha 2 và 3: một lượt model thật (`gpt-4o-mini`) ở cuối
- [ ] Pha 5: `curl` đủ chuỗi — tạo nháp → soạn → duyệt → phát hành hai lớp → thu hồi một lớp
- [ ] Luật Figma **không áp** lần này: không màn hình nào bị chạm
- [ ] Mỗi commit mang trailer `Plan: 2026-09-30-teacher-write-path-plan.md`

## Completion Criteria

Giáo viên gõ *"soạn cho tôi 10 câu đạo hàm cho lớp 12"*, agent hỏi nốt phần còn thiếu, rồi bắn 10 job
mang cùng một brief. Câu hỏi hiện dần. Giáo viên duyệt — và không duyệt được nếu còn câu đang soạn.
Phát hành cho 12A mở buổi sáng và 12B mở buổi chiều, hai bộ hạn độc lập. Thu hồi 12B trước giờ mở
được; sau giờ mở thì không; thu hồi lớp cuối cùng đưa đề về `đã duyệt` chứ không về nháp.

Và mỗi bước đó đọc lại được từ `teacher_turns`, kèm `entity_kind = assessment`.

## Status

**Pha 1 xong, chờ bạn review.** 147 pytest, 11 vitest, 5 repo check xanh.

Kiểm trên Postgres thật, và đây là điều model một-hàng **không biểu diễn được**: cùng một đề, cùng
một thời điểm, hai câu trả lời khác nhau.

```
lớp | mở lúc    | status           | actions
12A | 12:59     | đang-mở          | ['start']
12B | 17:59     | chưa-tới-giờ-mở  | []
```

`publications_pkey` trên Postgres nay là `PRIMARY KEY (assessment_id, class_id)`.

Một chỗ đáng ghi: `session.get(Publication, assessment_id)` là tra theo khoá chính **một cột**, nên
đổi khoá làm nó sai âm thầm — nó vẫn chạy, chỉ trả về hàng đầu tiên khớp. Sáu call site đã đổi, và
năm trong số đó dùng `attempt.class_id` chứ không dùng lớp hiện tại của học sinh: đó là lý do
`Attempt.class_id` tồn tại, và test thứ tư chứng minh chuyển lớp không đổi hạn của bài đã làm.

### Review Pha 1 bắt gì

Ba thứ nghiêm trọng, và hai trong số đó là **cùng một loại lỗi**: tôi đổi hình dạng dữ liệu rồi tin
rằng mọi chỗ đọc nó đã theo kịp.

- **`start_attempt` tra publication trước khi tra attempt**, nên cổng vào bị áp lại bằng lớp **hôm
  nay** mỗi lần gọi. Học sinh chuyển từ 12A sang 12B bị trả 409 *"chưa tới giờ mở"* về chính bài mình
  đang làm dở — hoặc 404 nếu lớp mới không được phát hành đề đó. Đây đúng là hạng bug mà
  `Attempt.class_id` sinh ra để diệt, và nó là call site duy nhất còn sót. Nó cũng **vi phạm ADR-03**,
  luật đã chốt từ lâu: *"Học sinh đã vào rồi thì không bị dừng giữa chừng."* Cổng canh việc **vào**,
  không canh việc tiếp tục.
- **`Assessment.publication` vẫn là `uselist=False`.** Chưa caller nào dùng nên chưa nổ, nhưng nó là
  một cái cưa để sẵn đúng trên đường Pha 4/5 đi qua: SQLAlchemy gặp nhiều hàng ở quan hệ một-một thì
  **cảnh báo rồi trả về một hàng bất kỳ**, nên một endpoint thu hồi sẽ kiểm giờ theo lớp *ngẫu nhiên*.
  Nay là `publications: list`.
- **Test thứ tư của tôi là test rỗng.** Nó so `ends_at` trước/sau khi chuyển lớp, mà `ends_at` là một
  cột ghi một lần lúc bắt đầu, và route trả nó **không đọc publication** lần nào. Nó xanh y nguyên kể
  cả khi revert cả năm call site. Thay bằng `remediation_deadline` ở `/result`, vốn đọc lại từ
  publication mỗi request — và tôi **đo** thay vì suy luận: revert đúng một call site làm hạn ấy nhảy
  mười hai tiếng (22:09 → 10:09 hôm sau).

Và hai chỗ tài liệu: ADR-02 còn dòng chốt *"Chưa có ở backend cho toàn bộ ADR này"* ngay sau khi tôi
thêm bốn gạch đầu dòng backend vào cùng mục đó; `local-development.md` không có chỗ nào nói rằng đổi
schema đòi `down -v`, trong khi `create_all` nói thẳng là nó không cứu được bảng đã đổi hình dạng.

Một điều review xác nhận ngược lại điều tôi lo: lập luận *"docstring cũ sai"* **không** phải viết lại
lịch sử — nó còn nói nhẹ đi. ADR-02 mục *Hệ quả* đã đòi *"phải nói rõ lớp nào đã nhận bản ghi phát
hành — với những lớp đó, thu hồi vẫn được nếu chưa qua giờ mở"*, tức đòi hàng phát hành **từng lớp**.
Docstring cũ không chỉ nhầm; nó mâu thuẫn trực tiếp với ADR-02 từ ngày được viết.

### Đã quyết trước Pha 5, từ review

Thu hồi là **soft**, không phải `DELETE`. `Publication.recalled_at` đã tồn tại và
`teacher_tools._class_assessment_summary` **đã có** nhánh đọc nó để trả *"đề này đã bị thu hồi"*. Nếu
thu hồi xoá hàng, nhánh đó thành code chết và tool trả *"đề này chưa phát hành cho lớp đó"* cho một
đề giáo viên vừa thu hồi — sai đúng chỗ ADR-02 dựng nhánh ấy lên để tránh. Plan Pha 5 phải sửa theo.

Kèm một lỗi có sẵn cần sửa cùng lúc: `_publication` ở `student_routes` **không kiểm `recalled_at`**,
nên một publication đã thu hồi vẫn phục vụ học sinh.

### Pha 2 — xong, chờ review

155 pytest, 11 vitest, 5 repo check xanh. Và chạy thật trên `gpt-4o-mini` qua worker thật + Postgres
thật: ba job bắn song song, **cả ba đáp trong 12 giây**, `state` lên `has_questions`, ba câu khác
nhau trên cùng một phạm vi.

**Điều đáng nhất của pha này: invariant `timeout-order` thôi nói dối.** Nó so
`LLM_TIMEOUT_SECONDS × LLM_MAX_ATTEMPTS` = 60 với 70 và báo xanh, trong khi `draft_assessment` gọi
model một lần **mỗi câu** với tới 50 câu một job — trường hợp xấu nhất 3000s. Tôi **không** sửa bằng
cách nhân thêm `question_count` vào phép so: làm thế thì check đỏ, và đường ra là nâng hạn job lên 50
phút, tức BE thôi phân biệt được worker chậm với worker chết. Sửa bằng cách đổi **hình dạng công
việc**. Nay mọi task đều nằm trong đúng một câu hỏi đáng giá số lần thử.

Còn một chỗ chưa bảo vệ được bằng máy: không gì ngăn ai thêm một vòng lặp theo số lượng vào một
handler và làm check nói dối **lần thứ ba** — nó đã sai đúng cách đó hai lần. Docstring của check nay
nói ra điều đó.

**Và lượt chạy thật lộ ra một thứ không test nào bắt:** ba câu cùng một brief viết số mũ ba kiểu —
`x³` ở câu 1, `x^3` ở câu 2 và 3. Prompt đòi Unicode và cấm LaTeX; `x^3` không phải LaTeX nên nó lọt.
Đây là **cùng loại lỗi** mà brief-bị-khoá dựng lên để ngăn, chỉ ở tầng hình thức: đọc từng câu không
thấy gì sai, đọc cả bộ mới thấy nó không phải một bộ. Ghi vào `backlog.md` kèm hai đường ra, chưa
chọn vì thêm một luật về *hình thức chữ* vào `validate_question` là một quyết định về phạm vi ADR-18.

**Chưa có caller nào** cho `fire()` và `harvest()` — tool bắn ở Pha 3, endpoint thu hoạch ở Pha 4. Nói
ra để không ai đọc pha này như một tính năng đã dùng được.

### Review Pha 2 bắt gì

Bốn thứ nghiêm trọng. Ba trong số đó là chỗ tôi **sao chép một pattern mà không sao chép hết lý do
của nó**, và cái thứ tư là một hàm tôi tưởng đang chạy.

- **`order_index` lấy từ biến đếm, không lấy từ `ordinal`.** Job chạy song song và đáp theo thứ tự
  model trả lời — đúng điều lượt chạy thật vừa chứng minh. Nên: `harvest` lần 1 thấy job 2 và 3 xong
  thì cho chúng vị trí 1 và 2; lần 2 job 1 xong thì nhận vị trí 3. Giáo viên yêu cầu 1, 2, 3 và nhận
  **2, 3, 1** — âm thầm, không constraint nào chạm. Nay `order_index = row.ordinal`, đúng với mọi thứ
  tự đáp.
- **`banned_stems` vô hiệu 100%,** đo được: BE gửi stem qua `resolve.normalise` (viết cho **tên
  lớp** — bóc chữ "lớp", xoá hết khoảng trắng, casefold) còn AGENT so bằng `authoring.normalise`
  (chỉ gộp khoảng trắng). `"Đạo hàm của y = x² là gì?"` thành `"đạohàmcủay=x²làgì?"` và không khớp
  gì. Docstring của `authoring.normalise` tự cảnh báo đúng chuyện này: *"Two functions that must
  agree, in two files, is a disagreement with a date on it"* — và tôi tạo ra nó. Sửa: BE gửi stem
  **thô**, AGENT chuẩn hoá bằng hàm của chính nó, đúng như đường retry **vốn đã làm**. Tôi chỉ không
  đi theo pattern có sẵn.
- **Không có đường thử lại một vị trí bị từ chối.** `harvest` đánh `failed` cho cả ba loại thất bại,
  và `fire` bỏ qua mọi vị trí đã có hàng — nên hai loại **ngẫu nhiên** (trùng stem, sai shape) làm
  đề thiếu câu **vĩnh viễn**. Gốc `_harvest` thì **xoá** hàng khi validate lỗi, đúng bằng lý do
  docstring của nó nói. Nhưng xoá vô điều kiện lại là lỗi ngược: một câu model không viết nổi sẽ bị
  bắn lại mỗi lần đọc, mãi mãi. Nay có bốn status và một bộ đếm `attempts`: ba lần thử rồi bỏ.
- **`fire` commit một lần ở cuối** trong khi gốc commit **từng hàng** và bắt `IntegrityError`. Hai
  tool call đồng thời: cả hai bắn 3 job, commit thứ hai đụng unique và rollback **cả ba hàng** —
  6 job đang chạy, 3 trong số đó không ai thu, tiền model đốt sạch, và exception thoát ra caller.

Cộng hai chỗ nữa: `question_count` không có trần trong khi `of_total` có (trần 50) — brief 60 câu sẽ
bắn 50 job **rồi** raise, tức 50 lượt model không ai thu; nay trần kiểm **trước** job đầu tiên. Và
brief "đóng băng" chỉ là một câu trong docstring — không gì thi hành: `DraftItem` không mang version
brief, nên đổi `topic_scope` rồi bắn lại sẽ cho một bộ đề **nửa ngữ cảnh này nửa ngữ cảnh kia**, đúng
cái defect cả thiết kế dựng lên để ngăn. Nay brief có `version`, `DraftItem` ghi version nó được bắn
dưới, và `harvest` **bỏ** câu của brief cũ.

Và một docstring nói quá: mock lấy `origins[(ordinal-1) % len(origins)]`, tôi viết rằng nó "diễn tập
đường chống trùng". Bank có **sáu** câu, nên brief 10 câu bằng mock **chắc chắn** cho 6 câu và 4 vị
trí bỏ — tất yếu, không phải ngẫu nhiên, và một bản demo không có API key sẽ luôn trông như soạn đề
hỏng trên mức sáu. Docstring nay nói thẳng con số.

Hai chỗ tài liệu lệch code: `architecture.md` còn bảng task ghi `draft_assessment` và câu "ba việc
thật sự cần model" (worker có 5 function); `local-development.md` còn dòng log mẫu
*"Starting worker for 4 functions: draft_assessment, ..."* — mà đó là **bằng chứng AGENT sống** mà
tài liệu dạy người ta đối chiếu, nên ai làm theo nó sẽ kết luận worker sai.

### Pha 3 — xong phần code, chờ review

170 pytest, 11 vitest, **6** repo check xanh.

Hai tool ghi đầu tiên, và cổng của bạn thành cấu trúc: `create_draft` **từ chối** một brief thiếu
trường và nói ra tên những trường còn thiếu. Một model được nhắc trong prompt rằng phải hỏi trước thì
quên được; một tool không chạy nổi khi thiếu trường thì không. Và việc nêu tên trường là thứ cho trợ
lý hỏi **một** câu có ích thay vì vài câu mơ hồ — đúng khuôn ADR-23 đã dùng cho tên lớp mơ hồ.

`start_drafting` từ chối khi đề **đang soạn dở**: hai đợt sinh chồng nhau là đúng thất bại mà brief
lưu sẵn dựng lên để ngăn, và từ chối rẻ hơn hoà giải.

**Check thứ sáu của repo, và nó bắt được thật.** Luật *"agent viết nội dung, giáo viên quyết trạng
thái"* nay là `tools-decide-nothing`: `teacher_tools.py` mà **nhắc tên** `advance` hay `withdraw` là
build đỏ. Tôi kiểm nó theo đúng kỷ luật `AGENTS.md` đòi — thêm một hàm gọi `advance` vào file đó, chạy
check, thấy nó đỏ đúng dòng, rồi phục hồi. Một check không thể đỏ thì không phải check.

Và **dây bẫy tôi dựng ở plan trước đã nổ** đúng như thiết kế: `test_the_catalog_only_offers_read_tools`
chuyển đỏ khi tôi thêm tool. Nay tôi là người phải giải thích, và lời giải thích đứng được — ADR-05
nói về việc **không thu hồi được**, không phải về mọi việc ghi, và cả hai tool mới đều đảo ngược được
khi đề chưa duyệt. Test viết lại thành luật còn đúng mãi: **không tool nào duyệt hay phát hành được.**

`_ENTITY_KEYS` nhận lại `assessment_id`. Review Việc 4 của plan trước bắt tôi bỏ nó ra vì không tool
nào trả về nó — nhánh không input nào chạm tới. `create_draft` trả về nó rồi, nên đây là lượt đầu tiên
có **chủ thể là một đề** chứ không phải một lớp, tức dữ liệu đầu tiên cho bảy variant
`Action result card`.

**Chưa gọi model thật.** Docker Desktop tắt giữa pha (máy sang ngày mới), nên Postgres và Redis không
có. Ô đó để trống chứ không tick — và tôi cũng ghi lại một lỗi thao tác của mình: tôi dìm lỗi `psql`
vào `/dev/null` nên việc tạo database thất bại **im lặng**, và triệu chứng hiện ra ở chỗ khác
(`ConnectionRefusedError` của BE). Không dìm output của bước dựng môi trường.

**Review Pha 3 đã chạy, và nó bắt một thứ nghiêm trọng hơn cả bốn thứ còn lại cộng lại:** check
`tools-decide-nothing` của tôi chỉ cấm **tên hàm**, nên `assessment.state = AssessmentState.APPROVED`
trong một tool vẫn qua được — đạt đúng kết quả ADR-01 cấm, và né luôn bảng `_ALLOWED`. Đó lại là dòng
mà một bản sửa "cho nhanh" dễ viết hơn hẳn so với việc đi tìm `advance`. Pattern nay bắt cả phép gán,
tha `==` (đọc trạng thái là cách một tool quyết định từ chối), và tôi kiểm nó đỏ được bằng một hàm
`_sneaky` gán `.state` rồi phục hồi.

Review cũng bắt rằng `FakeQueue` của `test_write_tools.py` không có `results`, nên **không test nào
trong file đó chạy nổi `harvest`** — và đúng là có một lỗ hổng cần nó: không test nào ở mức tool chứng
minh một câu job sinh ra **vào được** đề. Nay có, và tôi kiểm nó đỏ được bằng cách thay lời gọi
`harvest` thành `landed = 0`. Cộng một decision record còn thiếu cho lần nâng cap 172 → 173, và một
mục backlog cho đề nháp trống bị bỏ lại.

Pha 3.5 chen vào trước Pha 4: một đợt **sửa chữ, không sửa hành vi** — comment trong code chuyển sang
tiếng Việt, vì người đọc code này và người đọc đề nó sinh ra là cùng một người.

Năm pha rưỡi, dừng sau mỗi pha để bạn review; commit pha trước chỉ khi bắt đầu pha sau.
