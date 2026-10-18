# Đợt 4, cụm 6 — đăng nhập và tài khoản (việc 22)

## Goal

Làm việc 22 của `2026-10-18-deterministic-batch-master-plan.md`: đăng nhập thật thay cho header
`X-Actor` cố định (`ACTOR` trong `services/fe/src/api.ts`).

- **Giáo viên**: tự đăng ký bằng họ tên, số điện thoại, email và mật khẩu; đăng nhập bằng số điện
  thoại **hoặc** email.
- **Học sinh**: đăng nhập bằng tên đăng nhập và mật khẩu do giáo viên phát.
- Giáo viên thêm học sinh vào lớp: gõ họ tên, hoặc tải `.csv`/`.xlsx` một cột họ tên. Mã học sinh và
  tên đăng nhập do hệ thống cấp. Dòng trùng tên trong lớp phải xác nhận. Mật khẩu chỉ hiện một lần.

Figma đã duyệt 18/10/2026:
- giáo viên: `26 · Chưa đăng nhập — hộp đăng nhập` (`659:5160`), `26b · Tạo tài khoản giáo viên`
  (`659:5311`), `27 · Đã đăng nhập — menu tài khoản` (`659:5460`), `28 · Thêm học sinh — nhập danh sách`
  (`660:5367`), `28b … xem trước, có dòng trùng` (`660:5512`), `28c … mật khẩu chỉ hiện một lần`
  (`660:5677`), `10 · Chi tiết lớp` (`183:874`, cột tên đăng nhập và nút *Đặt lại mật khẩu*);
- học sinh: `12 · Đăng nhập của học sinh` (`659:5676`, trang Screen — Student).

## Người dùng đã chốt (18/10/2026)

1. **Mỗi vai một cookie**: demo giáo viên và học sinh song song trong một trình duyệt được.
2. **Đăng ký giáo viên bắt buộc cả SĐT lẫn email.**
3. Băm mật khẩu bằng `hashlib.scrypt`.
4. Không bắt đổi mật khẩu ở lần đăng nhập đầu (hậu ký ADR-13).
5. Giáo viên **không** nhập mã học sinh; tệp chỉ có cột họ tên. Mã học sinh là số thứ tự tăng dần 1 → N
   trên toàn hệ thống.
6. Tên đăng nhập: tên, cộng chữ đầu của họ và tên đệm, bỏ dấu (*Lê Kim Tính → tinhlk*). Trùng thì thêm
   số.
7. Xem trước chỉ có họ tên, tên đăng nhập, ghi chú (*Mới* / *Trùng tên trong lớp*) và cột *Xác nhận*.
   Ô đánh dấu chỉ bật ở dòng trùng; rê chuột hiện *"Xác nhận thêm học sinh"*.
8. Bước mật khẩu ghi *"Hãy lưu lại mật khẩu — chỉ hiển thị một lần duy nhất."*, có nút *Xuất file Excel
   (.xlsx)*.
9. Menu tài khoản: Cài đặt, Mức sử dụng, Ngôn ngữ, Trợ giúp, Đăng xuất. Chỉ Đăng xuất bấm được. Ô tài
   khoản chỉ có avatar và họ tên.
10. Google chỉ là giao diện.

## Scope

- **Trong phạm vi:**
  - schema:
    - `teachers.phone`, `teachers.email`, `teachers.password_hash`;
    - `students.username`, `students.password_hash`;
    - bảng `sessions`;
    - ALTER idempotent trên DB dev;
  - BE:
    - `be/accounts.py`: băm mật khẩu, phiên, tên đăng nhập, mã học sinh;
    - route đăng ký, đăng nhập, đăng xuất, `me` cho hai vai;
    - `identity.py`: cookie thắng; `X-Actor` chỉ được nhận khi `dev_identity_enabled` bật **và** không
      có cookie, để 26 file test không phải đổi;
  - BE, danh sách lớp:
    - xem trước (gõ tay, hoặc tệp `.csv`/`.xlsx`);
    - tạo tài khoản;
    - tệp mật khẩu `.xlsx`, dựng từ chính dữ liệu FE gửi lên, không lưu gì;
    - đặt lại mật khẩu một em;
  - FE giáo viên:
    - ô tài khoản ở góc dưới trái rail, menu tài khoản;
    - hộp đăng nhập và hộp đăng ký;
    - đăng xuất;
    - ba bước thêm học sinh ở Chi tiết lớp;
    - cột tên đăng nhập, *Đặt lại mật khẩu*;
  - FE học sinh: màn đăng nhập (12), nút *Đăng xuất* trên thanh trên chạy thật;
  - bỏ `ACTOR` khỏi `api.ts`; thay dòng `ACTOR` của `services/fe/AGENTS.md` bằng một dòng khác;
  - `.env.example`: `DEV_IDENTITY_ENABLED=false`. `.env` của người dùng để nguyên;
  - seed có thông tin đăng nhập mẫu. Tài khoản dev sẵn có được đặt mật khẩu mẫu, ghi ở
    `docs/local-development.md`;
  - ADR-36; hậu ký ADR-13; `data-model.md`; `teacher-surface.md`.
- **Ngoài phạm vi:**
  - đăng nhập Google thật;
  - quên mật khẩu, đổi mật khẩu của giáo viên;
  - giới hạn số lần thử đăng nhập (ghi vào backlog);
  - nút *Tạo lớp*: backlog, chờ người dùng.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `packages/schema/src/schema/models.py` | cột, bảng `sessions` |
| `services/be/src/be/accounts.py`, `account_routes.py`, `roster.py` (mới), `identity.py`, `main.py`, `seed.py` | BE |
| `services/be/tests/test_accounts.py`, `test_roster.py` (mới) | test BE |
| `services/fe/src/api.ts`, `App.tsx`, `screens/teacher/Rail.tsx`, `Account.tsx`, `Roster.tsx` (mới), `ClassDetail.tsx`, `screens/student/*`, `teacher.css`, `tokens.css`, test | FE |
| `services/fe/AGENTS.md`, `.env.example`, `docs/local-development.md`, ADR | tài liệu |

## Ordered Tasks

### Pha 0 — Figma
- [x] 1. Hộp *Đặt lại mật khẩu* (artboard `10b`), cùng khuôn với 28c: mật khẩu mới hiện một lần.

### Pha 1 — đăng nhập (schema, BE)
- [x] 2. Model và ALTER, cùng unique index cho `phone`, `email`, `username`, `token_hash`.
- [x] 3. `accounts.py`:
  - mật khẩu `scrypt$n$r$p$salt$hash`;
  - phiên: token ngẫu nhiên, chỉ lưu SHA-256 của nó, hạn 30 ngày;
  - tên đăng nhập và mã học sinh.
- [x] 4. Route:
  - `POST /api/teacher/sign-up`, `/api/teacher/sign-in`, `/api/teacher/sign-out`;
  - `POST /api/sign-in`, `/api/sign-out` cho học sinh.

  Cookie `HttpOnly`, `SameSite=Lax`, mỗi vai một tên. `GET /api/teacher/me` và `GET /api/me` thì đã
  có.
- [x] 5. `identity.py`: cookie thắng; `X-Actor` chỉ khi `dev_identity_enabled` và không cookie.
- [x] 6. Seed: thông tin đăng nhập mẫu. Tài khoản dev sẵn có: đặt mật khẩu mẫu bằng một lệnh, ghi vào
  `docs/local-development.md`.
- [x] 7. Test trên sqlite và `aiafa_test`.

### Pha 2 — danh sách lớp (BE)
- [x] 8. Xem trước từ danh sách tên, hay từ tệp `.csv`/`.xlsx` một cột.
- [x] 9. Tạo tài khoản: dòng trùng chỉ khi đã xác nhận. Mật khẩu ngẫu nhiên dạng `abc-def-gh`, trả về
  một lần.
- [x] 10. Tệp mật khẩu `.xlsx` dựng từ dữ liệu FE gửi; đặt lại mật khẩu một em.
- [x] 11. Test.

### Pha 3 — FE giáo viên: đăng nhập
- [x] 12. Ô tài khoản và menu; hộp đăng nhập (SĐT / email, Google chỉ giao diện); hộp đăng ký;
  đăng xuất.
- [x] 13. `api.ts` thôi gửi `X-Actor` ở các đường của giáo viên.
- [x] 14. Vitest; chụp, đo so với 26, 26b, 27; subagent chấm.

### Pha 4 — FE giáo viên: thêm học sinh
- [x] 15. Chi tiết lớp: cột tên đăng nhập, *Đặt lại mật khẩu*, *Thêm học sinh*.
- [x] 16. Ba bước 28, 28b, 28c; hộp đặt lại mật khẩu.
- [x] 17. Vitest; chụp, đo; subagent chấm.

### Pha 5 — FE học sinh
- [ ] 18. Màn đăng nhập 12; *Đăng xuất*; bỏ `ACTOR` hẳn.
- [ ] 19. Vitest; chụp, đo; subagent chấm.

### Pha 6 — đóng
- [ ] 20. ADR-36, hậu ký ADR-13, `services/fe/AGENTS.md`, `.env.example`, tài liệu; roadmap việc 22
  *Xong*; tick plan tổng; plan sang `completed/`.

## Decision Records

### Decision 1: `X-Actor` vẫn được nhận khi không có cookie và cờ dev bật
options considered: bỏ hẳn `X-Actor`; cookie thắng, `X-Actor` khi không cookie và cờ bật.
selected option: cookie thắng; `X-Actor` chỉ khi `dev_identity_enabled` bật và request không mang
cookie của vai ấy.
reason: 26 file test gọi bằng `X-Actor`; viết lại chúng không làm luật nào chắc hơn. FE thôi gửi header
ấy, nên trên trình duyệt chỉ còn cookie. `.env.example` tắt cờ, nên một cài đặt mới không nhận header.

### Decision 2: giữ *Đặt lại mật khẩu* của Figma 10
options considered: bỏ nút; giữ nút với một hộp hiện mật khẩu một lần.
selected option: giữ, theo ADR-13: luật *mật khẩu chỉ hiện một lần* áp cho cả nhập danh sách lẫn đặt
lại mật khẩu.
reason: một học sinh quên mật khẩu thì không có đường nào khác để vào lại, vì quên mật khẩu không có
trong phạm vi.

### Decision 3: tệp mật khẩu dựng từ dữ liệu FE gửi lên
options considered: BE giữ mật khẩu một lúc để tải; FE tự dựng `.xlsx`; BE dựng từ chính dữ liệu gửi
lên.
selected option: BE dựng từ dữ liệu FE gửi, không lưu gì.
reason: BE không được giữ mật khẩu rõ ở đâu cả, kể cả một lúc. FE chưa có thư viện `.xlsx`, còn BE đã
có `openpyxl` (việc 20).

### Decision 4: `dev_identity_enabled` mặc định `False`, nhưng lật ở Pha 5
options considered: giữ mặc định `True` (bản đầu của plan); lật ngay ở Pha 1; lật ở Pha 5.
selected option: lật ở Pha 5, khi FE học sinh thôi gửi `X-Actor`. Test bật cờ trong `conftest.py`;
BE chỉ đặt mật khẩu mẫu cho database rỗng khi cờ bật.
reason: review Pha 1–2 chỉ ra một cài đặt thiếu biến thì nhận `X-Actor`, mà mã `GV-00n` và mã học
sinh `1, 2, 3…` đều đoán được. Lật ngay thì hỏng màn học sinh đang chạy: `.env` dev không khai
biến này, và tới Pha 5 FE học sinh vẫn xưng danh bằng header.

## ALTER của DB dev (đã chạy 19/10/2026, dump trước ALTER ở scratchpad)

```sql
ALTER TABLE teachers ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE teachers ADD COLUMN IF NOT EXISTS email VARCHAR(254);
ALTER TABLE teachers ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
CREATE UNIQUE INDEX IF NOT EXISTS teachers_phone_key ON teachers (phone);
CREATE UNIQUE INDEX IF NOT EXISTS teachers_email_key ON teachers (email);
ALTER TABLE students ADD COLUMN IF NOT EXISTS username VARCHAR(64);
ALTER TABLE students ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
CREATE UNIQUE INDEX IF NOT EXISTS students_username_key ON students (username);
```

Bảng `sessions` do `create_all` tạo khi BE khởi động. Sau ALTER: `python -m be.seed` đặt đăng nhập
mẫu cho bốn tài khoản demo.

## Validation Checks

| Kiểm | Lệnh |
| --- | --- |
| Python, repo checks | `.\dev.ps1 test`, `.\dev.ps1 check` |
| Postgres | `pytest services/be/tests --postgres-url=…/aiafa_test` |
| Schema DB dev | `check_schema` khi BE khởi động lại sau ALTER |
| FE | `.\dev.ps1 typecheck`, vitest; Chrome headless + subagent chấm |
| Đầu cuối | đăng ký, đăng nhập, đăng xuất trên trình duyệt; nhập danh sách có dòng trùng; mật khẩu hiện một lần, F5 là mất; học sinh đăng nhập bằng tài khoản vừa tạo |

## Status

- 19/10/2026: plan mở. Pha 0 (Figma 10b `707:5377`) xong.
- 19/10/2026: Pha 1 và Pha 2 xong, hai commit. Subagent review sửa: `scrypt` và đọc tệp chạy ngoài
  event loop; tên đăng nhập lúc tạo lấy từ bảng xem trước; gốc tên đăng nhập cắt ở 56; `csv.Error`
  và tệp `.xlsx` hỏng lúc đọc thành 422; họ tên đăng ký dài quá 128 thành 422; phản hồi chở mật
  khẩu mang `Cache-Control: no-store`; đăng nhập dọn phiên hết hạn; mật khẩu mẫu chỉ đặt khi cờ dev
  bật; Decision 4. Còn lại, có ghi lý do: cookie chưa `Secure` (máy dev chạy http); trần 1 MB của
  tệp tải lên được kiểm sau khi Starlette đã nhận hết tệp -- trần thật đặt ở proxy khi triển khai.
- 19/10/2026: Pha 3 xong. Figma: canh giữa hộp 26b (`659:5311`), vẽ thêm 26c `709:5249` (đăng nhập sai,
  lời từ chối ngay trên nút). Subagent chấm ảnh 26, 26b, 26c, 27 khớp trong 1–2px. Review sửa:
  - lượt chat và kênh thư viện cũng báo 401;
  - phiên hết giữa chừng thì cây giữ nguyên dưới hộp đăng nhập, người khác vào thì về màn mở đầu;
  - lượt chat chạy dở không kéo màn sau khi đã tháo;
  - đăng xuất hỏng thì nói ra, phiên còn;
  - focus vào ô đầu, nền `inert` (`useInert` trong `Veil.tsx`);
  - hai tab là `radiogroup`.
- 19/10/2026: Pha 4 xong. Figma: thêm 28d `711:5287` (tab tải tệp). Chấm ảnh 10, 10b, 28, 28b,
  28c, 28d khớp 1–2px. Review sửa: nền `inert` và focus ở mọi bước; không tạo được em nào thì ở lại
  bước 2; khoá mọi *Đặt lại mật khẩu* khi một lần đang chạy; ô chọn tệp chọn lại được cùng tệp; đọc
  lại lớp hỏng thì nói ra. Chờ người dùng: *Đặt lại mật khẩu* chạy ngay, không hỏi lại (đúng Figma
  10b đã duyệt).
