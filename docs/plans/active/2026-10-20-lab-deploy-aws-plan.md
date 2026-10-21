# Plan — triển khai lab trên AWS (Terraform + Caddy) và seed dữ liệu lab

## Goal

Một môi trường lab cho 5 người trong team trên một account AWS free plan (credit): `terraform apply`
cộng vài key trong SSM là có một URL HTTPS dùng được, đã có dữ liệu giống thật (5 giáo viên, 30 lớp,
1000 học sinh, đề ở mọi trạng thái). Có OCR. Người dùng tự chạy `apply`.

## Scope

- Một EC2, một `docker compose`; Caddy phục vụ FE tĩnh, proxy `/api`, basic auth trước cả site.
- BE: đăng ký giáo viên tắt được theo môi trường (lab tắt; **FE không đổi**, lời từ chối của BE hiện
  sẵn trên hộp đăng nhập); cookie phiên có cờ `Secure` khi chạy HTTPS.
- Seed lab không gọi model; giáo viên và học sinh dùng **chung một mật khẩu** (lab, người dùng chốt
  20/10/2026), đọc từ stdin.
- Ngoài: `docs/report/`; CI; migration; tài liệu và hội thoại Kriky trong seed.

## Files

- `services/be/src/be/config.py`, `account_routes.py`, `.env.example`; test BE.
- Mới `services/be/src/be/lab_seed/`; `services/be/tests/test_lab_seed.py`. `be/reset_db.py` tách
  `wipe` (xoá database + bucket) để seed lab dùng chung; `be/seed.py` đổi `_QUESTIONS` thành
  `DEMO_QUESTIONS` vì seed lab dùng lại sáu câu ấy.
- Mới `deploy/lab/` (Dockerfile, Caddyfile, compose, `lab.env`, script) và `deploy/lab/terraform/`.
- Mới test ở `tools/tests/` cho `lab.env` và compose lab.
- Mới `docs/deploy-lab.md`; sửa `README.md`, `docs/local-development.md`, `.gitignore`, hậu ký
  ADR-36; `dev.ps1 install` cài thêm `pyyaml` (test cấu hình lab đọc file compose).

## Ordered Tasks

- [x] BE: `TEACHER_SIGN_UP_ENABLED`, `SESSION_COOKIE_SECURE`, test.
- [x] `be.lab_seed` + test (đếm, khớp `be.scoring`, route đọc trả 200, từ chối khi thiếu `--reset`).
- [x] `deploy/lab/`: Dockerfile, Caddy, compose, `lab.env`, script; test `tools/tests`.
- [x] Chạy stack lab ở local (project `aiafa-lab`, `127.0.0.1:8088`, `LLM_ENABLED=false`), seed:
  6 s trên Postgres; PDF có chữ và PDF scan tới *sẵn sàng* (OCR ~2,7 s/trang, 2 luồng); cả stack ~2 GB RAM.
- [x] Terraform: `fmt`, `validate`, `plan` (không `apply`): 25 tài nguyên.
- [x] Tài liệu.
- [x] `.\dev.ps1 test`, `check`, `typecheck`.
- [x] Subagent review code; sửa theo review: cron thiếu PATH của snap, IMDS hop limit 1, IAM đọc
  lại backup, vòng chữa lặp đề (thêm `lab_seed/retries.py`, 3 đề mỗi câu, test bằng chính
  `validate_question`/`validate_retry`), thiếu khoá Claude thì tắt model, bootstrap chịu khoá dpkg,
  bí mật compose bắt buộc, `.gitattributes`, tài liệu.
- [x] Thử tay trên stack lab local, chụp ảnh; subagent chấm ảnh (7/10); sửa lỗi của seed: đáp án
  luôn là A (nay xáo), giờ giấc về giờ học, tên đề trùng, "45 phút" cho 6 câu, chat hỏi một đằng
  đáp một nẻo, báo cáo trùng chữ, tên đệm trùng họ, phân bố điểm quá hẹp.
- [ ] Người dùng thêm key vào SSM, `terraform apply`; `smoke.sh` vào URL lab.

## Decision Records

- **D1 — đăng ký chặn ở BE, không ẩn ở FE.** Người dùng chọn 20/10/2026: basic auth đã chặn người
  ngoài, nên một lời từ chối rõ ràng là đủ và Figma không phải đổi.
- **D2 — `deploy/` là thư mục gốc mới**, chủ sở hữu là việc triển khai. Nó không phải một service:
  không code sản phẩm, không import từ `services/`. Ghi ở bảng *Cấu trúc* của `README.md`, **chưa**
  ở bảng layout của `AGENTS.md`: file ấy đang đúng trần 184 dòng của `contract-length`, và nâng
  trần là sửa contract -- để người dùng quyết.
- **D3 — hai image Python.** `app` (be, agent, ingest) không mang torch/paddle; `document` mang. Một
  image chung làm mọi process kéo vài GB không dùng tới.
- **D4 — một mật khẩu chung cho tài khoản seed**, băm một lần. Chỉ cho lab; nằm trong SSM, không in ra.
- **D5 — không có migration** (như `be/db.py`): đổi model thì seed lại lab. Chấp nhận được với dữ liệu
  seed; ngày lab có dữ liệu thật thì quyết định này phải xem lại.

## Validation Checks

- `.\dev.ps1 test`, `check`, `typecheck` xanh.
- `terraform fmt -check`, `terraform validate` sạch; `terraform plan` chỉ có tài nguyên đã liệt kê.
- Stack lab local: mọi container *healthy*; một PDF có chữ và một PDF scan đi tới *sẵn sàng*.
- Seed: đếm qua SQL đúng 5/30/1000; ảnh thử tay qua chấm.
- `smoke.sh`: 401 khi thiếu basic auth; đăng ký 403; `X-Actor` vô hiệu; cổng hạ tầng đóng.

## Status

Xong phần code và kiểm ở local. Còn: người dùng thêm khoá vào SSM, `terraform apply`,
`smoke.sh` vào URL lab. Chưa làm, ghi để người dùng quyết: chủ đề Toán theo đúng chương trình GDPT
2018 ("Mũ và logarit" là lớp 11, "Hàm số bậc hai" là học kỳ II); dòng `deploy/` trong bảng layout của
`AGENTS.md` (vượt trần dòng); sáu điểm của sản phẩm mà dữ liệu seed làm lộ ra (báo cáo cuối lượt).
