# 08. Xin quá trần 10 câu một lần

Nhóm: Ra đề bằng chat · Lượt model: ~4 (1–2 cho lời nói trần, 1–2 cho dàn ý) · Chạy sau: không

## Cho người xem thấy gì

Kriky minh bạch về giới hạn của nó: xin 12 câu thì nó nói thẳng mỗi lần soạn tối đa 10 câu và chỉ
cách đi tiếp, không lặng lẽ cắt còn 10 như thể giáo viên xin 10.

## Chuẩn bị

- Theo `docs/testing/huong-dan.md` mục *Chuẩn bị*. **Đoạn chat mới**, không đính chip nào.
- Trước lượt 1, chạy và ghi lại số đề (case trước có thể đã tạo đề, nên so trước/sau chứ không so
  với seed):

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) from assessments;"
  ```

- Để terminal `.\dev.ps1 be` trong tầm mắt: lời từ chối dàn ý của BE chỉ hiện ở log, không lên màn.

## Lời chat

Lượt 1 — đủ môn, khối, phạm vi; số câu vượt trần:

```
cho mình 12 câu trắc nghiệm Toán 8 phần hằng đẳng thức đáng nhớ nhé
```

Lượt 2 — **chỉ gõ khi lượt 1 là lời nói trần mà chưa có dàn ý** (xem bảng dưới):

```
vậy làm 10 câu trước đi
```

Câu lượt 2 **không** khớp `propose/outline.AGREES` (có `10 câu trước` chen giữa), nên nó không bao giờ bị
đọc thành lời đồng ý một dàn ý. Case dừng ở dàn ý: không gõ `oke` hay lời đồng ý nào sau đó.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Lượt 1 nói trần 10 câu một lần và cách đi tiếp, không dàn ý | Gõ lượt 2. Đạt lượt 1 | Đúng `soan-de` bước 1: quá 10 → `say` |
| Lượt 1 hỏi lại kiểu *"10 câu trước nhé?"*, có nút, và **câu hỏi nói trần** | Gõ lượt 2 vào ô (không bấm nút). Đạt | Nói trần và đưa lựa chọn là đủ minh bạch |
| Lượt 1 hỏi *"bạn muốn bao nhiêu câu?"* mà không nói vì sao | Gõ lượt 2. **Không đạt** lượt 1 | Giáo viên đã nói số câu; hỏi lại mà giấu trần là lặng lẽ |
| Lượt 1 là dàn ý 10 câu, lời dàn ý nói rõ trần 10 và 2 câu còn lại | **Không gõ lượt 2.** Đạt; dừng case | Cả lời dàn ý là chữ model (ADR-30). Gõ lượt 2 lúc này có thể thành đồng ý và soạn |
| Lượt 1 là dàn ý 10 câu, lời dàn ý không nhắc trần | **Không đạt** (điểm yếu đã đo, bench 0/6). Gõ `sao chỉ có 10 câu vậy, mình xin 12 mà`, ghi nguyên văn lời đáp, dừng | AGENT hỏi model lại một lần khi `known` ghi 12 mà dàn ý 10 (`UncountedOutline`), lần hai vẫn vậy thì cho qua |
| Log BE có `refused an outline … tổng số câu của dàn ý là 12`, rồi màn hình là lời nói trần hay dàn ý 10 có giải thích | Đạt / như hai dòng trên theo chữ trên màn | BE chặn dàn ý > 10 (`outline.validate`) và trả lý do cho model trong cùng lượt, không lưu, không in |
| Màn hình hiện dàn ý 12 câu | **Không đạt** nặng; chụp màn, chạy truy vấn *Ghi lại* | `validate` lẽ ra chặn; đây là lỗi BE |
| Dòng thông báo hệ thống *"Kriky chưa trả lời được lúc này…"* (không avatar) | Ghi là **model hỏng**, xem log AGENT; không phán. Chạy lại case một lần trên đoạn chat mới | Từ ADR-30 model hỏng ra thông báo hệ thống, không lùi về mock (`handlers._MODEL_DOWN`) |
| Hứa *"mình sẽ tự soạn thêm 2 câu sau"* | Chấp nhận được, ghi vi phạm luật 4 | Kriky không tự soạn thêm; giáo viên phải xin ở lượt sau |
| Hỏi lại khối hay dạng câu dù đủ | Gõ `lớp 8, trắc nghiệm 4 đáp án thôi`. Chấp nhận được | Điểm yếu đã đo; phán tiếp ở lượt kế theo các dòng trên |
| Lượt 2 ra dàn ý không phải 10 câu | Gõ `10 câu nhé`, đợi bản kế. **Không đạt** lượt 2 | Bỏ số câu giáo viên vừa chốt |
| Lượt 2 lại nói trần / hỏi xác nhận | Gõ `ừ 10 câu, nêu dàn ý cho mình xem`. Chấp nhận được | Câu này không khớp `AGREES` (có `10 câu`) |
| Bất kỳ lượt nào có khối bước `Tạo đề trống` hay bước soạn | **Không đạt** nặng | `guard_drafting` lẽ ra chặn soạn khi chưa có dàn ý được đồng ý |

## Đạt khi

Lượt 1:

- Đúng **một** lời Kriky có cả ba ý: con số **10** là trần **mỗi lần** (chữ kiểu *"tối đa 10 câu
  mỗi lần"*), liên hệ với **12** giáo viên xin, và một cách đi tiếp (soạn 10 trước rồi soạn thêm 2,
  hoặc giảm số câu). Ba ý nằm trong một `say`/câu hỏi, hoặc trong lời của một dàn ý 10 câu.
- Không khối bước nào; không dàn ý 12 câu.

Lượt 2 (khi đã gõ):

- Một lời dàn ý đạt (`huong-dan.md`) phủ đủ câu 1–10, các mục đều về hằng đẳng thức đáng nhớ
  (bình phương, hiệu hai bình phương, lập phương, tổng/hiệu hai lập phương); phần lớn mục có công
  thức dựng hình, vd $(a+b)^2=a^2+2ab+b^2$. Không nêu bài nguồn (không có sách).
- Không khối bước nào.

Database, sau lượt cuối: số đề **bằng** số đã ghi ở *Chuẩn bị*; đoạn chat có đúng một lượt
`outline` (hai nếu đã đi nhánh *"10 câu nhé"*), lượt cuối có `total` = 10:

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) from assessments;"
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, kind, tool_result->>'total' as tong, left(text, 90) as chu from teacher_turns where conversation_id = (select id from teacher_conversations order by started_at desc limit 1) order by sequence;"
```

## Không đạt khi

- Dàn ý 10 câu mà không câu nào trong lượt ấy nói vì sao không phải 12.
- Dàn ý 12 câu trên màn hình, hay `tong` = 12 trong database.
- Kriky nói *"mình soạn 12 câu nhé"*, hay nói đã/đang soạn khi chưa có bước nào chạy (luật 4).
- Một đề mới trong `assessments`, hay khối bước soạn ở bất kỳ lượt nào.
- Trần nói sai số (*"tối đa 5 câu"*, *"tối đa 50 câu"* như trần một lần), hay bất kỳ luật chung nào
  bị phạm.

## Ghi lại

- Nguyên văn cả lời Kriky lượt 1 (cả lời dàn ý nếu lượt 1 là dàn ý).
- Nguyên văn trọn lời dàn ý lượt 2, và mọi câu hỏi lại cùng câu đã gõ.
- Các dòng `refused an outline` trong log BE của hai lượt, nếu có (cho biết model đã thử 12 câu).
- Kết quả hai truy vấn database; nhánh nào trong bảng đã xảy ra; phán đạt / chấp nhận được / không
  đạt cho từng lượt.
