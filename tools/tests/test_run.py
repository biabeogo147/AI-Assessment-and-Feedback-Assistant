"""Bản ghi mỗi lượt benchmark: `data/results/run-<n>/<model>/`.

Chỉ các luật thuần được canh ở đây -- đánh số, đặt tên thư mục, và tên bền không mang mã task
của plan (luật `AGENTS.md`). Phần ghi file không có test vì
`tmp_path` không dùng được trên máy dev này (thư mục tạm của pytest bị khoá), và một test chạm
`data/` thật thì sẽ để lại rác trong đúng chỗ đang giữ bản ghi.
"""

import json
from pathlib import Path

import pytest

from ocr_bench.run import model_tag, next_run, task_code_in

_TOOLS = Path(__file__).resolve().parents[1]


def test_the_first_run_is_number_one() -> None:
    """`data/` chỉ có sách, nhãn và cache: chưa lượt nào được ghi."""
    assert next_run(["gold", "cache"]) == 1


def test_a_new_run_goes_after_the_largest() -> None:
    """So **theo số**, không theo chữ: `run-10` lớn hơn `run-9`."""
    assert next_run(["run-9", "run-10", "run-2"]) == 11


def test_a_gap_is_never_filled() -> None:
    """`run-2` đã bị xoá vẫn có thể đang được plan nhắc tới; dùng lại số ấy là gán hai lượt chạy
    khác nhau cho cùng một cái tên."""
    assert next_run(["run-1", "run-3"]) == 4


def test_only_exact_run_folders_count() -> None:
    """Thư mục tình cờ bắt đầu bằng `run-` không được làm nhảy số."""
    assert next_run(["run-x", "run-5-old", "rerun-7", "run-2"]) == 3


def test_each_reader_gets_its_own_folder() -> None:
    """Hai lựa chọn nằm cạnh nhau trong một lượt; cấu hình VietOCR là một phần của tên, vì đổi
    nó là đổi chữ đọc ra."""
    assert model_tag("easyocr", "vgg_seq2seq") == "easyocr"
    assert model_tag("vietocr", "vgg_seq2seq") == "vietocr-vgg_seq2seq"
    assert model_tag("vietocr", "vgg_transformer") == "vietocr-vgg_transformer"


def test_text_inside_a_picture_is_not_scored() -> None:
    """Từ đường `text2` (plan 3c, D2), khối hình mang chữ OCR nằm trong nó, còn nhãn vàng để khối
    hình rỗng. Chấm chữ ấy thì CER của đường mới tăng âm thầm, và bảng số không còn so được với các
    lượt trước."""
    from document.ocr.model import BlockKind
    from ocr_bench.gold import GoldBlock, GoldPage
    from ocr_bench.run import _score_page

    gold = GoldPage(
        "L6T1",
        6,
        (
            GoldBlock(BlockKind.IMAGE, "", None),
            GoldBlock(BlockKind.TEXT, "Khi tính toán", None),
        ),
    )
    read = {
        "blocks": [
            {"kind": "image", "text": "CHƯƠNG sấ HỌc 4v 12"},
            {"kind": "text", "text": "Khi tính toán"},
        ],
        "seconds": {"layout": 1.0},
    }
    assert _score_page(gold, read)["cer"] == 0


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("t5-sau-list-documents", "t5"),
        ("model-text-t2b-known", "t2b"),
        ("A1_moc", "A1"),
        ("thu b2", "b2"),
        ("(t5)", "t5"),
        ("ca,t3e", "t3e"),
        # Phiên bản kiểu `v2` cũng là một mã người ngoài không giải được -- bắt có chủ ý.
        ("prompt-v2", "v2"),
        # Tên model là tên thật, không phải mã.
        ("o4-mini-moc", ""),
        ("o3", ""),
        ("tai-lieu-sau-thu-vien", ""),
        ("pageindex-jev-1.13.0", ""),
        ("vision-gpt-4.1-mini", ""),
        ("L6T1", ""),
        ("du-pt-bac-hai-9", ""),
    ],
)
def test_a_task_code_is_found_in_a_lasting_name(name: str, code: str) -> None:
    """Luật đặt tên của `AGENTS.md`: mã task của plan không nằm trong tên sống lâu hơn plan."""
    assert task_code_in(name) == code


def test_bench_case_ids_carry_no_task_code() -> None:
    """Id ca đo là tên bền: bản ghi kết quả, plan và backlog nhắc tới nó sau khi plan đã đóng."""
    propose = json.loads((_TOOLS / "propose_bench" / "cases.json").read_text(encoding="utf-8"))
    routing = json.loads((_TOOLS / "skill_bench" / "cases.json").read_text(encoding="utf-8"))
    ids = [case["id"] for part in propose.values() for case in part] + [c["id"] for c in routing]

    assert [one for one in ids if task_code_in(one)] == []


def test_no_bench_case_id_is_the_prefix_of_another() -> None:
    """`--only` lọc theo tiền tố: `tai-lieu-khong-dinh` từng kéo theo cả một ca mang tên nó cộng
    hậu tố, và lượt đo lại 24 lần của một ca thành 48 lần của hai ca (review T6/T7)."""
    propose = json.loads((_TOOLS / "propose_bench" / "cases.json").read_text(encoding="utf-8"))
    ids = [case["id"] for part in propose.values() for case in part]

    assert [(a, b) for a in ids for b in ids if b.startswith(a + "-")] == []
