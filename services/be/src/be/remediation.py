"""Phase 2 time and eligibility rules.

Two clocks meet here and they do not agree, which is the whole reason this
module exists. Phase 1 gives each student a personal window that nothing
interrupts (ADR-03). Phase 2 gives a round a budget derived from how many
questions are still open, inside an absolute deadline the teacher set -- and
when the deadline arrives mid-round, the round is **stopped** (ADR-15).
"""

from datetime import datetime, timedelta


def round_budget_minutes(minutes_per_question: int, open_questions: int) -> int:
    """Compute how long a round may run.

    Args:
        minutes_per_question: What the teacher set at publish time.
        open_questions: Questions still to be fixed, which shrinks each round.

    Returns:
        Total minutes for the round.
    """
    return minutes_per_question * open_questions


def round_ends_at(now: datetime, budget_minutes: int, deadline: datetime) -> datetime:
    """Decide when a round stops.

    Args:
        now: Server time the round starts at.
        budget_minutes: Budget from round_budget_minutes.
        deadline: The phase 2 deadline set at publish time.

    Returns:
        The earlier of budget expiry and the deadline. This is where "hết hạn
        thì lượt đang làm bị DỪNG" becomes a number rather than a sentence.
    """
    return min(now + timedelta(minutes=budget_minutes), deadline)


def will_be_cut(now: datetime, budget_minutes: int, deadline: datetime) -> bool:
    """Tell whether a round started now would be stopped by the deadline.

    BE answers this, not the interface: comparing two instants is exactly the
    rule of ADR-15, and a client doing the comparison would own the rule.

    Args:
        now: Server time.
        budget_minutes: Budget the round would get.
        deadline: The phase 2 deadline.

    Returns:
        True when the budget does not fit before the deadline, which is what
        selects the warning form of the round gate.
    """
    return now + timedelta(minutes=budget_minutes) > deadline
