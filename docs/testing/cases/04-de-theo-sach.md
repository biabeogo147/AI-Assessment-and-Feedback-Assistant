# 04. Đề theo sách

Nhóm: Ra đề bằng chat · Lượt model: ~14 · Chạy sau: không (case 06 và 14 chạy tiếp trên đoạn chat này)

## Cho người xem thấy gì

Kriky đọc đúng cuốn sách giáo viên đưa (mục lục rồi chữ từng phần), dàn ý trỏ đúng tên bài và trang
có thật trong sách, và chữ OCR thô của sách không đi thẳng vào câu hỏi: job soạn câu chỉ nhận mục dàn ý.

## Chuẩn bị

- Đã làm đủ phần *Chuẩn bị* của `huong-dan.md`. Chip `Kết nối tri thức Lớp 6 tập 1 (tr6-28).pdf`
  trong ngăn TÀI LIỆU ở trạng thái *sẵn sàng* (dòng meta có số trang). Chưa tải tệp scan của case 13:
  nó cũng lên *sẵn sàng* (OCR đọc được) và sẽ thành cuốn thứ hai trong thư viện.
- Bấm *Đoạn chat mới*. Chip tự đính lúc tải lên đã bị dọn khi đổi đoạn chat, nên phải đính lại.
- **Thao tác đính:** kéo chip của tệp từ rail, thả vào ô nhập (viền ô đổi màu lúc kéo qua). Phải
  thấy dải trên ô nhập ghi tên tệp kèm nút *Bỏ*. Rồi mới gõ lượt 1. Chip chỉ đi cùng câu ấy; lượt 2
  không cần đính lại.
- Không duyệt, không phát hành, không xoá đề sau case: case 06 và 14 dùng tiếp đề này.

## Lời chat

Lượt 1 (chip đã đính):

```
cho mình 5 câu toán chương 1 lớp 6 nhé, lấy trong sách này
```

Lượt 2 (chỉ khi lượt 1 ra dàn ý):

```
oke
```

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Hỏi lại chương nào, nút là tên chương | Bấm nút có chữ `Chương I`. Chấp nhận được nếu một lần | Hỏi thừa: sách chỉ có một chương và giáo viên đã nói. Hỏi lần hai: không đạt |
| Hỏi lại bài nào, nút là tên bài | Bấm `Khác…`, gõ `cả chương luôn`. Chấp nhận được | Phạm vi đã đủ; nút tên bài vẫn là nhãn BE dựng từ mục lục (ADR-27) |
| Hỏi môn, khối hay dạng câu | Gõ `toán lớp 6, trắc nghiệm nhé`. Chấp nhận được nếu một lần | Môn không đọc ra được từ tên tệp, nhưng câu đã nói "toán" |
| Hỏi xác nhận "soạn 5 câu chương 1 nhé?" trước khi có dàn ý | Gõ `ừ đúng rồi`. Chấp nhận được | Điểm yếu đã đo: hỏi xác nhận dù đủ dữ kiện |
| Gọi danh sách tài liệu dù đã có chip, rồi đọc đúng tệp | Không trả lời gì. Chấp nhận được | Thừa một bước, kết quả không đổi |
| Lời dàn ý có mục **không nêu** bài nguồn | Ghi lại, vẫn gõ `oke` cho case sau. Không đạt | BE từ chối mục không có `source_nodes` (`outline.validate`) nhưng không soi bài nguồn trong lời (ADR-30, đối chiếu nhẹ): thiếu là giáo viên không biết câu theo bài nào |
| Bài nguồn của mọi mục chỉ là `Chương I. …` | Gõ `oke`. Chấp nhận được, ghi lại | Nhãn thật, nhưng không trỏ tới bài |
| Năm mục cùng một bài (vd chỉ Bài 1) | Gõ `oke`. Chấp nhận được nếu truy vấn A cho thấy đã đọc hết các phần | Chia câu là lựa chọn sư phạm của giáo viên; sửa được bằng "câu 2 đổi sang …" |
| Truy vấn A: chỉ có `part` 1 trong khi `parts` > 1, `more` = true | Không đạt | `_read_before_outline` phải đọc tiếp tới hết phạm vi trước khi nêu dàn ý |
| Sau `oke` ra dàn ý mới hay hỏi lại | Gõ `oke` thêm một lần, ghi lại. Không đạt | `oke` khớp khuôn đồng ý: phải ra plan dựng từ dàn ý (`_approved_plan`) |
| Bước soạn ghi `dừng ở 4/5 câu` | Chấp nhận được nếu câu kết nói đúng con số đó | Job có thể hỏng sau khi thử lại; ghi `last_fault` |
| Dàn ý tổng khác 5 câu (lần chạy 15/10/2026: 10 câu sau một lượt hỏi lại) | **Không đạt.** Gõ `mình cần 5 câu thôi nhé`, đợi bản kế đúng 5 câu rồi mới `oke` — để case 06, 14 vẫn chạy được | Lượt hỏi lại làm model mất số câu; `_miscounted` chỉ so với `known` của lượt ấy |

## Đạt khi

1. **Lượt 1** là một lượt Kriky: khối `Đã làm n bước` (n ≥ 2), rồi một lời dàn ý đạt
   (`huong-dan.md`) cho 5 câu. Mở khối ra: các bước mang tên `Xem mục lục`, `Đọc sách` với dòng
   `— phần k/n: …` (có thể thêm `Xem thư viện tài liệu`, `Mở một chương`), và **lúc lượt đang
   chạy** các bước ấy đã hiện đúng tên và dòng ấy. Không bước `Tạo đề trống`, không thẻ đề.
2. **Mọi mục nêu bài nguồn** là bài hay mục **trong chương I** của tệp, gần chữ một dòng `labels`
   của truy vấn A. Nhãn dựng từ cây mục lục OCR nên có thể thiếu số bài hay sai dấu (đã thấy
   `CÁCH GHI SỐ TỰ NHIÊN (tr. 9–13)`, `2. SỐ LA MÂ (tr. 10–13)`): so với `labels`, không so với tên
   in trong sách.
3. **Truy vấn A:** đúng một `list_chapters` (có thể thêm `get_chapter`), rồi 1–5 `read_section` với
   `part` 1, 2, … liên tiếp, phần cuối `more` = false.
4. **Lượt 2:** không câu mở cố định, bước `Tạo đề trống` → `Soạn câu hỏi` (cùng tên lúc chạy)
   với dòng `— đã soạn 5/5 câu`, một thẻ
   `Đã tạo đề "Đề Kết nối tri thức Lớp 6 tập 1 (tr6-28)"` có `Chưa duyệt · chưa phát hành` — đề
   theo sách mang **tên tệp** bỏ đuôi (ADR-31), một dòng trên thẻ. Bấm thẻ: panel có 5 câu, câu k
   bám kiến thức của mục chứa câu k, toán dựng hình; tiêu đề panel cùng tên ấy.
5. **Truy vấn B:** `dung_sach` = t, `scope_nodes` không rỗng, 5 mục dàn ý mỗi mục có `source_nodes`;
   5 hàng `draft_items` `ready`, `outline_item` không rỗng.
6. **Truy vấn C** (trong vòng 1 giờ sau lượt 2): mỗi job in `item_knowledge`, không job nào có `focus_`.
7. Câu hỏi không mang rác OCR (từ dính như `sốtự`, ký tự lạ, câu cụt) và không chép nguyên một bài
   tập của sách kèm số bài kiểu `1.1.`.

## Không đạt khi

- Lượt 1 đã soạn câu, có thẻ đề, hay không có dàn ý.
- Một mục không nêu bài nguồn, hay nêu bài không có trong `labels` của truy vấn A.
- Không đọc mục lục, không đọc bài, đọc quá 5 phần, hay dừng đọc khi còn `more` = true.
- Lượt 2 ra dàn ý mới, hỏi lại, mở hai đề, hay số câu khác 5 mà câu kết không nói đúng.
- Tên đề không phải tên tệp (vd `Đề <nhãn bài> (tr. 6–28)`), hay vỡ hai dòng trên thẻ.
- Truy vấn C có `focus_`; một câu hỏi chứa đoạn chữ OCR lỗi.
- Vi phạm một trong tám luật chung của `huong-dan.md`.

## Ghi lại

- Nguyên văn cả lời dàn ý bản 1, và mọi câu hỏi lại nếu có (kèm nút).
- Khối bước lượt 1: n, tên từng bước. Khối bước lượt 2: tên bước, dòng kết quả, chữ thẻ.
- Stem của 5 câu, và mỗi câu bám mục nào. Đầu ra truy vấn A, B, C.

Truy vấn (A, B chạy trong PowerShell; C chạy trong Git Bash):

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, kind, tool_name, tool_args->>'nodes' nodes, tool_args->>'part' part, tool_result->>'parts' parts, tool_result->>'more' more, tool_result->'labels' labels from teacher_turns where conversation_id = (select id from teacher_conversations order by started_at desc limit 1) and tool_name in ('list_chapters','get_chapter','read_section') order by sequence;"
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select b.document_id = (select id from documents where filename like '%tr6-28%' limit 1) dung_sach, b.scope_nodes, x->>'questions' cau, x->'source_nodes' nguon, left(x->>'knowledge', 60) kien_thuc from draft_briefs b join assessments a on a.id = b.assessment_id, json_array_elements(b.outline::json) x where a.id = (select id from assessments order by created_at desc limit 1);"
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select ordinal, status, outline_item, last_fault from draft_items where assessment_id = (select id from assessments order by created_at desc limit 1) order by ordinal;"
```

```
for j in $(docker exec aiafa-postgres psql -U aiafa -d aiafa -At -c "select job_id from draft_items where assessment_id = (select id from assessments order by created_at desc limit 1)"); do docker exec aiafa-redis redis-cli --raw GET "arq:result:$j" | grep -a -o "item_knowledge\|focus_[a-z_]*" | sort -u | tr '\n' ' '; echo; done
```
