# Figma giai đoạn 2 — dựng bề mặt học sinh

> **Không bắt đầu** trước khi cổng đo của
> [2026-09-10-publish-form-and-question-cards-plan.md](2026-09-10-publish-form-and-question-cards-plan.md)
> xanh. Bốn màn dưới đây hiển thị những con số mà biểu mẫu phát hành sinh ra.

## Goal

Bốn màn hình học sinh tồn tại trong Figma, phủ hết UC-03, UC-04, UC-06 và UC-07, và không màn nào phá
một ADR đang có hiệu lực.

## Bối cảnh

Mười một artboard hiện có đều là bề mặt giáo viên. `Density` đã có sẵn mode **Student** và đang chạy
thật: `Student result — chờ giáo viên` (`6:50`) giải ra `type/body 16` và `space/card-padding 24`, so
với `70:314` giải ra `type/label 13`, `type/caption 11` ở mode Teacher. Nên đây không phải việc thêm
mode mới vào design system — chỉ là việc đặt đúng mode cho artboard mới.

Cần nói ra một điều để người đọc sau không hiểu nhầm: **toàn bộ pha 2 đang bị chặn bởi hạ tầng**
(`docs/plans/backlog.md`, ADR-09 cho kết quả sống một giờ). Dựng thiết kế đi trước backend là thông lệ
của dự án, nhưng bốn màn này **không phải bằng chứng dữ liệu đã có**.

## Scope

**Trong:** trang `Screen — Student`; tám component mới; variant giọng học sinh cho bốn component đang
là giọng giáo viên; bốn artboard; sửa [ADR-10](../../decisions/adr-10-pham-vi-dot-dau.md).

**Ngoài:** artboard 10 và 11 phía giáo viên; chỗ giáo viên đọc báo cáo *giải thích chưa rõ*; màn
`Bảng theo dõi`; code và contract.

## Bốn màn

| Artboard | Phục vụ | Ghi chú |
| --- | --- | --- |
| `12 · Danh sách bài của tôi` | màn chủ | tám trạng thái, xem dưới |
| `13 · Làm bài` | UC-03, **và câu biến thể của UC-06** | hai chế độ: pha 1, và lượt |
| `14 · Kết quả bài làm` | UC-04 | **hai state**: *đã nộp, cần chữa* và *đã hoàn thành* |
| `15 · Chữa bài` | UC-04, UC-07 | chat trái + panel phải, **không tính giờ** |

Artboard 14 mang **hai hình dạng dữ liệu khác nhau**, không phải một hình dạng với vài trường rỗng —
ADR-14 chốt *đã nộp* và *đã hoàn thành* không thay nhau được, và ADR-16 chốt điểm sau khi nộp là **sàn**.
Dựng thành hai state của cùng artboard, mỗi state một khung riêng.

### Tám trạng thái của `Assignment row`

`chưa tới giờ mở` · `đang mở, chưa làm` · `đang làm dở` · `đã nộp, đang chấm` · **`đã nộp, cần chữa`** ·
`đã hoàn thành` · `quá hạn vào` · `hết hạn pha 2 khi chưa chữa xong`.

Khuôn chung, chốt trước khi dựng để tám trạng thái không thành tám thiết kế rời: **một chip trạng thái,
một hành động chính, phần còn lại là chữ.** Hàng nào cũng hiện **cả hai hạn** — hạn vào của pha 1 và
hạn kết thúc của pha 2.

## Component

**Tám cái mới:** `Student top bar` · `Assignment row` · `Option` · `Question nav` · `Time status` ·
`Score mark` · `Result row` · `Report control`.

`Time status` gộp ba thứ vốn loại trừ nhau trong cùng một khe: **đồng hồ đang chạy** (pha 1 và trong
lượt), **không tính giờ** (phần giải thích), và **cảnh báo lượt sẽ bị cắt**. Tách rời sẽ đẻ ra hai
component tranh nhau một chỗ trên màn Chữa bài, và cái thứ ba thì không có nhà.

**Bốn component cần variant giọng học sinh** — đây là việc thật, không phải "dùng lại":
`Consequence dialog` (`11:41`, hiện là *Phát hành đề kiểm tra?*), `Empty state` (`6:65`),
`Error state` (`6:75`), `Button` (`6:20`).

**Dùng lại nguyên:** `Message turn` · `Thinking` (`83:76`) · `Kriky state` (`234:1180`) ·
`Assistant thinking` (`222:59`) · `Async waiting` (`6:49`) · `Question card` (component do giai đoạn 1
tạo ra).

**Không dùng:** `Confidence meter` (`5:32`), `Review reason` (`5:53`), `Student result — chờ giáo viên`
(`6:50`) — cái cuối vì đợt này bỏ confidence của chẩn đoán nên trạng thái đó không tồn tại.

## Ba bề mặt bắt buộc mà dễ quên

**Cửa một chiều *Làm bài mới*** — [ADR-15](../../decisions/adr-15-thoi-gian-pha-hai.md) đòi giao diện
nói trước rằng lượt có thể bị cắt, **ngay tại nút**, kèm số phút còn lại thật. Hai trạng thái: lượt
lọt trong hạn, và lượt dài hơn phần hạn còn lại. Đây là variant của `Consequence dialog` cộng một
variant của `Time status`.

**Báo cáo *giải thích chưa rõ* ở cả hai thời điểm** — [ADR-19](../../decisions/adr-19-bao-cao-giai-thich-chua-ro.md)
chốt hai mốc: trong lúc chữa (trên artboard 15) và sau khi bài của **chính em đó** kết thúc (trên
artboard 14, state *đã hoàn thành*). Một component `Report control`, đặt ở hai chỗ.

**Danh tính và đăng xuất** — không có màn đăng nhập, và
[ADR-13](../../decisions/adr-13-lop-va-tai-khoan-hoc-sinh.md) chốt *mọi màn hình chạm tới học sinh phải
trả lời câu ai đọc được cái này*. Sản phẩm chỉ chạy trong phòng máy, tức máy dùng chung. `Student top
bar` mang **họ tên · lớp · mã học sinh · Đăng xuất**, và có mặt trên cả bốn màn. Mục nợ về việc không
có chỗ bắt đổi mật khẩu phải được xác nhận lại là **vẫn còn nguyên** sau đợt này.

## Lý do được 0,5 — hoãn công khai

ADR-16 chốt học sinh nhìn thấy **lý do** một câu được 0,5. `backlog.md` đã ghi lời hứa đó chưa có nguồn
dữ liệu: `GradingCompleted` nhận được `score = 0.5` nhưng không trường nào mang *vòng thứ mấy* hay *câu
gốc nào*. Đợt này **dựng chỗ cho nó** trên `Score mark` (một hàng phụ dưới con số) với chữ mẫu, và ghi
rõ trong mô tả component rằng dữ liệu chưa tồn tại. Im lặng là cách tệ nhất trong ba cách.

## Files

| Node / file | Việc |
| --- | --- |
| Trang `Screen — Student` | tạo mới |
| Tám component mới | tạo trên trang `Components` |
| `Consequence dialog`, `Empty state`, `Error state`, `Button` | thêm variant giọng học sinh |
| Bốn artboard `12` … `15` | tạo mới, 1440×900, Density **Student**, không rail |
| `docs/decisions/adr-10` | mở rộng *chỉ giáo viên*; cập nhật *Nơi thi hành* |
| `docs/decisions/README.md` | mục *Nguồn thiết kế*: số artboard và tên trang |
| `docs/plans/backlog.md` | xác nhận lỗ đăng nhập còn nguyên; lý do 0,5 chưa có dữ liệu |

## Ordered Tasks

- [ ] **Kiểm sáu component dùng lại ở Density `Student` trước khi dựng gì.** Đổi mode làm `type/body`
      14→16 và `card-padding` 16→24; component nào có chiều cao cố định sẽ tràn chữ.
- [ ] **Đọc lại mô tả từng component dùng lại và kiểm *luật*, không chỉ kiểm hình học.** ADR-10 đòi
      *dùng lại hình dạng thì được, dùng lại lý lẽ thì không*.
- [ ] Chốt khuôn chung cho `Assignment row` và liệt kê tám trạng thái.
- [ ] Dựng `Student top bar`, `Time status`, `Score mark`, `Report control` — bốn cái mang luật nặng nhất.
- [ ] **Dựng trọn artboard `13 · Làm bài` đầu tới cuối**, gồm cả chế độ lượt. Đây là màn kiểm chứng.
- [ ] Dựng bốn component còn lại và ba artboard còn lại.
- [ ] Thêm variant giọng học sinh cho bốn component của giáo viên.
- [ ] Sửa ADR-10; cập nhật `README.md` và `backlog.md`.
- [ ] Chụp cả bốn artboard; xem lại bằng mắt.
- [ ] Gọi 1 subagent review. Sửa theo phát hiện, hoặc phản bác có lý do.
- [ ] `.\dev.ps1 check`; link Markdown; LF; `AGENTS.md` vẫn 170 dòng.

## Validation Checks

- Bốn artboard đúng **1440×900**, chân nội dung đúng y=900, Density mode **Student**.
- Không artboard học sinh nào có rail.
- `Student top bar` có mặt trên cả bốn, mang họ tên · lớp · mã học sinh · Đăng xuất.
- `Time status` có đủ ba variant, và **variant cảnh báo cắt lượt không dùng hổ phách, không dùng đỏ**.
  Hổ phách nghĩa là *cần người* và đỏ nghĩa là *hỏng*; một lượt sắp bị cắt không phải cái nào
  ([ADR-12](../../decisions/adr-12-mau-va-hinh-anh-ma-hoa-luat.md)). Đây là đúng cái bẫy `backlog.md`
  đã cảnh báo cho mức 0,5, tái diễn ở chỗ thứ hai.
- `Score mark`: mức **0,5 không được cấp màu mới**; mức 1 và 0 dùng token đã có, trong đó 0 dùng
  `answer/incorrect` vì ADR-12 khoá đỏ vào *đáp án của học sinh sai*. Và cả ba phải phân biệt được khi
  bỏ màu đi.
- `Countdown` trong `Time status` **không có** trạng thái đỏ ở bất kỳ mốc nào.
- Không màn nào hiện `confidence`, `misconception_code`, hay lý do review (ADR-08).
- Artboard 14 có **hai state** riêng biệt, không phải một state với trường rỗng.
- `Report control` có mặt ở cả artboard 14 (state *đã hoàn thành*) và artboard 15.
- Nút *Làm bài mới* có khối đọc lại giá trị thật, và có trạng thái cảnh báo khi lượt dài hơn hạn còn lại.
- Mọi màu lấy từ biến; không hex thô.

## Decision Records

### Decision: Câu biến thể dùng lại màn Làm bài

options considered: đặt câu biến thể trong panel phải của màn Chữa bài; dùng lại artboard `13 · Làm bài`
ở một chế độ thứ hai.

selected option: dùng lại màn Làm bài.

reason: trải nghiệm trả lời câu biến thể phải **giống hệt** pha 1, vì đó chính là thứ làm 0,5đ có nghĩa
theo ADR-16 — *làm được trên dữ kiện mới*. Đặt nó trong khung chat biến nó thành một phần của cuộc trò
chuyện, và làm nhoè đúng ranh giới mà ADR-16 vừa dựng lên. Nó cũng tránh dựng hai bề mặt trả lời.

### Decision: Gộp đồng hồ, không-tính-giờ và cảnh báo-cắt vào một component

options considered: ba component rời; một component `Time status` ba variant.

selected option: một component ba variant.

reason: ba thứ này loại trừ nhau và tranh cùng một khe trên màn hình — không lúc nào hai cái cùng đúng.
Tách rời thì màn Chữa bài có hai component cùng đòi chỗ, và cảnh báo cắt lượt (thứ ADR-15 bắt buộc phải
có) không có nhà nên rất dễ bị bỏ quên. Một component ba variant làm việc "chỉ một cái hiện tại một
thời điểm" thành bất biến của component thay vì kỷ luật của người dựng.

### Decision: Artboard học sinh sang trang riêng

options considered: nối tiếp trên `Screen — Chat`; trang mới `Screen — Student`.

selected option: trang mới.

reason: bốn màn này không có cột chat và không có rail, nên để chung thì tên trang `Screen — Chat`
thành sai. Tách trang còn giữ cho một câu của ADR-10 kiểm được bằng mắt thay vì bằng trí nhớ.

## Rủi ro

**Density `Student` làm vỡ component dùng lại.** Sáu component sẽ dùng lại đều được dựng và căn ở
`Teacher`. Đây là lý do task đầu tiên là kiểm, không phải dựng.

**Trang mới không tự mang mode.** Biến `Color` và `Space` là cấp file nên sang được, nhưng **mode được
giải theo node**, nên trang mới sẽ về mode mặc định của collection. Phải đặt `Density=Student` tường
minh trên từng artboard, và kiểm bằng `get_variable_defs` chứ không bằng mắt.

**Dựng tám component rồi mới đặt lên artboard là phát hiện lỗi ở lần cuối.** Vì thế thứ tự là: kiểm cái
dùng lại → dựng bốn component mang luật nặng → dựng trọn **một** màn → rồi mới nhân ra.

**Bốn màn này là thiết kế đi trước backend.** Không có gì trong Redis sống quá một giờ, nên mọi trạng
thái pha 2 trên bốn artboard là dữ liệu mẫu. Phải ghi vào mô tả artboard, nếu không người sau sẽ đọc
chúng như bằng chứng rằng dữ liệu đã có.

## Status

Chưa bắt đầu. Đang chờ duyệt.
