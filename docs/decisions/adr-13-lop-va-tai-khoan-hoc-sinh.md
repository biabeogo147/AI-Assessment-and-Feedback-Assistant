# ADR-13 — Lớp và tài khoản học sinh do giáo viên tạo

- **Trạng thái:** đã chốt (phần *mật khẩu chỉ hiện một lần*: đã chốt, chưa thi hành)
- **Ngày:** 2026-09-07

## Bối cảnh

[ADR-02](adr-02-phat-hanh-va-cua-so-thu-hoi.md) chốt rằng phát hành đề phải chọn **lớp đã được tạo từ
trước**. Nhưng chưa ADR nào nói lớp từ đâu ra, học sinh vào lớp bằng cách nào, và ai cấp tài khoản cho
học sinh để các em đăng nhập mà làm bài.

Ba màn hình quản lý vật thể không dựng được khi chưa trả lời ba câu đó: màn hình lớp học có nút *Tạo
lớp* hay không, phụ thuộc hoàn toàn vào câu trả lời.

## Quyết định

- **Lớp thuộc về giáo viên.** Giáo viên tạo lớp — trực tiếp trên màn hình lớp học, hoặc bằng cách nhờ
  Kriky trong chat. Hai bề mặt, một quyền sở hữu; không bề mặt nào là của nhà trường.
- Tài khoản học sinh được tạo **hàng loạt từ file CSV danh sách lớp**. Mỗi dòng sinh một tên đăng nhập
  và một mật khẩu ban đầu.
- **Mã học sinh là khoá định danh**, không phải họ tên. Vì thế **mọi lần nhập sau lần đầu là *đối chiếu
  rồi mới ghi*, không phải *thêm vào***.
- **Mật khẩu chỉ hiện đúng một lần, ngay tại thao tác sinh ra nó**, kèm bản tải về để giáo viên in và
  phát. Luật này áp cho **cả hai** thao tác sinh mật khẩu: nhập CSV, và đặt lại mật khẩu cho một em.
  Ngoài hai khoảnh khắc đó, không bề mặt nào trong sản phẩm được hiển thị mật khẩu.
- **Tên đăng nhập thì hiện bình thường.** Nó là thứ giáo viên phải đọc cho học sinh, và biết tên đăng
  nhập của người khác không mở được gì.

## Vì sao

**Giáo viên tạo lớp**, vì MVP không thể chờ một hệ thống bên ngoài chưa tồn tại. Trói sản phẩm vào một
API của nhà trường là trói tiến độ vào một bên không kiểm soát được.

**CSV**, vì đó là định dạng giáo viên đã có sẵn từ sổ điểm. Bắt nhập tay bốn mươi em một lớp là cách
chắc chắn nhất để không ai dùng sản phẩm.

**Hai bề mặt tạo lớp**, vì chat là dòng lệnh (ADR-10) và màn hình vật thể là nơi vật thể sống. Cấm một
trong hai sẽ buộc giáo viên rời khỏi chỗ họ đang đứng để làm một việc nhỏ. Điều phải giữ không phải là
*một đường duy nhất*, mà là *một chủ sở hữu duy nhất*.

**Khoá theo mã học sinh**, vì hai em trùng tên trong một khối là chuyện thường. Khoá theo họ tên thì
lần nhập thứ hai sẽ đẻ ra tài khoản thứ hai cho cùng một người, và không ai phát hiện ra cho tới khi
điểm của một em nằm ở hai chỗ.

**Mật khẩu chỉ hiện một lần**, vì một bảng mật khẩu nằm vĩnh viễn trên màn hình lớp là thứ bất kỳ ai đi
ngang qua máy giáo viên cũng đọc được — và nó không phục vụ việc gì mà nút đặt lại không phục vụ được.

## Hệ quả

- Sản phẩm trở thành **nơi phát hành danh tính**, không chỉ nơi ra đề. Từ nay mọi màn hình chạm tới học
  sinh phải trả lời thêm câu *"ai đọc được cái này"* — câu hỏi trước đây không tồn tại, vì sản phẩm
  chưa giữ danh tính của ai.
- **Không có nguồn sự thật bên ngoài để đối chiếu.** Danh sách lớp nhập sai thì không hệ thống nào sửa
  hộ, và cũng không có gì để phát hiện ra là nó sai.
- Luồng nhập **lần hai đắt hơn hẳn lần đầu**: nó phải đọc dữ liệu đang có, so khớp, rồi báo cái gì mới
  và cái gì trùng — trước khi ghi bất cứ thứ gì.
- **Giáo viên làm mất mật khẩu thì không tra cứu lại được**, phải đặt lại và phát lại cho học sinh. Đó
  là cái giá đã chọn để đổi lấy việc không có bảng mật khẩu nằm phơi trên màn hình.
- Lớp không còn là dữ liệu tham chiếu đơn thuần: nó là vật thể có vòng đời, và **xoá một lớp nghĩa là
  đụng tới tài khoản của người thật**. Không thao tác nào trên lớp còn là thao tác nhẹ.

## Nơi luật này đang được thi hành

Figma `mOe2ZmrqOq1Uix45v6PNGD`:

- Artboard `9 · Danh sách lớp học` (`180:753`) — nút **Tạo lớp** là hành động chính của giáo viên.
- Artboard `10 · Chi tiết lớp` (`183:874`) — nút **Nhập thêm từ CSV**, và bảng học sinh có cột *tên
  đăng nhập* nhưng **không có cột mật khẩu**.
- `Student row` (`179:15`) — mô tả component ghi nguyên văn luật không-có-cột-mật-khẩu và lý do chọn
  mã học sinh làm khoá.
- `Empty state` variant `chua-co-lop` (`179:16`) và `lop-chua-co-hoc-sinh` (`179:19`) — cả hai chỉ
  đường tới việc nhập CSV.
- `Action result card` variant `tạo-lớp` (`10:34`) — *"Đã tạo lớp 12A"* / *"40 học sinh"* / *"Chưa có
  bài nào được giao"*: bằng chứng cho **bề mặt chat**.
- Artboard `1 · Bắt đầu`, câu hero (`12:33`) — *"Kriky sẽ tạo lớp, soạn đề, thêm câu hỏi — nhưng chỉ
  bạn mới phát hành được đề cho học sinh"*. Câu này chứng minh **lớp không thuộc nhà trường**; nó
  không mâu thuẫn với *"giáo viên tạo lớp"*, vì Kriky làm thay giáo viên theo lệnh trong chat.
- Hai dòng lịch sử *"Lớp 11B — nhập danh sách"* và *"Lớp 12B — nhập danh sách"* trên rail.
- `Publish settings` variant `chưa có lớp` (`77:341`) — *"Nhắn cho trợ lý tạo lớp trước, rồi quay lại
  đây"*: bề mặt chat, một lần nữa.
- Figma trang `Screen — Student`, `Student top bar` (`281:16`) — **cả mười hai artboard** mang họ
  tên · lớp · mã học sinh · **Đăng xuất**. Đó là hệ quả trực tiếp của luật này: phòng máy dùng chung
  thì mỗi màn phải trả lời được câu *ai đang đăng nhập*, và phải thoát được ngay tại chỗ.
- **Lỗ mật khẩu vẫn nguyên sau khi dựng xong bề mặt học sinh.** Không màn nào trong mười hai màn bắt
  đổi mật khẩu lần đầu, và không có màn đăng nhập nào. Mười hai màn mới **không** làm lỗ này nhỏ đi.
- **Link *Đặt lại mật khẩu*** trong `Student row` (`179:8`) — điểm vào của thao tác sinh mật khẩu thứ
  hai. **Bề mặt kết quả của nó chưa được dựng**, nên luật *chỉ hiện một lần* chưa có chỗ nào thi hành.

`docs/overview/project-overview.md` — mục glossary `Class`.

**Chưa có ở backend.** Không có model lớp, học sinh, tài khoản hay phiên đăng nhập nào trong code; toàn
bộ luật này hiện chỉ sống trong file thiết kế.

`packages/contracts/src/contracts/messages.py` đã có `student_id: str`, và `services/fe/src/api.ts` gán
cứng `"stu-demo"`. Khi dựng thật, `student_id` **là** mã học sinh nói ở trên, không phải một định danh
thứ hai — nếu để hai thứ song song thì khoá định danh mất tác dụng ngay.

**Chưa dựng:** cả hai bề mặt được phép hiện mật khẩu — luồng nhập CSV (đính file → xem trước danh sách
sẽ tạo → xác nhận → thẻ kết quả) và hộp kết quả của *Đặt lại mật khẩu*. Chừng nào chưa dựng, luật
*"chỉ hiện một lần"* mới chỉ đúng theo nghĩa **không nơi nào hiện nó cả** — đó là lý do trạng thái của
ADR ghi phần này là *chưa thi hành*.
