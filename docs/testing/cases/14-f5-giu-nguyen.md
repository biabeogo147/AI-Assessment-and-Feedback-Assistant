# 14. F5 giữ nguyên

Nhóm: Độ bền · Lượt model: ~5 (phần A: 0) · Chạy sau: 06 (trên đoạn chat của 04)

## Cho người xem thấy gì

Những gì giáo viên đã thấy không mất, không đổi chữ: F5 hay rời đoạn chat rồi quay lại vẫn ra đúng
từng dàn ý, khối bước, thẻ đề, câu kể. Dàn ý họ đã duyệt là bằng chứng đọc lại được. Đóng máy khi
một dàn ý đang chờ, hôm sau gõ "oke" thì lời đồng ý vẫn được nhận.

## Chuẩn bị

- Chạy tiếp **đúng đoạn chat của case 04 và 06**: đề `<tên>` 7 câu, chưa duyệt. Không đính chip.
- Chép `<CID>` từ thanh địa chỉ (`#/teacher/chat/<CID>`). Rail phải có **ít nhất một đoạn chat
  khác** (vd đoạn của case 02); chưa có thì phần A3 dùng nút *Đoạn chat mới*.
- Bấm thẻ `Đã tạo đề` cuối (case 06) để mở panel: địa chỉ thành `…/chat/<CID>/de/<id>`.
- **Chụp S0**, trước mọi thao tác. Mở (chevron) **mọi** khối `Đã làm n bước`, rồi ghi từ trên xuống:
  câu giáo viên; với mỗi lượt Kriky: câu mở, header khối, từng bước (dấu, tên, dòng `— …`), câu
  kết hoặc trọn lời dàn ý, chữ thẻ.
  Panel: số câu, chữ đầu của từng câu. Cùng lúc chạy (Git Bash):

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*), max(sequence) from teacher_turns where conversation_id = '<CID>';"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, tool_result->>'version' ban, tool_result->>'for' viec, left(text, 60) dau, json_array_length((tool_result->'items')::json) muc from teacher_turns where conversation_id = '<CID>' and kind = 'outline' order by sequence;"
  ```

## Lời chat

**Phần A — không gõ gì.** A1: F5 khi panel đang mở → chụp S1. A2: bấm đoạn chat khác trên rail,
đợi nó hiện, bấm lại đoạn `<CID>` → chụp S2; bấm thẻ `Đã tạo đề` cuối để mở lại panel. A3: chạy lại
truy vấn đếm.

**Phần B — một dàn ý đang chờ qua một lần đóng máy.** Lượt 1:

```
à còn thiếu lũy thừa, thêm 1 câu về lũy thừa nữa nhé
```

Khi lượt 1 ra dàn ý có mục `Câu 8`: chụp lời dàn ý (S3), **đóng hẳn tab**, mở tab mới
`http://127.0.0.1:5173/#/teacher`, bấm đoạn `<CID>` trên rail, so với S3. Rồi lượt 2:

```
oke
```

Xong lượt 2: F5 một lần nữa, so khối lượt 2 trước và sau.

`thêm 1 câu` khớp `_ADDS` nên dàn ý thành `for=more` (như case 06). `oke` khớp `AGREES`.
Không gõ `đề mới`, `đề khác`, `đề nữa`.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Sau F5 khối bước thu còn `Đã làm n bước` | Bấm chevron. Đạt | Khối tự thu lúc lượt xong; nấc mở không được nhớ |
| Bước đọc sách hiện `Một bước nữa`, hay tên, dòng `— …` của một bước khác giữa lúc chạy và sau F5 | Không đạt | Mọi tool có tên trong `STEP_TITLE` (`ActionCard.tsx`), và lúc chạy FE đặt tên bằng đúng bảng ấy (`kriky-writes-every-word`) |
| Quay lại từ rail mà panel đóng | Bấm thẻ cuối. Đạt | Panel đi theo route; rail mở `#/teacher/chat/<CID>` không kèm `/de/` |
| Lượt 1 đọc bài trước dàn ý | Đạt, đợi dàn ý | `read_before_outline` bắt đọc chữ trước dàn ý có sách |
| Lượt 1 hỏi lại bài nào | Gõ `Bài 6 trong sách ấy`. Chấp nhận được | Không chứa cụm đổi việc; `right_purpose` vẫn dò thấy câu `thêm 1 câu` |
| Lượt 1 hỏi khía cạnh của câu lũy thừa (nút: khái niệm / cách tính / ứng dụng) | Gõ `câu tính giá trị lũy thừa thôi`. Chấp nhận được | Một lượt thừa; câu đáp không chứa cụm đổi việc |
| Dàn ý `Câu 1` | Không đạt, không gõ `oke`, ghi lại | `for=new`: `oke` sẽ mở đề thứ hai (xem case 06) |
| Dàn ý 2 câu trở lên | Gõ `chỉ 1 câu lũy thừa thôi`, rồi lại đóng tab trước `oke` | Chấp nhận được nếu dàn ý kế đúng `Câu 8` |
| Mở lại tab mà dàn ý biến mất, khác chữ, hay có thẻ hỏi lại | Không đạt, dừng | Đọc lại không ghi gì; màn hình phải là thứ database giữ |
| Sau `oke` ra dàn ý mới hay hỏi lại | Không đạt. Chạy truy vấn đếm, ghi lại | `_shown_outline` chỉ đòi dàn ý là lượt ngay trước; F5 không thêm hàng nào |

## Đạt khi

1. **S1 = S0 = S2** từng chữ: cùng số lượt, cùng thứ tự; mọi lời dàn ý cùng chữ; mọi khối cùng
   header, cùng số bước, cùng tên bước, cùng dấu `✓`, cùng dòng kết quả; cùng thẻ; câu mở (nếu có)
   và câu kể ở đúng chỗ cũ.
2. Khối lượt 2 của case 04 vẫn `Tạo đề trống` `— đề "<tên>"` → `Soạn câu hỏi` `— đã soạn 5/5
   câu`, **không** thành 7/7: con số là của lượt ấy, không đếm lại. Khối lượt 2 case 06 là
   `Soạn câu hỏi` `— đã soạn 7/7 câu`. Không dòng nào thành `— N câu bắt đầu soạn`.
3. Mỗi lượt Kriky một avatar; hai thẻ `Đã tạo đề "<tên>"` (case 04, 06) đều còn, chip
   `Chưa duyệt · chưa phát hành`; không thẻ hỏi lại nào hiện ra.
4. Sau A1 panel mở lại tự động, 7 câu, cùng chữ như S0; sau A2 bấm thẻ cuối ra cùng 7 câu.
5. Truy vấn đếm cho cùng `count`, `max` ở S0, sau A1, sau A2: đọc lại không ghi hàng nào.
6. Các lời dàn ý trên màn, từ trên xuống, mở đầu đúng như cột `dau` theo `sequence`; `ban` tăng
   dần 1, 2, … không sót bản nào (cả bản bị sửa vẫn còn trên màn).
7. Phần B: một lời dàn ý đạt (`huong-dan.md`), `ban` = bản cuối + 1, một mục `Câu 8` lũy thừa, bài
   nguồn là mục lũy thừa (gần chữ một dòng `labels` của `read_section`). Mở lại tab: dàn ý y S3 và
   là lượt cuối trên màn.
8. Sau `oke`: không câu mở cố định, **một** bước soạn (không `Tạo đề
   trống`), `— đã soạn 8/8 câu`, thẻ `Đã tạo đề "<tên>"`. F5: khối ấy y nguyên, panel 8 câu, câu
   1–7 cùng chữ S0. Truy vấn dàn ý: hàng mới `viec` = `more`, `muc` = 1.

## Không đạt khi

- Một dàn ý mất, đổi chữ, hay đổi chỗ với một lượt khác sau F5 hay sau rail.
- Một bước mất, thêm, đổi dấu; dòng `— đã soạn …` đổi số; một thẻ mất hay hiện hai lần.
- Đoạn chat trắng khi quay lại từ rail; panel mở lại ra số câu khác đề.
- Truy vấn đếm đổi sau F5 hay sau rail.
- Sau khi mở lại tab, `oke` không được nhận là đồng ý (dàn ý mới, hỏi lại, không soạn).
- Lượt 2 phần B mở đề mới, hay câu 1–7 đổi chữ.
- Vi phạm một trong tám luật chung của `huong-dan.md`.

## Ghi lại

- S0 và mọi chỗ S1, S2 khác S0 (chép nguyên văn hai phía). Không khác thì ghi "trùng".
- Tên mọi bước trong mỗi khối lúc chạy và sau F5; đánh dấu chỗ nào khác nhau.
- Đầu ra hai truy vấn ở S0, sau A1, sau A2, và sau phần B.
- Phần B: nguyên văn dàn ý, nhánh bảng đã xảy ra, khối bước và câu kể lượt 2, chữ câu 8 trên panel.
