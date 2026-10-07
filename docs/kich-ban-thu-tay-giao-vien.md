# Kịch bản thử tay — bề mặt giáo viên, từ câu chat đầu tới lúc phát hành

Đây là một **bản thử tay**: một người ngồi gõ từng câu và soi từng dòng Kriky trả về. Không công
cụ, không tự động, không đo phủ nhánh. Thứ nó mua được mà không bộ test nào mua nổi: **một người
đọc và thấy câu đó vô lý**.

Chạy hết một lượt mất khoảng 25–30 phút và tốn **10 lượt gọi model** — đếm được bằng số mục
mang dấu `[1 lượt]`. (Thêm vài lượt ẩn: mỗi đoạn chat mới tốn một lượt để model đặt tên.) Mọi mục đánh dấu `[0]` không
tốn lượt gọi nào — chúng chạy qua nút bấm, không qua chat.

---

## Trước khi bắt đầu

1. `.\dev.ps1 db-reset` — để mọi lần chạy bắt đầu từ cùng một chỗ. Có dữ liệu seed: lớp **12A**
   với 3 học sinh, một đề đã phát hành.
2. Mở ba cửa sổ: `.\dev.ps1 be`, `.\dev.ps1 agent`, `.\dev.ps1 fe`.
3. Model phải là **`gpt-4o-mini`**.
4. Mở `http://localhost:5173/#/teacher`.
5. **Thêm một lớp thứ hai.** Chặng C cần ít nhất hai lớp khớp chữ "12" thì đường hỏi-lại-có-nút mới
   xảy ra. Chưa có màn hình tạo lớp **và cũng chưa có tool nào tạo lớp** — bốn đích đến trên rail
   còn trơ — nên phải thêm thẳng vào database:

   ```
   docker exec aiafa-postgres psql -U aiafa -d aiafa -c      "insert into classes (id, teacher_id, name) select gen_random_uuid()::text, id, '12B' from teachers limit 1;"
   ```

6. **Mỗi tình huống một đoạn chat.** Đừng dồn cả bản vào một đoạn: một đoạn dài làm mọi lượt sau
   mang theo ngữ cảnh của lượt trước, nên khi một câu trả lời sai thì không biết nó sai vì luật hay
   vì nó đọc nhầm câu cũ. Bấm **Đoạn chat mới** giữa các chặng.

---

## Luật áp cho **mọi** lượt Kriky trả lời

Đây là phần quan trọng nhất của bản này. Mỗi lần Kriky nói, soi đủ bảy dòng dưới đây — chúng
không phụ thuộc bạn đang ở mục nào.

| # | Phải đúng | Sai thì trông thế nào |
|---|---|---|
| 1 | **Một lượt, một avatar.** Kriky nói hai câu (mở đầu và kết) vẫn chỉ một hàng logo trên cùng | Hai hàng logo trong một lượt — cùng một người được giới thiệu hai lần |
| 2 | **Không con số nào không có trong kết quả.** Kriky không thấy đề, không thấy câu hỏi nào | *"mình đã soạn xong 10 câu rất hay"*, *"đề này khó vừa phải"* — nhận xét về thứ nó không đọc |
| 3 | **Con số trên thẻ và trong câu nói phải khớp nhau** | Câu nói *"đã soạn xong"* mà thẻ ghi `Dừng ở 2/10 câu` |
| 4 | **Không hứa một việc nó không làm được.** Nó không có tool bỏ duyệt, không có tool phát hành | *"để mình bỏ duyệt giúp bạn nhé"* |
| 5 | **Không Markdown.** Không `**đậm**`, không `` `mã` ``, không bảng | Thấy dấu sao hoặc dấu huyền kép nguyên văn trên màn hình |
| 6 | **Toán viết bằng LaTeX trong cặp `$`**, và màn hình **dựng hình** nó | Thấy `$\frac{1}{2}$` nguyên văn trên màn — tức cụm ấy không được dựng hình |
| 7 | **Không định danh máy nào lọt ra màn hình** | Thấy một chuỗi UUID, hay tên tool như `start_drafting` |

Luật 6 **đã bị lật một lần**, nên đọc kỹ: bản cũ của dòng này viết ngược — nó bắt toán phải là ký
hiệu Unicode và coi `$...$` là lỗi. Hợp đồng nay là ngược lại (ADR-26): prompt soạn câu **bắt**
model viết `$y = x^3 - 3x$`, và `MathText` dựng hình phần nằm giữa hai dấu `$`. Thấy dấu đô la trên
màn hình nghĩa là cụm ấy **không dựng được**, không phải model viết sai quy ước.

Và **hai luật cho khối bước**:

- `bước k/n` — `n` phải cố định từ lúc khối hiện ra. `n` nhảy giữa chừng nghĩa là nó đang đếm từ số
  bước đã chạy, chứ không đến từ plan.
- **Đúng một hàng có dải sáng quét**, và nó là hàng đang chạy. Bước xong rồi thì tắt; bước chưa tới
  thì chưa sáng. Cả khối cùng động, hoặc một hàng đã `✓` vẫn sáng, đều là sai — khối này là bằng
  chứng đọc lại được, không phải hiệu ứng chờ.

---

## Chặng A — câu chat đầu tiên

### A1. Nói chuyện không nhờ việc gì `[1 lượt]`

**Gõ:** `chào bạn`

**Phải thấy:** Kriky chào lại. **Không** khối bước, **không** thẻ, **không** nút nào. Rail hiện
một đoạn chat mới, tên do model đặt theo câu vừa gõ.

**Sai nếu:** có một khối bước (nó đi tra cứu cho một lời chào), hoặc đoạn chat không có tên sau
khi lượt xong.

### A2. Nhờ việc nhưng thiếu dữ kiện `[1 lượt]`

**Gõ:** `tạo cho mình một đề`

**Phải thấy:** Kriky **hỏi lại** — thiếu môn, khối, phạm vi, số câu. Câu hỏi là một bong bóng
bình thường, **không** có nút bấm (vì chưa tool nào trả về danh sách để bày ra).

Bốn mục, dù `create_draft` chỉ cần ba: số câu thuộc về `start_drafting`, và một plan soạn đề cần
**cả hai** bước, nên thiếu con số ấy thì plan vẫn chưa dựng được.

**Sai nếu:**
- có một bước đánh dấu `✕` — hỏi lại **không phải** một bước hỏng;
- có thẻ `Đã tạo đề` — tức một đề rỗng vừa được sinh ra cho một câu còn thiếu dữ kiện;
- nó hỏi từng mục một qua nhiều lượt (phải hỏi gộp một lần).

**Kiểm thêm:** không được có đề nháp mới nào. Rail **không** kiểm được chuyện này — bốn đích đến
của nó còn trơ, chưa màn hình nào liệt kê đề nháp. Cách duy nhất là đếm thẳng trong database:
`docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) from assessments;"`

### A3. Trả lời câu hỏi lại `[1 lượt]`

**Gõ:** `Toán 12, chương tích phân, 3 câu`

**Phải thấy:** khối bước chạy với `bước 1/2` rồi `bước 2/2`; dòng dưới bước soạn đếm tăng dần rồi
dừng ở `— đã soạn 3/3 câu`; một câu kể; và **một thẻ** `Đã tạo đề`. Thẻ **không có nút nào** —
bấm vào chính nó là mở panel đề.

Thẻ **không nhắc lại con số**: khối bước ngay trên nó đã nói `đã soạn 3/3 câu`, và thẻ trả lời một
câu khác — *đề này đang ở nấc nào*.

**Sai nếu:**
- **không thẻ nào** — đây là lỗi vừa sửa, nó quay lại thì đề không còn cửa nào mở ra;
- thẻ ghi `Đã tạo đề — Chưa có câu hỏi nào`: thẻ của bước trước, trong khi bước sau đã thay nó;
- hai thẻ;
- thẻ ghi một con số — thẻ nấc này không có con số nào;
- khối bước nói `bước 1/8` — `8` là mức trần, không phải số bước của plan.

---

## Chặng B — những lời từ chối phải nói ra thành tiếng

### B1. Số câu quá lớn `[1 lượt]`

**Gõ:** `tạo đề 500 câu Toán 12 về đạo hàm`

**Phải thấy:** bước **1** (`Tạo đề trống`) đánh `✓`, bước **2** (`Soạn câu hỏi`) đánh `✕` với lý do
nói đúng mức trần (**số câu phải từ 1 đến 50**), plan dừng ở đó, và Kriky thuật lại lý do ấy.

**Đề trống *có* được tạo, và đó là chủ ý.** Từ 06/10/2026 mức trần ở `start_drafting` chứ không ở
`create_draft`: một đề trống không có số câu nào để canh. Nên một đề nháp rỗng nằm lại trong
database, còn giáo viên nhận một lời từ chối đúng chỗ — ở bước xin năm trăm câu, không ở bước mở
một tờ giấy trắng. Đếm được: `docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select state,
count(*) from assessments group by state;"` — có thêm một dòng `empty`.

**Sai nếu:**
- nó âm thầm cắt xuống 50 và báo thành công — một lời từ chối bị nuốt là thứ tệ hơn một lời từ chối;
- **năm trăm job đi vào queue** — lời từ chối phải tới **trước** cú `fire`, không sau;
- bước 1 cũng đánh `✕` — nghĩa là mức trần còn sót lại ở `create_draft`.

**Hai thứ đã gặp ngày 06/10/2026, chuẩn bị tinh thần:**

- **Lượt đầu thường không chạm trần.** Model hỏi lại thay vì gọi tool, kể cả khi câu gõ đã đủ môn,
  khối và phạm vi — nó hỏi lại đúng hai thứ vừa được cho. Phải ép thêm một lượt (*"Tạo đề ngay,
  đừng hỏi lại nữa"*) mới tới được mức trần. Đây là lý do mục này **không** tính là một lượt.
- **Câu Kriky nói không thuật lại lý do.** Nó nói *"một mục trong yêu cầu chưa dùng được"* — con số
  50 chỉ nằm ở dòng bước, không nằm trong lời kể. Thông tin có trên màn hình nhưng không ở chỗ
  người ta đọc trước.

### B2. Soạn thêm khi đề đang soạn dở `[1 lượt]`

Gõ ngay sau khi vừa bắt đầu một vòng soạn khác, **trong lúc nó còn chạy**.

**Gõ:** `soạn thêm câu cho đề vừa rồi`

**Phải thấy:** từ chối với lý do *đề này đang soạn dở; chờ xong rồi hãy soạn thêm*.

**Sai nếu:** nó bắn thêm một vòng soạn nữa — hai vòng cùng ghi vào một đề.

### B3. Soạn thêm vào đề **đã duyệt** `[1 lượt]`

Làm sau khi đã duyệt ở mục D3.

**Gõ:** `thêm 2 câu nữa vào đề vừa duyệt`

**Phải thấy:** từ chối, lý do nói nội dung đã khoá và việc bỏ duyệt làm ở panel bên phải.

**Sai nếu:** Kriky nói *"để mình bỏ duyệt rồi soạn thêm nhé"*. Nó **không có** tool bỏ duyệt, nên
câu đó là một lời hứa không ai giữ được. Đây là chỗ luật số 4 ở bảng trên bị vi phạm dễ nhất.

---

## Chặng C — hỏi lại **có nút**, và đọc lại

### C1. Câu hỏi lại có phương án `[1 lượt]`

**Gõ:** `lớp 12 của mình thế nào`

**Phải thấy:** một thẻ hỏi lại với **hai nút**: `12A (3 học sinh)` và `12B (… học sinh)`.

**Soi kỹ con số học sinh.** Nó do BE đếm từ database, không do model viết. Nếu bạn thấy một lớp
không có thật, hoặc một con số sai, đó là lỗi nặng nhất trong cả bản này.

**Sai nếu:** câu hỏi hiện **hai lần** — một lần làm bong bóng, một lần làm tiêu đề thẻ.

### C2. F5 ngay tại đây `[0]`

**Phải thấy:** các nút **vẫn còn**. Câu hỏi vẫn chỉ hiện một lần.

**Sai nếu:** nút biến mất và câu hỏi tụt xuống thành một bong bóng thường — đó là hành vi **cũ**,
trước đợt vừa rồi.

### C3. Bấm một nút `[1 lượt]`

**Phải thấy:** đúng chuỗi trên nút được gửi đi làm câu của bạn, và Kriky trả lời về đúng lớp đó.

### C4. F5 sau một lượt đã xong `[0]`

**Phải thấy:** thẻ `Đã tạo đề` của mục A3 vẫn còn, và bấm vào thẻ vẫn mở được panel. Dòng dưới
bước soạn vẫn là `— đã soạn 3/3 câu` — **con số sống ở khối bước**, không ở thẻ.

**Sai nếu:** dòng ấy đổi thành `— 3 câu bắt đầu soạn` — tức một lần tải lại làm việc đã xong quay
về lúc mới bắt đầu.

### C5. Đoạn chat mới, rồi quay lại `[0]`

Bấm **Đoạn chat mới** → màn hình trắng. Bấm lại đoạn cũ trên rail.

**Phải thấy:** đoạn cũ hiện lại đầy đủ.

**Sai nếu:** màn trắng — màn hình tưởng đoạn ấy vẫn đang hiện.

---

## Chặng D — panel đề và ba cổng của ADR-05 `[0]`

### D1. Mở panel từ thẻ

Bấm vào **chính cái thẻ** (không phải một nút trên nó — thẻ không còn nút nào).

**Phải thấy:** panel bên phải mở đúng đề ấy, ba câu hỏi, mỗi câu có đáp án đúng đánh dấu và hai
cách giải. Địa chỉ trên thanh URL đổi.

**Soi nội dung câu hỏi.** Đây là chỗ duy nhất trong cả bản bạn đọc được thứ model thật sự viết ra.
Câu hỏi có đúng chương tích phân không? Bốn phương án có phương án nào trùng nhau không? Đáp án
đánh dấu có đúng không?

### D2. Chặn duyệt một đề **chưa có câu nào**

Nhờ Kriky mở một đề trống (`mở cho mình một đề trống Toán 11 chương lượng giác`) rồi vào panel của
nó và bấm **Duyệt đề**. `[1 lượt]`

**Phải thấy:** từ chối, câu nói *đề chưa có câu hỏi nào nên không duyệt được*.

### D3. Duyệt đề đủ câu

Quay lại đề 3 câu, bấm **Duyệt đề**.

**Phải thấy:** màn hình sang **thẳng** cài đặt phát hành (màn 7), ở đó có `Hoàn tác` trên
`Phát hành đề`. Và một **biên bản** xuất hiện trong dòng chat — thẻ `Đã duyệt đề …`, một dòng, chip
*Chưa phát hành cho học sinh* ở mép phải, **không nút nào**.

**Sai nếu:** màn hình dừng lại ở panel với hai nút `Hoàn tác` + `Phát hành đề` — đó là chặng 6.5 đã
bỏ; hoặc lượt duyệt mọc thêm một dòng trong khối bước, vì đó là việc bạn làm chứ không phải việc
model làm.

**Soi kỹ:** biên bản ấy phải rơi vào **đoạn chat đã sinh ra đề**, không phải đoạn mới nhất. Nếu
bạn đang đứng ở một đoạn khác lúc bấm Duyệt, hãy quay lại đoạn gốc và kiểm.

### D4. Bỏ duyệt

Bấm **Hoàn tác** ở màn cài đặt phát hành.

**Phải thấy:** thẻ quay về `Đã tạo đề`, đề sửa lại được, và **cài đặt phát hành giữ nguyên**.

**Một đợt cho đúng MỘT thẻ.** Thẻ là *trạng thái của đề*, ba nấc — `Đã tạo đề` → `Đã duyệt đề` →
`Đã phát hành` — và bỏ duyệt đưa nó **về nấc một**. Bấm duyệt rồi hoàn tác năm lần vẫn phải là một
thẻ.

**Sai nếu:** mọc thêm một thẻ `Đã bỏ duyệt đề` bên cạnh thẻ cũ. Đó là hành vi của một bản trước, và
nó cho ra một chồng thẻ nói luân phiên hai câu. Biên bản **không** mất vì thế: nó sống trong
`teacher_turns`, và thẻ chỉ là ô cửa nhìn vào trạng thái.

### D5. Sửa chữ một câu

Bấm **Sửa** trên một thẻ câu hỏi.

**Phải thấy:** mỗi phương án có một **nút chọn tròn** ở đầu hàng, và nút của đáp án đúng đang được
chọn. Mỗi phương án nhiễu có **hai** ô — chữ phương án và nhãn lỗi; đáp án đúng chỉ có một ô và
**không có nút Xoá**; mỗi lời giải có ô tên và ô thân. Hai nút `+ Thêm phương án` và
`+ Thêm cách giải`.

**Đổi đáp án đúng.** Bấm nút tròn của một phương án khác.

**Phải thấy:** dấu đúng chuyển sang phương án ấy, ô nhãn lỗi của nó **biến mất**, và một ô nhãn lỗi
**trống** mọc ra ở phương án vừa thôi đúng. Nút `Lưu` **khoá lại**, kèm một dòng tiếng Việt:
*Phương án X chưa có nhãn lỗi. ADR-18 bắt mọi phương án nhiễu phải có.*

**Sai nếu:** bấm `Lưu` được ngay rồi nhận một câu từ chối **tiếng Anh** dạng
`distractors ['A'] carry no error label: …` — đó là lời của BE, và nó không dành cho giáo viên đọc.
Hoặc: nhãn lỗi cũ của phương án vừa thành đúng **bị xoá mất** — bấm nhầm rồi bấm lại là mất chữ đã
gõ tay, không có đường hoàn lại.

Gõ nhãn lỗi cho phương án vừa thôi đúng rồi `Lưu`: lưu được, và đáp án đúng đã chuyển.

Thêm một phương án, gõ cả chữ lẫn nhãn lỗi, rồi **Lưu**.

**Phải thấy:** thẻ đóng lại, phương án mới hiện trong lưới hai cột.

**Sai nếu:** Lưu trả `Not Found` — BE đang chạy bản cũ không có endpoint sửa câu, khởi động lại nó;
hoặc Lưu bị từ chối vì một công thức LaTeX nằm ngoài cặp `$` — luật ấy đã bỏ, công thức viết sai thì
hiện nguyên văn để bạn sửa tay.

#### D5b. Ký tự hỏng, nếu câu đó có

**Mục này chỉ chạy được trên dữ liệu CŨ.** Sau một lần `db-reset`, đề seed không có LaTeX và đề
vừa soạn đã đi qua bộ khôi phục của ADR-26, nên thường **không ô nào** có dòng đỏ — và đó là kết
quả đúng, không phải một lần thử trượt. Bỏ qua mục này nếu không tìm thấy ô nào dính.

Một số câu soạn trước ngày 06/10/2026 mang ký tự điều khiển thay cho dấu gạch chéo của LaTeX —
`0x0C` thay `\f` của `\frac`, `0x09` thay `\t` của `\times`. Chúng **vô hình** trong ô nhập, nên
dưới mỗi ô dính sẽ có một dòng đỏ: *"N ký tự hỏng, không nhìn thấy được trong ô:"* kèm bản in lại
với `␌ ␉ ␈ ␡` ở đúng chỗ.

**Phải thấy:** dòng ấy chỉ hiện ở ô thật sự có ký tự hỏng. Ô lời giải nhiều dòng **không** được
báo chỉ vì nó xuống dòng. Và chữ trong ô nhập **không** đổi — ký hiệu chỉ ở dòng cảnh báo, vì nếu
nó vào ô thì nút Lưu sẽ ghi ký hiệu xuống database.

Sửa tay theo dòng cảnh báo rồi **Lưu**: dòng đỏ biến mất và công thức dựng hình được.

**Sai nếu:** một đề **vừa soạn mới** cũng có dòng đỏ ở nhiều ô. Câu mới phải sạch — AGENT dựng lại
dấu gạch chéo trước khi lưu (ADR-26). Một hai chỗ sót là chuyện thường: hoặc từ điển lệnh thiếu một
lệnh, hoặc model viết ra một lệnh không có thật như `\bigint`.

### D6. Lời giải mở thành hộp thoại

Bấm **Lời giải · n cách**.

**Phải thấy:** một hộp thoại rộng, các bước của lời giải **xuống dòng đúng chỗ** (không dính thành
một dải chữ), và ánh xạ mỗi phương án nhiễu gắn một lỗi. Đóng được bằng `Esc`, bằng nút `Đóng`, và
bằng cách bấm ra nền.

Duyệt lại trước khi sang chặng E.

---

## Chặng E — phát hành và thu hồi `[0]`

### E1. Biểu mẫu không gợi sẵn giờ nào

**Phải thấy:** năm ô thời gian **trống**. Đây là cố ý: một giờ gợi sẵn là một giờ sẽ được bấm qua
mà không ai đọc.

### E2. Ba lý do từ chối, nói **trước** cú bấm

Thử lần lượt, mỗi lần một lỗi. Câu từ chối phải hiện **ngay khi gõ xong**, ngay dưới hai câu luật,
và nút `Phát hành đề` **khoá lại** — không phải đợi bấm rồi mới biết:

| Nhập | Phải thấy lý do |
|---|---|
| giờ mở ở **quá khứ** | *giờ mở phải ở tương lai* |
| giờ đóng **trước** giờ mở | *giờ đóng phải sau giờ mở* |
| hạn chữa **trước** giờ nộp cuối pha 1 | *hạn pha 2 phải sau giờ nộp cuối của pha 1* |

Mốc của dòng thứ ba là **giờ nộp cuối** = giờ đóng + phút làm bài, không phải giờ đóng. Thử một hạn
nằm **giữa** hai mốc ấy: nó phải bị chặn.

**Soi kỹ hai câu luật ngay trên.** Khi cửa sổ vô lý, chúng vẫn in ra một câu đọc xuôi tai
(*"Vào tham gia tới hết 08:00 - có thể nộp lúc 08:15"*) — đó là lý do lời từ chối phải đứng **cạnh**
chúng chứ không đợi tới sau cú bấm.

**Sai nếu:** nút vẫn sáng và chỉ bị chặn sau khi bấm; hoặc câu từ chối khác chữ với câu BE trả về.

**Và với nhiều lớp:** cả biểu mẫu **không** được trượt vì một lớp sai. ADR-02 cho phép một lớp nhận
được và lớp khác không, nên lỗi phải là **lý do của riêng lớp đó** trong bảng kết quả.

### E3. Hộp xác nhận đọc lại đúng cái sắp xảy ra

Nhập giờ hợp lệ cho **cả hai lớp**, bấm xem trước.

**Phải thấy:** hộp xác nhận in lại đúng những giờ bạn vừa gõ, đúng số học sinh, và ba câu luật.

**Soi kỹ múi giờ.** Gõ `08:45`, hộp phải đọc lại `08:45` — không phải `01:45`. Đây là chỗ đã có
lỗi một lần.

**Và hộp chỉ kể MỘT câu chuyện.** Câu mở đầu, dòng `Thu hồi` và câu luật của BE phải nói cùng
một mốc. Đo được ngày 06/10/2026: câu mở đầu hứa thu hồi *"cho tới giờ mở của **từng lớp**"*
trong khi ngay dưới nó dòng luật nói *"cho tới hết giờ mở"* và dòng `Thu hồi` in đúng **một**
giờ — ba chỗ, hai câu chuyện. Một lần phát hành có một khung giờ (ADR-02, sửa đổi cùng ngày),
nên *"từng lớp"* không còn thứ gì để chỉ tới. Đã sửa, và `teacher.test.tsx` khẳng định hộp
không chứa chuỗi `từng lớp`.

**Sai nếu:** bấm xem trước mà đề đã bị phát hành — xem trước **không được ghi gì**; hoặc hộp
nói hai mốc thu hồi khác nhau.

### E4. Phát hành thật

**Phải thấy:** thẻ `Đã phát hành` — **không** chở tên lớp. Danh sách lớp thuộc về hộp xác nhận
và bảng kết quả, không thuộc một dòng tiêu đề; một đầu đề đổi chữ theo dữ liệu là một trạng
thái thứ tư trá hình. Và thẻ ấy **không** nói *"chưa phát hành"*: nó là thẻ duy nhất có hậu
quả đã xảy ra, nên câu an toàn của nó nói về **thu hồi**, không nói về việc chưa tới tay ai.

**Đếm thẻ: đúng một.** Cả chặng D và E chỉ được để lại **một** thẻ cho đề này, và nó đổi chữ
theo nấc — `Đã tạo đề` → `Đã duyệt đề` → `Đã phát hành`. Hai thẻ chồng nhau là lỗi.

**Sai nếu:** đầu đề là `Đã phát hành cho 12A và 12B`; hoặc chân panel mời `Phát hành thêm lớp`
— nút ấy đã bỏ, muốn đổi lớp thì hoàn tác trước.

### E5. Hoàn tác một đề **đã phát hành**, trước giờ mở

Mục này từng ghi **CHƯA LÀM ĐƯỢC**: màn hình hứa việc thu hồi hai lần mà không có nút nào để
làm, và nút `Hoàn tác` thì có nhưng bấm vào trả 409 — câu 409 ấy lại bị `Panel` nuốt, nên cú
bấm không làm gì và **không nói gì**. Từ 06/10/2026 đường lùi là **một** đường.

Bấm **Hoàn tác** ở màn cài đặt phát hành, khi chưa tới giờ mở của lớp nào.

**Phải thấy:** đề về thẳng `đang soạn` — hoàn tác thu hồi **mọi** lớp rồi hạ hai nấc trong một
cú bấm. Nội dung mở ra sửa được. Thẻ quay về `Đã tạo đề`.

**Kiểm bằng SQL**, vì màn hình không vẽ bảng `publications`:

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select state from assessments where id='<id>';"
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select class_id, recalled_at from publications where assessment_id='<id>';"
```

`state` phải là `has_questions`, và **mọi** dòng `publications` phải có `recalled_at`.

**Sai nếu:** chỉ một lớp bị thu hồi — hoặc tất cả hoặc không gì cả; hoặc `state` vẫn là
`published` trong khi các dòng đã thu hồi.

### E5b. Hoàn tác khi **đã qua giờ mở**

Đặt một `opens_at` về quá khứ rồi mở lại màn 7:

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "update publications set opens_at = now() - interval '5 minutes' where assessment_id='<id>';"
```

**Phải thấy:** nút `Hoàn tác` **hiện nhưng khoá**, kèm câu của BE gọi **tên lớp**: *"Đã qua giờ
mở của lớp 12A nên không hoàn tác được nữa…"*. Biểu mẫu nói trước cú bấm, cùng khuôn với cách
nó chặn một cửa sổ thời gian vô lý.

**Sai nếu:** nút biến mất (giáo viên đi tìm một đường lùi không còn tồn tại); hoặc nút bấm được
rồi mới nhận 409; hoặc câu từ chối nói *"một lớp nào đó"* mà không gọi tên lớp.

### E6. Phát hành một đề **chưa duyệt**

Lấy đề trống ở D2, mở biểu mẫu phát hành.

**Phải thấy:** chặn, với câu nói trạng thái hiện tại.

---

## Chặng F — rail `[0]`

| | Làm gì | Phải thấy |
|---|---|---|
| F1 | Rê chuột lên một hàng | `⋯` hiện ra, và **tên không bị đẩy ngang** |
| F2 | `⋯` → Đổi tên → gõ → Enter | Nhãn đổi ngay; F5 vẫn giữ |
| F3 | `⋯` → Đổi tên → xoá trắng → Enter | Tên cũ ở lại (tên rỗng bị từ chối) |
| F4 | `⋯` → Đổi tên → gõ → **Esc** | Tên cũ ở lại |
| F5 | `⋯` ở **hàng cuối** danh sách | Menu hiện **đè lên** ngăn TÀI LIỆU, và mục *Xoá* bấm được |
| F6 | Mở `⋯` hàng A rồi `⋯` hàng B | Chỉ **một** menu mở |
| F7 | Mở `⋯` rồi bấm ra ngoài, hoặc bấm Esc | Menu đóng |
| F8 | `⋯` → Xoá | **Hộp xác nhận** hiện ra trước. Bấm *Giữ lại* thì không có gì xảy ra |
| F9 | Xoá một đoạn **không** đang mở | Nó rời rail; đoạn đang mở không bị động tới |
| F10 | Xoá đoạn **đang mở** | Màn hình về *Đoạn chat mới* |
| F11 | Sau khi xoá, gõ một câu mới `[1 lượt]` | Nó mở một đoạn **khác**, không rơi vào đoạn đã xoá |

**Và một thứ phải kiểm sau khi xoá:** mở lại một đề đã tạo trong đoạn vừa xoá. Đề **vẫn còn** —
xoá đoạn chat không xoá đề.

---

## Chặng G — tài liệu `[0]`

| | Làm gì | Phải thấy |
|---|---|---|
| G1 | Icon tải lên cạnh nhãn `TÀI LIỆU` → chọn một PDF nhỏ | Chip lên rail với **kích thước**, không phải số trang |
| G2 | Dải dưới ô nhập | Đúng một dòng `Đã tải lên: {tên tệp}`. **Không** nút nào trong dải: tải lên chỉ có một cửa |
| G3 | Thử một file `.png` | Bị từ chối |
| G4 | Thử một file **trên 10 MB** | Bị từ chối, và câu từ chối **nói ra con số** 10 MB |

**Sai nếu:** dải dưới ô nhập nói *"phạm vi"* hay gợi ý rằng tài liệu sẽ giới hạn đề. Nội dung tài
liệu **chưa** đi vào việc soạn đề, và màn hình không được hứa ngược lại.

---

## Hai thứ đã biết là sai — gặp thì không phải phát hiện mới

1. **Đóng tab giữa lúc Kriky đang làm.** Lượt bị cắt ngay chỗ nó đang đợi: các bước đã ghi còn
   đó, nhưng **không có câu kết**, và nếu là lượt đầu thì đoạn chat **chưa có tên**. Đây là nợ số
   1 của ADR-25.
2. **Hai tab cùng chạy một plan trong một đoạn chat.** Không có khoá nào. Hai dãy bước sẽ cài răng
   lược trong một đoạn.

Và **một lỗi chưa sửa, đáng để ý nếu gặp**: nếu Kriky trả về một plan **không có bước nào**, màn
hình sẽ vẽ một khối bước rỗng rồi nói *"Mình tra mãi mà chưa ra câu trả lời gọn cho câu này"* —
câu của mức trần 8 bước, trong khi vòng lặp mới đi một bước. Hiếm, nhưng nếu bạn thấy câu ấy sau
đúng **một** bước thì bạn vừa gặp nó.

---

## Ghi lại

Mỗi lần chạy, ghi ba thứ: **ngày**, **câu nào làm hỏng**, và **nguyên văn** câu Kriky trả lời.
Nguyên văn quan trọng hơn mô tả — với một model, *"nó trả lời sai"* không sửa được, còn một câu
chép lại nguyên văn thì sửa được.

| Ngày chạy gần nhất | Ai | Mục hỏng |
|---|---|---|
| 2026-10-06 | Claude | E5 (không có nút), A3 (2/3 câu), B1 (phải ép 2 lượt), đánh số câu nhảy 1→3 |
| 2026-10-06 (lượt hai, sau khi sửa) | Claude | E3 (hộp xác nhận nói *"của từng lớp"*), A2 (hỏi lại thừa) |

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

---

## Lượt năm — 07/10/2026: biên bản thay biểu mẫu, và dải tài liệu thôi dính tay

Không một lượt model nào. Cả hai việc đo bằng DOM và bằng dữ liệu đã có trong database.

### Việc phát hiện ra lỗi: panel giấu ba trong sáu thông số

Người dùng báo *"panel đang không hiển thị giờ phút trong khi đã phát hành"*. Mở đề
`d3f40a77` (đã phát hành cho 12A và 12B) và đọc DOM:

```
ĐÃ PHÁT HÀNH
  12A · 3 học sinh   14:21 · 06/10 → 17:25 · 06/10 · thu hồi được tới 14:21 · 06/10
  12B · 4 học sinh   15:26 · 06/10 → 17:25 · 06/10 · thu hồi được tới 15:26 · 06/10
LỚP  [12A] [12B]
```

Số ô nhập: **0**. Và ba thông số **không xuất hiện ở đâu cả**: phút làm bài (**15**), phút
mỗi câu (**5**), hạn chữa (**14:25 · 07/10**).

Nguyên nhân là hai quyết định của lượt bốn đụng nhau. `.published-to` được viết gọn có chủ
ý, với lý do ghi thẳng trong comment: *"Thứ không suy ra được từ chỗ khác chỉ có: lớp nào,
mấy học sinh, khung giờ nào, và thu hồi được tới lúc nào."* Câu ấy **chỉ đúng khi năm ô còn
dựng**. `silent` bỏ năm ô đi khi các lớp lệch giờ, và tiền đề im lặng thành sai. Docstring
của `silent` còn khẳng định *"khối ĐÃ PHÁT HÀNH ngay trên đã nói đủ cho từng lớp"* — một lời
không ai kiểm, và nó in 3 trên 6.

Ca này **không hiếm**: giờ mở mặc định là *ngay bây giờ*, nên phát hành cho hai lớp ở hai
thời điểm là đủ để lệch.

### Chữa: đã khoá thì không ô nào

Khuyết tật là **cấu trúc**, không phải hiển thị. Năm cái ô chỉ diễn tả được **một** khung
giờ, trong khi `publications` khoá theo `(đề, lớp)` và trả **một khung mỗi lớp**. Nên việc
điền ô khoá chỉ đúng **tình cờ**, đúng lúc các lớp trùng giờ — và chính sự trùng hợp ấy là
thứ `shared` đi dò. Bỏ ô đi thì xoá được cả `shared`, `show` và `silent`.

Mỗi lớp nay một khối **bốn dòng**, đủ sáu thông số, dùng lại đúng từ vựng của biểu mẫu:

```
12A · 3 học sinh
Làm bài 14:21 · 06/10 → 17:25 · 06/10 · 15 phút
Chữa bài tới 14:25 · 07/10 · 5 phút/câu
Thu hồi được tới 14:21 · 06/10
```

**Đo sau khi sửa**, cửa sổ 854: tấm trượt **455**, vùng câu hỏi **260**, **0 ô**.

### Figma ↔ FE, bằng số

| | Figma (density Teacher) | Trình duyệt | Lệch |
|---|---|---|---|
| một dòng chữ | 17 | 16,5 | Figma làm tròn lên |
| `published-row` | 86 | 84 | `4 × 0,5` |
| `published-to` | 201 | 196,5 | `9 × 0,5` |
| tấm trượt | **377** | **377,5** (455 − 65,5 `trouble` − 12 gap) | `0,5` |

Cùng `type/caption` = **11**, cùng `line-height: 150%`, cùng padding, cùng gap. Mọi chênh
lệch còn lại là **Figma làm tròn chiều cao một dòng 16,5 lên 17** — không phải một khác biệt
thiết kế.

Hai việc phải sửa trên Figma mới khớp được: text của `published-row` dùng line-height mặc
định của font (14) thay vì `150%` như CSS, và `gap` của `published-to` là 8 thay vì 6.

**Khối `trouble` (câu `undo_blocked` của BE, 65,5) chưa từng có trên variant Figma** — một
thiếu sót có từ trước, không phải do lượt này. Chưa thêm.

### Dải tài liệu: đo ra lỗi, rồi chữa

`grep` cho bốn chỗ nhắc `scope` trong `Chat.tsx`: khai báo `:112`, ghi `:320` (sau upload),
ghi `:534` (sau khi thả chip), đọc `:490`. **Không chỗ nào xoá.** Và `App.tsx` mount `<Chat>`
ở ba chỗ (`:71`, `:85`, `:98`) **không chỗ nào truyền `key`**, nên React tái dùng đúng một
instance qua mọi chuyển cảnh.

Đo:

| | Trước | Sau |
|---|---|---|
| sau khi thả chip | `PDF Đã tải lên: dai-so-12.pdf` | `PDF dai-so-12.pdf Bỏ` |
| bấm *Đoạn chat mới* (đoạn rỗng **0 lượt**) | **còn nguyên** | **mất** |

Chữa bằng cách bỏ **nghĩa thừa** chứ không thêm lệnh dọn: dải từng chở hai nghĩa — *"vừa tải
lên"* (việc đã xong, thuộc thư viện) và *"đính vào câu đang gõ"* (ý định, thuộc tin nhắn) —
mà hai nghĩa muốn hai tuổi thọ, nên không luật dọn nào đúng cho cả hai. Nghĩa thứ nhất bị bỏ:
rail đã đẩy tệp vừa tải lên **đầu** danh sách, nên câu ấy kể lại một việc màn hình vừa nói.
Còn một nghĩa thì có một tuổi thọ — chết lúc nhấn Gửi, và lúc đổi đoạn chat.

### Còn nợ sau lượt này

- **Mặc định thu khi đã khoá: chưa làm.** Tiền đề cũ là tấm trượt **779** / vùng câu hỏi
  **24px**; nay là **455 / 260**. Con số đã đổi hẳn, nên quyết định phải được hỏi lại.
- **`publications` hỏng + đề đã khoá ⇒ panel không nói giờ nào cả.** Khối `ĐÃ PHÁT HÀNH`
  dựng từ `live`, nên lời gọi hỏng là không có khối nào, và không có gì nói rằng một lời gọi
  vừa hỏng. Test ghi lại sự thật ấy chứ không tán thành nó; lấp nó là thêm chữ ra màn hình.
- **Khối `trouble` chưa có trên variant Figma.**
- **Chưa sửa, và vẫn là việc của prompt pha 1:** ở A2 Kriky vẫn hỏi lại khi giáo viên đã cho
  cả khối lớp lẫn phạm vi. Lượt này không chạy pha 1 nên không có gì mới về nó.

### Phần bù của lượt năm — ba món còn nợ đã trả

**Mặc định thu khi đã khoá.** Xoá mọi nấc đã nhớ rồi mở lại đề `d3f40a77`, cửa sổ 855:

| | Tấm trượt | Vùng câu hỏi | Khoá đã ghi |
|---|---|---|---|
| mặc định (chưa ai bung) | **51,5** | **664,5** | `null` |
| sau khi tự bung | 455 | 261 | `"1"` |

Thu trả lại **403px** cho vùng câu hỏi. Và mặc định **không ghi gì xuống**: nó là một mặc
định, không phải lựa chọn của ai — ghi nó là bịa ra một quyết định rồi gán cho giáo viên.
Hàng rào `knows()` (mới trong `remember.ts`) giữ cho một tấm trượt giáo viên đã tự bung
không bị đóng sập ở lần mở sau; `readFlag` không phân biệt được *"đã ghi bật"* với
*"chưa ai ghi"*, nên nó không đủ.

**`publications` hỏng nay nói ra.** Trước đó panel im lặng hoàn toàn về một đề đang chạy.
Nay một dòng `role="status"` đứng đúng chỗ khối `ĐÃ PHÁT HÀNH` lẽ ra đứng: khung là chữ của
FE, phần sau là `detail` của BE nguyên văn (`call()` ném nó; BE không nói gì thì là
`Lỗi {status}`).

**Khối `trouble` nay có trên Figma.** Nó thiếu từ trước, nên variant đọc ra ngắn hơn màn
hình thật **77,5px** mà không ai thấy — và chính nó là phần lớn của khoảng lệch 89 đo được
ở đầu lượt. Variant: 366 → **456** (density Teacher), so **455** trên trình duyệt.

**Ba lỗi tôi tự gây ra giữa đường.** `useEffect` mới đặt **sau** một `return` sớm nên React
ném *"Rendered more hooks than during the previous render"* — phải đưa cả `locked` lẫn
effect lên trước mọi `return` sớm. File test có **ba** hàm cùng tên `open()`; tôi sửa hàm
của describe khác rồi kết luận sai rằng phép sửa không ăn.

Và lỗi thứ ba là lỗi đáng kể nhất, vì **chính phép sửa test của tôi đã che nó đi.** Mặc định
thu đọc sai một ca: `publish` gọi `setDone(result.classes)` rồi `setReread(+1)`, `form` được
đọc lại, `locked` bật **giữa tay người đang dùng** — và effect thu tấm trượt ngay lúc ấy, làm
thẻ `Outcome` biến mất cùng khối `ĐÃ PHÁT HÀNH` mà giáo viên vừa tạo ra. Cú bấm quan trọng
nhất của màn hình trả lời bằng cách đóng sập chính nó.

Test `"phát hành xong là KHOÁ ngay"` **vẫn xanh suốt**, vì helper `mount()` tôi vừa sửa gieo
sẵn khoá `"1"`. Tôi gieo nó để các test *nội dung* có trạng thái xác định, và cùng lúc nó đi
vòng qua đúng cái vừa thêm. Hàng rào thứ ba là `done !== null`: thu là quyết định về **cách
một đề đã khoá mở ra**, không phải phản ứng với việc *vừa bị khoá*. Cộng một test đi đúng
đường ấy và **không** gieo khoá; gỡ hàng rào ⇒ đúng nó đỏ.
