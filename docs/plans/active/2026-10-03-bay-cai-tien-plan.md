# Bảy cải tiến từ một đợt dùng thật — tên đoạn chat, viền panel, hộp thoại lời giải, toán, sửa câu

## Context

Giáo viên ngồi dùng một đợt thật và nêu bảy chỗ. Khảo sát cho thấy **năm trong bảy** có nguyên nhân
gốc đo được, không phải chuyện khẩu vị:

1. **Tên đoạn chat sai.** Gõ *"Chào bạn"* → rail hiện *"Tạo đề kiểm tra 15 phút"*. Prompt đặt tên
   (`agent/graphs/naming.py`) ép model *"gọi tên VIỆC, không chào hỏi"* — một lời chào **không có
   việc nào**, nên model buộc phải bịa, và nguồn duy nhất để bịa là chính hai ví dụ trong prompt.
   Cái tên sai là phép trộn đúng hai ví dụ ấy. Nó **tuân thủ** prompt — sáu từ, viết thường — nên
   `_tidy` không có cách nào bắt.
2. **Panel không có viền.** Vạch vẽ bằng `box-shadow: inset 1px 0 0` trên `.panel`, nhưng inset
   shadow của cha nằm **dưới** nền của con, và ba khối con đều có nền trải hết bề rộng — chúng phủ
   mất đúng dải 1px ấy. Vạch chỉ sống ở dải `.panel-head`.
3. **Nút *Hoàn tác* không bấm được.** Nó bấm được, nhưng **panel không có đường bỏ duyệt nào**: chân
   panel chỉ có một nút, và với đề đã duyệt nó `disabled`, trong khi dòng chú thích ngay trên nói
   *"muốn sửa thì bỏ duyệt trước"*. `teacher.unapprove` đã có trong `api.ts` và endpoint đã sống;
   **chưa ai gọi nó, một lần nào**.
4. **Hai nút giống nhau.** Nút phụ dùng **cùng màu `--accent`** cho chữ mà nút chính dùng cho nền,
   cùng cỡ chữ, cùng cân nặng, cùng bo góc, không `:hover` nào. Figma cũng vậy — lỗi của thiết kế
   trước, không chỉ của code.
5. **Lời giải mở tại chỗ.** Figma **đã có sẵn** `Solution dialog` và artboard `12 · Xem lời giải một
   câu`, có ánh xạ *mỗi phương án nhiễu gắn một lỗi* mà panel không hiện. Việc là **dựng thứ đã
   vẽ**.
6. **Toán không render.** Không một thư viện nào, không một chỗ nào: mọi vị trí in chữ câu hỏi đều
   là `{text}` thuần. Bốn prompt đều cấm LaTeX và bắt Unicode, **không dòng code nào thi hành** —
   và model thật đã trả một tích phân LaTeX ra thẳng màn hình giáo viên.
7. **Tải tài liệu đặt sai chỗ.** Nút `＋ Tài liệu` nằm ở composer, trong khi tài liệu thuộc về
   **giáo viên** chứ không thuộc đoạn chat (ADR-04).

**Kết quả mong muốn:** gõ một lời chào → tên đoạn nói về lời chào; một đề có tích phân → công thức
dựng hình; mở lời giải → hộp thoại; duyệt → chân panel đổi nút; bỏ duyệt → sửa được chữ một câu; kéo
một tài liệu từ kho vào ô nhập.

## Global Constraints

- **Figma đổi trước, code theo sau**, và cả hai trong **cùng một change set**, chứng minh bằng đo
  (`mcp__figma__get_metadata`), không bằng mắt.
- Sau **mỗi pha**: một subagent review code, **cộng** một subagent chuyên biệt **đối chiếu ảnh chụp
  màn hình FE với artboard Figma**. Không dừng chờ duyệt giữa các pha.
- Tiếng Việt cho chuỗi ra màn hình, comment và docs; identifier và log tiếng Anh.
- `.\dev.ps1 check` 8/8 + pytest + vitest + `tsc --noEmit` xanh trước khi sang pha sau.
- Mỗi luật mới kèm một **đột biến một dòng** đã đo là đỏ đúng một test.
- API key có hạn mức — gộp mọi lượt model thật vào một phiên, `gpt-4o-mini`.

## Files

- `services/agent/src/agent/graphs/` — `naming.py`, `authoring.py`, `explain.py`, `propose.py`,
  `reporting.py`
- `services/be/src/be/` — `teacher_chat.py`, `agent_gateway.py`, `teacher_routes.py`
- `services/fe/src/` — `MathText.tsx` (mới), `screens/teacher/Veil.tsx` (mới), `Panel.tsx`,
  `Chat.tsx`, `Rail.tsx`, `PublishSettings.tsx`, `teacher.css`, bốn màn học sinh, `api.ts`
- Test — `be/tests/test_math_delimiters.py` và `test_edit_question.py` (mới),
  `test_teacher_chat.py`, `test_teacher_memory.py`, `fe/src/math.test.tsx` (mới), `teacher.test.tsx`
- Docs — `docs/overview/teacher-surface.md`, `docs/kich-ban-thu-tay-giao-vien.md` (mới), `AGENTS.md`

## Ordered Tasks

- [x] **Pha 1 — Tên đoạn chat nói về câu đã gõ.** Prompt có **đường ra** cho câu không chứa việc
  nào, và hai ví dụ cũ thôi làm nguồn chữ cho mọi lần model bí. **Và một chốt kiểm ở BE, vì một
  prompt là một lời nhờ:** `_echoes(said, title)` bỏ cái tên không chia một từ nội dung nào với câu
  đã gõ, lùi về `_tidy(said)`. Cộng một lỗ hổng đang mở: nhận kết quả job mà không so `request_id`.
- [x] **Pha 2 — Panel: viền thật, đường bỏ duyệt, hai nút phân biệt được.** `box-shadow` thường
  thay cho `inset`; chân panel ba trạng thái (còn mở / đã duyệt / đã phát hành) với `Hoàn tác` trên
  `Phát hành đề`, gọi `teacher.unapprove`; nút phụ thôi dùng `--accent` cho chữ.
- [x] **Pha 3 — Lời giải mở thành hộp thoại.** Dựng `Solution dialog` đã vẽ, mang cả ánh xạ
  nhiễu→lỗi. **Ba thứ thiếu ở *mọi* hộp thoại** — Esc, bấm nền, `z-index` — gom vào `Veil.tsx` và
  áp cho cả ba chỗ dùng.
- [x] **Pha 4 — Tài liệu về đúng chỗ của nó.** Icon tải lên chuyển sang `pane-head` của kho tài
  liệu; chip `draggable` thả vào composer để đính vào một câu chat.
- [x] **Pha 5 — Toán render được.** Một component `<MathText>` thay `{text}` ở mọi vị trí in chữ câu
  hỏi, **hai bề mặt ship cùng lúc**; bốn prompt đổi từ *"cấm LaTeX"* sang *"toán viết trong `$…$`"*;
  **một nơi thi hành** trong `validate_question`, vì bốn prompt cũ chứng minh lời nhờ không đủ.
- [x] **Pha 6 — Giáo viên sửa được chữ của một câu hỏi.** Nút `Sửa` (một nút chết, không `onClick`)
  nối vào `PATCH /api/teacher/assessments/{id}/questions/{question_id}`. Cổng ADR-01: chỉ sửa khi đề
  còn mở. Câu sửa tay đi qua **đúng** `validate_question` mà câu model viết phải qua.
- [x] **Pha 7 — Đối chiếu Figma và dọn những gì review tìm ra.**

## Decision Records

### Decision: Đường render toán

options considered:

- **Unicode thuần, như bốn prompt đang đòi.** Không dependency, không đổi FE.
- **LaTeX trong `$…$`, dựng hình bằng KaTeX ở FE.**
- MathML, hoặc MathJax.

selected option: LaTeX + KaTeX.

reason: Unicode không viết nổi phân số chồng tầng, tích phân có cận, căn, giới hạn — mà đề Toán 12
đầy những thứ đó. Và lựa chọn ấy **đã được thử rồi**: bốn prompt cấm LaTeX suốt một thời gian dài,
không dòng code nào thi hành, và model cứ viết LaTeX. Hướng đi ngược lại — toán **được** viết bằng
LaTeX và FE dựng hình nó — biến một lệnh cấm không ai tuân thành một hợp đồng có nơi kiểm. KaTeX hơn
MathJax ở chỗ dựng đồng bộ (không nhảy layout) và hơn MathML ở chỗ không phụ thuộc trình duyệt. Giá
phải trả: ~280KB vào bundle, và nạp tách nếu đo thấy nặng.

### Decision: Corpus cũ không cần migration

options considered: một lần chuyển đổi dữ liệu sang `$…$`; hoặc nhận cả bốn kiểu dấu.

selected option: nhận bốn kiểu — `$…$`, `$$…$$`, `\(…\)`, `\[…\]`.

reason: Dữ liệu đã lưu mang `\(…\)` và `\[…\]` vì model viết thế suốt thời gian lệnh cấm không có
nơi thi hành. Nhận cả bốn thì corpus cũ đọc được ngay, và chuỗi Unicode thuần đi qua nguyên vẹn —
không một lần migration nào có thể chạy sai.

### Decision: Phạm vi đường sửa của giáo viên

options considered: sửa được chữ của câu hỏi; hoặc sửa cả cấu trúc (thêm/bớt phương án, đổi đáp án
đúng).

selected option: sửa được chữ.

reason: Đổi đáp án đúng là đổi **luật tính điểm** của một câu, và nó đòi một quyết định riêng về
những lượt đã làm. Sửa chữ thì không chạm gì tới điểm. Và cổng ADR-01 đã chặn mọi thứ sau khi duyệt,
nên đường sửa này chỉ sống trong khe trước gate đầu tiên.

### Decision: `Hoàn tác` đứng ở đâu

options considered: trên thẻ kết quả trong dòng chat; hoặc ở chân panel đề.

selected option: chân panel đề.

reason: Thẻ trong dòng chat là **biên bản** của một việc đã xảy ra (ADR-24) — một nút đổi trạng thái
hôm nay đứng trên một biên bản của hôm qua là mời bấm vào quá khứ. Chân panel là chỗ duy nhất luôn
nói trạng thái **hiện tại** của đề.

### Decision: Nâng cap `AGENTS.md` lên 179

options considered: để `docs/kich-ban-thu-tay-giao-vien.md` không có hàng nào trong bảng ownership;
gộp nó vào `docs/local-development.md`; hoặc nâng cap một dòng.

selected option: nâng cap lên 179, và cho nó một hàng.

reason: Kịch bản thử tay là thứ giáo viên và người dev **chạy lại nhiều lần**, không phải phần phụ
của một plan rồi chết theo plan. Một file ở gốc `docs/` không có chủ là đúng loại drift mà bảng ấy
tồn tại để chặn. Luật nâng cap đòi một decision record nói dòng đó mua gì — dòng này mua một chủ sở
hữu cho một quy trình sống lâu hơn plan này.

## Validation Checks

1. `.\dev.ps1 check` → 8/8.
2. `pytest -q` → xanh. `npx vitest run` + `npx tsc --noEmit` → xanh.
3. Đo Figma đối chiếu từng pha, bằng subagent chuyên biệt chạy riêng khỏi subagent review code.
4. Một lượt thật trên browser với `gpt-4o-mini`, theo `docs/kich-ban-thu-tay-giao-vien.md`.
5. Đột biến của mỗi pha, đo và ghi số.

## Đợt hai — tám món nữa từ cùng một đợt dùng

Giáo viên xem lại bảy pha và nêu tám chỗ. Hai trong số đó là **lỗi nối dây có nguyên nhân đo được**,
không phải việc mới:

- [x] **1 · Dòng *"Tệp đã vào thư viện tài liệu của bạn…"*** — người dùng tự xoá khỏi code. Dọn nốt
  `.scope-note` trong CSS, hàng G2 của kịch bản thử tay, và text node `455:2363` trên Figma.
- [x] **2 · Kéo để đổi bề rộng rail và panel.** Component `Split` mới, dùng lại hai kết luận đã trả
  giá của thanh kéo ngang trong rail: đo từ **mép cửa sổ** chứ không cộng dồn delta, và ghi lúc thả
  tay từ **`ref`** chứ không từ state. Bề rộng đi xuống bằng custom property, nên `Rail` và `Panel`
  không cần biết chúng tồn tại. Cột giữa thôi ghim 820/660, chuyển sang `min(…, 100%)`.
- [x] **3 · `teacher.approve` / `unapprove` / `publish` không vào khối `Thinking`.** Chúng là nút
  giáo viên bấm; khối ấy là bằng chứng **model** đã làm gì. Đo được: một cú bấm hiện **hai lần**.
- [x] **4 · Phương án hai cột, chữ to lên một bậc.** Lưới `auto-fit`, không `repeat(2, 1fr)` cứng.
- [x] **5 · Ba nút trên thẻ kết quả không chạy.** Nguyên nhân: duyệt thì bấm **từ trong panel**, nên
  lúc thẻ hiện ra route đã là `.../de/{đề}`, mà cả ba chỉ gọi `go()` tới đúng route ấy — gán lại một
  hash không đổi thì không có `hashchange` nào.
- [x] **6 · Bỏ nút *Tải tệp khác*.** Tải lên còn một cửa, icon cạnh nhãn `TÀI LIỆU`.
- [x] **7 · Bỏ hai dòng chi tiết** của thẻ `đã-duyệt` và `bỏ-duyệt`.
- [x] **8 · Chip `safety` về cùng dòng với đầu đề**, đẩy mép phải, trên cả chín variant Figma.

### Decision: thẻ kết quả là biên bản, không phải bộ điều khiển

options considered: nối lại dây cho ba nút chạy thật; bỏ sạch nút trên ba thẻ ấy; hoặc bỏ nút đổi
trạng thái và giữ lại một nút `Xem`.

selected option: giữ một nút `Xem`.

reason: Nối lại dây thì một thẻ cũ giữa dòng chat đổi được trạng thái đề **hiện tại**, và hai thẻ
duyệt/bỏ duyệt nằm cạnh nhau sẽ cùng bấm được trong khi chúng nói hai chuyện trái nhau. Bỏ sạch nút
thì khi panel đã đóng không còn cửa nào vào đề. Một nút `Xem` giữ đúng ranh giới mà quyết định
*"`Hoàn tác` đứng ở chân panel"* đã vạch: panel là nơi duy nhất nói trạng thái **hiện tại**.

### Đối chiếu Figma ↔ FE của đợt hai

Một subagent chuyên đối chiếu đo cả tám món: **tám KHỚP**, không chỗ nào phải chặn. Ba phát hiện,
và cách xử lý từng cái:

- **Thanh kéo lệch nửa pixel trên Figma** — instance đặt ở x=258 với bề rộng 5 cho tâm 260.5, trong
  khi mép cột là 260. Ở đây **code mới là bên đúng**, nên thiết kế đi theo phép đo: cả component và
  hai instance đổi thành 7px đặt tại x=256.5 và x=1016.5, tâm đúng 260 và 1020.
- **Nghi chip `safety` ở hai variant 480px dùng cỡ chữ to hơn** — đo lại `fontSize` của text node
  trong cả mười variant: **đều là 12**, không trừ cái nào. Chênh ~15px bề rộng đến từ chuỗi chữ khác
  nhau (`Chưa phát hành cho học sinh` dài hơn `Chưa duyệt · chưa phát hành`). Phát hiện không đứng.
- **`Xem` biến mất khi `paper === ""`** — giữ nguyên. `paper` đọc `assessment_id ?? entity_id`, và
  một lượt `teacher.approve` luôn mang `entity_id`, nên nhánh ấy không tới được qua giao diện. Cái
  guard là lưới cho một thẻ không có đề để mở, và một nút mở-không-có-gì-để-mở tệ hơn không nút.

Một khoảng trống subagent nêu — chưa đo được rail mặc định 260 trên trình duyệt vì `localStorage`
đã mang giá trị đã kéo — thực ra đã kín: phép đo đầu tiên của đợt này, **trước** cú kéo đầu tiên,
cho `rail: 260`, `--rail-w: "260px"`, `saved: null`.

## Đợt ba — bốn bug từ lượt review

- [x] **1 · Lời giải mất xuống dòng.** Bong bóng chat có `white-space: pre-wrap` từ lâu; ba khối
  chữ của hộp lời giải thì chưa bao giờ, nên một lời giải ba bước dính thành một dải chữ.
- [x] **2 · Cho sửa nhưng không cho lưu.** Xem *"Chẩn đoán sai"* bên dưới.
- [x] **3 · Số phương án và số lời giải không cố định.** Form sửa thêm/bớt được, và có ô cho
  `error_label` lẫn `method.title` — thiếu ô nhãn lỗi thì nút *Thêm phương án* chỉ dẫn tới một lần
  422, vì ADR-18 bắt mọi nhiễu phải có nhãn.
- [x] **4a · Thẻ kết quả.** Bỏ `detail` ở mọi variant, bỏ cả nút `Xem`: **bấm vào thẻ** là mở
  panel. Năm nút cũ (`Duyệt đề`, `Xem đề`, `Xem`) đều gọi đúng một hàm.
- [x] **4b · Xoá màn 6.5.** Duyệt xong là sang thẳng cài đặt phát hành; `Hoàn tác` chuyển về màn
  7; nút chính ở đó bỏ con số đầu người. Artboard 14 xoá khỏi Figma.

### Decision: lưới toán thôi chặn

options considered: giữ phép từ chối và chỉ đích danh ô sai; chỉ kiểm những ô giáo viên đã đổi;
hoặc bỏ hẳn phép chặn và hiện nguyên văn.

selected option: bỏ hẳn, hiện nguyên văn.

reason: **Đây là đảo chiều một quyết định của Pha 5** trong chính plan này, và lý do thì không phải
vì chẩn đoán cũ sai mà vì cái giá đã đo được: mọi câu soạn trước khi hợp đồng `$...$` ra đời đều
không lưu lại được — công cụ duy nhất để dọn nội dung hỏng lại từ chối lưu vì nội dung đang hỏng.
`MathText` chạy KaTeX với `throwOnError: false` và cho chuỗi không có cặp `$` đi qua như chữ
thường, nên một dòng LaTeX thô là thứ **đọc được và sửa được**. Những phép kiểm còn lại nói về tính
đúng của đề, không về cách gõ: cách gõ sửa được bằng mắt, còn một đề hai đáp án đúng thì không ai
nhìn ra lúc học sinh đang làm bài.

### Chẩn đoán sai, và nó sai ở đâu

Với bug 2 tôi chạy `_math_is_loose` lên đúng hai chuỗi đang nằm trên màn hình và chúng bị từ chối
thật. Tôi kết luận đó **là** nguyên nhân. Đo trên trình duyệt sau khi sửa thì lời từ chối hiện ra
là `Not Found`: tiến trình BE đang chạy khởi động từ trước khi endpoint `PATCH .../questions/{id}`
ra đời, và `--reload` không reload thật trong setup này — nên cú bấm Lưu trả **404**, chưa bao giờ
tới được phép kiểm kia.

Phép đo của tôi đúng về chuyện nó đo; sai là ở chỗ tôi gọi một **chặn thứ hai** là nguyên nhân duy
nhất, mà không kiểm xem request có tới nổi chỗ ấy không. Bài học giữ lại: khi một lời từ chối hiện
ra trên màn hình, **đọc chính câu ấy trước** rồi mới đi tìm luật nào phát ra nó — `curl
/openapi.json` tốn ba giây và đã trả lời xong câu hỏi.

## Đợt bốn — biểu mẫu phát hành đọc đỡ rối

- [x] **Bỏ dòng *"Đã chọn x trong y lớp · z học sinh"*.**
- [x] **Câu luật `--:--` không bao giờ cập nhật.** BE gửi **khuôn**, FE điền số đang gõ.
- [x] **Hai bậc nhãn + vạch mảnh.** Tám nhãn VIẾT HOA cùng sức nặng còn ba; năm nhãn ô xuống
  chữ thường. Một hairline `--line` trên mỗi mục pha.

### Decision: khuôn câu ở BE, chỗ trống do FE điền

options considered: bỏ hai câu khỏi biểu mẫu (chúng đã đúng số ở hộp xác nhận); gọi preview sau
mỗi lần gõ để lấy câu thật; hoặc BE trả khuôn và FE điền.

selected option: BE trả khuôn, FE điền.

reason: Người dùng chọn. Rủi ro tôi nêu trước khi làm là phép cộng *giờ đóng + phút làm bài* sẽ có
hai bản — và chính docstring của `publication_wording.py` lúc ấy đang **cấm** điều đó
(*"một câu có số do FE tự tính là một bản cài đặt thứ hai của phép tính ấy"*). Cách giữ lời hứa gốc
mà vẫn làm được việc: biến chính khuôn thành nguồn duy nhất — BE dựng câu thật **bằng** khuôn nó
gửi đi — nên thứ nhân đôi chỉ còn phép cộng, không phải chữ nghĩa. Docstring đã được viết lại cho
thành thật về chuyện này, và một test ghim khuôn-điền-tay phải khớp câu hàm dựng ra.

## Status

Bảy pha đã xong; `check` 8/8, pytest xanh, 79 test FE xanh, `tsc` sạch. Chưa commit — chờ người
dùng review một lượt.

## Những gì review tìm ra, và đã sửa

Review code và đối chiếu Figma chạy sau mỗi pha. Những phát hiện đáng ghi lại, vì mỗi cái là một
loại lỗi sẽ quay lại:

- **Tôi ship đúng cái lỗi tôi đang đi sửa.** Chân panel coi `published` như `approved`, nên một đề
  đã phát hành vẫn mời `Hoàn tác`, và cú bấm ấy luôn 409. Tách thành ba trạng thái.
- **Ví dụ trong prompt trả lời sẵn bài kiểm.** Tôi viết `Chào bạn → Chào hỏi` vào prompt đặt tên —
  đúng ca đo được là sai, nên nó thành không chứng minh được gì nữa. Đổi sang một ca khác.
- **Đo thắng trực giác.** Tôi bỏ nền `--paper` của vùng câu hỏi vì tin panel trắng toàn phần sẽ tách
  rõ hơn; đo Figma cho thấy ngược, và việc bỏ nó làm thẻ trắng trên trắng. Khôi phục.
- **Màu mất nghĩa.** Ánh xạ nhiễu→lỗi dùng `--accent`/`--ink` ở chỗ thuộc về `--answer-correct` /
  `--answer-incorrect` (ADR-12).
- **Pha 5 làm ba bề mặt tệ hơn trước một lúc:** prompt bắt đầu đòi LaTeX trong khi bong bóng chat vẫn
  in chữ thuần. Bọc cả bong bóng giáo viên, bong bóng học sinh và nhãn lỗi.
- **Tiền tệ.** `Một quyển 20$, hai quyển 40$` có số chẵn dấu `$`, nên phép đếm chẵn lẻ không thấy gì
  và cả đoạn giữa bị dựng thành công thức; còn `5$` một mình thì bị từ chối 422. Luật pandoc — dấu mở
  không dính chữ số, không khoảng trắng sát dấu — sửa cả hai, và **cùng một khuôn ở BE và FE**: lệch
  nhau thì BE nói hợp lệ còn màn hình vẽ ra thứ khác.
- **Cú pháp giãn dòng của `cases` bị từ chối oan** vì phép quét dấu ngoặc LaTeX chạy trên cả chuỗi
  thay vì chỉ phần ngoài công thức — nó rất thường gặp trong hệ phương trình.
- **Một cú thả tệp từ desktop làm SPA điều hướng đi**, mất cả chữ đang gõ. `preventDefault()` phải
  vô điều kiện, không chỉ khi đúng loại dữ liệu.
- **Sửa một câu đã có người trả lời** sinh `AnswerOption.id` mới và bỏ mồ côi mọi `Answer.option_id`
  — SQLite im lặng, Postgres nổ 500. Từ chối 409, kèm lưới.
- **Hai lỗ của lưới cũ**: hai phương án cùng nhãn (ra 500 vì `UniqueConstraint`) và câu chỉ có một
  phương án (lọt vì *"mọi nhiễu có nhãn lỗi"* đúng một cách rỗng khi không có nhiễu nào).
- **Churn.** Tôi chạy `prettier --write` rộng tay; prettier **không** nằm trong `dev.ps1 check`, nên
  nó chỉ sinh ra nhiễu: 119 dòng đổi cho một việc 20 dòng ở `PublishSettings.tsx`, 234 cho 25 ở
  `Tutor.tsx`, và một file không pha nào chạm tới. Lùi hết về HEAD rồi đắp lại đúng phần có nghĩa.
- **Một lỗi mà không test nào trong repo này bắt được.** Thanh kéo viết `flex: 0 0 0` cộng
  `width: 7px`; với một flex item thì `flex-basis` thắng `width`, nên vùng bắt chuột rộng **0** và
  trong trình duyệt thật không có gì để trỏ vào. Ba test jsdom xanh suốt, vì chúng bắn sự kiện thẳng
  vào element và không dựng bố cục. Chỉ một phép đo `getBoundingClientRect()` trên màn hình thật mới
  thấy. Kết luận giữ lại: **một luật về bố cục CSS không có nơi thi hành trong vitest** — lưới của
  nó là trình duyệt.
- **Thứ tự trong `onPointerUp`.** Bản đầu thả pointer capture **trước** rồi mới ghi bề rộng; một cú
  ném từ `releasePointerCapture` cắt ngang handler và bề rộng giáo viên vừa chọn mất trắng. Capture
  chỉ là tối ưu, ghi mới là việc chính — nên ghi trước, và bọc cả hai lời gọi capture để chúng không
  ném được.
- **Một subagent review chạy song song với lúc tôi đang sửa cùng file** đã khôi phục một bản backup
  trước khi sửa, và việc của cả một pha biến mất lặng lẽ. Bắt được nhờ một test. Từ đây: không chạy
  subagent review đồng thời với việc sửa cùng những file ấy.
