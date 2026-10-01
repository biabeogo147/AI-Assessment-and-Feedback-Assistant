"""Biến thứ giáo viên gõ vào thành một dòng dữ liệu, hoặc từ chối đoán.

`classes.name` không unique, nên một cái tên không phải một identifier. Mọi tool
nhận vào một lớp đều phải lấy nó từ đâu đó, và chỉ có ba câu trả lời trung thực:
"lớp này đây", "một trong mấy lớp này — lớp nào?" và "không lớp nào của bạn". Chọn
lấy dòng đầu tiên sẽ là câu trả lời thứ tư, câu sai, và là câu không ai nhận ra:
trợ lý sẽ đọc điểm của một lớp khác rồi nói ra một cách đầy tự tin.

Việc từ chối đoán đó là cổng đầu vào của ADR-05, và ADR-23 là nơi nó được ghi xuống.
Điều các test này pin lại là phần mà một prompt không giữ nổi: các candidate đưa ra
trong một câu hỏi làm rõ đều tới từ những dòng BE đã đọc, và một lớp thuộc về giáo
viên khác được trả lời giống y một lớp không tồn tại (ADR-22).
"""

import unicodedata

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions, prepare_schema
from be.identity import Asking
from be.models import SchoolClass, Student, Teacher
from be.resolve import Ambiguous, NotFound, Resolved, resolve_class
from be.seed import seed_if_empty
from be.teacher_tools import execute


@pytest_asyncio.fixture
async def stack():
    """Một database đã seed, cộng một giáo viên thứ hai có lớp riêng của mình."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
        session.add(stranger)
        await session.flush()
        session.add(SchoolClass(teacher_id=stranger.id, name="11B"))
        await session.commit()

    yield maker

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _mine(session) -> Asking:
    teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
    assert teacher is not None
    return Asking.of(teacher)


async def _add_class(session, asking: Asking, name: str, students: int = 0) -> SchoolClass:
    """Cho giáo viên đang hỏi thêm một lớp nữa, kèm danh sách học sinh riêng."""
    school_class = SchoolClass(teacher_id=asking.teacher_id, name=name)
    session.add(school_class)
    await session.flush()
    for index in range(students):
        session.add(
            Student(
                class_id=school_class.id,
                full_name=f"Học sinh {name} {index}",
                student_code=f"{name}-{index}",
            )
        )
    await session.flush()
    return school_class


@pytest.mark.asyncio
async def test_a_name_that_matches_one_class_resolves(stack) -> None:
    """Ca bình thường, và cũng là ca mà mọi câu trả lời khác đem ra đo với nó."""
    async with stack() as session:
        asking = await _mine(session)

        found = await resolve_class(session, asking, "12A")

    assert isinstance(found, Resolved)
    assert found.name == "12A"
    assert found.class_id


@pytest.mark.asyncio
async def test_case_and_the_word_lop_do_not_matter(stack) -> None:
    """Giáo viên gõ "lớp 12a", không gõ một identifier đã chuẩn hoá.

    Từ chối cách gõ đó sẽ đẩy trợ lý vào chỗ hỏi một câu mà nó đã có sẵn câu trả lời,
    và điều đó dạy giáo viên thôi tin vào câu hỏi làm rõ ngay lúc nó thật sự cần.
    """
    async with stack() as session:
        asking = await _mine(session)

        for typed in ("12a", "  12A  ", "lớp 12A", "Lớp 12a"):
            found = await resolve_class(session, asking, typed)
            assert isinstance(found, Resolved), typed


@pytest.mark.asyncio
async def test_two_classes_of_the_same_name_ask_rather_than_pick(stack) -> None:
    """Cả hai dòng trở về dưới dạng candidate, và không dòng nào được chọn.

    `classes.name` không có unique constraint chính vì chuyện này xảy ra — một giáo
    viên có thể dạy hai lớp cùng gọi là 12A ở hai năm khác nhau. Các candidate mang
    theo số học sinh để câu hỏi phân biệt được chúng bằng thứ giáo viên nhận ra;
    ADR-05 cấm đánh dấu bất cứ candidate nào là cái nên chọn.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12A", students=7)

        answer = await resolve_class(session, asking, "12A")

    assert isinstance(answer, Ambiguous)
    assert len(answer.candidates) == 2
    assert {candidate.name for candidate in answer.candidates} == {"12A"}
    assert sorted(candidate.student_count for candidate in answer.candidates) == [3, 7]


@pytest.mark.asyncio
async def test_a_partial_name_offers_the_classes_it_could_mean(stack) -> None:
    """ "12" khi có cả 12A và 12B là một câu hỏi, không phải một thất bại.

    Không có điều này, trợ lý sẽ đáp "không có lớp nào như vậy" với một giáo viên gọi
    tên một lớp thật nhưng gọi chưa chính xác, và câu đó đọc ra như hệ thống đã làm mất
    dữ liệu của họ.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12B", students=5)

        answer = await resolve_class(session, asking, "12")

    assert isinstance(answer, Ambiguous)
    assert {candidate.name for candidate in answer.candidates} == {"12A", "12B"}


@pytest.mark.asyncio
async def test_an_exact_name_wins_over_a_longer_one_containing_it(stack) -> None:
    """ "12A" vẫn phân giải được khi tồn tại cả 12A và 12A1.

    So khớp theo chuỗi con là thứ làm một cái tên chưa đủ trở nên hữu dụng, và cũng là
    thứ sẽ làm một cái tên chính xác thành nhập nhằng. Lượt khớp chính xác được thử
    trước, nên gọi tên một lớp cho đúng thì luôn có tác dụng.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12A1", students=9)

        answer = await resolve_class(session, asking, "12A")

    assert isinstance(answer, Resolved)
    assert answer.name == "12A"


@pytest.mark.asyncio
async def test_nothing_of_this_teachers_matches_and_the_list_says_what_does(stack) -> None:
    """Một lời từ chối có kèm tên các lớp của chính giáo viên đó.

    "Không có lớp nào tên đó" đứng một mình để giáo viên tự đoán xem họ gõ sai hay lớp
    đã mất. Danh sách kèm theo biến lời từ chối thành câu trả lời cho câu hỏi tiếp theo.
    """
    async with stack() as session:
        asking = await _mine(session)

        answer = await resolve_class(session, asking, "9Z")

    assert isinstance(answer, NotFound)
    assert {candidate.name for candidate in answer.available} == {"12A"}


@pytest.mark.asyncio
async def test_another_teachers_class_is_answered_as_if_it_did_not_exist(stack) -> None:
    """ADR-22, ở đây được thi hành chứ không chỉ được hứa.

    Hai lời từ chối khác nhau sẽ thành một cái máy dò: gõ hết các tên cho tới khi câu
    chữ đổi là bạn đã vẽ xong bản đồ cả trường. Danh sách lớp của chính giáo viên đang
    hỏi giống nhau trong cả hai câu trả lời, nên không còn gì để mà so.
    """
    async with stack() as session:
        asking = await _mine(session)

        theirs = await resolve_class(session, asking, "11B")
        absent = await resolve_class(session, asking, "9Z")

    assert isinstance(theirs, NotFound)
    assert isinstance(absent, NotFound)
    assert theirs == absent


@pytest.mark.asyncio
async def test_an_empty_name_is_not_found_rather_than_everything(stack) -> None:
    """Một tham số trắng không được phép khớp mọi lớp theo chuỗi con.

    Model là bên điền các tham số này, và một tham số bị bỏ qua sẽ tới nơi dưới dạng "".
    Không có điều này, trợ lý sẽ âm thầm phân giải về đúng cái lớp tình cờ đứng đầu.
    """
    async with stack() as session:
        asking = await _mine(session)

        answer = await resolve_class(session, asking, "   ")

    assert isinstance(answer, NotFound)


@pytest.mark.asyncio
async def test_find_class_hands_the_ambiguity_to_the_loop(stack) -> None:
    """Tool báo ra các candidate thay vì ném exception hay đoán.

    Vòng lặp đưa cái đó về cho model dưới dạng dữ liệu, nên câu hỏi làm rõ do trợ lý
    diễn đạt nhưng dựa trên những dòng BE đã đọc. Đó là nửa của ADR-05 không thể sống
    trong một prompt.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12A", students=7)

        result = await execute(session, asking, "find_class", {"name": "12A"})

    assert result["found"] is False
    assert result["ambiguous"] is True
    assert [candidate["name"] for candidate in result["candidates"]] == ["12A", "12A"]
    assert sorted(candidate["student_count"] for candidate in result["candidates"]) == [3, 7]


@pytest.mark.asyncio
async def test_a_class_with_no_students_still_resolves(stack) -> None:
    """Số học sinh bằng không là một con số, không phải một lớp bị thiếu.

    `outerjoin` cộng `count` là thứ làm chuyện này chạy được, và nó thuộc loại query âm
    thầm trả về rỗng khi viết bằng inner join — khi đó một lớp vừa mới lập sẽ biến mất
    khỏi mọi câu trả lời.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "10C", students=0)

        found = await resolve_class(session, asking, "10C")

    assert isinstance(found, Resolved)
    assert found.student_count == 0


@pytest.mark.asyncio
async def test_a_name_written_exactly_as_stored_wins_over_normalising(stack) -> None:
    """Hai lớp chỉ khác nhau ở khoảng trắng thì vẫn gọi tới được.

    "12A" và "12 A" chuẩn hoá về cùng một chuỗi, nên nếu chỉ dựa vào phép so sau chuẩn
    hoá thì chúng nhập nhằng mãi mãi — và không chuỗi nào giáo viên gõ được sẽ chọn ra
    một trong hai. Thử đúng cách viết đã lưu trước tiên cho cả hai một đường vào, mà
    không làm yếu đi nguyên tắc từ chối đoán.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12 A", students=4)

        spaced = await resolve_class(session, asking, "12 A")
        tight = await resolve_class(session, asking, "12A")

    assert isinstance(spaced, Resolved)
    assert spaced.name == "12 A"
    assert isinstance(tight, Resolved)
    assert tight.name == "12A"


@pytest.mark.asyncio
async def test_the_word_lop_may_carry_punctuation_or_no_space(stack) -> None:
    """Giáo viên cũng gõ cả "Lớp: 12A" và "lớp12A".

    Trước đây mọi cách gõ này đều nhận về câu không-tìm-thấy, và với giáo viên thì câu
    đó đọc ra như hệ thống đã làm mất cái lớp họ đang đứng trước mặt.
    """
    async with stack() as session:
        asking = await _mine(session)

        for typed in ("Lớp: 12A", "lớp12A", "lớp - 12A", "LỚP 12A"):
            found = await resolve_class(session, asking, typed)
            assert isinstance(found, Resolved), typed


@pytest.mark.asyncio
async def test_a_decomposed_name_matches_a_composed_one(stack) -> None:
    """Cùng một từ tiếng Việt viết theo hai cách Unicode vẫn là một từ.

    macOS và iOS gửi văn bản ở dạng phân rã, nên "lớp" có thể tới nơi dưới dạng "l" +
    "o" + U+031B + "p". Không chuẩn hoá dạng đó thì một giáo viên dùng Mac sẽ nhận
    không-tìm-thấy cho mọi lớp họ gọi tên.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12 Văn", students=6)

        decomposed = unicodedata.normalize("NFD", "lớp 12 Văn")

        found = await resolve_class(session, asking, decomposed)

    assert isinstance(found, Resolved)
    assert found.name == "12 Văn"


@pytest.mark.asyncio
async def test_a_missing_name_says_so_instead_of_searching_for_none(stack) -> None:
    """`{"name": null}` là một tham số bị bỏ qua, không phải một lớp tên là "none".

    `str(None)` ra "none", và chuỗi đó sẽ được đem đi tìm, khớp với bất cứ lớp nào có tên
    chứa nó, còn không thì bị báo là "không có lớp nào của bạn tên vậy" — câu sai cho một
    câu hỏi chưa từng gọi tên một lớp nào.
    """
    async with stack() as session:
        asking = await _mine(session)

        result = await execute(session, asking, "find_class", {"name": None})

    assert result["found"] is False
    assert result["reason"] == "chưa có tên lớp nào trong câu hỏi"


@pytest.mark.asyncio
async def test_a_summary_refusal_names_the_assessments_that_do_exist(stack) -> None:
    """Một lời từ chối trống rỗng là một lời mời bịa ra.

    Đo được ở lần chạy với model thật đầu tiên: `class_assessment_summary` trả về
    `{"found": false, "reason": "không tìm thấy..."}` mà không kèm danh sách, và
    gpt-4o-mini lấp khoảng trống đó bằng "12A1, 12A2, 12B1, 12B2" — bốn lớp không tồn
    tại, nói ra với giáo viên kèm theo cả uy tín của hệ thống đứng sau.

    ADR-23 vốn đã có câu trả lời cho `find_class`: một lời từ chối mang theo những dòng
    thật sự tồn tại. Chỗ này áp dụng điều đó cho tool còn lại, và cũng lấp luôn khoảng
    hở mà chính lần chạy ấy phơi ra — chẳng có gì trong catalog nói cho model biết nên
    hỏi về đề nào, nên nó phải đoán một id.
    """
    async with stack() as session:
        asking = await _mine(session)
        found = await resolve_class(session, asking, "12A")
        assert isinstance(found, Resolved)

        answer = await execute(
            session,
            asking,
            "class_assessment_summary",
            {"class_id": found.class_id, "assessment_id": "không-phải-id-thật"},
        )

    assert answer["found"] is False
    # Đề thật, để câu hỏi tiếp theo gọi tên nó được thay vì bịa ra một cái.
    titles = [entry["title"] for entry in answer["assessments_in_this_class"]]
    assert titles == ["Kiểm tra 15 phút — Hàm số"]
    assert all(entry["assessment_id"] for entry in answer["assessments_in_this_class"])
