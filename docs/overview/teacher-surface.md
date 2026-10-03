# Bề mặt giáo viên — behavior của màn hình

## Mục đích tài liệu

Tài liệu này ghi **luật hiển thị** của bề mặt giáo viên: một lượt của Kriky hiện ra thành những khối
nào, khối nào ứng với dữ liệu nào, và khi nào một khối đổi trạng thái. Nó tồn tại vì một lý do đo
được: những luật này trước đây **chỉ nằm trong file Figma**, dưới dạng tám artboard và mười hai
component. Ai dựng code cũng phải tự suy ra chúng từ bố cục, và mỗi lần suy lại một kiểu — một đợt
review đối chiếu tìm ra 23 chỗ lệch, 12 chỗ mức nặng, mà không chỗ nào vi phạm một câu chữ nào đã
viết ra, vì chưa có câu nào được viết.

Tài liệu này **không** mô tả nghiệp vụ (xem [Business Workflows](business-workflows.md)) và không
thay thế file thiết kế. File Figma `mOe2ZmrqOq1Uix45v6PNGD` vẫn là nguồn cho **hình khối**: toạ độ,
kích thước, màu, nhịp. Chỗ này là nguồn cho **hành vi**: cái gì hiện ra lúc nào, và vì sao.

Đọc kèm: `services/fe/AGENTS.md` (luật *Figma và code đổi cùng một change set*),
[ADR-05](../decisions/adr-05-ba-cong-teacher-in-the-loop.md) (ba cổng),
[ADR-23](../decisions/adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md) (hỏi lại khi không phân định được).

## Một lượt của Kriky là một dãy khối, theo thứ tự agent trả về

**Không có khuôn cố định nào.** Harness tiêm context và tool; model quyết nói lúc nào, tra lúc nào,
hỏi lúc nào — nên màn hình vẽ đúng thứ tự nó nhận được ([ADR-25](../decisions/adr-25-hai-pha-mot-luot-chat.md)).
Artboard là **ảnh chụp một trường hợp**, không phải kịch bản.

Trường hợp artboard `5 · Đã có đề nháp` (`12:46`) chụp lại — và cũng là trường hợp thường gặp nhất —
đọc từ trên xuống:

| # | Khối | Component | Có mặt khi nào |
| --- | --- | --- | --- |
| 1 | Câu mở đầu của Kriky | `Message turn` (Vai=agent) | Khi model nói một câu trước lúc gọi tool |
| 2 | Khối các bước | `Thinking` (`83:76`) | Khi lượt có từ một bước tool trở lên |
| 3 | Câu kết | `agent-conclusion`, cũng là `Message turn` (Vai=agent) | Khi lượt kết thúc bằng `say` |
| 4 | Thẻ kết quả | `Action result card` (`10:63`) | **Tối đa một thẻ cho một lượt** |

**MỘT LƯỢT, MỘT AVATAR, Ở TRÊN CÙNG.** Hàng avatar nói *"từ đây là Kriky"* — nó là **ranh giới giữa
hai người nói**, không phải một dấu trang trí cho mỗi đoạn văn. Nên nó xuất hiện đúng một lần cho cả
lượt, trước thứ đầu tiên nó giới thiệu, và mọi phần còn lại nằm dưới nó:

> avatar → (câu mở đầu, nếu có) → `Đã làm n bước` → câu kết → thẻ kết quả

Bản trước dựng avatar lần thứ hai cho câu kết — artboard 5 vẽ vậy, và FE chép theo. Trên một hội
thoại thật thì cùng một người nói được giới thiệu hai lần trong một lượt: ồn, và sai về nghĩa. Figma
đã sửa cùng change set (hàng avatar của `agent-conclusion` trên artboard 5 ẩn đi).

Nhịp: **6** giữa avatar và phần đầu tiên, **20** giữa các phần với nhau. Thứ tự đọc giữ nguyên dù
lượt thiếu phần nào — dữ liệu thật thường không có câu mở đầu, và khi đó avatar giới thiệu thẳng khối
bước.

### Luật quan trọng nhất: thẻ mọc cho kết quả còn đứng vững

Mọi `tool_result` thuộc về **các bước trong khối bằng chứng**. Chỉ một kết quả **còn đứng vững tới
cuối lượt** mới lên thẻ — một đề vừa tạo rồi được đổ câu hỏi vào ngay trong lượt ấy thì trạng thái
rỗng không bao giờ thành thẻ, vì nó đã bị chính bước sau thay thế.

Ánh xạ hiện hành, và đây là bảng duy nhất được phép quyết chuyện này:

| Tool | Hiện thành | Ghi chú |
| --- | --- | --- |
| `find_class` | một bước trong `Thinking` | Nhập nhằng thì lượt kết thúc bằng `Clarify request`, không phải thẻ |
| `class_assessment_summary` | một bước | Kết quả đi vào câu kết |
| `create_draft` | một bước. **Thẻ** `tạo-đề-trống` **chỉ** khi không bước nào trong lượt đổ câu vào đề ấy | Có `start_drafting` phía sau thì trạng thái trống **không còn đứng vững** — chính bước sau đã thay nó, nên không thẻ nào. Thất bại → thẻ `tạo-thất-bại` |
| `start_drafting` | một bước. **Thẻ** `thêm-câu-hỏi` **chỉ khi** bước ấy đã đợi hết câu và mang về `written`/`asked_for`/`still_drafting` | Chưa có ba con số ấy thì vẫn chỉ là một bước: một thẻ ở đó nói với giáo viên rằng một việc đã xong trong khi nó vừa bắt đầu. Cửa `POST` không đợi, nên ở đó không bao giờ có thẻ |
| `draft_progress` | một bước; **thẻ** `thêm-câu-hỏi` khi các câu đã về đủ | Thẻ ghi số câu **thật đã có**, không ghi số chỗ đã đặt. Nó là tool của **pha 1**, nên một plan không gọi nó — đường này chỉ còn sống khi giáo viên hỏi riêng về tiến độ |

Một tool mới phải có dòng trong bảng này **trước** khi nó có mặt trên màn hình. Không có dòng nào thì
nó là một bước, không phải một thẻ — mặc định an toàn, vì một bước không hứa gì.

## `Thinking` — các bước là bằng chứng, không phải hiệu ứng chờ

Mô tả component nói thẳng: *"các bước CHÍNH LÀ BẰNG CHỨNG cho biết đề được dựng ra thế nào, nên nó
thu gọn được nhưng không bao giờ mất."* Giáo viên đứng trước cổng duyệt cần biết câu hỏi từ đâu ra.

| Trạng thái | Khi nào | Hình dạng | Thu gọn được? |
| --- | --- | --- | --- |
| `đang chạy` (`83:72`) | Lượt đang chạy | Mở sẵn. Header là **tiêu đề của bước đang chạy** kèm `…`, bên phải là `bước k/n`; bước ấy đánh `○` | Được |

> **`đang chạy` nay chạy thật.** FE gửi lượt qua `POST /teacher/chat/messages/stream` và vẽ
> theo đúng thứ tự sự kiện nhận được: `say` → `plan` → `step_started` → `step_done` →
> `progress` → `report`. `n` của `bước k/n` lấy từ **plan**, nói được vì plan có trước khi chạy;
> số câu đã soạn là dòng kết quả của bước đang chạy. Khi lượt xong, màn hình **đọc lại cả đoạn
> từ database** — thứ ở lại phải là thứ database đang giữ, nếu không một lần F5 cho ra một màn
> hình khác. Vì thế khối tự thu lại lúc xong: nó được dựng lại từ dữ liệu, không phải được
> chuyển trạng thái.
| `đã xong` (`83:73`) | Lượt kết thúc **thành công** | **Tự thu lại** còn một dòng `Đã làm {n} bước` | Đang thu |
| `đã xong — mở` (`83:74`) | Người dùng bấm chevron | Mở lại đầy đủ các bước | Được |
| `thất bại` (`83:75`) | Lượt dừng vì một bước hỏng | Mở sẵn. Header `Dừng ở bước {k}` — **không** nhắc lại lý do, vì lý do đã nằm ở dòng của chính bước hỏng; bước ấy đánh `✕` | **Không.** Thu một lỗi lại là giấu lỗi |

Một bước gồm ba phần: **dấu** (`✓` xong, `○` đang chạy, `✕` hỏng), **tiêu đề việc**, và tuỳ chọn một
**dòng kết quả** mở đầu bằng `— `. Dòng kết quả là chữ của BE; FE in nguyên văn, không viết lại.

**Hai con số, hai chỗ đứng.** `bước k/n` ở góc phải header đếm **bước của plan** — nói được `2/2`
chính vì pha 1 nêu plan trước khi chạy (ADR-25). Số câu đã soạn là **dòng kết quả của bước đang
chạy** (*"— đã soạn 4/10 câu"*), không bao giờ gộp vào `k/n`: một con số trộn hai sự thật thì sai với
cả hai. Artboard 4 đã có sẵn chỗ cho dòng ấy, nên không cần thêm hàng mới.

**Chữ mẫu trong Figma không phải dữ liệu.** Các bước mẫu nay chụp đúng một plan hai bước thật (*"Tạo
đề trống"*, *"Soạn 10 câu hỏi"*); bản trước mô tả một ngân hàng câu hỏi mà BE **chưa có**
(`docs/plans/backlog.md`), và một thiết kế mô tả tính năng chưa tồn tại sẽ được chép vào code như một
lời khẳng định sai về hệ thống. Dù vậy luật không đổi: các bước phải dựng từ `tool_call` /
`tool_result` thật, đúng loại lỗi mà `services/fe/src/screens/teacher/invented-not-from-be.ts` sinh ra
để dồn lại một chỗ.

## `Action result card` — tám variant, hai luật chung

- **Mỗi thẻ nói hậu quả của việc vừa xong.** Bảy variant nói bằng một chip `safety` — *"Đề trống,
  chưa phát hành được"*, *"Chưa duyệt · chưa phát hành"*, *"Chưa có gì được thay đổi"*. Variant
  `đã-phát-hành` khác hình: **không có chip `safety`**, mà có ba dòng chữ trần — câu khoá–thu hồi,
  câu luật pha 1, câu luật pha 2. FE hiện gói hậu quả ấy vào **một** chip một dòng; ba dòng của
  thiết kế cần biểu mẫu phát hành trả về chúng, và đó là nợ chưa trả. Điều không được phép nhân
  nhượng: một thẻ im lặng về hậu quả là một thẻ mời người ta tưởng là xong, và thẻ có hậu quả lớn
  nhất mà im lặng thì là lỗi nặng nhất trong nhóm này.
- **Nút trên thẻ mời bước tiếp theo**, không phải `Xem`. `Xem` luôn là nút phụ.

**Khoảng trống đã đóng.** Tới hết đợt ADR-25, một lượt soạn đề **thành công** kết thúc không thẻ
nào: `create_draft` bị loại khi có `start_drafting` phía sau, `start_drafting` bị loại vô điều kiện,
và `draft_progress` là tool của pha 1 nên một plan không gọi nó. Ba lần loại trừ ấy giao nhau đúng ở
đường đi hạnh phúc — mà panel đề **chỉ mở được từ một nút trên thẻ**, nên Kriky nói *"đã soạn xong"*
và màn hình không có cửa nào vào xem. Nay bước soạn khi đóng lại đã biết số câu thật, và thẻ
`thêm-câu-hỏi` mọc từ chính nó.

| Variant | Head | Nút chính | Nút phụ |
| --- | --- | --- | --- |
| `tạo-đề-trống` | `Đã tạo đề "{tên}"` · detail `Chưa có câu hỏi nào` | `Thêm câu hỏi` | — |

**`tạo-đề-trống` chỉ mọc cho một lượt *chỉ* mở đề** — giáo viên nói *"mở cho tôi một đề trống"*. Khi
họ nói *"tạo đề 10 câu"* thì plan có hai bước (ADR-25) và thẻ này **không được xuất hiện**: nó nói
rằng việc được nhờ đã xong và cho ra một cái đề rỗng, trong khi việc ấy đang chạy. Một đề chưa đủ
câu ở lại **trong khối bước**, và câu báo cáo cuối lượt nói nó đang tới đâu.
| `thêm-câu-hỏi` | `Đã thêm {n} câu vào đề` | `Duyệt đề` | — (xem ghi chú) |
| `thiếu-câu` (`455:16`) | `Dừng ở {k}/{n} câu` | `Xem đề` — **không** mời duyệt | — |
| `đang-soạn-dở` (`456:16`) | `Đã soạn {k}/{n} câu` · detail `còn {r} câu đang soạn` | `Xem đề` — **không** mời duyệt | — |

**Điều kiện mời duyệt là `đã đủ câu`, và chỉ thế.** Không phải *"thiếu câu **và** không còn gì đang
chạy"* — viết thế thì một đề 3/10 còn bảy câu đang chạy rơi vào nhánh còn lại, thẻ in `Đã thêm 3 câu
vào đề` (giấu mất số 10) và mời duyệt. Đường ra ấy có thật: hết hạn im lặng thì vòng nghe chuông
đóng lại với `still_drafting > 0`. Và nó cãi lại `reporting._progress` của AGENT, nơi lời kể trong
cùng ca ấy chỉ được nói *"đang soạn"*.

Bảng này in `Xem` làm nút phụ cho `thêm-câu-hỏi` theo đúng Figma, nhưng **code chỉ dựng một nút**:
cổng duyệt nằm trong panel, nên `Duyệt đề` và `Xem` sẽ mở đúng cùng một chỗ, và hai nhãn khác nhau
cho một hành vi là một lời hứa rỗng.
| `đã-duyệt` | `Đã duyệt đề "{tên}"` | `Phát hành` | `Hoàn tác` |
| `bỏ-duyệt` | `Đã bỏ duyệt đề "{tên}"` | `Duyệt đề` | `Xem` |
| `tạo-thất-bại` | `Không tạo được đề` | `Thử lại` | — |
| `đã-phát-hành` | `Đã phát hành cho {lớp}` | `Xem` | `Thu hồi` — **chưa dựng** |
| `phát-hành-thất-bại` | `Phát hành chưa xong` | `Thử lại cho {lớp}` | — |
| `tạo-lớp` | `Đã tạo lớp {tên}` | `Xem` | — |

**Nút mời một việc làm bằng lời nói thì điền sẵn ô nhập.** `Thêm câu hỏi` và `Thử lại` không có
endpoint nào để gọi — thêm câu hỏi là một câu nói với Kriky, không phải một nút trên REST. Hai nút ấy
đặt con trỏ vào ô nhập và viết sẵn câu mở đầu; giáo viên sửa rồi gửi. Nút nào mời một việc **có** cổng
thì đi thẳng tới cổng ấy: `Duyệt đề` và `Hoàn tác` mở panel, `Phát hành` mở biểu mẫu phát hành.

`Thu hồi` **chưa dựng**: endpoint thu hồi có, nhưng FE chưa có đường gọi nó, nên thẻ chỉ mang
`Xem`. Một nút mang nhãn của thiết kế mà không làm được việc của nhãn ấy còn tệ hơn một nút vắng mặt.

`tạo-lớp` **chưa dựng được**: không tool nào tạo lớp. Nút `Phát hành` không bao giờ xuất hiện trên
thẻ `thêm-câu-hỏi` — phát hành đi qua panel (ADR-05, ADR-10). Nút `Thu hồi` phải **biến mất** sau giờ
mở (ADR-02); component set chưa có trục trạng thái đó và đã ghi nợ ngay trong mô tả component.

## `Clarify request` — thẻ hỏi lại ở lại dòng chat

- Thẻ có **đoạn ngữ cảnh** nói vì sao phải hỏi, rồi tới các phương án. Mỗi phương án **hai dòng**:
  nhãn, và một câu nói cái giá của lựa chọn đó.
- Chọn xong, thẻ **không biến mất**. Nó đổi sang variant `đã chọn` (`64:22`): câu hỏi + `✓` + phương
  án đã chọn, ở lại như một bản ghi.
- **Nợ hợp đồng BE:** `Answered.choices` hiện là `list[str]`, không chở nổi dòng thứ hai. Dựng đủ thẻ
  này cần BE trả về cặp (nhãn, đánh đổi), hoặc một quyết định bỏ dòng thứ hai khỏi thiết kế. Tới lúc
  đó FE dựng phần dựng được và **không bịa** dòng đánh đổi.
- **Các phương án sống qua F5.** Chúng nằm trong hai cột của `teacher_turns`, trên row của chính bước
  đã hỏi, và chỉ **bước cuối** của một đoạn chở chúng lên khi đọc lại — một câu hỏi đã được trả lời
  thì các nút của nó không còn nghĩa gì. Trước đợt chốt chặng A, `choices` chỉ sống trong response,
  và màn hình lấy chúng từ đúng cái response **không bao giờ** có chúng; nên thẻ này có thể chưa từng
  hiện lần nào, chứ không phải chỉ mất sau khi tải lại.

## Avatar `Kriky state` đổi theo pha của lượt

Không phải trang trí. Năm variant, pha nào variant ấy:

| Pha | Variant |
| --- | --- |
| Chưa nói gì | `nghỉ` |
| Đang chờ câu trả lời đầu tiên | `đang đọc` |
| Đang chờ giáo viên trả lời một câu hỏi lại | `đang hỏi` |
| `Thinking` đang chạy | `đang làm` |
| Lượt đã kết thúc, có thẻ kết quả | `đã xong` |

Chuyển cảnh 260ms, hai hình chồng nhau 60ms, **không phóng to, không xoay** (ghi chú `234:1349`).

## Hàng đoạn chat — một hộp, hai việc

Cả hàng **từng là một `<button>`**. Nó phải hết là thế từ đợt chốt chặng A, và lý do là cơ học chứ
không phải thẩm mỹ: một nút lồng trong một nút là HTML không hợp lệ, browser tự gỡ lồng, và cú bấm
vào nút trong rơi vào nút ngoài — tức bấm *Xoá* sẽ mở đoạn chat. Nên hàng là một `div`, phần chữ là
một nút chiếm hết chỗ còn lại, và `⋯` là một nút ngang hàng với nó.

`⋯` hiện khi con trỏ ở trên hàng hoặc khi bàn phím đang ở trong hàng, và nó giữ chỗ bằng
`visibility` chứ không `display`: tên đoạn chat không được giật ngang 24px mỗi lần chuột đi qua.
Menu hai mục — *Đổi tên* (phần chữ thành một ô nhập tại chỗ; Enter lưu, Esc huỷ) và *Xoá*.

Menu được dựng **qua portal vào `body`**, không nằm trong rail. Hai bước, mỗi bước mua bằng một
phép đo: `position: absolute` thì vùng cuộn (`overflow-y: auto`) cắt nó ở hàng cuối; đổi sang
`fixed` thì nó thoát ra được nhưng `mask-image` của chính vùng ấy dựng một stacking context, nên
`z-index` chỉ xếp hạng bên trong vùng cuộn và ngăn TÀI LIỆU vẽ đè lên — `elementFromPoint` ở giữa
mục *Xoá* trả về một chip tài liệu, tức mục nhìn thấy mà không bấm được. Vì menu không còn là con
cháu của rail, CSS của nó là `.row-menu`, **không** `.rail .row-menu`.

**Số đo, từ artboard `13 · Xoá một đoạn chat` (`455:2224`):** hàng 228×41; `⋯` 24×24, cách mép phải
**6**; menu 114 rộng, bo **8**, padding **4**, viền 1 — nên CSS lấy padding **3**, theo đúng luật
trừ-một của mọi hộp có viền ở file này; mỗi mục menu cao 28, bo 4, chữ 13. Variant hover của
`Conversation item` là `11:26`, và hộp xác nhận là `Consequence dialog — xoá đoạn chat` (`455:2195`),
460×202.

**Xoá đi qua hộp xác nhận**, dùng lại `.veil` / `.confirm` của biểu mẫu phát hành. Dưới lớp sơn nó là
xoá mềm (`deleted_at`), nhưng trên màn hình này không có nút hoàn tác nào — nên với người bấm nút đó
là một việc một chiều, và nó phải được hỏi lại. Xoá đoạn **đang mở** thì màn hình rời sang
`/teacher/moi`: đứng lại là đứng trên một màn hình mà mọi lần đọc lại từ nay sẽ ra 404.

## Ngăn `TÀI LIỆU` — chip in kích thước, không in số trang

Tài liệu tải lên được và liệt kê được; **nội dung của chúng chưa đi vào việc soạn đề**. Mỗi chip vì
thế in kích thước (`B` / `KB` / `MB`, dấu thập phân phẩy) chứ không in số trang: một con số trang
nói rằng hệ thống đã mở tệp ra đọc, và nó chưa mở. `documents` cũng không có cột số trang, nên đây
là một luật của schema chứ không chỉ của màn hình (ADR-04).

Dải dưới ô nhập, sau một lần tải lên, in `Đã tải lên: {tên tệp}` kèm nút `Tải tệp khác`, và một dòng
nhỏ nói thẳng rằng nội dung chưa được dùng để soạn đề. Đo trên artboard `2 · Kèm tài liệu` (`85:327`):
dải 820×33, dòng nhỏ rộng 820, thụt vào **12** so với mép dải và cách dải **6**, cỡ chữ `--type-caption`. Nó **từng** in *"Đổi phạm vi"* — chữ ấy hứa
một việc không xảy ra: thân request của một lượt chat đúng ba field (`text`, `conversation_id`,
`start_new`), không có `document_id` nào.

## Bề rộng, và chỗ duy nhất đọc được những con số này

Rail luôn **260**, panel đề luôn **420**, cột giữa cố định **820** và co còn **660** khi panel mở. Ba
con số sau chỉ đọc được từ artboard 6/7/8, nên chúng được ghi lại ở đây. Rail dán mép trái cửa sổ và
chỗ dư rơi vào cột giữa: rail là đồ nội thất của cửa sổ, không phải của trang.

## Composer trong lúc Kriky làm việc

Hai artboard nói hai chuyện: `2 · Kèm tài liệu` (`85:327`) để composer ở trạng thái `rỗng`, còn
`4 · Kriky đang làm` (`84:421`) để `disabled`. Cả hai đều vẽ khoảnh khắc **sau** khi gửi — thread của
artboard 2 có `Assistant thinking` — nên đây là mâu thuẫn thật, không phải hai khoảnh khắc khác nhau.
**Luật đã chốt: khoá từ lúc gửi cho tới khi lượt kết thúc**, theo artboard 4: một ô nhập mở trong lúc
BE không nhận câu thứ hai là một lời mời gõ vào chỗ không ai đọc. Composer của artboard 2 đã được đổi
sang `disabled` cho khớp.

## Những chỗ FE được phép có mà Figma không vẽ

Thiết kế không vẽ trạng thái rỗng và trạng thái đang tải cho mọi khối; FE vẫn phải có chúng. Hai luật
đi kèm: chữ phải nói **vì sao** trống chứ không chỉ nói trống, và mỗi chuỗi như vậy được thêm vào
Figma thành một variant trong **cùng change set** đã thêm nó. Một chuỗi sống trong code mà không có
chỗ đứng trong thiết kế là một chỗ lệch đang chờ ngày bị phát hiện.

Tuyệt đối không in **chuỗi kỹ thuật** ra bề mặt giáo viên: tên tool, tên state máy, id. Một thẻ không
nhận ra mình đang kể việc gì thì **không vẽ thẻ**; một bước không có tên tiếng Việt thì hiện là
*"Một bước nữa"*. Đường lùi của một bảng tra cứu không bao giờ được là chính cái khoá của nó —
`STEP_TITLE[name] ?? name` là cách lỗi này lọt vào lần đầu, và nó lọt vào cùng change set đã viết ra
câu cấm này.
