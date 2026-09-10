# ADR-06 — Agent phát bằng chứng, không đưa ra quyết định

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-06

## Bối cảnh

Đây là nguyên tắc lõi mà cả sản phẩm dựng quanh nó, nhưng nó đang được ghi rải ở năm chỗ và mỗi chỗ chỉ
nói một nửa: contract nói AGENT không phát trường quyết định, `AGENTS.md` nói FE không được so ngưỡng,
Figma nói các bước là bằng chứng. Không chỗ nào nói cả ba là một luật.

## Quyết định

- **AGENT** chỉ phát `score`, `confidence`, `misconception_code`, `feedback_text`. Nó **không** phát
  bất kỳ trường định tuyến nào.
- **Phạm vi: luật này nói về việc chấm bài.** Ở pha 2, agent còn **sinh câu biến thể** và **dẫn cuộc
  giải thích** — hai đầu ra không nằm trong danh sách trên. Chúng vẫn không phải quyết định định
  tuyến, nhưng chúng là **nội dung**, và nội dung thì đi thẳng tới học sinh. Xem
  [ADR-17](adr-17-ba-vong-moi-cau.md) và [ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md).
- **BE** là nơi duy nhất so ngưỡng và quyết định kết quả có cần giáo viên hay không.
- **FE** được **hiển thị** confidence, **không bao giờ** được so nó với ngưỡng.
- Các bước agent đã làm **là bằng chứng**, không phải hiệu ứng chờ. Chúng thu gọn được nhưng không bao
  giờ mất.
- Trạng thái **thất bại không thu gọn được**.
- **Màn hình có cổng bắt buộc có mặt dấu vết các bước.**
- Trích dẫn nguồn phải **tra ngược được**. Một nhãn không tra ngược được là trang trí.

## Vì sao

Cả sản phẩm sống bằng việc thú nhận giới hạn: máy chấm xong thì đưa bằng chứng kèm độ tin cậy, việc nào
không đủ chắc thì đẩy cho giáo viên. Nếu AGENT tự kết luận "cái này cần review" thì nó đang quyết định,
và ngưỡng nghiệp vụ bị chôn trong service không sở hữu nghiệp vụ.

FE bị cấm so ngưỡng vì một lý do cụ thể: nếu FE tô màu thang tin cậy theo ngưỡng, **ngưỡng bị mã hoá
vào giao diện** và đổi ngưỡng trong `.env` không còn đổi được cách người dùng đọc kết quả. Vì vậy thang
tin cậy cố ý **không có màu**.

Dấu vết các bước là bằng chứng vì đó là thứ duy nhất trả lời được câu hỏi giáo viên cần trả lời trước
khi duyệt: **câu hỏi này ở đâu ra**. Thu gọn một thất bại lại là giấu lỗi. Bỏ khối này khỏi màn hình có
cổng là bỏ toàn bộ dấu vết đúng lúc cần nó nhất.

## Hệ quả

- BE phải đọc lại ngưỡng ở mỗi lần trả kết quả, nên một kết quả đã chấm có thể đổi kết luận review khi
  ai đó sửa `.env`. Đó là cái giá của việc không lưu quyết định kèm kết quả.
- Không được cho `Confidence meter` một thang màu.
- Nếu port sang code mà không nối được trích dẫn về trang gốc thì **bỏ chữ "mở đoạn gốc" và bỏ gạch
  chân** — hứa một liên kết không tồn tại còn tệ hơn không hứa.
- Luật *trích dẫn phải tra ngược được* **không có gì để tra** với câu biến thể ở pha 2: nó sinh ra tại
  chỗ và không có trang nguồn nào để trỏ về. Nguồn gốc của nó là chuyện khác và do
  [ADR-04](adr-04-hai-nguon-cau-hoi.md) định — câu Kriky soạn, ở trạng thái *chưa kiểm*. Hai thứ này
  không thay nhau được: một cái nói **lấy từ đâu ra**, cái kia nói **đã có ai đọc chưa**.
- Bốn `ReviewReason` **hiển thị** cùng trọng lượng: chúng là bốn loại nghi ngờ, không phải bốn mức
  nghiêm trọng. Nhưng khi nhiều điều kiện cùng đúng thì việc **chọn lý do nào để báo** có thứ tự, và
  thứ tự đó nằm ở `review_policy.py` chứ không ở giao diện. Hai chuyện khác nhau.

## Nơi luật này đang được thi hành

- `packages/contracts/src/contracts/messages.py` — `GradingCompleted` cố ý không có trường
  `needs_teacher_review`.
- `services/be/src/be/review_policy.py` — `decide_review()`, nơi duy nhất so ngưỡng.
- `services/be/src/be/routes.py` — ngưỡng áp lúc đọc, không lưu kèm kết quả.
- `services/fe/src/App.tsx` — chỉ `toFixed(2)`, không so sánh.
- `AGENTS.md` bảng Invariants — dòng `AGENT emits no routing decision` (tự động) và dòng
  `FE never applies its own confidence threshold` (kiểm bằng review).
- Test `test_agent_emits_no_routing_decision`.
- **Phần phạm vi cho pha 2: chưa thi hành ở đâu cả.** Agent chưa sinh câu biến thể nào và chưa dẫn
  cuộc hội thoại nào, nên chưa có đầu ra nào để mà kiểm.
- Figma `mOe2ZmrqOq1Uix45v6PNGD` — `Thinking` (`83:76`) năm luật; `Confidence meter` (`5:32`) không có màu;
  `Source citation` (`84:35`) luật tra ngược.
