# Lần chạy 17/10/2026 (tối) trên Claude Haiku 5.5 — commit dba6bd0

- **Ngày:** 17/10/2026, 17:20–17:55. **Code:** `db-reset` lúc 17:20, BE và AGENT khởi động trên
  `dba6bd0` (đóng pha 5 của plan `backlog-tier-1`). Hai bản sửa Tier 1 vào giữa buổi, mỗi lần khởi
  động lại tiến trình đọc code mới:
  - 17:26, chỉ AGENT: brief của một câu kèm các câu đã có của đề (sau case 02);
  - 17:36, BE và AGENT: luật công thức của dàn ý (sau lần chạy đầu của case 04).

  Case 01 và 02 chạy trên code gốc. Case 03 và lần chạy đầu của case 04 chạy sau bản sửa thứ nhất.
  Lần chạy lại case 04, case 07, ca 16 và khối ĐÃ PHÁT HÀNH chạy sau cả hai bản sửa. Cả hai bản sửa
  commit cùng biên bản này.
  **Model:** `anthropic/claude-haiku-5-5`, `thinking=disabled`, `effort=low` (dòng `model=` trong log
  AGENT mỗi lần khởi động).
- **So với:** `2026-10-17-e8f7f9d-claude-haiku-5-5.md`, cùng model. Code khác ở plan
  `backlog-tier-1` (pha 1–5):
  - không còn câu mock;
  - lưới câu gần trùng trong một đề;
  - vá `brief`/`known`;
  - giờ địa phương ở khối ĐÃ PHÁT HÀNH;
  - lượt pha 2 đọc lại được ở tab mới;
  - hộp xác nhận bắt đầu bài và nộp lượt.
- **Phạm vi:** 01, 02, 03, 04, 07 và ca mới 16 (pha 6 của plan). Có thêm một lần kiểm khối ĐÃ PHÁT
  HÀNH trên đề seed. Sau `db-reset`, thêm lớp 12B, tải SGK.
- **Người chạy:** Claude, trên Chrome. Màn hình đọc bằng ảnh chụp và DOM; câu đề và lượt chữa đọc
  từ database; nguyên nhân các lần trả về đọc từ log BE và kết quả arq trong Redis.
- **Ảnh chụp:** 20 ảnh, không đưa vào repo, giao cho người review cùng biên bản. Ở luồng học sinh,
  chụp ảnh qua CDP hết giờ nhiều lần (màn kết quả, màn trợ lý, cả một lần ở màn giáo viên). Trang
  vẫn chạy, `document.getAnimations()` chỉ thấy lớp phủ của extension. Các bước ấy đọc bằng
  `get_page_text` và database, không có ảnh.
- **Token và chi phí:** 755 nghìn token trên 28 hàng `teacher_turns` có `model_tokens`.
  - Từ pha 4, cột này **đã tính** cả các lần gọi bị BE trả về: chúng cộng vào hàng ghi kế tiếp.
  - Riêng lần chạy đầu của case 04 là 403 nghìn token cho một lượt không ra dàn ý (xem lỗi 2).
  - Thêm khoảng 22 job soạn câu và 2 câu biến thể, không có trong cột ấy.
  - Ước 0,12–0,16 USD theo tỉ lệ của biên bản 02ba28a, trong mức 0,10–0,20 đã cho phép.

## Kết quả

| Case | Kết quả | Một dòng |
| --- | --- | --- |
| 01 Xin đề mơ hồ | **Đạt** | Thẻ ba câu (khối, số câu, phạm vi), trả lời qua `Khác…`, gửi gộp một tin; dàn ý 5 câu cấp số cộng (một mục) |
| 02 Đề không tài liệu | **Chấp nhận được** | Dàn ý 3 mục; *"được rồi, soạn đi nhé"* ra plan; 4/5 câu, ô 4 `failed` sau 3 lần vì gần trùng câu 3 — lưới chặn đúng, gốc ở brief (sửa trong buổi, lỗi 1) |
| 03 Sửa dàn ý | **Đạt** | Bản 2 đổi đúng câu 3 (bài vé xem phim), các câu khác giữ; *"oke, soạn đi"* ra 4/4; ô 1 thử lại một lần vì trùng, lần sau khác |
| 04 Đề theo sách | **Chấp nhận được** | Lần đầu **không đạt**: dàn ý bị trả về 7 lần (lỗi 2). Chạy lại sau bản sửa: hỏi lại *bài nào* một lần (bấm `Khác…`, *"cả chương 1"*), dàn ý 5 mục mỗi mục nêu bài nguồn, 5/5 câu, đề mang tên tệp |
| 07 Đồng ý kèm điều kiện | **Đạt** | *"ok nhưng câu 2 đổi…"* ra bản 2, `draft_briefs` và `assessments` không đổi; *"ok, soạn đi"* ra 4/4 theo bản 2 |
| 16 Pha 2 ở tab mới | **Đạt** | Đầu màn `2 câu · 10 phút`; tab mới có dòng nhắc và *Làm tiếp lượt đang mở*; câu 1 sáng lựa chọn đã lưu; hộp nộp đếm đúng, *Quay lại làm tiếp* không nộp; `rounds_used` mỗi câu tăng 1 |
| Khối ĐÃ PHÁT HÀNH (đề seed) | **Đạt** | `Mở 16:20 · 17/10`, `Hết giờ thu hồi lúc 16:20 · 17/10` — giờ +07:00 (seed mở 09:20 UTC), khớp màn học sinh |

**Tổng:** 4 đạt · 2 chấp nhận được trên 6 case. Có thêm khối ĐÃ PHÁT HÀNH, đạt. Các mục kiểm của plan
đều đạt:

- không câu mock nào vào đề: 17 câu model soạn, đọc từ database; mọi lần hỏng đều có lý do trong
  log;
- không hai câu gần trùng trong một đề: lưới bắt 3 lần (02, 03, 07);
- *"oke"* sau dàn ý ra plan;
- xin 5 câu sau một lượt hỏi lại vẫn ra 5 (01, 04);
- câu biến thể pha 2 khác câu gốc.

## Sửa trong buổi (commit cùng biên bản)

1. **Brief của một câu không nêu các câu đã có của đề** (case 02).
   - Triệu chứng: ô 4 hỏng cả 3 lần. Đọc kết quả arq thì thấy cả 3 lần model viết lại
     $\frac{x}{12}=\frac{5}{8}$ của câu 3.
   - Lưới gần trùng ở BE chặn đúng, nhưng lần thử lại không cho model biết thêm gì, nên lần nào cũng
     ra lại câu ấy.
   - Sửa: `authoring._already_written` đưa tối đa 10 đề bài đã có (`banned_stems`) vào brief, kèm lời
     dặn không viết lại.
   - Sau bản sửa, case 03 và 07 mỗi case có một ô trùng ở lần đầu và ra câu khác ở lần thứ hai;
     case 04 không ô nào phải thử lại.
2. **Dàn ý bị trả về 7 lần trong một lượt** (lần chạy đầu của case 04, 403 nghìn token).
   - Model viết công thức lẫn chữ: *"Nếu $a<b$ và $b<c$ thì $a<c$"*, *"$a=bq+r$, $0\le r<b$"*.
   - Lời trả về của `outline.validate` chỉ nói chung chung, nên model viết lại cả dàn ý, sửa mục này
     thì hỏng mục khác.
   - Lý do xen kẽ *mục 2*, *mục 3*, nên luật *cùng lý do hai lần thì dừng* không bắt.
   - Sửa:
     - lời trả về nêu đúng công thức hỏng và cách viết lại;
     - BE dừng ở lần trả về thứ ba, lý do gì cũng tính (`_MOST_OUTLINE_REFUSALS`);
     - prompt và mô tả field `formulas` có ví dụ đúng và sai.
   - Chạy lại thì không bị trả về lần nào, câu 3 viết theo đúng mẫu mới.

## Lỗi thấy được (ghi `backlog.md`)

1. **Không có đường nào bắn lại một ô `failed`** (case 02, bước thêm *"có, soạn lại câu còn thiếu
   giúp mình nhé"*).
   - Model nêu dàn ý soạn thêm. BE đánh số từ câu 6 (sau 5 ô, kể cả ô hỏng), còn lời model nói câu
     4, nên bị trả về hai lần và lượt dừng ở `OUTLINE_REFUSED`.
   - `_RETRYABLE` chỉ có `retry`.
   - Tier 2: cần chọn giữa soạn lại ô hỏng và soạn thêm một câu mới.
2. **Hai câu cùng dạng trong một mục** (case 07): câu 3 và 4 đều là $A\setminus B$ của hai tập hữu
   hạn, khác số. Lưới gần trùng không bắt vì khác số liệu. Thuộc Tier 2 câu 19.
3. **Câu biến thể giữ nguyên bốn phương án của câu gốc** (ca 16, câu 2): *đồng biến* thành *nghịch
   biến*, $2x+1$ thành $-3x+5$, phương án vẫn là bốn khoảng cũ. Câu vẫn khác câu gốc, `validate_retry`
   cho qua đúng luật; dạng câu lặp lại quá sát. Tier 4.
4. **Lỗi chữ trong lời Kriky**: *"Để này"* thay cho *"Đề này"* (case 01). Tier 4.
5. **Dòng *"câu làm đúng được 0,5 điểm"* trong hộp nộp lượt là chữ in cứng** (ca 16), đã ghi ở Tier 2
   câu 20.

## Ghi chép theo case

- **01** (chat `bb7ed623…`)
  - Thẻ `Câu 1/3` khối, `2/3` số câu, `3/3` phạm vi. Trả lời *"Khác: lớp 11"*, *"5 câu"*, *"Khác:
    cấp số cộng"*.
  - Một bong bóng gộp đúng thứ tự, lượt hỏi đã qua hiện kèm nhãn.
  - Dàn ý một mục 5 câu (Tier 2 câu 6: gộp mọi câu vào một mục).
- **02** (`1adbddf1…`, đề *"Đề tỉ lệ thức và dãy tỉ số bằng nhau"*)
  - Dàn ý 3 mục (1–2, 3–4, 5), plan, 4/5 câu, câu kết nói đúng 4/5.
- **03** (`f949dad6…`, *"Đề hệ phương trình bậc nhất hai ẩn"*)
  - Bản 2 thay câu 3 thành bài vé xem phim, giữ các câu khác. Soạn 4/4.
- **04**
  - Lần đầu (`3f8bdf33…`): đọc sách 6 bước, mỗi bước có tên và dòng `— phần k/5`, rồi
    `OUTLINE_REFUSED`.
  - Lần hai (`eca63f49…`): đọc 2 bước, hỏi lại phần nào (10 nút tên bài + `Khác…`), đọc 5 bước, dàn
    ý 5 mục, *"oke"*, 5/5.
  - Đề *"Đề Kết nối tri thức Lớp 6 tập 1 (tr6-28)"* có 5 câu khác nhau: tập hợp, giá trị chữ số,
    bắc cầu, tính chất phân phối, luỹ thừa.
- **07** (`37b7ba8b…`)
  - Bản 1 có 2 mục. Bản 2 có 3 mục, câu 2 là giao, hợp của hai khoảng.
  - `draft_briefs` = 3 và `assessments` = 4, trước cũng như sau lời xin sửa. Câu 2 của đề:
    $A=[-2;\ 4]$, $B=(1;\ 6)$, tìm $A\cap B$.
- **16** (attempt `107f5169…`, lượt `99f4f2e5…`)
  - Pha 1 sai câu 1 và 2. Hộp *Bắt đầu làm bài?* hiện trước khi đồng hồ chạy.
  - Lượt: `started_at` 10:47:10Z, `ends_at` 10:57:10Z (10 phút), `submitted_at` 10:50:33Z.
  - Biến thể câu 1: đạo hàm $y=x^3-4x^2+5x$ (gốc $y=x^2+3x$). Biến thể câu 2: $y=-3x+5$ nghịch biến
    (gốc $y=2x+1$ đồng biến).
  - Kết quả: câu 1, 2 có `mark` 0,5 và `rounds_used` 1; các câu khác `mark` 1, `rounds_used` 0. Màn
    kết quả *"5,0 trên 6 câu"*.
  - Tab mới được thay bằng tab giáo viên: `sessionStorage` của tab ấy không có lượt này, nên giống một
    tab mới.
