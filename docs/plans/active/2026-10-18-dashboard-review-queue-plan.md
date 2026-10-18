# Đợt 4, cụm 4 — Bảng theo dõi: hàng đợi review và điểm gộp theo lớp (việc 19, 21)

## Goal

Làm việc 19 và 21 của `2026-10-18-deterministic-batch-master-plan.md`: màn *Bảng theo dõi* của rail
có thân thật. Gồm:
- hàng đợi *Cần bạn xem*: báo cáo *giải thích chưa rõ* gom theo đề, và câu có tỉ lệ sai cao;
- điểm gộp theo lớp, chỉ tính đề đã hết hạn chữa;
- màn đọc báo cáo của một đề;
- màn đọc một câu có tỉ lệ sai cao;
- hộp đọc đoạn chat hỏi trợ lý của một học sinh.

Cả ba màn đều **chỉ đọc**. Sửa lời giải chỉ làm ở *Ngân hàng câu hỏi* (22b), và câu đã nằm trong đề
đã phát hành không đổi.

## Người dùng chốt 18/10/2026 (sau buổi review Figma, khi mở plan này)

1. **Báo cáo gom theo đề**, không theo câu. `Report` gắn với cả lượt làm bài (ADR-19), nên hàng đợi có
   một dòng cho mỗi đề, và màn 25 là màn của cả đề. Figma 20 và 25 vẽ lại.
2. **"Đánh dấu đã xem" tính theo đề**: mọi báo cáo chưa xem của đề ấy được đánh dấu. Báo cáo đến sau
   đó làm đề vào lại hàng đợi.
3. **Link "Mở hội thoại hỏi trợ lý ›"** mở một hộp chỉ đọc đoạn chat pha 2 của lượt làm bài ấy. Hộp
   này vẽ thêm vào Figma.
4. **Tỉ lệ sai cao:**
   - ngưỡng ≥ 70% sai ở lần làm đầu, và cỡ mẫu **trên 20 bài**;
   - tính khi bài kiểm tra **đã hết giai đoạn 2**, không tính lúc bài đang diễn ra, vì 70% của 20 bài
     có thể không còn là 70% khi đủ 50 bài;
   - câu ở lại hàng đợi cho tới khi giáo viên đánh dấu đã xem.

## Scope

- **Trong phạm vi:**
  - schema:
    - `reports.resolved_at`: đánh dấu đã xem, theo đề;
    - `questions.wrong_rate_seen_at`: đã xem một câu có tỉ lệ sai cao;
    - ALTER idempotent trên DB dev;
  - BE, module mới `be/teacher_board.py`:
    - `GET /teacher/board`: hàng đợi cộng điểm gộp;
    - `GET /teacher/board/reports/{assessment_id}`: báo cáo của một đề;
    - `POST /teacher/board/reports/{assessment_id}/seen`;
    - `GET /teacher/board/questions/{question_id}`: một câu có tỉ lệ sai cao;
    - `POST /teacher/board/questions/{question_id}/seen`;
    - `GET /teacher/board/chat/{report_id}`: đoạn chat của lượt có báo cáo ấy;
  - FE:
    - màn 20 *Bảng theo dõi* có hai bảng và hai biểu đồ;
    - màn 25 *báo cáo của một đề*;
    - màn 29 *một câu có tỉ lệ sai cao* (số 26–28 đã có artboard đăng nhập);
    - hộp đọc đoạn chat;
    - nút *Chỉnh sửa trong Ngân hàng câu hỏi* mở 22b;
  - Figma:
    - vẽ lại 20 và 25;
    - artboard 29;
    - hộp đọc đoạn chat (artboard 25b);
  - tài liệu: ADR-34, ADR-35; hậu ký ADR-07, ADR-08, ADR-19, ADR-28; `data-model.md`;
    `teacher-surface.md`.
- **Ngoài phạm vi:**
  - sửa câu trong đề đã phát hành: không bao giờ làm;
  - chặn học sinh hay lượt làm bài vì có báo cáo (ADR-19: không chặn);
  - xếp nặng nhẹ các dòng trong hàng đợi (ADR-08).

## Files

| Đường dẫn | Việc |
| --- | --- |
| `packages/schema/src/schema/models.py` | hai cột |
| `services/be/src/be/teacher_board.py` (mới), `main.py` | route đọc, hai route *đã xem* |
| `services/be/tests/test_teacher_board.py` (mới) | test BE |
| `services/fe/src/api.ts`, `App.tsx` (`boardFor`), `screens/teacher/Dashboard.tsx`, `BoardReports.tsx`, `BoardQuestion.tsx` (mới), `teacher.css`, `teacher.test.tsx` | FE |
| `docs/decisions/adr-34-*`, `adr-35-*` (mới), `adr-07`, `adr-08`, `adr-19`, `adr-28`, `README.md`, `docs/overview/data-model.md`, `teacher-surface.md` | tài liệu |

## Ordered Tasks

### Pha 0 — Figma
- [x] 1. Vẽ lại artboard 20: dòng báo cáo mang tên đề, không mang câu. Cột thứ hai thành *NỘI DUNG*.
  Dòng tỉ lệ sai giữ *Câu k · đề bài* và đề gốc. Phụ đề ghi rõ điểm gộp quy về thang 10.
- [x] 2. Vẽ lại artboard 25 thành màn của một đề:
  - trái: các câu học sinh báo cáo làm sai, mỗi câu kèm link *Chỉnh sửa trong Ngân hàng câu hỏi*;
  - phải: thẻ từng báo cáo;
  - *Đánh dấu đã xem* cho cả đề.
- [x] 3. Artboard 29 *Câu có tỉ lệ sai cao*: câu chỉ đọc, tỉ lệ chọn từng phương án ở lần đầu, hai nút.
- [x] 4. Hộp đọc đoạn chat (từ dòng *Mở hội thoại hỏi trợ lý*).

### Pha 1 — schema và BE
- [x] 5. Model và ALTER:
  ```sql
  ALTER TABLE reports ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
  ALTER TABLE questions ADD COLUMN IF NOT EXISTS wrong_rate_seen_at TIMESTAMPTZ;
  ```
- [x] 6. Hàng đợi:
  - mỗi đề có báo cáo chưa xem là một dòng (*x lượt báo cáo*);
  - mỗi câu có tỉ lệ sai cao chưa xem là một dòng (*x% bài sai*). Câu chỉ vào khi:
    - đề của nó đã hết giai đoạn 2 ở mọi lớp còn giữ đề;
    - có trên 20 bài nộp;
    - tỉ lệ sai ở lần đầu ≥ 70%;
  - không xếp nặng nhẹ (ADR-08). Thứ tự xếp: báo cáo mới nhất trước, rồi tới tỉ lệ sai.
- [x] 7. Điểm gộp theo lớp, chỉ tính đề đã hết hạn chữa ở lớp ấy. Mỗi lớp có:
  - số đề;
  - trung bình, cao nhất, thấp nhất của **bài**, quy về thang 10;
  - mục kiến thức có tỉ lệ sai lần đầu cao nhất.

  Kèm thêm năm mục kiến thức có tỉ lệ sai cao nhất trên mọi lớp.
- [x] 8. Báo cáo của một đề:
  - mỗi báo cáo gồm học sinh, lớp, giờ, lời ghi và các câu em ấy làm sai;
  - các câu bị báo cáo, kèm `bank_id` để mở 22b;
  - *đã xem* đặt `resolved_at` cho mọi báo cáo chưa xem của đề.
- [x] 9. Một câu có tỉ lệ sai cao: câu, tỉ lệ chọn từng phương án, `bank_id`; *đã xem*.
- [x] 10. Đoạn chat của một báo cáo: `chat_messages` của lượt ấy. Chỉ giáo viên chủ đề; của người khác
  là 404 (ADR-22).
- [x] 11. Test BE trên sqlite và `aiafa_test`.

### Pha 2 — FE
- [ ] 12. Màn 20: hai bảng, hai biểu đồ. Hàng đợi rỗng là tin tốt, không vẽ như lỗi (ADR-08).
- [ ] 13. Màn 25, màn 29, hộp đọc đoạn chat; route trong `boardFor`.
- [ ] 14. Vitest; chụp, đo so với Figma; subagent chấm.

### Pha 3 — đóng
- [ ] 15. ADR-34, ADR-35, các hậu ký, `data-model.md`, `teacher-surface.md`; roadmap việc 19, 21
  *Xong*; backlog; tick plan tổng; plan sang `completed/`.

## Decision Records

### Decision 1: điểm gộp qua nhiều đề quy về thang 10
options considered: trung bình điểm thô; quy về thang 10; trung bình tỉ lệ đúng.
selected option: mỗi bài quy về thang 10 (`điểm / số câu × 10`), rồi mới gộp.
reason: điểm của một đề là tổng trên số câu (ADR-16), nên đề 6 câu và đề 10 câu không cộng được với
nhau. Màn 11 vẫn in thang của từng đề; chỉ màn gộp quy đổi, và phụ đề nói rõ điều đó.

### Decision 2: *hết giai đoạn 2* là mọi lớp còn giữ đề đã qua hạn chữa
options considered: tính theo từng lớp; tính khi mọi lớp đã qua hạn chữa.
selected option: tính khi mọi lớp còn giữ đề đã qua hạn chữa. Tỉ lệ cộng trên mọi bài của đề.
reason: một câu là một câu cho mọi lớp. Tính sớm theo lớp đầu tiên kết thúc là đúng cái hại người dùng
đã chỉ ra: tỉ lệ của một mẫu nhỏ hơn.

## Validation Checks

| Kiểm | Lệnh |
| --- | --- |
| Python, repo checks | `.\dev.ps1 test`, `.\dev.ps1 check` |
| Postgres | `pytest services/be/tests --postgres-url=…/aiafa_test` |
| Schema DB dev | `check_schema` khi BE khởi động lại sau ALTER |
| FE | `.\dev.ps1 typecheck`, vitest; Chrome headless + subagent chấm |

## Status

- 18/10/2026: plan mở; người dùng chốt bốn câu ở trên.
- Pha 0, Figma: artboard 20 vẽ lại -- dòng báo cáo mang tên đề và số học sinh, không ghi lớp; cột
  *NỘI DUNG*; phụ đề *"Điểm quy về thang 10 trước khi gộp"* (`657:4135`, `657:4133`, `657:4130`,
  `I657:4140;657:49/50`, `I657:4160;657:49/50`). Artboard 25 thành màn của một đề (`657:4265`): trái
  các câu học sinh báo cáo làm sai, mỗi câu một link *Chỉnh sửa trong Ngân hàng câu hỏi*; phải thẻ báo
  cáo có dòng *"Làm sai: …"*; một nút *Đánh dấu đã xem*. Mới: `29 · Câu có tỉ lệ sai cao` (`699:5667`),
  `25b · Đọc đoạn chat hỏi trợ lý` (`699:5826`, hộp `699:5916`).
- Pha 1: `be/teacher_board.py`, sáu route; ALTER DB dev (`pg_dump` trước, `aiafa-before-viec19.sql`
  trong scratchpad). Review pha 1, sửa: *đã xem* chỉ đánh dấu các báo cáo màn 25 đã hiện
  (`report_ids`) -- báo cáo đến trong lúc giáo viên đang đọc ở lại; sổ điểm đọc bằng join tới lần
  phát hành sống và `GROUP BY`, không bằng danh sách id (asyncpg dừng ở 32767 tham số); một mẫu số cho
  các phương án, kèm `unanswered`; thang của một bài là số câu của đề; hoà tỉ lệ lấy tên đứng trước;
  dòng báo cáo không ghi lớp. 14 test, xanh trên sqlite và `aiafa_test`.
- BE tự nạp lại (`--reload`) treo hai lần trong cụm này (`WinError 10038`, uvicorn trên Windows);
  khởi động lại tay. Ghi vào backlog.
