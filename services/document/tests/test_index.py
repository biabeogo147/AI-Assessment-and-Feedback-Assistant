"""Phần thuần của document agent (`document-agent-hierarchy`): ứng viên, luật, dựng cây, và cách hỏi
Jev.

Mọi mẫu chữ ở đây là chữ OCR **thật** của Lớp 6 tập 1 (pipeline `text2`), kể cả lỗi của nó -- luật
được viết cho đúng những lỗi ấy, và test phải giữ chúng lại.
"""

from datetime import UTC, datetime

import pytest

from contracts import BlockRef, DecidedBy, RawBlock, RawPage, RawSource, TitleSource
from document.index.assemble import Banner, assemble, headings
from document.index.features import (
    banner_gates,
    candidates,
    fold,
    numbering,
    page_offset,
    printed_pages,
    units,
)
from document.index.jev import (
    _QUESTIONS,
    JevClassifier,
    JevUnavailable,
    decision_from,
    open_paths,
    state_of,
)
from document.index.rules import (
    ACTIVITY_LABEL,
    BOOK_SECTION,
    DEEPER,
    NOT_HEADING,
    NUMBERED_EXERCISE,
    ROLES,
    RUNNING_HEADER,
    Decision,
    combine,
    decide,
)

_AT = datetime(2026, 10, 11, tzinfo=UTC)
_W, _H = 1520.0, 2100.0


def _page(
    number: int, *blocks: tuple[str, tuple[float, float, float, float] | None, str]
) -> RawPage:
    return RawPage(
        document_id="doc-1",
        page=number,
        source=RawSource.OCR,
        width=_W,
        height=_H,
        blocks=tuple(RawBlock(kind=kind, box=box, text=text) for kind, box, text in blocks),
        read_at=_AT,
    )


_BANNER = (0.0, 0.0, 1517.0, 1256.0)
_TOP = (366.0, 127.0, 994.0, 186.0)
_LEFT = (140.0, 970.0, 481.0, 1007.0)
_SMALL = (205.0, 1092.0, 793.0, 1126.0)


def _book() -> list[RawPage]:
    """Năm trang thu nhỏ của Lớp 6 tập 1: banner chương, một bài, mục, tiêu đề con, nhãn hoạt
    động, bài tập đánh số, ruy băng bài tập."""
    return [
        _page(1, ("doc_title", _TOP, "LỜl NÓI ĐẨU"), ("number", (96, 2004, 114, 2030), "")),
        _page(
            2,
            ("image", _BANNER, "0 CHƯƠNG sấ HỌc 0 5 CaoooraORCTNTTTSMY"),
            ("paragraph_title", (589.0, 1263.0, 989.0, 1340.0), ""),
            ("text", (134.0, 1500.0, 1381.0, 1600.0), "Khi tính toán với những số nhỏ"),
            ("number", (96, 2004, 114, 2030), "1"),
        ),
        _page(
            3,
            ("header", (78.0, 70.0, 318.0, 305.0), "BÀ 9"),
            ("doc_title", _TOP, "CÁCH GHI SỐ TỰ NHIÊN"),
            ("paragraph_title", (167.0, 346.0, 426.0, 379.0), "KHÁl NIỆM, THUẬT NGỮ"),
            ("paragraph_title", _LEFT, "1. HỆ THẬP PHÂN"),
            ("paragraph_title", _SMALL, "Cách ghi số tự nhiên trong hệ thập phân"),
            ("text", (160.0, 1200.0, 1300.0, 1300.0), "Ta dùng mười chữ số"),
            ("paragraph_title", (136.0, 1400.0, 229.0, 1430.0), "Ví dụ"),
            ("number", (96, 2004, 114, 2030), "2"),
        ),
        _page(
            4,
            ("paragraph_title", (135.0, 160.0, 374.0, 197.0), "2 SỐ LA MÂ"),
            ("paragraph_title", (136.0, 1317.0, 423.0, 1350.0), "1.1. Cho hai tập hợp:"),
            ("paragraph_title", (528.0, 1267.0, 984.0, 1336.0), "CnamAâ M @ V01 ~BAI TAP"),
            ("number", (96, 2004, 114, 2030), "3"),
        ),
        _page(5, ("doc_title", (501.0, 129.0, 1000.0, 184.0), "BÀl TẬP CUỐl CHƯƠNG |")),
    ]


# --- features ---


def test_folding_keeps_the_length_so_the_title_can_be_cut_from_the_original() -> None:
    for text in ("BÀl TẬP CUỐl CHƯƠNG |", "1.sỐ NOUYÊN TỐ", "Đường thẳng"):
        assert len(fold(text)) == len(text)
    assert fold("Đường") == "DUONG"


@pytest.mark.parametrize(
    ("text", "scheme", "label", "rest"),
    [
        ("1, HÌNH GHỮ NHẬT", "number", "1.", "HÌNH GHỮ NHẬT"),
        ("2 HÌNH VUôNO", "number", "2.", "HÌNH VUôNO"),
        ("1.sỐ NOUYÊN TỐ VÀ HỢP sỐ", "number", "1.", "sỐ NOUYÊN TỐ VÀ HỢP sỐ"),
        ("BÀl TẬP CUỐl CHƯƠNG |", "chapter_end", "Chương I", "BÀl TẬP CUỐl CHƯƠNG |"),
        ("CHƯƠNG III. SỐ NGUYÊN", "chapter", "Chương III", "SỐ NGUYÊN"),
        ("Bài 8. Quan hệ chia hết", "lesson", "Bài 8", "Quan hệ chia hết"),
        ("1.1. Cho hai tập hợp:", "dotted", "1.1", "Cho hai tập hợp:"),
        ("A.I.1 Khái niệm", "dotted", "A.I.1", "Khái niệm"),
        ("I. TỔNG QUAN", "roman", "I.", "TỔNG QUAN"),
        ("a) Tính", "sub", "a)", "Tính"),
    ],
)
def test_numbering_survives_the_ocr_errors_measured_on_the_real_book(
    text: str, scheme: str, label: str, rest: str
) -> None:
    found = numbering(text)
    assert found is not None
    assert (found.scheme, found.label, found.rest) == (scheme, label, rest)


def test_activity_labels_carry_no_numbering() -> None:
    for text in ("Luyện tập 1", "~HĐ1) Trong số 32 019", "HOẠT ĐỘNG 1 TẤM THIỆP"):
        assert numbering(text) is None


def test_a_picture_is_never_a_candidate_even_when_it_reads_chapter() -> None:
    """Khối hình chỉ mở cổng banner (D2, `document-agent-hierarchy`); hộp chồng nhau nên chữ của nó
    có thể lặp khối khác."""
    found = candidates(_book())
    assert all(candidate.unit.kind != "image" for candidate in found)
    assert all(candidate.unit.kind not in {"header", "number"} for candidate in found)
    assert "Khi tính toán với những số nhỏ" not in [c.unit.text for c in found]


def test_only_a_wide_picture_at_the_top_that_reads_chapter_opens_the_gate() -> None:
    """Trang 63 thật: một hình minh hoạ giữa trang có chữ *"Phần dấu, Phần số tự nhiên"*."""
    figure = _page(9, ("image", (589.0, 897.0, 900.0, 1013.0), "-3 Phần dấu _ Phần số tự nhiên"))
    assert banner_gates([*_book(), figure]) == [BlockRef(page=2, block=0)]


def test_printed_page_numbers_and_their_usual_offset() -> None:
    printed = printed_pages(_book())
    assert printed == {2: 1, 3: 2, 4: 3}
    assert page_offset(printed) == 1
    assert page_offset({}) is None


def test_a_plain_text_file_is_split_into_lines_without_touching_the_raw_content() -> None:
    page = RawPage(
        document_id="doc-1",
        page=1,
        source=RawSource.PLAIN,
        blocks=(RawBlock(kind="text", text="# Chương 1\nMở đầu\n## Bài 1"),),
        read_at=_AT,
    )
    found = units([page])
    assert [unit.ref.line for unit in found] == [0, 1, 2]
    assert page.blocks[0].text.count("\n") == 2
    marked = candidates([page])
    assert [c.markdown_level for c in marked] == [1, 2]


# --- rules ---


def _decided() -> dict[str, Decision]:
    return {c.unit.text: decide(c) for c in candidates(_book())}


def test_the_rules_read_a_textbook_the_way_its_gold_tree_does() -> None:
    decided = _decided()
    assert decided["CÁCH GHI SỐ TỰ NHIÊN"] == Decision(BOOK_SECTION, 2)
    assert decided["1. HỆ THẬP PHÂN"] == Decision(BOOK_SECTION, 3)
    assert decided["2 SỐ LA MÂ"] == Decision(BOOK_SECTION, 3)
    assert decided["BÀl TẬP CUỐl CHƯƠNG |"] == Decision(BOOK_SECTION, 2)
    assert decided["Cách ghi số tự nhiên trong hệ thập phân"] == Decision(BOOK_SECTION, DEEPER)


def test_the_rules_keep_activities_exercises_and_noise_out_of_the_tree() -> None:
    decided = _decided()
    assert decided["Ví dụ"].role == ACTIVITY_LABEL
    assert decided["KHÁl NIỆM, THUẬT NGỮ"].role == ACTIVITY_LABEL
    assert decided["1.1. Cho hai tập hợp:"].role == NUMBERED_EXERCISE
    assert decided["CnamAâ M @ V01 ~BAI TAP"].role in {ACTIVITY_LABEL, RUNNING_HEADER}
    assert decided["LỜl NÓI ĐẨU"].role == RUNNING_HEADER
    assert not any(d.is_node for t, d in decided.items() if t.startswith(("Ví", "1.1", "LỜl")))


def test_the_safe_choice_is_asked_first() -> None:
    """Jev 1.13 nghiêng về lựa chọn đầu tiên: đứng đầu phải là lựa chọn mà sai thì rẻ nhất."""
    assert ROLES[0] == NOT_HEADING
    assert list(_QUESTIONS["role"].criteria)[0] == NOT_HEADING
    assert list(_QUESTIONS["level"].criteria)[0] == "deeper"


def test_jev_decides_when_sure_and_the_rules_decide_otherwise() -> None:
    ruled = Decision(BOOK_SECTION, DEEPER)
    sure = Decision(BOOK_SECTION, 3, 0.9, DecidedBy.JEV, {"book_section": 0.95})
    unsure = Decision(BOOK_SECTION, 3, 0.4, DecidedBy.JEV, {"book_section": 0.6})
    assert combine(sure, ruled, 0.8) is sure
    kept = combine(unsure, ruled, 0.8)
    assert (kept.level, kept.decided_by) == (DEEPER, DecidedBy.RULES)
    assert kept.role_probabilities == {"book_section": 0.6}


# --- assemble ---


def _tree(decided: list[tuple], banners: list[Banner]):
    return assemble("doc-1", headings(decided, banners), 5, {2: 1, 3: 2, 4: 3}, 1)


def test_the_tree_from_the_small_book() -> None:
    found = candidates(_book())
    banner = Banner(
        BlockRef(page=2, block=0), "Chương I", "TẬP HỢP CÁC SỐ TỰ NHIÊN", "Bài 1", "TẬP HỢP"
    )
    nodes = _tree([(c, decide(c)) for c in found], [banner])
    shown = [(n.level, n.numbering, n.title, n.parent_ordinal) for n in nodes]
    assert shown == [
        (1, "Chương I", "TẬP HỢP CÁC SỐ TỰ NHIÊN", None),
        (2, "Bài 1", "TẬP HỢP", 0),
        (2, None, "CÁCH GHI SỐ TỰ NHIÊN", 0),
        (3, "1.", "HỆ THẬP PHÂN", 2),
        (3, "2.", "SỐ LA MÂ", 2),
        # Tên dựng từ nhãn đã tách, không giữ rác OCR *"BÀl TẬP CUỐl CHƯƠNG |"* (review Task 3,
        # `document-agent-hierarchy`).
        (2, None, "BÀI TẬP CUỐI CHƯƠNG I", 0),
    ]
    assert nodes[0].title_source is TitleSource.BANNER
    assert (nodes[0].page_start, nodes[0].page_end) == (2, 5)
    assert (nodes[2].page_start, nodes[2].page_end, nodes[2].printed_start) == (3, 5, 2)


def test_deeper_headings_never_become_nodes() -> None:
    """Người dùng chốt ba cấp: bậc sâu hơn gộp vào cha."""
    found = candidates(_book())
    nodes = _tree([(c, decide(c)) for c in found], [])
    assert all(n.level <= 3 for n in nodes)
    assert "Cách ghi số tự nhiên trong hệ thập phân" not in [n.title for n in nodes]


def test_a_level_never_jumps_and_the_first_node_is_level_one() -> None:
    found = [c for c in candidates(_book()) if c.unit.text == "1. HỆ THẬP PHÂN"]
    nodes = _tree([(found[0], Decision(BOOK_SECTION, 3))], [])
    assert [n.level for n in nodes] == [1]


def test_a_chapter_without_a_readable_name_keeps_its_number_and_no_invented_title() -> None:
    nodes = _tree([], [Banner(BlockRef(page=2, block=0), "Chương 1")])
    assert (nodes[0].title, nodes[0].title_source) == ("Chương 1", TitleSource.NUMBERING)


# --- jev ---


def test_the_state_is_one_block_and_words_not_coordinates() -> None:
    [candidate] = [c for c in candidates(_book()) if c.unit.text == "1. HỆ THẬP PHÂN"]
    state = state_of(candidate, {"level_1": "TẬP HỢP CÁC SỐ TỰ NHIÊN"})
    assert state["block"]["text"] == "1. HỆ THẬP PHÂN"
    assert state["numbering"] == "1."
    assert "left-aligned" in state["block"]["position"]
    assert state["page"] == "3 of 5"
    assert not any(isinstance(value, float) for value in state["block"].values())


def test_a_jev_answer_becomes_a_decision() -> None:
    section = decision_from(
        {"not_heading": 0.1, "book_section": 0.9}, {"deeper": 0.3, "level_3": 0.7}, (0.9, 0.5)
    )
    assert (section.role, section.level, section.confidence) == (BOOK_SECTION, 3, 0.5)
    label = decision_from({"activity_label": 0.8, "book_section": 0.2}, {"level_1": 1.0}, (0.7, 1))
    assert (label.role, label.level, label.confidence) == (ACTIVITY_LABEL, None, 0.7)


def test_the_open_path_comes_from_the_rules_and_the_banner() -> None:
    found = candidates(_book())
    paths = open_paths(found, [decide(c) for c in found], {2: "TẬP HỢP CÁC SỐ TỰ NHIÊN"})
    by_text = dict(zip([c.unit.text for c in found], paths, strict=True))
    assert by_text["1. HỆ THẬP PHÂN"] == {
        "level_1": "TẬP HỢP CÁC SỐ TỰ NHIÊN",
        "level_2": "CÁCH GHI SỐ TỰ NHIÊN",
    }
    assert by_text["LỜl NÓI ĐẨU"] == {}


@pytest.mark.asyncio
async def test_jev_down_is_its_own_error_so_the_tree_can_take_the_rules() -> None:
    from typesafe_sdk import TypeSafeError

    class _Down:
        async def system_one(self, **_: object) -> None:
            raise TypeSafeError("overloaded")

    jev = JevClassifier("k", "jev-1.13.0", 2, 5)
    jev._client = _Down()
    with pytest.raises(JevUnavailable):
        await jev.decide_all([{"block": {}}])


@pytest.mark.asyncio
async def test_a_jev_answer_in_an_unexpected_shape_takes_the_rules_path() -> None:
    """Thiếu câu hỏi, khoá lạ: không đoán bù -- cùng đường lùi với Jev không với tới được."""
    from types import SimpleNamespace

    class _Odd:
        async def system_one(self, **_: object) -> object:
            role = SimpleNamespace(probabilities={"mystery": 1.0}, confidence=1.0)
            return SimpleNamespace(answers={"role": role, "level": role}, usage=None, model="x")

    jev = JevClassifier("k", "jev-1.13.0", 2, 5)
    jev._client = _Odd()
    with pytest.raises(JevUnavailable):
        await jev.decide_all([{"block": {}}])


def test_the_banner_gate_does_not_open_on_chung_or_phan() -> None:
    """*CHUNG* (ước chung, bội chung) và *PHÂN* (phân số) không phải *CHƯƠNG* hay *PHẦN*."""
    for words in ("ƯỚC CHUNG LỚN NHẤT", "PHÂN SỐ TỐI GIẢN"):
        page = _page(9, ("image", _BANNER, words))
        assert banner_gates([page]) == []
    assert banner_gates([_page(9, ("image", _BANNER, "PHẦN HÌNH HỌC"))]) != []


def test_a_decomposed_text_layer_still_reads_its_numbering() -> None:
    """Chữ NFD (vài PDF có text layer ra vậy) phải đi qua cùng mẫu với chữ NFC."""
    import unicodedata

    page = _page(1, ("doc_title", _TOP, unicodedata.normalize("NFD", "BÀI 3. THỨ TỰ")))
    [candidate] = candidates([page])
    assert candidate.numbering is not None and candidate.numbering.label == "Bài 3"


def test_a_markdown_heading_does_not_carry_its_hashes_into_the_title() -> None:
    page = RawPage(
        document_id="doc-1",
        page=1,
        source=RawSource.PLAIN,
        blocks=(RawBlock(kind="text", text="# Giới thiệu\nNội dung"),),
        read_at=_AT,
    )
    found = candidates([page])
    nodes = assemble("doc-1", headings([(c, decide(c)) for c in found], []), 1, {}, None)
    assert [node.title for node in nodes] == ["Giới thiệu"]


def test_a_text_layer_report_reads_its_chapters_and_two_line_sections() -> None:
    """`report.pdf` thật (thử đầu-cuối Task 4, `document-agent-hierarchy`): *"Chương 1"* một khối,
    tên chương khối kế, và số mục cùng tên mục là **hai dòng của một khối**. Bản đầu đòi một dòng và
    dựng 6 nút cho 45 tiêu đề; *"1.1"* ở đây là mục, không phải bài tập như trong SGK."""
    page = RawPage(
        document_id="doc-1",
        page=6,
        source=RawSource.TEXT_LAYER,
        width=595.0,
        height=842.0,
        blocks=(
            RawBlock(kind="text", box=(85, 151, 190, 176), text="Chương 1"),
            RawBlock(kind="text", box=(85, 208, 199, 233), text="Đặt vấn đề"),
            RawBlock(kind="text", box=(85, 283, 188, 300), text="1.1\nBối cảnh"),
            RawBlock(
                kind="text",
                box=(85, 313, 524, 369),
                text="Ở trường phổ thông, một bài\nkiểm"
                " tra thường kết thúc\nkhi giáo viên trả điểm.",
            ),
        ),
        read_at=_AT,
    )
    found = candidates([page])
    nodes = assemble("doc-1", headings([(c, decide(c)) for c in found], []), 6, {}, None)
    assert [(n.level, n.numbering, n.title) for n in nodes] == [
        (1, "Chương 1", "Đặt vấn đề"),
        (2, "1.1", "Bối cảnh"),
    ]
