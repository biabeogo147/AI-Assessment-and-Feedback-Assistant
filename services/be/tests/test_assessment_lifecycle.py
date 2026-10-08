"""Bốn state của một `Assessment`, và ai là chủ của nó.

ADR-01 cho một `Assessment` bốn state và hai luật về chúng: duyệt là **khoá nội
dung**, và việc duyệt phải đảo lại được vì nó không phải cổng cuối. Tới giờ không
điều nào trong đó tồn tại trong code — chính ADR-01 nói vậy, ở một dòng viết "Chưa
có ở backend: không model, không endpoint, không test nào biết tới bốn trạng thái
này".

Test đầu tiên ở đây chính là cái mà `AGENTS.md` gọi tên trong bảng invariant là
"Teacher approves an assessment before release". Nó từng nằm trong nhóm luật không
ai thi hành; file này là thứ đưa nó ra khỏi nhóm đó.

Quyền sở hữu được test ở tầng `schema`, không qua một route, vì chưa có route nào
cho giáo viên. Điều chứng minh được hôm nay là mọi lớp và mọi đề đều có chủ, và một
query lọc theo một giáo viên khác thì về rỗng — đó là toàn bộ những gì thay đổi này
thêm vào. Phần phân quyền dùng tới nó sẽ tới cùng với tool executor.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.assessment_state import AssessmentState, advance, assert_editable
from be.db import bind_sessions
from be.seed import seed_if_empty
from schema.ddl import prepare_schema
from schema.models import Assessment, SchoolClass, Teacher


@pytest_asyncio.fixture
async def session():
    """Một database in-memory đã seed, với session đang mở."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as open_session:
        await seed_if_empty(open_session)
        yield open_session

    await engine.dispose()
    db_module._SESSION_MAKER = None


def _draft() -> Assessment:
    """Một `Assessment` chưa có câu hỏi nào, không gắn với session nào."""
    return Assessment(
        title="Đề đang soạn",
        subject="Toán",
        grade="12",
        state=AssessmentState.EMPTY,
    )


def test_teacher_approves_an_assessment_before_release() -> None:
    """Phát hành mà chưa duyệt thì bị từ chối.

    Đây là invariant mà `AGENTS.md` liệt ra là cần một test khi UC-02 được dựng.
    ADR-05 gọi việc duyệt là cổng đầu trong ba cổng teacher-in-the-loop, và một cái cổng
    đi vòng qua được thì không phải cổng.
    """
    assessment = _draft()
    advance(assessment, AssessmentState.HAS_QUESTIONS)

    with pytest.raises(HTTPException) as refused:
        advance(assessment, AssessmentState.PUBLISHED)

    assert refused.value.status_code == 409
    assert assessment.state == AssessmentState.HAS_QUESTIONS


def test_an_assessment_walks_the_four_states_of_adr_01() -> None:
    """Trọn con đường, đúng thứ tự: rỗng, có câu hỏi, đã duyệt, đã phát hành."""
    assessment = _draft()

    for state in (
        AssessmentState.HAS_QUESTIONS,
        AssessmentState.APPROVED,
        AssessmentState.PUBLISHED,
    ):
        advance(assessment, state)
        assert assessment.state == state


def test_approval_locks_the_content() -> None:
    """Câu hỏi không được sửa nữa khi đề đã được duyệt.

    ADR-01: "Duyệt khoá nội dung". Không có điều này thì việc duyệt chẳng có nghĩa gì
    — chính ADR đó lập luận như vậy cho luật của mình.
    """
    assessment = _draft()
    advance(assessment, AssessmentState.HAS_QUESTIONS)
    assert_editable(assessment)  # vẫn còn mở, nên dòng này không được ném exception

    advance(assessment, AssessmentState.APPROVED)

    with pytest.raises(HTTPException) as refused:
        assert_editable(assessment)
    assert refused.value.status_code == 409


def test_unapproving_reopens_the_content() -> None:
    """Việc duyệt đảo lại được khi đề chưa phát hành.

    ADR-01 đòi phải có cạnh quay về trạng thái sửa được, vì duyệt không phải cổng cuối
    và một giáo viên phát hiện câu hỏi tồi sau khi đã duyệt thì không được mắc kẹt với
    nó.
    """
    assessment = _draft()
    advance(assessment, AssessmentState.HAS_QUESTIONS)
    advance(assessment, AssessmentState.APPROVED)

    advance(assessment, AssessmentState.HAS_QUESTIONS)

    assert assessment.state == AssessmentState.HAS_QUESTIONS
    assert_editable(assessment)


def test_a_published_assessment_never_returns_to_editing() -> None:
    """Phát hành đóng cửa việc sửa, và chỉ đóng cửa việc sửa.

    ADR-01 cấm đường quay về soạn thảo: đổi đề ngay dưới chân những học sinh đang làm
    nó chính là điều duy nhất việc phát hành phải ngăn.

    `APPROVED` cố ý không có trong vòng lặp này. ADR-02 nói thu hồi đưa một đề trở về
    *đã duyệt* với nội dung vẫn bị khoá, nên `published → approved` là một cạnh hợp lệ
    trong tương lai. Khẳng định ở đây rằng nó bất hợp pháp sẽ biến test này thành cái
    chốt chặn ngược lại một quyết định đã được đưa ra.
    """
    assessment = _draft()
    advance(assessment, AssessmentState.HAS_QUESTIONS)
    advance(assessment, AssessmentState.APPROVED)
    advance(assessment, AssessmentState.PUBLISHED)

    for state in (AssessmentState.EMPTY, AssessmentState.HAS_QUESTIONS):
        with pytest.raises(HTTPException):
            advance(assessment, state)


def test_an_assessment_starts_empty_before_it_is_ever_saved() -> None:
    """Một `Assessment` vừa dựng nằm ở state rỗng, không phải ở chẳng state nào.

    Giá trị mặc định của một cột do câu INSERT áp vào, nên giữa `Assessment(...)` và
    lượt flush thì thuộc tính đó là None. Mọi đường tạo một đề rồi thêm câu hỏi đầu
    tiên trong cùng một unit of work đều đi qua khoảng hở ấy, và máy trạng thái phải
    trả lời được ở đó nữa — bằng một lời từ chối tiếng Việt khi cạnh đi sai, không bao
    giờ bằng một `ValueError` nói về None.
    """
    fresh = Assessment(teacher_id="whoever", title="Chưa lưu", subject="Toán", grade="12")

    advance(fresh, AssessmentState.HAS_QUESTIONS)

    assert fresh.state == AssessmentState.HAS_QUESTIONS


@pytest.mark.asyncio
async def test_a_state_outside_the_lifecycle_cannot_be_stored(session) -> None:
    """Database từ chối một state mà ADR-01 không định nghĩa.

    `advance` là cửa duy nhất, nhưng một cái cửa chỉ là cửa khi mọi người đều đi qua
    nó. Nếu không, chỉ một phép gán đi lạc — `state = "draft"`, đúng giá trị cột này
    từng mặc định — sẽ được ghi xuống êm ru rồi mới ném exception ở lượt đọc bảng tiếp
    theo, trong một route chẳng liên quan gì tới kẻ đã ghi nó.
    """
    assessment = await session.scalar(select(Assessment))
    assert assessment is not None

    assessment.state = "draft"

    with pytest.raises(StatementError):
        await session.flush()


@pytest.mark.asyncio
async def test_the_stored_string_is_the_one_the_documents_name(session) -> None:
    """Cột đó chứa `published`, không phải `PUBLISHED`.

    SQLAlchemy lưu một enum Python theo **name** của thành viên nếu không được bảo
    khác đi, nên chỗ này từng trôi lệch khỏi bộ từ vựng đã viết trong tài liệu mà
    chẳng có gì đỏ: cả `data-model.md` và ADR-01 đều gọi tên các giá trị viết thường,
    và những dòng ghi từ trước khi có enum cũng chứa `published`. Một giá trị được lưu
    mà không ai ghi lại là một giá trị người sau phải tự mò ra từ một phiên psql.
    """
    stored = await session.scalar(
        select(Assessment.state).where(Assessment.state == AssessmentState.PUBLISHED)
    )
    assert stored is AssessmentState.PUBLISHED

    raw = await session.execute(text("SELECT state FROM assessments LIMIT 1"))
    assert raw.scalar_one() == "published"


@pytest.mark.asyncio
async def test_a_class_cannot_exist_without_an_owner(session) -> None:
    """Một lớp không có giáo viên bị `schema` từ chối.

    ADR-22 gọi cột đó là not-nullable; đây là test biến tuyên bố ấy thành thứ kiểm được
    thay vì một câu trong tài liệu.
    """
    session.add(SchoolClass(name="Lớp không chủ"))

    with pytest.raises(IntegrityError):
        await session.flush()


def test_skipping_a_state_is_refused() -> None:
    """Một đề rỗng thì không duyệt được.

    ADR-01 cho state rỗng một luật riêng: nó chặn việc phát hành. Duyệt một đề không có
    câu hỏi nào sẽ để một giáo viên nhận trách nhiệm cho nội dung không tồn tại.
    """
    assessment = _draft()

    with pytest.raises(HTTPException) as refused:
        advance(assessment, AssessmentState.APPROVED)

    assert refused.value.status_code == 409


@pytest.mark.asyncio
async def test_every_class_and_assessment_has_an_owner(session) -> None:
    """Các dòng đã seed đều nêu tên giáo viên mà chúng thuộc về.

    ADR-13 nói một lớp thuộc về một giáo viên. Luật đó từng không có cột nào để trú, nên
    không gì thi hành được nó và cũng không gì hỏi được về nó.
    """
    teacher = await session.scalar(select(Teacher))
    assert teacher is not None

    classes = (await session.scalars(select(SchoolClass))).all()
    assessments = (await session.scalars(select(Assessment))).all()
    assert classes and assessments

    assert all(row.teacher_id == teacher.id for row in classes)
    assert all(row.teacher_id == teacher.id for row in assessments)


@pytest.mark.asyncio
async def test_owner_partitions_the_data_both_ways(session) -> None:
    """Query của mỗi giáo viên trả về đủ phần của mình và không phần của bất cứ ai khác.

    Cả hai hướng đều quan trọng. Một test chỉ kiểm rằng người lạ không thấy gì sẽ vẫn
    xanh khi `teacher_id` bị điền sai, khi bộ lọc đọc sai cột, và cả khi cột ấy chẳng
    phân hoạch gì cả — nó chỉ chứng minh rằng một query tìm tập rỗng thì về rỗng. Vậy
    nên người lạ ở đây có những dòng của riêng mình, và điều được khẳng định là hai tập
    đó rời nhau và đầy đủ.
    """
    mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
    assert mine is not None

    stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
    session.add(stranger)
    await session.flush()

    their_class = SchoolClass(teacher_id=stranger.id, name="11B")
    their_assessment = Assessment(
        teacher_id=stranger.id,
        title="Đề của người khác",
        subject="Toán",
        grade="11",
        state=AssessmentState.EMPTY,
        created_at=datetime.now(UTC),
    )
    session.add_all([their_class, their_assessment])
    await session.flush()

    async def classes_of(teacher: Teacher) -> set[str]:
        query = select(SchoolClass).where(SchoolClass.teacher_id == teacher.id)
        return {row.id for row in await session.scalars(query)}

    async def assessments_of(teacher: Teacher) -> set[str]:
        rows = await session.scalars(select(Assessment).where(Assessment.teacher_id == teacher.id))
        return {row.id for row in rows}

    assert their_class.id in await classes_of(stranger)
    assert their_class.id not in await classes_of(mine)
    assert await classes_of(mine)  # lớp đã seed thì họ vẫn thấy được

    assert their_assessment.id in await assessments_of(stranger)
    assert their_assessment.id not in await assessments_of(mine)
    assert await assessments_of(mine)
