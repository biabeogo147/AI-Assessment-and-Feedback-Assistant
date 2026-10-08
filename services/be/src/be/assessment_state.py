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
mọi đường ghi một câu hỏi đều phải hỏi câu đó trước. Hai cách hỏi, vì hai loại
caller: `assert_editable` **từ chối**, dành cho một hành động giáo viên vừa yêu cầu;
còn `editable` chỉ trả lời, dành cho một caller cần **bỏ qua** -- `drafting.harvest`
thu hoạch trên đường đọc, và một đường đọc nổ vì một việc dọn dẹp thì tệ hơn là nó
không dọn.

`withdraw` là ngoại lệ duy nhất, và nó được ghi ra thành một thao tác có tên chính
vì thế. Cạnh `đã phát hành → đã duyệt` có **điều kiện** -- chỉ đi được khi chưa tới giờ
mở và không lớp nào còn giữ đề -- nên để nó thành một hàng vô điều kiện trong `_ALLOWED`
sẽ làm cửa duy nhất thôi canh đúng cái đáng canh.

Một chỗ `_ALLOWED` **không** đủ, và nó đã cắn một lần: bảng biết *cạnh nào tồn tại*,
không biết *ai đang xin đi*. Cạnh `EMPTY → HAS_QUESTIONS` tồn tại cho `harvest`, nên
một endpoint bỏ duyệt giao hết cho bảng sẽ đi lậu qua đúng cạnh đó và nâng một đề 0
câu lên `đang soạn`. Nên một caller biết nó đang ở cạnh nào thì phải tự nêu tiền đề
của mình; bảng chỉ là chốt cuối.
"""

from datetime import datetime

from fastapi import HTTPException

from schema.models import Assessment, AssessmentState

# Re-export để một caller chỉ cần một import là hỏi được một câu về vòng đời.
# Phần từ vựng thuộc về schema và nằm trong `models`; phần các cạnh thì thuộc về
# đây.
__all__ = [
    "AssessmentState",
    "advance",
    "assert_editable",
    "editable",
    "may_withdraw",
    "readable",
    "state_of",
    "withdraw",
]


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
    # Để trống có chủ đích, và `withdraw` dưới đây là lý do nó được phép trống.
    # Bảng này chứa các cạnh **vô điều kiện**; `published → approved` thì có điều
    # kiện -- nó chỉ đi được khi chưa tới giờ mở -- nên nếu nó nằm đây thì cửa duy
    # nhất thôi canh đúng cái đáng canh: bất kỳ caller tương lai nào quên kiểm giờ
    # đều thu hồi được một bài học sinh **đang ngồi làm**, và `advance` sẽ vui vẻ
    # đồng ý. Một cạnh có điều kiện là một thao tác có tên, tự chở điều kiện của nó.
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


def state_of(assessment: Assessment) -> AssessmentState:
    """State hiện tại của một đề, kể cả khi nó chưa từng được lưu.

    Args:
        assessment: Row đó.

    Returns:
        State hiện tại.
    """
    return _state_of(assessment)


def readable(state: AssessmentState) -> str:
    """Tên của một state theo cách giao diện gọi nó, để ghép vào một câu tiếng Việt.

    Args:
        state: State cần gọi tên.

    Returns:
        Cụm từ tiếng Việt cho state đó.
    """
    return _READABLE[state]


def editable(assessment: Assessment) -> bool:
    """Nội dung của đề này còn sửa được không (ADR-01).

    Phiên bản trả lời của `assert_editable`, cho caller chỉ cần bỏ qua chứ không cần
    từ chối.

    Args:
        assessment: Row đó.

    Returns:
        True khi đề còn ở một state sửa được.
    """
    return _state_of(assessment) in _EDITABLE


def _refuse_unless_reachable(assessment: Assessment, to: AssessmentState) -> None:
    """Từ chối khi ADR-01 không có cạnh nào tới `to`, mà không đổi gì.

    Tách ra khỏi `advance` để câu từ chối có đúng một chỗ viết. Chưa công khai: endpoint
        duyệt hỏi một câu khác -- *nội dung còn mở không* -- vì chính `harvest` làm câu trả
        lời của hàm này đổi giữa đường. Khi nào có caller thật thì mở ra lúc đó.

        Args:
            assessment: Row đó.
            to: State đang được nhắm tới.

        Raises:
            HTTPException: 409 kèm một câu nêu tên cả hai state.
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
    _refuse_unless_reachable(assessment, to)
    assessment.state = to


def may_withdraw(opens_at: datetime, now: datetime) -> bool:
    """Lần phát hành này còn lấy lại được không (ADR-02).

    Hàm thuần trên hai **giá trị**, không nhận hàng ORM nào -- cùng luật mà cả file này
    tuân theo. Ranh giới đặt ở **giờ mở** chứ không ở lúc bấm nút, vì thứ làm hành động
    thành không đảo ngược được là **học sinh đã có thể nhìn thấy đề**, không phải thao
    tác của giáo viên.

    Mốc là **bao gồm**: đúng giây giờ mở vẫn thu hồi được. Cùng kiểu bao gồm mà ADR-03
    dùng cho giờ đóng, và cùng một lý do -- một luật "tới hết" mà loại trừ đúng cái mốc
    nó nêu tên thì không ai đoán đúng được.

    Args:
        opens_at: Giờ mở của lần phát hành đó, đã tz-aware.
        now: Bây giờ, đã tz-aware.

    Returns:
        True khi chưa qua giờ mở.
    """
    return now <= opens_at


def withdraw(assessment: Assessment, *, still_held: int) -> None:
    """Đưa một đề về `đã duyệt` khi không lớp nào còn giữ nó.

    `advance` **không tham gia**, và đây là chỗ trả lời câu hỏi đó cho rõ: bảng
    `_ALLOWED[PUBLISHED]` để trống nên không ai tới được `APPROVED` từ `PUBLISHED` mà
    không đi qua hàm này. Hàm này tự đặt `state`, và đó là lần đi vòng duy nhất quanh
    bảng cạnh trong cả file -- được phép vì điều kiện của cạnh ấy (chưa tới giờ mở, và
    không lớp nào còn giữ) nằm ngay đây, cạnh phép gán, chứ không rải ở chỗ khác.

    Không chạm `Publication`. Một đề phát hành cho nhiều lớp thì thu hồi một lớp **không**
    làm nó thôi phát hành: nó vẫn đang phát hành cho những lớp còn lại, và một đề về
    `đã duyệt` trong lúc 12B đang làm bài là đúng cái hại mà ADR-02 ngăn.

    Args:
        assessment: Row của đề. `state` được ghi tại chỗ; commit là việc của caller.
        still_held: Còn bao nhiêu lớp đang giữ đề này, đếm **sau** khi lần thu hồi này
            đã được ghi. Caller đếm, vì đếm cần một session.

    Side effects:
        Ghi `assessment.state` khi `still_held` bằng 0.
    """
    if still_held:
        return
    # Đi vòng qua `_ALLOWED` có chủ ý: xem docstring, và xem hàng `PUBLISHED` của bảng.
    assessment.state = AssessmentState.APPROVED


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
