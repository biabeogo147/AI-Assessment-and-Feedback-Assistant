# 17. Công thức từ sách

Nhóm: Ra đề bằng chat · Lượt model: ~8 · Chạy sau: 04 (cùng cuốn sách; không dùng đề của 04)

## Cho người xem thấy gì

Bài có công thức thì dàn ý dẫn đúng công thức in trong sách: `read_section` kèm khối công thức Claude
Haiku đọc từ ảnh trang (plan `formulas-on-demand`, hậu ký ADR-29 26/10/2026). Ảnh chỉ đọc **một lần**
cho mỗi trang: đoạn chat thứ hai đọc cùng bài lấy công thức từ cache, không gọi model nào.

## Chuẩn bị

- Đã làm đủ phần *Chuẩn bị* của `huong-dan.md`. Chip `Kết nối tri thức Lớp 6 tập 1 (tr6-28).pdf`
  *sẵn sàng*. Worker `index` (`.\dev.ps1 index`, nơi job `read_formulas` chạy) chạy **code của
  commit đang thử** -- nó không tự nạp lại code; khởi động lại nếu đã chạy từ trước.
- Trước lượt 1, chạy truy vấn D và ghi số: số hàng `page_formulas` của cuốn này cho trang 18–21. Lần
  chạy đầu sau khi tải lên là 0. Muốn thử lại đường *chưa có cache* thì xoá các hàng ấy (lệnh xoá
  dưới truy vấn D) -- không cần `db-reset`.
- Bấm *Đoạn chat mới*, đính chip (kéo chip vào ô nhập, như case 04).

## Lời chat

Đoạn chat 1, lượt 1 (chip đã đính):

```
soạn giúp mình 3 câu về luỹ thừa với số mũ tự nhiên trong sách này
```

Đoạn chat 1, lượt 2 (chỉ khi lượt 1 ra dàn ý): không gõ gì, chỉ ghi lại -- case này không soạn đề.

Đoạn chat 2 (bấm *Đoạn chat mới*, đính chip lại), lượt 1: cùng câu của đoạn chat 1.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Hỏi lại bài nào, nút là tên bài | Bấm nút có chữ `LUÝ THỪA`. Chấp nhận được nếu một lần | Nhãn OCR có thể sai dấu (`VỚl`) nên khớp không chắc |
| Hỏi môn, khối hay dạng câu | Gõ `toán lớp 6, trắc nghiệm nhé`. Chấp nhận được nếu một lần | Như case 04 |
| Đọc cả bài 14 lẫn hai mục con 15, 16 | Không trả lời gì. Chấp nhận được | Cùng trang; công thức mỗi trang chỉ in một lần mỗi phần đọc |
| Bước `Đọc sách` lâu hơn thường lệ (tới ~15 s) ở đoạn chat 1 | Đợi. Chấp nhận được | BE chờ `services/document` đọc ảnh, trần `FORMULA_WAIT_SECONDS` |
| Truy vấn A có `formulas_pending` = true ở đoạn chat 1 | Ghi lại. Chấp nhận được nếu đoạn chat 2 không còn nó | Hết trần chờ, job vẫn chạy và lấp cache cho lần sau |
| Dàn ý viết công thức khác cách ghi của khối (vd `a^m \cdot a^n` thay `a^{m} . a^{n}`) | Chấp nhận được | Cùng một công thức; Kriky được dặn sửa chỗ máy đọc sai rõ ràng |
| Dàn ý gọi một công thức **không** có trong khối là *của sách* | Ghi lại. Không đạt | `CORE`: chỉ công thức chép từ khối mới được nói là của sách |

## Đạt khi

1. **Đoạn chat 1, lượt 1:** một lời dàn ý đạt (`huong-dan.md`) cho 3 câu, mọi mục nêu bài nguồn
   *Luỹ thừa với số mũ tự nhiên* (hay một mục con của nó).
2. **Truy vấn A (đoạn chat 1):** mỗi `read_section` có `text` chứa
   `[Công thức đọc từ ảnh trang sách -- máy đọc, có thể sai]` và ít nhất một dòng `Trang N: $…$` với
   N trong 18–20. Trang là trang **tệp**, không phải số in trên trang (nhãn ghi `tr. 22–25`). Trang
   21 có khối `formula` nhưng không đoạn chữ nào của bài phủ tới nó, nên không được xin (lần chạy
   26/10/2026).
3. Ít nhất một mục dàn ý có trong `formulas` công thức nhân hai luỹ thừa cùng cơ số
   ($a^m \cdot a^n = a^{m+n}$) hoặc chia ($a^m : a^n = a^{m-n}$), đúng như sách -- so với khối của
   truy vấn A, không so với trí nhớ.
4. **Truy vấn D sau đoạn chat 1:** có hàng cho các trang 18, 19, 20, `refused` = false, `model` =
   `claude-haiku-5-5`. Log của worker `index` có dòng `read formulas of …` cho các trang ấy.
5. **Đoạn chat 2:** truy vấn A lại có khối công thức, **không** có `formulas_pending`; log worker
   **không** có dòng `read formulas of …` mới, và số hàng của truy vấn D không đổi.

## Không đạt khi

- `read_section` không có khối công thức dù truy vấn D đã có hàng.
- Đoạn chat 2 sinh job `read_formulas` mới (log worker có dòng mới) cho trang đã có hàng.
- Dàn ý dẫn công thức sai so với khối (vd $a^m \cdot a^n = a^{m \cdot n}$) mà không ghi là tự viết.
- Lượt 1 đã soạn câu, có thẻ đề, hay không có dàn ý.
- Vi phạm một trong tám luật chung của `huong-dan.md`.

## Ghi lại

- Nguyên văn lời dàn ý của cả hai đoạn chat; dòng `formulas` của từng mục (truy vấn B nếu đã soạn,
  không thì chép từ lời).
- Đầu ra truy vấn A của hai đoạn chat (chỉ phần khối công thức), truy vấn D trước và sau.
- Các dòng `read formulas of …` trong log worker `index` (trang, số công thức, số token).

Truy vấn A (PowerShell; khối công thức nằm cuối `text`):

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, tool_result->>'part' part, tool_result->>'formulas_pending' cho, substring(tool_result->>'text' from '\[Công thức đọc từ ảnh[^\]]*\].*') cong_thuc from teacher_turns where conversation_id = (select id from teacher_conversations order by started_at desc limit 1) and tool_name = 'read_section' and kind = 'tool_result' order by sequence;"
```

Truy vấn D (Git Bash):

```
D=$(docker exec aiafa-postgres psql -U aiafa -d aiafa -At -c "select id from documents where filename like '%tr6-28%' limit 1")
docker exec aiafa-mongo mongosh --quiet aiafa_content --eval 'db.page_formulas.find({document_id: "'"$D"'", page: {$gte: 18, $lte: 21}}, {_id: 0, page: 1, model: 1, refused: 1, tokens: 1, formulas: 1}).sort({page: 1}).forEach(r => print(JSON.stringify(r)))'
```

Xoá cache để thử lại đường *chưa có cache* (Git Bash):

```
D=$(docker exec aiafa-postgres psql -U aiafa -d aiafa -At -c "select id from documents where filename like '%tr6-28%' limit 1")
docker exec aiafa-mongo mongosh --quiet aiafa_content --eval 'printjson(db.page_formulas.deleteMany({document_id: "'"$D"'", page: {$gte: 18, $lte: 21}}))'
```
