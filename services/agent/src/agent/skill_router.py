"""Jev chọn skill nào được nạp cho một lượt của Kriky (plan 4a). Module duy nhất của AGENT import
`typesafe_sdk`.

**Mỗi skill chuyên biệt một câu `choice` có/không** (D2), chạy song song trong một lời gọi: một tin
nhắn có thể cần hai skill (*"xem kết quả lớp 12A rồi soạn đề ôn"*). Skill bao quát không được hỏi --
nó là chỗ rơi vào khi không skill nào qua ngưỡng.

Ba quyết định đến từ jaggedness của `jev-1.13` (plan 3c, *Khảo sát Jev*):

- *Nghiêng về lựa chọn đầu* → **"yes" đứng đầu**. Ở đây lựa chọn an toàn là nạp: nạp thừa một skill
  chỉ là prompt trước plan 4a, thiếu `soan-de` là một plan bị BE từ chối.
- *State to làm Jev lạc* → state chỉ là vài lượt **chữ** gần nhất, không có kết quả tool (D3). Nhờ
  vậy mọi bước trong một vòng tool của BE thấy cùng một state và chọn cùng skill.
- *Kém với ngôn ngữ khác* → `instructions` và `criteria` tiếng Anh; chữ hội thoại giữ tiếng Việt.

Hỏng theo bất kỳ cách nào -- thiếu khoá, timeout, lỗi mạng, câu trả lời lạ -- thì nạp **mọi** skill
(D4): đúng bằng prompt trước plan 4a, không bao giờ tệ hơn.
"""

import asyncio
import json
import logging
from collections import OrderedDict
from collections.abc import Sequence
from functools import cache

from typesafe_sdk import AsyncTypeSafeClient, Choice, RetryPolicy, TypeSafeError

from agent import skills
from agent.config import get_settings
from contracts import TurnRecord

logger = logging.getLogger(__name__)

# Bao nhiêu lượt chữ gần nhất Jev được đọc. Đủ để một lời đáp ngắn (*"10 câu"*) còn thấy câu hỏi lại
# ngay trước nó; không đủ để Jev lạc vào một chủ đề đã qua.
_TURNS = 4
# Trần chữ mỗi lượt gửi đi: một câu giáo viên hiếm khi dài hơn, phần dư chỉ là token.
_TEXT_CHARS = 600
# Bao nhiêu lựa chọn được nhớ trong process.
_REMEMBERED = 256

_INSTRUCTIONS = (
    "The state holds the latest messages of a chat between a Vietnamese school teacher and the "
    "assistant Kriky, oldest first; the last one is the teacher's newest message. Decide whether, "
    "to answer that newest message, Kriky needs the guide described in the criteria. A short reply "
    "to a question Kriky just asked continues the same task as that question."
)


def state_of(history: Sequence[TurnRecord]) -> dict | None:
    """`state` gửi Jev: vài lượt chữ gần nhất, không có lượt tool. Hàm thuần.

    Args:
        history: Lịch sử hội thoại, cũ nhất trước.

    Returns:
        `{"conversation": [...]}`, hoặc `None` khi không có lượt nào của giáo viên -- không có gì
        để chọn.
    """
    said = [turn for turn in history if turn.kind in {"teacher", "assistant"} and turn.text]
    if not any(turn.kind == "teacher" for turn in said):
        return None
    return {
        "conversation": [
            {"speaker": turn.kind, "text": turn.text.strip()[:_TEXT_CHARS]}
            for turn in said[-_TURNS:]
        ]
    }


def _questions(specialised: Sequence[skills.Skill]) -> dict[str, Choice]:
    """Một câu yes/no cho mỗi skill chuyên biệt, "yes" đứng đầu.

    Args:
        specialised: Các skill trừ skill bao quát.

    Returns:
        Câu hỏi theo tên skill.
    """
    return {
        skill.name: Choice(
            instructions=_INSTRUCTIONS,
            criteria={
                "yes": f"Kriky needs this guide. It is for: {skill.description}",
                "no": "Kriky does not need this guide for the newest message.",
            },
        )
        for skill in specialised
    }


@cache
def _client() -> AsyncTypeSafeClient | None:
    """Client Jev dùng chung cho cả process, `None` khi không có khoá.

    Returns:
        Client, hoặc `None`.
    """
    settings = get_settings()
    if not settings.jev_api_key:
        return None
    return AsyncTypeSafeClient(
        api_key=settings.jev_api_key,
        model=settings.jev_model,
        timeout=settings.skill_router_timeout_seconds,
        retry=RetryPolicy(max_retries=1),
    )


_chosen: OrderedDict[str, tuple[str, ...]] = OrderedDict()


async def choose(history: Sequence[TurnRecord]) -> tuple[str, ...]:
    """Tên các skill nạp cho lượt này.

    Args:
        history: Lịch sử hội thoại, cũ nhất trước.

    Returns:
        Tên skill theo thứ tự của `skills.every()`. Không skill chuyên biệt nào qua ngưỡng thì chỉ
        skill bao quát; Jev hỏng thì mọi skill.
    """
    everything = tuple(skill.name for skill in skills.every())
    specialised = [skill for skill in skills.every() if skill.name != skills.GENERAL]
    client = _client()
    state = state_of(history)
    if client is None or state is None or not specialised:
        return everything

    key = json.dumps(state, ensure_ascii=False, sort_keys=True)
    if key in _chosen:
        _chosen.move_to_end(key)
        return _chosen[key]

    settings = get_settings()
    try:
        response = await asyncio.wait_for(
            client.system_one(state=state, questions=_questions(specialised)),
            timeout=settings.skill_router_timeout_seconds,
        )
        picked = tuple(
            skill.name
            for skill in specialised
            if float(response.answers[skill.name].probabilities.get("yes", 0))
            >= settings.skill_min_yes
        )
    except (TypeSafeError, TimeoutError) as exc:
        logger.warning("jev could not choose a skill, loading every skill: %s", exc)
        return everything
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        # Một câu trả lời thiếu câu hỏi hay mang hình dạng lạ: không đoán bù -- cùng đường lùi với
        # Jev không với tới được. Không nhớ lựa chọn này, để lượt sau còn được hỏi lại.
        logger.warning("jev answered in an unexpected shape, loading every skill: %r", exc)
        return everything

    chosen = picked or (skills.GENERAL,)
    _chosen[key] = chosen
    if len(_chosen) > _REMEMBERED:
        _chosen.popitem(last=False)
    logger.info("skills chosen: %s", ", ".join(chosen))
    return chosen
