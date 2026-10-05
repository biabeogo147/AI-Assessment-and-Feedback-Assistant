# Tám lỗi từ đợt khảo sát 05/10/2026

## Context

Một lượt chạy tay trên trình duyệt — BE, FE và AGENT thật, data vừa seed — tìm được 16 lỗi.
Người dùng chọn làm **tám**, và gạt ra ngoài những món cần sửa prompt hoặc cần họ nhúng tay
vào harness của agent.

Gốc rễ của phần nặng nhất đã đo tới byte: đề bài trong database chứa `0x0C`, `0x09`, `0x08`
thay cho `\frac`, `\times`, `\bigg`. Đầy đủ lý lẽ nằm ở **ADR-26**; plan này chỉ thi hành.

Ba điều đã xác minh trước khi viết plan, và chúng làm plan rẻ hơn dự tính:

- `OptionEdit.is_correct` **đã có** ở `services/be/src/be/teacher_routes.py:1421`, và PATCH đã
  dựng lại `GeneratedQuestion` rồi gọi `validate_question` để giữ ADR-18 → **D11 là lỗ thuần FE**.
- `_schedule_fault(wanted, now) -> str` ở `teacher_routes.py:681` đã là một hàm thuần trả về
  đúng ba câu tiếng Việt → **E14 đi theo khuôn đã dựng đợt trước**: BE trả câu, FE hiện trước
  cú bấm. `.trouble` với `role="alert"` đã có sẵn chỗ hiện (`PublishSettings.tsx:238`).
- PATCH câu hỏi **cũng** dựng `GeneratedQuestion` → đặt bộ lọc ở tầng `packages/contracts` sẽ
  sửa luôn chữ giáo viên tự gõ. Chỗ đúng là **ranh giới structured-output của agent**.

**Kết quả mong muốn:** dữ liệu mới sinh ra sạch; dữ liệu đã hỏng thì giáo viên **nhìn thấy**
chỗ hỏng mà sửa; ba lỗ ở dòng lượt nói, biểu mẫu sửa câu và biểu mẫu phát hành được bịt.

## Global Constraints

- Tiếng Việt cho chuỗi ra màn hình, comment và docs; identifier và log tiếng Anh.
- Figma và code đổi **cùng một change set**, chứng minh bằng đo, không bằng mắt.
- Mỗi luật mới phải **đỏ đúng test của nó** khi đột biến một dòng.
- Ngân sách model: cả ba pha dùng **một** lượt `gpt-4o-mini`.
- `.\dev.ps1 check`, `test`, `typecheck` phải xanh trước khi tuyên bố xong.
- Gọi một subagent review sau mỗi pha.

## Files

| File | Việc |
|---|---|
| `services/agent/src/agent/latex_escapes.py` | MỚI — bộ khôi phục theo từ điển lệnh |
| `services/agent/src/agent/graphs/authoring.py` | `_unmangled()`, gọi trong `_write` |
| `tools/check_contract.py` | check thứ 11, đọc cây cú pháp của `_write` |
| `services/fe/src/screens/teacher/Panel.tsx` | `MANGLED`, `visible()`, dòng `.mangled`; radio đáp án đúng |
| `services/fe/src/screens/teacher/Chat.tsx` | mốc plan trong `spoken()` |
| `services/fe/src/screens/teacher/ActionCard.tsx` | `cardTurns()` trả nhiều thẻ |
| `services/fe/src/screens/teacher/PublishSettings.tsx` | `aria-pressed`, chặn cửa sổ thời gian |
| `services/fe/src/MathText.tsx` | docstring trỏ vào symbol đã xoá |
| `services/be/src/be/agent_gateway.py`, `teacher_routes.py` | docstring kể một lưới đã gỡ |
| `dev.ps1`, `.pre-commit-config.yaml` | `PYTHONIOENCODING` cho `lint-imports` |
| Figma `mOe2ZmrqOq1Uix45v6PNGD` | `Question card — đang sửa`, thẻ kết quả, `Publish settings` |

## Ordered Tasks

### Pha 1 — ADR-26 (A1–A4, F16)

- [x] `latex_escapes.py`: từ điển, luật ranh giới, luật ≥4 chữ sau xuống dòng
- [x] `test_latex_escapes.py`: 20 test, gồm ba ca "phải giữ nguyên"
- [x] `_unmangled()` trong `authoring.py`, phủ **cả sáu** field chữ
- [x] Check thứ 11 bằng `ast`, không bằng grep
- [x] Dòng `.mangled` trong `Field`, giá trị ô nhập không đổi
- [x] Figma: node `mangled` trong `Question card — đang sửa`
- [x] `MathText.tsx` + ba docstring BE thôi kể về lưới toán đã gỡ
- [x] `dev.ps1` + pre-commit: `PYTHONIOENCODING`
- [x] Review subagent, và sửa sáu phát hiện của nó

### Pha 2 — dòng lượt nói và đường lùi (B5, B6, B7, E15)

- [ ] Figma: trạng thái **hai thẻ xếp chồng** trong một khối Kriky
- [ ] `spoken()` đổi mốc từ `steps.length` sang "đã gặp lượt `plan` chưa" (B5 + B7)
- [ ] `cardTurn()` → `cardTurns()`: mọi lượt `byTheTeacher` đều lên thẻ (B6, ADR-24)
- [ ] `onUnpublish` song sinh với `onPublish`, hash rụng đuôi `/phat-hanh` (E15)
- [ ] Review subagent

### Pha 3 — hai biểu mẫu (D11, E13, E14)

- [ ] Figma: cột radio trong `Question card — đang sửa`; trạng thái cảnh báo ở `Publish settings`
- [ ] Radio đáp án đúng, ô nhãn lỗi ẩn ở phương án đang đúng (D11)
- [ ] `aria-pressed` cho chip lớp (E13)
- [ ] Ba câu của `_schedule_fault` thành hằng BE, FE hiện trước cú bấm (E14)
- [ ] Mở rộng check thứ 9: ba câu FE hiện phải là ba hằng BE khai
- [ ] Review subagent

## Validation Checks

- `.\dev.ps1 check` — 11 check, `lint-imports` KEPT cả hai hợp đồng.
- `.\dev.ps1 test` — pytest và vitest.
- `.\dev.ps1 typecheck`.
- **Đột biến:** mỗi luật mới sửa một dòng cho sai, chạy lại, phải đỏ **đúng** test của nó.
- **Trình duyệt** (đo DOM, không chụp ảnh — tab ẩn làm `captureScreenshot` treo): một lượt
  soạn `gpt-4o-mini`, rồi `psql` dump hex xác nhận không còn `0c`/`09`/`08`; đếm thẻ của
  khối `approve`+`unapprove` phải ra **hai**; bấm radio rồi lưu, `psql` xác nhận `is_correct`
  đã chuyển dòng.
- **Figma ↔ FE** so bằng số: `get_metadata` và `getBoundingClientRect()`.

## Decision Records

### Decision: đặt bộ khôi phục ở `services/agent`, không ở `packages/contracts`

options considered: (a) `field_validator` trên `GeneratedQuestion` ở `packages/contracts`;
(b) một hàm trong `services/agent`, gọi ngay sau `ainvoke`.

selected option: (b).

reason: `packages/contracts/AGENTS.md` nói "Data only. No thresholds, no scoring, no routing,
no I/O" — bộ khôi phục là hành vi. Và nặng hơn: `be/teacher_routes.py:1555` dựng lại chính
`GeneratedQuestion` cho đường PATCH của giáo viên, nên (a) sẽ sửa cả chữ **giáo viên tự gõ**
— một bề mặt đoán mò đặt đúng vào cổng người của ADR-05. Hỏng hóc sinh ra ở ranh giới
structured-output nên nó được chữa ở đúng ranh giới ấy.

### Decision: check thứ 11 đọc cây cú pháp, không grep chuỗi

options considered: (a) grep `_unmangled(` trong file; (b) `ast.walk` thân hàm `_write` tìm
một `ast.Call`.

selected option: (b).

reason: đo được — bản (a) **không đỏ** khi gỡ lời gọi, vì chuỗi `_unmangled(` khớp luôn dòng
`def _unmangled(`. Một luật không đỏ khi bị vi phạm thì không phải luật.

### Decision: `PYTHONIOENCODING` đặt trong `dev.ps1` chứ không chỉ trong pre-commit

options considered: (a) để nguyên, coi là chuyện của riêng pre-commit; (b) vá cả `dev.ps1`.

selected option: (b).

reason: `rich` nhìn stdout — nối console thì nói UTF-8, nối **pipe** thì rơi về bộ render cũ
và chết trên cp1252. Lỗi encode xảy ra **sau** khi check đã chạy, nên nó nuốt kết quả thật và
trả exit 1 bất kể hợp đồng còn hay vỡ. Đo được: `.\dev.ps1 check 2>&1 | ...` báo đỏ trong khi
cả hai hợp đồng KEPT. Một cổng báo đỏ khi mọi thứ đúng sẽ dạy người ta bỏ qua nó.

## Status

Pha 1 **xong**, gồm cả sáu phát hiện của review. Pha 2 và pha 3 chưa bắt đầu.

Ngoài phạm vi plan này, đã ghi vào `docs/plans/backlog.md`: chữ model nói trong khung chat
giáo viên (`propose.py` → `_Proposal.text` → `MathText`) đi cùng một ống JSON mà **chưa** được
khôi phục; `vet_plan` cho lọt một id là chuỗi số trần; chất lượng toán model sinh ra.
