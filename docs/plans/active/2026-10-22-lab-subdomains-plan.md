# Plan — lab trên hai subdomain: `teacher.<tên gốc>` cho giáo viên, `student.<tên gốc>` cho học sinh

## Goal

Lab bỏ tên sslip.io và chạy trên tên miền riêng, tách theo vai: giáo viên vào `teacher.recruitai.io.vn`,
học sinh vào `student.recruitai.io.vn`. Hai tên dùng chung một bản FE, cùng `/api`, cùng một Caddy;
BE không đổi. Trên hai tên ấy FE chọn vai theo hostname thay cho hash: trên tên học sinh, `#/teacher`
về màn học sinh. Đây là giao diện, không phải ranh giới quyền: quyền vẫn ở cookie theo vai của BE.

## Scope

- Terraform: biến bắt buộc `base_domain`, hai tên con dựng từ hai tiền tố cố định `teacher.` /
  `student.`. Bản ghi DNS tạo tay, Terraform không quản.
- FE: `surfaceFor(hostname, route)` ở `App.tsx`; giao diện không đổi, Figma không đổi.
- `smoke.sh` kiểm được nhiều URL; tài liệu lab.
- Không đổi BE, contract, endpoint.

## Files

- `deploy/lab/terraform/{variables,main,ssm,outputs}.tf`, `deploy/lab/Caddyfile`, `deploy/lab/smoke.sh`
- `services/fe/src/App.tsx`, `services/fe/src/App.test.tsx`
- `tools/tests/test_lab_deploy.py`
- `docs/operation/deploy-lab.md`, `docs/operation/architecture.md` (người dùng chuyển từ `docs/` sang,
  22/10/2026)

## Ordered Tasks

- [x] Bỏ sslip.io: `site_domain` bắt buộc, validation không nhận IP; docs (subagent review, đã sửa).
- [x] Terraform: `base_domain`, `teacher_host` / `student_host`, `SITE_ADDRESS` hai tên, output
      `teacher_url` / `student_url`.
- [x] FE: `surfaceFor` + test vitest.
- [x] Test khoá hai tiền tố có mặt ở cả Terraform lẫn FE.
- [x] `smoke.sh` nhiều URL; comment Caddyfile; tài liệu.
- [x] `.\dev.ps1 check`, `test`, `typecheck`.
- [ ] DNS (người dùng): sửa delegation của zone, hai bản ghi A về Elastic IP.
- [ ] `terraform apply`; đẩy code lên máy lab; `render-env.sh`; `up -d --build caddy`.
- [ ] `smoke.sh` hai URL thật; thử trên browser, chụp ảnh.
- [x] Subagent review phần code (chạy trước khi đưa lên máy lab, vì DNS chặn); đã sửa: tài liệu nói rõ
      tách tên là giao diện chứ không phải quyền, cảnh báo apply trước DNS, quét cổng một lần, test khoá
      tiền tố theo từng vai.

## Decision Records

### Decision: Vai theo hostname, quy ước bằng tiền tố

options considered: hai biến tên miền tự do, FE đọc tên qua build arg của image caddy; một tên gốc,
tiền tố `teacher.` / `student.` cố định mà FE nhận ra từ hostname; chỉ chuyển hướng ở Caddy.
selected option: một tên gốc, tiền tố cố định.
reason: FE là một bản build tĩnh phục vụ cả hai tên, nên nó chỉ biết mình đang ở đâu qua
`location.hostname`; một build arg cho mỗi tên làm image caddy phụ thuộc vào cấu hình của từng môi
trường. Caddy không thấy hash nên không chặn được `#/teacher` trên tên học sinh. Tiền tố cố định là một
quy ước duy nhất, và một test ở `tools/tests` đòi nó có mặt ở cả Terraform lẫn FE.

## Validation Checks

- `terraform fmt -check`, `validate`; validation từ chối `1.2.3.4` và `https://x.vn/`; `plan` chỉ đổi
  tham số SSM.
- `.\dev.ps1 check`, `.\dev.ps1 test`, `.\dev.ps1 typecheck`.
- `smoke.sh` qua trên cả hai URL thật.
- Browser: `teacher.…/#/` về `#/teacher`; `student.…/#/teacher` về `#/`; hai phiên ở hai tab không đá
  nhau.

## Status

Đang làm. DNS của zone `recruitai.io.vn` còn SERVFAIL (22/10/2026): NS mà `.vn` ủy quyền từ chối trả
lời, nên bước đưa lên máy lab chờ người dùng sửa.
