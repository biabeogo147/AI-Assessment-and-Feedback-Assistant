"""Luật *job soạn câu không đọc chữ tài liệu thô* (`draft-outline`, ADR-29).

Chỉ phần thuần: chuỗi nguồn vào, các dòng vi phạm ra -- như `test_check_contract.py`, không đọc file
nào ngoài `drafting.py` thật.
"""

import pytest

from check_contract import (
    DOCUMENT_TEXT_READS,
    _code_only,
    check_drafting_reads_no_document_text,
)


def _offending(source: str) -> list[int]:
    return [
        number
        for number, line in enumerate(_code_only(source), 1)
        if DOCUMENT_TEXT_READS.search(line)
    ]


@pytest.mark.parametrize(
    "source",
    [
        "reader = get_reader()\n",
        "pieces = await reader.chunks(document_id, inside)\n",
        "asked = Asked(focus_text=text)\n",
        "fields = dict(other_foci=titles, focus_title=own)\n",
        "from be.content_reader import get_reader\n",
    ],
)
def test_a_way_back_to_document_text_is_caught(source: str) -> None:
    assert _offending(source) == [1]


@pytest.mark.parametrize(
    "source",
    [
        "# reader = get_reader()\n",
        '"""Trước ADR-29, `focus_text=` chở chữ OCR."""\n',
        "item = item_fields(brief, index, part)\n",
        "chunked = ' '.join(parts)\n",
    ],
)
def test_dead_code_history_and_outline_fields_pass(source: str) -> None:
    assert _offending(source) == []


def test_drafting_as_it_is_reads_no_document_text() -> None:
    assert check_drafting_reads_no_document_text() is None
