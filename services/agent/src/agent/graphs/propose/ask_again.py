"""Các tín hiệu hỏi model lại đúng một lần (`AskAgain` và họ hàng), kèm lý do cho lần hỏi lại."""

from agent.graphs.propose.outline import Miscount
from contracts import MOST_CLARIFY_QUESTIONS, NextStepCompleted


class AskAgain(ValueError):
    """Một đề nghị hỏng theo kiểu hỏi lại model một lần thường là sửa được.

    Attributes:
        hint: Lý do nói với model ở lần hỏi lại, khi lệch có hệ thống -- một lần hỏi lại mù dễ ra
            lại đúng câu cũ (review pha 5, `kriky-writes-every-word`). Rỗng thì hỏi lại y như lần
            đầu.
    """

    hint = ""


class NothingToSay(AskAgain):
    """Model chọn `say`, `ask_clarify` hay `outline` mà để `text` rỗng."""


class Flawed(AskAgain):
    """Một đề nghị dùng được nhưng thiếu một thứ: mang nó theo, để lần hỏi lại hỏng thì còn nó.

    Lưới hỏi lại không bao giờ được làm kết quả tệ hơn khi chưa có nó (review T2b,
    `unbiased-model-text`): lần hai hỏng kiểu khác -- im lặng, provider lỗi -- thì giữ đề nghị lần
    đầu. Lần hai cũng thiếu thì giữ lần hai cho plan, vì cả hai đều tới BE và BE tự xét; với câu hỏi
    thì giữ lần có nhiều lựa chọn hơn (review T3: lần hai có thể còn ít hơn lần đầu).
    """

    def __init__(self, flaw: str, step: NextStepCompleted) -> None:
        super().__init__(flaw)
        self.step = step


class IncompletePlan(Flawed):
    """Model nêu plan mà một bước thiếu tham số bắt buộc của tool ấy.

    Đo được khi `soan-de` bắt ghi giá trị bốn mục vào `known` (`unbiased-model-text` T2b): hỏi thừa
    giảm từ 80/192 xuống 1/192, nhưng ~11/192 plan nêu `create_draft` không kèm tham số nào -- giá
    trị đã nằm ở `known`, model không chép sang. BE `vet_plan` từ chối đúng những plan ấy, và giáo
    viên nhận một lời từ chối cho một câu đã đủ ý. Hỏi lại ở đây rẻ hơn.
    """


class NoOutline(AskAgain):
    """Model chọn `outline` mà không nêu mục nào, hay một mục không đọc được (`draft-outline`)."""


class UncountedOutline(Flawed):
    """Dàn ý có tổng câu khác số câu model vừa ghi trong `known`, hay dàn ý thay câu không phải đúng
    một mục một câu (`draft-outline`). Đo ở bench run-98: *"6 câu"* ra dàn ý 4 mục × 2 câu; *"thay
    câu 2"* ra dàn ý nêu lại cả đề.

    Lần hỏi lại phải nói **số câu đúng** (review code pha 5, plan `backlog-tier-1`): hint rỗng thì
    model không biết sai ở đâu, và lần hai ra đúng dàn ý ấy.
    """

    def __init__(self, flaw: Miscount, step: NextStepCompleted) -> None:
        super().__init__(str(flaw), step)
        # Đọc trường của `Miscount`, không đọc chuỗi log: đổi câu log từng đổi lời nhắc mà không
        # test nào đỏ (backlog, chia `propose.py` 20/10/2026).
        if flaw.source == "replace":
            self.hint = (
                "Dàn ý thay câu chỉ có đúng một mục, mục ấy một câu: chỉ cho câu bị thay. Nêu lại."
            )
        elif flaw.source == "known":
            # Con số là của **model** (`known`), không phải lời giáo viên: nói đúng nguồn, để model
            # tự xét lại cả `known` khi giáo viên vừa đổi số câu (review code vòng 2).
            n = flaw.wanted
            self.hint = (
                f"Bạn ghi question_count={n} trong known mà tổng số câu của dàn ý khác {n}. Nêu "
                "lại dàn ý đủ đúng số câu giáo viên xin, và sửa known nếu giáo viên vừa đổi số câu."
            )
        else:
            n = flaw.wanted
            self.hint = (
                f"Giáo viên xin {n} câu: tổng số câu của các mục trong dàn ý phải đúng {n}. "
                "Nêu lại dàn ý."
            )


class AnsweredUnread(Flawed):
    """Lượt hỏi về sách mà model trả lời khi chưa mở mục nào kể từ câu hỏi (`ask-the-document`).

    Thử tay case 18 (26/10/2026, Haiku): *"bài nào nói về số La Mã?"* -- mục ấy là mục con của *Cách
    ghi số tự nhiên*, label chương không lộ ra, và model nói *"mình chưa đọc nên chưa chỉ đúng
    trang"* thay vì mở mục. Hai lần đổi chữ `BOOK_QUESTIONS` không giữ được nó. Hỏi lại một lần;
    lần hai vẫn trả lời thì giữ lần hai -- *"sách không có phần này"* đọc từ mục lục là lời đúng.
    """

    hint = (
        "Bạn trả lời về tài liệu mà lượt này chưa mở mục nào. Điều được hỏi có thể nằm trong một "
        "bài hay mục con: gọi get_chapter các node có thể chứa nó, hay read_section (không "
        "questions) mục nói về nó, rồi mới trả lời. Chỉ trả lời ngay khi mục lục đã cho thấy "
        "tài liệu không có điều ấy."
    )


class AskedWhatWasKnown(Flawed):
    """Model hỏi lại trong khi chính `known` của nó đã ghi đủ bốn mục (Tier 2 câu 33 = A, 21/10).

    Thử tay V6 (20/10/2026, Haiku): *"Bạn cho mình biết thêm một điều nhé:"* rồi hết -- không câu
    hỏi, không nút, giáo viên kẹt; 4/10 lần hỏi lại hôm ấy `known` đã đủ. Hỏi lại model một lần, kèm
    lời nhắc nêu dàn ý.
    """

    hint = (
        "Bạn đã ghi đủ môn, khối, phạm vi và số câu trong known, nên không còn gì để hỏi "
        "giáo viên. Đừng hỏi lại: hãy nêu dàn ý (kind=outline)."
    )


class PlanOverRevision(Flawed):
    """Model nêu plan soạn ngay sau lời giáo viên **xin sửa** dàn ý: plan ấy soạn theo dàn ý cũ mà
    giáo viên vừa xin đổi (plan `backlog-tier-1`, pha 3: *Plan soạn … sau một lời xin sửa dàn ý vẫn
    qua cổng*; cổng BE chỉ
    đòi một dàn ý ở lượt ngay trước, plan `backlog-tier-1`)."""

    hint = (
        "Giáo viên vừa xin SỬA dàn ý, chưa đồng ý soạn. Đừng nêu plan soạn: nêu lại dàn ý đã sửa "
        "đúng lời giáo viên (kind=outline), rồi chờ giáo viên đồng ý."
    )


class WrongQuestion(Flawed):
    """Model hỏi lại ngay sau danh sách tài liệu mà không hỏi tài liệu nào -- nút của câu hỏi là các
    tài liệu (`which_book`, `kriky-writes-every-word`)."""

    hint = (
        "Câu hỏi vừa rồi không hợp: ngay sau danh sách tài liệu, các nút giáo viên bấm là tên tài "
        "liệu, nên câu hỏi phải hỏi giáo viên soạn theo tài liệu nào. Viết lại câu hỏi ấy."
    )


class TooManyQuestions(Flawed):
    """Model hỏi hơn `MOST_CLARIFY_QUESTIONS` câu một lượt (ADR-32). Đề nghị mang theo đã giữ đủ
    trần -- lần hai vẫn vậy thì ba câu đầu đi tiếp."""

    hint = (
        f"Một lượt hỏi lại có nhiều nhất {MOST_CLARIFY_QUESTIONS} câu. Gộp hay bỏ bớt câu, giữ "
        "những điều giáo viên thật sự phải trả lời."
    )


class FewChoices(Flawed):
    """Model hỏi lại mà đưa ít lựa chọn hơn mức người dùng chốt (`unbiased-model-text` T3: ít nhất
    3)."""
