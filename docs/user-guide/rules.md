# Luật viết hướng dẫn sử dụng

Luật cho `docs/user-guide/`, cuốn PDF người dùng gửi cho giáo viên và học sinh thật. Đây **không phải
báo cáo**, nên luật chọn chữ của `docs/report/rules.md` (từ điển, chú thích thuật ngữ) không áp ở đây.
Hai luật trình bày của báo cáo thì vẫn dùng: bảng `booktabs` (qua `bangtra`), và chữ trong hình, kể cả
ảnh chụp, ≥ 7pt khi in ra. Ảnh chụp không có caption: tiêu đề việc ngay trên nó đã nói nó là gì.

## 1. Người đọc và giọng

| Phần | Gọi người đọc | Kriky là |
| --- | --- | --- |
| Đầu sách, Làm quen | "bạn" | "Kriky" |
| Phần I, giáo viên | "thầy cô" | "Kriky" |
| Phần II, học sinh | "em" | "Kriky" |

App có chỗ gọi Kriky là "trợ lý" (nút *Hỏi trợ lý và làm lại dạng bài sai* của học sinh, *Mở hội thoại
hỏi trợ lý ›* của giáo viên). Khi trỏ vào nút thì chép đúng chữ ấy; lời dẫn của sách vẫn gọi là Kriky.

- Câu ngắn. Một bước là một hành động.
- Không lập luận, không giải thích hệ thống được xây ra sao.
- **Không chữ kỹ thuật**: không *model*, *job*, *server*, *AGENT*, *backend*, *database*, *API*,
  *upload*. Dùng chữ đời thường: *tải lên*, *đợi một lát*, *tải lại trang*.
- Không hứa thứ app chưa có (xem *Chỗ app chưa khớp* cuối tệp).

## 2. Chữ trên màn hình

- Nút: `\nut{...}`. Ô, nhãn, dòng chữ trên app: `\nhan{...}`. Chữ người dùng gõ: `\go{...}`.
- **Chép đúng từng chữ** như trên app, kể cả hoa thường, ngoặc (app dùng cả “…” lẫn "…"), dấu `…`,
  `›`, `＋`. Nguồn: bảng kiểm kê dưới đây, đọc từ `services/fe/src/` và các nhãn trạng thái của BE.
- Chữ có số đổi theo dữ liệu (*Thêm 2 câu vào đề*, *Cần làm lại 2 câu*) thì viết đúng một ví dụ, khớp
  ảnh chụp.
- App đổi chữ thì sửa bảng kiểm kê trước, rồi sửa sách.

## 3. Khuôn một việc

Mọi mục trong Phần I và II theo đúng khuôn này:

```
\viec{Thêm học sinh vào lớp}          tiêu đề: một động từ
Một câu: việc này để làm gì.
\anh{tệp}{\diem{1}{x}{y} ...}          ảnh chụp, số vẽ trên ảnh
\begin{buoc} \item ... \end{buoc}      số bước khớp số trên ảnh
\xong{...}                             thấy gì là xong
\machnho{...} \luuy{...} \neuloi{...}  chỉ khi cần
```

- Ảnh không sửa tay. Số vẽ bằng TikZ, toạ độ tương đối theo ảnh: `x` từ trái 0 tới phải 1, `y` từ
  trên 0 tới dưới 1.
- **Chấm số đặt cạnh chỗ bấm, không đè lên chữ.** Chỗ bấm nhỏ thì vẽ `\khung` quanh nó và đặt chấm ở
  một góc khung. Bước không có gì để chỉ trên ảnh (bấm ở màn trước) thì không có chấm.

### Các lệnh (định nghĩa ở `style.tex`)

| Lệnh | Dùng cho |
| --- | --- |
| `\trangphan{gv\|hs}{Phần I}{Tên}{Lời dẫn}{\item …}` | Trang mở một phần; tự đổi màu của phần |
| `\phanchung` | Về màu của phần chung (đầu sách, tra nhanh) |
| `\chapter{…}`, `\viec{…}` | Chương; một việc |
| `\nut{…}`, `\nhan{…}`, `\go{…}` | Nút; ô hay nhãn; chữ ngắn người dùng gõ |
| `\begin{loinhan}…\end{loinhan}` | Câu nhắn dài gửi Kriky |
| `\begin{buoc}\item …\end{buoc}` | Các bước có số |
| `\anh{tệp}{\diem{n}{x}{y} \khung{x1}{y1}{x2}{y2}}` | Ảnh chụp có số |
| `\xong{…}`, `\machnho{…}`, `\luuy{…}`, `\neuloi{…}` | Dấu hiệu xong; ba loại ô |
| `\begin{bangtra}{L{4cm}Y}{\dau{A} & \dau{B}}…\end{bangtra}` | Bảng tra, ngắt được qua trang |
| `\chocandien{…}` | Chỗ còn chờ điền (in đỏ); không được còn trong bản gửi đi |
- Mỗi việc nằm gọn trong một trang hoặc nửa trang; dài hơn thì tách việc.
- Bảng *Khi gặp trục trặc* cuối mỗi phần có hai cột: *Thầy cô thấy* (hay *Em thấy*) và *Làm gì*.

## 4. Ảnh chụp

- Chụp từ app chạy thật, cửa sổ rộng 1440 (app chỉ dựng cho bề rộng ấy), độ nét gấp đôi.
- **Chỉ ảnh bản đồ màn hình chụp toàn cửa sổ.** Mọi ảnh khác cắt quanh vùng thao tác, rộng **tối đa
  850px** của màn hình: ảnh 1440px co vào bề rộng trang thì chữ của app còn chừng 4pt, không đọc được
  (review pha 2). Hộp thoại chụp đúng khung của nó, không chừa lề, để không dính mẩu chữ của nền.
- **Ngoại lệ: màn bảng rộng của giáo viên** (danh sách lớp, kết quả đề, bài làm một em, ngân hàng) được
  rộng tới 1130px. Màn giáo viên không co giãn, cắt hẹp thì mất cột, và sách đọc trên màn hình nên
  người đọc phóng to được.
- **Màn học sinh co giãn theo cửa sổ**, nên chụp ở cửa sổ rộng **1100px** (trang làm bài, kết quả, hỏi
  Kriky, lượt làm lại), rồi vẫn cắt từng cột như trên.
- Một màn hai cột (hỏi Kriky, báo cáo của học sinh, làm bài) thì mỗi cột một ảnh, ảnh thứ hai mang chữ
  `b` sau số (`07b`).
- Dữ liệu mẫu **hư cấu**. Không dùng tên, số điện thoại hay email thật.
- Góc trái dưới của app hiện tên bản; tên ấy phải khớp `\tenban` ở `config.tex`.
- Tên tệp: `screenshots/<T|S>/<nn-ten>.png`, theo đúng danh sách ảnh dưới đây.
- App đổi giao diện thì chụp lại đúng các ảnh của màn ấy (tra cột *Màn* trong danh sách).

## 5. Sơ đồ

Nguồn ở `docs/diagrams/user-guide/*.drawio`; xuất PDF vào `figures/` bằng
`draw.io.exe -x -f pdf --crop`; ghi sha256 vào `figures/sources.json`. `.\dev.ps1 check` bắt hình chưa
xuất lại. Sơ đồ dùng màu và phông của sách.

## Dàn bài

| Phần | Chương | Việc |
| --- | --- | --- |
| Đầu sách | Bìa | Tên sách, chú dế, tên bản |
| | Đọc tài liệu này thế nào | Bảng: giáo viên đọc Phần I, học sinh đọc Phần II |
| | Làm quen với Kriky | Kriky là ai; sơ đồ `vong-doi-bai-kiem-tra`; cần gì; hai địa chỉ |
| **I. Giáo viên** | 1. Đăng nhập | Đăng nhập (tài khoản do người quản lý cấp: bản lab tắt đăng ký, `TEACHER_SIGN_UP_ENABLED=false`); menu tài khoản, đăng xuất; quên mật khẩu |
| | 2. Bản đồ màn hình | Ảnh toàn màn có số: thanh trái (bốn mục, đoạn chat theo ngày, tài liệu), khung chat, khung đề |
| | 3. Lớp và học sinh | Tạo lớp (ở màn lớp, hay nhờ Kriky trong chat); danh sách lớp và các cột tiến độ; thêm học sinh gõ tên; thêm bằng tệp; kiểm tra trùng tên; lưu mật khẩu, xuất Excel; đặt lại mật khẩu; xoá lớp trống |
| | 4. Tài liệu | Tải tài liệu lên; bốn trạng thái của tài liệu |
| | 5. Soạn đề cùng Kriky | Bắt đầu đoạn chat (câu gợi ý); gắn tài liệu vào lời nhắn (kéo thả); trả lời Kriky hỏi lại (nút, *Khác…*, thẻ tóm tắt); đọc dàn ý, đồng ý hay sửa **bằng cách nhắn**; xem khung đề; xem lời giải; sửa câu (phương án, đáp án, lỗi của phương án nhiễu, cách giải); xoá câu; thêm câu từ ngân hàng; nhờ soạn thêm; câu *Chưa soạn được* → *Thử lại*; đổi tên đề, xoá đề nháp; đổi tên, xoá đoạn chat; bảng *nhắn sao cho Kriky hiểu* |
| | 6. Duyệt và phát hành | Sơ đồ `trang-thai-de`; duyệt đề; cài đặt phát hành (lớp, hai pha); xác nhận phát hành; phát hành thêm cho lớp khác; *Hoàn tác* (trước giờ mở: bỏ duyệt, hay thu đề về khỏi mọi lớp) |
| | 7. Theo dõi kết quả | Bảng theo dõi (*Cần bạn xem*, *Điểm gộp theo lớp*); xem câu tỉ lệ sai cao; xem báo cáo, hội thoại của em, *Đánh dấu đã xem*; các bài kiểm tra; kết quả một đề ở một lớp (từ màn lớp), xuất bảng điểm; bài làm một em; hỏi Kriky về kết quả trong chat |
| | 8. Ngân hàng câu hỏi | Câu vào ngân hàng khi duyệt đề; sửa câu trong ngân hàng |
| | 9. Khi gặp trục trặc | Bảng |
| **II. Học sinh** | 10. Đăng nhập | Tên đăng nhập, mật khẩu do thầy cô phát; quên mật khẩu thì nhờ thầy cô đặt lại; đăng xuất |
| | 11. Làm bài | *Bài của tôi* và các trạng thái; bắt đầu; làm (chuyển câu bằng ô số); nộp; hết giờ |
| | 12. Kết quả và hỏi Kriky | Sơ đồ `vong-chua-bai`; xem kết quả; hỏi Kriky; xem lời giải đầy đủ; báo giải thích khó hiểu |
| | 13. Làm lại | Bắt đầu lượt làm lại; làm và nộp (hết giờ thì tự nộp); kết quả sau chữa; hết lượt, hết hạn |
| | 14. Khi gặp trục trặc | Bảng |
| Cuối sách | Tra nhanh | Nhãn trạng thái của đề (phía giáo viên), của bài (phía học sinh), của tài liệu; màu trên app |

## Bảng kiểm kê: chữ trên màn hình

Chép từ `services/fe/src/` và `services/be/src/be/teacher_reads.py` ngày 15/11/2026; review pha 1 đối
chiếu lại.

### Giáo viên

| Màn | Tệp | Chữ cần dùng |
| --- | --- | --- |
| Hộp đăng nhập | `teacher/Account.tsx` | *Đăng nhập vào Kriky*; ô *Số điện thoại / email*, *Mật khẩu*; nút *Đăng nhập*; *Tiếp tục với Google* (chưa dùng được); *Chưa có tài khoản? Tạo tài khoản* |
| Hộp tạo tài khoản | `teacher/Account.tsx` | *Tạo tài khoản giáo viên*; ô *Họ và tên*, *Số điện thoại*, *Email*, *Mật khẩu*; nút *Tạo tài khoản*; *Đã có tài khoản? Đăng nhập* |
| Menu tài khoản | `teacher/Account.tsx` | *Đăng xuất* (bốn mục còn lại chưa dùng được) |
| Thanh trái | `teacher/Rail.tsx` | *Đoạn chat mới*; *Bảng theo dõi*, *Danh sách lớp học*, *Các bài kiểm tra*, *Ngân hàng câu hỏi*; nhóm *ĐOẠN CHAT* chia theo *Hôm nay*, *7 ngày qua*, *30 ngày qua*, *Cũ hơn* (menu *Đổi tên*, *Xoá*); nhóm *TÀI LIỆU* (nút tải lên) |
| Trạng thái tài liệu | `teacher/Rail.tsx` | *Đang xử lý…* (kèm tiến độ); xong thì hiện số trang; *Không đọc được chữ*; *Xử lí lỗi. Hãy tải lại*. Nhận `.pdf`, `.txt`, `.md`, tối đa 100 MB. Tải lên **không** tự gắn vào đoạn chat |
| Khung chat | `teacher/Chat.tsx` | *Hôm nay bạn muốn làm gì?* và ba câu gợi ý (bấm là điền sẵn vào ô); ô *Nhắn cho Kriky…*; dải tên tài liệu đã kéo vào, nút *Bỏ*; nút *Gửi* (*Đang gửi…*); *Đang chờ Kriky trả lời…*; *Đang đọc yêu cầu…* / *Vẫn đang xử lý — …*; khối *Đã làm n bước* (hay *Dừng ở bước k*); hộp *Xoá đoạn chat này?* (*Giữ lại*, *Xoá đoạn chat*) |
| Kriky hỏi lại | `teacher/Chat.tsx`, `ClarifySteps.tsx` | nút lựa chọn; *Khác…* → ô *Ghi rõ lựa chọn khác…*, *Gửi* / *Chọn*; *Còn n lựa chọn nữa không nằm trong danh sách.*; nhiều câu thì *Câu k/n · …*, *Câu sau ›*, *‹ Câu trước*, *Xem lại ›*, thẻ *Kiểm tra lại trước khi gửi* (*Sửa*, *Gửi*) |
| Dàn ý | `teacher/Chat.tsx` | lời Kriky viết, **không có nút**: thầy cô nhắn để đồng ý (ví dụ *oke, soạn đi*) hay để sửa; *Kriky chưa nêu được dàn ý…* thì nhắn *thử lại* |
| Thẻ kết quả trong chat | `teacher/ActionCard.tsx` | *Đã tạo đề "…"* + *Chưa duyệt · chưa phát hành*; *Đã duyệt đề "…"* + *Chưa phát hành cho học sinh*; *Đã phát hành* + *Thu hồi được tới trước giờ mở, từ giờ mở thì không*. Nút *Thêm câu hỏi* chỉ điền sẵn *Soạn câu hỏi cho đề này* vào ô (vẫn phải bấm *Gửi*); nút *Thử lại* của thẻ hỏng chỉ xoá trắng ô nhắn |
| Khung đề | `teacher/Panel.tsx` | *Đổi tên*, *Xoá đề*, *Lưu*, *Huỷ*, *Đóng*; *n câu · môn*; thẻ câu *Câu k*, *Kriky soạn* / *Từ ngân hàng*, *Sửa*, *Xoá*, *Lời giải · n cách*; *＋ Thêm câu từ ngân hàng*; ô hỏng *Chưa soạn được*, *Thử lại* (soạn lại thật), *Đang soạn lại*; nút *Duyệt đề*; hộp *Xoá câu k khỏi đề?* (*Giữ lại*, *Xoá câu*); hộp *Xoá đề nháp “…”?* |
| Lời giải | `teacher/Panel.tsx` | *Lời giải — Câu k*; *MỖI PHƯƠNG ÁN NHIỄU GẮN MỘT LỖI*; *✓ đúng*; *Đóng* |
| Sửa câu | `teacher/Editing.tsx` | *Đang sửa*; *Đề bài*, *Phương án*, *Cách giải*; nút tròn chọn đáp án đúng; *Lỗi của X* (bắt buộc cho phương án sai); *+ Thêm phương án*, *+ Thêm cách giải*, *Xoá*; *Huỷ*, *Lưu*; *Công thức có ký tự hỏng…* |
| Thêm từ ngân hàng | `teacher/BankPicker.tsx` | *Thêm câu từ ngân hàng*; ô *Tìm theo nội dung câu hoặc mục kiến thức…*; *đã có trong đề này*; *Đã chọn n câu*; *Đóng*, *Thêm vào đề* (chưa chọn) / *Thêm n câu vào đề* |
| Cài đặt phát hành | `teacher/PublishSettings.tsx` | *Cài đặt phát hành*; *LỚP*; *PHA 1 — LÀM BÀI VÀ NỘP*: *Làm bài*, *Mở lúc*, *Đóng lúc*; *PHA 2 — CHỮA BÀI*: *Phút mỗi câu*, *Hạn chữa xong*; *Bản nháp bạn gõ …*, *Bỏ bản nháp*; *Hoàn tác*; *Phát hành đề* |
| Xác nhận phát hành | `teacher/PublishSettings.tsx` | *Phát hành đề kiểm tra?*; *Đề*, *Lớp*, *Thời gian*, *Hạn chữa*, *Thu hồi*; *Xem lại cài đặt*, *Phát hành cho n học sinh*; sau đó *ĐÃ PHÁT HÀNH*, *Thu hồi được tới …* / *Hết giờ thu hồi lúc …* |
| Danh sách lớp học | `teacher/Classes.tsx` | *Tạo lớp*; cột *LỚP*, *KHỐI / MÔN*, *SĨ SỐ*, *ĐỀ ĐANG MỞ*, *CHƯA NỘP BÀI*, *XONG GIAI ĐOẠN 1*, *XONG GIAI ĐOẠN 2* (rê chuột xem từng đề); hộp *Tạo lớp mới*, ô *Tên lớp* (*Ví dụ: 12C*), *Huỷ*, *Tạo lớp* |
| Chi tiết lớp | `teacher/ClassDetail.tsx` | *Thêm học sinh*, *Xoá lớp*; *Bài kiểm tra đã phát hành cho lớp này* (bấm một hàng là mở kết quả đề ở lớp này); *Học sinh* (*HỌ TÊN*, *MÃ HỌC SINH*, *TÊN ĐĂNG NHẬP*); *Đặt lại mật khẩu*, hộp *Đặt lại mật khẩu cho …?*, *Giữ mật khẩu cũ*, rồi *Đã đặt lại mật khẩu cho …*; hộp *Xoá lớp “…”?* |
| Thêm học sinh | `teacher/Roster.tsx` | *Thêm học sinh vào lớp …*; *Gõ tên* / *Tải tệp .csv / .xlsx*; *Chọn tệp* (tối đa 1 MB); *Đóng*, *Xem trước*; *Kiểm tra lại trước khi tạo tài khoản*: *Mới*, *Trùng tên trong lớp*, ô *XÁC NHẬN*; *Quay lại*, *Tạo n tài khoản*; *Đã tạo n tài khoản*, *Hãy lưu lại mật khẩu — chỉ hiển thị một lần duy nhất.*, *Xuất file Excel (.xlsx)*, *Đã lưu, đóng* |
| Bảng theo dõi | `teacher/Dashboard.tsx` | *Cần bạn xem* (*Giải thích chưa rõ* → *Xem báo cáo*; *Tỉ lệ sai cao* → *Xem câu*); *Điểm gộp theo lớp* (bấm hàng là mở lớp); *Đánh dấu đã xem* / *Đã xem*; *Mở hội thoại hỏi trợ lý ›* → hộp *Hội thoại hỏi trợ lý — …* (chỉ đọc, *Đóng*); *Chỉnh sửa trong Ngân hàng câu hỏi ›* (màn báo cáo) / *Chỉnh sửa trong Ngân hàng câu hỏi* (màn câu); *Không ghi gì thêm.* |
| Các bài kiểm tra | `teacher/Papers.tsx` | cột *TÊN ĐỀ*, *TRẠNG THÁI*, *LỚP*, *MỞ LÚC*; *Xem kết quả* (chỉ mở lớp đầu tiên) / *Mở đoạn chat* |
| Kết quả một đề | `teacher/ClassResults.tsx` | *Xuất bảng điểm (.xlsx)*; *CAO NHẤT*, *TRUNG BÌNH*, *TRUNG VỊ*, *THẤP NHẤT*; *PHÂN BỐ ĐIỂM* |
| Bài làm một em | `teacher/StudentWork.tsx` | *ĐIỂM*, *ĐÚNG NGAY LẦN ĐẦU*, *LƯỢT CHỮA ĐÃ LÀM*, *GIẢI THÍCH CHƯA RÕ*; *EM CHỌN*, *ĐÁP ÁN* |
| Ngân hàng câu hỏi | `teacher/Bank.tsx` | *n câu · từ n lần duyệt đề*; *Sửa câu trong ngân hàng*; câu nhắc *Chỉ sửa bản trong ngân hàng…* |
| Trạng thái đề (BE) | `be/teacher_reads.py` | *Đề trống*, *Đang soạn*, *Chưa duyệt*, *Đã duyệt*; *Chưa tới giờ mở*, *Đang mở*, *Đang chữa bài*, *Đã kết thúc* |

### Học sinh

Học sinh có đúng năm màn sau màn đăng nhập (`App.tsx`), không màn nào khác.

| Màn | Tệp | Chữ cần dùng |
| --- | --- | --- |
| Đăng nhập | `student/SignIn.tsx` | *Đăng nhập để làm bài*; *Tên đăng nhập*, *Mật khẩu*; *Đăng nhập*. Không có "quên mật khẩu" |
| Đầu trang | `components.tsx` | *Lớp …*, *Mã …*; *Đăng xuất*; *Còn lại* (đồng hồ) |
| Bài của tôi | `student/AssignmentList.tsx` | trạng thái *Chưa tới giờ mở*, *Đang mở*, *Đang làm*, *Cần làm lại n câu*, *Đã hoàn thành*, *Hết hạn làm lại*, *Đã đóng*; nút *Bắt đầu*, *Tiếp tục*, *Xem kết quả*, *Hỏi trợ lý và làm lại dạng bài sai*; hộp *Bắt đầu làm bài?* (*Để sau*, *Bắt đầu làm bài*) |
| Làm bài | `student/Sitting.tsx` | *Câu k / n*; ô số các câu bên phải (chuyển câu); *CÒN n CÂU CHƯA TRẢ LỜI*; *Nộp bài*; hộp *Nộp bài?* (*Quay lại làm tiếp*, *Nộp bài*) |
| Kết quả | `student/Result.tsx` | *Hỏi trợ lý và làm lại dạng bài sai* / *Xem lại phần chữa các câu sai*; *Lượt làm lại*; *Lượt chữa vừa rồi đã hết giờ nên được nộp luôn…* |
| Hỏi Kriky | `student/Tutor.tsx` | ô *Hỏi Kriky về bất kỳ câu nào bạn làm sai…*; *Gửi*; *CÁC CÂU EM LÀM SAI*; *Xem lời giải đầy đủ ›* → hộp *Lời giải — Câu k*, *ĐỐI CHIẾU TỪNG PHƯƠNG ÁN*, *Đóng*; *Báo cáo Trợ lý giải thích khó hiểu* (hiện từ khi Kriky trả lời câu hỏi đầu tiên: lời chào đã là một tin) → *Đã báo cho giáo viên*; *Làm bài mới · n câu · n phút*; *Làm tiếp lượt đang mở*; hộp *Bắt đầu lượt làm lại?* (*Để sau*, *Làm bài mới*) |
| Lượt làm lại | `student/Round.tsx` | *Làm lại dạng bài sai · n câu*; *CÂU CÒN PHẢI LÀM LẠI TRONG LƯỢT NÀY* (ô số mang số câu gốc); *Câu k — Lượt làm lại thứ k / tối đa 3*; *Nộp bài*; hộp *Nộp lượt này?*; hết giờ thì tự nộp |

## Danh sách ảnh

`T` = giáo viên, `S` = học sinh. Cột *Chương* theo dàn bài.

| Tệp | Màn, trạng thái | Chương |
| --- | --- | --- |
| `T/01-dang-nhap.png` | hộp đăng nhập | 1 |
| `T/03-menu-tai-khoan.png` | menu tài khoản mở | 1 |
| `T/04-ban-do.png` | toàn màn: thanh trái, chat có một lượt, khung đề mở | 2 |
| `T/05-danh-sach-lop.png` | danh sách lớp học | 3 |
| `T/06-tao-lop.png` | hộp tạo lớp mới | 3 |
| `T/07-chi-tiet-lop.png` | chi tiết lớp có học sinh và một đề đã phát hành | 3 |
| `T/08-them-hs-go-ten.png` | thêm học sinh, thẻ *Gõ tên* | 3 |
| `T/09-them-hs-tai-tep.png` | thẻ *Tải tệp* | 3 |
| `T/10-them-hs-kiem-tra.png` | *Kiểm tra lại…* có một dòng trùng tên | 3 |
| `T/11-them-hs-mat-khau.png` | *Đã tạo n tài khoản*, bảng mật khẩu | 3 |
| `T/12-dat-lai-mat-khau.png` | hộp đặt lại mật khẩu | 3 |
| `T/13-tai-lieu.png` | nhóm *TÀI LIỆU*: một tệp đang xử lý, một tệp xong | 4 |
| `T/14-chat-moi.png` | *Hôm nay bạn muốn làm gì?* và câu gợi ý | 5 |
| `T/15-gan-tai-lieu.png` | ô nhắn có dải tên tài liệu đã kéo vào | 5 |
| `T/16-hoi-lai.png` | thẻ Kriky hỏi lại | 5 |
| `T/17-dan-y.png` | dàn ý của Kriky | 5 |
| `T/18-da-soan.png` | khối bước + lời kết + thẻ *Đã tạo đề* | 5 |
| `T/19-khung-de.png` | khung đề nhiều câu, nút *Duyệt đề* | 5 |
| `T/20-loi-giai.png` | hộp lời giải | 5 |
| `T/21-sua-cau.png` | một câu đang sửa | 5 |
| `T/22-xoa-cau.png` | hộp *Xoá câu k khỏi đề?* | 5 |
| `T/23-ngan-hang-chon.png` | hộp thêm từ ngân hàng, đã chọn một câu | 5 |
| `T/24-tuy-chon-doan-chat.png` | menu *Đổi tên* / *Xoá* của một đoạn chat | 5 |
| `T/25-cai-dat-phat-hanh.png` | đề đã duyệt, cài đặt phát hành đã điền | 6 |
| `T/26-xac-nhan-phat-hanh.png` | hộp *Phát hành đề kiểm tra?* | 6 |
| `T/27-da-phat-hanh.png` | khối *ĐÃ PHÁT HÀNH*, nút *Hoàn tác* | 6 |
| `T/28-bang-theo-doi.png` | bảng theo dõi có việc cần xem | 7 |
| `T/29-cau-sai-nhieu.png` | màn một câu tỉ lệ sai cao (cần > 20 bài nộp) | 7 |
| `T/30-bao-cao.png` | báo cáo *Giải thích chưa rõ* | 7 |
| `T/31-hoi-thoai-cua-em.png` | hộp *Hội thoại hỏi trợ lý — …* | 7 |
| `T/32-cac-bai-kiem-tra.png` | các bài kiểm tra | 7 |
| `T/33-ket-qua-de.png` | kết quả một đề | 7 |
| `T/34-bai-lam-mot-em.png` | bài làm một em | 7 |
| `T/35-ngan-hang.png` | ngân hàng câu hỏi | 8 |
| `T/36-sua-ngan-hang.png` | sửa câu trong ngân hàng | 8 |
| `S/01-dang-nhap.png` | đăng nhập học sinh | 10 |
| `S/02-bai-cua-toi.png` | *Bài của tôi*, nhiều trạng thái | 11 |
| `S/03-bat-dau.png` | hộp *Bắt đầu làm bài?* | 11 |
| `S/04-lam-bai.png` | đang làm, đồng hồ chạy | 11 |
| `S/05-nop-bai.png` | hộp *Nộp bài?* | 11 |
| `S/06-ket-qua.png` | kết quả lần đầu, có câu sai | 12 |
| `S/07-hoi-kriky.png` | hỏi Kriky, đã có câu trả lời | 12 |
| `S/08-loi-giai.png` | lời giải đầy đủ | 12 |
| `S/09-bao-cao.png` | *Đã báo cho giáo viên* (cần Kriky đã trả lời hai lần) | 12 |
| `S/10-bat-dau-lam-lai.png` | hộp *Bắt đầu lượt làm lại?* | 13 |
| `S/11-lam-lai.png` | đang làm lượt làm lại | 13 |
| `S/12-ket-qua-sau-chua.png` | kết quả sau chữa | 13 |

Ảnh phụ đã chụp thêm: `T/19b-duyet-de` (chân khung đề, nút *Duyệt đề*), `T/21b-sua-phuong-an` (ô sửa mở *Phương án*, nút tròn đáp án, ô *Lỗi của …*), `T/16b-hoi-lai-tom-tat` (thẻ *Kiểm tra lại trước khi gửi*), `T/24b-xoa-doan-chat`
(hộp *Xoá đoạn chat này?*), `T/30b-bao-cao-hoc-sinh` (cột *BÁO CÁO CỦA HỌC SINH*), `S/04b-dong-ho`
(đồng hồ, ô số câu, *Nộp bài*), `S/07b-cau-sai` (cột *CÁC CÂU EM LÀM SAI*), `S/11b-nop-luot` (hộp *Nộp
lượt này?*). Ô *Chưa soạn được*, hộp xoá đề nháp và hộp *Đã đặt lại mật khẩu…* không dựng được tự nhiên
lúc chụp, nên ba việc ấy chỉ viết bằng lời.

Ảnh `T/21-sua-cau` cố ý chụp một câu có công thức hỏng, để thấy dòng *Công thức có ký tự hỏng…*.

## Chỗ app chưa khớp

Ghi lại để sách không hứa sai. Sửa app thì sửa luôn mục này.

- **Thu hồi đề:** không có nút *Thu hồi*. Thu hồi làm bằng nút *Hoàn tác* ở khung đề, trước giờ mở:
  đề bị thu về khỏi **mọi lớp** và trở về chưa duyệt; không thu riêng một lớp được. Qua giờ mở thì nút
  khoá.
- **Menu tài khoản:** *Cài đặt*, *Mức sử dụng*, *Ngôn ngữ*, *Trợ giúp* chưa dùng được.
- **Đăng nhập bằng Google:** nút có hiện nhưng chưa dùng được.
- **Quên mật khẩu:** học sinh nhờ thầy cô đặt lại; giáo viên chưa có cách tự lấy lại mật khẩu.
- **Đăng ký giáo viên:** bản lab tắt (`deploy/lab/lab.env`), nên sách không dạy *Tạo tài khoản*; hộp
  tạo tài khoản báo *"Máy này không mở đăng ký…"*.
- **Cài đặt phát hành tự thu lại** khi mọi lớp đã nhận đề: phải bấm vào dòng ấy mới thấy *Hoàn tác*.
- **Sửa câu thiếu lỗi của phương án nhiễu:** app hiện câu có chữ kỹ thuật *"ADR-18 bắt mọi phương án
  nhiễu phải có."* Sách giải thích bằng lời thường: mỗi phương án sai phải ghi lỗi của nó.
- **Xem kết quả** ở *Các bài kiểm tra* chỉ mở lớp đầu tiên; kết quả ở lớp khác mở từ màn của lớp ấy.
- **Bài lần đầu không tự nộp khi hết giờ** (`Sitting.tsx`: `TimeCard` không có `onExpire`): em phải bấm
  *Nộp bài*; chưa nộp thì bài nằm ở *Đang làm*. Lượt làm lại thì tự nộp.
- **Nhãn *Hết hạn làm lại* không bao giờ hiện:** *Cần làm lại n câu* đè lên (`AssignmentList.tsx`).
- **"Bài đóng quá 30 ngày không hiện ở đây nữa"** chỉ là chữ trên màn; BE chưa lọc.
- **Kriky gọi học sinh là "bạn"**, sách gọi "em".
- **Hai chữ cho một việc:** hộp *Bắt đầu lượt làm lại?* ghi *"vòng 1 — mỗi câu còn 3 vòng"*, màn làm lại
  ghi *"Lượt làm lại thứ 1 / tối đa 3"*. Sách dùng chữ *lượt*.
