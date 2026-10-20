# Lượt năm của kịch bản giáo viên — 07/10/2026

Dời nguyên văn từ `docs/testing/kich-ban-thu-tay-giao-vien.md` ngày 20/10/2026, khi kịch bản được viết lại thành kịch bản đầu-cuối. Các mục chặng A–H nhắc tới là của kịch bản cũ (xem git log).

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
