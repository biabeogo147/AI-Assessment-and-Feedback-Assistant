# Đợt 3 của đợt tất định — panel đề nháp: ô hỏng, lưới phương án, thẻ báo, đề trống

## Goal

Làm việc 16, 12, 13, 14, 15 của `2026-10-18-deterministic-batch-master-plan.md`, theo Figma đã duyệt
18/10/2026:
- `Failed slot` `652:3635` (`hỏng` `652:3611`, `đang soạn lại` `652:3623`), artboard
  `17 · Ô câu soạn hỏng` `652:3636`;
- `System notice` `619:20`, artboard `16 · Dàn ý bị trả về tới trần` `652:3468`;
- `Consequence dialog — xoá đề nháp trống` `652:3899`, variant `tạo-đề-trống — đã xoá` `652:3900`,
  artboard `18` `653:2846`, `18b` `653:3095`.

## Scope

- **Trong phạm vi:**
  - việc 16: `check_schema` kiểm cả ràng buộc unique, hai chiều;
  - việc 12: ô hỏng hiện trên panel đúng vị trí, nút *Thử lại*, duyệt thì bỏ ô hỏng và dồn số;
  - việc 13: hai lưới lúc thu hoạch (phương án trùng; lời giải *"chọn X"* lệch phương án khoá);
  - việc 14: thẻ báo trung tính kiểu mới, chữ `OUTLINE_REFUSED` mới;
  - việc 15: xoá cứng đề trống; đoạn chat đã có đề trống thì BE dùng lại đề ấy;
  - thử tay việc 2 (panel tự đọc lại khi một lượt soạn vào đề đang mở), dời từ Đợt 1.
- **Ngoài phạm vi:**
  - nút *Thêm câu từ ngân hàng* và dòng *"Hoặc nhắn cho Kriky…"* trên artboard 18 (việc 17, Đợt 4);
  - câu kết của Kriky trên artboard 17 (*"bạn bấm Thử lại ở panel"*): chữ do model viết, AGENT khoá;
  - ô đang soạn lần đầu (chưa hỏng lần nào) vẫn không vẽ trên panel, như nay.
- Cổng mỗi pha theo plan tổng; mỗi pha một commit.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `packages/schema/src/schema/ddl.py`, `packages/schema/tests/test_schema_guard.py`, `docs/local-development.md` | 16 |
| `services/be/src/be/drafting.py`, `teacher_routes.py`, `services/fe/src/api.ts`, `screens/teacher/Panel.tsx`, `teacher.css`, tests | 12 |
| `services/be/src/be/drafting.py`, `agent_gateway.py` (docstring), tests | 13 |
| `services/be/src/be/notices.py`, `services/fe/src/screens/teacher/Chat.tsx`, `teacher.css`, tests | 14 |
| `services/be/src/be/teacher_routes.py`, `teacher_tools.py`, `teacher_chat.py`, `services/fe/src/screens/teacher/Panel.tsx`, `ActionCard.tsx`, `Chat.tsx`, tests | 15 |
| `docs/decisions/adr-18-*`, `adr-29-*`, `adr-33-*` (mới), `adr-01-*`, `adr-22-*`, `adr-24-*`, `docs/decisions/README.md`, `docs/overview/teacher-surface.md`, `docs/overview/data-model.md` | hậu ký và tài liệu |

## Ordered Tasks

### Pha 0 — `check_schema` kiểm unique (việc 16)
- [x] 1. `ddl.check_schema` so **bộ cột** của mọi ràng buộc unique ở hai phía:
  - model: `UniqueConstraint`, cột `unique=True`, `Index(unique=True)`;
  - database: `get_unique_constraints` cộng `get_indexes` có `unique`.
  - Model có mà database thiếu → lệch (*"thiếu unique …"*). Database còn mà model đã bỏ → lệch
    (*"thừa unique …"*), vì đó là ca `teacher_conversations.teacher_id` từng chặn ghi.
  - Partial index so theo bộ cột, không so điều kiện `WHERE`. Ghi giới hạn này trong docstring.
  - Câu sửa lỗi nêu cả hai đường: `ALTER` theo `docs/local-development.md` (giữ dữ liệu), hay
    `db-reset`.
- [x] 2. Test trên sqlite: unique bị gỡ thì lệch; unique thừa thì lệch; khớp thì im. Chạy thử phép
  đối chiếu mới trên DB dev **trước** khi khởi động lại BE. Nếu DB dev lệch thì ghi SQL idempotent
  vào plan này rồi chạy theo thứ tự của plan tổng.

### Pha 1 — ô hỏng và *Thử lại* (việc 12)
- [ ] 3. BE đọc: `AssessmentDetail.failed_slots: tuple[SlotRead, ...]` (`order`, `redrafting`).
  - Một ô vào danh sách khi vị trí của nó chưa có câu và ô `failed`, hoặc ô đang
    `pending`/`retry` mà đã hỏng ít nhất một lần (`last_fault` có chữ). Ô thứ hai là variant
    *đang soạn lại*.
  - Ô đang soạn lần đầu không vào: panel hôm nay không vẽ chúng, và việc này không đổi điều ấy.
- [ ] 4. BE ghi: `POST /teacher/assessments/{id}/slots/{order}/redraft`.
  - Chỉ tác giả (404 như mọi đường ADR-22), chỉ đề còn sửa được (409), chỉ ô `failed` chưa có câu
    (409 khác).
  - Đặt `status="retry"`, `attempts=0`, rồi `fire(wanted=0)`. `fire` tăng `attempts` lên 1 nên ô
    có lại đủ ba lượt.
  - Trả `AssessmentDetail`, như đường sửa câu.
- [ ] 5. Duyệt: ô `failed` bị xoá và số câu dồn lên (`_close_the_gap`, đi từ ô cao nhất xuống),
  trong cùng commit với state. Đề duyệt không còn lỗ số. Hậu ký ADR-29 (đánh số theo vị trí).
- [ ] 6. FE:
  - `api.ts`: `failed_slots`, `api.redraft`;
  - `Panel.tsx`: câu và ô hỏng xếp chung theo `order`; `FailedSlot` theo `652:3635`: nét đứt,
    chip *Chưa soạn được* họ `answer/incorrect`, lời *"Kriky gặp gián đoạn khi đang soạn câu này,
    bạn hãy thử lại nhé!"*, nút *Thử lại*. Variant *đang soạn lại*: chip *● Đang soạn lại*, lời
    *"Kriky đang soạn lại câu này. Các câu khác vẫn sửa và xoá được."*, nút tắt *Đang soạn…*;
  - đầu panel: *"{câu + ô hỏng} câu · {n} câu chưa soạn được · …"* như artboard 17;
  - đang có ô *đang soạn lại* thì panel đọc lại lặng lẽ sau 4 giây, cùng cơ chế của Đợt 1.
- [ ] 7. Test BE: danh sách ô; redraft từ chối ô không hỏng, đề đã duyệt, người khác; redraft
  bắn đúng một job và đặt lại lượt; duyệt bỏ ô hỏng và dồn số. Vitest: ô hỏng đúng vị trí, nút gọi
  BE, đầu panel đếm đúng. Trình duyệt: chụp hai variant, đo so với `652:3636`.

### Pha 2 — hai lưới lúc thu hoạch (việc 13)
- [ ] 8. `drafting._tidy_options(question)` chạy trong `harvest` **trước** `validate_question`:
  - so chữ phương án sau khi gộp khoảng trắng (cùng phép của `validate_question`);
  - trùng thì giữ một: phương án khoá luôn ở lại, giữa hai phương án nhiễu thì giữ cái đứng trước;
  - đánh lại nhãn A, B, C… theo thứ tự còn lại;
  - còn dưới 3 phương án thì `_give_up_or_retry` (*"phương án trùng, còn quá ít"*).
- [ ] 9. `drafting._names_another_option(question)`: lời giải có *"chọn X"*, *"đáp án là X"*, *"đáp án
  đúng là X"* (chữ thường hay hoa, X là một nhãn A–E viết hoa đứng riêng) mà X khác nhãn phương án
  khoá **sau khi đánh lại nhãn** → `_give_up_or_retry` (*"lời giải chọn phương án khác phương án
  khoá"*). Đánh lại nhãn làm lệch chữ *"chọn D"* của model thì cũng bị bắt và thử lại; đó là cái
  giá được chấp nhận, đổi lại không phải sửa chữ của model.
- [ ] 10. Test với kết quả AGENT giả: trùng phương án nhiễu thì bỏ một và đánh lại nhãn; trùng với
  phương án khoá thì phương án khoá ở lại; còn 2 thì thử lại; *"Chọn B."* lệch khoá C thì thử lại;
  *"chọn a = 2"* không bị bắt. Hậu ký ADR-18; sửa docstring `validate_question`.

### Pha 3 — thẻ báo (việc 14)
- [ ] 11. `notices.OUTLINE_REFUSED` = *"Kriky chưa nêu được dàn ý cho đề này. Bạn hãy thử lại nhé!"*.
- [ ] 12. `Notice` (`Chat.tsx`) và `.system-notice` (`teacher.css`) theo `619:20`: nền surface, viền
  line/default, vòng `!` trung tính (sunken + ink/muted), không dòng nguồn. Kiểm avatar Kriky đứng
  trên khối bước khi lượt có bước rồi kết bằng thông báo, cả lúc đang chạy lẫn sau F5 (artboard
  16); thiếu thì sửa `voiced()`/`blocks()`.
- [ ] 13. Test BE theo chữ mới; vitest avatar cộng thẻ. Trình duyệt: AGENT mock không chạm được
  trần dàn ý, nên dựng lượt bằng API giả (CDP) như Đợt 2; chụp, đo so với `652:3468`.

### Pha 4 — đề trống: xoá và dùng lại (việc 15)
- [ ] 14. `DELETE /teacher/assessments/{id}`, 204:
  - chỉ tác giả (404); chỉ đề `EMPTY`, không câu, không ô soạn nào (409 với lý do);
  - xoá cứng `DraftBrief` rồi `Assessment` trong một giao dịch. Lượt chat cũ giữ `entity_id`.
- [ ] 15. Lượt chat đọc lại: `TurnRead` thêm `entity_gone: bool` khi `entity_kind="assessment"` mà
  đề không còn. `ActionCard` đọc cờ ấy: đầu đề giữ *Đã tạo đề …*, câu an toàn *"Đề trống này đã
  xoá"*, không nút, không mở được (variant `652:3900`).
- [ ] 16. Panel: link *Xoá đề* cạnh *Đóng* chỉ khi đề trống (`state=EMPTY`, không câu, không ô);
  hộp xác nhận theo `652:3899` (*"Xoá đề nháp "{tên}"?"*, *Giữ lại* / *Xoá đề*); xoá xong thì đóng
  panel và đọc lại đoạn chat.
- [ ] 17. `create_draft` dùng lại đề trống mới nhất của **đoạn chat đang chạy**:
  - `Running` thêm `conversation_id`; `teacher_chat` truyền đoạn đang chạy vào `execute`;
  - tìm qua `TeacherTurn.entity_kind/entity_id` của đoạn ấy, chỉ đề còn `EMPTY`, không câu, không ô;
  - ghi tên, môn, khối mới lên đề ấy rồi `rebrief`; kết quả mang `reused: true` cùng id cũ.
- [ ] 18. ADR-33 *chỉ đề trống mới xoá được*; hậu ký ADR-01, ADR-22, ADR-24; sửa docstring
  `BankQuestion` *"Đề không bao giờ bị xoá"*. `data-model.md` ghi đường xoá.
- [ ] 19. Test BE: xoá đề có câu, có ô, đã duyệt, của người khác đều bị từ chối; xoá xong lượt cũ
  mang `entity_gone`; `create_draft` lần hai trong cùng đoạn chat trả cùng id, đoạn khác thì đề
  mới. Vitest: link chỉ hiện ở đề trống, hộp xác nhận, thẻ *đã xoá*. Trình duyệt: hộp, thẻ.

### Pha 5 — đóng
- [ ] 20. Thử tay việc 2 trên AGENT mock: soạn thêm vào đề đang mở, panel tự cập nhật.
- [ ] 21. Roadmap việc 12–16 sang *Xong*; backlog và artifact backlog ghi đã làm; tick plan tổng;
  plan này sang `completed/`.

## Decision Records

### Decision: `check_schema` so unique theo bộ cột, hai chiều
options considered: chỉ kiểm cột (như nay); so tên ràng buộc; so bộ cột, chỉ chiều thiếu; so bộ cột
cả hai chiều.
selected option: so bộ cột cả hai chiều.
reason: tên ràng buộc do database tự đặt khi model không đặt (`teacher_conversations_teacher_id_key`),
nên so tên là so một thứ không ai khai. Chiều *thừa* là ca đã xảy ra thật: constraint cũ trên
`teacher_conversations` chặn mở đoạn chat thứ hai. Partial index chỉ so bộ cột; hai index cùng bộ cột
khác điều kiện là ca chưa có trong model nào.

### Decision: ô *đang soạn lại* là ô đã hỏng ít nhất một lần
options considered: thêm cột `redrafting`; suy từ `attempts`; suy từ `last_fault`.
selected option: `last_fault` có chữ và vị trí chưa có câu.
reason: không đổi schema. `attempts` bị `fire` tăng, nên không phân biệt được lần đầu với lần soạn
lại. Một ô tự thử lại lần hai (không qua nút) cũng hiện *đang soạn lại*, và câu ấy đúng với nó.

### Decision: lưới *"chọn X"* chạy sau khi đánh lại nhãn
options considered: chạy trước khi gộp phương án; sửa chữ lời giải theo nhãn mới; chạy sau.
selected option: chạy sau, không sửa chữ.
reason: sửa chữ của model là BE viết thay lời giải (ADR-30 giữ lời cho model). Chạy sau thì một nhãn
dời chỗ vì gộp cũng bị bắt, và lần thử lại là một câu sạch.

## Validation Checks

| Kiểm | Lệnh |
| --- | --- |
| Python, repo checks | `.\dev.ps1 test`, `.\dev.ps1 check` |
| FE | `.\dev.ps1 typecheck`, vitest |
| Schema trên DB dev | phép đối chiếu mới chạy trên DB dev trước khi khởi động lại BE |
| Trình duyệt | Chrome headless (CDP) + subagent chấm ảnh, pha 1, 3, 4 |

## Status

- 18/10/2026: plan mở.
- Pha 0 xong 18/10/2026: phép đối chiếu mới chạy trên Postgres dev trước khi khởi động lại BE; 13
  bảng có unique, hai bên khớp từng bộ cột, không cần ALTER nào. Hậu ký ADR-17 (câu *"không soi
  index"* đã sai).
