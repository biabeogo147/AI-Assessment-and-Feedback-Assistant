# Architecture

## Mục đích tài liệu

Tài liệu này mô tả kiến trúc kỹ thuật của giai đoạn đầu Phase 2: có những service nào, chúng nói chuyện với nhau ra sao, ranh giới quyền quyết định nằm ở đâu, và cơ chế nào giữ cho ranh giới đó không bị phá.

Tài liệu này không mô tả nghiệp vụ. Nghiệp vụ thuộc về [Project Overview](project-overview.md), [Business Workflows](business-workflows.md) và [Use Case Specification](use-case-specification.md).

Diagram liên quan:

- [System Architecture Diagram](../diagrams/system-architecture.drawio)

## Ba service

| Service | Vai trò | Chạy bằng |
| --- | --- | --- |
| `fe` | Giao diện cho Teacher và Student. Chỉ nói chuyện với BE. | Vite dev server, cổng 5173 |
| `be` | Business layer, system of record, nơi giữ mọi quyết định nghiệp vụ. | uvicorn, cổng 8000 |
| `agent` | Chấm bài và phân tích lỗi sai bằng AI. Phát bằng chứng, không quyết định. | arq worker, không có cổng |

FE không biết AGENT tồn tại. Mọi thứ FE cần đều đi qua BE.

## Đường giao tiếp

```text
FE  --HTTP /api-->  BE  --queue-->  Redis  --queue-->  AGENT
                     ▲                                   │
                     └────────── arq result store ───────┘
```

Chấm bài chạy bất đồng bộ vì một lần gọi LLM đủ lâu để giữ kết nối HTTP mở là không hợp lý. Vì vậy:

1. FE gọi `POST /api/submissions`, BE đẩy job vào Redis và trả về `job_id`.
2. FE poll `GET /api/jobs/{job_id}` mỗi giây, tối đa 30 giây.
3. AGENT nhận job, chấm, trả kết quả. arq tự lưu kết quả nên hệ thống không cần job store riêng.
4. BE đọc kết quả, áp ngưỡng, rồi trả về kèm quyết định review.

FE gọi đường tương đối `/api` và Vite proxy sang BE, nên trình duyệt chỉ làm việc với một origin duy nhất và BE không cần cấu hình CORS.

## Ranh giới quyền quyết định

Đây là ràng buộc nghiệp vụ quan trọng nhất trong kiến trúc.

`business-workflows.md` tách bước hệ thống tạo kết quả khỏi bước hệ thống quyết định đưa kết quả vào `Teacher Review Queue`. Kiến trúc tôn trọng sự tách đó:

- AGENT trả về `GradingCompleted` chỉ chứa **bằng chứng**: `score`, `confidence`, `misconception_code`, và hai cờ cho biết đáp án có mâu thuẫn với cách làm hay không và có đủ căn cứ hay không.
- BE, trong `be/review_policy.py`, so ngưỡng và sinh `needs_teacher_review` cùng `review_reason`.

Nếu để AGENT tự quyết định, cổng teacher-in-the-loop sẽ nằm bên trong AI service, trái nguyên tắc trong [Project Overview](project-overview.md).

`ReviewReason` có bốn giá trị, khớp bốn điểm kiểm soát trong Workflow 4. Giá trị `ANOMALY` chưa sinh ra được vì cần lịch sử học tập của học sinh; nó có mặt sẵn để lúc thêm không phải đổi contract.

Ngưỡng được áp lúc đọc kết quả chứ không lưu kèm, nên đổi `REVIEW_CONFIDENCE_THRESHOLD` có hiệu lực ngay mà không phải chấm lại.

## Ranh giới dữ liệu

Giai đoạn này chưa có database. Khi thêm, quy ước là Postgres và MongoDB thuộc về BE. AGENT không nhận credential của bất kỳ database nào, nên một job phải mang theo đủ dữ liệu để chấm — đó là lý do `GradingRequested` chứa cả `learning_objective` và `student_explanation` thay vì chỉ chứa id.

## Shared code

`packages/contracts` là thứ duy nhất cả BE và AGENT cùng import. Nó chỉ chứa dữ liệu: message, enum, và hằng số tên task. Không có logic, vì bất cứ hành vi nào đặt ở đây sẽ trở thành hành vi dùng chung mà không service nào sở hữu.

Tên task queue là hằng số trong `contracts`, nên BE enqueue bằng chuỗi và không bao giờ phải import `agent`.

Hai loại package dùng chung khác chưa được tạo và chỉ tạo khi có nhu cầu thật: một thư viện hạ tầng không dính nghiệp vụ, và một client TypeScript sinh từ OpenAPI của BE. Không tạo package tên `common`, `utils` hay `shared`, vì tên vô nghĩa sẽ hút mọi thứ vào.

## Cơ chế giữ ranh giới

BE và AGENT hiện dùng chung một conda env. Đó là quyết định về thao tác, không phải về kiến trúc, nhưng nó có hệ quả: **không có gì chặn được import chéo lúc chạy**.

Vì vậy ranh giới chỉ còn một cơ chế duy nhất đỡ, và nó phải tự động:

- `import-linter` cấu hình trong `pyproject.toml` với hai contract: `be` và `agent` độc lập với nhau, và `contracts` không được import ngược lên service nào.
- Hook pre-commit chạy nó mỗi lần commit, dùng đường dẫn tuyệt đối tới interpreter của conda env.

Hai lưu ý khi sửa cấu hình này:

- Phải gọi console script `lint-imports`. Lệnh `python -m importlinter.cli` thoát 0 mà không kiểm tra gì — một false pass sẽ vô hiệu hoá toàn bộ cơ chế mà không ai biết.
- Ba package Python dùng `setuptools` chứ không phải `hatchling`, vì editable install của hatchling khiến `grimp` có thể không dựng được đồ thị import và im lặng báo không có vi phạm.

Cách duy nhất biết hàng rào còn sống là thử phá nó: thêm `import be` vào `services/agent/src/agent/worker.py`, chạy `.\dev.ps1 check`, xác nhận nó fail, rồi hoàn tác.

## Quy ước đặt tên service mới

| Thứ | Quy tắc | Ví dụ |
| --- | --- | --- |
| Tên thư mục | Chữ thường, đặt theo domain chứ không theo tầng | `services/review-queue` |
| Python import package | snake_case của tên thư mục, nằm dưới `src/` | `src/review_queue/` |
| Tên distribution | Tiền tố `aiafa-` để không đụng tên trên PyPI | `aiafa-review-queue` |
| Tiền tố biến môi trường | UPPER_SNAKE | `REVIEW_QUEUE_DB_DSN` |
| Cổng | BE 8000, service mới cộng thêm 100 | `8100`, `8200` |

`be`, `agent` và `fe` là ngoại lệ của quy tắc đặt theo domain vì chúng là tầng chứ không phải domain. Service thứ tư trở đi đặt theo domain.

Mỗi service giữ `pyproject.toml` riêng khai báo đúng dependency của mình, kể cả khi đang dùng chung môi trường. Nhờ vậy lúc tách service ra không phải viết lại gì, chỉ đổi cách cài đặt.
