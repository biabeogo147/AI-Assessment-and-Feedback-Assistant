# ADR-25 — Một lượt chat có hai pha: lên plan, rồi thực hiện plan

- **Trạng thái:** đã chốt, chưa thi hành
- **Ngày:** 2026-10-02
- **Mở rộng:** [ADR-23](adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md) (thêm một kết quả thứ tư)

## Bối cảnh

Một lượt chat của giáo viên hiện là **một vòng lặp phẳng**: model chọn một tool, BE chạy, model nhìn
kết quả rồi chọn tiếp, tối đa tám bước. Đọc và ghi trộn lẫn trong cùng vòng ấy, và lượt kết thúc ngay
khi model nói một câu.

Ba chỗ vỡ ra từ cùng một gốc.

**Thiết kế hứa một thứ vòng lặp phẳng không cấp được.** Artboard `4 · Kriky đang làm` in `bước 3/5`.
Chỉ nói được *3/5* khi **biết trước có 5 bước** — tức danh sách công việc phải tồn tại trước khi chạy.

**Một câu hỏi lại có thể bỏ lại việc đã làm dở.** Model được phép gọi `create_draft` rồi mới phát hiện
thiếu dữ kiện và hỏi lại. Database hiện có một đề rỗng sinh ra đúng theo đường đó, mang tên tác giả là
giáo viên, và không có đường nào xoá.

**Không ai báo cáo kết quả.** Lượt kết thúc bằng *"đang soạn"*; việc soạn chạy tiếp trong hàng đợi, và
câu kết của artboard 5 — *"Đề đã đủ 10 câu: 8 câu lấy từ ngân hàng, 2 câu tôi soạn thêm"* — không có
chỗ nào sinh ra được.

## Quyết định

Một lượt chat của giáo viên có **hai pha**.

**Pha 1 — lên plan.** Model tra cứu bằng tool đọc, hỏi lại khi thiếu dữ kiện, và kết thúc pha bằng một
câu nói, một câu hỏi lại, **hoặc** một plan kèm một câu mở đầu. Plan là một danh sách có thứ tự; mỗi
phần tử gồm tên tool, các tham số, và một câu tiếng Việt nói bước ấy làm gì.

**Một tham số lấy giá trị từ bước trước được viết là `{k.tên_field}`**, với `k` là số thứ tự bước,
đếm từ 1. BE là bên duy nhất giải nó, đọc từ `tool_result` của bước ấy. Tham chiếu tới một field
không có trong kết quả thì **plan bị từ chối trước khi chạy bước nào**. Cú pháp này tồn tại vì model
chỉ trả về được chuỗi phẳng (`_Argument{name, value}`), và vì `start_drafting` cần một `assessment_id`
mà `create_draft` mới sinh ra.

**Trong pha 1 không có tool nào ghi.** Pha 1 có `find_class`, `class_assessment_summary`,
`draft_progress`; pha 2 có `create_draft`, `start_drafting`.

**Nhưng pha 1 vẫn phải *thấy* danh mục pha 2.** Nó nêu tên tool và tên tham số trong plan, nên không
thấy mô tả thì nó đoán — và một tham số đoán sai tên làm `vet_plan` từ chối trọn gói cả plan, tức một
yêu cầu hợp lệ nhận một lời từ chối. Vì thế `NextStepRequested` chở **hai** danh mục: `catalog` là
những tool gọi được ngay, `plannable` là những tool chỉ hẹn làm được. Hai field chứ không một danh
sách kèm cờ, vì "được gọi ngay" và "được hẹn làm" là hai quyền khác nhau, và trộn chúng lại là mở
đúng cánh cửa ADR này đóng. **`draft_progress` phải bỏ phần
`harvest`** trước khi luật này đúng: hôm nay nó khai `writes=False` nhưng thân nó ghi `Question` và
đẩy state đề sang `HAS_QUESTIONS`. Việc thu hoạch chuyển về đường nghe tiến độ và về cổng duyệt.

**Pha 2 — thực hiện plan.** BE chạy từng bước theo thứ tự và phát sự kiện cho mỗi bước: bắt đầu, xong
kèm một dòng kết quả, hoặc hỏng kèm lý do. **Một bước hỏng thì dừng plan**; các bước sau không chạy.

**Pha 2 xong khi plan đã chạy hết *và* không còn câu nào đang soạn.** Hai điều kiện, vì các bước plan
mất chưa tới một giây còn việc soạn mười câu mất hàng phút.

**Pha 2 xong thì model báo cáo.** BE đưa kết quả của cả plan cho model trong một lời gọi riêng; câu
trả lời ấy là câu kết trên màn hình. Báo cáo chạy cả khi plan hỏng giữa chừng. Giáo viên đóng tab
trước khi soạn xong thì báo cáo được viết ở **lần quan sát kế tiếp** — lượt chat sau, hoặc lần mở lại
đoạn chat — chứ không mất.

**Tiến độ là một cái chuông, không phải một đường dữ liệu.** AGENT phát một tin lên Redis mỗi khi
viết xong một câu. BE **subscribe trước khi đẩy job**, đúng khuôn của `agent_gateway`, và mỗi tiếng
chuông thì thu hoạch rồi đẩy xuống FE. Câu hỏi vẫn đọc từ result store của arq. **Không ai nghe thì
không mất gì**: thu hoạch ở lần quan sát sau vẫn đưa đủ câu vào đề. BE **vẫn không có worker chạy
nền**; chuông chỉ cắt độ trễ cho một người đang nhìn.

**Màn hình vẽ theo đúng thứ tự nhận được.** Không khuôn cố định nào cho một lượt; artboard là ảnh
chụp một trường hợp. Khối bằng chứng (`Thinking` `83:76` trên Figma, `Steps` trong code) vẽ **mọi**
bước của **cả hai pha**; nó **sống** trong pha 2 và tới nguyên khối ở pha 1. Spinner chờ của pha 1 là
một component khác (`Assistant thinking` `222:59`).

**Hai con số tiến độ, hai chỗ đứng.** `bước k/n` trên đầu khối đếm **bước của plan**. Số câu đã soạn
là một dòng riêng dưới bước đang chạy. Gộp chúng vào một chỗ là nói hai sự thật bằng một con số.

## Vì sao

**Plan tồn tại vì con số `k/n` phải nói thật.** Một thanh tiến độ không biết đích đến là một lời nói
dối có hình dạng đẹp. Có plan thì `n` là số bước plan nêu — đọc được, không ước lượng.

**Tách đọc khỏi ghi là cách duy nhất làm "hỏi lại" vô hại.** ADR-23 bắt hỏi lại khi không phân định
được. Nếu một câu hỏi lại xảy ra **sau** một lần ghi thì mỗi lần hỏi là một lần để lại rác, và giáo
viên trả lời một câu hỏi trong khi hệ thống đã làm một việc họ chưa đồng ý. Ranh giới pha biến chuyện
đó thành không thể, thay vì thành một lời dặn trong prompt — và lời dặn thì model quên được.

**Báo cáo là một lời gọi riêng vì nó có đầu vào khác**: nó đọc kết quả của cả plan, không đọc catalog.
Và nó phải do model viết, không phải BE ghép chuỗi: câu kết là chỗ duy nhất nói *vì sao* bộ đề ra như
vậy. **Không check nào hôm nay bắt được điều này.** Check gần nhất là
`check_model_call_fits_inside_the_job_waiting_for_it`, và nó chỉ canh thứ tự timeout; docstring của
chính nó đã nhận là không thấy được một vòng lặp mới. Nên luật này phải **mua lấy một check mới**,
hoặc nó không phải một luật mà chỉ là một ý định.

**Tiến độ đi qua Redis vì hai service đã dùng chung đúng hạ tầng ấy** — AGENT đã publish ngoài arq
cho đường kèm học của học sinh. Một callback HTTP sẽ bắt AGENT biết địa chỉ BE và mang một bộ
credential mới.

**Vẽ theo thứ tự nhận được vì harness không ép luồng nào.** Hệ thống tiêm context và tool; model quyết
nói lúc nào, tra lúc nào, hỏi lúc nào. Một màn hình ép dữ liệu vào khuôn *lời mở → bước → lời kết →
thẻ* đã nói sai ngay lần đầu: câu *"Mình đang soạn đề…"* bị đẩy xuống dưới khối bước vì khuôn ấy coi
câu cuối là lời kết.

### Phương án đơn giản hơn, và vì sao không chọn

Gộp `create_draft` + `start_drafting` thành **một tool atomic**, lấy `k/n` từ `asked_for`/`written` mà
`draft_progress` đã trả về, và thêm một lời gọi model ở cuối lượt để báo cáo. Nó đạt khoảng 80% mục
tiêu với 10% rủi ro: không đổi contract, không đổi ranh giới service, không cần plan tĩnh.

Không chọn vì nó chữa **một** luồng chứ không đặt một luật. Tool ghi thứ ba — tạo lớp, nhập học sinh,
sửa đề — lại phải tự lo chuyện "đừng hỏi lại sau khi đã ghi", và lần sau người viết nó sẽ không biết
luật ấy tồn tại. Và `bước k/n` theo nghĩa *bước việc* thì vẫn không nói được. Cái giá phải trả là một
cú pháp tham chiếu và một ranh giới pha; cả hai đo được bằng test.

## Hệ quả

- **`draft_progress` phải bỏ `harvest`** — không thì câu *"pha 1 không ghi gì"* sai ở chính tool đầu
  tiên. Cờ `writes` của nó hôm nay cũng sai và phải sửa cùng lúc.
- **Prompt pha 1 đổi nghĩa.** Lời dặn *"Sau create_draft thì gọi start_drafting"* mô tả một thế giới
  không còn và phải viết lại, nếu không model sẽ gọi một tool không có trong catalog pha nó đứng.
- **Mô tả của chính các tool ghi cũng đổi nghĩa.** `create_draft` hôm nay dặn *"thiếu mục nào thì hỏi
  rồi gọi lại"* — một câu chỉ đúng khi tool còn gọi được giữa lượt. Trong một plan, thiếu mục nào thì
  bước ấy **không được nhét vào plan**, vì nó sẽ dừng cả plan và để lại một đề rỗng.
- **Lời từ chối `missing` mất vai trò cũ**: thiếu dữ kiện bị chặn trước khi plan dựng, nên nó chỉ còn
  là lưới cuối. Màn hình **không** được vẽ nó thành bước hỏng — nó là đường dẫn tới câu hỏi lại.
- **ADR-23 có kết quả thứ tư.** Nhập nhằng lẽ ra đã giải xong ở pha 1; nếu một bước pha 2 vẫn gặp,
  nó **dừng plan** và câu báo cáo nói ra, thay vì hỏi lại giữa chừng. Đó là một kết quả mới so với ba
  kết quả của ADR-23, và nó được ghi ở đây chứ không đi vòng.
- **ADR-01 làm đúng việc của nó vẫn ra "bước hỏng".** Đề đã duyệt thì `fire` ném 409 và `harvest` lặng
  lẽ không ghi gì. Trong một plan, hai ca ấy dừng plan — và câu báo cáo phải nói rằng **không có gì
  sai**, chỉ là nội dung đã khoá.
- **Thẻ kết quả mọc cho mỗi kết quả còn đứng vững tới cuối lượt**, không phải mỗi `tool_result`. Luật
  *"tối đa một thẻ cho một lượt"* trong `teacher-surface.md` là một suy diễn từ artboard 5 và phải
  viết lại theo luật này.
- **`teacher-surface.md` phải sửa trong cùng change set**: mục *"Một lượt của Kriky gồm bốn khối, theo
  đúng thứ tự này"* trái thẳng với luật vẽ-theo-thứ-tự-nhận-được ở trên.
- **Ngân sách tách đôi.** Pha 1 giữ `max_tool_steps = 8` và 90 giây. Các bước plan chạy trong cùng
  request (mỗi bước dưới một giây). Việc soạn câu **không** nằm trong request nào: nó đã chạy trong
  arq và sống sót qua mọi lần đóng tab.
- **Plan phải được lưu**, nếu không một lần F5 làm mất nó trong khi màn hình hứa dựng lại được.
  `teacher_turns` cần chỗ cho nó.
- **Một lượt đầu tiên nay tiêu ba loại lời gọi model**: pha 1, báo cáo, và đặt tên đoạn chat.
- **Figma phải nói rõ artboard là ảnh chụp**, và mô tả component `Thinking` phải nói nó cập nhật liên
  tục trong pha 2.
- **Chuông phải rung sau khi kết quả đã vào store.** arq ghi kết quả *sau khi* coroutine của job trả
  về, nên một tiếng chuông phát ra từ trong thân job báo một câu xong trước khi ai đọc được nó: BE
  nghe chuông rồi thu hoạch sẽ gặp `pending`, màn hình trễ một nhịp, và **tiếng chuông cuối cùng
  không gặt được gì** — tức điều kiện *"pha 2 xong khi không còn câu nào đang soạn"* không bao giờ
  được thoả. Chỗ đúng là hook `after_job_end` của worker.
- **Chuông không phải một bộ đếm.** Một vị trí thử lại rung thêm một lần cho cùng số thứ tự, và một
  tiếng chuông có thể mất. Số câu đã soạn phải đếm từ database.

## Nơi luật này đang được thi hành

Chưa chỗ nào — ADR viết **trước** khi code, có chủ đích, vì nó đổi ranh giới giữa hai service và đổi
hợp đồng giữa BE với AGENT. Plan thi hành: `docs/plans/active/2026-10-02-hai-pha-mot-luot-chat-plan.md`.
Những chỗ sẽ phải thi hành nó:

- `packages/contracts/src/contracts/teacher_chat.py` — kiểu của một plan, và task báo cáo.
- `services/agent/src/agent/graphs/propose.py` — prompt pha 1, và đường trả về một plan.
- `services/agent/src/agent/graphs/reporting.py` — lời kể sau khi plan chạy; một task riêng.
- `services/be/src/be/teacher_chat.py` — hai pha, và đường SSE của một lượt.
- `services/be/src/be/teacher_tools.py` — catalog theo pha; `draft_progress` bỏ `harvest`.
- `services/be/src/be/drafting.py` — nghe chuông tiến độ; thu hoạch vẫn là đường bền.
- `services/fe/src/screens/teacher/Chat.tsx` — vẽ theo thứ tự nhận được, khối bằng chứng sống.
- `tools/check_contract.py` — check mới cho luật *báo cáo là một job riêng*.
- `docs/overview/teacher-surface.md` — luật hiển thị của hai pha.
