# ADR-21 — Trạng thái bài làm là bền; hạn một giờ chỉ áp cho kết quả job

- **Trạng thái:** đã chốt, chưa thi hành
- **Ngày:** 2026-09-11

## Bối cảnh

[ADR-09](adr-09-ket-qua-cham-la-tam-thoi.md) chốt kết quả chấm **sống một giờ** rồi biến mất, vì hệ
thống lúc đó không có database và arq là chỗ lưu duy nhất. Luật ấy đúng với thứ nó mô tả: một kết quả
job nằm trong Redis.

[ADR-14](adr-14-hai-pha-lam-bai.md) rồi [ADR-15](adr-15-thoi-gian-pha-hai.md) dựng lên một mô hình
kéo dài **hàng giờ tới hàng ngày**: giáo viên đặt hạn pha 2 lúc phát hành, học sinh nộp bài lúc 14:12
và chữa tới 22:00. `docs/plans/backlog.md` đã ghi mâu thuẫn này từ đầu: *chừng nào kết quả còn sống
một giờ, pha 2 không tồn tại được*.

Mười hai artboard của bề mặt học sinh giờ đã dựng xong và bày ra mâu thuẫn ấy ở dạng cụ thể: màn `15`
hứa *"nâng điểm các câu sai tới hết 22:00 · 15/9"*, màn `24` hứa đọc lại được đoạn chat **sau khi bài
kết thúc**, và màn `22` in kết quả của từng lượt làm lại. Cả ba lời hứa đều chết sau sáu mươi phút.

## Quyết định

- **Thu hẹp ADR-09**, không bãi bỏ. Hạn một giờ chỉ còn áp cho **kết quả của một job trong arq** —
  thứ ADR-09 thật sự nói tới.
- **Trạng thái bài làm là bền và do BE sở hữu**, trong Postgres: lần làm bài và từng câu trả lời,
  điểm từng câu ở ba mức, bộ đếm vòng, từng lượt làm lại cùng đề đã sinh ra, đoạn chat pha 2, và các
  báo cáo *giải thích khó hiểu*.
- **Ranh giới giữa hai thứ**: cái gì học sinh hoặc giáo viên còn phải nhìn lại sau khi đóng trình
  duyệt thì là trạng thái bền. Cái gì chỉ là kết quả trung gian của một lần gọi agent thì để arq lo
  và biến mất cùng TTL.
- **Hạn lưu trữ dài hơn một học kỳ chưa quyết.** Ghi vào `docs/plans/backlog.md` chứ không đoán ở
  đây.

## Vì sao

Một lời hứa in trên màn hình mà hạ tầng không giữ nổi thì **tệ hơn không hứa**. Học sinh đọc *"chữa
tới 22:00"*, đi ăn cơm, quay lại lúc 19:00 và mất sạch — đó không phải lỗi hiển thị, đó là hệ thống
nói dối.

ADR-09 không sai, nó chỉ **hết phạm vi**. Lý lẽ của nó — *kết quả chấm là tạm thời vì chưa có nơi lưu
bền* — là một mô tả hạ tầng, và hạ tầng vừa đổi. Giữ nguyên câu chữ cũ trong khi dựng pha 2 lên trên
nó là để hai tài liệu cùng đúng trên giấy và cùng sai trên thực tế.

Chọn Postgres vì [architecture.md](../overview/architecture.md) đã chốt Postgres và MongoDB thuộc BE,
và vì mọi thứ cần lưu ở đây đều có quan hệ rõ: một lần làm bài có nhiều câu trả lời, một câu sai có
nhiều lượt, một lượt có nhiều câu sinh ra.

## Hệ quả

- **AGENT vẫn không có credential database.** Ranh giới của architecture.md không đổi: job vẫn phải
  tự chứa, và chỗ lưu mới nằm hoàn toàn bên BE.
- **Biến `JOB_RESULT_TTL_SECONDS` giữ nguyên nghĩa nhưng mất tầm quan trọng.** Nó không còn là thứ
  quyết định học sinh xem được kết quả bao lâu; nó chỉ quyết định một job của agent nằm lại trong
  Redis bao lâu.
- **Trạng thái lỗi `hết hạn 404` hẹp lại.** `Error state` variant `het-han-404` trong Figma nói
  *"Kết quả chỉ được giữ trong một giờ"* — câu đó nay chỉ đúng cho một lần poll job, không đúng cho
  màn kết quả của học sinh. Chuỗi ấy phải sửa cùng đợt dựng core, nếu không nó thành lời nói dối thứ
  hai.
- **Có database nghĩa là có migration, backup và một hình dạng dữ liệu phải bảo trì.** Đây là chi phí
  vận hành thật mà giai đoạn trước cố ý chưa trả. Trả nó vì pha 2 không có đường nào khác, chứ không
  phải vì database là bước tiến tự nhiên.
- **`docs/overview/data-model.md`** — tên đã được `AGENTS.md` giữ chỗ — nay có nội dung thật để viết,
  và phải được viết trong cùng đợt dựng schema.

## Nơi luật này đang được thi hành

**Chưa ở đâu cả.** Hiện không có Postgres, không có migration, không có model nào.

- `.env.example:21` — `JOB_RESULT_TTL_SECONDS=3600` vẫn là hạn duy nhất tồn tại, và nó đang mang cả
  hai nghĩa.
- Kế hoạch thi hành: `docs/plans/active/2026-09-11-core-two-phase-backend-plan.md`.
- `docs/plans/backlog.md`, mục *Luồng học sinh — mô hình hai pha*, ghi đúng mâu thuẫn mà ADR này giải
  quyết. Mục đó phải được cập nhật khi core lên, không để lại một lời cảnh báo đã hết hiệu lực.
