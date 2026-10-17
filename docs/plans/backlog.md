# Nợ — việc đã hoãn có chủ đích

Mỗi mục ở đây là một thứ **đã được nêu ra và cố ý chưa làm**, không phải một ý tưởng bỏ ngỏ. Ghi lại vì
một tính năng bị hoãn mà không ai ghi thì lần sau sẽ được đề xuất lại từ đầu, hoặc tệ hơn, bị tưởng là
đã có.

Mỗi mục phải trả lời được: **cái gì đang chặn nó**. Không chặn bởi gì thì nói thẳng là chưa cần.

File này khác `docs/decisions/`: ở đó là luật nghiệp vụ đã chốt và còn hiệu lực; ở đây là việc chưa làm.
Nó cũng khác mục *Còn thiếu* trong `docs/decisions/README.md`, vốn liệt kê những **luật** chưa được ghi
thành ADR, không phải những **tính năng** chưa dựng.

## Tài liệu quyết định nói về code không còn

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~Ba ADR mô tả đường chấm bài cũ như thể nó còn chạy~~ | **Đã làm: hậu ký 17/10 ở ADR-07, ADR-08, ADR-20; phần trên giữ làm lịch sử** (plan `backlog-tier-1`, pha 4). Không bị chặn. Cố ý hoãn: sửa một ADR là sửa lịch sử |

Ngày 09/10/2026, đường chấm bài cũ (`POST /api/submissions` → task `grade_submission` →
`decide_review`) bị xoá khỏi code, cùng `ReviewReason`, `GradingRequested`, `GradingCompleted` và
`REVIEW_CONFIDENCE_THRESHOLD`. Báo cáo, `AGENTS.md`, `architecture.md` và `local-development.md` đã
dọn theo. Ba ADR thì chưa:

- [ADR-07](../decisions/adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md) và
  [ADR-08](../decisions/adr-08-bon-loai-nghi-ngo.md) — mục *Nơi thi hành* của cả hai nay trỏ **100%
  vào hư không** -- mục *Nơi luật này đang được thi hành* -- kèm số dòng chính xác: `review_policy.py:53-69`, `routes.py:123`,
  `test_review_policy.py:37`, `contracts/enums.py`. Một người đọc theo số dòng sẽ đi tìm và không
  thấy gì.
- [ADR-20](../decisions/adr-20-cham-trac-nghiem-thuoc-be.md) — chính ADR đã thay thế đường ấy. Phần
  *Hệ quả* của nó dặn gỡ hai message *"ngay khi UC-05 chốt hình dạng"*; hai message nay đã gỡ, dù
  vì một lý do khác -- UC-05 chưa bao giờ được thiết kế -- nên điều kiện ADR nêu chưa từng được
  thoả. ADR không biết cả hai chuyện. Nó cũng tự ghi trạng thái *"đã chốt, chưa thi hành"* trong khi code đã thi hành.

**Vì sao hoãn chứ không làm luôn:** một ADR là bản ghi của một quyết định tại một thời điểm, nên
sửa nó cho khớp hiện tại là xoá mất chính thứ nó tồn tại để giữ. Cách đúng là một dòng **hậu ký** có
ngày, và viết hậu ký cho ba ADR là một lượt có chủ ý — không phải một dòng tiện tay kẹp vào lượt dọn
code.

## Bề mặt giáo viên — năm món nợ còn lại

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~Nguồn câu hỏi và trạng thái kiểm là **chữ bịa**~~ | **Chip đã gỡ 17/10/2026 (người dùng chọn A); nguồn thật vẫn chờ cột nguồn — plan P1** (plan `backlog-tier-1`, pha 2). `Question` không có cột nào nói nguồn hay việc đã kiểm, và `drafting._write` không nối `DraftItem` với `Question` — nên ngay cả *"do model viết"* cũng không truy được. Cần **một** cột nguồn và một đường ghi nó; *đã kiểm* không còn là một cột mà đọc từ trạng thái của đề (ADR-28: duyệt là đã kiểm mọi câu). Dòng tổng *"x câu thêm mới đã kiểm · y câu chưa kiểm"* gỡ ở plan `2026-10-13-question-bank-write-path-plan.md`; chip trên từng câu vẫn bịa |
| Nội dung tài liệu **chưa** đi vào prompt của AGENT | Cần đọc PDF, cắt đoạn, nhồi ngữ cảnh — một phần lớn hơn hẳn việc tải lên, và nó đổi cả thứ AGENT nhận, nên nó xứng một ADR riêng. Việc **tải lên** thì đã trả xong, và màn hình nay nói thẳng rằng nội dung chưa được dùng |
| Bốn đích đến trên rail trơ | Bốn artboard kia chưa dựng |
| Danh sách đoạn chat không phân trang | Một giáo viên dùng một năm sẽ có vài trăm hàng, và lúc ấy rail cần một đường **tìm kiếm** chứ không phải một danh sách dài hơn |
| Mỗi lớp một bộ giờ riêng | `Publication` khoá theo `(đề, lớp)` nên schema **đã** cho phép; thiếu bề mặt. Figma chưa vẽ |
| `services/fe` nay là tên sai | Nó phục vụ **hai** bề mặt. Đổi tên chạm `pnpm-workspace.yaml`, `dev.ps1`, `check_contract.py`, `AGENTS.md`, `local-development.md` — không khó, chỉ rộng |

Danh sách đoạn chat **đã trả xong**: `teacher_conversations` nay chứa nhiều luồng, mỗi luồng một
tiêu đề do model đặt (ADR-24), và từ đợt chốt chặng A thì xoá và đổi tên được. Món *phân trang* ở
cuối bảng là thứ đợt ấy đẻ ra.

Hai món vừa rời bảng, cộng một món chưa từng là một dòng ở đây — và một câu cho mỗi món:

- **`choices` mất sau F5** — `teacher_turns` nay có hai cột cho chúng, và bước cuối của một đoạn
  chở các phương án lên khi đọc lại. Đo ra chuyện nặng hơn dòng cũ ghi: `asked` được set từ đúng
  cái response **không bao giờ** có `choices`, nên thẻ hỏi lại có thể chưa từng hiện lần nào.
- **Xoá và đổi tên một đoạn chat** — câu chặn (*biên bản duyệt đi đâu*) trả bằng **xoá mềm**: một
  cột `deleted_at`, đoạn rời rail và đọc ra 404, các lượt của nó nằm nguyên trong bảng.
- **Tải tài liệu lên** — chưa từng là một dòng của bảng, vì nó vốn đã chạy; thứ còn thiếu là một
  cái vỏ không hứa sai. Dải dưới ô nhập từng in *"Đổi phạm vi"* cho một thứ không rời khỏi màn
  hình. Dòng *nội dung tài liệu chưa đi vào prompt* thì **vẫn còn trong bảng**: việc ấy chưa làm.

Món thứ nhất vẫn là món nặng nhất, vì nó là thứ **duy nhất** trong danh sách mà màn hình đang nói
một điều hệ thống không biết là đúng. Nó bị dồn vào đúng một module tên tự tố cáo và canh bằng một repo
check, nhưng hàng rào chỉ giữ cho nó không lan ra — nó không làm cho mấy cái chip đúng hơn.

## Màn hình Danh sách lớp học

| Việc | Cái gì đang chặn |
| --- | --- |
| Bộ lọc theo khối (1–12) | Không bị chặn. Chưa cần khi một giáo viên có chín lớp |
| Cột hoặc khối thống kê điểm ngay trên **danh sách lớp** | **Bị chặn bởi hạ tầng** — xem dưới |
| Sắp xếp danh sách lớp theo trung bình / cao nhất / thấp nhất | Cùng vật chặn |

Thống kê điểm **của một bài kiểm tra trong một lớp** thì đã được thiết kế — artboard
`11 · Kết quả bài kiểm tra trong lớp`. Cái còn nợ ở đây là thống kê **gộp theo lớp** hiện trên chính
hàng của bảng danh sách lớp, tức là gộp qua nhiều bài kiểm tra.

### Vì sao thống kê điểm chưa làm được

[ADR-09](../decisions/adr-09-ket-qua-cham-la-tam-thoi.md) chốt rằng kết quả chấm **chỉ sống một giờ**
trong Redis rồi biến mất, vì hệ thống chưa có cơ sở dữ liệu. Không có lịch sử làm bài thì không có gì
để tính trung bình, và một con số trung bình dựng trên dữ liệu của một giờ vừa qua sẽ sai theo cách
không ai phát hiện được.

Điều này áp cho **cả** artboard 11 đã dựng: màn hình đó là thiết kế đi trước backend, đúng thông lệ
của dự án (ADR-10), chứ không phải bằng chứng rằng dữ liệu đã có. Chừng nào kết quả còn sống một giờ,
mọi con số trên đó vẫn là dữ liệu mẫu.

Ba mục này vì thế nằm cùng nhóm với loại nghi ngờ thứ tư của
[ADR-08](../decisions/adr-08-bon-loai-nghi-ngo.md) -- *bất thường so với lịch sử học tập* -- và
toàn bộ tính năng mastery: **cùng bị chặn bởi
đúng một thứ**, và cùng mở khoá khi có cơ sở dữ liệu thật. Đó là lý do nên làm chúng một đợt chứ không
rải rác.

### Hai điều người làm sau cần biết

**Bảng lớp đã kín chiều ngang.** Bề rộng trong của bảng là 1068px và bố cục hiện tại dùng hết:
`tên FILL(376) + khối/môn 200 + sĩ số 80 + đề đang mở 120 + hoạt động 160 + chevron 12`, cộng năm gap
24px. Thêm ba cột điểm là **phải bỏ bớt cột khác**, hoặc chuyển thống kê sang một khối riêng phía trên
bảng thay vì nhét vào hàng. Luật nhịp cột nằm trong mô tả component `Class row` (`178:19`) của file
Figma `mOe2ZmrqOq1Uix45v6PNGD`.

**Khối chạy từ 1 đến 12**, nên sản phẩm phục vụ cả tiểu học và THCS, không riêng THPT. Dữ liệu mẫu
trong Figma hiện chỉ có khối 10–12; khi làm bộ lọc thì phải kiểm lại các giả định khác có bị lệch theo
không — đặc biệt là độ dài tên lớp và cách đặt tên.

## Màn hình Kết quả bài kiểm tra trong lớp

| Việc | Cái gì đang chặn |
| --- | --- |
| Xuất bảng điểm ra file | Không bị chặn. Chưa dựng vì chưa quyết định dạng file và ai được xuất |
| Màn hình xem bài làm của một học sinh | Không bị chặn. Chevron ở mỗi hàng đã trỏ tới đó nhưng đích chưa dựng |
| Đánh dấu bài **cần giáo viên xem lại** ngay trên bảng điểm | Đã dựng rồi gỡ đi — xem dưới |
| Tỉ lệ đạt / số bài dưới trung bình | **Chưa quyết định nghiệp vụ** — xem dưới |

### Vì sao "cần xem lại" bị gỡ khỏi bảng điểm

Khái niệm này **không phải thứ bịa ra**:
[ADR-07](../decisions/adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md) ghi đủ bốn luật chọn nó. Nhưng
phần code từng tính nó -- `needs_teacher_review` trong contract và `be/review_policy.py` -- **đã bị
xoá ngày 09/10/2026**, vì chưa bao giờ có màn hình nào tiêu thụ nó. Hôm nay nó là một quyết định
nghiệp vụ đã chốt mà chưa có một dòng code nào.

Nhưng trên **bảng điểm của một lớp** nó không dẫn tới đâu: không hành động, không đích đến, không cách
nào xử lý. Một nhãn cảnh báo không có lối đi là nhiễu chứ không phải thông tin — và tệ hơn, nó dạy giáo
viên bỏ qua màu hổ phách, đúng thứ [ADR-12](../decisions/adr-12-mau-va-hinh-anh-ma-hoa-luat.md) muốn
giữ cho đắt.

Chỗ đúng của nó là **hàng đợi review**, nơi có hành động đi kèm. Khi màn hình đó được dựng, nhãn này
quay lại — nhưng quay lại ở đó, không phải ở đây.

### Mốc điểm đạt là một quyết định chưa ai chốt

Biểu đồ phân bố hiện tại dùng **một màu duy nhất** cho mọi cột. Tô cột theo mức đạt / không đạt là mã
hoá một ngưỡng điểm vào giao diện, đúng việc [ADR-06](../decisions/adr-06-agent-phat-bang-chung.md)
cấm frontend làm với ngưỡng độ tin cậy.

Trường Việt Nam có mốc 5,0 thật, nên đây không phải chuyện bịa ra vấn đề. Nhưng chừng nào chưa có ADR
nói mốc đó là bao nhiêu và ai đặt nó, giao diện không được tự nhận. Khi chốt, nó sẽ mở khoá cả ba thứ
cùng lúc: màu theo mức trên biểu đồ, ô thống kê *tỉ lệ đạt*, và bộ lọc *chỉ xem bài dưới trung bình*.

## Linh vật — trạng thái theo lượt

| Việc | Cái gì đang chặn |
| --- | --- |
| Xuất lại năm PNG trên khung vuông chuẩn hoá | Không bị chặn. Cần làm ngoài Figma |
| Hạ bão hoà thân linh vật về `#9C7A5A` cho bản raster | **Việc ngoài code: người vẽ làm, rời Tier 1** (plan `backlog-tier-1`, pha 4). Không bị chặn. Cần làm ngoài Figma |
| Cho tư thế toàn thân đọc được | **Chưa quyết** — xem dưới |

### Hai món nợ ảnh, và một câu hỏi chưa trả lời

**Khung chưa chuẩn hoá.** `scaleMode: FIT` giữ chiều cao và thả chiều ngang, mà năm file nguồn khác tỉ
lệ, nên bề ngang biểu kiến chạy 23,8 → 33,2px và mép trái dịch tới 6,2px giữa hai trạng thái. Hoà tan
độ mờ không giấu được dịch chuyển ngang. Sửa bằng cách xuất lại năm PNG trên cùng một khung vuông với
nhân vật chiếm cùng tỉ lệ.

**Bão hoà.** Năm ảnh đang dùng là bản gốc của hoạ sĩ, cam bão hoà cao.
[ADR-12](../decisions/adr-12-mau-va-hinh-anh-ma-hoa-luat.md) đòi thân linh vật hạ bão hoà về `#9C7A5A`
để không lấn át hổ phách `#8A5A22` của `state/needs-human`. Bản **vector** `Assistant avatar` (`28:6`)
đã tuân thủ, nhưng nó hiện không còn instance nào; bản raster đang chạy thì chưa. Trên artboard 5 và 8,
linh vật rực hơn chính thẻ cảnh báo mà nó không được phép lấn át.

**Câu chưa trả lời: tư thế toàn thân có đọc được ở 40px không?** Đo thực tế: laptop thành một vệt xám,
lá cờ thành một chấm đỏ ~4px. Hai ảnh `expression_` (cận ngực) thì còn thấy mặt. Một nhân vật toàn thân
kèm đạo cụ cần **≥64px** để đạo cụ đạt ~16px. Hai hướng, chưa chọn:

1. Giữ ô 40px và dùng crop cận cho cả năm trạng thái; để `Thinking` và `Action result card` nói trạng
   thái bằng chữ. Hợp ADR-10 — chat là dòng lệnh, linh vật không nên nở thành một thành phần của cột.
2. Giữ tư thế toàn thân nhưng dời sang chỗ có đất: một ô 64px ở đầu panel, hoặc cạnh composer.

## Luồng học sinh — mô hình hai pha

Mô hình hai pha được chốt trong [ADR-14](../decisions/adr-14-hai-pha-lam-bai.md) …
[ADR-19](../decisions/adr-19-bao-cao-giai-thich-chua-ro.md). Cả sáu mang trạng thái *chưa thi hành*.
Dưới đây là những gì đã nêu ra và cố ý chưa làm.

| Việc | Cái gì đang chặn |
| --- | --- |
| Toàn bộ pha 2 | **Bị chặn bởi hạ tầng** — xem dưới |
| Cổng duyệt cho câu luyện tập | **Chưa quyết định nghiệp vụ** — xem dưới |
| Bật lại confidence của chẩn đoán | Chưa cần, và bật lại hôm nay sẽ hỏng — xem dưới |
| Ba dòng invariant trong `AGENTS.md` cần chỉnh lời | Chặn bởi câu hỏi cổng duyệt ở trên |
| Dữ liệu để giải thích *vì sao 0,5* | Không bị chặn. Cần một trường mới trong contract |
| ~~Hai tab hoặc tải lại trang giữa pha 2~~ | **Đã sửa 17/10/2026: GET /rounds/{id} đọc lại lượt đang mở, FE nút Làm tiếp lượt đang mở; ADR-15/21 đã quyết đồng hồ** (plan `backlog-tier-1`, pha 2). Không bị chặn. Chưa quyết vòng đếm và đồng hồ ứng xử ra sao |
| Màn hình học sinh trên điện thoại | Không bị chặn. Quyết định phạm vi — xem dưới |
| Bắt đổi mật khẩu ở lần đăng nhập đầu | Không bị chặn. Không có màn hình nào để đặt nó vào |
| Cách thể hiện mức 0,5 bằng màu | **Chưa quyết định nghiệp vụ.** ADR-12 mới khoá hai trạng thái đáp án |
| Phát hiện sớm một lời giải sai | **Chưa quyết định nghiệp vụ** — xem dưới |
| Hai chỗ contract nói không còn đúng | Không bị chặn. Chờ đợt sửa code |

### Vì sao pha 2 chưa dựng được

Mọi thứ ở pha 2 là **trạng thái có nhớ**: đã lặp mấy vòng cho từng câu, hội thoại đã nói gì, dạng nào
đã đóng, và điểm cuối. [ADR-09](../decisions/adr-09-ket-qua-cham-la-tam-thoi.md) chốt kết quả chấm chỉ
sống **một giờ** trong Redis, trong khi hạn kết thúc pha 2 có thể là cuối ngày.

Học sinh chữa dở, đi ăn cơm, quay lại — hệ thống không còn biết em đã làm hai vòng hay chưa vòng nào.
Luật *tối đa ba vòng* không tồn tại được nếu chưa có cơ sở dữ liệu.

Đây cùng nhóm với loại nghi ngờ thứ tư của ADR-08 và thống kê điểm: **cùng bị chặn bởi một
thứ**, cùng mở khoá khi có cơ sở dữ liệu thật. Khác biệt là ở quy mô — hai mục kia là tính năng phụ, còn đây là **toàn bộ
nửa sau của sản phẩm**.

### Câu luyện tập chưa qua cổng duyệt nào

Hiện tại trợ lí sinh câu `x'` và nó tới thẳng tay học sinh.
[ADR-05](../decisions/adr-05-ba-cong-teacher-in-the-loop.md) cổng số một nói *giáo viên duyệt đề trước
khi phát hành cho học sinh*; câu `x'` là ngoại lệ, và ADR-05 đã ghi ngoại lệ đó.

Cái giá, để lần bàn sau khỏi phải dựng lại lập luận: `x'` **được dùng để dạy lại** và **quyết định câu
gốc được 0,5 hay 0 điểm**. Nó không phải một gợi ý trôi qua như bong bóng chat. Thêm nữa,
câu Kriky soạn thành *đã kiểm* khi đề chứa nó được duyệt
([ADR-28](../decisions/adr-28-ngan-hang-cau-hoi-ghi-khi-duyet.md), sửa ADR-04) — `x'` không thuộc đề
nào được duyệt, nên vĩnh viễn ở trạng thái *chưa kiểm*.

Ba đường đã nêu và chưa chọn:

- `x'` chỉ được lấy từ ngân hàng câu hỏi **đã kiểm**, không sinh mới.
- Giáo viên duyệt sẵn **bộ câu chữa cho từng lỗi** ngay lúc duyệt đề, rồi hệ thống chỉ chọn trong đó.
- Giữ nguyên, và chấp nhận rằng cổng số một có một lỗ.

### Vì sao chưa bật lại confidence của chẩn đoán

[ADR-08](../decisions/adr-08-bon-loai-nghi-ngo.md) đã thu hẹp: đúng/sai là phép so xác định, thứ từng
cần giữ lại là **chẩn đoán**. Đợt này bỏ hẳn confidence của chẩn đoán khỏi luồng học sinh.

Bật lại hôm nay thì hỏng ngay, và hỏng theo **hai** đường chứ không phải một.

`services/agent/src/agent/handlers.py` trả `confidence = 0.55` khi `student_explanation` là `None`;
ngưỡng là `0.7` và phép so là **bao gồm**
([ADR-07](../decisions/adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md)). Pha 1 của mô hình mới không thu
lời giải thích, nên điều kiện đó đúng với **mọi câu của mọi học sinh** — một lớp 40 em làm bài 10 câu
sinh ra 400 mục chờ giáo viên, và pha 2 không khởi động cho ai.

Đường thứ hai độc lập với ngưỡng: nếu pha 1 gửi **chuỗi rỗng** thay vì `None`, cùng file trả
`confidence = 0.30` **và** `has_sufficient_evidence = False`, và luật *thiếu căn cứ* của ADR-07 đẩy
kết quả vào hàng đợi mà không hề so ngưỡng. Gỡ mỗi điều kiện ngưỡng là chưa đủ. (Phần code của cả
hai đường đã bị xoá 09/10/2026; ràng buộc trên là ràng buộc của **thiết kế**, còn nguyên.)

Việc cần làm trước khi bật lại không phải chỉnh ngưỡng, mà là **định nghĩa lại confidence đo cái gì**
khi phần chấm đã xác định — rồi mới tới việc pha 1 gửi `None` hay chuỗi rỗng.

### Mức 0,5 chưa có màu, và ADR-12 chưa nhận

[ADR-12](../decisions/adr-12-mau-va-hinh-anh-ma-hoa-luat.md) khoá `answer/incorrect` vào **hai**
trạng thái đáp án: đúng và sai. [ADR-16](../decisions/adr-16-thang-diem-ba-muc.md) thêm trạng thái thứ
ba — *đã chữa được* — và cố ý **không tự nhận** cách thể hiện nó, vì luật màu thuộc ADR-12.

`Score mark` đã dựng và **đi vòng qua câu hỏi này**: nó phân biệt ba mức bằng hình tròn đầy / nửa /
rỗng, mức 0,5 dùng `ink/default` chứ không xin một token mới. Cách đó đọc được cả khi bỏ màu, nhưng
nó **không phải câu trả lời** — nó chỉ làm câu hỏi bớt gấp.

Đây là chỗ dễ làm sai nhất: mức 0,5 trông như một mức trung gian nên rất mời gọi màu hổ phách, mà hổ
phách nghĩa là **cần người** — một câu đã chữa xong thì không cần ai cả. Khi quyết, phải quyết trong
ADR-12 chứ không phải trong màn hình đầu tiên bày ba mức.

### Lời giải sai bị khuếch đại, và chưa có cách phát hiện sớm

[ADR-18](../decisions/adr-18-cau-hoi-phai-kem-loi-giai.md) đòi mỗi câu kèm lời giải. Một lời giải sai
**chỉ lộ ra qua những em làm sai câu đó** — đúng những em sẽ được **dạy lại bằng chính lời giải sai
đó**, cùng lúc, cả lớp. So với việc feedback sai tới từng em một cách rời rạc, mô hình mới **khuếch
đại** lỗi này.

Kênh phát hiện duy nhất là [ADR-19](../decisions/adr-19-bao-cao-giai-thich-chua-ro.md), và nó cố ý
**không chặn ai**. Chấp nhận có chủ đích ở đợt này; khi có hàng đợi review thật thì đây là ứng viên
đầu tiên được nối vào.

### Chỉ desktop

Không bị chặn bởi gì. Lý do là ràng buộc bố cục, cùng loại với ràng buộc đã sinh ra
[ADR-10](../decisions/adr-10-pham-vi-dot-dau.md): ở pha 2, học sinh phải đọc **lời giải nhiều cách**
cạnh **câu hỏi** và cạnh **hội thoại**. Trên điện thoại một trong ba phải biến mất, và mất cái nào
cũng làm hỏng bước chữa bài.

Hệ quả cần biết: sản phẩm chỉ chạy trong phòng máy, tức là ràng buộc lịch của cả trường chứ không phải
ràng buộc kỹ thuật.

### Không có màn đăng nhập nên không có chỗ bắt đổi mật khẩu

[ADR-13](../decisions/adr-13-lop-va-tai-khoan-hoc-sinh.md) để mật khẩu ban đầu đi trên **giấy in** từ
tay giáo viên. Ai nhặt được tờ giấy cũng đăng nhập được. Cách chặn thông thường là bắt đổi mật khẩu ở
lần đăng nhập đầu, nhưng đợt thiết kế học sinh cố ý bỏ qua màn đăng nhập nên không có chỗ đặt nó.

Đây là **lỗ hổng đã biết**, không phải chuyện chưa ai nghĩ tới. Cột *trạng thái tài khoản* trên màn
`Chi tiết lớp` — phân biệt *chưa đăng nhập lần nào* với *đang hoạt động* — hiện là dấu vết duy nhất
trong sản phẩm cho thấy lần đăng nhập đầu có ý nghĩa riêng.

### Lý do được 0,5 vẫn chưa có nguồn dữ liệu

Món nợ này từng được ghi ở hai docstring của `contracts/messages.py`; tệp ấy **đã bị xoá
09/10/2026** cùng đường chấm bài cũ, nên hai chỗ nói sai kia tự hết. Phần còn lại thì không hết:
không message nào trên đường đang sống mang *vòng thứ mấy*, *câu gốc nào* hay *lỗi nào đã được
chữa*, nên lời hứa giao diện của
[ADR-16](../decisions/adr-16-thang-diem-ba-muc.md) -- hiện lý do được 0,5 -- vẫn **chưa có nguồn dữ
liệu**.

## Duyệt lời giải

| Việc | Cái gì đang chặn |
| --- | --- |
| Ghi nhận giáo viên đã đọc lời giải của từng câu | **Đã quyết ở cấp đề** (ADR-28, 13/10/2026): duyệt là đã kiểm cả lời giải. Dấu kiểm riêng từng lời giải vẫn là đường còn mở — xem dưới |

[ADR-18](../decisions/adr-18-cau-hoi-phai-kem-loi-giai.md) bắt mỗi câu hỏi kèm lời giải, và tự cảnh báo
rằng **lời giải khó duyệt hơn câu hỏi** — một câu hỏi sai thì đọc là thấy, một lời giải sai tinh vi thì
phải làm thử mới thấy. Nhưng hiện **không có gì** ghi nhận giáo viên đã thật sự đọc nó.

Hai đường đã cân nhắc và loại ở đợt dựng `Question card`:

- **Mở rộng nghĩa nhãn *đã kiểm*** của [ADR-04](../decisions/adr-04-hai-nguon-cau-hoi.md). Loại, vì nó
  lẫn hai thứ: *khoá khi duyệt* là hệ quả tự động của một thao tác, còn *đã kiểm* là lời giáo viên tự
  nhận đã đọc từng câu. Cho một cú bấm sẵn có gánh thêm một cam kết nặng hơn, không đòi thêm bằng
  chứng gì, là **làm yếu** cổng chứ không phải ghi lại điều vốn đúng.
- **Thêm một dấu kiểm thứ hai** riêng cho lời giải. Loại ở đợt này vì nó tạo hai thứ phải nhớ tick,
  tức thêm một chỗ để bỏ sót — nhưng đây là đường còn mở khi nào có người quyết.

**Ngày 13/10/2026, đường thứ nhất được chọn**, với chính cái giá đã nêu ở trên:
[ADR-28](../decisions/adr-28-ngan-hang-cau-hoi-ghi-khi-duyet.md) chốt *duyệt đề là đã kiểm mọi câu* --
gồm cả lời giải và ánh xạ nhiễu, đúng phần duyệt khoá lại (ADR-01, ADR-18) -- và mục *Hệ quả* của nó
ghi rằng *"đã kiểm"* yếu đi một bậc. Việc *ghi nhận* nay là chính lần duyệt, ở cấp đề chứ không ở cấp
câu. Nếu một ngày cần bằng chứng mạnh hơn, đường còn mở là dấu kiểm thứ hai riêng cho lời giải ở
trên.

## Nút Thu hồi chưa biết lúc nào phải biến mất

| Việc | Cái gì đang chặn |
| --- | --- |
| Trục trạng thái *chưa mở* / *đã mở* cho `Action result card` | Không bị chặn. Chưa dựng vì nó nhân đôi số variant |

[ADR-02](../decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md) chốt thu hồi được **cho tới hết giờ mở**,
và đòi nút Thu hồi **mất đi** khi đã qua mốc đó. Thẻ `đã-phát-hành` (`10:45`) nay có nút, nhưng
component set `Action result card` (`10:63`) không có trục nào phân biệt hai trạng thái con mà
[ADR-01](../decisions/adr-01-vong-doi-de-kiem-tra.md) đã nêu — *đã phát hành, chưa mở* và *đã mở*.

Nên hiện nút luôn hiện, tức file đang nói thu hồi lúc nào cũng được. Đó là sai theo chiều ngược với
câu cũ: trước đây thẻ nói không bao giờ thu hồi được, giờ nó nói luôn luôn.

Cái giá của việc sửa: thêm một trục vào một set đã có tám variant. Đó là lý do hoãn, không phải vì nó
không quan trọng.

## Bề mặt học sinh — đã dựng, chưa chạy

Mười hai artboard trên trang `Screen — Student` là **thiết kế đi trước backend**, đúng thông lệ của dự án.
Không con số nào trên chúng là dữ liệu thật, và không nên đọc chúng như bằng chứng rằng dữ liệu đã có.

Dải chú thích *DỮ LIỆU MẪU* từng dán trên mặt mỗi artboard **đã bị xoá** — nó lặp nguyên văn tám lần
và lọt vào mọi ảnh chụp gửi cho người khác xem. Mục này giờ là **nơi duy nhất** ghi điều đó, cùng với
mô tả từng component. Ai chụp màn gửi ra ngoài thì phải tự nói kèm.

| Việc | Cái gì đang chặn |
| --- | --- |
| Toàn bộ pha 2 chạy được | **Bị chặn bởi ADR-09** — đã ghi ở mục *Luồng học sinh* |
| Dữ liệu cho câu *lý do được 0,5* | Không bị chặn. Cần một trường mới trong contract |
| **Đề của từng lượt làm lại**, in trên màn kết quả | Không bị chặn. Cần lưu chính câu đã sinh, không chỉ kết quả đúng/sai |
| Màn đăng nhập, và chỗ bắt đổi mật khẩu lần đầu | Không bị chặn. Quyết định phạm vi — lỗ ADR-13 **vẫn nguyên** |
| Học sinh trên điện thoại | Không bị chặn. Quyết định phạm vi |

Câu chữ của từng lượt là món nợ **mới và dễ bị bỏ sót nhất**: nếu backend sinh câu biến thể rồi
vứt đi, màn kết quả sẽ có một khung để in đề mà không có đề để in. Câu biến thể phải được **lưu lại cùng lượt**, không phải sinh xong dùng một lần.

Ba dòng cuối là những thứ **đợt dựng này không làm cho tốt lên**. Đặc biệt: mười hai màn mới đều mang khối
danh tính và nút Đăng xuất trên `Student top bar`, nhưng điều đó **không lấp** được lỗ
[ADR-13](../decisions/adr-13-lop-va-tai-khoan-hoc-sinh.md): mật khẩu ban đầu vẫn đi trên giấy in và
vẫn không có chỗ nào bắt học sinh đổi nó.

### Hai lỗ điều hướng vòng review thứ tư tìm ra — **đã dựng xong**

Ghi lại vì cách sửa ràng buộc những gì làm sau. Hàng bài trên màn `13` từng chỉ mang **một** hành
động, nên bài đang ở pha 2 nhảy thẳng sang màn `17` và **màn `15` không quay lại được** — đóng tab
là mất chỗ duy nhất nói *điểm bây giờ là sàn*. Nay `Assignment row` có variant **hai** hành động:
*Xem kết quả* (phụ, viền) cạnh *Hỏi trợ lý và làm lại dạng bài sai* (chính). Cột hành động nới lên
348 cho **mọi** hàng, nếu không bốn cột lại lệch.

Nút *Xem lại phần chữa các câu sai* trên màn kết quả thì từng mở về màn `17` — màn vẫn nói *còn
phải làm lại 2 câu* và vẫn mời *Làm bài mới*. Nay nó mở artboard `24`: lịch sử chat còn nguyên, ô
nhập khoá, nút làm bài mới bỏ đi, nút báo cáo giữ lại.

### Hai cửa một chiều của học sinh chưa có cổng

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~Hộp xác nhận khi **bắt đầu làm bài**~~ | **Đã làm: artboard 13b, AssignmentList hỏi trước khi mở đồng hồ** (plan `backlog-tier-1`, pha 4). Không bị chặn. Chưa dựng |
| ~~Hộp xác nhận khi **nộp bài**~~ | **Đã có từ trước (artboard 15, Sitting); nộp lượt pha 2 nay cũng hỏi (artboard 22b)** (plan `backlog-tier-1`, pha 4). Không bị chặn. Chưa dựng |

Học sinh có **ba** cửa một chiều: bắt đầu làm bài (đồng hồ chạy và không ai dừng được), nộp bài
([ADR-14](../decisions/adr-14-hai-pha-lam-bai.md): nộp kết thúc pha 1), và bắt đầu một lượt chữa. Chỉ
cửa thứ ba có cổng — `Round gate`, đặt trên artboard 19. Hai cửa kia hiện là nút trơn.

Cửa **nộp bài** đáng có cổng nhất trong hai cái còn lại, vì dải nhảy câu đã đếm sẵn con số mà hộp xác
nhận cần đọc lại: *"còn 2 câu chưa trả lời"*. Đó là cùng nguyên tắc
[ADR-02](../decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md) dùng cho hộp xác nhận phát hành — đọc lại
giá trị thật thay vì một con số ghi cứng.

## Model thật — hai lỗ hổng mở cùng lúc với nó

Ghi từ [plan 2026-09-29](completed/2026-09-29-agent-real-model-plan.md), đợt đưa AGENT lên model thật.
Cả hai là **quyết định có chủ đích**, không phải sót.

| Việc | Cái gì đang chặn |
| --- | --- |
| Kiểm toán học của đề model sinh ra | Không bị chặn. Cố ý chưa làm để baseline chạy được trước |
| Bộ đo (eval) chất lượng sinh đề và giải thích | Không bị chặn. Chưa cần khi chưa biết model làm được tới đâu |

### Vì sao lỗ thứ nhất nghiêm trọng hơn nó trông

`validate_question` (`be/agent_gateway.py`) chỉ kiểm **cấu trúc** mà
[ADR-18](../decisions/adr-18-cau-hoi-phai-kem-loi-giai.md) đòi: đúng một phương án mang cờ
`is_correct`, nhiễu nào cũng có nhãn lỗi, ít nhất hai cách giải. Không dòng nào kiểm rằng phương án
mang cờ ấy **thật sự là đáp án đúng**.

Ngân hàng viết tay thì luôn đúng vì người soạn ra nó. Model thì không. Và BE chấm lượt làm lại bằng
cách so lựa chọn của học sinh với chính cờ `is_correct` đó — nên một đáp án gắn sai cờ nghĩa là
**học sinh làm đúng bị chấm sai**, rồi mất một trong ba vòng của
[ADR-17](../decisions/adr-17-ba-vong-moi-cau.md) vì lỗi không phải của em.

Đây là lý do nó nằm ở đây chứ không nằm trong `decisions/`: nó chưa phải một luật đã chốt, nó là một
món nợ đã biết giá.

### Ba đường đã nghĩ tới, chưa chọn

- **Model tự giải lại** câu nó vừa ra, lệch thì bỏ và sinh lại. Rẻ nhất, nhưng cùng một model kiểm
  chính nó thì cùng một chỗ mù.
- **Model thứ hai giải độc lập**, chỉ nhận đề chứ không nhận đáp án. Đắt gấp đôi, bắt được nhiều hơn.
- **Giáo viên duyệt** trước khi đề tới tay học sinh. Bắt được hết, nhưng đổi mô hình nghiệp vụ: pha 2
  đang là tự động và tức thì.

Chọn cái nào là một quyết định **nghiệp vụ**, nên khi chọn phải viết thành ADR chứ không nhét vào
plan.

### Không ai chặn Markdown và LaTeX, chỉ có prompt xin

Ghi từ pha 2 của [plan 2026-09-29](completed/2026-09-29-agent-real-model-plan.md). Prompt của trợ lý
cấm LaTeX và Markdown, nhưng **không dòng code nào kiểm**. `Turn` trong
`services/fe/src/screens/Tutor.tsx` in thẳng `text` vào JSX — không parser, không
`dangerouslySetInnerHTML` — nên model lỡ trả `**in đậm**` hay `\(x²\)` là học sinh đọc nguyên ký tự.

Cả hai đã thật sự xảy ra trong hai lần gọi model đầu tiên, nên đây không phải nỗi lo lý thuyết. Sau
mỗi lần sửa prompt thì tắt, nhưng một luật chỉ sống trong prompt là một luật không có nơi thi hành.

| Việc | Cái gì đang chặn |
| --- | --- |
| Chặn hoặc biến đổi Markdown/LaTeX trước khi lưu | Không bị chặn. Chưa quyết định *chặn* hay *dựng hình* |

Hai đường, và chúng dẫn đi rất khác nhau: **lọc** ở AGENT trước khi trả (rẻ, nhưng dấu `*` còn là
phép nhân, nên lọc ngây thơ sẽ ăn cả toán), hoặc **dựng hình** ở FE (đắt hơn, nhưng lúc đó công
thức hiện ra đẹp và ta thôi phải xin model đừng viết đẹp).

## Một effect tự nuôi mình, và 69 GB

Ghi ngày 2026-09-29, sau khi máy hết RAM sau bốn tiếng chạy app. Đây là **lỗi đã sửa**, ghi lại vì
hình dạng của nó sẽ quay lại.

Windows nêu đích danh: `node.exe` chiếm **74.688.204.800 byte** — tức Vite dev server, gần 70 GB.
BE, AGENT và Docker cộng lại chưa tới một phần ba mươi chỗ đó.

Nguyên nhân không nằm ở Vite. Trong `Tutor.tsx`, effect xin lượt mở đầu **đọc** `history` và cũng
**thay** `history` (qua `pull()` → `reload()`). Khi một lượt không sinh ra được — BE trả 409 lúc pha
1 chưa nộp — lịch sử quay lại vẫn rỗng, effect chạy lại ngay. Đo được **~1.500 request mỗi giây**;
bốn tiếng là chừng 22 triệu request đi qua proxy của dev server.

| Việc | Cái gì đang chặn |
| --- | --- |
| Tầng phòng thủ thứ hai cho vòng lặp client | **Tier 2: ngưỡng chặn tần suất là quyết định (đặt sai thì cắt nhầm học sinh thật)** (plan `backlog-tier-1`, pha 4). Không bị chặn. Chưa quyết định đặt ở đâu |

Bản sửa là một cái chốt: xin nhiều nhất một lần cho mỗi bài làm. Nó đúng và đủ cho nguyên nhân gốc,
nhưng nó nằm ở **client** — mà client là thứ ta ít kiểm soát nhất. Một tầng thứ hai ở BE (chặn tần
suất, hoặc trả 429 khi cùng một bài mở stream quá dày) sẽ biến "một effect viết sai" từ tai nạn cấp
máy tính thành một dòng log. Chưa làm vì chưa quyết định ngưỡng, và vì một ngưỡng đặt sai sẽ cắt
nhầm học sinh thật.

**Bài học đáng giữ hơn cả bản sửa:** một `useEffect` phụ thuộc vào state mà chính nó làm thay đổi là
một vòng lặp đang chờ một lần thất bại để bắt đầu. Nó chạy êm suốt quá trình phát triển vì đường đi
thành công luôn làm điều kiện dừng thành đúng. Chỉ đường đi **hỏng** mới lộ ra nó.

## Check `timeout-order` đã thôi nói dối (đóng 2026-09-30)

Ghi ngày 2026-09-29 khi phát hiện, **đóng** ngày 2026-09-30 ở Pha 2 của plan đường ghi.

`check_model_call_fits_inside_the_job_waiting_for_it` so `LLM_TIMEOUT_SECONDS × LLM_MAX_ATTEMPTS`
= 60 với `AGENT_JOB_TIMEOUT_SECONDS` = 70 rồi báo xanh. Nhưng `draft_assessment` gọi model **một lần
mỗi câu** và nhận tới 50 câu một job, nên trường hợp xấu nhất là 50 × 3 × 20s = **3000s**. Check
đang nói dối đúng về handler gọi model nhiều nhất — lần thứ hai, và docstring của chính nó kể rằng
nó từng sai y như vậy một lần rồi.

Không sửa bằng cách nhân thêm `question_count` vào phép so — làm thế thì check đỏ và đường ra là
nâng hạn job lên 50 phút, tức BE thôi phân biệt được worker chậm với worker chết. Sửa bằng cách đổi
**hình dạng công việc**: `draft_assessment` bị khai tử, thay bằng `write_draft_question` — một câu
một job. Nay mọi task đều nằm trong đúng một câu hỏi đáng giá số lần thử, nên phép so 60 < 70 là
thật với **tất cả** chúng, lần đầu tiên.

**Còn lại một chỗ chưa được bảo vệ bằng máy:** không gì ngăn ai đó thêm một vòng lặp theo số lượng
vào một handler và làm check nói dối lần thứ ba. Nó đã sai hai lần theo đúng cách đó. Một check tĩnh
cho "handler không gọi model quá `llm_max_attempts` lần" thì tôi chưa thấy cách viết cho đáng tin,
nên hiện luật này do review giữ, và docstring của check nói ra điều đó.

## Model chưa gọi lại tool khi đã được trao đúng id

Ghi ngày 2026-09-30, từ lượt gọi model thật đầu tiên của platform giáo viên.

Hỏi *"lớp 12A làm bài kiểm tra vừa rồi thế nào?"*, gpt-4o-mini làm đúng ba việc: gọi `find_class`,
rồi gọi `class_assessment_summary` với `assessment_id` rỗng như description dạy, rồi **nhận được**
`assessments_in_this_class` chứa đúng đề cần tìm. Sau đó nó trả lời "mình không tìm thấy" thay vì
gọi lại với id vừa được trao.

| Việc | Cái gì đang chặn |
| --- | --- |
| Làm model bền hơn ở bước cuối | Không bị chặn. Chưa làm vì đây là chất lượng model, không phải harness |

Trần vòng lặp còn 5 bước và ngân sách thời gian còn hơn 80 giây, nên nó có chỗ để đi tiếp; nó chọn
không đi. Ba đường: viết rõ trong `_SYSTEM` rằng thấy `assessments_in_this_class` thì phải gọi lại;
thêm một tool `class_assessments` để việc chọn đề là một bước riêng thay vì một lời từ chối; hoặc đổi
model. Đường thứ hai có vẻ đúng nhất, vì nó biến một lời từ chối có ích thành một hành động bình
thường.

Chưa làm vì ưu tiên đã chốt từ đầu là **chạy được trước, chấp nhận output tệ** — và luồng thì đã
chạy: ba lượt gọi model, nối tool đúng thứ tự, token và độ trễ có thật.


## Ba việc plan harness giáo viên cố ý để lại

Ghi ngày 2026-09-30, khi đóng `2026-09-30-teacher-harness-foundation-plan.md`. Chuyển sang đây vì
plan trong `completed/` là hồ sơ đóng: một ô `[ ]` nằm lại trong đó là một việc không ai sửa được và
không ai tìm thấy.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~Test rằng **đường HTTP** phát hành từ chối đề chưa duyệt~~ | **Xong** ở Pha 5 |
| ~~Bất biến giữa `Assessment.state` và số câu hỏi~~ | **Xong** ở Pha 4 |
| `entity_kind`/`entity_id` đủ cho bảy variant `Action result card` | **Tier 3: BE chưa ghi lần phát hành hỏng (_note_publication), không phải việc FE** (plan `backlog-tier-1`, pha 4). Còn **một** variant: `phát-hành-thất-bại` |

**Hai việc đầu đã xong** (`2026-09-30-teacher-write-path-plan.md`, Pha 4 và 5), và cả hai đúng theo
cách backlog này đoán: đường HTTP phát hành có test riêng ở tầng HTTP, và phép đếm câu hỏi nằm ở
endpoint duyệt chứ không trong `advance()`, vì đọc `.questions` ở đó là một lazy-load async.

Một điều backlog này **đoán sai**: nó viết *"khi có endpoint, không gì buộc nó đi qua `advance()`"*.
Có — `tools/check_contract.py :: tools-decide-nothing` grep `.state =` nên một phép gán viết rời
trong `teacher_tools.py` là build đỏ, và `grep -rn '\.state\s*=' services/be/src` nay cho đúng hai
kết quả, cả hai trong `assessment_state.py`. Nhưng phép grep ấy chỉ quét một file, và nó **không**
bắt được `Assessment(state=...)` ở constructor — xem mục nợ mới dưới đây.

**Việc thứ ba còn một variant.** Sáu trong bảy nay có dữ liệu: `tạo-đề-trống` và `thêm-câu-hỏi` từ
Pha 3, `đã-duyệt`/`bỏ-duyệt` từ Pha 4, `đã-phát-hành` từ Pha 5, `tạo-lớp` từ `find_class`. Thiếu
`phát-hành-thất-bại`: `_note_publication` chỉ ghi một bước khi **có** lớp nhận được, nên một lần phát
hành trượt toàn bộ không để lại dấu nào trong `teacher_turns`.

## Ba mục nợ của Pha 5

Ghi ngày 2026-10-01, từ review Pha 5.

| Việc | Cái gì đang chặn |
| --- | --- |
| `UniqueConstraint` mới trên `questions` chưa áp vào database đã tồn tại | Không có migration; `create_all` bỏ qua bảng đã có |
| Hai ADR chọn **bao gồm** ở hai phía của cùng một mốc | Cần một quyết định, không phải một bản sửa |
| ~~`check_contract` không bắt `Assessment(state=...)` ở constructor~~ | **Đã làm: lượt đọc AST trong tools-decide-nothing, tool chỉ được tạo đề EMPTY** (plan `backlog-tier-1`, pha 4). Chưa quyết nên mở rộng grep hay đổi cách |

**Việc thứ nhất.** `db.py` dùng `Base.metadata.create_all`, và `data-model.md` ghi rõ rằng gọi nó
trên một bảng đã tồn tại thì *"không có gì xảy ra và cũng không có lỗi nào"*. Nên
`UniqueConstraint("assessment_id", "order_index")` thêm ở Pha 5 chỉ có hiệu lực với ai xoá volume —
và lập luận *"để database làm bên phân xử thay vì một biến cục bộ"* trong comment của `models.py`
đúng về thiết kế mà chưa đúng về máy đang chạy. Cùng một vật chặn với mọi thay đổi schema khác ở đây.

**Việc thứ hai, và nó là một cái hở trong ADR chứ không trong code.** ADR-02 cho thu hồi **tới hết**
giờ mở (bao gồm); ADR-03 cho học sinh vào **từ** giờ mở (cũng bao gồm). Tại đúng khoảnh khắc
`now == opens_at`, một học sinh được vào **và** giáo viên được thu hồi — và nếu cả hai xảy ra thì
`_publication` trả 404 cho một bài đang làm, trái điều khoản *đã vào rồi thì không bị dừng giữa
chừng* của ADR-03. Xác suất thực tế gần 0 vì so tới micro-giây, nhưng thứ cần sửa là **một trong hai
ADR phải chọn loại trừ**, và đó là một quyết định về sản phẩm.

**Việc thứ ba.** Pattern của `tools-decide-nothing` là `\b(advance|withdraw)\s*\(|\.state\s*=[^=]|\bteacher_routes\b`.
Nó không bắt `Assessment(state=AssessmentState.PUBLISHED)` ở constructor, nên một tool **tạo** một đề
ở trạng thái bất kỳ thì check vẫn xanh. Chưa sửa vì bản sửa thẳng nhất — cấm cả `state=` — sẽ đỏ ở
`seed.py` và `teacher_tools.py`, hai chỗ tạo đề hợp lệ; nên nó cần một cách phân biệt *tạo* với *đổi*,
và đó là việc đáng làm một lượt cùng với việc nới check sang nhiều file hơn một.

## Hai việc còn lại của plan `core-two-phase-backend`

Ghi ngày 2026-09-30, khi dọn `docs/plans/active/`. Plan đó đóng theo xác nhận của người dùng, nhưng
hai ô này **thật sự chưa làm**, nên chúng sang đây thay vì đi theo plan vào `completed/`.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~Vòng đời đề ở BE: nháp → duyệt → phát hành, kèm cổng *chỉ giáo viên phát hành*~~ | **Xong** ở Pha 4 và 5 |
| ~~Chuyển hai dòng invariant của UC-05 sang nhóm tự động~~ | **Hết lý do** — xem dưới |

Việc đầu **đã xong** ở `2026-09-30-teacher-write-path-plan.md`: `teacher_routes.py` có cả năm
endpoint — duyệt, bỏ duyệt, mở biểu mẫu, phát hành nhiều lớp, thu hồi một lớp — và chúng đi qua
`advance()`/`withdraw()`. Nó gộp luôn hai mục backlog ở trên như đã đoán; mục thứ ba
(`entity_kind`/`entity_id`) còn đúng một variant.

Việc thứ hai **hết lý do tồn tại ngày 09/10/2026**. Nó nói về hai dòng trong nhóm chưa-enforce
của `AGENTS.md`. Dòng *"A low-confidence result is not shown to the Student before a Teacher handles
it"* đã bị **xoá** cùng cả đường chấm bài cũ — không còn gì để chuyển. Dòng còn lại, *"A retry
question is a variant of the same question"*, thuộc [ADR-17](../decisions/adr-17-ba-vong-moi-cau.md)
chứ không thuộc UC-05, và nó vẫn ở nhóm chưa-enforce — đúng chỗ. Nhóm ấy nay còn **một** dòng, dưới
trần ba.

(Số hiệu *UC-05* ở đây là theo cách đánh số **cũ** của báo cáo, nơi UC-05 là *Xử lý bài cần review*.
Sau lượt 09/10/2026 thì UC-05 là *Hệ thống tạo câu biến thể*.)

## Trộn đề: bộ câu hỏi lớn, mỗi học sinh một lát

Ghi ngày 2026-09-30, khi `publications` thành một hàng mỗi (đề, lớp).

Phát hành lệch giờ là chuyện bình thường của một trường: 12A học sáng thì mở sáng, 12B học chiều thì
mở chiều. Nhưng nó mở ra một khoảng thời gian mà lớp trước đã làm và lớp sau chưa, nên **nếu hai lớp
làm đúng cùng một mười câu** thì lệch giờ là một lỗ.

| Việc | Cái gì đang chặn |
| --- | --- |
| Bộ đề lớn hơn bài kiểm tra: 50 câu trong bộ, mỗi học sinh lấy 10 câu | Không bị chặn. Chưa cần ở đợt đường ghi đầu tiên |

Đường đi đã rõ: một đề giữ **bộ câu hỏi**, và mỗi `Attempt` giữ lát của riêng nó — cùng hình dạng với
`round_items` của pha 2, vốn đã lưu câu của một lượt riêng cho một bài làm. Cái phải quyết là ai chọn
lát: chọn lúc bắt đầu làm bài (đơn giản, nhưng hai học sinh cùng lớp có đề khác nhau nên không so
điểm trực tiếp được), hay chọn một lát mỗi lớp (so được trong lớp, không so được giữa lớp).

**Chừng nào chưa có nó**, lệch giờ là tiện lợi về lịch, **không** phải bảo đảm về bí mật đề — và
docstring của `Publication` nói đúng câu đó để không ai đọc việc phát hành lệch giờ thành một tính
năng chống lộ đề.

## Ký hiệu toán không đồng nhất trong một bộ đề

Ghi ngày 2026-09-30, từ lượt gọi model thật đầu tiên của đường soạn đề.

Ba câu sinh ra cùng một brief, và chúng viết số mũ **ba kiểu khác nhau**:

```
1. ... y = 2x³ - 6x² + 4 ...        <- đúng, Unicode
2. ... P(x) = 2x^3 - 6x^2 + 4x - 8  <- dấu mũ ASCII
3. ... P(x) = x^4 - 4x^3 + ...      <- dấu mũ ASCII
```

`_SYSTEM` của `graphs/authoring.py` viết *"Toán viết bằng ký hiệu Unicode: y = x³ − 3x... Tuyệt đối
KHÔNG dùng LaTeX"*. `x^3` **không phải** LaTeX, nên nó không vi phạm câu cấm — nó chỉ không làm theo
câu yêu cầu, và không gì kiểm.

| Việc | Cái gì đang chặn |
| --- | --- |
| Chuẩn hoá ký hiệu toán lúc thu hoạch, hoặc từ chối câu dùng `^` | Không bị chặn. Chưa quyết chuẩn hoá hay từ chối |

Đây là **cùng loại lỗi** với thứ brief-bị-khoá dựng lên để ngăn, chỉ ở tầng hình thức thay vì nội
dung: đọc từng câu thì không thấy gì sai, đọc cả bộ mới thấy nó không phải một bộ. Và nó là lỗi học
sinh sẽ nhìn thấy trực tiếp.

Hai đường: chuẩn hoá ở `harvest` (`x^3` → `x³`, một bảng tra nhỏ, nhưng `x^10` thì không có ký tự
Unicode tương ứng), hoặc từ chối như một lỗi shape ADR-18 và để BE hỏi lại — đắt hơn nhưng đặt luật
ở đúng chỗ đã có cơ chế hỏi lại. Chưa làm vì `validate_question` hiện chỉ kiểm cấu trúc, và thêm một
luật về *hình thức chữ* vào đó là một quyết định về phạm vi của ADR-18.


## Đề nháp trống bị bỏ lại, và không có đường xoá

Ghi ngày 2026-10-01, từ review Pha 3 của đường ghi.

`create_draft` ghi một `Assessment` + một `DraftBrief` rồi trả về ngay. Nó **không** idempotent, và
đó là có chủ ý: hai lần hỏi là hai đề, vì dùng lại đề đầu sẽ âm thầm trộn hai brief vào một bộ, còn
từ chối lần thứ hai thì cấm giáo viên soạn hai đề trong một buổi. Cái giá là mỗi lượt chat chết sau
`create_draft` nhưng trước `start_drafting` để lại một đề `EMPTY` không ai gọi tên nữa — và hôm nay
**không có đường nào xoá nó**.

| Việc | Cái gì đang chặn |
| --- | --- |
| Một đường xoá đề nháp (tool, hay endpoint của giáo viên) | Chưa quyết ai được xoá và xoá tới đâu |
| Tool đọc liệt kê đề nháp của giáo viên, để thấy mà dọn | Chờ đường xoá: liệt kê rác mà không dọn được thì tệ hơn |

Chưa làm vì xoá là thao tác **không đảo ngược được**, nên theo ADR-05 nó thuộc phía giáo viên, không
phải một tool — và nó cần ít nhất một hộp xác nhận. Nó cũng cần biết một đề `EMPTY` khác gì một đề
giáo viên đang cố ý soạn dở: `created_at` cũ bao lâu thì được coi là rác là một quyết định về sản
phẩm, không phải về code. Tác hại hiện tại chỉ là rác trong bảng, không ai thấy, nên nó chờ được.

## Lỗi từ đợt khảo sát 05/10/2026 chưa làm

Đợt khảo sát tìm 16 lỗi; tám món đã vào `2026-10-06-tam-loi-khao-sat-plan.md`. Tám món còn lại nằm
đây, mỗi món kèm lý do nó chờ.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~`vet_plan` cho lọt một id là chuỗi số trần (`"1"` thay cho `{1.assessment_id}`)~~ | **Đã làm: *_id toàn chữ số bị từ chối, nhắc viết {k.field}** (plan `backlog-tier-1`, pha 4). Siết hợp đồng lập kế hoạch của agent — người dùng gạt ra ngoài đợt này |
| `start_drafting` gọi thẳng không qua plan, bị ADR-25 từ chối, mất một lượt model | Cùng hợp đồng trên |
| Model đánh dấu sai đáp án đúng, và đáp án đúng không nằm trong bốn phương án | Chất lượng model sinh ra; đường sửa đi qua prompt |
| Model viết *"định thức"* cho một bài tích phân, và `\bigint` — một lệnh không có thật | Cùng trên |
| ~~Chip nguồn câu hỏi vẫn là chữ bịa (`invented-not-from-be.ts`)~~ | **Chip đã gỡ 17/10/2026** (plan `backlog-tier-1`, pha 2). Chờ BE có cột nguồn; nợ đã khai báo, có check giữ nó ở một file. Từ ADR-28 phần *đã kiểm / chưa kiểm* của chip suy được từ trạng thái đề, nhưng plan ngân hàng giữ nguyên giao diện nên chip chưa đổi |

Đã làm trong đợt này nhưng đáng ghi lại vì nó mở rộng phạm vi ADR-26: chữ Kriky nói trong khung chat
(`propose.py` → `_Proposal.text` → `MathText`) đi **cùng một ống JSON** với đề bài, và trước đợt này
không chỗ nào sửa. Check `escape-repair-is-wired-in` nay tự tìm mọi chỗ gọi `with_structured_output`
trong `graphs/`, nên một graph mới quên nối dây sẽ làm build đỏ thay vì im lặng.

## Hai component Figma chưa vẽ xong

Ghi ngày 2026-10-08, lúc xếp lại page `Components` cho plan 2b. Cả hai là **quyết định thiết
kế**, không phải lỗi máy móc, nên chúng không được sửa vội trong một plan đang làm việc khác.

| Việc | Cái gì đang chặn |
| --- | --- |
| `Kriky state` (`234:1180`) có năm variant — `nghỉ`, `đang đọc`, `đang hỏi`, `đang làm`, `đã xong` — mỗi cái là một hộp **40×40 rỗng không** | Cần vẽ năm tư thế của linh vật Dế Mèn. Tài sản nằm ở page `Assets — Dế Mèn`; việc còn lại là chọn tư thế nào cho trạng thái nào, và đó là một quyết định về nhân vật chứ không phải về code |
| ~~`Question card` (`267:30`) là COMPONENT_SET nhưng chỉ có **một** variant `Lời giải=thu gọn`~~ | **Đã làm: bỏ trục, thành component thường; 34 instance giữ liên kết, mô tả bỏ đoạn chip nguồn** (plan `backlog-tier-1`, pha 4). Một trục variant một giá trị thì không phải một trục. Tên trục ngụ ý phải có `Lời giải=mở`, nhưng chưa ai vẽ thẻ lời giải mở. Hai đường: vẽ variant thứ hai, hoặc bỏ trục và để nó là một component thường — thuộc tính boolean `Sửa được` thì thật và đang được ADR-01 nhắc tới, nên nó ở lại dù chọn đường nào |

Không chặn gì đang chạy: `Kriky state` chưa artboard nào dùng, và `Question card` dùng được bình
thường ở artboard 6 và 7 với variant duy nhất của nó.

## Kênh SSE của thư viện tài liệu không tự nối lại

Đo được ngày 2026-10-08, trong lúc chạy cổng sống của plan 2c. **Lỗi có từ plan 2b**, không phải
do việc tách `services/ingest` sinh ra — 2c chỉ là lần đầu có người restart BE trong khi một tab
đang mở, nên nó mới lộ ra.

`teacher.watchDocuments` dùng `fetch` + reader thay vì `EventSource`, và lý do thì đúng:
`EventSource` không gửi được header `X-Actor`, mà nhét danh tính vào query string là đưa nó vào
mọi access log. Nhưng `EventSource` **tự nối lại** khi kết nối đứt, còn một vòng đọc `fetch` thì
không — nó chỉ kết thúc.

**Triệu chứng đo được:** một tab mở từ trước khi BE restart hiển thị **6 tài liệu trong khi API
trả 13**, và không có một dấu hiệu nào trên màn hình. Giáo viên nhìn thấy một thư viện đúng-như-cũ,
tức một màn hình nói dối theo đúng nghĩa ADR-27 dùng chữ ấy. Chỉ F5 mới chữa, mà không gì bảo họ
phải F5.

| Việc | Cái gì đang chặn |
| --- | --- |
| Nối lại kênh sau khi nó đứt — một vòng lặp ngoài, có backoff, và dừng khi `AbortController` bị huỷ | Không chặn gì. Nó là một thay đổi **FE**, nên theo luật phải đi qua Figma trước nếu có gì hiện lên màn hình. Câu chưa trả lời: lúc kênh đứt thì màn hình có **nói ra** không, hay nối lại im lặng? Nói ra thì cần một trạng thái mới trên bản vẽ; im lặng thì rẻ hơn nhưng lặp lại đúng thói quen vừa bị bắt |
| Trần số connection của `StreamingResponse` vẫn **chưa đo** | Nợ từ plan 2b. Một giáo viên mở năm tab là năm connection, và không có gì giới hạn. Một vòng nối lại làm con số này đáng đo hơn, không kém đi |

**Dòng đầu đã trả ngày 12/10/2026** (`completed/2026-10-12-document-channel-reconnect-plan.md`):
FE nay tự nối lại, giãn 3 s → 30 s, coi kênh câm quá 40 s là chết, và đọc lại danh sách ngay khi
kênh nghe được. Câu hỏi *nói ra hay im lặng* được trả bằng **im lặng**: không có gì mới trên màn
hình, nên không qua Figma. Còn lại: các lần `GET` danh sách chạy song song có thể về lệch thứ tự,
và bản cũ hơn có thể đè bản mới (`Chat.tsx`, gọi `listDocuments` không có thẻ thứ tự). **Đã trả 17/10/2026**
(plan `backlog-tier-1`, pha 3): `readDocuments` chỉ nhận lời đáp của lần đọc mới nhất.

## Ba món nợ còn lại của plan 2a

Chép từ mục *Còn nợ* của `completed/2026-10-08-document-service-text-layer-gate-plan.md` ngày
10/10/2026, lúc plan ấy về `completed/`. Hai món khác của cùng danh sách **không** chép xuống: trần
connection SSE đã nằm ở mục *Kênh SSE của thư viện tài liệu không tự nối lại*, và nhãn
`HTTP /api, qua Vite proxy` đè hai hộp thì **hết đúng** — sơ đồ `system-architecture` đã được vẽ lại
ngày 09–10/10/2026 và nhãn ấy nay chỉ còn là `HTTP /api`.

| Việc | Cái gì đang chặn |
| --- | --- |
| `aiafa:grading` vẫn mang cái tên sai | Không bị chặn. Nó chở bảy task và sáu cái không chấm bài. Đổi tên là một refactor riêng: nó chạm `.env.example`, `be/config.py`, `agent/config.py`, và một queue đang có job thì không đổi tên nóng được |
| ~~Không có lưới cho chiều *"`config.py` đọc một biến mà `.env.example` không khai"*~~ | **Đã làm: check env-example đi hai chiều; khai năm biến còn thiếu** (plan `backlog-tier-1`, pha 4). Chưa quyết hình dạng lưới. `dev_identity_header` đã sống như vậy từ lâu, và nay `document/config.py` cùng `ingest/config.py` mang đúng rủi ro ấy. Lưới hiện có chỉ đi một chiều: nó bắt biến khai trong `.env.example` mà không ai đọc |
| Một job `probe` bị arq thử lại không có trần riêng | Không bị chặn. Cần một phép đo trước một quyết định: `max_tries` mặc định của arq nhân với giãn cách của nó có thể vượt `DOCUMENT_STALE_AFTER_SECONDS`, và lúc ấy API suy ra `failed` trong khi job vẫn còn sống — đúng ca mà plan 2a đã chứng minh là *"một job về muộn vẫn thắng"*, nhưng chưa ai đo xem nó muộn tới đâu |

## Lời gọi báo cáo cuối lượt — không cấp ngân sách, vì nó sẽ không ở lại

Quyết định ngày 10/10/2026: **không** đi thêm `deadline` vào `_report` và `_name_the_thread`.
Lý do không phải là chưa kịp, mà là chỗ chữa nằm ở tầng khác — **bước báo cáo cứng ở cuối lượt
sẽ tan vào quy trình của skill**. Một trợ lí được nói cho biết việc của nó thì tự biết khi nào
phải kể lại; một dòng code buộc mọi lượt phải gọi model lần nữa thì không biết gì cả, nó chỉ
tuân lệnh. Skill là chỗ quy trình ấy sống (ADR-27: Markdown có frontmatter `name` + `description`,
Jev chọn), nên việc này **đi cùng plan 4 — Jev và skill** của đợt *Đọc PDF vào ngữ cảnh ra đề*.

Phép đo đã có, để người làm sau không phải đo lại. Hai mức chặn hiện hành chỉ canh pha 1:
`max_tool_steps = 8` và `turn_budget_seconds = 90` (`services/be/src/be/config.py:93-96`), và mức
thời gian được kiểm **ở đầu** mỗi vòng lặp pha 1 (`services/be/src/be/teacher_chat.py:1350-1355`),
không chỗ nào khác trong `run_turn`. Từ đó, p99 xấu nhất của cửa `POST`:

| Đoạn | Trần thật |
| --- | --- |
| Pha 1 | 90s, nhưng một job đã bắt đầu vẫn chạy hết → tới 90 + 70 |
| Pha 2 | `POST` không đợi câu hỏi (`watching=False`), chỉ là thời gian đẩy job |
| Báo cáo | `run_task` → `agent_job_timeout_seconds` = 70s (`be/agent_gateway.py:76`), không hỏi `deadline` |
| Đặt tên đoạn chat | thêm một `run_task` nữa ở lượt đầu → 70s |

Khoảng **300 giây**, trong khi con số duy nhất được thiết kế để giáo viên cảm thấy là 90. Nghịch lý
nằm ở chỗ `turn_budget_seconds` sinh ra **chính vì** một trần số bước không phải một lời hứa về thời
gian — rồi hai lời gọi model cuối cùng đứng ngoài nó.

Chưa đau hôm nay: FE dùng cửa SSE, nơi không request nào phải đứng chờ, và nó có
`stream_silence_timeout_seconds = 25` canh sự im lặng. Cửa `POST` còn sống cho sáu test cũ và cho
một client không stream.

| Việc | Cái gì đang chặn |
| --- | --- |
| Bỏ bước báo cáo cứng, đưa việc kể lại vào quy trình của skill | Chờ plan 4 (Jev và skill). Không phải một lượt sửa `teacher_chat.py`: nó gỡ một luật của ADR-25 |
| Cờ *"lượt này đã báo cáo chưa"* trong `teacher_turns` | **Đã bỏ**, không phải đang chờ (người dùng, 10/10/2026). Cái cờ chỉ có nghĩa khi còn một bước báo cáo cứng để đếm xem lượt nào còn nợ một câu kết; bỏ bước ấy thì không còn gì để đếm. Nó cũng đòi đẩy pha 2 sang một job arq, tức một đường chạy nền thứ hai trong BE mà ADR-25 cố ý tránh. ADR-25 đã ghi lại ở khối *Sửa ngày 10/10/2026* |
| Cấp ngân sách cho `_report` và `_name_the_thread` như một đường vá tạm | **Cố ý không làm.** Đường lùi đã có — `_report` nuốt mọi exception và trả câu do BE viết (`teacher_chat.py:594-596`) — nên hết ngân sách không phải một lượt chết. Vá nó là làm chắc một bước sắp bị bỏ |

**Người làm sau cần biết thứ tự.** Bước báo cáo không chỉ là code: ADR-25 chốt nó thành luật
(*"Pha 2 xong thì model báo cáo... trong một lời gọi riêng"*), và `check_the_report_is_a_job_of_its_own`
trong `tools/check_contract.py` canh đúng luật ấy ở ba chỗ chịu lực — task riêng trong
`agent/worker.py`, `PlanReportRequested` không có field nào chở tool, và graph kể lại không chạm
`ToolSpec`. Nên đường đi là **sửa ADR-25 trước**, rồi mới tới check, rồi mới tới code
(`agent/graphs/reporting.py`, `REPORT_PLAN_TASK`, `PlanReportRequested`, `PlanReportCompleted`).
Gỡ check trước là gỡ nơi thi hành của một luật vẫn còn hiệu lực.

## Hai món review khoá lượt để lại (10/10/2026)

Review pha A của `2026-10-10-one-turn-per-conversation-plan.md` tìm ra sáu lớp lỗi. Bốn đã vá trong
chính plan ấy; hai món dưới đây cố ý để lại, vì cả hai chỉ đau trong một hình thế mà hệ chưa có.

**Nhả khoá muộn trên một session đã đóng.** `_let_go_of_the_thread` nhận chính `session` của request,
và nó chạy trong `finally` của một generator. Khi lượt đi hết đường bình thường thì session còn sống,
nên đường nhả chạy ngay. Ca xấu là khi generator **không** được đóng ở đây mà bị bỏ lại cho bộ dọn
async-generator của event loop: lúc ấy câu `UPDATE` nhả khoá chạy trên một session có thể đã bị
`close()`, và cú nhả thất bại — `logger.exception` ghi lại, rồi cửa sổ quá hạn nhả hộ sau mười phút.
*Cái gì đang chặn:* chưa đo được ca ấy xảy ra trên cửa SSE thật. Phép đo ngày 10/10/2026 (ngắt kết
nối giữa lượt, ba lần) cho thấy khoá nhả trong 0,06s, tức đường `finally` **có** chạy với session còn
sống. Sửa đúng cách là mở một session riêng cho đường nhả, và việc ấy chỉ đáng làm khi có một phép đo
cho thấy nó cần.

**Đồng hồ của process, không phải của database.** `_hold_the_thread` ghi `datetime.now(UTC)` lấy từ
process BE, rồi so chính nó với `cutoff` cũng lấy từ process BE. Một BE thứ hai có đồng hồ lệch vài
phút sẽ coi một khoá còn sống là đã quá hạn, hoặc ngược lại — và fencing (`WHERE running_since =
:mine`) chỉ chặn hậu quả tệ nhất chứ không chữa cái lệch. *Cái gì đang chặn:* chỉ có một BE. Sửa bằng
`func.now()` cho cả mốc ghi và `cutoff` thì để Postgres làm đồng hồ duy nhất — nhưng bộ test chạy
trên `sqlite+aiosqlite://`, nơi `func.now()` có kiểu trả về khác, nên việc này kéo theo một lượt đổi
nền của test. Đáng làm cùng lúc với BE thứ hai, không trước.

**Và một thứ bộ test không canh được.** Tính atomic của `_hold_the_thread` — một câu `UPDATE ... WHERE`
rồi đọc `rowcount` — không có lưới trong `pytest`, vì sqlite không tái hiện được cách Postgres phân xử
hai câu `UPDATE` cùng giành một hàng. Nó đã được đo bằng tay trên Postgres thật (40 lượt × 4 session,
đúng một người thắng mỗi lượt; bản đọc-rồi-ghi đối chứng cho `[1, 4]`), và phép đo ấy ghi trong Status
của plan. Nhưng một phép đo bằng tay không chạy lại ở mỗi `check`: hồi quy ở đây sẽ đi qua cổng mà
không ai thấy. Dựng một lưới thật đòi cho bộ test chạy trên Postgres, cùng một việc với món đồng hồ ở
trên.

## Hai món nợ còn hiệu lực của plan hai pha

Chép từ mục *Rủi ro đã biết* của `completed/2026-10-02-hai-pha-mot-luot-chat-plan.md` ngày
10/10/2026, lúc plan ấy về `completed/`. Hai món khác của cùng danh sách **không** chép xuống, vì
chúng đã được xử hẳn và Status của plan ấy ghi rõ: cờ *"lượt này đã báo cáo chưa"* đã **bỏ**, và
ngân sách cho lời gọi báo cáo đã **không cấp** (mục *Lời gọi báo cáo cuối lượt* ở trên giữ phép đo).
Món thứ năm — hai tab cùng một đoạn chat — đã làm xong trong
`completed/2026-10-10-one-turn-per-conversation-plan.md`.

| Việc | Cái gì đang chặn |
| --- | --- |
| Luật *"nói đang soạn, chứ không nói đã soạn xong"* còn là một câu trong prompt (`agent/graphs/reporting.py`, `_SYSTEM`) chứ chưa là dữ liệu | Không bị chặn, nhưng **đang đúng vì ăn may**: nó đúng chỉ vì báo cáo hôm nay chạy ngay sau bước cuối, lúc arq còn đang soạn. Ngày nào pha 2 xong trước lúc báo cáo thì chính dòng ấy thành máy sinh lời nói sai chiều ngược lại. Chỗ chữa là đưa *còn bao nhiêu câu đang soạn* vào `PlanReportRequested` rồi xoá dòng prompt. Việc này nay vướng quyết định lớn hơn: bước báo cáo cứng ở cuối lượt sẽ tan vào skill, nên sửa prompt trước là sửa một chỗ sắp biến mất |
| `StepOutcome` không có field nào chở con số thật | Không bị chặn, và đây là món **đắt dần**: `detail` của `start_drafting` mãi là *"10 câu bắt đầu soạn"*, còn câu kết mà artboard 5 đã vẽ — *"8 câu lấy từ ngân hàng, 2 câu tôi soạn thêm"* — không có đường nào đi qua hợp đồng. Thêm field sau khi hợp đồng deploy là một lần bump `SCHEMA_VERSION`; hôm nay thì chưa |

## Jev dựng hierarchy cho một cuốn sách đã OCR — plan 3c (document agent) của đợt đọc PDF

Ghi ngày 10/10/2026, lúc plan 3 của `active/2026-10-07-doc-pdf-vao-ngu-canh-plan.md` vỡ làm ba.
Thiết kế do người dùng đề ra cùng ngày; hình dạng đã chốt, file plan thì chưa viết.

Ý chính, và nó là chỗ toàn bộ đợt này đứng hay sụp: **không tin mục lục của tài liệu.** Thay vì đọc
`get_toc()`, mỗi khối mà OCR trả về đi qua Jev với hai câu hỏi đóng, chạy song song trên một `state`:

- **Loại khối** — heading, đoạn văn, chú thích hình, bảng, header/footer.
- **Quan hệ cấu trúc** với heading liền trước — cấp cao hơn, cùng cấp, cấp con, hoặc không phải một
  heading.

**Đổi ngày 11/10/2026, khi plan 3c được viết** (`completed/2026-10-11-document-agent-hierarchy-plan.md`,
D1): người dùng ghim cây **đúng ba cấp**, bậc sâu hơn gộp vào cha, nên câu thứ hai thành **cấp tuyệt
đối** (`level_1` / `level_2` / `level_3` / `deeper`) -- câu tương đối thì một lần sai kéo sai cả chuỗi.
Câu thứ ba (công thức) chuyển hẳn sang 3d. Phần dưới giữ làm lịch sử của thiết kế.

Cộng một câu thứ ba cho công thức, để mục nợ dưới đây có đầu vào: **công thức được dùng / đề bài /
bước giải**.

| Việc | Cái gì đang chặn |
| --- | --- |
| Dựng cây mục lục bằng Jev từ nhãn khối + hình học + số thứ tự | Chờ plan 3a. Không có chữ thì không có gì để hỏi |
| ~~Quyết OCR cả bộ một lần rồi cache, hay OCR theo yêu cầu từng chương~~ | **Đã quyết 11/10/2026**: OCR lúc upload, theo lô trang, bản thô vào Mongo -- plan 3b. Số của 3a: 4,5 s/trang, 1 561 trang ≈ 2 giờ trên 4 luồng |
| ~~Mongo vào `docker-compose.infra.yml`~~; chunk xuống Mongo | Mongo và bản thô: **plan 3b**. Chunk: vẫn ở đây (3c), và 3c ghi bằng khoá Mongo của chính document agent -- người dùng chốt 11/10/2026 *"Mongo là kho nội dung, như MinIO"*, nên không còn phải đi qua `services/ingest`. 3c **không sửa** collection `pages` (bất biến, D6 của plan 3b) |

**Bốn phép đo phải giữ, để người làm 3c không phải đo lại:**

- **`get_toc()` không dùng được trên dữ liệu thật.** Bốn cuốn báo `toc == page_count` vì máy quét ghi
  **một bookmark mỗi trang**: `[1, 'TOÁN 11 - KNTT - TẬP 01_Page_001', 1]`. Một mục lục giả tệ hơn
  không có mục lục, vì code tin nó.
- **Mọi tín hiệu font đã chết.** Cả 14 cuốn trong `data/` là ảnh scan thuần — mỗi trang đúng một ảnh
  toàn trang, **0 ký tự**, `drawings=0`, ~1190×1667 px trên A4 ≈ 144 DPI. Cỡ chữ, in đậm, font
  Computer Modern cho công thức: không cái nào tồn tại. Hierarchy phải dựng từ **hình học + nhãn
  layout + số thứ tự**, và đó chính là lý do thiết kế Jev ở trên thành trung tâm chứ không phải một
  lớp phụ trợ.
- **Heuristic heading ngây thơ sai thảm.** Đo trên `docs/report/report.pdf` — một PDF **có** text
  layer, tức điều kiện dễ hơn SGK: **252 ứng viên cho 45 heading thật**, recall 87%, precision ~15%,
  và phần lớn rác đến từ chính trang mục lục in trong tài liệu. Đó là phép đo biện hộ cho module
  `toc_boilerplate` của PageIndex Flash **và** cho bộ lọc Jev.
- **PP-DocLayout đã cho sẵn tín hiệu.** Nó trả `doc_title`, `paragraph_title`, `text`, `formula`,
  `image`, `number` kèm bbox và thứ tự đọc — `number` chính là số trang in, mảnh để nối trang PDF với
  trang in trong sách. Nên câu gửi Jev không phải *"đây là gì"* mà là *"xác nhận, và xếp cấp"*, rẻ hơn
  hẳn một câu mở.

## sympy kiểm công thức, và vòng sửa phải có trần kép — plan 3d của đợt đọc PDF

Ghi ngày 10/10/2026, cùng lượt trên.

| Việc | Cái gì đang chặn |
| --- | --- |
| Kiểm một công thức vừa OCR, sai thì gọi LLM sửa, lặp tới khi đúng | Chờ đường đọc công thức bằng VLM (mục dưới) và 3c (nhãn phân loại công thức, việc của Jev) |

**Đầu vào đổi ngày 11/10/2026.** Công thức không còn đến từ PP-FormulaNet lúc upload, mà từ **VLM
lúc ra đề** (`gpt-4.1-mini` / `gpt-5.6-luna` / `gpt-6-luna`, xem mục *Đọc công thức bằng VLM lúc ra
đề* dưới). Nên sympy kiểm **kết quả VLM**, và "bước LLM tự dựng lại" là vòng sửa của chính mục này.
Người dùng kỳ vọng hai bước ấy kéo cả ba model lên. Hai lỗi đo được mà vòng này phải bắt: VLM đọc `⋮`
(chia hết) thành `:` (chia) -- đổi nghĩa mà vẫn là một biểu thức hợp lệ, nên **sympy không kêu**,
giống hệt ca `P(x)=P(x)-C(x)` dưới -- và mất `\underbrace{…}_{n \text{ thừa số}}`.

Phạm vi được người dùng thu hẹp ngày 10/10/2026, và chính cái thu hẹp ấy làm việc này khả thi: công
thức ở đây **không phải một đề bài cần chứng minh**, mà là **đẳng thức đã được chứng minh trước mà
học sinh được dùng lại không cần chứng minh**. sympy quyết được **tính đúng đắn cú pháp** của mọi
công thức, nhưng quyết được **tính đúng về toán** chỉ cho đúng lớp hẹp ấy — nên Jev là thứ phải phân
biệt hai lớp trước khi sympy được gọi.

**Hai ràng buộc phải mang vào thiết kế, cả hai từ phép đo chứ không từ suy đoán:**

- **Vòng sửa cần trần kép, không chỉ một điều kiện dừng.** Qua được sympy là **chưa đủ**: một LLM có
  thể sửa một công thức bị OCR sai thành một đẳng thức **khác** vẫn đúng — và lúc ấy nó đã viết lại
  nội dung sách giáo khoa, im lặng, với một lưới báo xanh. Nên bản sửa phải bị ràng thêm bằng
  **khoảng cách sửa so với chuỗi OCR gốc**, cộng một trần số vòng.
- **Có một ca sympy không bắt được, và nó đã xảy ra thật.** PP-FormulaNet đọc `P(x)=R(x)-C(x)` thành
  `P(x)=P(x)-C(x)`. Đó là một **định nghĩa**, không phải một đẳng thức đúng, nên không phép kiểm toán
  học nào kêu lên được. Lưới cho hình dạng ấy phải so với **ảnh của khối**, không so với **toán** —
  tức nó là một việc khác hẳn, và gộp nó vào vòng sympy là tự lừa mình.

## Đọc công thức bằng VLM lúc ra đề — việc còn lại của plan 3a

Ghi ngày 11/10/2026, khi plan 3a đóng. Chi tiết, số đo và lý do nằm ở `Status` của
`completed/2026-10-10-document-ocr-text-and-latex-plan.md`.

Đường upload giờ **chỉ đọc chữ**. Công thức được đọc lúc ra đề, chỉ ở phần tài liệu được tham chiếu,
bằng VLM của OpenAI trên **cả ảnh trang**. Người dùng chốt ba lựa chọn: `gpt-4.1-mini` (mặc định,
nhanh nhất), `gpt-5.6-luna` (chính xác nhất trên mẫu 19 công thức, chậm 2,6 lần), `gpt-6-luna` (rẻ
nhất). Chưa dòng code nào của đường này được viết.

| Việc | Cái gì đang chặn |
| --- | --- |
| `agent/vision.py` + `vision_provider`/`vision_model` trong `agent/config.py` + `vision_model()` trong `llm.py`; structured output; đi qua bước sửa thoát ký tự; test không gọi mạng | không gì -- hướng đã chốt ở plan duyệt 11/10/2026 |
| Prompt cho `⋮` (`\vdots`, không phải `:`) và `\underbrace`, đo lại 5 trang của `data/results/run-5` | không gì; dưới 1 cent |
| Thước công thức chuẩn hoá mạnh + ghép phủ-đủ vào `tools/ocr_bench/score.py`, có test | không gì -- hiện chỉ ở script khảo sát ngoài repo |
| Benchmark 50 trang cho ba lựa chọn (≈ $0,13) | người dùng cho phép (lệ đặt 11/10/2026: chi phí báo trước, benchmark sau) |
| Nối vào lúc ra đề: chunk → dải trang, message mới, byte ảnh đi `document` → AGENT, cache theo trang | plan 3c (chưa có chunk) |

**Ba cái bẫy đã đo, phải mang vào thiết kế:**

- **JSON nuốt dấu `\` của LaTeX.** `gpt-4.1-nano` trả `\text` không thoát, nên `\t` thành tab; cùng
  bẫy biến `\frac`, `\neq` thành ký tự điều khiển. Repo đã có bước sửa cho chữ model trả về và một check
  canh nó (`check_the_model_text_passes_through_the_escape_repair`).
- **`gpt-4o-mini` -- model chat đang dùng -- không hợp cho ảnh**: 36 890 token cho một trang, gấp ~15
  lần các model khác, và đọc sai `ƯCLN`. Đường vision phải có model riêng, không mượn `LLM_MODEL`.
- **Gửi ảnh trang SGK ra OpenAI** là điều người dùng đã chấp nhận khi chọn GPT vision; ghi ra để plan
  nối đường không phải hỏi lại, nhưng cũng không quên nó.

## Paddle chưa có seam, và lỗ đã rộng ba file

Ghi ngày 10/10/2026, từ review Task 4 của plan 3a.

`services/document/AGENTS.md` nói hai SDK sync mỗi cái đúng một module được import, và
`check_only_one_module_per_service_talks_to_a_sync_sdk` canh đúng hai cái: `minio` và `pymupdf`.
Docstring của chính check ấy viết *"PyMuPDF cùng hình dạng và **gắt hơn một chút**: nó sync và
CPU-bound, còn arq chạy tới `max_jobs` job đồng thời"*.

**Paddle khớp từng chữ với mô tả đó, và nặng hơn nhiều.** `pymupdf` dựng một trang mất mili giây;
`LayoutReader.read` đo được **3,6–5,3 giây một trang**, và đường OCR đầy đủ mất hơn trăm giây. Hiện
`paddleocr` được import ở **hai** module (`ocr/layout.py`, `ocr/textline.py`; `ocr/formula.py` đã xoá
15/10/2026), và
trong cả `services/document/src/document/ocr/` **không có một `asyncio.to_thread` nào**.

| Việc | Cái gì đang chặn |
| --- | --- |
| Mở seam thứ ba cho `paddle`/`paddleocr`, hoặc dựng một `ocr/engine.py` làm cửa duy nhất | **Tier 2: chọn hình dạng (danh sách ba file hay một cửa ocr/engine.py) là quyết định** (plan `backlog-tier-1`, pha 4). Chưa quyết hình dạng. Danh sách ba file giữ được luật grep được nhưng phá câu *"đúng một module"*; một cửa duy nhất giữ câu ấy nhưng thêm một lớp gián tiếp cho ba model không liên quan nhau |
| Bọc đường OCR trong `asyncio.to_thread` | **Chờ OCR theo lô** (mục *việc còn lại của plan 3b* cuối file). Plan 3a cố ý chưa nối đường job nào, nên hôm nay chưa có event loop nào để chặn. Việc này sinh ra cùng lúc với job per-trang |

Chưa đau hôm nay vì bộ đo chạy đồng bộ trong một script. Nó đau đúng vào ngày đầu tiên có một
worker gọi nó.

## PP-DocLayout mù với trang mục lục, và không gì báo động

Ghi ngày 10/10/2026, từ review Task 4. Đây là **tin xấu nhất cho plan 3c** (dựng cây; trước 11/10/2026 gọi là 3b), không phải cho 3a.

Trên trang mục lục của *Kết nối tri thức Lớp 6 tập 1* -- sáu khung màu, khoảng sáu mươi mục --
PP-DocLayout trả về **đúng một hộp**: số trang. Không phải lỗi ngưỡng; đó là đầu ra thô. Cùng kiểu
mất mát ở vài chỗ khác: hai khung vở ở trang 46, ngôi nhà hồng ở trang 40, và trang 2 chỉ ra ba hộp.

Đúng trang mà bước dựng mục lục cần nhất thì lại là trang model đọc tệ nhất.

| Việc | Cái gì đang chặn |
| --- | --- |
| Một tín hiệu *"trang này gần như rỗng mà nó không trắng"* | Chưa quyết đo bằng gì. Đếm khối thì một trang bìa thật cũng ít khối; đo lượng mực trên ảnh thì cần một phép đo mới. Hôm nay `logger.info` in `found 1 boxes, kept 1` rồi đi tiếp, và bộ đo sẽ chấm trang ấy gần 0 điểm mà không ai biết đó là lỗi **recall của layout** chứ không phải lỗi đọc chữ |
| Một đường đọc mục lục không qua PP-DocLayout | Chờ số của bộ đo. Nếu mục lục in là thứ duy nhất model mù, nó có thể được xử riêng -- nhưng ADR-27 đã chốt là **không tin mục lục của tài liệu**, nên giá trị của việc ấy chưa rõ |

Hai điều này không chặn plan 3a: cổng của 3a là *đọc đúng tới đâu*, và một trang model không thấy
gì vẫn là một con số thật trong bảng. Chúng chặn 3c, nơi cây mục lục được dựng.

## Nợ của plan 3b — kho nội dung và OCR theo lô

Ghi ngày 11/10/2026. Mục này từng mang tên *"OCR theo lô cho PDF scan — việc còn lại của plan 3b"*,
khi plan ấy đóng sớm sau Task 2. Plan được **mở lại** cùng ngày và Task 3 đã làm xong
(`completed/2026-10-11-mongo-content-store-plan.md`): PDF scan giờ đi đường OCR theo lô, có tiến độ,
và về `ready`. Còn lại là nợ.

14/10/2026 (`2026-10-14-document-debts-and-comment-codes-plan.md`): năm dòng đã làm và đã gỡ -- chip
nói *đang đọc x/y trang*, lô chạy lại bỏ trang đã có, `pages_read` không lùi, ghi trang theo lô,
lần thử cuối gửi `FAILED`.

| Việc | Ghi chú |
| --- | --- |
| **Nhiều cuốn scan cùng lúc bị đọc ra *xử lý hỏng* cùng lúc.** Worker `document` chạy `max_jobs = 1`, lô kế của mỗi cuốn xếp cuối queue, nên `k` cuốn đọc xen nhau và khoảng giữa hai tiếng báo tiến độ của một cuốn là chừng `k` × 45 s | Vượt ngưỡng 300 s từ `k` ≈ 7 (≈ 4 với trang dày chữ). Một lần dò tệp có chữ cũng chờ chừng ấy. Hướng: đo *đứng quá lâu* theo nhịp sống của worker chứ không theo tiến độ từng cuốn, hoặc cho chuỗi lô đầu tiên chạy hết trước (FIFO theo cuốn) và báo tiến độ `0` lúc xếp hàng. Phát hiện ở review Task 3 |
| Id cố định của lô (`ocr:<doc>:<first>`) chỉ chặn chuỗi trùng với **một** process `document` | Chạy hai process thì một lần chạy lại có thể đẻ chuỗi thứ hai và `begin` xoá trang của chuỗi kia |
| **PDF lai qua cổng 10%** (vd. 40/400 trang có lớp chữ mỏng) ra `READY` / `text_layer` với 360 trang rỗng, không bao giờ đi OCR | 3c sẽ dựng cây trên bản thô thủng. Hướng: trang dưới `_MIN_CHARS_PER_PAGE` đi OCR -- cần một bản scan có lớp OCR mỏng thật để đo |
| **Xoá bản thô khi giáo viên xoá tài liệu**; và bản thô mồ côi khi kho ghi xong mà `_hand_back` hỏng hết lượt thử | BE không giữ khoá Mongo (D1). Có thể là một task `document` nhận lệnh xoá |
| Một trang đơn lẻ OCR quá 120 s vẫn chạm `job_timeout` | Ngân sách 90 s của lô chỉ kiểm giữa hai trang. Chưa gặp: trang chậm nhất đo được ~12 s |

## Nợ của plan 3c — document agent, Jev và cây ba cấp

Ghi ngày 11/10/2026, cùng lượt viết plan 3c (`completed/2026-10-11-document-agent-hierarchy-plan.md`).
Số đo nằm ở `Status` của plan ấy và ở `data/results/run-6/pageindex-jev-1.13.0/`.

14/10/2026 (`2026-10-14-document-debts-and-comment-codes-plan.md`): ba dòng đã gỡ -- chip nói
*đang dựng mục lục*, token banner tách khỏi token tóm tắt, và dòng *job hỏng vì lỗi lập trình thì
chip chờ 300 s* (đã xong từ commit `b0dc342`: `index_document` bắt mọi lỗi và gửi `FAILED`).

| Việc | Ghi chú |
| --- | --- |
| **Jev chưa hơn luật trên SGK.** Ở `jev_min_confidence = 0,8` Jev thắng luật đúng một ca, và ca ấy sai; cây hiện nay gần như là cây của luật. *Sau plan 4c T4 (tiêu chí bỏ ví dụ chương, `data/results/run-67`): không ca nào -- cây Lớp 6 tập 1 là đúng cây của luật; trên Lớp 10 tập 1 Jev chắc hơn hẳn ở mục cấp 3 thật nhưng vẫn dưới 0,8 phần lớn. `usage` của Jev bằng nhau trước và sau khi đổi tiêu chí (626 495 token), tức nó chỉ đếm `state` -- con số ~1 270 token của criteria bên phải chưa kiểm được* | Lượt Jev thứ hai chờ người dùng duyệt (plan hứa báo số thật trước lượt ấy, $0,026 mỗi lượt). Thiết kế đề xuất: bỏ số khỏi `state` (`page`, `numbering` thành lời), thêm `letter_case`, `level_3` chỉ nhận một số đơn **và** viết hoa toàn bộ, rút gọn `criteria` để hạ ~1 270 token mỗi lời gọi |
| **Cây vàng chỉ có một cuốn**, và luật lẫn ngưỡng đều chỉnh trên chính cuốn ấy | Cần cây vàng của một cuốn khác (một tập khác của bộ KNTT, và một tài liệu không phải SGK) để so Jev với luật cho công bằng |
| D1 hứa *"dùng luật khi số thứ tự đi lùi"* -- chưa làm; `Numbering.value` chưa ai đọc | **Tier 3 P6 (đọc tài liệu): một bước mới của assemble, cần đo trên cây vàng** (plan `backlog-tier-1`, pha 4). Một bước trong `assemble`: tiêu đề cùng cấp mà số nhỏ hơn số trước nó thì hỏi lại luật |
| Thứ OCR không đọc ra thì không cây nào có: tên Bài 10 (trang 39), hai mục Bài 21 (trang 100–101), *Hoạt động thực hành trải nghiệm* (banner không có chữ CHƯƠNG) | Một cổng thứ hai cho luna: trang mở bài (có hộp *KHÁI NIỆM, THUẬT NGỮ*) mà không có `doc_title` -- đọc tên bài trên ảnh. Dải mục màu đỏ (*"1. HÌNH CÓ TRỤC ĐỐI XỨNG..."*) thì PP-DocLayout không thấy khối nào |
| Mẫu riêng cho bộ KNTT trong luật: watermark *"KẾT NỐI TRI THỨC"*, nhãn hoạt động, `[IL1]` cho lỗi OCR | Overfit có chủ ý cho bộ sách đang dùng; một bộ sách khác cần đo lại |
| Ba tool đọc (`list_chapters` / `get_chapter` / `get_chunk`) chưa có | Plan 5 hoặc một plan riêng. Cây và chunk đã nằm trong Mongo, có `summary` |
| `LLM_TIMEOUT_SECONDS` dùng chung với AGENT | Tách một biến riêng nếu luna hay tóm tắt cần trần khác |
| *"1.1"* là bài tập chỉ khi tài liệu đi qua OCR -- một SGK **có** text layer thì *"1.1. Cho hai tập hợp"* thành mục cấp 2 | **Tier 3 P6: cần đo trên cây vàng trước khi tin** (plan `backlog-tier-1`, pha 4). Phân biệt theo hình dạng (*"1.1."* có chấm cuối, theo sau là câu chữ thường) thay vì theo nguồn đọc |
| Một khe hẹp: lô OCR cuối của một lần đọc mới giao job dựng cây **trong lúc** job cũ còn chạy thì bị id cố định từ chối, và job cũ bỏ vì bản thô đang đọc dở | **Tier 3 P6: đổi id job dựng cây** (plan `backlog-tier-1`, pha 4). Không ai dựng cây; chip ra *xử lý hỏng* sau 300 s. Hướng: id theo `raw.started_at` thay vì theo tài liệu |
| Một đơn vị đọc dài hơn 1 500 ký tự không bị cắt, nên chunk vượt trần | **Tier 3 P6: cắt theo câu khi ghi kho** (plan `backlog-tier-1`, pha 4). Khối text layer lớn; cắt theo câu khi cần |
| `except Exception` ở bước banner và tóm tắt che cả lỗi lập trình (chỉ còn `logger.exception`) | **Tier 3 P6: đếm lần hỏng vào IndexHeader là đổi schema của kho** (plan `backlog-tier-1`, pha 4). Đếm số lần hỏng vào `IndexHeader` để thấy được từ dữ liệu |
| Lượt Jev thứ hai không chạy khi đóng plan: trên SGK Jev thuần ra 138 nút cho 91, ở ngưỡng 0,8 nó thắng luật đúng một lần và lần ấy sai -- cây hiện nay là cây của luật. *Plan 4c T4 đổi tiêu chí (bỏ ví dụ chương): Jev thuần 120 nút, thắng luật 0 lần ở 0,8; cuốn thứ hai (Lớp 10 tập 1, chưa có cây vàng) lộ `"a. Mệnh đề"` OCR thành `"2. Mệnh để"` bị Jev xếp cấp 3 -- ứng viên cho `letter_case`* | Thiết kế câu hỏi mới ($0,026 một lượt trên Lớp 6 tập 1): bỏ số khỏi state (`page` thành *đầu / giữa / cuối sách*, `numbering` thành loại nhãn bằng chữ), thêm `letter_case`, `level_3` chỉ nhận một nhãn số **và** chữ in hoa toàn bộ, criteria ngắn lại; đo lại bằng `tools/pageindex_bench`, và cần cây vàng thứ hai để luật không được chấm trên chính cuốn đã chỉnh nó |

## Test khoá lượt hỏng trên Windows vì đồng hồ 15,6 ms

Ghi ngày 12/10/2026. `test_a_turn_that_outlived_its_lock_does_not_wipe_the_next_ones`
(`services/be/tests/test_teacher_chat.py`) hỏng 4 trong 5 lần chạy cả bộ, và đôi khi qua khi chạy
riêng. **Không phải lỗi của luật khoá** -- lỗi của cách test dựng kịch bản.

Test lấy thẻ của lượt A từ `_hold_the_thread` (`datetime.now(UTC)`), rồi gọi `datetime.now(UTC)` lần
nữa để làm khoá của B. Trên Windows, Python 3.12 đọc giờ bằng `GetSystemTimeAsFileTime()`, độ phân
giải **0,015625 s**: 1 000 cặp `now()` liền nhau ra 1 000 cặp bằng nhau. Hai lần gọi rơi vào cùng
một nhịp thì khoá của B **trùng** thẻ của A, fencing `WHERE running_since = :mine` khớp, và A nhả
đúng như luật cho phép -- assert báo *"khoá của B đã bị lượt A xoá mất"*.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~Cho B một mốc chắc chắn khác A, ví dụ `b = a + timedelta(seconds=1)`~~ | **Đã làm: b = a + 1 s; test chập chờn đã biết hết chập chờn** (plan `backlog-tier-1`, pha 4). Không chặn gì. Một dòng trong test, chưa làm vì nằm ngoài lượt sửa kênh SSE |
| Cùng nguyên nhân ở code thật: hai lượt giành khoá trong cùng một nhịp 15,6 ms thì mang cùng thẻ | Chỉ xảy ra khi lượt trước đã quá hạn **và** lượt sau giành đúng nhịp ấy. Thẻ thật nên là một giá trị duy nhất (uuid, hay một bộ đếm) thay vì giờ -- đổi cột, nên đi cùng món *đồng hồ của process* ở mục khoá lượt bên trên |

## BE kẹt khi `--reload` nạp lại lúc một tab đang mở

Đo ngày 12/10/2026, trong plan 4a: `.\dev.ps1 be` chạy uvicorn `--reload` không `--reload-dir`, nên nó theo dõi thư mục đang đứng -- **cả repo** khi
chạy từ gốc như mọi lần. Sửa
một file bất kỳ -- kể cả một test của AGENT -- làm uvicorn tắt process cũ, rồi **kẹt** ở *"Waiting
for connections to close"*: kênh SSE `/api/teacher/documents/stream` của mỗi tab không bao giờ tự
đóng. BE không trả lời gì cho tới khi khởi động lại tay; màn hình giáo viên đứng ở *"Đang đọc yêu
cầu…"*. Gặp hai lần trong một buổi.

| Việc | Cái gì đang chặn |
| --- | --- |
| Cho uvicorn đóng kênh khi tắt (`timeout_graceful_shutdown`), hoặc stream tự kết thúc khi app tắt | **Tier 3: đi cùng mục BE kẹt khi --reload; sửa dev.ps1 cần plan riêng** (plan `backlog-tier-1`, pha 4). Không chặn gì. Ngoài phạm vi plan 4a. Chạy BE bằng compound PyCharm (không `--reload`) thì không gặp |

## Bày nhiều cách chia số câu khi giáo viên không thu hẹp phạm vi

Ghi ngày 12/10/2026, hậu ký ADR-27. ADR-27 đòi: giáo viên không thu hẹp phạm vi thì Kriky đưa
**nhiều** cách chia, mỗi cách tự nêu cái giá, không cách nào được đánh dấu là nên chọn, phương án do BE
dựng. Plan 4b chỉ hỏi lại bằng tên chương/bài; số câu BE tự rải theo độ dài nội dung, mỗi câu một mục.

**Đóng 15/10/2026** (ADR-29, `2026-10-15-draft-outline-plan.md`): phép rải theo độ dài thôi tồn tại.
Mọi đề đi qua một dàn ý Kriky đề xuất và BE in ra; giáo viên không chọn trong nhiều cách chia, họ sửa
thẳng một cách chia hiện rõ. Dòng dưới giữ làm lịch sử.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~BE dựng 2--3 cách chia (rải đều mọi bài · dồn vào bài dài · chỉ một bài) làm phương án `ask_clarify`~~ | Thay bằng dàn ý (ADR-29) |

## Soạn đề: lỗi lộ ra khi thử tay plan 4c T5

Ghi ngày 13/10/2026, gpt-4o-mini. Ca nào có số A/B thì đo 24 lần với bản đã commit `8b02fd7` (bản ghi
`data/results/ab-8b02fd7/`) và bản hiện tại (`data/results/run-*`); mục nào không có số thì nói ra.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Lời đáp ngắn sau câu hỏi lại làm model quên lượt trước** -- có từ trước. *"Mình muốn kiểm tra nhanh phần logarit"* → hỏi khối → *"Khối 11"*: `known` chỉ còn `grade=11`, hỏi lại môn và phạm vi. Đạt: bản cũ ~1/24 (chấm theo chữ -- bản cũ không qua được `min_choices`, vì trước T3 lựa chọn model bị bỏ hết), nay 1--5/24. Nút *"Lớp 11"*: Jev nạp thêm `lop-va-ket-qua`, model gọi `list_class` rồi nói *"không tìm thấy lớp 11"* -- gọi `list_class` ở bản cũ 22/24 (ab run-11), nay 15 và 8/24 (run-71, run-80). Lỗi cũ, nhưng từ T3 nó chỉ cách giáo viên **một cú bấm**: chính nút *"Lớp 11"* là lựa chọn model đề xuất. Cùng câu mở đầu mà đáp *"lớp 11, 10 câu"* thì 21/24 | Cần thiết kế: đổi chữ đã thua ở chính chỗ này nhiều lần (plan 4c). Hướng có thể: dựng lời đáp ngắn thành cặp *câu hỏi -- câu trả lời* trong message gửi model, hay để BE ghép giá trị nút vào mục nó trả lời |
| **Phạm vi là một bài trong chương thì đề rải khắp chương** -- có từ trước, nay nặng hơn. Chip Lớp 6 tập 1, *"Ra 6 câu về ước chung lớn nhất trong sách này"*: model khớp vào **tóm tắt** chương II rồi nêu plan `nodes=[20]`, không gọi `get_chapter`. Gọi `get_chapter` đúng chương: bản cũ 3/24, nay 0/24 (run-72, ab run-12; tệp ca tạm từng chấm `"node": 20` kiểu số nên báo nhầm bản cũ 0/24). Trên trình duyệt 6 câu rải sáu mục của chương, 2/6 về ƯCLN dù cây có bài *"Ước chung. Ước chung lớn nhất"* | Cần quyết: ép đọc `get_chapter` khi lời giáo viên không trùng label chương nào, hay đưa nhãn bài vào kết quả `list_chapters` |
| **Câu hỏi lại bày *"Chương 1/2/3"* khi không có sách**, và môn khác Toán (*"Ngữ văn"*, *"Vật lý"*) khi chưa có phạm vi (18/50, plan 4c T3) -- **hệ quả của T3**, không phải lỗi cũ: trước T3 lựa chọn model viết bị bỏ hết, nên không thành nút. Chưa đo riêng *"Chương N"* | Môn khác: chờ người dùng quyết hệ thống có hứa soạn môn khác không. *"Chương N"*: chưa đo |
| **Ngay sau `list_documents` (không chip), model hỏi lại thay vì đọc mục lục** -- hồi quy của T2b/T3, **đã chặn bằng code** trong plan 4c. Gọi `list_chapters` đúng cuốn: bản cũ 17 rồi 10/24 (ab run-14, run-15; nhiễu lớn), bản stage 4/24 (ab-staged run-3), trước luật 1--4/24 (run-83, run-87); sau `_misfiled_read` (model nêu `ask_clarify` mà điền `list_chapters` của một tài liệu trong danh sách -- 16/24 ở run-88) 17/24 (run-90) và 22/24 (run-97, ca `tai-lieu-sau-thu-vien` trong `cases.json`). Câu hỏi còn lại hỏi *"Bạn soạn theo tài liệu nào?"* cho khớp nút (`_which_book`, chỉ ngay sau danh sách); bấm tên cuốn thì code đọc mục lục (`_picked_book_first`, 24/24); đề theo tài liệu chưa đọc mục lục thì đọc trước (`_toc_first`). Còn lại: giáo viên nhắc một cuốn **không có** trong thư viện thì câu của model (*"chưa có sách lớp 11…"*) bị thay bằng câu hỏi tài liệu, nút là các cuốn khác -- chưa đo; gõ một câu không trùng tên tài liệu nào thì model có thể soạn đề không sách | Hướng (i) của review T5 -- chỉ một tài liệu hợp thì đọc mục lục luôn -- là chọn hộ, chờ người dùng duyệt. Ca *cuốn không có trong thư viện* cần đo trước khi quyết `_which_book` |
| **Cây Lớp 10 tập 1** (đường thật, không có số A/B): trang mục lục thành ba chương cấp 1, *"Chương IV VECTƠ"* phủ tr. 5--23 nuốt Chương I; tiêu đề OCR rác ở mở đầu chương; 2/5 cổng banner; Bài 6 lên cấp 1; số trang in đọc nhầm (*"tr. 74--722"*). **Hậu quả thấy được**, thử tay T5: *"Lấy cuốn Toán 10 mình mới tải lên, ra 8 câu phần vectơ"* → model chọn đúng nút *"Chương IV. VECTƠ"*, nhưng nút ấy là nội dung Chương I -- cả 8 câu bám mục *mệnh đề, tập hợp* (node 8--16) | Gốc ở OCR chữ trang trí và cổng banner (plan 3c); cần cây vàng thứ hai để đo |

## Còn treo khi đóng plan 4c

Ghi ngày 13/10/2026, khi đóng `2026-10-12-unbiased-model-text-plan.md`. Mỗi dòng chờ người dùng
quyết, không phải lỗi đã biết cách sửa.

Người dùng quyết ngày 14/10/2026 (`2026-10-14-document-debts-and-comment-codes-plan.md`): năm dòng
đã gỡ -- đọc mục lục khi chỉ một tài liệu hợp **giữ nguyên** (agent quyết, kể cả khi nó hỏi lại);
luật mã trong comment, tên cache `ocr_bench`, thẻ hỏi lại giữ chữ ô chính, Figma theo code đã làm.

| Việc | Cái gì đang chặn |
| --- | --- |
| **BE tự kiểm "đã đọc mục lục"** trước khi mở đề theo tài liệu. ADR-27 (đoạn thêm từ plan 4c) chỉ thi hành ở AGENT (`propose._toc_first`, `_picked_book_first`); BE vẫn nhận `nodes` model bịa nếu một đề nghị đi vòng qua `_choose` -- hiện chưa đường nào làm thế | Người dùng 14/10/2026: **chưa làm** khi chưa có lỗi thật -- lưới ở AGENT đủ cho tới khi có một đề nghị đi vòng qua `_choose` |

## Lộ ra khi làm plan ngân hàng câu hỏi

Ghi ngày 13/10/2026, trong `2026-10-13-question-bank-write-path-plan.md`. Một lỗi có từ trước, một lỗi lộ ra cùng route xoá câu (gốc của nó -- `fire` không khoá hàng đề -- cũng có từ trước); cả hai nằm ngoài
phạm vi plan ấy, chờ người dùng quyết có sửa không.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~**Lần `_owned` thứ hai của route duyệt -- và của route xoá câu, cùng khuôn -- không đọc lại state** (`teacher_routes.py`, ngay sau `harvest`); lần `assert_editable` thứ hai của route xoá vì thế kiểm trên state cũ. Comment nói *"đọc lại cũng là đọc lại sự thật"*, nhưng session để `expire_on_commit=False` và câu `SELECT … FOR UPDATE` không có `populate_existing`: hàng bị khoá, còn object trả về vẫn là bản trong identity map. Review đo được bằng probe: phiên khác đổi state rồi commit, lần đọc lại vẫn thấy state cũ. Khe chỉ mở trong lúc `harvest` vừa commit: hai lần duyệt chạy đua ghi hai bước biên bản; duyệt và phát hành chen nhau có thể kéo `PUBLISHED → APPROVED` đi vòng qua `withdraw`. `question_bank.file_approved` đã tự đọc lại câu bằng `populate_existing` nên ngân hàng không chép bản cũ~~ | **Đã làm: `_owned` khoá hàng với `populate_existing`, lần đọc sau đọc lại từ database; test hai session** (plan `backlog-tier-1`, pha 3). Sửa là một dòng (`populate_existing` trong `_owned` khi `lock=True`), chữa cả hai route -- chờ người dùng duyệt vì đụng mọi route dùng `_owned` |
| ~~**Xoá câu đua với *"soạn thêm"* từ chat.** `drafting.fire` không khoá hàng đề (`FOR UPDATE`). Nếu `fire` chèn một ô mới sau khi route xoá đã chọn các ô cần dồn, đề có một lỗ số; tệ hơn, route xoá trừ `brief.question_count` từ con số `fire` vừa ghi, rồi `harvest` coi ô mới là cũ và xoá nó. Khe rất hẹp: giáo viên phải bấm Xoá trên panel đúng lúc một lượt chat đang mở job~~ | **Đã làm: `fire` khoá Assessment và DraftBrief (`with_for_update`, `populate_existing`)** (plan `backlog-tier-1`, pha 3). Cho `fire` khoá hàng đề như các route ghi; chờ người dùng duyệt vì đụng đường soạn đề |

**Hoãn có chủ ý** (người dùng chốt phạm vi *chỉ đường ghi*):

| Việc | Cái gì đang chặn |
| --- | --- |
| **Đường đọc ngân hàng**: tool để Kriky rút câu từ ngân hàng khi soạn đề, và câu kết *"8 câu lấy từ ngân hàng, 2 câu tôi soạn thêm"* của artboard 5 | Một plan riêng. Cần quyết cách chọn câu (theo môn, khối, mục tiêu, phạm vi) và cách hỏi lại giáo viên về nguồn (ADR-05: không đánh dấu lựa chọn nào là nên chọn) |
| **Câu lấy từ ngân hàng sang đề mới không được sinh bản trùng khi duyệt** (ADR-28, Hệ quả). `file_approved` hôm nay chép **mọi** câu của đề, khoá theo `question_id`; một câu chép từ ngân hàng sang là một `Question` mới, nên sẽ thành một dòng mới | Cần một cột nguồn trên `Question` (trỏ về `BankQuestion`) -- cùng cột mà chip nguồn thật cần. Làm cùng đường đọc |
| **Mục kiến thức và tài liệu chưa vào ngân hàng.** `drafting._write` không nối `DraftItem` với `Question`, nên lúc duyệt không có mục nào (nay là `outline_item`) để chép; đường đọc theo phạm vi sách sẽ cần nó | Nối `DraftItem` ↔ `Question` lúc thu hoạch, rồi chép tiêu đề mục (bền qua lần dựng lại cây) vào `BankQuestion` |
| **Chip nguồn thật trên từng câu.** Từ ADR-28 phần *đã kiểm / chưa kiểm* suy được từ trạng thái đề; phần *ngân hàng / Kriky soạn* cần cột nguồn ở dòng trên. Hôm nay chip bịa có thể in *"Lấy từ ngân hàng câu hỏi"* trên đúng câu mà hộp xoá nói *"chưa có trong ngân hàng câu hỏi"* | Người dùng dặn giữ nguyên giao diện ở plan ngân hàng; chờ quyết |
| **Sửa bản trong ngân hàng** (vòng ADR-19) và câu hỏi đi kèm: lần duyệt lại đề gốc sẽ ghi đè bản đã sửa ấy | Chưa có màn ngân hàng; quyết lúc dựng đường sửa (ADR-28, Hệ quả) |
| ~~**`docs/decisions/README.md` (*Nguồn thiết kế*) đã cũ, từ trước plan này**: ghi trang `Screen — Chat` *"mười hai artboard"*, trong khi trang nay tên `Screen — Teacher` (`12:2`) và có 16 artboard đánh số (1--15 và `3b`); số `13`--`15` bên giáo viên trùng số bên học sinh (*"13…24"*). Cùng chữ cũ ở `adr-10-pham-vi-dot-dau.md` và *"mười hai artboard"* ở `data-model.md` (*Dữ liệu mẫu*)~~ | **Đã làm: README, ADR-10 (mục thi hành), data-model.md** (plan `backlog-tier-1`, pha 4). Sửa chữ, miễn plan; chưa làm vì ngoài phạm vi plan ngân hàng |

## Lộ ra khi làm plan dàn ý đề

Ghi ngày 15/10/2026, khi đóng `2026-10-15-draft-outline-plan.md` (ADR-29). Số đo là `propose_bench`
gpt-4o-mini 6 lần/ca (`data/results/run-101`, trước `_approved_plan`) và ba lượt thử trình duyệt; chi
tiết ở mục *Status* của plan.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Plan chỉ có `create_draft` không qua cổng duyệt.** Cổng ADR-29 chỉ xét plan có `start_drafting` hay `replace_question`; thử tay lượt ba, model chép lại một plan hỏng của lượt trước và mở một **đề trống mới** cho lời xin *"soạn thêm 2 câu"* | **Chờ người dùng quyết**: chặn nó là bỏ khả năng mở đề trống bằng chat (đề trống vẫn thêm câu tay được ở panel) |
| **`tra-lop-ket-qua` tụt 6/6 → 2/6** -- hồi quy ngoài luồng dàn ý: model nêu `call_tool` không tên tool hay không tham số khi tra kết quả lớp | Chưa rõ gốc: prompt `_CORE` dài thêm việc thứ năm là nghi vấn đầu. Cần đo riêng ca ấy trên bản trước plan và bản hiện tại |
| **Dàn ý chung chung.** Thử tay: năm mục cùng ghi *"tỉ lệ thức"*, công thức thiếu hay lặp y nhau giữa các mục, nên câu 1, 3, 4 ra cùng một dạng. Dàn ý theo sách (đọc `read_section`) cụ thể hơn hẳn | Một luật prompt (*mỗi mục một kiến thức khác nhau, công thức của riêng mục*) và một ca bench chấm độ khác nhau giữa các mục -- chưa làm, cần đo trước khi tin |
| **`vuot-tran-12-cau` 0/6**: xin 12 câu thì model nêu dàn ý 10 câu thay vì nói trần 10 câu một lần | BE vẫn chặn quá 10 nên không hỏng dữ liệu; giáo viên chỉ không được nói vì sao. Sửa bằng một lời BE thêm khi tổng dàn ý thấp hơn số xin, hay luật prompt |
| **`dan-y-duyet-khong-gian` 2/6 đo trước `_approved_plan`** | Đo lại khi có lần chạy bench thật kế tiếp (không chạy riêng chỉ để đo ca này) |
| **Model nói "mình sẽ soạn dàn ý ngay" trong một `ask_clarify`** (thử tay lượt ba) và hỏi phạm vi trên sách khác khối của đề (chip Lớp 6 đính vào đoạn chat của đề lớp 7) | Lỗi thứ hai là hệ quả của chip tự đính lúc tải lên (plan 4b), không của dàn ý |
| **Mục dàn ý của câu đã bị thay vẫn nằm trong `brief.outline`** và vẫn vào `other_items` của job sau (có trần); thẻ kết quả bước thay câu dùng đầu đề *"Đã tạo đề"* | **Không sửa: để job né cả kiến thức câu giáo viên đã bỏ là vô hại; đầu đề Đã tạo đề cho bước thay câu đúng thiết kế bốn đầu đề chốt 06/10** (plan `backlog-tier-1`, pha 4). Review đợt 5 ghi nhận; không sai dữ liệu |
| ~~**`IntegrityError` ở commit đầu của `fire` cuộn lại `brief.outline`** mà ô sau vẫn trỏ mục -- cùng lỗ đã có với `question_count`~~ | **Đã làm: replace khoá đề và brief như fire, hai đường ghi đi nối nhau** (plan `backlog-tier-1`, pha 4). Review đợt 3 ghi nhận; khe hẹp (hai lần bắn cùng đề cùng lúc) |
| ~~**Dàn ý và plan bị từ chối không ghi `model_tokens`**; một lượt dàn ý không đóng câu hỏi lại đang mở trước nó (`_rows_in_play`)~~ | **Đã làm: token của lượt bị trả về cộng vào dòng ghi kế; dàn ý hay plan sau câu hỏi về dòng là câu hỏi đã qua** (plan `backlog-tier-1`, pha 4). Review đợt 3 ghi nhận |
| **Bench `be_refuses` chỉ chạy `vet_plan`**, không chạy cổng duyệt -- một plan soạn khi chưa có dàn ý vẫn được chấm là đạt nếu đủ tham số | **Tier 4: bench cần dựng lịch sử có lượt dàn ý** (plan `backlog-tier-1`, pha 4). Cần bench dựng lịch sử có lượt dàn ý; ca `dan-y-*` hiện chấm bằng hình dạng đề nghị |
| **Kriky hỏi lại dù đã đủ mục** (thử tay lượt bốn: *"soạn thêm 1 câu về cách ghi số La Mã"* → hai câu hỏi lại về khía cạnh và bài, rồi mới nêu dàn ý; bench run-98 thấy cùng kiểu ở ca đủ mục). Chữ kiến thức trong dàn ý đôi khi đuôi dấu `;` (*"Cách đọc số La Mã từ 1 đến 30;"*) | Chưa có cách sửa bằng code; luật prompt *đủ bốn mục thì nêu dàn ý* đã có. Cần đo riêng trước khi đổi prompt |
| ~~**`_document_scope` của `create_draft` đọc `nodes` *"1 2"* thành nút 12** (có từ plan 4b; `read_section` đã sửa lỗi ấy ở đợt 2)~~ | **Đã sửa 17/10/2026: _node_list dùng chung với read_section** (plan `backlog-tier-1`, pha 1). Ngoài phạm vi plan dàn ý |

## Lộ ra ở lần chạy mốc bộ ca thử tay

Ghi ngày 15/10/2026, plan `2026-10-15-manual-browser-test-cases-plan.md`. Biên bản nguyên văn:
`docs/testing/ket-qua/2026-10-15-6287fc3.md` (gpt-4o-mini). Mỗi dòng ghi case thấy nó.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~**Câu mở của lượt dàn ý chép lại một dàn ý giả** (case 03, 06, 14): model viết cả dàn ý vào `text`, BE in `text` rồi in dàn ý thật~~ | **Hết lý do** 17/10/2026 (`kriky-writes-every-word`, ADR-30): lời Kriky nay **là** cả dàn ý, BE không dựng bản thứ hai; `outline.check_message` trả lại lời nhắc câu ngoài dàn ý (*"Câu 1"* thay vì *"Câu 8"*) |
| **Nút hỏi lại không phải giá trị bấm được** (01, 08, 13): *"khối 6, 7, 8, 9"*, *"số câu từ 1 đến 10"*, *"Mình chỉ soạn 1 lần 12 câu."* (trái với trần vừa nói), *"Môn học là Lịch sử"* | `_answers` chỉ bỏ câu hỏi và tên mục trần; chưa có luật cho nút gộp cả dải giá trị |
| ~~**Mất số câu sau một lượt hỏi lại** (04): xin 5 câu, sau khi Kriky hỏi bài nào và giáo viên đáp *"cả chương luôn"*, dàn ý ra 10 câu~~ | **Đã sửa code 17/10/2026: _miscounted đối chiếu số câu giáo viên đã nói khi known trống — chờ thử tay** (plan `backlog-tier-1`, pha 1). `_miscounted` chỉ đối chiếu với `known` của chính lượt ấy, mà `known` đã mất số 5 |
| **Dàn ý không công thức, câu lệch mục** (02, 07, 08): 0/5 mục có công thức; câu 2 *"vận tốc 120 km / 2 giờ"* dưới mục tỉ lệ thức, câu 4 tỉ số đơn dưới mục dãy tỉ số | Trùng mục *"Dàn ý chung chung"* ở trên; nay có số đo trên trình duyệt |
| **Tên đề là chuỗi nhãn bài kèm trang, bị cắt** (04): *"Đề Bài 1. TẬP HỢP (tr. 5–9), CÁCH GHI SỐ TỰ NHIÊN (tr. 9–13), …, P"* | `_create_draft` đặt `Đề <topic_scope>`, mà `topic_scope` của đề theo sách là chuỗi nhãn |
| **`read_section` đọc nhầm nút** (06): xin 2 câu số La Mã, Kriky đọc nút 4 (Hệ thập phân) và dàn ý ghi `Theo: 1. HỆ THẬP PHÂN` | Model chọn nút; chưa có luật đối chiếu chủ đề với nhãn nút |
| ~~**Khối ĐÃ PHÁT HÀNH in giờ theo UTC** (10): đóng 20:00 hiện *"Vào tham gia tới hết 13:00"*, hạn chữa 22:00 hiện *"Chữa bài tới hết 15:00"*; dòng *"Mở 19:00"* cùng khối thì đúng~~ | **Đã sửa 17/10/2026: lỗi ở BE (đường đọc không có offset); FE điền khuôn bằng giờ địa phương, BE thôi gửi câu dựng sẵn** (plan `backlog-tier-1`, pha 2). Lỗi FE hiển thị; database đúng giờ |
| **Kết quả lớp dừng ở bước tra lớp** (12): *"bài kiểm tra 15 phút hàm số của 12A các em làm thế nào rồi"* → chỉ `list_class` rồi *"Lớp 12A có 3 học sinh."* | Cùng kiểu ca bench `tra-lop-ket-qua` 2/6; log cho thấy model tự chọn `say`, không phải lùi về mock |
| **Tệp đang xử lý thì Kriky nói "chưa thấy tài liệu"** (13) thay vì nói tệp đang được đọc và nhờ chờ | Prompt có dòng *đang xử lý*; model không theo |

**Đọc ra từ code khi viết case, lần chạy này chưa gặp** (chờ thấy trên trình duyệt):

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~Plan soạn model tự nêu ngay sau một lời **xin sửa** dàn ý vẫn qua cổng, với dàn ý cũ (cổng chỉ đòi dàn ý ở lượt ngay trước)~~ | **Đã làm, mức nhắc lại: `_PlanOverRevision` trả plan về model một lần; lần hai vẫn hỏng thì plan đi qua -- chặn cứng cần BE đọc lời đồng ý (Tier 2 câu 5)** (plan `backlog-tier-1`, pha 3). Case 03, 07 đều ra bản 2 đúng, nên chưa thấy |
| ~~`list_assessment` không lọc bản phát hành đã thu hồi: sau khi hoàn tác ở case 10, 12A sẽ có hai đề~~ | **Đã sửa 17/10/2026: lọc recalled_at** (plan `backlog-tier-1`, pha 1). Thứ tự chạy đã đưa 11, 12 lên trước 09–10 để tránh |
| ~~Lý do của bước `✕` in thẳng `reason` / `error`, có thể lộ tên tool (luật 7)~~ | **Đã làm: lời từ chối mang thêm `said` cho giáo viên, FE in `said` trước; mới phủ các chỗ từ chối của `teacher_tools`** (plan `backlog-tier-1`, pha 3). Lần chạy này không có bước `✕` nào |
| ~~Chữ *"sách"* trong lời phủ định (*"ko cần sách"*) vẫn mở thư viện (`_BOOK_WORDS`)~~ | **Đã làm: `_NO_BOOK` bỏ cụm phủ định (không/ko/k/hok) trước khi dò chữ sách** (plan `backlog-tier-1`, pha 3). Case 02, 08 đã bỏ cụm ấy; giáo viên thật vẫn có thể gõ |

## Lộ ra khi chạy bộ ca thử tay trên Claude Haiku 5.5

Ghi ngày 16/10/2026, plan `2026-10-16-claude-provider-option-plan.md`. Biên bản:
`docs/testing/ket-qua/2026-10-16-d6c82d4-claude-haiku-5-5.md`, đặt cạnh mốc gpt-4o-mini. Mỗi dòng
ghi case thấy nó.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~**Haiku để trống `known` từ lượt thứ hai** (03, 04, 07): dàn ý lưu `brief` rỗng, nên *"oke"* lùi về plan của model thay vì plan dựng từ dàn ý (`_approved_plan`), và `_miscounted` không còn gì để so~~ | **Đã sửa code 17/10/2026: BE lấp brief rỗng từ dàn ý trước — chờ thử tay** (plan `backlog-tier-1`, pha 1). Chưa sửa. Hướng: dàn ý mới mang `brief` của dàn ý trước khi `known` rỗng, hoặc BE ghi `brief` từ `create_draft` đầu tiên của đoạn chat |
| ~~**Tool soạn câu trả sai hình dạng rồi câu mock vào đề** (05, 1/24 job): thiếu `options`, `methods` là chuỗi JSON; `write_draft_question` lùi về câu soạn sẵn (*"Giới hạn của (x² − 1)/(x − 1)…"*), câu ấy thay câu 3 của đề lớp 7 và bước báo *"đã thay câu 3"*~~ | **Đã sửa 17/10/2026: sai hình dạng thành lời phàn nàn cho model viết lại; hết lượt thì job hỏng, BE hỏi lại có trần, không câu soạn sẵn nào vào đề — chờ thử tay** (plan `backlog-tier-1`, pha 1). Hai việc: đường ép tool của Claude chưa `strict`; và lùi về mock khi model thật hỏng là đưa một câu lạc đề vào đề thật — với mọi provider. **Người dùng chốt 17/10/2026: để backlog, chưa sửa; cùng ngày gỡ hoãn — làm ở plan `2026-10-17-backlog-tier-1-plan.md`.** Hướng sửa khi tới lượt: tool `strict`, bỏ đường lùi về câu soạn sẵn trong `write_draft_question` — ô hỏng thì báo hỏng (`last_fault`), không thay bằng câu khác |
| **Hai câu cùng mục trùng nhau** (02, 06, 07): job bám ví dụ trong `formulas`, bỏ lời dặn *"khác cách hỏi hoặc số liệu"*; `banned_stems` chỉ bắt chữ trùng y | Chưa sửa. Mốc gpt-4o-mini không thấy vì dàn ý của nó ít khi gộp câu vào một mục |
| **Dàn ý một mục cho cả đề** (01, 03, 07, 08, 13): `Câu 1–N` một mục | Đúng `outline.validate`; chưa có luật về số mục |
| ~~**`_read_before_outline` để lọt dàn ý đọc dở** (04): đọc phần 3/5 xong, dàn ý chỉ trỏ nút phần 1–2, nên không giao nút phần vừa đọc và AGENT thôi bắt đọc tiếp~~ | **Đã làm: lấy hợp mọi nút đã đọc trong lượt** (plan `backlog-tier-1`, pha 3). Điều kiện *"dàn ý trỏ vào phạm vi ấy"* so với phần **cuối**, không với cả phạm vi đã gọi |
| **Hỏi lại hai lần với tệp scan một trang, một `get_chapter` sai id tài liệu** (13) | Chưa sửa |
| **Tóm tắt nút cây mở bằng "Phần này"** (mục lục SGK dựng trên Haiku) | Prompt tóm tắt cấm; Haiku không theo |

## Lộ ra khi thử tay plan lời Kriky do model viết

Ghi ngày 17/10/2026, plan `2026-10-17-kriky-writes-every-word-plan.md`. Biên bản:
`docs/testing/ket-qua/2026-10-17-02ba28a-claude-haiku-5-5.md`. Bốn lỗi sửa ngay trong buổi (160 ký tự
của `learning_objective`, thẻ hỏi lại dính chữ, plan bị từ chối lặp lại, số node trong lời dàn ý) không
ghi ở đây.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~**Câu mock vào đề nay 3/21 job** (02, 06, 07) — dòng *"Tool soạn câu trả sai hình dạng"* ở trên, tần suất tăng từ 1/24~~ | **Đã sửa cùng dòng trên — chờ thử tay** (plan `backlog-tier-1`, pha 1). Như dòng trên. Đây là lỗi nặng nhất của lần chạy: ba trên năm ca có soạn câu không đạt vì nó |
| **Dàn ý sửa không tách mục gộp** (03): sửa câu 3 của mục `Câu 3–4` thì câu 4 thành cùng dạng | Chưa có luật; `_right_purpose` không biết câu nào trong mục bị đổi |
| ~~**Lời đồng ý không thành plan khi `brief` rỗng, và model bịa một nút "xác nhận soạn đề"** (04, lần chạy dở): lời ấy *đáp* dàn ý, nên lượt sau BE chặn mọi plan soạn vì *"chưa thấy dàn ý"*~~ | **Đã sửa code cùng dòng trên — chờ thử tay** (plan `backlog-tier-1`, pha 1). Gốc là dòng *"Haiku để trống `known`"* ở trên |
| ~~**BE trả dàn ý về năm lần vì công thức sai khuôn `$…$`** (04, lượt chạy lại): mỗi lần một lời gọi model với ngữ cảnh lớn dần~~ | **Đã làm: cùng lý do hai lần liền thì dừng, thông báo `OUTLINE_REFUSED`** (plan `backlog-tier-1`, pha 3). Khuôn `outline.validate` đúng; chưa có dừng sớm như với plan bị từ chối lặp lại |
| **Tên đoạn chat chép lời dặn**: *"Soạn đề toán lớp 6 chương 1 (từ chối? không) — tiêu đề: Soạn"* | `naming.py` trên Haiku; chưa đo lại |
| **"Cả chương" mà chỉ đọc một phần chương** (04): `read_section` với `nodes` 1, 3, 6, 17 do model chọn, bỏ bốn bài, mà lời dàn ý vẫn nói *"lấy từ bài 1 đến thứ tự thực hiện các phép tính"* | Model chọn nút; `_read_before_outline` chỉ đòi đọc hết phạm vi **đã gọi**, không đối chiếu với phạm vi giáo viên nói |

## Lộ ra khi thử tay plan tên đề và hỏi nhiều câu

Ghi ngày 17/10/2026, plan `2026-10-17-assessment-title-and-multi-question-plan.md`. Biên bản:
`docs/testing/ket-qua/2026-10-17-e8f7f9d-claude-haiku-5-5.md`. Thẻ hỏi lại thiếu avatar Kriky đã sửa
trong buổi, không ghi ở đây.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Nút của câu hỏi phạm vi là *loại* phạm vi** (01): *"Một chương đang học"*, *"Một chủ đề cụ thể"* — không bấm được thành một phạm vi | `_answers` bỏ tên mục và câu hỏi, không nhận ra một *loại*; luật skill chưa nói nút phạm vi phải là tên một phần kiến thức |
| ~~**Hai ô cùng một mục lấy cùng một bài từ ngân hàng** (02): câu 3 và 4 đều $\frac{x}{6}=\frac{4}{9}$, chỉ khác chữ~~ | **Đã sửa phần lưới 17/10/2026: harvest bắt câu cùng biểu thức có số liệu; gốc không phải ngân hàng mà là model viết hai câu gần trùng (chip ngân hàng là chữ bịa)** (plan `backlog-tier-1`, pha 1). Đường lấy câu ngân hàng không loại câu đã dùng trong đề; lưới *"đề trùng một câu đã có"* chỉ chặn câu model viết |
| **Lời dàn ý gộp bài nguồn ở cuối** (04) thay vì nêu theo từng mục | ADR-30 chỉ đối chiếu nhẹ lời dàn ý; `source_nodes` từng mục vẫn đúng, chỉ chữ không nói |
| **Phương án rác `$4\,volume$`** (04, câu 3) do job soạn câu viết, và đáp án đánh dấu theo đó sai | Không lưới nào soi chữ không phải toán trong phương án số |
| **Tên đoạn chat là lời trợ lý** (04): *"Bạn gửi kèm sách hoặc chụp các trang chương 1 Toán 6 giúp mì…"* | Cùng gốc với dòng *"Tên đoạn chat chép lời dặn"* ở trên (`naming.py` trên Haiku) |
| ~~**Tên giáo viên gõ bị cụt giữa từ ở 60** (15): *"…cách ghi số và lũy thừ"* — `maxLength` dừng ô, chỉ bộ đếm `60/60` báo~~ | **Đã làm: dòng nhắc dưới ô khi chạm 60 (variant chạm trần)** (plan `backlog-tier-1`, pha 4). Tên hệ thống cắt ở ranh giới từ kèm `…`; ô nhập chưa nói gì khi chạm trần. Một dòng nhắc dưới ô, hay chặn `Lưu` khi chữ dán vào dài hơn |
| ~~**Tiêu đề panel bẻ dòng giữa `(tr6-` / `28)`** (04)~~ | **Đã làm: cụm trong ngoặc white-space nowrap (keepingParens)** (plan `backlog-tier-1`, pha 4). `h2` xuống dòng ở dấu gạch; cần không bẻ trong ngoặc (gạch nối không ngắt hay `white-space` cho cụm ngoặc) — đổi chữ hiển thị, nên đi cùng Figma |
| **Lời mở lượt soạn chép nguyên ví dụ trong prompt** (02, 04): *"Được, mình soạn đề ngay."* | Ví dụ nằm trong `propose._CORE`; lời model nhưng đọc như câu cố định (ADR-30). Bỏ ví dụ nguyên văn, hay cho nhiều ví dụ |
| ~~**Hàng đoạn chat bị vạch chia ngăn rail cắt ngang** (ảnh 04–15)~~ | **Đã đối chiếu artboard rail, không sửa: hàng bị cắt vì vùng cuộn tràn, đúng ý ngăn cuộn** (plan `backlog-tier-1`, pha 4). Có thể đúng ý ngăn cuộn; chưa đối chiếu artboard rail |
| ~~**Câu trả lời tự ghi chứa `·` làm tin gộp mơ hồ** (review code pha 6): *"Phạm vi: tỉ lệ thức · dãy tỉ số"*~~ | **Đã làm: merged đổi · trong chữ tự ghi thành dấu phẩy** (plan `backlog-tier-1`, pha 4). Nhẹ; chưa thấy ở lần chạy nào. Sửa: thay ` · ` trong chữ tự ghi, hay nói khuôn gộp cho model ở `_asked_back` |

## Lộ ra khi review code `/code-review high` (17/10/2026)

Phạm vi: 66 commit từ upstream, chủ yếu ADR-31 (tên đề) và ADR-32 (hỏi lại nhiều câu), sau commit
`be30d34`. Chưa chạy verifier; người dùng dặn ghi hết, chưa sửa.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~**Ô đổi tên sống sang đề khác** (`Panel.tsx:66`): effect theo `assessmentId` dọn `paper`, `erasing` nhưng không dọn `naming` — đang gõ tên đề A, mở đề B, Enter thì **B bị đổi tên**~~ | **Đã sửa 17/10/2026** (plan `backlog-tier-1`, pha 2). Không bị chặn. Dọn `naming` cùng chỗ dọn `erasing`, thêm một vitest |
| ~~**Enter gửi PATCH đổi tên nhiều lần** (`Panel.tsx:257`): phím Enter không xét `working`, chỉ nút `Lưu` khoá — hai PATCH, hai lần đọc lại đoạn chat, có thể một 409 đỏ dù đã đổi xong~~ | **Đã sửa 17/10/2026: xét working và isComposing** (plan `backlog-tier-1`, pha 2). Không bị chặn. Chặn `rename()` khi `working` |
| ~~**`clipped()` ra tên rỗng** (`titles.py:36`): `_unquoted` bóc `""` hay `“ ”` thành rỗng, `_create_draft` chỉ xét chuỗi thô — đề lưu với tên rỗng, thẻ *Đã tạo đề ""*~~ | **Đã làm: rỗng thì lùi về `default_title`** (plan `backlog-tier-1`, pha 3). Không bị chặn. Rỗng thì lùi về `default_title` |
| ~~**`_TooManyQuestions` đếm cả câu trống** (`propose.py:1769`): bốn câu, một câu trống — ba câu hợp lệ vẫn bị hỏi lại model, tốn một lượt gọi~~ | **Đã làm: chỉ đếm câu đã qua `asked()`** (plan `backlog-tier-1`, pha 3). Không bị chặn. Đếm câu đã qua `asked()` |
| ~~**Mức lựa chọn tối thiểu theo số dòng áp cho mọi câu** (`propose.py:1772`): kết quả tool gần nhất có 2 lớp thì câu hỏi tham số (*Khối*, *Số câu*) 2 nút cũng lọt, trái luật ≥ 3 nút cho tham số~~ | **Đã làm: chỉ áp cho câu về dòng, câu tham số vẫn ≥ 3** (plan `backlog-tier-1`, pha 3). Bản sửa theo review pha 6 đi quá đà. Cần phân biệt câu về dòng (lựa chọn khớp `candidates`) với câu về tham số |
| ~~**Tên đề lồng trong danh sách không đổi theo** (`teacher_chat.py:1516`): `_titled` chỉ thay `title` cấp ngoài, kết quả như `class_assessments` (`assessments: [{assessment_id, title}]`) giữ tên cũ trong lịch sử gửi AGENT. Đường lộ: hoàn tác phát hành → đổi tên → phát hành lại~~ | **Đã làm: `_named_papers`/`_titled` đệ quy vào danh sách lồng** (plan `backlog-tier-1`, pha 3). Review pha 6 cho rằng đề đã phát hành không đổi tên được; đường hoàn tác làm điều đó sai. Đi đệ quy theo `assessment_id` |
| **Phép ghép *lời mở + câu hỏi* chép ở hai nơi** (`teacher_chat.py:916` và `propose.py:1360`) | **Tier 3 P4: một hàm dùng chung trong contracts là đổi contracts, cần plan** (plan `backlog-tier-1`, pha 4). Hai bản có thể lệch; hợp đồng chỉ soi hình dạng. Một hàm dùng chung trong `contracts` |
| ~~**Lượt hỏi nhiều câu đã qua không hiện nhãn** (`Chat.tsx:45`, `aloud`): FE vẽ *"1. câu hỏi"*, model thấy *"1. nhãn: câu hỏi (lựa chọn: …)"*; tin gộp *"Khối: Khối 7 · …"* dùng nhãn mà phía trên không có, nhãn đánh số *"Khối (2)"* càng khó đối~~ | **Đã làm: aloud in kèm nhãn từng câu** (plan `backlog-tier-1`, pha 4). Đổi chữ hiển thị — đi cùng Figma (`Clarify request`, lượt đã qua) |
| **Hai dòng `# TODO: Cần xem lại` trong `propose.py` chưa stage** (dòng 58, 1573) | Không phải lỗi: ghi chú riêng của người dùng, cố ý không commit — stage bằng script bỏ hai dòng ấy. Ghi để `git add` thẳng file không lỡ tay |

## Lộ ra khi làm plan Tier 1 (17/10/2026)

Plan `2026-10-17-backlog-tier-1-plan.md`. Mỗi dòng có tier ở artifact *Backlog theo tier*. Lỗi do chính
plan sinh ra và đã sửa trong cùng pha thì không ghi ở đây.

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~**Đầu màn lượt chữa ghi *"6 câu · 29 phút"*** (`Round.tsx:122-127`): con số là thời gian **còn lại** (`ends_at` − giờ máy) mà đọc như độ dài của lượt (6 × 5 = 30) — review ảnh pha 2~~ | **Đã làm: RoundOpenOut.started_at, đầu màn in độ dài lượt** (plan `backlog-tier-1`, pha 4). Tier 1. Ghi *"còn 29 phút"* hay tính độ dài từ giờ bắt đầu; đổi chữ đi cùng Figma (artboard lượt chữa) |
| ~~**Ô tóm tắt câu phải làm lại lặp *"và"***: *"câu 1 và câu 2 và câu 3 …"*, trong khi lời chào ngay trên viết *"câu 1, câu 2, …, và câu 6"* — review ảnh pha 2~~ | **Đã làm: câu 1, câu 2 và câu 3** (plan `backlog-tier-1`, pha 4). Tier 1. Dùng chung hàm nối của lời chào |
| ~~**Dòng *"Thu hồi được tới 10:46"* vẫn in khi đã qua giờ mở** (khối ĐÃ PHÁT HÀNH), ngay trên hộp đỏ nói đã qua giờ mở — review ảnh pha 2~~ | **Đã làm: PublishedTo.recallable; qua giờ mở ghi Hết giờ thu hồi lúc …; Figma variant khoá cập nhật** (plan `backlog-tier-1`, pha 4). Tier 1. Qua `opens_at` thì ghi *"Đã qua hạn thu hồi"* hay bỏ dòng; đổi chữ đi cùng Figma |
| **Câu luật pha 1 bẻ dòng để lại *"làm."* một mình; câu luật dùng ` - `, tiêu đề dùng `—`** — review ảnh pha 2 | **Tier 2: đổi chữ câu luật chạm nguyên văn ADR-03 và bốn chỗ Figma** (plan `backlog-tier-1`, pha 4). Tier 1 hạng thấp: chữ của `publication_wording` (ADR-03, một nguồn), chỉ đáng khi đổi câu luật |
| ~~**Không lưới nào giữ `reason` khỏi tên tool hay tên tham số**: pha 3 thêm `said` cho mọi lời từ chối của `teacher_tools` đang chở tên tool/tham số (rà tay), nhưng một tool hay một lời từ chối viết sau này chỉ có `reason` thì dòng ✕ lại in chữ cho model~~ | **Đã làm: check refusal-said** (plan `backlog-tier-1`, pha 4). Tier 1 (dòng 18, pha 4). Một lưới ở `check_contract`: `reason` chứa tên tool hay khoá tham số mà không kèm `said` thì đỏ |
| ~~**Nhãn `.stat .key` co lại khi giá trị dài**: ô tóm tắt màn trợ lý gãy *"Còn phải làm / lại"*, cột giá trị lệch dòng -- review ảnh pha 4~~ | **Đã làm: `flex: none` cho nhãn** (plan `backlog-tier-1`, pha 4) |
| ~~**Hộp xác nhận phát hành nối tên lớp bằng *"và"* lặp** (`PublishSettings.tsx:755`) -- review ảnh pha 4~~ | **Đã làm: hàm `listed` dùng chung trong `api.ts`** (plan `backlog-tier-1`, pha 4) |
| ~~**Figma: dải cảnh báo câu bỏ trống (artboard 15, 22b) không viền, không in đậm số câu**, trong khi `.warn-strip` có cả hai; **variant `đã phát hành — khoá` còn câu luật cũ** và hai chip lớp vẽ thành khối đen (paint gắn biến mà giá trị dự phòng là đen) -- review ảnh pha 4~~ | **Đã làm trong Figma** (plan `backlog-tier-1`, pha 4) |
| **Lượt chữa đã hết giờ (đồng hồ 00:00) vẫn cho chọn đáp án, và hộp nộp vẫn mời *"Quay lại làm tiếp"*** -- `Round.tsx` không có trạng thái *đã dừng*; BE từ chối lưu nên lựa chọn bấm sau giờ không được tính -- review ảnh pha 4 | Tier 2: màn *lượt đã dừng* trông thế nào (khoá phương án, chỉ còn nút nộp) là việc thiết kế, cần artboard |
| **Câu luật của BE viết chưa tự nhiên**: *"có thể nộp lúc 18:01"* nên là *"nộp muộn nhất lúc 18:01"*; *"bị DỪNG"* viết hoa như hét -- review ảnh pha 4 | Tier 2 (gộp câu 17): chữ câu luật là nguyên văn ADR-03 |
| **Kriky viết *"Để bạn vừa làm"*, *"Để hiện ở"* thay cho *"Đề"*** (đoạn chat case 04, lượt hỏi tên đề) -- review ảnh pha 4 | Tier 4: lỗi chữ của model |
| ~~**`_filled_brief` lấp môn/khối/phạm vi từ dàn ý của một đề khác trong cùng đoạn chat** -- *"soạn thêm một đề mới lớp 8"* ra đề khối 7 -- review code pha 5, Nặng~~ | **Đã làm: chỉ lấy dàn ý sau lượt `plan` gần nhất** (plan `backlog-tier-1`, pha 5) |
| ~~**Hỏi lại vì dàn ý sai số câu mà không nói số đúng** (`_UncountedOutline` không hint) -- review code pha 5~~ | **Đã làm: hint *"Giáo viên xin N câu…"*** (plan `backlog-tier-1`, pha 5) |
| ~~**`_gist` tính chữ số trong `x^{2}`, `u_{10}` là số liệu** -- review code pha 5~~ | **Đã làm: bỏ cụm `^{…}`/`_{…}`; docstring ghi giới hạn** (plan `backlog-tier-1`, pha 5) |
| ~~**Panel: thao tác của đề cũ về muộn đè lên đề vừa mở** (`<Panel>` không `key`) -- review code pha 5~~ | **Đã làm: `key={openPaper}`** (plan `backlog-tier-1`, pha 5) |
| ~~**`_row_names` không nhận nhãn nút *"12A (32 học sinh)"*** -- review code pha 5~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| ~~**`_read_before_outline` gộp nút đọc của mọi phạm vi**, bắt đọc tiếp nhầm mục -- review code pha 5~~ | **Đã làm: chỉ gộp lần đọc cùng phạm vi với lần cuối** (plan `backlog-tier-1`, pha 5) |
| ~~**`_count_said` đọc *"lớp 7 câu hỏi"* thành 7, *"thêm 2 câu"* sau dàn ý thành tổng 2** -- review code pha 5~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| ~~**`_drafts_over_a_revision` coi *"không cần sửa gì"* là lời xin sửa** -- review code pha 5~~ | **Đã làm: `_NO_CHANGE`** (plan `backlog-tier-1`, pha 5) |
| ~~**`error` của vòng chạy bước chở tên tool lên dòng ✕**, check `refusal-said` không soi `error`, `teacher_chat.py`, dict có `**` -- review code pha 5~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| ~~**`recallable` chép lại luật ADR-02 mà lệch mốc** (`<` thay `<=`) -- review code pha 5~~ | **Đã làm: `may_withdraw`** (plan `backlog-tier-1`, pha 5) |
| ~~**Hai lưới mới có lỗ**: `models.Assessment(...)`, `Assessment(**f)`; `import aiohttp`, `prometheus_client`, `asyncio.start_server` -- review code pha 5~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| ~~**Docstring `handlers.py` và `harvest` nói sai đường lùi khi model hỏng** -- review code pha 5~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| ~~**Test chứng minh ít hơn điều nó nói**: lượt *mô hình bật* không phân biệt soạn câu với biến thể; vitest giờ địa phương xanh cả trên máy UTC; `fire`/`replace` khoá mà không test -- review code pha 5~~ | **Đã làm: đếm schema + stem ngoài kho; `TZ` ghim trong `vite.config.ts`; test đọc câu lệnh `FOR UPDATE`** (plan `backlog-tier-1`, pha 5) |
| ~~**Plan không trung thực** (việc 26 chưa tick, Status cũ) -- review code pha 5~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| **Lưới gần trùng báo nhầm hai câu khác ý cùng mở bằng một hàm cụ thể** (*"Cho hàm số $y=x^3-3x+2$"* đồng biến / cực đại): câu sau thử lại tới `failed` -- review code pha 5 | Tier 2: *gần trùng* nghĩa là gì (cùng gist **và** cùng phần chữ hỏi?) là quyết định |
| **Hộp nộp lượt in cứng *"câu làm đúng được 0,5 điểm"*** (`Round.tsx`): bản sao FE của `scoring.MARK_REMEDIATED` -- review code pha 5 | Tier 2: thêm một trường BE, hay bỏ dòng ấy (artboard 22b đang vẽ nó) |
| ~~**`onApproved` của panel cũ đọc lại đoạn chat cũ rồi vẽ lên đoạn chat mới** khi lời đáp về sau một cú chuyển đoạn -- review ảnh pha 5~~ | **Đã làm: bỏ lời đáp khi đoạn chat đã đổi (`hereNow`); chưa có test riêng** (plan `backlog-tier-1`, pha 5) |
| ~~**Lưới `refusal-said` không đọc chỗ điền f-string hay `a if … else b`**: tên tool trong `{step.tool_name}` lọt -- review code vòng 2~~ | **Đã làm: đọc mã nguồn chỗ điền và cả hai nhánh; test BE cho `said` của tool gọi sai lượt** (plan `backlog-tier-1`, pha 5) |
| ~~**`_NO_CHANGE` sai hai chiều**: *"không cần thay đổi gì"* vẫn bị chặn, *"không cần thêm câu hình học"* lọt -- review code vòng 2~~ | **Đã làm: động từ phải đứng cuối ý** (plan `backlog-tier-1`, pha 5) |
| ~~**`_filled_brief` lấp chéo giữa đề X (*soạn thêm*) và đề mới; mốc là mọi plan kể cả plan `create_draft` hỏng** -- review code vòng 2~~ | **Đã làm: chỉ dàn ý cùng `assessment_id`, mốc là `create_draft` thành công** (plan `backlog-tier-1`, pha 5) |
| ~~**`_BRACED_SCRIPT` làm lưới gần trùng mất bài lũy thừa có cơ số là số** ($5^{3}\cdot5^{4}$) -- review code vòng 2~~ | **Đã làm: chỉ bỏ chỉ số/số mũ của một chữ** (plan `backlog-tier-1`, pha 5) |
| ~~**Hint số câu nói *"Giáo viên xin N"* cả khi N từ `known`; `known` vẫn đối chiếu sau lời *thêm/bớt*** -- review code vòng 2~~ | **Đã làm: hint theo nguồn; `_count_revised`** (plan `backlog-tier-1`, pha 5) |
| ~~**`_read_before_outline` so phạm vi bằng chuỗi thô** (`"1, 2"` khác `"1,2"`) -- review code vòng 2~~ | **Đã làm: chuẩn hoá `nodes`** (plan `backlog-tier-1`, pha 5) |
| ~~**`http_servers_imported` báo nhầm client `aiohttp`, `self.start_server()`; sót `from asyncio import start_server`** -- review code vòng 2~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| ~~**Status của plan nằm trong commit mà vẫn ghi *chờ commit*** -- review code vòng 2~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| ~~**`onApproved`: lỗi đọc lại đoạn cũ vẫn hiện trên đoạn mới; comment `Panel` nói sai cơ chế** -- review code vòng 2~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| **Bỏ một dàn ý đề mới rồi nêu dàn ý đề mới khác, không plan nào ở giữa**: dàn ý sau vẫn mượn môn/khối/phạm vi của dàn ý trước -- review code vòng 2 | Tier 2: hai dàn ý đề mới liền nhau là *sửa* hay *đề khác* là quyết định nghĩa. Rộng hơn một chút (review code vòng 3): dàn ý đề mới B bỏ dở → *soạn thêm cho X* → dàn ý đề mới D thì D mượn của B, vì plan *soạn thêm* không tạo đề mới nên không phải mốc |
| ~~**`_count_revised` chỉ xét lời giáo viên cuối**: *"thêm 2 câu"* rồi *"câu 3 khó hơn nhé"* kéo dàn ý 7 câu về 2 -- review code vòng 3, Nặng~~ | **Đã làm: duyệt ngược tới lời đầu tiên mang con số** (plan `backlog-tier-1`, pha 5) |
| ~~**`_NO_CHANGE` quên tiểu từ cuối câu**: *"ok không cần sửa nhé"* bị giữ lại như lời xin sửa -- review code vòng 3~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| ~~**Lưới `document-opens-no-port` thu hẹp quá tay**: lọt `get_running_loop().create_server`, `prometheus_client.start_http_server` -- review code vòng 3~~ | **Đã làm: mọi đối tượng gọi trừ `self`/`cls`** (plan `backlog-tier-1`, pha 5) |
| ~~**`_NO_CHANGE` coi *"luôn"*, *"đi"* giữa câu là cuối ý**: *"sao không đổi luôn câu 3 sang tự luận?"* lọt qua như lời không xin sửa -- review code vòng 4~~ | **Đã làm: tiểu từ chỉ tính khi theo sau là cuối ý** (plan `backlog-tier-1`, pha 5) |
| ~~**Docstring `_count_revised` còn tả hành vi cũ** -- review code vòng 4~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| **`_COUNT_SAID` đọc *"2 câu cuối khó hơn nhé"* thành tổng 2** -- có từ trước, review code vòng 4 | Tier 4: lời nói về một phần của đề hay về tổng là chuyện đọc hiểu, regex không đủ; đo trên bench trước khi đổi |
| ~~**`_NO_CHANGE` vòng 4 bắt cả tiểu từ cuối câu thật phải có dấu câu theo sau**: *"không cần sửa nhé em"* bị giữ như lời xin sửa; *"không cần sửa thêm"* cũng vậy -- review code vòng 5~~ | **Đã làm: chỉ *luôn/đi* cần cuối ý; nhận hai động từ liền nhau** (plan `backlog-tier-1`, pha 5) |
| ~~**Docstring `_count_revised` không nói tới lời *soạn thêm* không con số** -- review code vòng 5~~ | **Đã làm** (plan `backlog-tier-1`, pha 5) |
| **Phân biệt *đồng ý* với *xin sửa* dàn ý bằng regex không bao giờ kín**: bốn vòng review liền (pha 5) đều ra một ca biên mới của `_NO_CHANGE`/`_REVISES` | Tier 2 câu 5 (lời đồng ý dàn ý): nút *Soạn theo dàn ý này* do BE dựng thay cho regex. Từ nay ca biên của regex này xếp vào câu 5, không vào Tier 1. Đã biết còn lọt hay còn mơ hồ: 9 câu ở `OPEN` của `tests/test_revision_words.py` (*"không đổi nhé câu 3 sang tự luận"*, *"không cần bỏ câu nào"*…); tiểu từ miền Nam chưa nhận (*ha, hen, nghen, nghe, nhỉ, á, nè*); *"sao em/lại không sửa luôn đi"* |
| ~~**`_NO_CHANGE` vòng 5 bỏ sót *"luôn"/"đi"* đứng trước tiểu từ cuối câu**: *"khỏi sửa luôn nha"* bị giữ như lời xin sửa; *"nha"* ăn đầu chữ *"nhanh"* -- review code vòng 6~~ | **Đã làm; so ~90 câu với bản trước: không câu nào từ đúng thành sai** (plan `backlog-tier-1`, pha 5) |
| ~~**`_NO_CHANGE` vòng 6 coi *"luôn cả/hết"* là cuối ý** (*"sao không bỏ luôn cả câu 3?"* lọt) và **`\b` làm hỏng tiểu từ kéo dài** (*"không cần sửa nhen/nhaa/ạạ"* bị giữ) -- review code vòng 7~~ | **Đã làm: regex viết lại theo ba hình dạng cuối ý, *"sao không …"* là lời gợi ý sửa; bộ 140 câu có nhãn ở `tests/test_revision_words.py`, sửa regex là chạy lại cả bộ** (plan `backlog-tier-1`, pha 5) |
| ~~**`thêm` ở đuôi `_NO_CHANGE` nuốt lời xin thêm câu đi liền sau** (*"không cần sửa nhé thêm 1 câu hình học"* lọt) và **lookbehind `sao` chặn cả *"không sao không cần sửa"*** -- review code vòng 8~~ | **Đã làm: *thêm* chỉ khi cũng là cuối ý; trừ *"không sao"*; bộ câu nay 147 câu** (plan `backlog-tier-1`, pha 5) |

## Lộ ra khi viết chương 7 của báo cáo

Ghi ngày 16/10/2026, plan `2026-10-16-report-service-chapter-plan.md`. Ba subagent khảo sát
`backend`, `agent`, `document`, và năm lần review đọc lại code từng câu; những thứ dưới đây là sự
thật code mà báo cáo đã tả đúng hiện trạng, hay chỗ tài liệu nói sai mà plan ấy không được sửa. Ba
mục đã có ở trên thì không ghi lại: ADR-20 ghi trạng thái cũ, nhiều cuốn scan đọc xen nhau, và
`agent/vision.py` chưa viết.

### Nội dung dọn trước đi tới người dùng mà không ai biết

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~**Câu dọn trước lọt vào đề nháp.** Mô hình hỏng khi soạn một câu thì `write_draft_question` trả câu thứ `(ordinal-1) % 6` của sáu câu Toán cố định, không theo môn hay phạm vi giáo viên xin (`agent/handlers.py:383`, `:986-993`). `DraftQuestionCompleted` không có dấu nào để `backend` nhận ra (`contracts/authoring.py:164-175`), và câu ấy đúng hình dạng nên qua phép kiểm. Chỉ cổng duyệt của giáo viên chặn nó~~ | **Đã sửa 17/10/2026: job hỏng thay vì trả câu soạn sẵn** (plan `backlog-tier-1`, pha 1). Chưa quyết: đánh dấu câu dọn trước để `backend` từ chối hay cảnh báo, hay để job hỏng hẳn thay vì trả câu. Báo cáo chương 7 tả đúng hiện trạng |
| ~~**Câu biến thể dọn trước lặp lại câu gốc.** Câu gốc không có trong kho dọn trước thì `retry_question` trả lại chính câu gốc -- cùng phương án, cùng đáp án -- chỉ thêm đuôi *"(đề thay số cho lượt N)"* (`agent/handlers.py:432-437`). `validate_retry` chỉ so đề bài đã chuẩn hoá khoảng trắng (`be/agent_gateway.py:458-463`), nên đuôi ấy đủ để lọt. Học sinh làm lại đúng câu cũ dưới một nhãn nói số đã đổi, và không cổng nào chặn: đúng điều ADR-17 cấm~~ | **Đã sửa 17/10/2026: hết biến thể thì ném, BE 503 bằng câu cho học sinh (không mất vòng); validate_retry bắt câu gốc kèm đuôi** (plan `backlog-tier-1`, pha 1). Chưa quyết, cùng câu hỏi với dòng trên. Nặng hơn dòng trên vì đi thẳng tới học sinh |
| ~~**Đề xuất dọn trước có thể là một plan thật.** `propose_next_step` hỏng thì lùi về `next_step`, và chính comment ở `agent/handlers.py:560-565` ghi rằng một lần hết giờ trên một câu *hỏi* từng ghi một đề thật vào database~~ | **Hết lý do: model hỏng thì propose_next_step trả thông báo hệ thống, không lùi về next_step (handlers.py)** (plan `backlog-tier-1`, pha 1). `_ASKS_TO_MAKE` đã siết; chưa có dấu nào báo `backend` đề xuất ấy là dọn trước |

### Lưới yếu hơn tên của nó

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~**Lượt *"mô hình bật"* của `test_no_routing_decision` không soi được ba task.** `GenericFakeChatModel` không có `with_structured_output`, nên `write_draft_question`, `generate_retry_question`, `propose_next_step` ném `NotImplementedError` rồi rơi về nội dung dọn trước. Đã chạy xác nhận ngày 16/10/2026: log `handlers.py:992`, `:1027`, `:882`~~ | **Đã làm: model giả có with_structured_output, test assert hai schema đã được xin** (plan `backlog-tier-1`, pha 4). Cần một mô hình giả dựng được đầu ra theo khuôn |
| **Check `timeout-order` không tính mô hình dự phòng** (`agent/llm.py:106-107`: mỗi lần thử có thể chạy hai mô hình nối nhau) **và số lần thử lại mặc định của SDK OpenAI** (`max_retries` không đặt) | **Tier 2: tính đủ lần thử lại của SDK thì check đỏ (3 + 20 × 3 × 3 = 183 s so với 70 s); bỏ thử lại SDK hay nới ngân sách là quyết định** (plan `backlog-tier-1`, pha 4). Không bị chặn; chưa làm |
| ~~**Không gì canh luật "`document` không mở cổng HTTP nào".** Luật ấy chỉ nằm trong `services/document/AGENTS.md` và docstring của worker. (Luật thứ hai từng ghi ở đây, *`ocr_worker` chạy một job một lúc*, thì đã có ca kiểm thử: `tests/test_ocr_worker.py:54-61`, `assert max_jobs == 1`; review lượt viết lại mục Document tìm ra)~~ | **Đã làm: check document-opens-no-port** (plan `backlog-tier-1`, pha 4). Không bị chặn; chưa làm |
| **Lời đồng ý dàn ý chỉ được đọc trong `agent`** (regex `_AGREES`, `graphs/propose.py:820-824`). `guard_drafting` chứng minh được dàn ý đã hiện ở lượt hội thoại ngay trước, không chứng minh được giáo viên đã đồng ý | Chưa quyết `backend` có cần tự đọc lời đồng ý không |

### Luật chưa ép

| Việc | Cái gì đang chặn |
| --- | --- |
| ~~**`submit_round` không kiểm giờ kết thúc của lượt hay hạn giai đoạn 2** (`be/student_routes.py:2095`), trong khi `save_round_answer` có kiểm (`:2082`). Chương 04 của báo cáo (`04:116`) hứa *"hết hạn thì dừng"*~~ | **Không phải lỗi: đúng ADR-15 (phần đã lưu trước `ends_at` được chấm); thêm test và comment** (plan `backlog-tier-1`, pha 3). Chưa làm |
| **Câu biến thể giữ cấu trúc của câu gốc (ADR-17):** ngoài các phép kiểm chung, chỉ có phép so đề bài; không gì so cấu trúc | Đã có dòng *"chưa ép"* trong `AGENTS.md`; chưa làm |
| **Đóng tab giữa một lượt hội thoại thì lượt ấy không có lời kể lại** (ADR-25) | Chưa làm |
| **Chương 04 (`04:121-123`) nói giáo viên xem được báo cáo *"giải thích chưa rõ"* của học sinh**, nhưng `backend` chỉ có đường ghi `file_report`; không api hay tool nào đọc bảng `reports` | Chưa làm |

### Tài liệu nói sai về code, ngoài phạm vi plan báo cáo

| Việc | Cái gì đang chặn |
| --- | --- |
| **ADR ghi trạng thái cũ:** ADR-15, 16, 18, 21, 27 vẫn ghi *"chưa thi hành"* hay *"chưa có ở backend"*; ADR-23:114 trỏ `propose._SYSTEM`, nay là `_CORE`; ADR-25 (sửa 10/10) định bỏ job kể lại, code vẫn chạy nó; ADR-27 nói Jev là bộ định tuyến của `document`, đã bị thay ngày 12/10; ADR-29:68 nói lời đồng ý đọc bằng mô hình, thực ra bằng regex | Cố ý hoãn, như mục *Tài liệu quyết định* ở đầu tệp: sửa một ADR là sửa lịch sử |
| ~~**`AGENTS.md`:** `services/be/AGENTS.md` nói *"clients poll once per second"* (không còn gì poll), *"`advance` is the only function"* (`withdraw` cũng đặt state, `assessment_state.py:236`), *"every path calls `assert_editable`"* (`edit_question`, `approve`, `harvest` dùng `editable()`); `AGENTS.md:16` gốc nói `agent` làm *"AI grading"*~~ | **Đã làm: DR-1 của plan backlog-tier-1** (plan `backlog-tier-1`, pha 4). Sửa `AGENTS.md` cần plan và decision record riêng |
| ~~**Docstring, comment và cấu hình nói sai về chính code:** `be/student_routes.py:1717-1723` (*"lưu rồi mới stream"*), `fe/src/api.ts:991-994`, `screens/student/Tutor.tsx:93-95` (cùng câu ấy); `agent/handlers.py:3-6` (*"mọi handler là mock"*), `worker.py:91`, `llm.py:4-5`, `graphs/__init__.py:3-6`, `graphs/propose.py:12-15`; docstring đầu `be/teacher_documents.py`; `contracts/documents.py:1` (*"Hai message"*, có năm), `:109-110`; `document/index_handlers.py:7` (*"Ba cách"* rồi kể bốn), `index/graph.py:12-14`, `content_store.py:77-83`, `probe.py:12-13`, câu ở `probe.py:195-198` không bao giờ tới giáo viên; `ocr/page.py:3-9` kể chặng theo thứ tự cũ; `pyproject.toml:65`, `.pre-commit-config.yaml:1` (số service dùng chung env), `dev.ps1:89-91` (*"BE không giữ khoá Mongo"*), `be/config.py:40` (tên check cũ), `be/teacher_routes.py:1122` (*"mỗi lớp một bộ hạn riêng"*, trái với code bên dưới), `.env.example:3`, `:20-21`~~ | **Đã làm mọi chỗ liệt kê; contracts/documents.py: hai message thành năm, DocumentProbed giao về cho ingest ghi** (plan `backlog-tier-1`, pha 4). Không bị chặn; chưa làm |
| ~~**FE nói *"`fault` có sáu giá trị"*** (`Rail.tsx:305`, `api.ts:409`); `document` phát mười câu, chưa kể câu của phép suy 300 s ở `backend`~~ | **Đã làm: bỏ con số, nói một câu cho mỗi cách hỏng** (plan `backlog-tier-1`, pha 4). Chưa làm |
| **ERD chưa vẽ**, dù điều kiện cũ trong `architecture.md` (*"khi có Postgres"*) đã đạt | Chưa quyết có cần: `data-model.md` đang nói hai mươi hai bảng bằng bảng và lời |

### Báo cáo

| Việc | Cái gì đang chặn |
| --- | --- |
| **Hình `activity-overview` ở chương 04 vượt trang 23,8 pt** (`Float too large`, có từ trước plan này) | **Việc của phiên báo cáo (docs/report), rời Tier 1** (plan `backlog-tier-1`, pha 4). Ngoài phạm vi plan chương 7 |
| **Chữ *"pha"* lệch giữa hai tài liệu:** từ điển của báo cáo dành *"pha"* cho lượt hội thoại giáo viên và *"giai đoạn"* cho bài làm học sinh, còn `architecture.md` và các ADR dùng *"pha 1/pha 2"* cho học sinh | Chưa quyết bên nào đổi |
| **Ô `ingest` của `tab:nam-service` ghi `postgres (chỉ ghi)`**, nhưng `ingest` cũng lọc theo `documents.state` khi ghi (`ingest/handlers.py:126-140`) | Chưa làm |
| **Mục *"Những chỗ đã biết là còn sai"* của `docs/report/rules.md`** chưa xử lí: bộ nhãn trạng thái, `04:116`, logo không có trong `sources.json`, newline cuối tệp và khoảng trắng cuối dòng | **Việc của phiên báo cáo (docs/report), rời Tier 1** (plan `backlog-tier-1`, pha 4). Như mục ấy ghi |

## Lộ ra khi sửa từ điển chương 3 của báo cáo

Ghi ngày 16/10/2026, plan `2026-10-16-report-dictionary-plan.md`. Plan ấy chốt **thông báo** cho
thứ `ingest` và `agent` phát lên channel, **event** cho thứ `backend` gửi xuống màn hình qua SSE, và
miễn mục từ điển cho tên riêng. Những chỗ dưới đây nằm ngoài phạm vi của nó.

| Việc | Cái gì đang chặn |
| --- | --- |
| **`docs/overview/architecture.md` còn dùng "chuông", "hích", "chở"** cho thứ phát lên channel và thứ gửi xuống qua SSE (`:15`, `:77`, `:88-89`, `:154-157`, `:334`), và "chở" theo nghĩa *một job mang gì* (`:48`, `:98`, `:104`, `:192`): đúng những chữ báo cáo vừa bỏ | Chưa quyết `architecture.md` có theo bảng chữ của báo cáo (`docs/report/rules.md` §2) không |
| **Ô `ingest` của hình `system-architecture` mang dòng phụ *"Đẩy dữ liệu bất đồng bộ"*.** Đó là nghĩa thứ ba của "đẩy" (ghi vào database), bên cạnh đẩy job lên queue và cách báo cáo cũ gọi việc gửi xuống màn hình | Hình của người dùng; chưa quyết |
| **`02:67` viết `` câu 3\` ``.** LaTeX đọc `` \` `` là lệnh dấu huyền, nên trang in ra dấu huyền chồng lên dấu phẩy ngay sau thay cho dấu phẩy trên (câu 3′) | **Việc của phiên báo cáo (docs/report), rời Tier 1** (plan `backlog-tier-1`, pha 4). Không gì chặn; chương 02 nằm ngoài phạm vi plan ấy |
| **Chữ vẽ trong các hình của người dùng chưa theo từ điển.** Chữ tiếng Anh không có mục: `upload`, `cache` (`system-architecture`), `Boundary` (`domain-context`), "Teacher review" (`activity-overview`), "Review đề" (`business-workflows`). Nặng hơn: `domain-context` và `use-case` ghi "pha 1 / pha 2" cho bài làm học sinh, trong khi từ điển dành "pha" cho lượt hội thoại của giáo viên và gọi phần của học sinh là "giai đoạn" | Hình chỉ sửa được bằng một việc riêng (`rules.md` §6); chưa quyết |
| **Tên UC-02 *"Review và phát hành đề"* có chữ tiếng Anh "Review"** mà từ điển không có mục; plan trên miễn nó như một tên use case. Đổi tên phải đổi cùng lúc bảng `tab:sau-use-case`, tiêu đề `\subsection`, các `\emph` ở chương 05, và nhãn vẽ trong `use-case` (`rules.md` §6) | Chưa quyết có đổi không |

## Lộ ra khi viết lại mục backend của chương 7

Ghi ngày 16/10/2026, plan `2026-10-16-report-backend-section-plan.md`. Một subagent debate dàn ý và
một subagent review đọc lại code từng câu; những thứ dưới đây nằm ngoài mục backend hay ngoài báo
cáo. Bốn giới hạn mà mục ấy nêu (giờ kết thúc của một lượt, cấu trúc câu biến thể, plan bị cắt khi
đóng thẻ, giáo viên chưa đọc được báo cáo) đã có ở *Luật chưa ép* phía trên nên không ghi lại.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Đoạn mở chương 07 (`07:4-7`, người dùng viết) dùng "service" lần đầu mà không in đậm, không chú thích** (`rules.md` §3); ba dòng `07:4-6` có khoảng trắng cuối dòng, `07:4` có hai dấu cách liền nhau | Phần người dùng viết; chỉ báo, không sửa |
| **Báo cáo chưa chỗ nào nói rằng chưa có đăng nhập.** `backend` xác định người gọi bằng header `X-Actor` do màn hình tự khai (`be/identity.py:1-8`, `be/config.py:53-58`); phần kiểm quyền phía sau là thật. Review đề nghị thêm thành giới hạn thứ năm của mục backend | Chưa quyết có thêm không |
| **Docstring đầu `be/content_reader.py` (`:1-6`) nói `backend` đọc đoạn chữ của tài liệu *"để job soạn câu có kiến thức của mục mình"*,** trái với `check_drafting_reads_no_document_text` (`tools/check_contract.py:483`): job soạn câu chỉ nhận mục dàn ý | Không bị chặn; chưa làm |
| ~~**`be/config.py:99` khai `job_result_ttl_seconds` mà code `backend` không dùng ở đâu.** Thời gian kết quả sống trong `redis` do `agent` đặt (`agent/worker.py:103`)~~ | **Đã làm: bỏ khỏi be/config.py; AGENT vẫn đọc** (plan `backlog-tier-1`, pha 4). Không bị chặn; chưa làm |
| **"Hàm" mang hai nghĩa trong chương 07.** Từ lượt viết lại mục Agent, phần của graph gọi là *hàm*, theo mục *Graph* của từ điển; *hàm nhận job* (chỗ worker gọi vào) cũng là "hàm". Đã ghi ở *Những chỗ đã biết là còn sai* của `rules.md` | Người dùng giữ *hàm nhận job* và sẽ tự chọn chữ khác |
| ~~**Docstring của `agent` nói sai về chính code:** `handlers.py:3-6` (*"mọi handler đều là mock, không có lời gọi model nào"*), `:125-128` (`backend` từ chối câu đóng thế — thực ra câu ấy lọt, xem *Nội dung dọn trước đi tới người dùng* ở trên), `graphs/propose.py:12-15` (*"không có loop tự check"* — có phép kiểm và một lần gọi lại), `worker.py:91-94` (*"một job là một lần gọi model"* — propose có thể gọi hai lần, cộng Jev). Review lượt viết lại mục Agent tìm ra~~ | **Đã làm** (plan `backlog-tier-1`, pha 4). Không bị chặn; chưa làm |
| ~~**Docstring của `document` cũ sau commit `d6c82d4`** (tóm tắt và đọc tên chương chọn được OpenAI hay Claude): `index/graph.py:85-86` và `index_handlers.py:49-50` vẫn viết *"khi không có khoá OpenAI"*, nay đúng ra là khi Model Provider của mô hình ấy chưa được cấu hình. Review lượt viết lại mục Document tìm ra~~ | **Đã làm** (plan `backlog-tier-1`, pha 4). Không bị chặn; chưa làm |
| ~~**Phát một mảnh chữ hỏng giữa lúc trả lời học sinh thì câu được lưu khác chữ em đã thấy.** `handlers.explain` ghi mảnh vào danh sách *trước* khi phát (`said.append` rồi `redis.publish`, `handlers.py:1062-1078`), nên khi lần phát hỏng, nhánh "hỏng giữa chừng" trả về cả mảnh chưa tới màn hình. Review lượt viết lại mục Agent tìm ra~~ | **Đã làm: phát trước rồi mới ghi; test mảnh không ra tới màn hình thì không lưu** (plan `backlog-tier-1`, pha 3). Không bị chặn; chưa làm |
