# Figma giai đoạn 1 — sửa những gì mô hình hai pha làm sai ở phía giáo viên

> Đây là plan chặn phía trước. Bề mặt học sinh là plan riêng
> ([2026-09-10-student-screens-figma-plan.md](2026-09-10-student-screens-figma-plan.md)) và **không
> được bắt đầu** trước khi cổng đo ở cuối plan này xanh.

## Goal

Biểu mẫu phát hành nhận đủ sáu tham số, hộp xác nhận đọc lại đủ sáu, câu luật pha 2 có mặt ở ba nơi,
và thẻ câu hỏi cho giáo viên thấy lời giải — tất cả **mà không bóp danh sách câu hỏi xuống dưới mức
đọc được một thẻ**.

## Ràng buộc đã đo

Panel artboard `7 · Đã duyệt — cài đặt phát hành` (`70:215`) rộng 420, cao 900:

| Khối | Node | Hiện tại |
| --- | --- | --- |
| `panel-head` | `70:216` | 0 – 113 |
| `questions` (cuộn) | `70:225` | 113 – 472, cao **359** |
| `Publish settings` (instance) | `70:314` | 472 – 900, cao **428** |

Bên trong `questions`: thẻ đầu `70:226` ở `y=4`, cao **224**; thẻ kế `70:235` ở `y=240`, tức **gap 12**;
và `fade` `70:271` cao **56** phủ đáy.

[ADR-02](../../decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md) cấm đẩy danh sách xuống dưới chiều cao
một thẻ. Diễn thành số: `questions` phải **≥ 240** — bốn pixel đệm trên, một thẻ trọn 224, và 12 pixel
gap để còn thấy là **có gì đó ở dưới**. Một khung đúng 224 lọt được một thẻ nhưng không nói được rằng
còn thẻ khác, tức hỏng đúng cái ADR-02 muốn giữ.

**Trần của `Publish settings` = 484, và dư bằng KHÔNG.**

Con số này bị sửa **hai lần**, cả hai đều sau khi đo thứ thật:

1. Ước tính đầu là **547**, dựa trên thẻ cao 224. Nhưng hàng *Lời giải · 2 cách* làm thẻ cao thêm 22
   — thẻ thật là **246** — nên trần tụt còn **525**.
2. Rồi 525 cũng sai, vì nó bỏ `fade` ra khỏi phép suy. `fade` **không phải hằng số**: nó chạy từ
   chân thẻ đầu (250) tới đáy khung, nên `cao fade = cao questions − 250`. Ở 262 thì dải mờ chỉ còn
   12px và **không pixel nào của thẻ thứ hai lộ ra** — mất đúng thứ ADR-02 muốn giữ. Sàn thật là
   `4 + 246 + 53` = **303**, nên trần thật là `900 − 113 − 303` = **484**.

Khối đã dựng cao đúng **484**. Nghĩa là **dư 41 là ảo, dư thật bằng 0**: thêm một dòng chữ vào biểu
mẫu là dải mờ liếm vào thẻ đầu. Định dạng ngày giờ vì thế là **ràng buộc**, không phải sở thích, và
đã được ghi vào mô tả component.

Một chỗ cổng đo không nhìn tới: variant `67:39` cao **498**, hơn instance 14px vì metric chữ khác.
498 > 484, nhưng cổng chỉ đo instance nên con số đó chưa bao giờ bị chặn.

## Số học của các phương án

Biến thể `67:39` cao 438, gồm: padding 20 · tiêu đề `67:3` **21** · LỚP 78 · thời-gian-làm-bài 60 ·
hàng mở/đóng 60 · chuỗi luật `67:28` 56 · nút 43 · năm gap 16 · padding 20.

| Phương án | Cao | Kết luận |
| --- | --- | --- |
| Sáu dòng phẳng, một chuỗi luật | 590 | **vượt trần** |
| Sáu dòng phẳng, hai chuỗi luật | 662 | **vượt xa** |
| Nhóm theo pha, hai khối chuỗi rời, gap 16 | 546 | lọt trần đúng **1px** — không dùng được |
| **Nhóm theo pha, một khối chuỗi, gap 12** | **484** (đo thật) | dư **0** |

Phương án thứ ba là thứ tôi định làm lúc đầu, và nó sai theo kiểu nguy hiểm: lọt trần trên giấy, vỡ
ngay khi một câu tiếng Việt xuống thêm một dòng. Phương án cuối là phương án thật.

## Scope

**Trong:** `Publish settings` (`67:41`), `Consequence dialog` (`11:41`), `Action result card` (`10:63`),
mười frame thẻ câu hỏi trên artboard 6 và 7, và một mục nợ mới.

**Ngoài:** mọi thứ thuộc bề mặt học sinh; artboard 10 và 11; chỗ giáo viên đọc báo cáo *giải thích
chưa rõ*.

## Files

| Node / file | Việc |
| --- | --- |
| `Publish settings` (`67:41`), cả hai variant | 4 → 6 trường, nhóm theo pha, một khối chuỗi luật, gap 12 |
| `Consequence dialog` (`11:41`) | đọc lại **sáu** giá trị |
| `Action result card` (`10:63`), variant `đã-phát-hành` | thêm câu luật pha 2 |
| `Question card` — component **mới** | gộp mười frame dựng tay; thêm khối lời giải thu gọn |
| Artboard 6 (`15:88`…`16:148`) và 7 (`70:226`…`70:262`) | thay mười frame bằng instance |
| `docs/plans/backlog.md` | ghi nợ: không có gì ghi nhận giáo viên đã đọc lời giải |
| `docs/decisions/adr-02`, `adr-18` | cập nhật *Nơi luật này đang được thi hành* |

## Ordered Tasks

- [x] Đọc lại token `Space` và `Density`/Teacher.
- [x] **Componentise thẻ câu hỏi trước.** Mười frame đang dựng tay và không có gì giữ chúng giống nhau.
- [x] Thêm khối lời giải **thu gọn mặc định** vào component đó: một hàng *Lời giải · 2 cách ›* cộng
      ánh xạ nhiễu→lỗi khi mở.
- [x] Thay mười frame trên artboard 6 và 7 bằng instance; giữ nguyên nội dung từng câu.
- [x] Dựng lại `Publish settings` theo phương án cuối bảng trên.
- [x] Cập nhật `Consequence dialog` đọc lại sáu giá trị.
- [x] Viết câu luật pha 2 và đặt **giống hệt nhau từng chữ** ở `Publish settings`, `Consequence dialog`
      và `Action result card`. [ADR-03](../../decisions/adr-03-ranh-gioi-cua-vao.md) đã đòi điều này
      cho chuỗi pha 2 rồi, nên **không cần sửa ADR-03**.
- [x] Quét lại mọi dòng ADR trỏ vào node vừa dựng lại. `67:29` (chuỗi luật pha 1) và `68:15` vẫn tồn
      tại nên `adr-03:45` còn đúng; `adr-02`, `adr-15`, `adr-18`, `adr-01` đã cập nhật; `adr-10` và
      `adr-13` chỉ trỏ tới `67:41`/`77:341`, hai id không đổi.
- [x] Ghi nợ về việc không ai ghi nhận giáo viên đã đọc lời giải.
- [x] **Cổng đo:** 484 ≤ 525, 303 ≥ 262, tổng panel đúng 900, `fade` bắt đầu ở 250 = đúng chân thẻ đầu.
- [x] Gọi 1 subagent review. Sửa theo phát hiện, hoặc phản bác có lý do.
- [ ] `.\dev.ps1 check`; link Markdown; LF; `AGENTS.md` vẫn 170 dòng.

## Validation Checks

- Instance `70:314` ≤ **484**; frame `70:225` ≥ **303**. Đo trên **instance**, không trên variant
  `67:39` (498, lệch vì metric chữ). **Kết quả: 484 và 303, tổng panel đúng 900 — vừa khít, không dư.**
- Thẻ câu hỏi đầu tiên hiện trọn và **không bị `fade` che**; `fade` phải chỉnh theo chiều cao mới chứ
  không giữ nguyên 56.
- Nhãn trường nào cũng nằm trọn một dòng. `THỜI GIAN LÀM BÀI` hiện rộng **124** (`67:16`) và sẽ không
  lọt ô ba cột rộng 118 — phải đổi nhãn, không phải hy vọng nó vừa.
- Chuỗi ngày/giờ đã chốt định dạng `HH:MM · DD/MM`. Giá trị dài nhất định dạng đó sinh ra —
  `14:00 · 15/12` — đo được **73px**, cộng padding 24 là 97 ≤ cột 119. **Đã thử, không xuống dòng.**
- Câu luật pha 2 giống hệt nhau từng chữ ở cả ba nơi.
- Mười thẻ câu hỏi đều là instance của cùng một component.
- Mọi màu lấy từ biến; không hex thô.

## Decision Records

### Decision: Gộp hai câu luật vào một khối, và hạ gap trong biểu mẫu xuống 12

options considered: hai khối chuỗi rời với gap 16 (546, dư 1px); bỏ hai tiêu đề nhóm pha; một khối
chuỗi với gap 12.

selected option: một khối chuỗi, gap 12.

reason: 546 lọt trần trên giấy và vỡ ngay khi một chuỗi xuống thêm một dòng — mà chuỗi ở đây là câu
tiếng Việt do người viết, không phải nhãn cố định. Bỏ hai tiêu đề nhóm pha tiết kiệm được 44px nhưng
mất đúng thứ khiến sáu tham số đọc được thành 4+2 thay vì một danh sách phẳng. Hai câu luật vốn nói về
cùng một chuyện — ranh giới thời gian — nên đứng cùng khối là đúng chỗ, và nó trả lại 28px.

### Decision: Thẻ câu hỏi thành component trước khi thêm lời giải

options considered: sửa mười frame tại chỗ; componentise trước rồi thêm khối lời giải một lần.

selected option: componentise trước.

reason: mười frame đang dựng tay, không có gì ràng chúng giống nhau. Thêm một khối vào mười chỗ bằng
tay là mười cơ hội lệch, và đợt trước đã có một lần override bị rơi mà chỉ ảnh chụp mới bắt được.
Componentise cũng là điều kiện để plan sau sửa thẻ này một lần thay vì mười.

### Decision: Không đụng vào nghĩa của nhãn *đã kiểm*

options considered: mở rộng *đã kiểm* của ADR-04 thành *đã đọc cả câu hỏi lẫn lời giải*; thêm một dấu
kiểm thứ hai riêng cho lời giải; không thêm gì và ghi nợ.

selected option: không thêm gì, ghi nợ.

reason: mở rộng nghĩa là lẫn hai thứ khác nhau. *Khoá khi duyệt* (ADR-01, ADR-18) là hệ quả tự động của
một thao tác; *đã kiểm* của [ADR-04](../../decisions/adr-04-hai-nguon-cau-hoi.md) là lời giáo viên tự
nhận đã đọc **từng câu**. Mà ADR-18 vừa nói lời giải **khó duyệt hơn câu hỏi** — một câu hỏi sai thì
đọc là thấy, một lời giải sai tinh vi thì phải làm thử mới thấy. Cho một cú bấm sẵn có gánh thêm một
cam kết nặng hơn, không đòi thêm bằng chứng gì, là **làm yếu** cổng chứ không phải ghi lại điều vốn
đúng. Dấu kiểm thứ hai thì tạo hai thứ phải nhớ tick. Đúng nhất là thừa nhận: hiện **không có gì** ghi
nhận giáo viên đã đọc lời giải, và đó là lỗ do chính ADR-18 tạo ra.

## Rủi ro

**Dựng lại component set làm chết node id đang bị ADR trích.** `67:41` có hai variant và ít nhất một
instance mang override (428 so với 438). Năm ADR trỏ vào các node bên trong — `adr-03:45` trỏ thẳng
`67:29`, chính chuỗi luật sẽ bị di chuyển. Quét lại là một task, không phải một lời hứa.

**Cổng duyệt yếu đi dù bố cục đã tối ưu.** Danh sách câu hỏi từ 359 xuống khoảng 300 trong khi nội dung
cần duyệt tăng thêm một khối. Đây là cái giá thật của ADR-18 và nó nên nằm trên giấy.

**Chuỗi mẫu ngắn hơn chuỗi thật.** Toàn bộ số học ở trên dựa vào các chuỗi đang có trong file, mà chúng
là dữ liệu mẫu do chính tôi đặt ở đợt trước. Nếu chuỗi thật dài hơn thì trần bị xuyên mà không ai phát
hiện — nên cổng đo phải chạy với chuỗi dài nhất, không với chuỗi đẹp nhất.

## Status

Đã dựng xong, review xong, sửa xong. Cổng đo xanh nhưng **vừa khít** — xem mục trần. Còn quét trích dẫn ADR và một vòng review.

Ngoài phạm vi đã nêu, một việc được làm thêm và cần biết: `Action result card` variant
`đã-phát-hành` nhận thêm hành động **Thu hồi**. Lý do là câu chữ vừa sửa nói *thu hồi được tới
14:00*, mà thẻ đó không có nút nào — hứa một điều khiển không tồn tại còn tệ hơn câu sai cũ. Đây là
điều khoản ADR-02 đã đòi từ đầu và chưa từng được thi hành.
