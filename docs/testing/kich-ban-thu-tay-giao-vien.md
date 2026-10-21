# Kịch bản thử tay đầu-cuối — từ lúc giáo viên đăng nhập tới bảng điểm của cả lớp

Một người ngồi trước trình duyệt, đi hết **một vòng đời** của một bài kiểm tra:
1. giáo viên đăng nhập và tạo học sinh;
2. soạn đề với Kriky, duyệt, phát hành;
3. học sinh làm pha 1 và chữa ở pha 2;
4. giáo viên đọc báo cáo, bảng điểm, tệp `.xlsx`.

Mỗi bước có ba phần:
- **Làm**: bấm gì, gõ gì, nguyên văn.
- **Phải thấy**: chữ in nghiêng là chữ nguyên văn trên màn; số trong ngoặc là artboard Figma.
- **Sai nếu**: những hình dạng hỏng đã gặp hay dễ gặp.

Kịch bản này **không** thay bộ ca cố định `cases/`. Bộ ca đo chất lượng lời Kriky ở từng tình huống;
kịch bản này đo **luồng**: mọi màn nối được với màn sau, không chỗ nào kẹt. Lời Kriky ở chặng 3 vẫn soi
theo tám luật và hai luật khối bước của `huong-dan.md`.

Kết quả mỗi lần chạy ghi ở `ket-qua/<ngày>-<commit>-dau-cuoi-<model>.md`, **không** ghi vào file này.

---

## Chặng 0 — chuẩn bị

1. Hạ tầng (`.\dev.ps1 infra-up`) và ba tiến trình: `.\dev.ps1 be`, `.\dev.ps1 agent`, `.\dev.ps1 fe`
   (`docs/local-development.md`). Tài liệu không nằm trong luồng chính, nên không cần `ingest`,
   `document`, `index` (xem *Phụ lục — tài liệu*).
2. Model là `claude-haiku-5-5` hoặc `gpt-4o-mini`: đọc dòng `model=` trong log AGENT lúc khởi động.
   Một vòng tốn khoảng 15–30 lượt gọi model: chat giáo viên, sáu job soạn câu, trợ lý của học sinh,
   câu làm lại. Ước 0,05–0,15 USD với Haiku.
3. **Không `db-reset`.** Kịch bản chạy được nhiều lần trên cùng một database:
   - giáo viên luôn là **GV-001** *Cô Phạm Thu Lan* của seed; SĐT, email và mật khẩu ở
     `SAMPLE_TEACHER` trong `services/be/src/be/seed.py`;
   - lớp luôn là **12A**;
   - chọn một **mã vòng** chưa dùng, dạng `V3`, và gắn nó vào tên học sinh, tên đề, SĐT của tài khoản
     thử ở chặng 1. Nhờ vậy hàng của vòng trước không lẫn vào bảng điểm của vòng này. Mã vòng đã
     dùng: đọc tên đề trong *Các bài kiểm tra*.
4. Mở `http://127.0.0.1:5173/#/teacher`, cửa sổ rộng ít nhất 1440 × 900. Dùng `127.0.0.1`, không
   `localhost` (`docs/local-development.md`).
5. Ghi giờ bắt đầu. Chặng 4 đặt giờ theo đồng hồ thật, và chặng 8 phải chờ qua hạn chữa: cả vòng mất
   khoảng một giờ đồng hồ.
6. Có sẵn một **cửa sổ ẩn danh** (hay một trình duyệt khác) cho học sinh. Giáo viên và học sinh mỗi vai
   một cookie (ADR-36), nhưng tách cửa sổ thì không bao giờ nhầm ai đang đăng nhập.
7. Một tờ giấy (hay ghi chú riêng) để chép mật khẩu học sinh ở 2.4. **Không** ghi mật khẩu vào biên
   bản.

---

## Chặng 1 — tài khoản giáo viên (Figma 26, 26c, 26b, 27)

### 1.1 Màn đăng nhập

**Làm:** mở `#/teacher` khi chưa đăng nhập. Nếu đang đăng nhập thì bấm ô tài khoản ở góc dưới trái rail,
bấm *Đăng xuất*.

**Phải thấy (26):** hộp *Đăng nhập vào Kriky*; **một ô** *Số điện thoại / email*, không có tab SĐT /
Email; ô *Mật khẩu*; nút *Đăng nhập*; nút *Tiếp tục với Google*; dòng *Chưa có tài khoản? Tạo tài
khoản*. Rail vẫn có, phần đoạn chat ghi *Đăng nhập để thấy các đoạn chat và tài liệu của bạn.*

**Làm tiếp:** bấm *Tiếp tục với Google*.

**Phải thấy:** *Đăng nhập bằng Google chưa có. Hãy dùng số điện thoại hoặc email.*

### 1.2 Sai mật khẩu

**Làm:** gõ SĐT của GV-001, mật khẩu `sai-mat-khau`, bấm *Đăng nhập*.

**Phải thấy (26c):** dòng đỏ *Số điện thoại, email hoặc mật khẩu không đúng.*; ô SĐT giữ nguyên chữ; vẫn ở
màn đăng nhập.

**Sai nếu:** câu báo phân biệt *sai mật khẩu* với *không có tài khoản* (ADR-36: không lộ ai có tài
khoản).

### 1.3 Tạo tài khoản thử

**Làm:** bấm *Chưa có tài khoản? Tạo tài khoản*. Form có bốn ô:
- *Họ và tên*: `Thầy Thử Nghiệm <mã vòng>`;
- *Số điện thoại*: `099900000` + chữ số của mã vòng (ví dụ `0999000003`);
- *Email*: `thu.<mã vòng>@example.com`, viết thường;
- *Mật khẩu*: tuỳ ý, ít nhất 8 ký tự.

Bấm *Tạo tài khoản*.

**Phải thấy (26b → 27):** vào thẳng bề mặt giáo viên, không phải đăng nhập lại; ô tài khoản góc dưới trái
có avatar và tên vừa gõ.

**Làm tiếp:** rail → *Danh sách lớp học*.

**Phải thấy:** *0 lớp · 0 học sinh* và bảng không có hàng. Tài khoản mới chưa có lớp, và chưa có đường
tạo lớp (backlog).

### 1.4 Menu tài khoản, đăng xuất, đăng nhập GV-001

**Làm:** bấm ô tài khoản.

**Phải thấy (27):** menu nổi *Cài đặt*, *Mức sử dụng*, *Ngôn ngữ*, *Trợ giúp*, *Đăng xuất*. Bốn mục đầu
mờ, chỉ *Đăng xuất* bấm được.

**Làm tiếp:** bấm *Đăng xuất*. Đăng nhập lại bằng **email** của GV-001, lần này dùng email để thử ô gộp.

**Phải thấy:** ô tài khoản ghi *Cô Phạm Thu Lan*; rail có các đoạn chat cũ của GV-001.

---

## Chặng 2 — lớp và học sinh (Figma 9, 10, 28, 28d, 28b, 28c, 10b)

### 2.1 Danh sách lớp học

**Làm:** rail → *Danh sách lớp học*.

**Phải thấy (9):**
- bảng các lớp của GV-001;
- cột *LỚP*, *KHỐI / MÔN*, *SĨ SỐ*, *ĐỀ ĐANG MỞ*, rồi ba cột tiến độ *CHƯA NỘP BÀI*, *XONG GIAI ĐOẠN
  1*, *XONG GIAI ĐOẠN 2*; mỗi đầu cột một dòng.

Lớp không có đề đang mở thì ba cột tiến độ ghi *—*. Ghi lại sĩ số của *Lớp 12A*.

### 2.2 Chi tiết lớp 12A

**Làm:** bấm hàng *Lớp 12A*.

**Phải thấy (10):**
- đầu trang *Lớp 12A*, dòng *N học sinh · Toán 12*, nút *Thêm học sinh*;
- bảng *Bài kiểm tra đã phát hành cho lớp này*: cột *TÊN ĐỀ*, *TRẠNG THÁI*, *MỞ LÚC*, *ĐÓNG LÚC*,
  *ĐÃ NỘP*;
- bảng *Học sinh*: cột *HỌ TÊN*, *MÃ HỌC SINH*, *TÊN ĐĂNG NHẬP*, mỗi hàng một nút *Đặt lại mật khẩu*.

### 2.3 Thêm học sinh — gõ tay, có một tên trùng

**Làm:** bấm *Thêm học sinh*.

**Phải thấy (28):** hộp *Thêm học sinh vào lớp 12A*, hai lựa chọn *Gõ tên* và *Tải tệp .csv / .xlsx*,
dòng nhắc *Mỗi dòng một học sinh: họ và tên. Mã học sinh và tên đăng nhập do Kriky tạo.*, nút *Đóng*
và *Xem trước*.

**Làm:** ở *Gõ tên*, gõ bốn dòng:

```
Kiều Minh Châu <mã vòng>
Lò Văn Dũng <mã vòng>
Mạc Thị Én <mã vòng>
Nguyễn Minh Anh
```

Dòng cuối trùng tên một em đã có trong 12A (seed). Bấm *Xem trước*.

**Phải thấy (28b):** *Kiểm tra lại trước khi tạo tài khoản*; bảng *HỌ VÀ TÊN*, *TÊN ĐĂNG NHẬP*, *GHI
CHÚ*, *XÁC NHẬN*.
- Ba dòng đầu ghi *Mới*.
- Tên đăng nhập theo luật ADR-36: **từ cuối của họ tên** cộng chữ đầu các từ trước, bỏ dấu, viết
  thường. Mã vòng đứng cuối nên nó thành phần tên, ví dụ `Kiều Minh Châu V3` → `v3kmc`, `Lò Văn Dũng
  V3` → `v3lvd`, `Mạc Thị Én V3` → `v3mte`.
- Dòng *Nguyễn Minh Anh* ghi *Trùng tên trong lớp*, tên đăng nhập có số (`anhnm2`), ô xác nhận chưa tick.
- Chân hộp: *Sẽ tạo 3 tài khoản · 1 học sinh cần xác nhận*, nút *Quay lại* và *Tạo 3 tài khoản*.

**Sai nếu:** dòng trùng được tính vào số tài khoản khi chưa tick; tên đăng nhập còn dấu tiếng Việt.

### 2.4 Bỏ dòng trùng, tạo tài khoản

**Làm:** **không** tick dòng *Nguyễn Minh Anh*. Bấm *Tạo 3 tài khoản*.

**Phải thấy (28c):**
- hộp *Đã tạo 3 tài khoản*;
- câu *Hãy lưu lại mật khẩu — chỉ hiển thị một lần duy nhất.*;
- bảng *HỌ VÀ TÊN*, *TÊN ĐĂNG NHẬP*, *MẬT KHẨU*;
- nút *Xuất file Excel (.xlsx)* và *Đã lưu, đóng*.

**Chép tên đăng nhập và mật khẩu của Châu và Dũng** ra giấy: đây là lần duy nhất chúng hiện.

**Làm tiếp:** bấm *Xuất file Excel (.xlsx)*.

**Phải thấy:** tệp *Mật khẩu - 12A.xlsx* tải về, đúng ba hàng như trên màn.

**Làm tiếp:** bấm *Đã lưu, đóng*, rồi F5.

**Phải thấy:**
- ba em mới có trong bảng *Học sinh*, mã học sinh là số thứ tự do hệ thống cấp;
- **không** chỗ nào còn hiện mật khẩu;
- dòng đầu trang và sĩ số ở *Danh sách lớp học* tăng 3.

### 2.5 Thử tải tệp

**Làm:** bấm *Thêm học sinh*, chọn *Tải tệp .csv / .xlsx*.

**Phải thấy (28d):** dòng nhắc *Một cột họ và tên, dòng tiêu đề có thể có. Mã học sinh và tên đăng nhập do
Kriky tạo.*, nút *Chọn tệp*, dòng *Chưa chọn tệp nào · tối đa 1 MB*.

**Làm:** bấm *Chọn tệp*, chọn một `.csv` hai dòng:

```
Họ và tên
Kiều Minh Châu <mã vòng>
```

**Phải thấy:** tên tệp hiện thay cho *Chưa chọn tệp nào*, nút đổi thành *Chọn tệp khác*.

**Làm:** bấm *Xem trước*.

**Phải thấy (28b):**
- dòng ấy ghi *Trùng tên trong lớp*, vì em vừa được tạo ở 2.4;
- chân hộp *Sẽ tạo 0 tài khoản · 1 học sinh cần xác nhận*;
- nút *Tạo 0 tài khoản* bị khoá.

**Làm:** bấm *Quay lại*, rồi *Đóng*. Không tạo gì.

### 2.6 Đặt lại mật khẩu

**Làm:** ở hàng *Mạc Thị Én <mã vòng>*, bấm *Đặt lại mật khẩu*.

**Phải thấy (10b):** hộp *Đã đặt lại mật khẩu cho Mạc Thị Én <mã vòng>*, câu *Hãy lưu lại mật khẩu — chỉ
hiển thị một lần duy nhất.*, bảng một hàng có mật khẩu mới, nút *Đã lưu, đóng*. Đặt lại chạy ngay,
không hỏi lại; có nên hỏi lại hay không là backlog Tier 2 câu 30.

**Làm:** bấm *Đã lưu, đóng*. Em Én không đăng nhập ở các chặng sau.

---

## Chặng 3 — soạn đề với Kriky (Figma 1, 2, 3, 3b, 16, 5, 17, 6, 12, 14, 15, 19b, 19)

Mỗi lượt Kriky nói: soi tám luật của `huong-dan.md`.

### 3.1 Đoạn chat mới, lời nhắn

**Làm:** rail → *＋ Đoạn chat mới*. Gõ nguyên văn vào ô *Nhắn cho Kriky…*, bấm *Gửi*:

```
Tạo đề kiểm tra 15 phút chương Hàm số lớp 12, 6 câu trắc nghiệm.
```

**Phải thấy (1 → 4):**
- lời nhắn ở bên phải;
- ô nhắn đổi thành *Đang chờ Kriky trả lời…* và khoá, nút đổi thành *Đang gửi…*;
- khối bước của Kriky chạy, đúng một hàng có dải sáng.

Lượt xong thì ô nhắn mở lại.

### 3.2 Hỏi lại, nếu có

Kriky có thể hỏi lại (3b): mỗi câu một thẻ, nút riêng, đi từng câu, rồi tóm tắt và gửi gộp.

**Làm:** trả lời theo đúng bộ dữ kiện này, câu nào hỏi gì thì lấy đúng ý ấy:

| Kriky hỏi về | Trả lời |
| --- | --- |
| môn | *Toán* |
| khối hay lớp | *Khối 12*, hay *12A* nếu hỏi lớp |
| mức độ | *nhận biết và thông hiểu* |
| tài liệu, sách | *không dùng tài liệu* |
| dạng câu, số câu, thời gian | *trắc nghiệm*, *6 câu*, *15 phút* |

Có nút mang đúng ý ấy thì bấm nút. Không có thì bấm *Khác…*: ô gõ hiện ra, gõ ý ấy (ví dụ `Nhận biết và
thông hiểu, không dùng tài liệu.`) rồi gửi. Có nhiều câu thì sau câu cuối là thẻ tóm tắt; bấm gửi gộp. Chờ ô nhắn mở lại.

Kriky có thể hỏi một điều lời nhắn đã nói, ví dụ *Đề này dành cho khối nào?* dù lời nhắn ghi *lớp 12*.
Đó là chất lượng model (backlog Tier 4, *hỏi lại dù đủ mục*); trả lời rồi đi tiếp, ghi vào biên bản.

**Sai nếu:** một nút được đánh dấu *nên chọn*; một nút gợi lớp không có của GV-001.

### 3.3 Dàn ý, đồng ý

**Phải thấy (16):** lời dàn ý Kriky tự viết, các mục `Câu k–m` cộng lại đúng 6 câu, công thức dựng
hình, kết bằng một câu xin đồng ý.

Có thể thay vào đó là thông báo hệ thống *Kriky chưa nêu được dàn ý cho đề này. Bạn hãy thử lại nhé!*
(dòng riêng, không avatar). Đó là lỗi đã biết của model, backlog Tier 4: nó gửi một *công thức* có chữ ngoài
cặp `$`, BE từ chối. **Làm:** gõ `thử lại`, tối đa **sáu** lần; chương Hàm số gần như lần nào cũng gặp.
Ghi số lần vào biên bản, vì đó là chỉ số của lỗi; sáu lần vẫn hỏng thì dừng vòng và ghi *không đạt ở
3.3*.

**Làm:** khi có dàn ý, gõ `oke, soạn đi`.

**Phải thấy (5):**
- lời Kriky viết trước khi chạy (ví dụ *Được, mình soạn đề … ngay.*);
- khối bước *Đã làm 2 bước*: tạo đề trống, soạn câu hỏi;
- thẻ *Đã tạo đề "…"* có chip *Chưa duyệt · chưa phát hành*;
- lời kết (ví dụ *Mình đã soạn xong đề "…" với đủ 6/6 câu hỏi…*) khớp số câu trên thẻ.

Tên đề là tên **BE tự đặt** khi Kriky không truyền tên, ví dụ *Đề chương Hàm số* hay *Đề Hàm số*. Bước
3.4 đổi nó thành tên mang mã vòng.

### 3.4 Panel đề, đổi tên

**Làm:** bấm vào chính thẻ *Đã tạo đề*.

**Phải thấy (6):**
- panel phải: tên đề, dòng *6 câu · Toán 12 · <phạm vi>*; phạm vi do Kriky ghi, ví dụ *Hàm số* hay
  *chương Hàm số*;
- mỗi câu một thẻ: *Câu k*, chip *Kriky soạn*, nút *Sửa* và *Xoá*, dòng *Lời giải · 2 cách*;
- cuối danh sách là nút *＋ Thêm câu từ ngân hàng*;
- chân panel: *Bạn duyệt xong mới phát hành được. Học sinh chưa nhìn thấy đề này.* và nút *Duyệt đề*.

Nếu một ô hỏng (17): thẻ *Chưa soạn được* và nút *Thử lại*. Bấm *Thử lại*, đợi ô ấy thành câu.

**Làm:** cạnh tên đề, bấm *Đổi tên*. Xoá chữ cũ, gõ `Hàm số <mã vòng>`, bấm *Lưu*.

**Phải thấy:** đầu panel và thẻ trong chat cùng đổi sang tên mới, không cần F5 (ADR-31).

### 3.5 Lời giải một câu

**Làm:** ở câu 1, bấm *Lời giải · 2 cách*.

**Phải thấy (12):**
- hộp hai cách giải, rồi *MỖI PHƯƠNG ÁN NHIỄU GẮN MỘT LỖI*;
- phương án đúng ghi *✓ đúng*, mỗi phương án sai một dòng lỗi;
- công thức dựng hình, không còn dấu `$`.

**Làm:** bấm *Đóng*.

### 3.6 Sửa một câu

**Làm:** câu 2 → *Sửa*.

**Phải thấy (14):** thẻ mở thành ô sửa ba tầng *Đề bài*, *Phương án*, *Cách giải*, nhãn *Đang sửa*, nút
*Huỷ* và *Lưu*. Ô đề bài hiện chữ thô có `$`: đó là chữ để sửa, không phải lỗi.

**Làm:** thêm `(đề vòng <mã vòng>)` vào cuối đề bài, bấm *Lưu*.

**Phải thấy:** thẻ về dạng đọc, đề bài mới.

**Sai nếu:** dòng đỏ *Công thức có ký tự hỏng…* hiện ở ô không có ký tự hỏng.

### 3.7 Xoá một câu

**Làm:** câu 6 → *Xoá*.

**Phải thấy (15):** hộp *Xoá câu 6 khỏi đề?*, lời dẫn *Câu này chưa có trong ngân hàng câu hỏi — xoá rồi thì
không lấy lại được.*, nút *Giữ lại* và *Xoá câu*.

**Làm:** bấm *Xoá câu*.

**Phải thấy:** đầu panel *5 câu · …*.

### 3.8 Thêm một câu từ ngân hàng

**Làm:** bấm *＋ Thêm câu từ ngân hàng*.

**Phải thấy (19b):**
- hộp *Thêm câu từ ngân hàng*, ô tìm *Tìm theo nội dung câu hoặc mục kiến thức…*;
- mỗi câu một hàng: đề bài, rồi *mục kiến thức · tên đề nguồn*. Câu đã có trong đề này thì mờ, ghi *đã
  có trong đề này*;
- chân hộp *Đã chọn 0 câu*, nút *Đóng* và *Thêm vào đề* (khoá).

**Làm:** bấm một hàng không mờ.

**Phải thấy:** hàng đổi sang đã chọn; chân hộp *Đã chọn 1 câu*, nút thành *Thêm 1 câu vào đề*.

**Làm:** bấm *Thêm 1 câu vào đề*.

**Phải thấy (19):** đầu panel *6 câu*; câu 6 mang chip *Từ ngân hàng*.

**Làm tiếp:** đọc câu ấy và tự giải. Câu trong ngân hàng do model soạn ở các vòng trước. Nếu đáp án
khoá sai, ghi lại làm lỗi sản phẩm; vòng V1 đã gặp một câu như thế.

---

## Chặng 4 — duyệt và phát hành (Figma 7, 8)

### 4.1 Duyệt

**Làm:** chân panel → *Duyệt đề*.

**Phải thấy (7):**
- các câu khoá, không còn *Sửa*, *Xoá*;
- thẻ trong chat thành *Đã duyệt đề "Hàm số <mã vòng>"*, chip *Chưa phát hành cho học sinh*;
- dưới các câu là *Cài đặt phát hành*: dòng *LỚP* với một chip mỗi lớp, khối *PHA 1 — LÀM BÀI VÀ NỘP*
  (*Làm bài*, *Mở lúc*, *Đóng lúc*) và *PHA 2 — CHỮA BÀI* (*Phút mỗi câu*, *Hạn chữa xong*);
- nút *Hoàn tác* và *Phát hành đề*.

**Sai nếu:** form gợi sẵn một giờ nào đó.

### 4.2 Cài đặt giờ

**Làm:** bấm chip *12A* (nó hiện dấu ✓). Điền theo đồng hồ thật, gọi `T` là lúc này, làm tròn phút:

| Ô | Giá trị |
| --- | --- |
| Làm bài | `6` |
| Mở lúc | `T + 5 phút` |
| Đóng lúc | `T + 30 phút` |
| Phút mỗi câu | `2` |
| Hạn chữa xong | `T + 50 phút` |

Giờ đóng để rộng vì Châu và Dũng phải **vào** làm bài trước giờ đóng, mà chặng 5 của Châu (hỏi trợ lý,
chờ câu làm lại) mất 10–15 phút với người thật. Luật của BE (`teacher_routes.py`): giờ mở phải ở tương
lai; hạn chữa phải sau *giờ đóng + thời gian làm bài*. Điền quá lâu tới mức giờ mở đã qua thì BE từ chối
khi phát hành: đặt lại giờ mở rồi bấm lại.

**Phải thấy:** khung vàng dưới form đọc lại đúng giờ: *Vào làm bài tới hết … — nộp muộn nhất lúc …, và không
dừng người đang làm.* và *Chữa bài tới hết … — mỗi lượt 2 phút một câu; hết hạn thì lượt đang làm bị
dừng.*

### 4.3 Hộp xác nhận, phát hành

**Làm:** bấm *Phát hành đề*.

**Phải thấy (8):** hộp *Phát hành đề kiểm tra?*, câu *Đề sẽ hiển thị cho N học sinh của lớp 12A. Bạn còn
thu hồi được tới trước giờ mở.*, các dòng *Đề*, *Lớp*, *Thời gian*, *Hạn chữa*, *Thu hồi*, nút *Xem lại
cài đặt* và *Phát hành cho N học sinh*. *N* là sĩ số 12A sau 2.4.

**Làm:** bấm *Phát hành cho N học sinh*.

**Phải thấy:** panel ghi *ĐÃ PHÁT HÀNH*, *12A · N học sinh*, giờ mở và câu luật; thẻ trong chat thành *Đã
phát hành*, chip *Thu hồi được tới trước giờ mở, từ giờ mở thì không*.

Chờ tới giờ mở trước khi sang chặng 5. Trong lúc chờ có thể làm 7.2.

---

## Chặng 5 — học sinh Châu: sai hai câu, rồi chữa (Figma HS 12–23)

Ở **cửa sổ ẩn danh**.

### 5.1 Đăng nhập học sinh

**Làm:** mở `http://127.0.0.1:5173/#/`.

**Phải thấy (HS 12):** *Đăng nhập để làm bài*, ô *Tên đăng nhập* và *Mật khẩu*, nút *Đăng nhập*; dưới
nút không có dòng chữ nào.

**Làm:** gõ tên đăng nhập và mật khẩu của Châu đã chép ở 2.4, bấm *Đăng nhập*.

**Phải thấy (HS 13):** thanh trên *Kiều Minh Châu <mã vòng> · Lớp 12A · <mã học sinh>* và nút *Đăng
xuất*.

### 5.2 Danh sách bài

**Phải thấy (HS 13):** *Bài của tôi*; dòng *Hàm số <mã vòng>*:
- *Toán · 6 câu · làm bài 6 phút*;
- *Vào tới <giờ đóng>*, *Chữa tới <hạn chữa>*;
- trước giờ mở thì chip *Chưa tới giờ mở*, không có nút;
- từ giờ mở thì *Đang mở* và nút *Bắt đầu* (F5 để thấy).

Đề cũ của 12A cũng có, đúng trạng thái của em; em mới chưa làm đề nào nên đề đã đóng ghi *Đã đóng*.

**Sai nếu:** có chip *Đang chấm*: code không có trạng thái này (ADR-20).

### 5.3 Bắt đầu, làm bài, cố ý sai hai câu

**Làm:** bấm *Bắt đầu*.

**Phải thấy (HS 13b):** hộp *Bắt đầu làm bài?*, câu *Bắt đầu là đồng hồ chạy. Đóng trang hay mất mạng thì
đồng hồ vẫn chạy, không dừng lại được.*, dòng *Bài*, *Số câu*, *Thời gian làm*, nút *Để sau* và *Bắt đầu
làm bài*.

**Làm:** bấm *Bắt đầu làm bài*. Ở màn làm bài (HS 14), mỗi câu: bấm số câu ở dải chip bên phải, chọn một
phương án. Chọn đúng câu 3–6 và **cố ý chọn sai câu 1 và câu 2**. Đáp án đúng đọc ở panel giáo viên
(dấu ✓).

**Phải thấy:** đầu màn *Câu k / 6*; cột phải *Còn lại* đếm ngược, *CÒN n CÂU CHƯA TRẢ LỜI* giảm dần tới
0; chip câu đã trả lời đổi màu.

### 5.4 Nộp bài

**Làm:** bấm *Nộp bài*.

**Phải thấy (HS 15):** hộp *Nộp bài?*, *Nộp là kết thúc phần làm bài. Bạn không sửa được câu nào nữa.*,
*Đã trả lời 6 trên 6 câu*, *Chưa trả lời không còn câu nào*, *Sau khi nộp điểm này là điểm sàn, còn
nâng được*, nút *Quay lại làm tiếp* và *Nộp bài*. Không có dải cảnh báo câu trống.

**Làm:** bấm *Nộp bài* trong hộp.

### 5.5 Kết quả pha 1

**Phải thấy (HS 16):**
- *Đã nộp lúc … · còn 2 câu cần chữa*;
- nút *Hỏi trợ lý và làm lại dạng bài sai*;
- câu *Bạn có thể nâng điểm các câu sai bằng cách Hỏi trợ lý và làm lại dạng bài sai tới hết …*;
- mỗi câu một hàng: câu 1, 2 điểm 0; câu 3–6 điểm 1.

### 5.6 Hỏi trợ lý, báo cáo

**Làm:** bấm *Hỏi trợ lý và làm lại dạng bài sai*.

**Phải thấy (HS 17):**
- lời chào của trợ lý nêu đúng hai câu sai;
- cột phải *CÁC CÂU EM LÀM SAI*, kèm đáp án em chọn và đáp án đúng;
- câu *Phần này không tính giờ. Hỏi đến khi hiểu rồi hãy bấm làm bài mới.*;
- ô nhắn *Hỏi Kriky về bất kỳ câu nào bạn làm sai…*;
- nút *Làm bài mới · 2 câu · 4 phút*.

**Làm:** gõ `Câu 1 em sai ở đâu ạ?`, bấm *Gửi*. Đợi trợ lý trả lời.

**Phải thấy:** câu trả lời đi theo lời giải đã soạn của câu 1, không có con số độ tin hay mã lỗi.
Trợ lý trả lời xong lượt đầu thì nút *⚑ Báo cáo Trợ lý giải thích khó hiểu* mới hiện: phải có hơn một
lượt trợ lý, lời chào tính là một.

**Làm:** bấm *⚑ Báo cáo Trợ lý giải thích khó hiểu*.

**Phải thấy:** *Đã gửi báo cáo tới giáo viên.* Câu này hiện trong dải đỏ của thông báo lỗi; đó là lỗi đã
biết (xem cuối file), không phải báo cáo hỏng.

### 5.7 Lượt làm lại

**Làm:** bấm *Làm bài mới · 2 câu · 4 phút*.

**Phải thấy (HS 19):** hộp *Bắt đầu lượt làm lại?*, *Bấm là đồng hồ chạy ngay. Đóng trình duyệt cũng không
dừng nó.*, dòng:
- *Lượt này*: 2 câu, câu 1 và câu 2;
- *Vòng*: vòng 1, mỗi câu còn 3 vòng;
- *Thời gian*: 2 phút mỗi câu, 4 phút;
- *Hạn làm lại*.

Nút *Để sau* và *Làm bài mới*.

**Làm:** bấm *Làm bài mới*. Đợi câu sinh xong.

**Phải thấy (HS 21):**
- *Làm lại dạng bài sai · 2 câu · 4 phút*;
- *Câu 1 — Lượt làm lại thứ 1 / tối đa 3*;
- câu **mới**, cùng dạng câu gốc, khác số liệu;
- cột phải *CÂU CÒN PHẢI LÀM LẠI TRONG LƯỢT NÀY*.

**Làm:** tự giải hai câu, chọn đáp án đúng. Câu do model sinh: nếu có hai phương án cùng đúng về toán,
chọn phương án được khoá và ghi lại làm lỗi sản phẩm; vòng V1, V2 đã gặp. Phương án khoá đọc trong
database:

```
docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select order_index, options from round_items order by round_id desc, order_index limit 4;"
```
Bấm *Nộp bài*.

**Phải thấy (HS 22b):** hộp *Nộp lượt này?*, *Đã trả lời 2 trên 2 câu*, *Sau khi nộp câu làm đúng được 0,5
điểm*. Bấm *Nộp bài*.

### 5.8 Kết quả sau chữa

**Phải thấy (HS 23):**
- *Bài đã kết thúc · 5,0 trên 6 câu*, nếu chữa đúng cả hai;
- dưới câu 1 và câu 2 là hàng *Lượt làm lại · 1 · đúng*, kèm đề của lượt, điểm 0,5.

**Làm:** bấm *Đăng xuất*.

**Phải thấy:** về màn *Đăng nhập để làm bài*.

---

## Chặng 6 — học sinh Dũng đúng hết; học sinh Én không vào

**Làm:** cửa sổ ẩn danh, đăng nhập Dũng; *Bắt đầu* → *Bắt đầu làm bài*; chọn đúng cả sáu câu; *Nộp bài*
→ *Nộp bài*.

**Phải thấy:** *Bài đã kết thúc · 6,0 trên 6 câu*; không có nút *Hỏi trợ lý và làm lại dạng bài sai*. Link
*Xem lại phần chữa các câu sai* vẫn hiện dù em không sai câu nào: lỗi đã biết (xem cuối file). Bấm
*Đăng xuất*.

Dũng phải **vào** làm bài trước giờ đóng. Nếu chặng 5 kéo dài, cho Dũng làm ngay sau khi Châu nộp bài ở 5.4,
rồi quay lại 5.5.

Én không đăng nhập: em là học sinh *chưa nộp* ở chặng 7.

---

## Chặng 7 — giáo viên đọc kết quả (Figma 20, 25, 25b, 21, 9, 10, 11, 23, 22, 22b)

Về cửa sổ giáo viên.

### 7.1 Bảng theo dõi, báo cáo

**Làm:** rail → *Bảng theo dõi*.

**Phải thấy (20):**
- dòng phụ *k việc cần bạn xem · m lớp có đề đã hết hạn chữa*;
- khối *Cần bạn xem*: dòng *Giải thích chưa rõ · Hàm số <mã vòng> · 1 học sinh · 1 lượt báo cáo · Xem
  báo cáo*;
- khối *Điểm gộp theo lớp* **chưa** tính đề này, vì chưa hết hạn chữa.

**Làm:** bấm dòng ấy.

**Phải thấy (25):**
- *‹ Bảng theo dõi*, tên đề, *1 lượt báo cáo chưa xem · Lớp 12A*;
- *CÁC CÂU HỌC SINH BÁO CÁO ĐÃ LÀM SAI*: câu 1, câu 2, mỗi câu *1 trên 1 em báo cáo làm sai câu này* và
  link *Chỉnh sửa trong Ngân hàng câu hỏi ›*;
- nút *Đánh dấu đã xem*;
- *BÁO CÁO CỦA HỌC SINH*: *Kiều Minh Châu <mã vòng> · <giờ>*, *Làm sai: Câu 1, Câu 2*, *Không ghi gì
  thêm.*, link *Mở hội thoại hỏi trợ lý ›*.

**Làm:** bấm *Mở hội thoại hỏi trợ lý ›*.

**Phải thấy (25b):** hộp *Hội thoại hỏi trợ lý — Kiều Minh Châu <mã vòng>*, *Hàm số <mã vòng> · Lớp 12A ·
Chỉ đọc*, đúng lời chào, câu Châu hỏi và câu trợ lý trả lời. Bấm *Đóng*.

**Làm:** bấm *Đánh dấu đã xem*.

**Phải thấy:** về *Bảng theo dõi*; nếu không còn việc nào thì khối *Cần bạn xem* ghi *Không có việc nào
cần bạn xem.*

### 7.2 Các bài kiểm tra

**Làm:** rail → *Các bài kiểm tra*.

**Phải thấy (21):** cột *TÊN ĐỀ*, *TRẠNG THÁI*, *LỚP*, *MỞ LÚC*. *Hàm số <mã vòng>* đứng đầu, trạng thái
theo lúc xem:
- trước giờ mở: *Chưa tới giờ mở*, kèm *thu hồi được*;
- trong giờ: *Đang mở*;
- sau giờ đóng tới hạn chữa: *Đang chữa bài*;
- sau hạn chữa: *Đã kết thúc*.

Cột *MỞ LÚC* ghi *Mở … · …*, và từ giờ mở tới hạn chữa thêm dòng *chữa tới …*.

Lớp *12A*, *Mở … · …*, nút *Xem kết quả* từ giờ mở.

### 7.3 Danh sách lớp và tiến độ

**Làm:** rail → *Danh sách lớp học*.

**Phải thấy (9):** hàng *Lớp 12A* tính cả đề này ở *ĐỀ ĐANG MỞ*. Ba cột tiến độ cộng trên mọi đề đang mở:
- Châu và Dũng ở *XONG GIAI ĐOẠN 2*, vì cả hai đã chốt hết câu;
- mọi em chưa nộp, gồm Én, ở *CHƯA NỘP BÀI*.

Ba cột cộng lại bằng sĩ số nhân số đề đang mở.

### 7.4 Bảng điểm của đề — đích của kịch bản

**Làm:** *Lớp 12A* → bảng *Bài kiểm tra đã phát hành cho lớp này* → hàng *Hàm số <mã vòng>*. Hoặc nút *Xem
kết quả* ở 7.2.

**Phải thấy (11):**
- *‹ Lớp 12A*, tên đề, *Lớp 12A · 2/N đã nộp · thang 6 điểm · đóng lúc …*, nút *Xuất bảng điểm (.xlsx)*;
- bốn thẻ số: *CAO NHẤT 6,0*, *TRUNG BÌNH 5,5*, *TRUNG VỊ 5,5*, *THẤP NHẤT 5,0*;
- biểu đồ *PHÂN BỐ ĐIỂM · 2 BÀI*: ô `k` đếm bài trong `[k, k+1)`, bài 6,0 vào ô cuối, nên ô *5* có 2;
- bảng *HỌ TÊN*, *▾ ĐIỂM*, *SỐ CÂU ĐÚNG*, *THỜI GIAN LÀM*, *NỘP LÚC*, *GHI CHÚ*: hàng *Lò Văn Dũng
  <mã vòng> · 6,0 · 6/6* trên hàng *Kiều Minh Châu <mã vòng> · 5,0 · 4/6*, cả hai ghi chú *Đã chữa xong*.

*THỜI GIAN LÀM* tính bằng phút làm tròn: làm dưới nửa phút thì ghi *0 phút*.

Em chưa nộp không có hàng; *2/N* đếm các em ấy ở mẫu số. *N* là sĩ số **hiện tại** của 12A, kể cả em
được thêm sau khi đề phát hành (ví dụ học sinh của một vòng sau). Các em của vòng trước làm đề **khác**,
nên không có hàng ở đây.

**Sai nếu:** hàng không xếp theo điểm giảm dần rồi tên; trung vị, trung bình không khớp bảng.

### 7.5 Xuất bảng điểm

**Làm:** bấm *Xuất bảng điểm (.xlsx)*, mở tệp *Bảng điểm - Hàm số <mã vòng> - 12A.xlsx*.

**Phải thấy:**
- cột *Mã học sinh*, *Họ tên*, *Câu 1* … *Câu 6*, *Tổng*;
- **mọi** học sinh của 12A một hàng; em chưa nộp thì ô trống;
- Châu: 0,5 · 0,5 · 1 · 1 · 1 · 1 · 5; Dũng: sáu ô 1, tổng 6.

### 7.6 Bài làm của một học sinh

**Làm:** ở màn 11, bấm hàng Châu.

**Phải thấy (23):**
- *‹ Hàm số <mã vòng> · Lớp 12A*, *Kiều Minh Châu <mã vòng>*, *Mã học sinh … · nộp lúc … · đã chữa xong*;
- bốn thẻ *ĐIỂM 5,0 / 6*, *ĐÚNG NGAY LẦN ĐẦU 4 / 6*, *LƯỢT CHỮA ĐÃ LÀM 1*, *GIẢI THÍCH CHƯA RÕ 1*;
- bảng *CÂU*, *EM CHỌN*, *ĐÁP ÁN*, *ĐIỂM*: câu 1, 2 điểm 0,5, còn lại 1.

Đề bài có công thức ở cột *CÂU* vỡ thành nhiều dòng (chữ, công thức, chữ): lỗi đã biết (xem cuối file).

### 7.7 Ngân hàng câu hỏi, sửa lời giải

**Làm:** rail → *Ngân hàng câu hỏi*.

**Phải thấy (22):** *n câu · từ m lần duyệt đề*; cột *CÂU HỎI*, *MỤC KIẾN THỨC*, *KHỐI / MÔN*. Các câu của
đề vòng này đã vào ngân hàng lúc duyệt; câu 2 có chữ *(đề vòng <mã vòng>)*.

**Làm:** bấm hàng câu 2.

**Phải thấy (22b):**
- panel *Sửa câu trong ngân hàng*, dòng mục kiến thức;
- ô sửa *Câu trong ngân hàng* ba tầng *Đề bài*, *Phương án*, *Cách giải*, nút *Huỷ* và *Lưu*;
- chân panel *Chỉ sửa bản trong ngân hàng. Câu đã nằm trong đề đã phát hành không đổi; đề sau lấy câu
  này sẽ dùng bản mới.*

**Làm:** mở tầng *Cách giải*, thêm `(sửa ở ngân hàng, vòng <mã vòng>)` vào cuối ô *Lời giải 1*, bấm *Lưu*.

**Phải thấy:** về danh sách ngân hàng. Mở lại câu thì thấy chữ vừa thêm. Câu 2 trong đề đã phát hành
(màn 23, hay *Lời giải* ở panel) **không** đổi (ADR-35).

---

## Chặng 8 — sau hạn chữa (Figma 20, 11, 21)

**Làm:** chờ qua *Hạn chữa xong* (khoảng `T + 50 phút`). Mở lại *Bảng theo dõi*, *Các bài kiểm tra* và
màn 11.

**Phải thấy:**
- *Điểm gộp theo lớp* (20) tính thêm đề này cho 12A: *ĐỀ ĐÃ KẾT THÚC* tăng 1, điểm quy về thang 10
  (Châu 8,3, Dũng 10,0) gộp với các đề đã kết thúc trước;
- biểu đồ *TỈ LỆ BÀI SAI THEO MỤC KIẾN THỨC* có mục kiến thức của câu 1, 2;
- *Các bài kiểm tra*: đề *Đã kết thúc*;
- màn 11: ghi chú không đổi, vì cả hai em đã chữa xong. Một em còn câu chưa chữa thì ghi *Hết hạn
  chữa*.

Dòng *Tỉ lệ sai cao* cần trên 20 bài (ADR-34), nên **không tới được** trong một lần thử tay. Không tính
là trượt.

---

## Phụ lục — tài liệu (tuỳ chọn)

Cần thêm ba tiến trình `.\dev.ps1 ingest`, `document`, `index`.

**Làm:** rail → *TÀI LIỆU* → nút tải lên, chọn một PDF có chữ.

**Phải thấy (1, 2):** chip *Đang xử lý…*, rồi *Đang dựng mục lục…*, rồi sẵn sàng, có số trang. Tệp không
có chữ thì *Không đọc được chữ*.

Đề theo sách và các tình huống tài liệu đo ở `cases/04` và `cases/13`.

---

## Những thứ đã biết — gặp thì không phải phát hiện mới

1. **Đóng tab giữa lúc Kriky đang làm.** Lượt bị cắt ngay chỗ nó đang đợi: các bước đã ghi còn đó,
   nhưng **không có câu kết**, và nếu là lượt đầu thì đoạn chat **chưa có tên** (nợ số 1 của ADR-25).
2. **Chưa có đường tạo lớp**: lớp chỉ đến từ seed (ADR-13, backlog Tier 2 câu 28).
3. **Dàn ý bị từ chối vì công thức có chữ ngoài `$`** (3.3), và **câu model sinh có đáp án khoá sai hay
   hai phương án cùng đúng** (3.8, 5.7): chất lượng model, backlog Tier 4.
4. Lỗi giao diện ghi ở backlog, mục *Lộ ra khi chạy kịch bản thử tay đầu-cuối*:
   - công thức trong mục kiến thức hiện nguyên `$…$` (Ngân hàng, hộp thêm câu, biểu đồ ở Bảng theo dõi);
   - link *Xem lại phần chữa các câu sai* hiện cả khi không sai câu nào (6);
   - màn trống của đoạn chat ghi *Kriky sẽ tạo lớp…*;
   - thanh trên của học sinh ghi mã trần, Figma ghi *Mã …* (5.1);
   - đề bài có công thức vỡ dòng ở màn 23 (7.6);
   - *Đã gửi báo cáo tới giáo viên.* hiện trong dải lỗi (5.6).
