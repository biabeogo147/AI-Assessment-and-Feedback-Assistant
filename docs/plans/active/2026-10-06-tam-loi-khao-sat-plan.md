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
| `tools/check_contract.py` | check thứ 11 (bộ khôi phục được nối dây); check thứ 9 nới ra giữ ba lời từ chối |
| `services/be/src/be/publication_wording.py` | ba hằng `FAULT_*` |
| `services/be/tests/test_publishing.py` | ghim khúc nối ba field với ba hằng |
| `services/fe/src/api.ts`, `teacher.css`, `teacher.test.tsx` | kiểu, hình, và lưới |
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

- [x] Figma: ba thẻ xếp chồng trong một khối Kriky — thẻ của model, rồi hai biên bản
- [x] `spoken()` đổi mốc sang **phép nhìn trước**: có plan thì câu cuối trước plan là lời
      mở, không plan thì câu trước bước đầu tiên (B5 + B7)
- [x] `cardTurn()` → `cardTurns()`: thẻ của model **cộng** mỗi việc giáo viên một thẻ
      (B6, ADR-24); ADR-25 được sửa vì luật một-thẻ của nó bị nới
- [x] `onUnpublish` song sinh với `onPublish`, cộng `goInstead` thay vì đẩy mục (E15)
- [x] Review subagent, và sửa cả hai lỗi correctness nó tìm ra

### Pha 3 — hai biểu mẫu (D11, E13, E14)

- [x] Figma: cột radio trong `Question card — đang sửa`; biến thể `cửa sổ thời gian sai` ở
      `Publish settings`
- [x] Radio đáp án đúng, ô nhãn lỗi ẩn ở phương án đang đúng (D11), cộng một cú chặn
      tiếng Việt khi còn nhiễu chưa có nhãn
- [x] `aria-pressed` cho chip lớp (E13)
- [x] Ba câu của `_schedule_fault` thành hằng BE, FE hiện trước cú bấm (E14)
- [x] Mở rộng check thứ 9: ba câu FE hiện phải là ba hằng BE khai
- [x] Review subagent, và sửa cả bảy phát hiện có thật của nó

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

Cả ba pha **xong**. Pha 1 và pha 2 đã commit (6 commit); pha 3 chờ commit.

Mỗi pha có một subagent review, và **cả ba lần review đều tìm được lỗi thật trong chính
bản sửa** — không lần nào là nghi thức:

- **Pha 1:** cả file test bị CRLF hoá, chôn 82 dòng thật trong một diff 4810 dòng;
  `learning_objective` không đi qua bộ khôi phục trong khi docstring nói "mọi field chữ";
  chữ model nói trong khung chat đi cùng ống JSON mà chưa ai sửa; thiếu plan và ADR theo
  hợp đồng; ba docstring BE còn kể về một lưới đã gỡ.
- **Pha 2:** `cardTurns` nuốt mất thẻ của model khi giáo viên duyệt trong cùng khối —
  dựng lại đúng cái bug `chot-chang-a-plan` đã sửa; và lấy `plan` làm mốc duy nhất làm
  hỏng ca **không có plan**, đảo thứ tự đọc đã chốt.
- **Pha 3:** radio xoá `error_label` nên bấm xong là một đường thẳng tới 422 **tiếng
  Anh**, và cái xoá ấy làm mất chữ giáo viên đã gõ; mốc *giờ nộp cuối* ở FE không có lưới
  nào (đột biến xanh); hai trong ba lời từ chối không có test; khúc nối ba field với ba
  hằng ở BE không ai gác; `Number(minutes)` ngoài khoảng cho ra `[object Object]`.

Ngoài phạm vi plan này, đã ghi vào `docs/plans/backlog.md`: chữ model nói trong khung chat
giáo viên đi cùng ống JSON (**đã sửa trong pha 1**); `vet_plan` cho lọt một id là chuỗi số
trần; chất lượng toán model sinh ra.
