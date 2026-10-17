"""Luật *mã plan trong comment kèm tên plan* (`document-debts-and-comment-codes`).

Chỉ phần thuần được canh ở đây: chuỗi nguồn vào, khối comment ra -- không đọc file nào (`tmp_path`
không dùng được trên máy dev này).
"""

import pytest

from check_contract import (
    assessments_made_past_empty,
    codes_without_a_plan,
    comment_blocks,
    http_servers_imported,
    reasons_for_the_model_only,
)

_SLUGS = {"document-agent-hierarchy", "unbiased-model-text"}


def _bad(source: str, suffix: str = ".py") -> list[tuple[int, str]]:
    return codes_without_a_plan(comment_blocks(source, suffix), _SLUGS)


@pytest.mark.parametrize(
    "said",
    [
        "# (review Task 4)\n",
        "# Từ plan 3c, cây có ba cấp.\n",
        "# tên chương nằm trong ảnh (D9)\n",
        "# lời dẫn review B7\n",
        "# Plan 4c T4: ví dụ là khuôn\n",
    ],
)
def test_a_bare_plan_code_is_named(said: str) -> None:
    """Mỗi dạng trong bốn dạng, đứng một mình, là một vi phạm."""
    assert _bad(said) != []


def test_a_label_cut_across_two_lines_is_still_caught() -> None:
    """*"plan"* cuối dòng này, *"4b"* đầu dòng sau: khối được nối lại trước khi so."""
    assert _bad("# chip đi cùng câu (plan\n# 4b), BE lưu nó\n") != []


def test_a_label_cut_across_an_indented_docstring_is_still_caught() -> None:
    """Trong docstring thụt lề, chỗ nối dòng là cả một dải khoảng trắng, không phải một dấu cách."""
    assert _bad('def f():\n    """Thứ tự đọc là thứ ở plan\n    3b dựa vào."""\n') != []


@pytest.mark.parametrize(
    "source",
    [
        "# (review Task 4, `document-agent-hierarchy`)\n",
        "# `unbiased-model-text` T4: ví dụ là khuôn\n",
        # Một slug cho cả khối, dù mã nằm ba dòng dưới.
        "# Đo ở `unbiased-model-text`.\n# ...\n# ...\n# (review T2)\n",
        'def f():\n    """Tóm tắt.\n\n    Review T5: ... (`unbiased-model-text`).\n    """\n',
    ],
)
def test_a_block_that_names_its_plan_passes(source: str) -> None:
    """Một khối nêu tên plan một lần là đủ cho mọi mã trong nó."""
    assert _bad(source) == []


def test_two_comment_blocks_do_not_lend_each_other_a_slug() -> None:
    """Một dòng code chen giữa thì là hai lời dẫn khác nhau."""
    source = "# `document-agent-hierarchy`\nx = 1\n# (review Task 4)\n"
    assert _bad(source) == [(3, "Task 4")]


def test_a_prompt_in_a_triple_quoted_string_is_not_a_comment() -> None:
    """Chuỗi ba nháy không phải docstring là chữ gửi model hay dữ liệu, không phải lời dẫn."""
    assert _bad('_CORE = """Bước T3: hỏi lại khối D2."""\n') == []


@pytest.mark.parametrize(
    "said",
    ["# Lớp 6 tập 1 (L6T1), trang 3-5\n", "# gpt-4.1-mini đọc `\\frac`\n", "# jev 1.13.0\n"],
)
def test_names_that_only_look_like_codes_pass(said: str) -> None:
    """Tên thật -- mã sách, model, phiên bản -- không phải mã plan."""
    assert _bad(said) == []


def test_typescript_comments_are_blocks_and_urls_are_not() -> None:
    """`//` liền nhau là một khối; `//` trong một URL không phải comment."""
    source = (
        'const url = "http://x/T4";\n'
        "// chip đi cùng câu (plan 4b):\n"
        "// BE lưu nó.\n"
        "/** Lối Khác (`unbiased-model-text` T3). */\n"
    )
    assert _bad(source, ".tsx") == [(2, "plan 4b")]


def test_a_tool_may_only_make_an_empty_paper() -> None:
    """Plan `backlog-tier-1`: `Assessment(state=APPROVED)` là đường vòng qua ADR-01 mà grep
    `.state =` không thấy -- nhất là khi lời gọi trải nhiều dòng."""
    made = "x = Assessment(\n    title='a',\n    state=AssessmentState.APPROVED,\n)\n"
    empty = "x = Assessment(title='a', state=AssessmentState.EMPTY)\n"

    assert assessments_made_past_empty(made) == [1]
    assert assessments_made_past_empty(empty) == []
    # Review code pha 5: qua tên module, và qua khoá trải ra.
    assert assessments_made_past_empty("x = models.Assessment(state=AssessmentState.APPROVED)") == [
        1
    ]
    assert assessments_made_past_empty("x = Assessment(**fields)") == [1]


def test_a_server_import_in_any_form_is_caught() -> None:
    """Plan `backlog-tier-1`: luật *`document` không mở cổng* nay có lưới."""
    assert http_servers_imported("import uvicorn") == [1]
    assert http_servers_imported("from fastapi import FastAPI") == [1]
    assert http_servers_imported("from http import server") == [1]
    assert http_servers_imported("from aiohttp import web") == [1]
    assert http_servers_imported("import aiohttp") == [1]
    assert http_servers_imported("from prometheus_client import start_http_server") == [1]
    assert http_servers_imported("server = await asyncio.start_server(handle, port=8001)") == [1]
    assert http_servers_imported("import httpx\nfrom http import HTTPStatus") == []


def test_a_refusal_naming_a_tool_must_carry_words_for_the_teacher() -> None:
    """Plan `backlog-tier-1`: `reason` chở `list_class` mà không `said` thì dòng ✕ in tên tool."""
    bare = 'x = {"found": False, "reason": "thiếu class_id; gọi list_class"}'
    said = 'x = {"found": False, "reason": "gọi list_class", "said": "Kriky chưa chọn lớp nào"}'
    plain = 'x = {"found": False, "reason": "không có lớp nào như vậy"}'

    assert reasons_for_the_model_only(bare) == [1]
    assert reasons_for_the_model_only(said) == []
    assert reasons_for_the_model_only(plain) == []
    assert reasons_for_the_model_only('_refusal(f"part phải từ 1 đến {n}")') == [1]
    # Review code pha 5: khoá `error` của vòng chạy bước, và dict có `**rest`, cũng được soi.
    assert reasons_for_the_model_only('x = {"error": f"tool {t} chạy không xong"}') == []
    assert reasons_for_the_model_only('x = {"error": "không có tool nào tên create_draft"}') == [1]
    assert reasons_for_the_model_only('x = {**base, "reason": "gọi list_class trước"}') == [1]
