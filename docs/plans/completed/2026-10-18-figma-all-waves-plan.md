# Figma cho cả bốn đợt của đợt tất định

## Goal

Vẽ trước mọi thay đổi màn hình của 23 việc (`2026-10-18-deterministic-batch-master-plan.md`) trên
Figma `mOe2ZmrqOq1Uix45v6PNGD`. Mục đích là để người dùng duyệt một lần trước khi viết code. Xong thì
**dừng**, chờ người dùng review. Không code gì trong plan này.

## Scope

- **Trong phạm vi:** artboard và component trên trang `Screen — Teacher` và `Screen — Student`, chỉ
  cho các việc 3, 4, 7, 8, 10, 11, 12, 14, 15, 17, 18, 19, 20, 21, 22.
- **Ngoài phạm vi:**
  - code;
  - `docs/overview/teacher-surface.md`: luật mới mà artboard chở được ghi vào đó ở đợt code, cùng
    change set với màn ấy.
- **Luật vẽ:**
  - dùng component, variable và density `Teacher` có sẵn, không đặt mã hex trần;
  - mỗi artboard 1440×900;
  - chữ tiếng Việt, theo luật `docs/overview/teacher-surface.md`: ba màu trạng thái ngang hàng, không
    nhãn *nên chọn*, mỗi lời của Kriky là chữ model viết, chữ của hệ thống chỉ ở thông báo hệ thống.
- **Không commit:** Figma không nằm trong repo. Plan này ghi node id của mọi chỗ đã đổi.

## Files

- Figma `mOe2ZmrqOq1Uix45v6PNGD`, các trang `Screen — Teacher` và `Screen — Student`.
- Plan này (cột *Node đã đổi* của bảng dưới).

## Ordered Tasks

- [x] F0. Nạp skill `/figma-use`. Liệt kê mọi trang bằng plugin API: MCP chỉ thấy trang
  `Foundations`, còn artboard như `12:46` vẫn đọc được theo id. Ghi id của các trang và artboard vào
  mục *Status*.
- [x] F1 (việc 3). Rail `128:435`: bỏ huy hiệu "3" của `Rail destination` *Bảng theo dõi*, trên mọi
  artboard có rail.
- [x] F2 (việc 4). `Action result card` `đã-phát-hành` `10:45`: bỏ nút *Thu hồi*, cho khớp code.
- [x] F3 (việc 7). Hộp nộp lượt (22b): dòng *"câu làm đúng được 0,5 điểm"* là giá trị BE gửi. Chỉ
  sửa nếu artboard vẽ nó như chữ cố định khác ngữ cảnh.
- [x] F4 (việc 8). Bốn chỗ câu luật giờ:
  - `Publish settings` `534:20`, `542:20`, `517:17`;
  - khối ĐÃ PHÁT HÀNH;
  - màn học sinh.

  Đổi *"có thể nộp lúc"* thành *"nộp muộn nhất lúc"*, *"bị DỪNG"* thành chữ thường, dùng dấu *—*,
  không để *"làm."* rớt dòng. Mốc nào khác ngày giờ mở thì in thêm ngày.
- [x] F5 (việc 11). Composer sau khi tải tài liệu: bỏ chip tự đính, nếu artboard có vẽ.
- [x] F6 (việc 10). Màn xem điểm của học sinh: một variant có thông báo *lượt chữa đã hết giờ*, cho
  lúc màn tự chuyển về đây.
- [x] F7 (việc 14). `System notice` `619:20`: vẽ lại thẻ báo cho dễ nhìn (chữ `OUTLINE_REFUSED` giữ
  nguyên), và cập nhật artboard chat dùng nó.
- [x] F8 (việc 12). Panel đề cộng `Question card` `267:30`:
  - ô hỏng có nút *Soạn lại*;
  - câu đánh số theo vị trí, không chừa lỗ.
- [x] F9 (việc 15). Panel đề trống:
  - nút *Xoá đề nháp*;
  - một variant của `Consequence dialog` (khuôn `592:3180`);
  - variant `Action result card` *đã xoá*.
- [x] F10 (việc 17). Panel, cả đề trống lẫn đề có câu:
  - nút *Thêm từ ngân hàng*;
  - hộp chọn câu từ ngân hàng;
  - chip nguồn thật trên `Question card`.
- [x] F11 (việc 18, 20). Dựng các màn còn thiếu theo artboard có sẵn:
  - *Bảng theo dõi*;
  - `9 · Danh sách lớp học` `180:753`;
  - `10 · Chi tiết lớp` `183:874`;
  - *Các bài kiểm tra*;
  - *Ngân hàng câu hỏi*;
  - `11 · Kết quả bài kiểm tra trong lớp`, cộng nút *Xuất .xlsx*;
  - bài làm của một học sinh;
  - ô tìm kiếm đoạn chat.
- [x] F12 (việc 19, 21). *Bảng theo dõi*:
  - khối thống kê gộp theo lớp, chỉ tính đề đã hết hạn chữa;
  - hàng đợi review: báo cáo *giải thích chưa rõ*, và câu có tỉ lệ sai bất thường;
  - artboard mới: giáo viên đọc một báo cáo và sửa lời giải.
- [x] F13 (việc 22). Đăng nhập:
  - ô tài khoản ở góc dưới trái rail, hai trạng thái: chưa đăng nhập ghi *Đăng nhập*; đã đăng nhập
    hiện avatar và tên;
  - menu nổi Settings, Usage, Language, Get help, Log out; chỉ Log out bấm được, bốn mục kia mờ;
  - hộp đăng nhập bằng SĐT, email hay Google (Google chỉ là giao diện), và form đăng ký giáo viên;
  - màn đăng nhập học sinh;
  - nhập danh sách lớp trên `Chi tiết lớp`: gõ tay, hay tải `.csv`/`.xlsx` có cột mã tuỳ chọn;
  - màn xem trước, đánh dấu *trùng*;
  - hộp *mật khẩu chỉ hiện một lần*;
  - `Student top bar` `281:16`: *Đăng xuất* chạy thật.
- [x] F14. Chụp từng artboard đã đổi. Một subagent soát ảnh so với luật màn hình của
  `teacher-surface.md` và ADR liên quan.
- [x] F15. **DỪNG.** Báo người dùng danh sách node, ảnh, và năm câu ở mục *Câu đem ra buổi review
  Figma* của plan tổng.

## Validation Checks

| Kiểm | Cách |
| --- | --- |
| Mỗi việc có Figma thì có node đã đổi | bảng *Node đã đổi* đủ hàng |
| Không mã hex trần trong node mới | plugin API quét `fills` và `strokes` không gắn variable |
| Mỗi artboard mới 1440×900, density `Teacher` cho màn giáo viên | đọc kích thước và mode |
| Ảnh đúng luật | subagent chấm ảnh ở F14 |

### Node đã đổi

| Việc | Node | Đổi gì |
| --- | --- | --- |
| 3 | 19 instance `Rail destination` trên `Screen — Teacher` (vd `170:691`, `180:762`, `205:1009`) | `Có badge` = false; component set `11:40` giữ property cho số thật sau này |
| 4 | `Action result card` `đã-phát-hành` `10:45` | **không đổi**: Figma vốn không có nút *Thu hồi*, chỉ có dòng an toàn |
| 7 | `22b · Xác nhận nộp lượt làm lại` `639:664`, text `639:699` | **không đổi**: *"câu làm đúng được 0,5 điểm"* đã là ô giá trị |
| 8 | `Publish settings` `67:29`, `77:368`, `496:64`, `505:45`, `552:2`, `552:4`, `269:1330`, `269:1368`, `496:65`, `505:46`, `644:752`, `644:753`; `Consequence dialog — phát hành đề` `68:15`, `269:1375`; `Time status` `278:12`; override trên artboard 7 `I70:314;67:29` | *"Vào làm bài tới hết"*, *"—"*, *"nộp muộn nhất lúc"*, *"bị dừng"* thường, dấu `;`; khối ĐÃ PHÁT HÀNH in *"14:25 · 07/10"* vì hạn chữa rơi sang ngày sau giờ mở |
| 11 | `2 · Kèm tài liệu` `85:327` | **không đổi**: chip trên artboard là kéo-thả có chủ ý, không phải tải lên |
| 10 | `16b · Kết quả — lượt chữa vừa hết giờ` `652:3384` (trang `Screen — Student`), khung `ran-out` `652:3413` | artboard mới: thông báo *"Lượt chữa vừa rồi đã hết giờ nên được nộp luôn. Câu bỏ trống trong lượt ấy tính là sai."*, nền sunken viền line/strong như `Time status` *sắp bị cắt* |
| 14 | `System notice` `619:20` (vẽ lại tại chỗ, thêm `badge` `652:3465`, `body` `652:3466`, `source` `652:3467`); artboard `16 · Dàn ý bị trả về tới trần` `652:3468` | nền surface, viền line/default, vòng `!` **trung tính** (sunken + ink/muted: component chở cả lỗi lẫn *đang chạy việc khác*, ADR-12), dòng nguồn *Thông báo của hệ thống*; chữ thông báo giữ nguyên |
| 12 | component set `Failed slot` `652:3635` (`hỏng` `652:3611`, `đang soạn lại` `652:3623`); artboard `17 · Ô câu soạn hỏng — Soạn lại` `652:3636` | ô nét đứt, chip *Chưa soạn được* họ `answer/incorrect` (ADR-12: hệ thống không làm được việc), nút secondary *Soạn lại*, ghi chú *tối đa 3 lần*; đầu panel *"10 câu · 1 câu chưa soạn được"* |
| 15 | `Consequence dialog — xoá đề nháp trống` `652:3899`; variant `tạo-đề-trống — đã xoá` `652:3900` trong `10:63`; artboard `18 · Đề nháp trống` `653:2846`, `18b · Xoá đề nháp trống — hộp xác nhận` `653:3095` | link *Xoá đề* ở đầu panel chỉ khi đề trống; thẻ cũ giữ đầu đề *Đã tạo đề* (không nấc thứ năm), dòng an toàn *"Đề trống này đã xoá"*; Duyệt đề tắt (sunken + ink/faint) |
| 17 | component set `Source chip` `654:25`; instance `654:26` trong `Question card` `267:28` (mô tả viết lại); `Bank row` `655:38`; `Bank picker` `655:39`; artboard `19 · Panel — chip nguồn và nút thêm câu từ ngân hàng` `655:3974`, `19b · Thêm câu từ ngân hàng — hộp chọn` `655:4222` | chip trung tính *Kriky soạn* / *Từ ngân hàng*; nút secondary *＋ Thêm câu từ ngân hàng* ở cuối danh sách câu (và giữa panel khi đề trống, artboard 18); hộp chọn: tìm, đếm, ba trạng thái hàng, nút chính đếm số câu chọn |
| 18 | `Assessment row` `655:4474`, `Bank question row` `655:4483`, `Answer row` `656:4080`; artboard `21 · Các bài kiểm tra` `655:4929`, `22 · Ngân hàng câu hỏi` `655:5226`, `23 · Bài làm của một học sinh` `656:4089`, `22b · Ngân hàng câu hỏi — sửa một câu` `666:5816` | (artboard 24 *tìm đoạn chat* đã xoá theo người dùng) ba màn vật thể theo nhịp cột của `Class row`; chỉ *Đang mở* và *Đang chữa bài* tô processing |
| 20 | `11 · Kết quả bài kiểm tra trong lớp` `205:1000`, `page-header` | bật *Hành động*: *"Xuất bảng điểm (.xlsx)"* |
| 19 | `Review item row` `657:46`, `Class stat row` `657:55`; artboard `20 · Bảng theo dõi` `657:3889` | hai bảng: *Cần bạn xem* (giải thích chưa rõ, tỉ lệ sai cao; không tô màu loại) và *Điểm gộp theo lớp* (chỉ đề đã hết hạn chữa) |
| 22 | `Account` `658:63` (`chưa đăng nhập` `658:46`, `đã đăng nhập` `658:49`, `menu mở` `658:56`); `Account menu` `658:64`; `Sign-in dialog` `659:116` (`SĐT` `659:46`, `email` `659:70`, `đăng ký` `659:94`); `Student sign-in card` `659:5672`; `Roster import` `660:139` (`nhập` `660:52`, `xem trước` `660:73`, `mật khẩu` `660:114`); `Student row` `179:15` (tên đăng nhập theo luật mới); artboard `26 · Chưa đăng nhập — hộp đăng nhập` `659:5160`, `26b · Tạo tài khoản giáo viên` `659:5311`, `27 · Đã đăng nhập — menu tài khoản` `659:5460`, `28` `660:5367`, `28b` `660:5512`, `28c` `660:5677`; trang `Screen — Student`: `12 · Đăng nhập của học sinh` `659:5676` | ô tài khoản thêm vào rail của **mọi** artboard giáo viên (ngăn `lists` co 60); chưa đăng nhập thì rail không hiện đoạn chat và tài liệu; menu năm mục, chỉ *Đăng xuất* bấm được; artboard 10 nút đầu trang đổi *"Nhập từ CSV"* → *"Thêm học sinh"*, tên đăng nhập của 12 em theo luật mới |
| 21 | artboard `25 · Báo cáo giải thích chưa rõ — sửa lời giải` `657:4265` (instance `Question card — đang sửa` tầng *cách giải* `657:4596`, ẩn `edit-actions`) | trái: sửa cách giải, *Lưu lời giải* / *Đánh dấu đã xem*, ghi chú *điểm đã chấm không đổi*; phải: thẻ từng báo cáo (ai, lúc, thời điểm ADR-19, lời ghi, link hội thoại) |

## Status

- 18/10/2026: plan mở.
- F0: file có sáu trang. `Foundations` `0:1`, `Components` `2:47`, `Screen — Teacher` `12:2`,
  `Screen — Student` `278:2`, `Linh vật — Dế Mèn` `27:2`, `Assets — Dế Mèn` `46:2`. MCP `get_metadata` chỉ
  liệt kê trang đầu; plugin API thấy đủ. *Bảng theo dõi*, *Các bài kiểm tra*, *Ngân hàng câu hỏi* chưa có
  artboard trước đợt này.
- F1–F13 xong. F14: một subagent soát 22 artboard. Đã sửa:
  - màu theo ADR-12 (thông báo hệ thống trung tính, ô hỏng đỏ);
  - số liệu và tên đề lệch nhau giữa các artboard mới;
  - lời Kriky xưng *tôi* lẫn *mình*;
  - câu chữ của ba hộp thoại;
  - cột hẹp làm rớt chữ.
- Còn lệch, có từ trước đợt này, không sửa:
  - artboard 11 chấm thang 10 với số câu đúng không khớp thang 1/0,5/0;
  - mã học sinh artboard 10 dạng `HS12A0xx`, trang học sinh dạng `HS2026-1204`. Hộp nhập danh sách
    mới dùng dạng của seed `HS2026-…`;
  - artboard 7 cho câu luật nêu số thật khi ô nhập còn trống.
- F15: dừng chờ người dùng review.
- 18/10/2026, review lần 1 của người dùng: sửa theo 26 ý của người dùng. Câu trả lời ghi ở plan
  tổng, mục *Người dùng chốt ở buổi review Figma lần 1*. Node mới hay đổi:
  - `Tooltip` `664:95`, `Class progress popover` `665:62`;
  - `Class row` `178:19` có ba cột tiến độ; `Student row` `179:15` bỏ cột trạng thái;
  - `Bank question row` bỏ cột đề gốc; `Answer row` bỏ cột lượt chữa; `Review item row` bỏ cột mới
    nhất;
  - `Roster import` `660:139` làm lại; `Account` `658:63` và `Account menu` `658:64` có icon SVG 12;
  - artboard 25 chỉ đọc (thẻ `666:5790`); artboard mới `22b` `666:5816`; artboard 24 xoá.
  - Mã học sinh trên artboard 10, 23 và `Student top bar` là số thứ tự (Nguyễn Minh Anh = 1204).
- Subagent soát lần 2: bốn điểm chưa đúng (tên cột màn 9, số trên popover, chú thích 28b che nhầm
  dòng, tiêu đề TRẠNG THÁI của bảng đề ở màn 10 bị xoá nhầm). Cả bốn đã sửa.
- Còn để nguyên, có từ trước đợt này:
  - tên và trạng thái của *Đề 15 phút / Kiểm tra 15 phút — Hàm số* lệch nhau giữa artboard 7, 8, 10,
    11 và các màn mới;
  - bộ phương án Câu 6 ở artboard 6, 15, 19 khác trang học sinh;
  - Kriky xưng *tôi* ở artboard 5, 7, 8, 15;
  - nút *Hoàn tác* ở artboard 7.
- Xếp lại theo luồng, đọc trái sang phải:
  - `Screen — Teacher`: ba hàng có nhãn — luồng chat, màn vật thể, tài khoản — cộng một hàng ghi chú
    và biên bản đã duyệt;
  - `Screen — Student`: hai hàng — pha 1, pha 2.
  - Số trên tên artboard giữ nguyên, vì tài liệu trỏ theo số.
- 18/10/2026: người dùng duyệt Figma ("oke duyệt, tiếp tục làm các phần khác nhé"). Plan đóng.
