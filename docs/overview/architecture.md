# Architecture

## Mục đích tài liệu

Tài liệu này mô tả kiến trúc kỹ thuật của giai đoạn đầu Phase 2: có những service nào, chúng nói chuyện với nhau ra sao, ranh giới quyền quyết định nằm ở đâu, và cơ chế nào giữ cho ranh giới đó không bị phá.

Tài liệu này không mô tả nghiệp vụ. Nghiệp vụ thuộc về [Project Overview](project-overview.md), [Business Workflows](business-workflows.md) và [Use Case Specification](use-case-specification.md).

Diagram liên quan:

- [System Architecture Diagram](../diagrams/system-architecture.drawio)

## Năm service, năm process

| Service | Vai trò | Chạy bằng |
| --- | --- | --- |
| `fe` | Giao diện cho Teacher và Student. Chỉ nói chuyện với BE. | Vite dev server, cổng 5173 |
| `be` | Business layer, system of record, nơi giữ mọi quyết định nghiệp vụ. | uvicorn cổng 8000 |
| `agent` | Soạn nội dung bằng AI: đề, câu của lượt làm lại, lượt trả lời trong chat. Phát nội dung, không quyết định. | arq worker, không có cổng |
| `document` | Đọc tệp giáo viên tải lên: có chữ hay không, bao nhiêu trang. Báo lại, không sở hữu hàng nào. | arq worker, không có cổng |
| `ingest` | Ghi lại thứ `document` báo về. Giữ credential database, sở hữu không quyết định nào. | arq worker, không có cổng |

**`ingest` giữ credential database, và nó vẫn là một service riêng.** Hai điều ấy
không mâu thuẫn, nhưng chúng đã từng bị đọc là mâu thuẫn, nên nói thẳng ra: cái làm
`agent` và `document` thành service đọc-và-báo là chúng **không ghi vào bảng nào** —
thứ chúng cần đi tới trong payload của job — chứ không phải việc chúng chạy process
riêng. Một service ghi một hàng thì cần đường tới hàng ấy.

Cái **thật sự** giữ ranh giới giữa `be` và `ingest` là một thứ khác, và nó đo được:
chúng không import nhau được. `lint-imports` cấm mọi chiều giữa bốn service, nên không
một luật nghiệp vụ nào của BE với tới được `ingest`, và danh sách những module bị cấm
thì **không tồn tại** — không có danh sách nào thì không có danh sách nào lỗi thời.

Hai service dùng chung đúng hai thứ, và cả hai là **khai báo**, không phải hành vi:
`packages/contracts` cho dữ liệu đi qua queue, `packages/schema` cho định nghĩa bảng.
Cái thứ hai là một cái giá đã nhận tường minh: hai service cùng ghi `documents` thì
dùng chung một định nghĩa schema, tức đổi một cột là một breaking change cho cả hai
cùng lúc. Đổi lại là một ranh giới `lint` được thay vì một ranh giới chỉ viết trong
văn bản.

Vì sao `ingest` phải rời khỏi `services/be`: từ 08/10/2026 tới plan 2c nó đúng là
process thứ hai của BE, và **không chỗ nào nói được process nào được làm gì**. Đo được
lúc ấy: `be/config.py` chở hai mươi trường cho một worker chạm năm; luật *API dựng
schema, worker chỉ kiểm* sống trong một docstring; và hai bootstrap gần giống nhau khác
đúng một dòng — trong đó một process đọc `LOG_LEVEL` còn process kia hardcode `INFO`.

Vòng xử lý tài liệu là thứ phá hình dạng cũ, vì **không ai chờ nó**: giáo viên đã rời
màn hình tải lên, và kết quả vẫn phải vào database. Một process đã rời đi thì không có
ai để trả 503 cho. Cho tới ngày ấy BE chỉ **đẩy** job rồi chờ kết quả ngay trong
request; `be/queue.py` không có một handler nào.

`document` và `ingest` **không mở cổng nào**, dù quy ước dưới dành cho `document` số
8100. Kết quả đi về bằng một job trên queue, không bằng một request, nên một cổng ở đó
là một bề mặt không ai canh. Số 8100 vẫn ghi là đã dành, để không ai cấp lại nó.

FE không biết AGENT tồn tại. Mọi thứ FE cần đều đi qua BE.

Một app phục vụ **hai** bề mặt, và chúng tách ở ba chỗ: route (`#/teacher…` rẽ trước mọi request),
actor (`ACTOR` là một record hai khoá, vai khai tại chỗ gọi endpoint), và stylesheet (`tokens.css`
giữ màu dùng chung, `teacher.css` giữ hình khối của giáo viên). Chúng **không** chia sẻ state nào.
Tên class của hai file không được trùng nhau: một class trùng tên không ghi đè mà **cộng vào**, nên
mọi property bản này không nhắc tới thì vẫn do bản kia quyết.

## Đường giao tiếp

```text
FE  --HTTP /api-->  BE  --aiafa:grading-->  Redis  -->  AGENT
                    │ ▲                                   │
                    │ └────────── arq result store ───────┘
                    │
                    ├--aiafa:document--> Redis -->  DOCUMENT
                    │                                   │
                    │        ┌--aiafa:ingest-- Redis <--┘
                    │        ▼
                    │     INGEST ──> Postgres, rồi một tiếng hích trên `documents:<id>`
                    └<────────┘  BE nghe tiếng hích ấy và đẩy xuống FE qua SSE
                    │
                    ├── Postgres (trạng thái bài làm, trạng thái tài liệu)
                    └── MinIO    (byte của tài liệu)   <-- DOCUMENT đọc trực tiếp
```

Hai mũi dưới là **hai queue khác nhau**, không phải một đường hai chiều, và tên chúng
đặt theo **bên tiêu thụ** chứ không theo công việc. Lý do nằm ngay ở dòng trên:
`aiafa:grading` đặt tên theo công việc, rồi nhận thêm sáu task không phải chấm bài, và
nay tên ấy nói dối. Một queue thì chỉ có một worker đứng sau, nên tên nói về bên tiêu
thụ không hết đúng được.

**`DOCUMENT` đọc MinIO trực tiếp, và không đọc Postgres.** Đó là cả lý do byte tài liệu
phải rời khỏi một cột `LargeBinary` ngày 08/10/2026: ba đường thay thế đều phá một luật
đang có. Nó cũng là lý do `DocumentProbeRequested` chở `storage_key` chứ không chở một
hàng id — một service không có credential database thì không tra được hàng nào.

Vì sao `DOCUMENT` không trả kết quả qua arq result store, cách `agent_gateway` đang
làm: `worker.py` đặt `keep_result = JOB_RESULT_TTL_SECONDS`, nên **kết quả job hết
hạn**. Một tài liệu xử lý xong trong mười giây mà không ai đọc trong một giờ là một kết
quả bốc hơi. Một job tự mang dữ liệu đi thì không có hạn sống nào.

**Chấm bài không đi qua hàng đợi.** Nó là một phép so giữa phương án đã chọn và đáp án đúng trong
database của BE, nên nó chạy ngay trong request nộp bài
([ADR-20](../decisions/adr-20-cham-trac-nghiem-thuoc-be.md)). Hệ quả nhìn thấy được: giữa màn làm
bài và màn kết quả không có trạng thái *đang chấm* nào.

**Hàng đợi `aiafa:grading` dành cho bốn việc thật sự cần model**, và cả bốn đều bất đồng bộ vì một lần gọi LLM đủ
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

**Thư viện tài liệu cũng dùng SSE, và đó là kênh đẩy đầu tiên của giáo viên.**
`GET /api/teacher/documents/stream` mở một `text/event-stream` sống suốt thời gian
màn hình mở. Nó tồn tại vì thư viện đổi **sau** lúc tải lên và không lời gọi nào của
màn hình gây ra việc ấy: một tài liệu đi từ *đang xử lý* sang *sẵn sàng* vài giây
sau, hoặc vài phút sau khi queue đang dồn.

**Kênh chỉ hích, không chở dữ liệu.** Mỗi khung chỉ nói *có gì đó đổi*; trình duyệt
nghe xong thì gọi lại `GET /api/teacher/documents`. Lý do là một bài học đã trả giá
một lần ở chuông tiến độ: pub/sub của Redis **không giữ lịch sử**, nên một khung chở
dữ liệu mà mất đi là một chip sai vĩnh viễn, còn một tiếng hích mất đi thì tiếng sau
sửa luôn. Hệ quả bắt buộc: trình duyệt vẫn phải đọc danh sách một lần lúc mở màn
hình — kênh này không bao giờ là nguồn đầu tiên.

**Hai service đứng hai đầu**, không hai process của một service: `ingest` **phát** sau
khi ghi xong kết quả xử lý, `be` **nghe** và đẩy xuống. Một channel cho mỗi **giáo
viên** (`documents:<id>`), vì rail vẽ cả thư viện chứ không vẽ từng tài liệu rời.

Tên channel sống ở `contracts.documents_channel`, và đó là chỗ duy nhất nó được viết
ra. Hai service ấy không import nhau được, nên cái string **là** ranh giới — đúng vai
`GRADE_SUBMISSION_TASK` đã nhận. Đáng một check riêng vì lúc hai bản sao lệch nhau thì
**không có lỗi nào**: `publish` vào một channel không ai nghe thành công y như một
channel có người nghe, và triệu chứng duy nhất là chip thôi tự đổi mặt.

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

Postgres thuộc về BE và chỉ BE — **cả hai process của nó**, API lẫn worker, cùng cầm
một credential và cùng đọc một `models.py`. Ranh giới ở đây là ranh giới **sở hữu**,
không phải ranh giới process. Nó giữ lớp, học sinh, đề, lần làm bài, sổ điểm ba mức, bộ đếm vòng,
từng lượt làm lại kèm đề đã sinh ra, đoạn chat và các báo cáo.
[ADR-21](../decisions/adr-21-trang-thai-bai-lam-la-ben.md) là lý do nó tồn tại: hạn pha 2 do giáo
viên đặt, tính bằng giờ hoặc ngày, nên trạng thái bài làm không thể sống trong một chỗ có TTL một
giờ. `JOB_RESULT_TTL_SECONDS` vẫn còn và vẫn đúng — nó nói về kết quả một job của arq, không nói về
bài làm của học sinh.

MinIO là **kho duy nhất không phải database**, và nó là kho duy nhất **hai** service chạm
tới. Byte của tài liệu giáo viên nằm ở đó; `documents.storage_key` trong Postgres là khoá,
còn bảng thì không giữ một byte nào. Chúng rời khỏi một cột `LargeBinary` ngày 08/10/2026 vì
`services/document` — service đọc tệp — không có credential database, nên nó không với tới
được một cột; ba đường thay thế đều phá một luật đang có.

**BE ghi, `document` đọc, và không có chiều ngược lại.** `document/storage.py` không có `put`,
và sự thiếu vắng ấy là thiết kế chứ không phải việc chưa làm: một `put` thứ hai là một đường
thứ hai để byte vào bucket, và hai đường thì sớm muộn khác nhau ở một chỗ — content type, sơ
đồ khoá, hay thứ tự với hàng trong database.

Việc `document` giữ khoá của MinIO **không** phá dòng *"BE sở hữu mọi database"*, và lý do
đáng nói ra chứ không nên để người đọc tự suy: object storage là nơi **byte** nằm, không phải
nơi **sự thật** nằm. Một tài liệu đã xử lý xong hay chưa thì chỉ `documents.state` trong
Postgres biết, và không service nào ngoài BE đọc được cột ấy. `document` đọc một tệp rồi báo
lại; nó không bao giờ biết câu trả lời của nó đã được ghi hay chưa.

Trong mỗi service, **đúng một module** được import `minio` — `be/storage.py` và
`document/storage.py` — và `tools/check_contract.py` canh cả hai bằng một hàm. Lý do không
phải gọn gàng: SDK là sync còn cả hai bên đều async, nên mỗi lời gọi phải đi qua một thread,
và một chỗ quên không ném gì cả — nó chỉ chặn event loop suốt thời gian một cuốn sách đi qua.
Gom vào một module biến luật *"nhớ bọc thread"* thành luật *"nhớ đừng import"*, và luật thứ
hai thì grep được.

Cùng hàm ấy canh `pymupdf`, và ở `services/document` nó gắt hơn: arq chạy tới `max_jobs` job
đồng thời trên một event loop, nên một lời gọi quên `asyncio.to_thread` giữ cả chín job kia
đứng chờ một cuốn sách được quét xong. Nhà của nó là `document/probe.py`.

AGENT và `document` không nhận credential của bất kỳ database nào, nên **một job phải tự
chứa**: `explain_turn` mang theo cả câu hỏi, phương án, lời giải và lỗi đã soạn chứ không mang
id để tra, và `DocumentProbeRequested` mang `storage_key` chứ không mang một hàng.
`tools/check_contract.py` canh điều này bằng cách quét mọi file Python của **cả hai** service
tìm dấu vết truy cập database.

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

**Deployment Diagram** sẽ cần khi các service được container hoá, và lúc ấy nó là chỗ **duy nhất** nói về nơi chạy. `system-architecture.drawio` cố ý **không** nói: nó vẽ ranh giới quyền quyết định và chìa khoá — những thứ không đổi khi hạ tầng đổi — nên một ranh giới native/container nằm trên đó sẽ sai vào đúng ngày đầu tiên đẩy lên máy chủ. Mục "Năm service, năm process" ở đầu file này và `docs/local-development.md` mới là nơi nói tiến trình nào chạy bằng gì trên máy local.

## Quy ước đặt tên service mới

| Thứ | Quy tắc | Ví dụ |
| --- | --- | --- |
| Tên thư mục | Chữ thường, đặt theo domain chứ không theo tầng | `services/review-queue` |
| Python import package | snake_case của tên thư mục, nằm dưới `src/` | `src/review_queue/` |
| Tên distribution | Tiền tố `aiafa-` để không đụng tên trên PyPI | `aiafa-review-queue` |
| Tiền tố biến môi trường | UPPER_SNAKE | `REVIEW_QUEUE_DB_DSN` |
| Cổng | BE 8000, service mới cộng thêm 100 | `8100`, `8200` |

`be`, `agent` và `fe` là ngoại lệ của quy tắc đặt theo domain vì chúng là tầng chứ không phải domain. Service thứ tư trở đi đặt theo domain — `services/document` là cái đầu tiên, `services/ingest` là cái thứ hai — và cả hai theo đúng bảng trên ở mọi dòng trừ **cổng**: chúng không mở cổng nào, nên 8100 chỉ là một số đã dành.

Mỗi service giữ `pyproject.toml` riêng khai báo đúng dependency của mình, kể cả khi đang dùng chung môi trường. Nhờ vậy lúc tách service ra không phải viết lại gì, chỉ đổi cách cài đặt.
