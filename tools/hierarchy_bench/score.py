"""Chấm một cây so với cây vàng. Hàm thuần, có test ở `tools/tests/test_hierarchy_score.py`.

**Một nút dự đoán khớp một nút vàng** khi cùng cấp, trang đầu lệch không quá `PAGE_SLACK`, và tên
đủ giống sau khi gấp (bỏ dấu, viết hoa) -- OCR đọc *"PHÉP CÔNG"* cho *"PHÉP CỘNG"*, và một phép so
từng ký tự sẽ chấm sai cả cuốn vì lỗi của OCR chứ không vì lỗi của cây. Ghép tham lam, mỗi nút dùng
một lần.

Precision và recall **theo cấp**: một cây đúng cấp 2 mà sai cấp 3 là một cây dùng được cho việc lần
xuống tới bài, và con số gộp sẽ giấu điều ấy.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from document.index.features import fold

# Trang đầu được lệch bao nhiêu: tên bài in ở cuối trang trước trang nội dung là chuyện thường.
PAGE_SLACK = 1
# Độ giống tối thiểu của hai tên đã gấp.
MIN_SIMILARITY = 0.5


@dataclass(frozen=True)
class TreeNode:
    """Một nút để chấm: của cây vàng hoặc của cây dựng ra.

    Attributes:
        level: 1..3.
        title: Tên.
        page: Trang tệp của tiêu đề.
        numbering: Nhãn số, `None` khi không có.
    """

    level: int
    title: str
    page: int
    numbering: str | None = None


@dataclass(frozen=True)
class LevelScore:
    """Điểm của một cấp.

    Attributes:
        level: Cấp.
        gold: Số nút vàng được chấm.
        built: Số nút dựng ra được chấm.
        matched: Số cặp khớp.
        same_page: Số cặp khớp có trang đầu đúng tuyệt đối.
    """

    level: int
    gold: int
    built: int
    matched: int
    same_page: int

    @property
    def precision(self) -> float:
        return self.matched / self.built if self.built else 0.0

    @property
    def recall(self) -> float:
        return self.matched / self.gold if self.gold else 0.0

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0


def similarity(left: str, right: str) -> float:
    """Độ giống của hai tên sau khi gấp, 0..1.

    Args:
        left: Tên thứ nhất.
        right: Tên thứ hai.

    Returns:
        Tỉ lệ của `SequenceMatcher`.
    """
    return SequenceMatcher(None, fold(left).strip(), fold(right).strip()).ratio()


def score(
    gold: list[TreeNode], built: list[TreeNode], unscored: list[tuple[int, int, int]] = ()
) -> list[LevelScore]:
    """Chấm cây dựng ra so với cây vàng.

    Args:
        gold: Cây vàng.
        built: Cây dựng ra.
        unscored: Các khoảng `(cấp, trang đầu, trang cuối)` không chấm ở cả hai phía -- ví dụ cấp 3
            dưới *Hoạt động thực hành trải nghiệm*, nơi cây vàng không đánh nhãn.

    Returns:
        Một `LevelScore` mỗi cấp 1..3.
    """

    def counted(node: TreeNode) -> bool:
        return not any(
            node.level == level and first <= node.page <= last for level, first, last in unscored
        )

    out = []
    for level in (1, 2, 3):
        wanted = [node for node in gold if node.level == level and counted(node)]
        offered = [node for node in built if node.level == level and counted(node)]
        # Ghép theo cặp **giống nhất trước**, không theo thứ tự cây vàng: một nút vàng mà OCR làm
        # mất không được giành nút của hàng xóm chỉ vì nó đứng trước (Bài 1, mục 1 và mục 2).
        pairs = sorted(
            (
                (similarity(truth.title, guess.title), gold_index, built_index)
                for gold_index, truth in enumerate(wanted)
                for built_index, guess in enumerate(offered)
                if abs(guess.page - truth.page) <= PAGE_SLACK
            ),
            reverse=True,
        )
        taken_gold: set[int] = set()
        taken_built: set[int] = set()
        matched = same_page = 0
        for alike, gold_index, built_index in pairs:
            if alike < MIN_SIMILARITY:
                break
            if gold_index in taken_gold or built_index in taken_built:
                continue
            taken_gold.add(gold_index)
            taken_built.add(built_index)
            matched += 1
            same_page += offered[built_index].page == wanted[gold_index].page
        out.append(LevelScore(level, len(wanted), len(offered), matched, same_page))
    return out
