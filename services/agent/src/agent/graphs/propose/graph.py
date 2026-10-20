"""Lắp graph hai node và `propose`: điểm vào, cùng vòng hỏi lại đúng một lần."""

import logging

from langgraph.graph import END, StateGraph

from agent import skill_router
from agent.graphs.propose.ask_again import (
    AskAgain,
    FewChoices,
    Flawed,
    NoOutline,
    NothingToSay,
)
from agent.graphs.propose.choose import choose
from agent.graphs.propose.clarify import choices_in
from agent.graphs.propose.compose import ProposeState, compose
from contracts import NextStepCompleted, NextStepRequested

logger = logging.getLogger("agent.graphs.propose")


# Thông báo hệ thống khi model hai lần liền để trống lời (ADR-30, ngoại lệ 1: không giọng Kriky; BE
# lưu nó thành lượt `notice`). Trung tính có chủ ý: **không** lùi về mock của
# `handlers.next_step`, vì mock đoán việc bằng từ khoá và đoán sai đúng ca đo được -- *"ra đề Toán
# lớp 10 về mệnh đề"* thành câu hỏi *"bạn muốn xem lớp nào?"* (review A1). Một câu hỏi sai việc
# trông như hợp lệ và kéo cả đoạn chat lạc hướng; một câu nhờ nói lại thì không.
_UNCLEAR = "Kriky chưa hiểu rõ ý bạn. Bạn nói lại theo cách khác giúp nhé?"


async def propose(request: NextStepRequested) -> NextStepCompleted:
    """Quyết định việc gì nên xảy ra tiếp theo trong cuộc hội thoại này.

    Args:
        request: Lịch sử tới lúc này và các tool giáo viên này được dùng.

    Returns:
        Một đề nghị. `request_id` bị ghi đè bằng id BE đã hỏi dưới: model không biết
        id đó, và một đề nghị mang theo một id nhắc lại hoặc bịa ra sẽ bị quy về job
        của một lượt khác.

    Raises:
        Exception: Bất cứ thứ gì provider raise. Handler ở tầng trên biến nó thành một thông
            báo hệ thống (ADR-30).
    """
    chosen = await skill_router.choose(request.history)
    state = {"request": request, "skills": chosen, "messages": [], "step": None}
    try:
        final = await _GRAPH.ainvoke(state)
    except AskAgain as first:
        # Một lần nữa, không hơn: lần hỏng thứ hai là model đang kẹt, không phải xui.
        logger.warning("%s for %s, asking once more", first, request.request_id)
        try:
            final = await _GRAPH.ainvoke({**state, "hint": first.hint})
        except Flawed as again:
            # Thiếu lần hai thì để đề nghị đi tiếp, như trước khi có lưới này: plan thiếu tham số
            # thì `vet_plan` của BE nói lời từ chối của nó, câu hỏi ít lựa chọn thì vẫn là một câu
            # hỏi -- giáo viên vẫn tự ghi được qua "Khác". AGENT không bịa tham số hay lựa chọn.
            logger.warning("%s again for %s", again, request.request_id)
            better = again.step
            if (
                isinstance(again, FewChoices)
                and isinstance(first, FewChoices)
                and choices_in(first.step) > choices_in(again.step)
            ):
                better = first.step
            final = {"step": better}
        except Exception as again:
            if not isinstance(first, Flawed):
                # Dàn ý hỏng hai lần cũng vậy: lùi về mock là cho giáo viên xem một dàn ý mock bịa
                # giữa một lượt chat thật (review đợt 4, `draft-outline`).
                if isinstance(again, (NothingToSay, NoOutline)):
                    logger.warning("empty answer twice for %s", request.request_id)
                    return NextStepCompleted(
                        request_id=request.request_id, kind="say", text=_UNCLEAR, notice=True
                    )
                raise
            # Lần đầu đã có một đề nghị dùng được: lần hai hỏng kiểu gì cũng giữ nó -- không bao giờ
            # tệ hơn trước khi có lưới này. Plan thì lượt không sách `vet_plan` từ chối như cũ, lượt
            # có sách `bind_book` có thể điền nốt (review T2b, `unbiased-model-text`). Lần hai im
            # lặng, hay provider hỏng, mà thả lỗi ra thì `handlers` ra một thông báo hệ thống.
            logger.warning(
                "asking again failed for %s (%r); keeping the first answer",
                request.request_id,
                again,
            )
            final = {"step": first.step}
    step: NextStepCompleted = final["step"]
    logger.info("proposed %s for %s", step.kind, request.request_id)
    return step.model_copy(update={"request_id": request.request_id})


def _build() -> object:
    """Lắp graph.

    Returns:
        Một graph đã compile, nhận `ProposeState` và điền vào `step`.
    """
    graph = StateGraph(ProposeState)
    graph.add_node("compose", compose)
    graph.add_node("choose", choose)
    graph.set_entry_point("compose")
    graph.add_edge("compose", "choose")
    graph.add_edge("choose", END)
    return graph.compile()


_GRAPH = _build()
