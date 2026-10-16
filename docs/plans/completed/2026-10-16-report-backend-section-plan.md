# Chương 7 của báo cáo: viết lại mục Backend theo bố cục mới

## Goal

Viết lại `\section{Backend}` của `docs/report/chapters/07-chi-tiet-cac-service.tex` theo bố cục
người dùng đề xuất: vai trò → cơ chế giao job và lấy kết quả → nghiệp vụ → ràng buộc → xử lý lỗi →
giới hạn hiện tại. Nội dung đúng với code, văn tự nhiên, theo `docs/report/rules.md`.

## Scope

- Trong phạm vi: mục backend của chương 7 (từ sau `\label{sec:be}` tới trước
  `\section{\texttt{agent}}`); bỏ in đậm lại ở hai dòng của mục document (`byte`, `object store`,
  `content store`) mà lần nhắc đầu đã dời lên mục backend; `rules.md` (đo lại số, thêm "đợi");
  `docs/plans/backlog.md`.
- Ngoài phạm vi: dòng 1–10 của chương 7 (người dùng viết); bố cục và chữ của mục agent, document;
  chương 03, 06; mọi tệp code.
- Không commit trong plan này; người dùng duyệt sau cả plan.

## Files

- `docs/report/chapters/07-chi-tiet-cac-service.tex`
- `docs/report/rules.md`, `docs/plans/backlog.md`, plan này
- `docs/report/report.pdf`

## Ordered Tasks

- [x] Pha 0: mốc các tệp sẽ sửa; tạo plan này.
- [x] Pha 1: viết sáu subsection và ba bảng, kiểm từng khẳng định với code lúc viết; ghép vào
      chương; bỏ đậm ở mục document.
- [x] Pha 2: build, `.\dev.ps1 check`, các script kiểm chữ, chú thích, văn phong, trang.
- [x] Pha 3: một subagent review — đúng với code, tự nhiên, theo `rules.md`; có PNG các trang.
- [x] Pha 4: sửa theo review; backlog; `rules.md`; Status; hỏi người dùng có commit không.

## Decision Records

### Decision: Cấp tiêu đề

options considered: năm `\subsection` và `\paragraph` bên trong; `\subsubsection` không số;
`secnumdepth` 3 cho có số 7.1.2.1; sáu `\subsection` và `\paragraph` bên trong.
selected option: sáu `\subsection` (*Các giới hạn hiện tại* tách khỏi *Xử lý lỗi*), bên trong là
`\paragraph{...}`.
reason: báo cáo chưa dùng `\subsubsection` lần nào và `rules.md` §9 cấm đặt kiểu trình bày mới;
`secnumdepth` 3 làm mục lục lệch vì chỉ một mục có cấp thứ tư. `\paragraph` là kiểu mục agent và
document đang dùng. Giới hạn hiện tại đứng thành một mục để không bị giấu cuối một bảng.

### Decision: Bảng ràng buộc bốn nhóm

options considered: năm nhóm theo đề xuất (Phân quyền, Tính hợp lệ, Tính nhất quán, Điều khiển
đồng thời, An toàn dữ liệu); bốn nhóm, bỏ An toàn dữ liệu.
selected option: bốn nhóm; luật "job soạn câu không nhận chữ thô của tài liệu" vào Tính hợp lệ.
reason: lý do của luật ấy là job phải nhận đúng thứ giáo viên đã xem, và rác của bước đọc chữ từ ảnh
thì không ai kiểm được (ADR-29; `scripts/check_contract.py`) — đó là tính hợp lệ, không phải an
toàn. Một nhóm chỉ có một hàng mà tên lại nói sai lý do thì làm bảng khó đọc hơn.

### Decision: Chữ mới chỉ ở mục backend

options considered: đổi "Luật và chỗ canh luật", "Khi hỏng" và cột "Luật | Nơi thi hành | Loại
lưới" ở cả ba mục; chỉ mục backend dùng chữ mới; mục backend giữ chữ cũ.
selected option: chỉ mục backend dùng chữ mới (*Các ràng buộc và cơ chế kiểm soát*, *Xử lý lỗi*,
cột *Ràng buộc | Cơ chế thực thi | Kiểm chứng*); chỗ lệch ghi backlog.
reason: người dùng chọn (16/10/2026). Chương 7 tạm mang hai bộ chữ cho một khái niệm, trái
`rules.md` §2; chỗ lệch được ghi ở backlog và ở mục *Những chỗ đã biết là còn sai* của `rules.md`.

## Validation Checks

- `.\dev.ps1 report` sạch; chuỗi dò của các tiêu đề mới có trong PDF; không `??`.
- `.\dev.ps1 check` xanh.
- Mục backend không còn `chờ`, `đợi`, `tác vụ`, `nguyên tử`, `streaming`, `timeout`, `retry`,
  `endpoint`, `\ref{sec:tu-dien}`, `tab:be-khoi`, `tab:be-luat`.
- Mọi chữ tiếng Anh lần đầu trong văn xuôi chương 7 có chú thích; không lần nào in đậm lại.
- Dòng 1–10 của chương 7 giống mốc từng byte.

## Status

Bốn pha xong ngày 16/10/2026. Người dùng duyệt (*"ổn rồi đấy"*) và cho commit cùng ngày.

- Build sạch (50 trang, trước lượt này 48), `.\dev.ps1 check` 23/23. Dòng 1–10 của chương 7 giống
  mốc từng byte; ngoài mục backend chỉ đổi hai chỗ bỏ in đậm ở mục document và gói lại dòng ấy.
- Review tìm mười hai chỗ nói sai hay nói quá so với code — gộp hai phép kiểm plan có hậu quả khác
  nhau, *"không tool nào đổi trạng thái của đề"* (thu hoạch có đổi), *"mục lục không lên màn hình"*,
  lý do của trần tám bước, câu biến thể mất kết quả được giao lại ngay chứ không *"lần sau"* — và
  sáu chỗ một chữ hai nghĩa (*luồng*, *đoạn chữ*, *kênh*, *lượt*, *việc*). Đã sửa cả.
- Bảng ràng buộc và bảng lỗi trôi xuống cuối chương hai lần vì cao quá 70% trang; nay là
  `longtable` theo khuôn chương 06. `rules.md` §8 ghi bài học ấy; §2 thêm hàng *luồng*, *đoạn chữ*
  và chữ *đợi*; các số đo §3, §4, §7, §9, §10 đo lại; mục *Những chỗ đã biết là còn sai* thêm chỗ
  chương 7 mang hai bộ chữ.
- Còn lại ở `backlog.md`, mục *Lộ ra khi viết lại mục backend của chương 7*: hai bộ chữ, ba nghĩa
  của *khoá*, đoạn mở chương 7, giới hạn *đăng nhập* chưa quyết có thêm, hai chỗ code nói sai.
