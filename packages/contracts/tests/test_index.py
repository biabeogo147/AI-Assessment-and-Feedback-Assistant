"""Hình dạng của cây mục lục trong kho nội dung, thứ document agent ghi và ba tool đọc sau này dựa
vào.

Canh những điều khoản mà một lần sửa vô ý phá được mà không bên nào đỏ lên, không canh pydantic.
"""

import pytest
from pydantic import ValidationError

from contracts import (
    MAX_LEVEL,
    BlockRef,
    IndexChunk,
    IndexNode,
    TitleSource,
    chunk_key,
    label_key,
    node_key,
    page_key,
)


def _node(level: int) -> IndexNode:
    return IndexNode(
        document_id="d",
        ordinal=0,
        level=level,
        title="Tập hợp",
        title_source=TitleSource.TEXT,
        anchor=BlockRef(page=7, block=1),
        page_start=7,
        page_end=9,
    )


def test_the_tree_has_exactly_three_levels() -> None:
    """Người dùng ghim ba cấp (11/10/2026): bậc sâu hơn gộp vào cha, không bao giờ thành nút."""
    assert MAX_LEVEL == 3
    assert _node(3).level == 3
    for wrong in (0, 4):
        with pytest.raises(ValidationError):
            _node(wrong)


def test_a_block_reference_counts_pages_from_one_and_blocks_from_zero() -> None:
    """Cùng cách đếm với `RawPage.page` và vị trí trong `RawPage.blocks`."""
    assert BlockRef(page=1, block=0).block == 0
    with pytest.raises(ValidationError):
        BlockRef(page=0, block=0)
    with pytest.raises(ValidationError):
        BlockRef(page=1, block=-1)


def test_the_keys_of_nodes_chunks_and_labels_never_collide_with_pages() -> None:
    """Bốn collection, bốn sơ đồ khoá; một khoá trùng là một lần ghi đè nhầm collection khác khi ai
    đó gộp chúng lại."""
    keys = {
        page_key("d", 1),
        node_key("d", 1),
        chunk_key("d", 1),
        label_key("d", BlockRef(page=1, block=1)),
    }
    assert len(keys) == 4


def test_a_chunk_before_the_first_node_belongs_to_no_node() -> None:
    """Bìa và lời nói đầu đứng trước nút đầu tiên: chúng vẫn là nội dung, chỉ không có nút cha."""
    chunk = IndexChunk(
        document_id="d",
        ordinal=0,
        blocks=(BlockRef(page=1, block=0),),
        text="LỜI NÓI ĐẦU",
        page_start=1,
        page_end=1,
        char_count=11,
    )
    assert chunk.node_ordinal is None


def test_stored_shapes_are_frozen() -> None:
    """Bản thô bất biến, và cây đọc từ Mongo cũng vậy: sửa là dựng lại, không vá tại chỗ."""
    node = _node(1)
    with pytest.raises(ValidationError):
        node.title = "khác"  # type: ignore[misc]
