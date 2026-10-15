# ADR-27 — Tài liệu đi vào ngữ cảnh ra đề

- **Trạng thái:** đã chốt, chưa thi hành
- **Ngày:** 2026-10-07
- **Sửa:** 2026-10-08 — cổng text layer thành **bất đồng bộ**, vì việc đọc tệp chuyển sang
  `services/document`. Luật không đổi ý; chỗ nó được thi hành thì đổi.
- **Sửa:** 2026-10-12 — **rút luật lọc bài tập**; *"nhiều cách chia"* hoãn. Xem *Hậu ký 12/10/2026*
  ở cuối. Phần trên giữ nguyên làm lịch sử.
- **Sửa:** 2026-10-15 — *mỗi câu một mục* và phép rải theo độ dài nhường cho ADR-29 (dàn ý đề). Xem
  *Hậu ký 15/10/2026*.

## Bối cảnh

[ADR-04](adr-04-hai-nguon-cau-hoi.md) chốt ngày 06/09/2026 rằng **tài liệu là phạm vi, không phải
nguồn**: *"Nó cung cấp kiến thức và giới hạn phạm vi ra đề. Nó không chứa câu hỏi."* Nhưng từ đó tới
nay nội dung tài liệu **chưa từng đi vào prompt**. Cái vỏ đã chạy — tải lên được, liệt kê được, kéo
thả vào ô chat được — còn `document_id` thì không rời khỏi màn hình.

Dựng phần ruột đẻ ra sáu câu hỏi **nghiệp vụ** mà ADR-04 không trả lời: một tệp không đọc được chữ
thì sao, giáo viên thấy gì trong lúc chờ xử lý, chuyện gì xảy ra khi xử lý hỏng giữa đường, làm sao
giữ cho bài tập trong sách không thành câu hỏi trong đề, ai quyết phạm vi khi lời giáo viên không đủ
phân định, và một phạm vi đã chốt có được đổi giữa vòng soạn không.

## Quyết định

- **Một tệp không đọc được chữ thì không bao giờ dùng được.** Phép kiểm chạy ngay sau khi nhận
  tệp, nhưng nó nằm trong service xử lý tài liệu chứ không trong đường `POST`, nên nó **bất đồng
  bộ**: chip đi từ *đang xử lý* sang *không đọc được chữ* trong vài giây, và lý do nói bằng lời
  giáo viên hiểu. Ảnh scan là một thứ sẽ làm sau, không phải một thứ nhận bừa rồi bỏ đó.
- **Tải lên xong không có nghĩa là dùng được ngay.** Tài liệu đi qua một bước xử lý, và màn hình nói
  rõ nó đang ở đâu trong **bốn** trạng thái: **đang xử lý** · **sẵn sàng** · **không đọc được chữ** ·
  **xử lý hỏng**. Một chip trông dùng được mà chưa dùng được là một chip nói dối — và một chip đứng
  mãi ở *đang xử lý* vì job đã chết cũng là một chip nói dối, nên ca ấy phải có tên riêng.
- **Bài tập trong tài liệu không bao giờ thành câu hỏi tới tay học sinh.** Luật này áp cho **mọi**
  prompt nhận nội dung tài liệu — prompt soạn đề, **và** prompt sinh câu luyện tập pha 2 (ADR-17).
  ADR-04 dành một ngoại lệ cho câu luyện tập về **trạng thái kiểm**, không về **nguồn**; mà pha 2
  chính là chỗ câu đi **thẳng tới học sinh và không ai kiểm**, nên nếu có chỗ nào cần cái lọc này hơn
  thì là chỗ đó. Việc lọc xảy ra **trước khi** nội dung rời BE — đây là nơi thi hành của ADR-04:
  luật ấy từ nay có một cơ chế, không chỉ có một câu.
- **Khi không phân định được phạm vi, Kriky hỏi giáo viên** — bằng tên **chương và bài**. Khoảng
  trang vẫn là một phạm vi hợp lệ và giáo viên nêu được nó bất cứ lúc nào (ADR-04 cho phạm vi tới
  *"cấp chương và khoảng trang"*); chỉ **câu hỏi của Kriky** dùng tên chương, vì hỏi bằng số trang
  bắt người trả lời đi tra cứu trước khi trả lời được.
- **Khi giáo viên không thu hẹp, Kriky đưa ra NHIỀU cách chia, mỗi cách tự nêu cái giá của nó, và
  không cách nào được đánh dấu là nên chọn.** Luôn giữ lối thoát trả lời tự do. Đây là ADR-05 nguyên
  văn chứ không phải một ngoại lệ của nó.
- **Các lựa chọn ấy do BE dựng, không do model viết** (ADR-23). Tên chương lấy từ mục lục là dữ liệu;
  cách chia mười câu thì không phải dữ liệu nào cả, nên nó đi qua đúng đường mà invariant
  *"the options in a clarifying question are written by BE from rows it read"* đang canh.
- **Phạm vi đã chốt thì đóng băng cho cả vòng soạn ấy.** Mười câu của một đề đến từ cùng một cách
  hiểu phạm vi. **Đổi phạm vi là mở một vòng mới** — nên nó vẫn *"phải đổi được"* đúng như ADR-04
  đòi, chỉ là việc đổi không sửa phần việc đang bay. Đây là cùng cơ chế `DraftBrief.version` đã dùng
  cho brief, mở rộng sang phạm vi tài liệu.

## Vì sao

**Biết trong vài giây, không phải lúc đem ra dùng**, vì một tệp nằm trong thư viện là một lời hứa.
Giáo viên tải một cuốn sách lên rồi ba tuần sau mới kéo nó vào ô chat; nghe *"tệp này không đọc được
chữ"* ở thời điểm ấy là nhận một lời từ chối cho một việc họ tưởng đã xong từ lâu.

Bản đầu của ADR này đòi từ chối **ngay trong lời gọi tải lên**, tức đồng bộ. Nó tự mâu thuẫn với
chính luật kế bên: nếu tệp bị chặn ở cửa thì **không có hàng nào** để mang trạng thái *không đọc được
chữ*, mà trạng thái ấy lại là một trong bốn trạng thái ADR này bắt màn hình phải nói được. Chỗ đọc
tệp nay là `services/document`, nên phép kiểm là bất đồng bộ, và cái giữ đúng lời hứa không còn là
*thời điểm từ chối* mà là **vài giây** giữa lúc tải xong và lúc chip đổi mặt.

**Bốn trạng thái chứ không hai**, vì xử lý một cuốn sách vài trăm trang không tức thì. Không có
trạng thái *đang xử lý* thì giáo viên kéo một chip chưa sẵn sàng vào ô chat và nhận một câu từ chối
khó hiểu — màn hình đã có đủ thông tin để nói trước, chỉ là không nói.

**Lọc bài tập bằng cấu trúc, không bằng lời dặn**, vì repo này đã đo và ghi lại rằng lời dặn không
giữ được model: `teacher_tools.py` phải cắt `create_draft` từ sáu tham số xuống ba sau năm lần đo với
`gpt-4o-mini`, vì *"mỗi lần prompt cấm hỏi một mục, model lại tìm ra một mục khác chưa bị cấm để
hỏi"*. Bài học ghi thẳng trong code là **"Thứ không nhìn thấy thì không hỏi được."** Một đoạn bài tập
đã bị loại khỏi payload thì model không chép được nó.

Và cái giá của việc không lọc là nặng hơn vẻ ngoài: một câu chép từ bài tập có đáp án in sẵn **tới
tay học sinh kèm nhãn "Kriky soạn, chưa kiểm"**. Học sinh đã thấy câu ấy, đã thấy đáp án, và màn hình
thì khẳng định ngược lại.

**Hỏi bằng tên chương, không bằng số trang**, vì số trang là cách *hệ thống* định vị, còn chương và
bài là cách *giáo viên* nghĩ. Một câu hỏi lại dùng từ vựng của hệ thống bắt người trả lời đi tra cứu
trước khi trả lời được.

**Nhiều cách chia, không một đề xuất**, vì chia mười câu cho ba tiểu mục là một quyết định **sư
phạm** — và ADR-05 đã chốt thẳng cho loại ấy: *"Agent **không đánh dấu lựa chọn nào là nên chọn** khi
đó là quyết định sư phạm. Mỗi lựa chọn tự nói ra cái giá của nó."* Bản nháp đầu của chính ADR này cho
Kriky đưa **đúng một** cách chia rồi viện ADR-05 làm lý do; đó là đọc ngược ADR-05, và nó rơi trúng
cảnh báo gay nhất của ADR-05: *"**gợi ý ngầm còn tệ hơn gợi ý công khai**"* — một phương án duy nhất
được ưu ái mà người đọc không nhận ra mình đang bị đẩy.

**Đóng băng phạm vi**, vì các job soạn câu chạy **song song và không thấy nhau** — cùng lý do
`DraftBrief` đã tồn tại. Nếu phạm vi được diễn giải lại ở mỗi job thì nửa đầu và nửa sau của một đề
trả lời hai cách hiểu khác nhau, và không ai đọc từng câu một sẽ nhận ra.

## Hệ quả

- **Thư viện tài liệu hẹp lại.** Sách scan — có thể là phần lớn bản sách giáo khoa lưu hành thật —
  không tải lên được cho tới khi có OCR. Đây là một **giới hạn đã biết và đã nhận**, không phải một
  thiếu sót.
- **Upload chậm hơn**, vì nó mở file ra đọc trước khi trả lời. Đổi lại, số trang và cờ *đọc được
  chữ* trở thành **đo được** — hai thứ mà `teacher_documents.py` cố ý bỏ đi vì *"một con số trang
  bịa ra thì tệ hơn hẳn việc không có nó: giáo viên sẽ tin."*
- **Một lượt chat có thể tốn thêm một lượt hỏi lại.** Đó là cái giá của việc không tự chọn, và nó
  được trả đúng ở chỗ ADR-05 muốn nó được trả.
- **Nhãn loại nội dung trở thành một trường bắt buộc**, nên phép phân loại ấy phải có người canh:
  một đoạn bị gán nhãn sai là một bài tập lọt vào đề, và không màn hình nào sẽ nói ra.
- **Chip tài liệu phải nói được bốn trạng thái**, nên Figma (`Document chip`) và FE đều phải vẽ
  thêm — chip hiện chỉ có một hình dạng.

## Nơi luật này đang được thi hành

**Năm trong sáu luật: chưa nơi nào.** Luật thứ sáu thì **đã có một nửa**: việc đóng băng để mười
job không hiểu phạm vi theo mười cách đang chạy thật ở `DraftBrief` (`models.py`), với `topic_scope`
cộng `version`, và docstring của nó nói gần đúng lý do ADR này đưa ra. Phần chưa có là **phạm vi tài
liệu** đi theo `version` ấy.

ADR vì thế mang trạng thái `đã chốt, chưa thi hành` — ghi lại một quyết định đã chốt là đúng, giả vờ
nó đang chạy thì không.

**Đây không phải cổng thứ tư của ADR-05**, và câu ấy phải nói ra vì ADR-19 đã đặt tiền lệ rằng mỗi
kênh việc mới phải tự trả lời. *Đang xử lý* là máy chờ máy, không phải *"chỗ hệ thống dừng lại chờ
**người**"*; còn hỏi lại về phạm vi là đường hỏi lại đã có của ADR-23, nằm **trong** một lượt chat
chứ không chặn một vòng đời. Ba cổng của ADR-05 vẫn là ba.

Nơi nó **sẽ** được thi hành, để lần sau đọc lại còn biết đi tìm ở đâu:

| Luật | Sẽ sống ở |
|---|---|
| Từ chối tệp không có text layer | `services/document` — nó đọc tệp từ MinIO và trả kết quả về cho BE ghi |
| Bốn trạng thái của chip | `models.Document` (một cột trạng thái), `Rail.tsx`, Figma artboard 1 và 2 |
| Bài tập không vào prompt | `services/be/src/be/drafting.py` chỗ dựng `DraftQuestionRequested`, và đường sinh câu luyện tập pha 2; cộng một repo check trong `tools/check_contract.py` |
| Hỏi bằng tên chương | prompt pha 1 của AGENT, và skill `tim-trong-tai-lieu.md` |
| Đề xuất cách chia | cùng skill ấy |
| Đóng băng phạm vi | **đã có**: `DraftBrief.topic_scope` + `version` (`models.py`). Còn thiếu: con trỏ chunk trên `DraftItem`, ghi trước khi `fire` đẩy job nào |

Quyết định **kỹ thuật** đi kèm — PyMuPDF, ba tool đọc thay cho một tool tìm, Jev làm bộ định tuyến
gọi từ `services/document`, skill viết bằng Markdown, byte tài liệu sang MinIO, chunk sang MongoDB,
và `services/document` thành service thứ tư — **không nằm ở đây**: theo `docs/decisions/README.md`,
chúng thuộc mục `## Decision Records` của các plan thi hành ADR này. Đợt thi hành chia thành **năm
plan**, vì một plan không chở nổi chừng ấy việc.

## Hậu ký 12/10/2026

Viết khi mở plan 4b (`2026-10-12-draft-from-document-plan.md`), lúc nội dung tài liệu lần đầu thật sự
đi vào job soạn câu. Một luật hẹp lại, một luật hoãn, một luật mới; ba luật còn lại giữ nguyên.

**Hẹp lại: luật lọc bài tập -- rút cho prompt soạn đề, giữ cho pha 2.** Với đề giáo viên soạn, tài
liệu đi vào prompt để **cung cấp kiến thức**, và luật lọc giả định một nhãn *bài tập / lý thuyết* trên
từng đoạn mà đơn vị nội dung không có: đo trên cây plan 3c, một chunk là một dải chữ liên tiếp dưới
một mục, gom cả định nghĩa, ví dụ giải sẵn lẫn *"Luyện tập"* và *"1.1. Cho hai tập hợp…"*. Dựng nhãn
ấy là một bộ phân loại mới mà mỗi lần sai là **im lặng** -- đúng cái giá mục *Hệ quả* đã cảnh báo --
trong khi phần nằm giữa các bài tập (định nghĩa, ví dụ) là thứ một câu hỏi tốt cần nhất. Job soạn câu
được dặn viết câu **mới** trên kiến thức của đoạn, không chép một câu có sẵn. Lời dặn yếu hơn cấu
trúc -- chính ADR này viện bài học *"thứ không nhìn thấy thì không hỏi được"* -- và lưới còn lại là
cổng **duyệt** của ADR-05: một đề soạn ra không tới học sinh khi giáo viên chưa duyệt.

Cổng ấy **không** che pha 2: câu luyện tập đi thẳng tới học sinh và mãi mãi *chưa kiểm* (ADR-04,
ADR-17). Nên với pha 2 luật **không đổi** -- prompt sinh câu luyện tập không nhận nội dung tài liệu
nào, cho tới khi có một quyết định riêng trả lời được câu *"lọc bằng gì"*.

**Mới: mỗi câu một mục kiến thức.** Phạm vi đã chốt (các chương/bài) được chia thành các mục lá của
cây; mỗi câu của một đề được gán **một mục**, và khi số câu nhiều hơn số mục thì một nhóm đoạn khác
nhau trong mục -- gán xong ghi lại trước khi câu được soạn. Vì sao: các job soạn câu chạy song song
và không thấy nhau (lý do `DraftBrief` tồn tại), nên không có phép gán thì hai câu dễ hỏi cùng một
kiến thức mà không ai đọc từng câu nhận ra; và gán một lần là để soạn thêm câu không xáo câu đã xong.

**Hoãn: *"Khi giáo viên không thu hẹp, Kriky đưa ra NHIỀU cách chia …"*.** Plan 4b hỏi lại bằng **tên
chương và bài** (phương án do BE dựng từ cây, ADR-23); khi phạm vi đã rõ, số câu được rải theo độ dài
nội dung từng mục. Phép rải ấy **là** một lựa chọn sư phạm ngầm -- loại ADR-05 gọi là tệ hơn gợi ý
công khai -- và hoãn nó có hai lý do: hỏi bằng tên chương thì giáo viên đã thu hẹp trước khi có gì
để chia, nên ca *"không thu hẹp"* có thể hiếm hơn ADR này giả định; và rải theo độ dài là phép duy
nhất không ưu tiên mục nào theo phán đoán của hệ thống. Kriky phải **nói ra** phép rải trong lời nêu
plan, để nó không còn ngầm. Việc bày nhiều cách chia nằm ở `docs/plans/backlog.md`.

**Nơi thi hành từ plan 4b:** phạm vi hỏi bằng tên chương/bài -- `_offered` trong `teacher_chat.py`
dựng phương án từ nút cây; phạm vi đóng băng -- `DraftBrief` mang tài liệu, các nút phạm vi và phiên
bản cây, cùng `version`; mỗi câu một mục -- `DraftItem` ghi mục được gán trước khi job chạy; pha 2
không nhận tài liệu -- không payload pha 2 nào có trường nội dung tài liệu.

**Thêm từ plan 4c T5 (13/10/2026):** đoạn chat không chip chỉ mở đề theo một tài liệu **sau khi**
đọc mục lục của nó -- không thì `nodes` là số model bịa, BE nhận, và đề soạn trên mục sai mà không ai
biết. Thi hành ở AGENT: `propose._toc_first` (plan tạo đề theo tài liệu chưa đọc mục lục → đọc trước)
và `_picked_book_first` (giáo viên chọn một tài liệu trong danh sách → đọc mục lục của nó).

## Hậu ký 15/10/2026

**Khi ADR-29 thi hành (plan `draft-outline`), luật *mỗi câu một mục* và phép rải câu theo độ dài nội
dung thôi áp dụng, và chữ tài liệu thô thôi đi vào job soạn câu.** Tới lúc ấy, code vẫn chạy theo hậu
ký 12/10. [ADR-29](adr-29-dan-y-de-truoc-khi-soan.md) thay chúng bằng một **dàn ý** Kriky đề
xuất từ chính tài liệu, BE in ra chat, giáo viên duyệt hay sửa bằng chat; job chỉ nhận mục dàn ý của
nó. Đo trên SGK Lớp 6 tập 1 ngày 14/10/2026 là lý do: 7–12% chữ OCR là rác hay công thức đọc lệch mà
job đọc nguyên, và phép rải theo độ dài -- hậu ký 12/10 đã tự gọi là một lựa chọn sư phạm ngầm -- nay
có chỗ để hiện ra và để sửa.

Tài liệu vẫn **cung cấp kiến thức và giới hạn phạm vi**, đúng như ADR-04; chỉ đường đi đổi: tài liệu
tới Kriky, Kriky tới dàn ý, dàn ý tới job. Luật *hỏi bằng tên chương và bài*, *phạm vi đóng băng* và
*pha 2 không nhận tài liệu* giữ nguyên. Mục *"nhiều cách chia"* đang hoãn ở `backlog.md` được dàn ý
trả lời: giáo viên không chọn trong nhiều cách chia, họ sửa thẳng một cách chia hiện rõ.
