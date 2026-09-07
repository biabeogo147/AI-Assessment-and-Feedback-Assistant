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

Redis lên trước, vì cả BE lẫn AGENT đều chết lúc khởi động nếu không kết nối được:

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

## Xác minh từng thành phần

Bốn lệnh dưới đây phân biệt được "cả hệ thống hỏng" với "đúng một mắt xích hỏng".

```powershell
docker exec aiafa-redis redis-cli ping          # PONG
curl http://localhost:8000/health               # {"status":"ok"}
curl -o NUL -w "%{http_code}" http://localhost:5173/   # 200
```

Với AGENT, không có endpoint nào để gọi, nên bằng chứng nó sống là dòng log lúc khởi động:

```text
Starting worker for 1 functions: grade_submission
AGENT worker ready: queue=aiafa:grading redis=redis://127.0.0.1:6379/0
```

Dòng thứ hai in ra tên queue có chủ đích. Nếu BE và AGENT đọc hai tên queue khác nhau thì hệ thống trông y hệt lúc bình thường: BE nhận bài, không báo lỗi gì, và không có gì được chấm.

## Demo

Mở `http://localhost:5173`. Câu hỏi mẫu là `1/2 + 1/3`, đáp án đúng là phương án A.

Phần chấm hiện tại là **placeholder có chủ đích**, chưa gọi LLM. Nó được viết sao cho mỗi nhánh Teacher Review đều tái hiện được bằng một thao tác cụ thể. Năm trường hợp dưới đây là kết quả thật:

| Bạn làm gì | score | confidence | Cần review | Lý do |
| --- | --- | --- | --- | --- |
| Chọn A, viết giải thích đầy đủ | 1.0 | 0.92 | không | |
| Chọn A, **để trống** giải thích | 1.0 | 0.55 | có | `low_confidence` |
| Chọn A, giải thích dưới 15 ký tự | 1.0 | 0.60 | có | `answer_explanation_conflict` |
| Chọn A, giải thích chỉ gồm dấu cách | 1.0 | 0.30 | có | `insufficient_evidence` |
| Chọn C, viết giải thích đầy đủ | 0.0 | 0.88 | không | kèm `misconception_code` |

Giá trị thứ tư của `ReviewReason` là `anomaly`, hiện **chưa sinh ra được** vì nó cần lịch sử làm bài của học sinh, mà hệ thống chưa lưu gì. Nó nằm sẵn trong enum để lúc thêm không phải đổi contract.

Chú ý dòng cuối bảng: đáp án sai nhưng **không** cần giáo viên review. Đó không phải lỗi — hệ thống tự tin rằng học sinh sai, và điều cần giáo viên là khi hệ thống *không chắc*, chứ không phải khi học sinh sai.

### Gọi thẳng API, không qua giao diện

Chấm bài chạy bất đồng bộ nên có hai bước: nộp rồi hỏi kết quả.

```powershell
curl -X POST http://localhost:8000/api/submissions `
  -H "Content-Type: application/json" `
  -d '{\"submission_id\":\"sub-1\",\"assessment_id\":\"asm-1\",\"question_id\":\"q-1\",\"student_id\":\"stu-1\",\"selected_option_id\":\"opt-a\",\"student_explanation\":null,\"learning_objective\":\"fraction-addition\"}'
```

Lệnh trên trả về `job_id`. Dùng nó để hỏi kết quả:

```powershell
curl http://localhost:8000/api/jobs/<job_id>
```

Khi chưa xong, `result` là `null` và `status` là `queued` hoặc `in_progress`. Khi xong:

```json
{
  "job_id": "...",
  "status": "complete",
  "result": {
    "submission_id": "sub-1",
    "score": 1.0,
    "confidence": 0.55,
    "misconception_code": null,
    "feedback_text": "Chua co phan giai thich nen he thong chi danh gia duoc dap an.",
    "needs_teacher_review": true,
    "review_reason": "low_confidence"
  }
}
```

`needs_teacher_review` và `review_reason` **không** do AGENT sinh ra. AGENT chỉ báo `score`, `confidence` và `misconception_code`; BE mới so ngưỡng `REVIEW_CONFIDENCE_THRESHOLD` rồi quyết định. Đổi ngưỡng trong `.env` và khởi động lại BE là kết quả cũ đổi theo ngay, vì ngưỡng được áp lúc đọc chứ không lưu kèm.

OpenAPI đầy đủ có sẵn tại `http://localhost:8000/docs`, sinh tự động, không có bản viết tay nào cần đồng bộ.

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

**Port đã bị chiếm.** Kiểm bằng `Get-NetTCPConnection -LocalPort 8000 -State Listen`. Thường là một tiến trình `uvicorn` cũ chưa tắt hẳn từ phiên trước.
