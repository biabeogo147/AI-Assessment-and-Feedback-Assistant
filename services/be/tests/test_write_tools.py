"""Những tool đầu tiên có quyền ghi, và cái cổng đứng trước chúng.

Hai luật quyết định mọi thứ ở đây.

**Agent ghi nội dung; giáo viên quyết định trạng thái.** Tạo nháp và điền câu
hỏi vào nó đều đảo lại được khi đề chưa được duyệt, nên trợ lý được phép làm.
Duyệt và phát hành là chỗ giáo viên nhận trách nhiệm — ADR-01 cho việc đầu,
ADR-02 cho việc sau — nên không tool nào chạm tới, và `tools/check_contract.py`
giờ từ chối một `teacher_tools.py` nhắc tới `advance` hay `withdraw` dù chỉ một
lần.

**Đủ ngữ cảnh trước khi ghi bất cứ thứ gì.** Đây là luật của giáo viên, và nó
nói về tính nhất quán chứ không phải sự ngăn nắp: các câu hỏi được viết bởi
những job độc lập, nên một brief còn đang gom dở sẽ cho ra một bộ mà hai nửa
của nó trả lời hai câu hỏi khác nhau. Vì vậy `create_draft` từ chối một brief
chưa đủ và nói rõ thiếu field nào — chính điều đó biến "hỏi trước đã" từ một
dòng trong prompt thành thứ model không thể bỏ qua.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting
from be.assessment_state import AssessmentState
from be.config import get_settings
from be.db import bind_sessions
from be.drafting import harvest
from be.identity import Asking
from be.seed import seed_if_empty
from be.teacher_tools import (
    PHASE_PLAN,
    PHASE_WORK,
    UnknownTool,
    Unresolvable,
    catalog_for,
    execute,
    resolve_args,
)
from contracts import DraftQuestionCompleted, GeneratedOption, GeneratedQuestion, SolutionMethod
from schema.ddl import prepare_schema
from schema.models import Assessment, DraftBrief, DraftItem, Question, Teacher


class FakeQueue:
    """Ghi lại những gì đã được đưa vào queue, và trả lời cho các job mà test cho hoàn tất."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict]] = []
        self.results: dict[str, tuple[str, object]] = {}

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        self.jobs.append((name, payload))
        return type("Queued", (), {"job_id": f"job-{len(self.jobs)}"})()

    def finish(self, job_id: str, question: GeneratedQuestion) -> None:
        """Khai báo rằng một job đã xong với câu hỏi này."""
        self.results[job_id] = (
            "ready",
            DraftQuestionCompleted(request_id="r", question=question).model_dump(mode="json"),
        )


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một database đã seed, giáo viên đang hỏi, và một queue biết ghi lại.

    Việc thu kết quả được stub lại vì các tool ghi giờ `harvest` trước khi quyết
    định bất cứ điều gì, mà `Job` của arq thì cần một Redis thật để hỏi. Một job
    chưa test nào cho hoàn tất sẽ đọc ra là vẫn đang chạy — và đó đúng là trạng
    thái của một vòng vừa được đẩy vào queue.
    """
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)

    queue = FakeQueue()

    async def collect(_pool, _settings, job_id):
        return queue.results.get(job_id, ("pending", None))

    monkeypatch.setattr(drafting, "collect_result", collect)

    yield maker, queue

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _asking(session) -> Asking:
    teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
    assert teacher is not None
    return Asking.of(teacher)


_FULL = {
    "subject": "Toán",
    "grade": "12",
    "topic_scope": "đạo hàm của đa thức",
    "question_count": 3,
    "difficulty": "cơ bản",
}


@pytest.mark.asyncio
async def test_a_complete_brief_creates_an_empty_draft(stack) -> None:
    """Đề nháp tồn tại, thuộc về giáo viên đang hỏi, và chưa chứa câu hỏi nào.

    Là `EMPTY` chứ không phải `HAS_QUESTIONS`, vì ADR-01 cho state rỗng một luật
    riêng: nó chính là thứ chặn việc phát hành một đề không có gì trên đó.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        answer = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )

        draft = await session.get(Assessment, answer["assessment_id"])
        brief = await session.get(DraftBrief, answer["assessment_id"])

    assert answer["created"] is True
    assert draft is not None
    assert draft.teacher_id == asking.teacher_id
    assert draft.state == AssessmentState.EMPTY
    assert brief is not None
    assert brief.topic_scope == "đạo hàm của đa thức"
    assert brief.question_count == 0
    assert brief.version == 1


@pytest.mark.asyncio
async def test_an_incomplete_brief_names_what_is_missing_and_writes_nothing(stack) -> None:
    """Lời từ chối chính là cơ chế, không phải một phép lịch sự.

    Một model được prompt dặn đi gom ngữ cảnh trước thì có thể quên; một tool
    không chịu chạy khi thiếu field thì không thể bị quên. Và việc nói rõ thiếu
    field nào là thứ cho phép trợ lý hỏi một câu có ích thay vì đoán — đúng cái
    cổng đầu vào của ADR-05, theo hình dạng mà ADR-23 đã dùng cho một tên lớp
    nhập nhằng.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        answer = await execute(
            session,
            asking,
            "create_draft",
            {"subject": "Toán", "topic_scope": "đạo hàm"},
            pool=queue,
            phase=PHASE_WORK,
        )
        drafts = (await session.scalars(select(Assessment))).all()

    assert answer["created"] is False
    assert set(answer["missing"]) == {"grade"}
    # Chỉ còn đúng Assessment đã seed; không có gì được ghi.
    assert len(drafts) == 1


@pytest.mark.asyncio
async def test_too_many_questions_is_refused_by_the_tool_that_spends_them(stack) -> None:
    """Mức trần sống ở `start_drafting`, không ở `create_draft`.

    Mở một đề trống không tiêu lượt gọi model nào, nên không có gì để chặn ở đó — và
    bắt khai số câu lúc ấy buộc giáo viên quyết một con số trước khi biết đề sẽ dài bao
    nhiêu. `start_drafting` mới là chỗ con số được tiêu: mỗi câu một job, mỗi job một
    lượt gọi model. Phát hiện ra mức trần giữa lúc đang bắn job nghĩa là năm mươi lượt
    đã bị tiêu trước khi có thứ gì lên tiếng.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        # 500 câu đi qua `create_draft` không bị chặn: nó không còn nhìn thấy con số ấy.
        made = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )
        assert made["created"] is True

        answer = await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": made["assessment_id"], "question_count": 60},
            pool=queue,
            phase=PHASE_WORK,
        )

    assert answer["started"] is False
    assert "1 đến 50" in answer["reason"]
    # Và không job nào bị bắn: mức trần được kiểm **trước** job đầu tiên.
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_drafting_starts_one_job_per_question(stack) -> None:
    """Các job được bắn đi và không ai đứng chờ chúng."""
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )

    async with maker() as session:
        asking = await _asking(session)
        started = await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": made["assessment_id"], "question_count": 3},
            pool=queue,
            phase=PHASE_WORK,
        )

    assert started["started"] is True
    assert started["queued"] == 3
    assert len(queue.jobs) == 3
    assert {name for name, _ in queue.jobs} == {"write_draft_question"}


@pytest.mark.asyncio
async def test_drafting_twice_does_not_start_a_second_round(stack) -> None:
    """Mỗi lần một vòng, để hai bộ chỉ dẫn không bao giờ dùng chung một đề.

    Hai vòng chồng lên nhau chính là hỏng hóc mà brief đóng băng được đặt ra để
    ngăn, và cách ngăn rẻ nhất là từ chối trong khi còn thứ gì đang chạy.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )
        again = await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": made["assessment_id"], "question_count": 3},
            pool=queue,
            phase=PHASE_WORK,
        )
        assert again["started"] is True

        second = await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": made["assessment_id"], "question_count": 3},
            pool=queue,
            phase=PHASE_WORK,
        )

    assert second["started"] is False
    assert len(queue.jobs) == 3


@pytest.mark.asyncio
async def test_no_tool_writes_into_an_approved_paper(stack) -> None:
    """ADR-01: duyệt là khoá nội dung lại.

    Đây là nơi đầu tiên gọi `assert_editable`, và cái khoá đó là toàn bộ lý do
    việc duyệt có nghĩa gì — nếu câu hỏi vẫn đổi được sau đó, thì giáo viên đã
    duyệt một thứ khác.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )
        draft = await session.get(Assessment, made["assessment_id"])
        assert draft is not None
        # Gán tay chỉ vì chưa có gì khác làm được: endpoint duyệt tới ở pha 4, và
        # lúc đó dòng này sẽ thành một lượt gọi tới nó. Được phép ở đây và không
        # chỗ nào trong `teacher_tools.py`, nơi `tools-decide-nothing` từ chối
        # đúng phép gán này.
        draft.state = AssessmentState.APPROVED
        await session.commit()

        locked = await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": made["assessment_id"], "question_count": 3},
            pool=queue,
            phase=PHASE_WORK,
        )

    assert locked["started"] is False
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_a_tool_cannot_draft_into_another_teachers_paper(stack) -> None:
    """ADR-22, ở phía ghi.

    Lời từ chối đọc ra giống y như với một đề không tồn tại, vì hai câu trả lời
    phân biệt được sẽ cho bất cứ ai dò xem giáo viên khác đang có những gì.
    """
    maker, queue = stack

    async with maker() as session:
        stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
        session.add(stranger)
        await session.flush()
        theirs = Assessment(
            teacher_id=stranger.id,
            title="Đề của người khác",
            subject="Toán",
            grade="11",
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(theirs)
        await session.flush()
        session.add(
            DraftBrief(
                assessment_id=theirs.id,
                topic_scope="của người khác",
                question_count=2,
                version=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        stranger_draft = theirs.id

    async with maker() as session:
        asking = await _asking(session)
        refused = await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": stranger_draft},
            pool=queue,
            phase=PHASE_WORK,
        )
        absent = await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": "không-tồn-tại"},
            pool=queue,
            phase=PHASE_WORK,
        )

    assert refused == absent
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_the_catalog_offers_only_reversible_writes(stack) -> None:
    """Một tool đã mô tả cho model là một tool nó sẽ thử, nên danh sách này là hợp đồng.

    Ở đây không có gì duyệt hay phát hành. Đó không phải sự bỏ sót: ADR-05 giữ
    hai việc ấy sau một form và một lần xác nhận, và cách tôn trọng nó rẻ nhất là
    luồng chat không có động từ nào như thế. Ranh giới của ADR-05 nói về những
    hành động **không lấy lại được**, không phải về việc ghi — nên ba tool ghi
    nằm đây mà không vượt ranh: mọi tool trong đó đều đảo lại được khi đề chưa
    được duyệt.
    """
    maker, _ = stack

    async with maker() as session:
        asking = await _asking(session)
        # Hợp đồng là **cả** catalog, nên hợp hai pha lại: một tool thứ bảy lọt vào pha nào
        # cũng phải tự biện hộ cho mình.
        offered = {
            tool.name for phase in (PHASE_PLAN, PHASE_WORK) for tool in catalog_for(asking, phase)
        }

    # Nửa bền vững: không tên nào ở đây đẩy việc tới học sinh, dù sau này có thêm
    # bao nhiêu tool nữa.
    assert not any(
        word in name
        for name in offered
        for word in ("approve", "publish", "release", "withdraw", "duyet", "phat_hanh")
    )
    # Và dây bẫy: một tool thứ bảy sẽ làm dòng này đỏ và phải tự biện hộ cho mình.
    assert offered == {
        "list_class",
        "get_class",
        "list_assessment",
        "class_assessment_summary",
        "create_draft",
        "start_drafting",
    }


@pytest.mark.asyncio
async def test_a_started_round_is_visible_as_pending_work(stack) -> None:
    """Việc duyệt cần biết có câu hỏi nào còn đang được viết hay không.

    Duyệt một đề viết dở là duyệt những câu hỏi giáo viên chưa từng thấy, nên con
    số đó phải đọc được từ trước khi có endpoint duyệt để dùng nó.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )
        await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": made["assessment_id"], "question_count": 3},
            pool=queue,
            phase=PHASE_WORK,
        )

    async with maker() as session:
        rows = (
            await session.scalars(
                select(DraftItem).where(DraftItem.assessment_id == made["assessment_id"])
            )
        ).all()

    assert len(rows) == 3
    assert {row.status for row in rows} == {"pending"}
    assert {row.brief_version for row in rows} == {1}


def _good(stem: str) -> GeneratedQuestion:
    """Một câu hỏi thoả ADR-18: một đáp án đúng, các `Distractor` có nhãn, hai `Method`."""
    return GeneratedQuestion(
        stem=stem,
        options=(
            GeneratedOption(label="A", text="đúng", is_correct=True),
            GeneratedOption(label="B", text="sai B", is_correct=False, error_label="lỗi B"),
            GeneratedOption(label="C", text="sai C", is_correct=False, error_label="lỗi C"),
        ),
        methods=(
            SolutionMethod(title="Cách 1", body="..."),
            SolutionMethod(title="Cách 2", body="..."),
        ),
        learning_objective="đạo hàm",
    )


@pytest.mark.asyncio
async def test_no_job_is_fired_for_a_draft_without_a_brief(stack) -> None:
    """Cửa này nói về job, không nói về số dòng trong bảng.

    Test từ chối ở trên chứng minh không có đề nháp nào được tạo từ một brief
    chưa đủ. Test này chứng minh phần tốn tiền: một đề hoàn toàn không có brief
    thì không tiêu gì cả, vì brief là thứ mọi job được viết ra từ đó.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        bare = Assessment(
            teacher_id=asking.teacher_id,
            title="Đề không có brief",
            subject="Toán",
            grade="12",
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(bare)
        await session.commit()

        refused = await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": bare.id},
            pool=queue,
            phase=PHASE_WORK,
        )

    assert refused["started"] is False
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_asking_twice_opens_two_drafts_rather_than_reusing_one(stack) -> None:
    """Hai yêu cầu là hai đề.

    Được pin lại vì cả hai lựa chọn còn lại đều tệ hơn: tái dùng đề nháp đầu sẽ
    âm thầm trộn hai brief vào một đề, còn từ chối yêu cầu thứ hai sẽ chặn một
    giáo viên soạn hai đề trong cùng một lần ngồi. Giá phải trả là một lượt hỏng
    sau điểm này sẽ để lại một đề nháp rỗng — `backlog.md` có ghi việc đó, vì
    muốn dọn nó thì cần một đường xoá mà hiện chưa tồn tại.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        first = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )
        second = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )

    assert first["created"] is True
    assert second["created"] is True
    assert first["assessment_id"] != second["assessment_id"]


@pytest.mark.asyncio
async def test_a_reading_tool_writes_nothing(stack) -> None:
    """Một tool đọc thì đọc, kể cả khi có một câu đang nằm sẵn chờ được thu.

    Luật này từng được ghim trên `draft_progress`, vì tool ấy gọi `harvest`: nó ghi
    `Question` và đẩy đề sang `HAS_QUESTIONS` trong khi khai `writes=False`. Tool ấy nay
    đã bỏ — SSE kể tiến độ — nên luật chuyển sang những tool đọc còn sống. Một luật không
    còn chủ thể thì không phải một luật đã hết hạn; nó là một luật cần chủ thể mới.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )
        await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": made["assessment_id"], "question_count": 3},
            pool=queue,
            phase=PHASE_WORK,
        )

    queue.finish("job-1", _good("Đạo hàm của y = x² là gì?"))

    async with maker() as session:
        asking = await _asking(session)
        for name in ("list_class", "list_assessment", "class_assessment_summary"):
            await execute(session, asking, name, {"class_id": "", "assessment_id": ""}, pool=queue)

    async with maker() as session:
        draft = await session.get(Assessment, made["assessment_id"])
        landed = (
            await session.scalars(
                select(Question).where(Question.assessment_id == made["assessment_id"])
            )
        ).all()

    # Câu kia vẫn nằm chờ trong Redis: không tool đọc nào thu nó về.
    assert landed == []
    assert draft is not None and draft.state == AssessmentState.EMPTY


@pytest.mark.asyncio
async def test_harvest_is_what_brings_a_finished_question_into_the_draft(stack) -> None:
    """Thu hoạch vẫn là đường duy nhất, chỉ không còn đi kèm một tool đọc.

    Sau ADR-25 nó chạy ở hai chỗ có người đang chờ: đường nghe tiến độ của một lượt
    đang chạy, và cổng duyệt. Test này gọi thẳng nó, vì nó là cái cửa chứ không phải
    một hiệu ứng phụ của ai đó.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(
            session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_WORK
        )
        await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": made["assessment_id"], "question_count": 3},
            pool=queue,
            phase=PHASE_WORK,
        )

    queue.finish("job-1", _good("Đạo hàm của y = x² là gì?"))

    async with maker() as session:
        landed = await harvest(session, queue, get_settings(), made["assessment_id"])

    assert landed == 1

    async with maker() as session:
        written = list(
            await session.scalars(
                select(Question.stem).where(Question.assessment_id == made["assessment_id"])
            )
        )

    assert written == ["Đạo hàm của y = x² là gì?"]

    async with maker() as session:
        draft = await session.get(Assessment, made["assessment_id"])
        waiting = list(
            await session.scalars(
                select(DraftItem).where(
                    DraftItem.assessment_id == made["assessment_id"],
                    DraftItem.status == "pending",
                )
            )
        )

    # Hai ô còn đang chạy, và câu đầu tiên đã đẩy đề ra khỏi EMPTY.
    assert len(waiting) == 2
    assert draft is not None and draft.state == AssessmentState.HAS_QUESTIONS


@pytest.mark.asyncio
async def test_the_planning_phase_sees_no_tool_that_writes(stack) -> None:
    """Ranh giới pha của ADR-25, đọc từ chính cờ `writes` chứ không từ một danh sách thứ hai.

    Pha lên plan chỉ tra cứu. Đó là thứ làm cho một câu hỏi lại không bao giờ bỏ lại việc
    đã làm dở: không phải vì prompt dặn thế, mà vì model không được cấp tool nào để ghi.
    """
    maker, _ = stack
    async with maker() as session:
        asking = await _asking(session)

    planning = {spec.name for spec in catalog_for(asking, PHASE_PLAN)}
    working = {spec.name for spec in catalog_for(asking, PHASE_WORK)}

    assert planning == {
        "list_class",
        "get_class",
        "list_assessment",
        "class_assessment_summary",
    }
    assert working == {"create_draft", "start_drafting"}
    assert planning & working == set()


@pytest.mark.asyncio
async def test_a_write_tool_asked_for_while_planning_is_refused(stack) -> None:
    """Cổng nằm ở `execute`, không ở catalog: catalog chỉ là lời mời, model đọc sai được."""
    maker, queue = stack
    async with maker() as session:
        asking = await _asking(session)
        with pytest.raises(UnknownTool):
            await execute(
                session, asking, "create_draft", dict(_FULL), pool=queue, phase=PHASE_PLAN
            )


def test_a_plan_step_reads_the_id_the_step_before_it_made() -> None:
    """`start_drafting` cần một id mà `create_draft` mới sinh ra.

    Không có cú pháp này thì một plan hai bước phụ thuộc nhau không diễn tả được, và cả
    ADR-25 sụp ở đúng chỗ đó.
    """
    done = [{"created": True, "assessment_id": "a-42", "title": "Đề tích phân"}]
    resolved = resolve_args({"assessment_id": "{1.assessment_id}"}, done)
    assert resolved == {"assessment_id": "a-42"}


def test_a_literal_argument_passes_through_untouched() -> None:
    """Chỉ đúng hình dạng `{k.field}` mới là tham chiếu; mọi thứ khác là chữ của giáo viên."""
    resolved = resolve_args({"topic_scope": "chương Hàm số {nâng cao}"}, [])
    assert resolved == {"topic_scope": "chương Hàm số {nâng cao}"}


@pytest.mark.parametrize(
    "reference",
    [
        "{2.assessment_id}",  # bước chưa chạy
        "{1.khong_co_field_nay}",  # field không có trong kết quả
        "{0.assessment_id}",  # không có bước 0 — cạnh dưới
        "{1.assessment_id} thêm chữ",  # trông như tham chiếu mà sai khuôn
        "{ 1.assessment_id }",  # khoảng trắng bên trong
    ],
)
def test_a_reference_that_cannot_be_resolved_stops_the_step(reference: str) -> None:
    """Hỏng thì hỏng **trước khi bước này chạy**, chứ không hỏng ở trong tool.

    Ba ca cuối là ba chỗ một chuỗi *gần đúng* đi lọt: để chúng qua nguyên văn nghĩa là một id
    rác tới tay một tool ghi, rồi lộ ra ở tận bên trong dưới dạng "không tìm thấy đề nào".
    Việc từ chối **trọn gói** một plan là phép kiểm tĩnh của vòng chạy plan, không phải của
    hàm này.
    """
    done = [{"created": True, "assessment_id": "a-42"}]
    with pytest.raises(Unresolvable):
        resolve_args({"assessment_id": reference}, done)


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_a_reference_to_an_empty_field_is_refused(empty) -> None:
    """Một field có mặt mà rỗng là một tham chiếu vô dụng, không phải một giá trị."""
    with pytest.raises(Unresolvable):
        resolve_args({"assessment_id": "{1.assessment_id}"}, [{"assessment_id": empty}])


def test_a_reference_to_a_list_is_refused() -> None:
    """`written` là một danh sách câu hỏi; nhét nó vào một tham số chuỗi là một lỗi im lặng."""
    with pytest.raises(Unresolvable):
        resolve_args({"assessment_id": "{1.written}"}, [{"written": ["c1", "c2"]}])


@pytest.mark.asyncio
async def test_a_read_tool_asked_for_while_working_is_refused(stack) -> None:
    """Cổng chặn cả hai chiều: pha thực hiện chỉ chạy tool ghi.

    Chiều này ít rõ hơn chiều kia nhưng cũng là một luật: một plan hỏi `list_class` giữa
    lúc đang ghi là một plan muốn tra cứu trong lúc làm, mà việc tra cứu thuộc về pha
    trước. Chủ thể cũ của test này là `draft_progress`, tool đã bỏ vì SSE kể tiến độ.
    """
    maker, queue = stack
    async with maker() as session:
        asking = await _asking(session)
        with pytest.raises(UnknownTool):
            await execute(
                session,
                asking,
                "list_class",
                {},
                pool=queue,
                phase=PHASE_WORK,
            )


def test_the_model_never_sees_the_optional_fields_of_a_draft() -> None:
    """Thứ không nhìn thấy thì không hỏi được.

    `difficulty` và `title` là tuỳ chọn, và tool vẫn **nhận** chúng. Nhưng chúng không còn được
    mô tả cho model: đo trên trình duyệt thật năm lần với gpt-4o-mini, mỗi lần prompt cấm hỏi một
    mục thì model tìm ra một mục khác chưa bị cấm — tên đề, độ khó, lớp, rồi xin xác nhận lại thứ
    vừa đọc. Mỗi câu hỏi thừa tiêu trọn một lượt của giáo viên.

    Đây là cùng một phép sửa mà ADR-25 dùng cho ranh giới pha: bỏ tool ghi khỏi catalog pha 1 thay
    vì dặn model đừng gọi. Một lời dặn thì model quên được; một danh sách thiếu thì không.
    """
    asking = Asking(teacher_id="t", teacher_code="GV-001", full_name="Cô Lan")
    spec = next(one for one in catalog_for(asking, PHASE_WORK) if one.name == "create_draft")

    assert set(spec.arguments) == {"subject", "grade", "topic_scope"}

    # Và `question_count` không nằm trong số đó: nó rời khỏi `create_draft` cùng lúc rời
    # khỏi brief. Một đề trống chưa có số câu nào, nên hỏi trước con số ấy là buộc giáo
    # viên quyết một thứ họ chưa biết. Nó về `start_drafting`, kèm cả mức trần.
    soan = next(one for one in catalog_for(asking, PHASE_WORK) if one.name == "start_drafting")
    assert "question_count" in soan.arguments


@pytest.mark.asyncio
async def test_each_reading_tool_answers_in_exactly_one_shape(stack) -> None:
    """Một tool, một hình dạng trả về. Đó là toàn bộ lý do danh mục này được chia lại.

    `find_class` có **bốn** hình dạng, vì nó làm hai việc: tra theo tên, và tự dựng một
    câu hỏi lại khi hai lớp trùng tên. Model phải đoán lần này nhận hình nào, và ba trong
    bốn hình đều là *"đây là danh sách, tự chọn đi"*. Nên test này đo đúng cái tính chất
    thay thế nó: mỗi khoá dưới đây là một hợp đồng, và đổi một khoá là đổi thứ model đọc.

    `candidates` là khoá nhạy nhất trong số đó. `teacher_chat._choices_from` dựng các nút
    của một câu hỏi lại **chỉ** từ nó — đó là cách ADR-23 giữ cho *model viết câu hỏi, BE
    viết các câu trả lời*. Đổi tên nó là bỏ các nút đi, và câu hỏi lại tụt về một bong
    bóng chữ mà giáo viên phải tự gõ câu trả lời.
    """
    maker, queue = stack
    async with maker() as session:
        asking = await _asking(session)
        paper = await session.scalar(select(Assessment))
        assert paper is not None

        listed = await execute(session, asking, "list_class", {}, pool=queue)
        only = listed["candidates"][0]
        got = await execute(
            session, asking, "get_class", {"class_id": only["class_id"]}, pool=queue
        )
        gone = await execute(session, asking, "get_class", {"class_id": "khong-co"}, pool=queue)
        papers = await execute(
            session, asking, "list_assessment", {"class_id": only["class_id"]}, pool=queue
        )
        nameless = await execute(session, asking, "list_assessment", {}, pool=queue)

    # `list_class`: một danh sách và một con số, không có cờ `found` nào. Nó luôn trả lời
    # được, nên một cờ thành-công ở đây sẽ luôn là `True` -- tức không nói gì.
    assert set(listed) == {"candidates", "more"}
    assert set(only) == {"class_id", "name", "student_count"}
    assert listed["more"] == 0

    # `get_class`: hai kết cục, và cả hai đọc được từ cùng một cờ.
    assert got == {"found": True, **only}
    assert gone["found"] is False
    assert gone["reason"]
    # ADR-22 ở dạng hình dạng dữ liệu: một lời từ chối không được chở theo tham số đã hỏi,
    # vì một id đoán đúng mà quay về kèm chính nó là một cách khẳng định rằng nó tồn tại.
    assert "class_id" not in gone

    # `list_assessment`: hai kết cục, cùng một cờ `found` -- đúng khuôn của `get_class`,
    # nên model đọc cả hai tool bằng cùng một phản xạ. Đó là ý của "một hình dạng": không
    # phải một kết cục duy nhất, mà một cách duy nhất để biết mình đang đọc kết cục nào.
    assert set(papers) == {"found", "assessments"}
    assert papers["found"] is True
    assert [one["assessment_id"] for one in papers["assessments"]] == [paper.id]
    assert set(papers["assessments"][0]) == {"assessment_id", "title"}

    assert nameless["found"] is False
    assert nameless["reason"]
    # Không trả về `assessments: []`: một danh sách rỗng đọc lên là "lớp này chưa có đề",
    # còn sự thật là chưa ai nói lớp nào. Hai câu đó không được trộn vào nhau.
    assert "assessments" not in nameless


@pytest.mark.asyncio
async def test_the_question_cap_lives_where_the_questions_are_made(stack) -> None:
    """Năm trăm câu: `create_draft` thôi từ chối, `start_drafting` vẫn từ chối.

    Mức trần đi theo con số nó canh. Một đề trống không có số câu nào để canh, nên
    `create_draft` từ chối ở đây là từ chối một việc nó không làm -- và nó buộc giáo viên
    quyết một con số trước khi biết đề sẽ dài bao nhiêu.

    Hai nửa của khẳng định này đều cần thiết. Thiếu nửa đầu, test xanh với một
    `create_draft` vẫn canh trần. Thiếu nửa sau, nó xanh với một hệ thống **không ai**
    canh trần, và năm trăm job đi vào queue.
    """
    maker, queue = stack
    async with maker() as session:
        asking = await _asking(session)
        opened = await execute(
            session,
            asking,
            "create_draft",
            {"subject": "Toán", "grade": "12", "topic_scope": "đạo hàm", "question_count": 500},
            pool=queue,
            phase=PHASE_WORK,
        )
        assert opened["created"] is True

        refused = await execute(
            session,
            asking,
            "start_drafting",
            {"assessment_id": opened["assessment_id"], "question_count": 500},
            pool=queue,
            phase=PHASE_WORK,
        )

    assert refused["started"] is False
    assert refused["reason"]
    # Và không một job nào được đẩy đi: một lời từ chối sau khi đã bắn job là một lời từ
    # chối nói sai.
    assert queue.jobs == []
