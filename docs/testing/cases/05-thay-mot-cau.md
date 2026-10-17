# 05. Thay một câu trong đề đã soạn

Nhóm: Ra đề bằng chat · Lượt model: ~5 · Chạy sau: 02 (`02-de-khong-tai-lieu.md`)

## Cho người xem thấy gì

Giáo viên chê một câu bằng lời thường, Kriky sửa đúng câu ấy: câu 3 đổi, bốn câu kia giữ nguyên
từng chữ, và vẫn chỉ một đề — sửa một chỗ không phá phần còn lại.

## Chuẩn bị

- Chạy tiếp **đúng đoạn chat của case 02**: bấm nó trên rail (case 03, 04 đã chạy chen giữa).
  Case 02 phải đạt: đề Toán
  lớp 7, tỉ lệ thức, đủ 5/5 câu, thẻ ghi `Chưa duyệt · chưa phát hành`. Đề đã duyệt thì nội dung
  khoá và case này không chạy được — dừng, ghi lại.
- Không chip nào đính. Bấm thẻ `Đã tạo đề "<tên>"` của case 02 để mở panel, đọc câu 3.
- Chụp trạng thái **trước** (giữ lại để so). Lấy id đề **của case 02** theo tên đã chép ở biên
  bản (không lấy đề mới nhất: case 03, 04 đã tạo đề sau nó), rồi số đề và từng câu. Chạy trong Git
  Bash — PowerShell 5.1 có thể làm hỏng chữ có dấu trong `'<tên>'`:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select id, title, state from assessments where title = '<tên>' order by created_at desc limit 1;"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select count(*) from assessments;"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select order_index, id, md5(stem) from questions where assessment_id = '<ID>' order by order_index;"
  ```

## Lời chat

Lượt 1 — gõ ngay sau khi đọc câu 3 trên panel:

```
câu 3 dễ quá, thay giúp mình câu khác về dãy tỉ số bằng nhau, kiểu bài chia tiền lãi theo số vốn góp ấy
```

Lượt 2 — chỉ gõ khi dàn ý vừa hiện có đúng một mục, mục `Câu 3`:

```
oke
```

Sau lượt 2: bấm thẻ mới để mở lại panel, đọc cả 5 câu.

## Nếu Kriky rẽ

Lượt 1 **không khớp** luật nhận việc của AGENT (`_REPLACES` chỉ bắt "thay/đổi/làm lại/soạn lại câu
N" liền nhau; ở đây là "thay giúp mình câu khác"). Nên dàn ý đúng việc ở lượt 1 là do **model** tự
ghi `for=replace, question=3`. Câu dự phòng dưới đây thì khớp luật, và AGENT tự sửa dàn ý.

| Kriky làm gì | Trả lời / phán | Vì sao |
|---|---|---|
| Dàn ý một mục `Câu 3` ngay lượt 1 | Gõ `oke`. **Đạt** | Đúng việc, model hiểu lời thường |
| Nêu lại dàn ý **cả đề** (mục `Câu 1` tới `Câu 5`) | KHÔNG gõ `oke`. Gõ dự phòng: `ko, chỉ thay câu 3 thôi, mấy câu kia giữ nguyên, câu 3 làm bài chia tiền lãi theo vốn góp nhé` → nếu ra mục `Câu 3` thì `oke`. **Chấp nhận được** | `oke` ở đây là mở đề mới. Câu dự phòng khớp `_REPLACES`, `_right_purpose` lấy đúng mục chứa câu 3 |
| Dàn ý `Câu 6` (hiểu là soạn thêm) | Như dòng trên. **Chấp nhận được** nếu lần hai ra `Câu 3` | Soạn thêm làm đề 6 câu, không thay gì |
| Dàn ý thay một câu khác số (`Câu 2`) | Như dòng trên. **Không đạt** nếu lần hai vẫn sai số | Luật AGENT không sửa số câu khi model đã ghi `replace` |
| Hỏi lại độ khó / dạng câu | `khó hơn chút, tầm vận dụng, vẫn trắc nghiệm 4 đáp án`. **Chấp nhận được** | Lời đã đủ dữ kiện; hỏi thêm là điểm yếu đã đo |
| Khối bước `Tạo đề trống` → `Soạn câu hỏi` sau `oke` | Dừng. **Không đạt** | Mở đề mới: đúng lỗi H4 cũ |
| Bước thay chạy luôn ở lượt 1, không dàn ý | **Không đạt** nếu câu 3 đổi; nếu bước bị từ chối rồi dàn ý hiện thì chấm theo dàn ý | ADR-29: không soạn trước khi đồng ý; BE chặn |
| Bước ghi `— câu 3 giữ nguyên: câu mới soạn không đạt`, thẻ `Không tạo được đề` | **Chấp nhận được** nếu Kriky nói rõ câu 3 vẫn là câu cũ và DB cho câu 3 cùng id | Câu mới hỏng thì câu cũ ở lại (`_keep_the_old`); nói "đã thay" là không đạt |
| Bước ghi `— câu 3 mới còn đang soạn` | Đợi 1 phút, bấm thẻ mở lại panel. **Chấp nhận được** nếu câu 3 rồi cũng đổi | Hết giờ đợi trước khi job về; `harvest` tráo lúc đọc đề |
| Bảo giáo viên tự sửa trên panel, không có dàn ý | **Không đạt** | Kriky có `replace_question` |

## Đạt khi

- Lượt 1: một lời dàn ý đạt (`huong-dan.md`) với đúng **một** mục, mục `Câu 3`, nói về dãy tỉ số
  bằng nhau / chia theo tỉ lệ. Database: hàng `outline` mới có `for` = `replace`, `version` = bản cuối
  của case 02 cộng một. Không khối bước nào chạy.
- Lượt 2: không câu mở cố định, khối bước **một** hàng `Thay một câu` (cùng tên lúc chạy), dòng
  dưới `— đã thay câu 3`; **không** có hàng `Tạo đề trống`. Thẻ
  `Đã tạo đề "<cùng tên đề case 02>"`, dòng `Chưa duyệt · chưa phát hành`.
- Câu kể của Kriky nói đã thay câu 3, không khen hay tả nội dung câu mới (luật 2).
- Panel: vẫn 5 câu; câu 1, 2, 4, 5 trùng từng chữ với lúc trước; câu 3 khác, đúng hướng giáo viên
  xin, toán dựng hình.
- Database, chạy lại ba truy vấn ở *Chuẩn bị*: số đề **không đổi**; dòng 1, 2, 4, 5 cùng `id` và
  cùng `md5`; dòng 3 khác cả `id` lẫn `md5`. Và ô soạn đã khép:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select ordinal, status, replacing, attempts, last_fault from draft_items where assessment_id = '<ID>' order by ordinal;"
  ```

  ô 3 `ready`, `replacing = f`. Đề chưa duyệt nên ngân hàng (ADR-28) không dính gì ở case này.

## Không đạt khi

- `oke` mở đề thứ hai (số đề tăng, khối bước có `Tạo đề trống`), dù đề cũ còn nguyên.
- Đề thành 6 câu, hay câu nào ngoài câu 3 đổi chữ, đổi số thứ tự, hay mất.
- Câu 3 đổi mà giáo viên chưa gõ `oke` (soạn trước khi đồng ý).
- Bước nói `đã thay câu 3` mà DB câu 3 vẫn id cũ; hay Kriky nói "đã thay" khi bước ghi giữ nguyên.
- Dàn ý một mục nhưng đánh số `Câu 1` thay vì `Câu 3`.
- Bất kỳ luật nào trong tám luật chung bị phá.

## Ghi lại

- Nguyên văn lượt 1 của Kriky: câu mở và cả khối dàn ý; ghi rõ nhánh nào (một mục ngay / cả đề /
  câu dự phòng đã phải gõ).
- Nguyên văn dòng dưới bước thay và câu kể cuối của Kriky.
- Chữ câu 3 trước và sau (chép từ panel).
- Kết quả ba truy vấn trước/sau và truy vấn `draft_items`, dán thẳng vào biên bản.
