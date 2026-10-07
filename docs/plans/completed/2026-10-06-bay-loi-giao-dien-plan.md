# Plan — Bảy lỗi giao diện, và nơi thi hành của từng cái

## Context

Lượt thử tay ngày 06/10/2026 kết thúc bằng bảy chỗ hỏng do người dùng chỉ ra, cộng một chỗ
tôi tìm thấy khi đọc dữ liệu của nó. Tôi đã đo cả bảy trên trình duyệt thật trước khi viết
plan này, nên dưới đây là số đo chứ không phải suy đoán:

- **Màn 6.5 còn sống.** Mở một đề đã phát hành từ thẻ: `.panel` có ba con —
  `panel-head`, `panel-questions`, `panel-foot` — với CTA `"Phát hành đề"`. Gốc ở
  `Chat.tsx:396`: `onOpen` của thẻ luôn đi `/de/{id}`, **không bao giờ** `/phat-hanh`,
  còn `Panel.tsx:201` chỉ dựng `PublishSettings` khi `publishing && locked`. Một cú bấm
  không mua gì cả.
- **Biểu mẫu phát hành ăn 73% panel.** Panel cao 911: head 139, `panel-questions`
  **111**, `publish-settings` **661,5**. Nội dung câu hỏi cần 569 ⇒ giáo viên thấy
  **19,5%** đề của mình.
- **Icon của `Rail destination` thấp hơn title đúng 2px.** Hộp `.icon` ở y 122→134 (tâm
  **128**), `<svg>` bên trong ở y 124→136 (tâm **130**), chữ title tâm **128,05**. Lý do
  đọc được từ computed style: svg là `display: inline` + `vertical-align: baseline`, và
  **không có** dòng CSS nào cho `.rail .destination .icon svg`. Figma đúng vì ở Figma icon
  là một frame 12×12, không có baseline nào.
- **Dấu `$` lọt ra màn.** Câu 3 của đề *"Đề hàm số bậc hai…"* có bốn phương án dạng
  `"$ (1, 8) $"` — khoảng trắng ngay sau dấu mở và ngay trước dấu đóng. `MathText.MATH`
  **cố ý** từ chối hình dạng ấy (luật pandoc, mua bằng ca `Một quyển 20$, hai quyển 40$`),
  nên cả chuỗi in nguyên văn: đếm được **8** dấu `$` trong `.panel-questions`.
- **Đổi tên đoạn chat chết, và `Xoá` chết cùng một đường.** `Rail.tsx:84` đóng menu ở
  `pointerdown` rồi miễn trừ cho `closest(".conversation")`, nhưng menu đã chuyển sang
  `createPortal(document.body)` để thoát stacking context — nên `closest(".conversation")`
  trả **null**. Dựng lại bằng chuỗi sự kiện thật: sau `pointerdown` thì
  `menuStillThere: false`, `itemConnected: false`, và `click` rơi vào một node đã tháo.
  `input.rename` không bao giờ xuất hiện. BE hoàn toàn lành: `PATCH
  /api/teacher/conversations/{id}` có thật, sống, và `openapi.json` kể tên nó.
- **Pane crop/expand chưa từng được dựng.** `.pane-head` là `DIV`, `cursor: auto`, không
  handler nào, `.caret` có `transform: none`. Cái mũi nhọn đang hứa một việc không tồn tại.
- **Hai phương án trùng nhau từng byte.** Câu 3: `A "$ (1, 8) $"` và `B "$ (1, 8) $"`,
  `is_correct` chỉ bật ở **B**. Học sinh chọn A bị chấm sai cho đúng cái đáp án đúng.
  `harvest()` chống trùng **stem giữa các câu**; không chỗ nào chống trùng **phương án
  trong một câu**.

**Kết quả mong muốn:** không màn hình nào bắt bấm thêm một cú vô nghĩa; biểu mẫu phát hành
nhường chỗ cho đề khi giáo viên muốn đọc đề; mọi thứ bấm được đều bấm được thật; và hai lỗi
dữ liệu trên có nơi thi hành chứ không chỉ có một dòng prompt.

## Global Constraints

- Tiếng Việt cho chuỗi ra màn hình, comment và docs; identifier và log tiếng Anh.
- **Figma đổi trước** mọi thay đổi FE, chứng minh bằng **đo** (`get_metadata` ↔
  `getBoundingClientRect`), không bằng mắt.
- Mỗi luật mới phải **đỏ đúng test của nó** khi đột biến một dòng.
- `.\dev.ps1 check`, `test`, `typecheck` xanh trước khi tuyên bố xong.
- **Không lượt model nào.** Cả bảy việc đo được bằng DOM và dữ liệu đã có trong database.
- Xin phép trước khi gọi subagent và trước khi commit.
- Không tắt BE/AGENT/FE khi chưa được nói. AGENT không watch file và `uvicorn --reload`
  có thể treo — kiểm bằng `openapi.json` trước mỗi lượt đo.

## Files

| File | Việc |
|---|---|
| `services/fe/src/screens/teacher/Panel.tsx` | `locked` ⇒ `PublishSettings`; bỏ prop `publishing`, bỏ nhánh `panel-foot` của `locked` |
| `services/fe/src/screens/teacher/Chat.tsx` | bỏ `onPublish`/`onUnpublish`; sửa chỗ đóng menu ở `pointerdown` |
| `services/fe/src/App.tsx` | bỏ hậu tố route `/phat-hanh`, nhưng vẫn ăn link cũ |
| `services/fe/src/screens/teacher/PublishSettings.tsx` | thành tấm trượt từ lề dưới: thu / bung |
| `services/fe/src/screens/teacher/Rail.tsx` | `Pane` có nấc thu; `pane-head` thành nút |
| `services/fe/src/teacher.css` | luật svg cho cả rail; hình khối hai nấc của tấm trượt và của pane |
| `services/fe/src/MathText.tsx` | `MATH` nhận phần đệm trong cặp dấu |
| `services/be/src/be/drafting.py` *(hoặc nơi `validate_question` đang ở)* | ADR-18 chặn hai phương án trùng |
| `tools/check_contract.py` | check thứ 13: trong rail, mọi `svg` có nơi định cỡ |
| `docs/overview/teacher-surface.md` | bảng chân panel đang **sai** (còn `Phát hành thêm lớp`); thêm luật tấm trượt và luật pane |
| `docs/decisions/adr-18-*.md` | luật trùng phương án |
| Figma `mOe2ZmrqOq1Uix45v6PNGD` | `Publish settings` hai variant; `Pane` thêm variant thu |

## Ordered Tasks

### Pha 0 — Figma trước, và chờ duyệt

Người dùng chốt: *"update lên figma để tôi duyệt trước"*. Đây là **cổng**, không phải một
bước làm cho đủ lệ — hai câu hỏi hình khối dưới đây quyết định bằng mắt trên Figma chứ
không quyết định trong code:

- [x] `Publish settings` thành **tấm trượt neo lề dưới**, hai variant:
      `Trạng thái=bung` (như hiện nay, cộng một thanh đầu có tay cầm và mũi nhọn chỉ
      xuống) và `Trạng thái=thu` (chỉ còn thanh đầu dính mép dưới panel).
- [x] Câu phải duyệt: lúc **thu** thì phần câu hỏi **giãn ra lấp chỗ** hay biểu mẫu **nổi
      lên che** nội dung? Đã vẽ cả hai, cạnh nhau, kèm số đo — frame `519:1603`, đặt ngay
      dưới artboard 7. **A**: câu hỏi 735/900, thanh đầu nằm trong dòng xếp, không pixel
      nào của đề bị che. **B**: câu hỏi 787/900 — hơn A đúng 52px, nhưng 52px ấy nằm vĩnh
      viễn dưới thanh đầu, nên cuộn tới đáy thì dòng cuối nằm sau tấm trượt. *Chờ duyệt.*
- [x] `Pane` (ngăn `ĐOẠN CHAT` / `TÀI LIỆU`) thêm `Trạng thái=thu`: `.caret` quay 90°,
      vùng cuộn biến mất, ngăn co về đúng chiều cao thanh đầu. Ba nấc dựng ở frame
      `521:1767`: mở cả hai (337 / 235), thu `TÀI LIỆU` (545 / 27), thu cả hai (27 / 27,
      thanh kéo biến mất). *Chờ duyệt.*
- [x] **Và ghi chú `129:2` đã đặc tả việc này từ lâu** — bốn luật, trong đó luật 2 viết
      đúng cái người dùng báo: *"Thu gọn là thao tác **CHÍNH**, kéo là tinh chỉnh. Bấm
      tiêu đề khung để đóng cả khung."* Ghi chú tự nói rằng những luật ấy **chỉ** tồn tại
      ở đó, vì rail được sao chép theo artboard chứ không phải component. Không dòng code
      nào dựng nó.
- [x] Mặc định khi mở màn 7 là **bung** — người dùng đã chốt, nên Figma để `bung` làm
      variant mặc định.

**Không** đụng FE cho hai mục này tới khi bạn duyệt. Các pha 1, 3, 4, 5 không phụ thuộc
cổng này nên chạy song song được.

### Pha 1 — Màn 6.5 biến mất

Người dùng chốt: bỏ hẳn, theo **state** chứ không theo route.

- [x] `Panel.tsx`: `{publishing && locked ? …}` → `{locked ? …}`. Bỏ prop `publishing`
      khỏi chữ ký và khỏi docstring. Nhánh `panel-foot` còn lại **chỉ** cho đề chưa duyệt,
      nên nút của nó thôi phải chọn giữa hai nhãn: luôn là `Duyệt đề`.
- [x] `Chat.tsx`: bỏ `onPublish` và `onUnpublish`. `onUnpublish` tồn tại **chỉ** để gỡ hậu
      tố `/phat-hanh` sau khi hoàn tác; không còn hậu tố thì không còn việc.
- [x] `App.tsx`: bỏ hậu tố `/phat-hanh` khỏi route. Vẫn **ăn** link cũ — regex bỏ qua một
      hậu tố `/phat-hanh` dư — vì một bookmark từ hôm qua không có lỗi gì; nhưng nó không
      còn mở ra một màn hình khác, nên nó thôi là một URL hứa hai thứ.
- [x] `Settle` thôi cần `tail`.
- [x] `docs/overview/teacher-surface.md`: bảng chân panel ở dòng ~325–330 **đang sai** —
      nó còn kể trạng thái *đã phát hành* mời `Phát hành thêm lớp`, một nút đã xoá từ đợt
      trước, và câu chữ thật là *"Đề đã tới học sinh. Muốn sửa thì hoàn tác trước."*. Bảng
      rút về **một** dòng (chưa duyệt → `Duyệt đề`) cộng một câu nói rằng đề đã khoá thì
      panel mở thẳng cài đặt phát hành.

**Nơi thi hành:** hai test FE mở một đề `approved` và một đề `published` **không** qua hậu
tố route nào, khẳng định `.publish-settings` có mặt và `.panel-foot` **không**. Cộng một
test rằng bấm `Duyệt đề` làm biểu mẫu hiện ra tại chỗ — bản cũ đo `onPublish` có được gọi
không, tức đo **cách** đi tới, nên nó vẫn xanh khi đích đến không hiện ra.

Đo đột biến (`{locked ? (` → `{locked && false ? (`): **8** test đỏ, gồm cả ba test trên.

Phép so theo nhãn `Phát hành đề` **không dùng được** và đó là một bài học của chính đợt
này: chuỗi ấy cũng là nút chính **của biểu mẫu**, nên một test viết theo chữ bắt nhầm chỗ.
Phải đo `.panel-foot`.

**Khác plan:** `goInstead` trong `App.tsx` mất caller cuối cùng — nó sinh ra **chỉ** để
thay mục lịch sử khi gỡ hậu tố sau lúc hoàn tác — nên nó và 7 test của nó đã xoá. Và mọi
stub `fetch` phục vụ một đề đã duyệt nay phải trả cả `/publish-form`, vì panel khoá dựng
biểu mẫu ngay: 8 test đỏ vì chuyện đó trước khi stub được sửa.

### Pha 2 — Tấm trượt từ lề dưới *(Figma đã duyệt 06/10/2026)*

- [x] `PublishSettings` nhận một nấc `thu` / `bung` và một thanh đầu bấm được:
      `<button>` mang `aria-expanded`, nhãn đọc được, mũi nhọn quay theo nấc.
- [x] Mặc định **bung**. Nấc không cần sống qua F5 — biểu mẫu vốn **không gợi sẵn giờ
      nào** (ADR-02), nên một lần F5 đã là một lần bắt đầu lại; nhớ nấc mà không nhớ giờ
      là nhớ nửa vời.
- [x] Hình khối lấy đúng số đo của variant đã duyệt — `517:17` ở **density Teacher**:
      420×52 trên Figma, 420×51,5 trên trình duyệt. Con số ấy **không** nằm trong CSS: nó
      là `16 + 19,5 + 16`, nên sửa một trong ba thì nó tự đi theo.
- [x] **Và chỗ này đã sai một lần.** Tôi lấy 53 từ một bản clone vẫn mang density của trang
      Components (chữ 14px/21), trong khi bề mặt giáo viên định nghĩa lại `--type-label`
      thành 13px và artboard 7, 8 đã đè chữ theo density ấy từ trước. Phép đo trên trình
      duyệt bắt được; Figma đã sửa theo. Đúng cái bẫy mà `teacher.css` đã ghi sẵn một ghi
      chú cảnh báo — *"đọc số từ artboard, không đọc từ trang Components"*.
- [x] Người dùng duyệt mà không chọn A hay B, nên đi theo **A** (câu hỏi giãn ra) — số đo
      của chính frame `519:1603` nói giúp: A cho 735/900 không che pixel nào, B cho 787/900
      nhưng 52px nằm vĩnh viễn sau thanh đầu, và muốn đọc dòng cuối thì lại phải đệm đúng
      52px ấy, tức vòng về A qua một đường dài hơn.

**Nơi thi hành:** bốn test FE. Mở ra là bung và `aria-expanded` nói ra nấc; bấm thanh đầu
thì năm ô nhập **rời khỏi cây DOM** (không `hidden` — tab vào một thứ không thấy là một cái
bẫy); bấm lại thì bung ở đúng chỗ ấy. Và một test cho **chính phương án A**: tấm trượt là
con trực tiếp của `.panel`, đứng **sau** `.panel-questions`.

Đo đột biến: `if (!open)` → `if (false)` ⇒ 1 đỏ; `aria-expanded={open}` → `{true}` ⇒ 1 đỏ;
bọc `PublishSettings` vào một `<div className="sheet-layer">` — tức dựng đúng cấu trúc mà
phương án B cần ⇒ đỏ **đúng** test phương án A. Đó là điểm của test ấy: jsdom không đo được
pixel nào, nhưng quan hệ cha–con là chỗ hai phương án thật sự khác nhau.

**Đã đo trên trình duyệt thật** (06/10/2026, đề đã phát hành `d3f40a77`): bung thì vùng câu
hỏi **94/911** (10,3%) và phải cuộn (`scrollHeight` 569 so `clientHeight` 94); thu thì
**720,5/911** (79,1%) và `scrollHeight` = `clientHeight` = **721** — tỉ lệ về đúng 1, không
còn phải cuộn, đúng tiêu chí đặt ra ở trên. Tổng ba khối `139 + 720,5 + 51,5` = **911** khít
đúng, nên không khối nào che khối nào: phương án A đo được, không phải A nói ra.

### Pha 3 — Hai thứ bấm được mà không bấm được

- [x] **Menu `⋯`.** `Rail.tsx` đổi chỗ miễn trừ thành
      `closest(".conversation, .row-menu")`. Đây là một lỗi **đã từng được lý giải sai**:
      comment nói chọn `pointerdown` để *"click của chính mục menu nổ sau"* — đúng ý,
      nhưng cái portal thêm vào sau đó đã cắt mất đường miễn trừ, và không test nào bắn
      `pointerdown` nên không ai thấy. Comment phải ghi lại đúng chuyện này.
- [x] **`Pane` thu được.** `.pane-head` thành `<button>` mang `aria-expanded`; thu thì
      `.scroll` biến mất và ngăn co về chiều cao thanh đầu.
- [x] **Nút tải lên không được lồng trong nút thu.** `action` của ngăn `TÀI LIỆU` là một
      `<button>`; một `<button>` trong một `<button>` là HTML không hợp lệ và trình duyệt
      tự tháo nó. Nên thanh đầu là một hàng chứa **hai** nút cạnh nhau, không phải một nút
      bọc mọi thứ.
- [x] **Thu ngăn `TÀI LIỆU` thì thanh kéo phải im.** `SPLIT_MIN` 120 giữ cho ngăn không
      biến mất; một ngăn đã thu thì con số ấy vô nghĩa, nên thanh kéo ẩn đi và chiều cao
      đã nhớ giữ nguyên cho lúc bung lại.
- [x] Nấc thu của **từng** ngăn sống qua F5 trong `localStorage`, cùng khuôn với
      `kriky.teacher.documents-height` đã có.

**Nơi thi hành:** một test FE bắn `pointerdown` **rồi** `click` lên mục `Đổi tên` và
khẳng định `input.rename` hiện ra — thứ tự sự kiện chính là cái bị hỏng, nên một test chỉ
gọi `click()` sẽ xanh một cách vô nghĩa, đúng như hôm nay. Cộng một test cho `Xoá`. Cộng
một test bấm `pane-head` và khẳng định vùng cuộn đi mất, cộng một test khẳng định nút tải
lên **không** nằm trong nút thu. Đột biến từng cái một.

Bốn test mới cho nửa pane, và mỗi cái đỏ đúng một đột biến: bỏ `{open && …}` quanh `.scroll`
⇒ 1 đỏ; bỏ class `thu` ⇒ 2 đỏ; `historyOpen && documentsOpen &&` → `true &&` ⇒ 1 đỏ; làm
`PANE_KEY` thôi đọc tham số `which` — tức hai ngăn dùng chung một cờ ⇒ 1 đỏ; chuyển `action`
vào trong `<button>` thu ⇒ 1 đỏ.

**Và lượt thử tay tìm thêm một lỗi mà không test nào thấy.** Thu `ĐOẠN CHAT` để ngăn tài
liệu đứng yên ở 225 và bỏ lại ~368px trắng dưới nó, trong khi thu `TÀI LIỆU` thì ngăn kia lấy
kín chỗ. Lỗi **chỉ** lộ ra ở một trong hai chiều — `.pane.history` là `flex: 1` nên chiều ấy
đúng miễn phí — và Figma vẽ đúng chiều đúng, nên không phép so hình nào thấy được. Sửa bằng
hai nửa: JSX thôi gửi chiều cao inline khi ngăn kia đã thu, và CSS cho
`.pane.history.thu ~ .pane.documents:not(.thu)` nhận `flex: 1`. Sau khi sửa: **27/568** và
**568/27**, tổng **595** = đúng chiều cao `.lists`. Mỗi nửa một đột biến: trả chiều cao inline
về như cũ ⇒ 1 test đỏ; bỏ luật CSS ⇒ check 14 FAIL.

**Khác plan — thêm một check, không chỉ test.** Hai cái bẫy của nấc thu nằm ngoài tầm jsdom:
`.pane.history` là `flex: 1` nên thu nó mà không đặt lại `flex` thì nó vẫn chiếm hết chỗ và
thanh đầu trôi giữa khoảng trắng; và `gap: 8px` giữa thanh đầu và vùng cuộn thành 8px đệm
chân khi vùng cuộn đi mất, làm ngăn cao 35 chứ không phải **27** của Figma. Nên **check thứ
14** đọc `teacher.css` và đòi cả `flex` lẫn `gap` trong `.rail .pane.thu`, cộng một luật
`.publish-settings.thu` cho tấm trượt. Đột biến: bỏ `flex` ⇒ FAIL; đổi tên luật của tấm
trượt ⇒ FAIL. Cùng khuôn với check 13 của Pha 4, và cùng một lý do.

### Pha 4 — 2px, và cả một lớp lỗi cùng loại

- [x] `teacher.css`: `.rail svg { display: block }` — chữa **lớp** lỗi chứ không chữa một
      chỗ. Trong rail, mọi `svg` đều là một icon nằm trong một hộp đã định cỡ, nên không
      cái nào được đứng trên baseline. `.caret` đang đúng chỉ vì nó có luật riêng; một
      icon mới thêm vào mai này sẽ lệch y như hôm nay.
- [x] Rà `.plus`, icon tải lên, `.kind` — cùng khuôn span-bọc-svg. `.caret` và icon tải lên
      có luật riêng chặt hơn nên giữ nguyên cỡ; `.plus` là chữ `＋`, không phải svg.
- [x] Đo lại: tâm icon và tâm chữ title phải trùng, sai số 0. **Đã đo** (06/10/2026, cả
      bốn đích đến): svg `122→134` tâm **128**, chữ title tâm **128** — lệch **0,00**, và svg
      lấp đúng cái hộp 12px. Trước: tâm svg 130 so title 128,05, lệch 2px.
- [x] **Và phải chữa chỗ trình duyệt không vào được dev server trước đã.** Bốn lượt thử thất
      bại với `ERR_CONNECTION_REFUSED` ở `localhost:5173` trong khi `curl` trả 200 ở đúng URL
      ấy. Nguyên nhân: Vite để `server.host` mặc định, chuỗi `localhost` phân giải ra `[::1]`
      nên server **chỉ** bind IPv6, còn trình duyệt phân giải `localhost` ra `127.0.0.1`
      trước. `vite.config.ts` nay ghim `host: "127.0.0.1"` — loopback, không phải
      `host: true`, vì `true` mở dev server ra cả mạng LAN.

**Nơi thi hành:** check thứ 13 trong `tools/check_contract.py` đọc `teacher.css` và đỏ khi
luật svg của rail vắng mặt. jsdom không dựng bố cục nên nó **không** đo được 2px này — và
đó chính là lý do lỗi sống tới giờ; bằng chứng thật là một lượt đo trên trình duyệt, ghi
vào kịch bản thử tay.

### Pha 5 — Hai lỗi của dữ liệu, mỗi cái một nơi thi hành

- [x] **`MATH` nhận phần đệm.** `$ (1, 8) $` là toán. Giữ nguyên chặn chữ số hai đầu —
      `40$` vẫn là tiền. Giá phải trả, ghi thẳng vào docstring: `"giá $ 5 và $ 7"` từ nay
      thành toán. Đề toán tiếng Việt hiếm viết thế, còn một phương án hiện ra kèm hai dấu
      `$` thì đang xảy ra thật.
- [x] **ADR-18 chặn hai phương án trùng.** Thêm vào `validate_question` — **một** bản
      kiểm, nên câu model viết và câu giáo viên sửa tay đi qua cùng một lưới. So sau khi
      chuẩn hoá khoảng trắng: `"$ (1,8) $"` và `"$(1,8)$"` là cùng một đáp án với học
      sinh, nên chúng phải là cùng một đáp án với cái lưới.
- [x] `docs/decisions/adr-18-*.md` nhận luật mới cùng lý do: một phương án trùng làm học
      sinh bị chấm sai cho đúng cái đáp án đúng — đo được trên dữ liệu thật ngày
      06/10/2026.
- [x] Dữ liệu đã có trong database **không** được sửa bằng tay: xoá database tạo lại là
      đường đã chốt cho local.

**Nơi thi hành:** ba test FE — `$ (1, 8) $` dựng ra KaTeX và không còn dấu `$` nào; `$  $`
**vẫn không** phải toán; phần đệm chỉ nhận dấu cách và tab, không nhận xuống dòng. Hai ca
mới trong `test_two_holes_the_old_net_let_through` cho luật BE. Đột biến đo riêng từng cái:
siết `MATH` về luật pandoc ⇒ đúng 1 test đỏ; tắt phép so phương án ⇒ đúng 2 test đỏ.

**Khác plan — luật hẹp hơn chỗ này từng hứa.** So sau khi **gộp** khoảng trắng liền nhau,
không xoá hẳn: `$ (1,8) $` và `$(1,8)$` dựng hình giống hệt nhau nên về lý vẫn lọt, nhưng
xoá hẳn thì `có 3 nghiệm` và `có 3nghiệm` thành một — hai chữ khác nhau. Lưới bắt ca đã
xảy ra thật, không hứa bắt mọi ca.

**Và nó bắt ngay sáu fixture trong chính bộ test**: mọi phương án nhiễu ở đó đều mang chữ
`"sai"`. Fixture phải sửa, không phải luật — một luật nhìn thấy được thứ nó sinh ra để
nhìn là một luật đang chạy.

### Pha 6 — Dọn

- [x] `docs/plans/active/2026-10-06-ba-trang-thai-the-plan.md` sang `completed/`: cổng của
      nó đã xanh và change set đã commit (`f01370a`).
- [x] Plan này nằm ở `docs/plans/active/2026-10-06-bay-loi-giao-dien-plan.md` với checkbox
      thật thà.

## Verification

- **Cổng:** `.\dev.ps1 check` (12 → **14** check) · `test` · `typecheck`.
- **Đột biến:** mỗi luật mới sửa một dòng cho sai, chạy lại, phải đỏ **đúng** test của nó.
- **Trình duyệt** (đo DOM, không chụp ảnh; **không** lượt model nào):
  - Mở đề `published` từ thẻ: một cú bấm tới cài đặt phát hành, không nút `Phát hành đề`.
  - Thu tấm trượt: `.panel-questions` cao bao nhiêu trên 911, so với **111** hôm nay.
  - `pointerdown`+`click` thật lên `Đổi tên`: input hiện ra, gõ tên mới, `PATCH` trả 200,
    hàng rail đổi chữ. Rồi `Xoá` mở được hộp xác nhận.
  - Bấm `pane-head` của cả hai ngăn: thu được, bung được, nhớ qua F5.
  - Tâm icon `Rail destination` trùng tâm chữ title.
  - Câu 3 của đề hàm số bậc hai: **0** dấu `$` trong `.panel-questions`.
- **Figma ↔ FE** so bằng số cho hai variant tấm trượt và variant thu của pane.
- **Kịch bản thử tay** (`docs/kich-ban-thu-tay-giao-vien.md`) nhận một lượt chạy mới với
  sáu con số trên.

## Status

**Xong cả sáu pha, và đã thử tay trên trình duyệt thật.** Cổng: `check` **14/14** ·
`pytest` **398** · `vitest` **143** · `typecheck` — xanh. Mỗi luật mới đỏ đúng test (hoặc
check) của nó dưới một đột biến một dòng.

**Không còn món nợ đo nào.** Lượt chạy ghi ở
`docs/kich-ban-thu-tay-giao-vien.md`, mục *"lượt ba"*, với số đo của cả bảy lỗi và **không**
một lượt model nào. Database giữ nguyên, vì chính nó là bằng chứng: câu 3 của đề `d3f40a77`
còn nguyên hai phương án trùng.

**Lượt thử tay tìm thêm một lỗi** (ngăn tài liệu không lấy chỗ trống khi ngăn kia thu) và
**sửa một con số tôi đã viết sai**: tấm trượt thu là 52 trên Figma / 51,5 trên trình duyệt,
không phải 53 — tôi đã đọc 53 từ một bản clone mang density của trang Components, đúng cái
bẫy mà `teacher.css` có sẵn một ghi chú cảnh báo. Figma đã sửa theo phép đo.

**Và một tai nạn đáng ghi**: một lệnh `git checkout services/fe/src/screens/teacher/Panel.tsx`
dùng để hoàn nguyên một đột biến đã xoá luôn phần sửa Pha 1 chưa commit của file ấy. Dựng lại
được đầy đủ, cổng xanh lại. Hoàn nguyên một đột biến trên cây làm việc còn thay đổi chưa
commit thì phải sao lưu file rồi chép lại, **không** dùng `git checkout`.
