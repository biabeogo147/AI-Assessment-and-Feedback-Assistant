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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from be.assessment_state import AssessmentState
from be.config import Settings, get_settings
from be.drafting import _MOST_QUESTIONS, fire, harvest, pending_count, rebrief
from be.identity import Asking
from be.models import (
    Assessment,
    Attempt,
    DraftBrief,
    Publication,
    Question,
    QuestionOutcome,
    SchoolClass,
    Student,
)
from be.resolve import Ambiguous, Candidate, NotFound, Resolved, resolve_class
from contracts import ToolSpec

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
    """

    session: AsyncSession
    asking: Asking
    pool: object
    settings: Settings


@dataclass(frozen=True)
class Tool:
    """Một tool: nó được mô tả cho model thế nào, và nó chạy cái gì.

    Attributes:
        spec: Thứ model đọc. `spec.name` là thứ vòng lặp dựa vào để phân phối.
        run: Nhận context đang chạy và các tham số. Identity nằm trong context đó chứ
            không phải được đọc ở bên trong, nên không có đường nào để một tool chạy
            mà không biết nó được chạm vào dữ liệu của ai.
        writes: True khi tool đổi một thứ gì đó. Chưa được dùng để quyết định điều gì
            -- mọi lần ghi ở đây đều đảo lại được khi đề chưa duyệt -- nhưng nó là
            thứ mà một cổng xác nhận sẽ đọc, và ghi lại nó theo từng tool thì rẻ hơn
            là sau này suy ra từ cái tên.
    """

    spec: ToolSpec
    run: Callable[[Running, dict], Awaitable[dict]]
    writes: bool = False


async def _find_class(running: Running, args: dict) -> dict:
    """Tra một lớp của giáo viên này theo cái tên họ gõ.

    Args:
        running: Session và giáo viên đang hỏi. Mọi candidate đều được filter theo
            `running.asking`.
        args: `name`, theo đúng cách giáo viên viết.

    Returns:
        Một trong bốn hình dạng: chính lớp đó; `ambiguous` kèm các candidate nó có thể
        là; không-tìm-thấy kèm những lớp giáo viên này thực sự có; hoặc, khi không có
        tên nào được đưa ra, một lời từ chối nói rõ điều đó. Không bao giờ đoán giữa
        các candidate -- lời từ chối đó là ADR-23, và vòng lặp biến nó thành một câu
        hỏi lại.
    """
    # `or ""` chứ không phải một giá trị mặc định, vì model có thể gửi `null` và
    # `str(None)` là "none" -- một string sẽ bị đem đi tìm, khớp với mọi lớp có tên
    # chứa nó, và nếu không khớp thì cho ra "không có lớp nào tên đó". Đó là câu sai
    # cho một câu hỏi không gọi tên lớp nào, và là câu trả lời sai cho một câu hỏi có
    # gọi tên lớp.
    session, asking = running.session, running.asking
    typed = str(args.get("name") or "")
    answer = await resolve_class(session, asking, typed)

    if not typed.strip():
        listed = answer.available if isinstance(answer, NotFound) else ()
        return {
            "found": False,
            "ambiguous": False,
            "reason": "chưa có tên lớp nào trong câu hỏi",
            "your_classes": [_shown(candidate) for candidate in listed],
            "more": answer.more if isinstance(answer, NotFound) else 0,
        }

    if isinstance(answer, Resolved):
        return {
            "found": True,
            "class_id": answer.class_id,
            "name": answer.name,
            "student_count": answer.student_count,
        }

    if isinstance(answer, Ambiguous):
        return {
            "found": False,
            "ambiguous": True,
            "reason": "tên đó khớp nhiều lớp, cần hỏi lại giáo viên chọn lớp nào",
            "candidates": [_shown(candidate) for candidate in answer.candidates],
            "more": answer.more,
        }

    return {
        "found": False,
        "ambiguous": False,
        "reason": "không có lớp nào tên đó trong danh sách của bạn",
        "your_classes": [_shown(candidate) for candidate in answer.available],
        "more": answer.more,
    }


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
        # Lời từ chối mang theo những thứ thực sự có, theo đúng cách `find_class` làm
        # (ADR-23). Một lời từ chối trống rỗng là một lời mời bịa ra, và đó không phải
        # một mối lo đoán trước -- nó đã được đo ở lần chạy đầu tiên với model thật,
        # khi gpt-4o-mini trả lời một câu không-tìm-thấy trơ trọi bằng cách gọi tên bốn
        # lớp không tồn tại. Nó cũng bịt luôn cái khe mà chính lần chạy đó lộ ra: không
        # có gì trong catalog nói cho model biết nên hỏi về đề nào, nên nó phải đoán
        # một id.
        return {
            "found": False,
            "reason": "không tìm thấy lớp hoặc đề trong danh sách của bạn",
            "assessments_in_this_class": await _assessments_of(session, asking, class_id),
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
_BRIEF_FIELDS = ("subject", "grade", "topic_scope", "question_count")

# Mỗi field văn bản tự do dài được bao nhiêu, lấy từ chính các cột lưu nó:
# `Assessment.subject` và `DraftBrief.difficulty` là String(64) còn `Assessment.grade`
# là String(16). Model là thứ ghi những field này, nên chúng đến đây đúng như lời giáo
# viên nói -- và `String(n)` không được thi hành trên SQLite, nên một bộ test không phát
# hiện ra chuyện này giúp chúng ta được.
_FIELD_CAPS = {"subject": 64, "grade": 16, "difficulty": 64}

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
        args: `subject`, `grade`, `topic_scope`, `question_count`, và tuỳ chọn thêm
            `difficulty` cùng `title`.

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
        }

    try:
        count = int(str(args["question_count"]).strip())
    except (TypeError, ValueError):
        # Không giống thiếu field. Báo "chưa đủ thông tin" cho một field model đã điền
        # rồi là đẩy nó đi một vòng để điền lại đúng giá trị đó, và cả lượt đó tiêu hết
        # mức trần của mình chỉ để phát hiện ra rằng "ba" không phải một con số.
        return {
            "created": False,
            "missing": [],
            "unreadable": ["question_count"],
            "reason": "question_count phải là một con số, ví dụ 10",
        }

    if not 1 <= count <= _MOST_QUESTIONS:
        return {
            "created": False,
            "missing": [],
            "unreadable": ["question_count"],
            "reason": f"số câu phải từ 1 đến {_MOST_QUESTIONS}",
        }

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
        }

    scope = str(args["topic_scope"]).strip()
    draft = Assessment(
        teacher_id=asking.teacher_id,
        # Một cái tên mà giáo viên đổi lại được sau, nên tự suy ra một cái thì không
        # tốn gì mà lại tiết kiệm được một vòng hỏi đáp về chuyện hình thức. Cắt ngắn
        # chứ không từ chối, cũng vì đúng lý do đó.
        title=str(args.get("title") or f"Đề {scope}").strip()[:160],
        subject=str(args["subject"]).strip(),
        grade=str(args["grade"]).strip(),
        state=AssessmentState.EMPTY,
        created_at=datetime.now(UTC),
    )
    session.add(draft)
    await session.flush()

    await rebrief(
        session,
        draft.id,
        topic_scope=scope,
        question_count=count,
        difficulty=str(args.get("difficulty") or "").strip(),
    )

    logger.info("teacher %s opened draft %s", asking.teacher_code, draft.id)
    return {
        "created": True,
        "assessment_id": draft.id,
        "title": draft.title,
        "question_count": count,
    }


async def _draft_progress(running: Running, args: dict) -> dict:
    """Thu về những gì đã xong, và nói đề nháp đã đi được tới đâu.

    Việc harvest mới là điểm cốt yếu. BE không có worker chạy nền, nên một câu hỏi chỉ
    vào được đề nháp khi có thứ gì hỏi tới nó -- và trước khi có tool này thì không gì
    hỏi tới cả: `start_drafting` đẩy các job vào queue mà câu trả lời của chúng hết hạn
    trong Redis một tiếng sau đó, để lại đề nháp trống và "đang soạn dở" mãi mãi.

    Args:
        running: Session, giáo viên đang hỏi, và queue.
        args: `assessment_id`.

    Returns:
        Các con số đếm được và các stem câu hỏi đã có tới lúc này, hoặc đúng cái câu trả
        lời không-tìm-thấy mà một đề nháp của người khác cho ra (ADR-22).

    Side effects:
        Ghi mọi câu hỏi đã xong vào đề nháp.
    """
    session, asking = running.session, running.asking
    assessment_id = str(args.get("assessment_id") or "")

    owned = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    if owned is None:
        return {"found": False, "reason": _NO_SUCH_DRAFT["reason"]}

    landed = await harvest(session, running.pool, running.settings, assessment_id)
    brief = await session.get(DraftBrief, assessment_id)
    stems = await session.scalars(
        select(Question.stem)
        .where(Question.assessment_id == assessment_id)
        .order_by(Question.order_index)
    )
    still_running = await pending_count(session, assessment_id)

    return {
        "found": True,
        "assessment_id": assessment_id,
        "title": owned.title,
        "state": str(owned.state),
        "asked_for": brief.question_count if brief is not None else 0,
        "written": list(stems),
        "just_landed": landed,
        "still_drafting": still_running,
    }


async def _start_drafting(running: Running, args: dict) -> dict:
    """Đẩy vào queue một job cho mỗi câu hỏi mà brief của một đề nháp yêu cầu.

    Từ chối khi còn có thứ gì đang chạy. Hai vòng gối lên nhau đúng là cái sự cố mà
    brief được lưu lại sinh ra để ngăn -- những câu hỏi soạn theo hai bộ hướng dẫn cùng
    nằm chung một đề -- và từ chối thì rẻ hơn là đi hoà giải.

    Args:
        running: Session, giáo viên đang hỏi, và queue.
        args: `assessment_id`.

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

    # Thu về trước đã. Không có gì khác trong BE đi thu những job này, nên một vòng đã
    # xong trong lúc không ai để ý thì vẫn đọc ra là đang chạy -- và lời từ chối bên
    # dưới khi đó sẽ là vĩnh viễn: đề nháp đó không bao giờ soạn tiếp được nữa.
    await harvest(session, running.pool, running.settings, assessment_id)

    if await pending_count(session, assessment_id):
        return {
            "started": False,
            "reason": "đề này đang soạn dở; chờ xong rồi hãy soạn thêm",
        }

    try:
        queued = await fire(session, running.pool, running.settings, assessment_id)
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
        }
    return {"started": True, "queued": queued, "assessment_id": assessment_id}


_TOOLS: tuple[Tool, ...] = (
    Tool(
        spec=ToolSpec(
            name="find_class",
            description=(
                "Tìm một lớp của giáo viên theo tên để lấy class_id. Gọi tool này trước khi hỏi "
                "về kết quả của một lớp, vì các tool khác cần class_id chứ không nhận tên lớp."
            ),
            arguments={"name": "tên lớp như giáo viên vừa nói, ví dụ 12A1"},
        ),
        run=_find_class,
    ),
    Tool(
        spec=ToolSpec(
            name="class_assessment_summary",
            description=(
                "Tóm tắt kết quả một bài kiểm tra trong một lớp: bao nhiêu em đã nộp, tổng điểm "
                "trung bình trên thang bằng số câu, và còn bao nhiêu câu chưa chữa xong. Cần "
                "class_id và assessment_id. Chưa biết assessment_id thì cứ gọi với class_id và một "
                "assessment_id rỗng: kết quả sẽ trả về assessments_in_this_class để bạn chọn đúng "
                "đề rồi gọi lại. TUYỆT ĐỐI không tự đoán assessment_id. Khi nói lại con số, PHẢI "
                "nói kèm thang — average_total_marks là điểm trên average_out_of câu, KHÔNG phải "
                "trên thang 10."
            ),
            arguments={
                "class_id": "id lớp, lấy từ find_class",
                "assessment_id": "id đề",
            },
        ),
        run=_class_assessment_summary,
    ),
    Tool(
        spec=ToolSpec(
            name="create_draft",
            description=(
                "Mo mot de nhap trong. BAT BUOC co du: subject (mon), grade (khoi), topic_scope "
                "(pham vi kien thuc, theo loi giao vien) va question_count (so cau). Thieu muc nao "
                "thi tool tra ve danh sach missing -- hay HOI giao vien nhung muc do roi goi lai, "
                "dung tu doan. difficulty va title la tuy chon. Tool nay KHONG sinh cau hoi; goi "
                "start_drafting sau."
            ),
            arguments={
                "subject": "mon hoc, vi du Toan",
                "grade": "khoi, vi du 12",
                "topic_scope": "pham vi kien thuc theo loi giao vien",
                "question_count": "so cau, 1 den 50",
                "difficulty": "muc do theo loi giao vien (tuy chon)",
                "title": "ten de (tuy chon, he thong tu dat neu bo trong)",
            },
        ),
        run=_create_draft,
        writes=True,
    ),
    Tool(
        spec=ToolSpec(
            name="start_drafting",
            description=(
                "Bat dau sinh cau hoi cho mot de nhap da co brief. Moi cau mot job chay nen, nen "
                "tool tra ve ngay va cau hoi hien dan -- dung cho, hay noi voi giao vien la dang "
                "soan. Tu choi neu de dang soan do hoac da duyet."
            ),
            arguments={"assessment_id": "id de nhap, lay tu create_draft"},
        ),
        run=_start_drafting,
        writes=True,
    ),
    Tool(
        spec=ToolSpec(
            name="draft_progress",
            description=(
                "Xem một đề nháp đã soạn được bao nhiêu câu, và đọc các câu đã có. Gọi tool này "
                "sau start_drafting để biết đã xong chưa — câu hỏi chỉ vào đề khi có ai hỏi tới, "
                "nên không gọi thì đề vẫn trống. still_drafting > 0 nghĩa là còn đang soạn."
            ),
            arguments={"assessment_id": "id đề nháp"},
        ),
        run=_draft_progress,
    ),
)

_BY_NAME = {tool.spec.name: tool for tool in _TOOLS}


def catalog_for(asking: Asking) -> tuple[ToolSpec, ...]:
    """Mô tả những tool giáo viên này được dùng trong lượt này.

    Mọi tool đều đã giới hạn theo chủ sở hữu, nên cả danh sách được đưa cho mọi giáo
    viên. Signature vẫn nhận vào giáo viên, vì tool đầu tiên không dành cho tất cả mọi
    người sẽ phải thu hẹp danh sách này lại chứ không phải bị chặn ở một chỗ muộn hơn --
    một tool đã được mô tả cho model là một tool model sẽ thử gọi.

    Args:
        asking: Ai đang hỏi.

    Returns:
        Các spec mà model được chọn trong đó.
    """
    return tuple(tool.spec for tool in _TOOLS)


async def execute(
    session: AsyncSession,
    asking: Asking,
    name: str,
    args: dict,
    *,
    pool: object = None,
    settings: Settings | None = None,
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

    Returns:
        Kết quả của tool, đã được tóm tắt sẵn.

    Raises:
        UnknownTool: Nếu không có tool nào mang tên đó dành cho giáo viên này.
    """
    tool = _BY_NAME.get(name)
    if tool is None or tool.spec not in catalog_for(asking):
        raise UnknownTool(name)

    logger.info("teacher %s runs %s", asking.teacher_code, name)
    return await tool.run(
        Running(
            session=session,
            asking=asking,
            pool=pool,
            settings=settings or get_settings(),
        ),
        args,
    )
