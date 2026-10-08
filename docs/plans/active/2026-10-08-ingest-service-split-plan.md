# Plan 2c — `services/ingest`, service thứ năm

## Context

Plan 2a cho BE một process thứ hai và **không chỗ nào nói process nào được làm gì**. Bốn chỗ mờ
đã đo ngày 08/10/2026 và ghi ở [file đợt việc](2026-10-07-doc-pdf-vao-ngu-canh-plan.md); plan này
không đo lại chúng. Hai phép đo mới, cùng ngày:

- **Ranh giới đã có trong thực tế.** Process worker kéo theo đúng **7** module `be.*`
  (`worker ingest config db models queue document_events`); process API kéo **23**. Không một
  module quyết định nào — `drafting`, `review_policy`, `assessment_state`, `teacher_tools`,
  `agent_gateway` — nằm trong đường của worker. Thiếu đúng cái lưới.
- **Một lỗi thật, hệ quả trực tiếp của chỗ mờ #3.** `be/worker.py` hardcode
  `logging.basicConfig(level=logging.INFO)`, nên `LOG_LEVEL` chỉ có tác dụng ở **một** trong hai
  process. Bản ghi cũ nói worker *đọc* `log_level` — nó không.

Người dùng chốt 08/10/2026: **tách thật thành `services/ingest`**, `models.py` vào
**`packages/schema`** dùng chung.

**Kết quả mong đợi:** `services/ingest` là service thứ năm, chạy bằng `.\dev.ps1 ingest`, giữ
credential database, và **không import được `be`** — `lint-imports` đỏ nếu thử. Chip tài liệu vẫn
đổi mặt đúng như plan 2b để lại, không một hành vi nào đổi.

## Scope

**Trong:** `packages/schema`; `services/ingest`; dọn `be` còn một process; `documents_channel` sang
`contracts`; hai cái lưới; lỗi `log_level`; đổi tên queue; `dev.ps1`; tài liệu.

**Ngoài:** mục lục/chương/chunk (plan 3); Jev (plan 4); nội dung vào prompt (plan 5). **Không một
hành vi nào đổi** — đây là plan hình dạng, không phải plan tính năng.

## Decision Records

### Decision: tách `services/ingest`, và cái giá đã nhận

**options considered:** (a) **tách thành service riêng** · (b) một service, ranh giới cắm lưới ·
(c) để nguyên, ghi backlog.

**selected option:** (a). Người dùng chốt 08/10/2026.

**Một lập luận đã bị rút, ghi lại để đừng ai viện lại.** Bản đầu chống (a) bằng câu *"một service
thứ hai giữ credential Postgres sẽ giết dòng `AGENTS.md` — `services/be` sở hữu mọi database"*.
Người dùng bác: **một worker giữ credential database là hợp lệ.** Cái làm `agent` với `document`
thành service đọc-và-báo là chúng **không giữ credential nào**, chứ không phải việc chúng chạy
process riêng.

**Cái giá chưa bị bác, nay nhận tường minh:** hai service cùng ghi `documents` thì dùng chung một
định nghĩa schema, và đó là hình dạng distributed monolith — đổi một cột của `attempts` là một
breaking change cho một service không biết `attempts` là gì. Người dùng chọn trả giá ấy để lấy
một ranh giới **lint được** thay vì một ranh giới chỉ viết trong văn bản.

**Thứ mua được, và nó mạnh hơn cổng đã hẹn:** cổng của 2c trong file đợt việc là *"một check đỏ
khi process worker chạm một luật nghiệp vụ"*. Tách service làm cái đó thành `independence` của
import-linter: `ingest` không import được **một dòng nào** của `be`, nên không cần liệt kê module
nghiệp vụ nào — danh sách không bao giờ lỗi thời vì không có danh sách.

(c) bị bác vì plan 3 thêm một handler nữa vào đúng chỗ đang mờ.

### Decision: `packages/schema` sở hữu khai báo schema **và câu lệnh về schema**, không gì khác

`packages/contracts/AGENTS.md` cảnh báo đúng chỗ: *"anything with behaviour placed here becomes
shared behaviour that neither service owns."* Nên ranh giới package mới vạch bằng số:

| Vào `packages/schema` | Ở lại mỗi service |
|---|---|
| `models.py` — 743 dòng, 22 bảng, `Base` | `create_engine` — đọc `Settings` của **chính** service |
| `prepare_schema`, `check_schema`, `reset_schema`, `SchemaDrifted` | `bind_sessions`, `session_scope`, `get_session` |

Ba hàm kia là **câu lệnh về schema**: `check_schema` lặp trên `Base.metadata.tables`, nên nó
không nói được gì nếu không ở cùng chỗ với metadata, và nhân đôi 30 dòng ấy vào hai service là
nhân đôi đúng cái thứ phải không bao giờ lệch. Engine và session thì là **hạ tầng process**, khác
nhau theo config từng service.

`tests/test_schema_guard.py` **đi theo ba hàm ấy** sang `packages/schema/tests/`: nó test đúng
chúng, và một test nằm cách xa thứ nó canh thì không ai sửa nó khi thứ ấy đổi.

Distribution tên `aiafa-schema`, package import tên `schema` — cùng khuôn `aiafa-contracts` /
`contracts`, và cùng lý do đã ghi ở `packages/contracts/pyproject.toml`: một cái tên trơ đụng với
project đã có trên PyPI. Đã kiểm: `schema`, `aiafa_schema`, `ingest` chưa có trong env.

`schema` được import `contracts` (`models.py` dùng `DocumentState`), **không** được import một
service nào.

### Decision: `prepare_schema` chỉ được gọi ở `be/main.py`

Cổng thứ hai mà file đợt việc hẹn, và nay nó cần thiết **hơn** trước: `prepare_schema` vào một
package dùng chung nên nó thành thứ `ingest` import được. Luật: process API sở hữu việc **dựng**
schema; `ingest` chỉ `check_schema` rồi chết ngay nếu lệch.

Vì sao không để `ingest` dựng luôn: `create_all` không bao giờ `ALTER`, nên hai process cùng dựng
là hai process cùng tin mình đúng về một schema chỉ một bên nhìn đủ. Và `ingest` khởi động được
**trước** API, nên nó sẽ dựng theo bản metadata nó đang có — một lần lệch phiên bản là một schema
sai mà không ai gọi là lỗi.

### Decision: tên channel vào `contracts`, `announce` theo người phát

`document_events.py` chở ba thứ, nay chúng thuộc ba chỗ:

| Thứ | Về đâu | Vì sao |
|---|---|---|
| `documents_channel(teacher_id)` | `contracts/documents.py` | Hai service phải nói **cùng một string**. Đúng vai `contracts` tự khai cho `GRADE_SUBMISSION_TASK`: *"that constant is the boundary, not a convenience"* |
| `announce` | `services/ingest` | Bên **phát** |
| `open_changes` | `services/be` | Bên **nghe** |

### Decision: `BE_QUEUE_NAME` → `INGEST_QUEUE_NAME`, `aiafa:be` → `aiafa:ingest`

**reason:** luật đặt tên queue của repo nằm ngay trong `be/config.py`: *"Đặt tên theo **bên tiêu
thụ** chứ không theo công việc, vì `aiafa:grading` đã mục ruỗng đúng theo cách kia: tên nói về
chấm bài và nay chở bảy task, sáu cái không phải chấm bài."* Bên tiêu thụ nay là `ingest`, nên
`BE_QUEUE_NAME` thành đúng loại tên mà luật ấy cấm — một biến `BE_` đi tới một service không tên
`be`, tức đúng loại chỗ mờ plan này tồn tại để dọn.

Giá: `.env.example`, `.env`, `services/document` (ba chỗ), `local-development.md`,
`document/AGENTS.md`. Người dùng chốt 08/10/2026.

### Decision: nâng trần `AGENTS.md` 182 → 186

Comment ở `check_contract.py:91` nói cái trần tồn tại để mỗi dòng mới **trả giá** bằng một lần
sửa hằng số kèm một decision record — record này là cái giá ấy. Bốn dòng, từng dòng nói nó mua
gì: hai dòng ownership (`services/ingest`, `packages/schema`) và hai dòng invariant (ranh giới
`ingest`↔`be`, `prepare_schema` một chỗ).

`CHILD_AGENTS_MD_MAX_LINES` **không** nâng: hai file con mới mỗi file tự ở dưới 25, và
`services/be/AGENTS.md` đang đầy 25/25 thì **giảm** — dòng *"in both of its processes"* chết theo
plan này.

### Decision: `log_level` sửa trong plan này

Nó đúng là *một process làm khác process kia mà không chỗ nào nói ra* — chính cái bệnh 2c tồn tại
để chữa. `ingest` cấu hình **cây logger của chính nó** (`ingest.*`) từ `Settings.log_level` của
chính nó, cùng hình dạng `_hear_our_own_loggers` ở `be/main.py` và cùng lý do đã ghi ở đó: không
dùng `basicConfig`, vì hàm ấy im lặng thành một lời gọi rỗng ở bất cứ process nào đã có handler
trên root. Người dùng chốt 08/10/2026.

## Files

| File | Việc |
| --- | --- |
| `packages/schema/` **(mới)** | `pyproject.toml` (`aiafa-schema`); `src/schema/models.py` chuyển nguyên từ `be/models.py`; `src/schema/ddl.py` nhận ba hàm + `SchemaDrifted`; `tests/test_schema_guard.py`; `AGENTS.md` |
| `services/ingest/` **(mới)** | `pyproject.toml`; `config.py` (**bốn** trường); `db.py` (engine + session); `worker.py`; `handlers.py`; `events.py`; `AGENTS.md`; `tests/` |
| `services/be/src/be/models.py` | **xoá** |
| 27 chỗ import `be.models` | 12 file nguồn + 15 file test đổi sang `schema` |
| `services/be/src/be/db.py` | bỏ ba hàm schema, giữ engine/session |
| `be/worker.py`, `be/ingest.py` | **xoá** |
| `be/document_events.py` | còn `open_changes` |
| `be/config.py` | `be_queue_name` đi |
| `packages/contracts/src/contracts/documents.py` | `documents_channel` |
| `pyproject.toml` (gốc) | `ruff.src`, `pytest.testpaths`, `importlinter.root_packages`, hai contract mới |
| `tools/check_contract.py` | `CHILD_AGENTS_FILES` +2; cap 182→186; check `prepare_schema`; check tên channel |
| `dev.ps1` | `be-worker` → `ingest`; install; help |
| `.env.example`, `.env` | `BE_QUEUE_NAME` → `INGEST_QUEUE_NAME` |
| `services/document/` | ba chỗ đọc tên queue + `AGENTS.md` |
| `AGENTS.md` | 2 dòng ownership + 2 dòng invariant |
| `services/be/AGENTS.md` | BE là một process |
| `docs/overview/architecture.md` | service thứ năm, và vì sao nó giữ credential trong khi `agent`/`document` thì không |
| `docs/overview/data-model.md` | nguồn sự thật của schema đổi đường |
| `docs/local-development.md` | tên queue, và process thứ sáu |
| 6 ADR (`adr-01`, `adr-02` ×3, `adr-04`, `adr-13`, `adr-22`, `adr-24`) | dòng *"ở đâu"* trỏ `be/models.py` → `packages/schema` |

`docs/plans/completed/` **không sửa**: nó là lịch sử, và một lịch sử bị sửa cho khớp hiện tại thì
không còn là lịch sử.

## Ordered Tasks

Bốn pha. **Xong mỗi pha, một subagent đọc lại diff của pha ấy** trước khi đi tiếp — người dùng
yêu cầu 08/10/2026, và lý do là một pha sai mà chỉ thấy ở cuối plan thì ba pha sau đã đứng lên
nó rồi.

### Pha A — `packages/schema`, và nó phải là một lần chuyển rỗng

- [x] **1.** Chuyển `models.py` + ba hàm schema + `SchemaDrifted` + `test_schema_guard.py`. Đổi
      **29** chỗ import (đo lúc làm: 28 dòng `from be.models`, cộng các dòng lấy ba hàm schema từ
      `be.db`). `pyproject.toml` gốc. `pip install -e`.

**Cổng pha A:** `check` 18/18 và cả 461 test xanh, **không một hành vi nào đổi**. Dừng ở đây nếu
chưa xanh — ba pha sau đều đứng trên bước này.

**Đã đạt:** `check` 18/18 · `lint-imports` 3 contract, 0 broken · `pytest` **461**, đúng con số
trước pha A · `ruff` sạch. `models.py` là rename thuần, và bốn thứ chuyển sang `ddl.py` khớp
**từng byte** với bản trong `git show HEAD`.

**Bốn lỗi review tìm ra, và không cổng nào trong số trên bắt được chúng.** Pha A tự khai là "một
lần chuyển rỗng", nên đây là bốn chỗ nó **đã đổi một hành vi** mà vẫn xanh:

1. **`.\dev.ps1 install` thành một lệnh hỏng.** Pha A thêm `aiafa-schema` vào dependency của BE
   nhưng không thêm bước cài nó, nên trên một env sạch `install be` đi tìm `aiafa-schema` trên
   PyPI và chết — đúng cái bẫy mà comment ngay trên dòng ấy nói là lý do `contracts` phải đi
   trước. Env lúc đo xanh **chỉ vì** package đã được cài bằng tay.
2. **Cổng "461 test xanh" không đi qua đường resolve mới.** `aiafa_be.egg-info/requires.txt`
   chưa có `aiafa-schema`, tức BE chưa được cài lại sau khi pyproject đổi. Đã cài lại rồi đo lại.
3. **`packages/schema` khai thiếu extra `[asyncio]` của SQLAlchemy.** `greenlet` không phải
   driver — nó là thứ `ddl.py` cần để chạy nổi một dòng. Thiếu nó thì package cài một mình là
   import vào là nổ, và chỉ nổ ở máy nào chưa có package khác kéo `greenlet` về.
4. **Hai comment ở `be/storage.py` trỏ vào chỗ không còn gì.** Một trong hai là **tiền lệ được
   viện ra** để biện minh cho `InMemoryStore` ở module production: *"nhánh `else` sqlite trong
   `db.reset_schema` cũng chỉ có test đi qua, và nó nằm trong `db.py`"*. Pha A dọn sạch đúng loại
   code ấy khỏi `db.py`, nên lập luận kia mất chỗ đứng mà không ai kêu.

Bài học ghi lại: **ba cổng tự động đều đo code đang chạy, không cổng nào đo đường cài đặt.**
Một package mới thì cái đầu tiên hỏng là `install`, và nó hỏng ở máy người khác chứ không ở máy
mình — chỗ không cổng nào đứng.

**Hai đột biến, cả hai đỏ:** sửa một `assert` trong `test_schema_guard.py` → `pytest
packages/schema/tests` đỏ, chứng minh cổng ấy sống thật chứ không chỉ được collect. Cho `ddl.py`
import `be.config` → `lint-imports` BROKEN.

### Pha B — `services/ingest` sinh ra, `be` còn một process

- [x] **2.** `services/ingest` theo khuôn `services/document`: cùng hình dạng thư mục, cùng cách
      khai dependency, cùng `_ENV_FILE = parents[4]`. Chuyển `worker.py`, `ingest.py`, `announce`
      và hai file test sang.
- [x] **3.** Dọn `be`: xoá bốn thứ đã đi, `be/config.py` bỏ `be_queue_name`.
- [x] **4.** `documents_channel` sang `contracts`, hai bên import từ đó.
- [x] **5.** `log_level` cho `ingest` — cây logger của chính nó.

**Cổng pha B:** `grep -rn "import be" services/ingest` ra rỗng; `.\dev.ps1 ingest` chạy lên và
log nói đúng queue, đúng database; test xanh.

**Đã đạt.** `check` 18/18 · `lint-imports` **4 service độc lập**, 0 broken · `pytest` **465** ·
`grep` ra rỗng. (Con số test là **461 lúc đo lần đầu**, đúng bằng trước pha B vì test chỉ đổi chỗ;
nó thành 465 sau khi review bắt pha B viết thêm bốn test còn thiếu — xem dưới. Bản đầu của mục
này ghi 461 và để nguyên, tức một con số đã chết ngay trong chính đoạn văn khai nó.) Hai phép đo sống:

- **Chuỗi đi qua hai service rời:** hai tiếng hích ở **0,72 s** (plan 2b đo 0,77 s trên một
  service), rồi đọc lại ra `ready` 29 trang và `no_text_layer`. Hành vi không đổi.
- **`ingest` là một process rời thật:** tắt nó, tải một tệp lên → tài liệu đứng ở `processing`
  suốt 8 giây; bật lại → **job vẫn được xử lý**, ra `ready` 29 trang. Một worker nhúng trong
  `lifespan` của uvicorn không làm được điều ấy.

**Việc 7 (đổi tên queue) chuyển từ pha C lên pha B.** Lý do: một trường config không sinh ra
được dưới cái tên plan đã quyết định bỏ, và để `ingest_queue_name` đọc `BE_QUEUE_NAME` trong
một pha rồi đổi ở pha sau là viết một dòng sai có hẹn.

**Bảy lỗi review tìm ra.** Ba loại, và loại thứ ba là loại đáng kể nhất:

*Loại 1 — tài liệu vận hành nói sai ngay giữa hai pha.* `dev.ps1` đổi ở pha B nhưng
`local-development.md` vẫn dạy `.\dev.ps1 be-worker`, một lệnh mà `ValidateSet` nay **từ chối**;
cộng sáu chỗ khác (`aiafa:be`, `BE_QUEUE_NAME`, hai dòng log mẫu). Và khối `install` — thứ pha A
vừa sửa — lại sai số ngay: pha B thêm bước thứ tám mà không sửa chữ "bảy".

*Loại 2 — bốn docstring trong code production trỏ vào file đã xoá*, đúng lỗi số 4 của pha A lặp
lại nguyên dạng: `be/queue.py`, `be/teacher_documents.py` (ba chỗ). Cộng dòng
`services/be/AGENTS.md` khai *"in both of its processes"* — một dòng **contract** nói sai về code
hiện tại — và một câu ở `AGENTS.md` gốc nói "five child AGENTS.md" trong khi tuple nay có bảy.

*Loại 3 — cái lưới cho chính thứ pha B vừa chữa thì không tồn tại.* Lỗi `log_level` được sửa mà
không có test nào: xoá dòng gọi `_hear_our_own_loggers`, hay thay nó bằng `basicConfig`, hay bỏ
luôn `await check_schema(engine)` — **cả ba vẫn 461 xanh**. Bảng đột biến của plan hẹn hai cái
đỏ ở "test của `ingest`"; hai cái ấy chưa được viết. Đã viết `services/ingest/tests/test_worker.py`
theo khuôn `be/tests/test_logging_config.py`, gồm test đọc **cây cú pháp** để chứng minh có người
**gọi** hàm ấy và gọi kèm `Settings.log_level` — bốn test, và bốn đột biến trên nay đỏ đúng chỗ.

Và một lỗi thứ tám, không thuộc ba loại: cổng chống orphan `.env.example` **chưa biết service thứ
năm tồn tại**. Nó đang xanh **bằng sự tình cờ** — `INGEST_QUEUE_NAME` đi qua được chỉ vì
`services/document` cũng đọc đúng tên trường ấy. Ngày `document` thôi cần nó, biến ấy thành mồ
côi thật mà cổng vẫn im. Đã nối `IngestSettings` vào.

**Bài học, và nó là bài học của cả hai pha:** cổng tự động đo **code đang chạy**. Không cổng nào
đo đường cài đặt, tài liệu vận hành, hay một comment biện minh đã mất chỗ đứng — và một pha
refactor thì sinh ra đúng ba loại rác ấy.

### Pha C — hai cái lưới, và tên gọi

- [x] **6.** Contract import-linter: bốn service độc lập, `schema` không import service nào.
      Check `prepare_schema` một chỗ. Check tên channel một chỗ.
- [x] **7.** `BE_QUEUE_NAME` → `INGEST_QUEUE_NAME` khắp nơi. `dev.ps1`: `be-worker` → `ingest`.

**Cổng pha C:** sáu đột biến ở bảng dưới, mỗi cái đỏ đúng chỗ.

**Đã đạt.** `check` nay **20/20** (hai check mới) · `lint-imports` 3 contract, 0 broken ·
`pytest` **465** · `ruff` sạch.

Hai check mới, và mỗi cái canh một thứ không cổng cũ nào thấy:

- **`check_one_process_builds_the_schema_and_the_rest_only_check_it`.** Luật này trước plan 2c
  **không cần** lưới: `prepare_schema` nằm trong `be/db.py`, một module chỉ `services/be` import
  được, nên ranh giới service đã trả lời hộ câu "ai được dựng schema". Nay nó ở package dùng
  chung, nên câu ấy phải tự có người canh.
- **`check_both_sides_of_the_document_channel_read_its_name_from_contracts`.** Hai service không
  import nhau được, nên cái string là ranh giới. Đáng một lưới riêng vì **lúc nó lệch thì không
  có lỗi nào**: `publish` vào một channel không ai nghe thành công y như một channel có người
  nghe, và triệu chứng duy nhất là chip thôi tự đổi mặt — một màn hình trông như đang chạy đúng.

Cả hai bỏ qua `tests/`, và đó không phải lỗ hổng: một test khẳng định `documents_channel("gv-1")`
ra chuỗi nào thì **phải** viết chuỗi ấy ra, nếu không nó chỉ so một hàm với chính nó; và một test
dựng sqlite trong bộ nhớ thì cái database ấy không phải schema của ai.

### Pha D — tài liệu, và cổng sống

- [x] **8.** Tài liệu: mười chỗ ở bảng `Files`, cộng trần `AGENTS.md`.
- [x] **9.** Đóng sổ đợt việc: tick ô 2a và 2b (**đang chưa tick** dù cả hai đã commit), thay bản
      ghi *"hình dạng còn để ngỏ"* bằng quyết định đã chốt, điền cổng của 2c.
- [x] **10.** Cổng sống trên sáu process.

## Validation Checks

**Đã đạt — cổng pha D, và cổng của cả plan.**

`check` **20/20** · `lint-imports` 3 contract, 0 broken · `pytest` **466** · `ruff` sạch ·
`AGENTS.md` 186/186, sát trần mới.

**Cổng sống, trên sáu tiến trình, nhìn bằng mắt trong trình duyệt:** tải hai tệp lên từ **ngoài**
trình duyệt, rail tự mọc hai chip sau ~3 giây, **không chạm F5**. Tệp scan ra `needs-human`,
*"Không đọc được chữ"*, `draggable=false`, `title` chở nguyên câu `fault`. Tệp có chữ ra
`settled`, `662 KB · 29 trang`, `draggable=true`. Đo đầu-cuối bằng script: **hai tiếng hích ở
0,59 s**, chuỗi đi qua `be` → `document` → `ingest` → `be`.

**`LOG_LEVEL` nay cả hai process nghe lời** — đo bằng biến môi trường, không chạm `.env` thật:
`INFO` → `ingest.*` và `be.*` đều INFO; `WARNING` → cả hai WARNING. Trước plan này chỉ một bên
nghe. (Phát biểu đúng của cổng là *"im phần log của chính mình"*: CLI của arq tự cấu hình logger
`arq` ở INFO, nên dòng job của nó in bất kể biến này. Bản cũ cũng vậy, nên không mất gì.)

**Sơ đồ kiến trúc đã vẽ lại và xuất lại hình**, `sources.json` cập nhật sha256. Ba lỗi chỉ hiện ra
khi **nhìn bản xuất**, không khi đọc XML: chữ `<id>` **biến mất** (drawio hiểu nó là một thẻ HTML
và nuốt), nhãn `import` đè lên khối `postgres`, và mũi `E. UPDATE documents` xuyên thẳng qua khối
`redis`. Sửa bằng waypoint tường minh, rồi xuất lại và nhìn lần hai.

**Một lỗi thật tìm được lúc chạy cổng sống, và nó có từ plan 2b** — đã ghi `backlog.md`: kênh SSE
**không tự nối lại**. Một tab mở từ trước lần restart BE hiển thị **6 tài liệu trong khi API trả
13**, không một dấu hiệu nào. `EventSource` tự nối lại; một vòng đọc `fetch` thì không, nó chỉ kết
thúc. 2c không sinh ra lỗi này — nó chỉ là lần đầu có người restart BE khi một tab đang mở.

**Cổng của plan này — và nó là một cổng *không có gì đổi*:** sau cả bốn pha, chạy lại kịch bản
G1–G12 của `kich-ban-thu-tay-giao-vien.md` trên **sáu** process (`be`, `ingest`, `document`, `fe`,
ba container) và mọi thứ hành xử **y như plan 2b để lại**: chip đi từ *đang xử lý* sang *không đọc
được chữ* không chạm F5. Một plan hình dạng mà làm đổi một hành vi là một plan đã trượt.

**Cổng riêng, đo được:**

- `.\dev.ps1 ingest` chạy lên, log nói đúng queue và đúng database.
- Tắt `ingest`, tải một tệp lên: tài liệu đứng ở *đang xử lý*, rồi thành *xử lí lỗi* sau
  `DOCUMENT_STALE_AFTER_SECONDS`. Bật lại: tài liệu **vẫn** được xử lý. Đó là bằng chứng `ingest`
  là một process rời thật, không phải một thread của API.
- `LOG_LEVEL=WARNING` làm **cả hai** process im — hôm nay chỉ một process nghe lời.
- `grep -rn "import be" services/ingest` ra rỗng.

**Đột biến:**

| Đột biến | Phải đỏ ở |
|---|---|
| `services/ingest` import một module của `be` | `lint-imports` |
| `packages/schema` import `be` | `lint-imports` |
| Gọi `prepare_schema` trong `ingest/worker.py` | check mới |
| Viết thẳng chuỗi `f"documents:{...}"` trong `ingest` thay vì gọi `documents_channel` | check mới |
| Bỏ `check_schema` khỏi startup của `ingest` | test của `ingest` |
| `ingest` cấu hình logger bằng `basicConfig` trở lại | test đọc `log_level` |

**Mười ba đột biến đã chạy, mười hai đỏ.** Sáu cái ở bảng trên, cộng bảy đường vòng mà một lượt
review tìm ra sau khi hai check đầu tiên đã xanh — và phần ấy mới là phần đáng kể:

| Đường vòng | Bản đầu | Nay |
|---|---|---|
| `prepare_schema as build` rồi gọi `build(engine)` | **lọt** | đỏ |
| `getattr(_ddl, "prepare_schema")(engine)` | **lọt** | đỏ |
| `await reset_schema(engine)` — nó dựng schema **và `DROP SCHEMA public CASCADE`** | **lọt** | đỏ |
| `Base.metadata.create_all` viết tay | **lọt** | đỏ |
| Tiền tố `"documents"` rồi nối dấu hai chấm | **lọt** | đỏ |
| `"documents" + ":" + teacher_id` · `":".join(...)` · `"{}:{}".format(...)` | **lọt** | đỏ |

Bài học, và nó là bài học về chính cách tôi viết lưới: **cả hai check đầu tiên canh một cái tên,
không canh một hành vi.** `reset_schema` là cái đắt nhất — nó xoá sạch database, im lặng, và đi
qua cả `check` lẫn test. Bản sửa canh thêm `metadata.create_all`/`drop_all`, và test của `ingest`
đổi từ *"không được lấy `prepare_schema`"* sang *"chỉ được lấy `check_schema`, và chỉ dưới cái tên
ấy"* — liệt kê cái **được phép** thì một đường vòng thứ năm chưa ai nghĩ ra cũng đâm vào cùng một
dòng assert.

Một đột biến vẫn lọt, ghi ra chứ không giấu: đổi lời gọi thành `await build(engine)` mà **không**
đổi dòng import. Nó là một `NameError` lúc worker khởi động — ồn ngay, không im — và nó chỉ có
nghĩa khi đi cùng đột biến kia, cái đã bị bắt. Nhưng nó phơi ra một chỗ thật: **không test nào
chạy `startup`**, chúng đọc cây cú pháp.

**Cổng chung:** `.\dev.ps1 check` · `test` · `typecheck`.

## Cạm bẫy đã biết

- **Pha A là nơi plan này sống hoặc chết.** 27 chỗ import là một lần đổi cơ học, nhưng
  `test_schema_guard.py` chạm thẳng `Base.metadata` và `be/reset_db.py` gọi `reset_schema`. Hai
  chỗ ấy đọc bằng mắt, không đổi bằng `sed`.
- **`.env.example` không được sinh orphan.** `be/config.py` bỏ `be_queue_name` thì `ingest` phải
  đọc nó. Đã kiểm: `services/document` tự đọc biến ấy từ config của chính nó, nên bên `be` bỏ đi
  không làm `document` mù.
- **`_ENV_FILE = parents[4]`** đúng cho `services/<tên>/src/<pkg>/config.py`. Service mới cùng độ
  sâu nên con số không đổi — nhưng một `.env` không tìm thấy **không phải lỗi**, nó là một bộ
  default đầy đủ, và triệu chứng là một công tắc cứ nằm ở off mà không ai nói gì.
- **`pytest --import-mode=importlib`** cần `testpaths` có `services/ingest/tests` và
  `packages/schema/tests`, nếu không những file test vừa chuyển sẽ **không chạy** và bảng kết quả
  vẫn xanh.
- **`pip install -e` cho hai package mới**, nếu không `lint-imports` xanh giả: comment ở
  `packages/contracts/pyproject.toml` ghi lại đúng chuyện ấy — grimp không liệt kê nổi submodule
  thì nó báo không có vi phạm nào.
- **Thứ tự xoá.** Xoá `be/models.py` trước khi `packages/schema` cài được là làm cả repo không
  import nổi, và lúc ấy không cổng nào nói được gì về nguyên nhân.
- **Windows: arq không đăng ký được signal handler** — Ctrl+C cắt ngang job, để lại một tài liệu
  đứng ở *đang xử lý*. Đã biết từ plan 2a, không phải lỗi mới của plan này.

## Status

**Xong cả bốn pha, chưa commit.** `check` **20/20** · `lint-imports` 3 contract, 0 broken ·
`pytest` **466** · `ruff` sạch.

**Hai mươi mốt lỗi do review tìm ra, không cổng nào trong số trên bắt được chúng** — bốn ở pha A,
tám ở pha B, chín ở pha C. Chúng rơi vào ba nhóm, và ba nhóm ấy là ba vùng mù có hình dạng rõ:

1. **Đường cài đặt.** `dev.ps1 install` thành một lệnh hỏng ở pha A, rồi sai số lần nữa ở pha B.
   Mọi cổng tự động đo **code đang chạy**; không cổng nào đo việc một người khác clone repo về có
   dựng được không — và nó hỏng ở máy họ, không ở máy mình.
2. **Văn bản đã mất chỗ đứng.** Sáu docstring và ba dòng contract trỏ vào file đã xoá, trong đó
   một cái là **tiền lệ được viện ra** để biện minh cho một thiết kế khác. Một plan refactor sinh
   ra đúng loại rác này, và `ruff` thì không đọc nghĩa.
3. **Lưới canh tên, không canh hành vi.** Chín đường vòng, cái nặng nhất là một hàm xoá sạch
   database đi qua cả check lẫn test. Viết một lưới xong rồi tự tin là xong chính là chỗ nó thủng.

Và một lỗi **có từ plan 2b**, chỉ lộ ra vì 2c buộc phải restart BE: kênh SSE không tự nối lại, nên
một tab mở sẵn hiển thị 6 tài liệu trong khi API trả 13, không một dấu hiệu nào. Đã ghi
`backlog.md`.
