# Nợ — việc đã hoãn có chủ đích

Mỗi mục ở đây là một thứ **đã được nêu ra và cố ý chưa làm**, không phải một ý tưởng bỏ ngỏ. Ghi lại vì
một tính năng bị hoãn mà không ai ghi thì lần sau sẽ được đề xuất lại từ đầu, hoặc tệ hơn, bị tưởng là
đã có.

Mỗi mục phải trả lời được: **cái gì đang chặn nó**. Không chặn bởi gì thì nói thẳng là chưa cần.

File này khác `docs/decisions/`: ở đó là luật nghiệp vụ đã chốt và còn hiệu lực; ở đây là việc chưa làm.
Nó cũng khác mục *Còn thiếu* trong `docs/decisions/README.md`, vốn liệt kê những **luật** chưa được ghi
thành ADR, không phải những **tính năng** chưa dựng.

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

Ba mục này vì thế nằm cùng nhóm với `ReviewReason.ANOMALY`
([ADR-08](../decisions/adr-08-bon-loai-nghi-ngo.md)) và toàn bộ tính năng mastery: **cùng bị chặn bởi
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

Khái niệm này **có thật và đang chạy**: `needs_teacher_review` nằm trong contract, do
`services/be/src/be/review_policy.py` quyết định, và [ADR-07](../decisions/adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md)
ghi đủ bốn luật chọn nó. Nó không phải thứ bịa ra.

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
| Hạ bão hoà thân linh vật về `#9C7A5A` cho bản raster | Không bị chặn. Cần làm ngoài Figma |
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
| Hai tab hoặc tải lại trang giữa pha 2 | Không bị chặn. Chưa quyết vòng đếm và đồng hồ ứng xử ra sao |
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

Đây cùng nhóm với `ReviewReason.ANOMALY` và thống kê điểm: **cùng bị chặn bởi một thứ**, cùng mở khoá
khi có cơ sở dữ liệu thật. Khác biệt là ở quy mô — hai mục kia là tính năng phụ, còn đây là **toàn bộ
nửa sau của sản phẩm**.

### Câu luyện tập chưa qua cổng duyệt nào

Hiện tại trợ lí sinh câu `x'` và nó tới thẳng tay học sinh.
[ADR-05](../decisions/adr-05-ba-cong-teacher-in-the-loop.md) cổng số một nói *giáo viên duyệt đề trước
khi phát hành cho học sinh*; câu `x'` là ngoại lệ, và ADR-05 đã ghi ngoại lệ đó.

Cái giá, để lần bàn sau khỏi phải dựng lại lập luận: `x'` **được dùng để dạy lại** và **quyết định câu
gốc được 0,5 hay 0 điểm**. Nó không phải một gợi ý trôi qua như bong bóng chat. Thêm nữa,
[ADR-04](../decisions/adr-04-hai-nguon-cau-hoi.md) chốt câu Kriky soạn có hai trạng thái kiểm và giáo
viên là người chuyển — `x'` thì vĩnh viễn ở trạng thái *chưa kiểm*.

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
`confidence = 0.30` **và** `has_sufficient_evidence = False`, và `services/be/src/be/review_policy.py`
đẩy kết quả vào hàng đợi qua `INSUFFICIENT_EVIDENCE` mà không hề so ngưỡng. Gỡ mỗi điều kiện ngưỡng là
chưa đủ.

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

### Hai chỗ contract nói không còn đúng

`packages/contracts/src/contracts/messages.py` — docstring của `GradingRequested` nói Adaptive Practice
cần `learning_objective` để sinh *"a variant of the same objective"*. Theo
[ADR-17](../decisions/adr-17-ba-vong-moi-cau.md), biến thể nay giữ **cùng câu hỏi**, chặt hơn hẳn cùng
learning objective.

Cùng file, `GradingCompleted` nhận được `score = 0.5` vì trường đã là `ge=0.0, le=1.0`. Nhưng không
trường nào mang *vòng thứ mấy*, *câu gốc nào* hay *lỗi nào đã được chữa* — nên lời hứa giao diện của
[ADR-16](../decisions/adr-16-thang-diem-ba-muc.md) là hiện lý do được 0,5 hiện **chưa có nguồn dữ
liệu**.

## Diagram

| Việc | Cái gì đang chặn |
| --- | --- |
| `system-architecture.drawio` — legend tràn dưới mép trang | Không bị chặn. Ngoài phạm vi đợt sửa diagram |

Legend của file này đặt ở `y=770` cao `120` trong khi trang cao `850`, nên hai dòng cuối **nằm hoàn
toàn dưới mép** và mất khi export. Thêm một giao cắt cạnh ở vùng `be`–`redis`–`agent`, và chín node
lệch lưới 10.

Nội dung thì **không** bị mô hình hai pha làm sai: hình chỉ vẽ `fe`/`be`/`agent`/`redis`/`contracts`,
không nói gì tới pha, điểm, vòng lặp hay đồng hồ. Nhãn *"đọc kết quả rồi áp ngưỡng"* vẫn đúng, vì
[ADR-07](../decisions/adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md) ghi rõ việc gỡ ngưỡng khỏi luồng
học sinh **chưa thi hành ở đâu** — `review_policy.py` vẫn áp cho mọi kết quả.

## Duyệt lời giải

| Việc | Cái gì đang chặn |
| --- | --- |
| Ghi nhận giáo viên đã đọc lời giải của từng câu | **Chưa quyết định nghiệp vụ** — xem dưới |

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

Câu chữ của từng lượt là món nợ **mới và dễ bị bỏ sót nhất**: `GradingCompleted` hôm nay chỉ mang
điểm, nên nếu backend sinh câu biến thể rồi vứt đi, màn kết quả sẽ có một khung để in đề mà không có
đề để in. Câu biến thể phải được **lưu lại cùng lượt**, không phải sinh xong dùng một lần.

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
| Hộp xác nhận khi **bắt đầu làm bài** | Không bị chặn. Chưa dựng |
| Hộp xác nhận khi **nộp bài** | Không bị chặn. Chưa dựng |

Học sinh có **ba** cửa một chiều: bắt đầu làm bài (đồng hồ chạy và không ai dừng được), nộp bài
([ADR-14](../decisions/adr-14-hai-pha-lam-bai.md): nộp kết thúc pha 1), và bắt đầu một lượt chữa. Chỉ
cửa thứ ba có cổng — `Round gate`, đặt trên artboard 19. Hai cửa kia hiện là nút trơn.

Cửa **nộp bài** đáng có cổng nhất trong hai cái còn lại, vì dải nhảy câu đã đếm sẵn con số mà hộp xác
nhận cần đọc lại: *"còn 2 câu chưa trả lời"*. Đó là cùng nguyên tắc
[ADR-02](../decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md) dùng cho hộp xác nhận phát hành — đọc lại
giá trị thật thay vì một con số ghi cứng.

## Model thật — hai lỗ hổng mở cùng lúc với nó

Ghi từ [plan 2026-09-29](active/2026-09-29-agent-real-model-plan.md), đợt đưa AGENT lên model thật.
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
