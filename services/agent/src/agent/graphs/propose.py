"""One turn of thinking for the teacher's chat: compose, then choose.

Two nodes, and the second one is a single structured call. That is smaller than
the authoring graph on purpose -- there is no self-check loop here, because the
thing being produced is not content anyone can validate. A proposal is either
executed by BE or refused by BE, and BE is the only side that can tell which.

What this module is careful about is the prompt. The model is choosing from a
list of tools it has never seen before and reading data it did not fetch, so
both have to arrive in a form it can act on: tool names spelled exactly as BE
dispatches on them, and tool results as data rather than as prose about data.

The system prompt carries three rules that are not style. AGENT may not claim
to have done anything -- it proposes, BE acts (ADR-05). It may not tell the
teacher which option to pick when the choice is pedagogical, because the
teacher holds that authority. And it asks rather than guesses when a name could
mean more than one thing, which is ADR-05's input gate.
"""

import json
import logging
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent import llm
from contracts import NextStepCompleted, NextStepRequested, ToolSpec, TurnRecord

logger = logging.getLogger(__name__)


_SYSTEM = """Bạn là trợ lý Kriky, làm việc cùng giáo viên phổ thông Việt Nam.

Mỗi lượt bạn chọn ĐÚNG MỘT trong ba việc:
- say: trả lời bằng lời. Dùng khi bạn đã có đủ thông tin để nói.
- call_tool: nhờ hệ thống chạy một tool trong danh sách được cấp, rồi bạn sẽ được hỏi lại với kết
  quả. Dùng khi bạn cần dữ liệu mà mình chưa có.
- ask_clarify: hỏi lại giáo viên. Dùng khi câu vừa rồi có thể hiểu theo nhiều cách.

Bốn điều không thương lượng:
- Bạn KHÔNG tự làm gì cả. call_tool là một lời đề nghị; hệ thống mới là người chạy. Vì thế TUYỆT ĐỐI
  không nói rằng bạn đã tạo, đã sửa, đã phát hành, đã lưu — chừng nào kết quả tool chưa nói vậy.
- ask_clarify chỉ để hỏi THÔNG TIN còn thiếu, trước một việc còn sửa lại được. TUYỆT ĐỐI không dùng
  nó để xin phép một việc không thu hồi được. Phát hành đề, xoá dữ liệu, đặt lại mật khẩu — những
  việc đó đi qua biểu mẫu riêng và hộp xác nhận, không bao giờ qua khung chat. Câu "phát hành cho
  lớp nào?" cũng vậy: đừng đưa lựa chọn, hãy nói rằng việc phát hành làm ở biểu mẫu phát hành.
- Khi việc phải chọn là quyết định sư phạm — chọn nguồn câu hỏi, chọn độ khó — bạn đưa thông tin và
  KHÔNG đánh dấu phương án nào là nên chọn. Giáo viên có thẩm quyền đó.
- Không đoán khi một cái tên có thể trỏ tới nhiều thứ. Hỏi lại, và chỉ đưa những lựa chọn có trong
  dữ liệu bạn được cấp. Không bịa tên lớp, tên đề hay con số nào.

Khi một tool trả về "ambiguous": true kèm "candidates", đó là lúc dùng ask_clarify. Bạn chỉ cần
viết CÂU HỎI; hệ thống tự dựng danh sách lựa chọn từ candidates, nên đừng tự liệt kê tên lớp hay
sĩ số trong câu hỏi và đừng điền gì vào choices — điền cũng bị bỏ. Và đừng nói lớp nào có vẻ
đúng hơn.

Nếu kết quả có "more" lớn hơn 0, nói rõ rằng danh sách chưa đầy đủ và còn bấy nhiêu lớp nữa, kèm
lời mời gõ tên cụ thể hơn. Không nói thì giáo viên đọc danh sách bị cắt như là dữ liệu đã mất.

Khi tool trả "found": false mà không ambiguous, hãy nói là không tìm thấy và nhắc lại các lớp trong
"your_classes" — đừng thử lại cùng một tên.

Cách viết:
- Tiếng Việt, gọn, như nói với đồng nghiệp. Tự gọi mình là "mình", gọi giáo viên là "bạn".
- KHÔNG dùng Markdown: không **in đậm**, không *nghiêng*, không `mã`, không bảng.
- Toán viết bằng ký hiệu Unicode: y = x³ − 3x, (−∞; −1), ≥, →. Không LaTeX."""


class ProposeState(TypedDict):
    """What flows through the two nodes.

    Attributes:
        request: The conversation and the catalog.
        messages: What the model sees, filled by `compose`.
        step: The proposal, filled by `choose`.
    """

    request: NextStepRequested
    messages: Annotated[list[BaseMessage], lambda old, new: new]
    step: NextStepCompleted | None


def _describe_tool(tool: ToolSpec) -> str:
    """Write one tool out for the model to choose from.

    Args:
        tool: The tool as BE described it.

    Returns:
        A block naming the tool exactly as BE dispatches on it, then what it
        does, then its arguments.
    """
    lines = [f"- {tool.name}: {tool.description}"]
    for argument, meaning in tool.arguments.items():
        lines.append(f"    {argument}: {meaning}")
    return "\n".join(lines)


def _describe_result(turn: TurnRecord) -> str:
    """Write a tool result out as data, not as a sentence about data.

    JSON rather than prose because the model has to read values out of it --
    an id it will pass to the next tool, a number it will quote to the teacher.
    Prose invites rounding and invites invention.

    Args:
        turn: A `tool_result` turn.

    Returns:
        One line naming the tool, then its result as JSON.
    """
    body = json.dumps(turn.tool_result, ensure_ascii=False, sort_keys=True)
    return f"Kết quả của {turn.tool_name}:\n{body}"


def _compose(state: ProposeState) -> dict:
    """Turn the request into the messages the model sees.

    The history becomes messages in order. A tool call and its result are the
    assistant's own move and what came back from it, so they are rendered as an
    assistant turn and a human turn -- which is the shape a chat model expects
    and the reason the model does not propose the same tool twice.

    Args:
        state: Carries the request.

    Returns:
        The `messages` slice of the state.
    """
    request = state["request"]

    opening = [_SYSTEM]
    if request.teacher_name:
        opening.append(f"Bạn đang nói với {request.teacher_name}.")
    if request.catalog:
        catalog = "\n".join(_describe_tool(tool) for tool in request.catalog)
        opening.append(f"Các tool bạn được dùng lượt này:\n{catalog}")
    else:
        # Saying so beats leaving the section out: a model given no list at all
        # tends to assume the omission is an oversight and names a tool anyway.
        opening.append("Lượt này bạn không có tool nào. Chỉ say hoặc ask_clarify.")

    messages: list[BaseMessage] = [SystemMessage("\n\n".join(opening))]
    for turn in request.history:
        if turn.kind == "teacher":
            messages.append(HumanMessage(turn.text))
        elif turn.kind == "assistant":
            messages.append(AIMessage(turn.text))
        elif turn.kind == "tool_call":
            args = json.dumps(turn.tool_args, ensure_ascii=False, sort_keys=True)
            messages.append(AIMessage(f"Mình xin gọi {turn.tool_name} với {args}."))
        else:
            messages.append(HumanMessage(_describe_result(turn)))

    return {"messages": messages}


def _spent(raw: object) -> int:
    """Read the provider's token count off a raw response.

    Args:
        raw: Whatever the provider returned alongside the parsed object.

    Returns:
        Total tokens, or 0 when the provider reported none. Zero means "not
        told", not "free": a fake model in a test reports nothing, and so do
        some providers.
    """
    usage = getattr(raw, "usage_metadata", None)
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if isinstance(total, int):
            return total
    return 0


async def _choose(state: ProposeState) -> dict:
    """Ask the model for one proposal, and note what it cost.

    `include_raw` is what makes the cost knowable. Structured output alone
    hands back the parsed object and drops the response it came in, and the
    usage report lives on that response -- so the plan's claim that recording
    tokens was "nearly free" was wrong: it needs this argument and a contract
    field.

    Args:
        state: Carries the composed messages.

    Returns:
        The `step` slice of the state, with `model_tokens` filled from the
        provider rather than from the model.
    """
    model = llm.with_fallback(
        lambda chat: chat.with_structured_output(NextStepCompleted, include_raw=True)
    )
    answered = await model.ainvoke(state["messages"])

    # A provider that cannot do `include_raw` -- or a fake that ignores it --
    # hands back the parsed object directly. Both shapes are supported because
    # the token count is a nicety and the proposal is not.
    if isinstance(answered, dict):
        parsed = answered["parsed"]
        if parsed is None:
            # `include_raw` turns a parse failure into `parsed=None` plus the
            # exception under `parsing_error`, where `include_raw=False` would
            # have raised it with the offending output attached. Letting it
            # through would trade a message naming the bad output for an
            # `AttributeError` on None, which names nothing.
            raise ValueError(
                f"model did not produce a usable proposal: {answered.get('parsing_error')}"
            )
        step: NextStepCompleted = parsed
        spent = _spent(answered.get("raw"))
    else:
        step, spent = answered, 0

    return {"step": step.model_copy(update={"model_tokens": spent})}


def _build() -> object:
    """Assemble the graph.

    Returns:
        A compiled graph taking `ProposeState` and filling in `step`.
    """
    graph = StateGraph(ProposeState)
    graph.add_node("compose", _compose)
    graph.add_node("choose", _choose)
    graph.set_entry_point("compose")
    graph.add_edge("compose", "choose")
    graph.add_edge("choose", END)
    return graph.compile()


_GRAPH = _build()


async def propose(request: NextStepRequested) -> NextStepCompleted:
    """Decide what should happen next in this conversation.

    Args:
        request: The history so far and the tools this teacher may use.

    Returns:
        One proposal. `request_id` is overwritten with the one BE asked under:
        the model does not know it, and a proposal carrying an echoed or
        invented id would be attributed to a different turn's job.

    Raises:
        Exception: Whatever the provider raises. The handler above decides what
            to fall back to, because only it knows whether anything has already
            reached the teacher.
    """
    final = await _GRAPH.ainvoke({"request": request, "messages": [], "step": None})
    step: NextStepCompleted = final["step"]
    logger.info("proposed %s for %s", step.kind, request.request_id)
    return step.model_copy(update={"request_id": request.request_id})
