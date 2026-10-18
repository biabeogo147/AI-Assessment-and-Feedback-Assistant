# ADR-15 — Thời gian ở pha 2: hai đồng hồ, và chỉ một trong hai chạy khi học sinh đang học

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-10
- **Sửa:** 2026-10-17 — hai dòng *chưa có ở backend* và *bị chặn* cuối mục thi hành đã cũ. Xem
  *Hậu ký 17/10/2026* ở cuối. Phần trên giữ nguyên làm lịch sử.

## Bối cảnh

[ADR-14](adr-14-hai-pha-lam-bai.md) cho bài kiểm tra một pha thứ hai. Pha đó cần thời gian, và thời
gian của nó không giống pha 1 ở bất cứ điểm nào: số câu phải làm **thay đổi theo từng lượt**, phần học
sinh đọc lời giải thì **không nên bị hối**, và cả pha có thể kéo dài tới cuối ngày.

[ADR-03](adr-03-ranh-gioi-cua-vao.md) đã cho thấy ba con số thời gian rất dễ bị gộp thành một trong đầu
người đọc. Pha 2 thêm hai con số nữa, nên nguy cơ đó tăng chứ không giảm.

## Quyết định

- Phát hành đề nhận thêm **hai** tham số cho pha 2: **số phút mỗi câu** và **hạn kết thúc pha 2**.
  Tổng cộng phát hành có sáu tham số; xem [ADR-02](adr-02-phat-hanh-va-cua-so-thu-hoi.md).
- **Số phút mỗi câu là một tỉ lệ, không phải một khoảng.** Thời lượng một lượt bằng số phút mỗi câu
  nhân số câu còn dở trong lượt đó. Sai hai câu với tỉ lệ 5 phút mỗi câu thì lượt đó là 10 phút.
- Thời lượng ấy là một **quỹ chung** cho cả lượt. Học sinh được dồn thời gian sang câu khó hơn.
- **Phần Kriky giải thích và học sinh hỏi lại không tính giờ.** Đồng hồ chỉ bắt đầu khi học sinh **tự
  bấm** nút làm bài mới.
- **Hạn kết thúc pha 2 là một mốc tuyệt đối** do giáo viên đặt, chung cho cả lớp, và dài hơn hẳn hạn
  của pha 1 — có thể là cuối ngày.
- **Hết hạn thì cắt**, kể cả khi học sinh đang làm dở một lượt. Câu chưa xong nhận 0 điểm.
- Một lượt vẫn được mở kể cả khi thời lượng của nó vượt quá phần hạn còn lại.

## Vì sao

Tỉ lệ thay vì khoảng cố định, vì số câu phải chữa **giảm dần qua từng lượt**. Một khoảng cố định sẽ quá
rộng ở lượt cuối và quá chật ở lượt đầu, và giáo viên không có cách nào đoán trước lớp mình sai bao
nhiêu câu để đặt cho đúng.

Phần giải thích không tính giờ vì **đó là lúc học sinh đang học**, không phải lúc em đang chứng minh.
Đặt đồng hồ lên một cuộc giải thích là dạy học sinh gật cho xong rồi bấm tiếp. Đồng hồ chỉ có nghĩa ở
phần đo được, và phần đo được là câu biến thể.

Ranh giới đặt ở nút làm bài mới vì đó là hành động **học sinh tự chọn**. Một cánh cửa một chiều mà
người đi qua tự mở thì công bằng; một cánh cửa tự đóng sau lưng họ thì không.

**Hết hạn thì cắt** là chỗ pha 2 đi ngược pha 1, và điều đó có chủ đích.
[ADR-03](adr-03-ranh-gioi-cua-vao.md) chọn *không dừng người đang làm* vì ở pha 1 thời gian là **thứ
được cấp cho mỗi người**, đo từ lúc họ vào, nên cắt ngang là lấy lại thứ đã hứa. Ở pha 2 thì ngược:
thời lượng lượt do học sinh **tự chọn lúc nào bắt đầu**, và hạn cuối là một mốc họ nhìn thấy suốt cả
ngày. Không cắt nghĩa là hạn cuối không tồn tại — ai cũng có thể mở một lượt dài lúc còn một phút và
kéo bài kiểm tra qua đêm. Ai đọc hai luật này rồi thấy chúng không nhất quán thì phải đọc lại đoạn này
trước khi sửa một trong hai.

## Hệ quả

- **Giao diện phải nói trước rằng lượt này có thể bị dừng**, ngay tại nút làm bài mới, kèm số phút còn
  lại thật. Một học sinh bị dừng giữa chừng mà không được báo trước sẽ tin là hệ thống hỏng. Từ dùng
  với học sinh là **dừng**, và nó được in đậm trong câu luật — *cắt* là từ nội bộ của ADR này.
- **Giáo viên phải đặt một con số mà họ chưa từng phải nghĩ tới.** Không có kinh nghiệm nào giúp đoán
  mấy phút là đủ cho một câu chữa, và đặt sai thì hoặc lớp không kịp, hoặc bài kiểm tra kéo lê.
- Vì số phút mỗi câu là **một con số cho cả đề**, một câu dài và một câu ngắn được cấp thời gian như
  nhau. Muốn phân biệt thì phải là một khái niệm khác, không phải nới tỉ lệ này.
- **Tổng thời gian một học sinh bỏ ra không dự đoán được**, vì phần giải thích không giới hạn. Mọi
  tính năng sau này muốn báo cáo em học bao lâu đều phải đo, không suy ra được từ cài đặt.
- Hai con số mới phải đi qua **cùng cả ba nơi** mà [ADR-03](adr-03-ranh-gioi-cua-vao.md) đòi cho các
  mốc pha 1: lúc đang chọn, lúc xác nhận, và trong biên bản sau khi phát hành.

## Nơi luật này đang được thi hành

- Figma `Publish settings` (`67:41`) — nhóm **PHA 2** với hai trường *PHÚT MỖI CÂU* và
  *HẠN CHỮA XONG*, ở cả hai variant.
- Figma — chuỗi *"Chữa bài tới hết 22:00 - mỗi lượt 5 phút một câu, và hết hạn thì lượt đang làm bị
  **DỪNG**."* xuất hiện **giống hệt nhau ở bốn nơi**: `Publish settings` (`67:41`), `Consequence dialog`
  (`11:41`), `Action result card` variant `đã-phát-hành` (`10:45`), và variant `chưa có lớp`
  (`77:341`) — đúng như [ADR-03](adr-03-ranh-gioi-cua-vao.md) đòi.
- Figma `Publish settings` (`67:41`) — mô tả component ghi định dạng ngày giờ `HH:MM · DD/MM` là
  **ràng buộc**, vì cột pha 1 chỉ rộng 119 và trừ padding còn 94.
- Figma `20 · Bắt đầu lượt chữa — sắp hết hạn` — `Round gate` variant `vượt hạn`, nói trước rằng lượt
  10 phút có thể bị **DỪNG** khi chỉ còn 6 phút tới hạn. Nó là **artboard riêng**, không phải trạng
  thái của màn `19`: hai màn ấy là hai thời điểm khác nhau trong ngày, và trộn chúng làm một thì mọi
  mốc giờ của bộ mẫu mâu thuẫn nhau.
- **Chưa có ở backend**: `packages/contracts` không có trường thời gian nào, kể cả của pha 1.
- **Bị chặn**: một đồng hồ chạy xuyên qua nhiều lượt là trạng thái có nhớ, mà
  [ADR-09](adr-09-ket-qua-cham-la-tam-thoi.md) xoá mọi thứ sau một giờ. Xem `docs/plans/backlog.md`.

## Hậu ký 17/10/2026

Hai dòng cuối của mục thi hành đúng vào ngày viết, và sai từ khi pha 2 có backend (plan
`backlog-tier-1` ghi lại):

- **Backend đã có hai đồng hồ.** `Publication` mang `phase2_minutes_per_question` và
  `remediation_deadline`; `be/remediation.py` tính độ dài lượt (`round_budget_minutes`) và giờ kết
  thúc đã cắt theo hạn (`round_ends_at`); `RemediationRound.ends_at` lưu nó. `save_round_answer` từ
  chối một lựa chọn sau `ends_at` -- lượt **DỪNG** -- còn `submit_round` vẫn nhận nộp và chấm phần
  đã lưu trước đó (test `test_a_stopped_round_is_marked_on_what_was_saved_before_it_stopped`).
- **Không còn bị ADR-09 chặn.** Trạng thái bài làm nằm ở Postgres, không ở kết quả job của arq
  ([ADR-21](adr-21-trang-thai-bai-lam-la-ben.md)), nên một đồng hồ xuyên nhiều lượt không mất sau
  một giờ.

## Hậu ký 18/10/2026

**Hết giờ lượt chữa thì màn hình tự rời màn làm bài**, nhưng chỉ khi BE trả lời. Đồng hồ của màn
lượt về 0 thì FE đọc lại lượt (`GET /rounds/{id}`), và lời đáp của BE quyết bước kế:

- `stopped` (`now > ends_at` theo đồng hồ của BE, cùng biên với chỗ `save_round_answer` thôi nhận
  câu): FE nộp phần đã lưu rồi về màn xem điểm. Ở đó `last_round_ran_out` hiện thông báo *"Lượt
  chữa vừa rồi đã hết giờ nên được nộp luôn"* (artboard `16b`). Cờ ấy chỉ nói về lượt nộp gần
  nhất, và bật khi lượt ấy nộp sau `ends_at`.
- 409 (lượt đã nộp ở tab khác): FE về thẳng màn xem điểm.
- chưa dừng (đồng hồ máy chạy nhanh hơn BE): FE ở lại. `ends_at` không bao giờ đổi, nên đồng hồ
  không tự bắn lần nữa; FE hỏi lại sau `max(1 giây, ends_at − giờ máy)`, tối đa năm lần.
- không nói được với BE, hay nộp hỏng vì lỗi khác 409: FE ở lại, hiện lời lỗi; nút *Nộp bài* vẫn
  còn.

Luật của ADR không đổi: BE vẫn là chỗ dừng lượt và từ chối câu trả lời muộn. Dòng *"A countdown is
decoration"* của `services/fe/AGENTS.md` đổi thành *"A countdown never decides: at zero the screen
asks BE, and only BE's answer moves it."* (Tier 2 câu 18, plan `wave-2-time-marks-titles`).
