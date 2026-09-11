# ADR-09 — Kết quả chấm là tạm thời

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-06

## Bối cảnh

Kết quả chấm sống trong Redis với `JOB_RESULT_TTL_SECONDS=3600`. Sau một giờ, API trả **404**. Đây là
một luật nghiệp vụ có hệ quả thật với học sinh, và nó chỉ tồn tại trong một biến môi trường.

## Quyết định

- Kết quả chấm **chỉ sống một giờ**. Sau đó nó biến mất và API trả 404.
- 404 vì hết hạn và 404 vì không có job **không phân biệt được** ở tầng API.
- Chờ quá lâu là **trạng thái chờ, không phải lỗi**: bài đã được nhận, chỉ kết quả về muộn.
- Mọi thông điệp lỗi phải **xác nhận bài làm không mất**.

## Vì sao

Một giờ là hệ quả của việc chưa có cơ sở dữ liệu: Redis giữ kết quả, và giữ vô hạn thì bộ nhớ chỉ có
tăng. Đây là quyết định **tạm thời do hạ tầng**, không phải một luật sư phạm — và phải ghi rõ như vậy,
nếu không người sau sẽ tưởng một giờ là con số có chủ đích.

Timeout tách khỏi lỗi vì hai thứ đòi hành động khác nhau: lỗi thì thử lại hoặc báo người, chờ thì chỉ
cần quay lại sau. Gộp chúng khiến học sinh tưởng bài mình hỏng.

Câu xác nhận bài không mất tồn tại vì đó là nỗi lo đầu tiên của người vừa nộp bài. Không nói ra thì
người ta tự đoán, và đoán về phía xấu.

## Hệ quả

- **Học sinh mở lại kết quả sau một giờ thì mất.** Với một sản phẩm đánh giá học tập, đây là hạn chế
  nặng, và nó sẽ phải biến mất khi có cơ sở dữ liệu thật.
- Giáo viên không thể dựa vào kết quả chấm như một hồ sơ. Mọi tính năng cần lịch sử — thống kê, mastery,
  luyện tập thích ứng, và cả `ReviewReason.ANOMALY` — đều bị chặn bởi cùng một hạn chế này.
- **Thứ lớn nhất bị chặn là toàn bộ pha 2** ([ADR-14](adr-14-hai-pha-lam-bai.md)). Bộ đếm vòng của
  từng câu, lịch sử hội thoại giải thích, trạng thái *câu nào còn dở*, và điểm cuối đều là trạng thái
  có nhớ — trong khi hạn kết thúc pha 2 có thể là cuối ngày
  ([ADR-15](adr-15-thoi-gian-pha-hai.md)). Học sinh chữa dở rồi quay lại thì hệ thống không còn biết
  em đã dùng mấy vòng. Đây không phải một tính năng bị chậm; nó là **nửa sau của sản phẩm** không tồn
  tại được. Sáu ADR từ 14 tới 19 vì thế đều mang trạng thái *chưa thi hành*.
- Không thể phân biệt "job không tồn tại" với "kết quả đã hết hạn", nên giao diện phải nói cả hai khả
  năng bằng một câu, hoặc nói theo cách đúng trong cả hai trường hợp.

## Nơi luật này đang được thi hành

- `.env.example:21` — `JOB_RESULT_TTL_SECONDS=3600`.
- `services/agent/src/agent/worker.py:75` — `keep_result = _settings.job_result_ttl_seconds`. Đây là
  chỗ **duy nhất** giá trị đó có tác dụng: hạn giữ do worker của AGENT đặt lúc lưu kết quả, không phải
  do BE đặt lúc đọc.
- `services/be/src/be/routes.py:110` — docstring nói 404 xảy ra cả khi kết quả đã qua hạn giữ.
- `services/be/src/be/routes.py:117` — `raise HTTPException(status_code=404, ...)`.
- Figma `mOe2ZmrqOq1Uix45v6PNGD` — `Error state` (`6:75`) variant `het-han-404`: *"Kết quả chỉ được giữ trong một giờ."*;
  `Async waiting` (`6:49`) variant `timeout` là trạng thái chờ, không phải lỗi.
- **Chưa có ở tài liệu nghiệp vụ**: `docs/overview/` không nói kết quả chấm là tạm thời.
- **Thu hẹp bởi [ADR-21](adr-21-trang-thai-bai-lam-la-ben.md).** Hạn một giờ nay chỉ còn áp cho kết
  quả một job của arq; trạng thái bài làm sống trong Postgres. Luật gốc vẫn đúng trong phạm vi mới
  của nó.
- **Chỗ vi phạm cũ ở FE đã biến mất cùng màn demo.** `api.ts` không còn poll job chấm bài, vì
  [ADR-20](adr-20-cham-trac-nghiem-thuoc-be.md) đưa việc chấm vào thẳng request nộp bài — không còn
  thời gian chờ nào để hiển thị nhầm thành lỗi.
