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

`services/agent/src/agent/llm.py` — hai hàm: `chat_models()` trả mọi model đã cấu hình, cái được
thử trước đứng đầu; `with_fallback(shape)` áp một phép biến đổi lên **từng** model rồi mới xâu
chuỗi chúng lại. Không handler nào import SDK của provider, nên đổi OpenAI sang Gemini hay DeepSeek
là đổi hai biến môi trường.

`init_chat_model` đọc `OPENAI_API_KEY` từ `os.environ`, nhưng ta nạp `.env` bằng pydantic-settings
vào một object `Settings` chứ không vào `os.environ`. Nên **phải truyền `api_key=` tường minh** —
đây là chỗ không tự chạy, và là lỗi sẽ mất một buổi để tìm nếu quên.

Vì sao `with_fallback` nhận một hàm thay vì trả thẳng model: `with_fallbacks` trả
`RunnableWithFallbacks`, lớp ấy không mang `with_structured_output`. Gọi vẫn được — `__getattr__`
của nó đọc annotation trả về của method, thấy `Runnable` thì dựng lại cả chuỗi qua đó — nhưng đó là
phản chiếu type hint, và nó gãy xấu khi một annotation không giải được trong module của chính nó:
lỗi hiện ra là `NameError: name 'Runnable' is not defined` ném từ trong `typing`, không nêu tên
method lẫn model. Áp phép biến đổi lên từng model là cùng kết quả khi phép màu chạy, và một lỗi
đọc được khi nó không chạy.

### Hai hình dạng gọi model

| Task | Kiểu gọi | Streaming |
| --- | --- | --- |
| `explain_turn` | văn xuôi | **có** — học sinh đang nhìn |
| `generate_retry_question`, `draft_assessment` | `with_structured_output(GeneratedQuestion)` | không — chạy nền, và structured output không stream có nghĩa |

### Streaming thật

arq trả *một kết quả*, không trả *một dòng chảy*. Nên arq ở lại lo vòng đời job, và thêm một kênh
Redis pub/sub chạy song song:

```
BE sinh stream_id → SUBSCRIBE aiafa:stream:{stream_id} → **rồi mới** enqueue job
AGENT vừa sinh vừa PUBLISH từng mẩu → BE đẩy ra SSE → job trả text đầy đủ → BE lưu ChatMessage
```

**Thứ tự này bắt buộc.** Redis pub/sub không đệm: publish lúc chưa ai subscribe là mẩu chữ mất
vĩnh viễn. Enqueue trước rồi mới subscribe là đưa cho worker cơ hội chạy trước — và nó sẽ chạy
trước, vì arq dequeue gần như tức thì.

Luật thoái lui, phát biểu chặt vì "n giây" nói chung sẽ sinh lỗi hiện chữ hai lần:

- **Chưa mẩu nào ra** sau `stream_first_chunk_timeout_seconds` → thoái về `_sse()`, phát toàn văn.
- **Đã có ít nhất một mẩu ra** → **không bao giờ** phát lại toàn văn nữa. Luồng khựng thì đóng
  stream ở đó; FE vốn `reload()` lịch sử sau khi stream kết thúc, nên câu trả lời đầy đủ hiện ra ở
  lần đọc lại. Thà cụt rồi tự lành còn hơn lặp nửa câu.

SSE vẫn là **chất xúc tác, không phải nguồn sự thật**: text lưu trong DB mới là thật.

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

**Kết quả job chỉ sống một giờ** (`JOB_RESULT_TTL_SECONDS=3600`), còn hạn pha 2 thì hàng giờ tới
hàng ngày ([ADR-21](../../decisions/adr-21-trang-thai-bai-lam-la-ben.md)). Học sinh đóng tab rồi
tối mới quay lại thì kết quả đã bốc hơi, và hàng `pregenerated_items` kẹt ở `pending` **mãi mãi**.
Nên thu hoạch có **ba** ngã chứ không phải hai:

| Job | Làm gì |
| --- | --- |
| xong | ghi vào bảng, `status = 'ready'` |
| chưa xong | để nguyên `pending` |
| **không còn trong Redis** | `status = 'expired'` → **bắn lại job mới** |

Thiếu ngã thứ ba, lưới an toàn "thiếu thì sinh tại chỗ" sẽ âm thầm biến mọi lần quay lại muộn
thành đúng hành vi hôm nay — chờ 20–40 giây — mà không ai biết cơ chế sinh trước đã chết.

Bảng mang ràng buộc `UNIQUE(attempt_id, origin_question_id, round_index)` và bắt `IntegrityError`,
theo đúng lối `uq_one_open_round_per_attempt` đã dùng cho `rounds` (`models.py:256-264`): hai tab
cùng thu hoạch thì cả hai cùng thấy Redis có kết quả, cả hai cùng insert. Kiểm-rồi-ghi không đủ.

### Ba tầng hứng lỗi

| Tầng | Ai | Hỏng kiểu gì | Làm gì |
| --- | --- | --- | --- |
| 1 | AGENT | sai shape, parse lỗi, mạng rớt | thử lại 1 lần → vẫn hỏng thì trả `_VARIANT_BANK` viết tay |
| 2 | BE | phạm ADR-18 / ADR-17 | luật là của BE → gọi lại task, tối đa 2 lần, **kèm đề vừa bị từ chối** |
| 3 | — | hết đường | 503, và **lượt không bị tiêu** vì `RemediationRound` mới `flush()` chứ chưa commit |

Con số tệ nhất, viết ra vì nó dễ quên: AGENT thử tối đa `LLM_MAX_ATTEMPTS` lần trong một job, BE
xin tối đa `1 + _RETRY_ASKS` job, nên **một câu tốn nhiều nhất 3 × 3 = 9 lượt gọi model**, và một
lượt mở lại N câu sai chạy tuần tự là 9N. Không ai nên thấy con số ấy, nhưng ngân sách phải sống
sót qua cái ngày model nhất định không chịu nghe.

Ngân hàng viết tay luôn qua được ADR-18, nên vòng lặp chắc chắn dừng.

Ở tầng 2, lần gọi lại phải **mang theo đề vừa bị từ chối** trong `previous_stems`. Gửi lại y nguyên
payload cũ thì model chỉ còn xác suất ngẫu nhiên để ra kết quả khác; nhét đề bị loại vào đó biến
một lần thử mù thành một lần sửa có hướng, mà `RetryQuestionRequested` đã có sẵn trường ấy.

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

- [x] Plan này, kèm kịch bản manual test bên dưới

### Pha 1 — adapter, chưa đổi hành vi ✅

- [x] Thêm dependency vào `services/agent/pyproject.toml`, cài, kiểm không vỡ import-linter
- [x] `agent/config.py`: `llm_enabled`, `llm_provider`, `llm_model`, `openai_api_key`,
      `google_api_key`, `llm_fallback_provider`, `llm_fallback_model`, `llm_timeout_seconds`
- [x] `be/config.py`: `stream_first_chunk_timeout_seconds` — ngưỡng chờ mẩu chữ đầu trước khi
      thoái về `_sse()`. Mọi ngưỡng khác trong repo đều có tên trong `.env.example`; cái này cũng vậy
- [x] `.env.example` thêm **tên** biến; `.env` nhận khoá thật
- [x] `agent/llm.py`: `chat_models()` + `with_fallback(shape)` — **shape trước, fallback sau**, vì
      `RunnableWithFallbacks` không có `with_structured_output`
- [x] `conftest.py` thay `get_chat_model` bằng model giả — test không được chạm mạng
- [x] Liệt kê model bằng `GET /v1/models` (**miễn phí**), chọn id, ghi vào `.env`
- [x] **Một** lần gọi model thật để xác nhận đường dây

### Pha 2 — trợ lý thật, streaming thật ✅

- [x] `agent/graphs/explain.py`, publish từng mẩu vào `aiafa:stream:{stream_id}`
- [x] `handlers.explain` gọi graph khi `llm_enabled`
- [x] `stream_reply`: **subscribe trước, enqueue sau**; thoái về `_sse()` **chỉ khi chưa mẩu nào ra**
- [x] Đóng subscription khi trình duyệt ngắt giữa chừng — `finally` quanh vòng đọc kênh
- [x] `services/fe/src/api.ts`: nối mọi dòng `data:` của một event bằng `\n`
- [x] Kiểm pub/sub bằng script publish tay — **không cần model**
- [x] Gọi model thật xác nhận chữ hiện dần

### Pha 3 — sinh đề thật ✅

- [x] `agent/graphs/authoring.py`: generate → validate shape → retry (≤2) → lưới `_VARIANT_BANK`
- [x] Prompt **cấm LaTeX và cấm Markdown**, bắt dùng Unicode toán như đề seed (`y = x³ − 3x`). Lần gọi thật ở pha 1
      trả về `\(f(x)=2x^4-3x^3+5x-1\)` — màn hình in chữ thuần nên cái đó hiện ra nguyên dấu gạch
      chéo. Không đọc code nào thấy được điều này; phải chạy mới biết
- [x] `handlers.generate_retry_question` và `handlers.draft_assessment` gọi graph
- [x] BE gọi lại task khi `validate_question`/`validate_retry` đỏ, tối đa 2 lần, **nhét đề vừa bị
      từ chối vào `previous_stems`** để lần thử sau có hướng
- [x] Gọi model thật xác nhận đề sinh ra qua được ADR-18

### Pha 4 — sinh trước ✅

- [x] `models.py`: bảng `pregenerated_items` + `UNIQUE(attempt_id, origin_question_id, round_index)`
- [x] `agent_gateway.py`: `enqueue_task()`, `collect_result()`
- [x] `submit_attempt` nhận `Request`, bắn job sau commit
- [x] `_harvest_pregenerated()` gọi từ `remediation_panel` và `start_round`, ba ngã
      **xong / chưa xong / kết quả đã hết hạn → bắn lại**, bắt `IntegrityError` khi hai tab cùng ghi
- [x] `start_round` ưu tiên hàng `ready`, thiếu thì sinh tại chỗ
- [x] `submit_round` bắn job vòng kế cho câu còn mở
- [x] Chạy một lượt đầy đủ, kiểm bằng SQL rằng hàng chuyển `pending → ready` trong lúc chat

### Pha 5 — manual test

- [x] Chạy kịch bản bên dưới trên trình duyệt, cửa sổ hiện ra để người dùng tự bấm
- [x] Ghi lại: thời gian từ bấm "Làm bài mới" tới lúc thấy đề, và đề có hợp lý không

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

### Decision: trần AGENTS.md 170 → 171

options considered: (a) để quan hệ timeout là lời khuyên trong comment như cũ; (b) thêm kiểm tra tự
động và cắt một dòng khác của `AGENTS.md` cho đủ trần; (c) thêm kiểm tra và nâng trần một dòng.

selected option: (c).

reason: (a) là đúng thứ `AGENTS.md` gọi là *ý tưởng chứ không phải quyết định* — một luật không có
nơi thi hành. Quan hệ này lại không service nào tự kiểm được: trần một lời gọi model nằm ở settings
của AGENT, còn độ kiên nhẫn với một job nằm ở settings của BE, và hai bên không import nhau —
`tools/check_contract.py` tồn tại đúng cho loại kiểm tra ấy. (b) là cắt một luật thật để thoả một
con số, chính điều comment cạnh `AGENTS_MD_MAX_LINES` cảnh báo. (c) dùng cửa thoát mà chính comment
ấy mở sẵn: nâng trần thì phải kèm một decision record nói dòng ấy mua được gì. Nó mua một hàng bất
biến có nơi thi hành tự động.

### Decision: kết quả job hết hạn thì bắn lại, không nâng TTL

options considered: (a) nâng `JOB_RESULT_TTL_SECONDS` lên bằng hạn pha 2; (b) BE chạy một tiến
trình nền thu hoạch ngay khi job xong; (c) thu hoạch lười, và coi "kết quả không còn" là một trạng
thái hợp lệ dẫn tới bắn lại.

selected option: (c).

reason: (a) không có số nào đúng — hạn pha 2 do giáo viên đặt, có thể vài ngày, và giữ mọi kết quả
job trong Redis suốt ngần ấy cho mọi học sinh là dùng cache làm cơ sở dữ liệu, đúng thứ
[ADR-21](../../decisions/adr-21-trang-thai-bai-lam-la-ben.md) vừa gỡ bỏ. (b) thêm một tiến trình
nền vào BE, hôm nay BE chưa có cái nào, chỉ để tiết kiệm một lần sinh lại. (c) không thêm gì: học
sinh quay lại muộn thì đằng nào cũng đi qua màn trợ lý trước khi mở lượt, và chính cú `GET
/remediation` ấy vừa phát hiện kết quả đã bay vừa bắn lại job. Cửa sổ sinh trước được dựng lại
đúng lúc nó lại cần thiết.

### Decision: `.env` neo vào gốc repo, không theo thư mục làm việc

options considered: (a) để `env_file=".env"` tương đối như pydantic-settings mặc định, và ghi vào
tài liệu rằng phải chạy từ gốc; (b) neo đường dẫn vào gốc repo tính từ `__file__`.

selected option: (b).

reason: (a) hỏng không một tiếng động. Một `.env` không tìm thấy **không phải lỗi** — nó là một bộ
mặc định đầy đủ, nên worker khởi động bình thường, `LLM_ENABLED` ở false, khoá rỗng, và triệu chứng
duy nhất là model lặng lẽ không chạy trong khi mọi thứ trông như đang chạy. Tôi đã tự dính đúng bẫy
ấy ở lần xác nhận đầu của pha 2: chạy worker từ `services/agent`, thấy 36 mẩu trong 0,24 giây và
suýt tin đó là streaming thật. Một cấu hình mà đặt sai chỗ thì im lặng không đáng được bảo vệ bằng
một câu trong tài liệu.

## Status

Pha 4 xong, chờ review. **18,1 giây → 0,02 giây.** Nộp bài không chờ gì (0,02s), hai hàng
`pending` hiện ngay, chín thành `ready` trong 12 giây — đúng quãng học sinh đọc màn trợ lý — và lúc
bấm "Làm bài mới" thì đề đã nằm sẵn. Hàng dùng xong bị xoá, bảng về 0.

Đề sinh ra vẫn đúng: tiệm cận ngang của (5x − 7)/(2x + 1) là y = 5/2, và nhiễu B là x = −1/2, tức
đúng cái lỗi học sinh mắc ở câu gốc — nên lượt này thật sự kiểm được em đã sửa chưa.

Pha 3 xong, review đã chạy, ba lỗi đã sửa (kiểm tra timeout liên service đã sai từ lúc pha 3 ra
đời; một biến cấu hình không ai đọc; đề bị từ chối bị lẫn vào danh sách đề học sinh đã thấy). Hai đề sinh ra bằng model thật đều đúng dạng, khác số, **toán đúng**, và
qua sạch ADR-18: 4 phương án, đúng một đáp án đúng, ba nhiễu đều mang nhãn lỗi có nghĩa sư phạm
("quên nhân đôi khi áp dụng AM-GM"), hai cách giải. Nhưng mở lượt mất **18,1 giây** — đúng con số
pha 4 sinh ra để xoá.

Pha 2 xong, review đã chạy, ba lỗi đã sửa: trợ lý trả lời bằng model thật và chữ chảy ra thật — mẩu đầu sau ~2–3 giây,
126 mẩu cho một câu trả lời, nói đúng câu 5, dùng đúng nhãn lỗi đã soạn, viết Unicode không LaTeX.
Ống dẫn pub/sub được chứng minh riêng bằng Redis thật và worker arq thật, không tốn một lượt model.

Pha 0 xong (review đã chạy, sáu phát hiện đã sửa). Pha 1 xong, review đã chạy: không lỗi runtime,
ba việc đã sửa — tên hàm trong mục Kiến trúc cho khớp code, test riêng cho `llm.py`, và quan hệ
timeout chuyển từ lời khuyên thành kiểm tra tự động. Trong lúc viết test thì phát hiện lý do tôi
nêu cho `with_fallback` là **sai**, đã kiểm chứng bằng code và viết lại bằng lý do đúng.

Model cho **manual test trên trình duyệt**: `gpt-4o-mini`, chốt ngày 2026-09-29. Dùng model khác
cho việc ấy phải hỏi trước. Lý do là ngân sách: khoá là khoá lab có hạn mức, và một lượt chạy trọn
kịch bản mười một bước tốn chừng 10–14 lượt gọi — thứ tốn model nhiều nhất trong cả dự án. Một model
rẻ và cố định khiến demo lặp lại được mà không phải canh ví.

Đây là luật cho **lần chạy thử**, không phải lựa chọn model cho sản phẩm; đừng lặng lẽ mang nó vào
mặc định hay vào `.env.example`.

---

**Đóng ngày 2026-09-30** khi dọn `docs/plans/active/`. Người dùng xác nhận đã hoàn thành. Các ô kiểm
chứng máy móc được chạy lại tại thời điểm đóng: `.\dev.ps1 check` xanh 5/5. Những ô cần một người
xác nhận — vòng subagent review, manual test trên trình duyệt — tick theo xác nhận đó, và bằng chứng
là lời xác nhận ấy chứ không phải một lần chạy tôi quan sát được.
