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
| 4 | Thẻ kết quả | `Action result card` (`10:63`) | **Một thẻ cho việc của model, cộng một thẻ cho mỗi việc giáo viên tự làm** |

Luật thẻ có **hai nửa**, vì nó trả lời hai câu hỏi khác nhau. Một lượt của model là *một* việc được
nhờ dù nó đi qua năm bước tool, nên nó có *một* kết quả — đó là nửa cũ, và nó không đổi. Nhưng mỗi
lần giáo viên tự duyệt, tự bỏ duyệt hay tự phát hành là một **biên bản riêng** mà ADR-24 đòi phải
sống sót; gộp chúng vào "một thẻ cho một lượt" thì cú sau xoá cú trước, và màn hình nói *"Đã bỏ duyệt
đề"* như thể chưa ai từng duyệt.

Hai nửa ấy gặp nhau trong **cùng một khối**, vì khối chỉ cắt ở lượt của giáo viên nói — mà bấm *Duyệt
đề* trên panel không phải một lượt nói. Nên một khối thường có **cả hai**: thẻ *Đã thêm N câu vào đề*
của model, rồi thẻ *Đã duyệt đề* của giáo viên, theo thứ tự thời gian.

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
| `list_class` | một bước trong `Thinking` | Trả cả danh sách lớp, và danh sách ấy **chính là** bộ phương án: khoá `candidates` là thứ `_choices_from` dựng nút từ đó. Nhiều hơn một lớp thì lượt kết thúc bằng `Clarify request`, không phải thẻ |
| `get_class` | một bước | Nhận `class_id`, không nhận tên. Việc gỡ nhập nhằng đã về `list_class` |
| `list_assessment` | một bước | Đề **đã phát hành** cho một lớp. Đề nháp chưa phát hành không thuộc lớp nào, nên không nằm ở đây |
| `class_assessment_summary` | một bước | Kết quả đi vào câu kết |
| `create_draft` | một bước. **Thẻ** nấc `drafted`, variant `tạo-đề-trống`, **chỉ** khi không bước nào trong lượt đổ câu vào đề ấy | Có `start_drafting` phía sau thì trạng thái trống **không còn đứng vững** — chính bước sau đã thay nó, nên không thẻ nào. Thất bại → nấc `failed`, variant `tạo-thất-bại` |
| `start_drafting` | một bước. **Thẻ** nấc `drafted`, variant `đã-tạo-đề`, **chỉ khi** bước ấy đã đợi hết câu và mang về `written`/`asked_for`/`still_drafting` | Chưa có ba con số ấy thì vẫn chỉ là một bước: một thẻ ở đó nói với giáo viên rằng một việc đã xong trong khi nó vừa bắt đầu. Cửa `POST` không đợi, nên ở đó không bao giờ có thẻ |

`draft_progress` **đã bỏ**. SSE kể tiến độ ngay khi từng câu về, nên một tool chỉ để ngó là một tool
không ai gọi — và nó là tool duy nhất của pha 1 từng phải `harvest`, tức từng phải ghi. Bỏ nó làm
câu *"pha 1 không ghi gì"* (ADR-25) đúng ở mọi dòng thay vì đúng trừ một.

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
  nút đọc ra là *hai viên xanh*, và giáo viên bấm nhầm. Figma vẽ sai y vậy ở gần hết component
  set; variant `đã-duyệt` thì vẽ đúng từ đầu, nên đây là luật của nó mở rộng ra cả bộ.

**Khoảng trống đã đóng.** Tới hết đợt ADR-25, một lượt soạn đề **thành công** kết thúc không thẻ
nào: `create_draft` bị loại khi có `start_drafting` phía sau, `start_drafting` bị loại vô điều kiện,
và tool kiểm tiến độ là tool của pha 1 nên một plan không gọi nó. Ba lần loại trừ ấy giao nhau đúng
ở đường đi hạnh phúc — mà panel đề **chỉ mở được từ một nút trên thẻ**, nên Kriky nói *"đã soạn
xong"* và màn hình không có cửa nào vào xem. Nay bước soạn khi đóng lại đã biết số câu thật, và nó
lên thẻ ở nấc `drafted`.

**Bốn đầu đề, và chỉ bốn.** Người dùng chốt ngày 06/10/2026: *"thẻ chỉ xuất hiện một lần trong một
đợt xử lí, không được phép xuất hiện hai lần liên tiếp. Trên đó chỉ hiện ba trạng thái: đã tạo đề →
đã duyệt đề → đã phát hành. Nếu chọn bỏ duyệt đề thì quay lại 'đã tạo đề'."* Cộng một nấc cho việc
**không** xảy ra, là bốn.

| Nấc | Head | Variant Figma | Nút chính |
| --- | --- | --- | --- |
| `drafted` | `Đã tạo đề "{tên}"` | `đã-tạo-đề` (`66:16`) | — |
| `drafted`, đề còn rỗng | `Đã tạo đề "{tên}"` | `tạo-đề-trống` (`66:3`) | `Thêm câu hỏi` (điền ô nhập) |
| `approved` | `Đã duyệt đề "{tên}"` | `đã-duyệt` (`66:29`) | — |
| `published` | `Đã phát hành` | `đã-phát-hành` (`10:45`) | — |
| `failed` | `Không tạo được đề` | `tạo-thất-bại` (`10:54`) | `Thử lại` (điền ô nhập) |

**Năm variant, bốn đầu đề.** `tạo-đề-trống` và `đã-tạo-đề` dùng chung đầu đề vì chúng là **cùng một
nấc**: đề vừa mở còn rỗng thì có thêm một nút mời bước tiếp theo, và một cái nút không phải một
trạng thái. `tạo-đề-trống` chỉ mọc cho một lượt *chỉ* mở đề — khi giáo viên nói *"tạo đề 10 câu"* thì
plan có hai bước (ADR-25) và trạng thái "trống" không còn đứng vững, vì chính bước sau đã thay nó.

**Năm variant khác đã thành *(không dùng)*, và lý do nằm ở dữ liệu chứ không ở màn hình:**

| Variant | Vì sao không ai tới được |
| --- | --- |
| `bỏ-duyệt` (`76:10`) | Bỏ duyệt đưa đề **về** nấc một, nên nó không có thẻ riêng — thẻ quay lại kể *đã tạo đề* |
| `thiếu-câu` (`455:16`) | Đầu đề chở con số, mà con số đã nằm ở khối `Thinking` ngay trên thẻ |
| `đang-soạn-dở` (`456:16`) | Như trên |
| `phát-hành-thất-bại` (`76:23`) | `_note_publication` **chỉ** ghi lượt khi phát hành thành công, nên một lần phát hành hỏng không bao giờ tới đây. Biểu mẫu phát hành phải tự hiện phần thất bại tại chỗ |
| `tạo-lớp` (`10:34`) | Không tool nào tạo lớp |

Giữ lại chứ không xoá khỏi Figma: chúng là bản ghi của những nấc đã thử và đã bỏ. Variant
`thêm-câu-hỏi` thì **chưa bao giờ tồn tại** trong component set — nó là một cái tên đi lạc vào
tài liệu từ thời `draft_progress`, và tool ấy đã bỏ vì SSE kể tiến độ.

**Nơi thi hành là check thứ 12 của `tools/check_contract.py`.** Nó đếm ba thứ phải khớp nhau —
union `CardState`, bảng `HEAD`, bảng `SAFETY` — và đỏ khi một trong ba mọc thêm dòng hoặc khi ba
cái không cùng một bộ tên. Cộng hai chốt nữa trên **vùng vẽ thẻ** (từ bảng `HEAD` tới hết file):
nhiều nhất **một** phép so `tool_name`, và **không** `switch`/`includes`/tra-bảng-tại-chỗ nào.

Nó là một phép quét có khoanh vùng, **không** phải một bộ parse TypeScript — nên nó đo được số
nấc chứ không đo được mọi cách viết. Bản đầu chỉ đếm `HEAD` bằng một regex neo đầu dòng, và một
đợt review tìm ra ba khe trong một buổi: nấc thứ năm viết **chung dòng**, một `switch` thay cho
phép so, và cả vùng phía trên `export default` không ai nhìn. Vì thế ba trong bốn phép kiểm ở
đây sinh ra từ một đột biến đã chạy thật, không từ một mối lo đoán trước.

Một phép so được phép, và nó có tên: `create_draft` phân biệt một đề vừa mở còn rỗng. Cái đó
thêm một **nút**, không thêm một trạng thái — và nó có test riêng, vì không có test thì
`const empty = false` xoá sạch nút ấy mà cả check lẫn bộ test đều xanh (đo được).

Tất cả vì đó là cách bảy đầu đề mọc ra lần trước: giao diện được dựng bằng một dãy
`if (turn.tool_name === …)`, nên **thêm một tool là thêm một trạng thái**. Không dòng code nào
sai; cái sai là không chỗ nào đếm.

**Luật *"đề thiếu câu thì không mời duyệt"* đổi chỗ hai lần, và chỗ cuối là chỗ chắc nhất.** Đầu
tiên nó sống trong nhãn nút (`Xem đề` thay vì `Duyệt đề`); nút bỏ thì nó sang chữ đầu đề (`Dừng ở
2/10 câu`); nay đầu đề chỉ còn bốn chuỗi cố định, nên nó sống ở chỗ nó đáng sống từ đầu — **thẻ
không có cổng duyệt nào cả**. Cổng thật ở chân panel, nơi duy nhất đọc được trạng thái **hiện tại**
của đề, chứ không phải một con số đóng băng trong một biên bản cũ.

**Nút mời một việc làm bằng lời nói thì điền sẵn ô nhập.** `Thêm câu hỏi` và `Thử lại` không có
endpoint nào để gọi — thêm câu hỏi là một câu nói với Kriky, không phải một nút trên REST. Hai nút ấy
đặt con trỏ vào ô nhập và viết sẵn câu mở đầu; giáo viên sửa rồi gửi. Nút nào mời một việc **có** cổng
thì đi thẳng tới cổng ấy — và với *"mở đề"* thì cổng ấy là **chính cái thẻ**.

**Một thẻ cho cả khối**, nên cú bấm cuối cùng thắng. Đó là nửa thứ hai của câu người dùng chốt:
*"không được phép xuất hiện hai lần liên tiếp"*. `cardTurns` không đọc `entity_id`, nên duyệt đề A
rồi phát hành đề B trong cùng một khối chỉ kể B — một giới hạn có thật, chưa có đường nào tới được
nó (một khối bị cắt ở mỗi lượt `teacher`), và nó được ghi ra ở docstring của hàm chứ không giấu đi.

**Tên lớp rời khỏi đầu đề:** `Đã phát hành`, không `Đã phát hành cho 12A và 12B`. Một đầu đề đổi
chữ theo dữ liệu là một trạng thái thứ tư trá hình: hai lần phát hành cho hai bộ lớp đọc ra như hai
nấc khác nhau của cùng một đề.

**Thẻ của một việc giáo viên tự làm là biên bản, không phải bộ điều khiển.** Nấc `approved` không
còn nút nào, và không còn dòng chi tiết nào — bấm vào **chính cái thẻ** là mở panel. Hai lý do, cả
hai đo được:

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

`Thu hồi` **không nằm trên thẻ**, và đó là một quyết định chứ không phải một món nợ. Thẻ là biên
bản; chỗ lùi một bước là **chân panel**, nơi duy nhất đọc được trạng thái hiện tại của đề — và từ
06/10/2026 nút ở đó là `Hoàn tác`, nó thu hồi mọi lớp rồi hạ hai nấc trong một cú bấm (ADR-02).
Figma `đã-phát-hành` (`10:45`) vẫn còn vẽ một `btn-recall`; **đó là món nợ Figma**, không phải món
nợ code.

Nút `Phát hành` không bao giờ xuất hiện trên một thẻ nào — phát hành đi qua biểu mẫu và hộp xác
nhận (ADR-05, ADR-10).

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

## Biểu mẫu phát hành — hai bậc nhãn, và câu luật nói đúng số đang gõ

**Câu luật điền bằng khuôn, không dựng sẵn.** Bản trước in `rules.phase_one` — một câu BE dựng với
`--:--` và FE tải **một lần lúc mở màn**. Nó đứng ngay dưới mấy ô nhập, trông như sắp đổi theo con
số vừa gõ, mà về cấu trúc thì không bao giờ đổi được. Một câu luật nói sai số ngay cạnh chỗ gõ số
tệ hơn hẳn một câu luật vắng mặt.

Nay `publication_wording.PHASE_ONE` / `PHASE_TWO` là **khuôn**, và là nguồn duy nhất của chữ nghĩa
ấy: BE dựng câu thật bằng chính chúng, biểu mẫu nhận chúng qua `rules.phase_one_form` rồi điền số
đang gõ. Đổi một chữ trong khuôn là đổi ở cả bốn chỗ ADR-03 đòi phải giống nhau. Hộp xác nhận và
biên bản **không** dùng khuôn — chúng có số thật và nhận câu đã dựng từ BE.

Cái giá, nói đủ: **bốn** thứ có hai bản — phép cộng *giờ đóng + phút làm bài*, tên bốn chỗ trống,
`--:--`, và `--`. Chữ nghĩa thì không. Ba thứ sau là hợp đồng giữa `publication_wording.py` và
`PublishSettings.tsx`, và nơi thi hành là check thứ chín trong `tools/check_contract.py`: đổi
`{last}` thành `{last_submission}` ở BE là một thay đổi **xanh hết mọi lưới khác** — BE tự sửa cùng
lúc, `tsc` không biết gì về nội dung chuỗi, test FE dùng khuôn trong fixture của chính nó — và thứ
duy nhất đổi là biểu mẫu thật in ra `{last_submission}` nguyên văn. Phép cộng thì được ghim bằng
một test BE và ba test FE, gồm ca `23:50 + 20` mà một phép cộng viết ẩu cho ra `23:70`.

**Và biểu mẫu tôn trọng khoảng BE nhận.** `min={1}` của một ô số không ngăn người ta gõ `-15`, và
khi ấy câu luật in ra *"đóng 18:00 - có thể nộp lúc 17:45"* — một câu tự phản bác, đúng con số
17:45 mà ADR-03 dành cả tài liệu để chống. Ngoài khoảng `1..600` thì chỗ trống ở lại: chưa nói gì
còn hơn nói sai.

**Vạch ngăn mang class `divider`, không phải `rule`.** Hộp xác nhận đã dùng `.rule` cho ba câu luật
của nó, và `Veil` không dựng qua portal — nên cả hộp nằm *bên trong* `.publish-settings`, và một
luật `.publish-settings .rule { height: 1px }` bóp ba câu ấy xuống cao một pixel. `tsc` không thấy,
jsdom không thấy; thứ ghim được là cái tên.

**Hai bậc nhãn.** Biểu mẫu từng có **tám** nhãn VIẾT HOA cùng một sức nặng — `LỚP`, `PHA 1`,
`LÀM BÀI`, `MỞ LÚC`, `ĐÓNG LÚC`, `PHA 2`, `PHÚT MỖI CÂU`, `HẠN CHỮA XONG` — nên nhãn mục và nhãn
trường trông y hệt nhau, và mắt không có bậc nào để bám. Nay `.caps` còn đúng ba chỗ (tên ba mục),
còn nhãn từng ô là `.label`: chữ thường, nhạt hơn, không đậm.

**Một vạch `--line` 1px trên mỗi mục pha**, không phải một khối viền: trong cột 420 thì ba cái hộp
lồng nhau đọc ra nặng hơn chứ không nhẹ đi.

**Và biểu mẫu thôi đếm lớp.** Dòng *"Đã chọn x trong y lớp · z học sinh"* đi mất: các chip lớp ngay
trên nó đã nói ai được chọn, và con số đầu người thì nằm ở hộp xác nhận — chỗ nó thật sự chịu lực.

**Chip lớp mang `aria-pressed`.** Nó là một toggle thật, nhưng dấu ✓ đã `aria-hidden` và
`class-chip on` là chuyện của CSS — nên thiếu thuộc tính ấy thì trình đọc màn hình đọc *"12A,
button"* y hệt dù đã chọn hay chưa. Đây là nút quyết định **ai nhận đề** (ADR-02), tức chỗ tệ nhất
để một người không biết mình vừa chọn gì.

**Cửa sổ thời gian vô lý bị chặn TRƯỚC cú bấm, bằng đúng lời của BE.** Biểu mẫu từng nhận mở-20:00 /
đóng-08:00 rồi vẫn sáng nút, và câu luật ngay dưới in ra *"Vào tham gia tới hết 08:00 - có thể nộp
lúc 08:15"* bằng giọng khẳng định. Cổng thật vẫn ở `_schedule_fault`; biểu mẫu chỉ nói sớm hơn, và
mượn nguyên ba hằng `FAULT_*` qua payload thay vì viết lại — ADR-03 đòi mọi nơi nói giống hệt nhau,
và một lời từ chối cũng là một nơi nói ra luật ấy. `check_the_form_fills_the_slots_the_wording_declares`
giữ việc mượn ấy; ba test giữ ba phép so, trong đó mốc *giờ nộp cuối* có test riêng vì nó là con số
ADR-03 dành cả tài liệu để chống.

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
- **Đáp án đúng đổi được, bằng một nhóm radio.** Trước đó phương án đúng chỉ có một cái nhãn và
  không control nào — nên thứ duy nhất hỏng ở một câu model soạn sai lại là thứ duy nhất giáo viên
  không sửa được. Đo được trên dữ liệu thật: một câu có đáp án đúng là `1/2`, bốn phương án không
  chứa `1/2`, và `1/3` đang đeo dấu đúng. Cổng người thứ nhất của ADR-05 hở đúng chỗ ấy.

  Nhóm radio **không** tự giữ ADR-18: `checked` đi từ state, nên thứ bỏ cờ cũ là `onChange`. Và nó
  **không xoá** nhãn lỗi của phương án vừa thành đúng — `OptionEdit` ở BE nói thẳng rằng nhãn gửi
  kèm đáp án đúng thì bị bỏ, không bị từ chối, nên xoá ở FE chỉ mua được một thứ: bấm nhầm rồi bấm
  lại là mất chữ giáo viên đã gõ tay.
- **Nút Lưu khoá khi còn nhiễu nào chưa có nhãn lỗi**, kèm một câu tiếng Việt. Đổi đáp án đúng biến
  phương án cũ thành một phương án nhiễu, mà nó thường chưa có nhãn — để cú bấm ấy đi tới BE thì
  lời từ chối về là `distractors ['A'] carry no error label: <cả đề bài>`.

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
