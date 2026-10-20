# Thử tay trên trình duyệt — hướng dẫn chung

Thư mục này là chỗ duy nhất của việc thử tay trên trình duyệt. Ba thứ sống ở đây:

| File | Dùng để |
| --- | --- |
| `cases/NN-<slug>.md` | **Bộ ca cố định.** Mỗi trường hợp đúng một case, gõ y nguyên văn mỗi lần chạy, để hai lần chạy so được với nhau và người xem hiểu dự án làm tốt tới đâu |
| `kich-ban-thu-tay-giao-vien.md` | **Kịch bản đầu-cuối**: một vòng đời bài kiểm tra, từ giáo viên đăng nhập tới bảng điểm. Chạy khi đổi luồng hay FE; không `db-reset` |
| `ket-qua/<ngày>-<commit>….md` | Biên bản mỗi lần chạy bộ ca cố định hay kịch bản đầu-cuối |

Bộ ca và kịch bản đầu-cuối khác nhau ở câu hỏi chúng trả lời. Kịch bản hỏi *"luồng có đi hết không,
màn nào cũng nối được màn sau không?"*. Bộ ca hỏi *"một giáo viên thật nói chuyện với Kriky thì được gì, và lần này có tốt hơn lần
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
3. Model là **`gpt-4o-mini`** hoặc **`claude-haiku-5-5`** (`.env` dev, kiểm dòng `model=` trong log
   khởi động AGENT); model khác phải xin phép. Ghi model vào tên biên bản.
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

Mỗi lần Kriky nói, soi đủ tám dòng — chúng không phụ thuộc case nào.

| # | Phải đúng | Sai thì trông thế nào |
|---|---|---|
| 1 | **Một lượt, một avatar.** Kriky nói hai câu (mở đầu và kết) vẫn chỉ một hàng logo trên cùng | Hai hàng logo trong một lượt |
| 2 | **Không con số nào không có trong kết quả.** Kriky không thấy chữ câu hỏi đã soạn | *"mình đã soạn xong 10 câu rất hay"*, *"đề này khó vừa phải"* — nhận xét về thứ nó không đọc |
| 3 | **Con số trên thẻ và trong câu nói khớp nhau** | Câu nói *"đã soạn xong"* mà khối bước ghi `Dừng ở 2/10 câu` |
| 4 | **Không hứa việc nó không làm được.** Kriky không có tool duyệt, bỏ duyệt, phát hành, xoá câu | *"để mình duyệt giúp bạn nhé"* |
| 5 | **Markdown được dựng** (ADR-30): đậm, gạch đầu dòng, bảng hiện thành định dạng | Dấu sao, dấu `#`, dấu `\|` hay dấu huyền nguyên văn trên màn hình |
| 6 | **Toán là LaTeX trong cặp `$`**, và màn hình **dựng hình** nó | `$\frac{1}{2}$` nguyên văn trên màn — cụm ấy không dựng được |
| 7 | **Không định danh máy nào lọt ra màn hình** | Một chuỗi UUID, tên tool như `start_drafting`, hay số node như *"(node 5)"* |
| 8 | **Lời Kriky là lời model viết; câu cố định chỉ là thông báo hệ thống** (ADR-30): dòng riêng, không avatar, thẻ trắng viền mảnh, vòng `!` nền chìm | Một câu dọn trước (*"Mình chưa dựng được các bước…"*, *"Được, mình soạn theo dàn ý ngay."*) dưới avatar Kriky; hay thông báo hệ thống mang avatar |

Luật 6 từng bị lật một lần: hợp đồng là ADR-26 — prompt soạn câu **bắt** model viết `$y = x^3$`, và
`MathText` dựng hình phần giữa hai dấu `$`. Thấy dấu đô la trên màn nghĩa là cụm ấy không dựng
được, không phải model sai quy ước.

Và **hai luật cho khối bước**:

- `bước k/n` — `n` cố định từ lúc khối hiện ra. `n` nhảy giữa chừng là đang đếm số bước đã chạy chứ
  không đến từ plan.
- **Đúng một hàng có dải sáng quét**, và nó là hàng đang chạy. Bước xong thì tắt, bước chưa tới thì
  chưa sáng.

**Tên bước là một, lúc đang chạy và sau F5.** Mỗi hàng mang tên theo tool (`STEP_TITLE` trong
`ActionCard.tsx`): `Xem mục lục`, `Đọc sách`, `Tạo đề trống`, `Soạn câu hỏi`, `Thay một câu`, `Xem
các lớp`… Bước tra cứu trước plan (đọc sách, tra lớp) hiện **ngay lúc chạy**, có dòng kết quả (vd
`— phần 2/5: 2. SỐ LA MÂ (tr. 10–13)`), và không vào `bước k/n` — `n` chỉ đếm bước của plan. Tên hay
dòng kết quả đổi sau F5 là trượt.

**Kriky làm được gì** (để không chờ nó làm thứ nó không có): tra lớp (`list_class`, `get_class`),
tra đề và kết quả lớp (`list_assessment`, `class_assessment_summary`), đọc tài liệu
(`list_documents`, `list_chapters`, `get_chapter`, `read_section`), mở và soạn đề (`create_draft`,
`start_drafting`), thay một câu (`replace_question`). Duyệt, bỏ duyệt, phát hành, hoàn tác, sửa chữ,
xoá câu và đổi tên đề là **nút trên panel**, không qua chat. Khi thiếu dữ kiện, Kriky hỏi lại tối đa
**3 câu** một lượt, mỗi câu nút riêng, đi từng câu rồi gửi gộp một tin (ADR-32). Mọi đề đi qua **dàn ý** giáo viên đã thấy và đồng
ý (ADR-29); mỗi lần xin tối đa **10 câu**.

**Một lời dàn ý đạt** ([ADR-30](../decisions/adr-30-loi-kriky-do-model-viet.md)) khi đó là lời Kriky
**tự viết**, Markdown dựng hình, và:

- mỗi mục nêu số câu của nó — `Câu k` hay `Câu k–m` — cộng lại đúng số câu đã xin, và không nhắc
  câu nào ngoài dàn ý;
- mỗi mục nói kiến thức và cách làm; mục có công thức thì công thức dựng hình;
- đề theo sách thì mỗi mục nêu bài hay mục nguồn, gần chữ một dòng `labels` của `read_section`
  (nhãn dựng từ cây OCR, có thể thiếu số bài hay sai dấu);
- kết bằng một câu hỏi xin giáo viên đồng ý hay sửa, do Kriky tự viết.

Chữ không cố định: hai lần chạy khác chữ, khác cách trình bày vẫn đạt. Màn hình không còn dòng
`Dàn ý — N câu (bản k)`: số bản và tổng câu đọc ở database (`tool_result->>'version'`, `->>'total'`
của hàng `outline`). Sau lời đồng ý, lượt soạn không có câu mở cố định — có lời mở thì là lời Kriky
viết lúc nêu plan, không thì khối bước đứng ngay dưới avatar.

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

Thứ tự: **01–08, 11, 12, 09, 10, 13, 14, 15, 16**. Case 11 và 12 chạy trước 09–10 vì hoàn tác ở
case 10 chỉ thu hồi mềm: bản phát hành cho 12A còn lại với `recalled_at`. Từ 17/10/2026
`list_assessment` đã lọc bản thu hồi, nhưng thứ tự giữ nguyên để các lần chạy so được với nhau. Bốn
chuỗi nối nhau:

- **02 → 05 → 09 → 10**: cùng một đề không tài liệu — soạn, thay câu 3, sửa / duyệt / xoá câu,
  phát hành rồi hoàn tác. Case 05 quay lại đúng đoạn chat của case 02.
- **04 → 06 → 14 → 15**: cùng một đề theo sách — soạn, soạn thêm, F5 và đổi đoạn chat, đổi tên.
  Case 15 chạy **sau cùng**: các case khác lọc database theo tên đề, đổi tên giữa chừng thì chúng
  hụt.
- **13 sau 04**: tệp scan cũng lên *sẵn sàng*, tải trước case 04 thì thư viện có hai cuốn.
- 01, 03, 07, 08, 11, 12: mỗi case một đoạn chat mới, không dựa vào đề của case nào.
- 16 là ca của **học sinh**, chạy sau cùng trên đề seed: không dựa vào đề nào của giáo viên.

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
