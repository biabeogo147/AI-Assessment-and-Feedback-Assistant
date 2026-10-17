# ADR-31 — Tên đề kiểm tra: tối đa 60 ký tự, giáo viên đổi được

- **Trạng thái:** đã chốt, chưa thi hành
- **Ngày:** 2026-10-17

## Bối cảnh

Tới ngày 17/10/2026, tên một đề do hệ thống đặt lúc mở đề nháp: `"Đề " + phạm vi` model ghi, cắt ở
160 ký tự (độ dài cột). Đề soạn theo sách có phạm vi là cả chuỗi nhãn bài kèm số trang, nên tên ra
kiểu *"Đề Bài 1. TẬP HỢP (tr. 5–9), CÁCH GHI SỐ TỰ NHIÊN (tr. 9–13), …"*. Thẻ *Đã tạo đề "…"* trong
chat vỡ thành nhiều dòng và đẩy chip *"Chưa duyệt · chưa phát hành"* đi. Giáo viên không có cách nào
sửa tên ấy.

## Quyết định

- **Tên đề tối đa 60 ký tự**, cho cả tên hệ thống đặt lẫn tên giáo viên gõ.
- **Tên hệ thống đặt:** đề soạn từ sách là `"Đề " + tên tệp sách` bỏ phần đuôi (`.pdf`); đề không
  sách là `"Đề " + phạm vi`, bỏ số trang `(tr. …)`. Dài hơn 60 thì cắt ở ranh giới từ, kèm `…`.
- **Giáo viên đổi được tên đề** khi đề **chưa duyệt** — cùng khoá với nội dung câu hỏi
  ([ADR-01](adr-01-vong-doi-de-kiem-tra.md)): đề đã duyệt hay đã phát hành thì phải *Hoàn tác* trước.
  Tên trống bị từ chối. Tên giáo viên gõ dài hơn 60 bị **từ chối**, không bị cắt lặng lẽ: chữ của giáo
  viên chỉ giáo viên sửa.
- **Mọi chỗ hiện tên hiện tại** của đề: panel, danh sách đề, hộp xác nhận phát hành, **cả thẻ kết quả
  và dòng bước cũ trong đoạn chat**. Những chỗ ấy chỉ đọc tên lúc hiện, không giữ một bản sao.
- **Lưới thứ hai ở giao diện:** thẻ kết quả in tên trên một dòng, phần dư thành `…`, rê chuột thì thấy
  đủ tên — cho đề cũ đặt trước luật này, và cho bất cứ đường nào lọt trần.

## Vì sao

**Tên đề là thứ giáo viên đọc lướt.** Rail, thẻ, danh sách đều dùng nó để tìm lại một đề; một chuỗi
nhãn bài dài 150 ký tự không giúp tìm gì, còn làm vỡ chỗ nó nằm. Tên tệp sách là thứ giáo viên đã tự
đặt và nhận ra ngay.

**Đổi tên đi cùng khoá nội dung.** Đề đã duyệt là thứ giáo viên đã ký vào; tên là một phần của thứ ấy
trên hộp phát hành. Giữ một khoá cho cả đề đơn giản hơn hai khoá cho hai phần.

**Thẻ cũ đổi theo tên mới**, dù thẻ là biên bản việc đã xảy ra
([ADR-24](adr-24-mot-giao-vien-nhieu-doan-chat.md)): biên bản ghi *đề nào* (`assessment_id`), không ghi
một cái nhãn; một đề hai tên ở hai chỗ trên cùng màn hình là hai đề với người đọc.

## Hệ quả

- Lượt đọc lại một đoạn chat tra tên hiện tại của mọi đề nó nhắc tới — một truy vấn mỗi lần đọc. Lịch
  sử gửi AGENT cũng mang tên hiện tại, để Kriky gọi đề đúng tên giáo viên vừa đặt.
- Tên đề cũ trong database (dài hơn 60) giữ nguyên; lưới giao diện che chúng.

## Nơi luật này đang được thi hành

Plan thi hành: `docs/plans/active/2026-10-17-assessment-title-and-multi-question-plan.md`. Bảng điền
khi plan đóng.
