# Plan — debug cả luồng tài liệu trong PyCharm, và giao diện xem ba kho dữ liệu

## Goal

Luồng FE → BE → `document` → `index` → `ingest` → FE đã thông về code (plan 3c), nhưng bật nó là
`infra-up` cộng sáu terminal `dev.ps1`, và các process ấy không gắn được debugger. Người dùng muốn
bấm Debug một lần, tải tệp trên FE, dừng ở breakpoint của bất kỳ service nào, rồi xem Postgres,
Redis và Mongo bằng giao diện. Người dùng chốt ngày 12/10/2026: **PyCharm compound**, không đưa nội
dung tài liệu vào prompt, không sửa code service.

## Files

| File | Việc |
|---|---|
| `.run/{be,ingest,agent,document,index,fe}.run.xml` | sáu run configuration, cùng lệnh với `dev.ps1` |
| `.run/toan-he-thong.run.xml` | compound *Toàn hệ thống* gom cả sáu |
| `docker-compose.infra.yml` | pgweb (8081), redis-commander (8082), mongo-express (8083), chỉ bind 127.0.0.1 |
| `dev.ps1` | nhãn `infra-up`, `infra-down` và dòng help nhắc ba giao diện |
| `docs/local-development.md` | mục *Debug cả luồng trong PyCharm*; bảng cổng |

## Ordered Tasks

- [x] Sáu cấu hình Python/npm và compound. Worker chạy `python -m arq` (debugger không gắn được vào
      `arq.exe`); BE bỏ `--reload` (reloader chạy app trong process con).
- [x] Ba giao diện trong `docker-compose.infra.yml`, không hỏi mật khẩu nên chỉ nghe ở 127.0.0.1.
- [x] Tài liệu: bản đồ breakpoint theo thứ tự chạy, bẫy timeout, lệnh `mongosh`, cổng.
- [x] Review bằng subagent, sửa theo review.

## Validation Checks

- Bảy file XML parse được.
- `python -m arq` của `ingest`, `agent`, `index` import xong và đọc `.env` (lúc ấy Docker tắt nên dừng
  ở bước nối Redis); `be.main` và `document.ocr_worker` import được.
- `infra-up` lên cả bảy container; 8081/8082/8083 trả 200; pgweb thấy schema `public`,
  redis-commander thấy Redis 7.4, mongo-express thấy `aiafa_content` và tắt basic auth.
- `.\dev.ps1 check` xanh.
- **Chưa kiểm:** mở `.run/` trong PyCharm và dừng thật ở một breakpoint -- việc của người dùng.

## Status

**Xong 12/10/2026**, trừ phép thử trong PyCharm ở trên. Review sửa: breakpoint SSE dời từ
`document_events.py:100` (dòng `while True:` chỉ chạy một lần, lúc mở trang) sang
`teacher_documents.py:238`; dặn tắt terminal `dev.ps1` trước khi Debug (hai consumer trên một queue
làm breakpoint im lặng); `indexes` ghi sau cùng; timeout 300 s của `ingest`; PDF scan chạy bằng Run.

Còn để ngỏ: `fe.run.xml` cần PyCharm Professional; tên module trong `.run/` theo tên thư mục clone
(`.idea/` không vào git); `redis-commander:latest` không ghim phiên bản (ảnh đứng ở 0.7.2-rc3 từ
2021).
