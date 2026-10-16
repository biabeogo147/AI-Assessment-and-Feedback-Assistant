"""Thông báo của **hệ thống** trên chat giáo viên -- ngoại lệ 1 của ADR-30
(`kriky-writes-every-word`).

Mọi lời Kriky do model viết. Những câu dưới đây là chỗ model không có mặt để viết: model hỏng, lượt
chạm trần bước, lượt gãy giữa chừng, không với tới AGENT, đoạn chat đang chạy một việc khác. Chúng
hiện như thông báo hệ thống (lượt `notice`), không avatar, không giọng của Kriky.

Một chỗ cho mọi câu ấy **của BE**. Hai câu AGENT nói khi model hỏng (`handlers._MODEL_DOWN`,
`propose._UNCLEAR`) sống bên AGENT -- hai service không import nhau -- và tự khai `notice=True`.
`tools/check_contract.py` (`check_kriky_says_nothing_fixed`) giữ cho không câu cố định nào vào lời
Kriky: câu ở đây chỉ được đi dưới `kind="notice"`, và một hằng chữ đi vào `say` hay `outline` là một
câu code nói thay model.
"""

# Đoạn chat đang chạy một lượt khác (HTTP 409, ADR-25).
ALREADY_RUNNING = "Đoạn chat này đang chạy một việc. Hãy đợi nó xong rồi gửi tiếp."

# Mức trần số bước của pha lên plan. Chạm tới, không phải đâm vào: câu gọi tên nguyên nhân và gợi
# ý đúng một việc có ích -- giáo viên nghe *"có gì đó sai rồi"* thì sẽ hỏi lại đúng câu đó và tiêu
# đúng lượng ngân sách đó để đụng đúng cái mức trần đó.
CEILING_REACHED = (
    "Kriky tra mãi mà chưa ra câu trả lời gọn cho câu này. Bạn thử hỏi cụ thể hơn, ví dụ nói rõ "
    "tên lớp và tên bài kiểm tra."
)

# Mức trần chạm tới vì model cứ nêu plan BE không nhận (review pha 5, `kriky-writes-every-word`):
# câu trần chung bảo *"nói rõ tên lớp"* là gợi ý sai. Lý do từng lần từ chối đã về model; câu này
# nói với giáo viên chỗ vướng.
PLAN_REFUSED = (
    "Kriky chưa dựng được các bước cho việc này. Bạn thử nói lại cụ thể hơn: việc gì, cho lớp hay "
    "đề nào."
)
BOOK_SCOPE_MISSING = (
    "Đoạn chat này đang soạn theo tài liệu {filename}, nên Kriky cần biết chương hay bài nào trong "
    "đó. Bạn nói tên chương, bài nhé. Muốn soạn đề không theo tài liệu thì mở một đoạn chat mới."
)
BOOK_NOT_READY = (
    "Tài liệu {filename} chưa dùng được để soạn đề -- nó còn đang xử lý, hoặc xử lý không thành. "
    "Bạn chờ tài liệu sẵn sàng rồi gửi lại, hoặc đính một tài liệu khác."
)

# Lượt gãy giữa stream: header đã gửi đi rồi, nên không còn status code nào để nói.
TURN_BROKE = "Lượt này hỏng giữa chừng. Bạn thử gửi lại câu vừa rồi nhé."

# Không với tới AGENT (HTTP 503).
AGENT_UNAVAILABLE = "Kriky chưa trả lời được. Bạn thử lại sau một chút nhé."

# Các bước của plan đã chạy, mà model không kể lại được. Kết quả từng bước vẫn nằm trong khối bước
# ngay trên, nên câu này chỉ nói vì sao không có lời kể -- không dựng lời kể thay model.
REPORT_MISSING = (
    "Kriky chưa kể lại được kết quả lượt này. Các bước đã chạy và kết quả của chúng ở khối ngay "
    "trên."
)
