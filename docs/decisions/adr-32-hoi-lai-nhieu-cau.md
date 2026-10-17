# ADR-32 — Hỏi lại tối đa ba câu một lượt

- **Trạng thái:** đã chốt, chưa thi hành
- **Ngày:** 2026-10-17

## Bối cảnh

Tới ngày 17/10/2026, một câu hỏi lại (`ask_clarify`) là **một** câu và **một** bộ nút. Skill `soan-de`
dặn hỏi gộp mọi mục còn thiếu trong một lần, nhưng nút chỉ cho **một** mục. Thử tay case 01: Kriky hỏi
khối, phạm vi và số câu trong một câu; nút chỉ có *Khối 6 / 7 / 8*, hai ý còn lại giáo viên phải gõ.

## Quyết định

- **Một lượt hỏi lại chở tối đa ba câu.** Mỗi câu có một **nhãn ngắn** (*"Khối"*, *"Số câu"*), chữ câu
  hỏi, và bộ nút riêng — tất cả do model viết, nút dựng theo luật của
  [ADR-23](adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md). Lời Kriky mở đầu thẻ cũng do model viết
  ([ADR-30](adr-30-loi-kriky-do-model-viet.md)). Một câu duy nhất vẫn là thẻ hỏi lại như cũ.
- **Câu hỏi về một dòng** (lớp, tài liệu, mục — nút là nhãn BE dựng từ hàng đã đọc, ADR-23) thì một
  lượt chỉ một câu: hệ thống giữ câu đầu và nhãn của nó.
- **Thẻ hiện từng câu**, có `Câu k/n`, nút *Câu trước* và *Câu sau*. **Không bỏ câu:** chưa trả lời câu
  đang xem thì không sang câu sau. Mỗi câu vẫn có lối *Khác…* để gõ.
- **Trả lời đủ thì có màn tóm tắt** các lựa chọn, sửa lại được từng câu, rồi mới gửi.
- **Gửi gộp một tin**, dạng *"Nhãn: trả lời · Nhãn: trả lời"* — ví dụ *"Khối: Khối 7 · Số câu: 5 câu
  · Phạm vi: tỉ lệ thức"*. Tin ấy là câu của giáo viên, đi vào hội thoại như mọi câu khác.

Skill `soan-de`: luật *"choices cho MỘT mục ghi ?"* thôi áp dụng; mỗi mục ghi `?` một câu, tối đa ba.

## Vì sao

**Mỗi ý một bộ nút** để giáo viên không phải gõ lại thứ bấm được. **Ba câu** là đủ cho ca thường gặp
nhất (khối, phạm vi, số câu); nhiều hơn là một biểu mẫu, không còn là hỏi lại.

**Gửi một lần, không gửi từng nút**: mỗi lần gửi là một lượt gọi model, và giữa hai lượt model có thể
đổi ý hỏi khác. **Nhãn đi kèm câu trả lời** để model không phải đoán câu trả lời nào của câu hỏi nào,
và giáo viên đọc lại bong bóng của mình hiểu ngay. **Không bỏ câu** vì câu nào được hỏi là câu thiếu;
bỏ nó thì lượt sau model hỏi lại đúng câu ấy.

## Hệ quả

- Hợp đồng `NextStepCompleted` có thêm danh sách câu hỏi; BE lưu chúng cùng lượt hỏi để đọc lại sau F5.
- Đang trả lời dở mà F5 thì các lựa chọn chưa gửi mất; thẻ hiện lại từ câu đầu.
- Lịch sử gửi model mang cả lời mở lẫn từng câu, để lượt sau model đọc được câu trả lời gộp.

## Nơi luật này đang được thi hành

Plan thi hành: `docs/plans/active/2026-10-17-assessment-title-and-multi-question-plan.md`. Bảng điền
khi plan đóng.
