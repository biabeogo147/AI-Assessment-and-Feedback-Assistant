# Plan — đường ghi câu hỏi vào ngân hàng câu hỏi

## Goal

BE chưa có ngân hàng câu hỏi (ADR-04, gạch *"Chưa có ở backend"* trong mục *Nơi luật này đang được thi
hành*): `Question` thuộc đúng một đề và không cột nào nói nguồn. Panel đề in dòng tổng *"N câu ngân hàng · x câu thêm mới đã kiểm · y câu chưa kiểm"* --
chữ bịa, chọn theo hash id (`services/fe/src/screens/teacher/invented-not-from-be.ts`).

Sau plan này: **duyệt đề là giáo viên đã kiểm hết**, và chính lần duyệt chép mọi câu của đề vào ngân
hàng riêng của giáo viên (ADR-28). Dòng tổng dưới tên đề không còn. Giáo viên xoá được một câu khỏi đề
chưa duyệt (còn sửa được), qua một hộp thoại xác nhận; khi câu đã có bản trong ngân hàng, hộp thoại nói
rõ bản ấy vẫn giữ. Luật nghiệp vụ nằm ở ADR-28; plan này chỉ giữ các quyết định kỹ thuật.

## Scope

Trong: bảng `bank_questions`; ghi lúc duyệt, ghi đè lúc duyệt lại; đề seed cũng có bản trong ngân
hàng; route xoá câu, dồn số; `QuestionRead.in_bank`; gỡ dòng tổng; nút Xoá và hộp thoại (Figma trước,
code sau).

Ngoài: tool để agent rút câu từ ngân hàng (đường đọc); màn xem ngân hàng; độ khó; mục kiến thức và tài
liệu của câu trong ngân hàng; chip nguồn thật trên từng câu -- người dùng dặn giữ nguyên giao diện,
nên chip vẫn bịa, nợ ghi ở ADR-04 và `backlog.md`.

## Decision Records

### Decision: ngân hàng là bảng chép, không phải phép truy vấn

**options considered:** (a) **bảng `bank_questions` riêng, chép nội dung lúc duyệt** · (b) ngân hàng
là phép truy vấn *"mọi câu trong đề đã duyệt của tôi"*, không bảng mới · (c) giáo viên tự chọn câu nào
lưu, trong hộp duyệt.

**selected option:** (a).

**reason:** ADR-28 (mục *Vì sao*, đoạn *Bản chép*) giữ lý do nghiệp vụ loại (b). Phía kỹ thuật: bảng
chép cho mỗi câu một id bền, thứ mà mọi thống kê sau này cần; `options`/`methods` là JSON như
`RoundItem`, vì không `Answer` nào trỏ vào phương án của một dòng ngân hàng. (c) thêm một thao tác vào
đúng chỗ ADR-28 vừa bỏ thao tác.

### Decision: `question_id` là khoá ghi đè, và được thả khi câu bị xoá

**options considered:** (a) **một cột `question_id` unique, nullable: duyệt lại ghi đè dòng của cùng
câu; xoá câu khỏi đề đặt cột về `NULL`** · (b) khoá theo nội dung (stem đã chuẩn hoá) · (c) mỗi lần
duyệt một dòng mới.

**selected option:** (a).

**reason:** ADR-28 đòi duyệt lại thì ghi đè bản của cùng câu, và xoá trong đề không xoá ngân hàng. Khoá
theo nội dung (b) vỡ đúng ở ca cần nó: sửa câu là đổi stem, nên lần duyệt lại tạo dòng mới thay vì ghi đè.
(c) để lại các bản gần trùng. `NULL` chứ không xoá dòng: dòng ngân hàng sống tiếp, chỉ mất câu nguồn;
và FK vẫn giữ được mà không chặn lần xoá câu.

### Decision: xoá câu dồn số cả `Question` lẫn `DraftItem`

**options considered:** (a) **dồn `order_index` và `DraftItem.ordinal` cùng nhau** · (b) chỉ dồn
`order_index` · (c) giữ số cũ, để lỗ.

**selected option:** (a).

**reason:** ADR-28 đòi số câu liền nhau sau khi xoá. Dồn một nửa (b) làm hai sổ lệch nhau: `fire` lấy
`max(DraftItem.ordinal)` làm điểm bắt đầu, `harvest` so `ordinal` với `order_index`, nên lần *"soạn
thêm"* kế tiếp để lại lỗ số. Đi kèm: từ chối xoá khi còn câu đang soạn (dồn số dưới chân một job đang
chạy là để nó ghi nhầm ô), từ chối xoá câu cuối (ADR-28: xoá không đổi trạng thái của đề; hậu ký ADR-01), và từ chối khi đề đã
có **lượt làm bài** -- **phòng thủ**: `answers`, `question_outcomes`, `round_items`, `pregenerated_items`
đều trỏ khoá ngoại về `questions.id` và đều treo dưới một `Attempt`, dù bỏ duyệt một đề đã qua giờ mở
đã bị chặn (ADR-02), nên ca này hôm nay không tới được. Chặn theo lượt **trả lời** (phép kiểm của
`edit_question`) thì không đủ: nộp pha 1 ghi `QuestionOutcome` cho cả câu bỏ trắng.

## Files

| File | Việc |
|---|---|
| `packages/schema/src/schema/models.py` | `BankQuestion` |
| `services/be/src/be/question_bank.py` (mới) | `file_approved`, `in_bank`, `release` |
| `services/be/src/be/teacher_routes.py` | `approve` ghi ngân hàng; `QuestionRead.in_bank`; route xoá câu |
| `services/be/src/be/seed.py` | đề seed đã phát hành có bản trong ngân hàng |
| `services/fe/src/api.ts`, `screens/teacher/Panel.tsx`, `teacher.css` | gỡ dòng tổng; nút Xoá, hộp thoại |
| Figma `mOe2ZmrqOq1Uix45v6PNGD` | gỡ dòng tổng; nút Xoá; artboard hộp thoại xoá câu |
| `docs/decisions/adr-28-ngan-hang-cau-hoi-ghi-khi-duyet.md` (mới) | luật mới |
| `docs/decisions/adr-04-hai-nguon-cau-hoi.md`, `docs/decisions/adr-01-vong-doi-de-kiem-tra.md` | hậu ký 13/10/2026 |
| `docs/decisions/README.md` | mục lục ADR |
| `docs/overview/project-overview.md` | glossary `Question Bank` |
| `docs/overview/use-case-specification.md` (UC-02), `docs/overview/business-workflows.md` | xoá câu; duyệt chép vào ngân hàng |
| `docs/overview/data-model.md`, `docs/overview/teacher-surface.md` | bảng mới; panel và hộp xoá câu |
| `docs/plans/backlog.md` | nợ chip bịa, dấu kiểm lời giải, câu luyện tập; việc hoãn |
| test của từng task | |

## Ordered Tasks

Mỗi task: xong → subagent review → sửa → task kế.

- [x] T1. Plan này; ADR-28; hậu ký ADR-04 và ADR-01; glossary; mục lục ADR; ba chỗ backlog nói về
      trạng thái kiểm; UC-02 và luồng nghiệp vụ.
      Review T1: ADR-01 còn hứa mở cạnh `có câu hỏi → trống` khi có đường xoá (nay hậu ký nói ngược
      lại, kèm lý do: bỏ duyệt là thao tác hạ trạng thái duy nhất); ba dòng backlog cũ về trạng thái
      kiểm; *dồn số* và nghĩa của *đã kiểm* sau khi bỏ duyệt chuyển vào ADR-28 có lý do thật; ADR-28
      nói rõ *đã kiểm* gồm cả lời giải (ADR-18) và *"có bản trong ngân hàng"* không phải nguồn
      *"Lấy từ ngân hàng câu hỏi"*; thêm hệ quả *ghi đè va với việc sửa trong ngân hàng*. Thuật ngữ
      thống nhất *ngân hàng câu hỏi* (glossary, chip) -- cả chữ trong hộp thoại xoá.
- [x] T2. Schema và đường ghi: `BankQuestion`, `question_bank.py`, nối vào `approve`, seed. Test:
      duyệt thì mỗi câu một dòng, đúng giáo viên; bỏ duyệt, sửa, duyệt lại thì cùng dòng bị ghi đè;
      hai giáo viên không lẫn; đề seed có dòng; duyệt bị từ chối không ghi gì.
      Review T2: không lỗi đúng-sai; test ghi đè chỉ sửa đề bài nên năm đột biến sống (không ghi đè
      phương án, lời giải, mục tiêu, `approved_at`; ghi đè `created_at`) -- nay sửa mọi phần và lùi
      mốc thời gian một giờ (đồng hồ Windows nhích 15,6 ms), cả năm đột biến đỏ; thêm kiểm nội dung
      ngân hàng của câu thu hoạch ngay trong request duyệt; `file_approved` đọc câu bằng
      `populate_existing`; `error_label` giữ `None` như `AnswerOption`; ba hàm lọc theo
      `teacher_id`; `question_id` thêm `ondelete="SET NULL"`, `teacher_id` có index (bảng còn mới
      nên miễn phí). Lỗi có từ trước của `_owned` (không đọc lại state) ghi ở `backlog.md`.
- [x] T3. Route xoá câu và `in_bank`. Test từng lời từ chối (404 người khác, 409 đề khoá, 409 còn
      câu đang soạn, 409 câu cuối, 409 đã có lượt làm bài); dồn số cả hai sổ rồi soạn thêm không lỗ;
      dòng ngân hàng còn với `question_id` `NULL`, duyệt lại không đụng nó; `in_bank` trước và sau
      duyệt. SQLite của file test bật khoá ngoại, để thứ tự xoá sai thì đỏ.
      Review T3: phép kiểm *"đã có lượt trả lời"* lọt bài nộp trắng (`QuestionOutcome` không kèm
      `Answer`) -- nay chặn theo `Attempt`, có test; route xoá thiếu bước kiểm lại sau khi lấy lại
      khoá -- nay `assert_editable` ở cả hai chỗ (đúng luật `services/be/AGENTS.md`); test hở: bỏ
      `harvest`, gom flush (đỏ 4/6 lần với đề bốn câu), route sửa trả `in_bank` sai -- nay đề mười
      câu, ca job xong chưa thu, ca ô `failed`/`retry`, `in_bank` từ PATCH, cả bốn đột biến đỏ;
      `in_bank` bỏ giá trị mặc định; docstring dồn số nêu đúng bẫy (flush xếp `UPDATE` theo khoá
      chính). Đua với `fire` ghi ở `backlog.md`.
- [x] T4. Figma: gỡ dòng tổng trên các artboard panel đề; nút `Xoá` trên thẻ câu; artboard hộp thoại
      xoá câu, hai nội dung theo `in_bank`. Review bằng ảnh chụp.
      **Đã làm:** gỡ `provenance` ở artboard 6, 7, 8, 12, 14 (hai bản ghi *"Đã duyệt 06/10/2026"* giữ
      làm lịch sử); `Question card` (`267:30`) thêm `Xoá` (`592:20`) cạnh `Sửa`, cùng thuộc tính
      `Sửa được`; set mới `Consequence dialog — xoá câu khỏi đề` (`592:3180`), ba variant
      `Trạng thái=đã lưu|chưa lưu|bị từ chối`; artboard `15 · Xoá một câu khỏi đề — đề từng duyệt
      rồi bỏ duyệt` (`594:2550`). Review T4: set mới đè ba component (dời sang chỗ trống); artboard 15
      trỏ hộp vào câu mang chip *"Lấy từ ngân hàng câu hỏi"* -- dễ đọc thành *"đã lưu vì lấy từ ngân
      hàng"* (nay câu 5, chip *"Thêm mới"*; tên artboard nói rõ đề từng duyệt rồi bỏ duyệt, vì code vẽ
      lượt bỏ duyệt bằng chính thẻ *"Đã tạo đề"* nên khung chat không phân biệt được); lớp phủ 35% lệch
      code (nay 45%, gắn `ink/default`); mô tả variant còn chép của hộp xoá đoạn chat; `&quot;` thừa;
      mô tả `Source citation` (`84:35`) thêm hậu ký ADR-28. Lệch có từ trước, chưa sửa: mọi hộp thoại
      Figma có bóng đổ mà `.confirm` không có; lớp phủ artboard 13 vẫn 35%.
- [x] T5. FE: gỡ `<Provenance>` (code chết comment lại); nút Xoá khi đề `editable`; hộp thoại theo
      khuôn *"Xoá đoạn chat này?"*; 409 hiện trong hộp. Vitest. Đo FE so với Figma.
      **Đo** (trình duyệt, 13/10/2026; số chi tiết ở `teacher-surface.md`): đầu panel 85,5 (Figma
      86), `Xoá` cùng kiểu `Sửa` cách 8, hộp 460 / padding 24 / gap 12 / bo 14, hai nút 72,6 và
      85,5 × 40 cách 16, hộp *"đã lưu"* cao 202 bằng Figma, lời từ chối `answer/incorrect` 11px,
      lớp phủ 45%. Lệch có từ trước: bóng đổ của hộp thoại.
      Review T5: xoá xong mà đọc lại hỏng thì lỗi mất trong hộp đã đóng (nay hai bước, lỗi đọc lại
      về chân panel); đang xoá vẫn đóng được hộp bằng `Esc`, bấm ra ngoài, `Giữ lại` (nay khoá cả
      ba); lời từ chối cũ đứng chờ lần bấm lại (nay xoá trước mỗi lần); đổi đề khi hộp đang mở thì
      hộp mọc lại với câu đề cũ (nay reset); bị từ chối thì đọc lại đề vì BE thu hoạch trước khi
      kiểm; `Sửa`/`Xoá` chung một khối điều kiện. Sáu đột biến sống trong bộ test đầu -- nay mười
      đột biến đều đỏ (đề hai câu, đọc lại ra đề đã dồn số, request treo bằng promise hoãn).
      Chưa sửa, có từ trước: `solving` cũng không reset khi đổi đề; hộp thoại không chuyển focus.
- [x] T6. Khởi động lại BE, thử đầu-cuối trên trình duyệt; `data-model.md`, `teacher-surface.md`,
      `backlog.md`; đóng plan. Nơi thi hành của ADR-28 và ADR-01 cập nhật; ADR-28 sang *đang thi
      hành*.
      Review T6: không lỗi chặn. Sửa: lỗi `_owned` trong backlog nay nêu cả route xoá (cùng khuôn, nên
      lần `assert_editable` thứ hai cũng kiểm trên state cũ); `data-model.md` đếm 22 bảng và nói đề
      seed vào ngân hàng; ADR-28 *"trước commit ghi `state`"* thay *"commit duy nhất"*; lời từ chối
      thêm ca *đề vừa bị duyệt ở nơi khác*; luồng nghiệp vụ nhắc xoá câu; docstring `release` nói đúng
      phạm vi của SQLite có khoá ngoại. Không làm, ghi lại: `docs/decisions/README.md` đếm artboard đã
      cũ từ trước (backlog); một hàng *Invariants* trong `AGENTS.md` cho ADR-28 cần plan và decision
      riêng, và `AGENTS.md` đang chạm trần 184 dòng. **Không cần `db-reset`**: `bank_questions` là bảng mới, và
      `prepare_schema` tạo bảng còn thiếu lúc BE khởi động (`check_schema` chỉ coi cột thiếu là lệch);
      plan không thêm cột nào vào bảng cũ. Đề đã duyệt trước plan này không có bản trong ngân hàng --
      không chép bù; đề còn bỏ duyệt được thì lần duyệt kế tiếp sẽ chép, còn đề đã phát hành quá giờ
      mở (kể cả đề seed trên database đang có) thì **không bao giờ** vào ngân hàng. Thử đầu-cuối dùng
      đề mới soạn. Cập nhật mục *Nơi luật này đang được thi hành* và trạng thái của ADR-28.

## Validation Checks

- Mỗi task: `.\dev.ps1 check`, `test`, `typecheck` xanh; đột biến một dòng ở luật mới làm test đỏ.
- Đầu-cuối (gpt-4o-mini cho phần soạn): soạn đề → duyệt → bỏ duyệt → sửa một câu → xoá một câu (hộp
  thoại nói *"đã lưu vào ngân hàng câu hỏi"*) → duyệt lại. Bảng `bank_questions`: đúng số dòng, bản đã sửa,
  dòng của câu đã xoá còn với `question_id` `NULL`. Số câu trên panel liền nhau.

## Status

Viết 13/10/2026, sau khi người dùng chốt hướng (a) của *Decision: ngân hàng là bảng chép* và năm điểm: duyệt = đã kiểm; vào ngân hàng lúc
duyệt; ngân hàng riêng từng giáo viên; duyệt lại ghi đè; xoá trong đề không xoá ngân hàng, có hộp
thoại báo, số dồn lên. Chỉ làm đường ghi.

**Xong 13/10/2026.** T1--T6, mỗi task qua review của subagent và đã sửa theo review. `check` 21/21,
`typecheck` xanh, vitest 204/204, pytest BE xanh trừ `test_a_turn_that_outlived_its_lock…` (chập
chờn có từ trước, đồng hồ 15,6 ms của Windows; nợ đã ghi). Commit: `0bcfc9c`..`2e2fe7a`, cộng commit đóng plan.

**Thử đầu-cuối** (gpt-4o-mini cho phần soạn; BE khởi động lại, `bank_questions` do `prepare_schema`
tạo, không `db-reset`): đoạn chat mới *"Tạo đề kiểm tra 15 phút Toán lớp 8, 4 câu trắc nghiệm về hằng
đẳng thức đáng nhớ, mức thông hiểu"* → đề `5653c5a5` 4 câu → **Duyệt**: ngân hàng 4 dòng → **Hoàn
tác** → sửa đề bài câu 1 → **Xoá** câu 2: hộp nói *"đã lưu vào ngân hàng câu hỏi từ lần duyệt
trước"* → xác nhận: panel còn câu 1--3, ô soạn 1--3 → **Duyệt lại**: ngân hàng vẫn 4 dòng, câu 1
ghi đè bằng bản đã sửa (`approved_at` mới), dòng của câu đã xoá ở lại với `question_id` `NULL` và
không bị lần duyệt lại đụng tới. Đo lời từ chối: bỏ duyệt, xoá tới câu cuối, thử xoá câu cuối → hộp
giữ nguyên với *"Đây là câu cuối cùng của đề nên không xoá được…"*. Đề thử ấy để lại, còn 1 câu,
chưa duyệt. Đề nháp có sẵn của người dùng chỉ được mở hộp rồi bấm *Giữ lại*, không xoá câu nào.

**Còn lại, ghi ở `backlog.md`:** lần `_owned` thứ hai không đọc lại state (có từ trước); xoá câu
đua với `fire`; chip nguồn trên từng câu vẫn bịa -- trên đề vừa soạn, chip in *"Lấy từ ngân hàng câu
hỏi"* và *"Thêm mới · đã kiểm"* cho một đề **chưa duyệt**, và có thể nằm trên đúng câu mà hộp xoá
nói *"chưa có trong ngân hàng câu hỏi"*; đường đọc ngân hàng; mục kiến thức và tài liệu chưa vào
ngân hàng; câu lấy từ ngân hàng sang đề mới không được sinh bản trùng khi duyệt.
