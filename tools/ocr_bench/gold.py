"""Hình dạng của một trang nhãn vàng, và phép kiểm nó.

Nhãn vàng là thứ **duy nhất** nói cho bộ đo biết câu trả lời đúng là gì, nên một file nhãn méo
không được phép đi qua im lặng: nó sẽ kéo điểm xuống và trông y như một engine tệ. Mọi lỗi ở đây
là `GoldInvalid` kèm đường dẫn và chỗ sai, không phải một `KeyError` ở giữa một vòng lặp.

**Nhãn và ảnh đều nằm ngoài git** (`data/` trong `.gitignore`). Mười bốn cuốn SGK có bản quyền,
và một bộ nhãn không có sách đi kèm thì không ai chạy lại được bằng nó. Thứ commit được là
module này, thước đo, test của chúng, và bảng số trong plan.

`BlockKind` **import từ `document.ocr.model`**, không khai lại ở đây. Hai bản sao của một bảng
nhãn là một chỗ để lệch nhau, và nó sẽ lệch đúng vào lúc ai đó thêm một nhãn mới ở đúng một phía
-- lúc ấy bộ đo im lặng so hai thứ khác nhau và chấm engine 0 điểm cho một khối nó đọc đúng. Giá
trị của bảng ấy trùng từng chữ với nhãn PP-DocLayout phát ra.
"""

import json
import unicodedata
from pathlib import Path
from typing import NamedTuple

from document.ocr.model import BlockKind


class GoldInvalid(ValueError):
    """Một file nhãn không dùng được.

    Luôn mang đường dẫn và chỗ sai, vì người đọc lỗi này là người vừa đánh nhãn xong và cần biết
    phải sửa dòng nào.
    """


# Khối thuộc những loại này **không** mang chữ, nên một chuỗi rỗng ở đó là hợp lệ. Mọi loại khác
# mà rỗng là một lần đánh nhãn bỏ dở, và bộ đo phải kêu lên chứ không âm thầm cho 0 điểm.
_KINDS_WITHOUT_TEXT = frozenset({BlockKind.IMAGE, BlockKind.TABLE})


class GoldBlock(NamedTuple):
    """Một khối đã đánh nhãn.

    Attributes:
        kind: Loại khối.
        text: Chữ đọc được, chuẩn hoá NFC. Rỗng với `IMAGE` và `TABLE`.
        latex: LaTeX của công thức, chỉ có ở `FORMULA`. `None` ở mọi loại khác.
    """

    kind: BlockKind
    text: str
    latex: str | None


class GoldPage(NamedTuple):
    """Một trang đã đánh nhãn.

    Attributes:
        book: Mã cuốn sách, ví dụ `L6T1`.
        page: Số thứ tự trang trong **tệp PDF**, đếm từ 1.
        blocks: Các khối theo **thứ tự đọc**. Thứ tự của danh sách chính là nhãn cho phép đo thứ
            tự đọc, nên đảo hai phần tử ở đây là đổi câu trả lời đúng.
    """

    book: str
    page: int
    blocks: tuple[GoldBlock, ...]


def load_page(path: Path) -> GoldPage:
    """Đọc một file nhãn và kiểm nó.

    Mỏng có chủ ý: nó chỉ đọc byte rồi giao cho `parse_page`. Mọi **luật** về hình dạng nằm ở
    hàm kia, nơi không có filesystem nào -- nên lưới canh luật chạy được ở mọi máy, kể cả máy
    mà thư mục tạm của pytest bị khoá.

    Args:
        path: Đường dẫn tới file JSON.

    Returns:
        Trang đã đánh nhãn.

    Raises:
        GoldInvalid: Khi file không đọc được, thiếu trường, sai kiểu, hoặc mang một khối rỗng ở
            một loại lẽ ra phải có chữ.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldInvalid(f"{path.name}: không đọc được JSON: {exc}") from exc
    return parse_page(payload, path.name)


def parse_page(payload: object, where: str) -> GoldPage:
    """Kiểm một trang nhãn đã giải mã JSON.

    Args:
        payload: Đối tượng vừa đọc từ JSON.
        where: Tên file, chỉ để ghép vào thông báo lỗi. Người đọc lỗi vừa đánh nhãn năm mươi
            trang và cần biết phải sửa cái nào.

    Returns:
        Trang đã đánh nhãn.

    Raises:
        GoldInvalid: Khi thiếu trường, sai kiểu, hoặc một khối sai hình dạng.
    """
    path = where
    if not isinstance(payload, dict):
        raise GoldInvalid(f"{path}: gốc phải là một object, không phải {type(payload).__name__}")

    book = payload.get("book")
    page = payload.get("page")
    raw_blocks = payload.get("blocks")
    if not isinstance(book, str) or not book:
        raise GoldInvalid(f"{path}: thiếu `book`")
    if not isinstance(page, int) or page < 1:
        raise GoldInvalid(f"{path}: `page` phải là số nguyên từ 1, gặp {page!r}")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise GoldInvalid(f"{path}: `blocks` phải là một danh sách không rỗng")

    blocks = tuple(_block(where, at, one) for at, one in enumerate(raw_blocks))
    return GoldPage(book, page, blocks)


def _block(where: str, at: int, raw: object) -> GoldBlock:
    """Kiểm một phần tử của `blocks`.

    Args:
        where: Tên file, chỉ để ghép vào thông báo lỗi.
        at: Vị trí trong danh sách, đếm từ 0.
        raw: Phần tử thô vừa đọc từ JSON.

    Returns:
        Khối đã kiểm, chữ đã chuẩn hoá NFC.

    Raises:
        GoldInvalid: Khi khối sai hình dạng.
    """
    where = f"{where}: blocks[{at}]"
    if not isinstance(raw, dict):
        raise GoldInvalid(f"{where} phải là một object")

    try:
        kind = BlockKind(raw.get("kind"))
    except ValueError as exc:
        known = ", ".join(sorted(one.value for one in BlockKind))
        raise GoldInvalid(f"{where}: `kind` lạ {raw.get('kind')!r}. Chỉ nhận: {known}") from exc

    text = raw.get("text", "")
    if not isinstance(text, str):
        raise GoldInvalid(f"{where}: `text` phải là chuỗi")
    if not text.strip() and kind not in _KINDS_WITHOUT_TEXT:
        raise GoldInvalid(f"{where}: khối `{kind.value}` rỗng chữ -- đánh nhãn bỏ dở?")

    latex = raw.get("latex")
    if latex is not None and not isinstance(latex, str):
        raise GoldInvalid(f"{where}: `latex` phải là chuỗi hoặc vắng mặt")
    if kind is BlockKind.FORMULA and not (latex or "").strip():
        raise GoldInvalid(f"{where}: khối `formula` phải có `latex`")
    if kind is not BlockKind.FORMULA and latex is not None:
        raise GoldInvalid(f"{where}: chỉ khối `formula` được mang `latex`")

    return GoldBlock(kind, _nfc(text), _nfc(latex) if latex is not None else None)


def _nfc(text: str) -> str:
    """Chuẩn hoá Unicode về NFC.

    Tiếng Việt có hai cách viết cùng một chữ -- `ế` dựng sẵn và `ế` tổ hợp -- và chúng **khác
    nhau từng byte**. Không chuẩn hoá thì một engine đọc đúng hoàn toàn vẫn ăn một CER khác 0,
    và không ai nhìn ra vì trên màn hình hai chuỗi giống hệt nhau.

    Args:
        text: Chuỗi bất kỳ.

    Returns:
        Chuỗi đã chuẩn hoá NFC.
    """
    return unicodedata.normalize("NFC", text)


def load_book(folder: Path, book: str) -> list[GoldPage]:
    """Đọc mọi trang nhãn của một cuốn, sắp theo số trang.

    Args:
        folder: Thư mục chứa các file `<book>_p###.json`.
        book: Mã cuốn sách.

    Returns:
        Các trang đã kiểm, sắp tăng dần theo `page`.

    Raises:
        GoldInvalid: Khi thư mục không có file nào, khi một file hỏng, hoặc khi hai file cùng nói
            về một trang -- ca cuối là dấu của một lần chép tay, và nó sẽ đếm một trang hai lần.
    """
    found = sorted(folder.glob(f"{book}_p*.json"))
    if not found:
        raise GoldInvalid(f"{folder}: không có file nhãn nào cho {book}")
    return collect([(path.name, load_page(path)) for path in found])


def collect(labelled: list[tuple[str, GoldPage]]) -> list[GoldPage]:
    """Sắp các trang theo số trang, và từ chối hai file cùng nói về một trang.

    Sắp theo **con số** chứ không theo tên file: hai thứ ấy trùng nhau khi số trang được đệm 0
    và khác nhau ngay khi không.

    Args:
        labelled: Cặp (tên file, trang đã kiểm).

    Returns:
        Các trang, sắp tăng dần theo `page`.

    Raises:
        GoldInvalid: Khi danh sách rỗng, hoặc hai file cùng nói về một trang -- ca sau là dấu của
            một lần chép tay, và nó sẽ đếm trang ấy hai lần.
    """
    if not labelled:
        raise GoldInvalid("không có file nhãn nào")

    seen: dict[int, str] = {}
    for name, one in labelled:
        if one.page in seen:
            raise GoldInvalid(f"{name} và {seen[one.page]} cùng nói về trang {one.page}")
        seen[one.page] = name
    return sorted((one for _, one in labelled), key=lambda one: one.page)
