# 18. Hỏi về sách

Nhóm: Ra đề bằng chat · Lượt model: ~12 · Chạy sau: 04 (cùng cuốn sách; không dùng đề của 04)

## Cho người xem thấy gì

Giáo viên hỏi Kriky về nội dung cuốn sách đã tải lên. Kriky mở sách, đọc đúng mục, rồi trả lời bằng
lời của nó, kèm bài và trang; sách không có thì nói là không có (plan `ask-the-document`, hậu ký
ADR-27 26/10/2026). Ngay trong đoạn chat ấy, khi giáo viên xin soạn đề, Kriky vẫn đọc phạm vi trước
khi nêu dàn ý: lần đọc để trả lời không thay cho lần đọc để soạn.

## Chuẩn bị

- Đã làm đủ phần *Chuẩn bị* của `huong-dan.md`. Chip `Kết nối tri thức Lớp 6 tập 1 (tr6-28).pdf`
  *sẵn sàng*. AGENT và worker `index` chạy **code của commit đang thử**: hai tiến trình ấy không tự
  nạp lại code, nên khởi động lại nếu đã chạy từ trước.
- Bấm *Đoạn chat mới*, đính chip (kéo chip vào ô nhập, như case 04). Chip chỉ đi cùng câu ấy; đoạn
  chat nhớ chip gần nhất, nên các lượt sau không cần đính lại.

## Lời chat

Lượt 1 (chip đã đính):

```
sách này định nghĩa luỹ thừa với số mũ tự nhiên thế nào vậy?
```

Lượt 2:

```
bài nào trong sách nói về số La Mã, ở trang mấy?
```

Lượt 3:

```
sách có phần phân số không bạn?
```

Lượt 4:

```
oke, soạn cho mình 3 câu về luỹ thừa trong sách nhé
```

Lượt 5 (chỉ khi lượt 4 ra dàn ý): không gõ gì, chỉ ghi lại. Case này không soạn đề.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Lượt 1–3 gọi `list_chapters`, `get_chapter` trước khi đọc | Không trả lời gì. Đạt | Thủ tục `BOOK_QUESTIONS` dặn tìm mục trong mục lục trước |
| Lượt 2–3 không đọc lại mục lục mà dùng mục lục của lượt 1 | Không trả lời gì. Đạt | Kết quả mục lục ở lại trong lịch sử |
| Lượt 3 đọc một bài chỉ để chắc chắn rồi mới nói không có | Chấp nhận được | Thừa một bước, kết quả đúng |
| Lượt 1 trả lời mà không có bước `Đọc sách` nào | **Không đạt** | Trả lời theo trí nhớ, không theo sách |
| Lượt 2 trả lời vị trí từ `get_chapter` mà kể thêm nội dung bài chưa đọc | Chấp nhận được, ghi lại | Vị trí và trang đúng theo label; phần nội dung là hiểu biết riêng (backlog) |
| Lượt 4 hỏi lại số câu hay khối | Gõ `toán lớp 6 nhé`. Chấp nhận được nếu một lần | Như case 04 |
| Lượt 4 nêu dàn ý mà không có bước `Đọc sách` nào trong lượt ấy | **Không đạt** | `read_before_outline` phải ép đọc phạm vi: lần đọc ở lượt 1 là đọc để trả lời |

## Đạt khi

1. **Lượt 1:** có ít nhất một bước `Đọc sách`. Lời Kriky nêu định nghĩa luỹ thừa (tích nhiều thừa số
   bằng nhau; $a^n$, cơ số $a$, số mũ $n$), tên bài *Luỹ thừa với số mũ tự nhiên* và trang. Trang
   so với `labels` của truy vấn A (nhãn ghi số trang in, ví dụ `tr. 22–25`). Không có dàn ý, không
   có thẻ đề.
2. **Lượt 2:** nêu mục *Số La Mã* (hay bài *Cách ghi số tự nhiên*) kèm trang, gần chữ một dòng
   `labels` hay `candidates` của mục lục.
3. **Lượt 3:** nói chương I của sách không có phần phân số. Có thể kể các bài sách có. Không bịa một
   bài phân số nào.
4. **Truy vấn A:** mọi `read_section` của lượt 1–3 **không** có `questions` và có
   `answering` = true.
5. **Lượt 4:** có một `read_section` **có** `questions` = 3 trong chính lượt ấy, rồi một dàn ý 3
   câu với bài nguồn *Luỹ thừa…*.

## Không đạt khi

- Lượt 1 trả lời mà không có `read_section` nào; lượt 2 hay 3 trả lời mà không mở mục lục
  (`list_chapters`/`get_chapter`) trong lượt ấy.
- Nêu một bài hoặc trang không có trong `labels`/`candidates`.
- Lượt 3 bịa ra một bài phân số trong sách.
- Lượt 1–3 nêu dàn ý, nêu plan hay tạo đề.
- Lượt 4 nêu dàn ý mà trong lượt ấy không có `read_section` nào có `questions`.
- Vi phạm một trong tám luật chung của `huong-dan.md`.

## Ghi lại

- Nguyên văn lời Kriky ở lượt 1–4. Khối bước của mỗi lượt: n, tên từng bước.
- Đầu ra truy vấn A.

Truy vấn A (PowerShell). Chạy ngay sau case, trước khi mở đoạn chat khác: nó đọc đoạn chat mới
nhất. Hàng `teacher` là ranh giới giữa các lượt.

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, kind, tool_name, left(text, 40) loi, tool_args->>'nodes' nodes, tool_args->>'questions' cau, tool_args->>'part' part, tool_result->>'answering' tra_loi, tool_result->'labels' labels, tool_result->'candidates' muc from teacher_turns where conversation_id = (select id from teacher_conversations order by started_at desc limit 1) and (kind = 'teacher' or tool_name in ('list_chapters','get_chapter','read_section')) order by sequence;"
```
