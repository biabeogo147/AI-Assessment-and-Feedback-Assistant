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
