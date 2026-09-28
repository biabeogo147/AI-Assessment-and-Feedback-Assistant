# AGENT chạy trên model thật — baseline

## Goal

Ba task của AGENT sinh nội dung bằng model thật thay vì trả nội dung soạn sẵn, với **OpenAI chính,
Gemini phụ**, qua một lớp adapter để đổi provider không phải sửa handler. Luồng hai pha phải chạy
đầu-cuối trên máy local để kiểm chứng được bằng mắt.

Plan trước ([2026-09-11](2026-09-11-core-two-phase-backend-plan.md)) hứa: *"Đổi sang model thật sau
này không được phép đụng tới một endpoint nào."* Plan này giữ lời hứa đó — không endpoint nào, không
request/response model nào thay đổi hình dạng.

## Scope

**Trong:** lớp adapter provider; ba task chạy qua LangGraph; streaming thật cho chat pha 2; sinh đề
lượt làm lại **trước** thay vì lúc học sinh bấm; ba tầng hứng lỗi để model hỏng không làm gãy luồng.

**Ngoài, có chủ đích:**

- **Không ai kiểm toán học.** `validate_question` vẫn chỉ kiểm cấu trúc ADR-18. Model có thể sinh
  câu mà đáp án đánh dấu đúng lại sai, và BE chấm lượt theo chính cờ đó — nghĩa là **học sinh làm
  đúng có thể bị chấm sai**. Chấp nhận cho baseline, ghi vào `backlog.md`.
- **Không đo (eval).** Chưa dựng bộ đo chất lượng. Baseline này để chạy và nhìn, chưa để kết luận
  model tốt tới đâu.
- Không provider thứ ba. Không đăng nhập. Không bề mặt giáo viên.

## Kiến trúc

### Mối nối duy nhất biết tới provider

`services/agent/src/agent/llm.py` — một hàm `get_chat_model()`. Không handler nào import SDK của
provider, nên đổi OpenAI sang Gemini hay DeepSeek là đổi hai biến môi trường.

`init_chat_model` đọc `OPENAI_API_KEY` từ `os.environ`, nhưng ta nạp `.env` bằng pydantic-settings
vào một object `Settings` chứ không vào `os.environ`. Nên **phải truyền `api_key=` tường minh** —
đây là chỗ không tự chạy, và là lỗi sẽ mất một buổi để tìm nếu quên.

### Hai hình dạng gọi model

| Task | Kiểu gọi | Streaming |
| --- | --- | --- |
| `explain_turn` | văn xuôi | **có** — học sinh đang nhìn |
| `generate_retry_question`, `draft_assessment` | `with_structured_output(GeneratedQuestion)` | không — chạy nền, và structured output không stream có nghĩa |

### Streaming thật

arq trả *một kết quả*, không trả *một dòng chảy*. Nên arq ở lại lo vòng đời job, và thêm một kênh
Redis pub/sub chạy song song:

```
BE sinh stream_id → enqueue job (payload mang stream_id) → SUBSCRIBE aiafa:stream:{stream_id}
AGENT vừa sinh vừa PUBLISH từng mẩu → BE đẩy ra SSE → job trả text đầy đủ → BE lưu ChatMessage
```

Không mẩu nào về trong `n` giây đầu (mock, hoặc provider không stream) thì BE quay lại `_sse()` như
cũ. SSE vẫn là **chất xúc tác, không phải nguồn sự thật**: text lưu trong DB mới là thật.

### Sinh đề trước

Hôm nay `POST /rounds` sinh đề tuần tự ngay trong request. Với model thật đó là 20–40 giây học sinh
nhìn màn hình trắng. Đổi thành: **nộp bài xong là bắn job ngay**, quãng em ngồi hỏi trợ lý chính là
quãng đề được soạn.

```
POST /attempts/{id}/submit        → commit xong, bắn job vòng 1 cho từng câu sai (không chờ)
GET  /attempts/{id}/remediation   → thu hoạch job đã xong vào bảng
POST /attempts/{id}/rounds        → lấy hàng 'ready'; thiếu thì sinh tại chỗ (lưới an toàn)
POST /rounds/{id}/submit          → bắn job vòng kế cho câu còn mở
```

AGENT **không** ghi bảng này — nó không giữ credential database, và `tools/check_contract.py` chặn
điều đó. BE đọc kết quả job từ Redis rồi mới ghi DB.

### Ba tầng hứng lỗi

| Tầng | Ai | Hỏng kiểu gì | Làm gì |
| --- | --- | --- | --- |
| 1 | AGENT | sai shape, parse lỗi, mạng rớt | thử lại 1 lần → vẫn hỏng thì trả `_VARIANT_BANK` viết tay |
| 2 | BE | phạm ADR-18 / ADR-17 | luật là của BE → gọi lại task, tối đa 2 lần |
| 3 | — | hết đường | 503, và **lượt không bị tiêu** vì `RemediationRound` mới `flush()` chứ chưa commit |

Ngân hàng viết tay luôn qua được ADR-18, nên vòng lặp chắc chắn dừng.

## Files

| File | Việc |
| --- | --- |
| `services/agent/pyproject.toml` | `langchain[openai]`, `langchain[google-genai]`, `langgraph` |
| `services/agent/src/agent/llm.py` | **mới** — adapter provider, điểm giả của test |
| `services/agent/src/agent/graphs/explain.py` | **mới** — graph trả lời, có stream |
| `services/agent/src/agent/graphs/authoring.py` | **mới** — graph sinh đề, vòng validate/retry |
| `services/agent/src/agent/config.py` | `llm_*`, `openai_api_key`, `google_api_key` |
| `services/agent/src/agent/handlers.py` | gọi graph khi bật, giữ mock làm lưới |
| `.env.example` | **tên** biến; giá trị thật chỉ nằm trong `.env`, đã gitignore |
| `services/be/src/be/agent_gateway.py` | `enqueue_task()` bắn-không-chờ, `collect_result()` |
| `services/be/src/be/models.py` | bảng `pregenerated_items` |
| `services/be/src/be/student_routes.py` | bốn điểm nối ở trên |
| `services/fe/src/api.ts` | `streamReply` nối nhiều dòng `data:` theo đúng chuẩn SSE |
| `docs/plans/backlog.md` | ghi nợ: chưa ai kiểm toán học, chưa có eval |

Không màn hình nào đổi → không có việc Figma trong đợt này.

## Ordered Tasks

### Pha 0 — kịch bản

- [ ] Plan này, kèm kịch bản manual test bên dưới

### Pha 1 — adapter, chưa đổi hành vi

- [ ] Thêm dependency vào `services/agent/pyproject.toml`, cài, kiểm không vỡ import-linter
- [ ] `agent/config.py`: `llm_enabled`, `llm_provider`, `llm_model`, `openai_api_key`,
      `google_api_key`, `llm_fallback_provider`, `llm_fallback_model`, `llm_timeout_seconds`
- [ ] `.env.example` thêm **tên** biến; `.env` nhận khoá thật
- [ ] `agent/llm.py`: `get_chat_model()` + `with_fallbacks` khi có khoá Gemini
- [ ] `conftest.py` thay `get_chat_model` bằng model giả — test không được chạm mạng
- [ ] Liệt kê model bằng `GET /v1/models` (**miễn phí**), chọn id, ghi vào `.env`
- [ ] **Một** lần gọi model thật để xác nhận đường dây

### Pha 2 — trợ lý thật, streaming thật

- [ ] `agent/graphs/explain.py`, publish từng mẩu vào `aiafa:stream:{stream_id}`
- [ ] `handlers.explain` gọi graph khi `llm_enabled`
- [ ] `stream_reply` subscribe kênh, đẩy SSE, giữ `_sse()` làm lưới
- [ ] `services/fe/src/api.ts`: nối mọi dòng `data:` của một event bằng `\n`
- [ ] Kiểm pub/sub bằng script publish tay — **không cần model**
- [ ] Gọi model thật xác nhận chữ hiện dần

### Pha 3 — sinh đề thật

- [ ] `agent/graphs/authoring.py`: generate → validate shape → retry (≤2) → lưới `_VARIANT_BANK`
- [ ] `handlers.generate_retry_question` và `handlers.draft_assessment` gọi graph
- [ ] BE gọi lại task khi `validate_question`/`validate_retry` đỏ, tối đa 2 lần
- [ ] Gọi model thật xác nhận đề sinh ra qua được ADR-18

### Pha 4 — sinh trước

- [ ] `models.py`: bảng `pregenerated_items`
- [ ] `agent_gateway.py`: `enqueue_task()`, `collect_result()`
- [ ] `submit_attempt` nhận `Request`, bắn job sau commit
- [ ] `_harvest_pregenerated()` gọi từ `remediation_panel` và `start_round`
- [ ] `start_round` ưu tiên hàng `ready`, thiếu thì sinh tại chỗ
- [ ] `submit_round` bắn job vòng kế cho câu còn mở
- [ ] Chạy một lượt đầy đủ, kiểm bằng SQL rằng hàng chuyển `pending → ready` trong lúc chat

### Pha 5 — manual test

- [ ] Chạy kịch bản bên dưới trên trình duyệt, cửa sổ hiện ra để người dùng tự bấm
- [ ] Ghi lại: thời gian từ bấm "Làm bài mới" tới lúc thấy đề, và đề có hợp lý không

**Sau mỗi pha: `dev.ps1 check` + pytest + vitest xanh → gọi 1 subagent review → sửa hết phát hiện →
mới được sang pha kế.**

## Kịch bản manual test

Viết trước để lần chạy nào cũng đi đúng các bước này. Đề model sinh ra khác nhau mỗi lần là chấp
nhận được; cái phải giống nhau là **các bước và điều cần thấy**.

| # | Làm gì | Phải thấy gì |
| --- | --- | --- |
| 1 | Reset DB, mở `#/`, bấm **Bắt đầu** | một bài `đang-mở` |
| 2 | Đúng câu 1–4, **sai câu 5 và 6** (chọn B), **Nộp bài** | — |
| 3 | Màn kết quả | điểm sàn 4,0 · còn 2 câu cần chữa. *Job sinh đề đã bắn — kiểm ở log AGENT, không phải trên màn* |
| 4 | **Hỏi trợ lý và làm lại dạng bài sai** | câu chào **hiện dần từng mẩu**, không đứng im rồi hiện một cục |
| 5 | Gõ `câu 5 em chưa hiểu vì sao sai` | trợ lý nói về **câu 5**, không phải câu 1 |
| 6 | Gõ `vậy còn câu 6 thì sao ạ` | thẻ **Câu 6** sáng lên "đang hỏi" |
| 7 | **Xem lời giải đầy đủ** ở thẻ câu 5 | dialog có ≥2 cách giải, mỗi nhiễu có nhãn lỗi |
| 8 | **Làm bài mới** → cổng → **Làm bài mới** | màn lượt mở **gần như tức thì**, và **đề khác đề cũ** dù cùng dạng |
| 9 | Câu 5 chọn đúng, câu 6 chọn sai, **Nộp bài** | — |
| 10 | Màn kết quả | câu 5 = 0,5đ kèm dòng "Lượt làm lại · 1 · đúng"; câu 6 = 0đ, còn 2 vòng |
| 11 | Lặp 8–9 cho câu 6 tới hết 3 vòng | bài `đã-hoàn-thành`, chat khoá, vẫn đọc lại được |

## Validation Checks

- `.\dev.ps1 check` — ruff, import-linter, bốn kiểm tra repo
- `pytest services -q` — không test nào chạm mạng
- `pnpm -C services/fe exec vitest run` và `tsc --noEmit`
- Pub/sub kiểm bằng script publish tay, không tốn một lần gọi model nào
- Sinh trước kiểm bằng SQL trên `pregenerated_items`, không kiểm bằng cảm giác nhanh chậm

## Decision Records

### Decision: streaming đi qua Redis pub/sub, không đổi arq

options considered: (a) kênh pub/sub song song với arq; (b) cho AGENT một mặt HTTP để BE proxy;
(c) BE gọi thẳng model.

selected option: (a).

reason: (c) phá ADR-06 — quyết định và bằng chứng lẫn vào nhau, và BE sẽ giữ khoá model. (b) thêm
một cổng mạng, một cách triển khai, một chỗ hỏng, chỉ để chở chữ. (a) dùng đúng Redis đang có, giữ
arq làm nguồn sự thật cho vòng đời job, và khi kênh im thì hệ thống tự thoái về hành vi hôm nay.

### Decision: FE sửa parser SSE thay vì bịa định dạng riêng

options considered: (a) mã hoá mẩu chữ thành JSON trong `data:`; (b) thay xuống dòng bằng dấu cách;
(c) dùng `data:` nhiều dòng theo đúng chuẩn SSE và sửa parser FE.

selected option: (c).

reason: mẩu chữ model trả về có xuống dòng, mà một dòng `data:` thì không chứa được. (b) làm mất
ngắt đoạn trong câu trả lời. (a) là định dạng riêng, phải nhớ. (c) là điều chuẩn SSE đã quy định
sẵn — FE đang cài thiếu chứ không phải BE đang phá. Sửa chỗ thiếu rẻ hơn dựng quy ước mới.

### Decision: sinh đề trước, không sinh lúc bấm

options considered: (a) giữ sinh trong request, chỉ song song hoá và nâng timeout; (b) sinh trước
từ lúc nộp bài, lưu vào bảng.

selected option: (b).

reason: (a) vẫn để học sinh chờ, chỉ chờ ít hơn, và cái trần là thời gian model — không tối ưu
được. (b) đặt việc sinh vào đúng quãng học sinh bận chuyện khác, và cái quãng đó có thật vì ADR-14
bắt em đi qua phần hỏi trợ lý trước khi mở lượt. Đường sinh tại chỗ vẫn giữ làm lưới, nên (b)
không xoá (a) mà bọc lên trên nó.

## Status

Pha 0 đang làm.
