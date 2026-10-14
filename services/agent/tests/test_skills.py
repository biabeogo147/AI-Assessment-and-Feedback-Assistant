"""Lõi, skill, và Jev chọn skill nào cho một lượt của Kriky (`kriky-skill-routing`).

Ba loại khẳng định. Lõi **luôn** mang luật an toàn, vì Jev chọn sai thì một skill vắng mặt -- nên
một luật ADR-05 lọt vào skill là một luật có thể biến mất mà không ai thấy. Bộ chọn hỏng theo cách
nào cũng lùi về **mọi** skill, tức prompt trước `kriky-skill-routing`. Và state gửi Jev là chữ,
không có kết quả tool, nên mọi bước của một vòng tool chọn cùng skill.

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
from agent.graphs.propose import _BOOK_PROCEDURE, _CORE, _LIBRARY_SLOT, _Proposal, propose
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
    """Thân skill như model đọc ở một lượt không có `list_documents`: chỗ trống thư viện đã xoá."""
    return _LIBRARY_SLOT.sub("", skills.named((name,))[0].body)


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
        # Ba luật đầu từng rơi mất ở lần tách đầu -- review `kriky-skill-routing` bắt được, không
        # test nào bắt. Từ ngày 12/10/2026 skill viết thành quy trình (người dùng chốt), nên mỗi
        # luật được kiểm bằng câu chữ của quy trình, không bằng câu chữ của `_SYSTEM` cũ.
        "hai lớp trùng tên chỉ giáo viên phân biệt",
        "Mọi id lấy từ kết quả tool, không bao giờ tự đoán",
        "call_tool get_class — class_id",
        # ADR-23, hậu ký `unbiased-model-text` T3: model đề xuất ít nhất 3 lựa chọn, FE vẽ thêm lối
        # "Khác"; hỏi về một lớp thì chép đúng tên -- BE chỉ giữ chữ khớp đúng một dòng nó đã đọc.
        "Hỏi thì kèm ít nhất 3 lựa chọn trong choices",
        # Câu này không còn bắn (lối "Khác" gửi câu giáo viên ghi, không gửi chữ "Khác"), nhưng
        # được giữ vì prompt nhạy đúng chỗ ấy: bỏ nó thì ca logarit tụt 23 → 6/24, thay câu khác
        # thì 0/24 (`unbiased-model-text`, sau T5; run-92..94). Xem comment trên `_CORE`.
        'Giáo viên vừa chọn "Khác" thì hỏi lại bằng một câu mở',
        "choices chép đúng name của các lớp",
        "Đừng liệt kê tên lớp trong text",
        "đừng chọn hộ",
        # Hai điểm dừng, không có chúng thì model gọi list_class lặp tới trần của BE (review A1).
        "Hẹp rồi mà vẫn more > 0 → say",
        "list_class không có name mà vẫn rỗng → say",
        "found: false",
        "con số đứng đầu tên lớp là khối",
        "Đề không thuộc lớp nào",
        "không hỏi để xác nhận",
        "Tổng số câu của một đề không quá 50",
        "đừng nói là đã soạn xong",
        "average_total_marks trên average_out_of câu",
        # `unbiased-model-text`: môn suy từ phạm vi (người dùng chốt), và câu hỏi của đề không viết
        # ra trong lời nói. Một dòng dặn *"không ghi tên phân môn"* từng đứng đây: lượt hỏi lại môn
        # ở 8 ca soạn đề đủ mục tăng từ 3 (run-13) lên 10--18 (run-14..19), mà subject vẫn ra "xác
        # suất thống kê" -- bỏ ở run-20.
        "hoặc suy từ phạm vi",
        "không tự viết câu hỏi ra trong lời nói",
        # `unbiased-model-text` T2b: `known` ghi giá trị bốn mục, không phải tên của chúng. Thử tay
        # run-20: đủ bốn mục mà `known` ghi *"Cần xác định môn học, khối, phạm vi kiến thức và số
        # câu"*, rồi hỏi cả ba thứ đã có.
        "Ghi vào known GIÁ TRỊ đọc được của từng mục",
        # Khuôn đẩy model lấp đủ ô: nhắc sách không chip thì nó tự điền khối 8, 10, 11 (run-25).
        "suy thẳng từ lời họ theo bước 1 -- không đoán",
        "còn ? → ask_clarify một lần",
        # Chữ trích «» đưa `thieu-khoi-va-so-cau` từ 2/6 lên 6/6 (run-27 → run-28); tham số plan
        # chép từ `known` (plan thiếu tham số 17/192, run-23); môn khác Toán chỉ khi gọi thẳng tên
        # môn (`du-xac-suat-10` 1/6 → 5/6, run-28 → run-29). Review T2b (`unbiased-model-text`):
        # không test nào khoá. Phạm vi đứng trước môn: chép phạm vi rồi mới suy môn
        # (`du-xac-suat-10` 8/24, run-42).
        "topic_scope=<giá trị> «<chữ>»; subject=<giá trị> «<chữ>»",
        "ĐỦ hai bước, mỗi tham số chép đúng giá trị đã ghi trong known",
        "Chỉ ghi môn khác khi giáo viên gọi thẳng tên một môn học khác",
        # `unbiased-model-text` T5: *"kiểm tra nhanh phần logarit"* → *"lớp 11, 10 câu"* -- cụm dùng
        # để suy môn bị coi là đã dùng hết, `topic_scope=? «phần logarit»`, hỏi lại dù đủ bốn mục:
        # bản đã commit 19/24, bản có T2b/T3 5/24, có câu này 24/24 (run-79). Nó kéo
        # `tai-lieu-khong-dinh` 24 → 16/24 cho tới khi `_library_first` giữ bước đầu của lượt nhắc
        # sách bằng code.
        "cụm suy\n     ra môn vẫn là phạm vi",
    ],
)
def test_no_rule_of_the_old_prompt_fell_between_core_and_skills(rule: str) -> None:
    """Luật của `_SYSTEM` cũ phải còn ở lõi **hoặc** ở một skill.

    Tách prompt là chỗ một câu lặng lẽ biến mất mà cả bộ test vẫn xanh: `test_propose_graph.py`
    chạy với mọi skill nạp, và chỉ kiểm một số cụm.
    """
    assert rule in _CORE or any(rule in skill.body for skill in skills.every())


@pytest.mark.parametrize(
    "rule",
    [
        # `draft-from-document`: tài liệu đọc TRƯỚC khi nêu plan (review B5), và phép rải số câu
        # phải được nói ra (hậu ký ADR-27). Từ `unbiased-model-text` thủ tục này nằm ở
        # `_BOOK_PROCEDURE`, chỉ chèn ở lượt có sách.
        "TRƯỚC khi nêu plan",
        "call_tool list_chapters — document_id",
        "rải đều theo độ dài các mục",
        "create_draft thêm document_id và nodes",
        # `unbiased-model-text` T2b: chương không có trong sách thì model lấy một chương khác thay
        # vào (run-25).
        "không phải một mục khác thay vào",
        # Có chip mà vẫn gọi `list_documents` (`tai-lieu-chua-doc` 2--3/6, run-27..29).
        "document_id đã có ở dòng tài liệu đính kèm thì\n   không gọi list_documents",
        # T3 (`unbiased-model-text`): tả nội dung nhãn, không tả trạng thái đối chiếu. *"Chưa khớp
        # được mục nào thì ?"* thì model ghi ? trước khi đối chiếu, rồi hỏi *"cả chương hay một
        # phần?"* (7/24, run-49); bỏ hẳn thì nó lấy chương khác thay chương không có (2/24, run-50).
        # Câu này: 23 và 24/24.
        "không label nào trong kết quả tool\n   nói về điều ấy thì topic_scope=?",
        # Chữ trích của khối đọc từ tên tài liệu là tên tài liệu -- không thì khối thành ?.
        "trong known, chữ trích của chúng là\n   tên tài liệu",
        # T3 (`unbiased-model-text`): câu hỏi về mục thì choices là label -- BE chỉ giữ chữ khớp
        # đúng một dòng.
        "choices chép đúng label của các mục",
    ],
)
def test_the_book_procedure_keeps_the_rules_of_plan_4b(rule: str) -> None:
    assert rule in _BOOK_PROCEDURE


def test_no_skill_carries_the_book_procedure() -> None:
    """`unbiased-model-text`: lượt không có sách thì thủ tục sách không tới model.

    Skill `soan-de` từng mang thủ tục sách, kèm dòng dặn *"không hỏi giáo viên có tài liệu hay
    không"*; model vẫn hỏi đúng câu ấy ~7/108 lượt (run-13), và 0/108 khi thủ tục rời skill
    (run-14). Dòng mở thư viện cũng rời skill ở T2b: nằm trong skill thì nó thắng cả lượt có chip
    (24 lần: 22/24 → 10/24), nên giờ là `propose._LIBRARY`, chỉ chèn ở lượt không có sách. Mô tả
    skill thì được nhắc -- Jev đọc nó, model soạn đề không đọc.
    """
    for skill in skills.every():
        assert "tài liệu" not in skill.body.casefold()
        assert "list_chapters" not in skill.body
        assert "list_documents" not in skill.body


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
    """Jev hỏng hay trả hình dạng lạ thì nạp cả ba -- đúng bằng prompt trước
    `kriky-skill-routing`."""
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
