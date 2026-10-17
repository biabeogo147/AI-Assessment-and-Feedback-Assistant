# 01. Xin đề mơ hồ

Nhóm: Ra đề bằng chat · Lượt model: ~2 · Chạy sau: không

## Cho người xem thấy gì

Giáo viên xin đề mà không nói môn, khối, phạm vi hay số câu: Kriky không đoán bừa, hỏi đúng những
thứ còn thiếu trong một lần — mỗi thứ một câu có nút riêng, đi từng câu rồi xem lại trước khi gửi
(ADR-32) — không mở đề rỗng nào, và khi đã đủ thì đưa ngay dàn ý để giáo viên duyệt.

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

Lượt 2 — trả lời **trên thẻ hỏi lại**, theo ba giá trị cố định: **lớp 11**, **cấp số cộng**,
**5 câu**. Ở mỗi câu của thẻ (`Câu k/n · <nhãn>`):

- có nút mang đúng giá trị của câu ấy (vd `Lớp 11`, `Cấp số cộng`, `5 câu`) thì bấm nút đó;
- không có thì bấm `Khác…`, gõ giá trị ấy (`lớp 11`, `cấp số cộng`, `5 câu`), bấm `Chọn`;
- câu hỏi môn thì chọn `Toán` (hay `Khác…` → `Toán`);
- rồi `Câu sau ›`; câu cuối là `Xem lại ›`. Ở màn *Kiểm tra lại trước khi gửi*, soát từng hàng rồi
  bấm `Gửi`.

Thẻ chỉ có một câu (thẻ cũ, không `Câu k/n`) thì gõ vào **ô chat chính**:

```
Toán lớp 11 nhé, phần cấp số cộng, tầm 5 câu thôi
```

Case dừng khi dàn ý hiện ra. **Không** gõ lời đồng ý — phần soạn là việc của case khác.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Lượt 1 ra thẻ nhiều câu: 2–3 câu, mỗi câu một mục thiếu với 3+ nút của riêng nó và `Khác…` | Trả lời trên thẻ, `Gửi`. **Đạt** | ADR-32: hỏi một lần, mỗi mục ghi ? một câu, tối đa 3 câu |
| Thẻ nhiều câu nhưng một câu có nút của mục khác (vd câu `Số câu` mà nút là `Lớp 10/11/12`) | Dùng `Khác…` cho câu ấy. **Chấp nhận được** | Nút lệch câu là lỗi model; `Khác…` vẫn trả lời được |
| Lượt 1 hỏi gộp mọi mục trong **một** câu (thẻ cũ), có 3+ nút cho một mục | Gõ lượt 2 vào ô chính. **Chấp nhận được** | Đúng hành vi trước ADR-32; nay skill dặn mỗi mục một câu |
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

- Đúng một lượt Kriky, một thẻ hỏi lại nêu cùng lúc các mục thiếu: ít nhất **khối, phạm vi, số
  câu** (môn có thể có).
- Không khối bước, không thẻ kết quả, không `✕`.
- **Thẻ nhiều câu** (`Câu 1/n`, n = 2 hay 3): mỗi câu một mục, nhãn ngắn sau `·`; nút của câu là giá
  trị bấm được của mục ấy (vd `Lớp 10`, `Lớp 11`, `Lớp 12`), không phải câu hỏi hay tên mục
  (`Khối lớp`); hàng cuối là `Khác…`.
- **Không bỏ câu:** chưa chọn gì thì `Câu sau ›` mờ, bấm không đi; `‹ Câu trước` ở câu 1 mờ. Lùi về
  câu trước, nút đã chọn vẫn sáng.
- Màn *Kiểm tra lại trước khi gửi*: đủ n hàng `nhãn / lựa chọn / Sửa`; bấm một hàng quay về đúng
  câu ấy.
- Sau `Gửi`: **một** bong bóng giáo viên dạng `Nhãn: trả lời · Nhãn: trả lời · …` theo thứ tự câu,
  thẻ hỏi lại biến mất.

Lượt 2:

- Một lời dàn ý đạt (`huong-dan.md`, *Một lời dàn ý đạt*) cho 5 câu, kiến thức đều thuộc cấp số
  cộng lớp 11 (số hạng tổng quát, công sai, tổng $n$ số hạng đầu…); công thức dựng hình, vd
  $u_n = u_1 + (n-1)d$. Không nêu bài nguồn nào (không có sách).
- Không khối bước, không thẻ.

Cả hai lượt qua tám luật chung. Database, sau lượt 2:

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) from assessments;"
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, kind, json_array_length(choices) as nut, json_array_length(tool_result->'questions') as cau, tool_result->>'total' as tong, left(text, 60) from teacher_turns where conversation_id = (select id from teacher_conversations order by started_at desc limit 1) order by sequence;"
```

- Số đề vẫn đúng bằng `N`.
- Các hàng theo thứ tự: `teacher`, `assistant` (thẻ nhiều câu: `cau` = 2 hay 3, `nut` = 0; thẻ cũ:
  `cau` trống, `nut` là số nút), `teacher` (chữ gửi gộp), `outline` với `tong` = 5 — có thể chen
  hàng `tool_call`/`tool_result` tra lớp (nhánh chấp nhận được ở bảng trên). Không hàng `plan` nào.

## Không đạt khi

- Lượt 1 không hỏi mà tự điền khối, phạm vi hay số câu (vd tự chọn lớp 12, 10 câu).
- Có đề mới: số đề lớn hơn `N`, hay thấy thẻ `Đã tạo đề`, bước `Tạo đề trống`, bước `✕`.
- Lượt 2 vẫn hỏi lại, hay hỏi xác nhận điều giáo viên vừa nói.
- Lượt 2 chạy plan soạn, hay có câu "đã soạn xong" (luật 2, 4).
- Dàn ý không phải 5 câu, hay có mục ngoài cấp số cộng (vd cấp số nhân, hàm số).
- Nút là câu hỏi hay tên mục; ký tự Markdown hay `$` nguyên văn, UUID hay tên tool trên màn hình.
- Thẻ nhiều câu cho sang câu sau khi chưa chọn, hay `Gửi` đi nhiều tin thay vì một; tin gộp thiếu
  nhãn hay sai thứ tự câu.
- Thẻ có hơn 3 câu.

## Ghi lại

- Nguyên văn lời mở ở lượt 1; với từng câu: nhãn, câu hỏi, chữ từng nút (hay ghi "không nút"), và
  câu ấy được trả lời bằng nút hay `Khác…`.
- Nguyên văn bong bóng gửi gộp.
- Nguyên văn cả dàn ý ở lượt 2, từ câu mở tới câu kết.
- Nhánh nào trong bảng *Nếu Kriky rẽ* đã xảy ra; nếu phải gõ thêm câu cố định thì ghi cả lượt ấy.
- `N` và số đề sau lượt 2; kết quả truy vấn `teacher_turns`.
