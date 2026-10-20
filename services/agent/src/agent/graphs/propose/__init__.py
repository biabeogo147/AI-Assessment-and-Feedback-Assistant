"""Pha lên plan của một lượt chat giáo viên: dựng prompt, rồi chọn.

Module này là **pha 1** của ADR-25. Nó tra cứu, hỏi lại, và khi đã đủ dữ kiện thì nêu một
plan — chứ không bao giờ ghi gì. Lời kể sau khi plan chạy nằm ở `reporting.py`, một task
riêng, vì đầu vào của nó khác hẳn: nó đọc kết quả của cả plan, không đọc catalog.

Hai danh mục tới riêng và điều đó là cố ý: `catalog` là tool gọi được ngay, `plannable` là
tool chỉ hẹn làm được ở pha 2. Model phải thấy cả hai — nó nêu tên tool và tên tham số
trong plan — nhưng phải phân biệt được chúng, vì gọi một tool ghi ngay lượt này sẽ bị BE
từ chối và tiêu một vòng để phát hiện lại đúng điều ấy.

Hai node, và node thứ hai là một lần gọi structured. Nó nhỏ hơn graph soạn đề một cách có
chủ ý: không có loop tự check nhiều vòng, vì một đề nghị thì hoặc được BE thực thi hoặc bị BE
từ chối, và BE là phía duy nhất biết được là cái nào. Có **một** phép kiểm phía AGENT với một
lần gọi lại: đề nghị hỏng hình dạng theo những luật AGENT tự biết (`_Flawed`: plan thiếu bước,
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

Từ `kriky-skill-routing`, prompt là **lõi + skill**. `_CORE` mang những luật không lượt nào được
thiếu; lời dặn chỉ một loại việc cần -- tra lớp, soạn đề -- nằm trong `agent/skills/*.md`, và
`skill_router` (Jev) chọn skill nào được nạp trước khi graph chạy.
"""

from agent.graphs.propose.books import _DOCUMENT_READS, _mentions_book
from agent.graphs.propose.clarify import _OTHER, _answers, _choices_wanted
from agent.graphs.propose.compose import _asked_back, _compose, _describe_tool
from agent.graphs.propose.graph import _UNCLEAR, propose
from agent.graphs.propose.outline import (
    _AGREES,
    _approved_plan,
    _brief_in,
    _miscounted,
    _right_purpose,
)
from agent.graphs.propose.plan_checks import _drafts_over_a_revision
from agent.graphs.propose.prompt import _BOOK_PROCEDURE, _CORE, _LIBRARY, _LIBRARY_SLOT
from agent.graphs.propose.proposal import _Argument, _OutlineItem, _Proposal, _Question, _Step
from agent.graphs.propose.read_order import _asks_which_book, _library_first, _read_before_outline

__all__ = [
    "_AGREES",
    "_Argument",
    "_BOOK_PROCEDURE",
    "_CORE",
    "_DOCUMENT_READS",
    "_LIBRARY",
    "_LIBRARY_SLOT",
    "_OTHER",
    "_OutlineItem",
    "_Proposal",
    "_Question",
    "_Step",
    "_UNCLEAR",
    "_answers",
    "_approved_plan",
    "_asked_back",
    "_asks_which_book",
    "_brief_in",
    "_choices_wanted",
    "_compose",
    "_describe_tool",
    "_drafts_over_a_revision",
    "_library_first",
    "_mentions_book",
    "_miscounted",
    "_read_before_outline",
    "_right_purpose",
    "propose",
]
