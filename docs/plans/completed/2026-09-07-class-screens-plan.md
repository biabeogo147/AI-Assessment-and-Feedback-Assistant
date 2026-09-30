# Màn hình vật thể 1/3 — Danh sách lớp học

## Goal

Dựng bộ khung màn hình vật thể, hai artboard cho lớp học, và ADR chốt quyền sở hữu lớp/tài khoản.

## Bối cảnh

Rail vừa được thêm ba điểm đến (`Danh sách lớp học`, `Các bài kiểm tra`, `Ngân hàng câu hỏi`); bấm vào
chúng chưa dẫn tới đâu. Ba màn hình này là **loại màn hình mới**: chúng quản lý vật thể chứ không phải
hội thoại. Tám artboard hiện có đều là bề mặt chat, nên chưa có component nào phục vụ dạng này.

Làm lớp học trước vì quyền sở hữu lớp ràng buộc hai màn còn lại — phát hành đề phải chọn lớp (ADR-02),
nên lớp phải có nghĩa trước — và vì đây là màn hình ít hành động không đảo ngược nhất, nên dựng khung
chung ở đây rẻ hơn dựng ở màn đề.

## Files

- Figma `mOe2ZmrqOq1Uix45v6PNGD`: `Page header` (`175:763`), `Class row` (`178:19`),
  `Student row` (`179:15`), hai variant mới của `Empty state` (`179:16`, `179:19`),
  artboard `9 · Danh sách lớp học` (`180:753`), artboard `10 · Chi tiết lớp` (`183:874`)
- `docs/decisions/adr-13-lop-va-tai-khoan-hoc-sinh.md` — mới
- `docs/decisions/README.md` — bảng và mục *Còn thiếu*
- `docs/overview/project-overview.md` — glossary `Class` và `Document`

## Ordered Tasks

- [x] Đọc token `Density`/Teacher và `Space` để lấy đúng padding/gap, không đặt số tuỳ ý.
- [x] Dựng `Page header`, `Class row`, `Student row` kèm mô tả.
- [x] Thêm hai variant `Empty state`.
- [x] Dựng artboard `9 · Danh sách lớp học` và `10 · Chi tiết lớp`.
- [x] Đặt đúng một điểm sáng trong rail trên cả hai artboard.
- [x] Viết ADR-13; cập nhật index và glossary.
- [x] Chạy `.\dev.ps1 check`; kiểm link Markdown; kiểm LF; kiểm `AGENTS.md` vẫn 170 dòng.
- [x] Gọi 1 subagent review.
- [x] Sửa theo phát hiện, hoặc phản bác có lý do.
- [x] Xếp lại trang `Components`: năm cặp component chồng lên nhau sau khi các set nở thêm variant.

## Bổ sung sau khi review: màn hình kết quả bài kiểm tra

Artboard `11 · Kết quả bài kiểm tra trong lớp` (`205:1000`), vào từ một hàng của bảng đề trên artboard
10. Phạm vi là **một đề trong một lớp**, nên nó không vướng câu hỏi *đề hay cặp đề×lớp* mà plan
`Các bài kiểm tra` phải trả lời.

Component mới: `Stat tile` (`203:10`), `Score row` (`204:27`), và ghi chú `Bảng sắp xếp được`
(`210:1164`).

Bổ sung tiếp: `Assistant thinking` (`222:59`) cho khoảnh khắc giữa lúc người dùng gửi và lúc có chữ
đầu tiên, đặt trên artboard `2 · Kèm tài liệu, giới hạn phạm vi`. Avatar theo lượt sau đó được gom thành component
set `Kriky state` (`234:1180`) — xem decision record bên dưới. Mô tả `Agent working` (`10:22`) được
sửa lại cho đúng: hai variant của nó đi hai đường khác nhau, `đang chạy` → `Thinking`, `đang nghĩ` →
`Assistant thinking`.

## Decision Records

### Decision: `Table head` Is A Pattern, Not A Component

options considered: dựng `Table head` thành component set dùng chung cho cả ba màn hình, với nhãn cột
là text property; dựng nó lại ở từng màn hình như một frame thường, theo một nhịp cột được ghi thành
luật trong mô tả `Class row`.

selected option: frame thường, nhịp cột ghi trong mô tả component.

reason: chiều rộng cột của tiêu đề **phải khớp tuyệt đối** với chiều rộng cột của hàng, nếu không bảng
lệch. Một component tiêu đề dùng chung buộc phải cho ghi đè chiều rộng ở từng instance — mà ghi đè
chiều rộng trong instance chính là thứ dễ trôi nhất và không có gì canh. Ba màn hình có ba bộ cột khác
hẳn nhau, nên "dùng chung" ở đây chỉ là dùng chung *nhịp*, không phải dùng chung *node*. Ghi nhịp đó
thành luật trong mô tả `Class row` giữ được sự nhất quán mà không giả vờ có một thứ tái sử dụng được.

### Decision: Badge Là Thuộc Tính Của Điểm Đến, Không Phải Trạng Thái

options considered: giữ `Trạng thái` ba giá trị (`mặc định | badge | đang chọn`) và thêm ba điểm đến
mới thành 12 variant; tách badge thành boolean + text property, `Trạng thái` còn hai giá trị, 8 variant.

selected option: badge là thuộc tính.

reason: mô hình cũ **không diễn tả được "đang chọn mà vẫn có badge"** — và nó tự mâu thuẫn, vì variant
`đang chọn` đã chứa sẵn một badge. Mâu thuẫn đó nổ ngay khi giáo viên đứng ở Bảng theo dõi. Tách ra còn
giảm 12 variant xuống 8, và cho phép mọi dòng cao đúng 40 thay vì nhảy 39→40 khi badge xuất hiện.

### Decision: Trạng Thái Tài Khoản Phân Biệt Bằng Tương Phản, Không Bằng Màu

options considered: tô *"chưa đăng nhập lần nào"* bằng `state/needs-human`; dùng `state/processing`;
không dùng màu ngữ nghĩa nào, phân biệt bằng độ đậm của chữ.

selected option: phân biệt bằng độ đậm.

reason: ADR-12 chốt hổ phách nghĩa là **cần giáo viên làm gì đó**. Một em chưa đăng nhập lần nào không
phải việc phải xử lý gấp — tô hổ phách là nói sai, và nó làm chìm những chỗ hổ phách thật. `processing`
cũng sai vì em đó không "đang chạy" gì cả. Nhưng đây vẫn là thứ giáo viên cần quét mắt tìm (em nào có
thể chưa nhận được mật khẩu), nên nó được làm nổi bằng `ink/default` trong khi trạng thái bình thường
lùi về `ink/faint`. Tương phản, không phải sắc độ.

### Decision: Không Thêm Lớp Mờ Ở Đáy Vùng Cuộn

options considered: thêm một gradient mờ ở đáy `scroll` để báo còn nội dung; để nguyên dòng bị cắt.

selected option: để nguyên.

reason: gradient không bind được vào biến màu qua Plugin API, nên nó buộc phải dùng màu thô — vi phạm
đúng luật *"mọi màu lấy từ biến"* mà chính plan này đặt ra. Dòng bị cắt ngang đã là tín hiệu còn-cuộn
được mà mọi người đều đọc quen. Không đáng đổi một luật lấy một hiệu ứng.

### Decision: Cột Trạng Thái — Tô Màu Cho Vật Thể, Dùng Tương Phản Cho Người

options considered: mọi cột trạng thái đều dùng màu ngữ nghĩa; mọi cột trạng thái đều dùng tương phản;
tách theo việc trạng thái đó nói về cái gì.

selected option: tách theo đối tượng.

reason: vòng review chỉ ra hai quy ước trái ngược nằm cạnh nhau trên cùng artboard 10 — bảng đề tô
`state/processing` cho *"Đang mở"*, bảng học sinh ngay dưới lại cố tình từ chối màu. Cả hai đều đúng
theo lý lẽ riêng, nhưng không luật nào nói khi nào dùng cái nào, nên người dựng màn `Các bài kiểm tra`
sẽ phải đoán. Luật chốt: **màu ngữ nghĩa chỉ dành cho vật thể đang chạy** (`state/processing` cho một
đề đang mở); mọi thứ khác — kể cả thứ giáo viên cần để mắt tới — phân biệt bằng tương phản. Trạng thái
của một con người không bao giờ được tô, vì ADR-12 đã gán nghĩa cho hai màu trạng thái và không nghĩa
nào nói về người.

Hệ quả kéo theo: thứ bậc tương phản trong bảng đề bị đảo lại. *"Chưa tới giờ mở"* chuyển sang
`ink/default` vì theo ADR-02 đó là trạng thái **duy nhất còn thu hồi được** — thứ đáng quét mắt tìm
nhất, chứ không phải thứ đang chạy.

### Decision: Bỏ Mệnh Đề "Cột Thời Gian Áp Chót" Khỏi Luật Nhịp Cột

options considered: giữ mệnh đề và sửa bảng đề trên artboard 10 cho khớp; bỏ mệnh đề, chỉ giữ phần bất
biến thật.

selected option: bỏ mệnh đề.

reason: tôi viết mệnh đề đó vào mô tả `Class row` rồi **vi phạm nó ngay trong cùng lô** — bảng đề trên
artboard 10 đặt `ĐÃ NỘP` sau hai cột thời gian. Một luật bị chính tác giả phá trong cùng một lần dựng
là luật sai, không phải bản dựng sai: vị trí cột thời gian phụ thuộc từng bảng, còn thứ thật sự bất
biến chỉ là *chevron đóng hàng, ô hành động ngay trước chevron*. Giữ mệnh đề sai sẽ khiến hai plan sau
hoặc phá luật, hoặc bẻ cong bảng cho vừa một luật vô nghĩa.

### Decision: Học Sinh Chưa Nộp Nằm Trong Bảng Điểm, Không Bị Lọc Đi

options considered: bảng chỉ liệt kê bài đã nộp, số người vắng để ở đầu trang; liệt kê cả người chưa
nộp, hàng của họ để trống.

selected option: liệt kê cả người chưa nộp.

reason: con số "38/40" ở đầu trang nói *có hai em chưa nộp* nhưng không nói *em nào*, và đó chính là
câu giáo viên hỏi tiếp. Lọc họ đi biến một câu trả lời được thành một câu phải đi tra chỗ khác. Hàng
của họ không có chevron, vì không có bài làm nào để mở — và khi sắp xếp, họ luôn nằm cuối bất kể tăng
hay giảm, vì "chưa nộp" không phải một điểm số: xếp nó lẫn vào dãy điểm sẽ khiến 0 điểm và không làm
bài trông giống nhau.

### Decision: Biểu Đồ Phân Bố Dùng Một Màu Duy Nhất

options considered: tô cột theo mức học lực (giỏi / khá / trung bình / yếu); tô cột dưới mốc 5,0 bằng
màu cảnh báo; một màu cho mọi cột.

selected option: một màu.

reason: cả hai phương án tô màu đều **mã hoá một ngưỡng điểm vào giao diện**, và chưa ADR nào chốt
ngưỡng đó là bao nhiêu hay ai đặt nó. Đây đúng cái bẫy mà ADR-06 giữ frontend tránh với ngưỡng độ tin
cậy: một khi màu đã nói "dưới mức này là kém", đổi chính sách chấm không còn đổi được cách người dùng
đọc biểu đồ. Trường Việt Nam có mốc 5,0 thật, nên đây là quyết định **hoãn**, không phải từ chối — đã
ghi vào `backlog.md` kèm ba thứ nó sẽ mở khoá cùng lúc.

### Decision: Bỏ Nhãn "Cần Xem Lại" Khỏi Bảng Điểm

options considered: giữ nhãn vì nghiệp vụ có thật trong code; gỡ khỏi màn này, để dành cho hàng đợi
review.

selected option: gỡ.

reason: `needs_teacher_review` có thật và ADR-07 ghi đủ luật chọn nó — nhưng trên bảng điểm nó không có
hành động, không có đích đến. Một nhãn hổ phách không dẫn tới đâu dạy người dùng bỏ qua màu hổ phách,
làm hỏng đúng thứ ADR-12 cố giữ cho đắt. Nó thuộc về nơi có việc để làm.

### Decision: Trung Bình Đi Kèm Câu Diễn Giải, Không Chỉ Con Số

options considered: bốn ô thống kê thuần số; ô trung bình mang thêm một dòng so sánh với trung vị.

selected option: có dòng so sánh.

reason: trung bình và trung vị chỉ đáng hiển thị cùng nhau khi chúng LỆCH nhau — bằng nhau thì con số
thứ hai là trang trí. Lệch nhau nghĩa là phân bố bị kéo về một phía, và nếu giao diện không nói ra thì
giáo viên phải tự trừ hai số mới thấy. Dữ liệu mẫu vì thế được chọn có độ lệch thật (6,7 so với 7,5),
chứ không phải một phân bố cân đối làm cả hai con số trông như nhau.

### Decision: Trạng Thái Chờ Là Một Component Riêng, Không Phải Variant Của `Thinking`

options considered: thêm variant `chưa có bước nào` vào `Thinking`; dựng component riêng
`Assistant thinking`.

selected option: component riêng.

reason: `Thinking` tự khai trong mô tả rằng nó **không phải hiệu ứng chờ** — nó là khối bằng chứng các
bước đã làm, và luật của nó (thất bại không thu gọn được, cổng duyệt phải mở lại được, bản thu gọn giữ
nguyên số bước) đều nói về *bước*. Trạng thái chờ thì chưa có bước nào để nói. Quan trọng hơn về cấu
trúc: `Thinking` **không bao giờ mang avatar** — avatar sống trong `Message turn` phía trên nó. Ở
khoảnh khắc vừa gửi thì chưa có lượt trả lời nào, nên khối chờ buộc phải tự mang avatar. Hai thứ có
giải phẫu khác nhau, nhồi vào một set sẽ đẻ ra variant nửa nạc nửa mỡ.

### Decision: Shimmer Trên Chữ Được Phép, Nhưng Bị Chặn Biên Độ

options considered: cấm hẳn gradient trên chữ, chỉ cho dải sáng chạy trên một thanh khung xương; cho
shimmer chạy trên chữ nhưng chặn biên độ để không bao giờ tiến về phía màu nền.

selected option: cho chạy trên chữ, chặn biên độ.

reason: luật 3 của `Thinking` ban đầu cấm hẳn kỹ thuật này, và tôi đã dựng theo. Nhưng khi soi lại thì
**thứ ăn mất dấu tiếng Việt không phải kỹ thuật gradient — mà là biên độ.** Dấu chồng (ữ ộ ế) biến mất
khi dải sáng tiến về phía màu nền, đúng khoảnh khắc nó quét qua. Một gradient đi giữa `ink/muted` và
`ink/default` thì chữ chỉ **đậm lên**, không bao giờ nhạt đi, và tương phản không tụt dưới ~6:1 — dấu
luôn còn trên màn hình. Luật cũ cấm quá rộng: nó chặn cả những cách dùng an toàn.

Điểm khác biệt với ChatGPT/Claude vẫn còn, chỉ là ở chiều: họ quét dải sáng về phía **trắng** vì tiếng
Anh không có dấu chồng; bản Việt quét về phía **đậm**. Nhìn vẫn ra shimmer, nhưng không bao giờ xoá dấu.

Luật 3 trong mô tả `Thinking` đã được viết lại theo phát hiện này, vì nó áp cho mọi hiệu ứng chờ trong
sản phẩm chứ không riêng khối này.

Thanh khung xương vẫn giữ dải sáng trắng mềm 0,62 — nó là khung xương, không có dấu nào để mất. Và chỉ
**một** thanh, không phải hai ba dòng: nhiều dòng là hứa hẹn độ dài câu trả lời mà ở khoảnh khắc đó
chưa ai biết.

### Decision: Chờ Lâu Đổi Câu Chữ, Không Đổi Màu

options considered: sau ~10 giây chuyển khối chờ sang hổ phách để báo bất thường; giữ nguyên màu, chỉ
đổi câu chữ.

selected option: đổi câu chữ.

reason: chờ lâu vẫn là **trạng thái chờ, không phải lỗi** — đúng luật ADR-09 đã chốt cho timeout chấm
bài. Chuyển sang hổ phách sẽ nói dối rằng có việc cần giáo viên xử lý, trong khi không có việc gì cả,
và làm mòn ý nghĩa của hổ phách ở những chỗ nó nói thật (ADR-12).

### Decision: Năm Trạng Thái Linh Vật Là Một Component Set, Không Phải Ghi Đè Fills

options considered: mỗi artboard tự ghi đè `fills` của ô avatar bằng ảnh tương ứng; gom năm trạng thái
thành component set `Kriky state` và đổi bằng property của instance.

selected option: component set.

reason: bản làm đầu tiên là ghi đè `fills` rời rạc trên từng artboard. Nó chạy được, nhưng **không có
chỗ nào để định nghĩa chuyển cảnh** — mà chuyển cảnh mới là thứ phân biệt "đổi trạng thái" với "nháy
lỗi". Ghi đè rời rạc cũng không có gì canh: thêm một artboard nữa là lại đi chép hash ảnh bằng tay.
Component set cho năm trạng thái một cái tên, một nguồn, và một chỗ duy nhất để viết luật chuyển cảnh.

Ghi chú kỹ thuật đã trả giá một lần: **`resize()` bị bỏ qua âm thầm bên trong instance.** `fills` và
`cornerRadius` ghi đè được, kích thước thì không — phải sửa ở component gốc.

### Decision: Trạng Thái "Nghỉ" Đổi Sang Ảnh Toàn Thân

options considered: giữ `24_icon_face` (crop mặt) cho trạng thái nghỉ; đổi sang `01_hero_main_wave`
(toàn thân).

selected option: đổi sang toàn thân.

reason: ở cùng khung 40px, crop mặt làm nhân vật trông **to gấp đôi** bốn tư thế toàn thân. Chuyển
giữa chúng là một cú nhảy cỡ 2x, và **không hiệu ứng hoà tan nào giấu được** — mắt đọc ra là hai nhân
vật khác nhau chứ không phải một Kriky đổi trạng thái. Cùng một cỡ nhân vật biểu kiến là điều kiện để
chuyển cảnh mượt, nên nó quyết định luôn việc chọn ảnh. `24_icon_face` vẫn giữ vai ở rail 28px, nơi nó
đứng một mình và không phải chuyển sang gì cả.

### Decision: Chuyển Trạng Thái Bằng Hoà Tan Chồng, Không Nảy

options considered: cắt thẳng; hoà tan đơn giản (tắt hẳn rồi bật); hoà tan CHỒNG NHAU; hoà tan kèm
phóng to nhẹ cho sinh động.

selected option: hoà tan chồng nhau, không phóng to.

reason: hai hình khác tư thế và khác đạo cụ nên không morph được — chỉ còn hoà tan. Nhưng hoà tan
**không chồng** để lại một khung hình trống ở giữa, và mắt đọc khung trống đó ra là nháy lỗi. Cho hình
mới bắt đầu ở 60ms trong khi hình cũ còn đang mờ dần thì không bao giờ có khoảnh khắc trắng.

Không phóng to, không nảy: linh vật là chỉ báo trạng thái, không phải điểm nhấn. Một cú nảy mỗi lần đổi
trạng thái biến nó thành thứ ồn nhất trên màn hình mà việc chính là đọc soát mười câu hỏi — cùng lo
ngại "duyệt lấy lệ" mà ADR-10 nêu.

Kèm một luật mà backend nhanh sẽ phá nếu không viết ra: **giữ tối thiểu 400ms mỗi trạng thái.** Agent
chạy từ *đọc* sang *hỏi* trong 150ms sẽ làm linh vật nhấp nháy qua những tư thế không ai kịp thấy.

### Decision: Trạng Thái "Nghỉ" Quay Về Crop Mặt, Chấp Nhận Lệch Cỡ

options considered: giữ `01_hero_main_wave` (toàn thân, khớp cỡ với bốn tư thế kia); quay về
`24_icon_face` (crop mặt, lệch cỡ nhưng trung tính).

selected option: quay về crop mặt.

reason: vòng review chỉ ra `01_hero_main_wave` là hình **vẫy tay kèm một trái tim** — cử chỉ chào đầu
phiên — và ở trạng thái mặc định nó đứng cạnh nút **Phát hành** trên artboard 7 và 8, tức hành động
không thu hồi được duy nhất của sản phẩm. ADR-12 cấm đúng sự kề cận đó, và nhóm `Cách ly — sai tông`
đã loại ba asset khác vì cùng lý do. Khớp cỡ không đáng đổi lấy việc phá luật đó.

Đổi lại được một thứ: crop mặt là **cùng file với logo ở rail**, nên logo góc trái và avatar trong chat
lại đọc ra một nhân vật — vấn đề mà bản trước vô tình tạo ra.

### Decision: Nói Ra Rằng Luật Chuyển Cảnh Mới Đúng Một Nửa

options considered: giữ nguyên câu "cùng một cỡ nhân vật biểu kiến" trong mô tả `Kriky state`; đo lại
và viết đúng số.

selected option: viết đúng số.

reason: reviewer đo được bề ngang biểu kiến chạy **23,8 → 33,2px** (chênh 1,40×) và mép trái dịch tới
6,2px giữa hai trạng thái. Tôi đã viết là chúng bằng nhau. **Hoà tan độ mờ không giấu được dịch chuyển
ngang** — nó chỉ làm cú giật trông như hình bị trượt, nên luật chuyển cảnh tôi vừa viết mới đúng một
nửa. Cách sửa thật là xuất lại năm PNG trên cùng một khung vuông, việc nằm ngoài Figma và chưa làm.
Ghi ra vẫn tốt hơn để lại một mô tả nói sai — đó đúng lỗi hệ thống đã bị bắt ba lần trong dự án này.

### Decision: Trạng Thái Phải Gắn Vào Câu Nó Mô Tả

options considered: để `đã xong` trên lượt agent đầu tiên của artboard 5; chuyển nó xuống câu kết luận.

selected option: chuyển xuống câu kết luận.

reason: lượt agent đầu tiên nói *"Được, tôi bắt đầu nhé."* — lá cờ "đã xong" dán lên đúng câu **bắt
đầu**, tức là phủ định chính nó. Câu thật sự báo đề đã soạn xong (*"Đề đã đủ 10 câu…"*) lại là một TEXT
trần, không lượt, không avatar. Đã dựng nó thành `Message turn` thật và cho nó mang trạng thái. Bài học
chung: trạng thái linh vật là **nhãn cho một câu**, không phải trang trí cho một màn hình.

Hệ quả kéo theo, phát hiện ngay sau đó: câu kết luận ấy **cũng có mặt trên artboard 6, 7 và 8**, và ở
ba màn đó nó vẫn là TEXT trần — nên cùng một câu lại mang avatar khác nhau tuỳ màn. Đã chuyển cả ba
thành `Message turn` thật với cùng trạng thái. Luật rút ra và đã ghi vào mô tả `Kriky state`: **trạng
thái đóng băng lúc gửi.** Hội thoại đi tiếp thì avatar của các lượt cũ không đổi theo — một tin nhắn
không tự viết lại sau khi đã gửi.

## Validation Checks

- Hai artboard 1440×900, Density mode `Teacher`, `rail` 260 + `center` 1180.
- Rail giống hệt tám artboard cũ: brand 28 · new-chat 38 · nav 172 · lists 574.
- Đúng một node ở trạng thái được chọn trong rail, trên mỗi artboard.
- Chân nội dung `center` không vượt y=900; bảng học sinh tràn thật (nội dung 539 > khung 442).
- Mọi màu **do plan này đặt** lấy từ biến. Ngoại lệ đã biết: hai node `fade` trong rail dùng gradient
  hex thô `#f2f2ef` — chúng có sẵn trên cả tám artboard cũ và đi theo bản sao rail, không phải do
  plan này tạo ra. Gradient không bind được vào biến qua Plugin API.
- `.\dev.ps1 check` xanh; link Markdown resolve; file mới giữ LF; `AGENTS.md` vẫn 170 dòng.
- ADR-13 đủ năm mục và trạng thái hợp lệ.

## Status

Xong. Vòng review bắt được ba lỗi thật của tôi, tất cả đã sửa:

1. **Mô tả `Class row` ghi sai chính con số dùng để chống lệch bảng** — ghi *"gap 16"* trong khi thực
   tế là 24 ở mọi nơi. Đây đúng là thứ plan viện dẫn để không dựng `Table head` thành component: người
   dựng màn sau đọc mô tả sẽ lệch cả bảng. Đã sửa, và thêm con số kiểm tra (tổng cột + gap = 1068).
2. **Luật nhịp cột bị chính tôi phá trong cùng lô.** Xem decision record ở trên.
3. **ADR-13 để hở đúng chỗ nó tuyên bố là kín** — chốt luồng CSV là nơi *duy nhất* mật khẩu được hiện,
   rồi ngay câu sau nói *"chỉ còn thao tác đặt lại mật khẩu"* mà không nói thao tác đó hiện cái gì. Đã
   mở rộng luật cho cả hai thao tác sinh mật khẩu, và ghi link `179:8` vào mục *Nơi thi hành* kèm nhãn
   chưa-dựng.

Hai điểm reviewer đọc nhầm, đã kiểm lại bằng số đo và giữ nguyên thiết kế: bảng học sinh artboard 10
**đã** là `FILL/FILL` (không phải FIXED 511) nên nó tự co khi bảng đề dài ra; và `scroll` artboard 9
**đã** là HUG nên lớp thứ 10 không biến mất. Dù vậy rủi ro nền vẫn thật — quá ~17 lớp thì thẻ tràn khỏi
`center` và bị cắt im lặng — nên artboard 9 đã đổi sang `FILL`, cuộn thật, và hết luôn 348px chết.

Ba việc được nêu ra và cố ý hoãn — bộ lọc theo khối, thống kê điểm (trung bình / cao nhất / thấp
nhất), và sắp xếp theo ba thống kê đó — đã ghi vào [`docs/plans/backlog.md`](../backlog.md), kèm vật
chặn của từng cái. Hai trong ba bị chặn bởi ADR-09 chứ không phải bởi thời gian.

Còn lại cho hai plan sau: `Các bài kiểm tra` phải quyết **liệt kê theo đề hay theo cặp đề×lớp** (ADR-02
cho phép phát hành thất bại một phần, nên một đề có thể *đã mở* ở lớp này và *chưa mở* ở lớp kia), và
phải mã hoá được phép so **bao gồm** của cửa sổ thu hồi — đồng hồ chạm 00:00 mà nút Thu hồi vẫn phải
còn.

---

**Đóng ngày 2026-09-30** khi dọn `docs/plans/active/`. Người dùng xác nhận đã hoàn thành. Các ô kiểm
chứng máy móc được chạy lại tại thời điểm đóng: `.\dev.ps1 check` xanh 5/5. Những ô cần một người
xác nhận — vòng subagent review, manual test trên trình duyệt — tick theo xác nhận đó, và bằng chứng
là lời xác nhận ấy chứ không phải một lần chạy tôi quan sát được.
