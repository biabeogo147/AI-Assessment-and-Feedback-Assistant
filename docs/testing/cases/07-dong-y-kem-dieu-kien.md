# 07. Đồng ý kèm điều kiện

Nhóm: Ra đề bằng chat · Lượt model: ~3 lượt chat + 4 job soạn câu · Chạy sau: không

## Cho người xem thấy gì

Giáo viên gõ *"ok nhưng câu 2 đổi…"* thì Kriky không coi chữ "ok" là đồng ý: nó đưa dàn ý bản 2
với câu 2 đã đổi, chờ một lời đồng ý gọn, rồi mới soạn, và soạn theo bản 2, không theo bản 1.

## Chuẩn bị

- Đoạn chat mới, không đính chip tài liệu nào. Lời chat không nhắc "sách", để Kriky không mở
  thư viện.
- Seed như `huong-dan.md`; lớp 12B có hay không không ảnh hưởng (đề không gắn lớp).
- Trước lượt 1, ghi số brief đang có:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) from draft_briefs;"
  ```

## Lời chat

Lượt 1:

```
Soạn cho mình 4 câu Toán lớp 10, phần mệnh đề với tập hợp nhé
```

Lượt 2 (sau khi dàn ý đầu tiên hiện):

```
ok nhưng câu 2 đổi sang tìm giao, hợp của 2 khoảng trên trục số đi
```

Chạy lại truy vấn `count(*)` ở trên: phải bằng số ghi lúc chuẩn bị.

Lượt 3 (sau khi dàn ý thứ hai hiện):

```
ok, soạn đi
```

Đợi dòng dưới bước soạn tới `đã soạn 4/4 câu`, bấm thẻ `Đã tạo đề "…"` mở panel.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
|---|---|---|
| Lượt 1 hỏi lại dù đã đủ môn, khối, phạm vi, số câu | Gõ `Toán 10, mệnh đề và tập hợp, 4 câu nha`. Chấp nhận được | Điểm yếu đã đo; không phải điều case này soi |
| Lượt 1 ra dàn ý một mục `Câu 1–4` | Vẫn gõ lượt 2 y nguyên. Chấp nhận được nếu bản 2 tách đúng câu 2 ra | Dàn ý không sách có lúc chung chung |
| Sau lượt 2 hiện khối bước `Tạo đề trống` / `Soạn câu hỏi`, hay thẻ `Đã tạo đề` | Dừng case. **Không đạt — nặng nhất** | Soạn theo bản 1 mà giáo viên vừa xin đổi; đúng lỗi đã sửa ở review đợt 6 |
| Sau lượt 2 chỉ nói *"mình đã ghi nhận, sẽ đổi câu 2"*, không nêu dàn ý | Gõ `gửi lại dàn ý mình xem đã`. **Không đạt** (ghi tiếp để biết nó có tự hồi không) | Giáo viên không thấy bản 2 thì không có gì để duyệt |
| Sau lượt 2 hỏi lại câu 2 dạng gì | Gõ `trắc nghiệm như mấy câu kia`. Chấp nhận được nếu sau đó ra bản 2 | Hỏi một lần là hợp lý; hỏi vòng là không |
| Bản 2 chỉ có một mục `Câu 2` | **Không đạt** | Sửa dàn ý là nêu lại ĐỦ mọi mục (skill `soan-de` bước 3) |
| Bản 2 câu 2 không đổi (giống bản 1) | **Không đạt** | Bỏ qua đúng điều giáo viên nói |
| Bản 2 đổi cả câu khác: chỉ khác chữ, cùng kiến thức | Chấp nhận được | Diễn đạt lại không đổi đề |
| Bản 2 đổi kiến thức của câu 1, 3 hay 4 | **Không đạt** | "chỉ sửa đúng chỗ họ nói" — giáo viên đã chấp nhận các câu ấy |
| Sau lượt 3 lại nêu dàn ý (bản 3) thay vì soạn | Gõ `ok`. Chấp nhận được nếu bản 3 trùng bản 2 và sau đó soạn | Một lượt thừa, chưa sai ý giáo viên |
| Sau lượt 3 hỏi lại khối hay phạm vi | Gõ `Toán 10, mệnh đề và tập hợp`. Không đạt | Lời đồng ý gọn phải đi thẳng vào soạn |

## Đạt khi

- Lượt 1: một lời dàn ý đạt (`huong-dan.md`) cho 4 câu. Không khối bước.
- Lượt 2: **không** khối bước, **không** thẻ `Đã tạo đề`; một lời dàn ý đạt mới (database: hàng
  `outline` `version` = 2), nêu đủ mọi mục; mục chứa câu 2 nói về giao, hợp của hai khoảng; các câu còn lại cùng kiến thức
  với bản 1. `count(*)` của `draft_briefs` không tăng.
- Lượt 3: khối bước `Tạo đề trống` → `Soạn câu hỏi` (cùng tên lúc chạy; `bước k/2`, n cố định), dòng đếm
  tới `đã soạn 4/4 câu`, một thẻ `Đã tạo đề "<tên>"` với `Chưa duyệt · chưa phát hành`.
- Panel: 4 câu, câu 2 hỏi giao hoặc hợp của hai khoảng (vd $[1;5)$ và $(3;+\infty)$), toán
  dựng hình.
- Database — đề vừa tạo theo đúng bản 2 (mọi dòng `ban` = 2, `count(*)` tăng đúng 1):

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select a.title, b.question_count, i->>'version' as ban, i->>'knowledge' as kien_thuc from draft_briefs b join assessments a on a.id = b.assessment_id, json_array_elements(b.outline::json) i where b.created_at = (select max(created_at) from draft_briefs);"
  ```

- Tám luật chung của `huong-dan.md` đúng ở cả ba lượt.

## Không đạt khi

- Bất kỳ khối bước soạn hay thẻ `Đã tạo đề` nào hiện giữa lượt 2 và lượt 3, hoặc `count(*)` tăng
  sau lượt 2. Đây là lỗi nặng nhất: đề soạn theo bản giáo viên vừa từ chối.
- Đề cuối có `ban` = 1 ở bất kỳ mục nào, hay câu 2 trên panel không về giao/hợp hai khoảng.
- Lượt 2 không có dàn ý bản 2 (chỉ một câu nói), hay bản 2 thiếu mục, hay đổi kiến thức câu khác.
- Lượt 3 không soạn, hoặc soạn số câu khác 4, hoặc mở hai đề.
- Câu nói ở lượt 3 khoe chất lượng câu hỏi (*"4 câu rất hay"*) hay nói *"đã soạn xong"* khi dòng
  đếm chưa tới 4/4.

## Ghi lại

- Nguyên văn hai dàn ý (bản 1, bản 2), đủ từng mục — để so mục nào đã đổi.
- Nguyên văn trọn lời Kriky ngay sau lượt 2, và câu mở của lượt 3 nếu có.
- Ba con số `count(*)`: lúc chuẩn bị, sau lượt 2, sau lượt 3.
- Kết quả truy vấn đề cuối (tên đề, `question_count`, `ban`, `kien_thuc` từng mục).
- Chữ câu 2 trên panel.
- Nhánh rẽ nào đã gặp (theo bảng), và lời cố định đã gõ để trả lời.
