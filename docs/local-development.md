# Local Development

Tài liệu này hướng dẫn dựng môi trường, chạy **năm process** của năm service, demo đủ các nhánh kết quả chấm, và tự chẩn đoán khi có gì đó hỏng.

Mọi lệnh và mọi output trong tài liệu này đều đã được chạy thật trên Windows 11 với PowerShell. Nếu bạn thấy khác, phần [Chẩn đoán sự cố](#chẩn-đoán-sự-cố) ở cuối gần như chắc chắn có câu trả lời.

Kiến trúc và lý do đằng sau các ranh giới nằm trong [Architecture](overview/architecture.md).

## Yêu cầu

| Thứ | Vì sao cần | Ghi chú |
| --- | --- | --- |
| conda với env Python 3.12 | BE, AGENT và DOCUMENT dùng chung một env | Script mặc định trỏ tới `D:\Anaconda\envs\AI-Assessment-and-Feedback-Assistant` |
| Node 22 và pnpm | FE chạy bằng Vite | |
| Docker Desktop | Chạy Redis, Postgres và MinIO | Năm service ứng dụng chạy native, không container hoá |

Nếu conda env của bạn nằm chỗ khác, đặt biến môi trường `AIAFA_PYTHON` trỏ tới `python.exe` của env đó. Bạn cũng cần sửa ba dòng `entry` trong `.pre-commit-config.yaml`, vì chúng dùng đường dẫn tuyệt đối có chủ đích.

## Cài đặt lần đầu

PowerShell chặn script chưa ký, nên **mỗi phiên terminal mới** cần chạy dòng này trước:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Sau đó:

```powershell
copy .env.example .env
.\dev.ps1 install
```

`install` chạy tám bước và in ra từng bước một:

```text
==> install contracts
==> install schema
==> install be
==> install agent
==> install document
==> install ingest
==> install dev tooling
==> install frontend
Done. Run '.\dev.ps1 check' to verify the import boundary.
```

Thứ tự này quan trọng: hai package dùng chung phải được cài trước, vì các service khai chúng là dependency tên `aiafa-contracts` và `aiafa-schema`. Cài sau thì pip sẽ đi tìm chúng trên PyPI và không thấy. Và `schema` đi sau `contracts` vì nó khai `contracts` là dependency của chính nó.

Xác minh sáu package đã vào đúng env:

```powershell
python -c "import be, agent, document, ingest, contracts, schema; print('ok')"
```

Nếu lệnh này lỗi thì mọi bước phía sau đều sẽ hỏng, đừng đi tiếp.

## Chạy hệ thống

Hạ tầng lên trước. BE và AGENT đều chết lúc khởi động nếu không kết nối được Redis; BE cũng chết
nếu không có Postgres, vì trạng thái bài làm sống ở đó (ADR-21), **và** nếu không có MinIO, vì byte
tài liệu sống ở đó. Cái chết thứ ba là cố ý: một BE nhận tài liệu mà không có chỗ cất thì nói dối ở
mỗi lần tải lên, và nói dối muộn — sau khi giáo viên đã đẩy xong cả trăm megabyte.

```powershell
.\dev.ps1 infra-up
docker compose -f docker-compose.infra.yml ps
```

Đợi tới khi cột `STATUS` ghi `Up ... (healthy)`, đừng đi tiếp khi nó còn `health: starting`.
MinIO không có healthcheck nên nó chỉ ghi `Up`: ảnh không mang theo `curl` lẫn `mc`, và phép thử
thật nằm ở chỗ khác — BE gọi `ensure_ready()` lúc khởi động và chết ngay nếu không với tới được.

Rồi mở **năm** terminal. Năm chứ không bốn, vì BE có hai process: một API và một worker.

```powershell
.\dev.ps1 be         # terminal 1 - http://localhost:8000
.\dev.ps1 ingest     # terminal 2 - ghi kết quả xử lý tài liệu, không có cổng
.\dev.ps1 agent      # terminal 3 - worker, không có cổng
.\dev.ps1 document   # terminal 4 - đọc tệp đã tải lên, không có cổng
.\dev.ps1 fe         # terminal 5 - http://localhost:5173
```

**Thiếu `ingest` hoặc `document` thì hệ thống trông y hệt lúc bình thường**, chỉ có mọi
tài liệu đứng ở *đang xử lý* rồi năm phút sau đổi sang *xử lý hỏng*. Không lỗi nào hiện ra,
vì không có gì sai — chỉ là không có ai làm việc.

Ba process còn lại (`be`, `agent`, `fe`) đủ cho mọi thứ **trừ** việc xử lý tài liệu.
`services/document` không có cổng nào, và đó là chủ ý: kết quả của nó đi về bằng một job
trên queue của BE, không bằng một request, nên một cổng ở đó là một bề mặt không ai canh.

| Cổng | Của ai |
| --- | --- |
| 5173 | FE, Vite dev server |
| 8000 | BE, FastAPI |
| 6379 | Redis, trong Docker |
| 5432 | Postgres, trong Docker |
| 9000 | MinIO, API S3, trong Docker |
| 9001 | MinIO, giao diện console, trong Docker |

Cổng **8100** đã dành cho `services/document` theo quy ước *BE + 100* trong
[Architecture](overview/architecture.md), nhưng service ấy chưa mở cổng nào và có thể sẽ
không bao giờ. Ghi ra đây để không ai cấp lại số ấy cho một service khác.

## Xác minh từng thành phần

Bốn lệnh dưới đây phân biệt được "cả hệ thống hỏng" với "đúng một mắt xích hỏng".

```powershell
docker exec aiafa-redis redis-cli ping          # PONG
curl -o NUL -w "%{http_code}" http://127.0.0.1:9000/minio/health/live   # 200, MinIO
curl http://localhost:8000/health               # {"status":"ok"}
curl -o NUL -w "%{http_code}" http://localhost:5173/   # 200
```

Với ba worker, không có endpoint nào để gọi, nên bằng chứng chúng sống là dòng log lúc khởi
động:

```text
Starting worker for 6 functions: write_draft_question, generate_retry_question, explain_turn, name_conversation, propose_next_step, report_plan
AGENT worker ready: queue=aiafa:grading redis=redis://127.0.0.1:6379/0
```

Hai worker kia cũng in ra tên queue của chúng:

```text
INGEST ready: queue=aiafa:ingest redis=redis://127.0.0.1:6379/0
DOCUMENT worker ready: consuming=aiafa:document handing back to=aiafa:ingest redis=redis://127.0.0.1:6379/0
```

Những dòng ấy in ra tên queue có chủ đích. Nếu hai bên đọc hai tên queue khác nhau thì hệ
thống trông y hệt lúc bình thường: job được đẩy vào, không báo lỗi gì, và không có gì chạy.
Dòng của DOCUMENT in **cả hai** tên vì nó vừa tiêu thụ một queue vừa đẩy vào một queue khác,
nên nó có hai cách để lệch.

## Demo

Mở `http://localhost:5173`. Lần chạy đầu, BE tự tạo dữ liệu mẫu đúng bằng câu chuyện trong file
thiết kế: lớp 12A, học sinh **Nguyễn Minh Anh** (`HS2026-1204`), và bài **Kiểm tra 15 phút — Hàm số**
sáu câu, đã phát hành.

Chưa có màn đăng nhập (ADR-10), nên FE tự xưng danh bằng header `X-Actor: student:HS2026-1204`. Đổi
mã trong `ACTOR` của `services/fe/src/api.ts` để vào vai học sinh khác — phân quyền là thật, chỉ cách
chứng minh danh tính là tạm.

Đi hết luồng lõi:

1. **Bài của tôi** — hàng đầu là bài đã phát hành, nút *Bắt đầu*.
2. **Làm bài** — chọn phương án, đồng hồ chạy, *Nộp bài*. Chấm xong ngay: không có màn chờ chấm, vì
   BE chấm bằng một phép so ([ADR-20](decisions/adr-20-cham-trac-nghiem-thuoc-be.md)).
3. **Kết quả** — điểm pha 1 là **sàn**. Hover vào dấu điểm để đọc lý do; câu 0 điểm nói *có thể nâng
   điểm*, câu 0,5 nói *đã làm đúng câu mới cùng dạng*.
4. **Hỏi trợ lý** — panel phải liệt kê mọi câu sai kèm đáp án đúng; *Xem lời giải đầy đủ* mở hộp
   thoại. Trợ lý chào một câu rồi chờ; gõ *"câu 4 em chưa hiểu"* để nó giải thích theo lỗi đã soạn
   sẵn. Chữ hiện dần qua SSE.
5. **Làm bài mới** — hộp cổng đọc lại số câu, số phút và hạn, rồi mở một lượt. Làm đúng thì câu gốc
   lên 0,5; sai ba lượt thì chốt 0.

Muốn thấy ca *sắp hết hạn* — cảnh báo lượt có thể bị **DỪNG** — thì sửa `remediation_deadline` của
hàng trong bảng `publications` về gần hiện tại rồi tải lại màn hỏi trợ lý.

**AGENT là mock.** Nó không gọi model nào: ba handler trả nội dung soạn sẵn, tất định. Cái chạy thật
là ranh giới, hợp đồng và luật chấm điểm.

### Gọi thẳng API, không qua giao diện

```powershell
$h = @{ "X-Actor" = "student:HS2026-1204"; "Content-Type" = "application/json" }
Invoke-RestMethod http://localhost:8000/api/me/assignments -Headers $h
```

Nộp bài rồi đọc bảng điểm:

```powershell
$a = Invoke-RestMethod -Method Post "http://localhost:8000/api/assignments/<assignment_id>/attempts" -Headers $h
Invoke-RestMethod -Method Post "http://localhost:8000/api/attempts/$($a.attempt_id)/submit" -Headers $h
Invoke-RestMethod "http://localhost:8000/api/attempts/$($a.attempt_id)/result" -Headers $h
```

Một điều đáng để ý ở mọi response phía học sinh: **không có** `confidence`, `misconception_code` hay
lý do review ([ADR-08](decisions/adr-08-bon-loai-nghi-ngo.md)), và **không có** `is_correct` trước
khi bài được nộp.

Phía giáo viên có một header actor khác, và năm endpoint:

```powershell
$t = @{ "X-Actor" = "teacher:GV-001"; "Content-Type" = "application/json" }
$a = "<assessment_id>"
Invoke-RestMethod -Method Post "http://localhost:8000/api/teacher/assessments/$a/approve" -Headers $t
Invoke-RestMethod -Method Post "http://localhost:8000/api/teacher/assessments/$a/unapprove" -Headers $t
Invoke-RestMethod "http://localhost:8000/api/teacher/assessments/$a/publish-form" -Headers $t
```

Duyệt **tự thu hoạch** các job đã xong trước khi đếm, nên không cần gọi gì khác trước nó: BE không có
worker chạy nền, và nếu endpoint này chỉ đếm thì một đề có đủ câu đã viết xong vẫn đọc ra là "còn
đang soạn" cho tới khi có ai mở một màn hình khác. Hai lời từ chối đáng gặp: `409` khi đề chưa có câu
nào, và `409` khi còn câu đang soạn — đề của giáo viên khác thì trả `404` giống hệt một đề không tồn
tại ([ADR-22](decisions/adr-22-de-co-tac-gia.md)).

Phát hành nhận **sáu tham số mỗi lớp** và nhiều lớp một lần. **Giờ phải kèm múi giờ** — một giá trị
không có offset bị trả `422`, có chủ ý: BE không có cách nào biết `08:00` là giờ nào, và đoán thì một
giáo viên đặt tiết sáng nhận được tiết chiều.

```powershell
$open = (Get-Date).ToUniversalTime().AddHours(2).ToString("o")
$body = @{ schedules = @(@{
    class_id = "<class_id>"
    opens_at = $open
    closes_at = (Get-Date $open).AddHours(1).ToString("o")
    phase1_minutes = 15
    phase2_minutes_per_question = 5
    remediation_deadline = (Get-Date $open).AddHours(6).ToString("o")
  }); preview = $true } | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Post "http://localhost:8000/api/teacher/assessments/$a/publications" -Headers $t -Body $body
```

`preview = $true` tính hết rồi **không ghi gì** — đó là thứ hộp xác nhận đọc, và nó đi qua đúng đoạn
code mà lần ghi thật đi qua. Đổi thành `$false` để phát hành thật. Một lớp sai giờ **không** làm cả
yêu cầu trượt: nó nhận một dòng `published = false` kèm lý do, và những lớp còn lại vẫn nhận được đề
([ADR-02](decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md)).

Thu hồi một lớp, chỉ được khi **chưa tới giờ mở** của lớp đó:

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/teacher/assessments/$a/publications/<class_id>/withdraw" -Headers $t
```

Sau giờ mở thì `409`. Thu hồi là thu hồi **mềm** — hàng ở lại với `recalled_at` làm sổ sách — nhưng
với học sinh thì lần phát hành ấy chưa từng xảy ra: `GET /api/me/assignments` không còn thấy nó, và
bắt đầu làm bài trả `404`. Đề chỉ về `đã duyệt` khi **không lớp nào còn giữ** nó.

### Thư viện tài liệu

```powershell
$f = @{ "X-Actor" = "teacher:GV-001" }
Invoke-RestMethod -Method Post "http://localhost:8000/api/teacher/documents" -Headers $f -Form @{ file = Get-Item .\sach.pdf }
Invoke-RestMethod "http://localhost:8000/api/teacher/documents" -Headers $f
```

Nhận PDF và văn bản thuần (`.pdf`, `.txt`, `.md`), tối đa 100 MB. `.doc` và `.docx` **không** còn
được nhận: PyMuPDF không đọc được chúng, nên nhận là hứa một thứ bước xử lý chắc chắn phải từ chối.

Kích thước đo bằng `seek`/`tell` trên phần thân đã nhận, không lấy từ `content-length`. Byte đi vào
**MinIO**, không vào database: `documents.storage_key` là khoá, và object nằm ở
`documents/<giáo viên>/<tài liệu>.pdf`. Xem nó bằng console ở <http://127.0.0.1:9001>.

**Tệp được mở ra đọc, nhưng không trong lời gọi `POST`.** Đường ấy cất byte rồi đẩy một job
cho `services/document`; worker đó đọc tệp từ MinIO bằng PyMuPDF và đẩy kết quả về
`aiafa:ingest`, nơi `services/ingest` ghi nó vào database. Nên lời gọi `POST` trả về
`state: "processing"` và `page_count: null`, rồi vài giây sau danh sách nói khác:

```text
state = ready           đọc được chữ, page_count là số trang thật
state = no_text_layer   bản scan, hoặc PDF không có trang nào; fault nói cái nào
state = failed          job đã chết, hoặc không giao được việc; thử tải lại
```

Tệp `.txt` và `.md` mang `page_count: null` **vĩnh viễn**: chúng không có trang, và một số
`0` ở đó thì màn hình sẽ in "0 trang" và giáo viên sẽ tin.

Nội dung tài liệu **vẫn chưa** đi vào prompt của AGENT. Vòng này chỉ đếm chữ và đếm trang;
việc cắt chương và nhồi ngữ cảnh là các plan sau của cùng đợt việc.

### Mở giao diện giáo viên

Dev server của FE phục vụ **cả hai** bề mặt; route quyết định bề mặt nào:

| Route | Màn hình |
| --- | --- |
| `http://localhost:5173/#/` | Danh sách bài của học sinh |
| `http://localhost:5173/#/teacher` | Đoạn chat **đang chạy** của giáo viên |
| `http://localhost:5173/#/teacher/moi` | Màn trống, sau khi bấm *Đoạn chat mới* |
| `http://localhost:5173/#/teacher/chat/{conversation_id}` | Một đoạn chat cụ thể |
| `.../chat/{conversation_id}/de/{assessment_id}` | Chat kèm panel đề |
| `.../chat/{conversation_id}/de/{assessment_id}/phat-hanh` | Panel ở chế độ cài đặt phát hành |

Panel sống **bên trong** đoạn chat đã sinh ra đề (ADR-24). Link cũ `#/teacher/de/{id}` vẫn chạy: nó
hỏi BE xem đề ấy thuộc đoạn nào rồi tự chuyển.

Vai được chọn **tại chỗ khai tên endpoint** trong `api.ts`, không suy từ route đang mở: một request
bay ra giữa lúc chuyển route sẽ mang sai vai, và triệu chứng là một `403` ở rất xa nguyên nhân.

### Database cũ hơn model

`prepare_schema` chỉ `create_all`, và `create_all` **không bao giờ** sửa một bảng đã tồn tại: không
thêm cột, không bỏ constraint. Một `500` kèm *"column ... does not exist"*, hay một `IntegrityError`
bất ngờ, gần như luôn là chuyện này.

Rẻ nhất là dựng một database mới rồi trỏ `DATABASE_URL` sang đó:

```powershell
docker exec aiafa-postgres psql -U aiafa -d postgres -c "CREATE DATABASE aiafa_fe OWNER aiafa;"
$env:DATABASE_URL = "postgresql+asyncpg://aiafa:aiafa@127.0.0.1:5432/aiafa_fe"
```

Muốn giữ dữ liệu đang có thì hai câu dưới đây là phần mà đợt *nhiều đoạn chat* cần:

```sql
ALTER TABLE teacher_conversations DROP CONSTRAINT teacher_conversations_teacher_id_key;
ALTER TABLE teacher_conversations ADD COLUMN title VARCHAR(120) NOT NULL DEFAULT '';
```

Đường chấm cũ (`POST /api/submissions` rồi poll `GET /api/jobs/{id}`) **đã bị gỡ** ngày
09/10/2026, cùng với hàng đợi review của giáo viên -- thứ chưa bao giờ được dựng. Việc chấm chạy
thẳng trong request nộp bài; xem ADR-20.

OpenAPI đầy đủ có sẵn tại `http://localhost:8000/docs`, sinh tự động, không có bản viết tay nào cần
đồng bộ.

## Dừng hệ thống

`Ctrl+C` ở từng terminal, rồi:

```powershell
.\dev.ps1 infra-down
```

Trên Windows, AGENT **không** shutdown graceful: arq đăng ký signal handler bằng cơ chế mà Windows không hỗ trợ, nên `Ctrl+C` cắt ngang job đang chạy thay vì đợi nó xong. Chấp nhận được ở giai đoạn MVP, và nó biến mất khi service được container hoá trên Linux.

## Kiểm tra trước khi commit

```powershell
.\dev.ps1 test        # pytest và vitest
.\dev.ps1 typecheck   # tsc, không build
.\dev.ps1 check       # ruff, hàng rào import, và các check ở tầng repo
.\dev.ps1 fmt         # format và autofix
```

`check` là thứ giữ cho BE và AGENT không import chéo nhau. Hai service dùng chung một conda env nên không có gì chặn được điều đó lúc chạy — `import-linter` là cơ chế duy nhất. Nó cũng chạy tự động qua pre-commit mỗi lần commit.

Cách duy nhất biết hàng rào còn sống là thử phá: thêm `import be` vào `services/agent/src/agent/worker.py`, chạy `.\dev.ps1 check`, xác nhận nó fail, rồi hoàn tác.

## Chẩn đoán sự cố

**`.\dev.ps1` không chạy, báo script bị chặn.** Chạy `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. Cần lặp lại ở mỗi terminal mới.

**`Python interpreter not found at ...`.** conda env của bạn nằm chỗ khác. Đặt `AIAFA_PYTHON` trỏ tới `python.exe` của env đó.

**BE hoặc AGENT chết ngay khi khởi động với `redis.exceptions.TimeoutError`.** Ba khả năng, theo thứ tự hay gặp:

1. Docker Desktop chưa chạy. Mở nó rồi `.\dev.ps1 infra-up`.
2. Redis mới lên và chưa `healthy`. Đợi `docker compose -f docker-compose.infra.yml ps` báo `(healthy)`.
3. `REDIS_URL` trong `.env` đang dùng `localhost`. **Phải dùng `127.0.0.1`.** Trên Windows, `localhost` phân giải ra `::1` trước, và cổng IPv6 mà Docker Desktop publish không nhận kết nối, nên client đợi hết timeout rồi service chết. `Test-NetConnection` của PowerShell che mất lỗi này vì nó tự fallback sang IPv4, nên đừng dùng nó để kết luận.

**Nộp bài xong mà kết quả không bao giờ về.** AGENT không nhận được job. Xem dòng `AGENT worker ready: queue=...` trong log của worker và so với `AGENT_QUEUE_NAME` trong `.env`. Lệch tên queue là lỗi im lặng: không bên nào báo gì cả.

**Chip tài liệu đứng mãi ở *đang xử lý*, rồi đổi sang *xử lý hỏng*.** Không ai đọc tệp. Theo thứ
tự hay gặp:

1. `.\dev.ps1 document` chưa chạy. Đây là ca gần như chắc chắn, vì nó là process mới nhất và dễ
   quên nhất trong năm cái.
2. `.\dev.ps1 ingest` chưa chạy. Lúc này `document` **đã** đọc xong và đã đẩy kết quả về, nhưng
   không ai lấy nó ra khỏi queue. Phân biệt hai ca bằng log của `document`: có dòng
   `probed document=... state=ready` tức nó đã làm xong phần của nó.
3. Tên queue lệch. So `DOCUMENT_QUEUE_NAME` và `INGEST_QUEUE_NAME` trong `.env` với hai dòng
   `... worker ready: queue=...` của hai worker. Lệch tên là lỗi im lặng: không bên nào báo gì.

Trạng thái *xử lý hỏng* ở đây **không** được ghi vào database — cột vẫn là `processing`. Nó được
suy ra lúc đọc, khi hàng đứng lâu hơn `DOCUMENT_STALE_AFTER_SECONDS`, vì một process bị giết thì
không còn ai sống để ghi một giá trị khác. Hệ quả hợp ý: bật `document` lên muộn thì tài liệu cũ
vẫn được xử lý, và lần đọc sau nói đúng.

**FE báo lỗi mạng khi bấm nộp bài.** BE chưa chạy. FE gọi đường tương đối `/api` và Vite proxy sang `http://localhost:8000`; không có BE thì proxy trả lỗi. Không thêm CORS vào BE để chữa — dùng proxy là có chủ đích, để trình duyệt chỉ làm việc với một origin.

**PyCharm gạch đỏ `import pydantic_settings` hoặc `import contracts`.** IDE chưa trỏ đúng interpreter. Chọn `python.exe` trong conda env của project. Code vẫn chạy và test vẫn pass; đây thuần tuý là cấu hình IDE.

**BE báo `UndefinedColumn`, hoặc insert phát hành thứ hai báo `duplicate key`.** Schema trong
Postgres cũ hơn code. `prepare_schema` chỉ gọi `create_all`, và docstring của nó nói thẳng là nó
**không** cứu được một bảng đã đổi hình dạng — nó tạo bảng còn thiếu, không sửa bảng đã có. Hai lần
đổi gần đây rơi vào đúng ca đó: `attempts` có thêm `class_id`, và `publications` đổi sang khoá chính
kép `(assessment_id, class_id)`.

Repo không có alembic, nên cách chữa là dựng lại database:

```powershell
docker compose -f docker-compose.infra.yml down -v   # -v xoá cả volume, tức xoá dữ liệu
.\dev.ps1 infra-up
```

`-v` nay xoá **hai** volume, không phải một: `aiafa-pgdata` và `aiafa-miniodata`. Tức là mọi tài
liệu đã tải lên cũng đi theo. Muốn giữ tài liệu thì dùng `.\dev.ps1 db-reset` — nó dựng lại schema
và seed, **và** dọn sạch bucket, nên hai kho không bao giờ lệch nhau; cái nó không làm là xoá
volume.

BE tạo lại bảng và seed lại dữ liệu mẫu ở lần khởi động sau. Mất dữ liệu dev là có chủ ý ở đây; nếu
một ngày dữ liệu dev đáng giữ thì lúc đó mới cần alembic, và đó là một quyết định có ADR chứ không
phải một lần chữa cháy.

**BE chết lúc khởi động với `StorageUnavailable`.** Không tới được MinIO. Cùng ba khả năng như
Redis ở trên, cộng một cái riêng: `MINIO_ENDPOINT` phải là `host:port` **không kèm scheme** —
`http://127.0.0.1:9000` là sai, `127.0.0.1:9000` mới đúng. SDK nhận scheme qua `MINIO_SECURE`.
Kiểm nhanh bằng `curl -o NUL -w "%{http_code}" http://127.0.0.1:9000/minio/health/live`.

**Tải tài liệu lên trả 503.** BE chạy được nhưng MinIO đã chết **sau** lúc khởi động. Câu trả lời
cố ý là 503 chứ không 500: đây là hạ tầng chưa sẵn sàng, không phải lỗi lập trình, và thử lại là
việc đáng làm. Không có hàng nào được ghi, nên thư viện không hiện một chip trỏ vào hư không.

**Port đã bị chiếm.** Kiểm bằng `Get-NetTCPConnection -LocalPort 8000 -State Listen`. Thường là một tiến trình `uvicorn` cũ chưa tắt hẳn từ phiên trước.
