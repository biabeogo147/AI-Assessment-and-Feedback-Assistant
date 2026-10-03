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

- **Mỗi thẻ nói hậu quả của việc vừa xong**, bằng một chip `safety` **trên cùng dòng với đầu đề**,
  đẩy về mép phải — *"Đề trống, chưa phát hành được"*, *"Chưa duyệt · chưa phát hành"*, *"Chưa có gì
  được thay đổi"*. Cùng dòng vì cả hai nói về một sự việc: việc gì vừa xảy ra, và nó đã tới tay học
  sinh chưa; hai dòng cho một sự việc là một dòng thừa. Chip **không** thừa kế màu của đầu đề dù giờ
  nằm trong nó: màu chip nói chuyện khác, và một `color` khai báo thẳng luôn thắng giá trị thừa kế.
  Variant
  `đã-phát-hành` khác hình: **không có chip `safety`**, mà có ba dòng chữ trần — câu khoá–thu hồi,
  câu luật pha 1, câu luật pha 2. FE hiện gói hậu quả ấy vào **một** chip một dòng; ba dòng của
  thiết kế cần biểu mẫu phát hành trả về chúng, và đó là nợ chưa trả. Điều không được phép nhân
  nhượng: một thẻ im lặng về hậu quả là một thẻ mời người ta tưởng là xong, và thẻ có hậu quả lớn
  nhất mà im lặng thì là lỗi nặng nhất trong nhóm này.
- **Bấm vào thẻ là mở panel đề**, và thẻ không mang nút nào cho việc ấy. Trước đó mỗi thẻ có một
  nút `Duyệt đề` / `Xem đề` / `Xem`, và cả năm nhãn gọi đúng một hàm — năm cách gọi tên cho một
  việc là năm lời hứa khác nhau về một thứ. Thẻ nào **không có đề** thì nằm yên: không `role`,
  không con trỏ, vì một thẻ bấm được mà chẳng mở gì tệ hơn hẳn một thẻ nằm yên.
- **Nút chỉ còn ở chỗ làm việc khác.** `Thử lại` và `Thêm câu hỏi` điền sẵn ô nhập; chúng chặn nổi
  bọt, nếu không một cú bấm vừa điền ô nhập vừa mở panel.
- **Không thẻ nào còn dòng `detail`.** Nội dung của nó do model hoặc BE ghép, khó kiểm soát trong
  thực tế — và sau khi nút biến mất thì một dòng chữ tự do giữa đầu đề và chip chỉ làm loãng thẻ.
- **Nút chính và nút phụ không được đọc ra giống nhau.** Nút chính: nền `--accent`, chữ trắng,
  không viền. Nút phụ: **không nền, không viền**, chữ `--ink-muted`. Trước đợt này nút phụ dùng
  đúng màu `--accent` mà nút chính dùng cho nền, cùng cỡ chữ, cùng cân nặng, cùng bo góc — hai
  nút đọc ra là *hai viên xanh*, và giáo viên bấm nhầm. Figma vẽ sai y vậy ở tám trên chín
  variant; variant `đã-duyệt` thì vẽ đúng từ đầu, nên đây là luật của nó mở rộng ra cả bộ.

**Khoảng trống đã đóng.** Tới hết đợt ADR-25, một lượt soạn đề **thành công** kết thúc không thẻ
nào: `create_draft` bị loại khi có `start_drafting` phía sau, `start_drafting` bị loại vô điều kiện,
và `draft_progress` là tool của pha 1 nên một plan không gọi nó. Ba lần loại trừ ấy giao nhau đúng ở
đường đi hạnh phúc — mà panel đề **chỉ mở được từ một nút trên thẻ**, nên Kriky nói *"đã soạn xong"*
và màn hình không có cửa nào vào xem. Nay bước soạn khi đóng lại đã biết số câu thật, và thẻ
`thêm-câu-hỏi` mọc từ chính nó.

| Variant | Head | Nút chính | Nút phụ |
| --- | --- | --- | --- |
| `tạo-đề-trống` | `Đã tạo đề "{tên}"` | `Thêm câu hỏi` (điền ô nhập) | — |

**`tạo-đề-trống` chỉ mọc cho một lượt *chỉ* mở đề** — giáo viên nói *"mở cho tôi một đề trống"*. Khi
họ nói *"tạo đề 10 câu"* thì plan có hai bước (ADR-25) và thẻ này **không được xuất hiện**: nó nói
rằng việc được nhờ đã xong và cho ra một cái đề rỗng, trong khi việc ấy đang chạy. Một đề chưa đủ
câu ở lại **trong khối bước**, và câu báo cáo cuối lượt nói nó đang tới đâu.
| `thêm-câu-hỏi` | `Đã thêm {n} câu vào đề` | — | — |
| `thiếu-câu` (`455:16`) | `Dừng ở {k}/{n} câu` | — | — |
| `đang-soạn-dở` (`456:16`) | `Đã soạn {k}/{n} câu` | — | — |

**Điều kiện mời duyệt là `đã đủ câu`, và chỉ thế.** Không phải *"thiếu câu **và** không còn gì đang
chạy"* — viết thế thì một đề 3/10 còn bảy câu đang chạy rơi vào nhánh còn lại, thẻ in `Đã thêm 3 câu
vào đề` (giấu mất số 10) và mời duyệt. Đường ra ấy có thật: hết hạn im lặng thì vòng nghe chuông
đóng lại với `still_drafting > 0`. Và nó cãi lại `reporting._progress` của AGENT, nơi lời kể trong
cùng ca ấy chỉ được nói *"đang soạn"*.

| `đã-duyệt` | `Đã duyệt đề "{tên}"` | — | — |
| `bỏ-duyệt` | `Đã bỏ duyệt đề "{tên}"` | — | — |
| `tạo-thất-bại` | `Không tạo được đề` | `Thử lại` (điền ô nhập) | — |
| `đã-phát-hành` | `Đã phát hành cho {lớp}` | — | `Thu hồi` — **chưa dựng** |
| `phát-hành-thất-bại` | `Phát hành chưa xong` | `Thử lại cho {lớp}` (điền ô nhập) | — |
| `tạo-lớp` | `Đã tạo lớp {tên}` | — | — |

**Nút mời một việc làm bằng lời nói thì điền sẵn ô nhập.** `Thêm câu hỏi` và `Thử lại` không có
endpoint nào để gọi — thêm câu hỏi là một câu nói với Kriky, không phải một nút trên REST. Hai nút ấy
đặt con trỏ vào ô nhập và viết sẵn câu mở đầu; giáo viên sửa rồi gửi. Nút nào mời một việc **có** cổng
thì đi thẳng tới cổng ấy — và với *"mở đề"* thì cổng ấy là **chính cái thẻ**.

**Luật *"đề thiếu câu thì không mời duyệt"* nay sống ở chữ đầu đề.** Nó từng sống trong nhãn nút
(`Xem đề` thay vì `Duyệt đề`); nút đã bỏ, nên `Dừng ở 2/10 câu` phải tự nói ra điều đó. Cổng duyệt
thật thì nằm ở chân panel, nơi duy nhất đọc được trạng thái hiện tại của đề.

**Thẻ của một việc giáo viên tự làm là biên bản, không phải bộ điều khiển.** `đã-duyệt` và `bỏ-duyệt`
chỉ còn **một** nút `Xem`, và không còn dòng chi tiết nào. Hai lý do, cả hai đo được:

- Ba nút cũ (`Phát hành`, `Hoàn tác`, `Duyệt đề`) **không chạy**. Duyệt thì bấm từ trong panel, nên
  lúc thẻ hiện ra route đã là `#/teacher/chat/{đoạn}/de/{đề}` rồi — mà cả ba chỉ gán lại đúng hash
  ấy, và một hash không đổi thì không bắn `hashchange` nào.
- Chỗ đổi trạng thái một đề là **chân panel**, nơi duy nhất nói trạng thái *hiện tại*. Hai thẻ duyệt
  và bỏ duyệt nằm cạnh nhau trong một đoạn chat cũ mà cả hai đều bấm được thì chúng nói hai chuyện
  trái nhau.

**Và việc giáo viên tự làm không vào khối `Thinking`.** `teacher.approve`, `teacher.unapprove`,
`teacher.publish` vẫn được ghi thành lượt — ADR-24 đòi biên bản duyệt sống sót — nhưng khối bước là
**bằng chứng model đã làm gì**, nên một dòng *Duyệt đề* trong đó nói rằng Kriky tự duyệt đề. Trước
đợt này một cú bấm hiện **hai lần**: một dòng trong khối bước và một cái thẻ.

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

## Phương án xếp hai cột, không bốn hàng

`options` của `Question card` (`307:17`) là một lưới `repeat(auto-fit, minmax(140px, 1fr))`, cỡ chữ
`--type-label` (13px, một bậc trên trước đây). Bốn phương án xếp dọc đẩy `Lời giải` xuống quá tầm
mắt, và panel là cột hẹp nhất của bề mặt — một đề mười câu thành mười lần cuộn.

`auto-fit` chứ không `repeat(2, 1fr)` cứng, vì hai chuyện: panel kéo hẹp tới 340 thì lưới tự rơi về
một cột thay vì cắt chữ làm đôi; và số phương án **không** luôn là bốn — ADR-18 chỉ đòi đúng một đáp
án đúng, nên năm phương án cho ra 2+2+1 chứ không phải một hàng tràn.

## Lời giải mở thành hộp thoại, không mở tại chỗ

Figma đã vẽ sẵn: `Solution dialog` (`309:41`, 680×431) và artboard `12 · Xem lời giải một câu`
(`309:1415`). Hộp mang bốn phần — tiêu đề `Lời giải — Câu n` kèm nút `Đóng`, đề bài, các cách giải,
và **ánh xạ mỗi phương án nhiễu gắn một lỗi**.

Phần cuối là lý do hộp thoại tồn tại. `error_label` nằm trong response từ lâu mà **panel chưa bao
giờ vẽ nó**, vì nó không vừa một cột rộng 380 — và nó là thứ nói cho giáo viên biết mỗi phương án
sai sai ở đâu, tức phần đáng đọc nhất.

**Số đo, đối chiếu sau khi dựng** (`Solution dialog` `309:41`): hộp 680, bo 14, viền `--line` (không
phải `--line-strong` của hộp xác nhận), padding 28; khối cách giải nền `--sunken` và **không viền** —
một mảng nền chìm là một phần của hộp, thêm viền vào thì nó thành một hộp rời nằm trong hộp; cột
nhãn phương án 120; mỗi dòng padding dọc 6.

**Ba khối chữ của hộp giữ nguyên xuống dòng** (`white-space: pre-wrap` trên `.solution-stem`,
`.ways .way .body`, `.fault .why`). Một lời giải ba bước xuống dòng giữa các bước, và không có luật
này thì cả ba bước dính thành một dải chữ. Bong bóng chat có `pre-wrap` từ lâu; hộp này thì chưa
bao giờ, và nó là chỗ chữ dài nhất của cả bề mặt.

**Hai màu của khối nhiễu là màu *có nghĩa*, không phải hai sắc độ cho đẹp.** ADR-12 chốt
`--answer-correct` là một câu trả lời đúng và `--answer-incorrect` là một câu sai, và đây đúng là
chỗ cần nói điều đó. Bản đầu của hộp này dùng `--accent` cho đáp án đúng và màu mực thường cho
phương án nhiễu — liếc một cái không phân biệt được đúng với sai, tức khối ấy mất hết việc của nó.

**Chữ trên bề mặt giáo viên nhỏ hơn bản vẽ 1–2px, và đó là cố ý**: `teacher.css` hạ `--type-label`
14→13 và `--type-caption` 12→11 cho cả bề mặt. Một phép đối chiếu với Figma sẽ báo lệch ở **mọi**
dòng chữ; đó là mật độ đã chọn, không phải lỗi từng chỗ.

**Mọi hộp thoại đi qua một khuôn chung** (`Veil.tsx`). Trước đợt này có ba bản sao của `.veil` +
`.confirm` ở ba file, và cả ba **cùng thiếu cùng ba thứ**: không đóng bằng `Esc`, không đóng bằng
cách bấm ra ngoài, và `.veil` không có `z-index` — trong khi menu `⋯` của rail có `z-index: 20` và
vẽ qua portal, nên một menu đang mở vẽ đè lên hộp thoại. Ba bản sao thiếu cùng ba thứ là dấu hiệu
của một khuôn chưa rút ra, không phải của ba lần quên. Hộp rộng dùng `.confirm.wide` (680, padding
27 = 28 trừ một cho viền).

## Chân panel đề — ba trạng thái, mỗi trạng thái một nút

| Trạng thái | Dòng chữ | Nút |
| --- | --- | --- |
| chưa duyệt | *Bạn duyệt xong mới phát hành được. Học sinh chưa nhìn thấy đề này.* | `Duyệt đề` |
| đã duyệt | *Nội dung đã khoá. Muốn sửa một câu thì hoàn tác trước.* | `Phát hành đề` — mở lại màn cài đặt phát hành |
| đã phát hành | *Đề đã tới học sinh. Muốn sửa thì thu hồi khỏi mọi lớp trước.* | `Phát hành thêm lớp` |

**Duyệt xong là sang THẲNG cài đặt phát hành.** Luồng thiết kế là màn 6 → màn 7. Trước đó cú bấm
`Duyệt đề` chỉ đổi chân panel thành hai nút rồi đứng im — một chặng dừng không có việc gì của riêng
nó, và giáo viên phải bấm thêm một lần nữa để tới đúng chỗ họ đang đi tới. Chặng ấy (artboard
`14 · Đã duyệt — chưa mở cài đặt phát hành`) đã bị xoá khỏi Figma.

Trạng thái *đã duyệt* vẫn **tới được** — mở lại một đề đã duyệt từ đoạn chat cũ, hoặc đóng màn 7 —
nhưng khi ấy chân panel chỉ còn một việc: mở lại màn 7.

**`Hoàn tác` sống ở màn cài đặt phát hành**, đứng trên nút chính. Một việc một chỗ: để đường lùi ở
cả chân panel lẫn màn 7 là cùng một việc có hai chỗ bấm, và hai chỗ bấm thì sớm muộn lệch nhau.
Đứng *trên* chứ không đứng *cạnh*, vì hai nút cạnh nhau đọc ra là hai lựa chọn ngang hàng mà bỏ
duyệt không ngang hàng với phát hành. Nút chính ở đó mang nhãn `Phát hành đề`, không mang con số
đầu người: con số ấy đã nằm ngay trên biểu mẫu, và chỗ nó thật sự chịu lực là **hộp xác nhận cuối
cùng** — nơi duy nhất không còn đường lùi nào sau đó.

**Ba trạng thái, không hai.** Gộp `đã phát hành` vào `đã duyệt` làm đường bỏ duyệt hiện ra cho một
đề đã tới tay học sinh — mà `POST .../unapprove` chỉ nhận đúng `APPROVED`, nên cú bấm ấy chắc chắn
trả 409. Đường lùi của một đề đã phát hành là **thu hồi**, không phải bỏ duyệt. Và nhãn `Phát hành
thêm lớp` nói đúng việc nút ấy làm: `_RELEASABLE` có cả `PUBLISHED`, nên bấm nó là thêm một lớp
nữa, không phải phát hành lại từ đầu.

Bản trước để đúng **một** nút ở chân panel, và với đề đã duyệt thì nút ấy bị khoá với nhãn *Đã
duyệt* — trong khi dòng chữ ngay trên bảo *"muốn sửa thì bỏ duyệt trước"*, một chỉ dẫn tới hành
động **không có trên màn hình**. `teacher.unapprove` đã nằm trong `api.ts` từ lâu mà **chưa một
dòng nào gọi**.

## Panel tách khỏi khung chat bằng **nền**, vạch chỉ là nét cuối

Số đo trên Figma: `panel` nền `#FFFFFF` + stroke `#E3E5E2` **cả bốn cạnh**; `questions` bên trong nó
nền `#FAFAF8` (`--paper`); mỗi `qcard` nền `#FFFFFF` có viền. Nghĩa là vùng câu hỏi của panel **cố ý**
cùng màu với cột giữa, và thẻ câu hỏi nổi lên nhờ chênh nền với nó.

Nên thứ tách panel khỏi khung chat là **vạch 1px**, không phải màu nền. Tôi đã thử bỏ nền `--paper`
của vùng câu hỏi cho panel toàn trắng; phép đo bác lại — bỏ nó thì `qcard` thành trắng trên trắng và
thứ duy nhất vạch ra một thẻ là một hairline.

Và vạch 1px dùng `box-shadow` **không `inset`**. Inset shadow của cha được vẽ **dưới** nền của con,
mà `.panel-questions`, `.panel-foot`, `.publish-settings` đều trải hết bề rộng — nên chúng phủ mất
đúng dải 1px ấy trên gần hết chiều cao, và vạch chỉ sống ở dải `.panel-head`, chỗ duy nhất không có
nền. Bỏ `inset` thì vạch nằm ngoài mép trái, trên cột giữa, và không con nào với tới được. Vẫn
không dùng `border`: một `border` ăn mất một pixel của 420.

## Nút `Sửa` thôi là một nút chết

Nó nằm trên mỗi thẻ câu hỏi từ lâu và **không có `onClick`**. Nay nó mở một ô soạn tại chỗ — bản
dựng của component `Question card — đang sửa` (`468:2050`).

**Gửi cả câu, không gửi từng mảnh.** ADR-18 là một luật về *quan hệ giữa các mảnh*: đúng một
phương án đúng, mọi phương án nhiễu có nhãn lỗi, hơn một lời giải. Nhận từng mảnh rời thì mỗi lần
sửa là một lần câu hỏi đi qua một trạng thái không ai kiểm được, và luật ấy chỉ còn đúng ở những
khoảnh khắc may mắn.

**Một câu sửa tay đi qua đúng cái lưới mà một câu model viết phải đi qua** — cùng một
`validate_question`, không phải một bản kiểm thứ hai viết riêng cho đường này. Hai bản kiểm của
cùng một luật là hai thứ chờ lệch nhau, và bản lỏng hơn sẽ là bản người ta đi qua.

**Số phương án và số lời giải KHÔNG cố định.** ADR-18 chỉ đòi đúng một đáp án đúng, mọi phương án
nhiễu có nhãn lỗi, và hơn một lời giải — nó không nói gì về con số bốn hay con số hai. Form sửa vì
thế thêm và bớt được, với ba luật đứng ngay trên màn hình thay vì đứng ở một lời từ chối:

- **Nhãn lỗi có ô riêng cho mỗi phương án nhiễu.** Không có ô này thì nút *Thêm phương án* chỉ dẫn
  tới một lần 422, vì ADR-18 bắt mọi nhiễu phải có nhãn.
- **Đáp án đúng không xoá được** — xoá nó là bỏ luật tính điểm của câu, một việc khác hẳn sửa chữ.
- **Nút xoá biến mất** khi còn đúng hai phương án, hoặc đúng hai lời giải; không để bấm rồi nhận
  một lời từ chối. Nhãn của phương án mới là chữ cái **trống đầu tiên**, không phải chữ sau chữ lớn
  nhất: xoá B rồi thêm lại cho ra B, không cho ra E.

**Cổng ADR-01**: chỉ sửa được khi đề còn mở. Đề đã duyệt thì nội dung khoá — chính cái khoá đó làm
việc duyệt có nghĩa — và đường mở lại là *Hoàn tác* ở màn cài đặt phát hành.

Lời từ chối hiện **ngay dưới ô gõ**, không đẩy lên dòng chung ở chân panel: ở đó nó đứng xa chỗ gõ
và không nói nó nói về câu nào, mà panel có thể đang hiện mười thẻ. Chữ gõ ở ô là **LaTeX nguồn**,
không phải công thức đã dựng hình — giáo viên thấy đúng thứ sẽ được lưu, và đúng thứ phép kiểm sẽ
đọc.

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

## Toán viết bằng LaTeX trong cặp `$`

Bốn prompt **cấm** LaTeX suốt một thời gian dài và không dòng code nào thi hành, nên model cứ viết.
Đo được trên panel thật, nguyên văn trước mặt giáo viên: `\int_{0}^{1}(3x^2 - 2x + 1)\, dx` và
`\(\frac{1}{3}\)`.

Hướng nay đổi: toán **được** viết bằng LaTeX, trong cặp `$`, và màn hình dựng hình nó. Unicode không
viết nổi phân số chồng tầng, tích phân có cận, căn hay giới hạn — mà đề Toán 12 đầy những thứ đó.

**Và nó KHÔNG phải một phép kiểm chặn.** `validate_question` từng từ chối công thức nằm ngoài cặp
`$`. Hệ quả đo được là một cái bẫy: mọi câu soạn **trước** khi hợp đồng ra đời đều không lưu lại
được — mở `Sửa`, không đổi một chữ nào, bấm `Lưu` thì 422. Công cụ duy nhất để dọn nội dung hỏng
lại từ chối lưu vì nội dung đang hỏng.

Hướng đã chốt: một công thức viết sai thì **hiện ra nguyên văn** và giáo viên sửa tay. `MathText`
đã làm đúng thế — KaTeX chạy với `throwOnError: false`, và chuỗi không có cặp `$` nào đi qua như
chữ thường. Một dòng LaTeX thô trên màn hình là thứ đọc được và sửa được; một lượt soạn bị giết vì
một dấu gạch chéo thì không.

Những phép kiểm còn lại của `validate_question` nói về **tính đúng của đề** — đúng một đáp án đúng,
mọi nhiễu có nhãn lỗi, đủ phương án, đủ lời giải — chứ không về cách gõ công thức. Khác biệt giữ
lại: cách gõ thì sửa được bằng mắt, còn một đề hai đáp án đúng thì không ai nhìn ra lúc học sinh
đang làm bài.

Phía màn hình, một component **`MathText`** thay cho `{text}` ở **mọi** chỗ chữ của model lên màn
hình, cả bề mặt giáo viên lẫn bề mặt học sinh: đề bài, phương án, lời giải, **nhãn lỗi**, và **bong
bóng chat** của cả hai bên.

Hai nhóm cuối suýt bị bỏ sót, và bỏ sót chúng thì đợt này làm mọi thứ **tệ hơn trước**: ba prompt
`propose`, `reporting`, `explain` sinh ra lời kể trong khung chat, và chúng vừa đổi từ *cấm LaTeX*
sang *bắt viết LaTeX* — nếu chỗ hiển thị không dựng hình thì giáo viên và học sinh nhận nguyên văn
`$\frac{1}{3}$` ở đúng ba bề mặt trước đây vẫn sạch. Nhãn lỗi thì hiện ngay trong hộp lời giải, cạnh
những công thức đã dựng hình đẹp. Hai bề mặt đi cùng một lượt: giáo
viên thấy công thức đẹp mà học sinh thấy `$x^2$` thô thì tệ hơn hiện trạng.

**Phép tách cụm toán là MỘT luật, và nó phải có cùng một bản cài đặt ở hai bên** —
`agent_gateway._MATH` và `MathText.MATH` dùng đúng một khuôn. Lệch nhau thì BE nói một câu hợp lệ
còn màn hình vẽ ra một thứ khác. Ba điều kiện quanh dấu `$`, mỗi cái mua bằng một ca hỏng đo được:
dấu mở **không dính chữ số** (`Một quyển 20$, hai quyển 40$` có hai dấu, số chẵn, và đoạn giữa bị
dựng thành công thức); **không khoảng trắng** ngay sau dấu mở hay ngay trước dấu đóng; và **cho phép
xuống dòng** bên trong, vì một công thức dài model ngắt dòng thì bản đầu in nguyên văn.

Nó nhận **bốn** kiểu dấu — `$…$`, `$$…$$`, `\(…\)`, `\[…\]` — không phải một. Hợp đồng mới là `$`,
nhưng dữ liệu đã lưu thì mang `\(…\)`: model viết thế suốt thời gian lệnh cấm không có nơi thi
hành. Nhận cả bốn nghĩa là corpus cũ đọc được ngay, không cần một lần chuyển đổi nào. Corpus Unicode
thuần không có dấu nào cũng đi qua nguyên vẹn.

**Một thứ không chữa được bằng dựng hình:** những row cũ có LaTeX **trần**, không dấu nào —
`\int_{0}^{1}(3x^2 - 2x + 1)\, dx` đứng giữa một câu tiếng Việt. Không có dấu thì không ai biết
công thức bắt đầu và kết thúc ở đâu, nên chúng ở lại dạng thô. Đoán bằng heuristic là đường đã được
cân nhắc và bỏ: `*` còn là phép nhân, nên một bộ lọc ngây thơ ăn cả toán thật. Chốt kiểm mới chặn
không cho sinh thêm row như vậy; row cũ thì sửa tay, hoặc soạn lại.

`throwOnError: false`: một công thức hỏng in ra chính nó bằng màu lỗi thay vì ném. Một câu hỏi xấu
vẫn phải đọc được, và một exception ở đó sẽ giết cả panel vì một dấu ngoặc thiếu.

## Ngăn `TÀI LIỆU` — chip in kích thước, không in số trang

Tài liệu tải lên được và liệt kê được; **nội dung của chúng chưa đi vào việc soạn đề**. Mỗi chip vì
thế in kích thước (`B` / `KB` / `MB`, dấu thập phân phẩy) chứ không in số trang: một con số trang
nói rằng hệ thống đã mở tệp ra đọc, và nó chưa mở. `documents` cũng không có cột số trang, nên đây
là một luật của schema chứ không chỉ của màn hình (ADR-04).

**Nút tải lên nằm trên đầu ngăn, không ở thanh chat.** Tài liệu thuộc về **giáo viên** và nằm trong
kho chung (ADR-04) — nó không thuộc về một đoạn chat nào, nên đặt nút ở composer là nói ngược lại
điều đó. Icon 16×16 dán mép phải nhãn `TÀI LIỆU`, đo trên Figma ở x=212 trong một `pane-head` rộng
228.

**Đính một tệp đã có vào một câu chat thì kéo thả**: kéo một chip từ rail, thả vào ô nhập. Chip
mang `document_id` chứ không mang tên tệp — tên tệp trùng nhau được, id thì không. Ô nhập lúc có
tệp đang lơ lửng trên nó đổi viền sang `--accent`, không đổi nền: đổi nền làm chữ đang gõ nhảy
tương phản ngay giữa lúc kéo.

Dải dưới ô nhập, sau một lần tải lên, in `Đã tải lên: {tên tệp}` và **không gì khác**: không nút,
không dòng chú thích. Tải lên có đúng **một** cửa — icon cạnh nhãn `TÀI LIỆU` — vì hai cửa cho cùng
một việc thì cửa nào cũng thành chỗ phải đoán. Đo trên artboard `2 · Kèm tài liệu` (`85:327`):
dải 820×33, cỡ chữ `--type-caption`. Nó **từng** in *"Đổi phạm vi"* — chữ ấy hứa
một việc không xảy ra: thân request của một lượt chat đúng ba field (`text`, `conversation_id`,
`start_new`), không có `document_id` nào.

## Bề rộng, và chỗ duy nhất đọc được những con số này

Rail **260** và panel đề **420** là hình dạng *lúc nghỉ*, không còn là hằng số: giáo viên kéo được
cả hai, và con số đã chọn sống qua F5 trong `localStorage`. Biên là rail 200–420 và panel 340–720 —
hẹp hơn thì tên đoạn chat cụt hoặc lưới hai cột của phương án gãy, rộng hơn thì một cột nuốt chỗ của
cột kia. Cột giữa **không** còn cố định: nó là `min(820px, 100%)`, và `min(660px, 100%)` khi panel
mở; một con số cứng ở đó sẽ tràn khỏi màn hình ngay khi panel kéo rộng.

Thanh kéo là một dải **7px** với `flex-basis: 7px` và hai lề âm `-3.5px` — lề âm trả lại đúng 7px ấy
cho bố cục, nên ba cột không xê dịch một pixel nào so với số đo Figma. Bản đầu viết `flex: 0 0 0`
cộng `width: 7px`, và với một flex item thì `flex-basis` thắng `width`: hộp rộng **0**, không có gì
để trỏ vào. Test jsdom không bắt được — nó bắn sự kiện thẳng vào element, không dựng bố cục — nên
chỗ này chỉ có một lưới duy nhất là đo trên trình duyệt thật.

Rail dán mép trái cửa sổ và chỗ dư rơi vào cột giữa: rail là đồ nội thất của cửa sổ, không phải của
trang. Cột giữa mang `min-width: 0`, nếu không thì `min-width: auto` mặc định của một flex item giữ
nó rộng bằng nội dung và chỗ thiếu bị lấy từ rail.

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
