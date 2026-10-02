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
| `start_drafting` | **chỉ là một bước** — không có variant thẻ nào | Figma không vẽ thẻ cho nó, và một thẻ tự chế ở đây nói với giáo viên rằng một việc đã xong trong khi nó vừa bắt đầu |
| `draft_progress` | một bước; **thẻ** `thêm-câu-hỏi` khi các câu đã về đủ | Thẻ ghi số câu **thật đã có**, không ghi số chỗ đã đặt |

Một tool mới phải có dòng trong bảng này **trước** khi nó có mặt trên màn hình. Không có dòng nào thì
nó là một bước, không phải một thẻ — mặc định an toàn, vì một bước không hứa gì.

## `Thinking` — các bước là bằng chứng, không phải hiệu ứng chờ

Mô tả component nói thẳng: *"các bước CHÍNH LÀ BẰNG CHỨNG cho biết đề được dựng ra thế nào, nên nó
thu gọn được nhưng không bao giờ mất."* Giáo viên đứng trước cổng duyệt cần biết câu hỏi từ đâu ra.

| Trạng thái | Khi nào | Hình dạng | Thu gọn được? |
| --- | --- | --- | --- |
| `đang chạy` (`83:72`) | Lượt đang chạy | Mở sẵn. Header là **tiêu đề của bước đang chạy** kèm `…`, bên phải là `bước k/n`; bước ấy đánh `○` | Được |

> **`đang chạy` chưa nối dữ liệu, nhưng `k/n` nay là số thật.** BE đã có một dãy sự kiện cho
> từng bước (`run_turn` phát `plan`, `step_started`, `step_done`, `step_failed`), và `n` đọc từ
> số bước của plan — nói được `bước 3/5` chính vì plan có **trước** khi chạy (ADR-25). Chỗ còn
> thiếu là **cửa ra**: `POST` rút cạn dãy ấy rồi chỉ trả trạng thái cuối, nên FE vẫn nhận cả
> lượt một lần và mọi bước tới nơi đã là `✓` hoặc `✕`. Dấu `○` và nhãn `bước k/n` vì thế **chưa
> chạy lần nào**; chúng sống khi đường SSE mở. Ngày ấy tới thì phải sửa thêm một chỗ: khối đang
> mở vì đang chạy phải **tự thu lại** lúc lượt xong, mà state hiện giữ nguyên lựa chọn của
> người đọc.
| `đã xong` (`83:73`) | Lượt kết thúc **thành công** | **Tự thu lại** còn một dòng `Đã làm {n} bước` | Đang thu |
| `đã xong — mở` (`83:74`) | Người dùng bấm chevron | Mở lại đầy đủ các bước | Được |
| `thất bại` (`83:75`) | Lượt dừng vì một bước hỏng | Mở sẵn. Header `Dừng ở bước {k} — {lý do}`; bước hỏng đánh `✕` kèm dòng giải thích | **Không.** Thu một lỗi lại là giấu lỗi |

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

| Variant | Head | Nút chính | Nút phụ |
| --- | --- | --- | --- |
| `tạo-đề-trống` | `Đã tạo đề "{tên}"` · detail `Chưa có câu hỏi nào` | `Thêm câu hỏi` | — |

**`tạo-đề-trống` chỉ mọc cho một lượt *chỉ* mở đề** — giáo viên nói *"mở cho tôi một đề trống"*. Khi
họ nói *"tạo đề 10 câu"* thì plan có hai bước (ADR-25) và thẻ này **không được xuất hiện**: nó nói
rằng việc được nhờ đã xong và cho ra một cái đề rỗng, trong khi việc ấy đang chạy. Một đề chưa đủ
câu ở lại **trong khối bước**, và câu báo cáo cuối lượt nói nó đang tới đâu.
| `thêm-câu-hỏi` | `Đã thêm {n} câu vào đề` | `Duyệt đề` | `Xem` |
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
