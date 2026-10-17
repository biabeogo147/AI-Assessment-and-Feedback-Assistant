# 09. Duyệt, sửa, xoá câu trên panel đề

Nhóm: Duyệt đề · Lượt model: 0 · Chạy sau: 05 (`05-thay-mot-cau.md`, trên đề của case 02)

## Cho người xem thấy gì

Mọi việc không thu hồi được là cú bấm của giáo viên trên panel, không qua chat (ADR-05), và luật
ngân hàng câu hỏi (ADR-28) nói ra trên màn hình trước cú bấm: câu đã duyệt một lần thì xoá khỏi đề
vẫn còn trong ngân hàng, các câu sau dồn số, và không có gì xảy ra lén.

## Chuẩn bị

- Các truy vấn lọc theo `title = '<tên>'` chạy trong **Git Bash**: PowerShell 5.1 có thể làm
  hỏng chữ có dấu khi truyền sang `docker exec`, và truy vấn ra 0 dòng.
- Chạy tiếp **đúng đoạn chat của case 02 và 05**. Đề phải: 5 câu, `Chưa duyệt · chưa phát hành`.
  Lấy **tên đề** từ biên bản case 02 (không dùng "đề mới nhất": case khác có thể chen giữa).
- Không gõ gì vào ô chat trong cả case. Chụp trạng thái **trước**:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select id, state from assessments where title = '<TÊN>';"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select order_index, id, md5(stem) from questions where assessment_id = '<ID>' order by order_index;"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select b.question_id is null as da_go, q.order_index as cau, md5(b.stem), right(b.stem, 30) as duoi, b.approved_at > b.created_at as ghi_de from bank_questions b left join questions q on q.id = b.question_id where b.assessment_id = '<ID>' order by q.order_index nulls last;"
  ```

  Phải ra: `state = has_questions`, 5 dòng `order_index` 1–5, ngân hàng **0 dòng**. Đề đã
  `approved` thì dừng, ghi lại: case 05 hay ai đó đã duyệt trước.
- Ba truy vấn này gọi tắt là **Q-đề**, **Q-câu**, **Q-kho** ở dưới.

## Lời chat

Không lượt chat nào. Chuỗi thao tác, làm đúng thứ tự, nguyên văn:

1. Bấm thẻ `Đã tạo đề "<TÊN>"` ở khối cuối đoạn chat → panel mở bên phải.
2. Câu 1 → `Sửa` → tầng `Đề bài` (mở sẵn): đặt con trỏ **cuối** ô, gõ một dấu cách rồi:

   ```
   Chọn một đáp án đúng.
   ```

   → `Lưu`.
3. Chân panel → `Duyệt đề`.
4. Màn cài đặt phát hành → `Hoàn tác`.
5. Câu 2 → `Xoá` → đọc hộp → `Giữ lại`. Rồi câu 2 → `Xoá` lần nữa → `Xoá câu`.
6. Chân panel → `Duyệt đề`. **Dừng ở đây**: không `Hoàn tác`, không `Phát hành đề` — case 10
   cần đề đã duyệt.

Chạy Q-đề, Q-câu, Q-kho sau bước 2, 3, 4, 5 và 6.

## Nếu Kriky rẽ

Không có model nào chạy, nên "rẽ" ở đây là panel hay BE đi khác.

| Kriky làm gì | Trả lời / phán | Vì sao |
|---|---|---|
| `Lưu` bị từ chối (dòng đỏ dưới ô) dù chỉ thêm chữ vào đề bài | `Huỷ`, đi tiếp từ bước 3. **Không đạt** bước 2; chép nguyên văn lời từ chối | Câu model soạn đã qua `validate_question`; sửa tay đi qua đúng lưới ấy nên phải qua lại |
| Duyệt bị từ chối: `Còn N câu đang soạn…` | Đợi 1 phút, F5, mở lại panel, bấm lại. **Chấp nhận được** nếu lần hai duyệt được | Case 05 còn câu 3 chưa thu hoạch; BE không cho duyệt câu chưa đọc |
| Duyệt xong mà panel đứng ở nội dung + nút `Phát hành đề`, không có tấm `Cài đặt phát hành` | **Không đạt** | Chặng 6.5 đã bỏ; duyệt là sang thẳng cài đặt phát hành |
| Khối bước mọc một dòng `Duyệt đề` / `Bỏ duyệt` | **Không đạt** | Khối bước là việc của model; dòng ấy nói Kriky tự duyệt |
| Khối cuối có hai thẻ, hay mọc thẻ `Đã bỏ duyệt đề` | **Không đạt** | Một đề một thẻ: thẻ là cú bấm cuối cùng trên đề (`cardTurns`) |
| `Hoàn tác` khoá sẵn, có dòng lý do | **Không đạt**; chép nguyên văn | Đề chưa phát hành thì luôn lùi được |
| Hộp xoá nói `Câu này chưa có trong ngân hàng câu hỏi…` | **Không đạt nặng**; chạy Q-kho ngay | Lần duyệt bước 3 lẽ ra đã chép câu 2 vào kho (`in_bank`) |
| `Xoá câu` bị từ chối trong hộp (`Còn N câu đang soạn…`) | `Giữ lại`, đợi, F5, làm lại bước 5. **Chấp nhận được** | Lời từ chối của BE ở trong hộp, hộp không tự đóng |
| Bấm `Giữ lại` mà câu 2 vẫn mất | **Không đạt nặng** | Bấm Xoá chỉ mở hộp; chỉ `Xoá câu` mới xoá |

## Đạt khi

- **Bước 1–2:** panel 5 câu, mỗi câu có `Sửa` và `Xoá`; chân panel *Bạn duyệt xong mới phát hành
  được. Học sinh chưa nhìn thấy đề này.* + `Duyệt đề`. Lưu xong ô đóng, câu 1 kết bằng
  `Chọn một đáp án đúng.`, toán vẫn dựng hình; bốn câu kia không đổi. Q-câu: chỉ `md5` dòng 1 đổi.
- **Bước 3:** panel sang thẳng `Cài đặt phát hành`, có `Hoàn tác` đứng trên `Phát hành đề`; mọi
  thẻ câu **mất** `Sửa` và `Xoá` (biến mất, không phải khoá xám) — sửa chữ đề đã duyệt không có
  đường bấm. Khối cuối đoạn chat: đúng một thẻ `Đã duyệt đề "<TÊN>"`, chip
  `Chưa phát hành cho học sinh`. Q-đề `approved`; Q-kho **5 dòng**, đủ `cau` 1–5, `ghi_de = f`,
  dòng câu 1 có `duoi` kết bằng `Chọn một đáp án đúng.` (kho chép bản đã sửa, lúc duyệt).
- **Bước 4:** panel về nội dung, `Sửa`/`Xoá` trở lại, chân panel `Duyệt đề`; thẻ khối cuối về
  `Đã tạo đề "<TÊN>"` · `Chưa duyệt · chưa phát hành`, vẫn **một** thẻ. Q-đề `has_questions`;
  Q-kho **y hệt** bước 3 (bỏ duyệt không đụng ngân hàng).
- **Bước 5:** hộp tiêu đề `Xoá câu 2 khỏi đề?`, lời dẫn nguyên văn:
  *Câu này đã lưu vào ngân hàng câu hỏi từ lần duyệt trước. Xoá ở đây chỉ gỡ nó khỏi đề này — bản
  trong ngân hàng vẫn giữ nguyên. Các câu sau dồn số lên.* Hai nút `Giữ lại`, `Xoá câu`. Sau
  `Giữ lại`: vẫn 5 câu, Q-câu như bước 2. Sau `Xoá câu`: hộp đóng, dòng meta đầu panel bắt đầu
  `4 câu ·`, thẻ đánh `Câu 1`–`Câu 4` liền; chữ câu 2 mới là chữ câu 3 cũ. Q-câu: 4 dòng
  `order_index` 1–4, `id` cũ của câu 3, 4, 5 nay ở 2, 3, 4. Q-kho: vẫn **5 dòng**, một dòng
  `da_go = t`, `cau` rỗng, `md5` bằng `md5` câu 2 ở Q-câu bước 2. Q-đề vẫn `has_questions`.
- **Bước 6:** như bước 3, nhưng Q-kho: 4 dòng `cau` 1–4 có `ghi_de = t` (duyệt lại ghi đè), dòng
  `da_go = t` giữ `ghi_de = f` (không ai đụng). Số dòng kho vẫn 5, không dòng trùng.
- Mỗi cú bấm cổng để lại đúng một biên bản, theo thứ tự:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, tool_name from teacher_turns where tool_name like 'teacher.%' and tool_args->>'assessment_id' = '<ID>' order by sequence;"
  ```

  Ra đúng `teacher.approve`, `teacher.unapprove`, `teacher.approve`.

## Không đạt khi

- Có cú bấm nào đổi dữ liệu mà không qua một nút có chữ nói rõ việc (vd `Xoá` xoá luôn, không hộp).
- Sau bỏ duyệt, Q-kho mất dòng hay đổi nội dung; sau xoá, Q-kho mất dòng của câu đã xoá.
- Đề sau xoá có lỗ số (`1, 3, 4, 5`), hay panel vẫn hiện 5 câu, hay `Câu 2` vẫn là chữ cũ.
- Đề còn `Sửa`/`Xoá` khi đã duyệt; hay `Lưu` của bước 2 làm đổi câu khác ngoài câu 1.
- Duyệt lại sinh dòng kho thứ sáu (bản trùng) thay vì ghi đè.
- Kết thúc case mà Q-đề không phải `approved` (case 10 không chạy được).
- Bất kỳ luật nào trong tám luật chung bị phá trên phần chat còn hiện.

## Ghi lại

- Q-đề, Q-câu, Q-kho sau từng bước 2–6, dán thẳng; và truy vấn `teacher_turns`.
- Nguyên văn chữ câu 1 trước/sau sửa, chữ câu 2 bị xoá, và chữ câu 2 mới.
- Nguyên văn tiêu đề + lời dẫn của hộp xoá; chữ thẻ khối cuối sau bước 3, 4, 6.
- Mọi lời từ chối gặp phải (dòng đỏ, `Còn N câu…`), nguyên văn, và bước nào.
