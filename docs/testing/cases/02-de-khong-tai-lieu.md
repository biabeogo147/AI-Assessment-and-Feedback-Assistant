# 02. Đề không tài liệu: duyệt dàn ý rồi mới soạn

Nhóm: Ra đề bằng chat · Lượt model: ~8 (1–2 cho dàn ý, 1 cho lượt đồng ý, 5 job soạn, 1 câu kết)
· Chạy sau: không (case 05 và 09 chạy tiếp trên đề và đoạn chat của case này)

## Cho người xem thấy gì

Giáo viên đọc và duyệt **kế hoạch từng câu** (kiến thức, công thức, cách làm) trước khi có câu nào
được soạn, và năm câu ra đúng kế hoạch ấy (ADR-29).

## Chuẩn bị

- Theo `docs/testing/huong-dan.md` mục *Chuẩn bị*. **Đoạn chat mới**, không đính chip tài liệu nào.
- Trước lượt 1, chạy và ghi lại: chỉ có đề seed.

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select title, state from assessments order by created_at;"
  ```

- **Để lại cho case sau:** đoạn chat này và đề nó tạo ra — **không** duyệt, không phát hành, không
  xoá câu nào ở đây. Tên đề do hệ thống đặt; chép nguyên văn từ thẻ vào biên bản để case 05, 09 tìm.

## Lời chat

Lượt 1 — đủ dữ kiện ngay câu đầu:

```
soạn giúp mình 1 đề kiểm tra 15 phút Toán 7, phần tỉ lệ thức và dãy tỉ số bằng nhau, 5 câu trắc nghiệm nhé
```

Lượt 2 — chỉ gõ sau khi dàn ý đã hiện, đọc hết dàn ý trước:

```
được rồi, soạn đi nhé
```

Câu này nằm trọn trong khuôn đồng ý của AGENT (`propose._AGREES`: *được*, *rồi*, *soạn đi*, *nhé*),
nên plan soạn dựng thẳng từ dàn ý vừa hiện, không phụ thuộc model đọc hiểu.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Hỏi xác nhận hay hỏi mức độ dù đủ dữ kiện | Gõ vào ô chat (không bấm nút): `đúng rồi, mức trung bình thôi, lớp đại trà`. **Chấp nhận được**, ghi nguyên văn câu hỏi | Điểm yếu đã đo; đủ môn, khối, phạm vi, số câu thì không cần hỏi |
| Câu hỏi lại có kiểu *"mình sẽ soạn ngay"* | Như dòng trên; ghi là vi phạm luật 4 | Hứa một việc chưa làm |
| Dàn ý các mục cùng một chủ đề, không công thức, cách làm chung chung | Vẫn gõ lượt 2. **Không đạt** tiêu chí dàn ý | Dàn ý như vậy không cho giáo viên duyệt được gì (ADR-29 *Vì sao*) |
| Dàn ý không đủ 5 câu (tổng ở dòng *"Dàn ý — N câu"* khác 5) | Gõ `mình cần đủ 5 câu nhé`, đợi *(bản 2)*, rồi gõ lượt 2. **Không đạt** lượt 1 | Kriky bỏ số câu giáo viên đã nói |
| Lượt 1 đã có khối bước `Tạo đề trống` / soạn câu | **Không đạt** nặng; chụp màn hình, chạy truy vấn ở *Ghi lại* | Cổng của BE (`guard_drafting`) lẽ ra chặn soạn khi chưa có dàn ý |
| Lượt 2 không soạn: đưa lại dàn ý hay hỏi tiếp | Nếu là dàn ý mới thì gõ `oke` một lần; vẫn không soạn thì dừng. **Không đạt** | Lời đồng ý khớp khuôn mà không được nhận là lỗi của `_approved_plan` |
| Bước soạn dừng ở 4/5 (một câu hỏng) | **Không đạt** tiêu chí 5/5; soi câu kết có nói đúng 4 không | Luật 3: số trên khối bước và câu nói phải khớp |
| Câu mở lượt 2 không phải *"Được, mình soạn theo dàn ý ngay."* mà vẫn soạn đúng | **Chấp nhận được**, ghi lại | Plan đến từ model chứ không từ dàn ý: lời đồng ý đã đi đường dự phòng |

## Đạt khi

Lượt 1:

- Đúng **một** lời Kriky, có dòng `Dàn ý — 5 câu (bản 1)`, rồi các mục `Câu a · …` hoặc
  `Câu a–b · …` phủ đủ câu 1 tới 5, mỗi mục có `Cách làm: …`; ít nhất phần lớn mục có
  `Công thức Kriky đề xuất: …` với toán dựng hình (vd $\frac{a}{b}=\frac{c}{d}$, $ad=bc$).
- Các mục **khác nhau thật**: không hai mục nào trùng cả kiến thức lẫn cách làm; dàn ý chạm cả
  tỉ lệ thức lẫn dãy tỉ số bằng nhau. Không dòng `Theo: …` (không có sách).
- Kết bằng nguyên văn: *Bạn đồng ý với dàn ý này chứ? Muốn đổi câu nào, cứ nói, ví dụ: "câu 2 đổi
  sang …". Câu hỏi chỉ được soạn sau khi bạn đồng ý.*
- Không khối bước nào chứa `Tạo đề trống` hay bước soạn; truy vấn ở *Chuẩn bị* chạy lại vẫn chỉ ra
  đề seed.

Lượt 2:

- Khối bước hai bước: `Tạo đề trống` → `Soạn câu hỏi` (tên khi lượt xong, xem `huong-dan.md`),
  `bước k/2` không nhảy, đúng một
  hàng có dải sáng lúc chạy; dòng dưới bước soạn kết thúc ở `đã soạn 5/5 câu`.
- Câu kết không khen câu hỏi, không nói số khác 5 (luật 2, 3); thẻ `Đã tạo đề "<tên>"` với dòng
  `Chưa duyệt · chưa phát hành`.
- Bấm thẻ mở panel: 5 câu trắc nghiệm, toán dựng hình. **Bám dàn ý**: với từng câu `i` trong panel,
  tìm mục dàn ý có khoảng `Câu a–b` chứa `i`; câu ấy kiểm đúng kiến thức của mục, giải được bằng
  công thức và cách làm mục nêu. Hai câu chung một mục thì khác số liệu hoặc cách hỏi.
- Database khớp với phép so trên màn hình — mỗi ô `ready`, `outline_item` không rỗng, `ban` = 1,
  và cột `muc` của ô `i` đúng là kiến thức của mục chứa câu `i` trên màn hình:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select d.ordinal, d.status, d.outline_item, d.item_part, b.outline->d.outline_item->>'knowledge' as muc, b.outline->d.outline_item->>'version' as ban, left(q.stem, 70) as cau from draft_items d join draft_briefs b on b.assessment_id = d.assessment_id left join questions q on q.assessment_id = d.assessment_id and q.order_index = d.ordinal where d.assessment_id = (select id from assessments order by created_at desc limit 1) order by d.ordinal;"
  ```

  (`outline_item` đếm từ 0: mục đầu tiên của dàn ý là 0.)

## Không đạt khi

- Lượt 1 đã soạn câu, hay đề mới xuất hiện trong `assessments` trước lượt 2.
- Dàn ý có Markdown, số node trần, UUID, tên tool; hay một mục thiếu `Cách làm`.
- Năm mục cùng ghi một chủ đề (vd năm lần *"Tỉ lệ thức"*) mà không công thức nào phân biệt chúng.
- Lời đồng ý `được rồi, soạn đi nhé` không dẫn tới khối `Tạo đề trống`.
- Một câu trong panel hỏi kiến thức không có trong mục của nó (vd câu 2 thuộc mục dãy tỉ số mà hỏi
  tìm $x$ trong tỉ lệ thức đơn), hay `muc` trong database lệch với mục giáo viên đã đọc.
- Đề dưới 5 câu mà câu kết hay thẻ vẫn nói đã soạn xong 5 câu.

## Ghi lại

- Nguyên văn cả lời dàn ý (bản 1, và bản 2 nếu có), câu hỏi lại nếu có, câu kết lượt 2.
- **Tên đề trên thẻ**, nguyên văn — case 05 và 09 dùng nó. Hệ thống đặt `Đề <phạm vi Kriky ghi>`
  khi plan dựng từ dàn ý, nên tên đổi theo lần chạy.
- Bảng năm dòng: câu `i` · mục dàn ý chứa nó · câu có bám mục không (có / lệch, một dòng vì sao).
- Kết quả hai truy vấn database, và dòng kết quả của bước soạn (`đã soạn k/5 câu`).
