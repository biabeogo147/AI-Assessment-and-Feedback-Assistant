# Kriky

Hệ thống hỗ trợ giáo viên tạo đề, chấm bài, phân tích lỗi sai và tạo vòng luyện tập thích ứng cho học sinh.

| Tài liệu | Trả lời câu hỏi |
| --- | --- |
| [Local Development](docs/local-development.md) | Chạy, demo và chẩn đoán sự cố trên máy |
| [Project Overview](docs/overview/project-overview.md) | Project giải quyết vấn đề gì, cho ai |
| [Architecture](docs/overview/architecture.md) | Hệ thống được chia thế nào và vì sao |
| [Decisions](docs/decisions/README.md) | Quyết định nghiệp vụ: cái gì không đảo ngược được, ai được làm gì |
| [AGENTS.md](AGENTS.md) | Luật khi sửa bất cứ thứ gì trong repo |

## Chạy nhanh

Cần conda với env Python 3.12, Node 22 kèm pnpm, và Docker Desktop để chạy Redis.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
copy .env.example .env
.\dev.ps1 install
.\dev.ps1 infra-up
```

Rồi mở ba terminal:

```powershell
.\dev.ps1 be       # http://localhost:8000
.\dev.ps1 agent    # worker, không có cổng
.\dev.ps1 fe       # http://localhost:5173
```

Mở `http://localhost:5173` và nộp thử một bài. Để trống phần giải thích để thấy trường hợp cần giáo viên xem lại.

Nếu có bước nào không chạy như mô tả, [Local Development](docs/local-development.md) có mục chẩn đoán sự cố.

## Cấu trúc

| Thư mục | Vai trò |
| --- | --- |
| `services/be` | Business layer, là service duy nhất FE biết tới |
| `services/agent` | Worker chấm bài, chỉ phát bằng chứng, không quyết định gì |
| `services/fe` | Vite + React, gọi BE qua proxy `/api` |
| `packages/contracts` | Message contract dùng chung. Chỉ có dữ liệu, không có logic |
| `tools/` | Check ở tầng repo mà không service nào tự kiểm được cho mình |
| `docs/` | Tài liệu nghiệp vụ, kiến trúc và vận hành |

Mỗi service có `AGENTS.md` riêng ghi ràng buộc cục bộ của nó.

## Về cái tên

Sản phẩm tên **Kriky**. Nhưng thư mục repo, conda env, container Redis, tên queue và distribution
name vẫn mang tiền tố cũ `aiafa` / `AI-Assessment-and-Feedback-Assistant`. Đó là **có chủ ý, không
phải sót**: chúng là định danh máy đang chạy thật, đổi tên là phải cài lại env, dựng lại container và
đồng bộ lại `.env`. Tên hiển thị đổi được rẻ, định danh máy thì không.
