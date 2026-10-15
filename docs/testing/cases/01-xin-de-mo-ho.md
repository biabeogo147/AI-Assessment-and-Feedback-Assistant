# 01. Xin đề mơ hồ

Nhóm: Ra đề bằng chat · Lượt model: ~2 · Chạy sau: không

## Cho người xem thấy gì

Giáo viên xin đề mà không nói môn, khối, phạm vi hay số câu: Kriky không đoán bừa, hỏi đúng những
thứ còn thiếu trong một lần, không mở đề rỗng nào, và khi đã đủ thì đưa ngay dàn ý để giáo viên duyệt.

## Chuẩn bị

- Đã làm đủ phần *Chuẩn bị* chung trong `docs/testing/huong-dan.md`.
- **Đoạn chat mới**, không chip tài liệu nào đính kèm.
- Trước khi gõ, đếm đề và ghi số ấy lại (gọi là `N`):

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) from assessments;"
  ```

## Lời chat

Lượt 1 — gõ vào ô chat:

```
mai mình cần một cái đề kiểm tra cho các em, bạn soạn giúp mình nhé
```

Lượt 2 — gõ vào **ô chat chính** (không bấm nút nào trên thẻ hỏi lại, kể cả khi có nút đúng):

```
Toán lớp 11 nhé, phần cấp số cộng, tầm 5 câu thôi
```

Case dừng khi dàn ý hiện ra. **Không** gõ lời đồng ý — phần soạn là việc của case khác.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Lượt 1 hỏi gộp các mục thiếu, có 3+ nút cho một mục (vd lớp) và hàng `Khác…` | Gõ lượt 2 vào ô chính. **Đạt** | Quy trình `soan-de`: hỏi một lần, nút là giá trị cho MỘT mục ghi ? |
| Lượt 1 hỏi gộp nhưng không nút, hay ít hơn 3 nút | Gõ lượt 2. **Chấp nhận được** | AGENT đã đòi model thêm lựa chọn một lần; câu hỏi vẫn đúng |
| Lượt 1 không hỏi môn, ngầm hiểu là Toán | Gõ lượt 2. **Chấp nhận được** | Hệ thống chỉ soạn Toán; khối, phạm vi, số câu vẫn phải được hỏi |
| Lượt 1 chỉ hỏi một mục (vd "lớp mấy?") | Vẫn gõ lượt 2 nguyên văn. **Chấp nhận được** nếu lượt 2 ra dàn ý | Câu trả lời đủ đã che lỗi; ghi "hỏi từng mục" |
| Lượt 1 hỏi thêm độ khó, thời lượng hay tên đề | Gõ lượt 2. **Chấp nhận được** | Skill: các mục ấy hệ thống tự lo, không cần hỏi |
| Lượt 1 có câu kiểu "mình sẽ soạn ngay" trong câu hỏi lại | Gõ lượt 2. **Chấp nhận được** nếu không có khối bước, không thẻ | Điểm yếu đã đo; chép nguyên văn |
| Lượt 1 có khối bước tra lớp, các bước `✓` | Gõ lượt 2. **Chấp nhận được** | Skill dặn đề không thuộc lớp nào thì không tra lớp |
| Sau lượt 2 lại hỏi xác nhận, hay hỏi độ khó | `đúng rồi, bạn lên dàn ý luôn đi` (một lần). **Không đạt** | Skill: mục đã có thì dùng luôn, không hỏi để xác nhận. Gõ để ghi dàn ý có ra không |
| Lượt 1 tự chọn khối, phạm vi hay số câu rồi nêu dàn ý ngay | Dừng. **Không đạt** | Đúng thứ case này chứng minh là không xảy ra |
| Bất kỳ lượt nào có bước `✕`, bước `Tạo đề trống`, hay thẻ `Đã tạo đề` | Dừng. **Không đạt** | Hỏi lại không phải bước hỏng; plan chỉ `create_draft` thì BE không chặn, đề rỗng nằm lại |
| Lượt 2 ra khối bước soạn thay vì dàn ý | Dừng. **Không đạt** | ADR-29: dàn ý trước, soạn sau khi đồng ý |
| Dàn ý tổng khác 5 câu | Dừng. **Không đạt** | "tầm 5 câu" vẫn là 5; AGENT đối chiếu tổng với `question_count` đã ghi |

## Đạt khi

Lượt 1:

- Đúng một lượt Kriky, một câu hỏi lại nêu cùng lúc các mục thiếu: ít nhất **khối, phạm vi, số
  câu** (môn có thể có).
- Không khối bước, không thẻ, không `✕`.
- Nếu có nút: mỗi nút là một giá trị bấm được (vd `Lớp 10`, `Lớp 11`, `Lớp 12`), không phải câu
  hỏi hay tên mục (`Khối lớp`); hàng cuối là `Khác…`.

Lượt 2:

- Một câu mở ngắn, rồi `Dàn ý — 5 câu (bản 1)`; các mục `Câu k · …` (hay `Câu k–m · …`) cộng lại
  đúng 5, mỗi mục có `Cách làm:`, kiến thức đều thuộc cấp số cộng lớp 11 (số hạng tổng quát,
  công sai, tổng $n$ số hạng đầu…).
- Không có dòng `Theo:` (không có sách). Có `Công thức Kriky đề xuất:` thì công thức được dựng
  hình, vd $u_n = u_1 + (n-1)d$.
- Kết bằng đúng câu: `Bạn đồng ý với dàn ý này chứ? Muốn đổi câu nào, cứ nói, ví dụ: "câu 2 đổi
  sang …". Câu hỏi chỉ được soạn sau khi bạn đồng ý.`
- Không khối bước, không thẻ.

Cả hai lượt qua bảy luật chung. Database, sau lượt 2:

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) from assessments;"
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, kind, json_array_length(choices) as nut, tool_result->>'total' as tong, left(text, 60) from teacher_turns where conversation_id = (select id from teacher_conversations order by started_at desc limit 1) order by sequence;"
```

- Số đề vẫn đúng bằng `N`.
- Các hàng theo thứ tự: `teacher`, `assistant` (cột `nut` là số nút), `teacher`, `outline` với
  `tong` = 5 — có thể chen hàng `tool_call`/`tool_result` tra lớp (nhánh chấp nhận được ở bảng
  trên). Không hàng `plan` nào.

## Không đạt khi

- Lượt 1 không hỏi mà tự điền khối, phạm vi hay số câu (vd tự chọn lớp 12, 10 câu).
- Có đề mới: số đề lớn hơn `N`, hay thấy thẻ `Đã tạo đề`, bước `Tạo đề trống`, bước `✕`.
- Lượt 2 vẫn hỏi lại, hay hỏi xác nhận điều giáo viên vừa nói.
- Lượt 2 chạy plan soạn, hay có câu "đã soạn xong" (luật 2, 4).
- Dàn ý không phải 5 câu, hay có mục ngoài cấp số cộng (vd cấp số nhân, hàm số).
- Nút là câu hỏi hay tên mục; Markdown, `$` nguyên văn, UUID hay tên tool trên màn hình.

## Ghi lại

- Nguyên văn câu hỏi lại ở lượt 1 và chữ của từng nút (hay ghi "không nút").
- Nguyên văn cả dàn ý ở lượt 2, từ câu mở tới câu kết.
- Nhánh nào trong bảng *Nếu Kriky rẽ* đã xảy ra; nếu phải gõ thêm câu cố định thì ghi cả lượt ấy.
- `N` và số đề sau lượt 2; kết quả truy vấn `teacher_turns`.
