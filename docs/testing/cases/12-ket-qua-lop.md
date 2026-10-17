# 12. Hỏi kết quả lớp: chỉ nói con số tra được

Nhóm: Kết quả · Lượt model: ~4 (ba lần tra, một câu trả lời) · Chạy sau: không, nhưng **trước 09–10** (xem `huong-dan.md`)

## Cho người xem thấy gì

Giáo viên hỏi bằng lời thường "các em làm thế nào rồi", Kriky tự tra lớp → đề → kết quả, rồi trả
lời bằng đúng những con số database đang giữ — ở đây là **chưa em nào nộp** — không bịa điểm, không
khen "các em làm khá tốt".

## Chuẩn bị

- Theo `docs/testing/huong-dan.md` mục *Chuẩn bị* (có cả lớp 12B). **Đoạn chat mới**, không chip.
- Seed (`seed.py`) cho: lớp 12A ba học sinh; đề "Kiểm tra 15 phút — Hàm số" **6 câu**, phát hành
  cho 12A (`published_at` = lúc seed chạy trừ 2 giờ, mở từ −1 tới +6 giờ); **không có bài làm,
  không có điểm nào**. Trước lượt 1, chạy và dán ba kết quả vào biên bản:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select c.name, count(s.id) as hoc_sinh from classes c left join students s on s.class_id = c.id group by c.name order by c.name;"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select a.title, a.state, (select count(*) from questions q where q.assessment_id = a.id) as so_cau, p.published_at, p.closes_at, p.recalled_at from publications p join assessments a on a.id = p.assessment_id join classes c on c.id = p.class_id where c.name = '12A';"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) as da_mo, count(t.submitted_at) as da_nop, (select count(*) from question_outcomes) as dong_diem from attempts t join students s on s.id = t.student_id join classes c on c.id = s.class_id where c.name = '12A';"
  ```

  Chờ: 12A 3, 12B 0; một dòng đề, `published`, 6 câu, `recalled_at` rỗng; `da_mo 0, da_nop 0,
  dong_diem 0`. Khác thế (một case trước đã phát hành thêm đề cho 12A) thì **chấm theo số đo
  được**, không theo dòng này, và ghi rõ trong biên bản.

## Lời chat

Lượt 1 — câu duy nhất:

```
bài kiểm tra 15 phút hàm số của 12A các em làm thế nào rồi
```

Đường đúng theo skill `lop-va-ket-qua`: `list_class` (name 12A) → `list_assessment` →
`class_assessment_summary`, rồi nói. Tool cuối trả về `assessment_title`, `question_count: 6`,
`submitted_count: 0`, `note: "chưa có học sinh nào nộp bài"` — **không** có điểm trung bình, không
mốc giờ, không gì về từng câu. Sĩ số 3 chỉ có từ `list_class`.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
|---|---|---|
| Ba bước ✓ rồi nói chưa em nào nộp | **Đạt** | Đúng đường skill |
| Bước đầu `Xem các lớp — 2 lớp` (không lọc tên) rồi tự đi tiếp với 12A | **Đạt**; ghi lại | Giáo viên đã gọi tên 12A, 12B không khớp; bench chấm thiếu `name` nhưng màn đúng |
| Hỏi lại lớp nào, nút `12A (3 học sinh)`, `12B (0 học sinh)` | Bấm `12A (3 học sinh)`. **Chấp nhận được** nếu sau đó đạt | Thừa một lượt (điểm yếu đã đo), không sai dữ liệu |
| Hỏi lại đề nào, dù 12A chỉ có một đề | Gõ `bài 15 phút hàm số ấy`. **Chấp nhận được** nếu câu hỏi chỉ nhắc đúng tên đề có thật | Thừa một lượt; giáo viên đã gọi tên đề và chỉ có một. Nêu tên đề không tồn tại là **không đạt** (luật 2) |
| Có bước ✕, rồi tự gọi lại đúng và trả lời đúng | **Không đạt** nếu dòng ✕ hiện chữ như `list_assessment`, `class_id`, `không có tool nào tên …`; ghi tách: câu trả lời đúng hay sai | Lý do từ chối của BE chở tên tool, FE in nguyên (`stepFor` → `why`): luật 7, lỗi sản phẩm → backlog |
| `Bạn có lớp 12A với 3 học sinh.`, `Mình tra được: …`, hay `Bạn đang dạy nhiều lớp. Bạn muốn xem lớp nào?` | **Không đạt**. Không gõ lại | Câu kiểu mock (`handlers.next_step`) -- từ ADR-30 model hỏng không lùi về mock nữa, nên câu này là chính model nói trần. Đúng hồi quy bench `tra-lop-ket-qua` 6/6 → 2/6 |
| Dòng thông báo hệ thống *"Kriky chưa trả lời được lúc này…"* (không avatar) | **Không đạt**. Không gõ lại | Model hỏng (ADR-30, ngoại lệ 1); terminal AGENT có `model could not propose a next step` |
| Dòng thông báo hệ thống *"Kriky tra mãi mà chưa ra câu trả lời gọn…"* (không avatar) | **Không đạt**. Không gõ lại | Chạm trần 8 bước của pha 1 (ADR-30, ngoại lệ 1) |
| Nói 12A chưa có bài kiểm tra nào | **Không đạt** | Trái truy vấn đề ở *Chuẩn bị* |
| Nói điểm trung bình (kể cả "0 điểm", "0/10"), "câu khó nhất", "các em làm tốt", hạn nộp | **Không đạt** | Không tool nào trả mấy thứ ấy (luật 2) |
| Hỏi "bạn có muốn mình nhắc các em nộp bài không" | **Không đạt** | Không có tool gửi gì cho học sinh (luật 4) |

## Đạt khi

- Một khối Kriky, **một** hàng avatar (luật 1). Khối bước, theo thứ tự, mọi hàng ✓:
  `Xem các lớp — 1 lớp` (hay `— 2 lớp`), `Xem các đề của lớp — 1 đề`, `Xem kết quả một đề`. Hàng cuối
  **không** có dòng kết quả — FE không có dòng cho tool này (`ActionCard.outcome`), đúng thiết kế.
  Thêm hàng `Xem một lớp — 12A, 3 học sinh` cũng đạt.
- Câu trả lời nằm **dưới** khối bước, gọi đúng tên đề, nói rõ **chưa có học sinh nào nộp bài** (hay
  0/3 em). Nếu nhắc số, chỉ được: 3 học sinh, 6 câu, 0 bài nộp, 1 đề — mỗi số có trong kết quả tool.
- Không đánh giá, không đoán vì sao chưa nộp, không mốc giờ, không câu nào về câu dễ hay khó.
- Không thẻ nào: tool đọc không lên thẻ (`STATE_OF`). Không ký tự Markdown nguyên văn, UUID hay tên tool (luật 5, 7).
- Database: mọi con số trong câu nói khớp ba truy vấn ở *Chuẩn bị*, và khớp chính kết quả tool:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, kind, tool_name, tool_args::text, left(tool_result::text, 300), left(text, 300) from teacher_turns where conversation_id = (select conversation_id from teacher_turns order by created_at desc limit 1) order by sequence;"
  ```

  Có `tool_result` của `class_assessment_summary` mang `"submitted_count": 0` và `"question_count":
  6`; các `tool_call` có `tool_name` không rỗng, `class_id`/`assessment_id` lấy từ kết quả bước
  trước (không id tự đoán).

## Không đạt khi

- Bất kỳ con số, nhận xét hay mốc giờ nào trong câu trả lời không có trong `tool_result` của lượt.
- Câu kiểu mock hay thông báo model hỏng (hai dòng của bảng trên), hay câu trần bước.
- Kriky trả lời mà không có bước `Xem kết quả một đề` ✓ nào — nói "chưa nộp" mà chưa tra là đoán
  trúng, không phải tra được.
- Dòng ✕ hay câu nói lộ tên tool, tên trường (`class_id`) hay UUID.
- Bất kỳ luật nào trong tám luật chung bị phá.

## Ghi lại

- Nguyên văn câu trả lời của Kriky, và từng hàng khối bước kèm dòng kết quả (✓/✕).
- Nhánh nào: thẳng / hỏi lại lớp / hỏi lại đề / có ✕ / model hỏng / trần. Model hỏng thì tìm trong
  terminal AGENT dòng `model could not propose a next step` và chép lỗi kèm theo.
- Kết quả ba truy vấn *Chuẩn bị* và truy vấn `teacher_turns`, dán thẳng.
- Mỗi con số Kriky nói, cạnh trường `tool_result` sinh ra nó; số nào không có nguồn thì đánh dấu.
