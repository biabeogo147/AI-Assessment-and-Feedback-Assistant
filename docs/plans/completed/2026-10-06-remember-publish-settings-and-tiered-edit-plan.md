# Plan — Cài đặt phát hành nhớ được và khoá được, và màn sửa câu hỏi thôi rối

## Goal

Biểu mẫu phát hành **nhớ** cái giáo viên gõ, **nói đúng** cái đang chạy, và **khoá** lại khi
không còn gì để đổi; thẻ sửa câu hỏi luôn vừa khung panel, và mỗi ô nói ra được nó là ô gì.

## Context

Hai việc, cùng tới từ lượt dùng thật ngày 06/10/2026, và cả hai đều là chuyện giao diện
đang **nói sai** về thứ nó đang giữ.

**Việc 1 — cài đặt phát hành không nhớ gì, và không khoá gì.** F5 là mất cả sáu ô vừa gõ.
Mở lại một đề đã phát hành thì sáu ô mở ra **trống**, trong khi đề đang thật sự chạy với
một bộ giờ cụ thể — nên màn hình không nói được *"12A mở lúc mấy giờ"*, và sáu ô vẫn gõ
được như thể gõ vào đó sẽ đổi được điều gì.

Số liệu nói việc này nhỏ hơn vẻ ngoài: `GET /teacher/assessments/{id}/publications`
(`teacher_routes.py:1755`) **đã** trả đủ sáu tham số cho từng lớp, kèm hai câu
`phase_one_note` / `phase_two_note` đã điền số bằng đúng hàm của `publication_wording`.
`api.ts:715` đã khai báo `teacher.publications`. `grep` cho ra **không một chỗ nào trong FE
gọi nó** — code chết. Việc cần làm là làm nó sống, **không** phải viết BE mới.

**Việc 2 — màn sửa câu hỏi rối, và đo được rối ở đâu.** Ba con số:

1. **~20 khối ngang hàng trong một cột 420px**: 1 ô đề bài + 4 phương án × 3 khối + nút
   thêm + 2 cách giải × 2 khối + nút thêm + hàng nút, tất cả cùng một cấp, `gap: 8px`.
2. **20 ô nhập, 0 nhãn hiện trên màn.** `Panel.Field` (`Panel.tsx:369`) chỉ đặt
   `aria-label`. Trình đọc màn hình biết ô nào là ô nào; mắt thì không.
3. **Lồng nhau tàng hình.** `.edit-option` không có viền, không nền, không thụt lề — chỉ
   `gap: 4px`. Thứ **duy nhất** nói "ô này thuộc phương án B" là chênh **4px so với 8px**.
   Năm thứ khác nghĩa hẳn nhau (đề bài, chữ phương án, nhãn lỗi, tên cách giải, lời giải)
   dùng **cùng một** `.field`: cùng viền, cùng 13px, cùng nền.

Và Figma xác nhận cái gốc: component `Question card — đang sửa` (`468:2050`) cao **775**,
trong khi vùng `questions` của panel cao **682** (panel 420×900, head 113). Sửa một câu là
chắc chắn không bao giờ thấy hết cái thẻ đang gõ — kể cả khi đề chỉ có một câu. Trang
`Screen — Teacher` có artboard 1→13 và **không artboard nào** dùng component ấy: màn sửa
câu hỏi chưa từng được vẽ trong ngữ cảnh.

**Kết quả mong muốn:** biểu mẫu phát hành nhớ đúng cái giáo viên gõ, nói đúng cái đang
chạy, và khoá lại khi không còn gì để đổi; thẻ đang sửa luôn vừa trong khung, và mỗi ô nói
ra được nó là ô gì.

## Global Constraints

- Tiếng Việt cho chuỗi ra màn hình, comment và docs; identifier và log tiếng Anh.
- **Figma đổi trước, người dùng duyệt, rồi mới vào FE** — người dùng đã chốt lại đúng câu
  này cho đợt. Bằng chứng tương đương là **đo** (`get_metadata` ↔ `getBoundingClientRect`),
  không phải mắt.
- Mỗi luật mới phải **đỏ đúng test (hoặc check) của nó** dưới một đột biến một dòng.
- `.\dev.ps1 check` · `test` · `typecheck` xanh trước khi tuyên bố xong.
- **Không lượt model nào.** Phát hành và sửa câu không gọi model; cả hai việc đo được bằng
  DOM và dữ liệu đã có trong database.
- Xin phép trước khi gọi subagent và trước khi commit. Không tắt BE/AGENT/FE, **không tắt
  Chrome**.
- **Không đụng BE.** Nếu giữa đường thấy cần sửa BE thì dừng và nói, vì nó nghĩa là tôi
  đọc sai hợp đồng.

## Hai quyết định đã chốt

- **Bản nháp khôi phục hết, kèm mốc đã gõ.** Hàng rào cho giờ quá khứ đã có sẵn và là chữ
  của BE: `faultOf` (`PublishSettings.tsx:647`) trả `rules.opens_in_the_past` khi
  `opens <= Date.now()`, hằng `FAULT_OPENS_IN_THE_PAST` ở `teacher_routes.py:537`. Nên
  khôi phục một giờ quá khứ **đỏ ngay**, bằng một câu không phải tôi viết.
- **Thẻ đang sửa: một lúc một tầng.** Mở `CÁCH GIẢI` thì `PHƯƠNG ÁN` tự thu. Đó là cả lý
  do làm việc này: chiều cao thẻ bị chặn trên bởi tầng cao nhất, nên nó không vượt 682 được.
  Vào màn thì `ĐỀ BÀI` mở.

## Files

| File | Việc |
|---|---|
| Figma `mOe2ZmrqOq1Uix45v6PNGD` | component `468:2050` thành variant set ba tầng; artboard **14**; variant `đã phát hành — khoá` cho `67:41`; sửa variant `thu` 53 → 52 |
| `services/fe/src/screens/teacher/remember.ts` | **mới** — đọc/ghi `localStorage` có kiểu, một chỗ |
| `services/fe/src/screens/teacher/PublishSettings.tsx` | nháp sống qua F5; đọc `publications`; khoá ô |
| `services/fe/src/screens/teacher/Editing.tsx` | **mới** — `Editing`, `Field`, `blankOption` rời khỏi `Panel.tsx`, cộng ba tầng |
| `services/fe/src/screens/teacher/Panel.tsx` | thôi giữ `Editing`/`Field`/`blankOption` |
| `services/fe/src/screens/teacher/Chat.tsx`, `Rail.tsx` | ba bản `try/catch` localStorage trùng nhau chuyển sang `remember.ts` |
| `services/fe/src/teacher.css` | khối `đã phát hành`; `:disabled`; ba tầng; vỏ cho option/method; nhãn hiện ra |
| `services/fe/src/teacher.test.tsx` | test cho từng luật mới |
| `tools/check_contract.py` | check **15**: cái khoá phải **nhìn thấy được** |
| `docs/overview/teacher-surface.md` | hai mục mới |
| `docs/decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md` | một dòng: khôi phục chữ giáo viên tự gõ **không** là một giá trị gợi sẵn |
| `docs/kich-ban-thu-tay-giao-vien.md` | lượt chạy mới, với số đo |

## Ordered Tasks

### Pha 0 — Figma, và chờ duyệt *(cổng)*

Người dùng chốt: *"cần làm figma trước, tôi duyệt thì implement vào fe"*. **Không** đụng FE
cho tới khi duyệt.

- [x] `Question card — đang sửa` (`468:2050`) thành **component set** với
      `Tầng=đề bài | phương án | cách giải`, 380 rộng, mỗi variant **≤ 400** cao. Ba thanh
      đầu luôn thấy; thanh đang mở bung ra. Thanh đầu mang caret + nhãn CAPS + một câu tóm:
      `PHƯƠNG ÁN · 4 · đúng: A`, `CÁCH GIẢI · 2`. Thanh đầu dùng lại từ vựng `sheet-head`
      vừa dựng cho tấm trượt phát hành — mũi nhọn **quay**, không đổi ký tự.
- [x] Trong tầng đang mở, **hướng A**: mỗi phương án và mỗi cách giải là một khối có nền
      `--sunken` + viền + padding 8, hàng nhãn làm đầu khối, ô nhãn lỗi **thụt vào** dưới ô
      chữ phương án và mang một caption `LỖI` thấy được.
- [x] **Nhãn hiện ra thật**, ba vai ba cỡ: `ĐỀ BÀI` / `PHƯƠNG ÁN A` + `LỖI CỦA A` /
      `CÁCH 1 — TÊN` + `LỜI GIẢI`. Đây là chỗ chữa lỗi số 2 ở trên.
- [x] Artboard **14 · Sửa một câu trong panel** (1440×900), nhân bản từ artboard 6
      (`15:55`) và thay thẻ câu đang xem bằng instance mới. Đây là phần *"bổ sung màn hình
      vào figma"* — hiện chưa có.
- [x] `Publish settings` (`67:41`) thêm variant **`Trạng thái=đã phát hành — khoá`**, 420
      rộng: khối `ĐÃ PHÁT HÀNH` một dòng mỗi lớp ở trên, sáu ô ở dưới **mờ**, chip lớp đã
      phát hành mờ, **không** CTA.
- [x] **Món này plan đặt SAI KHUNG, và phép đo nói ra.** 53 **đúng** cho trang Components,
      vì trang ấy chạy mode Student. Lỗi thật là chữ `Cài đặt phát hành` của nấc thu **gõ
      cứng 14px** trong khi **438/521** text của trang bind `fontSize` vào biến — chữ cùng
      chỗ ở nấc bung thì bind. Nay nó bind `type/label`, và phép đo chứng minh: **14/53 ở
      Components, 13/52 trên artboard Teacher**. Con số thôi bị ghim ở đâu cả.
- [x] Một frame quyết định trên trang Teacher ghi lại số đã duyệt, cùng khuôn `519:1603`.

### Pha 1 — Một chỗ nhớ, có kiểu *(không chờ cổng)*

- [x] `remember.ts`: `readJson<T>(key, fallback)`, `writeJson`, `readNumber`, `readFlag`,
      `forget`. Mỗi hàm nuốt lỗi — `localStorage` ném trong cửa sổ ẩn danh, và mất một bề
      rộng cột không được phép làm sập màn.
- [x] Ba bản `try/catch` đang trùng nhau chuyển sang nó: `Chat.tsx:988/996` (bề rộng cột),
      `Rail.tsx:8` (`SPLIT_KEY`), `Rail.tsx:25` (`PANE_KEY`). **Đây là refactor duy nhất
      của đợt**, và lý do là việc 1 sắp thêm bản thứ tư — bản đầu tiên cần JSON, nên chép
      lần thứ tư là chép một khuôn đã biết là sai chỗ.

**Nơi thi hành:** test persistence của pane và của bề rộng cột **đã có** và phải xanh
nguyên không sửa một chữ. Đó là điều kiện của một refactor: nó không được đổi hành vi nào.

### Pha 2 — Nháp sống qua F5 *(mở sau khi Figma được duyệt)*

- [x] Khoá `kriky.teacher.publish-draft.<assessmentId>`, giữ
      `{ picked, minutes, opensAt, closesAt, perQuestion, deadline, at }`. `at` là ISO có
      offset, lấy qua `isoWithOffset` đã có.
- [x] Đọc trong hàm khởi tạo của `useState`; ghi trong một `useEffect` theo sáu giá trị.
- [x] Một dòng `.draft-mark` dưới thanh đầu: *"Bản nháp bạn gõ 14:03 · 06/10."* + nút
      `Bỏ bản nháp` (xoá khoá, trả sáu ô về trống). Khôi phục im lặng là khôi phục không
      hỏi; dòng này là chỗ nói, và nút là đường lùi.
      Giờ in bằng `moment()` — **đúng** hàm mọi màn hình khác dùng, không có cách định dạng
      thứ hai nào sinh ra ở đây.
- [x] Xoá nháp khi có lớp nhận được đề (`result.classes.some(published)`).
- [x] Nấc thu/bung **nay cũng nhớ**, khoá `kriky.teacher.publish-open.<assessmentId>`. Lý
      do cũ cho việc nó **không** nhớ (*"nhớ nấc mà không nhớ giờ là nhớ nửa vời"*) chết
      theo pha này, nên docstring phải sửa chứ không để lại một lời đã hết đúng.
- [x] Docstring `PublishSettings` ghi cách đọc ADR-02: ADR-02 cấm **hệ thống gợi** một mốc
      giờ; khôi phục đúng cái giáo viên vừa tự gõ không phải một giá trị gợi sẵn. Và ghi
      hàng rào: giờ quá khứ đỏ bằng `rules.opens_in_the_past`, chữ của BE.
- [x] `adr-02-*.md` nhận một dòng cùng nội dung, vì đó là nơi luật ở.

**Nơi thi hành:** test gõ sáu ô → unmount → mount lại → sáu ô trở về, và `.draft-mark` in
đúng mốc. Cộng một test rằng `Bỏ bản nháp` trả sáu ô về trống **và** xoá khoá. Cộng một
test rằng một nháp mang `opensAt` quá khứ hiện `rules.opens_in_the_past` — chữ của BE, lấy
từ fixture, không gõ lại trong test. Đột biến: bỏ dòng ghi `localStorage` ⇒ đỏ.

### Pha 3 — Đọc lại giờ đã đặt, và khoá ô *(mở sau khi Figma được duyệt)*

- [x] `PublishSettings` gọi `teacher.publications(assessmentId)` cùng `publishForm` trong
      một `Promise.all`. Lỗi của lời gọi này **không** được chặn biểu mẫu: nó thêm thông
      tin, không mở cổng nào.
- [x] Khối `.published-to` trên trường `LỚP`: một dòng mỗi lớp — tên · N học sinh, giờ mở →
      giờ đóng dạng `HH:MM · DD/MM`, phút làm bài, phút/câu, hạn chữa, thu hồi được tới. Và
      **KHÔNG** in hai câu `phase_one_note` / `phase_two_note`. Plan ban đầu đòi in, và
      bản dựng đã bỏ chúng đi có chủ ý: hai câu ấy dài, và khối `rules` ngay dưới đã in
      đúng chúng rồi — chép lại cho **mỗi** lớp là đội tấm trượt lên quá chỗ panel có.
      Dòng này sửa lại cho khớp code; lời tuyên cũ là lời tuyên sai.
- [x] Chip của lớp đã phát hành: **thấy nhưng khoá** (`disabled`), không bỏ đi. Giáo viên
      cần thấy 12A đang giữ đề; bỏ chip đi là giấu mất thông tin ấy.
- [x] Mọi lớp đã phát hành ⇒ sáu ô `disabled`, và **CTA vắng mặt**. Vắng mặt chứ không
      khoá-kèm-lời-giải-thích, vì BE không có câu từ chối cho ca này và tôi **không bịa một
      câu tiếng Việt** vào chỗ ADR-03 giữ (đúng luật mà comment của `filled` đã ghi:
      *"chưa nói gì còn hơn nói một câu không phải của ai"*). Không còn lớp nào để phát hành
      thì không có việc nào để mời — đó là cấu trúc, không phải một câu.
- [x] **Một việc bị thu hẹp, nói ra chứ không lặng lẽ:** phát hành lại cho một lớp đang giữ
      đề (thay khung giờ của nó, theo docstring của bảng `publications`) từ nay phải đi qua
      `Hoàn tác` hoặc thu hồi lớp đó. Đó là cái giá của việc khoá ô, và nó đúng ý bạn đặt ra;
      ghi vào `teacher-surface.md` để không mất.
- [x] `teacher.css`: `:disabled` cho `input` và `.class-chip` của biểu mẫu — nền `--sunken`,
      chữ `--ink-faint`, `cursor: default`. Cái khoá phải **nhìn thấy được**, không chỉ có
      thật trong DOM.

**Và lượt thử tay tìm thêm HAI lỗi mà không test nào thấy.**

- **Năm ô khoá mà rỗng.** Hai lớp mở lệch giờ là hợp lệ, và khi ấy không có khung chung để
  điền — nên năm ô hiện ra vừa khoá vừa rỗng, ăn **805,5 trên 911** của panel và để vùng
  câu hỏi còn **24 pixel**. Đây đúng là thứ mà việc *điền giá trị vào ô khoá* sinh ra để
  chống; ca lệch giờ chỉ là ca không điền được. Sửa: không điền được thì **không dựng**.
  **805,5 → 428.** Thêm một test, một đột biến, và một variant Figma (`542:20`) cho nấc ấy.
- **Tên lớp CSS đụng nhau.** Tôi đặt `.who`, mà `.teacher .who` đã có chủ — hàng avatar của
  một lượt chat, `display: flex; height: 40px`. Một dòng chữ 11px cao **40** thay vì 16,5,
  và selector của tôi không ghi đè được vì tôi không đặt hai thuộc tính ấy. Đổi thành
  `.lop`: **428 → 381**, vùng câu hỏi **344 → 391**. jsdom không dựng bố cục nên không test
  nào bắt được lớp lỗi này — đó là lý do lượt thử tay tồn tại.

**Nơi thi hành:** test dựng `publications` trả hai lớp và khẳng định hai dòng có mặt với
đúng giờ của từng lớp. Cộng một test rằng khi mọi lớp đã phát hành thì
`input` đều `disabled` và không nút nào mang nhãn `Phát hành đề`. Cộng một test rằng một
lớp đã phát hành + một lớp chưa thì chip thứ nhất `disabled`, chip thứ hai bấm được, CTA
còn đó. Đột biến từng cái.

### Pha 4 — Thẻ đang sửa: ba tầng, một lúc một tầng *(mở sau khi Figma được duyệt)*

- [x] `Editing`, `Field`, `blankOption` rời `Panel.tsx` (852 dòng) sang `Editing.tsx`.
      Ranh giới thật: `Panel` là một panel ba khối, còn `Editing` là một biểu mẫu 20 ô với
      state tầng riêng. Đưa đi trước, đổi sau, nên `git` đọc ra hai việc chứ không một.
- [x] `tang` state: `"stem" | "options" | "methods"`, mặc định `"stem"`. Ba
      `<button className="tang-head" aria-expanded>`; chỉ thân của tầng đang mở vào cây DOM.
- [x] Câu tóm trên thanh đầu đếm từ `draft`: `PHƯƠNG ÁN · {n} · đúng: {label}`,
      `CÁCH GIẢI · {n}`. Đếm từ `draft` chứ không từ `question`: nó phải đổi theo cái đang gõ.
- [x] Dòng *"Phương án X chưa có nhãn lỗi"* và `refused` ở lại **ngoài** ba tầng, cạnh hàng
      nút. Một lời từ chối nằm trong một tầng đã thu là một lời từ chối không ai đọc được —
      và nút `Lưu` vẫn khoá theo nó, nên màn hình sẽ khoá mà không nói vì sao.
- [x] `Field` nhận nhãn **thấy được**: một `<label htmlFor>` thật thay cho `aria-label`.
      Lưu ý cái bẫy đã ghi trong comment: `Field` trả về một Fragment vì
      `.edit-method-head .field.title` nhận `flex: 1` từ một selector nhắm thẳng vào
      `textarea` — thêm một `<label>` sẽ đổi chỗ flex item ấy. Hàng đầu của cách giải đang
      được vẽ lại nên việc này an toàn, nhưng phải đo lại bề rộng ô tiêu đề sau khi sửa.
- [x] `teacher.css`: ba thanh đầu dùng lại khuôn `sheet-head`; `.edit-option` /
      `.edit-method` nhận nền `--sunken` + viền + padding; nhãn lỗi thụt vào; ba cỡ chữ cho
      ba vai.

**Nơi thi hành:** test rằng vào màn sửa thì thân `ĐỀ BÀI` có mặt và hai thân kia **không**;
bấm `CÁCH GIẢI` thì thân `PHƯƠNG ÁN` rời cây DOM — tức **đúng một** thân tại mỗi lúc, và đó
là luật chặn chiều cao. Cộng một test rằng số `<label>` nhìn thấy được **bằng** số ô nhập
trong tầng đang mở — luật vừa đổi là "nhãn thấy được", nên test phải đo đúng cái đó chứ
không đo `getByLabelText` (vốn đã xanh từ `aria-label`). Cộng một test rằng câu tóm đổi khi
`draft` đổi đáp án đúng.

### Pha 5 — Check, và đo trên trình duyệt thật

- [x] **Check 15** trong `tools/check_contract.py` (14 → 15): `teacher.css` phải có luật
      `:disabled` cho ô nhập và chip của biểu mẫu phát hành. Đây là một sự thật **CSS** mà
      jsdom không thấy — cùng lý do check 13 và 14 tồn tại: `getBoundingClientRect` trả 0
      nên không test nào đo được "mờ đi".
- [x] Đo trên trình duyệt thật, ghi vào `docs/kich-ban-thu-tay-giao-vien.md`:
      - Thẻ đang sửa, một tầng mở: cao bao nhiêu trên **682**, và `scrollHeight` =
        `clientHeight` — so với **775** của component cũ.
      - Nháp: gõ sáu ô, F5, sáu ô trở về, `.draft-mark` in đúng mốc.
      - [x] **Đã đo thật, sau khi review bắt được.** Lượt đầu tôi tick món này mà
        **không** làm: tôi tránh phát hành thật để khỏi đổi dữ liệu, rồi đọc một đề *đã*
        phát hành sẵn và coi như đã đi qua đường ấy. Hai đường khác nhau, và chính đường
        tôi bỏ qua là đường hỏng — lỗi `reread`.

        Đo trên `f348b4ba` (đã duyệt, chưa phát hành), **không tải lại trang**: phát hành
        cho 12A ⇒ chip 12A `disabled`, dòng `ĐÃ PHÁT HÀNH` của 12A hiện ra, 12B còn bấm
        được, CTA còn đó. Phát hành nốt 12B ⇒ **cả năm ô `disabled`** và mang đúng giá
        trị đã phát hành, cả hai chip khoá, **CTA biến mất**, hai dòng. Rồi thu hồi cả hai
        lớp để trả đề về `approved` — `publications` còn 0.
      - Nấc thu/bung của tấm trượt sống qua F5.
- [x] So Figma ↔ FE **bằng số** cho ba variant tầng và variant `đã phát hành — khoá`.
- [x] `teacher-surface.md` nhận hai mục, kèm cả việc bị thu hẹp ở Pha 3.
- [x] Plan này sang `docs/plans/active/2026-10-06-luu-cai-dat-va-man-sua-cau-hoi-plan.md`
      với checkbox thật thà.

## Validation Checks

- **Cổng:** `.\dev.ps1 check` (14 → 15) · `test` · `typecheck`.
- **Đột biến:** mỗi luật mới sửa một dòng cho sai, chạy lại, phải đỏ **đúng** test (hoặc
  check) của nó — không phải đỏ một chỗ khác.
- **Refactor không đổi hành vi:** test persistence đã có của pane và bề rộng cột phải xanh
  **không sửa một chữ**.
- **BE không đổi:** `git diff --stat services/be` phải rỗng. Nếu không rỗng thì tôi đã đọc
  sai hợp đồng, và đó là chỗ phải dừng để nói.
- **Trình duyệt** (đo DOM, **không** lượt model nào): năm phép đo ở Pha 5.
- **Figma ↔ FE** so bằng số, không bằng mắt.

## Status

**Xong cả sáu pha, Figma đã duyệt, và đã thử tay trên trình duyệt thật.** Cổng:
`check` **16/16** · `pytest` **398** · `vitest` **170** · `typecheck` — xanh. Hai mươi ba
luật mới, mỗi luật đỏ đúng test (hoặc check) của nó dưới một đột biến một dòng.

Hai con số trên là số **sau** lượt review ở mục dưới: `check` 15 → 16 (thêm phép canh tài
liệu tự lặp), `vitest` 164 → 170 (năm test cho bốn lỗi review tìm ra, cộng một test cho
phần bù icon rail). Con số 15/15 · 164 mà mục này từng mang là con số tôi tuyên "xong"
trước khi review chạy — giữ lại trong câu dưới vì nó chính là cái cần nhớ.

`git diff --stat services/be` đúng bằng change set của đợt trước: **không một dòng BE nào**
đổi trong đợt này, như ràng buộc đã đặt.

Lượt thử tay ghi ở `docs/kich-ban-thu-tay-giao-vien.md`, mục *"lượt bốn"*, với số đo của cả
hai việc và **không** một lượt model nào. Nó tìm thêm **hai** lỗi (năm ô khoá mà rỗng; tên
lớp CSS đụng nhau), và cả hai đã sửa, đo lại, và ghi vào tài liệu.

Một dòng của plan này đặt sai khung và phép đo đã bác: xem món `517:17` ở Pha 0.

### Review độc lập tìm thêm bảy chỗ, và tôi đã sửa cả bảy

Một lượt review độc lập chạy sau khi tôi tuyên "xong". Nó tìm ra **bốn lỗi thật**, **hai test
xanh vô nghĩa** và **hai check lách được** — tức cổng 15/15 của tôi đã xanh trên một change
set có bốn lỗi.

- **Tài liệu bị phá, 81 MB / 889.029 dòng.** Script sửa `kich-ban-thu-tay-giao-vien.md` cắt
  lát bằng hai `str.index()` mà không kiểm số lần xuất hiện; một mốc có mặt ở **hai** chỗ
  nên lát cắt thành rỗng, và `str.replace("", block)` chèn khối mới vào giữa **mọi ký tự**.
  Không cổng nào nhìn vào `docs/`, nên `check`, `pytest`, `vitest` và `typecheck` xanh suốt.
  Cứu nguyên vẹn (mọi ký tự gốc vẫn nằm giữa các bản chèn), và **check 16** nay canh đúng
  lớp lỗi ấy — đã dựng lại chính lần hỏng để chứng minh nó bắt được.
- **`form` không đọc lại sau khi phát hành** (`reread` thiếu trong deps): phát hành xong mà
  năm ô vẫn gõ được và CTA vẫn mời bấm lần nữa. Cái khoá chỉ tới sau một lần F5.
- **Mốc bản nháp tự ghi đè:** effect ghi cũng chạy lúc mount, nên chỉ *mở ra xem* là mốc
  nhảy, và từ lần F5 thứ hai dòng báo nói một giờ không ai gõ gì.
- **Nháp chảy sang đề khác** khi `assessmentId` đổi mà component không dựng lại.
- **`publications` hỏng + đề đã phát hành ⇒ mất sạch thân biểu mẫu**, ngược hẳn lời hứa
  "lời gọi này không được chặn biểu mẫu" ghi ngay trên nó.
- Hai test xanh vô nghĩa (`aria-labelledby` trỏ id không có thật vẫn truthy; biên `>= 12` bỏ
  lọt icon vẽ tràn) và hai check lách được (`inline-block` thoả phép kiểm `display`;
  `transform: none` thoả phép kiểm phần bù; `background: transparent` thoả check 15).

**Bài học, và nó không phải về code.** Mọi lỗi trên đều nằm ở đường mà test của tôi **không
đi**: test mount với trạng thái đã-phát-hành sẵn thay vì bấm nút phát hành; test `unmount()`
trước khi đổi đề thay vì đổi tại chỗ; test đọc DOM thay vì đọc lại `localStorage`. Tôi viết
test cho trạng thái *kết quả*, không cho *đường đi tới nó* — và đường đi là chỗ người dùng
thật sự bước qua.

Hai thứ còn nợ từ đợt trước, **không** thuộc đợt này và không bị mất: ba luật của ghi chú
Figma `129:2` chưa có code (tỉ lệ thay vì pixel, bấm đúp thanh kéo về 60/40, đường bàn phím
cho thanh kéo), và prompt pha 1 vẫn hỏi lại khi giáo viên đã cho cả khối lớp lẫn phạm vi.
Change set của đợt bảy lỗi giao diện vẫn **chưa commit**.
