# Thử tay trên trình duyệt — hướng dẫn chung

Thư mục này là chỗ duy nhất của việc thử tay bề mặt giáo viên. Ba thứ sống ở đây:

| File | Dùng để |
| --- | --- |
| `cases/NN-<slug>.md` | **Bộ ca cố định.** Mỗi trường hợp đúng một case, gõ y nguyên văn mỗi lần chạy, để hai lần chạy so được với nhau và người xem hiểu dự án làm tốt tới đâu |
| `kich-ban-thu-tay-giao-vien.md` | Danh sách soi lỗi giao diện từng nút, từng thẻ — chặng A–G. Chạy khi đổi FE |
| `ket-qua/<ngày>-<commit>.md` | Biên bản mỗi lần chạy bộ ca cố định |

Bộ ca và danh sách soi lỗi khác nhau ở câu hỏi chúng trả lời. Danh sách hỏi *"cái nút này còn đúng
không?"*. Bộ ca hỏi *"một giáo viên thật nói chuyện với Kriky thì được gì, và lần này có tốt hơn lần
trước không?"*.

---

## Chuẩn bị

Mọi lần chạy bộ ca bắt đầu từ cùng một chỗ, nên không bỏ bước nào.

1. `.\dev.ps1 infra-up`, rồi `.\dev.ps1 db-reset`. Seed (`services/be/src/be/seed.py`): giáo viên
   **Cô Phạm Thu Lan** (`GV-001`), lớp **12A** ba học sinh, đề **"Kiểm tra 15 phút — Hàm số"** đã
   phát hành cho 12A.
2. Sáu terminal: `.\dev.ps1 be`, `agent`, `ingest`, `document`, `index`, `fe`
   (`docs/local-development.md`). Thiếu `ingest`, `document` hay `index` thì tài liệu treo ở
   *Đang xử lý…* mãi mà không báo gì.
3. Model là **`gpt-4o-mini`**, không model nào khác.
4. Mở **`http://127.0.0.1:5173/#/teacher`** — `127.0.0.1`, không `localhost`.
5. **Thêm lớp 12B** (case 11 cần hai lớp khớp chữ *"12"*; chưa có màn hình hay tool tạo lớp):

   ```
   docker exec aiafa-postgres psql -U aiafa -d aiafa -c "insert into classes (id, teacher_id, name) select gen_random_uuid()::text, id, '12B' from teachers limit 1;"
   ```

6. **Tệp sách:** `data/Kết nối tri thức Lớp 6 tập 1 (tr6-28).pdf` (SGK Toán 6 tập 1, trang 6–28,
   chương I). Tệp là ảnh quét, không có lớp chữ: nó đi đường OCR rồi dựng mục lục, mất vài phút.
   Tải lên một lần ở đầu buổi, đợi chip lên *sẵn sàng* (có số trang) rồi mới chạy case 04.
7. **Tệp scan** cho case 13 — một trang SGK chụp lại, không có lớp chữ. Dựng một lần:

   ```
   python -c "import pymupdf; s=pymupdf.open('data/Kết nối tri thức Lớp 6 tập 1 (tr6-28).pdf'); p=s[0].get_pixmap(dpi=120); d=pymupdf.open(); d.new_page(width=p.width, height=p.height).insert_image(d[0].rect, pixmap=p); d.save('data/scan-mot-trang.pdf')"
   ```

   `data/` không bao giờ được commit.
8. **Mỗi case một đoạn chat mới**, trừ khi case ghi rõ là chạy tiếp trên đoạn chat của case trước.
   Một đoạn dài làm mọi lượt sau mang ngữ cảnh lượt trước, và khi một câu trả lời sai thì không biết
   nó sai vì luật hay vì đọc nhầm câu cũ.

---

## Luật áp cho **mọi** lượt Kriky trả lời

Mỗi lần Kriky nói, soi đủ bảy dòng — chúng không phụ thuộc case nào.

| # | Phải đúng | Sai thì trông thế nào |
|---|---|---|
| 1 | **Một lượt, một avatar.** Kriky nói hai câu (mở đầu và kết) vẫn chỉ một hàng logo trên cùng | Hai hàng logo trong một lượt |
| 2 | **Không con số nào không có trong kết quả.** Kriky không thấy chữ câu hỏi đã soạn | *"mình đã soạn xong 10 câu rất hay"*, *"đề này khó vừa phải"* — nhận xét về thứ nó không đọc |
| 3 | **Con số trên thẻ và trong câu nói khớp nhau** | Câu nói *"đã soạn xong"* mà khối bước ghi `Dừng ở 2/10 câu` |
| 4 | **Không hứa việc nó không làm được.** Kriky không có tool duyệt, bỏ duyệt, phát hành, xoá câu | *"để mình duyệt giúp bạn nhé"* |
| 5 | **Không Markdown.** Không `**đậm**`, không `` `mã` ``, không bảng | Dấu sao hay dấu huyền kép nguyên văn trên màn hình |
| 6 | **Toán là LaTeX trong cặp `$`**, và màn hình **dựng hình** nó | `$\frac{1}{2}$` nguyên văn trên màn — cụm ấy không dựng được |
| 7 | **Không định danh máy nào lọt ra màn hình** | Một chuỗi UUID, hay tên tool như `start_drafting` |

Luật 6 từng bị lật một lần: hợp đồng là ADR-26 — prompt soạn câu **bắt** model viết `$y = x^3$`, và
`MathText` dựng hình phần giữa hai dấu `$`. Thấy dấu đô la trên màn nghĩa là cụm ấy không dựng
được, không phải model sai quy ước.

Và **hai luật cho khối bước**:

- `bước k/n` — `n` cố định từ lúc khối hiện ra. `n` nhảy giữa chừng là đang đếm số bước đã chạy chứ
  không đến từ plan.
- **Đúng một hàng có dải sáng quét**, và nó là hàng đang chạy. Bước xong thì tắt, bước chưa tới thì
  chưa sáng.

**Tên bước đổi khi lượt xong — lệch đã biết, không tính trượt.** Lúc đang chạy, mỗi hàng mang tên
bước trong plan (*"Soạn câu hỏi theo dàn ý"*, *"Soạn thêm câu hỏi"*, *"Thay câu 3"*). Lượt xong, FE
đọc lại cả đoạn chat từ database và đặt tên theo tool (`STEP_TITLE` trong `ActionCard.tsx`):
`Tạo đề trống`, `Soạn câu hỏi`, `Thay một câu`, `Xem các lớp`… Các tool đọc sách (`list_chapters`,
`get_chapter`, `read_section`, `list_documents`) chưa có tên nên hiện **`Một bước nữa`**. Mọi case
chấm theo tên **sau khi lượt xong**, và F5 không được đổi gì thêm.

**Kriky làm được gì** (để không chờ nó làm thứ nó không có): tra lớp (`list_class`, `get_class`),
tra đề và kết quả lớp (`list_assessment`, `class_assessment_summary`), đọc tài liệu
(`list_documents`, `list_chapters`, `get_chapter`, `read_section`), mở và soạn đề (`create_draft`,
`start_drafting`), thay một câu (`replace_question`). Duyệt, bỏ duyệt, phát hành, hoàn tác, sửa chữ
và xoá câu là **nút trên panel**, không qua chat. Mọi đề đi qua **dàn ý** giáo viên đã thấy và đồng
ý (ADR-29); mỗi lần xin tối đa **10 câu**.

---

## Mẫu một case

Mọi file trong `cases/` theo đúng bảy mục này, đúng thứ tự:

1. **Cho người xem thấy gì** — một câu: case này chứng minh dự án làm tốt điều gì.
2. **Chuẩn bị** — trạng thái đầu: đoạn chat mới hay chạy tiếp case nào, chip nào đính, lớp nào có.
3. **Lời chat** — từng lượt gõ **nguyên văn**, giọng một giáo viên thật. Cố định: lần sau gõ y hệt.
4. **Nếu Kriky rẽ** — bảng các nhánh lường trước: Kriky hỏi lại gì thì trả lời cố định thế nào;
   Kriky làm gì thì tính là đạt, chấp nhận được hay không đạt, và vì sao.
5. **Đạt khi** — thấy được trên màn hình; một truy vấn database khi màn hình không nói được.
6. **Không đạt khi** — các hình dạng sai cụ thể.
7. **Ghi lại** — những gì chép nguyên văn vào biên bản.

---

## Thứ tự chạy

Thứ tự: **01–08, 11, 12, 09, 10, 13, 14**. Case 11 và 12 chạy trước 09–10 vì hoàn tác ở case 10
chỉ thu hồi mềm: bản phát hành cho 12A còn lại với `recalled_at`, và `list_assessment` vẫn liệt
kê nó, nên 12A sẽ có hai đề thay vì một. Bốn chuỗi nối nhau:

- **02 → 05 → 09 → 10**: cùng một đề không tài liệu — soạn, thay câu 3, sửa / duyệt / xoá câu,
  phát hành rồi hoàn tác. Case 05 quay lại đúng đoạn chat của case 02.
- **04 → 06 → 14**: cùng một đề theo sách — soạn, soạn thêm, F5 và đổi đoạn chat.
- **13 sau 04**: tệp scan cũng lên *sẵn sàng*, tải trước case 04 thì thư viện có hai cuốn.
- 01, 03, 07, 08, 11, 12: mỗi case một đoạn chat mới, không dựa vào đề của case nào.

Một case trong chuỗi không đạt thì các case sau vẫn chạy nếu trạng thái chúng cần vẫn có (ví dụ đề
vẫn đủ câu); không có thì ghi *"không chạy được — case NN hỏng"* thay vì đoán.

---

## Ghi kết quả

Mỗi lần chạy bộ ca là một file `ket-qua/<YYYY-MM-DD>-<commit ngắn>.md`:

- đầu file: ngày, commit, model, ai chạy, chi phí ước tính;
- một bảng: case, **đạt / chấp nhận được / không đạt**, một dòng lý do;
- dưới bảng, mỗi case một mục: **nguyên văn** câu Kriky ở các lượt quan trọng (dàn ý, câu kết, lời
  từ chối) và những gì trái với *Đạt khi*.

Nguyên văn quan trọng hơn mô tả: với một model, *"nó trả lời sai"* không sửa được, còn một câu chép
lại nguyên văn thì so được với lần sau và sửa được.

Lỗi của sản phẩm thấy lúc chạy thì ghi biên bản **và** `docs/plans/backlog.md`. Lỗi của chính case —
tiêu chí sai so với hành vi đã chốt, hay lời chat dẫn Kriky sai hướng — thì sửa case, và ghi trong
biên bản rằng case đã đổi, vì lần chạy sau không còn so được một một với lần này.
