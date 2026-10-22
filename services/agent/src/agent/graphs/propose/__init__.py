"""Pha lên plan của một lượt chat giáo viên: dựng prompt, rồi chọn.

Module này là **pha 1** của ADR-25. Nó tra cứu, hỏi lại, và khi đã đủ dữ kiện thì nêu một
plan — chứ không bao giờ ghi gì. Lời kể sau khi plan chạy cũng đi qua đây (ADR-25, hậu ký
22/10/2026): BE hỏi thêm một lượt với chỉ tool đọc (có `last_plan`) và `plannable` rỗng; kể thế nào
là bước 6 của skill `soan-de`.

Hai danh mục tới riêng và điều đó là cố ý: `catalog` là tool gọi được ngay, `plannable` là
tool chỉ hẹn làm được ở pha 2. Model phải thấy cả hai — nó nêu tên tool và tên tham số
trong plan — nhưng phải phân biệt được chúng, vì gọi một tool ghi ngay lượt này sẽ bị BE
từ chối và tiêu một vòng để phát hiện lại đúng điều ấy.

Hai node, và node thứ hai là một lần gọi structured. Nó nhỏ hơn graph soạn đề một cách có
chủ ý: không có loop tự check nhiều vòng, vì một đề nghị thì hoặc được BE thực thi hoặc bị BE
từ chối, và BE là phía duy nhất biết được là cái nào. Có **một** phép kiểm phía AGENT với một
lần gọi lại: đề nghị hỏng hình dạng theo những luật AGENT tự biết (`Flawed`: plan thiếu bước,
dàn ý không đếm câu, quá ba câu hỏi, câu tham số ít nút, plan soạn ngay sau lời xin sửa dàn ý)
thì model được hỏi lại đúng một lần kèm lý do.

Thứ module này cẩn thận với là prompt. Model đang chọn từ một danh sách tool nó chưa
từng thấy và đọc dữ liệu nó không tự lấy, nên cả hai phải tới dưới dạng nó làm việc
được: tên tool viết đúng chính xác như cách BE dispatch, và kết quả tool ở dạng dữ
liệu chứ không phải văn xuôi kể về dữ liệu.

System prompt mang ba luật không phải chuyện văn phong. AGENT không được nhận là mình
đã làm gì -- nó đề nghị, BE hành động (ADR-05). Nó không được nói với giáo viên nên
chọn phương án nào khi lựa chọn đó là một quyết định sư phạm, vì giáo viên giữ thẩm
quyền ấy. Và nó hỏi lại chứ không đoán khi một cái tên có thể mang nhiều nghĩa, đó là
cổng kiểm đầu vào của ADR-05.

Từ `kriky-skill-routing`, prompt là **lõi + skill**. `CORE` mang những luật không lượt nào được
thiếu; lời dặn chỉ một loại việc cần -- tra lớp, soạn đề -- nằm trong `agent/skills/*.md`, và
`skill_router` (Jev) chọn skill nào được nạp trước khi graph chạy.
"""

# Chỉ `propose` là điểm vào cho code ngoài package; mọi tên khác import thẳng từ submodule của
# nó. Đừng re-export `compose` hay `choose` ở đây: chúng trùng tên submodule, và re-export là che
# mất submodule (`agent.graphs.propose.choose` thành hàm).
from agent.graphs.propose.graph import propose

__all__ = ["propose"]
