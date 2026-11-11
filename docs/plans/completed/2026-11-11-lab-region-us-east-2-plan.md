# Lab chuyển sang account mới, region `us-east-2`

## Goal

Lab rời account AWS cũ sang một account mới nằm trong AWS Organization. SCP của tổ chức chỉ mở
`us-east-2` (Ohio): ở 33 region còn lại, mọi lệnh EC2, SSM, KMS, S3 đều bị từ chối tường minh, kể cả
với `AdministratorAccess` (kiểm 04/11/2026). Mặc định của repo phải trỏ vào region ấy, để `apply`,
`lab-ui` và tài liệu không còn dẫn sang Singapore.

## Files

- `deploy/lab/terraform/variables.tf`: `region` mặc định `us-east-2`, kèm lý do.
- `dev.ps1`: `lab-ui` dùng `us-east-2` khi không đặt `AIAFA_LAB_REGION`.
- `deploy/lab/lib.sh`: region dự phòng khi thiếu `/etc/aiafa-lab.conf`.
- `deploy/lab/smoke.sh`, `docs/operation/deploy-lab.md`, `docs/operation/infrastructure.md`: lệnh và
  chữ còn ghi Singapore.
- `docs/plans/backlog.md`: hai việc lộ ra lúc chuyển.

## Ordered Tasks

- [x] Destroy lab ở account cũ (23 tài nguyên), xoá hai khoá model tự thêm sau khi đã chép sang.
- [x] Tìm region SCP cho phép (quét 34 region) và kiểm dịch vụ lab cần ở `us-east-2`.
- [x] Đổi region mặc định và tài liệu.
- [x] `apply` ở account mới; sửa tay bước snap trên máy (backlog), chạy lại bootstrap.
- [x] `deploy.sh lab-2026.0.3`, `smoke.sh` xanh trên hai tên miền.
- [x] Sửa hai khoá model dính `\r` trong SSM (lệnh chép khoá ở Git Bash giữ CR), dựng lại `.env`.
- [x] Thử tay trên trình duyệt: giáo viên (lớp, Bảng theo dõi, đề, chat Kriky, tải tài liệu) và học sinh
  (bài của tôi, trang kết quả).

## Validation Checks

- `.\dev.ps1 check` (26/26) và `.\dev.ps1 test` (pytest 2028, vitest 392) xanh.
- `LAB_VERSION=lab-2026.0.3 bash deploy/lab/smoke.sh` qua hết trên `teacher.` và `student.`.

## Status

Xong 11/11/2026: lab chạy `lab-2026.0.3` ở account mới, máy `m7i-flex.large` ở `us-east-2`. Năm việc lộ
ra lúc chuyển nằm ở `docs/plans/backlog.md`, mục *Lộ ra khi chuyển lab sang account mới*.
