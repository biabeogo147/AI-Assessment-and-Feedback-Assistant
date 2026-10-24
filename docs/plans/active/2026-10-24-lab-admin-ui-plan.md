# Plan — xem dữ liệu lab bằng UI chạy ở máy mình, qua SSH tunnel

## Goal

Người vận hành mở Postgres, Redis, Mongo và MinIO **của lab** bằng UI trên trình duyệt, không đăng
nhập lần nào, như các UI của stack dev. Mọi UI chạy bằng Docker **ở máy mình** và đi vào lab qua một
SSH tunnel; máy lab không chạy UI nào ngoài FE (người dùng chốt 24/10/2026).

## Scope

- `.\dev.ps1 lab-ui`: tra IP container trên lab, mở tunnel, đọc mật khẩu từ SSM, bật bốn UI local, in
  bốn URL. Ctrl+C tắt UI và đóng tunnel. **Không** tự mở trình duyệt.
- Bốn UI, đều ghi được (người dùng chốt): `pgweb`, `redis-commander`, `mongo-express`, và
  `s3manager` thay cho console MinIO (console luôn bắt đăng nhập).
- Lab: tắt console có sẵn của MinIO (`MINIO_BROWSER=off`). Không mở cổng nào, không thêm container.
- Không đổi service, contract, endpoint.

## Decision Records

- **D1 — tunnel trỏ vào IP container, tra lại mỗi lần chạy.** Compose của lab không publish cổng hạ
  tầng nào, kể cả trên `127.0.0.1`; IP container đổi sau mỗi lần tạo lại, nên `lab-ui` đọc nó bằng
  `docker inspect` qua SSH ngay trước khi mở tunnel. Đổi lại: deploy giữa chừng làm tunnel chết, chạy
  lại `lab-ui` là xong.
- **D2 — mật khẩu không ghi file, và chỉ vào môi trường trong lúc compose chạy.** `lab-ui` đọc SSM
  bằng aws CLI vào một biến cục bộ, đặt biến môi trường ngay trước mỗi lệnh `docker compose` và xoá
  ngay sau (review: một Ctrl+C rơi vào lúc khác không bỏ chúng lại trong phiên gọi
  `.\dev.ps1`). Chúng vẫn thấy được qua `docker inspect` ở máy mình — chấp nhận, đó là máy của
  người vận hành.
- **D3 — cổng local khác cổng dev** (tunnel `15432`/`16379`/`19000`/`27018`, UI `18081`–`18084`), để
  chạy song song với `infra-up`.

## Files

- `deploy/lab/admin-ui.yml` (mới), `deploy/lab/docker-compose.lab.yml` (MinIO)
- `dev.ps1`
- `tools/tests/test_lab_deploy.py`
- `docs/operation/deploy-lab.md`, `docs/operation/infrastructure.md`

## Ordered Tasks

- [x] `admin-ui.yml`: bốn UI, cổng chỉ `127.0.0.1`, nối `host.docker.internal:<cổng tunnel>`.
- [x] `dev.ps1 lab-ui`: IP lab từ `terraform output`, IP container qua SSH, tunnel, SSM, compose, URL.
- [x] Lab: `MINIO_BROWSER=off`; đưa lên máy, tạo lại `minio`.
- [x] Test: mọi cổng của `admin-ui.yml` bind `127.0.0.1`; console MinIO của lab tắt.
- [x] Docs.
- [x] Thử thật (24/10/2026): `lab-ui` mở bốn URL, cả bốn thấy dữ liệu lab không qua đăng nhập; giết
      tunnel thì UI, network và biến mật khẩu được dọn sạch. Ctrl+C trong một console thật chưa thử.
- [x] Một subagent review (24/10/2026); đã sửa: escape trong docstring test, báo đúng tham số SSM
      thiếu, nháy cho đường dẫn khoá có dấu cách, container dừng, mật khẩu chỉ vào môi trường quanh
      lệnh compose, tunnel cũ còn giữ cổng. Chạy lại `lab-ui` thật sau khi sửa: bốn UI lên, dọn sạch.

## Validation Checks

- `.\dev.ps1 check`, `tools/tests` xanh.
- Bốn URL mở ra là thấy dữ liệu lab, không màn đăng nhập.
- Sau Ctrl+C: không còn tiến trình `ssh` của tunnel, không còn container của `aiafa-lab-ui`.
- Từ Internet: cổng lab vẫn chỉ 80/443 (+22 cho `ssh_cidrs`); `smoke.sh` qua.

## Status

Xong phần code và thử thật (24/10/2026); còn người dùng thử Ctrl+C trong một console thật.
