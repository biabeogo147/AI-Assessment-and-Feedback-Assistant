# ADR-11 — Bỏ `AssessmentType` khỏi contract

- **Trạng thái:** đã chốt (chỗ thu lời giải thích: đã có bề mặt ở Figma, contract chưa theo)
- **Ngày:** 2026-09-06

## Bối cảnh

`AssessmentType` khai hai giá trị `routine` và `high_stakes`, nằm trên `GradingRequested`, và đi xuyên
qua hàng đợi từ BE sang AGENT.

**Không một dòng nào đọc nó.** Không có bước chấm nào rẽ nhánh theo nó, không có luật review nào tham
chiếu nó, và màn hình phát hành trong thiết kế hiện tại không có trường nào để đặt nó — nên kể cả muốn
thi hành cũng chưa có đường nhập dữ liệu.

Nó tồn tại vì `business-workflows.md` phân biệt bài luyện tập với bài cuối kỳ. Sự phân biệt đó có thật.
Nhưng nó được cài vào **sai chỗ**.

## Quyết định

- **Bỏ `AssessmentType`** khỏi `packages/contracts` và khỏi mọi nơi dùng nó.
- Luật *"bài khó hoặc nhiều bước nên yêu cầu Student giải thích cách làm"* **vẫn còn hiệu lực**. Bỏ enum
  không bỏ luật.
- Khi luật đó cần thi hành, nó sẽ là một thuộc tính của **đề hoặc câu hỏi**, không phải một trường trên
  thông điệp chấm bài.
- **Cờ *đề này cần giải thích* vẫn là thuộc tính của đề hoặc câu hỏi**, đúng như dòng trên. Cái được
  chốt thêm ngày 2026-09-10 là **chỗ thu** lời giải thích: **hội thoại ở pha 2**, không phải một ô
  nhập ở pha 1. Hai chuyện khác nhau — một cái là *ai giữ luật*, cái kia là *hỏi học sinh lúc nào*.
  Xem [ADR-14](adr-14-hai-pha-lam-bai.md).

## Vì sao

Một trường mà không ai ghi và không ai đọc **tệ hơn là không có trường**: nó làm cho luật trông như đã
được xử lý. Người đọc contract thấy `assessment_type` sẽ tin rằng hệ thống đã phân biệt bài luyện tập
với bài cuối kỳ, và sẽ không hỏi tiếp.

Chỗ đúng của nó là đề, không phải submission. Yêu cầu giải thích được quyết lúc **soạn đề** — cùng lúc
với việc chọn câu hỏi và độ khó — chứ không phải lúc một bài làm đã nộp đi qua hàng đợi.

Và chỗ đúng để **thu** lời giải thích là pha 2, vì một ô nhập tuỳ chọn ở pha 1 là cái bẫy: học sinh
lười gõ bỏ trống thì `has_sufficient_evidence` thành sai, kết quả vào hàng đợi review, và theo
[ADR-08](adr-08-bon-loai-nghi-ngo.md) em đó **không nhận được gì cả** — bị phạt vì không gõ, và không
bao giờ biết vì sao. Hỏi sau, đúng câu em sai, không bị đồng hồ ép, cho bằng chứng tốt hơn và không
đặt bẫy nào. Đặt nó trên
`GradingRequested` nghĩa là mỗi bài làm phải mang theo một sự thật thuộc về đề, và mỗi client gọi API
phải nhớ điền đúng.

Gỡ được ngay và không gây vỡ vì `model_config` chỉ đặt `frozen=True`, không đặt `extra="forbid"` —
pydantic mặc định **bỏ qua** trường lạ, nên một client cũ vẫn gửi `assessment_type` thì request vẫn
được nhận.

## Hệ quả

- Contract **hẹp lại đúng một trường**, và sự phân biệt luyện tập / cuối kỳ mất chỗ trú trong code.
  Từ nay nó chỉ còn tồn tại trong tài liệu nghiệp vụ, cho tới khi có model đề thật.
- Việc `extra="forbid"` không được bật khiến lần gỡ này an toàn, nhưng cũng nghĩa là **contract không
  bắt được lỗi gõ sai tên trường**. Đó là cùng một đặc tính, đọc theo hai hướng.
- Ai muốn thi hành luật giải thích sẽ phải thiết kế trường đó trên đề trước, rồi mới tới bước chấm.
  Nặng hơn hẳn việc điền vào một enum đã có sẵn — và đó là lý do enum có sẵn nhưng bỏ trống lại nguy
  hiểm.
- Vì pha 1 không thu lời giải thích, `student_explanation` **luôn rỗng** ở đó. Điều đó kéo theo một
  hệ quả ở chỗ khác hẳn: điều kiện ngưỡng của
  [ADR-07](adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md) đúng với mọi câu của mọi học sinh, nên nó
  phải được gỡ khỏi luồng học sinh. Một quyết định về **chỗ đặt ô nhập** hoá ra chạm tới **cổng định
  tuyến**.

## Nơi luật này đang được thi hành

- `packages/contracts/src/contracts/enums.py` — `AssessmentType` đã bị xoá; file còn `ReviewReason`.
- `packages/contracts/src/contracts/messages.py` — `GradingRequested` không còn `assessment_type`.
- `packages/contracts/src/contracts/__init__.py` — không còn trong import và `__all__`.
- `packages/contracts/tests/test_messages.py`, `services/agent/tests/test_handlers.py` — payload mẫu
  đã bỏ trường; 20 test pytest xanh sau khi gỡ.
- `services/fe/src/api.ts` — thân request không còn gửi trường.
- `docs/local-development.md` — ví dụ `curl` đã bỏ trường.
- **Chỗ thu lời giải thích: bề mặt đã có, contract thì chưa theo.** Pha 2 nay có mười hai artboard,
  và lời giải thích của học sinh **không** được thu lúc nộp: màn `14 · Làm bài` chỉ có các phương án,
  còn phần nói ra cách nghĩ nằm trong **đoạn chat** của màn `17`. `GradingRequested` thì vẫn mang
  `student_explanation` như thể nó đi kèm lúc nộp — trường ấy nay mô tả sai chỗ dữ liệu sinh ra.
- Luật vẫn còn hiệu lực nằm ở `docs/overview/use-case-specification.md:255` và
  `docs/overview/business-workflows.md:76`, `91`; `business-workflows.md:86` là vế bù cho bài thường
  xuyên. Không dòng nào bị đụng tới trong lần gỡ này.
