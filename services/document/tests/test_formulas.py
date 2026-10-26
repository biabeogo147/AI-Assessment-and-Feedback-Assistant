"""Đọc công thức trên ảnh trang khi BE xin (plan `formulas-on-demand`).

Không test nào chạm mạng: VLM là một hàm giả trả `FormulaReading`, hay một `AIMessage` dựng tay.
"""

import asyncio

import pymupdf
import pytest
from langchain_core.messages import AIMessage

from contracts import FormulaReadRequested
from document import formula_handlers
from document.config import Settings
from document.formula_handlers import read_pages
from document.index import llm
from document.index.llm import FormulaReading, parse_formulas


def _pdf(pages: int) -> bytes:
    with pymupdf.open() as book:
        for _ in range(pages):
            book.new_page().insert_text((72, 72), "1 + 2 = 3")
        return book.tobytes()


def test_a_backslash_the_json_decoder_ate_comes_back() -> None:
    """`\\frac` không nhân đôi gạch chéo thành form-feed + `rac`; bản đọc phải dựng lại nó."""
    raw = '{"cong_thuc": ["\\frac{1}{2}", "x \\\\in A"]}'
    assert parse_formulas(raw, 7).formulas == (r"\frac{1}{2}", r"x \in A")


def test_a_lone_backslash_that_breaks_json_is_doubled_and_read_again() -> None:
    """`\\in` không nhân đôi là escape JSON không hợp lệ: `json.loads` từ chối cả chuỗi."""
    raw = '{"cong_thuc": ["a \\vdots b", "x \\in \\mathbb{N}"]}'
    assert parse_formulas(raw, 1).formulas == (r"a \vdots b", r"x \in \mathbb{N}")


def test_a_valid_json_escape_that_is_really_latex_is_not_turned_into_a_newline() -> None:
    """`\\neq` không nhân đôi là escape JSON **hợp lệ** (`\\n` + `eq`): giải mã thẳng thì công thức
    mang một xuống dòng thật (review pha 2, `formulas-on-demand`)."""
    raw = '{"cong_thuc": ["a \\neq b", "\\rho = 1", "\\underline{x}"]}'
    assert parse_formulas(raw, 1).formulas == (r"a \neq b", r"\rho = 1", r"\underline{x}")


def test_mixed_escaping_keeps_every_formula_of_the_page() -> None:
    """Một công thức thoát đúng, một không: cả hai ra `\\in`, trang không mất trắng."""
    raw = '{"cong_thuc": ["x \\\\in A", "y \\in B"]}'
    assert parse_formulas(raw, 1).formulas == (r"x \in A", r"y \in B")


def test_two_inline_formulas_are_not_cut_in_the_middle() -> None:
    assert parse_formulas('{"cong_thuc": ["$a$ và $b$"]}', 1).formulas == ("$a$ và $b$",)


def test_wrappers_are_stripped_and_empty_entries_dropped() -> None:
    raw = '```json\n{"cong_thuc": ["$x = 1$", "\\\\[ y = 2 \\\\]", "  ", 3]}\n```'
    assert parse_formulas(raw, 1).formulas == ("x = 1", "y = 2")


def test_an_answer_that_is_not_json_reads_as_no_formula() -> None:
    reading = parse_formulas("Xin lỗi, tôi không đọc được.", 5)
    assert reading == FormulaReading((), False, 5)


def test_a_refusal_keeps_its_flag_and_no_formula() -> None:
    assert parse_formulas('{"cong_thuc": ["x"]}', 2, refused=True) == FormulaReading((), True, 2)


def test_the_formula_model_runs_without_thinking_whatever_the_shared_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def capture(model: str, **kwargs: object) -> object:
        seen.update(kwargs, model=model)
        return object()

    monkeypatch.setattr(llm, "init_chat_model", capture)
    settings = Settings(
        _env_file=None, claude_api_key="k", llm_thinking="adaptive", llm_effort="high"
    )
    llm.model_for(settings, "anthropic", "claude-haiku-5-5", claude=llm.FORMULA_CLAUDE)
    assert seen["thinking"] == {"type": "disabled"}
    assert seen["effort"] == "low"


def test_read_formulas_reads_the_refusal_from_the_stop_reason() -> None:
    class Refuses:
        async def ainvoke(self, messages: object) -> AIMessage:
            return AIMessage(content="", response_metadata={"stop_reason": "refusal"})

    reading = asyncio.run(llm.read_formulas(Refuses(), b"png"))
    assert reading.refused is True
    assert reading.formulas == ()


def test_every_asked_page_is_read_and_a_failing_page_leaves_no_row() -> None:
    asked = FormulaReadRequested(document_id="d1", storage_key="k", pages=(1, 2, 9))
    calls = []

    async def read(png: bytes) -> FormulaReading:
        calls.append(png)
        if len(calls) == 2:
            raise TimeoutError("provider timed out")
        return FormulaReading(("x = 1",), False, 10)

    kept: list = []

    async def keep(row: object) -> None:
        kept.append(row)

    rows = asyncio.run(read_pages(asked, _pdf(2), read, keep, asyncio.Semaphore(2), "m", 72))

    # Trang 9 không có trong tệp hai trang: không dựng, không gọi model.
    assert len(calls) == 2
    assert [row.page for row in rows] == [1]
    assert rows[0].formulas == ("x = 1",)
    assert rows[0].model == "m"
    # Mỗi trang đọc xong được ghi ngay, trang hỏng không ghi gì.
    assert kept == rows


def test_a_file_that_does_not_open_reads_no_page() -> None:
    asked = FormulaReadRequested(document_id="d1", storage_key="k", pages=(1,))

    async def read(png: bytes) -> FormulaReading:
        raise AssertionError("must not be called")

    async def keep(row: object) -> None:
        raise AssertionError("must not write")

    done = asyncio.run(read_pages(asked, b"not a pdf", read, keep, asyncio.Semaphore(1), "m", 72))
    assert done == []


@pytest.mark.parametrize("pages", [(1, 1), (0,), ()])
def test_a_request_with_repeated_zero_or_no_pages_is_refused(pages: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        FormulaReadRequested(document_id="d1", storage_key="k", pages=pages)


def test_no_formula_model_answers_no_page_without_reading_anything() -> None:
    payload = FormulaReadRequested(document_id="d1", storage_key="k", pages=(1,)).model_dump()

    class NoReader:
        async def read(self, key: str) -> bytes:
            raise AssertionError("must not read the file")

    done = asyncio.run(formula_handlers.read_formulas_job({"reader": NoReader()}, payload))
    assert done["pages"] == []


def test_the_job_writes_its_rows_and_answers_their_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = FormulaReadRequested(document_id="d1", storage_key="k", pages=(1,)).model_dump()
    written = []

    class Reader:
        async def read(self, key: str) -> bytes:
            return _pdf(1)

    class Store:
        async def put_formulas(self, rows: list) -> None:
            written.extend(rows)

    async def fake(model: object, png: bytes) -> FormulaReading:
        return FormulaReading((r"a^{2}",), False, 4)

    monkeypatch.setattr(formula_handlers, "read_formulas", fake)
    ctx = {
        "reader": Reader(),
        "store": Store(),
        "formula_model": object(),
        "formula_limit": asyncio.Semaphore(1),
    }
    done = asyncio.run(formula_handlers.read_formulas_job(ctx, payload))

    assert done["pages"] == [1]
    assert [row.formulas for row in written] == [(r"a^{2}",)]
