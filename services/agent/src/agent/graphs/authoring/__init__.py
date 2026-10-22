"""Viết một câu hỏi, và từ chối giao ra một câu sai hình dạng.

Một loop, vì đây là việc có thể không qua được check của chính nó: model được yêu
cầu một câu hỏi có hình dạng nhất định và đôi khi viết ra một câu không như vậy.
Graph thử lại kèm theo lời phàn nàn, và đó là một việc khác với thử lại rồi hy vọng.

**Đây không phải nơi ADR-18 được thi hành.** BE check lại mọi thứ tới tay nó, và
`packages/contracts` nói rõ vì sao: một bộ sinh tự phán xét đầu ra của mình là tự
chấm bài của mình. Check ở đây là tự QC -- nó tiết kiệm một vòng đi về và một job
queue bỏ đi, và nếu nó có bao giờ không đồng ý với check của BE thì check của BE mới
là cái được tính.

Những gì model được dặn về hình dạng đến từ các decision record, không đến từ sở
thích: đúng một phương án đúng, mỗi distractor mang tên của lỗi mà nó đại diện, và
nhiều hơn một cách giải (ADR-18); còn với một lượt chữa lỗi thì là một câu hỏi kiểm
tra cùng một thứ mà không phải cùng một câu (ADR-17).
"""

from agent.graphs.authoring.brief import draft_brief, retry_brief
from agent.graphs.authoring.checks import normalise
from agent.graphs.authoring.graph import write_question

__all__ = ["write_question", "draft_brief", "retry_brief", "normalise"]
