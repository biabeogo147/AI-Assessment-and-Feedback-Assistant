# Giao diện giáo viên, dựng từ Figma

Plan bắt buộc theo `AGENTS.md`: đợt này chạm hai service, thêm một bảng, thêm endpoint, và sửa cả
file thiết kế.

## Goal

Giáo viên có màn hình. Năm pha rưỡi trước dựng xong đường ghi ở backend — soạn, duyệt, phát hành,
thu hồi — và tới giờ nó chỉ được kiểm bằng `pytest` và `curl`. Đợt này dựng artboard **1, 2, 3, 6,
7** của Figma `mOe2ZmrqOq1Uix45v6PNGD`, trong cùng `services/fe` với bề mặt học sinh, và **chứng minh
hai bên khớp bằng cách đo** chứ không bằng mắt.

## Scope

**Trong:** ba endpoint đọc cho giáo viên; model `Document` và đường tải lên; tái cấu trúc
`services/fe/src` để chứa hai vai; năm artboard; sửa chữ ô nhập giờ trên Figma.

**Ngoài, có chủ ý:**

- **Nhóm lớp** (artboard 9, 10, 11). Chúng cần thêm nhiều endpoint nữa và không có cái nào tồn tại.
- **Tài liệu thật sự giới hạn phạm vi ra đề.** Đợt này làm *tải lên, liệt kê, hiện trong rail, đính
  chip*. Việc nội dung tài liệu đi vào prompt của AGENT (đọc PDF, cắt đoạn, nhồi ngữ cảnh) là một
  phần lớn hơn hẳn. Ghi nợ — nếu không nói ra thì artboard 2 trông như đã xong trong khi nó mới xong
  phần vỏ.
- **Đổi tên `services/fe`.** Tên đó nay sai: nó là bề mặt học sinh **và** giáo viên. Đổi tên chạm
  `pnpm-workspace.yaml`, `dev.ps1`, `check_contract.py`, `AGENTS.md`, `local-development.md` — và
  `AGENTS.md` đang 175/175. Ghi nợ.
- **Vòng lặp chat của BE.** Người dùng đã chốt giữ nguyên thiết kế. `poll_delay` 500ms vẫn là mục mở.

## Bốn thứ chỉ tìm ra bằng đo

**1. Artboard giáo viên bind vào mode `Density` khác.** Đo trên `70:215`: `type/heading` **18**
(Student 20), `type/label` **13** (14), `type/caption` **11** (12). Màu thì **giống hệt** ở hai mode,
so từng hex — nên màu dùng chung an toàn, chữ phải tách.

**2. `toISOString()` sẽ làm sai giờ một cách im lặng.** Nó trả `Z`, mà `Z` vẫn aware nên BE **nhận**,
rồi `publication_wording._clock` in `strftime("%H:%M")` theo đúng tzinfo nhận được. Giáo viên gõ 14:00
và câu luật đáp lại *"tới hết 07:00"*. HTTP 200, không lỗi. Phải tự dựng offset từ
`getTimezoneOffset()`.

**3. `_note_publication` chỉ ghi các lớp thành công.** Nếu **mọi** lớp trượt thì không có gì vào
`teacher_turns` — nên FE phải tự hiện phần thất bại tại chỗ, không được chờ luồng chat nói hộ.

**4. `Question card` (`267:30`) có boolean `Sửa được`** — tắt ở artboard 7, bật ở artboard 6. Tức
**6 và 7 là cùng một panel ở hai trạng thái**, và FE suy nó từ `state` của BE chứ không tự quyết.

## Ordered Tasks

- [x] **Bước 0 — di chuyển, không thêm gì.** Năm màn học sinh vào `screens/student/`, sửa import ở
      `App.tsx` và `App.test.tsx`. Cổng: `tsc --noEmit` xanh và **11/11 test không sửa một dòng nào**.
- [x] **Bước 1 — ba endpoint đọc ở BE.** `GET /api/teacher/me`;
      `GET /api/teacher/assessments/{id}` (title, subject, grade, state, question_count,
      still_drafting, topic_scope từ `DraftBrief`, questions kèm options và methods);
      `GET /api/teacher/assessments/{id}/publications` (năm tham số mỗi lớp + hai câu note).
      Dùng lại `_owned(..., lock=False)` cho ADR-22. **Không** thêm khoá vào `publish-form` — test đã
      pin đúng 8 khoá, và test đó đang canh luật *"biểu mẫu không gợi sẵn giờ nào"*.
- [x] **Bước 1b** — endpoint thứ ba gọi **đúng** hai hàm trong `publication_wording`, và thêm một
      assert vào `test_the_timing_rules_read_identically_in_all_three_payloads`: ba nơi thành bốn.
- [x] **Bước 2 — `api.ts` hai vai.** `ACTOR` thành một record hai khoá, `call(role, path, init)`, vai
      chọn **tại chỗ gọi tên endpoint**. Cổng: 11/11 test vẫn xanh, không sửa test nào.
- [x] **Bước 3 — khung giáo viên + artboard 1.** `App.tsx` thành dispatcher; `TeacherBar`;
      `teacher.css` với `[data-surface="teacher"]`. Cổng đo artboard 1.
- [x] **Bước 4 — vòng lặp lượt + artboard 2.** `pending` → `turns`, `Thinking` hai variant,
      `ActionResultCard`. Thêm `Document` + tải lên + liệt kê trước khi dựng rail. Cổng đo artboard 2.
- [x] **Bước 5 — artboard 3.** `ask_clarify`, `choices`, rehydrate sau F5.
- [x] **Bước 6 — artboard 6.** `Panel`, `QuestionCard`, `SourceChip`, `provenance.ts`.
- [x] **Bước 7 — sửa Figma ô giờ, rồi artboard 7.** `PublishSettings`, `preview`, hộp xác nhận, thất
      bại một phần.
- [x] **Bước 8 — tài liệu.** ADR-04 (*FE đang giả vờ thi hành*), ADR-22 (*"chưa có màn hình nào của
      giáo viên"* nay sai), `backlog.md`, `local-development.md`, `architecture.md`,
      `services/fe/AGENTS.md` (đang 23/25 dòng, chật).

## Decision Records

### Decision: `ACTOR` thành một record, và vai được chọn tại chỗ gọi endpoint

options considered:

- **A. `ACTOR` là một record hai khoá; `call(role, path, init)` nhận vai; mỗi method khai vai của nó.**
- **B. Suy vai từ route (`location.hash.startsWith("/teacher")`).**
- **C. Một biến có setter (`setActor()`).**

selected option: A.

reason: B là thứ tôi viết đầu tiên, và nó hỏng ở một chỗ không nhìn ra khi đọc: một request bay ra
**giữa lúc chuyển route** sẽ mang sai vai, và triệu chứng là một 403 ở rất xa nguyên nhân. Repo này đã
trả giá hai lần cho đúng loại lỗi đó — effect tự nuôi mình ở `Tutor.tsx`, và `rollback` làm hết hạn
ORM. Rẻ khi viết, đắt khi gỡ.

C thì cho bất kỳ component nào đổi được app đang là ai, và trong vitest nó rò state giữa các case vì
không có setup file nào reset.

A đặt quyết định vào **chỗ duy nhất không thể sai**: `/api/teacher/*` vốn trả 403 với actor học sinh,
nên một dòng gắn sai vai là một dòng không chạy được ngay lần đầu, không phải một lỗi ngấm. Và câu
trong `services/fe/AGENTS.md` — *"`ACTOR` in `api.ts` is the stand-in for sign-in. One constant, one
call site to delete"* — **vẫn đúng từng chữ**, nên hợp đồng không phải sửa.

### Decision: `tokens.css` không đổi một byte; giáo viên thêm một lớp biến phạm vi

options considered:

- **A. `tokens.css` giữ nguyên. `teacher.css` khai lại các biến chữ dưới `[data-surface="teacher"]`,
  và `TeacherApp` bọc cây của nó trong một phần tử mang thuộc tính đó.**
- **B. Tách khối `:root` ra một file dùng chung, hai mode Density nằm cạnh nhau trong đó.**
- **C. Hai file token riêng, mỗi bề mặt một file.**

selected option: A.

reason: B là thứ plan đầu của tôi viết, và nó trả giá ở chỗ sai. Tách `:root` ra nghĩa là **mọi lần
tinh chỉnh cho giáo viên đều chạm vào một file mà bề mặt học sinh phụ thuộc** — một bề mặt đang chạy,
có người dùng, và **không test nào bắt được** vì jsdom không layout. A thì `tokens.css` không đổi một
byte, nên app học sinh **không thể** hỏng vì đợt này.

C mất phần đắt nhất: màu. Đo rồi, màu ở hai mode **giống hệt nhau từng hex** — hai bản sao của bảng
màu là hai bảng màu, và chúng sẽ lệch.

Custom property **kế thừa**, nên một rule dùng chung nằm ngoài wrapper vẫn nhận giá trị của giáo viên
khi phần tử nằm trong wrapper. Dùng thuộc tính `data-surface` thay vì class vì nó greppable (một chỗ
đặt), không đụng namespace class mà `tokens.css` đã dùng hết, và nó đọc lên như *"đây là bề mặt nào"*
chứ không như một theme.

**Rủi ro phải ghi ra:** cơ chế này sụp nếu hộp thoại render bằng portal ra `document.body` — nó rời
khỏi wrapper và mất bộ chữ. Repo hiện **không** dùng portal (`.scrim`/`.dialog` render inline trong
cây màn hình), nên luật thành: hộp thoại của giáo viên cũng render inline, và nếu có ngày dùng portal
thì `data-surface` phải lên `<html>`.

### Decision: Chip nguồn câu hỏi là dữ liệu bịa, nhận vào có điều kiện

options considered:

- **A. Một file `provenance.ts` chứa bản đồ cứng, tên tự tố cáo, mọi chip đọc từ đó.**
- **B. Bỏ chip khỏi đợt này.**
- **C. Thêm hai cột vào `Question` và một endpoint đánh dấu "đã kiểm".**

selected option: A (người dùng chốt).

reason: `Question` có năm cột và không cột nào nói nguồn hay trạng thái kiểm; `drafting._write` còn
không nối `DraftItem` với `Question` sau khi thu hoạch, nên ngay cả *"do model viết"* cũng không truy
được. Ba chip **không suy ra được từ bất cứ dữ liệu nào đang tồn tại**.

Nói thẳng cái giá: `services/fe/AGENTS.md` cấm một màn hình **suy ra** một luật; chỗ này nặng hơn một
bậc — nó **phát minh**. Một giáo viên đọc *"1 câu chưa kiểm"* sẽ tin rằng hệ thống biết câu nào chưa
ai đọc, và hệ thống không biết. **Màn hình này nói với giáo viên một điều mà hệ thống không biết là
đúng.**

Nhận vào với ba điều kiện: đúng một file chứa nó, **tên file tự tố cáo** (mọi `import` hiện dòng đó),
và dải chip tổng cùng chip trên từng thẻ đọc **cùng một bản đồ** nên chúng không thể nói ngược nhau.
Cộng một dòng `backlog.md` và một dòng trong mục *Nơi luật này đang được thi hành* của ADR-04 ghi rằng
FE hiện **giả vờ** thi hành nó.

## Files

| File | Việc |
| --- | --- |
| `services/be/src/be/teacher_routes.py` | ba endpoint đọc; dùng lại `_owned`, `_live_publications`, `publication_wording` |
| `services/be/src/be/models.py` | bảng `documents` |
| `services/be/tests/test_publishing.py` | thêm assert biến "ba nơi" thành bốn |
| `services/fe/src/api.ts` | `ACTOR` record, `call(role, …)`, type của ba endpoint mới, `isoWithOffset` |
| `services/fe/src/App.tsx` | dispatcher hai nhánh |
| `services/fe/src/teacher.css` | **mới** — `[data-surface="teacher"]` và hình khối của giáo viên |
| `services/fe/src/screens/student/` | **di chuyển** năm màn hiện có |
| `services/fe/src/screens/teacher/` | **mới** — `Chat`, `Panel`, `PublishSettings`, `parts`, `provenance` |
| `docs/decisions/adr-04`, `adr-22` | mục *Nơi luật này đang được thi hành* |
| `docs/plans/backlog.md` | ba món nợ: nguồn câu hỏi, tài liệu-vào-prompt, đổi tên `services/fe` |

## Validation Checks

- [x] `.\dev.ps1 check` và `.\dev.ps1 test` xanh sau **mỗi** bước
- [x] 11 test học sinh xanh sau bước 0 và bước 2, **không sửa một dòng test nào**
- [x] Mỗi artboard xong thì **đo**: `get_metadata` + `get_variable_defs` từ Figma, `getComputedStyle`
      + `getBoundingClientRect` từ Chrome ở 1440×900, so bằng bảng. Lệch 0px ở mọi số nguyên; ≤1px
      chỉ cho ba cột 118.667 (ba cột ấy nay không còn — xem bước 7). font-size, padding, gap, radius, màu: khớp tuyệt đối.
      **Ngưỡng này phải nới một lần, và lý do đo được:** Figma làm tròn chiều cao mỗi text node
      **lên** số nguyên (11px × 1.5 = 16.5 hiện thành 17), trình duyệt thì không. Nên mọi lệch còn
      lại ≤0.5px cho một dòng chữ, cộng dồn nhiều nhất 2px cho một thẻ nhiều dòng — và bề rộng chip
      chữ lệch ≤1.6px vì metric glyph, không vì CSS. Mọi con số **không** phải chiều cao text thì
      khớp đúng 0px.
- [x] `grep` hex thô trong code giáo viên phải rỗng
- [x] Ba phép đo không phải pixel: vùng câu hỏi là vùng cuộn **duy nhất** của panel; dải mờ cao
      đúng 56; và ba phần cộng lại đúng **900**, dư bằng không. Con số của phép thứ ba đổi theo bước
      7: 113 + 242 + 545 thay cho 113 + 304 + 483, vì ô `datetime-local` thật cao hơn ô vẽ
- [x] Bốn test FE: giờ gửi lên có offset chứ không phải `Z`; hộp xác nhận chỉ in chuỗi từ response
      `preview`; `turns` append mà bubble giáo viên không nhân đôi; `tool_result` của
      `teacher.publish` ra Action result card chứ không ra bubble lời model
- [x] Một lượt chạy thật end-to-end **qua giao diện** trên Postgres với `gpt-4o-mini`
- [x] Luật Figma **có** áp lần này: artboard nào bị sửa phải nói ra trong commit
- [x] Mỗi commit mang trailer `Plan: 2026-10-01-teacher-frontend-plan.md`

## Node id của mọi artboard giáo viên

Mục này trước đây tên là *"Cần người dùng cấp"*, và nó không còn cần nữa. `get_metadata` chỉ liệt kê
được `0:1 Foundations` vì Figma **nạp page theo nhu cầu** và nó chỉ thấy page đang mở; `use_figma`
chạy Plugin API thì đọc `figma.root.children` và thấy cả sáu page. Một lệnh đọc, hết chặn.

Page `Screen — Teacher` là `12:2`, mười hai artboard:

| # | Artboard | node-id |
| --- | --- | --- |
| 1 | Bắt đầu — đoạn chat mới | `12:3` |
| 2 | Kèm tài liệu, giới hạn phạm vi | `85:327` |
| 3 | Kriky hỏi lại trước khi làm | `69:159` |
| 4 | Kriky đang làm | `84:421` |
| 5 | Đã có đề nháp | `12:46` |
| 6 | Soi từng câu trong panel | `15:55` |
| 7 | Đã duyệt — cài đặt phát hành | `70:193` (panel bên phải là `70:215`) |
| 8 | Xác nhận phát hành | `72:256` |
| 9–12 | Lớp học, chi tiết lớp, kết quả, lời giải | `180:753`, `183:874`, `205:1000`, `309:1415` |

## Status

**Xong cả tám bước.** Bề mặt giáo viên chạy được từ đầu tới cuối: nói với Kriky, đọc lại hội thoại,
tải tài liệu, mở panel một đề, duyệt, rồi phát hành cho nhiều lớp qua một hộp xác nhận.

Một lượt chạy thật qua giao diện, trên Postgres với `gpt-4o-mini`, một tin nhắn: model tự gọi
`create_draft` rồi `start_drafting`, hai thẻ kết quả hiện ra kèm câu an toàn, bong bóng của giáo viên
**không** nhân đôi, ô nhập khoá rồi mở lại, và nút *Xem* mở panel đúng đề vừa tạo với
`topic_scope` đọc từ `DraftBrief`. Lượt phát hành thì chạy không tốn một lời gọi model nào: chọn lớp,
sáu tham số, xem trước, xác nhận, và nhận lại một dòng từ chối thật của BE.

### Bốn thứ đo được mà plan không đoán trước

1. **`border` của CSS không phải `stroke` của Figma.** Figma vẽ stroke `INSIDE` nên padding đo từ mép
   ngoài; CSS cộng border rồi mới tới padding. Năm thẻ lệch một pixel, rồi ba vạch ngăn của panel ăn
   mất một pixel bề rộng. Không ai nhìn ra; chỉ phép đo thấy.
2. **Ba lần trùng tên class với `tokens.css`** — `.mark`, `.composer`, `.thread`, rồi `.row`. Một
   class trùng tên **cộng vào** chứ không ghi đè, nên `.row` của học sinh làm mỗi hàng ô giờ cao thêm
   34px. Nay `services/fe/AGENTS.md` cấm thẳng.
3. **`preview` từng nói dối.** Một lớp đã qua giờ mở được xem trước báo `published: true` rồi lần gửi
   thật mới từ chối, vì `_publish_one` thoát sớm trước khi kiểm `_already_running`. Đây là lần thứ
   **tư** trong dự án một lượt chạy thật tìm ra thứ không test nào bắt.
4. **Thiết kế hứa bốn thứ hệ thống không biết**: số trang tài liệu, phạm vi *"chương 1, trang 30–62"*,
   phần giải thích cho mỗi lựa chọn, và ba ô giờ 118.67px. Cả bốn đã được sửa **trên Figma**, không
   phải lách trong code.

### Thứ vẫn chưa thật

Chip nguồn câu hỏi là **chữ bịa** — `Question` không có cột nào nói nguồn hay việc đã kiểm. Nó nằm
trong đúng một module tên tự tố cáo, canh bằng `check_invented_data_lives_in_one_file`, và ADR-04 nay
ghi thẳng rằng FE đang *giả vờ* thi hành luật ấy. Năm món nợ còn lại nằm trong `docs/plans/backlog.md`,
mỗi món kèm thứ đang chặn nó.

229 pytest, 21 vitest, 7 repo check, 2 import contract xanh.
