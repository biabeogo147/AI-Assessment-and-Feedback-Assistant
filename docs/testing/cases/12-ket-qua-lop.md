# 12. Hỏi kết quả lớp: chỉ nói con số tra được

Nhóm: Kết quả · Lượt model: ~4 (ba lần tra, một câu trả lời) · Chạy sau: không, nhưng **trước 09–10** (xem `huong-dan.md`)

## Cho người xem thấy gì

Giáo viên hỏi bằng lời thường "các em làm thế nào rồi", Kriky tự tra lớp → đề → kết quả, rồi trả
lời bằng đúng những con số database đang giữ — ở đây là **chưa em nào nộp** — không bịa điểm, không
khen "các em làm khá tốt".

## Chuẩn bị

- Theo `docs/testing/huong-dan.md` mục *Chuẩn bị* (có cả lớp 12B). **Đoạn chat mới**, không chip.
- Seed (`seed.py`) cho đề "Kiểm tra 15 phút — Hàm số" **6 câu**, phát hành cho 12A. Database không
  reset (`huong-dan.md`), nên 12A có thể đã thêm học sinh, thêm đề (kịch bản đầu-cuối phát hành *Hàm
  số Vn*) và có bài làm. Trước lượt 1, chạy và dán ba kết quả vào biên bản; mọi tiêu chí dưới **chấm
  theo số đo được ở đây**:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select c.name, count(s.id) as hoc_sinh from classes c join teachers t on t.id = c.teacher_id left join students s on s.class_id = c.id where t.teacher_code = 'GV-001' group by c.name order by c.name;"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select a.title, a.state, (select count(*) from questions q where q.assessment_id = a.id) as so_cau, p.published_at, p.closes_at, p.recalled_at from publications p join assessments a on a.id = p.assessment_id join classes c on c.id = p.class_id where c.name = '12A' and p.recalled_at is null;"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) as da_mo, count(t.submitted_at) as da_nop from attempts t join assessments a on a.id = t.assessment_id join students s on s.id = t.student_id join classes c on c.id = s.class_id where c.name = '12A' and a.title = 'Kiểm tra 15 phút — Hàm số';"
  ```

  Ghi **N** = sĩ số 12A, **D** = số đề của 12A (có `Kiểm tra 15 phút — Hàm số`, 6 câu), **K** =
  số bài đã nộp của đề ấy. Mọi chỗ dưới ghi `N`, `D`, `K` đọc theo ba truy vấn này.

## Lời chat

Lượt 1 — câu duy nhất:

```
bài kiểm tra 15 phút hàm số của 12A các em làm thế nào rồi
```

Đường đúng theo skill `lop-va-ket-qua`: `list_class` (name 12A) → `list_assessment` →
`class_assessment_summary`, rồi nói. Tool cuối trả về `assessment_title`, `question_count: 6`,
`submitted_count: K` (K = 0 thì kèm `note: "chưa có học sinh nào nộp bài"`) — **không** có điểm trung bình, không
mốc giờ, không gì về từng câu. Sĩ số N chỉ có từ `list_class`.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
|---|---|---|
| Ba bước ✓ rồi nói đúng K/N em đã nộp | **Đạt** | Đúng đường skill |
| Bước đầu `Xem các lớp — 2 lớp` (không lọc tên) rồi tự đi tiếp với 12A | **Đạt**; ghi lại | Giáo viên đã gọi tên 12A, 12B không khớp; bench chấm thiếu `name` nhưng màn đúng |
| Hỏi lại lớp nào, nút `12A (N học sinh)`, `12B (M học sinh)` | Bấm `12A (N học sinh)`. **Chấp nhận được** nếu sau đó đạt | Thừa một lượt (điểm yếu đã đo), không sai dữ liệu |
| Hỏi lại đề nào | Gõ `bài 15 phút hàm số ấy`. **Chấp nhận được** nếu câu hỏi chỉ nhắc đúng tên đề có thật (D > 1 thì hỏi lại là hợp lý) | Thừa một lượt khi D = 1; giáo viên đã gọi tên đề. Nêu tên đề không tồn tại là **không đạt** (luật 2) |
| Có bước ✕, rồi tự gọi lại đúng và trả lời đúng | **Không đạt** nếu dòng ✕ hiện chữ như `list_assessment`, `class_id`, `không có tool nào tên …`; ghi tách: câu trả lời đúng hay sai | Lý do từ chối của BE chở tên tool, FE in nguyên (`stepFor` → `why`): luật 7, lỗi sản phẩm → backlog |
| `Bạn có lớp 12A với N học sinh.`, `Mình tra được: …`, hay `Bạn đang dạy nhiều lớp. Bạn muốn xem lớp nào?` | **Không đạt**. Không gõ lại | Câu kiểu mock (`handlers.next_step`) -- từ ADR-30 model hỏng không lùi về mock nữa, nên câu này là chính model nói trần. Đúng hồi quy bench `tra-lop-ket-qua` 6/6 → 2/6 |
| Dòng thông báo hệ thống *"Kriky chưa trả lời được lúc này…"* (không avatar) | **Không đạt**. Không gõ lại | Model hỏng (ADR-30, ngoại lệ 1); terminal AGENT có `model could not propose a next step` |
| Dòng thông báo hệ thống *"Kriky tra mãi mà chưa ra câu trả lời gọn…"* (không avatar) | **Không đạt**. Không gõ lại | Chạm trần 8 bước của pha 1 (ADR-30, ngoại lệ 1) |
| Nói 12A chưa có bài kiểm tra nào | **Không đạt** | Trái truy vấn đề ở *Chuẩn bị* |
| Nói điểm trung bình (kể cả "0 điểm", "0/10"), "câu khó nhất", "các em làm tốt", hạn nộp | **Không đạt** | Không tool nào trả mấy thứ ấy (luật 2) |
| Hỏi "bạn có muốn mình nhắc các em nộp bài không" | **Không đạt** | Không có tool gửi gì cho học sinh (luật 4) |

## Đạt khi

- Một khối Kriky, **một** hàng avatar (luật 1). Khối bước, theo thứ tự, mọi hàng ✓:
  `Xem các lớp — 1 lớp` (hay `— 2 lớp`), `Xem các đề của lớp — D đề`, `Xem kết quả một đề`. Hàng cuối
  **không** có dòng kết quả — FE không có dòng cho tool này (`ActionCard.outcome`), đúng thiết kế.
  Thêm hàng `Xem một lớp — 12A, N học sinh` cũng đạt.
- Câu trả lời nằm **dưới** khối bước, gọi đúng tên đề `Kiểm tra 15 phút — Hàm số` (không lẫn với đề
  khác của 12A), nói đúng **K/N em đã nộp** (K = 0 thì nói chưa em nào nộp). Nếu nhắc số, chỉ được
  những số có trong kết quả tool: N học sinh, 6 câu, K bài nộp, D đề, và điểm nếu tool trả.
- Không đánh giá, không đoán vì sao chưa nộp, không mốc giờ, không câu nào về câu dễ hay khó.
- Không thẻ nào: tool đọc không lên thẻ (`STATE_OF`). Không ký tự Markdown nguyên văn, UUID hay tên tool (luật 5, 7).
- Database: mọi con số trong câu nói khớp ba truy vấn ở *Chuẩn bị*, và khớp chính kết quả tool:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, kind, tool_name, tool_args::text, left(tool_result::text, 300), left(text, 300) from teacher_turns where conversation_id = (select conversation_id from teacher_turns order by created_at desc limit 1) order by sequence;"
  ```

  Có `tool_result` của `class_assessment_summary` mang `"submitted_count": K` và `"question_count":
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
