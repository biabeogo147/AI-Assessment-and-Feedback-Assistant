"""Chia dàn ý giáo viên vừa đồng ý thành các câu (ADR-38).

Dàn ý là lời Markdown Kriky viết; BE chỉ biết **số câu** của nó. Khi giáo viên đồng ý và plan soạn
đã dựng (`approved_plan`, hay plan model tự nêu), AGENT đọc lại chính lời ấy và viết cho mỗi câu một
lời dặn tự đủ -- người soạn câu không thấy dàn ý và không thấy các câu khác. Lời chia việc (`note`)
đi kèm plan và hiện trên chat như một khối *thinking*, nên giáo viên thấy câu nào lo phần nào trước
khi câu nào được soạn.

Prompt và luật đo trên `tools/exam_bench` (plan `agent-split-bench`, Haiku): 49/50 job trung thành
với dàn ý; review pha 1 của plan ấy thêm luật *mỗi job chỉ nói về đúng câu của nó* và *chỉ công
thức dàn ý đã nêu*. Số job lệch số câu thì lý do về model một lần; vẫn thiếu thì không có plan nào
-- lượt hỏng thành thông báo hệ thống (ADR-30), và giáo viên gõ lại lời đồng ý.
"""

import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from agent import llm
from agent.graphs.propose.choose import _spent
from agent.graphs.propose.proposal import nfc
from agent.latex_escapes import restore_latex_escapes
from contracts import NextStepCompleted, NextStepRequested, Split, SplitJob, TurnRecord

logger = logging.getLogger("agent.graphs.propose")

# Bước plan soạn câu theo một dàn ý đã xem (cùng tập với `teacher_chat._DRAFTING_TOOLS` của BE).
DRAFTING_TOOLS = frozenset({"start_drafting", "replace_question"})

# Lời dẫn `differs` trong cách làm gửi người soạn: cũng là chữ model đọc.
DIFFERS_LEAD = "Khác các câu cùng phần dàn ý:"

SYSTEM = (
    "Bạn là Kriky, trợ lý soạn đề kiểm tra cho giáo viên phổ thông Việt Nam. Giáo viên vừa "
    "đồng ý dàn ý đề bạn đã trình bày; dàn ý ấy ở dưới, đúng như giáo viên đã đọc. Việc bây giờ: "
    "chia dàn ý thành từng câu hỏi, mỗi câu giao cho một người soạn riêng. Người soạn KHÔNG thấy "
    "dàn ý và không thấy các câu khác; họ chỉ nhận đúng phần bạn viết cho câu của họ.\n\n"
    "Luật:\n"
    "- Đúng số câu được dặn, mỗi câu một job, theo thứ tự câu của dàn ý.\n"
    "- Trung thành với dàn ý: không thêm kiến thức, công thức hay dạng câu mà dàn ý không có; "
    "không bỏ phần nào của dàn ý.\n"
    "- Mỗi job tự đủ: kiến thức câu kiểm, cách làm bài -- đủ để người soạn viết đúng câu ấy mà "
    "không cần hỏi lại.\n"
    "- Mỗi job chỉ nói về ĐÚNG câu của nó: không tả câu khác, không để người soạn tự chọn giữa "
    "hai dạng câu.\n"
    "- formulas chỉ gồm công thức dàn ý đã nêu cho phần ấy, mỗi công thức trong cặp $; dàn ý không "
    "nêu công thức thì để rỗng.\n"
    "- Một phần dàn ý phủ nhiều câu thì các câu ấy phải khác nhau ngay trong approach; differs nói "
    "câu này khác các câu kia ở đâu, vẫn trong điều dàn ý nói về phần ấy. Phần chỉ có một câu thì "
    "differs để rỗng.\n"
    "- note: lời bạn nói với giáo viên, Markdown ngắn: từng câu (hay nhóm câu) lo phần nào của dàn "
    "ý, gọi bằng số câu, và các câu cùng một phần khác nhau ra sao. Nói với giáo viên bằng chữ "
    "câu, không dùng chữ job. Không chép lại cả dàn ý."
)


class _Job(BaseModel):
    """Một câu giao cho một người soạn, dưới hình dạng model trả lời được."""

    model_config = ConfigDict(extra="forbid")

    part: str = Field(
        description=(
            "Nhãn của phần dàn ý mà câu này thuộc về, chép đúng như dàn ý ghi nhãn phần ấy."
        )
    )
    knowledge: str = Field(description="Kiến thức câu này kiểm.")
    formulas: tuple[str, ...] = Field(
        description="Công thức dàn ý đã nêu cho phần này, mỗi phần tử một công thức; có thể rỗng."
    )
    approach: str = Field(description="Cách làm bài của riêng câu này: dạng câu và các bước giải.")
    differs: str = Field(
        description="Câu này khác các câu cùng phần dàn ý ở đâu; rỗng khi phần ấy chỉ có một câu."
    )


class _Split(BaseModel):
    """Cách chia dàn ý đã duyệt thành các câu, dưới hình dạng model trả lời được."""

    model_config = ConfigDict(extra="forbid")

    note: str = Field(description="Lời ngắn bằng Markdown cho giáo viên: bạn chia việc thế nào.")
    jobs: tuple[_Job, ...] = Field(description="Mỗi câu hỏi một job, theo thứ tự của dàn ý.")


class SplitFailed(RuntimeError):
    """Model không chia được dàn ý thành đúng số câu, kể cả sau một lần trả lại."""


def split_prompt(asked: str, said: str, wanted: int, replacing: int | None) -> str:
    """Nội dung lời gọi chia việc. Hàm thuần.

    Args:
        asked: Lời giáo viên trước dàn ý, kể từ plan gần nhất.
        said: Lời dàn ý Markdown giáo viên đã đọc.
        wanted: Số câu của dàn ý (con số BE đã kiểm).
        replacing: Số câu bị thay, khi dàn ý là để thay một câu.
    """
    return (
        f"Lời giáo viên trước dàn ý: {asked}\n\n"
        f"Dàn ý bạn đã trình bày và giáo viên đã đồng ý:\n\n{said}\n\n{_task(wanted, replacing)}"
    )


def _task(wanted: int, replacing: int | None) -> str:
    if replacing is not None:
        return (
            f"Giáo viên muốn thay câu {replacing} của đề: chia đúng 1 job, cho câu {replacing}, "
            f"theo phần dàn ý nói về câu {replacing}."
        )
    return f"Chia thành đúng {wanted} job."


def recount(wanted: int, got: int, replacing: int | None = None) -> str:
    """Lời trả lại khi số job lệch số câu. Hàm thuần."""
    return f"Bạn chia ra {got} job. {_task(wanted, replacing)} Mỗi câu một job, theo thứ tự dàn ý."


def _unwritten(jobs: tuple["_Job", ...]) -> list[int]:
    """Số thứ tự (từ 1) các job thiếu kiến thức hay cách làm: người soạn nhận một lời dặn rỗng.
    Hàm thuần."""
    return [
        at
        for at, job in enumerate(jobs, start=1)
        if not job.knowledge.strip() or not job.approach.strip()
    ]


def _shown(request: NextStepRequested) -> tuple[TurnRecord | None, str]:
    """Lượt dàn ý giáo viên vừa đáp, và lời giáo viên trước nó; `(None, "")` khi không có. Hàm
    thuần.

    Cùng luật với cổng duyệt của BE (`teacher_chat._shown_outline`) và `approved_plan`: dàn ý phải
    đứng **ngay trước** lời giáo viên mở lượt này -- giữa chúng chỉ có lời giáo viên và thông báo
    hệ thống. Các bước của chính lượt này (tra cứu trước khi nêu plan) đứng sau lời ấy và không
    tính. Dàn ý cũ hơn đã qua: chia nó là tốn một lời gọi model cho một plan BE sẽ từ chối (review
    pha 1, plan `markdown-outline-agent-split`).
    """
    turns = list(request.history)
    opened = max((at for at, turn in enumerate(turns) if turn.kind == "teacher"), default=-1)
    at = opened
    while at >= 0 and turns[at].kind in {"teacher", "notice"}:
        at -= 1
    if at < 0 or turns[at].kind != "outline":
        return None, ""
    # Mọi lời giáo viên từ plan gần nhất tới dàn ý: sau một lượt sửa dàn ý, lời ngay trước nó là
    # *"câu 2 đổi sang tự luận"*, không phải yêu cầu gốc.
    begun = max((one for one, turn in enumerate(turns[:at]) if turn.kind == "plan"), default=-1)
    asked = " / ".join(
        nfc(turn.text).strip()
        for turn in turns[begun + 1 : at]
        if turn.kind == "teacher" and turn.text.strip()
    )
    return turns[at], asked


def _job(job: _Job) -> SplitJob:
    """Một job của model thành `SplitJob`: chữ dựng lại dấu gạch chéo, NFC, `differs` nối vào cách
    làm -- chỗ duy nhất của lời dặn soạn câu nói về dạng câu. Hàm thuần."""
    approach = nfc(restore_latex_escapes(job.approach)).strip()
    differs = nfc(restore_latex_escapes(job.differs)).strip()
    if differs:
        approach = f"{approach}\n{DIFFERS_LEAD} {differs}"
    return SplitJob(
        part=nfc(job.part).strip(),
        knowledge=nfc(restore_latex_escapes(job.knowledge)).strip(),
        formulas=tuple(nfc(restore_latex_escapes(one)).strip() for one in job.formulas if one),
        approach=approach,
    )


async def split_outline(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Gắn cách chia dàn ý vào một plan soạn (ADR-38); đề nghị khác đi qua nguyên vẹn.

    Plan soạn (`start_drafting`, `replace_question`) không đứng ngay sau một dàn ý giáo viên vừa
    đáp, dàn ý không có số câu, hay dàn ý khác việc (thay câu với soạn) cũng đi qua nguyên vẹn: cổng
    duyệt của BE từ chối nó bằng lời của nó, và model nêu dàn ý.

    Args:
        step: Đề nghị cuối của lượt.
        request: Lượt đang hỏi.

    Returns:
        `step`, với `split` khi nó là plan soạn.

    Raises:
        SplitFailed: Model không chia được đúng số câu, hay để một job trống, sau một lần trả lại.
            Handler ở tầng trên biến nó thành thông báo hệ thống (ADR-30).
        Exception: Bất cứ thứ gì provider raise -- cùng đường.
    """
    if step.kind != "plan" or step.split is not None:
        return step
    tools = {one.tool_name for one in step.steps}
    if not tools & DRAFTING_TOOLS:
        return step
    shown, asked = _shown(request)
    kept = (shown.tool_result if shown is not None else None) or {}
    wanted = int(kept.get("total") or 0)
    if shown is None or wanted < 1:
        return step
    replaces = kept.get("for") == "replace"
    if replaces != ("replace_question" in tools):
        return step
    replacing = int(kept.get("first") or 1) if replaces else None
    if replacing is not None:
        wanted = 1
    model = llm.with_fallback(lambda chat: chat.with_structured_output(_Split, include_raw=True))
    messages: list = [
        SystemMessage(SYSTEM),
        HumanMessage(split_prompt(asked, shown.text, wanted, replacing)),
    ]
    spent = 0
    found: _Split | None = None
    for attempt in range(2):
        answered = await model.ainvoke(messages)
        if isinstance(answered, dict):
            parsed, raw = answered.get("parsed"), answered.get("raw")
        else:
            parsed, raw = answered, None
        spent += _spent(raw)
        if parsed is None:
            logger.warning("split did not parse (attempt %d)", attempt + 1)
            continue
        got = len(parsed.jobs)
        # Thừa câu ở đề soạn mới hay soạn thêm thì cắt đuôi ngay: các câu theo thứ tự dàn ý, câu
        # thừa là câu sau số câu giáo viên duyệt. Thay câu thì không -- job đầu là câu 1, không phải
        # câu bị thay (review pha 1).
        usable = parsed.jobs[:wanted] if replacing is None else parsed.jobs
        if len(usable) == wanted and not _unwritten(usable):
            found = parsed.model_copy(update={"jobs": usable})
            break
        empty = _unwritten(usable)
        logger.warning("split gave %d job(s) for %d, empty %s", got, wanted, empty)
        if attempt == 0:
            reason = (
                recount(wanted, got, replacing)
                if len(usable) != wanted
                else f"Job {', '.join(map(str, empty))} thiếu kiến thức hay cách làm. Viết lại đủ."
            )
            messages += [
                AIMessage(json.dumps(parsed.model_dump(mode="json"), ensure_ascii=False)),
                HumanMessage(reason),
            ]
    if found is None:
        raise SplitFailed(f"no usable split of the outline into {wanted} question(s)")
    jobs = tuple(_job(one) for one in found.jobs)
    logger.info("split the outline into %d job(s)", len(jobs))
    return step.model_copy(
        update={
            "split": Split(note=nfc(restore_latex_escapes(found.note)).strip(), jobs=jobs),
            "model_tokens": step.model_tokens + spent,
        }
    )
