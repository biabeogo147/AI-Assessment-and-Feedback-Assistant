# 13. Tài liệu scan

Nhóm: Tài liệu · Lượt model: ~6 (cộng vài lời gọi model của job dựng mục lục) · Chạy sau: 04 (tải tệp scan trước thì thư viện case 04 có hai cuốn)

## Cho người xem thấy gì

Một trang sách chụp lại, không có lớp chữ, vẫn dùng được: hệ thống tự OCR nó, chip nói thật từng
nấc mà không cần F5, và Kriky nói đúng tình trạng tệp ở mỗi lúc: chưa xong thì bảo chờ chứ không
soạn bừa, xong rồi thì dàn ý trỏ đúng bài in trên trang ấy và không bịa phần sách nó không có.

Lưu ý cho người chạy: tệp scan **không** ra *Không đọc được chữ*. Từ `mongo-content-store`, PDF
không có lớp chữ đi đường OCR (`ocr_handlers.probe_document`). *Không đọc được chữ* chỉ còn khi OCR
đọc hết mà không ra ký tự nào (một trang trắng, một ảnh không chữ). Tệp này có chữ, nên nó *sẵn
sàng*.

## Chuẩn bị

- Đã làm đủ phần *Chuẩn bị* của `huong-dan.md`, có bước 9 dựng `data/scan-mot-trang.pdf`: trang 5
  SGK Toán 6 tập 1, tức banner *CHƯƠNG I. TẬP HỢP CÁC SỐ TỰ NHIÊN* và đầu *Bài 1. TẬP HỢP*.
- Đủ sáu terminal, nhất là `document` và `index`: thiếu một trong hai thì chip treo.
- Tệp tải lên lần này **chưa** có trong ngăn TÀI LIỆU. Chưa có đường xoá tài liệu, nên từ lần chạy
  thứ hai chép tệp thành `data/scan-mot-trang-Cn.pdf` (`Cn` là mã vòng) và tải bản ấy; mọi truy vấn
  dưới lọc `filename like 'scan-mot-trang%'` lấy bản mới nhất.
- Bấm *Đoạn chat mới*. **Gõ sẵn lượt 1 vào ô nhập, chưa gửi.** Rồi bấm icon tải lên cạnh nhãn
  `TÀI LIỆU`, chọn `data/scan-mot-trang.pdf`. Thấy chip mới ghi *Đang xử lý…* trên rail thì nhấn
  Enter **ngay**.
- Từ plan `wave-1-small-fixes` (Tier 2 câu 8) tải lên **không** tự đính vào ô nhập, và chip đang xử
  lý không kéo được: lượt 1 đi **không chip**. Kriky chỉ biết có tệp mới qua lời giáo viên và
  `list_documents` (đổi 22/10/2026, bộ ca C1).

## Lời chat

Lượt 1 (gửi ngay sau khi tải lên, chip còn *Đang xử lý…*):

```
mình vừa up 1 trang sách chụp lại, soạn giúp mình 3 câu trắc nghiệm từ trang đó nha
```

Đợi chip trên rail mất dòng trạng thái và dòng meta in `… · 1 trang`. Không F5. Rồi **kéo chip
`scan-mot-trang.pdf`** vào ô nhập (dải trên ô ghi tên tệp kèm *Bỏ*).

Lượt 2 (chip đã đính):

```
file lên rồi đó, giờ soạn 3 câu từ trang đó được chưa
```

Dừng ở dàn ý, **không** gõ đồng ý: soạn câu theo sách đã có ở case 04.

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Chip đã *sẵn sàng* trước khi kịp gửi lượt 1 | Bỏ lượt 2, chấm lượt 1 theo *Đạt khi* 3–4. Ghi lại | Lượt 1 không còn đo được nhánh *đang xử lý* |
| Lượt 1: nói tệp vừa tải là **một cuốn khác** trong thư viện (vd cuốn của case 04), hay hỏi chọn giữa các cuốn đã sẵn sàng | Không đạt; vẫn chạy lượt 2 | Từ plan `tier-1` (27/10/2026), `list_documents` trả tệp đang đọc ở `processing`, kèm `note` dặn nói tệp chưa đọc xong |
| Lượt 1: hỏi môn hay khối, **có** nói tệp đang xử lý | Gõ `toán 6`. Chấp nhận được | Câu hỏi lại vô hại nếu đã nói thật về tệp |
| Lượt 1: hỏi lại hay hứa soạn mà **không** nhắc tệp | Không đạt | Giáo viên vừa nói đã tải tệp; Kriky phải tra (`list_documents`) hay nói chưa thấy, không lờ đi |
| Lượt 1: nêu dàn ý không sách, hay soạn đề | Không đạt | Giáo viên xin soạn *từ trang đó*; dòng prompt *đang xử lý* và việc gỡ `create_draft` chỉ có khi chip đính mà chưa dùng được (`teacher_chat.py`), lượt này không có chip |
| Lượt 1: nói *"mình không đọc được ảnh"*, bảo tải tệp khác | Không đạt, ghi lại | Sai sự thật: tệp đang được OCR, chờ là xong |
| Chip treo *Đang xử lý…* quá 2 phút | Dừng case, xem terminal `document` / `index` | Lỗi chuẩn bị. Sau 300 s chip ra *Xử lí lỗi. Hãy tải lại* (`document_stale_after_seconds`) |
| Chip ra *Không đọc được chữ* hay *Xử lí lỗi* | Rê chuột chép `title`, chạy truy vấn A. Không đạt | OCR đọc được trang này: ra chữ thì phải *sẵn sàng* |
| Lượt 2: hỏi môn, khối hay dạng câu | Gõ `toán 6, trắc nghiệm nhé`. Chấp nhận được nếu một lần | Trang không in môn; lượt 1 đã nói trắc nghiệm |
| Lượt 2: hỏi bài hay chương, nút là tên mục | Bấm nút có chữ `TẬP HỢP`. Chấp nhận được | Nhãn nút do BE dựng từ mục lục của tệp scan |
| Lượt 2: hỏi *"tài liệu nào"*, nút có cả cuốn của case 04 | Bấm `scan-mot-trang.pdf`. Chấp nhận được | Model gọi danh sách dù chip của lượt 2 đã đính |
| Lượt 2: nói tệp chưa có mục lục, không nêu dàn ý | Chấp nhận được, ghi lại, chạy truy vấn B | Cây một trang có thể rỗng; nói thật vẫn hơn bịa |
| Lượt 2: dàn ý theo bài của cuốn case 04 (Bài 2 trở đi) | Không đạt | Đọc nhầm cuốn, hay bịa phần sách tệp này không có |

## Đạt khi

1. **Chip** đi *Đang xử lý…*, có thể qua *Đang dựng mục lục…*, rồi mất dòng trạng thái, dòng meta
   in `<kích thước> · 1 trang`, **không F5**. Lúc còn đang xử lý, kéo chip vào ô nhập không được;
   sẵn sàng rồi thì kéo được.
2. **Lượt 1** là một lượt Kriky, không dàn ý, không thẻ đề; khối bước nếu có chỉ một hàng `Xem thư
   viện tài liệu`. Câu trả lời nói chưa thấy tệp vừa tải, hay tệp **đang được xử lý / chưa đọc
   được**, và nhờ chờ tệp sẵn sàng rồi nhắn lại -- không lấy cuốn khác thay. Không nói tệp
   hỏng, không kể nội dung trang.
3. **Lượt 2**: khối `Đã làm n bước` (n ≥ 2; các bước mang tên `Xem mục lục`, `Đọc sách — phần
   k/n: …`, cả lúc đang chạy), rồi một lời dàn ý đạt (`huong-dan.md`) cho 3 câu. Không bước
   `Tạo đề trống`, không thẻ đề.
4. **Mọi mục nêu bài nguồn** là một nút của tệp scan: `Bài 1. TẬP HỢP` hoặc `Chương I. …`, trang
   `(tr. 5)` hoặc `(tr. 1)`. Kiến thức các mục nằm trong Bài 1: tập hợp, phần tử, cách mô tả
   một tập hợp, kí hiệu thuộc / không thuộc. Không mục nào về cách ghi số, số La Mã, phép tính.
5. **Truy vấn A**: `scan-mot-trang.pdf`, `ready`, `page_count` = 1, `fault` rỗng.
6. **Truy vấn B**: hàng `teacher` của lượt 1 **không** mang chip (`chip_scan` = f), lượt 2 mang
   id tệp scan; lượt 1 có thể có `list_documents`, không `list_chapters` nào;
   lượt 2 có `list_chapters` rồi `read_section`, mọi `document_id` là tệp scan (`dung_tep` = t).

## Không đạt khi

- Chip đứng im tới khi F5, hay F5 mới thấy chip đổi.
- Lượt 1 có dàn ý, thẻ đề, hay câu nói đã đọc / đã soạn từ trang ấy.
- Lượt 1 bảo tệp không đọc được, gọi một cuốn khác là tệp vừa tải, hay im lặng về tệp.
- Lượt 2 nêu bài nguồn của cuốn case 04, hay kiến thức vượt khỏi Bài 1.
- Lượt 2 nói đã đọc *"cả chương I"* hay kể nhiều bài trong khi tệp chỉ có một trang.
- Vi phạm một trong tám luật chung của `huong-dan.md`.

## Ghi lại

- Các nấc chip theo thứ tự, và số giây từ lúc chọn tệp tới khi in `· 1 trang`.
- Nguyên văn câu Kriky ở lượt 1, và cả lời dàn ý lượt 2 (kèm mọi câu hỏi lại, kèm nút).
- Khối bước lượt 2: n, tên từng bước. Đầu ra truy vấn A và B.

Truy vấn (chạy trong PowerShell):

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select filename, state, page_count, pages_read, fault from documents where filename like 'scan-mot-trang%' order by uploaded_at desc limit 1;"
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, kind, tool_name, document_id = (select id from documents where filename like 'scan-mot-trang%' order by uploaded_at desc limit 1) chip_scan, tool_args->>'document_id' = (select id from documents where filename like 'scan-mot-trang%' order by uploaded_at desc limit 1) dung_tep, left(tool_result::text, 100) ket_qua from teacher_turns where conversation_id = (select id from teacher_conversations order by started_at desc limit 1) order by sequence;"
```
