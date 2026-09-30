# Business ADR Plan — Round Two

## Goal

Viết sáu ADR còn lại (`adr-07` … `adr-12`), gỡ `AssessmentType` khỏi contract, và đóng plan đợt một.

## Bối cảnh

Đợt một ghi sáu ADR nền tảng cho luồng **tạo và phát hành đề**. Vòng review đợt một chỉ ra hai thứ.

Thứ nhất: **bốn luật nghiệp vụ đang chạy trong code mà không tài liệu nào biết** — thứ tự ưu tiên lý do
review, phép so ngưỡng bao gồm, giá trị `0.7`, và hạn giữ kết quả một giờ. Chúng đã được ghi tạm vào
mục *Còn thiếu* của `docs/decisions/README.md`; đợt này trả nợ đúng bốn cái đó.

Thứ hai: tôi đã **đưa quyết định giao diện vào ADR nghiệp vụ** (ba màu pill, chiều cao khối chọn lớp,
thang màu confidence). Đợt này lọc theo đúng vạch đó, nên danh sách ADR ngắn hơn con số 14 ước ban đầu.

## Files

- `docs/decisions/adr-07` … `adr-12` — mới
- `docs/decisions/README.md` — bảng và mục *Còn thiếu*
- `packages/contracts/src/contracts/{enums,messages,__init__}.py` — gỡ `AssessmentType`
- `packages/contracts/tests/test_messages.py`, `services/agent/tests/test_handlers.py` — payload mẫu
- `services/fe/src/api.ts`, `docs/local-development.md` — thân request và ví dụ `curl`
- `docs/plans/active/2026-09-06-business-adr-plan.md` — chuyển sang `completed/`

## Không làm ADR, và vì sao

Phần này quan trọng ngang danh sách ADR, vì nó giữ cho `docs/decisions/` không phình thành nơi chứa
mọi thứ.

- **Điều hướng rail** (không tab, đúng một vệt sáng, hội thoại xuất hiện khi gửi câu đầu) — thiết kế
  tương tác, không phải luật nghiệp vụ. Sống trong mô tả component `Rail destination`.
- **Hai mật độ Student/Teacher** — thiết kế, ở lại Figma.
- **Ràng buộc bộ gõ tiếng Việt** — kỹ thuật, ở lại mô tả `Composer`.
- **Adaptive practice** — đã có sẵn trong `business-workflows.md` và `use-case-specification.md`. Không
  phải "chưa ghi ở đâu", nên chưa cần ADR.

## Ordered Tasks

- [x] Đọc lại `docs/decisions/` và `review_policy.py` để lấy số dòng chính xác cho mục *Nơi thi hành*.
- [x] Viết `adr-07` … `adr-10` và `adr-12` theo khuôn `adr-00-template.md`.
- [x] Đọc lại từ Figma mọi node id và mọi câu được trích, thay vì viết theo trí nhớ.
- [x] Gỡ `AssessmentType` ở bảy chỗ; chạy `.\dev.ps1 test` sau khi gỡ.
- [x] Viết `adr-11` sau khi gỡ xong, để mục *Nơi thi hành* trỏ được vào thay đổi thật.
- [x] Cập nhật bảng và mục *Còn thiếu* trong `docs/decisions/README.md`.
- [x] Tick nốt checkbox và chuyển `2026-09-06-business-adr-plan.md` sang `docs/plans/completed/`.
- [x] Chạy `.\dev.ps1 check` và `.\dev.ps1 test`; kiểm link, kiểm LF, kiểm `AGENTS.md` vẫn 170 dòng.
- [x] Gọi 1 subagent review.
- [x] Sửa theo phát hiện, hoặc phản bác có lý do.

## Decision Records

### Decision: Delete `AssessmentType` Rather Than Wire It Up

options considered: giữ enum và thêm trường chọn loại bài vào màn hình phát hành để nó có đường nhập dữ
liệu; giữ enum, đánh dấu deprecated và để đó; xoá hẳn khỏi contract.

selected option: xoá hẳn.

reason: enum nằm sai tầng, không chỉ nằm không. Loại bài là thuộc tính của **đề**, quyết lúc soạn; đặt
nó trên `GradingRequested` bắt mỗi bài làm mang theo một sự thật thuộc về đề, và bắt mọi client nhớ
điền đúng. Wire nó lên nghĩa là đóng đinh chỗ sai đó vào giao diện. Deprecate mà giữ lại thì vẫn còn
nguyên tác hại chính: người đọc contract tưởng luật đã được xử lý. Gỡ được an toàn vì `model_config`
chỉ đặt `frozen=True`, không `extra="forbid"`, nên pydantic bỏ qua trường lạ và client cũ không vỡ.

### Decision: Write `adr-11` After The Code Change, Not Before

options considered: viết cả sáu ADR rồi mới sửa code; gỡ code trước rồi viết `adr-11`.

selected option: gỡ trước, viết sau.

reason: đợt một mắc đúng lỗi ngược lại ở năm chỗ — mục *Hệ quả* bị dùng như danh sách việc-phải-làm,
rồi việc làm xong ngay trong cùng commit, khiến ADR mô tả sai trạng thái repo kể từ ngày đầu. Viết
`adr-11` sau khi gỡ làm mục *Nơi luật này đang được thi hành* trỏ vào thay đổi có thật, kiểm chứng được
bằng `git diff`.

### Decision: Verify Every Figma Citation Against The File

options considered: viết mục *Nơi thi hành* theo node id nhớ được từ hội thoại; đọc lại từng node và
từng câu trích từ file trước khi viết.

selected option: đọc lại.

reason: mục *Nơi thi hành* là mục duy nhất phân biệt một ADR với một ý kiến, nên một tham chiếu sai ở
đó tệ hơn không có mục. Lần đọc lại bắt được hai lỗi thật: khối asset bị loại là `46:119` chứ không
phải `46:121` (đó là node chú thích bên trong), và nó chứa **sáu** asset chứ không phải ba.

### Decision: An ADR Must Name The Code That Currently Breaks It

options considered: mục *Nơi luật này đang được thi hành* chỉ liệt kê chỗ luật **đang được giữ**; mục
đó phải liệt kê cả chỗ luật **đang bị phá**.

selected option: liệt kê cả hai.

reason: vòng review bắt được ba ADR mô tả sản phẩm đẹp hơn code đang chạy — ADR-08 (`routes.py` trả một
hình dạng duy nhất, `App.tsx` hiện điểm cho kết quả cần review), ADR-09 (`api.ts` ném timeout ra như
lỗi), ADR-12 (`App.tsx` dùng đỏ thô). Cả ba mục *Nơi thi hành* đều im lặng về phản ví dụ nằm ngay
trong repo. Đó là **cùng căn bệnh đợt một** mặc áo khác: ADR mô tả một trạng thái không có thật. Một
mục chỉ kể phần đang đúng biến ADR thành quảng cáo; kể cả phần đang sai mới làm nó thành thứ kiểm
chứng được. Trạng thái `đã chốt, chưa thi hành` trong `adr-00-template.md` đã có sẵn cho tình huống
này và nay được dùng đúng ở ADR-08.

## Validation Checks

- `.\dev.ps1 check` và `.\dev.ps1 test` đều xanh (24 test: 20 pytest + 4 vitest).
- `grep -rn "AssessmentType\|assessment_type"` chỉ còn khớp trong `adr-11`, `docs/decisions/README.md`
  và plan này.
- `AGENTS.md` vẫn đúng 170 dòng.
- Mọi link nội bộ Markdown resolve.
- File mới và file sửa giữ **LF**.
- Nội dung file trong `docs/plans/completed/` không bị sửa (chuyển plan vào đó thì được).
- Mỗi ADR có đủ năm mục và một trạng thái hợp lệ theo `adr-00-template.md`.

## Rủi ro

**Rủi ro chính là lặp lại lỗi đợt một**: mục *Hệ quả* biến thành danh sách việc-phải-làm. Luật áp dụng
khi viết: mỗi dòng trong *Hệ quả* phải trả lời được câu *"cái gì trở nên khó hơn"* — nếu nó trả lời câu
*"phải sửa file nào"* thì nó thuộc về Ordered Tasks.

**Rủi ro thứ hai:** ADR-12 nói về màu, rất dễ trượt thành ghi chép design token. Nó chỉ được ghi những
ánh xạ mà **luật nghiệp vụ** áp đặt lên thiết kế. Chọn sắc độ nào là việc của design system.

**Rủi ro thứ ba:** ADR-07 chốt những con số đang là **placeholder**. `handlers.py` tự khai phần chấm sẽ
bị thay bằng lời gọi LLM thật, nên ADR nói rõ ngưỡng `0.7` là quyết định nghiệp vụ **còn hiệu lực sau
khi thay**, còn năm mốc confidence trong `handlers.py` thì không — chúng là dữ liệu giả.

## Status

Xong. Vòng review chỉ ra ba lỗi nghiêm trọng, tất cả đã sửa:

1. **ADR-07 bỏ sót hai điều kiện kích hoạt độc lập.** ADR mở đầu bằng `confidence <= ngưỡng` như thể
   đó là toàn bộ cổng, trong khi `review_policy.py:53-63` có hai điều kiện khác đẩy vào hàng đợi bất
   kể confidence cao tới đâu. Đã viết lại mục *Quyết định*.
2. **ADR-08 và ADR-09 mô tả sản phẩm đẹp hơn code đang chạy**, và mục *Nơi thi hành* im lặng về phản
   ví dụ. Đã thêm mục *Đang bị vi phạm ở code* với số dòng cụ thể, và đổi ADR-08 sang trạng thái ghép.
3. **ADR-12 chốt một luật màu mà chính file Figma đang phá.** Đọc lại `Error state` (`6:75`) cho thấy
   cả ba variant lỗi hệ thống dùng `answer/incorrect` — nên luật *"không trạng thái nào khác được dùng
   đỏ"* sai từ đầu. Đã viết lại: đỏ mang hai nghĩa dùng chung token, vạch thật nằm giữa *lỗi* và
   *cần-người*.

Ngoài ra: `adr-12` đổi tên thành `adr-12-mau-va-hinh-anh-ma-hoa-luat.md` (tên cũ hứa "tông giọng" mà
nội dung không có), gỡ ba con số pixel khỏi ADR-10, thêm liên kết chéo ADR-07 ↔ ADR-08, và sửa một
comment sai trong `.env.example` trỏ tới file test không tồn tại.

---

**Đóng ngày 2026-09-30** khi dọn `docs/plans/active/`. Người dùng xác nhận đã hoàn thành. Các ô
kiểm chứng máy móc được chạy lại tại thời điểm đóng: `.\dev.ps1 check` xanh 5/5. Những ô cần một
người xác nhận — vòng subagent review, manual test trên trình duyệt — tick theo xác nhận đó, và
bằng chứng là lời xác nhận chứ không phải một lần chạy tôi quan sát được.
