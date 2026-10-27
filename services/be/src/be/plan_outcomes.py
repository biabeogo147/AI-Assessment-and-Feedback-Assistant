"""Kết quả của một plan đã chạy, đọc thành chữ: bước nào xong, hỏng, hay chưa chạy, và tiến độ soạn.

Dùng chung cho hai chỗ: pha 2 của `teacher_chat._go` (dòng kết quả dưới mỗi bước) và tool đọc
`last_plan` (`teacher_tools`), nơi model đọc lại plan vừa chạy ở lượt kể lại (ADR-25, hậu ký
22/10/2026). Tách ra khỏi `teacher_chat` vì `teacher_tools` không import ngược được nó.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from be.drafting import pending_count
from schema.models import DraftBrief, Question, TeacherTurn

# Sáu cờ, một câu hỏi: việc đó có xảy ra không. Mọi tool trả lời bằng đúng một trong
# chúng, và hai chỗ cần biết câu trả lời -- `_subject` để quyết có chủ thể hay không, và
# `went_wrong` để quyết bước đó hỏng hay xong -- đọc chung danh sách này.
DID_IT_HAPPEN = ("found", "created", "started", "approved", "unapproved", "published")


# Câu nói cho giáo viên khi một bước hỏng. `reason` của một tool là văn bản viết **cho
# model** -- "hãy hỏi giáo viên những mục còn thiếu", "question_count phải là một con số" --
# và in nó ra màn hình là để giáo viên đọc trợ lý nói về mình ở ngôi thứ ba, kèm một
# identifier tiếng Anh. Nguyên nhân đi vào log; chỗ này nói bằng lời người.
_WHY_IT_STOPPED = "chưa làm được bước này"


# Bước sau cần một giá trị bước trước không đưa được. Một câu, không phải `str(Unresolvable)`:
# cái sau gọi tên field và trích cú pháp tham chiếu, tức là mở mặt trong của hệ thống ra cho
# người không cần thấy nó -- và nó còn đi vào prompt của lời kể, nơi model sẽ nhắc lại.
COULD_NOT_CARRY_OVER = "chưa ghép được dữ liệu từ bước trước"


def said_about(result: dict) -> str:
    """Một dòng tiếng Việt kể kết quả của một bước, dựng từ **con số** của chính kết quả ấy.

    Không bao giờ in `reason` hay `error` nguyên văn: cả hai là chữ viết cho model đọc, và
    chúng chở cả tên field lẫn lời dặn model phải làm gì tiếp. Một màn hình in chúng ra là
    một màn hình để lộ mặt trong của hệ thống cho người không cần thấy nó.

    Args:
        result: Thứ tool vừa trả về.

    Returns:
        Dòng để hiện dưới tiêu đề bước. Rỗng khi kết quả không có con số nào đáng nói.
    """
    if result.get("error") or went_wrong(result):
        if result.get("missing"):
            return "thiếu thông tin để làm bước này"
        if result.get("unreadable") or result.get("too_long"):
            return "một mục trong yêu cầu chưa dùng được"
        return _WHY_IT_STOPPED
    if "queued" in result:
        return f"{result['queued']} câu bắt đầu soạn"
    if "title" in result:
        asked = result.get("question_count")
        title = str(result["title"])
        # Tên tự đặt đã mở bằng *Đề* (`titles.default_title`): thêm *đề* nữa là *đề "Đề Hàm số"*,
        # và câu kết của Kriky chép lại thành *Đề **Đề Hàm số*** (backlog 22/10/2026).
        named = f'"{title}"' if title.casefold().startswith("đề") else f'đề "{title}"'
        return named if asked is None else f"{named}, cần {asked} câu"
    return ""


def went_wrong(result: dict) -> bool:
    """Bước đó hỏng hay xong.

    Dùng chung đúng một danh sách cờ với `_subject`, vì hai danh sách trong một file là định
    nghĩa của trôi dạt -- và chúng **đã** lệch nhau một lần: bản đầu của hàm này biết ba cờ
    trong khi `_subject` biết sáu, nên một bước phát hành hỏng sẽ được báo là xong.

    Args:
        result: Thứ tool vừa trả về.

    Returns:
        True khi việc không xảy ra.
    """
    return bool(result.get("error")) or any(result.get(flag) is False for flag in DID_IT_HAPPEN)


def how_many(counted: tuple[int, int, int]) -> str:
    """Dòng kết quả của bước soạn câu, viết từ ba con số đã đếm.

    Nó thay cho dòng `— N câu bắt đầu soạn` của lúc vừa bắn job: tới cuối bước thì con số
    đáng nói là **số câu thật sự đã có**, không phải số job đã đẩy đi.

    Args:
        counted: `(đã có, xin bao nhiêu, còn đang soạn)`.

    Returns:
        Dòng tiếng Việt để hiện dưới tiêu đề bước.
    """
    written, asked_for, running = counted
    if running:
        return f"đã soạn {written}/{asked_for} câu, còn {running} câu đang chạy"
    if asked_for and written < asked_for:
        return f"dừng ở {written}/{asked_for} câu"
    return f"đã soạn {written}/{asked_for} câu"


async def count_questions(session: AsyncSession, assessment_id: str) -> tuple[int, int, int]:
    """Đếm `(đã có, xin bao nhiêu, còn đang soạn)` câu của một đề.

    Đếm từ **database**, không đếm từ số tiếng chuông đã nghe: chuông có thể mất, và một vị
    trí thử lại rung hai lần. Một con số dựng từ số lần nghe là đúng loại con số mà ADR-25
    mở đầu bằng cách phê phán.

    Args:
        session: Session của database.
        assessment_id: Đề nào.

    Returns:
        Ba con số. Không có brief thì `xin bao nhiêu` là 0 — hàm này đếm theo id, nó không
        kiểm đề có tồn tại hay không.
    """
    written = await session.scalar(
        select(func.count()).select_from(Question).where(Question.assessment_id == assessment_id)
    )
    brief = await session.get(DraftBrief, assessment_id)
    running = await pending_count(session, assessment_id)
    counted = int(written or 0), int(brief.question_count if brief else 0), running
    # Thả connection ra ngay. Ba câu select này mở một transaction, và chỗ gọi nó rồi đứng
    # đợi tiếng chuông kế tiếp -- hàng chục giây một connection Postgres nằm `idle in
    # transaction`, nhân với số tab đang mở. Cùng luật mà vòng lặp tool đã giữ sau mỗi bước.
    await session.rollback()
    return counted


def step_detail(tool_name: str, result: dict) -> str:
    """Dòng kết quả của một bước plan, dựng lại từ chính kết quả đã lưu của bước ấy.

    Cùng luật với pha 2 của `teacher_chat._go`, để dòng trên màn hình lúc chạy và dòng `last_plan`
    kể lại sau đó là một câu: bước không ghép được dữ liệu (`carried=False`) nói vậy; bước hỏng nói
    vì sao bằng lời người; bước thay câu nói đã thay hay câu cũ ở lại; bước soạn nói đã có mấy câu.

    Args:
        tool_name: Tool của bước.
        result: Kết quả đã lưu của bước.

    Returns:
        Dòng tiếng Việt, có thể rỗng.
    """
    if result.get("carried") is False:
        return COULD_NOT_CARRY_OVER
    if went_wrong(result):
        if (
            tool_name == "replace_question"
            and result.get("replaced") is False
            and result.get("reason")
        ):
            return str(result["reason"])
        return said_about(result)
    if tool_name == "replace_question" and "replaced" in result:
        number = result.get("question_number")
        if result["replaced"]:
            return f"đã thay câu {number}"
        return f"câu {number} mới còn đang soạn"
    if "written" in result:
        return how_many((result["written"], result["asked_for"], result["still_drafting"]))
    return said_about(result)


async def plan_summary(session: AsyncSession, conversation_id: str) -> dict:
    """Plan gần nhất của một đoạn chat, kể gọn: từng bước và tiến độ soạn **lúc hỏi**.

    Đọc từ `teacher_turns`: dòng `plan` gần nhất giữ tiêu đề các bước theo thứ tự, các cặp
    `tool_call` / `tool_result` sau nó là các bước đã chạy. Bước nào không có kết quả là bước
    **không chạy**: plan dừng ở bước hỏng đầu tiên. Tiến độ đếm lại từ database, không đọc con số
    đã lưu: lượt kể lại có thể tới khi job soạn còn chạy.

    Args:
        session: Session của database.
        conversation_id: Đoạn chat.

    Returns:
        `{"found": True, "steps": [...], "progress": {...}}`, `progress` chỉ có khi plan đụng tới
        một đề; hay `{"found": False, "reason": ...}` khi đoạn chat chưa chạy plan nào.
    """
    plan = await session.scalar(
        select(TeacherTurn)
        .where(TeacherTurn.conversation_id == conversation_id, TeacherTurn.kind == "plan")
        .order_by(TeacherTurn.sequence.desc())
        .limit(1)
    )
    if plan is None:
        return {"found": False, "reason": "Đoạn chat này chưa chạy plan nào."}
    after = (
        await session.scalars(
            select(TeacherTurn)
            .where(
                TeacherTurn.conversation_id == conversation_id,
                TeacherTurn.sequence > plan.sequence,
                TeacherTurn.kind.in_(("tool_call", "tool_result", "teacher")),
            )
            .order_by(TeacherTurn.sequence)
        )
    ).all()
    titles = [str(one) for one in (plan.tool_result or {}).get("steps") or ()]
    results: list[TeacherTurn] = []
    for row in after:
        if row.kind == "teacher":
            # Lượt chat sau đã bắt đầu: những gì đi sau nó không còn là của plan này.
            break
        if row.tool_name.startswith("teacher."):
            # Nút của panel (`teacher.approve`, `teacher.publish`…) ghi vào cùng đoạn chat mà không
            # có lời giáo viên nào đi trước: không phải bước của plan.
            continue
        if row.kind == "tool_result":
            results.append(row)
            if went_wrong(dict(row.tool_result or {})) or len(results) == len(titles):
                # Plan dừng ở bước hỏng đầu tiên, và hết bước thì hết plan: kết quả sau đó (một lần
                # đọc của lượt kể lại, chẳng hạn) không phải của bước nào.
                break
    steps = []
    paper = ""
    for index, title in enumerate(titles):
        if index >= len(results):
            steps.append({"title": title, "status": "không chạy", "detail": ""})
            continue
        row = results[index]
        outcome = dict(row.tool_result or {})
        found = outcome.get("assessment_id")
        if isinstance(found, str) and found:
            paper = found
        steps.append(
            {
                "title": title,
                "status": "hỏng" if went_wrong(outcome) else "xong",
                "detail": step_detail(row.tool_name, outcome),
            }
        )
    summary: dict = {"found": True, "steps": steps}
    if paper:
        written, asked_for, running = await count_questions(session, paper)
        summary["progress"] = {
            "written": written,
            "asked_for": asked_for,
            "still_drafting": running,
        }
    return summary
