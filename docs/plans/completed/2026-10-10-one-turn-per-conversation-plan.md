# Plan — một đoạn chat chạy nhiều nhất một lượt

## Goal

Đóng hai món còn treo của `2026-10-02-hai-pha-mot-luot-chat-plan.md`, rồi đóng chính plan ấy.

Món thật: **hai tab cùng chạy một plan trong một đoạn chat**. Người dùng chốt ngày 10/10/2026 —
*từ chối plan thứ hai*. Món kia bị **bỏ**, cũng do người dùng chốt cùng ngày: không cần cờ *"lượt
này đã báo cáo chưa"*, vì skill mô tả quy trình và trợ lí tự quyết có kể lại hay không.

## Scope

**Trong:** một khoá theo đoạn chat trong Postgres; lời từ chối 409 bằng tiếng Việt; test BE và FE;
ADR-25 nhận hai mục; một hàng invariant trong `AGENTS.md`; đóng plan hai pha.

**Ngoài:** đẩy pha 2 sang job arq (đã bỏ cùng cái cờ); ngân sách cho `_report` (đã ghi nợ ngày
10/10/2026, sẽ tan vào skill); Figma — lời từ chối đi qua `.trouble`, một trạng thái **đã có**, nên
không có gì để vẽ trước.

## Decision Records

### Decision: khoá sống trong Postgres, không trong Redis

**options considered:** (a) khoá Redis `SET NX EX` qua pool arq · (b) **một cột `running_since` trên
`teacher_conversations`, cộng một cửa sổ quá hạn** · (c) một dict `asyncio.Lock` trong process.

**selected option:** (b).

**reason:** (c) chết ngay khi có BE thứ hai — một khoá trong bộ nhớ của một process không nói gì với
process kia. Giữa (a) và (b): cả hai đều tự nhả sau khi process chết, một bằng TTL một bằng cửa sổ
quá hạn, nên chúng ngang nhau ở chỗ ấy. Cái lệch là **nơi sự thật đã sống**. `_rendered` dựng lại cả
màn hình từ `teacher_turns`, nên *"đoạn này đang chạy"* để cạnh những hàng ấy là một nguồn, còn để
trong Redis là nguồn thứ hai cho một câu mà màn hình sẽ cần tới. Và đo được: `app.state.queue_pool`
là `object()` trần ở bốn fixture (`test_teacher_chat.py:132`, `:169`, `test_teacher_memory.py:97`,
`test_teacher_reads.py:62`), nên (a) đòi dựng fake Redis ở bốn chỗ hoặc một `getattr(pool, "set")` —
tức đúng cái bẫy *lưới canh tên chứ không canh hành vi* mà review plan 2c vừa bắt chín lần. Một cột
thì mọi fixture đã có database thật.

Cột đổi schema, và luật *"cứ xoá db rồi tạo lại khi dev ở local"* (người dùng, 09/10/2026) làm giá
ấy gần bằng không.

### Decision: từ chối bằng 409, không xếp hàng

**options considered:** (a) **409 kèm một câu tiếng Việt** · (b) xếp lượt thứ hai vào hàng đợi · (c)
cho hai plan chạy song song.

**selected option:** (a), do người dùng chốt.

**reason:** (c) biến dãy bước trộn lẫn thành hành vi có chủ đích, và khi đó màn hình phải phân biệt
hai dãy — việc Figma nhiều hơn hẳn phần code nó mua được. (b) hứa một thứ khó giữ: một lượt xếp hàng
sau một lượt dài vài phút thì giáo viên đã gõ xong câu khác từ lâu. 409 đi vào đúng đường có sẵn:
`Chat.tsx:233` đã ném khi gặp lỗi, trả chữ vừa gõ về ô nhập và hiện câu lỗi ở `.trouble`.

### Decision: khoá **trước** khi ghi hàng của giáo viên

**options considered:** (a) khoá ngay sau khi biết `thread`, trước `_record` · (b) khoá sau khi ghi
câu giáo viên vừa gõ.

**selected option:** (a).

**reason:** (b) để lại trong đoạn chat một câu hỏi không có câu trả lời nào — một hàng
`kind="teacher"` mồ côi mà F5 vẫn dựng lại. Lời từ chối phải **không để lại dấu vết nào** trong
`teacher_turns`.

### Decision: ADR-25 nhận hai mục, không có ADR mới

**options considered:** (a) **thêm vào ADR-25** · (b) một ADR-28 cho luật một-lượt-một-đoạn.

**selected option:** (a).

**reason:** `AGENTS.md` cấm thêm một tài liệu khi đã có tài liệu sở hữu chủ đề, và ADR-25 sở hữu vòng
đời của một lượt chat -- chính nó đã liệt kê *"hai tab cùng chạy một plan"* trong mục **ba thứ chưa
có nơi thi hành**. Một ADR riêng sẽ để lại hai tài liệu cùng nói về cùng một lượt, và lần sau người
đọc phải đoán cái nào mới. Khuôn `> **Sửa ngày …**` đã có sẵn trong chính ADR-25 (lần sửa
06/10/2026), nên bản ghi cũ không bị viết lại -- nó được ghi ngày.

### Decision: nâng trần `AGENTS.md` lên đúng một dòng

**options considered:** (a) **nâng 181 -> 182** · (b) không thêm hàng invariant · (c) cắt một hàng
khác cho vừa.

**selected option:** (a).

**reason:** Bảng Invariants là **chỉ mục** của những chỗ thi hành, nên (b) để một cái lưới vừa dựng
nằm ngoài chỗ người ta đi tra -- đúng cái lý do hai lần nâng/hạ trần trước đây đã viết ra trong
`check_contract.py`. (c) là cắt một luật còn hiệu lực để trả giá cho một luật mới, tức đổi một món
nợ thành một món nợ khác. Trần tăng đúng một dòng và comment tại chỗ nói nó mua gì, nên lần sau
không ai tiêu được tín dụng ấy mà khỏi phải giải thích.

## Files

| File | Việc |
| --- | --- |
| `packages/schema/src/schema/models.py` | `TeacherConversation.running_since` |
| `services/be/src/be/teacher_chat.py` | `_hold_the_thread()`, gọi trong `run_turn` ngay sau khi có `thread`; nhả trong `finally` |
| `services/be/src/be/config.py` | `turn_lock_stale_seconds: int = 600` |
| `.env.example` | `TURN_LOCK_STALE_SECONDS=600` |
| `services/be/tests/test_teacher_chat.py` | ba test: từ chối, không để lại dấu vết, khoá quá hạn thì nhường đường |
| `services/fe/src/teacher.test.tsx` | một test: lời từ chối hiện ra và chữ vừa gõ còn nguyên |
| `docs/decisions/adr-25-hai-pha-mot-luot-chat.md` | hai mục: một lượt mỗi đoạn; bỏ cờ báo cáo |
| `AGENTS.md` | một hàng invariant kèm tên test |
| `docs/plans/backlog.md` | món cờ báo cáo: ghi là **đã bỏ**, không phải đang chờ |

## Ordered Tasks

- [x] **Pha A — khoá và lời từ chối.** Cột, settings, `.env.example`, `_hold_the_thread`, ba test BE.
- [x] **Pha B — FE.** Một test chứng minh câu từ chối tới được `.trouble`. Không sửa `src` nếu
  đường có sẵn đã đủ; nếu phải sửa thì dừng lại và báo, vì lúc ấy Figma đi trước.
- [x] **Pha C — tài liệu và đóng sổ.** ADR-25 hai mục kèm nơi thi hành; hàng invariant trong
  `AGENTS.md`; backlog; rồi plan hai pha: Status, sửa link trong ADR-25, `git mv` sang `completed/`.

Sau mỗi pha: `check` + `test` + `typecheck`, rồi một subagent review đọc code thật.

## Validation Checks

- `.\dev.ps1 check` 20/20 · `.\dev.ps1 test` · `.\dev.ps1 typecheck` sạch.
- **Ba đột biến, mỗi cái phải làm đỏ ít nhất một test:** bỏ `finally` nhả khoá (lượt thứ hai trong
  cùng một tab bị từ chối) · bỏ điều kiện quá hạn trong câu `UPDATE` (một khoá chết chặn mãi) ·
  khoá **sau** `_record` (test *không để lại dấu vết* đỏ).
- Khoá phải **atomic**: một câu `UPDATE ... WHERE running_since IS NULL OR running_since < :cutoff`
  rồi đọc `rowcount`. Hai câu lệnh đọc-rồi-ghi là đúng cuộc đua đang đi sửa.
- Database local xoá rồi tạo lại, và một lượt thật qua trình duyệt với `gpt-4o-mini`: gửi một câu,
  rồi gửi tiếp từ một tab thứ hai trong lúc lượt đầu còn chạy → câu từ chối hiện ra, chữ còn nguyên,
  và `teacher_turns` **không** có hàng nào của lần bị từ chối.

## Status

Xong cả ba pha, và ba phép đo cuối đã chạy trên Postgres thật (10/10/2026).

**Cổng:** `check` 20/20 · `pytest` 459 (452 trước, +7) · `vitest` 186 · `tsc` sạch.

### Pha B không sửa `src`, nên không có việc trên Figma

Lời từ chối đi hết đường có sẵn: cửa SSE gửi một khung `done` mang `ended_as="error"`, và
`Chat.tsx:233` in thẳng `text` ấy vào dòng `.trouble` rồi trả chữ vừa gõ về ô nhập. Không trạng
thái mới nào, nên luật *"frontend đổi thì Figma đổi trước"* không có gì để áp ở lượt này.

### Review tìm ra một lỗi nặng, và phép đo đầu của tôi cho xanh giả

**F1 (nặng, đã vá).** `finally` nhả khoá **không chạy** khi client ngắt kết nối. Cancel scope của
anyio là *level-triggered*: sau khi scope bị cancel, mọi `await` mới bên trong raise
`CancelledError` ngay, và `except Exception` không bắt `BaseException`. Hậu quả: đóng tab giữa lượt
khoá đoạn chat ấy mười phút, im lặng. Vá bằng `anyio.CancelScope(shield=True)`, và `anyio` khai vào
`services/be/pyproject.toml` vì BE nay import nó trực tiếp.

Phép đo đầu của tôi **sai**: nó dùng `asyncio.Task.cancel()` trần, nơi `CancelledError` được giao
đúng một lần nên các `await` trong `finally` vẫn chạy xong → xanh cả khi code sai. Test nay dùng
`anyio.create_task_group()` + `tg.cancel_scope.cancel()`, và docstring nói rõ vì sao bản asyncio
không đủ.

**F2 (đã vá).** Nhả khoá không có fencing: một lượt sống lâu hơn cửa sổ quá hạn sẽ xoá khoá của
lượt đã giành nó, trả lại đúng hai plan cài răng lược. Nay `_hold_the_thread` trả về mốc nó ghi và
`_let_go_of_the_thread` nhả với `WHERE running_since = :mine`.

**F5 (đã vá).** Năm docstring nói sai, trong đó `config.py` và `.env.example` khẳng định cửa sổ quá
hạn *"chỉ có tác dụng khi một process chết"* — sai vì chính F1.

**F3 và F4 chưa vá**, đã ghi `docs/plans/backlog.md`: nhả khoá muộn trên một session đã đóng; và
đồng hồ của process thay vì của database, chỉ đau khi có BE thứ hai.

### Năm đột biến, mỗi cái làm đỏ đúng test của nó

Plan đặt ra ba; phải thêm hai sau review.

| Đột biến | Test đỏ |
|---|---|
| bỏ `finally` nhả khoá | lượt thứ hai trong cùng một tab bị từ chối |
| bỏ điều kiện quá hạn trong `UPDATE` | khoá của một process đã chết chặn mãi |
| khoá **sau** `_record` | *một lượt bị từ chối không để lại gì* |
| gỡ `shield` | 2 test (và cả phép đo trên cửa thật — xem dưới) |
| gỡ fencing | *một lượt quá hạn không xoá khoá của lượt sau* |

Cái cuối đáng ghi riêng: trước khi thêm test ấy, gỡ fencing ra thì **cả bộ test vẫn xanh**.

### Ba phép đo trên hạ tầng thật

Database xoá rồi tạo lại (`db-reset`), `running_since TIMESTAMPTZ` có mặt, `LLM_MODEL=gpt-4o-mini`.

**1. Khoá có atomic thật không — và đối chứng.** 40 lượt × 4 session asyncpg cùng giành một hàng:
số người thắng mỗi lượt `min=1 max=1`. Rồi chạy lại bằng một bản **đọc-rồi-ghi** viết riêng cho
phép đo: số người thắng ra `[1, 4]`. Nên cuộc đua là thật, và một câu `UPDATE ... WHERE` + `rowcount`
là thứ phân xử nó. Đây là chỗ bộ test **không** nói được gì: nó chạy trên `sqlite+aiosqlite://`.

**2. Cắt kết nối giữa lượt, trên cửa uvicorn thật.** Một lượt `gpt-4o-mini` thật, client ngắt ở
giây 1,2 (`curl -m`, thoát mã 28). Theo dõi cột 10 lần/giây: khoá **được giữ** trong lúc lượt chạy
rồi **nhả trong 0,06s** kể từ cú cắt. Ba lần đều vậy.

Rồi gỡ `shield` ra và dựng lại BE: khoá **không được nhả**, hai lần đo hợp lệ đều vậy — và lần thứ
ba thành rỗng *chính vì* lần trước đã khoá chết đoạn chat ấy. Nên F1 là lỗi thật trên cửa thật, và
`shield` là thứ chịu lực, không phải một sự cẩn thận thừa.

Một cái bẫy ở đây đáng ghi: `uvicorn --reload` nạp lại **đúng một lần** rồi thôi, nên bốn phép đo
đầu của tôi chạy trên bản đột biến trong khi tôi tưởng là bản sạch — đúng cái đã ghi trong memory
*"BE không tự nạp lại code"*. Phép đo chỉ đáng tin sau khi tôi bỏ `--reload` và dựng lại BE cho
từng nhánh.

**3. Hai tab một đoạn chat.** Tab A mở một lượt thật; 1,2s sau tab B gửi tiếp vào cùng
`conversation_id`. B nhận đúng một khung `done` / `ended_as="error"` mang nguyên văn *"Đoạn chat này
đang chạy một việc. Hãy đợi nó xong rồi gửi tiếp."* A vẫn xong bình thường (`teacher_turns` +2: một
hàng `teacher`, một hàng `assistant`). Câu của B để lại **0 hàng**, và khoá về `NULL` sau đó.

**4. Nửa màn hình, trên trình duyệt thật.** Hai tab Chrome cùng mở
`#/teacher/chat/22c839b2-…`. Tab A gửi *"soan cho toi mot de 12 cau tu luan ve tich phan tung
phan…"*; trong lúc A còn chạy, tab B bấm **Gửi**. Trên tab B hiện đúng một dòng hồng phía trên ô
nhập — *"Đoạn chat này đang chạy một việc. Hãy đợi nó xong rồi gửi tiếp."* — và ô nhập **vẫn giữ
nguyên** `tao de 10 cau tich phan`. Sau khi A xong: `teacher_turns` không có hàng nào mang câu của
B, và `running_since` về `NULL`.

Một thứ phát sinh trong phép đo này, **không** do khoá: lượt A trả lời *"Mình chưa dựng được các
bước cho việc này"* vì BE từ chối plan của agent — `WARNING be.teacher_chat refused a plan for
GV-001: bước 1 thiếu tham số ['grade', 'subject', 'topic_scope'] của create_draft`. Đó là một cửa
kiểm có sẵn và `gpt-4o-mini` trả về plan thiếu tham số. Nó lại thành một lượt coverage thêm: khoá
vẫn giữ rồi nhả đúng qua chính đường từ chối plan ấy.

### Một cái bẫy của chính máy này, đáng ghi

Extension Chrome có **ba** instance cùng nối vào account, và hai cái cũ tranh nhau nhóm tab:
`navigate` báo thành công nhưng mọi `screenshot` / `find` trả `Frame with ID 0 is showing error
page`, vite không thấy request nào, trong khi `curl` vào đúng cổng ấy thì 200. Chọn đúng instance
của Chrome đang mở trên máy thì hết. Lần sau gặp triệu chứng *"navigate xanh mà trang trắng"*, kiểm
số instance trước khi nghi dev server.
