"""Những đề nghị dọn trước mà AGENT đưa ra khi không có model nào được cấu hình.

Mock tồn tại để cái loop chạy được từ đầu tới cuối mà không mất tiền. Ở đây điều đó quan
trọng hơn so với các việc khác: một loop gọi tool có một hình dạng -- hỏi, chạy, hỏi lại,
trả lời -- và một mock chỉ biết nói một câu duy nhất sẽ để cái hình dạng đó không được
test cho tới lần chạy có trả tiền đầu tiên.

Vậy nên các test này khẳng định hình dạng, không khẳng định câu chữ. Thứ phải đúng là mock
xin một tool khi nó chưa có dữ liệu và thôi xin ngay khi dữ liệu đã tới, vì hai điều đó
cùng nhau là thứ làm cái loop kết thúc.
"""

import pytest

from agent import llm
from agent.handlers import propose_next_step
from contracts import NextStepRequested, ToolSpec, TurnRecord


@pytest.fixture(autouse=True)
def off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đi vào đường mock một cách có chủ ý, không phải do tình cờ.

    Không có fixture này thì các test này phụ thuộc vào `.env` của máy. Trên một máy có
    `LLM_ENABLED=true` và một id model -- tức là mọi máy từng chạy thật thứ này --
    `propose_next_step` đi vào đường gọi model, thất bại, rồi trả về mock từ exception
    handler của nó. Vẫn xanh, nhưng xanh qua đường hồi phục thay vì qua đường đang được
    test, và chỉ cách một argument sai là tới chỗ tiêu tiền để khẳng định một câu dọn
    trước.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)


_CATALOG = (
    ToolSpec(name="find_class", description="Tìm lớp theo tên.", arguments={"name": "tên lớp"}),
)


def _payload(*history: TurnRecord, catalog: tuple[ToolSpec, ...] = _CATALOG) -> dict:
    return NextStepRequested(request_id="r1", history=history, catalog=catalog).model_dump(
        mode="json"
    )


@pytest.mark.asyncio
async def test_the_mock_asks_for_a_class_it_was_told_about() -> None:
    """Một tên lớp trong câu hỏi trở thành một lời gọi tool với đúng tên đó.

    Việc truyền cái tên đi qua là quan trọng: một mock gọi `find_class` với một argument
    viết cứng sẽ làm cái loop trông đúng mà chẳng chứng minh được gì về chuyện các argument
    có sống sót qua một vòng đi về hay không.
    """
    asked = _payload(TurnRecord(kind="teacher", text="lớp 12A1 thế nào"))
    answer = await propose_next_step({}, asked)

    assert answer["kind"] == "call_tool"
    assert answer["tool_name"] == "find_class"
    assert answer["tool_args"] == {"name": "12A1"}


@pytest.mark.asyncio
async def test_the_mock_stops_asking_once_the_result_is_in() -> None:
    """Khi trong lịch sử đã có một kết quả tool, mock trả lời thay vì hỏi tiếp.

    Đây là điều kiện kết thúc. Không có nó thì cái loop sẽ chạy tới trần ở mỗi lượt, và
    cái trần sẽ trông như trường hợp bình thường.
    """
    answer = await propose_next_step(
        {},
        _payload(
            TurnRecord(kind="teacher", text="lớp 12A1 thế nào"),
            TurnRecord(kind="tool_call", tool_name="find_class", tool_args={"name": "12A1"}),
            TurnRecord(kind="tool_result", tool_name="find_class", tool_result={"name": "12A1"}),
        ),
    )

    assert answer["kind"] == "say"
    assert answer["text"]


@pytest.mark.asyncio
async def test_the_mock_asks_which_class_when_the_name_matched_several() -> None:
    """Một kết quả nhập nhằng trở thành một câu hỏi, không phải một bài đọc lại kết quả.

    Toàn bộ ý của ADR-23 là không ai chọn giữa các candidates. Mock cũng phải tôn trọng
    điều đó, không thì cách chạy cái loop miễn phí sẽ trình diễn đúng cái hành vi mà thiết
    kế cấm -- và đó lại chính là bản demo người ta xem.

    Nó không tự viết lựa chọn nào: BE render chúng từ những dòng nó đã đọc, và một mock
    cũng viết chúng ra sẽ là một nguồn thứ hai cho đúng cái thứ mà ADR-23 nói là chỉ có một
    nguồn.
    """
    answer = await propose_next_step(
        {},
        _payload(
            TurnRecord(kind="teacher", text="lớp 12A thế nào"),
            TurnRecord(kind="tool_call", tool_name="find_class", tool_args={"name": "12A"}),
            TurnRecord(
                kind="tool_result",
                tool_name="find_class",
                tool_result={
                    "found": False,
                    "ambiguous": True,
                    "candidates": [
                        {"class_id": "c-1", "name": "12A", "student_count": 3},
                        {"class_id": "c-2", "name": "12A", "student_count": 2},
                    ],
                },
            ),
        ),
    )

    assert answer["kind"] == "ask_clarify"
    assert answer["text"]
    assert answer["choices"] == []


@pytest.mark.asyncio
async def test_the_mock_never_proposes_a_tool_it_was_not_given() -> None:
    """Một danh mục rỗng nghĩa là chỉ có lời nói.

    BE dựng danh mục từ những gì giáo viên này được làm, nên một đề nghị gọi tên một tool
    ngoài danh mục đó là một đề nghị BE buộc phải từ chối -- và một mock sinh ra một đề nghị
    như vậy sẽ đang luyện đường lỗi của cái loop thay vì đường suôn sẻ của nó.
    """
    answer = await propose_next_step(
        {}, _payload(TurnRecord(kind="teacher", text="lớp 12A1 thế nào"), catalog=())
    )

    assert answer["kind"] in {"say", "ask_clarify"}
    assert not answer["tool_name"]


@pytest.mark.asyncio
async def test_the_mock_finds_a_name_written_against_the_word_lop() -> None:
    """ "lớp12A" là một cái tên lớp, và BE phân giải được nó.

    Bộ trích xuất của mock cần một word boundary trước các chữ số, nên ở đây nó không thấy
    gì và đi hỏi là lớp nào -- trong khi BE, nếu được cho cơ hội, phân giải cách viết đó rất
    ổn. Việc hai nửa lệch nhau làm buổi demo trông như có một bug phân giải vốn không tồn
    tại.
    """
    asked = _payload(TurnRecord(kind="teacher", text="lớp12A thế nào"))
    answer = await propose_next_step({}, asked)

    assert answer["kind"] == "call_tool"
    assert answer["tool_args"] == {"name": "12A"}


@pytest.mark.asyncio
async def test_the_mock_still_ignores_numbers_that_are_not_class_names() -> None:
    """Nới cái boundary ra không được biến thời lượng và năm thành tên lớp.

    "15 phút" và "2026" nằm trong cùng những câu có tên lớp, và một mock đi tra một trong số
    đó sẽ đẩy cái loop đi tìm một lớp không ai nhắc tới.
    """
    for text in ("bài 15 phút hôm qua thế nào", "năm 2026 có mấy bài", "còn 2 câu chưa chữa"):
        answer = await propose_next_step({}, _payload(TurnRecord(kind="teacher", text=text)))
        assert answer["kind"] == "ask_clarify", text


@pytest.mark.asyncio
async def test_the_mock_asks_back_when_no_class_was_named() -> None:
    """Không có gì để tra và không có gì để trả lời thì phải hỏi lại.

    Cổng kiểm đầu vào của ADR-05 ở dạng rẻ nhất: mock không có cách nào đoán được lớp nào
    đang được nói tới, nên nó không đoán.
    """
    answer = await propose_next_step({}, _payload(TurnRecord(kind="teacher", text="tình hình sao")))

    assert answer["kind"] == "ask_clarify"
    assert answer["text"]


@pytest.mark.asyncio
async def test_the_mock_looks_only_at_this_turn_not_the_whole_conversation() -> None:
    """Một kết quả từ lượt trước không phải là câu trả lời cho câu hỏi hiện tại.

    Việc lưu lại cuộc hội thoại đã làm thay đổi chỗ này mà không sửa một dòng nào của mock:
    nó từng thấy từng lượt một, và giờ nó thấy tất cả. Thế là check "mình đã có dữ liệu
    chưa?" của nó tìm thấy một kết quả từ một lượt trước rồi thôi gọi tool hẳn -- khiến trợ
    lý lặp lại câu cuối của mình mãi mãi. Tìm ra bằng cách đọc bảng `teacher_turns` sau hai
    tin nhắn, không phải bằng test nào.
    """
    answer = await propose_next_step(
        {},
        _payload(
            TurnRecord(kind="teacher", text="lớp 12A thế nào"),
            TurnRecord(kind="tool_call", tool_name="find_class", tool_args={"name": "12A"}),
            TurnRecord(kind="tool_result", tool_name="find_class", tool_result={"name": "12A"}),
            TurnRecord(kind="assistant", text="Lớp 12A có 3 học sinh."),
            # Một câu hỏi mới. Kết quả ở trên thuộc về câu hỏi cũ.
            TurnRecord(kind="teacher", text="còn lớp 12B thì sao"),
        ),
    )

    assert answer["kind"] == "call_tool"
    assert answer["tool_args"] == {"name": "12B"}
