# Plan 2b — Chip bốn trạng thái, và một kênh nói khi nó đổi

## Context

Plan 2a làm cho `documents.state` nói đúng bốn trạng thái của ADR-27 và đẩy chúng ra tới
`GET /api/teacher/documents`. Nhưng **không ai nhìn thấy**: chip trên rail vẫn đúng một hình
dạng — `kind`, tên tệp, kích thước — và `Chat.tsx:171` fetch thư viện **đúng một lần**, lúc
mount, deps `[]`.

Nghĩa là hôm nay một bản SGK chụp lại vẫn trông y hệt một cuốn sách dùng được. Đó là thứ ADR-27
gọi tên: *"Một chip trông dùng được mà chưa dùng được là một chip nói dối."*

Plan này là **nửa còn lại của C11**, và là plan cuối của đợt không có một lời gọi model nào.

**Kết quả mong đợi:** tải một PDF scan lên, chip đi từ *đang xử lý* sang *không đọc được chữ*
**ngay trên màn hình, không cần F5**, kèm một câu giáo viên đọc được; và nó không kéo thả được
vào ô chat.

## Scope

**Trong:** Figma `Document chip`; một kênh SSE cho thư viện tài liệu; `Rail.tsx` + `teacher.css`
+ `api.ts`; cổng kéo thả; một check đếm nấc; FE kiểm kích thước trước khi gửi.

**Ngoài:** mục lục, chương, chunk (plan 3); Jev (plan 4); nội dung vào prompt (plan 5); ranh
giới giữa hai process của BE (plan 2c).

## Decision Records

### Decision: SSE, không phải poll

**options considered:** (a) poll 2 giây, tự dừng khi hết `processing` · (b) **một kênh SSE** ·
(c) chỉ fetch lại sau mỗi lần tải lên.

**selected option:** (b).

**reason:** tôi đã khuyên (a) dựa trên một phép đo — ba tệp đi hết vòng trong **1,2 giây** — và
người dùng bác đúng chỗ phép đo ấy mỏng: *"nhìn thì đơn giản nhưng nó không chỉ xong trong 2s
đâu, nếu người dùng upload theo batch, nếu hệ thống có nhiều người dùng và gây nghẽn queue thì
con số 2s sẽ tăng lên."*

Đúng. 1,2 giây là đường sướng trên một máy rảnh với ba tệp. Một giáo viên kéo cả bộ sách vào thì
`services/document` xử lý tuần tự, và thời gian chờ **không có trần**. Poll 2 giây cho một việc
kéo dài vài phút là ba mươi request mỗi phút mỗi giáo viên, cho một thứ hầu hết thời gian không
đổi. Nhịp poll đúng phụ thuộc vào tải — tức không có nhịp nào đúng.

(c) bị bác vì nó để lại đúng cái chip nói dối mà plan này tồn tại để xoá.

### Decision: kênh chỉ **hích**, không chở dữ liệu

**options considered:** (a) event chở nguyên `DocumentRead` · (b) **event chỉ nói "thư viện của
bạn vừa đổi", FE gọi lại `GET /api/teacher/documents`.**

**selected option:** (b).

**reason:** repo này **đã học bài này một lần rồi**, và bài học nằm nguyên trong `drafting.py`:
*"Chuông **không phải một bộ đếm**: một vị trí thử lại rung thêm một lần cho cùng số thứ tự, và
một tiếng chuông có thể mất. Số câu đã soạn phải đếm từ database."* Lý do kỹ thuật cũng ghi ở
đó: *"pub/sub của Redis **không giữ lịch sử**"*.

Nếu event chở dữ liệu thì một event mất = một chip sai **vĩnh viễn**. Nếu event chỉ hích thì
event sau sửa luôn cái trước, và một lần mở lại kênh cũng sửa — nó **tự lành**. Giá phải trả là
một lời gọi `GET` mỗi lần đổi, mà đó là một truy vấn theo `teacher_id` trên một bảng nhỏ.

### Decision: một channel cho mỗi **giáo viên**, không phải mỗi tài liệu

**options considered:** (a) `documents:{document_id}` · (b) **`documents:{teacher_id}`**.

**reason:** rail vẽ **cả thư viện**, không vẽ từng tài liệu rời. (a) bắt FE subscribe N channel
và huỷ đăng ký khi một tài liệu xong — N lần phức tạp cho cùng một thông tin. (b) là một
subscription cho một màn hình đang mở.

`teacher_id` lấy bằng `update(...).returning(Document.teacher_id)` trong `be/ingest.py` — một
câu lệnh, không thêm một `SELECT`. Payload `DocumentProbed` **không** nhận thêm trường
`teacher_id`: `services/document` không cần biết tài liệu thuộc về ai, và thêm vào là bắt nó
cầm một thứ nó không dùng.

### Decision: `fetch` + reader, không phải `EventSource`

**options considered:** (a) `EventSource` · (b) **`fetch` + `body.getReader()`**.

**selected option:** (b).

**reason:** `EventSource` **không gửi được header tuỳ ý**, mà cả ứng dụng này xưng danh bằng
`X-Actor` (ADR-10/ADR-13). Dùng (a) thì danh tính phải chui vào query string — một định danh
nằm trong URL, đi vào mọi access log.

Và (b) **đã có sẵn trong repo**: `api.ts:675` và `api.ts:838` đều đọc `text/event-stream` bằng
đúng vòng lặp ấy. `api.ts:766` còn ghi thẳng lý do không dùng `EventSource` cho đường kia.

**Kèm một việc dọn:** vòng lặp tách khung SSE hiện **đã có hai bản sao**. Bản thứ ba là lúc phải
rút nó ra một hàm. Đây là *dùng lại*, không phải *thêm mới*.

### Decision: bốn trạng thái trên **ba** màu của design system

**options considered:** (a) thêm màu thứ tư vào Foundations · (b) **ba màu, hai trạng thái xấu
dùng chung một màu** · (c) dùng `accent` cho một trạng thái.

**selected option:** (b).

**reason:** Foundations đã chốt **ba** token trạng thái, và ghi lý do ngay trên frame:
*"Trạng thái — ba màu cùng trọng lượng, **cố ý không xếp hạng nghiêm trọng**"*. (c) bị cấm
thẳng: *"Accent — chỉ cho hành động chính, **không dùng cho trạng thái**"*.

Ánh xạ:

| ADR-27 | token | vì sao |
|---|---|---|
| đang xử lý | `state/processing` | đúng nghĩa đen |
| sẵn sàng | `state/settled` | việc đã ngã ngũ |
| không đọc được chữ | `state/needs-human` | giáo viên phải làm gì đó |
| xử lý hỏng | `state/needs-human` | giáo viên phải làm gì đó |

Hai trạng thái xấu chung màu nhưng **khác chữ**, và chữ mới là chỗ phân biệt: một cái là phán
quyết (*tệp này là ảnh scan*), một cái là một lần không trả lời được (*thử tải lại*). Tô chúng
hai màu là xếp hạng nghiêm trọng — đúng thứ Foundations từ chối làm.

### Decision: dòng trạng thái là **nhãn cố định**, `fault` xuống tooltip

**options considered:** (a) chip in thẳng `fault` từ API · (b) **chip in một nhãn cố định theo
trạng thái, `fault` đi vào `title`** · (c) rút gọn `fault` ở BE xuống còn hai câu.

**selected option:** (b), người dùng chốt 08/10/2026.

**reason:** bản đầu của plan này cho chip in `fault`, và nó sai về kích thước lẫn về vai trò.
Về kích thước: câu đầy đủ xuống dòng ở cột 165px, nên chip phình lên **96px** — đo trên Figma.
Về vai trò: `fault` có **sáu** giá trị khác nhau (ba cho `no_text_layer`, ba cho `failed`), và
chúng là *chẩn đoán*, không phải *nhãn*.

Nay chip in hai câu người dùng chốt — *Không đọc được chữ* và *Xử lí lỗi. Hãy tải lại* — lấy từ
bảng `CHIP` của FE, và chip về **78px**, bằng đúng chiều cao trạng thái *đang xử lý*.

`fault` **không mất**: nó đi vào thuộc tính `title` của chip, nên rê chuột vẫn đọc được *"Tệp
PDF này không có trang nào"* hay *"Không mở được tệp PDF này"*. (c) bị bác vì rút gọn ở BE là
xoá khả năng chẩn đoán khỏi **cả log lẫn database**, không chỉ khỏi màn hình.

**Code BE không đổi một dòng nào vì quyết định này.**

### Decision: chip cao theo nội dung, không ghim 56px

**reason:** `teacher.css:586` ghim `.rail .document { height: 56px }`, trong khi variant thứ ba
của Figma cao **78px** vì nó có dòng thứ ba. Ba trong bốn trạng thái cần dòng ấy. Đổi sang
`min-height`, nên chip *sẵn sàng* vẫn 56px và ba cái kia tự cao lên.

Hệ quả nhìn thấy được, và nó **đáng có**: lúc một tài liệu đi từ *đang xử lý* sang *sẵn sàng*,
chip co lại một nhịp. Đó là phản hồi, không phải nhiễu.

### Decision: chỉ `ready` mới kéo thả được

**reason:** ADR-27 nói thẳng: *"Không có trạng thái đang xử lý thì giáo viên kéo một chip chưa
sẵn sàng vào ô chat và nhận một câu từ chối khó hiểu — màn hình đã có đủ thông tin để nói trước,
chỉ là không nói."* Hôm nay `Rail.tsx:263` đặt `draggable` cho **mọi** chip.

## Files

| File | Việc |
| --- | --- |
| Figma `Document chip` (`84:25`) | Thuộc tính `Trạng thái` đổi từ ba variant hiện tại (`đọc được`, `đọc được — 2`, `đang đọc` — chúng nói về **tải lên**, không về cổng text layer) sang **bốn** variant đúng từ vựng ADR-27; dòng meta thành `kích thước · số trang` |
| Figma artboard `1` và `2` | Instance chip cập nhật theo |
| `services/be/src/be/ingest.py` | `returning(Document.teacher_id)`, rồi publish một hích lên `documents:{teacher_id}` qua `ctx["redis"]` |
| `services/be/src/be/teacher_documents.py` *(hoặc một module kề)* | `GET /teacher/documents/stream` — khuôn `open_bells` của `drafting.py`: context manager, subscribe tại `__aenter__` |
| `services/be/src/be/drafting.py` | rút `_bells_from`/`open_bells` thành thứ dùng lại được, hoặc nhân một bản có chủ đích — **quyết định lúc đọc code**, không đoán trước |
| `services/fe/src/api.ts` | `TeacherDocument` + `state`, `page_count`, `fault`; rút vòng tách khung SSE thành một hàm (bản sao thứ ba); `teacher.watchDocuments()` |
| `services/fe/src/screens/teacher/Rail.tsx` | `ChipState` union + bảng `CHIP`; `draggable={one.state === "ready"}`; dòng meta |
| `services/fe/src/screens/teacher/Chat.tsx` | mở kênh trong `useEffect`, đóng khi unmount; kiểm `file.size` trước khi gửi |
| `services/fe/src/teacher.css` | `height` → `min-height`; ba token trạng thái |
| `services/fe/src/teacher.test.tsx` | test chip bốn trạng thái, cổng kéo thả, kiểm cỡ |
| `tools/check_contract.py` | check đếm nấc, **so hai ngôn ngữ** (dưới) |
| `docs/kich-ban-thu-tay-giao-vien.md` | G7–G10 từ "đọc bằng API" thành "nhìn bằng mắt" |
| `docs/overview/architecture.md` | kênh SSE thứ hai, và nó là kênh đầu tiên của **giáo viên** |

## Ordered Tasks

- [x] **1. Figma trước.** Bốn variant đúng từ vựng ADR-27, dòng meta `kích thước · số trang`.
      Dọn luôn variant trùng tên `đọc được — 2`. Cập nhật instance trên artboard 1 và 2.
- [x] **2. Đo Figma.** Ghi lại số đo từng variant — cao, padding, cỡ chữ, token màu — để task 6
      có cái đối chiếu. **Không** code trước bước này.
- [x] **3. BE: hích.** `ingest.py` publish sau khi `UPDATE` thành công, dùng `returning`. Lỗi
      publish chỉ **log**, không ném: hàng đã ghi rồi, và một kênh gãy không được biến một job
      đã xong thành một job thử lại.
- [x] **4. BE: kênh.** `GET /teacher/documents/stream`, theo khuôn `open_bells`. Mỗi hích là một
      khung `data:` một dòng, đúng khuôn `_as_sse` của `teacher_chat.py`.
- [x] **5. FE: đường ống.** `api.ts` — ba field mới, hàm tách khung dùng chung, `watchDocuments`.
      `Chat.tsx` mở/đóng kênh, và fetch lại mỗi lần nghe hích.
- [x] **6. FE: chip.** `ChipState` + bảng `CHIP`, CSS, cổng kéo thả. Đo lại và so với task 2.
- [x] **7. FE: kiểm cỡ trước khi gửi.** Món nợ của plan 1.
- [x] **8. Check đếm nấc.** Chi tiết dưới.
- [x] **9. Test.** `teacher.test.tsx`, và test BE cho kênh.
- [x] **10. Tài liệu.** Hai file ở bảng trên.

## Validation Checks

**Cổng của plan này — đo trên hệ thật, năm process cộng `fe`:** tải một PDF scan lên và **nhìn**
chip đi từ *đang xử lý* sang *không đọc được chữ* **mà không chạm F5**; kéo thử chip ấy vào ô
chat, nó không đi.

**Cổng Figma:** số đo của chip trên trình duyệt khớp số đo đã ghi ở task 2 — cao, padding, cỡ
chữ, màu. Khớp **bằng số**, không bằng mắt.

**Check đếm nấc, và nó làm một việc không service nào tự làm được:** so union `ChipState` trong
`Rail.tsx` với `DocumentState` trong `packages/contracts/src/contracts/documents.py` — **hai
ngôn ngữ, cùng một bảng từ vựng**. Nó đỏ vào đúng ngày BE thêm trạng thái thứ năm mà FE không
vẽ, hay FE đổi tên một nấc. Khuôn lấy từ `check_the_result_card_has_exactly_three_states`: đếm
union, đếm bảng `CHIP`, bắt hai cái khớp nhau, và từ chối dựng giao diện bằng một chuỗi `if`
trên `state`.

Test phải có:

- **Bốn trạng thái, bốn hình dạng** — mỗi cái một test, và mỗi test khẳng định **chữ** giáo viên
  đọc được, không khẳng định tên class.
- **Nhãn đúng cho từng trạng thái**, lấy từ bảng `CHIP` — không phải từ `fault`.
- **`fault` nằm trong `title`**, và hai `fault` khác nhau cho ra hai tooltip khác nhau trong
  khi nhãn trên chip vẫn y hệt. Đây là test duy nhất giữ `fault` khỏi biến mất khỏi FE.
- **`page_count: null` thì không in "0 trang"** — in mỗi kích thước.
- **Chỉ `ready` mới `draggable`.**
- **Nghe một hích thì gọi lại `GET /api/teacher/documents`** — và đây là test duy nhất khẳng
  định kênh chỉ hích chứ không chở dữ liệu.
- **Kênh gãy không làm vỡ màn hình**: rail vẫn vẽ thư viện đã fetch lúc mount.
- **`file.size` quá trần thì không có request nào rời trình duyệt.**

**Đột biến:**

- Thêm một nấc thứ năm vào `ChipState` → check đếm nấc đỏ.
- Đổi `ready` thành `done` chỉ ở FE → check so hai ngôn ngữ đỏ.
- Bỏ `draggable={...}` thành `draggable` → test cổng kéo thả đỏ.
- Cho event chở `DocumentRead` và FE đọc thẳng → test "nghe hích thì gọi lại" đỏ.

**Cổng chung:** `.\dev.ps1 check` · `test` · `typecheck`.

## Cạm bẫy đã biết

- **Thứ tự subscribe/publish.** `drafting.py` ghi lại một lần mất trọn vòng soạn đầu tiên vì
  thân một async generator không chạy cho tới lần lặp đầu. Kênh này phải là **context manager**,
  subscribe tại `__aenter__` — "mở tai trước đã" là tính chất của cú pháp, không phải lời dặn.
- **Redis pub/sub không giữ lịch sử.** Hích phát ra trước khi FE subscribe là rơi vào phòng
  trống. Đó là lý do FE **vẫn phải** fetch một lần lúc mount, và vì sao hích chỉ là hích.
- **Hai process, một Redis.** `ingest.py` chạy trong `be-worker`, route chạy trong `be`. Giống
  hệt hình dạng chuông hiện có (AGENT publish, BE subscribe), nên không có cơ chế mới nào.
- **`StreamingResponse` giữ một connection mở cho mỗi tab đang mở.** Chưa đo trần. Ghi ra đây
  chứ không giả vờ đã biết.
- **`teacher.test.tsx` đã stub `/api/teacher/documents` trả `[]`** (dòng ~1029). Thêm trạng thái
  vào stub ấy, đừng dựng một stub thứ hai.
- **`weight()` ở `Rail.tsx:342`** đã định dạng kích thước kiểu Việt (`2,4 MB`). Dùng lại, đừng
  viết hàm thứ hai cho dòng meta.
- **Variant Figma tên trùng** (`đọc được` và `đọc được — 2`) — một trong hai là rác, xác minh
  trước khi xoá.

## Status

**Xong cả mười việc, chưa commit.** Cổng: `check` **18/18** · `pytest` **461** ·
`vitest` **185** · `tsc` sạch.

### Bốn variant Figma, và số đo FE phải khớp

`Document chip` (`84:25`) nay bốn variant, xếp theo vòng đời một tài liệu:

| Variant | Cao | Dòng trạng thái | Token |
|---|---|---|---|
| `đang xử lý` | 78 | `Đang xử lý…` | `state/processing` |
| `sẵn sàng` | 58 | *(không có)* | — |
| `không đọc được chữ` | 78 | `Không đọc được chữ` | `state/needs-human` |
| `xử lý hỏng` | 78 | `Xử lí lỗi. Hãy tải lại` | `state/needs-human` |

Dòng meta của `sẵn sàng` thành `8,6 MB · 184 trang`; artboard 1 và 2 cập nhật theo.

### Đo trên hệ thật, năm process cộng `fe`

**Kênh SSE chạy.** Nghe kênh rồi tải hai tệp lên: **hai tiếng hích về sau 0,77 giây**, và đọc
lại danh sách ra `ready` 29 trang với `no_text_layer` 1 trang. Không chạm F5 lần nào.

**Chip đo trên trình duyệt**, so với Figma ở **mode Density = Teacher**:

```
rộng 228 · gap 10 · radius 8 · border 1px #e3e5e2      khớp
tên tệp  11px · 600 · #1a1f2b  (ink/default)           khớp
meta     11px · 400                                    khớp
status   11px · 600 · #8a5a22 / #2f6f73                khớp
line-height 150% -> 16,5px                             khớp
cao      56 (sẵn sàng) · 74 (ba trạng thái kia)
draggable  true chỉ ở `ready`                          khớp
title      chở `fault` đầy đủ                          khớp
```

**Một phép đo của tôi từng sai, và đáng ghi lại:** số đo Figma ở task 2 nói 12px, trình duyệt
nói 11px — tôi suýt gọi đó là lệch. Nó không lệch: collection `Density` có hai mode, và
`type/caption` là **12 ở Student, 11 ở Teacher**. Component set mặc định ở mode Student, còn
rail của giáo viên chạy mode Teacher. Phải tra bảng biến mới biết, không nhìn ra được.

### Một lỗi chỉ trình duyệt mới chỉ ra

Dòng `.status` render ở **14px** cạnh hai dòng 11px, vì tôi quên đặt `font-size` nên nó ăn cỡ
mặc định. Không test nào bắt được — chúng khẳng định **chữ**, không khẳng định cỡ chữ — và
Figma cũng không, vì bản vẽ đâu biết CSS quên gì. Chỉ phép đo trên trình duyệt nói ra. Đã thêm
`font-size: var(--type-caption)` và `line-height: 1.5` cho `.status`.

### Năm đột biến, năm cái đỏ

Thêm nấc thứ năm vào `ChipState` → check đếm nấc đỏ. Đổi tên một nấc chỉ ở FE → check **so hai
ngôn ngữ** đỏ. Bỏ cổng kéo thả → test kéo thả đỏ. Bỏ cổng kiểm cỡ → test kiểm cỡ đỏ. Cho kênh
chở dữ liệu thay vì đọc lại → test *"nghe một tiếng hích thì đọc lại danh sách"* đỏ.

### Ba chỗ lệch Figma **có từ trước plan này**, không sửa

- Padding chip: Figma `10/12`, CSS `9px 11px`. Padding của chip không bind vào biến Density nào,
  nên đây là lệch thật — một pixel mỗi cạnh.
- Màu dòng meta: Figma `ink/faint` `#6b7280`, CSS `--ink-muted` `#5b6472`.
- Chiều cao `sẵn sàng`: `min-height: 56px` ghim nó, trong khi nội dung ở mode Teacher chỉ cao 53.

Cả ba đã có trước khi plan này chạm vào file, và sửa chúng là đổi một chip đang dùng ở mười sáu
artboard. Ghi ra đây chứ không im lặng.

### Còn nợ

- **`StreamingResponse` giữ một connection cho mỗi tab đang mở.** Chưa đo trần. Một giáo viên
  mở năm tab là năm connection, và không có gì giới hạn.
- **Hai component Figma hỏng** — `Kriky state` năm variant rỗng, `Question card` component set
  một variant — đã ghi vào `docs/plans/backlog.md`.
