# AI Assessment and Feedback Assistant

Hệ thống hỗ trợ giáo viên tạo đề, chấm bài, phân tích lỗi sai và tạo vòng luyện tập thích ứng cho học sinh.

Bối cảnh nghiệp vụ: [Project Overview](docs/overview/project-overview.md).
Kiến trúc kỹ thuật: [Architecture](docs/overview/architecture.md).
Quy tắc cộng tác cho dev và coding agent: [AGENTS.md](AGENTS.md).

## Yêu cầu

- conda với một env Python 3.12. Mặc định script trỏ tới `D:\Anaconda\envs\AI-Assessment-and-Feedback-Assistant`; đặt biến `AIAFA_PYTHON` nếu env của bạn nằm chỗ khác.
- Node 22 và pnpm.
- Docker Desktop, chỉ dùng để chạy Redis.

## Chạy lần đầu

PowerShell chặn script chưa ký, nên phiên làm việc đầu tiên cần:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Sau đó:

```powershell
copy .env.example .env
.\dev.ps1 install
.\dev.ps1 infra-up
```

## Chạy hệ thống

Ba service chạy native, mỗi cái một terminal:

```powershell
.\dev.ps1 be       # http://localhost:8000
.\dev.ps1 agent    # worker, không có cổng
.\dev.ps1 fe       # http://localhost:5173
```

Mở `http://localhost:5173` và nộp thử một bài. Để trống phần giải thích để thấy trường hợp cần giáo viên xem lại.

## Kiểm tra

```powershell
.\dev.ps1 test     # pytest và vitest
.\dev.ps1 check    # ruff và hàng rào import
.\dev.ps1 fmt      # format và autofix
```

`check` là thứ giữ ranh giới giữa BE và AGENT. Vì hai service dùng chung một conda env, không có gì chặn được import chéo lúc chạy — `import-linter` là cơ chế duy nhất, và nó cũng chạy tự động qua pre-commit.

## Cấu trúc

| Thư mục | Vai trò |
| --- | --- |
| `services/be` | Business layer, là service duy nhất FE biết tới |
| `services/agent` | Worker chấm bài, chỉ phát bằng chứng, không quyết định gì |
| `services/fe` | Vite + React, gọi BE qua proxy `/api` |
| `packages/contracts` | Message contract dùng chung. Chỉ có dữ liệu, không có logic |
| `docs/` | Tài liệu nghiệp vụ và kiến trúc |

Quy ước đặt tên khi thêm service mới nằm trong [Architecture](docs/overview/architecture.md).
