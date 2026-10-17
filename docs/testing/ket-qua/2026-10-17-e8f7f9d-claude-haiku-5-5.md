# Lần chạy 17/10/2026 (chiều) trên Claude Haiku 5.5 — commit e8f7f9d

- **Ngày:** 17/10/2026, 11:47–12:35. **Code:** BE và AGENT khởi động 11:47 sau `db-reset`, trên
  `e8f7f9d` (plan `assessment-title-and-multi-question`, cả bản sửa theo review code). Riêng FE: bản
  sửa **avatar trên thẻ hỏi lại** (xem dưới) vào lúc 12:24, giữa lượt 1 và lượt 2 của case 01 —
  ảnh `01-a`, `01-b` là trước, mọi ảnh sau là sau.
  **Model:** `anthropic/claude-haiku-5-5`, `thinking=disabled`, `effort=low` (dòng `model=` trong log
  AGENT lúc khởi động).
- **So với:** `2026-10-17-02ba28a-claude-haiku-5-5.md` — cùng model. Code khác ở plan này: tên đề
  tối đa 60 ký tự, đề sách mang tên tệp, giáo viên đổi tên đề ở panel (ADR-31); `ask_clarify` hỏi
  tối đa 3 câu một lượt, thẻ đi từng câu rồi tóm tắt, gửi gộp một tin (ADR-32).
- **Phạm vi:** 01, 02, 04 (case đã đổi) và 15 (case mới), người dùng chọn 17/10. Sau `db-reset`,
  thêm lớp 12B, tải SGK. Case 15 chạy trên đề của case 04 (06 và 14 không chạy lần này).
- **Người chạy:** Claude, trên Chrome. Màn hình đọc bằng DOM và ảnh chụp; lời Kriky nguyên văn từ
  `teacher_turns.text`.
- **Ảnh chụp:** 17 ảnh, không đưa vào repo — giao cho người review cùng biên bản. Giữa buổi chụp
  treo (CDP hết giờ) một lúc, rồi extension tự chuyển sang một trình duyệt Edge khác; người dùng
  chọn lại Chrome.
- **Token và chi phí:** 232 nghìn token cho 40 hàng `teacher_turns` (case 01: 21 nghìn, 02: 21
  nghìn, 04 + 15: 191 nghìn), cộng 10 job soạn câu. Ước 0,06–0,08 USD, trong mức 0,05–0,10 đã báo.
  Một bước Kriky trung bình 4,0 s (tối đa 6,7 s).

## Kết quả

| Case | Kết quả | Lý do |
| --- | --- | --- |
| 01 Xin đề mơ hồ | **Chấp nhận được** | Thẻ ba câu, không bỏ câu, tóm tắt, gửi gộp một tin, dàn ý 5 câu cấp số cộng; nút câu 3 là *loại* phạm vi, không phải giá trị |
| 02 Đề không tài liệu | **Không đạt** | Tên đề 36 ký tự, không số trang; nhưng câu 3 và câu 4 cùng một bài $\frac{x}{6}=\frac{4}{9}$, do model viết (nhãn *ngân hàng* trên panel là chữ bịa) — trượt *"khác số liệu hoặc cách hỏi"* |
| 04 Đề theo sách | **Không đạt** | Tên đề đúng tên tệp; nhưng bài nguồn gộp ở cuối lời dàn ý thay vì nêu từng mục, và câu 3 có phương án rác `4 volume` kèm đáp án sai |
| 15 Đổi tên đề | **Đạt** (một phần) | Ô 60 ký tự, thẻ cũ + dòng bước + panel đổi theo không cần F5, đã duyệt thì không đổi được, Kriky nói tên mới; chỉ một thẻ cũ vì 06 không chạy |

Lỗi giao diện người dùng chỉ ra giữa buổi, **đã sửa trong buổi**: thẻ hỏi lại (một câu lẫn nhiều
câu) **không có avatar Kriky** khi lượt chỉ gồm câu hỏi lại — lượt cuối được gấp vào thẻ để câu hỏi
không hiện hai lần, nhưng thẻ đứng trần. Có từ `e6debbb`, mọi vitest vẫn xanh. Nay thẻ mở lượt thì
mang hàng avatar (cao 40, cách thẻ 6, thẻ rộng 820 — bằng artboard `3 · Kriky hỏi lại`, `69:159`,
đã chỉnh cùng lúc). Luật mới ở `services/fe/AGENTS.md`: mọi thay đổi FE kết thúc bằng một lượt
trình duyệt và một subagent chấm ảnh.

## 01. Xin đề mơ hồ — chấp nhận được

Lượt 1 ra **một** thẻ nhiều câu. Lời mở: *"Được cô, mình soạn đề kiểm tra cho các em. Cô cho mình
biết thêm:"*

| Câu | Nhãn | Câu hỏi | Nút | Trả lời bằng |
| --- | --- | --- | --- | --- |
| 1/3 | Khối | *Đề này dành cho khối mấy?* | Khối 6 · Khối 7 · Khối 8 | `Khác…` → `lớp 11` |
| 2/3 | Số câu | *Cô muốn đề có bao nhiêu câu?* | 5 câu · 8 câu · 10 câu | nút `5 câu` |
| 3/3 | Phạm vi | *Kiểm tra phạm vi kiến thức nào?* | Một chương đang học · Một chủ đề cụ thể · Nhiều bài ôn tập | `Khác…` → `cấp số cộng` |

- Chưa chọn thì `Câu sau ›` khoá; ở câu 1 `‹ Câu trước` khoá. Lùi từ câu 2 về câu 1, hàng `Khác:
  lớp 11` vẫn sáng (`aria-pressed=true`).
- Màn *Kiểm tra lại trước khi gửi*: ba hàng `Khối / lớp 11`, `Số câu / 5 câu`, `Phạm vi / cấp số
  cộng`, mỗi hàng `Sửa`; `‹ Câu trước` và `Gửi`.
- Bong bóng gửi gộp, **một** tin: *"Khối: lớp 11 · Số câu: 5 câu · Phạm vi: cấp số cộng"*.
- Sau khi gửi, lượt hỏi cũ hiện lời mở cùng ba câu đánh số (ảnh `01-e`).
- Lượt 2 — dàn ý, không hỏi lại: *"Cô Lan, mình đề xuất dàn ý đề 5 câu về cấp số cộng cho lớp 11:"*
  Câu 1–2 số hạng tổng quát và công sai ($u_n = u_1 + (n-1)d$), Câu 3–4 tổng $n$ số hạng đầu
  ($S_n = \frac{n(u_1+u_n)}{2}$), Câu 5 tìm số hạng khi biết hai số hạng ($u_m = u_1 + (m-1)d$);
  kết *"Cô xem dàn ý này đã ổn chưa, hay cô muốn đổi chỗ nào?"*
- Database: số đề vẫn 1 (`N` = 1). `teacher_turns`: `teacher`, `assistant` (`cau` = 3, `nut` = 0),
  `teacher` (chữ gộp), `outline` (`tong` = 5). Không hàng `plan`.
- Vì sao **chấp nhận được**: nút câu 3 không phải giá trị bấm được của phạm vi (bảng *Nếu Kriky
  rẽ*: dùng `Khác…`). Trước khi sửa avatar, lượt 1 không có avatar Kriky (ảnh `01-a`, `01-b`).

## 02. Đề không tài liệu — không đạt

- Lượt 1 — dàn ý: *"Mình đề xuất dàn ý 5 câu trắc nghiệm cho đề 15 phút Toán 7, phạm vi tỉ lệ thức
  và dãy tỉ số bằng nhau:"* Câu 1–2 nhận biết tỉ lệ thức ($\frac{a}{b}=\frac{c}{d} \Rightarrow
  ad=bc$), Câu 3–4 tìm số hạng chưa biết ($x = \frac{b \cdot c}{d}$), Câu 5 dãy tỉ số bằng nhau;
  kết *"Bạn đồng ý với dàn ý này không, hay muốn đổi chỗ nào?"* Chưa có đề nào ngoài đề seed.
- Lượt 2 (`được rồi, soạn đi nhé`): lời mở *"Được, mình soạn đề ngay. Bạn đang chọn đề mới cho Toán
  7, …"*, khối `Đã làm 2 bước`, câu kết *"Xong rồi bạn ơi! Mình đã tạo đề "Đề tỉ lệ thức và dãy tỉ
  số bằng nhau" và soạn đủ 5/5 câu hỏi. Bạn xem qua và duyệt giúp mình nhé."*, thẻ `Đã tạo đề "Đề
  tỉ lệ thức và dãy tỉ số bằng nhau"` · `Chưa duyệt · chưa phát hành`, một dòng.
- **Tên đề:** `Đề tỉ lệ thức và dãy tỉ số bằng nhau`, 36 ký tự, không `(tr. …)`. Panel có `Đổi tên`.
- Bám dàn ý: năm ô `ready`, `ban` = 1; câu 1, 2 → mục 0; 3, 4 → mục 1; 5 → mục 2 — đúng kiến thức.
- Vì sao **không đạt**: câu 3 *"Tìm số hạng chưa biết $x$ trong tỉ lệ thức
  $\frac{x}{6}=\frac{4}{9}$"* và câu 4 *"Tìm số x biết $\frac{x}{6}=\frac{4}{9}$. Giá trị của x là:"*
  cùng số liệu và cùng cách hỏi, chỉ khác chữ. Cả hai mang nhãn *Lấy từ ngân hàng câu hỏi* trên panel, nhưng nhãn ấy là **chữ bịa** chọn theo hash id (`invented-not-from-be.ts`, đã gỡ trong plan `backlog-tier-1`): hệ thống chưa có đường đọc ngân hàng nào, hai câu do model viết. *(Sửa sau review tranh luận 17/10.)* *Đạt
  khi* của case đòi hai câu chung một mục khác số liệu hoặc cách hỏi. (Bản đầu biên bản ghi *chấp
  nhận được*; review ảnh chỉ ra là quá nhẹ.)

## 04. Đề theo sách — không đạt

- Chip đính trước lượt 1. Lượt 1: khối `Đã làm 6 bước`; truy vấn A: một `list_chapters`, rồi
  `read_section` `part` 1–5, phần cuối `more` = false.
- Lời dàn ý: *"Mình đã đọc xong chương I (Tập hợp các số tự nhiên). Mình đề xuất dàn ý 5 câu như
  sau, tất cả lấy từ phần Tập hợp, cách ghi số, thứ tự, các phép tính và luỹ thừa:"* — Câu 1–2 tập
  hợp ($x \in A$, $\{x \in \mathbb{N} \mid x < 5\}$), Câu 3 thứ tự trên tia số, Câu 4 phép cộng và
  tính chất, Câu 5 luỹ thừa ($a^m \cdot a^n = a^{m+n}$); rồi *"Cách làm: … Bài nguồn là Bài 1 Tập hợp,
  Cách ghi số tự nhiên, Thứ tự trong tập hợp các số tự nhiên, Phép cộng và phép trừ, và Luỹ thừa với
  số mũ tự nhiên."* — bài nguồn **gộp ở cuối**, không nêu theo từng mục.
- Lượt 2 (`oke`): *"Được, mình soạn đề ngay."*, `Đã làm 2 bước`, *"Mình đã soạn xong đề "Đề Kết nối
  tri thức Lớp 6 tập 1 (tr6-28)" với đủ 5/5 câu hỏi, …"*, thẻ `Đã tạo đề "Đề Kết nối tri thức Lớp 6
  tập 1 (tr6-28)"`.
- **Tên đề:** đúng tên tệp bỏ đuôi, 40 ký tự; một dòng trên thẻ. Tiêu đề panel xuống hai dòng ở bề
  rộng panel mặc định, và **bẻ giữa** `(tr6-` / `28)` — xuống dòng thì được (`h2` không cắt), bẻ ở
  dấu gạch trong ngoặc là lỗi chữ (backlog).
- Truy vấn B: `dung_sach` = t, `scope_nodes` 1–16, bốn mục dàn ý (2 + 1 + 1 + 1), mỗi mục có
  `source_nodes`. Năm ô `ready`; ô 1 có `last_fault` *"đề trùng một câu đã có"* nhưng vẫn ra câu.
  Truy vấn C: cả năm job in `item_knowledge`, không `focus_`.
- Vì sao **không đạt**: (1) dàn ý không nêu bài nguồn từng mục (bảng *Nếu Kriky rẽ*); (2) câu 3
  *"Trong các số sau, số nào nhỏ nhất?"* có phương án A là `$4\,volume$` — rác do job soạn câu viết,
  không phải chữ OCR — và đáp án đánh dấu C `1 025`: nếu A định là `4` thì A mới nhỏ nhất.
- Tên đoạn chat do model đặt: *"Bạn gửi kèm sách hoặc chụp các trang chương 1 Toán 6 giúp mì…"* — lời
  của trợ lý, không phải chủ đề.

## 15. Đổi tên đề — đạt (một phần)

- **A1:** `Đổi tên` → ô nhập viền nhấn, điền sẵn tên cũ, đếm `40/60`, `Lưu`, `Huỷ`. `Đóng` **ẩn**
  lúc sửa — đúng variant `rename` (`626:2730`); case ghi *"Nút Đóng vẫn đó"* là sai, đã sửa case.
- **A2:** `Huỷ` → tiêu đề về nguyên tên cũ.
- **A3:** gõ chuỗi 72 ký tự → ô giữ 60 ký tự đầu, đếm `60/60`.
- **A4:** tên mới `Kiểm tra 15 phút — Số tự nhiên`, Enter → tiêu đề panel, thẻ cũ (`Đã tạo đề
  "Kiểm tra 15 phút — Số tự nhiên"`, `title` cùng chữ) và dòng bước `— đề "Kiểm tra 15 phút — Số tự
  nhiên"` đổi ngay, không F5; F5 vẫn vậy. Câu kết Kriky đã viết lúc trước vẫn nhắc tên cũ — đó là
  lời model đã nói, hệ thống không viết lại lời Kriky (ADR-30).
- Database: đề `Kiểm tra 15 phút — Số tự nhiên`, 30 ký tự, `has_questions` (không đổi trạng thái).
  Hai hàng `teacher_turns` có `title` vẫn giữ `Đề Kết nối tri thức Lớp 6 tập 1 (tr6-28)` — tên hiện
  tại thay lúc đọc.
- **B1:** `Duyệt đề` → cài đặt phát hành; tiêu đề panel chỉ còn `Đóng`. **B2:** `Hoàn tác` → nội
  dung đề, `Đổi tên` hiện lại.
- **Phần chưa thử được:** đoạn chat chỉ có **một** thẻ `Đã tạo đề` (case 06 không chạy), nên *"mọi
  thẻ … case 04 lẫn 06"* mới thử nửa. Chữ rê chuột và màn sau F5 kiểm bằng DOM (`title`, đọc lại
  sau `reload`), không có ảnh.
- **C:** *"đề mình vừa làm giờ tên là gì nhỉ?"* → không gọi tool: *"Đề bạn vừa làm tên là "Kiểm tra
  15 phút — Số tự nhiên", gồm 5 câu. Lưu ý: lúc trước mình có ghi tên là "Đề Kết nối tri thức Lớp 6
  tập 1 (tr6-28)", nhưng tên đúng theo hệ thống là "Kiểm tra 15 phút — Số tự nhiên". Đề hiện ở
  trạng thái chưa duyệt (mình vừa thấy có thao tác duyệt rồi bỏ duyệt). Việc duyệt và phát hành bạn
  làm ở panel bên phải nhé."*

**Ngoài case — tên dài trên thẻ** (ảnh `15-d`, `15-e`): đổi tên lần nữa, gõ 61 ký tự *"Ôn tập chương
I số tự nhiên: tập hợp, cách ghi số và lũy thừa"*. Ô dừng ở 60, tên lưu thành *"…và lũy thừ"* —
`maxLength` cắt giữa từ mà không báo gì ngoài bộ đếm `60/60` (cũng thấy ở A3: *"…ghi số và t"*).
Tên hệ thống đặt thì cắt ở ranh giới từ kèm `…`; chữ giáo viên gõ thì cụt giữa từ — backlog. Thẻ cũ: một dòng, `white-space:
nowrap`, `text-overflow: ellipsis`, cao 20; `title` mang đủ tên. Tiêu đề panel xuống hai dòng.

## Review ảnh chụp

Một subagent chấm 17 ảnh cùng biên bản: không ảnh nào trái với một câu của biên bản. Theo đó đã sửa
ở trên: case 02 hạ xuống **không đạt**; case 04 thêm đáp án sai; tiêu đề panel bẻ giữa `(tr6-28)`
là lỗi; case 15 ghi rõ phần chưa thử. Thêm: hàng đoạn chat thứ ba trên rail bị vạch chia ngăn
ĐOẠN CHAT / TÀI LIỆU cắt ngang ở mọi ảnh từ `04-a` (ngăn cuộn, chưa đối chiếu Figma); lời mở *"Được,
mình soạn đề ngay."* ở 02 và 04 là chép nguyên văn ví dụ trong prompt `propose._CORE` — lời model,
không phải câu cố định, nhưng đọc như câu cố định. Trạng thái chưa có ảnh: câu 3/3 với `Xem lại ›`,
hàng `Khác: lớp 11`, lùi về câu 1, `Sửa` từ tóm tắt, F5 thẻ nhiều câu, chữ rê chuột, Esc và lưu ô
trống — các trạng thái ấy đã kiểm bằng DOM hay vitest, không bằng ảnh.

## Case đã đổi trong lần này

- Case 15, mục *Đạt khi* A1: bỏ *"Nút `Đóng` vẫn đó"*, thay bằng *"`Đóng` ẩn lúc sửa"* (variant
  `626:2730`).
