# Kịch bản thử tay — bề mặt giáo viên, từ câu chat đầu tới lúc phát hành

Đây là một **bản thử tay**: một người ngồi gõ từng câu và soi từng dòng Kriky trả về. Không công
cụ, không tự động, không đo phủ nhánh. Thứ nó mua được mà không bộ test nào mua nổi: **một người
đọc và thấy câu đó vô lý**.

Chạy hết một lượt mất khoảng 25–30 phút và tốn **9 lượt gọi model**. Mọi mục đánh dấu `[0]` không
tốn lượt gọi nào — chúng chạy qua nút bấm, không qua chat.

---

## Trước khi bắt đầu

1. `.\dev.ps1 db-reset` — để mọi lần chạy bắt đầu từ cùng một chỗ. Có dữ liệu seed: lớp **12A**
   với 3 học sinh, một đề đã phát hành.
2. Mở ba cửa sổ: `.\dev.ps1 be`, `.\dev.ps1 agent`, `.\dev.ps1 fe`.
3. Model phải là **`gpt-4o-mini`**.
4. Mở `http://localhost:5173/#/teacher`.
5. **Thêm một lớp thứ hai.** Mục 3 cần ít nhất hai lớp khớp chữ "12" thì đường hỏi-lại-có-nút mới
   xảy ra. Chưa có màn hình tạo lớp, nên thêm bằng tay vào database một lớp tên **12B**.

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
| 6 | **Toán viết bằng ký hiệu Unicode**: `y = x³ − 3x`, `≥`, `→` | Thấy `\frac`, `$...$`, `x^3` |
| 7 | **Không định danh máy nào lọt ra màn hình** | Thấy một chuỗi UUID, hay tên tool như `start_drafting` |

Và **một luật cho khối bước**: `bước k/n` — `n` phải cố định từ lúc khối hiện ra. Nếu `n` nhảy
giữa chừng thì nó đang được đếm từ số bước đã chạy, chứ không đến từ plan.

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

**Sai nếu:**
- có một bước đánh dấu `✕` — hỏi lại **không phải** một bước hỏng;
- có thẻ `Đã tạo đề` — tức một đề rỗng vừa được sinh ra cho một câu còn thiếu dữ kiện;
- nó hỏi từng mục một qua nhiều lượt (phải hỏi gộp một lần).

**Kiểm thêm:** vào panel bất kỳ / rail — **không** được có đề nháp mới nào.

### A3. Trả lời câu hỏi lại `[1 lượt]`

**Gõ:** `Toán 12, chương tích phân, 3 câu`

**Phải thấy:** khối bước chạy với `bước 1/2` rồi `bước 2/2`; dòng dưới bước soạn đếm tăng dần rồi
dừng ở `— đã soạn 3/3 câu`; một câu kể; và **một thẻ** `Đã thêm 3 câu vào đề`. Thẻ **không có nút
nào** — bấm vào chính nó là mở panel đề.

**Sai nếu:**
- **không thẻ nào** — đây là lỗi vừa sửa, nó quay lại thì đề không còn cửa nào mở ra;
- thẻ ghi `Đã tạo đề — Chưa có câu hỏi nào`: thẻ của bước trước, trong khi bước sau đã thay nó;
- hai thẻ;
- thẻ ghi `Đã thêm 0 câu`;
- khối bước nói `bước 1/8` — `8` là mức trần, không phải số bước của plan.

---

## Chặng B — những lời từ chối phải nói ra thành tiếng

### B1. Số câu quá lớn `[1 lượt]`

**Gõ:** `tạo đề 500 câu Toán 12 về đạo hàm`

**Phải thấy:** một bước đánh `✕` với lý do nói đúng mức trần (**50**), và Kriky thuật lại lý do
ấy. Không đề nào được tạo.

**Sai nếu:** nó âm thầm cắt xuống 50 và báo thành công — một lời từ chối bị nuốt là thứ tệ hơn
một lời từ chối.

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

**Phải thấy:** thẻ `Đã thêm 3 câu vào đề` của mục A3 vẫn còn, con số vẫn là 3, và bấm vào thẻ
vẫn mở được panel. Dòng dưới bước soạn vẫn là `— đã soạn 3/3 câu`.

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

**Phải thấy:** thẻ `Đã bỏ duyệt đề …`, đề sửa lại được, và **cài đặt phát hành giữ nguyên**.

### D5. Sửa chữ một câu

Bấm **Sửa** trên một thẻ câu hỏi.

**Phải thấy:** mỗi phương án nhiễu có **hai** ô — chữ phương án và nhãn lỗi; đáp án đúng chỉ có một
ô và **không có nút Xoá**; mỗi lời giải có ô tên và ô thân. Hai nút `+ Thêm phương án` và
`+ Thêm cách giải`.

Thêm một phương án, gõ cả chữ lẫn nhãn lỗi, rồi **Lưu**.

**Phải thấy:** thẻ đóng lại, phương án mới hiện trong lưới hai cột.

**Sai nếu:** Lưu trả `Not Found` — BE đang chạy bản cũ không có endpoint sửa câu, khởi động lại nó;
hoặc Lưu bị từ chối vì một công thức LaTeX nằm ngoài cặp `$` — luật ấy đã bỏ, công thức viết sai thì
hiện nguyên văn để bạn sửa tay.

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

### E2. Ba lý do từ chối theo từng lớp

Thử lần lượt, mỗi lần một lỗi:

| Nhập | Phải thấy lý do |
|---|---|
| giờ mở ở **quá khứ** | *giờ mở phải ở tương lai* |
| giờ đóng **trước** giờ mở | *giờ đóng phải sau giờ mở* |
| hạn chữa **trước** giờ nộp cuối pha 1 | *hạn pha 2 phải sau giờ nộp cuối của pha 1* |

**Sai nếu:** cả biểu mẫu trượt vì một lớp sai. ADR-02 cho phép một lớp nhận được và lớp khác
không, nên lỗi phải là **lý do của riêng lớp đó**.

### E3. Hộp xác nhận đọc lại đúng cái sắp xảy ra

Nhập giờ hợp lệ cho **cả hai lớp**, bấm xem trước.

**Phải thấy:** hộp xác nhận in lại đúng những giờ bạn vừa gõ, đúng số học sinh, và ba câu luật.

**Soi kỹ múi giờ.** Gõ `08:45`, hộp phải đọc lại `08:45` — không phải `01:45`. Đây là chỗ đã có
lỗi một lần.

**Sai nếu:** bấm xem trước mà đề đã bị phát hành — xem trước **không được ghi gì**.

### E4. Phát hành thật

**Phải thấy:** thẻ `Đã phát hành cho 12A và 12B`, và thẻ ấy **không** nói *"chưa phát hành"* —
nó là thẻ duy nhất có hậu quả đã xảy ra, nên câu an toàn của nó phải nói về **thu hồi**, không
nói về việc chưa tới tay ai.

### E5. Thu hồi một lớp, trước giờ mở

**Phải thấy:** lớp ấy rời danh sách, đề vẫn ở trạng thái đã phát hành vì **lớp kia còn giữ**.

Thu hồi nốt lớp còn lại → đề quay về **đã duyệt**.

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
| | | |
