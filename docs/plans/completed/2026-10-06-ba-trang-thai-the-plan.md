# Ba trạng thái thẻ, một khung giờ, và danh mục tool đọc được

## Context

Một lượt thử tay ngày 06/10/2026 trên dữ liệu sạch cho thấy năm chỗ lệch giữa thứ sản phẩm
**định** làm và thứ code **đang** làm. Chúng không rời rạc: bốn trong năm cái cùng một gốc —
giao diện đang được dựng **theo tên tool** thay vì theo **trạng thái của đề**.

Đo được, không suy đoán:

- **Thẻ kết quả có bảy đầu đề**, không ba: `Không tạo được đề`, `Đã tạo đề "X"`, `Đã tạo đề`,
  `Đã soạn k/n câu`, `Dừng ở k/n câu`, `Đã thêm N câu vào đề`, `Đã duyệt đề`, `Đã bỏ duyệt đề`,
  `Đã phát hành cho 12A và 12B`. Mỗi `if (turn.tool_name === …)` trong `ActionCard.tsx` là một
  trạng thái mới, nên thêm một tool là thêm một trạng thái.
- **Đề đã phát hành không hoàn tác được, và màn hình im lặng.** Nút `Hoàn tác` vẫn vẽ ở màn 7;
  BE trả `409 "Đề đang ở trạng thái đã phát hành nên không bỏ duyệt được."`; `Panel` lưu câu ấy
  vào `trouble` nhưng nhánh `publishing` **không vẽ `trouble`** — nên 0 thông báo trên màn.
- **`Phát hành thêm lớp`** tồn tại để lách một ràng buộc: đường duy nhất về `approved` là thu hồi
  **mọi** lớp, mà `may_withdraw` chặn sau giờ mở của lớp đầu.
- **`create_draft` bắt khai `question_count` và tự kiểm 1..50** — hai việc nó không nên làm.
  `fire()` rồi lặp `range(1, brief.question_count + 1)`, nên số câu bị đóng đinh từ lúc tạo đề.
- **A3 mất một câu, và không ai truy được vì sao.** Trace đầy đủ ở Pha 3.

**Kết quả mong muốn:** thẻ là một máy trạng thái ba nấc của **đề**; phát hành là **một** việc với
**một** khung giờ, lùi được khi chưa ai mở; số câu khai lúc soạn chứ không lúc tạo; và một câu
hỏi hỏng để lại dấu vết đọc được.

## Global Constraints

- Tiếng Việt cho chuỗi ra màn hình, comment và docs; identifier và log tiếng Anh.
- **Figma đổi trước** mọi thay đổi FE, và chứng minh bằng **đo**, không bằng mắt.
- Mỗi luật mới phải **đỏ đúng test của nó** khi đột biến một dòng.
- `.\dev.ps1 check`, `test`, `typecheck` xanh trước khi tuyên bố xong.
- Ngân sách model: tối đa **hai** lượt `gpt-4o-mini`, ở mục kiểm chứng Pha 3 và Pha 5.
- Gọi một subagent review sau mỗi pha.

## Files

| File | Việc |
|---|---|
| `services/be/src/be/teacher_tools.py` | danh mục tool: thêm `list_class`, `get_class`, `list_assessment`; bỏ `find_class`, `draft_progress`; `create_draft` thôi nhận số câu |
| `services/be/src/be/drafting.py` | `fire()` nhận số câu; `harvest()` tự bắn lại `retry` |
| `services/be/src/be/main.py` | cấu hình logging — hiện **không có** |
| `services/be/src/be/teacher_routes.py` | một khung giờ cho mọi lớp; `unapprove` nhận đề `published` |
| `services/be/src/be/assessment_state.py` | cạnh `PUBLISHED → APPROVED` |
| `services/fe/src/screens/teacher/ActionCard.tsx` | ba trạng thái, dựng theo **state** không theo `tool_name` |
| `services/fe/src/screens/teacher/Panel.tsx` | bỏ `Phát hành thêm lớp`; vẽ `trouble` ở cả nhánh `publishing` |
| `services/fe/src/screens/teacher/PublishSettings.tsx` | `Hoàn tác` khoá kèm lý do khi hết cửa lùi |
| `tools/check_contract.py` | check thứ 12: thẻ chỉ có ba nấc |
| Figma `mOe2ZmrqOq1Uix45v6PNGD` | `Action result card` rút về ba variant; `Publish settings` bỏ nhánh thêm lớp |

## Ordered Tasks

### Pha 1 — Danh mục tool

- [x] **`list_class`** — không tham số. Dùng lại `resolve.classes_with_counts()` đã có; nó đếm học
      sinh trong một query và lọc theo `teacher_id` (ADR-22). Trả `{classes: [{class_id, name,
      student_count}]}`.
- [x] **`get_class`** thay `find_class` — nhận `class_id`, trả đúng một lớp. Việc *tìm theo tên* và
      việc *hỏi lại khi trùng tên* chuyển lên `list_class`: model liệt kê rồi tự chọn, thay vì tool
      vừa tìm vừa hỏi lại. Bốn hình dạng trả về của `find_class` rút còn một.
- [x] **`list_assessment`** — nhận `class_id`. Dùng lại `_assessments_of()` **đã tồn tại** ở
      `teacher_tools.py:198`, vốn đã join `publications` và lọc hai đầu theo `teacher_id`.
      Lưu ý: đề thuộc **giáo viên**, không thuộc lớp; "đề của một lớp" nghĩa là đề đã phát hành
      cho lớp ấy.
- [x] **Bỏ `draft_progress`.** SSE đã kể tiến độ. Nhánh `assessments_in_this_class` của
      `class_assessment_summary` cũng bỏ, vì `list_assessment` nay làm việc đó — năm hình dạng
      trả về của nó rút còn ba.
- [x] Cập nhật `catalog_for()` và prompt pha 1 của `propose.py` theo danh mục mới.

**Nơi thi hành:** test ở `services/be/tests/test_write_tools.py` — mỗi tool một test cho hình dạng
trả về, và một test khẳng định danh mục pha 1 **không** chứa tool ghi (ADR-25).

### Pha 2 — Số câu khai lúc soạn, không lúc tạo

- [x] `create_draft` bỏ `question_count` khỏi `arguments` **và** khỏi thân hàm; bỏ luôn phép kiểm
      `1 <= count <= 50`. Nó còn ba mục: `subject`, `grade`, `topic_scope`.
- [x] `start_drafting(assessment_id, question_count)` — nhận số câu và **giữ mức trần ở đây**.
      Gọi lại với số khác là soạn thêm.
- [x] `DraftBrief.question_count` thôi là thứ khai trước: `fire()` nhận số câu làm tham số thay vì
      đọc từ brief. Cột vẫn còn để `harvest` biết vòng này xin bao nhiêu.
- [x] `agent/handlers.py` đang tự bóc số câu từ chữ (`how_many.group(1)`) — rà lại cho khớp.

**Nơi thi hành:** check thứ 12 mở rộng — `create_draft` spec **không** được chứa chuỗi
`question_count`. Cộng một test BE: gọi `create_draft` với 500 câu thì **không** còn bị từ chối ở
đó, và `start_drafting` với 500 thì bị.

### Pha 3 — A3: câu hỏi mất tích, và dấu vết của nó

**Trace đã xong, đây là năm mắt xích đo được:**

1. `fire()` tính `banned` **một lần**, trước khi đẩy job — đề mới nên danh sách rỗng.
2. Ba job chạy song song với **cùng một `banned` rỗng**; không job nào thấy hai job kia.
3. Model viết ba câu độc lập; hai câu mở đầu giống hệt nhau.
4. `harvest()` ghi câu của ô 1 rồi `seen.add(stem)`; ô 2 trùng → `retry` kèm lý do
   *"đề trùng một câu đã có"*.
5. `fire()` **chỉ** được gọi từ `start_drafting`, nên `retry` thực tế nghĩa là **bỏ dở**.

- [x] **`harvest()` tự bắn lại.** Sau khi đánh `retry`, bắn lại job ngay với `banned` **đã cập
      nhật** — lần hai tránh được câu vừa ghi. Giữ `_MOST_ATTEMPTS` làm trần.
- [x] **Cấu hình logging.** `be` không có `basicConfig`/`dictConfig` nào, nên mọi `logger.info` của
      `be.drafting` đi vào hư không — kể cả dòng nói **vì sao** một câu bị loại. Thêm cấu hình ở
      `main.py`, mức từ `Settings`.
- [x] **Ghi lý do vào database.** Thêm cột `last_fault` cho `DraftItem`: một status `retry` không
      nói được vì sao là một dấu vết không dùng được. Đây là thứ biến "không ai truy được" thành
      "đọc một dòng SQL".

**Nơi thi hành:** test BE dựng hai job trả **cùng một stem**, chạy `harvest`, và khẳng định (a)
item thứ hai được bắn lại, (b) `last_fault` nói đúng lý do. Cộng một test rằng `logger` của
`be.drafting` có handler.

### Pha 4 — Thẻ: đúng ba nấc

Figma trước: `Action result card` rút về **ba** variant dùng được — `Loại=đã-tạo-đề`,
`Loại=đã-duyệt`, `Loại=đã-phát-hành` — cộng `Loại=tạo-thất-bại` cho ca tool bị từ chối. Các variant
còn lại đánh dấu *(không dùng)* chứ không xoá.

- [x] **`ActionCard` thôi dựng theo `tool_name`.** Nhận một **trạng thái** (`đã tạo đề` / `đã duyệt
      đề` / `đã phát hành`) cộng tên đề, và vẽ đúng ba nấc. `cardTurns` chịu trách nhiệm dịch lượt
      → trạng thái; `ActionCard` thôi biết tool là gì.
- [x] Bỏ tên lớp khỏi đầu đề: `Đã phát hành` chứ không `Đã phát hành cho 12A và 12B`. Danh sách lớp
      thuộc về hộp xác nhận và bảng kết quả, không thuộc một dòng tiêu đề.
- [x] Bỏ nhánh `Đã bỏ duyệt đề` và `Đã thêm N câu vào đề` — nay không ai tới được.

**Nơi thi hành:** check thứ 12 trong `tools/check_contract.py` đếm union `CardState`, bảng `HEAD`
và bảng `SAFETY`, đỏ khi một trong ba khác bốn hoặc khi ba cái không cùng một bộ tên. Cộng hai
chốt trên vùng vẽ: nhiều nhất **một** phép so `tool_name`, và **không** `switch`/`includes`/tra
bảng tại chỗ nào. Cộng một test FE đi qua **mọi** `tool_name` và khẳng định **đẳng thức** đầu đề
cho từng tool.

*Đã làm khác plan ở hai chỗ, và đây là lý do.* (1) Plan nói *"đọc cây cú pháp"*; gate Python không
có parser TypeScript, và kéo một cái vào là đổi hình dạng `dev.ps1` cho đúng một check — nên nó
là một phép quét **có khoanh vùng**. Cái giá đã đo: một đợt review chạy bốn đột biến và ba cái đi
lọt (nấc thứ năm viết chung dòng, `switch` thay cho phép so, và cả vùng phía trên
`export default` không ai nhìn). Cả ba nay đỏ. (2) Plan nói *"vượt bốn"*; cài thành `!= 4`, nên
nó đỏ cả khi **thiếu** một nấc.

### Pha 5 — Phát hành: một khung giờ, một đường lùi

- [x] **Một khung giờ cho mọi lớp.** `ClassSchedule` tách làm hai: một `Schedule` (năm tham số thời
      gian) cộng `class_ids: tuple[str, ...]`. FE **đã** gửi cùng một bộ cho mọi lớp
      (`PublishSettings.schedules()`), nên đây là siết hợp đồng cho khớp thực tế, không đổi hành vi.
- [x] Câu an toàn thôi nói *"của từng lớp"*: một khung giờ thì một mốc thu hồi.
- [x] **Bỏ `Phát hành thêm lớp`.** Muốn đổi lớp thì hoàn tác trước — đúng như người dùng chốt.
- [x] **`Hoàn tác` làm thật trên đề đã phát hành.** Mở cạnh `PUBLISHED → APPROVED` trong
      `assessment_state.py`, và `unapprove` thu hồi **mọi** lớp rồi hạ state. Chặn khi một lớp đã
      qua giờ mở (`may_withdraw`).
- [x] **Khi hết cửa lùi:** nút hiện nhưng **khoá**, kèm câu của BE — cùng khuôn với cách biểu mẫu
      chặn cửa sổ thời gian vô lý trước cú bấm.
- [x] **Vá chỗ nuốt lỗi:** `Panel` phải vẽ `trouble` ở **cả** nhánh `publishing`. Hiện `trouble`
      chỉ sống trong `panel-foot`, nên mọi lỗi phát ra ở màn 7 đều im lặng.

**Nơi thi hành:** test FE rằng một lỗi của `undo()` hiện ra khi `publishing` bật — đột biến xoá
chỗ vẽ ấy phải đỏ. Cộng test BE cho `PUBLISHED → APPROVED`: thu hồi hết thì xuống `approved`; một
lớp đã mở thì 409 kèm câu tiếng Việt.

## Verification

- **Cổng:** `.\dev.ps1 check` (11 → 12 check) · `test` · `typecheck`.
- **Đột biến:** mỗi luật mới sửa một dòng cho sai, chạy lại, phải đỏ **đúng** test của nó.
- **Trình duyệt** (đo DOM, không chụp ảnh):
  - Pha 3 cần **một** lượt `gpt-4o-mini` soạn 3 câu: `draft_items` không còn dòng `retry` nào treo,
    và nếu có thì `last_fault` đọc được bằng SQL.
  - Pha 4: đi hết vòng `đã tạo đề → đã duyệt đề → đã phát hành → hoàn tác`, đếm thẻ luôn bằng **1**
    và đầu đề luôn thuộc ba nấc.
  - Pha 5 cần **một** lượt nữa để có đề mới: phát hành cho hai lớp, bấm `Hoàn tác`, `psql` xác nhận
    `state='approved'` và `publications` rỗng; rồi đặt một `opens_at` quá khứ và xác nhận nút khoá
    kèm câu của BE.
- **Figma ↔ FE** so bằng số: `get_metadata` và `getBoundingClientRect()`.
- **Kịch bản thử tay** (`docs/kich-ban-thu-tay-giao-vien.md`) cập nhật cùng change set: mục E5 thôi
  là *"chưa làm được"*, và chặng D/E đổi theo ba nấc thẻ.

## Decision Records

### Decision: `list_class` + `get_class` thay cho `find_class`

options considered: (a) giữ `find_class` và thêm `list_class`; (b) tách đôi thành `list_class` để
liệt kê và `get_class` để lấy một lớp.

selected option: (b).

reason: `find_class` có **bốn** hình dạng trả về vì nó làm hai việc — tìm theo tên, và hỏi lại khi
trùng tên. Model phải đoán lần này nhận hình nào. Tách ra thì mỗi tool một hình dạng, và việc chọn
giữa hai lớp trùng tên về đúng chỗ của nó: model đọc danh sách rồi hỏi giáo viên, thay vì tool tự
dựng một câu hỏi lại.

### Decision: harvest tự bắn lại thay vì soạn tuần tự

options considered: (a) soạn tuần tự để `banned` luôn đầy đủ; (b) giữ song song, harvest tự bắn lại
khi trùng; (c) cả hai.

selected option: (b).

reason: tuần tự làm một đề 10 câu chậm gấp mười, mà nguyên nhân trùng câu chỉ xảy ra ở **lần đầu**
của một đề rỗng — từ lần hai trở đi `banned` đã có nội dung. Bắn lại cũng chữa được ba ca hỏng khác
(`kết quả hết hạn`, `sai hình dạng ADR-18`, `vị trí đã có câu`) mà tuần tự không chạm tới.

### Decision: số câu đi cùng `start_drafting`

options considered: (a) giữ `question_count` trong brief, chỉ bỏ phép kiểm ở `create_draft`;
(b) bỏ hẳn khỏi `create_draft`, `start_drafting` nhận số câu và giữ mức trần.

selected option: (b).

reason: một đề trống không có số câu nào để khai — số ấy chỉ có nghĩa khi bắt đầu soạn. Giữ nó ở
brief buộc giáo viên quyết một con số trước khi biết đề sẽ dài bao nhiêu, và làm `create_draft` từ
chối một việc nó không làm.

## Status

- **Pha 1 — Danh mục tool:** xong. `list_class`, `get_class`, `list_assessment` thay `find_class`;
  `draft_progress` bỏ hẳn; nhánh `assessments_in_this_class` của `class_assessment_summary` bỏ theo.
- **Pha 2 — Số câu khai lúc soạn:** xong. `create_draft` còn ba mục và không còn mức trần nào;
  `start_drafting` nhận `question_count` và giữ trần 1..50.
- **Pha 3 — A3 và dấu vết của nó:** xong. `harvest()` tự bắn lại với `banned` đã cập nhật, cột
  `draft_items.last_fault`, và BE lần đầu có cấu hình logging (cây `be`, mức từ `Settings.log_level`).

**Một đợt review sau pha 1-3 tìm ra tám món, và tám món đã sửa.** Ghi ra vì ba trong số đó là lỗi
của chính plan này, không phải món nợ cũ:

- **Prompt pha 1 của `propose.py` chưa được cập nhật** — task cuối của Pha 1 bị bỏ sót. Nó dặn model
  theo cờ `ambiguous`, cờ chết cùng `find_class`; mock thì **đã** sửa, nên test và demo vẫn xanh
  trong khi đường model thật mất nơi thi hành duy nhất của ADR-23. Nay prompt dặn theo
  `len(candidates) > 1`, và `test_the_prompt_is_where_adr_23_reaches_the_real_model` đọc thẳng prompt.
- **Lớp thứ bảy trở đi không với tới được.** `list_class` trả mọi lớp rồi cắt sáu, mà không có tham
  số nào để thu hẹp và `get_class` cần một id model chưa thấy. `more` nói đúng con số nhưng là một
  lời thừa nhận, không phải một đường ra. Thêm `name` **tuỳ chọn**: lọc rồi vẫn một hình dạng, và
  việc chọn giữa hai lớp trùng tên vẫn thuộc về model. Đây là một sửa chữa cho Decision Record thứ
  nhất bên dưới — nó so hai phương án mà không thấy rằng (b) bỏ mất phép tra theo tên.
- **`commit()` của nhánh bắn-lại nằm ngoài lưới `IntegrityError`** — nên khi có ô `retry`, mọi thứ
  `harvest` vừa ghi được commit ngoài khối `try`, và một tab thứ hai nhanh tay hơn làm cả lượt chat
  500. Đợt này còn làm nhánh `retry` thành đường hay đi nhất, nên lỗ ấy vừa mới vừa rộng.
- `_refire` tiêu một lượt `attempts` kể cả khi queue chết và không job nào đi được.
- Trần cho **tổng** chỉ `logger.warning` rồi `return 0`, mà caller dịch 0 thành *"hàng đợi đang
  hỏng"* — một lời từ chối nêu nguyên nhân không có thật. `too_many()` là chỗ nó có tiếng nói.
- Hai luật to nhất của Pha 2 (`fire` cộng dồn, trần trên tổng) **không test nào đo**; đột biến bỏ
  `start +` sống sót qua cả bộ test. Nay cả hai đỏ đúng test của mình.
- `lifespan` gọi cấu hình logging mà không ai đo lời gọi ấy — xoá dòng đó thì suite vẫn xanh và BE
  im lặng trở lại.
- Ba chỗ chữ nói ngược code: comment `cardTurns` viện `entity_id` mà hàm không đọc nó, bảng variant
  trong `teacher-surface.md`, và nơi thi hành của ADR-23 trỏ vào `resolve_class()` — hàm nay không
  còn caller nào trong `src/`, đã ghi rõ thay vì để nó đọc như đang có hiệu lực.
- **Pha 4 — Thẻ ba nấc:** xong. `ActionCard` nhận một **nấc** (`drafted` → `approved` →
  `published`, cộng `failed`); Figma rút về năm variant dùng được trên bốn đầu đề, năm variant
  còn lại đánh dấu *(không dùng)*; check thứ 12 đếm ba bảng phải khớp nhau.

  **Một đợt review sau pha 4 tìm ra sáu món, và sáu món đã sửa.** Ba trong số đó là lỗi thật:

  - **Thẻ duyệt im lặng về tên đề.** `_note` chưa bao giờ ghi `title`, nên `Đã duyệt đề "{tên}"`
    là một chuỗi production **không dựng nổi** — mà cả Figma lẫn bảng trong `teacher-surface.md`
    đều vẽ nó. BE nay chở `title` ở cả `_note` lẫn `start_drafting`, nên tài liệu thành đúng
    thay vì bị hạ xuống cho khớp code.
  - **`Hoàn tác` làm MẤT thẻ.** `blocks()` chỉ cắt khối ở lượt `teacher` gõ tay, nên một giáo
    viên gõ *"cảm ơn"* rồi mở một đề cũ, bấm Duyệt, bấm Hoàn tác có cả hai cú bấm rơi vào một
    khối không có việc nào của model — nhánh cũ trả thẻ của model, model không có thẻ, màn hình
    còn **0 thẻ** và mất luôn cửa vào panel. Nay chính lượt `teacher.unapprove` vẽ thẻ, và nhánh
    riêng ấy biến mất.
  - **Tool lạ mặc định thành một nấc thật.** `?? "drafted"` khiến một tool chưa ai biết làm gì
    cho ra một thẻ khẳng định *một cái đề đã tồn tại*. Bản cũ `return null` — mặc định an toàn —
    và nay nó quay lại: `cardState` trả `null`, và `modelCardTurn` hỏi `STATE_OF` thay vì giữ một
    danh sách tool đọc viết cứng.
  - Check thứ 12 hở ba khe (xem *Nơi thi hành* ở Pha 4); test sweep dùng `toContain` nên một tool
    gán sai nấc vẫn xanh, nay là đẳng thức; nút `Thêm câu hỏi` không có test nào, nay có.
  - Chín chỗ `teacher-surface.md` nói ngược code, cộng hai docstring đếm sai số variant.
- **Pha 5 — Phát hành một khung giờ:** xong. `PublishRequest` là một `Schedule` cộng `class_ids`;
  `unapprove` nhận đề `đã phát hành` và thu hồi mọi lớp trước (hoặc tất cả hoặc không gì cả);
  `Phát hành thêm lớp` đã bỏ; `Hoàn tác` khoá kèm câu của BE qua `publish-form.undo_blocked`; và
  `Panel` thôi nuốt lỗi ở nhánh `publishing`.

  Hai chỗ đáng ghi lại:

  - **ADR-02 được sửa đổi, không bị phá.** Khoá kép của `Publication` giữ nguyên, nên thu hồi vẫn
    từng lớp một. Thứ bỏ đi là *mỗi lớp một đồng hồ trong MỘT lần phát hành* — một khả năng chưa
    bao giờ được dựng, vì biểu mẫu chỉ có một bộ ô nhập. Muốn hai lớp hai đồng hồ thì phát hành hai
    lần. Hai test ghim luật cũ đã viết lại chứ không xoá: một đo *một* đồng hồ cho hai lớp, một đo
    thất bại-một-phần qua một **cớ** khác (lớp của giáo viên khác).
  - **Câu chặn `Hoàn tác` dùng chung một hàm với lời từ chối.** `_why_undo_is_shut` phục vụ cả
    biểu mẫu lẫn endpoint, nên câu hiện trước cú bấm và câu 409 sau cú bấm không thể lệch nhau —
    và test khẳng định chúng **bằng nhau từng chữ**. Hai bản cài đặt của một luật là hai luật.

- **Thử tay trên trình duyệt:** xong, một lượt `gpt-4o-mini` (ngân sách là hai). Biên bản đầy đủ
  ở `docs/kich-ban-thu-tay-giao-vien.md`, mục *Lần chạy 2026-10-06, lượt hai*. Ba nấc thẻ, một
  khung giờ và hai ca hết cửa lùi đều đúng như đã thiết kế — nhưng lượt chạy tìm ra **hai** thứ
  mà không test nào bắt được:

  - **Hộp xác nhận kể hai câu chuyện cùng lúc.** Câu mở đầu hứa thu hồi *"cho tới giờ mở của
    **từng lớp**"* trong khi dòng luật của BE ngay dưới nó nói *"cho tới hết giờ mở"*, và dòng
    `Thu hồi` in đúng **một** giờ. Pha 5 đổi hợp đồng và đổi câu an toàn trên thẻ, nhưng sót
    chuỗi này — nó là chuỗi FE **tự viết** thay vì mượn của BE, nên nó trôi được. Đã sửa, và
    test nay khẳng định hộp không chứa chuỗi `từng lớp`.
  - **Một test đã âm thầm thôi đo.** `expect(JSON.stringify(shown.schedules)).toBe(...done.schedules)`
    đọc một khoá đã đổi tên thành `schedule` ở chính Pha 5. `JSON.stringify(undefined)` là
    `undefined` ở **cả hai** vế, nên phép so vẫn xanh trong khi nó không còn so gì nữa. Tệ hơn,
    `FORM` chỉ có **một** lớp, nên đột biến `picked` → `picked.slice(0, 1)` cũng sống sót. Nay
    fixture có hai lớp, test chọn cả hai, và cả hai đột biến đều đỏ.

  **Một thứ của model, chưa sửa:** giáo viên viết *"Tạo cho tôi một đề toán lớp 12 gồm 3 câu về
  hàm số bậc hai"* — đủ cả môn, khối và phạm vi — mà Kriky vẫn hỏi lại. Đây là prompt pha 1, và
  sửa nó cần một vòng đo bằng model thật; đã ghi vào kịch bản chứ chưa động tới.

- **Dọn code chết:** `resolve_class` cùng `Resolved` / `Ambiguous` / `NotFound` đã xoá — không
  caller nào ngoài test. Hai luật chỉ của riêng chúng (*khớp chính xác thắng khớp chuỗi con*,
  *cách viết đúng như đã lưu thắng bản chuẩn hoá*) chết theo, vì `list_class` không xếp hạng: nó
  lọc rồi trả cả danh sách, việc chọn thuộc về model (ADR-23). Mọi luật **còn sống** —
  `normalise`, ADR-22, `outerjoin` đếm lớp rỗng — chuyển sang đo qua `list_class`, bề mặt thật.

Cổng cuối: `.\dev.ps1 check` (12 check), `pytest` 396, `vitest` 135, `typecheck` — xanh.
Mười chín luật mới đo bằng đột biến một dòng, mỗi luật đỏ đúng test của nó.
