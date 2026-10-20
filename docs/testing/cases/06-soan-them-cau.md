# 06. Soạn thêm câu vào đề đang có

Nhóm: Ra đề bằng chat · Lượt model: ~6 · Chạy sau: 04

## Cho người xem thấy gì

Kriky làm tiếp trên đề đang soạn như một người cộng tác: xin thêm 2 câu thì dàn ý đánh số tiếp
`Câu 6–7`, đồng ý thì đề thành 7 câu, 5 câu cũ y nguyên, không mở thêm đề nào.

## Chuẩn bị

- Các truy vấn lọc theo `title = '<tên>'` chạy trong **Git Bash**: PowerShell 5.1 có thể làm
  hỏng chữ có dấu khi truyền sang `docker exec`, và truy vấn ra 0 dòng.
- Chạy tiếp **đúng đoạn chat của case 04**: đề 5 câu theo SGK Toán 6 chương I đã soạn xong, thẻ
  `Đã tạo đề "<tên>"` ghi `Chưa duyệt · chưa phát hành`. Chép lại `<tên>` trên thẻ ấy.
- Đề **chưa duyệt**. Lỡ bấm Duyệt ở case 04 thì bấm Bỏ duyệt trước — đề đã duyệt bị khoá (ADR-01),
  soạn thêm sẽ hỏng ở bước soạn.
- **Không đính chip lại.** Sách của dàn ý soạn thêm là sách của đề (`outline_turn` lấy
  `document_id` từ `draft_briefs`), không phải chip trên ô gõ.
- Chụp trạng thái trước khi gõ (để so ở *Đạt khi*):

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select a.title, count(q.id) from assessments a left join questions q on q.assessment_id = a.id group by a.id order by a.created_at;"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select order_index, md5(stem) from questions where assessment_id = (select id from assessments where title = '<tên>' order by created_at desc limit 1) order by order_index;"
  ```

## Lời chat

Lượt 1 — sau khi xem đề 5 câu của case 04:

```
đề ổn rồi mà còn thiếu phần số La Mã, thêm 2 câu về số La Mã nữa nhé
```

Lượt 2 — chỉ gõ khi dàn ý vừa hiện đánh số `Câu 6–7` (hoặc `Câu 6` và `Câu 7`):

```
oke soạn đi
```

Câu lượt 1 có cụm `thêm 2 câu` là cố ý: khớp `_ADDS` (`thêm\s+\d+\s+câu`) trong
`propose/outline.py`, nên `_right_purpose` sửa dàn ý `for=new` thành `for=more` khi đoạn chat
đã có đề.
Cách nói *"thêm cho mình 2 câu"* **không** khớp (chữ chen giữa `thêm` và số) và chỉ còn trông vào
model tự ghi `for=more`. Không gõ cụm `đề mới`, `đề khác`, `đề nữa` ở bất kỳ lượt nào của case
này: `_ANOTHER_PAPER` gặp chúng thì dừng dò và việc thành đề mới. `oke soạn đi` khớp `_AGREES`
(cả câu chỉ là lời đồng ý), nên `_approved_plan` dựng plan từ chính dàn ý.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
|---|---|---|
| Đọc mục lục / đọc bài 2 trước rồi mới nêu dàn ý (khối bước đọc sách) | Đạt, đợi dàn ý | Dàn ý theo sách phải trỏ về bài có thật (`validate` đòi `source_nodes`) |
| Hỏi lại bài nào | Gõ `Bài 2 trong sách ấy, phần số La Mã` | Điểm yếu đã đo (backlog: hỏi lại dù đủ mục). Chấp nhận được; câu đáp không chứa cụm nào đổi việc, `_right_purpose` vẫn dò thấy lượt 1 |
| Hỏi đọc hay viết số La Mã, có nút lựa chọn | Gõ `1 câu đọc số, 1 câu viết số` | Như trên. Không bấm nút: chữ trên nút không cố định giữa các lần |
| Hỏi thêm vào đề vừa soạn hay đề mới | Gõ `thêm vào đề vừa soạn` | Chấp nhận được. Không gõ chữ `mới` sau chữ `đề` |
| Dàn ý ra `Câu 1–2` | **Không đạt** (dàn ý). Không gõ `oke`; gõ `ko, thêm 2 câu vào đề vừa soạn, nối sau câu 5` rồi ghi xem dàn ý kế có thành `Câu 6–7` không | `Câu 1–2` là `for=new`: `oke` sẽ ra `Tạo đề trống` → đề thứ hai. Lỗi đã sửa một lần — gặp lại là lỗi sản phẩm, ghi backlog |
| Dàn ý `Câu 6–8` (3 câu) hay sai chủ đề | Gõ `chỉ 2 câu về số La Mã thôi` → đợi bản kế | Chấp nhận được nếu bản kế đúng. Chữ ấy không khớp `_ADDS`, lượt 1 vẫn là lời nói rõ việc gần nhất |
| Nêu plan `Tạo đề trống` mà không có bước soạn, ngay lượt 1 | **Không đạt**. Ghi nguyên văn, dừng case | Lỗ đã biết: `guard_drafting` chỉ chặn plan có bước soạn; plan chỉ `create_draft` mở một đề trống không qua dàn ý |
| Sau `oke soạn đi`, khối bước có `Tạo đề trống` | **Không đạt** | Dàn ý đã xem là `for=new`; đề mới, không phải đề đang có |
| Nói "mình sẽ soạn ngay" mà không nêu dàn ý | Gõ `nêu dàn ý trước cho mình xem` | Chấp nhận được nếu lượt kế là dàn ý `Câu 6–7`. BE từ chối soạn khi chưa có dàn ý |

## Đạt khi

1. Lượt 1 kết bằng một lời dàn ý đạt (`huong-dan.md`) cho 2 câu, mục `Câu 6–7` (hoặc `Câu 6` và
   `Câu 7`) nói về số La Mã, bài nguồn là mục số La Mã (gần chữ một dòng `labels` của
   `read_section`, vd `2. SỐ LA MÂ (tr. 10–13)`). Database: hàng `outline` mới có `version` lớn hơn
   bản cuối của case 04. Kriky đọc lại sách thì các bước mang tên `Xem mục lục` / `Đọc sách — phần
   k/n: …` ngay lúc chạy. Lượt này không có bước soạn nào chạy.
2. Lượt 2: khối bước **một** bước `Soạn câu hỏi` (cùng tên lúc chạy; không `Tạo đề trống`), dòng
   dưới ghi
   `đã soạn 7/7 câu` — `_count_questions` đếm cả đề, không chỉ 2 câu mới.
3. Thẻ cuối `Đã tạo đề "<tên>"` — **cùng tên** đề case 04 — với `Chưa duyệt · chưa phát hành`.
   Bấm thẻ: panel có 7 câu; câu 6, 7 về số La Mã; câu 1–5 cùng chữ như trước.
4. Câu kể của Kriky khớp con số trên khối bước (luật 3) và không khen câu nó không đọc (luật 2).
5. Database, chạy lại hai truy vấn ở *Chuẩn bị*: danh sách đề **cùng số dòng**, đề `<tên>` từ 5
   thành 7; năm dòng `md5(stem)` của câu 1–5 trùng hệt. Thêm:

   ```
   docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select d.ordinal, d.outline_item, d.status from draft_items d join assessments a on a.id = d.assessment_id where a.title = '<tên>' order by d.ordinal;"
   docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select b.question_count, json_array_length(b.outline) from draft_briefs b join assessments a on a.id = b.assessment_id where a.title = '<tên>';"
   ```

   Ordinal 1–7, đều `ready`; `outline_item` của 6, 7 lớn hơn mọi `outline_item` của 1–5;
   `question_count` = 7, và số mục `outline` tăng đúng bằng số mục của dàn ý lượt 1.

## Không đạt khi

- Dàn ý đánh số `Câu 1`/`Câu 1–2`, hay khối bước có `Tạo đề trống`, hay số dòng đề tăng.
- Một câu nào trong 1–5 đổi chữ (md5 khác), hay đề còn 5 câu mà Kriky nói đã thêm.
- Câu hỏi được soạn ngay lượt 1, trước khi giáo viên đồng ý dàn ý.
- Thẻ cuối mang tên khác đề case 04, hay hai thẻ `Đã tạo đề` ở lượt 2.
- Câu 6, 7 không phải số La Mã, hay trùng ý một câu cũ.
- Dàn ý không nêu bài nguồn dù đề theo sách; hay bất kỳ dòng nào trong tám luật chung bị phạm.

## Ghi lại

- Nguyên văn trọn lời dàn ý lượt 1, và mọi câu hỏi lại
  trước nó cùng câu đã gõ trả lời (theo bảng *Nếu Kriky rẽ*).
- Tên các bước trong khối lượt 2 và dòng `đã soạn k/n câu`; nguyên văn câu kể của Kriky.
- Đề bài câu 6 và 7 trên panel.
- Kết quả bốn truy vấn trước/sau: số dòng đề, năm md5, `draft_items`, `question_count`.
- Nhánh nào trong bảng đã xảy ra, và phán đạt / chấp nhận được / không đạt.
