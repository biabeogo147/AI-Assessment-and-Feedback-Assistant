"""Trợ lý của giáo viên được làm những gì, và ai là người kiểm.

Hai tầng, và chuyện tầng nào là tầng chịu lực thì rất quan trọng.

`catalog_for` quyết định một giáo viên được *kể* về những gì, nên một tool họ không
được dùng thì không bao giờ được mô tả cho model. `execute` sau đó phân phối theo
tên, từ chối mọi thứ không có trong bảng. Nhưng **không cái nào trong hai cái đó là
thứ giữ giáo viên này ở ngoài dữ liệu của giáo viên khác.** Mọi tool trong phiên bản
này đều được đưa cho mọi giáo viên, nên cái check catalog bên trong `execute` hiện
là một phép thử không thể đỏ được; nó ở đó để dành cho tool đầu tiên không dành cho
tất cả.

Tầng làm việc thật nằm bên trong từng tool: mọi query đều filter theo
`asking.teacher_id` (ADR-22). Đó là chỗ phải xem khi review một tool mới, và một
tool bỏ qua chỗ đó thì không được bất cứ thứ gì ở trên bảo vệ -- và đó là lý do các
tool được trao sẵn một `Asking` chứ không tự với tay đi lấy identity.

Có vài tool ở đây ghi dữ liệu. Đó không phải là nới lỏng ADR-05: đường biên của
ADR-05 nói về những hành động **không lấy lại được**, còn mở một đề nháp hay điền
câu hỏi vào nó là chuyện đảo lại được khi đề chưa duyệt. Thứ mà không tool nào làm
là thả phần việc đó ra cho học sinh -- duyệt (ADR-01) và phát hành (ADR-02) là việc
của giáo viên, qua panel và qua form phát hành, và `tools/check_contract.py` từ chối
file này nếu nó với tay vào vòng đời dù chỉ một chút.

Hai luật mà mọi tool đều tuân theo:

- **Luôn luôn giới hạn theo chủ sở hữu.** Mọi query đều filter theo `teacher_id`
  (ADR-22). Một tool nhận vào một id rồi tin ngay sẽ làm cho catalog trở thành thứ
  duy nhất đứng giữa giáo viên này và điểm của lớp giáo viên khác.
- **Trả về một bản tóm tắt, không trả về các row.** "Lớp 11B làm thế nào" là bốn
  mươi học sinh nhân mười câu hỏi. Gộp số ngay ở đây giữ cho prompt nhỏ, và giữ kết
  quả của cả một lớp ở ngoài một payload đang đi sang một service không giữ
  credential nào của database.
"""

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from be.assessment_state import AssessmentState
from be.config import Settings, get_settings
from be.content_reader import ContentUnavailable, get_reader
from be.drafting import (
    _MOST_QUESTIONS,
    drop_failed_slots_of_empty,
    fire,
    harvest,
    pending_count,
    rebrief,
    replace,
    too_many,
    why_not_erasable,
)
from be.identity import Asking
from be.outline import MOST_QUESTIONS_ASKED
from be.resolve import Candidate, capped, classes_with_counts, normalise
from be.titles import clipped, default_title
from be.toc import heading, parts, scope_of, title_path
from contracts import DocumentState, IndexNode, PlanStep, ToolSpec
from schema.models import (
    Assessment,
    Attempt,
    Document,
    DraftBrief,
    Publication,
    Question,
    QuestionOutcome,
    SchoolClass,
    Student,
    TeacherTurn,
)

logger = logging.getLogger(__name__)


class UnknownTool(Exception):
    """Một đề xuất đã gọi tên một tool không tồn tại, hoặc không phải của giáo viên này.

    Được raise lên chứ không trả về, để vòng lặp không nhầm nó thành một tool đã chạy
    và không tìm thấy gì. Vòng lặp biến nó thành một kết quả mà model đọc được và hồi
    lại được, và đó là chuyện khác với một lần tra cứu thành công nhưng trả về rỗng.
    """


def _shown(candidate: Candidate) -> dict:
    """Dựng một lớp candidate ra để model đọc.

    Số học sinh đi kèm với tên lớp, vì một câu hỏi lại đưa ra "12A" và "12A" là câu
    hỏi mà giáo viên không trả lời được. Nó là mẩu thông tin nhỏ nhất phân biệt được
    hai lớp cùng một tên.

    Args:
        candidate: Một lớp giáo viên này sở hữu.

    Returns:
        id, tên và số học sinh của lớp đó.
    """
    return {
        "class_id": candidate.class_id,
        "name": candidate.name,
        "student_count": candidate.student_count,
    }


@dataclass(frozen=True)
class Running:
    """Những gì một lần gọi tool có để làm việc.

    Một object nhỏ chứ không phải một danh sách tham số dài hơn, vì các tool ghi cần
    tới queue còn các tool đọc thì không được chạm vào nó -- và một tool đọc mà được
    trao sẵn một pool thì chỉ cách việc đẩy một thứ gì vào queue đúng một lần
    refactor.

    Attributes:
        session: Session của database.
        asking: Ai đang hỏi. Mọi query đều filter theo `asking.teacher_id`.
        pool: Pool của arq, hoặc None khi không với tới được queue. Chỉ các tool ghi
            đọc nó.
        settings: Settings của process, cung cấp tên queue.
        outline: Dàn ý giáo viên đã xem mà bước này soạn theo (ADR-29, `draft-outline`) -- chính
            `tool_result` của lượt dàn ý, do cổng duyệt của vòng lượt tìm ra. `None` khi lượt
            không có dàn ý nào hợp lệ; tool soạn câu từ chối khi ấy.
        conversation_id: Đoạn chat đang chạy lượt này. `create_draft` dùng lại đề trống của chính
            đoạn ấy thay vì mở đề trống thứ hai (plan `wave-3-draft-panel`, việc 15). `None` ở các
            đường gọi không thuộc đoạn chat nào (test, công cụ).
    """

    session: AsyncSession
    asking: Asking
    pool: object
    settings: Settings
    outline: dict | None = None
    conversation_id: str | None = None


@dataclass(frozen=True)
class Tool:
    """Một tool: nó được mô tả cho model thế nào, và nó chạy cái gì.

    Attributes:
        spec: Thứ model đọc. `spec.name` là thứ vòng lặp dựa vào để phân phối.
        run: Nhận context đang chạy và các tham số. Identity nằm trong context đó chứ
            không phải được đọc ở bên trong, nên không có đường nào để một tool chạy
            mà không biết nó được chạm vào dữ liệu của ai.
        writes: True khi tool đổi một thứ gì đó. **Đây là ranh giới pha của ADR-25**:
            `catalog_for` chia hai pha theo đúng cờ này, nên lật nó là đổi pha của tool
            chứ không phải sửa một dòng metadata. Một tool ghi lọt vào pha lên plan là
            một câu hỏi lại có thể bỏ lại việc đã làm dở.
    """

    spec: ToolSpec
    run: Callable[[Running, dict], Awaitable[dict]]
    writes: bool = False


async def _list_class(running: Running, args: dict) -> dict:
    """Mọi lớp của giáo viên này.

    **Một hình dạng trả về, không bốn.** Tool trước (`find_class`) nhận một cái tên rồi
    trả về một trong bốn hình: lớp đã tìm thấy, `ambiguous` kèm candidate, không-tìm-thấy
    kèm danh sách, và một lời từ chối khi không có tên nào. Model phải đoán lần này nhận
    hình nào, và ba trong bốn hình đều là *"đây là danh sách, tự chọn đi"* -- tức chính
    cái việc tool này làm thẳng.

    Việc chọn giữa hai lớp trùng tên nay về đúng chỗ của nó: model đọc danh sách rồi hỏi
    giáo viên (ADR-23), thay vì tool vừa tra vừa tự dựng một câu hỏi lại.

    **`name` là tuỳ chọn, và nó ở đây vì một lỗi đo được.** Bản đầu không nhận tham số nào:
    tool trả mọi lớp rồi `capped` giữ sáu. Với một giáo viên có mười lớp, lớp thứ bảy trở đi
    thành **không với tới được** -- `more` nói đúng rằng còn ba lớp nữa, nhưng không có đường
    nào lấy id của chúng, vì `get_class` cần một id model chưa bao giờ thấy. `more` khi đó là
    một lời thừa nhận, không phải một đường ra.

    Lọc theo tên **không** đem bốn hình dạng của `find_class` quay lại: lọc rồi vẫn trả đúng
    `candidates` kèm `more`, và việc chọn giữa hai lớp trùng tên vẫn thuộc về model (ADR-23).
    Khác biệt là tool thôi *quyết*, chỉ *thu hẹp*.

    Args:
        running: Session và giáo viên đang hỏi.
        args: `name` tuỳ chọn -- một phần tên lớp để thu hẹp danh sách. Không có thì liệt kê
            mọi lớp.

    Returns:
        `candidates`: mỗi lớp một dòng với `class_id`, `name`, `student_count`. Cộng `more`:
        đã bỏ lại bao nhiêu lớp vì danh sách chỉ chở sáu. `more` là **một nửa hợp đồng**,
        không phải một con số trang trí — `_offered` đọc nó để nói ra rằng danh sách chưa
        đầy đủ, và prompt pha 1 dặn model gọi lại tool với `name` để thu hẹp. Luôn trả nó,
        kể cả khi bằng 0.

        **Khoá tên là `candidates`, không phải `classes`, và đó là một hợp đồng chứ không
        phải một lựa chọn chữ nghĩa.** `teacher_chat._choices_from` dựng các nút của một
        câu hỏi lại **chỉ** từ khoá ấy — đó là cách ADR-23 giữ cho *model viết câu hỏi,
        BE viết các câu trả lời*, nên không một chuỗi nào trên nút đi qua tay model. Đổi
        tên khoá này là bỏ các nút đi, và câu hỏi lại tụt về một bong bóng chữ.

        Danh sách này **là** bộ phương án: model gọi tool này đúng lúc nó cần giáo viên
        chọn một lớp. Khác với một danh sách "không tìm thấy, đây là những lớp bạn có",
        vốn chỉ là context để nhắc tới.
    """
    # `classes_with_counts` đếm học sinh trong **một** query và lọc theo `teacher_id` --
    # cái filter ấy chính là toàn bộ ADR-22 ở đây. Nó cũng sắp theo name rồi id, nên hai
    # lớp cùng tên lần nào cũng về theo cùng thứ tự.
    found = await classes_with_counts(running.session, running.asking)

    # `normalise` trả rỗng khi không có tên nào, và caller **không được** coi rỗng là "khớp
    # tất cả" -- docstring của nó nói thẳng điều đó. Ở đây rỗng nghĩa là không lọc, và hai
    # việc ấy tình cờ cùng một kết quả; viết tách ra để cái tình cờ không thành một luật.
    narrowing = normalise(str(args.get("name") or ""))
    if narrowing:
        found = [one for one in found if narrowing in normalise(one.name)]
    # `capped` cắt danh sách xuống mức một câu hỏi lại chở được, và nói ra đã bỏ lại bao
    # nhiêu. Trả hết ba mươi lớp rồi báo `more: 0` là nói sai: giao diện chỉ vẽ sáu nút,
    # nên hai mươi bốn lớp kia mất đi mà không dòng nào trên màn hình nhắc tới chúng.
    kept, more = capped(found)
    return {"candidates": [_shown(candidate) for candidate in kept], "more": more}


async def _get_class(running: Running, args: dict) -> dict:
    """Thông tin một lớp, theo `class_id`.

    Nhận **id**, không nhận tên: tên là thứ nhập nhằng, và việc gỡ nhập nhằng đã chuyển
    lên `list_class`. Một tool nhận id thì chỉ có hai kết cục, và cả hai đều đọc được.

    Args:
        running: Session và giáo viên đang hỏi.
        args: `class_id`.

    Returns:
        `found` kèm `class_id`, `name`, `student_count`; hoặc `found: False` kèm `reason`.
    """
    wanted = str(args.get("class_id") or "").strip()
    if not wanted:
        return {
            "found": False,
            "reason": "thiếu class_id; gọi list_class để lấy id trước",
            "said": _SAID_NO_CLASS,
        }

    # Lọc ngay trong danh sách đã thuộc về giáo viên này, nên một id của người khác đọc
    # ra **giống hệt** một id không tồn tại (ADR-22).
    for candidate in await classes_with_counts(running.session, running.asking):
        if candidate.class_id == wanted:
            return {"found": True, **_shown(candidate)}
    return {"found": False, "reason": "không có lớp nào như vậy trong danh sách của bạn"}


async def _list_assessment(running: Running, args: dict) -> dict:
    """Những đề đã phát hành cho một lớp.

    **Đề thuộc về giáo viên, không thuộc về lớp** -- `assessments` có `teacher_id` chứ
    không có `class_id`. Lớp nối vào qua `publications`, nên "đề của một lớp" nghĩa là đề
    đã phát hành cho lớp ấy, và một đề nháp chưa phát hành thì không thuộc lớp nào.

    Args:
        running: Session và giáo viên đang hỏi.
        args: `class_id`.

    Returns:
        `assessments`: mỗi đề một dòng với `assessment_id` và `title`, mới nhất trước.
    """
    wanted = str(args.get("class_id") or "").strip()
    if not wanted:
        return {
            "found": False,
            "reason": "thiếu class_id; gọi list_class để lấy id trước",
            "said": _SAID_NO_CLASS,
        }

    listed = await _assessments_of(running.session, running.asking, wanted)
    return {"found": True, "assessments": listed}


async def _assessments_of(session: AsyncSession, asking: Asking, class_id: str) -> list[dict]:
    """Liệt kê những đề giáo viên này đã phát hành cho một lớp.

    Args:
        session: Session của database.
        asking: Đề của ai. Cả lớp và đề đều được filter theo cái này, nên một class_id
            của người khác sẽ liệt kê ra không gì cả thay vì liệt kê đề của họ.
        class_id: Lớp nào.

    Returns:
        Tên và id của từng đề, mới nhất trước. Rỗng khi lớp đó không phải của giáo viên
        này, và đó cũng chính là câu trả lời cho một lớp không có đề nào -- ADR-22 giữ
        cho hai trường hợp đó không phân biệt được với nhau.
    """
    listed = await session.execute(
        select(Assessment.id, Assessment.title)
        .join(Publication, Publication.assessment_id == Assessment.id)
        .join(SchoolClass, SchoolClass.id == Publication.class_id)
        .where(
            Publication.class_id == class_id,
            # Bản đã thu hồi không còn là đề của lớp (ADR-02, thu hồi mềm): liệt kê nó thì lớp
            # vừa hoàn tác rồi phát hành lại thấy hai đề cùng tên (thử tay case 10/11).
            Publication.recalled_at.is_(None),
            SchoolClass.teacher_id == asking.teacher_id,
            Assessment.teacher_id == asking.teacher_id,
        )
        .order_by(Assessment.created_at.desc())
    )
    return [{"assessment_id": found, "title": title} for found, title in listed.all()]


async def _class_assessment_summary(running: Running, args: dict) -> dict:
    """Tóm tắt một lớp đã làm một đề như thế nào.

    Các con số đếm được, không phải các row: bao nhiêu em đã nộp, trung bình tổng điểm
    của các em **kèm theo thang mà nó tính trên**, và còn bao nhiêu câu hỏi chưa xong.
    Một giáo viên hỏi "các em làm thế nào" là muốn mấy con số đó, còn bốn mươi row điểm
    thì không vừa prompt mà cũng không vừa một câu trả lời.

    Thang điểm đi kèm trung bình là có chủ đích. Điểm tính theo từng câu và chạy 0 /
    0,5 / 1, nên trung bình 3,4 nghĩa là 3,4 trên tổng số câu hỏi có trong đề -- và một
    con số như thế, đưa ra một mình, thì với mọi giáo viên trong cả nước đọc lên là 3,4
    trên thang 10.

    Args:
        running: Session và giáo viên đang hỏi. Cả lớp và đề đều phải là của họ.
        args: `class_id` và `assessment_id`.

    Returns:
        Bản tóm tắt, hoặc một câu trả lời không-tìm-thấy khi một trong hai id không phải
        của giáo viên này.
    """
    session, asking = running.session, running.asking
    class_id = str(args.get("class_id", ""))
    assessment_id = str(args.get("assessment_id", ""))

    owns_class = await session.scalar(
        select(SchoolClass.id).where(
            SchoolClass.id == class_id, SchoolClass.teacher_id == asking.teacher_id
        )
    )
    assessment = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    if owns_class is None or assessment is None:
        # Lời từ chối nay **không** mang theo danh sách đề. Nó từng mang, vì không có gì
        # trong catalog nói cho model biết nên hỏi về đề nào -- đo ở lần chạy đầu với
        # gpt-4o-mini: một câu không-tìm-thấy trơ trọi khiến nó gọi tên bốn lớp không tồn
        # tại. Cái khe ấy nay có một tool đứng chắn: `list_assessment`. Chở danh sách trong
        # một lời từ chối là hình dạng trả về thứ năm của tool này, và nó dạy model rằng
        # cách tra đề là gọi sai tool một lần.
        return {
            "found": False,
            "reason": (
                "không tìm thấy lớp hoặc đề trong danh sách của bạn; "
                "hãy gọi list_assessment với class_id để lấy đúng assessment_id"
            ),
            "said": "không tìm thấy lớp hoặc đề ấy trong danh sách của bạn",
        }

    publication = await session.scalar(
        select(Publication).where(
            Publication.assessment_id == assessment_id, Publication.class_id == class_id
        )
    )
    if publication is None:
        return {"found": False, "reason": "đề này chưa phát hành cho lớp đó"}
    if publication.recalled_at is not None:
        # Cửa sổ thu hồi của ADR-02. Một đề đã thu hồi đọc lên y như một đề bình
        # thường nếu không nói ra điều này, và một giáo viên đã thu hồi một đề rồi hỏi
        # đề đó làm thế nào sẽ được kể về những bài làm không còn tính nữa.
        return {
            "found": True,
            "assessment_title": assessment.title,
            "recalled": True,
            "note": "đề này đã bị thu hồi",
        }

    # Một bài làm gắn với một học sinh, không gắn với một lớp, nên cái filter theo lớp
    # phải đi qua danh sách học sinh. Filter theo các học sinh của lớp này chứ không
    # theo mọi bài làm của đề chính là thứ giữ cho bản tóm tắt của một lớp không lặng
    # lẽ bao gồm cả lớp khác.
    # `Student.class_id` là lớp của học sinh *ở hiện tại*. Một học sinh đã chuyển lớp
    # thì mang theo các bài làm cũ của mình, nên chỗ này đếm chúng vào lớp mới. Sai, và
    # không phải do chỗ này sinh ra -- nhưng đây là caller đầu tiên bị nó ảnh hưởng,
    # nên người sau đọc một bản tóm tắt lạ sẽ có chỗ để bắt đầu.
    #
    # Chỉ tính các bài đã nộp. Một bài còn đang làm thì chưa có row `QuestionOutcome`
    # nào -- chúng được tạo lúc nộp -- nên đếm nó vào thì không thêm gì vào tổng mà
    # thêm một vào số chia, lặng lẽ kéo điểm trung bình xuống trong khi một học sinh
    # vẫn đang gõ.
    attempts = (
        await session.scalars(
            select(Attempt)
            .join(Student, Student.id == Attempt.student_id)
            .where(
                Attempt.assessment_id == assessment_id,
                Student.class_id == class_id,
                Attempt.submitted_at.is_not(None),
            )
        )
    ).all()
    counting = (
        select(func.count()).select_from(Question).where(Question.assessment_id == assessment_id)
    )
    question_count = await session.scalar(counting) or 0
    if not attempts:
        return {
            "found": True,
            "assessment_title": assessment.title,
            "question_count": question_count,
            "submitted_count": 0,
            "note": "chưa có học sinh nào nộp bài",
        }

    ids = [attempt.id for attempt in attempts]
    marks = (
        await session.scalars(select(QuestionOutcome).where(QuestionOutcome.attempt_id.in_(ids)))
    ).all()
    wrong_still_open = sum(1 for mark in marks if mark.mark == 0 and not mark.closed)
    total = sum(mark.mark for mark in marks)

    # Điểm tính theo từng câu và chạy 0 / 0,5 / 1 (ADR-16), nên tổng điểm của một bài
    # làm là trên thang `question_count` chứ không phải trên thang mười. Chính sự phân
    # biệt đó là toàn bộ lý do cả hai con số đều được trả về và field này không được gọi
    # là "điểm trung bình": một giáo viên Việt Nam đọc một con 3,4 trơ trọi thành 3,4/10
    # rồi kết luận cả lớp trượt, trong khi 3,4 trên 5 là 68%.
    average = round(total / len(attempts), 2)
    return {
        "found": True,
        "assessment_title": assessment.title,
        "question_count": question_count,
        "submitted_count": len(attempts),
        "average_total_marks": average,
        "average_out_of": question_count,
        "average_percent": round(100 * average / question_count) if question_count else None,
        "questions_still_open": wrong_still_open,
    }


# Những thứ mà thiếu chúng thì không mở được một đề nháp. Không phải sở thích -- các
# câu hỏi do những job độc lập soạn ra, nên một brief còn đang ghép dở sẽ cho ra một bộ
# đề mà hai nửa trả lời hai câu hỏi khác nhau, và đó là loại lỗi không ai tìm ra bằng
# cách đọc từng câu hỏi một.
# Ba muc, khong bon. `question_count` roi khoi day cung luc no roi khoi `create_draft`:
# mot de trong chua co so cau nao de khai.
_BRIEF_FIELDS = ("subject", "grade", "topic_scope")

# Mỗi field văn bản tự do dài được bao nhiêu, lấy từ chính các cột lưu nó:
# `Assessment.subject` và `DraftBrief.difficulty` là String(64) còn `Assessment.grade`
# là String(16). Model là thứ ghi những field này, nên chúng đến đây đúng như lời giáo
# viên nói -- và `String(n)` không được thi hành trên SQLite, nên một bộ test không phát
# hiện ra chuyện này giúp chúng ta được.
_FIELD_CAPS = {"subject": 64, "grade": 16, "difficulty": 64}
# Tên mỗi trường trên màn hình giáo viên (`said`, plan `backlog-tier-1`).
_FIELD_SAID = {"subject": "môn", "grade": "khối", "difficulty": "độ khó"}

# Nói y một câu cho một đề nháp không có ở đó và một đề nháp của người khác (ADR-22).
_NO_SUCH_DRAFT = {
    "started": False,
    "reason": "không có đề nháp nào như vậy trong danh sách của bạn",
}


async def _create_draft(running: Running, args: dict) -> dict:
    """Mở một đề nháp trống, khi brief đã đủ.

    Từ chối một brief còn thiếu và gọi tên những field đang thiếu. Lời từ chối đó là cơ
    chế đứng sau câu "thu thập context trước đã": một model được dặn phải hỏi trước khi
    soạn thì có thể quên, còn một tool không chịu chạy khi thiếu field thì không thể bị
    quên. Gọi tên chúng ra chính là thứ cho phép trợ lý hỏi một câu có ích thay vì nhiều
    câu mơ hồ.

    Không có gì được đẩy vào queue ở đây. Mở đề nháp và điền nó là hai bước riêng, nên
    brief đọc được -- bởi giáo viên, trong panel -- trước khi tiêu một lượt gọi model
    nào vào nó.

    Args:
        running: Session và giáo viên đang hỏi, người sẽ thành tác giả.
        args: `subject`, `grade`, `topic_scope`, và tuỳ chọn thêm `difficulty` cùng
            `title`.

    Returns:
        id của đề nháp mới, hoặc một lời từ chối gọi tên những gì brief còn thiếu.

    Side effects:
        Ghi một `Assessment` ở state empty cùng `DraftBrief` của nó.
    """
    session, asking = running.session, running.asking

    missing = [field for field in _BRIEF_FIELDS if not str(args.get(field) or "").strip()]
    if missing:
        return {
            "created": False,
            "missing": missing,
            "reason": "chưa đủ thông tin để soạn đề; hãy hỏi giáo viên những mục còn thiếu",
            "said": "chưa đủ thông tin để soạn đề",
        }

    # **Không có số câu ở đây, và không có mức trần ở đây.** Một đề trống chưa có số câu
    # nào để khai: con số ấy chỉ có nghĩa lúc bắt đầu soạn, và nó đổi được -- soạn 3 câu
    # rồi soạn thêm 2 là chuyện thường. Bắt khai trước buộc giáo viên quyết một con số
    # trước khi biết đề sẽ dài bao nhiêu, và làm tool này từ chối một việc không phải
    # của nó. Mức trần nay thuộc về `start_drafting`, nơi con số thật sự được tiêu.
    #
    # Độ dài lấy từ chính các cột, và câu trả lời là một lời từ chối chứ không phải một
    # lần cắt ngắn lặng lẽ: một `grade` bị cắt là dữ liệu sai nhưng trông như dữ liệu.
    # Bộ test chạy trên SQLite, nơi `String(n)` không có tác dụng gì, nên không dòng nào
    # dưới đây đỏ lên cho đến khi một giáo viên gặp Postgres -- và đó đúng là việc mà
    # "lớp 12 ban khoa học tự nhiên" làm với một cột 16 ký tự.
    too_long = [
        field for field, cap in _FIELD_CAPS.items() if len(str(args.get(field) or "")) > cap
    ]
    if too_long:
        return {
            "created": False,
            "missing": [],
            "too_long": too_long,
            "reason": (
                "mấy mục này dài quá mức lưu được: "
                + ", ".join(f"{field} tối đa {_FIELD_CAPS[field]} ký tự" for field in too_long)
            ),
            "said": "mấy mục này dài quá mức lưu được: "
            + ", ".join(
                f"{_FIELD_SAID[field]} tối đa {_FIELD_CAPS[field]} ký tự" for field in too_long
            ),
        }

    document_id, scope_nodes, built_at, refused = await _document_scope(running, args)
    if refused is not None:
        return refused

    scope = str(args["topic_scope"]).strip()
    # Đề theo sách mang tên tệp sách (ADR-31): phạm vi của nó là cả chuỗi nhãn bài kèm số trang.
    book = await session.get(Document, document_id) if document_id else None
    fallback = default_title(scope, book.filename if book is not None else "")
    invented = clipped(str(args["title"])) if str(args.get("title") or "").strip() else ""
    # Một cái tên mà giáo viên đổi lại được sau, nên tự suy ra một cái thì không tốn gì mà lại tiết
    # kiệm được một vòng hỏi đáp về chuyện hình thức. Cắt ngắn chứ không từ chối, cũng vì đúng lý do
    # đó -- tối đa 60 ký tự (ADR-31). Tên model gửi mà dọn xong rỗng (chỉ có cặp ngoặc `""`) thì lùi
    # về tên tự đặt: một đề tên rỗng là thẻ *Đã tạo đề ""* (review code 17/10, plan
    # `backlog-tier-1`).
    title = invented if invented and book is None else fallback

    # Đoạn chat đã có một đề trống thì dùng lại đề ấy, không mở đề trống thứ hai (người dùng chốt
    # 18/10/2026, plan `wave-3-draft-panel`, việc 15): hai đề trống trong một đoạn chat là hai thẻ
    # *Đã tạo đề* cho một việc, và đề trống nào cũng phải đi xoá tay.
    draft = await _empty_draft_of(running)
    reused = draft is not None
    if draft is None:
        draft = Assessment(
            teacher_id=asking.teacher_id,
            title=title,
            subject=str(args["subject"]).strip(),
            grade=str(args["grade"]).strip(),
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(draft)
        await session.flush()
    else:
        draft.title = title
        draft.subject = str(args["subject"]).strip()
        draft.grade = str(args["grade"]).strip()
        # Dàn ý và ô hỏng của lần trước không theo sang yêu cầu mới: lần soạn sau đánh số từ 1, và
        # `rebrief` thay phần còn lại của brief.
        await drop_failed_slots_of_empty(session, draft.id)
        old = await session.get(DraftBrief, draft.id)
        if old is not None:
            old.outline = []

    # `question_count=0`: đề vừa mở thì chưa ai xin câu nào. `start_drafting` ghi đè con số
    # thật khi giáo viên nói rõ muốn bao nhiêu.
    await rebrief(
        session,
        draft.id,
        topic_scope=scope,
        question_count=0,
        difficulty=str(args.get("difficulty") or "").strip(),
        document_id=document_id,
        scope_nodes=scope_nodes,
        index_built_at=built_at,
    )

    logger.info(
        "teacher %s %s draft %s", asking.teacher_code, "reused" if reused else "opened", draft.id
    )
    return {
        "created": True,
        "assessment_id": draft.id,
        "title": draft.title,
        **({"reused": True} if reused else {}),
    }


async def _empty_draft_of(running: Running) -> Assessment | None:
    """Đề trống mới nhất của đoạn chat đang chạy, nếu có (việc 15, plan `wave-3-draft-panel`).

    Tìm qua các bước `create_draft` của **chính đoạn ấy** (`entity_kind/entity_id`, cùng dữ liệu mà
    `conversation_of` đọc) -- chỉ bước tạo đề, để một bước tra cứu có nhắc tới một đề không kéo đề
    ấy vào đoạn này --, chỉ đề của giáo viên đang hỏi, và chỉ đề còn xoá được theo
    `why_not_erasable`: một đề đã có câu hay đang soạn thì không còn là đề trống để ghi đè.

    Đề được chọn bị **khoá hàng** rồi kiểm lại: một lần xoá từ panel chen vào giữa lúc chọn và lúc
    ghi thì lượt này mở đề mới thay vì ghi lên một hàng vừa mất (review pha 4).

    Args:
        running: Lượt đang chạy; `conversation_id` rỗng thì không có gì để dùng lại.

    Returns:
        Đề trống ấy, hay `None`.
    """
    if not running.conversation_id:
        return None
    session = running.session
    candidates = list(
        await session.scalars(
            select(Assessment)
            .join(TeacherTurn, TeacherTurn.entity_id == Assessment.id)
            .where(
                TeacherTurn.conversation_id == running.conversation_id,
                TeacherTurn.tool_name == "create_draft",
                TeacherTurn.entity_kind == "assessment",
                Assessment.teacher_id == running.asking.teacher_id,
                Assessment.state == AssessmentState.EMPTY,
            )
            .order_by(Assessment.created_at.desc(), Assessment.id)
            .distinct()
        )
    )
    for one in candidates:
        locked = await session.scalar(
            select(Assessment)
            .where(Assessment.id == one.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked is not None and not await why_not_erasable(session, locked):
            return locked
    return None


async def _start_drafting(running: Running, args: dict) -> dict:
    """Đẩy vào queue một job cho mỗi câu hỏi mà brief của một đề nháp yêu cầu.

    Từ chối khi còn có thứ gì đang chạy. Hai vòng gối lên nhau đúng là cái sự cố mà
    brief được lưu lại sinh ra để ngăn -- những câu hỏi soạn theo hai bộ hướng dẫn cùng
    nằm chung một đề -- và từ chối thì rẻ hơn là đi hoà giải.

    **Số câu đi vào đây, không vào `create_draft`.** Một đề trống chưa có số câu nào để
    khai; con số ấy chỉ có nghĩa lúc bắt đầu soạn. Và mức trần sống ở đây vì đây là chỗ
    con số thật sự được tiêu -- mỗi câu một job, mỗi job một lượt gọi model.

    Args:
        running: Session, giáo viên đang hỏi, và queue.
        args: `assessment_id` và `question_count`.

    Returns:
        Đã đẩy bao nhiêu job vào queue, hoặc một lời từ chối. Lời từ chối cho đề nháp
        của giáo viên khác đọc lên y như lời từ chối cho một đề nháp không tồn tại
        (ADR-22).

    Side effects:
        Ghi các job lên queue và một row `DraftItem` cho mỗi job.
    """
    session, asking = running.session, running.asking
    assessment_id = str(args.get("assessment_id") or "")

    owned = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    if owned is None:
        return dict(_NO_SUCH_DRAFT)

    # ADR-29: không soạn câu nào giáo viên chưa thấy dàn ý. Cổng chính ở vòng lượt
    # (`teacher_chat._shown_outline`); dòng này giữ luật ở chính tool, cho mọi đường gọi.
    if running.outline is None:
        return {
            "started": False,
            "reason": "chưa có dàn ý nào giáo viên đã xem cho lần soạn này; nêu dàn ý trước",
            "said": "Kriky chưa nêu dàn ý cho lần soạn này",
        }
    if args.get("question_count") in (None, ""):
        # Số câu là tổng của dàn ý đã xem -- BE biết, không phải đoán.
        args = {**args, "question_count": str(running.outline.get("total") or "")}

    try:
        wanted = int(str(args.get("question_count") or "").strip())
    except (TypeError, ValueError):
        # Không giống thiếu field. Báo "chưa đủ thông tin" cho một field model đã điền
        # rồi là đẩy nó đi một vòng để điền lại đúng giá trị đó.
        #
        # `unreadable` là cờ cho người kể, không phải cho model: `_said_about` đọc nó để
        # nói "một mục trong yêu cầu chưa dùng được" mà không in `reason` ra màn hình --
        # `reason` chở theo tên field, và tên field là mặt trong của hệ thống.
        return {
            "started": False,
            "unreadable": ["question_count"],
            "reason": "question_count phải là một con số, ví dụ 10",
            "said": "số câu Kriky gửi không đọc được",
        }

    if not 1 <= wanted <= _MOST_QUESTIONS:
        return {"started": False, "reason": f"số câu phải từ 1 đến {_MOST_QUESTIONS}"}
    if wanted != running.outline.get("total"):
        # Cổng của vòng lượt đã so điều này; dòng này giữ luật cho mọi đường gọi khác.
        return {
            "started": False,
            "reason": f"dàn ý đã xem có {running.outline.get('total')} câu, không phải {wanted}",
        }

    # Thu về trước đã. Không có gì khác trong BE đi thu những job này, nên một vòng đã
    # xong trong lúc không ai để ý thì vẫn đọc ra là đang chạy -- và lời từ chối bên
    # dưới khi đó sẽ là vĩnh viễn: đề nháp đó không bao giờ soạn tiếp được nữa.
    await harvest(session, running.pool, running.settings, assessment_id)

    if await pending_count(session, assessment_id):
        return {
            "started": False,
            "reason": "đề này đang soạn dở; chờ xong rồi hãy soạn thêm",
        }

    # Hỏi **sau** `harvest`, vì chỉ lúc này số câu đã có mới là số thật. Và hỏi ở đây chứ
    # không để `fire` tự canh: `fire` canh đúng nhưng chỉ `return 0`, mà caller dịch 0
    # thành "hàng đợi đang hỏng" -- một lời từ chối nêu nguyên nhân không có thật.
    overflowing = await too_many(session, assessment_id, wanted)
    if overflowing:
        return {"started": False, "reason": overflowing}

    try:
        queued = await fire(
            session, running.pool, running.settings, assessment_id, wanted, running.outline
        )
    except HTTPException:
        # `fire` gọi `assert_editable`, nên một đề đã duyệt sẽ rơi vào đây. ADR-01 khoá
        # nội dung ở lúc duyệt, và chính cái khoá đó là lý do việc duyệt có nghĩa.
        #
        # Có chủ đích không dùng `refused.detail`. Câu đó kết thúc bằng "muốn sửa thì bỏ
        # duyệt trước", viết cho một giáo viên đang đọc màn hình -- còn prompt thì dặn
        # model thuật lại lý do, nên trợ lý sẽ ngỏ lời bỏ duyệt giúp. Nó không có tool
        # nào để làm việc đó, và cái check trong `tools/check_contract.py` ở đó để giữ
        # nguyên tình trạng ấy, nên thuật lại câu đó là biến một lời từ chối đúng đắn
        # thành một lời hứa không ai giữ được.
        return {
            "started": False,
            "reason": "đề này đã duyệt nên nội dung đã khoá; việc bỏ duyệt làm ở panel bên phải",
        }

    if not queued:
        return {
            "started": False,
            "reason": "chưa soạn được câu nào; có thể đề chưa có brief, hoặc hàng đợi đang hỏng",
            "said": "chưa soạn được câu nào; bạn thử lại sau ít phút",
        }
    # `title` đi theo vì **thẻ kết quả đọc nó**. Một thẻ `Đã tạo đề` trần không nói đề nào,
    # và nó là cửa duy nhất vào panel của chính cái đề ấy -- giáo viên bấm vào một cái tên
    # họ không đọc được. `create_draft` đã trả `title` từ đầu; bước này thì không, nên thẻ
    # của một plan hai bước mất tên trong khi thẻ của một plan một bước thì có.
    return {
        "started": True,
        "queued": queued,
        "assessment_id": assessment_id,
        "title": owned.title,
        # Dàn ý nào đã thành câu: cổng duyệt đọc nó để một dàn ý chỉ được dùng một lần.
        "outline_version": running.outline.get("version"),
    }


async def _replace_question(running: Running, args: dict) -> dict:
    """Soạn lại đúng một câu của đề nháp theo dàn ý giáo viên vừa duyệt (ADR-29).

    Câu cũ ở lại cho tới khi câu mới qua ADR-18 (`drafting.replace`, `harvest`), nên một job hỏng
    không để lại một ô trống. Bản ngân hàng của câu cũ theo luật xoá của ADR-28: ở lại.

    Args:
        running: Session, giáo viên đang hỏi, queue, và dàn ý đã xem (`Running.outline`).
        args: `assessment_id`, `question_number`.

    Returns:
        `started` cùng `queued`, `assessment_id`, `title`, `outline_version`, `question_number`;
        hoặc một lời từ chối.
    """
    session, asking = running.session, running.asking
    assessment_id = str(args.get("assessment_id") or "")
    owned = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    if owned is None:
        return dict(_NO_SUCH_DRAFT)
    if running.outline is None or running.outline.get("for") != "replace":
        return {
            "started": False,
            "reason": "chưa có dàn ý thay câu nào giáo viên đã xem; nêu dàn ý trước",
            "said": "Kriky chưa nêu dàn ý cho câu cần thay",
        }
    try:
        number = int(str(args.get("question_number") or "").strip())
    except ValueError:
        return {
            "started": False,
            "unreadable": ["question_number"],
            "reason": "question_number phải là số của câu, ví dụ 3",
            "said": "số thứ tự câu Kriky gửi không đọc được",
        }
    if number != running.outline.get("first"):
        meant = running.outline.get("first")
        return {
            "started": False,
            "reason": f"dàn ý đã xem là để thay câu {meant}, không phải {number}",
        }

    await harvest(session, running.pool, running.settings, assessment_id)
    if await pending_count(session, assessment_id):
        return {"started": False, "reason": "đề này đang soạn dở; chờ xong rồi hãy thay câu"}
    sat = await session.scalar(
        select(func.count()).select_from(Attempt).where(Attempt.assessment_id == assessment_id)
    )
    if sat:
        return {"started": False, "reason": "đề đã có lượt làm bài nên không thay câu được"}
    there = await session.scalar(
        select(Question.id).where(
            Question.assessment_id == assessment_id, Question.order_index == number
        )
    )
    if there is None:
        return {"started": False, "reason": f"đề không có câu {number}"}

    try:
        queued = await replace(
            session, running.pool, running.settings, assessment_id, number, running.outline
        )
    except HTTPException:
        # Cùng lý do với `start_drafting`: không thuật lại câu *"bỏ duyệt trước"* viết cho màn hình.
        return {
            "started": False,
            "reason": "đề này đã duyệt nên nội dung đã khoá; việc bỏ duyệt làm ở panel bên phải",
        }
    if not queued:
        return {
            "started": False,
            "reason": "chưa thay được câu: đề chưa có yêu cầu soạn, hoặc hàng đợi đang hỏng",
        }
    return {
        "started": True,
        "queued": queued,
        "assessment_id": assessment_id,
        "title": owned.title,
        "outline_version": running.outline.get("version"),
        "question_number": number,
        # Câu bị thay: vòng lượt so với câu đang đứng ở vị trí này sau khi đợi, để nói đúng
        # câu đã được thay hay vẫn giữ nguyên (review đợt 5, `draft-outline`).
        "replaced_question_id": there,
    }


# ------------------------------------------- tài liệu (`draft-from-document`)

# Một câu hỏi lại vẽ được bao nhiêu nút. Một cuốn SGK có 4--8 chương; một chương có tới ~10 bài.
_MOST_NODES = 12
# Tóm tắt một nút cắt ở đây: đủ để model khớp *"chương Hàm số"* với một tên chương. Nội dung thì đi
# bằng `read_section`, khi Kriky đọc để viết dàn ý (`draft-outline`, ADR-29) -- không bằng tóm tắt.
_SUMMARY_CHARS = 200
# Trần chữ của **một** phần đọc (`read_section`). Mười phần (trần 10 câu mỗi lần xin) là ~80 nghìn
# ký tự trong một lượt -- vừa một prompt gpt-4o-mini; một phần to hơn thì giáo viên xin ít câu trên
# một chương dài sẽ nhét cả chương vào một bước. Phần vượt trần thì **mỗi đơn vị** bị cắt theo tỉ lệ
# độ dài của nó, giữ phần đầu -- định nghĩa và ví dụ mẫu thường đứng đầu bài.
_PART_CHARS = 8000
_NO_SUCH_DOCUMENT = {
    "found": False,
    "reason": "không có tài liệu sẵn sàng nào như vậy trong thư viện của bạn",
}
_CONTENT_DOWN = {"found": False, "reason": "kho nội dung tài liệu tạm thời không đọc được"}


async def owned_document(
    session: AsyncSession, asking: Asking, document_id: str
) -> Document | None:
    """Tài liệu này khi nó thuộc giáo viên đang hỏi, ở **bất kỳ** trạng thái nào.

    Chip của một tệp vừa tải lên còn đang xử lý vẫn là chip của giáo viên: BE lưu nó cùng câu, để
    lượt sau dùng được khi tài liệu đã sẵn sàng (review B6, `draft-from-document`). Của người khác
    thì như không có (ADR-22).

    Args:
        session: Session của database.
        asking: Ai đang hỏi.
        document_id: Id tài liệu.

    Returns:
        Hàng tài liệu, hoặc `None`.
    """
    if not document_id:
        return None
    return await session.scalar(
        select(Document).where(Document.id == document_id, Document.teacher_id == asking.teacher_id)
    )


async def ready_document(
    session: AsyncSession, asking: Asking, document_id: str
) -> Document | None:
    """Tài liệu này, khi nó thuộc giáo viên đang hỏi **và** đã *sẵn sàng*.

    Hai điều kiện là một: tài liệu của người khác và tài liệu chưa có cây đọc lên y như nhau
    (ADR-22), và câu *"đã sẵn sàng chưa"* chỉ Postgres trả lời -- kho nội dung không bao giờ được
    hỏi nó (`be/content_reader.py`).

    Args:
        session: Session của database.
        asking: Ai đang hỏi.
        document_id: Id tài liệu.

    Returns:
        Hàng tài liệu, hoặc `None`.
    """
    if not document_id:
        return None
    return await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.teacher_id == asking.teacher_id,
            Document.state == DocumentState.READY.value,
        )
    )


def _pages(node: IndexNode) -> str:
    """Khoảng trang giáo viên nhận ra: trang **in** khi biết, không thì trang tệp."""
    start = node.printed_start if node.printed_start is not None else node.page_start
    end = node.printed_end if node.printed_end is not None else node.page_end
    return f"tr. {start}" if start == end else f"tr. {start}–{end}"


def node_label(node: IndexNode) -> str:
    """Tên một nút như giáo viên đọc trên nút bấm: *"Bài 3. Phép cộng phân số (tr. 12–15)"*.

    Args:
        node: Nút cây.

    Returns:
        Nhãn số, tên, khoảng trang.
    """
    return f"{heading(node)} ({_pages(node)})"


def _shown_node(node: IndexNode, children: int) -> dict:
    return {
        "node": node.ordinal,
        "label": node_label(node),
        "level": node.level,
        "children": children,
        "summary": (node.summary or "")[:_SUMMARY_CHARS],
    }


def _listed(nodes: list[IndexNode], every: list[IndexNode]) -> dict:
    """`candidates` + `more` cho một danh sách nút -- cùng hợp đồng với `list_class` (ADR-23)."""
    counts: dict[int, int] = {}
    for one in every:
        if one.parent_ordinal is not None:
            counts[one.parent_ordinal] = counts.get(one.parent_ordinal, 0) + 1
    kept = nodes[:_MOST_NODES]
    return {
        "found": True,
        "candidates": [_shown_node(node, counts.get(node.ordinal, 0)) for node in kept],
        "more": max(0, len(nodes) - len(kept)),
    }


async def _tree_of(running: Running, args: dict) -> tuple[list[IndexNode], dict | None]:
    """Cây của tài liệu trong `args`, hoặc một lời từ chối đọc được."""
    owned = await ready_document(
        running.session, running.asking, str(args.get("document_id") or "").strip()
    )
    if owned is None:
        return [], dict(_NO_SUCH_DOCUMENT)
    try:
        found = await get_reader().tree(owned.id)
    except ContentUnavailable:
        return [], dict(_CONTENT_DOWN)
    if found is None:
        return [], {"found": False, "reason": "tài liệu này chưa có mục lục"}
    return found[1], None


async def _list_documents(running: Running, args: dict) -> dict:
    """Những tài liệu *sẵn sàng* trong thư viện của giáo viên, mới nhất trước.

    Args:
        running: Session và giáo viên đang hỏi.
        args: Không có.

    Returns:
        `candidates` (mỗi tài liệu `document_id`, `label` là tên tệp) và `more`. `label` là thứ
        `teacher_chat._offered` vẽ thành nút khi model hỏi lại *"tài liệu nào"*.
    """
    rows = list(
        await running.session.scalars(
            select(Document)
            .where(
                Document.teacher_id == running.asking.teacher_id,
                Document.state == DocumentState.READY.value,
            )
            .order_by(Document.uploaded_at.desc(), Document.id)
        )
    )
    kept = rows[:_MOST_NODES]
    return {
        "candidates": [{"document_id": one.id, "label": one.filename} for one in kept],
        "more": max(0, len(rows) - len(kept)),
    }


async def _list_chapters(running: Running, args: dict) -> dict:
    """Các chương (nút gốc) của một tài liệu.

    Args:
        running: Session và giáo viên đang hỏi.
        args: `document_id`.

    Returns:
        `candidates` (mỗi nút `node`, `label`, `level`, `children`, `summary`) và `more`; hoặc
        `found: False` kèm `reason`.
    """
    every, refused = await _tree_of(running, args)
    if refused is not None:
        return refused
    return _listed([node for node in every if node.parent_ordinal is None], every)


async def _get_chapter(running: Running, args: dict) -> dict:
    """Các nút con trực tiếp của một nút: bài của một chương, mục của một bài.

    Args:
        running: Session và giáo viên đang hỏi.
        args: `document_id`, `node` (số `node` lấy từ `list_chapters` hay `get_chapter`).

    Returns:
        Cùng hình dạng với `list_chapters`; `found: False` khi nút không có.
    """
    every, refused = await _tree_of(running, args)
    if refused is not None:
        return refused
    try:
        wanted = int(str(args.get("node") or "").strip())
    except ValueError:
        return {
            "found": False,
            "reason": "node phải là một số lấy từ list_chapters",
            "said": _SAID_NO_SUCH_PART,
        }
    if not any(node.ordinal == wanted for node in every):
        return {"found": False, "reason": "tài liệu không có mục nào như vậy"}
    return _listed([node for node in every if node.parent_ordinal == wanted], every)


def _units(every: list[IndexNode], chunks: list, scope: list[int]) -> list[tuple[int, list[str]]]:
    """Các đơn vị của phạm vi, thứ tự đọc: mỗi nút có đoạn của riêng nó, kèm chữ các đoạn ấy."""
    inside = scope_of(every, scope)
    owned: dict[int, list[str]] = {}
    for chunk in sorted(chunks, key=lambda one: one.ordinal):
        if chunk.node_ordinal in inside:
            owned.setdefault(chunk.node_ordinal, []).append(chunk.text)
    return [(ordinal, owned[ordinal]) for ordinal in sorted(owned)]


def _part_text(every: list[IndexNode], units: list[tuple[int, list[str]]]) -> str:
    """Chữ một phần đọc: mỗi đơn vị một dòng tiêu đề rồi chữ của nó, cắt theo `_PART_CHARS`."""
    bodies = ["\n".join(texts) for _, texts in units]
    total = sum(len(body) for body in bodies)
    # Sàn mỗi đơn vị không vượt phần chia đều của trần: một câu trên cả cuốn sách là ~150 đơn vị
    # trong một phần, và sàn cố định 200 ký tự sẽ đưa phần ấy lên gấp năm lần trần (review đợt 2,
    # `draft-outline`).
    floor = min(200, _PART_CHARS // len(units))
    out = []
    for (ordinal, _), body in zip(units, bodies, strict=True):
        if total > _PART_CHARS:
            keep = max(floor, _PART_CHARS * len(body) // total)
            if len(body) > keep:
                body = body[:keep] + "\n[… phần sau của mục này không đọc trong lượt này]"
        out.append(f"## {title_path(every, ordinal)}\n{body}")
    return "\n\n".join(out)


# Lời cho **giáo viên** khi `reason` chở tên tool hay tên tham số (`said`, plan `backlog-tier-1`):
# dòng `✕` của khối bước in `said` trước, nên chữ ấy là chữ của người đọc màn hình, còn `reason` vẫn
# là chữ cho model sửa lời gọi. Tên tool trên màn hình là mặt trong của hệ thống (luật 7).
_SAID_NO_CLASS = "Kriky chưa chọn lớp nào"
_SAID_NO_SUCH_PART = "Kriky trỏ tới một mục không có trong mục lục"


def _node_list(raw: str) -> list[int]:
    """Các số node trong chữ model gửi, tách ở dấu phẩy **và** khoảng trắng. Hàm thuần.

    Bỏ khoảng trắng rồi mới tách thì *"1 2"* thành nút 12, và nút ấy có thật thì đọc nhầm bài mà
    không ai biết (review đợt 2, `draft-outline`). Một chỗ cho cả `read_section` lẫn
    `create_draft` -- bản cũ sửa ở chỗ thứ nhất, quên chỗ thứ hai (plan `backlog-tier-1`).

    Raises:
        ValueError: Khi có một mảnh không phải số.
    """
    return sorted({int(one) for one in re.split(r"[,\s]+", raw.strip()) if one})


async def _read_section(running: Running, args: dict) -> dict:
    """Chữ của một phạm vi tài liệu, gộp thành tối đa `questions` phần, trả phần thứ `part`.

    Kriky đọc trước khi viết dàn ý (`draft-outline`, ADR-29). Phạm vi -- các nút giáo viên chọn và
    cây con của chúng -- được gộp **không tách nút** thành `min(questions, số đơn vị)` phần liên
    tiếp (`toc.parts`), nên số lần đọc không vượt số câu xin. Chữ là chữ OCR: công thức và hình
    không có, và Kriky được dặn công thức trong dàn ý là của nó.

    Args:
        running: Session và giáo viên đang hỏi.
        args: `document_id`, `nodes` (các số node cách nhau bằng dấu phẩy), `questions` (số câu
            giáo viên xin), `part` (đếm từ 1; trống là 1).

    Returns:
        `found`, `part`, `parts`, `more` (còn phần chưa đọc), `nodes` (các nút trong phần này --
        nguồn cho dàn ý), `labels`, `text`; hoặc `found: False` kèm `reason`.
    """
    every, refused = await _tree_of(running, args)
    if refused is not None:
        return refused
    raw = str(args.get("nodes") or "").strip()
    try:
        scope = _node_list(raw)
        questions = int(str(args.get("questions") or "").strip())
        part = int(str(args.get("part") or "1").strip())
    except ValueError:
        return {
            "found": False,
            "reason": "nodes, questions, part phải là số",
            "said": _SAID_NO_SUCH_PART,
        }
    known = {node.ordinal for node in every}
    if not scope or any(one not in known for one in scope):
        return {
            "found": False,
            "reason": "nodes phải là số node lấy từ list_chapters/get_chapter",
            "said": _SAID_NO_SUCH_PART,
        }
    if not 1 <= questions <= MOST_QUESTIONS_ASKED:
        return {
            "found": False,
            "reason": f"questions là số câu giáo viên xin, 1 đến {MOST_QUESTIONS_ASKED}",
            "said": f"số câu phải từ 1 đến {MOST_QUESTIONS_ASKED}",
        }
    try:
        document_id = str(args.get("document_id") or "").strip()
        chunks = await get_reader().chunks(document_id, scope_of(every, scope))
    except ContentUnavailable:
        return dict(_CONTENT_DOWN)
    units = _units(every, chunks, scope)
    if not units:
        return {"found": False, "reason": "phạm vi này không có chữ nào đọc được"}
    grouped = parts([sum(len(text) for text in texts) for _, texts in units], questions)
    if not 1 <= part <= len(grouped):
        return {
            "found": False,
            "reason": f"part phải từ 1 đến {len(grouped)}",
            "said": f"phạm vi này chỉ có {len(grouped)} phần để đọc",
        }
    chosen = [units[index] for index in grouped[part - 1]]
    by_ordinal = {node.ordinal: node for node in every}
    return {
        "found": True,
        "part": part,
        "parts": len(grouped),
        "more": part < len(grouped),
        "nodes": [ordinal for ordinal, _ in chosen],
        "labels": [node_label(by_ordinal[ordinal]) for ordinal, _ in chosen],
        "text": _part_text(every, chosen),
    }


def _refusal(reason: str, said: str = "") -> dict:
    """Lời từ chối của `create_draft`: `reason` cho model, `said` cho giáo viên khi `reason` chở tên
    tool hay tên tham số."""
    refused: dict = {"created": False, "missing": [], "reason": reason}
    if said:
        refused["said"] = said
    return refused


async def _document_scope(
    running: Running, args: dict
) -> tuple[str, list[int], datetime | None, dict | None]:
    """Phạm vi tài liệu `create_draft` nhận: tài liệu, các nút, phiên bản cây -- hoặc từ chối.

    Không có `document_id` là một đề không tài liệu, như trước `draft-from-document`. Có tài liệu
    thì `nodes` bắt buộc -- thiếu nó là từ chối, không phải *cả cuốn* (review B5).

    Args:
        running: Session và giáo viên đang hỏi.
        args: `document_id`, `nodes` (các số `node` cách nhau bằng dấu phẩy).

    Returns:
        `(document_id, nodes, built_at, None)`, hoặc `("", [], None, lời từ chối)`.
    """
    document_id = str(args.get("document_id") or "").strip()
    if not document_id:
        return "", [], None, None
    owned = await ready_document(running.session, running.asking, document_id)
    if owned is None:
        return "", [], None, _refusal(_NO_SUCH_DOCUMENT["reason"])
    try:
        found = await get_reader().tree(owned.id)
    except ContentUnavailable:
        return "", [], None, _refusal(_CONTENT_DOWN["reason"])
    if found is None:
        return "", [], None, _refusal("tài liệu này chưa có mục lục")
    header, every = found
    try:
        nodes = _node_list(str(args.get("nodes") or ""))
    except ValueError:
        return (
            "",
            [],
            None,
            _refusal("nodes là các số node cách nhau bằng dấu phẩy", _SAID_NO_SUCH_PART),
        )
    if not nodes:
        # **Không** tự hiểu là cả cuốn (review B5, `draft-from-document`): một model nêu plan ngay
        # mà bỏ qua mục lục sẽ gửi `topic_scope="chương 1"` không kèm `nodes`, và đề rải câu khắp
        # sách. Cả cuốn là một lựa chọn phải nói ra -- mọi chương -- chứ không phải giá trị mặc
        # định.
        return (
            "",
            [],
            None,
            _refusal(
                "thiếu nodes: gọi list_chapters rồi gửi số node phạm vi (cả cuốn thì mọi chương)",
                "Kriky chưa chọn chương nào trong sách",
            ),
        )
    known = {node.ordinal for node in every}
    unknown = [one for one in nodes if one not in known]
    if unknown:
        return (
            "",
            [],
            None,
            _refusal(f"tài liệu không có mục {unknown}; gọi list_chapters", _SAID_NO_SUCH_PART),
        )
    # `built_at` **của cây đọc từ Mongo**, không phải giờ hiện tại: `fire` so đúng giá trị này để
    # biết cây có bị dựng lại giữa chừng không (review B2, `draft-from-document`).
    return owned.id, nodes, header.built_at, None


_PAGES_TAIL = re.compile(r"\s*\(tr\.[^)]*\)\s*$")


def _plain(text: str) -> str:
    """Chữ để so một nhãn: bỏ khoảng trang ở đuôi, gộp khoảng trắng, không phân biệt hoa thường."""
    return " ".join(_PAGES_TAIL.sub("", text).split()).casefold()


async def bind_book(steps: tuple["PlanStep", ...], document_id: str) -> tuple["PlanStep", ...]:
    """Điền tham số tài liệu mà model bỏ quên ở `create_draft`, khi đoạn chat gắn với **một** cuốn.

    Đo ngày 12/10/2026 trên gpt-4o-mini: cùng một lượt, khoảng một lần trong bốn--năm model nêu
    `create_draft` không kèm `document_id` và `nodes`, dù spec ghi chúng bắt buộc và skill dặn thêm
    -- lời dặn không giữ được model. Hai thứ ấy BE **biết** mà không phải đoán:

    - `document_id`: đoạn chat gắn với đúng một cuốn sẵn sàng (chip gần nhất).
    - `nodes`: `topic_scope` của model thường **là** nhãn BE đã dựng cho một mục (nút của câu hỏi
      lại, ADR-23) -- *"Chương I. TẬP HỢP CÁC SỐ TỰ NHIÊN"*. Khớp đúng nhãn (bỏ khoảng trang, không
      phân biệt hoa thường) thì đó là mục ấy. Không khớp thì để trống, và `vet_plan` từ chối như cũ.

    Args:
        steps: Các bước model nêu.
        document_id: Cuốn sách đoạn chat đang gắn với.

    Returns:
        Các bước, `create_draft` đã được điền những gì điền được.
    """
    if not any(one.tool_name == "create_draft" for one in steps):
        return steps
    try:
        found = await get_reader().tree(document_id)
    except ContentUnavailable:
        found = None
    # Mỗi khoá → **mọi** nút mang nó. Khoá trỏ tới hai nút thì không dùng (review B7,
    # `draft-from-document`): SGK có hai mục *"LUYỆN TẬP CHUNG"*, và chọn cái đầu là đoán. Nhãn đầy
    # đủ giữ khoảng trang -- thứ duy nhất phân biệt hai mục trùng tên -- nên chép đúng nút bấm vẫn
    # ra đúng một mục.
    keyed: dict[str, set[int]] = {}
    for node in found[1] if found else []:
        head = heading(node)
        full = " ".join(node_label(node).split()).casefold()
        for key in {full, _plain(head), _plain(node.title)}:
            keyed.setdefault(key, set()).add(node.ordinal)
    labels = {key: next(iter(ordinals)) for key, ordinals in keyed.items() if len(ordinals) == 1}

    out = []
    for one in steps:
        if one.tool_name != "create_draft":
            out.append(one)
            continue
        args = dict(one.args)
        chosen = str(args.get("document_id") or "").strip()
        if chosen and chosen != document_id:
            # Model chọn cuốn khác (qua `list_documents`): cây đang có là của cuốn kia, khớp nhãn
            # trên nó là gắn nhầm sách (review B7, `draft-from-document`). Để nguyên cho
            # `_document_scope` xét.
            out.append(one)
            continue
        # Trống **hoặc** rỗng: `""` qua được `vet_plan` (chỉ kiểm có mặt) rồi thành đề không
        # sách -- cùng lỗi review B6 (`draft-from-document`) định chặn, đi đường khác (review B7).
        args["document_id"] = document_id
        if not str(args.get("nodes") or "").strip():
            wanted = [part for part in str(args.get("topic_scope") or "").split(";")]
            matched = [
                labels.get(" ".join(part.split()).casefold(), labels.get(_plain(part)))
                for part in wanted
            ]
            if matched and all(hit is not None for hit in matched):
                args["nodes"] = ",".join(str(ordinal) for ordinal in matched)
        out.append(one.model_copy(update={"args": args}))
    return tuple(out)


_TOOLS: tuple[Tool, ...] = (
    # Bốn tool đọc tài liệu (`draft-from-document`; `read_section` từ `draft-outline`). Mô tả chỉ
    # nói **làm gì và nhận gì**; dùng lúc nào, theo thứ tự nào là việc của quy trình -- skill
    # `soan-de` mở thư viện khi giáo viên nhắc sách, còn đọc mục lục nằm ở `propose._BOOK_PROCEDURE`
    # bên AGENT, chỉ chèn ở lượt có sách (`unbiased-model-text`). Một nguồn cho mỗi điều, không lặp
    # ở hai chỗ.
    Tool(
        spec=ToolSpec(
            name="list_documents",
            description="Liệt kê tài liệu đã sẵn sàng trong thư viện của giáo viên.",
            arguments={},
        ),
        run=_list_documents,
    ),
    Tool(
        spec=ToolSpec(
            name="list_chapters",
            description="Các chương của một tài liệu: node, tên, trang, tóm tắt.",
            arguments={"document_id": "id tài liệu"},
        ),
        run=_list_chapters,
    ),
    Tool(
        spec=ToolSpec(
            name="get_chapter",
            description="Các mục con của một node: bài của một chương, mục của một bài.",
            arguments={"document_id": "id tài liệu", "node": "số node, lấy từ list_chapters"},
        ),
        run=_get_chapter,
    ),
    Tool(
        spec=ToolSpec(
            name="read_section",
            description=(
                "Đọc chữ của phạm vi tài liệu để viết dàn ý. Phạm vi được gộp thành tối đa "
                "questions phần; đọc lần lượt part 1, 2, … tới khi more là false. Chữ đọc từ ảnh "
                "quét: công thức và hình không có."
            ),
            arguments={
                "document_id": "id tài liệu",
                "nodes": "các số node của phạm vi, cách nhau bằng dấu phẩy",
                "questions": "số câu giáo viên xin, 1 đến 10",
                "part": "phần thứ mấy, đếm từ 1",
            },
        ),
        run=_read_section,
    ),
    Tool(
        spec=ToolSpec(
            name="list_class",
            description=(
                "Liệt kê các lớp của giáo viên kèm sĩ số, nhiều nhất 6 lớp; more là số lớp còn "
                "lại chưa hiện. Trả về candidates, mỗi lớp có class_id."
            ),
            arguments={"name": "tùy chọn: một phần tên lớp, chép từ lời giáo viên, để thu hẹp"},
            optional=("name",),
        ),
        run=_list_class,
    ),
    Tool(
        spec=ToolSpec(
            name="get_class",
            description=(
                "Thông tin một lớp theo class_id: tên và số học sinh. Lấy class_id từ list_class, "
                "TUYỆT ĐỐI không tự đoán."
            ),
            arguments={"class_id": "id lớp, lấy từ list_class"},
        ),
        run=_get_class,
    ),
    Tool(
        spec=ToolSpec(
            name="list_assessment",
            description=(
                "Liệt kê các đề đã phát hành cho một lớp, mới nhất trước. Dùng để tìm "
                "assessment_id trước khi hỏi kết quả. Đề nháp chưa phát hành KHÔNG nằm ở đây, vì "
                "nó chưa thuộc lớp nào."
            ),
            arguments={"class_id": "id lớp, lấy từ list_class"},
        ),
        run=_list_assessment,
    ),
    Tool(
        spec=ToolSpec(
            name="class_assessment_summary",
            description=(
                "Tóm tắt kết quả một bài kiểm tra trong một lớp: bao nhiêu em đã nộp, tổng điểm "
                "trung bình trên thang bằng số câu, và còn bao nhiêu câu chưa chữa xong. Cần "
                "class_id và assessment_id. Chưa biết assessment_id thì gọi list_assessment với "
                "class_id trước để lấy đúng id, rồi gọi lại tool này. TUYỆT ĐỐI không tự đoán "
                "assessment_id. Khi nói lại con số, PHẢI "
                "nói kèm thang — average_total_marks là điểm trên average_out_of câu, KHÔNG phải "
                "trên thang 10."
            ),
            arguments={
                "class_id": "id lớp, lấy từ list_class",
                "assessment_id": "id đề",
            },
        ),
        run=_class_assessment_summary,
    ),
    Tool(
        spec=ToolSpec(
            name="create_draft",
            description=(
                "Mở một đề nháp trống. Tool này không sinh câu hỏi và không nhận số câu: câu "
                "hỏi do start_drafting sinh, ngay sau nó."
            ),
            # Ba mục, không sáu. `difficulty` và `title` vẫn **nhận được** ở thân tool, nhưng
            # không còn được mô tả cho model -- và đó là một phép sửa cấu trúc, không phải một
            # lời dặn nữa. Đo trên trình duyệt thật năm lần với gpt-4o-mini: mỗi lần prompt
            # cấm hỏi một mục, model lại tìm ra một mục khác chưa bị cấm để hỏi, và mỗi câu
            # hỏi thừa tiêu trọn một lượt của giáo viên. Thứ không nhìn thấy thì không hỏi
            # được -- cùng cách ADR-25 bỏ tool ghi khỏi catalog pha 1 thay vì dặn đừng gọi.
            arguments={
                "subject": "môn học",
                "grade": "khối, chỉ con số",
                "topic_scope": "phạm vi kiến thức, chép đúng lời giáo viên",
            },
        ),
        run=_create_draft,
        writes=True,
    ),
    Tool(
        spec=ToolSpec(
            name="start_drafting",
            description=(
                "Sinh câu hỏi cho một đề nháp; câu hỏi hiện dần. Từ chối khi đề đang soạn dở "
                "hoặc đã duyệt."
            ),
            arguments={
                "assessment_id": "id đề nháp, lấy từ create_draft",
                "question_count": "số câu soạn lần này: đúng tổng số câu của dàn ý vừa duyệt",
            },
        ),
        run=_start_drafting,
        writes=True,
    ),
    Tool(
        spec=ToolSpec(
            name="replace_question",
            description=(
                "Soạn lại một câu của đề nháp theo dàn ý thay câu giáo viên vừa đồng ý. Câu cũ ở "
                "lại tới khi câu mới soạn xong."
            ),
            arguments={
                "assessment_id": "id đề nháp",
                "question_number": "số của câu bị thay",
            },
        ),
        run=_replace_question,
        writes=True,
    ),
)

_BY_NAME = {tool.spec.name: tool for tool in _TOOLS}

# Hai pha của một lượt (ADR-25). Pha lên plan chỉ tra cứu; pha thực hiện chỉ ghi.
PHASE_PLAN = 1
PHASE_WORK = 2


# Tool và tham số chỉ hiện khi lượt chat **có tài liệu** (`draft-from-document`). Cùng phép sửa với
# `test_the_model_never_sees_the_optional_fields_of_a_draft`: thứ không nhìn thấy thì không hỏi
# được -- `document_id` hiện cho một lượt không có sách là mời model hỏi *"dùng tài liệu nào?"*.
_DOCUMENT_TOOLS = frozenset({"list_chapters", "get_chapter", "read_section"})
_DOCUMENT_ARGUMENTS = {
    "document_id": "id tài liệu của phạm vi: tài liệu đính kèm, hoặc lấy từ list_documents",
    "nodes": (
        "các số node của phạm vi, cách nhau bằng dấu phẩy, lấy từ list_chapters/get_chapter; "
        "bắt buộc khi có document_id"
    ),
}
# `topic_scope` **không** đổi mô tả ở lượt có sách, dù mô tả chung (*"chép đúng lời giáo viên"*) cãi
# `_BOOK_PROCEDURE` (*"tên các mục đã chọn"*) -- review T2 (`unbiased-model-text`) thử một mô tả
# riêng nói cả hai nguồn, và `tai-lieu-khop-chuong` tụt 18/24 → 9/24: model hỏi *"cả chương hay một
# phần?"*. Khi model bỏ `nodes`, `bind_book` chỉ đỡ được nếu `topic_scope` trùng tên mục.


def _with_document(spec: ToolSpec, bound: bool) -> ToolSpec:
    """`create_draft` kèm hai tham số tài liệu.

    Tuỳ chọn khi lượt chỉ *từng* mở thư viện -- đề không sách vẫn mở được. **Bắt buộc** khi đoạn
    chat đang gắn với một cuốn sách sẵn sàng (`bound`): bỏ `document_id` là mở một đề không sách
    trong một đoạn chat về sách, lặng lẽ (review B6, `draft-from-document`) -- `vet_plan` từ chối nó
    trước khi có gì ghi.
    """
    if spec.name != "create_draft":
        return spec
    return spec.model_copy(
        update={
            "arguments": {**spec.arguments, **_DOCUMENT_ARGUMENTS},
            "optional": () if bound else tuple(_DOCUMENT_ARGUMENTS),
        }
    )


def catalog_for(
    asking: Asking, phase: int, documents: bool = False, bound: bool = False
) -> tuple[ToolSpec, ...]:
    """Mô tả những tool giáo viên này được dùng ở pha này.

    Mọi tool đều đã giới hạn theo chủ sở hữu, nên cả danh sách được đưa cho mọi giáo
    viên. Signature vẫn nhận vào giáo viên, vì tool đầu tiên không dành cho tất cả mọi
    người sẽ phải thu hẹp danh sách này lại chứ không phải bị chặn ở một chỗ muộn hơn --
    một tool đã được mô tả cho model là một tool model sẽ thử gọi.

    Phép chia theo pha đọc từ chính cờ `writes`, không từ một danh sách thứ hai: hai
    danh sách sẽ trôi dạt, còn một cờ trên chính tool thì đi theo tool khi ai đó thêm
    cái mới. Pha lên plan chỉ thấy tool đọc, nên **không có đường nào** để một câu hỏi
    lại bỏ lại việc đã làm dở (ADR-25).

    Args:
        asking: Ai đang hỏi.
        phase: `PHASE_PLAN` khi đang lên plan, `PHASE_WORK` khi đang chạy plan. Không có
            giá trị mặc định: một caller chưa nói mình đang ở pha nào là một caller chưa
            quyết định xem nó được phép ghi hay chưa, và chỗ để quyết là chỗ gọi.
        documents: Lượt này có tài liệu -- chip đính kèm, hoặc model vừa gọi
            `list_documents`. False thì tool đọc mục lục và tham số tài liệu của
            `create_draft` không được mô tả (`draft-from-document`).
        bound: Đoạn chat đang gắn với một cuốn sách sẵn sàng -- tham số tài liệu của
            `create_draft` thành bắt buộc.

    Returns:
        Các spec mà model được chọn trong đó.
    """
    wanted = phase == PHASE_WORK
    return tuple(
        _with_document(tool.spec, bound) if documents else tool.spec
        for tool in _TOOLS
        if tool.writes is wanted and (documents or tool.spec.name not in _DOCUMENT_TOOLS)
    )


class Unresolvable(Exception):
    """Một tham số trỏ tới thứ không có trong kết quả của bước nó gọi tên."""


REFERENCE = re.compile(r"^\{(\d+)\.([A-Za-z_][A-Za-z0-9_]*)\}$")

# Trông như một tham chiếu. Dùng để bắt những chuỗi gần đúng -- `{0.x}`, `{1.x} thêm chữ`,
# `{1.}` -- vì chúng là lỗi của model, không phải chữ của giáo viên. Để chúng đi tiếp
# nguyên văn nghĩa là một id rác tới tay một tool ghi, rồi hỏng ở trong đó dưới dạng một
# bước hỏng thay vì một plan bị từ chối.
LOOKS_LIKE_REFERENCE = re.compile(r"\{\s*\d+\s*\.")


def resolve_args(args: dict[str, str], done: list[dict]) -> dict[str, object]:
    """Thay các tham chiếu `{k.ten_field}` bằng giá trị thật của bước thứ k.

    Model chỉ trả về được chuỗi phẳng, nên một plan hai bước phụ thuộc nhau chỉ diễn tả
    được bằng một chuỗi như vậy: `start_drafting` cần `assessment_id` mà `create_draft`
    mới sinh ra (ADR-25). BE là bên duy nhất giải nó.

    **Tầm của hàm này là một bước**, không phải cả plan: nó giải ngay trước khi bước ấy
    chạy, từ kết quả các bước đã xong. Việc từ chối **trọn gói** một plan trước khi chạy
    bước nào cần một phép kiểm tĩnh -- `k` phải nhỏ hơn số thứ tự của bước đang xét, và
    field phải nằm trong những thứ tool của bước `k` hứa trả về -- và phép kiểm ấy thuộc
    về vòng chạy plan, không thuộc về đây.

    `k` đếm từ 1 và trỏ tới bước, không trỏ tới "bước trước": một plan ba bước có thể
    cần lại thứ bước đầu tiên sinh ra.

    Args:
        args: Tham số của một bước, toàn chuỗi.
        done: Kết quả của các bước đã chạy, theo thứ tự.

    Returns:
        Tham số đã giải, sẵn sàng đưa cho `execute`.

    Raises:
        Unresolvable: Khi `k` nằm ngoài những bước đã chạy, hoặc field không có trong
            kết quả của bước ấy.
    """
    out: dict[str, object] = {}
    for key, value in args.items():
        if not isinstance(value, str):
            raise Unresolvable(f"{key} không phải một chuỗi")
        match = REFERENCE.match(value.strip())
        if match is None:
            if LOOKS_LIKE_REFERENCE.search(value):
                raise Unresolvable(f"{key} viết sai khuôn tham chiếu: {value}")
            out[key] = value
            continue
        index, field = int(match.group(1)), match.group(2)
        if not 1 <= index <= len(done):
            raise Unresolvable(f"bước {index} chưa chạy")
        taken = done[index - 1].get(field)
        # Một field **có mặt mà rỗng** cũng là một tham chiếu vô dụng: để nó đi tiếp là
        # đưa một chuỗi rỗng vào chỗ đáng lẽ là một id, và cái sai ấy chỉ lộ ra ở tận bên
        # trong tool, dưới dạng "không tìm thấy đề nào".
        if taken is None or (isinstance(taken, str) and not taken.strip()):
            raise Unresolvable(f"bước {index} trả về {field} rỗng")
        if not isinstance(taken, (str, int, float, bool)):
            raise Unresolvable(f"bước {index} trả về {field} không phải một giá trị đơn")
        out[key] = taken
    return out


async def execute(
    session: AsyncSession,
    asking: Asking,
    name: str,
    args: dict,
    *,
    pool: object = None,
    settings: Settings | None = None,
    phase: int = PHASE_PLAN,
    outline: dict | None = None,
    conversation_id: str | None = None,
) -> dict:
    """Chạy một tool thay mặt giáo viên này.

    Đây là cái cổng. Catalog đã nói model được xin những gì; chỗ này quyết định chuyện gì
    thực sự xảy ra, và nó kiểm lại quyền sở hữu bên trong từng tool chứ không tin rằng
    catalog đã được đọc cho đúng.

    Thứ mà hàm này không bao giờ làm là đổi state của một đề.
    `tools/check_contract.py` từ chối file này nếu nó chỉ cần nhắc tới `advance` hay
    `withdraw`: trợ lý soạn nội dung, còn giáo viên mới là người quyết định nội dung đó
    có được thả ra hay không (ADR-01, ADR-02, ADR-05).

    Args:
        session: Session của database.
        asking: Ai đang hỏi.
        name: Tool được gọi tên trong đề xuất.
        args: Các tham số được nêu trong đề xuất, chưa qua validate.
        pool: Pool của arq, dành cho những tool đẩy việc vào queue.
        settings: Settings của process. Đọc từ process khi không được truyền vào.
        phase: Pha đang chạy. Một tool ghi gọi ở pha lên plan bị từ chối y như một tool
            không tồn tại -- cổng là chỗ này, không phải catalog. Mặc định là pha lên
            plan, tức mặc định **không ghi được gì**: một caller quên nói mình đang ở pha
            nào thì bị từ chối, chứ không lặng lẽ được cấp quyền ghi.
        outline: Dàn ý đã xem cho bước soạn câu (`Running.outline`).
        conversation_id: Đoạn chat đang chạy (`Running.conversation_id`).

    Returns:
        Kết quả của tool, đã được tóm tắt sẵn.

    Raises:
        UnknownTool: Nếu không có tool nào mang tên đó dành cho giáo viên này.
    """
    tool = _BY_NAME.get(name)
    # So theo **tên** trong catalog rộng nhất của pha: spec của `create_draft` đổi theo lượt
    # có tài liệu hay không, còn quyền thì không đổi -- pha nào ghi được vẫn là pha ấy.
    allowed = {spec.name for spec in catalog_for(asking, phase, documents=True)}
    if tool is None or name not in allowed:
        raise UnknownTool(name)

    logger.info("teacher %s runs %s", asking.teacher_code, name)
    return await tool.run(
        Running(
            session=session,
            asking=asking,
            pool=pool,
            settings=settings or get_settings(),
            outline=outline,
            conversation_id=conversation_id,
        ),
        args,
    )
