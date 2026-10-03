# Chốt chặng A — thẻ kết quả, `choices` sống qua F5, xoá/đổi tên đoạn chat, và A8

## Context

ADR-25 đã thi hành xong (pha A→F). Nhưng một lượt soạn đề **thành công** hôm nay kết thúc mà
giáo viên không có đường nào đi tiếp:

- `cardTurn()` (`services/fe/src/screens/teacher/ActionCard.tsx:…`) loại `start_drafting` **luôn
  luôn**, loại `create_draft` khi có `start_drafting` phía sau, và `draft_progress` là tool của
  **pha 1** nên một plan không bao giờ gọi nó. Ba lần loại trừ ấy giao nhau đúng ở đường đi hạnh
  phúc: không thẻ nào mọc.
- Panel đề chỉ mở được từ nút trên thẻ (`Chat.tsx:252`, `onOpen`). Không thẻ ⇒ **không có cửa** vào
  đề vừa soạn. Kriky nói "đã soạn xong", màn hình không cho xem — đó đúng là thứ người dùng thấy.
- Nguyên nhân gốc nằm ở BE: `_start_drafting` trả `{"started", "queued", "assessment_id"}`
  (`services/be/src/be/teacher_tools.py:599`) — **không có con số nào**, mà thẻ có nút *Duyệt đề*
  thì cần một con số.

Nhân đây chốt hai món còn lại của chặng A (`docs/plans/backlog.md:20-22`):

- **`choices` mất sau F5.** Nặng hơn backlog ghi: `Chat.tsx:189` set `asked` từ
  `GET /teacher/chat`, đường mà BE **không bao giờ** gửi `choices` (`teacher_chat.py:1750-1765`).
  Event SSE `done` *có* mang choices nhưng FE chỉ nuôi `live` bằng nó rồi xoá ở `finally`
  (`Chat.tsx:171`, `:199`). Nghĩa là thẻ hỏi lại có thể **chưa bao giờ** hiển thị, không chỉ sau F5.
- **Không xoá hay đổi tên được một đoạn chat.** Chỉ có bốn route trong `teacher_chat.py`, không
  route nào sửa; tên đặt một lần tự động bởi `_name_the_thread` và không ai sửa được.
- **A8** — người dùng đã chốt phạm vi: *"chỉ cần upload được tài liệu lên là được, chưa làm phần
  đưa tài liệu vào agent"*. Upload + thư viện **đã chạy** và có 8 test. Việc còn lại là trả cho nó
  một cái vỏ **không hứa sai**, và viết tài liệu cho nó.

**Không làm trong plan này** (đã hỏi và người dùng chốt): phân trang danh sách đoạn chat; đọc nội
dung tài liệu vào prompt (B10 — cần cắt đoạn, nhồi ngữ cảnh, đổi hợp đồng AGENT; xứng một ADR riêng).

**Kết quả mong muốn:** gõ *"tạo đề 10 câu về tích phân"* → khối bước chạy → câu báo cáo → **một thẻ
`Đã thêm 10 câu vào đề` có nút *Duyệt đề*** mở panel. F5 lại: thẻ vẫn đó, và thẻ hỏi lại vẫn còn
các nút. Rail xoá và đổi tên được một đoạn.

## Global Constraints

- Tiếng Việt cho chuỗi ra màn hình, comment và docs; identifier và log tiếng Anh.
- Figma và code đổi **cùng một change set**, chứng minh bằng đo (`mcp__figma__get_metadata`), không
  bằng mắt.
- FE không quyết luật: con số nào hiện trên thẻ cũng do BE đọc từ database rồi gửi.
- Đổi schema thì dùng `.\dev.ps1 db-reset`; chốt kiểm `check_schema` lúc khởi động là lưới.
- Manual test trên browser chạy `gpt-4o-mini`, và API key có hạn mức — gộp các lượt thật.
- `.\dev.ps1 check` 8/8 + `.\dev.ps1 test` + test FE xanh trước khi nói xong.

---

## Việc 1 — Thẻ kết quả cho một lượt soạn đề

### 1.1 BE: bước soạn khi kết thúc đã biết số câu thật

**File:** `services/be/src/be/teacher_chat.py`, `services/be/tests/test_teacher_chat.py`

Trong pha 2, nhánh `if paper:` đã **đợi hết câu** rồi mới `history.append(TurnRecord(kind=
"tool_result", ...))` và `_record`. Khe ấy là chỗ đúng: sau vòng đợi, làm giàu `result` bằng chính
ba con số `_count_questions(session, paper)` đã đếm cho `_how_many`:

```
result = {**result, "written": n, "asked_for": m, "still_drafting": r}
```

Tái dùng, không viết mới: `_count_questions` trả `(written, asked_for, running)`; `_how_many` đang
in `đã soạn 3/3 câu` từ đúng bộ số đó. Vì làm giàu **trước** `_record`, con số đi vào row — nên SSE
và F5 thấy cùng một thứ, không phải hai đường tính.

Cửa `POST` không đợi, nên ở đó `result` không có ba field này. Đó là chủ ý: thẻ chỉ mọc khi con số
là thật.

**Test:**
- `test_a_finished_drafting_step_carries_the_real_counts` — row `tool_result` của `start_drafting`
  mang đúng `written`/`asked_for`/`still_drafting`, và đọc lại bằng `GET /teacher/chat` vẫn mang.
- `test_the_post_door_adds_no_counts_it_did_not_wait_for` — cửa `POST` không bịa số.
- **Đột biến:** chuyển dòng làm giàu xuống **sau** `_record` → đúng test F5 đỏ.

### 1.2 FE: thẻ mọc từ bước soạn

**File:** `services/fe/src/screens/teacher/ActionCard.tsx`, `services/fe/src/teacher.test.tsx`

`cardTurn()`: bỏ loại trừ vô điều kiện `start_drafting`, thay bằng *chỉ loại khi kết quả không mang
`asked_for`* — một bước soạn chưa đợi xong thì vẫn không có thẻ.

Thêm một variant đọc `written: number` (khác thẻ `draft_progress` hiện có, nơi `written` là một
**array** — không mượn hình dạng ấy, mượn là mời hai nghĩa vào một tên):

| Điều kiện | Head | Nút chính |
|---|---|---|
| `written >= asked_for` | `Đã thêm {written} câu vào đề` | *Duyệt đề* → `onOpen(assessment_id)` |
| `written < asked_for`, `still_drafting == 0` | `Dừng ở {written}/{asked_for} câu` | *Xem đề* → `onOpen(...)`, **không** mời duyệt |

Vế thứ hai đi cùng luật đã có trong `reporting._progress`: duyệt một đề thiếu câu là phát hành một
bài kiểm tra dở, nên lời kể và thẻ phải nói cùng một câu.

**Test:** `test_mot_luot_soan_de_xong_moc_mot_the_co_nut_duyet`,
`test_de_thieu_cau_khong_moi_duyet`, `test_buoc_soan_chua_doi_xong_khong_moc_the`.

### 1.3 Figma

`docs/overview/teacher-surface.md` đang ghi khoảng trống này thành một đoạn *"một lượt soạn đề thành
công hôm nay kết thúc không có thẻ nào"* — xoá đoạn ấy, thêm hai dòng trên vào bảng variant của thẻ.
Component thẻ kết quả trên page `Screen — Teacher` thêm variant tương ứng, và **đo** head + nút đối
chiếu với FE.

---

## Việc 2 — `choices` sống qua F5 (A7, món 1)

### 2.1 Lưu nó

**File:** `services/be/src/be/models.py`, `teacher_chat.py`, `services/be/tests/test_teacher_chat.py`

- `teacher_turns` thêm hai cột: `choices` JSON (default `list`), `more_choices` Integer (default 0).
- `_record(...)` nhận thêm hai keyword (`choices`, `more_choices`), đúng khuôn `duration_ms` /
  `model_tokens` đang dùng. **Không** thêm vào `TurnRecord`: type đó đi qua queue sang AGENT, và
  docstring của `Turn` (`teacher_chat.py:162-174`) đã chốt đúng lý do tách hai thứ — choices là nhu
  cầu của màn hình, model không dùng được nó.
- `Turn` + `_visible` chở hai field ấy ra FE.
- `read_conversation` (`:1715-1785`): ở cả ba đường ra, lấy `choices`/`more_choices` của **bước cuối
  cùng** đưa vào `Answered`. Chỉ bước cuối: một câu hỏi đã được trả lời thì các nút của nó không còn
  nghĩa gì.
- Chạy `.\dev.ps1 db-reset` sau khi đổi model.

**Test:** `test_the_options_survive_a_reload` (POST xong → `GET /teacher/chat` vẫn trả đúng hai
phương án; đây là chỗ test hiện có `test_the_options_are_written_by_be_not_by_the_model` **không**
chạm tới vì nó chỉ đi cửa POST), `test_an_answered_question_no_longer_offers_its_buttons`.

### 2.2 FE dùng nó

**File:** `services/fe/src/api.ts`, `Chat.tsx`, `teacher.test.tsx`

`Turn` của FE thêm hai field (khớp 1-1 với BE như hiện nay). `Chat.tsx:189` giữ nguyên hình dạng —
nó đọc `whole.choices`, và nay `whole` thật sự có. Effect đổi route (`:99-107`) cũng dựng lại `asked`
từ bước cuối thay vì `setAsked(null)` cứng. Luật "gấp" lượt cuối (`:221-226`) và comment ở đó phải
viết lại: sau F5 câu hỏi **không** còn quay về làm một bong bóng thường.

**Test:** `test_the_hoi_lai_con_nut_sau_khi_tai_lai` — hiện **không có test nào** cho `Clarify`.

---

## Việc 3 — Xoá và đổi tên một đoạn chat (A7, món 2)

Backlog để ngỏ câu hỏi chặn: *xoá một đoạn thì biên bản duyệt trong đó đi đâu (ADR-24)*. Plan này
quyết: **xoá mềm**. Một cột `deleted_at`; đoạn biến khỏi rail và khỏi `read_conversation`, các row
`teacher_turns` **không** mất. Biên bản duyệt là thứ ADR-24 bắt giữ, nên nó không được chết vì một
cú dọn nhà; và giáo viên muốn "mất đi khỏi mắt tôi" chứ không muốn một cuộc điều tra sau này không
còn bằng chứng.

### 3.1 BE

**File:** `services/be/src/be/models.py`, `teacher_chat.py`, `services/be/tests/test_teacher_memory.py`

- `teacher_conversations` thêm `deleted_at` DateTime(tz), nullable.
- `PATCH /api/teacher/conversations/{conversation_id}` — body `{title}`. Dọn bằng **chính hàm dọn
  `_name_the_thread` đang dùng** (cùng giới hạn 120 ký tự của cột), tên rỗng sau khi dọn → 400.
- `DELETE /api/teacher/conversations/{conversation_id}` — set `deleted_at`, trả 204.
- Lọc `deleted_at.is_(None)` ở `conversations` (`:1787`), `read_conversation` (`:1715`) và
  `_latest_conversation`. Đoạn đã xoá đọc ra **y như một đoạn không tồn tại**: 404, đúng khuôn
  `:1746-1749` đang dùng cho đoạn của người khác.
- Quyền: lọc `teacher_id`, không nhận id nào từ caller ngoài id đoạn (ADR-13/ADR-22).

**Test:** `test_a_deleted_conversation_leaves_the_rail`,
`test_a_deleted_conversation_keeps_its_turns`, `test_one_teacher_cannot_delete_anothers_conversation`,
`test_a_renamed_conversation_keeps_the_name_the_teacher_typed`,
`test_a_title_that_is_only_spaces_is_refused`,
`test_a_new_turn_never_lands_in_a_deleted_conversation`.

### 3.2 FE

**File:** `services/fe/src/api.ts`, `screens/teacher/Rail.tsx`, `Chat.tsx`, `teacher.css`,
`teacher.test.tsx`

`Row` hiện là **một `<button>` bọc cả hàng** (`Rail.tsx:260-286`) — một nút lồng trong nút là HTML
sai, nên hàng phải tách: một `div.conversation` chứa `<button class="open">` (phần tên, giữ
`aria-current`) và một `<button class="more" aria-label="Tuỳ chọn đoạn chat">`. Menu `⋯` hai mục:
*Đổi tên* (đổi phần tên thành `<input>` tại chỗ, Enter lưu, Esc huỷ) và *Xoá*.

Xoá đi qua **hộp xác nhận đã có** (khuôn `hộp xác nhận phát hành`, `teacher.test.tsx:71`) — xoá là
việc một chiều với người dùng, dù dưới lớp sơn là xoá mềm. Xoá đoạn đang mở → điều hướng
`/teacher/moi`.

**Test:** chưa có test nào cho `Rail` — thêm `test_doi_ten_mot_doan_chat`, `test_xoa_doan_dang_mo_thi_ve_doan_moi`,
`test_xoa_phai_qua_hop_xac_nhan`.

### 3.3 Figma

Rail trên page `Screen — Teacher`: hàng đoạn chat thêm state `hover` có `⋯`, cộng một menu hai mục
và một hộp xác nhận xoá. Đo đối chiếu chiều rộng rail 260 (`teacher-surface.md:175`) và nhãn.

---

## Việc 4 — Chốt A8: cái vỏ không hứa sai

**File:** `services/fe/src/screens/teacher/Chat.tsx`, `docs/overview/teacher-surface.md`,
`docs/plans/backlog.md`, `services/fe/src/teacher.test.tsx`

Upload và thư viện đã chạy đúng và đã có 8 test BE (`services/be/tests/test_documents.py`). Hai
việc còn lại:

1. **Dải `scope` đang nói sai.** Nó in *"Đổi phạm vi"* và `scope` **không bao giờ** rời khỏi màn
   hình: `send()` không đọc nó, body `streamTurn` đúng ba field `{text, conversation_id, start_new}`
   (`api.ts:537-546`). Chữ "phạm vi" hứa một việc chưa xảy ra. Sửa chữ, không sửa luồng: dải đổi
   thành `Đã tải lên: {filename}` với nút *Tải tệp khác*, và một dòng nhỏ **nói thật** rằng nội dung
   tài liệu chưa đi vào việc soạn đề. Nút `＋ Tài liệu` giữ nguyên.
2. **Test FE cho đường tài liệu — hiện bằng không.** `test_tai_len_mot_tai_lieu_thi_no_hien_tren_rail`.

Tài liệu: `teacher-surface.md` hiện **không có mục nào** về ngăn Tài liệu — thêm một mục ngắn (chip
in kích thước chứ không in số trang, và vì sao). `backlog.md` tách dòng hiện tại thành *A8 đã trả
xong* và một món B10 còn nợ: *nội dung tài liệu chưa đi vào prompt của AGENT*.

Figma: nếu dải `scope` có trên artboard `2 · Kèm tài liệu` (`85:327`) thì sửa chữ ở đó cùng lúc.

---

## Verification

1. `.\dev.ps1 check` → 8/8. `.\dev.ps1 test` + test FE → xanh.
2. `.\dev.ps1 db-reset` (hai cột mới), khởi động lại BE **thủ công** — `uvicorn --reload` không
   reload thật trong setup này.
3. Một lượt thật trên browser, `gpt-4o-mini`, gộp vào một phiên để tiết kiệm hạn mức:
   - *"tạo đề 3 câu về tích phân"* → khối bước chạy, câu báo cáo, **thẻ `Đã thêm 3 câu vào đề`**,
     bấm *Duyệt đề* → panel mở đúng đề.
   - **F5** → thẻ vẫn đó, số vẫn đúng.
   - *"tạo cho tôi một đề"* → câu hỏi lại **có các nút**; F5 → nút **vẫn còn**.
   - Rail: đổi tên đoạn, F5 thấy tên mới; xoá một đoạn khác → hộp xác nhận → đoạn rời rail; đoạn còn
     lại vẫn đọc được.
   - `＋ Tài liệu` một PDF nhỏ → chip lên rail, dải dưới composer nói đúng.
4. Đo Figma đối chiếu: thẻ kết quả, hàng rail + menu, dải tài liệu.
5. **Một subagent review toàn bộ thay đổi code** của bốn việc trên (BE + FE + model/schema), trước
   khi xin phép commit.

---

## Những gì review tìm ra, và đã sửa

Một subagent review cả nhánh sau khi bốn việc xong. Hai phát hiện là **màn hình nói sai với giáo
viên**, và cả hai đều có một comment ngay bên cạnh tuyên bố điều ngược lại:

1. Thẻ mời `Duyệt đề` cho một đề **3/10 câu** khi bảy câu còn đang chạy — điều kiện mời duyệt viết
   là *"thiếu câu **và** không còn gì chạy"* thay vì *"đã đủ câu"*. Sửa, cộng một variant Figma thứ
   mười (`đang-soạn-dở`) và một test.
2. `choices` được ghi cho cả một bước `say`, nên một lời **thông báo** sau `find_class` mọc ra hai
   cái nút; bấm một nút gửi `"12A (3 học sinh)"` đi như một câu của giáo viên. Chặn ở BE, nơi duy
   nhất biết `step.kind`.

Cộng: menu `⋯` bị vùng cuộn của rail cắt ở hàng cuối — `position: fixed` gỡ được phần cắt, nhưng
đo tiếp bằng `elementFromPoint` thì mục *Xoá* vẫn trả về một chip tài liệu, nên menu phải đi qua
**portal vào `body`**; hai menu mở được
cùng lúc và không có đường đóng (nâng state lên `Rail`, thêm Esc + bấm ra ngoài); một race làm tên
vừa đặt bị revert (đổi nhãn lạc quan rồi lùi lại khi hỏng); và năm chỗ chưa có lưới — `deleted_at`
ở `_latest_conversation` và `conversation_of`, `more_choices`, hai nhánh còn lại của `drafted()`,
hai đường lỗi của rail. Mỗi chỗ một test, và hai đột biến đã đo là đỏ đúng chỗ.
