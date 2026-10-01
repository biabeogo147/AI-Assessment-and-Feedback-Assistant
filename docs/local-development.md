# Local Development

Tài liệu này hướng dẫn dựng môi trường, chạy ba service, demo đủ các nhánh kết quả chấm, và tự chẩn đoán khi có gì đó hỏng.

Mọi lệnh và mọi output trong tài liệu này đều đã được chạy thật trên Windows 11 với PowerShell. Nếu bạn thấy khác, phần [Chẩn đoán sự cố](#chẩn-đoán-sự-cố) ở cuối gần như chắc chắn có câu trả lời.

Kiến trúc và lý do đằng sau các ranh giới nằm trong [Architecture](overview/architecture.md).

## Yêu cầu

| Thứ | Vì sao cần | Ghi chú |
| --- | --- | --- |
| conda với env Python 3.12 | BE và AGENT dùng chung một env | Script mặc định trỏ tới `D:\Anaconda\envs\AI-Assessment-and-Feedback-Assistant` |
| Node 22 và pnpm | FE chạy bằng Vite | |
| Docker Desktop | Chỉ để chạy Redis | Ba service ứng dụng chạy native, không container hoá |

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

`install` chạy năm bước và in ra từng bước một:

```text
==> install contracts
==> install be
==> install agent
==> install dev tooling
==> install frontend
Done. Run '.\dev.ps1 check' to verify the import boundary.
```

Thứ tự này quan trọng: `contracts` phải được cài trước, vì BE và AGENT khai nó là dependency tên `aiafa-contracts`. Cài sau thì pip sẽ đi tìm nó trên PyPI và không thấy.

Xác minh ba package đã vào đúng env:

```powershell
python -c "import be, agent, contracts; print('ok')"
```

Nếu lệnh này lỗi thì mọi bước phía sau đều sẽ hỏng, đừng đi tiếp.

## Chạy hệ thống

Redis và Postgres lên trước. BE và AGENT đều chết lúc khởi động nếu không kết nối được Redis; BE
cũng chết nếu không có Postgres, vì trạng thái bài làm sống ở đó (ADR-21):

```powershell
.\dev.ps1 infra-up
docker compose -f docker-compose.infra.yml ps
```

Đợi tới khi cột `STATUS` ghi `Up ... (healthy)`, đừng đi tiếp khi nó còn `health: starting`.

Rồi mở ba terminal, mỗi terminal một service:

```powershell
.\dev.ps1 be       # terminal 1 - http://localhost:8000
.\dev.ps1 agent    # terminal 2 - worker, không có cổng
.\dev.ps1 fe       # terminal 3 - http://localhost:5173
```

| Cổng | Của ai |
| --- | --- |
| 5173 | FE, Vite dev server |
| 8000 | BE, FastAPI |
| 6379 | Redis, trong Docker |
| 5432 | Postgres, trong Docker |

## Xác minh từng thành phần

Bốn lệnh dưới đây phân biệt được "cả hệ thống hỏng" với "đúng một mắt xích hỏng".

```powershell
docker exec aiafa-redis redis-cli ping          # PONG
curl http://localhost:8000/health               # {"status":"ok"}
curl -o NUL -w "%{http_code}" http://localhost:5173/   # 200
```

Với AGENT, không có endpoint nào để gọi, nên bằng chứng nó sống là dòng log lúc khởi động:

```text
Starting worker for 5 functions: write_draft_question, generate_retry_question, explain_turn, propose_next_step, grade_submission
AGENT worker ready: queue=aiafa:grading redis=redis://127.0.0.1:6379/0
```

Dòng thứ hai in ra tên queue có chủ đích. Nếu BE và AGENT đọc hai tên queue khác nhau thì hệ thống trông y hệt lúc bình thường: BE nhận bài, không báo lỗi gì, và không có gì được chấm.

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

Phía giáo viên, hai quyết định của ADR-01 đi qua đúng hai endpoint, với một header actor khác:

```powershell
$t = @{ "X-Actor" = "teacher:GV-001"; "Content-Type" = "application/json" }
Invoke-RestMethod -Method Post "http://localhost:8000/api/teacher/assessments/<assessment_id>/approve" -Headers $t
Invoke-RestMethod -Method Post "http://localhost:8000/api/teacher/assessments/<assessment_id>/unapprove" -Headers $t
```

Duyệt **tự thu hoạch** các job đã xong trước khi đếm, nên không cần gọi gì khác trước nó: BE không có
worker chạy nền, và nếu endpoint này chỉ đếm thì một đề có đủ câu đã viết xong vẫn đọc ra là "còn
đang soạn" cho tới khi có ai mở một màn hình khác. Hai lời từ chối đáng gặp: `409` khi đề chưa có câu
nào, và `409` khi còn câu đang soạn — đề của giáo viên khác thì trả `404` giống hệt một đề không tồn
tại ([ADR-22](decisions/adr-22-de-co-tac-gia.md)).

Đường chấm cũ (`POST /api/submissions` rồi poll `GET /api/jobs/{id}`) vẫn còn cho tới khi hàng đợi
review của giáo viên được thiết kế. Nó **không** nằm trong luồng lõi nữa; đừng đọc nó như cách hệ
thống chấm bài.

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

BE tạo lại bảng và seed lại dữ liệu mẫu ở lần khởi động sau. Mất dữ liệu dev là có chủ ý ở đây; nếu
một ngày dữ liệu dev đáng giữ thì lúc đó mới cần alembic, và đó là một quyết định có ADR chứ không
phải một lần chữa cháy.

**Port đã bị chiếm.** Kiểm bằng `Get-NetTCPConnection -LocalPort 8000 -State Listen`. Thường là một tiến trình `uvicorn` cũ chưa tắt hẳn từ phiên trước.
