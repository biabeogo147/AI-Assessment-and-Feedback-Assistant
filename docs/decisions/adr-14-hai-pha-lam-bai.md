# ADR-14 — Một bài kiểm tra có hai pha; nộp bài không phải điểm kết thúc

- **Trạng thái:** đã chốt, và đã thi hành ở backend (cập nhật 2026-10-10)
- **Ngày:** 2026-09-10

## Bối cảnh

Mọi tài liệu và mọi màn hình đã dựng đều coi **nộp bài** là điểm kết thúc của một bài kiểm tra.
`business-workflows.md` Workflow 2 kết thúc ở *"Hệ thống ghi nhận submission"*; artboard
`10 · Chi tiết lớp` đếm một cột **ĐÃ NỘP**; artboard `11 · Kết quả bài kiểm tra trong lớp` bày điểm
như một con số đã chốt.

Quyết định sư phạm của sản phẩm thì ngược lại: học sinh sai một câu **phải được chữa** trước khi bài
đóng lại. Việc chữa đó không phải một tính năng đi kèm — nó là **nửa sau của cùng một bài kiểm tra**.

## Quyết định

- Một bài kiểm tra có **hai pha**. **Pha 1** là làm bài và nộp. **Pha 2** là chữa những câu đã sai.
- **Nộp bài kết thúc pha 1, không kết thúc bài.** Bài kết thúc khi pha 2 xong, hoặc khi hạn pha 2 hết.
- **Pha 2 bắt buộc.** Học sinh không có đường tắt bỏ qua nó để đóng bài sớm.
- Nhưng bắt buộc là bắt buộc **thử**, không phải bắt buộc **đạt**: hết ba vòng vẫn sai thì câu đó đóng
  lại và bài kết thúc bình thường. Xem [ADR-17](adr-17-ba-vong-moi-cau.md).
- **Bắt buộc được thi hành bằng điểm, không bằng khoá.** Hệ thống không giam học sinh lại. Em không
  vào pha 2 lần nào thì tới hạn, mọi câu sai thành 0 điểm — đúng bằng kết quả của em vào rồi sai cả
  ba vòng.
- Pha 2 có **đồng hồ riêng**, độc lập với thời gian làm bài của pha 1. Xem
  [ADR-15](adr-15-thoi-gian-pha-hai.md).
- Một bài kiểm tra vì thế có **hai trạng thái hoàn thành khác nhau**: *đã nộp* và *đã hoàn thành*.
  Chúng không thay thế cho nhau được.

## Vì sao

Một bài kiểm tra chỉ nói cho học sinh biết em sai ở đâu thì mới làm xong nửa việc. Nửa còn lại — sửa
được lỗi đó — là thứ duy nhất thay đổi kết quả học tập, và nó là lý do sản phẩm này tồn tại.

Đặt việc chữa **bên trong** bài kiểm tra chứ không phải bên cạnh nó là quyết định có sức nặng. Nếu chữa
bài là một mục tuỳ chọn ở đâu đó, nó sẽ được làm bởi đúng những em không cần nó. Đặt nó vào trong bài,
với điểm gắn liền, khiến em nào sai cũng phải đi qua.

Bắt buộc *thử* chứ không bắt buộc *đạt* vì phương án ngược lại giam học sinh lại vì một lỗ hổng mà bản
thân em không tự lấp được. Một vòng lặp không có lối ra là hình phạt, không phải việc dạy.

Thi hành bằng điểm chứ không bằng khoá, vì một cái khoá cần chỗ để mở — và chỗ đó sẽ là một ngoại lệ
do giáo viên bấm, tức là một cổng thứ tư không ai muốn. Để điểm nói thay thì luật tự thi hành, và học
sinh chọn không chữa vẫn là học sinh đã chọn, không phải học sinh bị kẹt.

## Hệ quả

- **Mọi con số đếm "đã nộp" đều trở nên mơ hồ.** Một lớp 40 em có thể nộp đủ 40 mà chưa em nào hoàn
  thành. Từ nay mỗi chỗ đếm phải chọn một trong hai nghĩa và nói ra mình chọn cái nào.
- Vì bắt buộc chỉ được thi hành bằng điểm, **hai em cùng 0 điểm ở một câu vì hai lý do khác nhau.**
  Dữ liệu phân biệt được: `MarkReason` có `NOT_YET_REMEDIATED` cho em không vào, và `ROUNDS_EXHAUSTED`
  cho em cố mà không được (`services/be/src/be/scoring.py:29-30`). Nhưng phân biệt ấy chưa tới được
  giáo viên --- xem gạch về tín hiệu bị bỏ rơi trong [ADR-17](adr-17-ba-vong-moi-cau.md).
- **Bài kiểm tra không còn đóng lại tại một thời điểm duy nhất.** Trước đây giáo viên biết chắc sau giờ
  đóng cộng thời gian làm bài là xong; giờ mỗi học sinh kết thúc vào một lúc khác nhau.
- **Điểm không đứng yên.** Xem [ADR-16](adr-16-thang-diem-ba-muc.md).
- **Một khái niệm mới phải được lưu:** bài đang ở pha nào, câu nào còn dở. Đây là trạng thái có nhớ,
  và nay nó nằm trong database chứ không trong kết quả job --- xem mục *Nơi luật này đang được thi
  hành* dưới đây. Kết quả job vẫn hết hạn sau một giờ ([ADR-09](adr-09-ket-qua-cham-la-tam-thoi.md)).
- Mọi tính năng sau này muốn hỏi *"lớp làm xong chưa"* đều phải hỏi lại câu **"xong theo nghĩa nào"**
  trước khi trả lời được.

## Nơi luật này đang được thi hành

**Ở backend, và ở Figma phía học sinh. Phía giáo viên chưa theo kịp.**

- **Ở Figma**: trang `Screen — Student` dựng cả hai pha — nộp bài kết thúc pha 1 (`14 · Làm bài`),
  hai hình dạng của màn kết quả tuỳ pha 2 còn hay hết (`15` và `22`), và sáu màn của chính pha 2:
  `17` hỏi trợ lý, `18` lời giải đầy đủ, `19` và `20` hai ca của cổng bắt đầu lượt, `21` làm câu của
  lượt, `24` khi bài đã kết thúc.
- **Phía giáo viên chưa theo kịp**: artboard `10 · Chi tiết lớp` vẫn đếm **ĐÃ NỘP** như trạng thái
  cuối, và `11 · Kết quả bài kiểm tra trong lớp` bày điểm như đã chốt. Xem `docs/plans/backlog.md`.
- `docs/overview/business-workflows.md` Workflow 2 và `use-case-specification.md` UC-03/UC-04 đã ghi
  luật hai pha; `docs/diagrams/activity-overview.drawio` vẽ nó thành hai băng. Đó là **mô tả**, không
  phải thi hành.
- **Ở backend**: `Attempt` chở `submitted_at` tách khỏi lúc bài xong (`packages/schema/src/schema/models.py`),
  `QuestionOutcome` giữ sổ điểm và `RemediationRound` giữ từng lượt. Các endpoint dựng hai pha
  nằm ở `services/be/src/be/student_routes.py`: `start_attempt` (`:677`), `submit_attempt` (`:853`)
  đóng pha 1, rồi `remediation_panel` (`:1007`), `start_round` (`:1866`), `save_round_answer` (`:2052`)
  và `submit_round` (`:2095`) dựng pha 2 --- chính `submit_round` là nơi lượt được chấm, `mark`
  được nâng, `rounds_used` tăng và câu đóng lại, tức nơi thi hành câu *bài kết thúc khi pha 2 xong*.
  Thang điểm ba mức và trần ba vòng nằm ở `services/be/src/be/scoring.py:12-16`.
  `services/be/tests/test_core_flow.py` đi hết cả hai pha, kể cả ca hạn pha 2 đã đi qua.
- **Chỗ từng bị chặn đã được giải**: kết quả của job vẫn sống một giờ (`be/config.py:84`), nhưng
  `_harvest` (`services/be/src/be/student_routes.py:1458`) coi *câu trả lời đã mất* là một cái kết
  bình thường và xoá dòng ấy đi, rồi `_write_ahead` (`:1547`) đẩy lại job khi cần --- nên hạn pha 2
  cách đó nhiều ngày không còn là vấn đề.
