"""Luật *mọi lời Kriky do model viết* (ADR-30, `kriky-writes-every-word`).

Chỉ phần thuần được canh ở đây: chuỗi nguồn vào, chỗ vi phạm ra -- không đọc file nào. Các ca *bắt*
dựng từ đúng những câu cố định pha 5 của plan ấy đã gỡ (review pha 5: bản đầu của check chỉ bắt được
3/7 câu ấy).
"""

import pytest

from check_contract import fixed_kriky_words

_NOTICES = {"CEILING_REACHED"}


def _bad(source: str, within: set[str] | None = None) -> list[tuple[int, str]]:
    return fixed_kriky_words(source, _NOTICES, within)


def _in(body: str) -> str:
    """Một đoạn thân hàm, thụt vào trong `async def _go()`."""
    return "async def _go():\n" + "".join(f"    {line}\n" for line in body.splitlines())


@pytest.mark.parametrize(
    "said",
    [
        _in('yield TurnEvent(kind="say", text="Mình chưa dựng được các bước.")'),
        _in('history.append(TurnRecord(kind="assistant", text="Được, mình soạn ngay."))'),
        _in('return NextStepCompleted(request_id="", kind="say", text="Bạn soạn theo sách nào?")'),
        _in('yield TurnEvent(kind="outline", text=f"Dàn ý — {n} câu")'),
        '_REFUSED = "Mình chưa làm được."\n' + _in('yield TurnEvent(kind="say", text=_REFUSED)'),
        '_LONG = (\n    "một câu "\n    "hai dòng"\n)\n'
        + _in('history.append(TurnRecord(kind="assistant", text=_LONG))'),
        # `_go` cũ: câu từ chối qua một biến cục bộ, và `.format()` trên hằng.
        '_PLAN_REFUSED = "Mình chưa dựng được."\n'
        + _in('refusal = _PLAN_REFUSED\nyield TurnEvent(kind="say", text=refusal)'),
        '_BOOK = "Tài liệu {filename} chưa dùng được."\n'
        + _in('refusal = _BOOK.format(filename=x)\nyield TurnEvent(kind="say", text=refusal)'),
        # `which_book` cũ: đè chữ qua `model_copy`.
        '_WHICH_BOOK = "Bạn soạn theo tài liệu nào?"\n'
        + _in('return step.model_copy(update={"text": _WHICH_BOOK})'),
        # Một nhánh `or` / `if…else` là câu cố định.
        _in('yield TurnEvent(kind="report", text=written or "Mình chưa làm được bước nào.")'),
        _in('yield TurnEvent(kind="say", text=step.text if ok else "Mình chưa rõ.")'),
        # Câu hệ thống dưới kind của lời Kriky: lúc chạy FE vẽ nó có avatar (review pha 5, N1).
        _in('yield TurnEvent(kind="say", text=CEILING_REACHED)'),
        # Kind không đọc ra được thì có thể là lời Kriky.
        _in('yield TurnEvent(kind=pick(), text="Mình chưa rõ.")'),
        # Lời kể cuối lượt cũng là lời Kriky.
        _in('return PlanReportCompleted(request_id="r", text="Mình đã tạo đề.")'),
        # Handler lùi về mock khi model hỏng.
        "async def propose_next_step(ctx, payload):\n"
        "    try:\n"
        "        return await propose(request)\n"
        "    except Exception:\n"
        "        return next_step(request).model_dump()\n",
    ],
)
def test_a_fixed_sentence_in_kriky_s_mouth_is_caught(said: str) -> None:
    assert _bad(said) != []


def test_a_kind_chosen_by_a_condition_counts_every_branch() -> None:
    """`"clarify" if x else "notice"` vẫn có thể ra lời Kriky, nên chữ cố định vẫn bị bắt."""
    source = _in('yield TurnEvent(kind="clarify" if asking else "notice", text="Chọn lớp nào?")')
    assert _bad(source) != []


@pytest.mark.parametrize(
    "said",
    [
        # Lời model viết.
        _in('yield TurnEvent(kind="say", text=step.text)'),
        _in('history.append(TurnRecord(kind="assistant", text=proposal.text.strip()))'),
        # Câu hệ thống của `be/notices.py` dưới `notice` (ngoại lệ 1).
        _in('yield TurnEvent(kind="notice", text=CEILING_REACHED)'),
        _in('history.append(TurnRecord(kind="notice", text=CEILING_REACHED))'),
        # Hai nhánh tách hẳn: kind đọc ra từ biến cục bộ, chữ là lời đã lưu.
        _in(
            'if telling:\n    shown = "report"\nelse:\n    shown = "notice"\n'
            "yield TurnEvent(kind=shown, text=history[-1].text)"
        ),
        # Không phải lời Kriky: thông báo, và sự kiện `done` chở lại chữ đã nói.
        _in('yield TurnEvent(kind="notice", text="Lượt này hỏng giữa chừng.")'),
        _in('yield TurnEvent(kind="done", text="x", ended_as="error")'),
        # AGENT tự khai câu của nó là thông báo hệ thống.
        '_DOWN = "Kriky chưa trả lời được."\n'
        + _in('return NextStepCompleted(kind="say", text=_DOWN, notice=True)'),
        # Không lời nào thì không phải lời cố định.
        _in('return NextStepCompleted(request_id="", kind="say", text="")'),
        _in('return step.model_copy(update={"request_id": request.request_id})'),
        # Chế độ demo: mock khi model tắt, không phải trong một `except`.
        "async def propose_next_step(ctx, payload):\n"
        "    if not llm.enabled():\n"
        "        return next_step(request).model_dump()\n",
    ],
)
def test_what_the_model_wrote_and_the_named_exceptions_pass(said: str) -> None:
    assert _bad(said) == []


def test_only_the_named_functions_are_read_when_asked() -> None:
    """Planner demo (`handlers.next_step`) là ngoại lệ có tên; handler gọi model thì không."""
    source = (
        "def next_step(request):\n"
        '    return NextStepCompleted(kind="say", text="Được, mình soạn đề ngay.")\n'
        "\n"
        "async def propose_next_step(ctx, payload):\n"
        '    return NextStepCompleted(kind="say", text="Mình đang bận.")\n'
    )
    assert [line for line, _ in _bad(source, {"propose_next_step"})] == [5]
