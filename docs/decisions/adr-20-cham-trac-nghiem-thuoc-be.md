# ADR-20 — Chấm trắc nghiệm là việc của BE, không phải của AGENT

- **Trạng thái:** đã chốt, chưa thi hành
- **Ngày:** 2026-09-11

## Bối cảnh

`services/agent/src/agent/handlers.py:73` tính `score = 1.0 if is_correct else 0.0`, trong đó
`is_correct` là một phép so chuỗi: `selected_option_id.endswith("a")`. BE đẩy job qua Redis, chờ, rồi
đọc điểm về.

Cách sắp xếp ấy có lý do lịch sử: lúc dựng đường đi end-to-end, chấm bài là **việc duy nhất** hệ thống
làm, nên đặt nó ở đâu cũng thành ra đặt cả luồng ở đó.

Hai ADR sau đó đã nói khác đi mà chưa ai áp lại vào code.
[ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md) viết: *"Với trắc nghiệm, phần chấm là một phép so và
không có gì để mà không chắc."* [ADR-06](adr-06-agent-phat-bang-chung.md) viết agent **phát bằng
chứng**, không quyết định. Một phép so không phải bằng chứng — nó là sự thật, và sự thật thuộc về nơi
giữ sổ.

## Quyết định

- **BE chấm.** Nó so `option_id` học sinh chọn với đáp án đúng của câu hỏi **đã duyệt** trong database
  của chính nó. Không qua hàng đợi, không chờ ai.
- **AGENT không bao giờ trả về điểm.** Ba việc của agent trong luồng core là: soạn đề nháp, sinh câu
  cho một lượt làm lại, và viết một lượt trả lời trong đoạn chat pha 2.
- Điều này áp cho **cả hai pha**: câu của lượt làm lại cũng do agent sinh ra kèm đáp án đúng, BE lưu
  lại, và khi học sinh nộp lượt thì **BE** so.
- Đường demo cũ (`POST /api/submissions` → task `grade_submission`) **không nằm trong luồng core**.
  Nó chỉ sống tới khi hàng đợi review của giáo viên được thiết kế, và lúc đó phải được dựng lại từ
  nhu cầu thật chứ không phải giữ vì đang có.

## Vì sao

**Một hệ thống chấm bài không được phụ thuộc vào LLM để biết đúng hay sai.** Nếu queue nghẽn, model
hết quota, hay worker chết, học sinh vẫn phải nộp được bài và vẫn phải thấy điểm pha 1 — vì
[ADR-16](adr-16-thang-diem-ba-muc.md) nói điểm đó là **sàn**, và một cái sàn phụ thuộc vào dịch vụ
bên ngoài thì không phải sàn.

**Đáp án đúng nằm trong database mà agent không được phép đọc.** [Architecture](../overview/architecture.md)
chốt agent không giữ credential database nào. Muốn agent chấm thì phải gửi đáp án đúng kèm mỗi job —
tức là để một service không được quyết định gì đi cầm chính thứ quyết định đúng/sai.

**Một vòng queue cho một phép so là cái giá không mua được gì.** Nộp một bài sáu câu hiện là sáu job,
sáu lần chờ, sáu chỗ hỏng. Cùng phép so ấy chạy trong BE là sáu lần so chuỗi.

Cái **thật sự** cần agent thì vẫn cần: giải thích lỗi, dạy lại, sinh câu mới. Đó là chỗ không có phép
so nào thay được, và [ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md) đã buộc chúng đi theo lời giải
soạn sẵn thay vì để agent tự nghĩ.

## Hệ quả

- **`GradingRequested` và `GradingCompleted` mất vai trò trong luồng học sinh.** Chúng vẫn nằm trong
  `packages/contracts` cho tới khi hàng đợi review được thiết kế; giữ lại **không** có nghĩa là còn
  dùng. Ai đọc contract mà tưởng luồng chấm đi qua hàng đợi sẽ hiểu sai toàn bộ kiến trúc — đây là
  đúng cái bẫy [ADR-11](adr-11-bo-assessment-type.md) đã mô tả với `AssessmentType`, nên nó phải được
  gỡ ngay khi UC-05 chốt hình dạng.
- **Ba invariant trong `AGENTS.md` đang canh một luồng sắp không còn là luồng chính**:
  *AGENT emits no routing decision*, *low confidence is flagged*, *a correct answer does not exempt*.
  Chúng vẫn đúng và vẫn phải xanh, nhưng chúng canh đường demo chứ không canh core.
- **BE phải kiểm đầu ra của agent trước khi lưu.** Đúng một phương án `is_correct`, mọi phương án còn
  lại có `error_label`, ít nhất hai cách giải. Agent không được quyết định gì thì cũng không được tự
  nới luật của [ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md) — và vòng review ngày 2026-09-11 đã bắt
  được một câu mẫu có **hai** đáp án đúng, nên đây không phải rủi ro lý thuyết.
- **Chấm nhanh làm lộ một câu hỏi mới**: nộp bài xong thì màn kết quả hiện ra **ngay**, không có
  trạng thái *đang chấm*. Chip `Đang chấm` trên màn `13` vì thế chỉ còn đúng cho bài **chưa** chuyển
  sang mô hình này; xem `docs/plans/backlog.md`.

## Nơi luật này đang được thi hành

**Chưa ở đâu cả.** Code hiện làm ngược lại: `services/agent/src/agent/handlers.py:47-79` vẫn chấm, và
`services/be/src/be/routes.py:67-91` vẫn đẩy bài làm qua hàng đợi.

- Kế hoạch thi hành: `docs/plans/active/2026-09-11-core-two-phase-backend-plan.md`.
- Figma không có bề mặt nào chứng minh hay phản đối luật này — chấm ở đâu là thứ học sinh không nhìn
  thấy. Bằng chứng duy nhất trên màn là **không có trạng thái chờ chấm** giữa màn `14` và màn `15`.
