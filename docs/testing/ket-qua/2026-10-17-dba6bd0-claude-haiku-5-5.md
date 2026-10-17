# Lần chạy 17/10/2026 (tối) trên Claude Haiku 5.5 — commit dba6bd0

- **Ngày:** 17/10/2026, 17:20–17:55. **Code:** `db-reset` lúc 17:20, BE và AGENT khởi động trên
  `dba6bd0` (đóng pha 5 của plan `backlog-tier-1`). Hai bản sửa Tier 1 vào giữa buổi, mỗi lần khởi
  động lại tiến trình đọc code mới:
  - 17:26, chỉ AGENT: brief của một câu kèm các câu đã có của đề (sau lượt soạn của case 02);
  - 17:36, BE và AGENT: luật công thức của dàn ý (sau lần chạy đầu của case 04).

  Case 01 và lượt soạn của case 02 chạy trên code gốc. Bước thêm của case 02 (17:27), case 03 và lần
  chạy đầu của case 04 chạy sau bản sửa thứ nhất. Lần chạy lại case 04, case 07, ca 16 và khối ĐÃ
  PHÁT HÀNH chạy sau cả hai bản sửa. Cả hai bản sửa commit ở `05bec8e`; ba chỗ review code tìm ra
  trong chúng sửa ở commit kế (danh sách câu đã có, xem *Sửa trong buổi*), sau khi thử tay đã xong.
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
  từ database; nguyên nhân các lần trả về đọc từ log BE và kết quả arq trong Redis. Bài đã chấm lại
  bởi một subagent đọc ảnh và database; phán dưới đây là bản sau khi chấm lại.
- **Ảnh chụp:** 23 ảnh, không đưa vào repo, giao cho người review cùng biên bản. Ở luồng học sinh,
  chụp ảnh qua CDP hết giờ nhiều lần (màn kết quả, màn trợ lý, cả một lần ở màn giáo viên). Trang
  vẫn chạy, `document.getAnimations()` chỉ thấy lớp phủ của extension. Các bước ấy đọc bằng
  `get_page_text` và database, không có ảnh: bước 3 và màn kết quả của ca 16.
- **Token và chi phí:** 755 nghìn token trên 28 hàng `teacher_turns` có `model_tokens`.
  - Từ pha 4, cột này **đã tính** cả các lần gọi bị BE trả về: chúng cộng vào hàng ghi kế tiếp.
  - Riêng lần chạy đầu của case 04 là 403 nghìn token cho một lượt không ra dàn ý (sửa 2).
  - Cột ấy không tính khoảng 22 job soạn câu, 2 câu biến thể, câu kết sau khi soạn (`_report`) và
    lời đặt tên đoạn chat (`_name_the_thread`).
  - Ước 0,12–0,16 USD theo tỉ lệ của biên bản 02ba28a, trong mức 0,10–0,20 đã cho phép.

## Kết quả

| Case | Kết quả | Một dòng |
| --- | --- | --- |
| 01 Xin đề mơ hồ | **Đạt** | Thẻ ba câu (khối, số câu, phạm vi), trả lời qua `Khác…`, gửi gộp một tin; dàn ý 5 câu cấp số cộng (một mục) |
| 02 Đề không tài liệu | **Không đạt** | Dàn ý 3 mục; *"được rồi, soạn đi nhé"* ra plan; nhưng 4/5 câu — bảng rẽ: *dừng ở 4/5 là không đạt tiêu chí 5/5*. Ô 4 `failed` sau 3 lần vì gần trùng câu 3; lưới chặn đúng, gốc ở brief (sửa 1). Câu kết nói đúng 4/5 |
| 03 Sửa dàn ý | **Chấp nhận được** | Bản 2 đổi đúng câu 3 (bài vé xem phim); câu 1–2 và câu 4 diễn đạt lại cùng ý (câu 4 bỏ *"theo tham số…"*); *"oke, soạn đi"* ra 4/4 |
| 04 Đề theo sách | **Không đạt** trên `dba6bd0` | Dàn ý bị trả về 7 lần (sửa 2). Chạy lại sau bản sửa: **chấp nhận được** — hỏi lại *bài nào* một lần, đọc đủ 5 phần, dàn ý 5 mục mỗi mục nêu bài nguồn, 5/5 câu, đề mang tên tệp; **lệch kịch bản**: gõ *"cả chương 1, rải đều các bài"* thay cho `cả chương luôn` |
| 07 Đồng ý kèm điều kiện | **Chấp nhận được** | *"ok nhưng câu 2 đổi…"* ra bản 2, `draft_briefs` và `assessments` không đổi; nhưng bản 2 tự đổi công thức mục 3–4 từ $A\cap B$ sang $A\setminus B$; *"ok, soạn đi"* ra 4/4 theo bản 2 |
| 16 Pha 2 ở tab mới | **Đạt** | Đầu màn `2 câu · 10 phút`; tab mới có dòng nhắc và *Làm tiếp lượt đang mở*; câu 1 sáng lựa chọn đã lưu; hộp nộp đếm đúng, *Quay lại làm tiếp* không nộp; `rounds_used` mỗi câu tăng 1. Lệch ở bước 3, xem *Ghi chép* |
| Khối ĐÃ PHÁT HÀNH (đề seed) | **Đạt** | `Mở 16:20 · 17/10`, `Hết giờ thu hồi lúc 16:20 · 17/10` — giờ +07:00 (seed mở 09:20 UTC), khớp màn học sinh |

**Tổng:** 2 đạt · 2 chấp nhận được · 2 không đạt trên 6 case (04 chạy lại sau bản sửa: chấp nhận
được). Có thêm khối ĐÃ PHÁT HÀNH, đạt. Hai ca không đạt vì hai lỗi Tier 1, cả hai đã sửa trong buổi.
Các mục kiểm của plan:

- không câu mock nào vào đề: 17 câu model soạn, đọc từ database; mọi lần hỏng đều có lý do trong
  log — **đạt**;
- không hai câu gần trùng trong một đề: lưới chặn 5 job (02: 3, 03: 1, 07: 1) — **đạt**;
- *"oke"* sau dàn ý ra plan — **đạt ở mọi ca, nhưng chỉ case 03 qua `_approved_plan`**. 4 trên 7
  dàn ý lưu `brief` rỗng (01, 04 lần hai, 07 cả hai bản): Haiku để trống `known`, và bản vá pha 1
  chỉ lấp từ dàn ý **trước**. Ở 04 và 07, plan là của model, đúng nhờ model (Tier 2 câu 24);
- xin 5 câu sau một lượt hỏi lại vẫn ra 5 (01, 04) — **đạt**;
- câu biến thể pha 2 khác câu gốc — **đạt**.

## Sửa trong buổi

1. **Brief của một câu không nêu các câu đã có của đề** (case 02).
   - Triệu chứng: ô 4 hỏng cả 3 lần. Đọc kết quả arq thì thấy cả 3 lần model viết lại
     $\frac{x}{12}=\frac{5}{8}$ của câu 3.
   - Lưới gần trùng ở BE chặn đúng, nhưng lần thử lại không cho model biết thêm gì, nên lần nào cũng
     ra lại câu ấy.
   - Sửa (`05bec8e`): `authoring._already_written` đưa tối đa 10 đề bài đã có (`banned_stems`) vào
     brief, kèm lời dặn không viết lại.
   - Review code tìm ra ba chỗ, sửa ở commit kế: `_stems` không có `order_by` và brief lấy mười câu
     **đầu**, nên đề dài có thể bỏ sót đúng câu vừa vào đề (nay theo `order_index`, mười câu cuối);
     danh sách đứng trước *"Bám đúng … trên"* nên chữ *trên* trỏ vào nó (nay xuống cuối brief).
   - Sau bản sửa, case 03 và 07 mỗi case có một ô trùng ở lần đầu và ra câu khác ở lần thứ hai;
     case 04 không ô nào phải thử lại.
2. **Dàn ý bị trả về 7 lần trong một lượt** (lần chạy đầu của case 04, 403 nghìn token).
   - Model viết công thức lẫn chữ: *"Nếu $a<b$ và $b<c$ thì $a<c$"*, *"$a=bq+r$, $0\le r<b$"*.
   - Lời trả về của `outline.validate` chỉ nói chung chung, nên model viết lại cả dàn ý, sửa mục này
     thì hỏng mục khác.
   - Lý do xen kẽ *mục 2*, *mục 3*, nên luật *cùng lý do hai lần thì dừng* không bắt.
   - Sửa (`05bec8e`):
     - lời trả về nêu đúng công thức hỏng và cách viết lại;
     - BE dừng ở lần trả về thứ ba, lý do gì cũng tính (`_MOST_OUTLINE_REFUSALS`);
     - prompt và mô tả field `formulas` có ví dụ đúng và sai.
   - Chạy lại thì không bị trả về lần nào, câu 3 viết theo đúng mẫu mới.

## Lỗi thấy được (ghi `backlog.md`)

1. **Không có đường nào soạn lại một ô `failed`** (case 02).
   - Câu kết mời *"Bạn có muốn mình thử soạn lại câu còn thiếu không?"* trong khi không đường nào làm
     được: luật 4 của bộ ca (lời không hứa việc hệ thống không làm).
   - Bước thêm *"có, soạn lại câu còn thiếu giúp mình nhé"*: model nêu dàn ý soạn thêm. BE đánh số từ
     câu 6 (sau 5 ô, kể cả ô hỏng), còn lời model nói câu 4, nên bị trả về hai lần và lượt dừng ở
     `OUTLINE_REFUSED`. `_RETRYABLE` chỉ có `retry`.
   - Panel ghi *4 câu* mà đánh số Câu 1, 2, 3, **5** (ảnh 02d): `order_index` giữ khe của ô hỏng.
   - Tier 2 câu 22: soạn lại ô hỏng tại chỗ, hay coi là câu soạn thêm và bỏ ô hỏng.
2. **Dàn ý đầu của đoạn chat lưu `brief` rỗng** (01, 04, 07), xem mục kiểm thứ ba ở trên. Tier 2
   câu 24.
3. **Hai câu cùng dạng trong một mục** (case 07): câu 3 và 4 đều là $A\setminus B$ của hai tập hữu
   hạn, khác số. Gốc có lẽ là bản 2 tự đổi công thức mục 3–4 sang phép hiệu; lưới gần trùng không
   bắt vì khác số liệu. Tier 2 câu 19 và Tier 4.
4. **Câu luật ở khối ĐÃ PHÁT HÀNH**: *"Chữa bài tới hết 01:20"* thiếu ngày khi qua nửa đêm (màn học
   sinh ghi *"01:20 · 18/10"*); *"có thể nộp lúc 23:35"* đọc sai nghĩa; gạch `-` lạc kiểu (ảnh 17).
   Tier 2 câu 17.
5. **Câu biến thể giữ nguyên bốn phương án của câu gốc** (ca 16, câu 2): *đồng biến* thành *nghịch
   biến*, $2x+1$ thành $-3x+5$, phương án vẫn là bốn khoảng cũ (chỉ D đổi *đồng* thành *nghịch*).
   `validate_retry` cho qua đúng luật; dạng câu lặp lại quá sát. Tier 4.
6. **Thông báo `OUTLINE_REFUSED` bảo giáo viên nói lại** trong khi lỗi nằm ở model (ảnh 02c, 04a).
   Tier 4.
7. **Lời model lệch nhẹ**: nút *Khối 6–9* và *Số học/Hình học/Đại số* khi giáo viên dạy lớp 11 (01);
   *"Đề có 4 câu, mỗi câu một mục"* khi chỉ có 3 mục (03 bản 1); `\text{tổng tiền}` trong công thức
   (03 bản 2); câu kết *"đề thiếu câu sẽ không dùng được"* (02). Tier 4.
8. **Dòng *"câu làm đúng được 0,5 điểm"* trong hộp nộp lượt là chữ in cứng** (ca 16), đã ghi ở Tier 2
   câu 20.

## Ghi chép theo case

- **01** (chat `bb7ed623…`)
  - Thẻ `Câu 1/3` *Khối* (nút `Khối 6`, `Khối 7`, `Khối 8`, `Khối 9`), `2/3` *Số câu* (`5 câu`,
    `8 câu`, `10 câu`), `3/3` *Phạm vi* (`Số học`, `Hình học`, `Đại số`), mỗi câu thêm `Khác…`.
  - Tin gộp: *"Khối: lớp 11 · Số câu: 5 câu · Phạm vi: cấp số cộng"*; lượt hỏi đã qua hiện kèm nhãn.
  - Dàn ý một mục `Câu 1–5` cấp số cộng, công thức $u_{n} = u_{1} + (n-1)d$ (Tier 2 câu 6: gộp mọi
    câu vào một mục). `brief` của dàn ý rỗng.
- **02** (`1adbddf1…`, đề *"Đề tỉ lệ thức và dãy tỉ số bằng nhau"*)
  - Dàn ý 3 mục (1–2, 3–4, 5), plan, 4/5 câu. Câu kết: *"…việc soạn câu hỏi dừng ở 4/5 câu… Bạn có
    muốn mình thử soạn lại câu còn thiếu không?"*. Panel (ảnh 02d): Câu 1, 2, 3, 5.
- **03** (`f949dad6…`, *"Đề hệ phương trình bậc nhất hai ẩn"*)
  - Bản 1, câu 3: *"Bài toán thực tế đưa về hệ hai ẩn (ví dụ về số, tiền, quãng đường)… Công thức:
    $s=v\cdot t$."* Câu 4: *"Biện luận nghiệm theo tham số, hoặc xác định điều kiện để hệ có nghiệm
    thỏa điều kiện cho trước."* Lời kết: *"Đề có 4 câu, mỗi câu một mục."* (3 mục).
  - Lời xin sửa: *"câu 3 đổi thành bài toán thực tế đi, kiểu mua vé xem phim người lớn với trẻ em
    ấy, lập hệ rồi giải"*.
  - Bản 2, câu 3: *"Bài toán thực tế mua vé xem phim người lớn và trẻ em… Công thức:
    $\text{tổng tiền} = x\cdot \text{giá vé người lớn} + y\cdot \text{giá vé trẻ em}$."* Câu 4:
    *"Biện luận số nghiệm của hệ."* Câu 1–2 diễn đạt lại cùng ý. Soạn 4/4, đề *"Đề hệ phương trình
    bậc nhất hai ẩn"*; *"oke, soạn đi"* đi qua `_approved_plan`.
- **04**
  - Lần đầu (`3f8bdf33…`): đọc sách 6 bước, mỗi bước có tên và dòng `— phần k/5`, rồi
    `OUTLINE_REFUSED` (ảnh 04a).
  - Lần hai (`eca63f49…`): đọc 2 bước, hỏi *"Bạn muốn 5 câu từ phần nào của Chương I?"* (10 nút tên
    bài + `Khác…`); người chạy gõ `Khác…` *"cả chương 1, rải đều các bài"* — **lệch kịch bản** (bảng
    rẽ dặn `cả chương luôn`), và *"rải đều các bài"* lái dàn ý thành *"mỗi câu một bài khác nhau"*.
  - Truy vấn A: `list_chapters`, `get_chapter`, rồi `read_section` nút `1,3,6,7,10,14,17` phần 1–5,
    phần 5 `more` = false. Truy vấn B: `dung_sach` = t, `scope_nodes` = `[1,3,6,7,10,14,17]`, 5 mục
    mỗi mục 1 câu với `source_nodes` `[1]`, `[3,4]`, `[6]`, `[7,10]`, `[14,16,17]`. Truy vấn C: 5
    hàng `draft_items` `ready`, mỗi job có `item_knowledge`, không `focus_`.
  - Đề *"Đề Kết nối tri thức Lớp 6 tập 1 (tr6-28)"* (panel, ảnh 04e) có 5 câu khác nhau: tập hợp (5
    phương án, ADR-18 cho phép), giá trị chữ số, bắc cầu, tính chất phân phối, luỹ thừa.
- **07** (`37b7ba8b…`)
  - Bản 1: *"Câu 1–2: Mệnh đề và mệnh đề phủ định"*, *"Câu 3–4: Tập hợp và các phép toán"*, công thức
    mục 3–4 $A\cap B=\{x \mid x\in A \text{ và } x\in B\}$.
  - Bản 2: *"Câu 1"* mệnh đề, *"Câu 2: Giao và hợp của hai khoảng trên trục số"* (công thức
    $A\cap B$), *"Câu 3–4: Tập hợp và các phép toán"* nay với công thức
    $A\setminus B=\{x \mid x\in A \text{ và } x\notin B\}$ — không ai xin đổi.
  - `draft_briefs` = 3 và `assessments` = 4, trước cũng như sau lời xin sửa. Panel (ảnh 07d): câu 2
    $A=[-2;\ 4]$, $B=(1;\ 6)$, tìm $A\cap B$; câu 3 $D\setminus C$, câu 4 $A\setminus B$.
- **16** (attempt `107f5169…`, lượt `99f4f2e5…`)
  - Pha 1 sai câu 1 và 2. Hộp *Bắt đầu làm bài?* hiện trước khi đồng hồ chạy (ảnh 16a).
  - Lượt: `started_at` 10:47:10Z, `ends_at` 10:57:10Z (10 phút), `submitted_at` 10:50:33Z.
  - Biến thể câu 1: đạo hàm $y=x^3-4x^2+5x$ (gốc $y=x^2+3x$). Biến thể câu 2: $y=-3x+5$ nghịch biến
    (gốc $y=2x+1$ đồng biến).
  - **Lệch ở bước 3:** đã đóng tab học sinh và mở một tab mới, nhưng tab mới không chụp được ảnh
    (CDP hết giờ), nên phần còn lại chạy trên tab giáo viên đang hiện. `sessionStorage` của tab ấy
    không có lượt này, nên với màn lượt nó giống một tab mới. Màn trợ lý bước 3 đọc bằng chữ: dòng
    nhắc *"Em đang có một lượt làm lại chưa nộp: bấm làm tiếp lượt đang mở"* và nút *Làm tiếp lượt
    đang mở*. Ảnh 16b là màn lượt ở bước 4, ảnh 16c là hộp nộp ở bước 5.
  - Kết quả: câu 1, 2 có `mark` 0,5 và `rounds_used` 1; các câu khác `mark` 1, `rounds_used` 0. Màn
    kết quả *"5,0 trên 6 câu"* (đọc bằng chữ, không ảnh).
