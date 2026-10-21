# ADR-36 — Đăng nhập bằng phiên cookie; giáo viên phát tài khoản học sinh

- **Trạng thái:** đã chốt, đang thi hành
- **Ngày:** 2026-10-19

## Bối cảnh

Từ đợt đầu ([ADR-10](adr-10-pham-vi-dot-dau.md)) danh tính chỉ là một header `X-Actor` mà FE gán
cứng. Phân quyền đã thật ([ADR-22](adr-22-de-co-tac-gia.md)), nhưng ai cũng tự khai được là ai.
[ADR-13](adr-13-lop-va-tai-khoan-hoc-sinh.md) đã nói tài khoản học sinh do giáo viên sinh ra và mật
khẩu chỉ hiện một lần, nhưng chưa có chỗ nào thi hành luật ấy. Việc 22 của đợt tất định
(`2026-10-18-sign-in-and-accounts-plan.md`) dựng phần còn thiếu. Người dùng chốt
các điểm dưới đây ở buổi review Figma 18/10/2026.

## Quyết định

**Giáo viên tự đăng ký.** Cần họ tên, số điện thoại **và** email, mật khẩu ít nhất 8 ký tự. Đăng nhập
bằng số điện thoại **hoặc** email. Nút Google chỉ là giao diện: bấm thì màn nói thẳng là chưa có.

**Học sinh không đăng ký.** Giáo viên thêm học sinh vào lớp, bằng cách gõ họ tên hoặc tải tệp
`.csv`/`.xlsx` một cột họ tên. Hệ thống cấp ba thứ:
- **mã học sinh**: số thứ tự tăng dần 1 → N trên toàn hệ thống (mã demo dạng `HS2026-1204` nằm ngoài
  dãy này);
- **tên đăng nhập**: tên, cộng chữ đầu của họ và tên đệm, bỏ dấu (*Lê Kim Tính* → `tinhlk`).
  Tên này duy nhất trên toàn hệ thống, vì học sinh đăng nhập mà không chọn lớp. Trùng thì thêm số từ
  2 (`anhpd2`);
- **mật khẩu** ngẫu nhiên dạng `k7m-pq4-xd`, không có ký tự dễ nhầm (`0/o`, `1/l/i`).

Trước khi tạo, giáo viên xem trước bảng. Một em **cùng họ tên với một em đã có trong lớp**, hay với
một dòng phía trên, chỉ được tạo khi giáo viên đánh dấu *Xác nhận*. Lúc tạo, BE tính lại bảng xem
trước theo cùng luật rồi cấp đúng tên của bảng ấy. Chỉ khi có người vừa lấy cùng tên giữa hai bước thì
số đuôi mới nhảy.

**Mật khẩu rõ chỉ hiện một lần**, ở hai chỗ: hộp *Đã tạo N tài khoản* và hộp *Đặt lại mật khẩu*.
BE chỉ giữ `scrypt` của nó, không giữ bản rõ nào, kể cả trong một lúc. Tệp `.xlsx` mật khẩu dựng từ
chính các dòng đang hiện trên màn mà FE gửi lên. Đặt lại mật khẩu thì đóng mọi phiên cũ của em ấy.

**Không bắt đổi mật khẩu ở lần đăng nhập đầu.** Xem hậu ký ADR-13.

**Mỗi vai một phiên.** Cookie `aiafa_teacher` và `aiafa_student` đều `HttpOnly`, `SameSite=Lax`, hạn
30 ngày. Một trình duyệt mở cùng lúc được phiên giáo viên và phiên học sinh, để demo. Cookie của vai
này không mở được route của vai kia.

**Mỗi vai một câu cho mọi lần đăng nhập sai.** Câu ấy không cho biết số điện thoại, email hay tên đăng
nhập nào đã có, và lần sai tốn cùng một khoảng thời gian dù tài khoản có hay không.

## Vì sao

- **Học sinh không tự đăng ký** vì lớp thuộc giáo viên (ADR-13). Một tài khoản tự tạo là một tài
  khoản không thuộc lớp nào.
- **Tên đăng nhập suy từ họ tên** vì giáo viên phát nó trên giấy, và học sinh lớp 10 phải gõ lại được.
- **Dòng trùng phải được xác nhận** vì hai em cùng họ tên trong một lớp là chuyện có thật, nhưng một
  tệp dán hai lần cũng vậy. Hệ thống không phân biệt được hai trường hợp ấy, chỉ giáo viên phân biệt
  được.
- **Mật khẩu chỉ hiện một lần** vì một mật khẩu đọc lại được là một mật khẩu đã bị cất.
- **Hai cookie** vì demo phải cho thấy giáo viên phát hành rồi học sinh làm bài, trên cùng một máy.

## Hệ quả

- `X-Actor` còn được nhận, nhưng chỉ khi `DEV_IDENTITY_ENABLED` bật **và** request không mang cookie
  của vai ấy. Mặc định của cờ là tắt. Test và lệnh `curl` trên máy dev dùng đường này.
- Học sinh có từ trước việc 22 chưa có tên đăng nhập, trừ ba em demo mà seed đã cấp. Lần *Đặt lại mật
  khẩu* đầu tiên cấp luôn.
- **Đăng ký thì vẫn nói được SĐT hay email nào đã có:** 409 *"Số điện thoại này đã có tài khoản."*. Một
  giáo viên cần biết vì sao đăng ký không được, nên câu ấy được giữ. Muốn che thì phải có xác nhận qua
  email, mà việc ấy chưa có.
- Quên mật khẩu, đổi mật khẩu và đăng nhập Google thật chưa có. Giới hạn số lần thử đăng nhập cũng
  chưa có; việc này ghi ở `docs/plans/backlog.md`.
- Cookie chưa mang cờ `Secure`, vì máy dev chạy http. Khi triển khai sau HTTPS thì phải bật.

## Nơi luật này đang được thi hành

- `packages/schema/src/schema/models.py`:
  - `Teacher.phone/email/password_hash`;
  - `Student.username/password_hash`;
  - `AccountSession`.
- `services/be/src/be/accounts.py`: băm, phiên, tên đăng nhập, mã học sinh, mật khẩu phát.
- `services/be/src/be/account_routes.py`: đăng ký, đăng nhập, đăng xuất.
- `services/be/src/be/identity.py`: cookie thắng `X-Actor`.
- `services/be/src/be/config.py`: `dev_identity_enabled` mặc định tắt; `services/be/tests/conftest.py`
  bật nó cho test.
- `services/be/src/be/seed.py`: đăng nhập mẫu của dữ liệu demo.
- `services/be/src/be/roster.py`: xem trước, tạo tài khoản, tệp mật khẩu, đặt lại mật khẩu.
- Test: `services/be/tests/test_accounts.py`, `test_roster.py`.
- FE:
  - `services/fe/src/screens/teacher/Account.tsx`, `Roster.tsx`, `ClassDetail.tsx`;
  - `services/fe/src/screens/student/SignIn.tsx`;
  - `services/fe/src/App.tsx`, cổng phiên của cả hai vai.
- Figma:
  - trang giáo viên: 26 `659:5160`, 26b `659:5311`, 26c `709:5249`, 27 `659:5460`, 28 `660:5367`,
    28b `660:5512`, 28c `660:5677`, 28d `711:5287`, 10 `183:874`, 10b `707:5377`;
  - trang học sinh: 12 `659:5676`, 12b `713:830`, 13c `714:836`.

## Hậu ký 20/10/2026

**Đăng ký giáo viên tắt được theo máy; cookie có cờ `Secure` sau HTTPS** (plan `lab-deploy-aws`).
Máy lab cho năm người trong team mở ra Internet, nên `TEACHER_SIGN_UP_ENABLED=false` ở đó:
`POST /api/teacher/sign-up` trả 403 *"Máy này không mở đăng ký…"*, và tài khoản chỉ đến từ seed
lab (`python -m be.lab_seed`). FE không đổi: lời từ chối của BE hiện ngay trên hộp đăng ký (người
dùng chọn chặn ở BE, D1 của plan). `SESSION_COOKIE_SECURE=true` ở lab đóng việc còn treo ở trên về
cờ `Secure`; máy dev vẫn để tắt vì chạy HTTP. Mặc định của cả hai biến giữ nguyên hành vi máy dev.
Thi hành ở `be/config.py`, `be/account_routes.py`, `services/be/tests/test_accounts.py`, và
`deploy/lab/lab.env` (`tools/tests/test_lab_deploy.py`).
