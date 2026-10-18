# ADR-35 — Sửa lời giải sau khi phát hành là sửa bản trong ngân hàng

- **Trạng thái:** đã chốt, đang thi hành
- **Ngày:** 2026-10-18

## Bối cảnh

[ADR-19](adr-19-bao-cao-giai-thich-chua-ro.md) hình dung một vòng khép kín: học sinh nói lời giải khó
hiểu, giáo viên xem, giáo viên sửa lời giải đã lưu, ngân hàng câu hỏi tốt lên. Nhưng câu bị báo cáo
nằm trong một đề **đã phát hành**, mà duyệt thì khoá nội dung đề
([ADR-01](adr-01-vong-doi-de-kiem-tra.md)):
- học sinh đã làm bài trên chính câu ấy;
- `Answer.option_id` trỏ vào phương án của nó;
- điểm đã chấm theo nó.

Lúc mở plan Figma, thiết kế đầu tiên của màn báo cáo cho sửa lời giải ngay tại chỗ.

## Quyết định

- **Câu nằm trong đề đã phát hành không bao giờ sửa.** Màn báo cáo
  ([ADR-34](adr-34-hang-doi-review-va-diem-gop.md)) và màn câu có tỉ lệ sai cao chỉ đọc: đề bài, phương
  án, cách giải.
- **Sửa là sửa bản trong ngân hàng câu hỏi.** Nút *Chỉnh sửa trong Ngân hàng câu hỏi* mở bản ngân hàng
  của câu ấy ở màn 22b. Bản ấy là bản chép **từ** câu, nếu câu đã được duyệt
  ([ADR-28](adr-28-ngan-hang-cau-hoi-ghi-khi-duyet.md)); hay là dòng câu được chép **từ**, nếu câu lấy
  từ ngân hàng ra (việc 17). Câu không có bản ngân hàng nào thì không có nút.
- Đề sau lấy câu từ ngân hàng dùng bản đã sửa. Đề đã phát hành giữ bản đã có.

## Vì sao

Sửa câu của một đề đã có bài làm là đổi đề bài dưới chân những em đã làm: một lời giải mới có thể kết
luận một phương án khác, và điểm đã chấm theo bản cũ thì không còn khớp với cái màn hình đang hiện.
Ngân hàng thì có vòng đời riêng (ADR-28): nó là thứ được phép tốt lên theo thời gian. Đặt chỗ sửa ở
đó giữ được vòng ADR-19 nói tới mà không phá lời hứa *đã phát hành là đã khoá*.

Người dùng chốt điều này ở buổi review Figma lần 1 (18/10/2026): *"Không sửa lời giải ở Bảng theo dõi"*.

## Hệ quả

- Học sinh đang chữa bài trên một lời giải khó hiểu vẫn đọc lời giải ấy tới hết bài. Đây là cái giá
  ADR-19 đã chấp nhận: báo cáo không chặn gì.
- Bản ngân hàng đã sửa có thể bị đè khi đề gốc được bỏ duyệt rồi duyệt lại, vì `file_approved` ghi đè
  theo `question_id`. Chỗ hở này chờ người dùng chốt (`docs/plans/backlog.md`).

## Nơi luật này đang được thi hành

- `services/be/src/be/teacher_board.py`: `ReportedQuestion.bank_id`, `WrongRateQuestion.bank_id`. Cả hai
  lấy từ `_bank_ids`, đọc hai chiều chép. Không có route ghi nào vào `questions`.
- `services/be/src/be/teacher_reads.py`: `edit_bank_question` (màn 22b) chỉ ghi `bank_questions`.
- FE: `services/fe/src/screens/teacher/Dashboard.tsx`; nút dẫn tới `#/teacher/ngan-hang/{bank_id}`.
- Figma: artboard 25 (`657:4265`) và 29 (`699:5667`), không ô sửa nào.
