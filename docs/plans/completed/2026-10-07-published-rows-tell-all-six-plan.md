# Plan — Dòng ĐÃ PHÁT HÀNH nói đủ sáu, nháp scope thôi dính tay

## Goal

Ba việc, cùng tới từ một lượt dùng thật ngày 07/10/2026, làm **trước** tính năng đọc PDF
vì cả ba đều chạm đúng những chỗ tính năng ấy sắp xây lên.

**Việc 1 — panel giấu ba trong sáu thông số của một đề đang chạy.** Đo trên đề
`d3f40a77`, đã phát hành cho 12A (mở 14:21) và 12B (mở 15:26):

| Thông số | Giá trị thật | Có trên panel? |
|---|---|---|
| Giờ mở → giờ đóng | 14:21 → 17:25 | có |
| Thu hồi được tới | 14:21 · 06/10 | có |
| **Phút làm bài** | **15** | **không** |
| **Phút mỗi câu** | **5** | **không** |
| **Hạn chữa xong** | **14:25 · 07/10** | **không** |

Nguyên nhân là hai quyết định của chính đợt trước đụng nhau. `.published-to` được viết gọn
có chủ ý, và comment ở `PublishSettings.tsx:460` nói lý do: *"Thứ không suy ra được từ chỗ
khác chỉ có: lớp nào, mấy học sinh, khung giờ nào, và thu hồi được tới lúc nào."* Câu ấy
**chỉ đúng khi năm ô còn dựng**, vì ba thông số kia nằm trong năm ô. `silent` bỏ năm ô đi
khi các lớp lệch giờ, và tiền đề của comment im lặng thành sai. Docstring của `silent` còn
khẳng định *"khối `ĐÃ PHÁT HÀNH` ngay trên đã nói đủ cho từng lớp"* — một lời không ai kiểm,
và nó in 3 trên 6.

Ca này **không hiếm**: giờ mở mặc định là *ngay bây giờ*, nên phát hành cho hai lớp ở hai
thời điểm là đủ để lệch.

**Việc 2 — `scope` ở thanh chat dính tay.** `grep` ra bốn chỗ nhắc `scope` trong `Chat.tsx`:
khai báo `:112`, ghi `:320` (sau upload), ghi `:534` (sau khi thả chip), đọc `:490`. **Không
chỗ nào xoá.** Và `App.tsx` mount `<Chat>` ở ba chỗ (`:71`, `:85`, `:98`) **không chỗ nào
truyền `key`**, nên React tái dùng đúng một instance qua mọi chuyển cảnh.

Đo trên trình duyệt ngày 07/10/2026: thả chip `dai-so-12.pdf` vào ô nhập ⇒ `.scope-strip`
hiện; bấm *Đoạn chat mới* ⇒ route sang `#/teacher/moi`, đoạn chat rỗng **0 lượt**, mà
`.scope-strip` **còn nguyên chữ cũ**.

Phép đo còn lộ thêm một chuyện: dải in **"Đã tải lên: dai-so-12.pdf"** trong khi việc vừa
làm là **đính một tệp đã có**, không phải tải lên. Một state đang chở **hai nghĩa** —
*"tôi vừa tải tệp này lên"* (việc đã xong, thuộc thư viện) và *"tôi đính tệp này vào câu
đang gõ"* (ý định, thuộc tin nhắn đang soạn). Hai nghĩa ấy muốn hai tuổi thọ khác nhau, và
đó là lý do không có chỗ nào dọn được: dọn đúng cho nghĩa này thì sai cho nghĩa kia.

**Việc 3 — tấm trượt mặc định thu khi đã khoá.** Người dùng chốt 07/10/2026. Tiền đề là
phép đo cũ: hai lớp chung khung giờ ⇒ tấm trượt cao **779**, `panel-questions` còn **24px**.
Việc 1 có thể **xoá mất tiền đề ấy**; xem Ordered Tasks.

**Kết quả mong muốn:** panel nói đủ sự thật về một đề đang chạy, cho **từng lớp**; thanhthực
chat thôi nhớ nhầm; và tấm trượt đã khoá không chiếm chỗ của việc đang làm.

## Decision Records

### Decision: Năm ô khoá bị bỏ hẳn, không phải bỏ có điều kiện

**options considered:**

- (a) Giữ năm ô, điền theo lớp đầu tiên, thêm một dòng nói các lớp khác khác giờ.
- (b) Dựng năm ô cho **mỗi** lớp.
- (c) Khi `locked` thì **không dựng ô nào**; mọi sự thật nằm ở dòng `ĐÃ PHÁT HÀNH`, một khối
  mỗi lớp, đủ sáu thông số.

**selected option:** (c).

**reason:** khuyết tật là **cấu trúc**, không phải hiển thị. Năm cái ô chỉ diễn tả được
**một** khung giờ, trong khi dữ liệu `publications` là **theo từng lớp**. Nên "điền giá trị
vào ô khoá" không bao giờ *đúng* cho nhiều lớp — nó chỉ đúng **tình cờ** khi các lớp trùng
giờ, và chính sự trùng hợp ấy là thứ `shared` đang đi dò. (a) giữ nguyên khuyết tật và thêm
một câu xin lỗi; (b) cho hai lớp là mười ô, panel không còn chỗ cho câu hỏi.

(c) còn **xoá** được ba thứ dẫn xuất sinh ra chỉ để phục vụ ô khoá: `shared`, `show` và
`silent`. Một biểu mẫu đã khoá thì không phải biểu mẫu nữa; nó là một biên bản, và biên bản
thì viết theo dòng, không theo ô.

### Decision: `scope` giữ đúng MỘT nghĩa, và dải "Đã tải lên" bị bỏ

**options considered:**

- (a) Thêm `setScope(null)` ở ba chỗ: gửi tin, đổi `conversationId`, `start_new`.
- (b) `key={conversationId ?? "moi"}` trên `<Chat>`.
- (c) Tách làm hai state: `justUploaded` và `attached`.
- (d) **Bỏ hẳn nghĩa "vừa tải lên"**: dải chỉ còn chở *tệp đính vào câu đang gõ*, mang một
  đường lùi `Bỏ`, và chết lúc nhấn Gửi cũng như lúc đổi đoạn chat. Upload thì đính luôn.

**selected option:** (d) — người dùng chốt 07/10/2026.

**reason:** (a) chữa triệu chứng mà để lại nguyên nhân: một biến hai nghĩa thì mọi luật dọn
đều sai cho một nửa số ca. (b) dựng lại cả `Chat`, kéo theo tải lại `turns` và mất `live` —
quá tay cho một dải chữ. (c) đúng về chẩn đoán nhưng giữ lại một thông báo **không cần
tồn tại**: rail đã đẩy tệp vừa upload lên **đầu** danh sách, nên câu *"Đã tải lên"* kể lại
một việc màn hình vừa nói. (d) bỏ nghĩa thừa đi, nên còn **một** nghĩa và do đó **một** tuổi
thọ — và một tuổi thọ rõ ràng chính là thứ chữa được lỗi dính tay. Nó cũng là chỗ đặt được
khoảng trang của tính năng PDF, vì khoảng trang thuộc về **câu đang gõ**.

## Files

| File | Việc |
|---|---|
| Figma `mOe2ZmrqOq1Uix45v6PNGD` | `534:20` dựng lại; `542:20` **xoá**; khối `trouble` thêm vào; artboard 2 đổi dải; frame quyết định `554:2391` |
| `services/fe/src/screens/teacher/PublishSettings.tsx` | bỏ `shared` / `show` / `silent`; `.published-row` nói đủ sáu; mặc định thu khi `locked` |
| `services/fe/src/screens/teacher/Chat.tsx` | `scope` giữ đúng **một** nghĩa; bỏ dải *"Đã tải lên"*; thêm nút `Bỏ` |
| `services/fe/src/api.ts` | `localInput` có thể thành code chết — kiểm rồi xoá nếu đúng |
| `services/fe/src/teacher.css` | `.scope-strip .quiet`; bỏ `input:disabled` khỏi luật khoá. `.published-row` **không đổi** — nó đã là một cột `gap: 6px` từ trước, nên bốn dòng tự xếp |
| `services/fe/src/teacher.test.tsx` | test cho từng luật mới |
| `tools/check_contract.py` | check 15 nói về `input:disabled` của biểu mẫu phát hành — xem Task 5 |

## Ordered Tasks

### Pha 0 — Figma trước *(cổng)* — **đã duyệt 07/10/2026**

- [x] `.published-row` thành **năm** dòng mỗi lớp, đủ sáu thông số. Hai dòng giữa là
      `phase_one_note` / `phase_two_note` của BE **nguyên văn** — ADR-03 đòi câu luật xuất
      hiện ở cả ba nơi và *"giống hệt nhau từng chữ"*, và biên bản sau khi phát hành là nơi
      thứ ba. Dòng thứ hai nêu **tham số thô** (giờ mở, phút làm bài) vì hai câu luật không
      nói hai thứ ấy.
      Đo: row 44 → 78 → **86**, `published-to` 119 → 187 → **201** (hai con số sau là ở
      density Teacher, **sau** khi sửa line-height 150% và `gap` 6 cho khớp CSS; hai con số
      giữa là bản đo đầu trên trang Components, giữ lại để thấy phép sửa đã đổi gì).
- [x] Bỏ năm ô khỏi variant khoá: `534:20` 677 → **366**.
- [x] Hai variant khi ấy **giống hệt nhau, cùng 366**, nên xoá `542:20`
      (`đã phát hành — lệch giờ`). Kiểm trước khi xoá: **0 instance**, và không text nào
      trên trang Teacher nhắc tới nó.
- [x] Khối `trouble` (câu `undo_blocked` của BE) nay **có** trên variant — nó thiếu từ
      trước, nên variant đọc ra ngắn hơn màn hình thật 77,5px mà không ai thấy. Clone từ
      `505:47` của variant `hết cửa lùi` để giữ nguyên biến màu. Variant: 366 → **456**
      (density Teacher).
- [x] Một cột thứ ba trên frame quyết định: dòng nói ra khi `publications` hỏng.
- [x] Artboard 2: dải tài liệu còn **một** nghĩa — `PDF · <tên tệp> · Bỏ`. Dải *"Đã tải lên"*
      bị bỏ hẳn.
- [x] Frame quyết định `554:2391`, cùng khuôn `519:1603`. Và một dòng `BỊ THAY 07/10/2026`
      ghi vào frame 06/10 (`537:2306`), vì tấm trượt trong đó là **instance** nên nó đã tự
      đổi theo và không còn khớp với chữ của chính nó.

### Pha 1 — Panel nói đủ sáu *(mở sau khi Figma được duyệt)*

- [x] `.published-row` dựng **bốn** dòng cho mỗi lớp, đủ sáu thông số. Giờ in bằng `moment()`.
- [x] Xoá `shared`, `show`, `silent` và comment biện minh cho chúng.
- [x] `locked` ⇒ không dựng nhóm PHA 1 / PHA 2 / `.rules`; CTA vẫn vắng như hiện tại. Và
      `disabled={locked}` trên năm ô bị bỏ: ô chỉ dựng khi `!locked`, nên điều kiện ấy
      không bao giờ đúng — một điều kiện chết là một lời hứa sai về cấu trúc.
- [x] `localInput` thành code chết (chỉ còn định nghĩa + một import thừa) ⇒ xoá nó và test
      của nó.

**Nơi thi hành:** test dựng `publications` hai lớp **lệch giờ** và khẳng định cả sáu con số
có mặt **cho từng lớp** — đây đúng là đường mà test cũ không đi. Đột biến: bỏ một trong ba
thông số mới ⇒ đúng một test đỏ.

### Pha 2 — Tấm trượt thu khi đã khoá

- [x] **Đo trước:** cửa sổ 854 ⇒ tấm trượt **455**, `panel-questions` **260**, **0 ô**.
      Tiền đề cũ (779 / 24px) đã mất; người dùng vẫn chốt **thu**.
- [x] Thu bằng một `useEffect` **sau** khi `publishForm` về — **không** phải bằng giá trị
      khởi tạo của `open`, và sự khác biệt ấy có thật: `open` khởi tạo bằng
      `readFlag(OPEN_KEY)` tức `true` khi khoá vắng, nên có một khung hình tấm trượt bung
      trước khi effect thu nó. Nói "giá trị khởi tạo" là che mất cửa sổ thời gian ấy.
- [x] **Bốn** điều kiện gác nó, mỗi cái chống một ca khác: `locked`; `knows(OPEN_KEY)` (chưa
      ai tự quyết — `readFlag` không phân biệt được *"đã ghi bật"* với *"chưa ai ghi"*);
      `done !== null` (vừa phát hành trong phiên này — xem Status); và `liveFault !== null`
      (lời báo lỗi nằm **trong** thân tấm trượt, nên thu là giấu nó đi). Cộng một `ref` để
      việc thu xảy ra đúng một lần, vì `locked` bật **giữa phiên** nhờ `reread`.
- [x] **Không ghi khoá** khi áp mặc định: đó là một mặc định, không phải lựa chọn của ai.
- [x] Đo lại, cửa sổ 855, đã xoá mọi nấc đã nhớ: mặc định ⇒ tấm trượt **51,5**, vùng câu
      hỏi **664,5**, khoá `null`. Tự bung ⇒ **455 / 261**, khoá `"1"`. Thu trả lại **403px**.

### Pha 3 — `scope` thôi dính tay

- [x] Bỏ nghĩa *"vừa tải lên"*; dải chỉ còn chở tệp đính vào câu đang gõ, kèm nút `Bỏ`.
- [x] Dải về `null` khi: gửi tin thành công, khi `conversationId` đổi, và khi bấm `Bỏ`.
- [x] Dải in **tên tệp**, không thêm nhãn: nút `Bỏ` và chỗ đứng của nó đã nói nó là gì.

**Nơi thi hành:** test thả chip ⇒ dải hiện; đổi `conversationId` **tại chỗ** (rerender, không
`unmount`) ⇒ dải mất. Cộng một test rằng gửi tin xong thì dải mất. Đột biến từng cái.

### Pha 4 — Cổng

- [x] Check 15 **thu hẹp về chip**. `grep 'disabled'` trong `PublishSettings.tsx` cho bốn
      chỗ: một chip (`:465`) và ba nút — **không ô nhập nào**. Nên `input:disabled` rời khỏi
      cả selector CSS lẫn docstring của check: một selector không khớp gì là một lời hứa đã
      hết hạn, và một docstring mô tả hành vi không còn tồn tại là một lời khai sai.
- [x] `.\dev.ps1 check` **16/16** · `typecheck` · `pytest` **398** · `vitest` **173**.
- [x] So Figma ↔ FE bằng số: tấm trượt **377** (Figma, density Teacher) so **377,5**
      (trình duyệt, trừ khối `trouble` mà variant chưa từng vẽ). Mọi chênh lệch còn lại là
      Figma làm tròn chiều cao một dòng **16,5 → 17**. Phải sửa hai thứ trên Figma mới
      khớp: line-height mặc định của font → `150%`, và `gap` 8 → 6.
- [x] Ghi lượt năm vào `docs/kich-ban-thu-tay-giao-vien.md` (742 → 841 dòng, 56 KB).
- [x] **`publications` hỏng nay nói ra.** Một dòng `role="status"` đứng đúng chỗ khối
      `ĐÃ PHÁT HÀNH` lẽ ra đứng, chỉ khi `form` **biết** có lớp đang giữ đề. Khung là chữ
      của FE (nó kể một việc của client, không phải một lời từ chối, nên không chạm chỗ
      ADR-03 giữ cho BE); phần sau là `detail` của BE nguyên văn do `call()` ném ra.

## Validation Checks

- **Cổng:** `.\dev.ps1 check` · `test` · `typecheck`.
- **Đột biến:** mỗi luật mới sửa một dòng cho sai, phải đỏ **đúng** test của nó.
- **BE không đổi:** `git diff --stat services/be` rỗng.
- **Figma ↔ FE** so bằng số, không bằng mắt.
- **Không lượt model nào:** cả ba việc đo được bằng DOM và dữ liệu đã có.

## Status

**Xong cả năm pha.** Cổng: `check` **16/16** · `typecheck` · `pytest` **398** ·
`vitest` **178** — xanh. Chín luật mới, mỗi luật đỏ **đúng** test của nó dưới một đột biến
một dòng.

`git diff --stat services/be packages/contracts` rỗng, như ràng buộc đã đặt.

**Figma ↔ FE, bằng số:** tấm trượt đã khoá **456** (Figma, density Teacher) so **455**
(trình duyệt). Mọi chênh lệch còn lại là Figma làm tròn chiều cao một dòng **16,5 → 17**.
Phải sửa ba thứ trên Figma mới khớp được — line-height mặc định của font → `150%`,
`gap` 8 → 6, và khối `trouble` vốn thiếu hẳn.

### Ba lỗi tôi tự gây ra giữa đường

- `useEffect` mới đặt **sau** một `return` sớm (`if (!open)`), nên số hook đổi giữa hai lần
  render và React ném *"Rendered more hooks than during the previous render"*. Phải đưa cả
  `locked` lẫn effect lên **trước** mọi `return` sớm.
- File test có **ba** hàm cùng tên `open()`; tôi sửa hàm của describe khác rồi kết luận sai
  rằng phép sửa không ăn.
- **Và lỗi đáng kể nhất, do chính phép sửa test của tôi che đi.** Mặc định thu đọc sai ca
  *vừa phát hành xong*: `publish` gọi `setDone(...)` rồi `setReread(+1)`, `form` được đọc
  lại, `locked` bật **giữa tay người đang dùng**, và effect thu tấm trượt — làm thẻ
  `Outcome` biến mất cùng khối `ĐÃ PHÁT HÀNH` giáo viên vừa tạo ra. Cú bấm quan trọng nhất
  của màn hình trả lời bằng cách đóng sập chính nó. Test `"phát hành xong là KHOÁ ngay"`
  **vẫn xanh suốt**, vì helper `mount()` tôi vừa sửa gieo sẵn khoá `"1"` — tôi gieo nó để
  các test *nội dung* có trạng thái xác định, và cùng lúc nó đi vòng qua đúng cái vừa thêm.

### Review độc lập tìm thêm, và đã sửa

- **Khối `ĐÃ PHÁT HÀNH` vi phạm ADR-03.** Bản đầu tự viết `Làm bài 14:21 → 17:25 · 15 phút`
  và `Chữa bài tới … · 5 phút/câu` — một **cách diễn đạt thứ hai** cho hai luật mà ADR-03
  đòi phải *"giống hệt nhau từng chữ"* ở cả ba nơi, trong đó nơi thứ ba đúng là *"biên bản
  sau khi phát hành"*. Nó trình bày giờ đóng như mốc **kết thúc**, bỏ mất mốc nộp cuối, và
  bỏ chữ **DỪNG**. Mà `publications` đã chở sẵn `phase_one_note` / `phase_two_note` theo
  từng lớp và **không chỗ nào trong FE đọc chúng**. Nay hai dòng ấy là chữ của BE nguyên
  văn; dòng thứ hai nêu tham số thô (giờ mở, phút làm bài) vì hai câu luật không nói.
- **Dòng báo lỗi không với tới được ở trạng thái mặc định.** Nó nằm **trong** thân tấm
  trượt, mà mọi ca nó sinh ra để nói đều là ca đề đã có lớp giữ — và *mọi lớp đều giữ* là
  ca thường gặp nhất, tức mặc định **thu**. Hai việc của đợt triệt tiêu nhau. Thêm điều
  kiện thứ tư `liveFault`, và nó **bung lại** chứ không chỉ "đừng thu", vì `form` và
  `publications` là hai lời gọi riêng nên lỗi có thể về **sau** khi đã thu.
- **Phép khẳng định sáu thông số sống sót một cú đột biến đảo hai con số.**
  `toContain("15 phút")` vẫn khớp chuỗi `"15 phút/câu"`, và `toContain("5 phút/câu")` cũng
  vậy — nên luật trung tâm của đợt không phân biệt được phút làm bài với phút mỗi câu. Nay
  khớp **nguyên văn** hai câu của BE (fixture mang tên lớp, nên nó chứng minh luôn "theo
  từng lớp") và khớp tham số kèm dấu phân cách.
- **`teacher-surface.md` và ADR-02 còn giữ nguyên văn lời khai sai** mà chính plan này dành
  một đoạn để tố: *"khối ĐÃ PHÁT HÀNH ở trên đã nói đủ cho từng lớp"*, *"Ô khoá MANG giá
  trị đã phát hành"*, *"Giá trị đi qua `localInput`"* (hàm đã xoá), *"chip của lớp ấy **và
  năm ô thời gian** `disabled`"*. `AGENTS.md` đòi tài liệu sở hữu chủ đề đi **cùng** change
  set; cả hai đã sửa.
- **Docstring check 15 nói `420x366`** (variant nay là **456**) và gọi chip là control khoá
  *"duy nhất"* của biểu mẫu — sai, `Hoàn tác` và CTA cũng khoá được. Chúng **đã có** luật
  CSS riêng, nên không thiếu lưới; chỉ là chữ "duy nhất" sai. Đã sửa cả hai.
- Và bảy chỗ số má lệch nhau giữa plan, docstring và `kich-ban`: ba con số `vitest` khác
  nhau cho một phép đo, bảng `Files` nói ngược Decision Record, một dòng ghi `teacher.css`
  đổi `.published-row` trong khi file ấy **không đổi một dòng nào** ở chỗ đó.

### Còn nợ, đã ghi để không mất

- `setScope(null)` đứng **trước** `await teacher.conversation(...)`, nên nếu lời gọi đọc lại
  ấy hỏng thì chữ được trả về ô nhập mà tệp đính thì không — ngược với chính comment của nó.
- `text` và `scope` khác tuổi thọ khi đổi đoạn chat: chữ còn, tệp mất. Phải chọn một.
- `cause.message` của `publications` còn chở được câu tiếng Anh của trình duyệt
  (`Failed to fetch`, lỗi parse JSON), trong khi comment hứa đó là "chữ của BE".
- Một response **200 sai hình dạng** vẫn im lặng: `live = []`, `liveFault = null`.
- `draft-mark` và `impossible` vẫn dựng được khi `locked`.
- `useLayoutEffect` sẽ bỏ được khung hình nháy lúc thu.
