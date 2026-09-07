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
