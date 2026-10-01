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

- [ ] `teacher_tools.py`: `create_draft(subject, grade, topic_scope, question_count)`. **Thiếu trường
      nào thì từ chối** kèm tên trường còn thiếu — đúng khuôn lời-từ-chối-có-ích của ADR-23. Nghĩa là
      model *không thể* bắt đầu soạn khi chưa đủ ngữ cảnh, và lời từ chối dạy nó phải hỏi gì. Luật
      của bạn thành **cấu trúc**, không phải một câu trong prompt.
- [ ] `teacher_tools.py`: `draft_questions(assessment_id)` — bắn N job. Từ chối nếu brief chưa đủ,
      nếu đề đã duyệt, hoặc nếu **còn `DraftItem` đang pending**: không bao giờ có hai đợt sinh chồng
      nhau cho một đề.
- [ ] Một khi đã bắn, brief **đóng băng**. Giáo viên nói "cho khó hơn" là một brief **mới**, tức một
      đợt sinh mới — không phải một thay đổi giữa dòng. Ghi rõ trong docstring vì đây là chỗ dễ bị
      "sửa cho tiện" nhất.
- [ ] `tools/check_contract.py`: check mới — `advance(` và `withdraw(` không được xuất hiện trong
      `teacher_tools.py`. Cộng một dòng trong bảng Invariants của `AGENTS.md`.
- [ ] `graphs/propose.py`: prompt biết ba hình dạng từ chối mới, và biết rằng nó **không** được tự
      quyết duyệt hay phát hành.
- [ ] Test: brief thiếu → từ chối kèm tên trường; bắn hai lần không nhân đôi job; tool không có đường
      nào chạm `advance`.
- [ ] Một lượt model thật.

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

Năm pha, dừng sau mỗi pha để bạn review; commit pha trước chỉ khi bắt đầu pha sau.
