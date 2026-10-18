# Đợt 4, cụm 3 — thêm câu từ ngân hàng vào đề (việc 17)

## Goal

Làm việc 17 của `2026-10-18-deterministic-batch-master-plan.md`: giáo viên thêm câu từ ngân hàng của
mình vào một đề còn mở, ngay trên panel phải; mỗi câu trên panel có chip nguồn thật (*Kriky soạn* /
*Từ ngân hàng*). Figma đã duyệt 18/10/2026: artboard `19 · Panel — chip nguồn và nút thêm câu từ ngân
hàng` `655:3974`, `19b · Thêm câu từ ngân hàng — hộp chọn` `655:4222`, `18 · Đề nháp trống` `653:2846`
(nút ở đề trống), component `Source chip` `654:25`, `Bank row` / `Bank picker` `655:38` / `655:39`.

## Scope

- **Trong phạm vi:**
  - schema: `questions.source` (`kriky` / `bank`), `questions.bank_question_id` (trỏ `bank_questions`,
    `SET NULL` khi xoá); ALTER idempotent trên DB dev, theo thứ tự của plan tổng;
  - BE: `POST /teacher/assessments/{id}/bank-questions` chép các câu đã chọn vào cuối đề, mỗi câu
    một ô `DraftItem` `ready`; `GET /teacher/assessments/{id}/bank-picker` liệt kê ngân hàng, đánh dấu
    câu đã có trong đề này; `QuestionRead.source`; duyệt không chép lại câu lấy từ ngân hàng;
  - FE: chip nguồn trên thẻ câu; nút *Thêm câu từ ngân hàng* cuối danh sách câu và trong đề trống;
    hộp chọn có ô tìm (lọc tại chỗ), ô đánh dấu, đếm *"Đã chọn n câu"*, nút *Thêm n câu vào đề*;
  - hậu ký ADR-04, ADR-28; `data-model.md`; `teacher-surface.md`.
- **Ngoài phạm vi:** Kriky rút câu từ ngân hàng khi soạn (chạm AGENT, khoá); dòng *"Hoặc nhắn cho
  Kriky…"* của artboard 18 giữ như Figma vẽ.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `packages/schema/src/schema/models.py` | hai cột |
| `services/be/src/be/teacher_routes.py`, `question_bank.py` (`choose`, `take_into`, `picker`) | route, `source`, duyệt |
| `services/be/tests/test_bank_into_draft.py` (mới) | test BE |
| `services/fe/src/api.ts`, `screens/teacher/Panel.tsx`, `BankPicker.tsx` (mới), `teacher.css`, `teacher.test.tsx` | FE |
| `docs/overview/data-model.md`, `teacher-surface.md`, `docs/decisions/adr-04-*`, `adr-28-*`, `README.md` | tài liệu |

## Ordered Tasks

### Pha 1 — schema và BE
- [x] 1. Model: `Question.source` `String(16)` mặc định `"kriky"`; `Question.bank_question_id`
  `ForeignKey("bank_questions.id", ondelete="SET NULL")`, nullable. ALTER trên DB dev (dừng BE và
  ingest, `pg_dump` vào scratchpad, `docker exec -i aiafa-postgres psql`, khởi động lại; `check_schema`
  qua là xác nhận):
  ```sql
  ALTER TABLE questions ADD COLUMN IF NOT EXISTS source VARCHAR(16) NOT NULL DEFAULT 'kriky';
  ALTER TABLE questions ADD COLUMN IF NOT EXISTS bank_question_id VARCHAR(36)
    REFERENCES bank_questions(id) ON DELETE SET NULL;
  ```
- [x] 2. `GET /teacher/assessments/{id}/bank-picker`: mọi câu ngân hàng của giáo viên (đề bài, mục,
  tên đề gốc), cờ `in_this_paper` khi câu ấy đã nằm trong đề (qua `bank_question_id`, hay chính là
  bản của một câu của đề).
- [x] 3. `POST /teacher/assessments/{id}/bank-questions` `{bank_ids: [...]}`: chỉ tác giả (404), đề còn
  mở (`assert_editable`, 409), không còn ô đang soạn (409, như xoá câu); bỏ qua câu đã có; chép đề bài,
  phương án, lời giải vào cuối đề (`order_index` tiếp theo), `source="bank"`, `bank_question_id`; mỗi câu
  một ô `DraftItem` `ready`; đề `EMPTY` sang `HAS_QUESTIONS` qua `advance`; trả `AssessmentDetail`.
- [x] 4. `QuestionRead.source`; `file_approved` bỏ qua câu `source="bank"` (bản ngân hàng đã có, và
  chép lại là hai bản của một câu).
- [x] 5. Test BE (sqlite và `aiafa_test`): chép đúng thứ tự và đủ phương án; đề trống sang có câu;
  câu đã có bị bỏ qua; người khác 404; đề đã duyệt 409; soạn thêm sau đó đánh số nối tiếp; duyệt
  không tạo bản ngân hàng thứ hai.

### Pha 2 — FE
- [ ] 6. `Source chip` trên thẻ câu (`Kriky soạn` / `Từ ngân hàng`), theo `654:25`.
- [ ] 7. Nút *Thêm câu từ ngân hàng* (cuối danh sách câu, và trong đề trống), chỉ khi đề còn mở; hộp
  chọn theo `655:4222`; thêm xong thì panel đọc lại.
- [ ] 8. Vitest; chụp, đo so với 19, 19b, 18; subagent chấm.

### Pha 3 — đóng
- [ ] 9. Tài liệu, hậu ký; roadmap việc 17 *Xong*; backlog; tick plan tổng; plan sang `completed/`.

## Decision Records

### Decision: câu lấy từ ngân hàng là một **bản chép** trong đề, nhớ nó từ đâu
options considered: đề trỏ thẳng vào dòng ngân hàng; chép câu và nhớ `bank_question_id`.
selected option: chép, kèm `source` và `bank_question_id`.
reason: câu trong đề mang `options` riêng mà `Answer.option_id` trỏ vào (ADR-28 đã chọn bản chép theo
hướng ngược lại); sửa ngân hàng sau đó không được đổi câu đã nằm trong đề (người dùng chốt 18/10).
`bank_question_id` cho biết câu đã có trong đề để hộp chọn khoá nó lại.

### Decision: duyệt không chép lại câu lấy từ ngân hàng
options considered: chép như mọi câu (thành bản thứ hai); ghi đè dòng ngân hàng gốc; bỏ qua.
selected option: bỏ qua.
reason: chép là hai bản của một câu trong ngân hàng; ghi đè là để một lần sửa trong đề lặng lẽ đổi
bản ngân hàng, ngược điều người dùng chốt cho màn 22b.

## Validation Checks

| Kiểm | Lệnh |
| --- | --- |
| Python, repo checks | `.\dev.ps1 test`, `.\dev.ps1 check` |
| Postgres | `pytest services/be/tests --postgres-url=…/aiafa_test` |
| Schema DB dev | `check_schema` khi BE khởi động lại sau ALTER |
| FE | `.\dev.ps1 typecheck`, vitest; Chrome headless + subagent chấm |

## Status

- 18/10/2026: plan mở.
- Pha 1: hai cột trên `questions`; khoá ngoại `bank_question_id` đặt `use_alter` và tên
  `fk_questions_bank_question_id`, vì `bank_questions.question_id` trỏ ngược lại và hai bảng không
  dựng được theo thứ tự nào. ALTER DB dev 18/10/2026 (`pg_dump` trước, `aiafa-before-viec17.sql` trong
  scratchpad), BE khởi động lại, `check_schema` qua. `question_bank.choose` lọc câu (404 câu của người
  khác, bỏ qua câu đã có theo hai chiều chép), trần số câu kiểm ở route vì `drafting` đã import
  `question_bank`; `take_into` chép, mỗi câu một ô `ready` (`job_id` `bank:<id>`), nâng
  `brief.question_count` -- `harvest` coi ô vượt con số này là ô cũ. Câu `bank` đọc ra `in_bank`: xoá
  nó khỏi đề không xoá ngân hàng. 9 test, xanh trên sqlite và `aiafa_test`; bộ BE 656.
- Review pha 1 (commit được, không lỗi phải sửa), sửa: đề trống còn ô hỏng thì dọn ô trước
  (`drop_failed_slots_of_empty`, như khi dùng lại đề trống) để câu ngân hàng đầu là *Câu 1*; brief
  khoá và đọc lại như `fire`; `drafting.too_many` tính từ số cao nhất của ô **hay** câu (đề seed có câu
  mà không có ô từng nhận quá trần); `QuestionRead.source` là `Literal`; docstring duyệt và `in_bank`.
  Thêm 5 test: vượt trần, ô hỏng của đề trống, xoá câu ngân hàng (dòng ở lại, brief bớt một, hộp chọn
  mở lại), hộp chọn không lộ ngân hàng người khác, sửa câu giữ `source`. 14 test.
