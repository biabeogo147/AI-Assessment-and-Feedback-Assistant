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
    ToolSpec(name="list_class", description="Liệt kê các lớp của giáo viên.", arguments={}),
)


_PLANNABLE = (
    ToolSpec(
        name="create_draft",
        description="Mở một đề nháp trống.",
        arguments={
            "subject": "môn",
            "grade": "khối",
            "topic_scope": "phạm vi kiến thức",
        },
    ),
    ToolSpec(
        name="start_drafting",
        description="Bắt đầu sinh câu hỏi.",
        arguments={"assessment_id": "id đề nháp", "question_count": "số câu"},
    ),
)


def _payload(
    *history: TurnRecord,
    catalog: tuple[ToolSpec, ...] = _CATALOG,
    plannable: tuple[ToolSpec, ...] = (),
) -> dict:
    return NextStepRequested(
        request_id="r1", history=history, catalog=catalog, plannable=plannable
    ).model_dump(mode="json")


@pytest.mark.asyncio
async def test_the_mock_asks_for_a_class_it_was_told_about() -> None:
    """Một tên lớp trong câu hỏi trở thành một lời gọi tool tra lớp.

    Cái tên **không** đi vào tham số: `list_class` không nhận tham số nào, vì việc gỡ nhập
    nhằng đã rời khỏi tool. Nên thứ đo được ở đây là một quyết định, không phải một giá
    trị — mock nhận ra giáo viên đang nói về một lớp và đi tra, thay vì hỏi lại một câu đã
    có câu trả lời. Test ngay dưới đo chiều còn lại: không tên nào thì hỏi lại.
    """
    asked = _payload(TurnRecord(kind="teacher", text="lớp 12A1 thế nào"))
    answer = await propose_next_step({}, asked)

    assert answer["kind"] == "call_tool"
    assert answer["tool_name"] == "list_class"
    assert answer["tool_args"] == {}


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
            TurnRecord(kind="tool_call", tool_name="list_class", tool_args={}),
            TurnRecord(
                kind="tool_result",
                tool_name="list_class",
                tool_result={
                    "candidates": [{"class_id": "c-1", "name": "12A1", "student_count": 3}],
                    "more": 0,
                },
            ),
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
            TurnRecord(kind="tool_call", tool_name="list_class", tool_args={}),
            TurnRecord(
                kind="tool_result",
                tool_name="list_class",
                tool_result={
                    "more": 0,
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
    assert answer["tool_name"] == "list_class"


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
            TurnRecord(kind="tool_call", tool_name="list_class", tool_args={}),
            TurnRecord(
                kind="tool_result",
                tool_name="list_class",
                tool_result={
                    "candidates": [{"class_id": "c-1", "name": "12A", "student_count": 3}],
                    "more": 0,
                },
            ),
            TurnRecord(kind="assistant", text="Lớp 12A có 3 học sinh."),
            # Một câu hỏi mới. Kết quả ở trên thuộc về câu hỏi cũ.
            TurnRecord(kind="teacher", text="còn lớp 12B thì sao"),
        ),
    )

    assert answer["kind"] == "call_tool"


async def _outline_then_agree(said: str) -> tuple[dict, dict]:
    """Lượt một: câu nhờ soạn. Lượt hai: *"oke"* sau dàn ý mock vừa nêu (ADR-29)."""
    outlined = await propose_next_step(
        {}, _payload(TurnRecord(kind="teacher", text=said), plannable=_PLANNABLE)
    )
    agreed = await propose_next_step(
        {},
        _payload(
            TurnRecord(kind="teacher", text=said),
            TurnRecord(kind="outline", text="Dàn ý — …", tool_result={"version": 1}),
            TurnRecord(kind="teacher", text="oke"),
            plannable=_PLANNABLE,
        ),
    )
    return outlined, agreed


@pytest.mark.asyncio
async def test_the_mock_outlines_first_and_plans_both_steps_once_agreed() -> None:
    """Một bản dev không có API key vẫn phải soạn được một đề có câu hỏi -- qua dàn ý (ADR-29).

    Lượt một là dàn ý, không phải plan: BE chỉ soạn trên một dàn ý giáo viên đã thấy, nên một mock
    nêu plan ngay sẽ bị chặn tới trần bước. Lượt hai, giáo viên đồng ý, mới là plan hai bước, và
    bước hai trỏ về bước một bằng cú pháp BE giải.
    """
    outlined, agreed = await _outline_then_agree("tạo đề 10 câu Toán về tích phân cho lớp 12A1")

    assert outlined["kind"] == "outline"
    assert outlined["outline"][0]["questions"] == 10
    assert outlined["tool_args"] == {"for": "new"}
    assert agreed["kind"] == "plan"
    assert [one["tool_name"] for one in agreed["steps"]] == ["create_draft", "start_drafting"]
    assert agreed["steps"][0]["args"]["subject"] == "Toán"
    assert agreed["steps"][0]["args"]["grade"] == "12"
    # Số câu đi với bước **hai**, và để trống: BE điền tổng của dàn ý đã xem.
    assert "question_count" not in agreed["steps"][0]["args"]
    assert agreed["steps"][1]["args"] == {
        "assessment_id": "{1.assessment_id}",
        "question_count": "",
    }


@pytest.mark.asyncio
async def test_the_mock_says_ten_is_the_most_at_once() -> None:
    answer = await propose_next_step(
        {},
        _payload(
            TurnRecord(kind="teacher", text="soạn đề 25 câu môn Hoá học cho lớp 10B"),
            plannable=_PLANNABLE,
        ),
    )

    assert answer["kind"] == "say"
    assert "tối đa 10 câu" in answer["text"]


@pytest.mark.asyncio
async def test_the_mock_asks_instead_of_guessing_a_brief_it_does_not_have() -> None:
    """Thiếu một mục bắt buộc thì hỏi, không điền hộ.

    Cả bộ đề sinh ra từ một brief duy nhất, nên một mục đoán sai làm sai toàn bộ bộ đề.
    Mock mà đoán thay giáo viên đang trình diễn đúng hành vi prompt cấm -- và nó cũng để
    lại một đề thật trong database.
    """
    answer = await propose_next_step(
        {}, _payload(TurnRecord(kind="teacher", text="soạn cho tôi một đề"), plannable=_PLANNABLE)
    )

    assert answer["kind"] == "ask_clarify"
    assert answer["steps"] == []


@pytest.mark.asyncio
async def test_the_mock_never_plans_a_tool_it_was_not_given() -> None:
    """Không có `plannable` thì không có plan, dù câu gõ nghe rõ là nhờ soạn đề.

    Hai danh mục là hai quyền. Một mock nêu plan với những tool BE không gửi tới đang
    khẳng định rằng ranh giới pha là chuyện của prompt, chứ không phải chuyện cấu trúc.
    """
    answer = await propose_next_step(
        {}, _payload(TurnRecord(kind="teacher", text="tạo đề 10 câu Toán cho lớp 12A1"))
    )

    assert answer["kind"] != "plan"


@pytest.mark.asyncio
async def test_the_mock_reads_the_brief_instead_of_remembering_one() -> None:
    """Câu thứ hai, với mọi mục khác hẳn câu thứ nhất.

    Một test với đúng một câu đầu vào không phân biệt được *đọc* với *hằng số*: mock gán
    cứng `subject="Toán"` hay `grade="12"` vẫn xanh. Hai câu khác nhau là giá rẻ nhất để
    luật "mock chỉ đọc" có một nơi thi hành.
    """
    outlined, agreed = await _outline_then_agree("soạn đề 8 câu môn Hoá học cho lớp 10B")

    assert outlined["outline"][0]["questions"] == 8
    args = agreed["steps"][0]["args"]
    assert args["subject"] == "Hoá học"
    assert args["grade"] == "10"
    # `topic_scope` là *phạm vi kiến thức theo lời giáo viên*, nên lời họ là giá trị đúng
    # nhất mock có -- và nó phải là lời của **câu ấy**, không phải một chuỗi dọn sẵn.
    assert args["topic_scope"] == "soạn đề 8 câu môn Hoá học cho lớp 10B"


@pytest.mark.asyncio
async def test_the_mock_does_not_plan_on_an_agreement_without_an_outline() -> None:
    answer = await propose_next_step(
        {}, _payload(TurnRecord(kind="teacher", text="oke"), plannable=_PLANNABLE)
    )

    assert answer["kind"] != "plan"


@pytest.mark.asyncio
async def test_the_mock_does_not_find_a_subject_inside_an_ordinary_word() -> None:
    """Tiếng Việt không có biên từ như tiếng Anh, và một bảng tra substring thì bịa.

    "học sinh" chứa "sinh", "nhanh" chứa "anh", "xử lý" chứa "lý". Cả ba là câu bình thường
    của giáo viên, và cả ba từng cho ra một bộ đề **sai môn** -- mà cả bộ đề sinh từ một
    brief, nên một môn sai làm sai cả mười câu, không chỉ một.
    """
    for text in (
        "tạo đề 10 câu cho học sinh lớp 12 về tích phân",
        "soạn nhanh đề 10 câu cho lớp 12 phần tích phân",
        "tạo đề 10 câu xử lý số liệu lớp 12",
    ):
        answer = await propose_next_step(
            {}, _payload(TurnRecord(kind="teacher", text=text), plannable=_PLANNABLE)
        )
        assert answer["kind"] == "ask_clarify", text


@pytest.mark.asyncio
async def test_a_question_about_a_paper_is_not_an_order_to_make_one() -> None:
    """Mock là **đường lùi khi model lỗi**, không chỉ là đường của máy dev không key.

    Vì thế một mock đọc "đề Toán 12A1 đã có 10 câu chưa?" thành một lệnh tạo đề nghĩa là:
    một lần model timeout trên một câu HỎI sẽ ghi một đề mới cùng mười job soạn câu vào
    database của giáo viên. Đó đúng là việc ADR-25 sinh ra để diệt, chỉ là từ phía khác.
    """
    for text in ("đề Toán 12A1 đã có 10 câu chưa?", "lớp 12A1 có vấn đề gì không"):
        answer = await propose_next_step(
            {}, _payload(TurnRecord(kind="teacher", text=text), plannable=_PLANNABLE)
        )
        assert answer["kind"] != "plan", text


@pytest.mark.asyncio
async def test_the_mock_asks_back_when_the_number_is_outside_what_the_tool_takes() -> None:
    """ "100 câu" quá trần của `create_draft`, nên nó là một câu hỏi lại, không một bước đỏ.

    Hai cách sai ở đây, và bản đầu mắc cả hai: regex hai chữ số cắt "100" thành "00" rồi
    đưa số 0 cho tool, và một con số ngoài khoảng đi vào plan thì thành một bước đỏ --
    một bước đỏ không nói cho giáo viên biết phải sửa gì.
    """
    answer = await propose_next_step(
        {},
        _payload(
            TurnRecord(kind="teacher", text="tạo đề 100 câu Toán lớp 12"), plannable=_PLANNABLE
        ),
    )

    assert answer["kind"] == "ask_clarify"


@pytest.mark.asyncio
async def test_a_model_that_breaks_gives_a_system_notice_not_the_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model bật mà hỏng thì không lùi về mock (ADR-30, `kriky-writes-every-word`).

    Mock nói dưới giọng Kriky một việc nó đoán bằng từ khoá; giữa một lượt chat thật, đó là code nói
    thay model. Lượt ra một thông báo hệ thống, và BE lưu nó thành `notice`.
    """
    from agent import handlers

    async def breaks(request):
        raise RuntimeError("provider đi vắng")

    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(handlers, "propose", breaks)

    answer = await propose_next_step(
        {}, _payload(TurnRecord(kind="teacher", text="lớp 12A thế nào"))
    )

    assert answer["kind"] == "say"
    assert answer["notice"] is True
    assert answer["tool_name"] == ""
