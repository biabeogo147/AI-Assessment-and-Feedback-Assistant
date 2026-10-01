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
| `agent` | Soạn nội dung bằng AI: đề, câu của lượt làm lại, lượt trả lời trong chat. Phát nội dung, không quyết định. | arq worker, không có cổng |

FE không biết AGENT tồn tại. Mọi thứ FE cần đều đi qua BE.

## Đường giao tiếp

```text
FE  --HTTP /api-->  BE  --queue-->  Redis  --queue-->  AGENT
                    │ ▲                                  │
                    │ └────────── arq result store ──────┘
                    └── Postgres (trạng thái bài làm)
```

**Chấm bài không đi qua hàng đợi.** Nó là một phép so giữa phương án đã chọn và đáp án đúng trong
database của BE, nên nó chạy ngay trong request nộp bài
([ADR-20](../decisions/adr-20-cham-trac-nghiem-thuoc-be.md)). Hệ quả nhìn thấy được: giữa màn làm
bài và màn kết quả không có trạng thái *đang chấm* nào.

**Hàng đợi dành cho bốn việc thật sự cần model**, và cả bốn đều bất đồng bộ vì một lần gọi LLM đủ
lâu để giữ kết nối HTTP mở là không hợp lý:

| Task | Khi nào | BE làm gì với kết quả |
| --- | --- | --- |
| `write_draft_question` | **một câu** của bộ đề giáo viên yêu cầu | kiểm theo ADR-18 rồi lưu vào đúng vị trí đã yêu cầu |
| `generate_retry_question` | học sinh mở một lượt làm lại | kiểm rồi lưu kèm đáp án đúng, để BE tự chấm lượt |
| `explain_turn` | mỗi lượt trả lời trong chat pha 2 | lưu vào lịch sử **trước** khi phát ra SSE |
| `propose_next_step` | mỗi bước của một lượt chat giáo viên | chạy tool đã đề xuất, hoặc từ chối nó |

`write_draft_question` viết **một** câu một job, không phải cả bộ. Đó không phải khẩu vị mà là số
học: `tools/check_contract.py` so `LLM_TIMEOUT_SECONDS × LLM_MAX_ATTEMPTS` với độ kiên nhẫn của BE
cho **một** job, nên một job soạn 50 câu là 50 lần ngân sách mà check đang kiểm. Task cũ
`draft_assessment` làm đúng thế, và check nói dối về nó suốt thời gian nó tồn tại.

Ngoài bốn task trên, worker còn đăng ký `grade_submission` — legacy của ADR-20, giữ để client cũ
không treo, và không gọi model.

BE chờ job xong ngay trong request (`agent_gateway.run_task`) thay vì trả `job_id` cho FE: mọi lời
gọi ấy đều nằm trong một thao tác người dùng đang nhìn, nên thêm một giao thức poll thứ hai chồng
lên arq không mua được gì.

**Chat dùng SSE.** `GET /api/attempts/{id}/chat/stream` trả `text/event-stream`, chữ hiện dần. Nó là
**kênh tăng tốc cảm giác, không phải nguồn sự thật**: lượt trả lời được lưu xong mới phát, nên mất
kết nối chỉ mất phần hoạt hình. Client đọc lại lịch sử bằng REST sau mỗi lần stream.

FE gọi đường tương đối `/api` và Vite proxy sang BE, nên trình duyệt chỉ làm việc với một origin duy nhất và BE không cần cấu hình CORS.

## Ranh giới quyền quyết định

Đây là ràng buộc nghiệp vụ quan trọng nhất trong kiến trúc.

`business-workflows.md` tách bước hệ thống tạo kết quả khỏi bước hệ thống quyết định đưa kết quả vào `Teacher Review Queue`. Kiến trúc tôn trọng sự tách đó:

- AGENT trả về `GradingCompleted` chỉ chứa **bằng chứng**: `score`, `confidence`, `misconception_code`, và hai cờ cho biết đáp án có mâu thuẫn với cách làm hay không và có đủ căn cứ hay không.
- BE, trong `be/review_policy.py`, so ngưỡng và sinh `needs_teacher_review` cùng `review_reason`.

Nếu để AGENT tự quyết định, cổng teacher-in-the-loop sẽ nằm bên trong AI service, trái nguyên tắc trong [Project Overview](project-overview.md).

Cùng lằn ranh ấy áp cho nội dung AGENT sinh ra: BE **kiểm lại** mọi câu hỏi trước khi lưu — đúng một
đáp án đúng, mọi nhiễu gắn một lỗi, ít nhất hai cách giải. Một luật nghiệp vụ chỉ được nhắc trong
prompt là một luật không được thi hành.

`ReviewReason` có bốn giá trị, khớp bốn điểm kiểm soát trong Workflow 4. Giá trị `ANOMALY` chưa sinh ra được vì cần lịch sử học tập của học sinh; nó có mặt sẵn để lúc thêm không phải đổi contract.

Ngưỡng được áp lúc đọc kết quả chứ không lưu kèm, nên đổi `REVIEW_CONFIDENCE_THRESHOLD` có hiệu lực ngay mà không phải chấm lại.

## Ranh giới dữ liệu

Postgres thuộc về BE và chỉ BE. Nó giữ lớp, học sinh, đề, lần làm bài, sổ điểm ba mức, bộ đếm vòng,
từng lượt làm lại kèm đề đã sinh ra, đoạn chat và các báo cáo.
[ADR-21](../decisions/adr-21-trang-thai-bai-lam-la-ben.md) là lý do nó tồn tại: hạn pha 2 do giáo
viên đặt, tính bằng giờ hoặc ngày, nên trạng thái bài làm không thể sống trong một chỗ có TTL một
giờ. `JOB_RESULT_TTL_SECONDS` vẫn còn và vẫn đúng — nó nói về kết quả một job của arq, không nói về
bài làm của học sinh.

AGENT không nhận credential của bất kỳ database nào, nên **một job phải tự chứa**: `explain_turn`
mang theo cả câu hỏi, phương án, lời giải và lỗi đã soạn, chứ không mang id để tra. `tools/check_contract.py`
canh điều này bằng cách quét mọi file Python của AGENT tìm dấu vết truy cập database.

Bảng được tạo từ metadata của model lúc khởi động, chưa có công cụ migration. Đó là một món nợ có
chủ đích: schema hiện có một người dùng và chưa có dữ liệu thật nào. Ngày có dữ liệu thật, đánh đổi
ấy lật ngược.

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

## Vì sao chưa có các diagram khác

Repo hiện có bốn diagram nghiệp vụ từ Phase 1 và một diagram kiến trúc. Ba loại còn lại chưa tạo, mỗi loại có một điều kiện rõ ràng để bắt đầu.

**Sequence Diagram** sẽ cần khi luồng chấm có nhiều hơn một bước bất đồng bộ. Hiện chỉ có đúng một chặng qua queue, và mô tả bằng lời trong mục "Đường giao tiếp" đã đủ. Khi AGENT gọi LLM thật, luồng sẽ có thêm ít nhất một bước chờ và một nhánh lỗi — lúc đó sequence diagram bắt đầu nói được thứ mà lời văn không nói nổi.

**Class Diagram hoặc ERD** sẽ cần khi có Postgres. Hiện chưa có bảng nào, nên vẽ ra chỉ khiến team hiểu nhầm rằng data model đã chốt. `domain-context.drawio` chỉ mô tả boundary và tương tác với Teacher, Student; nó không mô tả object nội bộ hay schema.

**Deployment Diagram** sẽ cần khi ba service được container hoá. Hiện chúng chạy native trên một máy và `system-architecture.drawio` đã thể hiện đủ ranh giới giữa tiến trình native và container hạ tầng.

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
