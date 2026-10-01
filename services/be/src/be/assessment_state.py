"""Vòng đời của một đề, và cái cửa duy nhất làm nó thay đổi.

ADR-01 cho một đề bốn state và hai luật còn quan trọng hơn chính mấy cái state
đó: duyệt thì **khoá nội dung**, và duyệt thì **bỏ được** khi đề chưa phát hành.
Trước khi có module này, state là một string tự do kèm một giá trị mặc định, nên
cả hai luật chỉ là tài liệu.

Mọi thứ làm một đề đổi state đều đi qua `advance`. Một cửa duy nhất chính là
điểm cốt yếu: một bước chuyển state viết thẳng ở đâu đó khác sẽ là một cạnh thứ
năm mà không ai tìm ra được, và thứ mất đầu tiên sẽ là cổng duyệt, vì phát hành
thẳng từ đề nháp chỉ cách đúng một phép gán.

`assert_editable` là nửa còn lại. Lập luận của ADR-01 cho việc khoá nội dung là
"nếu nội dung còn sửa được sau khi duyệt thì việc duyệt không có nghĩa gì" -- nên
mọi đường ghi một câu hỏi đều gọi hàm này trước.
"""

from fastapi import HTTPException

from be.models import Assessment, AssessmentState

# Re-export để một caller chỉ cần một import là hỏi được một câu về vòng đời.
# Phần từ vựng thuộc về schema và nằm trong `models`; phần các cạnh thì thuộc về
# đây.
__all__ = ["AssessmentState", "advance", "assert_editable"]


# Toàn bộ vòng đời, dưới dạng dữ liệu. Đọc bảng này là cách nhanh nhất để trả
# lời "bây giờ giáo viên làm được X không", câu hỏi mà chat agent sẽ hỏi gần như
# ở mỗi lượt.
_ALLOWED: dict[AssessmentState, frozenset[AssessmentState]] = {
    AssessmentState.EMPTY: frozenset({AssessmentState.HAS_QUESTIONS}),
    AssessmentState.HAS_QUESTIONS: frozenset({AssessmentState.APPROVED}),
    # Cả hai cạnh đi ra từ `approved`: tiến lên phát hành, và lùi về soạn tiếp.
    # Cạnh lùi là bỏ duyệt, thứ ADR-01 bắt buộc phải có và cũng là thứ ADR-01
    # chỉ riêng ra như hành động duy nhất hạ một state xuống -- nên nó là cạnh
    # cần được ghi lại trong hội thoại nhất.
    AssessmentState.APPROVED: frozenset({AssessmentState.PUBLISHED, AssessmentState.HAS_QUESTIONS}),
    # Để trống có chủ đích. Thu hồi là cạnh của ADR-02, không phải một lần bỏ
    # duyệt, và nó không đưa đề về trạng thái soạn được.
    AssessmentState.PUBLISHED: frozenset(),
}

_EDITABLE = frozenset({AssessmentState.EMPTY, AssessmentState.HAS_QUESTIONS})

# Một cụm từ cho mỗi state, bằng tiếng Việt, vì người đọc nó là giáo viên. Câu từ
# chối thì do `advance` và `assert_editable` ghép lại từ mấy cụm này -- đặt cả câu ở
# đây sẽ buộc mỗi caller mới phải thêm một hàng, trong khi cái bất biến thật sự là
# "mỗi state có đúng một cách gọi tên". Tên state viết theo cách giao diện viết, chứ
# không theo cách database viết.
_READABLE = {
    AssessmentState.EMPTY: "chưa có câu hỏi",
    AssessmentState.HAS_QUESTIONS: "đang soạn",
    AssessmentState.APPROVED: "đã duyệt",
    AssessmentState.PUBLISHED: "đã phát hành",
}


def _state_of(assessment: Assessment) -> AssessmentState:
    """Đọc state của một đề, kể cả khi nó chưa từng được lưu.

    Giá trị mặc định của cột do câu INSERT áp vào, nên `Assessment(...)` để
    attribute đó là None cho đến lúc flush. Mọi đường tạo một đề rồi ghi câu hỏi
    đầu tiên của nó trong cùng một unit of work đều đi qua đúng cái khe đó, và
    một đề chưa được lưu xuống thì theo định nghĩa là rỗng -- đúng y những gì giá
    trị mặc định nói, chỉ muộn hơn một câu lệnh.

    Args:
        assessment: Row đó, đã lưu hay chưa lưu.

    Returns:
        State hiện tại, coi "chưa đặt" là `EMPTY`.
    """
    return AssessmentState.EMPTY if assessment.state is None else AssessmentState(assessment.state)


def advance(assessment: Assessment, to: AssessmentState) -> None:
    """Chuyển một đề sang state khác, hoặc từ chối.

    Args:
        assessment: Row cần chuyển. `state` của nó được ghi tại chỗ; commit là
            việc của caller.
        to: State đang được yêu cầu.

    Raises:
        HTTPException: 409 khi không có cạnh nào của ADR-01 nối state hiện tại
            với state được yêu cầu, kèm một câu nêu tên cả hai.

    Side effects:
        Ghi `assessment.state` khi cạnh đó tồn tại.
    """
    current = _state_of(assessment)
    if to not in _ALLOWED[current]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Đề đang ở trạng thái {_READABLE[current]}, "
                f"không chuyển sang {_READABLE[to]} được."
            ),
        )
    assessment.state = to


def assert_editable(assessment: Assessment) -> None:
    """Từ chối khi nội dung của đề đã bị khoá.

    Mọi đường thêm, sửa hay xoá một câu hỏi đều gọi hàm này. ADR-01 khoá nội dung
    ở lúc duyệt, và câu từ chối nói luôn cách mở khoá, vì một giáo viên chỉ được
    nghe "không" thì có lý mà kết luận rằng câu hỏi đó mắc kẹt mãi mãi.

    Args:
        assessment: Row đang bị ghi vào.

    Raises:
        HTTPException: 409 khi đề đã duyệt hoặc đã phát hành.
    """
    current = _state_of(assessment)
    if current not in _EDITABLE:
        raise HTTPException(
            status_code=409,
            detail=(f"Đề {_READABLE[current]} nên nội dung đã khoá. Muốn sửa thì bỏ duyệt trước."),
        )
