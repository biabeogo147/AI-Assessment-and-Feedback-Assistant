"""Biến thứ giáo viên gõ vào thành một dòng dữ liệu, hoặc từ chối đoán.

`classes.name` không unique, nên một cái tên không phải một identifier. Mọi tool
nhận vào một lớp đều phải lấy nó từ đâu đó, và chọn lấy dòng đầu tiên là câu trả
lời sai mà không ai nhận ra: trợ lý sẽ đọc điểm của một lớp khác rồi nói ra một
cách đầy tự tin.

Việc từ chối đoán đó là cổng đầu vào của ADR-05, và ADR-23 là nơi nó được ghi xuống.
Điều các test này pin lại là phần mà một prompt không giữ nổi: các candidate đưa ra
trong một câu hỏi làm rõ đều tới từ những dòng BE đã đọc, và một lớp thuộc về giáo
viên khác được trả lời giống y một lớp không tồn tại (ADR-22).

**Mọi phép đo ở đây đi qua `list_class`**, vì đó là bề mặt thật. Trước 06/10/2026
chúng gọi `resolve_class`, một hàm tự phân định một cái tên ra `Resolved` /
`Ambiguous` / `NotFound` và tự dựng sẵn câu hỏi lại. Hàm ấy mất caller khi việc
hỏi lại chuyển về cho model, nên nó đã xoá -- cùng ba kiểu trả về, và cùng hai luật
chỉ của riêng nó: *khớp chính xác thắng khớp chuỗi con* ("12A" giữa 12A và 12A1) và
*cách viết đúng như đã lưu thắng bản chuẩn hoá* ("12 A" so với "12A"). Cả hai là
luật xếp hạng, và `list_class` không xếp hạng: nó lọc rồi trả cả danh sách kèm số
học sinh, còn việc chọn thuộc về model (ADR-23). Giữ test cho một hàm không ai gọi
là giữ một luật đã chết -- và tệ hơn, là một luật trông như còn sống.
"""

import unicodedata

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions
from be.identity import Asking
from be.seed import seed_if_empty
from be.teacher_tools import execute
from schema.ddl import prepare_schema
from schema.models import SchoolClass, Student, Teacher


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
async def test_the_way_a_teacher_types_a_name_does_not_matter(stack) -> None:
    """Giáo viên gõ "lớp 12a", không gõ một identifier đã chuẩn hoá.

    Từ chối cách gõ đó sẽ đẩy trợ lý vào chỗ hỏi một câu mà nó đã có sẵn câu trả lời,
    và điều đó dạy giáo viên thôi tin vào câu hỏi làm rõ ngay lúc nó thật sự cần.

    Bảy cách viết, một lớp. Phép lọc của `list_class` chạy trên `normalise`, nên đây là
    nơi hàm ấy được thi hành -- không phải nơi nó được hứa.
    """
    async with stack() as session:
        asking = await _mine(session)

        for typed in ("12a", "  12A  ", "lớp 12A", "Lớp 12a", "Lớp: 12A", "lớp12A", "lớp - 12A"):
            found = await execute(session, asking, "list_class", {"name": typed})
            assert [one["name"] for one in found["candidates"]] == ["12A"], typed


@pytest.mark.asyncio
async def test_a_decomposed_name_matches_a_composed_one(stack) -> None:
    """Cùng một từ tiếng Việt viết theo hai cách Unicode vẫn là một từ.

    macOS và iOS gửi văn bản ở dạng phân rã, nên "lớp" có thể tới nơi dưới dạng "l" +
    "o" + U+031B + "p". Không chuẩn hoá dạng đó thì một giáo viên dùng Mac sẽ nhận danh
    sách rỗng cho mọi lớp họ gọi tên.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12 Văn", students=6)

        decomposed = unicodedata.normalize("NFD", "lớp 12 Văn")
        found = await execute(session, asking, "list_class", {"name": decomposed})

    assert [one["name"] for one in found["candidates"]] == ["12 Văn"]


@pytest.mark.asyncio
async def test_another_teachers_class_is_answered_as_if_it_did_not_exist(stack) -> None:
    """ADR-22, ở đây được thi hành chứ không chỉ được hứa.

    Hai câu trả lời khác nhau sẽ thành một cái máy dò: gõ hết các tên cho tới khi câu
    chữ đổi là bạn đã vẽ xong bản đồ cả trường. `11B` là lớp **thật** của một giáo viên
    khác và `9Z` không của ai cả; hai lượt gọi phải trả về **cùng một thứ**, nên không
    còn gì để mà so.

    Nơi thi hành là cái filter `teacher_id` trong `classes_with_counts` -- bỏ filter ấy
    đi thì chính test này đỏ.
    """
    async with stack() as session:
        asking = await _mine(session)

        theirs = await execute(session, asking, "list_class", {"name": "11B"})
        absent = await execute(session, asking, "list_class", {"name": "9Z"})

    assert theirs["candidates"] == []
    assert theirs == absent


@pytest.mark.asyncio
async def test_a_class_with_no_students_is_a_number_not_an_absence(stack) -> None:
    """Số học sinh bằng không là một con số, không phải một lớp bị thiếu.

    `outerjoin` cộng `count` là thứ làm chuyện này chạy được, và nó thuộc loại query âm
    thầm trả về rỗng khi viết bằng inner join — khi đó một lớp vừa mới lập sẽ biến mất
    khỏi mọi câu trả lời, tức giáo viên không phát hành được đề cho đúng cái lớp họ vừa
    tạo.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "10C", students=0)

        found = await execute(session, asking, "list_class", {"name": "10C"})

    assert [one["name"] for one in found["candidates"]] == ["10C"]
    assert found["candidates"][0]["student_count"] == 0


@pytest.mark.asyncio
async def test_list_class_hands_the_ambiguity_to_the_loop(stack) -> None:
    """Tool báo ra các candidate thay vì ném exception hay đoán.

    Vòng lặp đưa cái đó về cho model dưới dạng dữ liệu, nên câu hỏi làm rõ do trợ lý
    diễn đạt nhưng dựa trên những dòng BE đã đọc. Đó là nửa của ADR-05 không thể sống
    trong một prompt.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12A", students=7)

        result = await execute(session, asking, "list_class", {})

    # `list_class` **luôn** trả cả danh sách, và danh sách ấy CHÍNH LÀ bộ phương án:
    # khoá `candidates` là thứ `teacher_chat._choices_from` dựng nút từ đó. Trước đợt
    # này việc gỡ nhập nhằng nằm trong `find_class`, nên nó có bốn hình dạng trả về và
    # model phải đoán lần này nhận hình nào. Nay một hình, và việc chọn giữa hai lớp
    # trùng tên về đúng chỗ của nó: model hỏi giáo viên (ADR-23).
    assert [candidate["name"] for candidate in result["candidates"]] == ["12A", "12A"]
    assert sorted(candidate["student_count"] for candidate in result["candidates"]) == [3, 7]


@pytest.mark.asyncio
async def test_a_summary_refusal_points_at_the_tool_that_names_the_real_assessments(
    stack,
) -> None:
    """Một lời từ chối trống rỗng là một lời mời bịa ra.

    Đo được ở lần chạy với model thật đầu tiên: `class_assessment_summary` trả về
    `{"found": false, "reason": "không tìm thấy..."}` mà không kèm danh sách, và
    gpt-4o-mini lấp khoảng trống đó bằng "12A1, 12A2, 12B1, 12B2" — bốn lớp không tồn
    tại, nói ra với giáo viên kèm theo cả uy tín của hệ thống đứng sau.

    Câu trả lời từng là: chở danh sách đề **trong** lời từ chối. Nó hết đúng khi
    `list_assessment` ra đời — chở danh sách là hình dạng trả về thứ năm của một tool đã
    có bốn, và nó dạy model rằng cách tra đề là gọi sai tool một lần. Nay lời từ chối chỉ
    đường, và danh sách thật nằm ở tool làm đúng việc đó. Hai khẳng định dưới đây là hai
    nửa của cùng một luật: cái khe vẫn bị lấp, chỉ bằng một tool thay vì một field.
    """
    async with stack() as session:
        asking = await _mine(session)
        # Đúng đường model đi: liệt kê, lấy `class_id`, rồi gọi tool cần nó.
        listing = await execute(session, asking, "list_class", {"name": "12A"})
        class_id = listing["candidates"][0]["class_id"]

        answer = await execute(
            session,
            asking,
            "class_assessment_summary",
            {"class_id": class_id, "assessment_id": "không-phải-id-thật"},
        )
        listed = await execute(session, asking, "list_assessment", {"class_id": class_id})

    assert answer["found"] is False
    # Lời từ chối gọi tên tool chứ không chở dữ liệu: thiếu câu này, model lại phải đoán.
    assert "list_assessment" in answer["reason"]
    assert "assessments_in_this_class" not in answer

    # Đề thật, để câu hỏi tiếp theo gọi tên nó được thay vì bịa ra một cái.
    titles = [entry["title"] for entry in listed["assessments"]]
    assert titles == ["Kiểm tra 15 phút — Hàm số"]
    assert all(entry["assessment_id"] for entry in listed["assessments"])


@pytest.mark.asyncio
async def test_a_class_past_the_sixth_is_still_reachable(stack) -> None:
    """Lớp thứ bảy trở đi phải có một đường tới, không chỉ một con số thừa nhận nó tồn tại.

    Đây là một lỗi của chính đợt 06/10/2026, và nó đáng ghi lại. Bản đầu của `list_class`
    không nhận tham số nào: trả mọi lớp rồi `capped` giữ sáu. Với một giáo viên mười lớp,
    `more` nói **đúng** rằng còn bốn lớp nữa — nhưng không có đường nào lấy `class_id` của
    chúng, vì `get_class` cần một id model chưa bao giờ thấy. `find_class` trước đó khớp
    theo tên nên lớp nào cũng tra được; tách đôi tool đã bỏ mất khả năng ấy mà không ai
    nhận ra, vì `more` trông như đã xử lý xong vấn đề.

    `name` là tuỳ chọn và nó **không** đem bốn hình dạng của `find_class` quay lại: lọc rồi
    vẫn đúng `candidates` kèm `more`, và việc chọn giữa hai lớp trùng tên vẫn thuộc về model
    (ADR-23). Tool thôi *quyết*, nó chỉ *thu hẹp*.
    """
    async with stack() as session:
        asking = await _mine(session)
        # Seed đã có 12A. Thêm chín lớp nữa: mười lớp, mà một danh sách chở sáu.
        for name in ("10A", "10B", "10C", "11A", "11C", "12B", "12C", "12D", "12E"):
            await _add_class(session, asking, name, students=1)

        everything = await execute(session, asking, "list_class", {})
        narrowed = await execute(session, asking, "list_class", {"name": "12"})
        exactly = await execute(session, asking, "list_class", {"name": "12C"})
        nothing = await execute(session, asking, "list_class", {"name": "lớp nào tên này"})

    # Không lọc: sáu lớp đầu theo thứ tự tên, và bốn lớp bị bỏ lại được nói ra.
    assert len(everything["candidates"]) == 6
    assert everything["more"] == 4
    # `12C` **không** nằm trong sáu lớp ấy — đó chính là cái lỗ.
    assert "12C" not in [one["name"] for one in everything["candidates"]]

    # Lọc "12": năm lớp khối 12, vừa một danh sách, nên `more` về 0 và `12C` tới được.
    assert [one["name"] for one in narrowed["candidates"]] == ["12A", "12B", "12C", "12D", "12E"]
    assert narrowed["more"] == 0

    # Và lọc đúng một tên thì ra đúng một lớp — model lấy `class_id` rồi gọi `get_class`.
    assert [one["name"] for one in exactly["candidates"]] == ["12C"]
    assert exactly["candidates"][0]["class_id"]

    # Lọc không khớp gì thì rỗng, **không** phải "khớp tất cả". `normalise` trả rỗng cho một
    # chuỗi không mang tên nào, và coi rỗng là khớp-tất-cả sẽ làm một cái tên gõ sai đọc ra
    # y như không lọc gì — tức giáo viên tưởng mình đã thu hẹp trong khi chưa.
    assert nothing["candidates"] == []
