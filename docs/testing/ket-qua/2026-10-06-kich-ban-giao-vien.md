# Các lần chạy kịch bản giáo viên ngày 06/10/2026

Dời nguyên văn từ `docs/testing/kich-ban-thu-tay-giao-vien.md` ngày 20/10/2026, khi kịch bản được viết lại thành kịch bản đầu-cuối. Các mục chặng A–H nhắc tới là của kịch bản cũ (xem git log).

### Lần chạy 2026-10-06 — năm đoạn chat, giữ lại để đọc lại

| Đoạn | Mục | Kết quả |
|---|---|---|
| `chào bạn` | A1 | đạt |
| `Tạo đề` | A2, A3, D1, D3–D6, E1–E4 | A3 **2/3 câu**; còn lại đạt |
| `tạo đề 500 câu…` | B1 | đạt sau khi ép lượt thứ hai |
| `Kết quả lớp 12` | C1, C2 | đạt |

**Bốn thứ đo được, nguyên văn:**

1. **A3 cho 2/3 câu.** Ba job soạn chạy song song trên cùng một brief; hai câu mở đầu giống hệt
   nhau (*"Tính giá trị của tích phân sau: $\int…"* và *"…: $\bigg|…"*), BE loại một câu là trùng,
   `draft_items` còn lại một dòng `retry`. Thẻ ghi `Dừng ở 2/3 câu` và câu kể nói *"chỉ có 2/3 câu.
   Đề chưa đủ câu"* — **hai chỗ khớp nhau**, nên đây là hệ thống nói thật về một lần soạn hụt, không
   phải lỗi giao diện.

   **Đã sửa 06/10/2026.** Năm mắt xích, truy được hết: `fire()` tính `banned` **một lần** trước khi
   đẩy job (rỗng, vì đề mới) → ba job song song cùng cầm danh sách rỗng ấy → hai câu mở đầu giống
   nhau → ô thứ hai bị đánh `retry` → mà `fire()` chỉ được gọi từ `start_drafting`, nên `retry` thực
   tế nghĩa là **bỏ dở**. Nay `harvest()` tự bắn lại ngay trong lượt thu, với `banned` **đã có** câu
   vừa ghi; `attempts` vẫn là trần. Cộng hai thứ biến *"không ai truy được"* thành *"đọc một dòng
   SQL"*: cột `draft_items.last_fault` chở lý do, và BE **có cấu hình logging** — trước đợt này
   không có dòng nào, nên mọi `logger.info` của `be.drafting` rơi vào hư không.

2. **Đánh số câu nhảy 1 → 3.** `order_index` giữ chỗ của câu soạn hỏng, và panel in thẳng số ấy. Đầu
   panel ghi *"2 câu"* trong khi thân ghi *"Câu 1"* rồi *"Câu 3"* — hai con số trên một màn hình nói
   ngược nhau, và giáo viên đọc ra là có một câu bị giấu.

3. **Model đánh dấu sai đáp án.** `$\int_0^1 (3x^2-2x+1)\,dx$` bằng **1**, nhưng phương án được
   đánh dấu đúng là `1/3`. Sửa bằng nút chọn trong form (mục D5) thì đi được trọn đường. Và một câu
   nữa vô nghĩa về mặt toán: *"Tính giá trị của tích phân sau: $\bigg|\frac{1}{2}\bigg| =
   \bigg|\frac{1}{2}$"* — ADR-26 cho chữ hỏng đi tới giáo viên đúng như đã chốt.

4. **ADR-26 chạy đúng.** Không một ký tự điều khiển nào trong toàn bộ dữ liệu mới (`stem`, `option`,
   `method` đều 0), panel dựng **10 công thức** với **0 lỗi KaTeX** và **0 dấu đô la lọt ra màn**.

### Lần chạy 2026-10-06, lượt hai — sau khi sửa, trên database vừa tạo lại

Một đoạn chat, một lượt `gpt-4o-mini` soạn đề, rồi đi hết vòng `đã tạo đề → đã duyệt đề → đã
phát hành → hoàn tác` và quay lại phát hành lần nữa để thử hai ca hết cửa lùi.

**Năm thứ đo được:**

1. **A3 cho 3/3 câu.** Giáo viên xin ba câu, nhận ba câu: `draft_items` là `ready:1, ready:1,
   ready:1` — không dòng `retry` nào, không lần bắn lại nào. Và cái log **nói ra được**:
   `be.drafting queued 3 question(s) for draft …`, `be.teacher_tools teacher GV-001 runs
   start_drafting`. Trước đợt này những dòng ấy đi vào hư không, nên lần soạn hụt đầu tiên
   không để lại dấu vết nào. `last_fault` đọc được bằng SQL (rỗng, vì không câu nào hỏng).

2. **Thẻ luôn đúng MỘT, đổi chữ theo nấc.** `Đã tạo đề "tên"` → `Đã duyệt đề "tên"` → `Đã
   phát hành` → (hoàn tác) `Đã tạo đề "tên"`. Nấc đầu chở **hai** việc (`create_draft` và
   `start_drafting`) mà vẫn một thẻ. `Đã phát hành` **không** chở tên lớp, và nút `Phát hành
   thêm lớp` không còn tồn tại trên màn hình.

3. **Một khung giờ, đo ở hai chỗ.** Chọn thêm lớp thứ hai **không** làm mọc thêm ô thời gian
   nào (vẫn đúng 5 ô), và hai dòng `publications` có **cùng** `opens_at`.

4. **Hoàn tác: hoặc tất cả hoặc không gì cả.** Một cú bấm → cả 12A lẫn 12B đều có
   `recalled_at`, và `state` xuống thẳng `has_questions`. Khi một lớp đã qua giờ mở: BE trả
   409 và **không** thu hồi lớp nào — `recalled_at` của cả hai vẫn rỗng, `state` vẫn
   `published`.

5. **Đường lùi nói ra được, ở cả hai nửa.** Mở lại màn 7 khi đã qua giờ mở: nút `Hoàn tác`
   **hiện nhưng khoá**, kèm `role="status"` chở câu của BE gọi **tên lớp**. Còn khi biểu mẫu
   trong tay giáo viên là bản cũ — đồng hồ vừa qua giữa lúc họ đang nhìn — cú bấm nhận 409 và
   câu ấy hiện ra với `role="alert"` **ngay ở màn cài đặt phát hành**, đúng chỗ `Panel` từng
   nuốt mất nó. Hai câu **giống nhau từng chữ**, vì chúng dùng chung một hàm.

**Một thứ của model, không phải của code:** ở A2, giáo viên viết *"Tạo cho tôi một đề toán lớp
12 gồm 3 câu về hàm số bậc hai"* — đã có cả khối lớp lẫn phạm vi — mà Kriky vẫn hỏi lại
*"Bạn vui lòng cho mình biết khối lớp và phạm vi kiến thức nào…"*. Hỏi lại khi đã đủ dữ kiện
tốn của giáo viên một lượt, và dạy họ rằng câu hỏi lại là thủ tục chứ không phải nhu cầu thật.
Đây là việc của prompt pha 1, chưa sửa.

### Lần chạy 2026-10-06, lượt ba — bảy lỗi giao diện, đo bằng DOM, **không** lượt model nào

Lượt này không nhờ Kriky một việc gì: cả bảy chỗ hỏng đo được bằng `getBoundingClientRect`,
`localStorage` và dữ liệu đã có trong database. Database **giữ nguyên**, vì chính nó là bằng
chứng — câu 3 của đề `d3f40a77` còn nguyên hai phương án trùng.

**Trước khi đo, một thứ phải chữa trước:** trình duyệt tự động không vào được dev server.
`ERR_CONNECTION_REFUSED` ở `localhost:5173` trong khi `curl` từ shell trả 200 ở đúng URL ấy —
một triệu chứng đọc ra như server đang chết, và nó ngốn bốn lượt thử. Nguyên nhân: Vite để
`server.host` mặc định, chuỗi `localhost` phân giải ra `[::1]` nên server **chỉ** bind IPv6,
còn trình duyệt phân giải `localhost` ra `127.0.0.1` trước. `vite.config.ts` nay ghim
`host: "127.0.0.1"`.

1. **Màn 6.5 biến mất, đo đúng đường người dùng báo.** Bấm thẻ `Đã phát hành` trong đoạn chat:
   `.panel` có đúng ba con — `panel-head`, `panel-questions`, `publish-settings` — và **không**
   `panel-foot`. Một cú bấm tới biểu mẫu, không còn cú bấm `Phát hành đề` nào ở giữa. Link cũ
   mang hậu tố `/phat-hanh` vẫn mở, và mở ra **cùng** màn ấy.

2. **Tấm trượt phát hành, trên đề đã phát hành `d3f40a77`.** Bung: vùng câu hỏi **94/911**
   (10,3%), `scrollHeight` 569 so `clientHeight` 94 — phải cuộn. Thu: **720,5/911** (79,1%),
   `scrollHeight` = `clientHeight` = **721** — không còn phải cuộn. Thanh đầu 51,5. Tổng ba
   khối `139 + 720,5 + 51,5` = **911** khít đúng, nên không khối nào che khối nào: đó là
   phương án A đo được, không phải A nói ra.

3. **Icon rail thôi lệch.** Cả bốn đích đến: svg `122→134` tâm **128**, chữ title tâm **128** —
   lệch **0,00**, và svg lấp đúng cái hộp 12px. Trước: tâm svg 130 so title 128,05, lệch 2px.

4. **Hai ngăn rail thu được.** Ba nấc đo được: mở cả hai **358 / 225** (thanh kéo có mặt), thu
   `TÀI LIỆU` **568 / 27**, thu cả hai **27 / 27**. Ngăn thu cao đúng 27 = `pane-head`. Thanh
   kéo biến mất ở cả hai nấc thu. Nút tải lên **không** nằm trong nút thu. Nấc sống qua F5,
   hai khoá riêng (`...pane-open.history` = `0`, `...documents` = `1`).

   **Và phép đo bắt được một chỗ hở mà không test nào thấy:** thu `ĐOẠN CHAT` để ngăn tài liệu
   đứng yên ở 225 và bỏ lại ~368px trắng dưới nó, trong khi chiều ngược lại kín chỗ. Lỗi chỉ
   lộ ra ở **một** trong hai chiều, và Figma vẽ đúng chiều kia. Sau khi sửa: 27/568 và 568/27,
   tổng **595** = đúng chiều cao `.lists`.

5. **Dấu `$` hết lọt ra màn.** Vùng câu hỏi của đề `d3f40a77`: **0** dấu `$`, trước đợt này
   đếm được 8. Thẻ câu 3 có 5 khối KaTeX, và cả bốn phương án `$ (1, 8) $` dạng ấy đều dựng
   thành toán.

6. **Luật hai phương án trùng sống thật trong BE đang chạy.** Một vòng đầy đủ trên đề
   `f348b4ba`: hoàn tác → `has_questions` → `PATCH` một câu với hai phương án chỉ khác nhau số
   khoảng trắng → **422 `two options say the same thing`** → gửi lại nguyên bản → 200 → duyệt
   lại → `approved`. Không để lại dấu nào.

7. **Đổi tên và xoá sống lại.** Bắn đúng chuỗi `pointerdown → pointerup → click` như ngón tay
   thật: menu `⋯` **sống qua `pointerdown`**, `input.rename` hiện ra mang sẵn tên cũ, gõ tên
   mới rồi Enter thì `PATCH /api/teacher/conversations/{id}` đi ra với đúng thân
   `{"title": …}`, hàng rail đổi chữ, ô nhập đóng. Mục `Xoá` mở hộp *"Xoá đoạn chat này?"* với
   `Giữ lại` / `Xoá đoạn chat`; bấm `Giữ lại` và hai đoạn chat còn nguyên. Tên đã trả về như cũ
   qua chính đường ấy.

**Hai cái bẫy của phép đo, ghi lại để không mất lần nữa.**

- **Transition đứng im trong tab không được vẽ.** Mũi nhọn của ngăn đã thu đọc ra
  `matrix(1,0,0,1,0,0)` — ma trận đơn vị — sau 600ms, và `document.getAnimations()` cho thấy
  một transition còn **đang chạy**. Tab tự động không được paint nên transition không tiến. Tắt
  `transition` bằng một `<style>` tạm rồi đo lại: `matrix(0,-1,1,0,0,0)` = `rotate(-90deg)` lúc
  thu, `none` lúc bung. Luật đúng; cái đọc sai là phép đo.
- **React render không đồng bộ.** Bắn `pointerdown` lên nút `⋯` rồi query `.row-menu` **ngay**
  trong cùng một biểu thức thì ra `null`, và nó đọc như menu bị tháo — đúng cái bug vừa sửa.
  Phải `await` một nhịp giữa cú bấm và phép đo.

**Và một con số tôi đã viết sai, Figma sửa theo phép đo chứ không ngược lại.** Tôi ghi tấm trượt
thu cao **53**, lấy từ một bản clone trên frame quyết định vẫn mang density của trang Components
(chữ 14px/21). Bề mặt giáo viên định nghĩa lại `--type-label` thành **13px**, và artboard 7 với 8
đã đè chữ title theo density ấy từ trước — `teacher.css` thậm chí có sẵn một ghi chú cảnh báo
đúng cái bẫy này. Số thật: Figma **52**, trình duyệt **51,5**; chênh 0,5 là Figma làm tròn hộp
chữ 13px/150% thành 20 trong khi CSS tính 19,5.

**Chưa sửa, và vẫn là việc của prompt pha 1:** ở A2 Kriky vẫn hỏi lại khi giáo viên đã cho cả
khối lớp lẫn phạm vi. Lượt này không chạy pha 1 nên không có gì mới về nó.

### Lần chạy 2026-10-06, lượt bốn — cài đặt phát hành nhớ được, và thẻ sửa câu thôi rối

Lượt này cũng **không** nhờ Kriky một việc gì: cả hai đổi đo được bằng `getBoundingClientRect`,
`localStorage` và dữ liệu đã có trong database. Database giữ nguyên.

Dữ liệu dùng để đo, và nó có sẵn đúng ca khó: đề `d3f40a77` đã phát hành cho **cả hai lớp, lệch
giờ** (12A 14:21, 12B 15:26); đề `f348b4ba` đã duyệt mà **chưa** phát hành; đề `668251b5` còn nháp.

1. **Biểu mẫu nhớ cái giáo viên vừa gõ.** Trên `f348b4ba`: gõ sáu tham số, F5, cả sáu trở về
   **từng ký tự một**, chip `12A` vẫn `aria-pressed="true"`, và dòng *"Bản nháp bạn gõ 21:48 ·
   06/10."* hiện ra kèm nút `Bỏ bản nháp`. Bấm nút ấy: sáu ô về trống, chip bỏ chọn, khoá
   `kriky.teacher.publish-draft.f348b4ba…` biến mất khỏi `localStorage`.

2. **Nấc thu/bung cũng nhớ.** Bung 658,5 / câu hỏi 140,5 → thu **51,5** / câu hỏi **747,5**, với
   `scrollHeight` = `clientHeight` = 748. Nấc sống qua F5 (`publish-open…` = `0`). Con số 51,5
   khớp đúng phép đo lượt trước, tức luật thu không bị đợt này làm xê dịch.

3. **Giờ đã đặt đọc lại được, và ô khoá lại.** Trên `d3f40a77`: hai dòng `ĐÃ PHÁT HÀNH` in đúng
   giờ của **từng** lớp, cả hai chip `disabled`, năm ô `disabled`, và **không** nút `Phát hành đề`
   nào — chỉ còn `Cài đặt phát hành` và `Hoàn tác`.

4. **Và phép đo tìm ra một lỗi mà không test nào thấy.** Vì hai lớp lệch giờ nên không có khung
   chung để điền, và năm ô hiện ra vừa khoá vừa **rỗng**: tấm trượt ăn **805,5 trên 911**, vùng câu
   hỏi còn **24 pixel**. Ba trăm pixel để nói đúng một điều — *"có năm cái ô, và bạn không được
   chạm vào"* — trong khi khối ngay trên đã nói đủ. Đây đúng là thứ mà việc *điền giá trị vào ô
   khoá* sinh ra để chống; ca lệch giờ chỉ là ca không điền được. Sửa: không điền được thì không
   dựng. **805,5 → 428.**

5. **Rồi một lỗi thứ hai lộ ra ngay trong lúc kiểm lại con số ấy.** Dòng tên lớp cao **40** trong
   khi một dòng chữ 11px chỉ cần 16,5. Nguyên nhân: tôi đặt tên lớp CSS là `.who`, mà `.teacher
   .who` đã có chủ từ lâu — nó là hàng avatar của một lượt chat, `display: flex; height: 40px`. Tên
   trùng thì selector của tôi không ghi đè được, vì tôi không đặt hai thuộc tính ấy. Đổi thành
   `.lop`: **428 → 381**, vùng câu hỏi **344 → 391**.

   Tổng cho màn này: tấm trượt **805,5 → 381**.

   **Và một chỗ tôi đã đo cẩu thả:** `panel` cao bằng **toàn bộ** cửa sổ, `panel-questions` là
   phần còn lại — nên con số "vùng câu hỏi 24 → 391" chỉ đúng cho một cửa sổ cao 911, và mọi tỉ
   lệ `x/911` ở trên cũng thế. Đo lại ở cửa sổ cao 855: tấm trượt vẫn **381**, vùng câu hỏi
   **335**. Thứ đo được mà không phụ thuộc cửa sổ là chiều cao của **chính tấm trượt**; tôi đã
   trình bày một con số dẫn xuất như thể nó là hằng số.

6. **Thẻ sửa câu hỏi: ba tầng, một lúc một tầng.** Trên `668251b5`, khung `panel-questions` cao
   **694,5**: `ĐỀ BÀI` **214,5**, `PHƯƠNG ÁN` **616,9**, `CÁCH GIẢI` **603,6** — cả ba vừa, tầng
   nặng nhất dư 77,6. Luôn đúng **một** thanh đầu mang `aria-expanded="true"`.

   Và con số của bản phẳng, đo trên chính dữ liệu ấy: phần khung chung 164,5 cộng ba thân
   50 + 452,4 + 439,1 = **1106**, tức tràn **411,5** khỏi khung. Figma cho 774 trên một câu ngắn
   hơn; đề thật thì tệ hơn hẳn.

7. **Nhãn nhìn thấy được.** Trong cả ba tầng: **0** `textarea` nào mang `aria-label` trần. Nhãn
   hiện ra đếm được — `Lỗi của A/C/D` ở tầng phương án, `Tên cách giải 1/2` và `Lời giải 1/2` ở
   tầng cách giải — còn ô đề bài và ô chữ phương án mượn chữ đã hiện sẵn qua `aria-labelledby`.

**Một cái bẫy mới, ghi lại để không mất lần nữa.** `location.reload()` rồi `await` một `setTimeout`
trong **cùng một** lượt `javascript_tool` thì lượt ấy chết giữa chừng: *"Inspected target navigated
or closed"*. Phải tách làm hai lượt — một lượt bắn `reload`, một lượt đo sau đó. Giá trị cần mang
qua thì gửi bằng `sessionStorage`.

8. **Icon rail: ba phép đo tâm nói cân, mắt nói xệ — và mắt đúng.** Người dùng báo icon vẫn hơi
   thấp so với chữ, sau khi lượt trước đã đo lệch **0,00**. Đo lại ba cách, cả ba vẫn nói cân: tâm
   icon 128, tâm hộp dòng 128, tâm thân chữ hoa 128. Nét trong `viewBox` lệch nhiều nhất 0,25.

   **Lần đầu tôi chẩn sai.** Tôi đo *trọng tâm khối mực* — đổ icon ra canvas rồi cân từng dòng theo
   alpha — và nó cho biểu đồ cột 7,38, ba chấm 6,83, tập giấy 5,95, lưới ô 6,00 trên thang 12. Theo
   đó tôi nâng **hai** hình. Người dùng quay lại: *"bài kiểm tra và ngân hàng đề vẫn còn lệch"* —
   đúng hai hình mà mô hình ấy tuyên là đã cân. Mô hình sai, và nó sai một cách kiểm được.

   **Đại lượng đúng là baseline.** Icon cao **12**, thân chữ hoa cao **10**, nên một icon căn giữa
   hộp dòng thò xuống dưới baseline đúng 1px. Đo mép dưới của mực so với baseline: cột **+1**, tập
   giấy **+1**, lưới ô **+1**, ba chấm **0** — và số 0 ấy chỉ vì hình ba chấm hụt 1px ở đáy. Mô
   hình này giải thích **cả hai** lượt người dùng báo, kể cả lượt mà mô hình cũ không giải thích nổi.

   Sửa: vẽ lại ba chấm cho chạm đáy (`cy 9 → 10`), rồi nâng **cả bốn** 1px bằng **một** luật ở mức
   rail — không phải cờ từng icon. Sau khi nâng, mép mực so với baseline: **0,00** cho cả bốn.

**Và một bài học về phép đo, không phải về code.** Lượt ba tôi đo *"lệch 0,00"* rồi coi việc này là
xong. Con số ấy **đúng** — nó chỉ không phải con số trả lời câu hỏi. Hộp bao nói hình nằm đâu;
khối mực nói mắt thấy nó nặng ở đâu. Với hình đối xứng trên dưới thì hai thứ trùng nhau, nên phép
đo cũ đi lọt qua ba icon và chỉ sai ở hai cái bất đối xứng. *"Đo được"* chưa đủ — còn phải đo đúng
cái đại lượng mà người dùng đang nhìn.

### Lượt bốn, phần bù — đường mà lượt đầu tôi tick mà không đi

Review độc lập bắt được: tôi tick *"phát hành rồi xem cái khoá có tới không"* mà thật ra chỉ mở
một đề **đã** phát hành sẵn. Hai đường khác nhau, và đúng đường tôi bỏ qua là đường hỏng —
`form` không được đọc lại sau khi phát hành, nên cái khoá chỉ tới sau một lần F5.

Đo lại cho đúng, trên `f348b4ba` (đã duyệt, chưa phát hành), **không tải lại trang**:

- Phát hành cho **12A** ⇒ chip 12A `disabled` ngay, dòng `12A · 3 học sinh · 22:54 07/10 →
  00:54 08/10 · thu hồi được tới 22:54` hiện ra; 12B còn bấm được, CTA còn đó. Đúng cách 1.
- Phát hành nốt **12B** ⇒ cả **năm ô `disabled`** và mang đúng giá trị đã phát hành, cả hai chip
  khoá, **CTA biến mất**, hai dòng `ĐÃ PHÁT HÀNH`.
- Thu hồi cả hai lớp để trả đề về `approved`; `publications` còn 0.

**Và phép đo lộ một chuyện chưa chữa:** ở ca này (hai lớp **chung** khung giờ) năm ô vẫn được
dựng — chúng mang thông tin thật nên chúng đáng chỗ — và tấm trượt cao **779**, vùng câu hỏi còn
**24**. Đúng con số đã chữa cho ca lệch giờ, nay quay lại ở ca chung giờ. Nấc thu vẫn là đường
thoát, và nó nhớ; nhưng mặc định khi đã khoá có lẽ nên là **thu**, vì một biểu mẫu không bấm được
thì là một biên bản, không phải chỗ làm việc. Chưa làm — cần người dùng chốt.

**Chưa sửa, và vẫn là việc của prompt pha 1:** ở A2 Kriky vẫn hỏi lại khi giáo viên đã cho cả khối
lớp lẫn phạm vi. Lượt này không chạy pha 1 nên không có gì mới về nó.
