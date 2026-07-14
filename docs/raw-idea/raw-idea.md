# Bản tổng hợp hiện tại về project

## 1. Mô tả ngắn gọn

Project là một **hệ thống AI Agent hỗ trợ giáo viên ra đề, chấm bài, phân tích lỗi sai và tạo vòng luyện tập thích ứng cho học sinh**.

Hệ thống không chỉ là công cụ sinh đề hoặc chấm trắc nghiệm. Mục tiêu dài hạn là tạo thành một quy trình khép kín:

```text
Giáo viên tạo và duyệt đề
        ↓
Học sinh làm bài
        ↓
AI đánh giá đáp án và cách tư duy
        ↓
AI xác định lỗi sai hoặc misconception
        ↓
AI sinh câu hỏi tương tự để sửa đúng lỗi đó
        ↓
Học sinh luyện tập lặp lại
        ↓
Dừng khi đạt ngưỡng thành thạo
```

Trong toàn bộ quy trình, giáo viên vẫn giữ quyền kiểm soát ở những vị trí quan trọng.

---

# 2. Mục tiêu chính của hệ thống

Hệ thống có bốn mục tiêu nghiệp vụ chính.

## 2.1. Hỗ trợ giáo viên ra đề

Giáo viên cung cấp yêu cầu, ví dụ:

* Nội dung kiến thức.
* Chương hoặc chủ đề.
* Mục tiêu học tập.
* Số lượng câu hỏi.
* Độ khó.
* Loại bài kiểm tra.
* Thời gian làm bài.
* Phạm vi kiến thức.
* Các ràng buộc khác.

AI Agent dựa trên yêu cầu đó để tạo:

* Đề kiểm tra.
* Các phương án trắc nghiệm.
* Đáp án đúng.
* Cách giải.
* Giải thích cho từng phương án sai, nếu cần.
* Metadata của câu hỏi như độ khó, chủ đề và kỹ năng được kiểm tra.

AI không tự phát hành đề ngay. Giáo viên phải review trước.

---

## 2.2. Hỗ trợ chấm và nhận xét

Sau khi học sinh làm bài, AI sẽ:

* Kiểm tra đáp án.
* Chấm điểm.
* Phân tích cách làm, nếu học sinh có cung cấp.
* Dự đoán lỗi sai, nếu không có phần giải thích.
* Xác định misconception hoặc lỗ hổng kiến thức.
* Sinh nhận xét phù hợp.
* Tính mức độ tin cậy của kết quả đánh giá.

Kết quả có độ tin cậy thấp sẽ được chuyển cho giáo viên xem xét.

---

## 2.3. Cá nhân hóa việc luyện tập

Sau khi phát hiện lỗi sai, AI không chỉ giải thích đáp án đúng mà còn sinh thêm câu hỏi tương tự.

Câu hỏi mới phải được tạo dựa trên:

* Kiến thức mà học sinh đang yếu.
* Loại lỗi mà học sinh vừa mắc.
* Mức độ thành thạo hiện tại.
* Lịch sử trả lời trước đó.
* Độ khó phù hợp.
* Mục tiêu tránh lặp lại nguyên văn câu hỏi cũ.

Học sinh tiếp tục làm các câu mới và hệ thống lặp lại quá trình đánh giá.

---

## 2.4. Theo dõi mức độ thành thạo

Hệ thống duy trì trạng thái học tập của từng học sinh, có thể bao gồm:

* Số câu đã làm.
* Tỷ lệ đúng.
* Những kiến thức đã thành thạo.
* Những kiến thức còn yếu.
* Các lỗi sai thường gặp.
* Số lần lặp lại cùng một lỗi.
* Mức độ tự tin của hệ thống khi đánh giá.
* Tiến độ đạt ngưỡng mastery.

Vòng luyện tập kết thúc khi học sinh đạt một ngưỡng đã được định nghĩa.

---

# 3. Các actor chính

## 3.1. Giáo viên — Teacher

Giáo viên là người có quyền kiểm soát nghiệp vụ cao nhất.

Giáo viên có thể:

* Nhập prompt hoặc yêu cầu ra đề.
* Chọn loại bài kiểm tra.
* Thiết lập cấu hình đề.
* Yêu cầu AI sinh đề.
* Xem đề AI tạo.
* Chỉnh sửa câu hỏi.
* Chỉnh sửa đáp án và lời giải.
* Yêu cầu AI tạo lại một phần hoặc toàn bộ đề.
* Duyệt đề.
* Phát hành đề.
* Xem kết quả học sinh.
* Xem các bài có confidence thấp.
* Chỉnh sửa nhận xét của AI.
* Xác nhận hoặc thay đổi điểm.
* Theo dõi tiến độ học tập của học sinh.

Điểm quan trọng:

> Teacher-in-the-loop không có nghĩa là giáo viên phải duyệt mọi hành động của AI.

Giáo viên bắt buộc tham gia ở các điểm cần kiểm soát, đặc biệt là:

* Duyệt đề trước khi phát hành.
* Xử lý những kết quả chấm có độ tin cậy thấp.
* Xử lý trường hợp bất thường hoặc mâu thuẫn.

---

## 3.2. Học sinh — Student

Học sinh có thể:

* Xem bài kiểm tra được giao.
* Làm câu hỏi trắc nghiệm.
* Chọn đáp án.
* Giải thích cách làm trong trường hợp được yêu cầu.
* Nộp bài.
* Xem kết quả và nhận xét.
* Làm các câu hỏi luyện tập tương tự.
* Theo dõi tiến độ thành thạo.

Học sinh không trực tiếp quyết định xem AI chấm đúng hay sai, nhưng kết quả của học sinh có thể được giáo viên xem xét khi hệ thống không đủ tự tin.

---

## 3.3. AI/LLM Provider

Đây là hệ thống bên ngoài cung cấp khả năng AI, ví dụ mô hình ngôn ngữ hoặc mô hình chuyên biệt.

Nó không phải actor nghiệp vụ giống giáo viên và học sinh, nhưng là một external system mà ứng dụng sẽ kết nối.

---

# 4. Vòng tạo đề của giáo viên

Tôi đang hiểu quy trình tạo đề như sau:

```text
Giáo viên
    ↓
Nhập prompt và các ràng buộc
    ↓
AI Agent phân tích yêu cầu
    ↓
AI sinh đề kiểm tra
    ↓
AI sinh đáp án và cách giải
    ↓
Giáo viên review
    ↓
Đề chưa phù hợp?
 ┌───────┴────────┐
 Có               Không
 ↓                 ↓
Chỉnh sửa hoặc     Duyệt đề
yêu cầu sinh lại       ↓
                   Phát hành
```

## 4.1. Hai loại bài kiểm tra chính

Hiện tại hệ thống phân biệt ít nhất hai loại:

### Kiểm tra thường xuyên

Đặc điểm dự kiến:

* Thực hiện sau mỗi buổi học hoặc mỗi phần kiến thức.
* Câu hỏi tương đối dễ.
* Số bước suy luận ít.
* Lỗi sai có thể dễ dự đoán hơn.
* Tập trung vào phản hồi nhanh và luyện tập.

### Kiểm tra cuối kỳ hoặc bài khó

Đặc điểm dự kiến:

* Câu hỏi khó hơn.
* Có thể cần nhiều bước suy luận.
* Chỉ dựa vào phương án trắc nghiệm là không đủ để biết học sinh sai ở đâu.
* Học sinh cần giải thích cách làm.
* AI phân tích cả đáp án lẫn lời giải thích.

Hai loại này có thể dùng chung cấu trúc đề, nhưng khác nhau ở chính sách đánh giá.

---

# 5. Vòng đánh giá của học sinh

Đây là phần cốt lõi nhất của hệ thống.

## 5.1. Bước chung đầu tiên

```text
Học sinh nhận đề
        ↓
Học sinh làm câu hỏi trắc nghiệm
        ↓
Học sinh chọn đáp án
```

Sau đó hệ thống chia thành hai nhánh.

---

## 5.2. Nhánh A — Bài cuối kỳ, bài khó hoặc bài nhiều bước

```text
Học sinh chọn đáp án
        ↓
Học sinh giải thích cách làm
        ↓
AI đọc đáp án + phần giải thích
        ↓
AI xác định bước đúng và bước sai
        ↓
AI chấm điểm và sinh nhận xét
```

Mục đích của phần giải thích là giúp hệ thống biết:

* Học sinh hiểu đúng khái niệm nào.
* Sai từ bước nào.
* Dùng công thức nào sai.
* Có suy luận đúng nhưng tính toán sai hay không.
* Có chọn đúng đáp án bằng cách làm sai hay đoán hay không.
* Lỗi thuộc kiến thức, suy luận hay tính toán.

Trong nhánh này, AI không nên chỉ so sánh đáp án cuối cùng.

Ví dụ:

```text
Đáp án đúng + cách làm đúng
→ Kết quả hoàn toàn đúng.

Đáp án sai + phần đầu cách làm đúng
→ Học sinh hiểu khái niệm nhưng sai ở bước tính toán.

Đáp án đúng + cách làm sai
→ Không nên mặc định học sinh đã thành thạo.

Đáp án sai + cách làm sai từ khái niệm
→ Có misconception cần sửa.
```

---

## 5.3. Nhánh B — Kiểm tra thường xuyên, bài dễ hoặc ít bước

```text
Học sinh chọn đáp án
        ↓
AI không bắt buộc học sinh giải thích
        ↓
AI dự đoán lỗi sai từ phương án đã chọn
        ↓
AI chấm điểm và sinh nhận xét
```

Việc dự đoán lỗi có thể dựa trên:

* Phương án sai mà học sinh chọn.
* Cách các distractor được thiết kế.
* Lỗi sai được gắn sẵn với từng phương án.
* Lịch sử lỗi của học sinh.
* Những câu trả lời trước đó.
* Mức độ thành thạo hiện tại.

Ví dụ:

```text
Đáp án A: đúng.

Đáp án B: quên đổi dấu.

Đáp án C: áp dụng sai công thức.

Đáp án D: nhầm thứ tự thực hiện phép tính.
```

Khi học sinh chọn C, hệ thống có căn cứ để dự đoán rằng học sinh đã áp dụng sai công thức.

Đây là lý do các phương án sai không nên được sinh ngẫu nhiên. Mỗi distractor nên đại diện cho một lỗi có ý nghĩa.

---

# 6. AI chấm và nhận xét

Sau khi có dữ liệu từ một trong hai nhánh, AI thực hiện:

```text
Dữ liệu bài làm
+ đáp án chuẩn
+ lời giải chuẩn
+ rubric
+ lời giải thích của học sinh, nếu có
+ lịch sử học tập
        ↓
AI đánh giá
        ↓
Điểm số
+ nhận xét
+ lỗi sai
+ misconception
+ confidence
```

Kết quả chấm dự kiến gồm:

* Đúng hoặc sai.
* Điểm đạt được.
* Bước sai.
* Loại lỗi.
* Chủ đề kiến thức liên quan.
* Nhận xét cho học sinh.
* Khuyến nghị học lại.
* Mức độ tin cậy.
* Có cần giáo viên review hay không.

---

# 7. Confidence và Teacher Review

Tôi hiểu chính sách hiện tại như sau:

```text
AI hoàn thành chấm bài
        ↓
AI tính confidence
        ↓
Confidence có đạt ngưỡng không?
   ┌─────────┴─────────┐
  Không                Có
   ↓                    ↓
Chuyển giáo viên       AI có thể tự
xem xét                công bố kết quả
```

## 7.1. Khi confidence thấp

Bài được đưa vào `Teacher Review Queue`.

Giáo viên có thể:

* Xem câu hỏi.
* Xem đáp án chuẩn.
* Xem câu trả lời học sinh.
* Xem phần giải thích của học sinh.
* Xem nhận xét của AI.
* Xem lý do AI không tự tin.
* Xác nhận kết quả AI.
* Sửa điểm.
* Sửa loại lỗi.
* Sửa nhận xét.
* Yêu cầu AI phân tích lại.

## 7.2. Khi confidence cao

Hệ thống có thể:

* Lưu kết quả.
* Hiển thị phản hồi cho học sinh.
* Cập nhật hồ sơ năng lực.
* Sinh câu hỏi luyện tập tiếp theo.

Điểm cần nhấn mạnh:

> Giáo viên chỉ bắt buộc review khi confidence không đạt ngưỡng hoặc xuất hiện điều kiện bất thường.

Điều này khác với vòng tạo đề, nơi giáo viên luôn review trước khi phát hành.

---

# 8. Vòng luyện tập thích ứng

Sau khi AI xác định lỗi sai, hệ thống tạo câu hỏi mới.

```text
Lỗi sai của học sinh
        ↓
Xác định kiến thức hoặc misconception
        ↓
Sinh câu hỏi tương tự
        ↓
Điều chỉnh độ khó
        ↓
Học sinh làm câu hỏi mới
        ↓
AI đánh giá lại
        ↓
Cập nhật mastery
        ↓
Đạt ngưỡng?
   ┌────────┴────────┐
  Chưa               Đạt
   ↓                  ↓
Sinh câu tiếp       Kết thúc vòng
```

## 8.1. “Câu hỏi tương tự” không có nghĩa là sao chép câu cũ

Câu hỏi mới nên giữ lại:

* Cùng mục tiêu kiến thức.
* Cùng loại kỹ năng.
* Có thể cùng misconception cần kiểm tra.

Nhưng có thể thay đổi:

* Dữ kiện.
* Ngữ cảnh.
* Giá trị số.
* Cách diễn đạt.
* Mức độ khó.
* Số bước suy luận.

## 8.2. Mục tiêu của vòng lặp

Không chỉ làm cho học sinh trả lời đúng một câu, mà phải xác định học sinh đã thực sự hiểu.

Ví dụ:

```text
Sai do áp dụng nhầm công thức
    ↓
Sinh câu mới kiểm tra đúng công thức đó
    ↓
Nếu tiếp tục sai:
    giảm độ khó hoặc cung cấp hướng dẫn
    ↓
Nếu trả lời đúng:
    sinh câu khác cùng kỹ năng nhưng biến đổi ngữ cảnh
    ↓
Nếu đúng ổn định:
    đánh dấu đạt mastery
```

---

# 9. Mastery — Ngưỡng thành thạo

Mastery là điều kiện dừng của vòng luyện tập.

Tôi chưa hiểu ngưỡng này là một điểm duy nhất cho toàn bài hay được tính theo từng kiến thức. Về mặt thiết kế lâu dài, hợp lý hơn nếu có nhiều mức:

* Mastery của từng `Learning Objective`.
* Mastery của từng `Topic`.
* Mastery của một practice session.
* Mastery tổng quát của học sinh.

Ví dụ minh họa:

```text
Học sinh làm đúng 1 câu
→ Chưa chắc đã mastery.

Học sinh làm đúng nhiều câu có biến thể khác nhau
→ Confidence về mastery tăng.

Học sinh lặp lại cùng một lỗi
→ Mastery giảm hoặc giữ nguyên.

Học sinh làm đúng nhưng cách giải sai
→ Không nên tăng mastery tối đa.
```

Công thức cụ thể chưa được chốt.

