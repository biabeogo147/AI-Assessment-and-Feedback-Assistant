# 03. Sửa một mục dàn ý

Nhóm: Ra đề bằng chat · Lượt model: ~3 · Chạy sau: không

## Cho người xem thấy gì

Giáo viên lái kế hoạch ra đề bằng lời thường: nói "câu 3 đổi thành …" thì Kriky sửa đúng mục ấy,
giữ nguyên các mục khác, và đề được soạn theo bản đã sửa chứ không theo bản đầu (ADR-29).

## Chuẩn bị

- Đoạn chat **mới**, không đính chip. Không chạy tiếp case 02.
- Seed như `huong-dan.md` (lớp 12A, 12B). Case không dùng lớp nào, không dùng sách.
- Lời chat cố ý không có chữ "sách", "tài liệu", "file": có chữ ấy thì Kriky được mời mở thư viện
  (`propose._LIBRARY`) và case thành case khác.

## Lời chat

Lượt 1 — xin đề, đủ môn (suy từ phạm vi), khối, phạm vi, số câu:

```
Soạn giúp mình đề 15 phút Toán lớp 9, hệ phương trình bậc nhất hai ẩn, 4 câu nhé
```

Lượt 2 — sau dàn ý bản 1, sửa đúng một mục, không nhắc gì tới các câu khác:

```
câu 3 đổi thành bài toán thực tế đi, kiểu mua vé xem phim người lớn với trẻ em ấy, lập hệ rồi giải
```

Lượt 3 — sau dàn ý bản 2, đồng ý:

```
oke, soạn đi
```

Trước khi gõ lượt 3, **chép nguyên văn cả bản 1 và bản 2** vào biên bản để đối chiếu từng mục.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
|---|---|---|
| Lượt 1 hỏi lại dù đã đủ (độ khó, xác nhận phạm vi) | Gõ `mức trung bình thôi, bạn cứ ra dàn ý đi`; chấp nhận được, ghi câu hỏi | Điểm yếu đã đo; không phải điểm case này soi |
| Lượt 1 ra dàn ý khác 4 câu | Không đạt; dừng | Tổng phải bằng `question_count` đã ghi (`_miscounted`) |
| Câu 3 bản 1 đã là bài vé xem phim lập hệ | Không tính; ghi lại, chạy lại ở đoạn chat mới | Lời sửa không đổi gì thì không chứng minh được gì |
| Câu 3 bản 1 nằm trong mục gộp `Câu 2–3` | Bản 2 tách thành `Câu 2` + `Câu 3` là đạt, nếu câu 2 giữ ý | Sửa một câu của mục gộp buộc phải tách |
| Lượt 2 ra khối bước, soạn luôn | **Không đạt**; ghi biên bản và `backlog.md` | Dàn ý ngay trước là bản 1, nên BE soạn theo bản 1 (`guard_drafting` chỉ biết dàn ý đã hiện) |
| Lượt 2 chỉ nói một câu ("Được, mình đổi câu 3…"), không nêu dàn ý | Gõ `bạn gửi lại dàn ý đủ 4 câu mình xem đã`; chấp nhận được nếu lượt sau ra bản 2 đúng | Không gõ "oke": dàn ý không còn ở lượt ngay trước, BE sẽ từ chối soạn |
| Bản 2 đổi luôn câu 1, 2 hay 4 (kiến thức, dạng, công thức, cách làm khác) | Không đạt; không gõ "oke" | Prompt: "nêu lại outline ĐỦ mọi mục, chỉ sửa đúng chỗ họ nói" |
| Bản 2 diễn đạt lại câu 1, 2, 4 nhưng cùng ý | Chấp nhận được; chép cả hai bản của mục ấy | Ý giữ, chữ trôi — đáng theo dõi giữa các lần chạy |
| Bản 2 tổng khác 4 câu, hoặc câu 3 không phải bài vé xem phim | Không đạt; không gõ "oke" | Sửa sai chỗ, hay sửa thừa |
| Sau "oke, soạn đi" Kriky hỏi lại hay chỉ nói | Không đạt | "oke, soạn đi" khớp `_AGREES`; `_approved_plan` phải dựng plan từ chính bản 2 |
| Bước soạn dừng ở `k/4` | Chấp nhận được nếu câu đã ra theo bản 2 và câu nói khớp số trên khối | Job hỏng không phải điểm case này soi |

## Đạt khi

1. Lượt 1: một lời có `Dàn ý — 4 câu (bản 1)`, các mục phủ đủ Câu 1–4, kết bằng câu
   "Bạn đồng ý với dàn ý này chứ? …". Không khối bước nào.
2. Lượt 2: một lời có `Dàn ý — 4 câu (bản 2)`, nêu lại **đủ** mục (không chỉ mục 3). Không khối
   bước nào.
3. Đối chiếu từng mục bản 1 với bản 2:
   - `Câu 3 · …` là bài toán thực tế mua vé xem phim (người lớn, trẻ em), cách làm có lập hệ hai
     ẩn rồi giải; công thức (nếu có) trong `$…$` và dựng hình.
   - Câu 1, 2, 4: dòng kiến thức, `Công thức Kriky đề xuất`, `Cách làm` cùng ý với bản 1 (y hệt
     chữ là tốt nhất).
4. Lượt 3: khối bước `Tạo đề trống` → `Soạn câu hỏi` (tên khi lượt xong), dòng dưới bước soạn đếm tới
   "đã soạn 4/4 câu"; thẻ `Đã tạo đề "<tên>"` với `Chưa duyệt · chưa phát hành`.
5. Bấm thẻ, panel: đúng 4 câu; câu 3 là bài vé xem phim giải bằng lập hệ; câu 1, 2, 4 khớp kiến
   thức mục tương ứng của bản 2.
6. Database — hai dàn ý trong đoạn chat, và bước soạn ghi đã dùng **bản 2**:

   ```
   docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select kind, sequence, tool_result->>'version' as ban, tool_result->>'outline_version' as soan_theo, tool_result->>'total' as tong from teacher_turns where (kind='outline' or (kind='tool_result' and tool_name='start_drafting')) and conversation_id=(select id from teacher_conversations order by started_at desc limit 1) order by sequence;"
   ```

   Đúng: hai hàng `outline` bản 1 và bản 2 (tổng 4), và hàng `start_drafting` có `soan_theo` = 2.
7. Database — dàn ý đã đóng băng vào đề, chạy ngay sau case:

   ```
   docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select i.n, i.e->>'version' as ban, i.e->>'questions' as so_cau, left(i.e->>'knowledge', 80) as kien_thuc from (select outline::json as o from draft_briefs order by created_at desc limit 1) b, json_array_elements(b.o) with ordinality as i(e, n);"
   ```

   Đúng: mọi hàng `ban` = 2, tổng `so_cau` = 4, mục chứa câu 3 nói về vé xem phim; không hàng
   nào `ban` = 1.

## Không đạt khi

- Lượt 2 có khối bước, hay bất kỳ câu hỏi nào ra trước lượt 3.
- Bản 2 chỉ nêu mục 3, hay viết lại cả đề (câu 1, 2, 4 đổi kiến thức, dạng hoặc cách làm).
- Bản 2 khác 4 câu, hay tiêu đề không ghi `(bản 2)`.
- Câu 3 trên panel không phải bài vé xem phim, hay câu 1, 2, 4 trên panel theo bản 1 khác bản 2.
- `draft_briefs.outline` có mục `version` = 1, hay `soan_theo` khác 2.
- Kriky nói "đã soạn xong 4 câu" trong khi khối bước dừng ở `k/4`; hay khen câu hỏi nó không đọc.
- Vi phạm bất kỳ luật chung nào của `huong-dan.md` (Markdown, `$` nguyên văn, UUID, tên tool).

## Ghi lại

- Nguyên văn trọn dàn ý bản 1 và bản 2, đặt cạnh nhau; đánh dấu mục nào chữ y hệt, mục nào diễn
  đạt lại, mục nào đổi ý.
- Nguyên văn câu mở của lượt 2 và lượt 3, và mọi câu hỏi lại.
- Chữ trên khối bước lượt 3 (tên bước, dòng đếm) và chữ trên thẻ kết quả.
- Đề bài câu 3 trên panel, nguyên văn.
- Kết quả hai truy vấn database.
