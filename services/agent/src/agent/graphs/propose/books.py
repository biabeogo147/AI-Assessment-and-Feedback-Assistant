"""Lượt này có nói tới sách không, có tài liệu trong tầm không, có mở thư viện không."""

import re
import unicodedata

from agent import skills
from agent.graphs.propose.prompt import LIBRARY_SLOT
from contracts import NextStepRequested

# Chữ cho biết giáo viên đang nói về một tài liệu. *"Danh sách"* bị bỏ trước khi tìm: *"danh sách
# lớp"* không phải một cuốn sách.
_BOOK_WORDS = re.compile(
    r"\b(sách|tài liệu|tệp|file|giáo trình|giáo án|đề cương|bài giảng|cuốn|quyển|pdf|docx|"
    r"slide|sgk)\b",
    re.IGNORECASE,
)


_NOT_A_BOOK = re.compile(r"danh\s+sách", re.IGNORECASE)


# Lời **từ chối** sách: *"ko cần sách"*, *"không dùng tài liệu"*, *"khỏi sách nhé"*. Giáo viên Việt
# gõ tắt *ko*, *k*, *hok* rất thường; bỏ cả cụm trước khi tìm chữ sách (plan `backlog-tier-1`).
_NO_BOOK = re.compile(
    r"\b(?:không|ko|k|hok|hông|khỏi|chẳng|chả)\s+(?:cần\s+|dùng\s+|lấy\s+|theo\s+|có\s+)?"
    r"(?:sách|tài liệu|tệp|file|giáo trình|sgk|cuốn|quyển)\b",
    re.IGNORECASE,
)


# Tool đọc tài liệu; kết quả của một trong số chúng trong lịch sử là *đoạn chat đang chọn sách*.
# Cùng bộ với `teacher_chat._DOCUMENT_READS` bên BE.
DOCUMENT_READS = frozenset({"list_documents", "list_chapters", "get_chapter", "read_section"})


def opens_library(request: NextStepRequested, chosen: tuple[str, ...]) -> bool:
    """Lượt này có dòng mở thư viện (`LIBRARY`) không. Hàm thuần.

    Không chip, chưa đọc sách: lượt duy nhất mà mở thư viện là một bước có nghĩa. Chip chưa sẵn
    sàng thì không -- dòng báo chip đã dặn đừng soạn. Và chỉ khi một skill được chọn có chỗ trống
    cho dòng ấy, tức đang soạn đề.

    Args:
        request: Lượt đang hỏi.
        chosen: Tên các skill Jev chọn cho lượt này.

    Returns:
        True khi `compose` điền `LIBRARY` vào chỗ trống.
    """
    return (
        request.attached_document is None
        and not book_in_view(request)
        and any(tool.name == "list_documents" for tool in request.catalog)
        and _mentions_book(request)
        and any(LIBRARY_SLOT.search(skill.body) for skill in skills.named(chosen))
    )


def book_in_view(request: NextStepRequested) -> bool:
    """Lượt này có một cuốn sách để soạn theo không -- tức `BOOK_PROCEDURE` có được chèn không.

    Đọc **sự kiện**, không đọc catalog (review T2, `unbiased-model-text`). BE mở tool mục lục cho
    mọi lượt sau khi đoạn chat từng đọc tài liệu (`teacher_chat._read_documents_before`), nên
    *"`list_chapters` có trong catalog"* đúng cả ở một lượt soạn đề không dính gì tới sách -- và thủ
    tục sẽ bắt model đọc mục lục, hay bịa `document_id`.

    Có sách khi: chip sẵn sàng; hoặc, không có chip, lịch sử có kết quả của một tool đọc tài liệu
    mà **chưa** có plan nào nêu sau nó -- việc chọn sách còn dở (hỏi lại chương nào, giáo viên trả
    lời ở lượt sau). Plan đã nêu thì việc ấy đã xong; một đề mới không nhắc sách là đề không sách,
    còn giáo viên nhắc sách thì skill `soan-de` mở thư viện lại. Chip chưa sẵn sàng thì không: chưa
    có mục lục, và dòng báo chip đã dặn đừng soạn.

    Args:
        request: Lượt đang hỏi.

    Returns:
        True khi thủ tục sách áp dụng cho lượt này.
    """
    if request.attached_document is not None:
        return request.attached_document.state == "ready"
    for turn in reversed(request.history):
        if turn.kind == "plan":
            return False
        if turn.kind == "tool_result" and turn.tool_name in DOCUMENT_READS:
            return True
    return False


def _mentions_book(request: NextStepRequested) -> bool:
    """Giáo viên có nhắc tới một tài liệu, kể từ plan gần nhất, không.

    Mọi câu của giáo viên từ plan gần nhất, không chỉ câu cuối (review T3, `unbiased-model-text`):
    nhắc sách ở lượt này rồi trả lời *"lớp 8"* ở lượt sau thì việc soạn đề vẫn là việc soạn theo
    sách. Plan đã nêu thì việc ấy xong -- một đề mới không nhắc sách là đề không sách.

    Args:
        request: Lượt đang hỏi.

    Returns:
        True khi một câu ấy có một chữ trong `_BOOK_WORDS`, không tính *"danh sách"*.
    """
    for turn in reversed(request.history):
        if turn.kind == "plan":
            return False
        if turn.kind != "teacher":
            continue
        # NFC trước khi tìm: macOS gửi chữ có dấu dạng phân rã, "sách" phân rã không khớp (ADR-23).
        said = _NOT_A_BOOK.sub(" ", unicodedata.normalize("NFC", turn.text))
        said = _NO_BOOK.sub(" ", said)
        if _BOOK_WORDS.search(said):
            return True
    return False
