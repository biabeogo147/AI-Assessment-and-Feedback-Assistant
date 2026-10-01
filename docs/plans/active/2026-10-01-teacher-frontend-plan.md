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
- [ ] **Bước 4 — vòng lặp lượt + artboard 2.** `pending` → `turns`, `Thinking` hai variant,
      `ActionResultCard`. Thêm `Document` + tải lên + liệt kê trước khi dựng rail. Cổng đo artboard 2.
- [ ] **Bước 5 — artboard 3.** `ask_clarify`, `choices`, rehydrate sau F5.
- [ ] **Bước 6 — artboard 6.** `Panel`, `QuestionCard`, `SourceChip`, `provenance.ts`.
- [ ] **Bước 7 — sửa Figma ô giờ, rồi artboard 7.** `PublishSettings`, `preview`, hộp xác nhận, thất
      bại một phần.
- [ ] **Bước 8 — tài liệu.** ADR-04 (*FE đang giả vờ thi hành*), ADR-22 (*"chưa có màn hình nào của
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

- [ ] `.\dev.ps1 check` và `.\dev.ps1 test` xanh sau **mỗi** bước
- [ ] 11 test học sinh xanh sau bước 0 và bước 2, **không sửa một dòng test nào**
- [ ] Mỗi artboard xong thì **đo**: `get_metadata` + `get_variable_defs` từ Figma, `getComputedStyle`
      + `getBoundingClientRect` từ Chrome ở 1440×900, so bằng bảng. Lệch 0px ở mọi số nguyên; ≤1px
      chỉ cho ba cột 118.667. font-size, padding, gap, radius, màu: khớp tuyệt đối.
- [ ] `grep` hex thô trong code giáo viên phải rỗng
- [ ] Ba phép đo không phải pixel: vùng câu hỏi cuộn còn `panel-head` và `Publish settings` thì không;
      đỉnh `fade` trùng chân thẻ đầu; và 113 + 304 + 483 = **900**, dư bằng không
- [ ] Bốn test FE: giờ gửi lên có offset chứ không phải `Z`; hộp xác nhận chỉ in chuỗi từ response
      `preview`; `turns` append mà bubble giáo viên không nhân đôi; `tool_result` của
      `teacher.publish` ra Action result card chứ không ra bubble lời model
- [ ] Một lượt chạy thật end-to-end **qua giao diện** trên Postgres với `gpt-4o-mini`
- [ ] Luật Figma **có** áp lần này: artboard nào bị sửa phải nói ra trong commit
- [ ] Mỗi commit mang trailer `Plan: 2026-10-01-teacher-frontend-plan.md`

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

Xong bước 0, 1, 1b, 2. Bước 0 và bước 2 là hai commit **không thêm tính năng nào**, có chủ đích: nếu
`ACTOR` đổi hình dạng mà 11 test đỏ, tôi muốn biết điều đó khi diff chỉ có `api.ts`. Cả hai cổng đã
qua đúng như thế: 11/11 xanh mà `git diff` của `App.test.tsx` rỗng.

Bước 2 mang thêm `isoWithOffset` và **năm test cho riêng nó** — sớm hơn bước 7, nơi nó được dùng. Lý
do là nó đứng một mình được: một hàm thuần không cần màn hình nào để kiểm, và đột biến dấu offset làm
đúng năm test đó đỏ. Đó là test FE thứ nhất trong bốn test mà mục *Validation Checks* đòi.

Bước 3 xong, và nó sửa ba điều plan nói sai:

**Bề mặt giáo viên không có dải trên cùng.** Plan viết `TeacherBar`; artboard 1 có một **rail 260px
bên trái**, và không artboard nào trong mười hai cái in tên hay mã giáo viên — kiểm bằng cách quét
mọi text node của page. Hệ quả thẳng: `GET /api/teacher/me` dựng ở bước 1 **chưa có chỗ nào vẽ**. Nó
ở lại (có test, và màn đăng nhập thật sẽ cần) nhưng lý do trong plan là lý do sai, và đó đúng là thứ
docstring của chính nó cảnh báo: *"một field không ai vẽ là một field sẽ lệch trong im lặng"*.

**Gần cả rail đang trơ, và nó trơ lộ liễu.** Bốn đích đến là bốn artboard chưa dựng; danh sách đoạn
chat là chữ bịa vì BE có đúng **một** luồng cho mỗi giáo viên (`GET /teacher/chat` không nhận id
nào); tài liệu chờ bước 4. Chúng dồn vào `invented-not-from-be.ts` — tên file tự tố cáo, và dựng
bằng `div` chứ không `button`, vì một `button` hứa một việc không xảy ra.

**Density tách bằng một thuộc tính, không phải hai.** Plan định `data-surface` cộng `data-density`;
nay mode `Teacher` viết lại ngay trên `.teacher` trong `teacher.css`. Bề mặt nào thì density ấy, và
hai thuộc tính cho một quyết định là hai thứ sẽ lệch nhau.

Phép đo artboard 1: **mọi hộp khớp**, sau khi sửa một lỗi thật mà con mắt không thấy — ba loại hàng
trong vùng cuộn bị flex **co lại**, hàng đoạn chat cao 26.56 thay vì 40. Phần lệch còn lại đều ≤0.5px
và đều cùng một nguồn: Figma làm tròn chiều cao text **lên số nguyên** (11px × 1.5 = 16.5 hiện thành
17), còn trình duyệt thì không. Bề rộng của chip chữ lệch ≤1.6px vì metric glyph, không vì CSS.

Cửa sổ Chrome đang maximize nên `resize_window` không ăn; khung 1440×900 được ép bằng CSS trước khi
đo. Thứ duy nhất phép đo này không kiểm là `height: 100vh`.
