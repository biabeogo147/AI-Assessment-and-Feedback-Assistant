# Nợ — việc đã hoãn có chủ đích

Mỗi mục ở đây là một thứ **đã được nêu ra và cố ý chưa làm**, không phải một ý tưởng bỏ ngỏ. Ghi lại vì
một tính năng bị hoãn mà không ai ghi thì lần sau sẽ được đề xuất lại từ đầu, hoặc tệ hơn, bị tưởng là
đã có.

Mỗi mục phải trả lời được: **cái gì đang chặn nó**. Không chặn bởi gì thì nói thẳng là chưa cần.

File này khác `docs/decisions/`: ở đó là luật nghiệp vụ đã chốt và còn hiệu lực; ở đây là việc chưa làm.
Nó cũng khác mục *Còn thiếu* trong `docs/decisions/README.md`, vốn liệt kê những **luật** chưa được ghi
thành ADR, không phải những **tính năng** chưa dựng.

## Bề mặt giáo viên — nợ còn lại

| Việc | Cái gì đang chặn |
| --- | --- |
| Bốn đích đến trên rail trơ | Bốn artboard kia chưa dựng. Con số trên huy hiệu *Bảng theo dõi* là chữ bịa (`invented-not-from-be.ts`, `DASHBOARD_WAITING`), nên rail không mời bấm |
| Danh sách đoạn chat không phân trang | Một giáo viên dùng một năm sẽ có vài trăm hàng, và lúc ấy rail cần một đường **tìm kiếm** chứ không phải một danh sách dài hơn |
| Mỗi lớp một bộ giờ riêng | `Publication` khoá theo `(đề, lớp)` nên schema **đã** cho phép; thiếu bề mặt. Figma chưa vẽ |
| `services/fe` nay là tên sai | **Không làm** (17/10/2026): không người dùng nào chạm tới. Nó phục vụ **hai** bề mặt; đổi tên chạm `pnpm-workspace.yaml`, `dev.ps1`, `check_contract.py`, `AGENTS.md`, `local-development.md` |

## Màn hình Danh sách lớp học

| Việc | Cái gì đang chặn |
| --- | --- |
| Bộ lọc theo khối (1–12) | **Không làm** (17/10/2026): chưa cần khi một giáo viên có chín lớp |
| Cột hoặc khối thống kê điểm ngay trên **danh sách lớp** | Không còn bị hạ tầng chặn — xem dưới. Thiếu thiết kế: gộp qua nhiều đề thế nào, và đặt ở đâu |
| Sắp xếp danh sách lớp theo trung bình / cao nhất / thấp nhất | Cùng vật chặn |

Thống kê điểm **của một bài kiểm tra trong một lớp** thì đã có — artboard
`11 · Kết quả bài kiểm tra trong lớp`. Cái còn nợ ở đây là thống kê **gộp theo lớp** hiện trên chính
hàng của bảng danh sách lớp, tức là gộp qua nhiều bài kiểm tra.

Hai dòng này từng ghi *bị chặn bởi hạ tầng*: [ADR-09](../decisions/adr-09-ket-qua-cham-la-tam-thoi.md)
cho kết quả chấm sống một giờ trong Redis. Nay bài làm và điểm từng câu nằm trong Postgres (`attempts`,
`question_outcomes`), nên dữ liệu đã có; thứ còn thiếu là quyết định gộp (trung bình của đề nào, đề
đang mở có tính không) và chỗ đặt trên màn hình.

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

Mô hình hai pha ([ADR-14](../decisions/adr-14-hai-pha-lam-bai.md) …
[ADR-21](../decisions/adr-21-trang-thai-bai-lam-la-ben.md)) đã chạy trên database: pha 1, lượt chữa
pha 2 có trần ba vòng, điểm ba mức và lý do được 0,5 đều có thật. Còn lại ba việc cố ý chưa làm.

| Việc | Cái gì đang chặn |
| --- | --- |
| Cổng duyệt cho câu luyện tập | **Chưa quyết định nghiệp vụ** — xem dưới |
| Bắt đổi mật khẩu ở lần đăng nhập đầu | Không bị chặn. Không có màn hình nào để đặt nó vào — xem dưới |
| Phát hiện sớm một lời giải sai | **Chưa quyết định nghiệp vụ** — xem dưới |

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

### Lời giải sai bị khuếch đại, và chưa có cách phát hiện sớm

[ADR-18](../decisions/adr-18-cau-hoi-phai-kem-loi-giai.md) đòi mỗi câu kèm lời giải. Một lời giải sai
**chỉ lộ ra qua những em làm sai câu đó** — đúng những em sẽ được **dạy lại bằng chính lời giải sai
đó**, cùng lúc, cả lớp. So với việc feedback sai tới từng em một cách rời rạc, mô hình mới **khuếch
đại** lỗi này.

Kênh phát hiện duy nhất là [ADR-19](../decisions/adr-19-bao-cao-giai-thich-chua-ro.md), và nó cố ý
**không chặn ai**. Chấp nhận có chủ đích ở đợt này; khi có hàng đợi review thật thì đây là ứng viên
đầu tiên được nối vào.

### Không có màn đăng nhập nên không có chỗ bắt đổi mật khẩu

[ADR-13](../decisions/adr-13-lop-va-tai-khoan-hoc-sinh.md) để mật khẩu ban đầu đi trên **giấy in** từ
tay giáo viên. Ai nhặt được tờ giấy cũng đăng nhập được. Cách chặn thông thường là bắt đổi mật khẩu ở
lần đăng nhập đầu, nhưng đợt thiết kế học sinh cố ý bỏ qua màn đăng nhập nên không có chỗ đặt nó.

Đây là **lỗ hổng đã biết**, không phải chuyện chưa ai nghĩ tới. Cột *trạng thái tài khoản* trên màn
`Chi tiết lớp` — phân biệt *chưa đăng nhập lần nào* với *đang hoạt động* — hiện là dấu vết duy nhất
trong sản phẩm cho thấy lần đăng nhập đầu có ý nghĩa riêng.

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

## Variant `phát-hành-thất-bại` của `Action result card` chưa có dữ liệu

Ghi ngày 2026-09-30, khi đóng `2026-09-30-teacher-harness-foundation-plan.md`.

| Việc | Cái gì đang chặn |
| --- | --- |
| `entity_kind`/`entity_id` đủ cho bảy variant `Action result card` | **Tier 3: BE chưa ghi lần phát hành hỏng (`_note_publication`), không phải việc FE** (plan `backlog-tier-1`, pha 4). Còn **một** variant: `phát-hành-thất-bại` |

Sáu trong bảy nay có dữ liệu: `tạo-đề-trống` và `thêm-câu-hỏi` từ
Pha 3, `đã-duyệt`/`bỏ-duyệt` từ Pha 4, `đã-phát-hành` từ Pha 5, `tạo-lớp` từ `find_class`. Thiếu
`phát-hành-thất-bại`: `_note_publication` chỉ ghi một bước khi **có** lớp nhận được, nên một lần phát
hành trượt toàn bộ không để lại dấu nào trong `teacher_turns`.

## Hai mục nợ của Pha 5

Ghi ngày 2026-10-01, từ review Pha 5.

| Việc | Cái gì đang chặn |
| --- | --- |
| `UniqueConstraint` mới trên `questions` chưa áp vào database đã tồn tại | Không có migration; `create_all` bỏ qua bảng đã có |
| Hai ADR chọn **bao gồm** ở hai phía của cùng một mốc | Cần một quyết định, không phải một bản sửa |

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

Đợt khảo sát tìm 16 lỗi; tám món đã vào `2026-10-06-tam-loi-khao-sat-plan.md`, các món khác đã làm
dần ở những plan sau. Ba món còn lại nằm đây, mỗi món kèm lý do nó chờ.

| Việc | Cái gì đang chặn |
| --- | --- |
| `start_drafting` gọi thẳng không qua plan, bị ADR-25 từ chối, mất một lượt model | Model thấy cả tool đọc lẫn tool ghi trong một danh sách; sửa ở prompt hay ở danh sách tool model thấy |
| Model đánh dấu sai đáp án đúng, và đáp án đúng không nằm trong bốn phương án | Chất lượng model sinh ra; đường sửa đi qua prompt |
| Model viết *"định thức"* cho một bài tích phân, và `\bigint` — một lệnh không có thật | Cùng trên |

## `Kriky state` của Figma chưa vẽ xong

Ghi ngày 2026-10-08, lúc xếp lại page `Components` cho plan 2b. Đây là **quyết định thiết
kế**, không phải lỗi máy móc, nên nó không được sửa vội trong một plan đang làm việc khác.

| Việc | Cái gì đang chặn |
| --- | --- |
| `Kriky state` (`234:1180`) có năm variant — `nghỉ`, `đang đọc`, `đang hỏi`, `đang làm`, `đã xong` — mỗi cái là một hộp **40×40 rỗng không** | Cần vẽ năm tư thế của linh vật Dế Mèn. Tài sản nằm ở page `Assets — Dế Mèn`; việc còn lại là chọn tư thế nào cho trạng thái nào, và đó là một quyết định về nhân vật chứ không phải về code |

Không chặn gì đang chạy: `Kriky state` chưa artboard nào dùng. Cùng câu hỏi với mục *Linh vật*
(Tier 2 câu 12).

## Queue `aiafa:grading` mang tên sai

| Việc | Cái gì đang chặn |
| --- | --- |
| `aiafa:grading` vẫn mang cái tên sai | **Không làm** (17/10/2026): không người dùng nào chạm tới. Nó chở bảy task và sáu cái không chấm bài; đổi tên chạm `.env.example`, `be/config.py`, `agent/config.py`, và một queue đang có job thì không đổi tên nóng được |

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
15/10/2026). Đường job gọi chúng qua `asyncio.to_thread` (`ocr_handlers.py`), nên event loop không bị
chặn; thứ còn thiếu là luật *một module* của check.

| Việc | Cái gì đang chặn |
| --- | --- |
| Mở seam thứ ba cho `paddle`/`paddleocr`, hoặc dựng một `ocr/engine.py` làm cửa duy nhất | **Tier 2: chọn hình dạng (danh sách ba file hay một cửa ocr/engine.py) là quyết định** (plan `backlog-tier-1`, pha 4). Chưa quyết hình dạng. Danh sách ba file giữ được luật grep được nhưng phá câu *"đúng một module"*; một cửa duy nhất giữ câu ấy nhưng thêm một lớp gián tiếp cho ba model không liên quan nhau |

## PP-DocLayout mù với trang mục lục, và không gì báo động

Ghi ngày 10/10/2026, từ review Task 4. Đây là **tin xấu nhất cho plan 3c** (dựng cây; trước 11/10/2026 gọi là 3b), không phải cho 3a.

Trên trang mục lục của *Kết nối tri thức Lớp 6 tập 1* -- sáu khung màu, khoảng sáu mươi mục --
PP-DocLayout trả về **đúng một hộp**: số trang. Không phải lỗi ngưỡng; đó là đầu ra thô. Cùng kiểu
mất mát ở vài chỗ khác: hai khung vở ở trang 46, ngôi nhà hồng ở trang 40, và trang 2 chỉ ra ba hộp.

Đúng trang mà bước dựng mục lục cần nhất thì lại là trang model đọc tệ nhất.

| Việc | Cái gì đang chặn |
| --- | --- |
| Một tín hiệu *"trang này gần như rỗng mà nó không trắng"* | Chưa quyết đo bằng gì. Đếm khối thì một trang bìa thật cũng ít khối; đo lượng mực trên ảnh thì cần một phép đo mới. Hôm nay `logger.info` in `found 1 boxes, kept 1` rồi đi tiếp, và bộ đo sẽ chấm trang ấy gần 0 điểm mà không ai biết đó là lỗi **recall của layout** chứ không phải lỗi đọc chữ |

## Nợ của plan 3b — kho nội dung và OCR theo lô

Ghi ngày 11/10/2026. Mục này từng mang tên *"OCR theo lô cho PDF scan — việc còn lại của plan 3b"*,
khi plan ấy đóng sớm sau Task 2. Plan được **mở lại** cùng ngày và Task 3 đã làm xong
(`completed/2026-10-11-mongo-content-store-plan.md`): PDF scan giờ đi đường OCR theo lô, có tiến độ,
và về `ready`. Còn lại là nợ.

| Việc | Ghi chú |
| --- | --- |
| **Nhiều cuốn scan cùng lúc bị đọc ra *xử lý hỏng* cùng lúc.** Worker `document` chạy `max_jobs = 1`, lô kế của mỗi cuốn xếp cuối queue, nên `k` cuốn đọc xen nhau và khoảng giữa hai tiếng báo tiến độ của một cuốn là chừng `k` × 45 s | Vượt ngưỡng 300 s từ `k` ≈ 7 (≈ 4 với trang dày chữ). Một lần dò tệp có chữ cũng chờ chừng ấy. Hướng: đo *đứng quá lâu* theo nhịp sống của worker chứ không theo tiến độ từng cuốn, hoặc cho chuỗi lô đầu tiên chạy hết trước (FIFO theo cuốn) và báo tiến độ `0` lúc xếp hàng. Phát hiện ở review Task 3 |
| **PDF lai qua cổng 10%** (vd. 40/400 trang có lớp chữ mỏng) ra `READY` / `text_layer` với 360 trang rỗng, không bao giờ đi OCR | 3c sẽ dựng cây trên bản thô thủng. Hướng: trang dưới `_MIN_CHARS_PER_PAGE` đi OCR -- cần một bản scan có lớp OCR mỏng thật để đo |
| **Xoá bản thô khi giáo viên xoá tài liệu**; và bản thô mồ côi khi kho ghi xong mà `_hand_back` hỏng hết lượt thử | BE không giữ khoá Mongo (D1). Có thể là một task `document` nhận lệnh xoá |

## Nợ của plan 3c — document agent, Jev và cây ba cấp

Ghi ngày 11/10/2026, cùng lượt viết plan 3c (`completed/2026-10-11-document-agent-hierarchy-plan.md`).
Số đo nằm ở `Status` của plan ấy và ở `data/results/run-6/pageindex-jev-1.13.0/`.

| Việc | Ghi chú |
| --- | --- |
| **Cây vàng chỉ có một cuốn**, và luật lẫn ngưỡng đều chỉnh trên chính cuốn ấy | Cần cây vàng của một cuốn khác (một tập khác của bộ KNTT, và một tài liệu không phải SGK) để so Jev với luật cho công bằng |
| D1 hứa *"dùng luật khi số thứ tự đi lùi"* -- chưa làm; `Numbering.value` chưa ai đọc | **Tier 3 P6 (đọc tài liệu): một bước mới của assemble, cần đo trên cây vàng** (plan `backlog-tier-1`, pha 4). Một bước trong `assemble`: tiêu đề cùng cấp mà số nhỏ hơn số trước nó thì hỏi lại luật |
| Thứ OCR không đọc ra thì không cây nào có: tên Bài 10 (trang 39), hai mục Bài 21 (trang 100–101), *Hoạt động thực hành trải nghiệm* (banner không có chữ CHƯƠNG) | Một cổng thứ hai cho luna: trang mở bài (có hộp *KHÁI NIỆM, THUẬT NGỮ*) mà không có `doc_title` -- đọc tên bài trên ảnh. Dải mục màu đỏ (*"1. HÌNH CÓ TRỤC ĐỐI XỨNG..."*) thì PP-DocLayout không thấy khối nào |
| `LLM_TIMEOUT_SECONDS` dùng chung với AGENT | **Không làm** (17/10/2026): chưa trần nào cần khác. Tách một biến riêng nếu luna hay tóm tắt cần trần khác |
| *"1.1"* là bài tập chỉ khi tài liệu đi qua OCR -- một SGK **có** text layer thì *"1.1. Cho hai tập hợp"* thành mục cấp 2 | **Tier 3 P6: cần đo trên cây vàng trước khi tin** (plan `backlog-tier-1`, pha 4). Phân biệt theo hình dạng (*"1.1."* có chấm cuối, theo sau là câu chữ thường) thay vì theo nguồn đọc |
| Một khe hẹp: lô OCR cuối của một lần đọc mới giao job dựng cây **trong lúc** job cũ còn chạy thì bị id cố định từ chối, và job cũ bỏ vì bản thô đang đọc dở | **Tier 3 P6: đổi id job dựng cây** (plan `backlog-tier-1`, pha 4). Không ai dựng cây; chip ra *xử lý hỏng* sau 300 s. Hướng: id theo `raw.started_at` thay vì theo tài liệu |
| Một đơn vị đọc dài hơn 1 500 ký tự không bị cắt, nên chunk vượt trần | **Tier 3 P6: cắt theo câu khi ghi kho** (plan `backlog-tier-1`, pha 4). Khối text layer lớn; cắt theo câu khi cần |
| `except Exception` ở bước banner và tóm tắt che cả lỗi lập trình (chỉ còn `logger.exception`) | **Tier 3 P6: đếm lần hỏng vào IndexHeader là đổi schema của kho** (plan `backlog-tier-1`, pha 4). Đếm số lần hỏng vào `IndexHeader` để thấy được từ dữ liệu |
| Lượt Jev thứ hai không chạy khi đóng plan: trên SGK Jev thuần ra 138 nút cho 91, ở ngưỡng 0,8 nó thắng luật đúng một lần và lần ấy sai -- cây hiện nay là cây của luật. *Plan 4c T4 đổi tiêu chí (bỏ ví dụ chương): Jev thuần 120 nút, thắng luật 0 lần ở 0,8; cuốn thứ hai (Lớp 10 tập 1, chưa có cây vàng) lộ `"a. Mệnh đề"` OCR thành `"2. Mệnh để"` bị Jev xếp cấp 3 -- ứng viên cho `letter_case`* | Thiết kế câu hỏi mới ($0,026 một lượt trên Lớp 6 tập 1): bỏ số khỏi state (`page` thành *đầu / giữa / cuối sách*, `numbering` thành loại nhãn bằng chữ), thêm `letter_case`, `level_3` chỉ nhận một nhãn số **và** chữ in hoa toàn bộ, criteria ngắn lại; đo lại bằng `tools/pageindex_bench`, và cần cây vàng thứ hai để luật không được chấm trên chính cuốn đã chỉnh nó |

## Khi có process hay BE thứ hai

Những thứ dưới đây **chưa phải nợ**: chúng đúng với một process `document` và một BE, như hôm nay.
Chúng thành lỗi đúng vào ngày chạy cái thứ hai, nên ghi gom một chỗ để lượt ấy đọc một lần.

| Việc | Cái gì đang chặn |
| --- | --- |
| Id cố định của lô (`ocr:<doc>:<first>`) chỉ chặn chuỗi trùng với **một** process `document` | Chạy hai process thì một lần chạy lại có thể đẻ chuỗi thứ hai và `begin` xoá trang của chuỗi kia |
| Một trang đơn lẻ OCR quá 120 s vẫn chạm `job_timeout` | Ngân sách 90 s của lô chỉ kiểm giữa hai trang. Chưa gặp: trang chậm nhất đo được ~12 s |
| Trần số connection của `StreamingResponse` vẫn **chưa đo** | Nợ từ plan 2b. Một giáo viên mở năm tab là năm connection, và không có gì giới hạn. Một vòng nối lại làm con số này đáng đo hơn, không kém đi |
| Thẻ khoá lượt là giờ của process: trên Windows (nhịp đồng hồ 15,6 ms) hai lượt giành khoá trong cùng một nhịp thì mang cùng thẻ | Chỉ xảy ra khi lượt trước đã quá hạn **và** lượt sau giành đúng nhịp ấy. Thẻ thật nên là một giá trị duy nhất (uuid, hay một bộ đếm) thay vì giờ -- đổi cột, nên đi cùng món *đồng hồ của process* dưới đây. Test từng hỏng vì cùng nhịp ấy đã sửa (plan `backlog-tier-1`, pha 4) |

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

## Lộ ra khi làm plan ngân hàng câu hỏi

Ghi ngày 13/10/2026, trong `2026-10-13-question-bank-write-path-plan.md`. **Hoãn có chủ ý** (người dùng chốt phạm vi *chỉ đường ghi*):

| Việc | Cái gì đang chặn |
| --- | --- |
| **Đường đọc ngân hàng**: tool để Kriky rút câu từ ngân hàng khi soạn đề, và câu kết *"8 câu lấy từ ngân hàng, 2 câu tôi soạn thêm"* của artboard 5 | Một plan riêng. Cần quyết cách chọn câu (theo môn, khối, mục tiêu, phạm vi) và cách hỏi lại giáo viên về nguồn (ADR-05: không đánh dấu lựa chọn nào là nên chọn) |
| **Câu lấy từ ngân hàng sang đề mới không được sinh bản trùng khi duyệt** (ADR-28, Hệ quả). `file_approved` hôm nay chép **mọi** câu của đề, khoá theo `question_id`; một câu chép từ ngân hàng sang là một `Question` mới, nên sẽ thành một dòng mới | Cần một cột nguồn trên `Question` (trỏ về `BankQuestion`) -- cùng cột mà chip nguồn thật cần. Làm cùng đường đọc |
| **Mục kiến thức và tài liệu chưa vào ngân hàng.** `drafting._write` không nối `DraftItem` với `Question`, nên lúc duyệt không có mục nào (nay là `outline_item`) để chép; đường đọc theo phạm vi sách sẽ cần nó | Nối `DraftItem` ↔ `Question` lúc thu hoạch, rồi chép tiêu đề mục (bền qua lần dựng lại cây) vào `BankQuestion` |
| **Chip nguồn thật trên từng câu.** Từ ADR-28 phần *đã kiểm / chưa kiểm* suy được từ trạng thái đề; phần *ngân hàng / Kriky soạn* cần cột nguồn ở dòng trên. Chip bịa đã gỡ 17/10/2026 (Tier 2 câu 1 = A, plan `backlog-tier-1` pha 2), nên panel hôm nay không nói nguồn | Chờ cột nguồn ở dòng trên |
| **Sửa bản trong ngân hàng** (vòng ADR-19) và câu hỏi đi kèm: lần duyệt lại đề gốc sẽ ghi đè bản đã sửa ấy | Chưa có màn ngân hàng; quyết lúc dựng đường sửa (ADR-28, Hệ quả) |

## Lộ ra khi làm plan dàn ý đề

Ghi ngày 15/10/2026, khi đóng `2026-10-15-draft-outline-plan.md` (ADR-29). Số đo là `propose_bench`
gpt-4o-mini 6 lần/ca (`data/results/run-101`, trước `_approved_plan`) và ba lượt thử trình duyệt; chi
tiết ở mục *Status* của plan.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Plan chỉ có `create_draft` không qua cổng duyệt.** Cổng ADR-29 chỉ xét plan có `start_drafting` hay `replace_question`; thử tay lượt ba, model chép lại một plan hỏng của lượt trước và mở một **đề trống mới** cho lời xin *"soạn thêm 2 câu"* | **Chờ người dùng quyết**: chặn nó là bỏ khả năng mở đề trống bằng chat (đề trống vẫn thêm câu tay được ở panel) |
| **`tra-lop-ket-qua` tụt 6/6 → 2/6** -- hồi quy ngoài luồng dàn ý: model nêu `call_tool` không tên tool hay không tham số khi tra kết quả lớp | Chưa rõ gốc: prompt `_CORE` dài thêm việc thứ năm là nghi vấn đầu. Cần đo riêng ca ấy trên bản trước plan và bản hiện tại |
| **Dàn ý chung chung.** Thử tay: năm mục cùng ghi *"tỉ lệ thức"*, công thức thiếu hay lặp y nhau giữa các mục, nên câu 1, 3, 4 ra cùng một dạng. Dàn ý theo sách (đọc `read_section`) cụ thể hơn hẳn. Lần chạy mốc 15/10 (02, 07, 08): 0/5 mục có công thức, câu lệch mục | Một luật prompt (*mỗi mục một kiến thức khác nhau, công thức của riêng mục*) và một ca bench chấm độ khác nhau giữa các mục -- chưa làm, cần đo trước khi tin |
| **`vuot-tran-12-cau` 0/6**: xin 12 câu thì model nêu dàn ý 10 câu thay vì nói trần 10 câu một lần | BE vẫn chặn quá 10 nên không hỏng dữ liệu; giáo viên chỉ không được nói vì sao. Sửa bằng một lời BE thêm khi tổng dàn ý thấp hơn số xin, hay luật prompt |
| **`dan-y-duyet-khong-gian` 2/6 đo trước `_approved_plan`** | Đo lại khi có lần chạy bench thật kế tiếp (không chạy riêng chỉ để đo ca này) |
| **Model nói "mình sẽ soạn dàn ý ngay" trong một `ask_clarify`** (thử tay lượt ba) và hỏi phạm vi trên sách khác khối của đề (chip Lớp 6 đính vào đoạn chat của đề lớp 7) | Lỗi thứ hai là hệ quả của chip tự đính lúc tải lên (plan 4b), không của dàn ý |
| **Mục dàn ý của câu đã bị thay vẫn nằm trong `brief.outline`** và vẫn vào `other_items` của job sau (có trần); thẻ kết quả bước thay câu dùng đầu đề *"Đã tạo đề"* | **Không sửa: để job né cả kiến thức câu giáo viên đã bỏ là vô hại; đầu đề Đã tạo đề cho bước thay câu đúng thiết kế bốn đầu đề chốt 06/10** (plan `backlog-tier-1`, pha 4). Review đợt 5 ghi nhận; không sai dữ liệu |
| **Bench `be_refuses` chỉ chạy `vet_plan`**, không chạy cổng duyệt -- một plan soạn khi chưa có dàn ý vẫn được chấm là đạt nếu đủ tham số | **Tier 4: bench cần dựng lịch sử có lượt dàn ý** (plan `backlog-tier-1`, pha 4). Cần bench dựng lịch sử có lượt dàn ý; ca `dan-y-*` hiện chấm bằng hình dạng đề nghị |
| **Kriky hỏi lại dù đã đủ mục** (thử tay lượt bốn: *"soạn thêm 1 câu về cách ghi số La Mã"* → hai câu hỏi lại về khía cạnh và bài, rồi mới nêu dàn ý; bench run-98 thấy cùng kiểu ở ca đủ mục). Chữ kiến thức trong dàn ý đôi khi đuôi dấu `;` (*"Cách đọc số La Mã từ 1 đến 30;"*) | Chưa có cách sửa bằng code; luật prompt *đủ bốn mục thì nêu dàn ý* đã có. Cần đo riêng trước khi đổi prompt |

## Lộ ra ở lần chạy mốc bộ ca thử tay

Ghi ngày 15/10/2026, plan `2026-10-15-manual-browser-test-cases-plan.md`. Biên bản nguyên văn:
`docs/testing/ket-qua/2026-10-15-6287fc3.md` (gpt-4o-mini). Mỗi dòng ghi case thấy nó.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Nút hỏi lại không phải giá trị bấm được** (01, 08, 13): *"khối 6, 7, 8, 9"*, *"số câu từ 1 đến 10"*, *"Mình chỉ soạn 1 lần 12 câu."* (trái với trần vừa nói), *"Môn học là Lịch sử"* | `_answers` chỉ bỏ câu hỏi và tên mục trần; chưa có luật cho nút gộp cả dải giá trị |
| **`read_section` đọc nhầm nút** (06): xin 2 câu số La Mã, Kriky đọc nút 4 (Hệ thập phân) và dàn ý ghi `Theo: 1. HỆ THẬP PHÂN` | Model chọn nút; chưa có luật đối chiếu chủ đề với nhãn nút |
| **Kết quả lớp dừng ở bước tra lớp** (12): *"bài kiểm tra 15 phút hàm số của 12A các em làm thế nào rồi"* → chỉ `list_class` rồi *"Lớp 12A có 3 học sinh."* | Cùng kiểu ca bench `tra-lop-ket-qua` 2/6; log cho thấy model tự chọn `say`, không phải lùi về mock |
| **Tệp đang xử lý thì Kriky nói "chưa thấy tài liệu"** (13) thay vì nói tệp đang được đọc và nhờ chờ | Prompt có dòng *đang xử lý*; model không theo |

## Lộ ra khi chạy bộ ca thử tay trên Claude Haiku 5.5

Ghi ngày 16/10/2026, plan `2026-10-16-claude-provider-option-plan.md`. Biên bản:
`docs/testing/ket-qua/2026-10-16-d6c82d4-claude-haiku-5-5.md`, đặt cạnh mốc gpt-4o-mini. Mỗi dòng
ghi case thấy nó.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Hai câu cùng mục trùng nhau** (02, 06, 07): job bám ví dụ trong `formulas`, bỏ lời dặn *"khác cách hỏi hoặc số liệu"* | Đã có lưới gần trùng ở `harvest` (plan `backlog-tier-1`, pha 1) và brief nêu mọi câu đã có (pha 6). Còn lại hai câu cùng dạng khác số: Tier 2 câu 19 |
| **Dàn ý một mục cho cả đề** (01, 03, 07, 08, 13): `Câu 1–N` một mục | Đúng `outline.validate`; chưa có luật về số mục |
| **Hỏi lại hai lần với tệp scan một trang, một `get_chapter` sai id tài liệu** (13) | Chưa sửa |
| **Tóm tắt nút cây mở bằng "Phần này"** (mục lục SGK dựng trên Haiku) | Prompt tóm tắt cấm; Haiku không theo |

## Lộ ra khi thử tay plan lời Kriky do model viết

Ghi ngày 17/10/2026, plan `2026-10-17-kriky-writes-every-word-plan.md`. Biên bản:
`docs/testing/ket-qua/2026-10-17-02ba28a-claude-haiku-5-5.md`. Bốn lỗi sửa ngay trong buổi (160 ký tự
của `learning_objective`, thẻ hỏi lại dính chữ, plan bị từ chối lặp lại, số node trong lời dàn ý) không
ghi ở đây.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Dàn ý sửa không tách mục gộp** (03): sửa câu 3 của mục `Câu 3–4` thì câu 4 thành cùng dạng | Chưa có luật; `_right_purpose` không biết câu nào trong mục bị đổi |
| **Tên đoạn chat chép lời dặn**: *"Soạn đề toán lớp 6 chương 1 (từ chối? không) — tiêu đề: Soạn"* | `naming.py` trên Haiku; chưa đo lại |
| **"Cả chương" mà chỉ đọc một phần chương** (04): `read_section` với `nodes` 1, 3, 6, 17 do model chọn, bỏ bốn bài, mà lời dàn ý vẫn nói *"lấy từ bài 1 đến thứ tự thực hiện các phép tính"* | Model chọn nút; `_read_before_outline` chỉ đòi đọc hết phạm vi **đã gọi**, không đối chiếu với phạm vi giáo viên nói |

## Lộ ra khi thử tay plan tên đề và hỏi nhiều câu

Ghi ngày 17/10/2026, plan `2026-10-17-assessment-title-and-multi-question-plan.md`. Biên bản:
`docs/testing/ket-qua/2026-10-17-e8f7f9d-claude-haiku-5-5.md`. Thẻ hỏi lại thiếu avatar Kriky đã sửa
trong buổi, không ghi ở đây.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Nút của câu hỏi phạm vi là *loại* phạm vi** (01): *"Một chương đang học"*, *"Một chủ đề cụ thể"* — không bấm được thành một phạm vi | `_answers` bỏ tên mục và câu hỏi, không nhận ra một *loại*; luật skill chưa nói nút phạm vi phải là tên một phần kiến thức |
| **Lời dàn ý gộp bài nguồn ở cuối** (04) thay vì nêu theo từng mục | ADR-30 chỉ đối chiếu nhẹ lời dàn ý; `source_nodes` từng mục vẫn đúng, chỉ chữ không nói |
| **Phương án rác `$4\,volume$`** (04, câu 3) do job soạn câu viết, và đáp án đánh dấu theo đó sai | Không lưới nào soi chữ không phải toán trong phương án số |
| **Tên đoạn chat là lời trợ lý** (04): *"Bạn gửi kèm sách hoặc chụp các trang chương 1 Toán 6 giúp mì…"* | Cùng gốc với dòng *"Tên đoạn chat chép lời dặn"* ở trên (`naming.py` trên Haiku) |
| **Lời mở lượt soạn chép nguyên ví dụ trong prompt** (02, 04): *"Được, mình soạn đề ngay."* | Ví dụ nằm trong `propose._CORE`; lời model nhưng đọc như câu cố định (ADR-30). Bỏ ví dụ nguyên văn, hay cho nhiều ví dụ |

## Lộ ra khi review code `/code-review high` (17/10/2026)

Phạm vi: 66 commit từ upstream, chủ yếu ADR-31 (tên đề) và ADR-32 (hỏi lại nhiều câu), sau commit
`be30d34`. Chưa chạy verifier; người dùng dặn ghi hết, chưa sửa.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Phép ghép *lời mở + câu hỏi* chép ở hai nơi** (`teacher_chat.py:916` và `propose.py:1360`) | **Tier 3 P4: một hàm dùng chung trong contracts là đổi contracts, cần plan** (plan `backlog-tier-1`, pha 4). Hai bản có thể lệch; hợp đồng chỉ soi hình dạng. Một hàm dùng chung trong `contracts` |
| **Hai dòng `# TODO: Cần xem lại` trong `propose.py` chưa stage** (dòng 58, 1573) | Không phải lỗi: ghi chú riêng của người dùng, cố ý không commit — stage bằng script bỏ hai dòng ấy. Ghi để `git add` thẳng file không lỡ tay |

## Lộ ra khi làm plan Tier 1 (17/10/2026)

Plan `2026-10-17-backlog-tier-1-plan.md`. Mỗi dòng có tier ở artifact *Backlog theo tier*. Lỗi do chính
plan sinh ra và đã sửa trong cùng pha thì không ghi ở đây.

| Việc | Cái gì đang chặn |
| --- | --- |
| **Lượt chữa đã hết giờ (đồng hồ 00:00) vẫn cho chọn đáp án, và hộp nộp vẫn mời *"Quay lại làm tiếp"*** -- `Round.tsx` không có trạng thái *đã dừng*; BE từ chối lưu nên lựa chọn bấm sau giờ không được tính -- review ảnh pha 4 | Tier 2: màn *lượt đã dừng* trông thế nào (khoá phương án, chỉ còn nút nộp) là việc thiết kế, cần artboard |
| **Lưới gần trùng báo nhầm hai câu khác ý cùng mở bằng một hàm cụ thể** (*"Cho hàm số $y=x^3-3x+2$"* đồng biến / cực đại): câu sau thử lại tới `failed` -- review code pha 5 | Tier 2: *gần trùng* nghĩa là gì (cùng gist **và** cùng phần chữ hỏi?) là quyết định |
| **Hộp nộp lượt in cứng *"câu làm đúng được 0,5 điểm"*** (`Round.tsx`): bản sao FE của `scoring.MARK_REMEDIATED` -- review code pha 5 | Tier 2: thêm một trường BE, hay bỏ dòng ấy (artboard 22b đang vẽ nó) |
| **Bỏ một dàn ý đề mới rồi nêu dàn ý đề mới khác, không plan nào ở giữa**: dàn ý sau vẫn mượn môn/khối/phạm vi của dàn ý trước -- review code vòng 2 | Tier 2: hai dàn ý đề mới liền nhau là *sửa* hay *đề khác* là quyết định nghĩa. Rộng hơn một chút (review code vòng 3): dàn ý đề mới B bỏ dở → *soạn thêm cho X* → dàn ý đề mới D thì D mượn của B, vì plan *soạn thêm* không tạo đề mới nên không phải mốc |
| **`_COUNT_SAID` đọc *"2 câu cuối khó hơn nhé"* thành tổng 2** -- có từ trước, review code vòng 4 | Tier 4: lời nói về một phần của đề hay về tổng là chuyện đọc hiểu, regex không đủ; đo trên bench trước khi đổi |
| **Phân biệt *đồng ý* với *xin sửa* dàn ý bằng regex không bao giờ kín**: bốn vòng review liền (pha 5) đều ra một ca biên mới của `_NO_CHANGE`/`_REVISES` | Tier 2 câu 5 (lời đồng ý dàn ý): nút *Soạn theo dàn ý này* do BE dựng thay cho regex. Từ nay ca biên của regex này xếp vào câu 5, không vào Tier 1. Đã biết còn lọt hay còn mơ hồ: 9 câu ở `OPEN` của `tests/test_revision_words.py` (*"không đổi nhé câu 3 sang tự luận"*, *"không cần bỏ câu nào"*…); tiểu từ miền Nam chưa nhận (*ha, hen, nghen, nghe, nhỉ, á, nè*); *"sao em/lại không sửa luôn đi"*; *"k sao k cần sửa"*, *"hông sao hông cần sửa"*; *"gì thêm"* rồi tân ngữ ngoài danh sách (*khoảng 2 câu*, *ví dụ*, *đáp án*, *nhiều/các/chục*…), và *năm/ba* trong danh sách cũng mang nghĩa khác (*"gì thêm năm nay"*). Test thời gian treo chứ không đỏ nếu lỗi hàm mũ quay lại (môi trường không có `pytest-timeout`) |
| **Không có đường nào soạn lại một ô `failed`**: *"soạn lại câu còn thiếu"* thành dàn ý soạn thêm, BE đánh số từ câu 6 (sau cả ô hỏng) còn lời model nói câu 4, bị trả về hai lần rồi `OUTLINE_REFUSED`; `_RETRYABLE` chỉ có `retry` -- case 02 thử tay pha 6 | Tier 2 câu 22: soạn lại ô hỏng tại chỗ, hay coi nó là một câu soạn thêm và bỏ ô hỏng. Cùng gốc: panel ghi *4 câu* mà đánh số Câu 1, 2, 3, **5** (`order_index` giữ khe của ô hỏng); và câu kết mời *"thử soạn lại câu còn thiếu"* trong khi không đường nào làm được (luật 4 của bộ ca) |
| **Hai câu cùng một dạng trong một mục, chỉ khác số**: câu 3 và 4 đều là $A\setminus B$ của hai tập hữu hạn -- case 07 thử tay pha 6 | Tier 2 câu 19 (định nghĩa gần trùng): lưới gần trùng so số liệu, không so dạng câu |
| **Câu biến thể pha 2 giữ nguyên bốn phương án của câu gốc**: *đồng biến* → *nghịch biến*, $2x+1$ → $-3x+5$, vẫn bốn khoảng cũ; `validate_retry` cho qua đúng luật -- ca 16 thử tay pha 6 | Tier 4: dặn model đổi cả phương án, hay so phương án ở `validate_retry`; đo trên nhiều câu trước khi đổi |
| **Thay một câu: brief cấm cả chính câu đang bị thay**, trong khi `harvest` miễn câu ấy khỏi lưới gần trùng (`drafting.py` `replace`, `_refire`) -- giáo viên thay câu 3 bằng một mục vẫn giữ bài cũ thì brief vừa bảo dùng công thức ấy vừa bảo dùng số liệu khác -- review code vòng 12 | Tier 2 câu 23: câu thay có được giữ bài cũ không. Được → bỏ câu cũ khỏi `banned_stems` khi `replace`; không → bỏ miễn trừ ở `harvest` |
| **Bộ đếm `outlines_refused` không về 0 sau một bước tra cứu** (khác `stuck`/`refused`): trả về 2 lần, model `read_section`, lần 3 là dừng -- review code vòng 12 | Tier 4: chủ ý (*một lượt, lý do gì cũng tính*); chỉ ghi, xem lại nếu thử tay thấy dừng oan |
| **Một câu đã có dài hay nhiều dòng đi thẳng vào brief**: không trần độ dài mỗi câu, xuống dòng làm vỡ gạch `·` -- review code vòng 12 | Tier 4: cắt mỗi câu ~300 ký tự, gộp khoảng trắng |
| **Thiếu test hàng notice khi chạm trần 3 lần trả về dàn ý có cộng token nợ** (code đã đúng) -- review code vòng 12 | Tier 4 |
| **Dàn ý lưu `brief` rỗng khi không có dàn ý trước nào để lấp** (4/7 dàn ý ở thử tay pha 6: 01, 04, 07 cả hai bản): Haiku để trống `known` khi nêu dàn ý; bản vá pha 1 chỉ lấp từ một dàn ý trước có `brief`, mà 01, 04, 07 không có (dàn ý đầu của 02 và 03 thì có, nên hai ca ấy qua `_approved_plan`). *"oke"* khi ấy không qua `_approved_plan` -- plan là của model, đúng hay sai tuỳ model -- chấm biên bản pha 6 | Tier 2 câu 24: lấy môn/khối/phạm vi từ đâu khi không có `brief` nào để lấp. A từ chối dàn ý thiếu `brief` (thêm một lượt gọi) · B `_approved_plan` lấy chúng từ `create_draft` model vừa nêu · C BE ghi `brief` từ `create_draft` đầu tiên |
| **Chữ câu luật**: pha 1 bẻ dòng để lại *"làm."* một mình (review ảnh pha 2); *"có thể nộp lúc 18:01"* nên là *"nộp muộn nhất lúc"*, *"bị DỪNG"* viết hoa như hét (review ảnh pha 4); khối ĐÃ PHÁT HÀNH **thiếu ngày khi qua nửa đêm** (*"Chữa bài tới hết 01:20"*, màn học sinh ghi *"01:20 · 18/10"*), gạch ` - ` lạc kiểu với `—` của tiêu đề -- chấm ảnh pha 6 | Tier 2 câu 17: chữ của `publication_wording` là nguyên văn ADR-03; đổi ở BE, FE `fill()`, ADR-03 và bốn chỗ Figma |
| **Thông báo `OUTLINE_REFUSED` bảo giáo viên nói lại** (*"Bạn thử nói lại cụ thể hơn: phạm vi, số câu, dạng câu"*) trong khi lỗi nằm ở model -- chấm ảnh pha 6 | Tier 4: chữ của thông báo hệ thống; đổi cùng `PLAN_REFUSED` nếu đổi |
| **Lời model lệch nhẹ ở thử tay pha 6**: nút *Khối 6–9* và *Số học/Hình học/Đại số* khi giáo viên dạy lớp 11 (01); *"Đề có 4 câu, mỗi câu một mục"* khi chỉ có 3 mục (03 bản 1); `\text{tổng tiền}` trong công thức (03 bản 2); câu kết *"đề thiếu câu sẽ không dùng được"* (02); bản 2 tự đổi công thức mục 3–4 sang $A\setminus B$ không ai xin, nên câu 3 và 4 cùng phép hiệu (07) -- chấm ảnh pha 6 | Tier 4: hành vi model, chỉ ghi |

## Lộ ra khi viết chương 7 của báo cáo

Ghi ngày 16/10/2026, plan `2026-10-16-report-service-chapter-plan.md`. Ba subagent khảo sát
`backend`, `agent`, `document`, và năm lần review đọc lại code từng câu; những thứ dưới đây là sự
thật code mà báo cáo đã tả đúng hiện trạng, hay chỗ tài liệu nói sai mà plan ấy không được sửa.

### Lưới yếu hơn tên của nó

| Việc | Cái gì đang chặn |
| --- | --- |
| **Check `timeout-order` không tính mô hình dự phòng** (`agent/llm.py:106-107`: mỗi lần thử có thể chạy hai mô hình nối nhau) **và số lần thử lại mặc định của SDK OpenAI** (`max_retries` không đặt) | **Tier 2: tính đủ lần thử lại của SDK thì check đỏ (3 + 20 × 3 × 3 = 183 s so với 70 s); bỏ thử lại SDK hay nới ngân sách là quyết định** (plan `backlog-tier-1`, pha 4). Không bị chặn; chưa làm |
| **Lời đồng ý dàn ý chỉ được đọc trong `agent`** (regex `_AGREES`, `graphs/propose.py:820-824`). `guard_drafting` chứng minh được dàn ý đã hiện ở lượt hội thoại ngay trước, không chứng minh được giáo viên đã đồng ý | Chưa quyết `backend` có cần tự đọc lời đồng ý không |

### Luật chưa ép

| Việc | Cái gì đang chặn |
| --- | --- |
| **Câu biến thể giữ cấu trúc của câu gốc (ADR-17):** ngoài các phép kiểm chung, chỉ có phép so đề bài; không gì so cấu trúc | Đã có dòng *"chưa ép"* trong `AGENTS.md`; chưa làm |
| **Đóng tab giữa một lượt hội thoại thì lượt ấy không có lời kể lại** (ADR-25) | Chưa làm |
| **Chương 04 (`04:121-123`) nói giáo viên xem được báo cáo *"giải thích chưa rõ"* của học sinh**, nhưng `backend` chỉ có đường ghi `file_report`; không api hay tool nào đọc bảng `reports` | Chưa làm |

### Tài liệu nói sai về code, ngoài phạm vi plan báo cáo

| Việc | Cái gì đang chặn |
| --- | --- |
| **ADR ghi trạng thái cũ:** ADR-15, 16, 18, 21, 27 vẫn ghi *"chưa thi hành"* hay *"chưa có ở backend"*; ADR-23:114 trỏ `propose._SYSTEM`, nay là `_CORE`; ADR-25 (sửa 10/10) định bỏ job kể lại, code vẫn chạy nó; ADR-27 nói Jev là bộ định tuyến của `document`, đã bị thay ngày 12/10; ADR-29:68 nói lời đồng ý đọc bằng mô hình, thực ra bằng regex | Sửa một ADR là sửa lịch sử, nên đường đúng là một dòng hậu ký có ngày. Đã có hậu ký 17/10/2026 cho ADR-15, 16, 23, 27, 29 (plan `backlog-tier-1`, pha 4); còn ADR-18, 21, 25 |
| **ERD chưa vẽ**, dù điều kiện cũ trong `architecture.md` (*"khi có Postgres"*) đã đạt | Chưa quyết có cần: `data-model.md` đang nói hai mươi hai bảng bằng bảng và lời |

### Báo cáo

| Việc | Cái gì đang chặn |
| --- | --- |
| **Hình `activity-overview` ở chương 04 vượt trang 23,8 pt** (`Float too large`, có từ trước plan này) | **Việc của phiên báo cáo (docs/report), rời Tier 1** (plan `backlog-tier-1`, pha 4). Ngoài phạm vi plan chương 7 |
| **Chữ *"pha"* lệch giữa hai tài liệu:** từ điển của báo cáo dành *"pha"* cho lượt hội thoại giáo viên và *"giai đoạn"* cho bài làm học sinh, còn `architecture.md` và các ADR dùng *"pha 1/pha 2"* cho học sinh | Chưa quyết bên nào đổi |
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
| **"Hàm" mang hai nghĩa trong chương 07.** Từ lượt viết lại mục Agent, phần của graph gọi là *hàm*, theo mục *Graph* của từ điển; *hàm nhận job* (chỗ worker gọi vào) cũng là "hàm". Đã ghi ở *Những chỗ đã biết là còn sai* của `rules.md` | Người dùng giữ *hàm nhận job* và sẽ tự chọn chữ khác |
