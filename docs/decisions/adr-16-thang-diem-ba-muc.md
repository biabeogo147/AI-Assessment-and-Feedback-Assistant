# ADR-16 — Mỗi câu có ba mức điểm, và 0,5 nghĩa là hiểu sau khi được dạy

- **Trạng thái:** đã chốt, chưa thi hành
- **Ngày:** 2026-09-10

## Bối cảnh

[ADR-14](adr-14-hai-pha-lam-bai.md) cho học sinh cơ hội chữa một câu đã sai. Cơ hội đó phải có giá trị
nhìn thấy được, nếu không nó chỉ là bài tập thêm cho người vừa bị điểm kém.

Câu hỏi đi kèm là học sinh **nhìn thấy** cái gì. `score` trong contract là số thực 0,0–1,0; trường Việt
Nam đọc thang 10; và `docs/plans/backlog.md` đã chốt rằng **mốc điểm đạt chưa ai quyết** nên giao diện
không được tự nhận.

## Quyết định

- Mỗi câu có **đúng ba mức**: **1** khi đúng ngay ở pha 1, **0,5** khi sai ở pha 1 nhưng chữa được ở
  pha 2, **0** khi sai và không chữa được.
- **Học sinh nhìn thấy cả ba con số**, và nhìn thấy **lý do** một câu được 0,5.
- **0,5 nghĩa là hiểu sau khi được dạy, không phải tự làm được.** Đây là định nghĩa, không phải một
  cách diễn giải.
- Pha 2 **chỉ cộng, không bao giờ trừ**. Điểm tính ngay sau khi nộp là **sàn**, không phải một giá trị
  có thể lên hoặc xuống.
- Đúng ở vòng nào cũng là 0,5. Không trừ dần theo số vòng.
- Không có mốc đạt và không xếp loại.
- **Mức 0,5 chưa có cách thể hiện bằng màu.** [ADR-12](adr-12-mau-va-hinh-anh-ma-hoa-luat.md) là chủ
  sở hữu luật màu và hiện chỉ khoá **hai** trạng thái đáp án vào `answer/incorrect`. Trạng thái thứ
  ba chưa ai định, và ADR này **không tự nhận** — nó ghi nợ. Xem `docs/plans/backlog.md`.

## Vì sao

Ba mức thay vì hai, vì hai mức biến việc chữa bài thành công việc không được trả công. Một học sinh sửa
được lỗi của mình đã học đúng thứ bài kiểm tra muốn dạy, và mức giữa là chỗ duy nhất ghi nhận điều đó.

Không trừ dần theo vòng, vì trừ dần biến việc chữa thành một hình phạt mới và dạy học sinh đoán mò cho
nhanh ở vòng đầu. Cái giá của lựa chọn này nằm ở mục *Hệ quả*.

**0,5 phải được định nghĩa thẳng ra** vì con số này rất dễ bị đọc thành *làm được một nửa*. Sự thật
khác hẳn: ngay trước khi làm câu biến thể, học sinh vừa được Kriky giải thích chính câu gốc, không giới
hạn thời gian và không giới hạn số lượt hỏi ([ADR-15](adr-15-thoi-gian-pha-hai.md)). Một em kiên nhẫn
có thể moi ra gần trọn phương pháp trước khi bấm nút làm bài mới. Cho nên 0,5 **không đo năng lực độc
lập**, và không được dùng như thể nó đo.

Sản phẩm chọn không siết chỗ đó lại. Việc học sinh hỏi cho tới khi hiểu là **kết quả mong muốn**, không
phải lỗ hổng cần vá. Nhưng nếu định nghĩa này không nằm trên giấy, người sau sẽ thấy con số 0,5 trông
như một phép đo và siết đúng chỗ không nên siết.

Học sinh thấy con số vì em cần biết chữa được một câu thì được gì. Giấu đi khiến pha 2 thành việc bắt
buộc mà không rõ để làm gì.

## Hệ quả

- **Điểm của một lớp không có thời điểm nào là đúng cho tới khi em cuối cùng xong.** Một con số chỉ đi
  lên vẫn là con số chưa chốt, nên mọi bề mặt bày điểm phải mang thêm nghĩa *ít nhất bằng* — và mọi
  thống kê gộp trên đó đều là thống kê của một cận dưới, không phải của kết quả.
- **Không so sánh được hai học sinh bằng tổng điểm.** Một em 8,5 gồm toàn điểm 1 và một em 8,5 có bốn
  câu 0,5 đã học hai thứ khác nhau. Muốn so thì phải nhìn cấu thành, và giao diện phải cho nhìn được.
- Vì điểm phẳng ở mức 0,5, **chi phí của việc thử ở vòng một và vòng ba là như nhau**. Trần ba vòng
  ([ADR-17](adr-17-ba-vong-moi-cau.md)) vì thế không răn đe gì; nó chỉ chọn thời điểm dừng. Đó là hệ
  quả đã biết của việc không trừ dần, không phải một thiếu sót.
- **Nói được 0,5 thì dễ, nói *vì sao* 0,5 thì chưa.** Lý do đòi biết câu gốc nào và vòng thứ mấy —
  những thứ hiện không đi cùng kết quả chấm. Một con số không giải thích được là con số học sinh sẽ
  hỏi giáo viên, và giáo viên cũng không trả lời được.
- Bỏ mốc đạt khiến sản phẩm **không trả lời được câu em có qua không**. Đó là câu giáo viên Việt Nam sẽ
  hỏi, và câu trả lời hiện là chưa ai quyết mốc.

## Nơi luật này đang được thi hành

**Ở Figma phía học sinh. Chưa ở đâu khác** — trừ một trường tình cờ tương thích.

- **Ở Figma**: `Score mark` (`279:19`) ba variant `1` / `0.5` / `0`, phân biệt bằng hình tròn đầy,
  nửa, rỗng nên **bỏ màu đi vẫn đọc được**; mức 0,5 không được cấp màu mới
  ([ADR-12](adr-12-mau-va-hinh-anh-ma-hoa-luat.md)).
- **Lý do chỉ hiện khi hover**, dựng thành hai artboard: `21 · Kết quả — hover vào điểm 0,5` và
  `16 · Kết quả — hover vào điểm 0`. In thành một dòng dưới mỗi câu thì nó lặp ở mọi hàng và làm dày
  bảng điểm mà không thêm thông tin.
- **Hai chuỗi hover, không phải một.** Mức 0,5 nói *đã chữa được*; mức 0 nói *còn chữa được* — và
  chuỗi ấy **chỉ đúng khi pha 2 chưa đóng**. Trên màn *đã hoàn thành*, một số 0 là số đã chốt; chuỗi
  cho ca đó chưa viết, và mô tả `Score mark` ghi rõ là chưa.
- **Điểm pha 1 là sàn**, nói bằng một câu duy nhất trên artboard `15`:
  *"Bạn có thể nâng điểm các câu sai bằng cách **Hỏi trợ lý và làm lại dạng bài sai** tới hết
  22:00 · 15/9."*
- **Bảng điểm của giáo viên chưa theo kịp**: `11 · Kết quả bài kiểm tra trong lớp` bày điểm như số đã
  chốt và chưa có trạng thái *chưa chốt*; xem `docs/plans/backlog.md`.
- **Ở contract, một nửa may mắn đúng**: `packages/contracts/src/contracts/messages.py` khai `score` là
  `Field(ge=0.0, le=1.0)` nên nhận được 0,5 mà không phải đổi contract. Nhưng không trường nào phân
  biệt 0,5 do chữa được với 0,5 do chấm một nửa.
- **Chưa có ở backend**: `services/agent/src/agent/handlers.py` chỉ sinh 1,0 hoặc 0,0.
- **Bị chặn**: xem `docs/plans/backlog.md`.
