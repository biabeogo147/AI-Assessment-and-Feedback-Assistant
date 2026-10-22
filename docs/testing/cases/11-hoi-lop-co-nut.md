# 11. Hỏi lớp mơ hồ, chọn bằng nút

Nhóm: Tra lớp · Lượt model: ~6 · Chạy sau: không, nhưng **trước 09–10** (xem `huong-dan.md`)

## Cho người xem thấy gì

Giáo viên nói "lớp 12" trong khi có hai lớp khớp: Kriky không đoán, tra rồi hỏi lại bằng nút mang
đúng tên và sĩ số lớp thật do hệ thống đếm (ADR-23), và khi giáo viên bấm thì trả lời bằng dữ kiện
thật của đúng lớp ấy, không nhận xét bịa.

## Chuẩn bị

- Đã làm đủ phần *Chuẩn bị* chung trong `docs/testing/huong-dan.md`, **gồm bước 6 thêm lớp 12B**.
- **Đoạn chat mới**, không chip tài liệu nào đính kèm.
- Ghi lại sự thật trong database trước khi gõ (các case khác có thể đã phát hành thêm đề hay có
  bài nộp; tiêu chí dưới so với kết quả này, không so với seed):

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select c.name, count(s.id) as si_so from classes c join teachers t on t.id = c.teacher_id left join students s on s.class_id = c.id where t.teacher_code = 'GV-001' group by c.name order by c.name;"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select a.title, p.recalled_at from publications p join assessments a on a.id = p.assessment_id join classes c on c.id = p.class_id where c.name = '12A';"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) from attempts t join students s on s.id = t.student_id join classes c on c.id = s.class_id where c.name = '12A' and t.submitted_at is not null;"
  ```

  Ghi **N** = sĩ số 12A, **M** = sĩ số 12B, và các đề của 12A. Database không reset (`huong-dan.md`),
  nên N, M và số bài nộp là của lúc chạy; mọi chỗ dưới ghi `N`/`M` đọc theo truy vấn này. Có lớp
  thứ ba chứa "12" thì dừng — case cần đúng hai lớp khớp.

## Lời chat

Lượt 1 — gõ vào ô chat:

```
lớp 12 của mình dạo này sao rồi bạn
```

Lượt 2 — **bấm nút** `12A (N học sinh)` trên thẻ hỏi lại (không gõ). Bấm là gửi đúng chữ trên nút.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Lượt 1: bước `Xem các lớp — 2 lớp`, thẻ hỏi lại hai nút `12A (N học sinh)`, `12B (M học sinh)`, hàng `Khác…` | Bấm `12A (N học sinh)`. **Đạt** | Đúng đường ADR-23: model hỏi, BE dựng nút từ `candidates` |
| Hai nút đúng nhưng 12B đứng trước | Bấm nút 12A. **Đạt** | Model chép đúng tên chỉ đổi được thứ tự (`_choices`), không đổi tập nút |
| Chữ câu hỏi liệt kê sẵn "12A hay 12B" | Bấm nút 12A. **Đạt**, ghi lại | Skill dặn đừng liệt kê, nhưng tên đúng thì không hại |
| Câu hỏi hỏi *nội dung* ("muốn xem sĩ số hay kết quả?") mà nút vẫn là hai lớp | Bấm nút 12A. **Chấp nhận được** | Lỗi đã biết ở hậu ký ADR-23: câu hỏi sau `candidates` luôn mang nút dòng |
| Lượt 1 trả lời gộp cả hai lớp, không hỏi, số liệu khớp database | Dừng, không làm lượt 2. **Chấp nhận được** | Không chọn hộ lớp nào nên không sai lớp; nhưng case không chứng minh được nút |
| Lượt 1 chỉ nói về 12A (hay 12B) mà không hỏi | Dừng. **Không đạt** | Chọn một trong nhiều — đúng thất bại ADR-23 cấm |
| Lượt 1 hỏi lại **không** có bước `Xem các lớp` (không tra) | Dừng. **Không đạt** | Nút khi đó là chữ model, AGENT đòi đủ 3 nên dễ ra lớp bịa |
| Có nút không mang `(… học sinh)`, nút `12C`, hay nút là câu hỏi | Dừng. **Không đạt** | Nhãn BE luôn có sĩ số; thiếu nghĩa là chữ model đã thành nút |
| Lượt 1 hỏi bằng bong bóng thường, không thẻ, tên lớp trong chữ đúng | Gõ `12A nhé`. **Chấp nhận được** | Không đoán, nhưng mất phần lựa chọn từ dữ liệu; ghi lại |
| Lượt 2 hỏi lại muốn biết gì về 12A | Gõ `thì sĩ số với mấy bài kiểm tra của lớp ấy`. **Chấp nhận được** | Câu gốc mơ hồ cả về nội dung; lớp thì đã rõ |
| Lượt 2 hỏi lại lớp nào, hay bày lại hai nút | Dừng. **Không đạt** | Bấm một nhãn là đã trả lời xong (`_rows_in_play`) |
| Lượt 2 báo không tìm thấy lớp "12A (N học sinh)" | Dừng. **Không đạt** | Chữ nút do chính BE dựng; Kriky phải dùng id lớp đã tra ở lượt 1 |
| Lượt 2 chỉ nói sĩ số, không nhắc đề | **Chấp nhận được** | Dữ kiện đúng nhưng mỏng — điểm yếu đã đo của câu trả lời tra lớp |
| Lượt 2 nói điểm, nhận xét "các em làm tốt", khi chưa có bài nộp | **Không đạt** | Luật 2: con số và nhận xét không có trong kết quả tool |
| Lượt 2 nói "chưa em nào nộp bài" | **Đạt** nếu đếm bài nộp ở *Chuẩn bị* là 0 | Đúng `note` của `class_assessment_summary` |

## Đạt khi

Lượt 1:

- Đúng một lượt Kriky. Có khối bước với hàng `Xem các lớp — 2 lớp`, đánh `✓`.
- Một thẻ hỏi lại, câu hỏi hiện **một lần** (không vừa bong bóng vừa tiêu đề thẻ).
- Đúng hai nút: `12A (N học sinh)` và `12B (M học sinh)` — tên và sĩ số khớp truy vấn đầu tiên
  ở *Chuẩn bị*. Không nút thứ ba nào. Hàng cuối là `Khác…`.
- Không câu nào nói lớp nào "có vẻ đúng hơn", không số liệu về lớp nào.

Lượt 2:

- Bong bóng của giáo viên ghi đúng `12A (N học sinh)`.
- Kriky nói về **12A**: sĩ số N; đề đã phát hành cho lớp đúng tên trong truy vấn thứ hai. Nếu nói
  về bài nộp thì đúng con số truy vấn thứ ba, và điểm nếu có thì kèm thang "trên … câu", không thang 10.
- Không một chữ nào về 12B. Khối bước (nếu có) gồm các hàng tra lớp/đề như `Xem các đề của lớp`,
  `Xem kết quả một đề`, tất cả `✓`.

Cả hai lượt qua tám luật chung. Database, sau lượt 2:

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, kind, tool_name, tool_args->>'name' as ten, choices, left(text, 70) from teacher_turns where conversation_id = (select id from teacher_conversations order by started_at desc limit 1) order by sequence;"
```

- Có hàng `tool_call`/`tool_result` của `list_class` **trước** hàng `assistant` đầu tiên.
- Hàng `assistant` ấy có `choices` = `["12A (N học sinh)", "12B (M học sinh)"]` (thứ tự có thể
  đảo), không có `"Khác"`.
- Hàng `teacher` kế tiếp có text đúng `12A (N học sinh)`. Không hàng `plan`, `outline` nào.

## Không đạt khi

- Lượt 1 tự chọn một lớp, hay trả lời mà không tra (`list_class`) trước khi hỏi.
- Có nút một lớp không tồn tại (`12C`, `12A1`), sĩ số sai, nút thiếu `(… học sinh)`, nút là câu
  hỏi hay tên mục, hoặc thiếu hàng `Khác…`.
- Lượt 2 nói về 12B, trộn số của hai lớp, hay hỏi lại lớp nào.
- Lượt 2 đưa điểm, tỉ lệ, nhận xét học lực không có trong database; nói đề chưa phát hành; nêu đề
  không có ở truy vấn thứ hai.
- Có thẻ `Đã tạo đề`, bước `Tạo đề trống`, dàn ý, hay bước `✕`.
- Ký tự Markdown hay `$` nguyên văn, UUID (kể cả `class_id`) hay tên tool trên màn hình.

## Ghi lại

- Kết quả ba truy vấn ở *Chuẩn bị*.
- Nguyên văn câu hỏi lại ở lượt 1, chữ từng nút theo đúng thứ tự, và có hay không hàng `Khác…`.
- Nguyên văn câu trả lời ở lượt 2, và các hàng khối bước của nó.
- Nhánh nào trong bảng *Nếu Kriky rẽ* đã xảy ra; nếu phải gõ thêm câu cố định thì ghi cả lượt ấy.
- Kết quả truy vấn `teacher_turns`.
