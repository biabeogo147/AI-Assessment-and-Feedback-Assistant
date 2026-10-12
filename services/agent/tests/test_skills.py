"""Lõi, skill, và Jev chọn skill nào cho một lượt của Kriky (plan 4a).

Ba loại khẳng định. Lõi **luôn** mang luật an toàn, vì Jev chọn sai thì một skill vắng mặt -- nên
một luật ADR-05 lọt vào skill là một luật có thể biến mất mà không ai thấy. Bộ chọn hỏng theo cách
nào cũng lùi về **mọi** skill, tức prompt trước plan 4a. Và state gửi Jev là chữ, không có kết quả
tool, nên mọi bước của một vòng tool chọn cùng skill.

Không test nào ở đây gọi Jev thật: `conftest.py` đóng `_client`, và test nào cần Jev tự cài một
client giả.
"""

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.runnables import RunnableLambda
from typesafe_sdk import TypeSafeError

from agent import llm, skill_router, skills
from agent.config import get_settings
from agent.graphs.propose import _CORE, _Proposal, propose
from contracts import NextStepRequested, TurnRecord


class FakeJev:
    """Một client Jev trả xác suất "yes" xếp sẵn theo tên skill, có đếm số lời gọi."""

    def __init__(self, yes: dict[str, float] | None = None, fails: Exception | None = None):
        self.yes = yes or {}
        self.fails = fails
        self.calls: list[dict] = []
        self.delay = 0.0

    async def system_one(self, state: dict, questions: dict) -> SimpleNamespace:
        """Trả lời như Jev, hoặc raise như Jev hỏng."""
        self.calls.append(state)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fails:
            raise self.fails
        assert list(next(iter(questions.values())).criteria) == ["yes", "no"]
        said = {name: self.yes.get(name, 0.0) for name in questions}
        return SimpleNamespace(
            answers={
                name: SimpleNamespace(probabilities={"yes": yes, "no": 1 - yes})
                for name, yes in said.items()
            }
        )


def _jev(monkeypatch: pytest.MonkeyPatch, fake: FakeJev) -> FakeJev:
    monkeypatch.setattr(skill_router, "_client", lambda: fake)
    return fake


def _teacher(text: str) -> TurnRecord:
    return TurnRecord(kind="teacher", text=text)


def _body(name: str) -> str:
    return skills.named((name,))[0].body


class Recording:
    """Chat model chỉ ghi prompt rồi nói "vâng"."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def with_structured_output(self, schema: object, **kwargs: object) -> RunnableLambda:
        def answer(messages: object) -> _Proposal:
            self.prompts.append("\n".join(message.text for message in messages))
            return _Proposal(kind="say", text="vâng")

        return RunnableLambda(answer)


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Recording:
    recording = Recording()
    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_models", lambda: (recording,))
    return recording


def _asked(*history: TurnRecord) -> NextStepRequested:
    return NextStepRequested(request_id="r1", teacher_name="Cô Lan", history=history)


def test_every_skill_reads_and_the_general_one_exists() -> None:
    """Ba skill, frontmatter đọc được, `description` tiếng Anh vì nó là `criteria` của Jev."""
    names = [skill.name for skill in skills.every()]
    assert names == ["lop-va-ket-qua", "soan-de", "tro-chuyen-chung"]
    assert skills.GENERAL in names
    for skill in skills.every():
        assert skill.description.isascii(), skill.name
        assert skill.body


@pytest.mark.parametrize(
    "rule",
    [
        "Bạn KHÔNG tự làm gì cả",
        "TUYỆT ĐỐI không dùng\n  nó để xin phép một việc không thu hồi được",
        "KHÔNG đánh dấu phương án nào là nên chọn",
        "Không đoán khi một cái tên có thể trỏ tới nhiều thứ",
        "duyệt đề, và phát hành đề",
        "{k.ten_field}",
        "chỉ `$`",
    ],
)
def test_the_core_carries_every_safety_rule_on_its_own(rule: str) -> None:
    """Luật ADR-05 và *không duyệt / không phát hành* nằm ở lõi, không ở skill nào.

    Gỡ một trong số chúng khỏi `_CORE` để đưa vào skill thì test này đỏ: một lượt Jev chọn sai sẽ
    gửi model đi mà không mang luật ấy.
    """
    assert rule in _CORE
    assert not any(rule in skill.body for skill in skills.every())


@pytest.mark.parametrize(
    "rule",
    [
        # Ba luật đầu từng rơi mất ở lần tách đầu -- review plan 4a bắt được, không test nào bắt.
        # Từ ngày 12/10/2026 skill viết thành quy trình (người dùng chốt), nên mỗi luật được kiểm
        # bằng câu chữ của quy trình, không bằng câu chữ của `_SYSTEM` cũ.
        "hai lớp trùng tên chỉ giáo viên phân biệt",
        "Mọi id lấy từ kết quả tool, không bao giờ tự đoán",
        "call_tool get_class — class_id",
        # ADR-23: model viết câu hỏi, hệ thống dựng phương án.
        "ask_clarify, chỉ viết câu hỏi",
        "đừng điền choices",
        "đừng chọn hộ",
        # Hai điểm dừng, không có chúng thì model gọi list_class lặp tới trần của BE (review A1).
        "Hẹp rồi mà vẫn more > 0 → say",
        "list_class không có name mà vẫn rỗng → say",
        "found: false",
        '"lớp 12A" là 12',
        "Đề không thuộc lớp nào",
        "không hỏi để xác nhận",
        "Tổng số câu của một đề không quá 50",
        "đừng nói là đã soạn xong",
        "average_total_marks trên average_out_of câu",
    ],
)
def test_no_rule_of_the_old_prompt_fell_between_core_and_skills(rule: str) -> None:
    """Luật của `_SYSTEM` cũ phải còn ở lõi **hoặc** ở một skill.

    Tách prompt là chỗ một câu lặng lẽ biến mất mà cả bộ test vẫn xanh: `test_propose_graph.py`
    chạy với mọi skill nạp, và chỉ kiểm một số cụm.
    """
    assert rule in _CORE or any(rule in skill.body for skill in skills.every())


@pytest.mark.asyncio
async def test_the_prompt_carries_only_the_skills_jev_chose(
    monkeypatch: pytest.MonkeyPatch, model: Recording
) -> None:
    """Jev nói *soạn đề* thì prompt mang `soan-de` và không mang skill tra lớp."""
    _jev(monkeypatch, FakeJev({"soan-de": 0.9, "lop-va-ket-qua": 0.05}))

    await propose(_asked(_teacher("tạo đề 10 câu chương Hàm số lớp 12A")))

    prompt = model.prompts[0]
    assert _CORE in prompt
    assert _body("soan-de") in prompt
    # Lõi đứng trước: không skill nào nói trước được một luật an toàn.
    assert prompt.index(_CORE) < prompt.index(_body("soan-de"))
    assert _body("lop-va-ket-qua") not in prompt
    assert _body("tro-chuyen-chung") not in prompt


@pytest.mark.asyncio
async def test_two_skills_load_together_when_the_message_needs_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Một câu yes/no mỗi skill, nên một tin nhắn hai việc nạp được cả hai."""
    _jev(monkeypatch, FakeJev({"soan-de": 0.7, "lop-va-ket-qua": 0.8}))

    chosen = await skill_router.choose([_teacher("xem kết quả lớp 12A rồi soạn đề ôn")])

    assert chosen == ("lop-va-ket-qua", "soan-de")


@pytest.mark.asyncio
async def test_a_message_no_workflow_claims_falls_to_the_general_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """*"căn bậc 3 của x^2 viết vào đề thế nào"* không thuộc quy trình nào: skill bao quát."""
    fake = _jev(monkeypatch, FakeJev({"soan-de": 0.1, "lop-va-ket-qua": 0.02}))
    asked = _teacher("căn bậc 3 của x^2 được viết vào đề như thế nào?")

    chosen = await skill_router.choose([asked])

    assert chosen == (skills.GENERAL,)
    # Skill bao quát không bao giờ được hỏi: nó là chỗ rơi vào, không phải một lựa chọn.
    assert skills.GENERAL not in str(fake.calls)


@pytest.mark.asyncio
async def test_the_threshold_leans_towards_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """P(yes) dưới 0,5 mà còn trên ngưỡng vẫn nạp: thiếu `soan-de` đắt hơn thừa nó."""
    _jev(monkeypatch, FakeJev({"soan-de": 0.35}))

    assert await skill_router.choose([_teacher("10 câu")]) == ("soan-de",)


@pytest.mark.asyncio
async def test_a_probability_exactly_on_the_threshold_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Đúng ngưỡng là nạp: `>=`, không phải `>`."""
    _jev(monkeypatch, FakeJev({"soan-de": get_settings().skill_min_yes}))

    assert await skill_router.choose([_teacher("10 câu")]) == ("soan-de",)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fake",
    [
        FakeJev(fails=TypeSafeError("rate limited")),
        FakeJev(fails=KeyError("soan-de")),
    ],
)
async def test_a_broken_jev_loads_every_skill(
    monkeypatch: pytest.MonkeyPatch, fake: FakeJev
) -> None:
    """Jev hỏng hay trả hình dạng lạ thì nạp cả ba -- đúng bằng prompt trước plan 4a."""
    _jev(monkeypatch, fake)

    chosen = await skill_router.choose([_teacher("tạo đề")])

    assert chosen == tuple(skill.name for skill in skills.every())


@pytest.mark.asyncio
async def test_a_slow_jev_is_cut_off_and_every_skill_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trần thời gian là của **cả** lời chọn: nó cộng vào ngân sách một job propose."""
    fake = _jev(monkeypatch, FakeJev({"soan-de": 0.9}))
    fake.delay = 1
    monkeypatch.setattr(get_settings(), "skill_router_timeout_seconds", 0.05)

    chosen = await skill_router.choose([_teacher("tạo đề")])

    assert chosen == tuple(skill.name for skill in skills.every())


@pytest.mark.asyncio
async def test_a_history_with_no_teacher_turn_loads_every_skill_without_asking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Không có câu giáo viên thì không có gì để chọn: nạp cả ba, Jev không bị hỏi."""
    fake = _jev(monkeypatch, FakeJev({"soan-de": 0.9}))

    chosen = await skill_router.choose([TurnRecord(kind="assistant", text="Chào bạn")])

    assert chosen == tuple(skill.name for skill in skills.every())
    assert fake.calls == []


@pytest.mark.asyncio
async def test_without_a_key_every_skill_loads_and_jev_is_never_asked() -> None:
    """`conftest.py` cho `_client` trả `None`, đúng như một máy không có `JEV_API_KEY`."""
    chosen = await skill_router.choose([_teacher("tạo đề")])

    assert chosen == tuple(skill.name for skill in skills.every())


def test_jev_reads_the_latest_words_and_never_a_tool_result() -> None:
    """State là bốn lượt chữ gần nhất; lượt tool không vào, và một lời đáp ngắn còn thấy câu hỏi."""
    history = [
        _teacher("chào Kriky"),
        TurnRecord(kind="assistant", text="Chào bạn"),
        _teacher("tạo đề Toán lớp 12"),
        TurnRecord(kind="tool_call", tool_name="list_class", tool_args={}),
        TurnRecord(kind="tool_result", tool_name="list_class", tool_result={"candidates": []}),
        TurnRecord(kind="assistant", text="Bạn muốn phạm vi nào và bao nhiêu câu?"),
        _teacher("chương Hàm số, 10 câu"),
    ]

    state = skill_router.state_of(history)

    assert state == {
        "conversation": [
            {"speaker": "assistant", "text": "Chào bạn"},
            {"speaker": "teacher", "text": "tạo đề Toán lớp 12"},
            {"speaker": "assistant", "text": "Bạn muốn phạm vi nào và bao nhiêu câu?"},
            {"speaker": "teacher", "text": "chương Hàm số, 10 câu"},
        ]
    }
    assert "candidates" not in str(state)


@pytest.mark.asyncio
async def test_every_step_of_one_tool_loop_asks_jev_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """BE gọi propose lại sau mỗi kết quả tool; state không đổi nên Jev được hỏi một lần."""
    fake = _jev(monkeypatch, FakeJev({"lop-va-ket-qua": 0.9}))
    first = [_teacher("lớp 12A làm bài thế nào")]
    later = [
        *first,
        TurnRecord(kind="tool_call", tool_name="list_class", tool_args={"name": "12A"}),
        TurnRecord(kind="tool_result", tool_name="list_class", tool_result={"candidates": []}),
    ]

    assert await skill_router.choose(first) == ("lop-va-ket-qua",)
    assert await skill_router.choose(later) == ("lop-va-ket-qua",)
    assert len(fake.calls) == 1
