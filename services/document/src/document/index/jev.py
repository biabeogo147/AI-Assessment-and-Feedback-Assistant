"""Jev (TypeSafe AI) xếp vai trò và cấp cho từng ứng viên. Module duy nhất import `typesafe_sdk`.

**Một lời gọi mỗi ứng viên, hai câu `choice`** (D1 của plan 3c). Jev chạy mọi câu của một lời gọi
song song và độc lập trên cùng một `state`, nên câu thứ hai gần như miễn phí -- và mỗi câu phải tự
đứng được: câu `level` không biết câu `role` trả gì.

Bốn quyết định đến từ jaggedness đo được của `jev-1.13` (plan 3c, *Khảo sát Jev*):

- `instructions` và `criteria` viết **tiếng Anh** -- Jev kém hơn với ngôn ngữ khác; chữ của khối
  vẫn tiếng Việt, vì đó là dữ liệu chứ không phải câu hỏi.
- **Lựa chọn an toàn đứng đầu** (`not_heading`, `deeper`) -- Jev nghiêng về lựa chọn đầu tiên.
- `state` là **một khối và ngữ cảnh hẹp**, không phải cả trang -- state to làm Jev lạc.
- Không số nào phải so: vị trí kể bằng lời, thứ tự nhãn số do `assemble` canh.

**Credential được truyền vào**, như `agent/llm.py`: SDK tự đọc `TYPESAFE_API_KEY`, còn repo này giữ
khoá ở `JEV_API_KEY` trong `.env`, đọc qua `Settings` -- thứ không bao giờ tới `os.environ`.
"""

import asyncio
import logging
from dataclasses import dataclass

from typesafe_sdk import AsyncTypeSafeClient, Choice, RetryPolicy, TypeSafeError

from contracts import DecidedBy
from document.index.features import Candidate
from document.index.rules import (
    ACTIVITY_LABEL,
    BOOK_SECTION,
    DEEPER,
    NOT_HEADING,
    NUMBERED_EXERCISE,
    ROLES,
    RUNNING_HEADER,
    Decision,
)

logger = logging.getLogger(__name__)

_ROLE_INSTRUCTIONS = (
    "The state describes one block of text that OCR read from a page of a document, usually a "
    "Vietnamese school textbook. Decide what this block is. The block text is in `block.text`; "
    "`open_path` lists the section titles that are open just before it."
)
_ROLE_CRITERIA = {
    NOT_HEADING: (
        "Body text, a sentence, a question, an instruction, a caption, a formula or a list item: "
        "anything that is not a title."
    ),
    ACTIVITY_LABEL: (
        "A short label of a recurring textbook activity or box, not a section of the book: e.g. "
        "'Ví dụ 1', 'Luyện tập 2', 'Vận dụng', 'HĐ1', 'Giải', 'Chú ý', 'Nhận xét', 'Thực hành', "
        "'Tranh luận', 'EM CÓ BIẾT?', 'KHÁI NIỆM, THUẬT NGỮ', 'KIẾN THỨC, KĨ NĂNG', 'BÀI TẬP', "
        "'MỤC TIÊU', 'Chuẩn bị'."
    ),
    # Plan 4c T4: ví dụ là khuôn -- số bài tập rồi một động từ yêu cầu -- không phải câu của một
    # chương. Bản trước chép *"Cho hai tập hợp"* nguyên văn từ SGK Toán 6.
    NUMBERED_EXERCISE: (
        "The start of a numbered exercise or problem that asks the reader to do something, e.g. "
        "'1.1. Cho ...', '2.15 Tính ...', '3.4 Tìm ...'."
    ),
    RUNNING_HEADER: (
        "A running header or footer, a page number, the book or series name, a publisher line, or "
        "front or back matter such as 'LỜI NÓI ĐẦU', 'MỤC LỤC', 'BẢNG TRA CỨU THUẬT NGỮ'."
    ),
    # Plan 4c T4: mục trong bài là chỗ trống `<...>`; bản trước dùng *"1. HỆ THẬP PHÂN"* của SGK
    # Toán 6 tập 1.
    BOOK_SECTION: (
        "The title of a part of the book's table of contents: a chapter or part, a lesson "
        "('Bài 3 ...' or an unnumbered lesson title in capitals), a review lesson ('LUYỆN TẬP "
        "CHUNG', 'BÀI TẬP CUỐI CHƯƠNG'), or a numbered section inside a lesson ('1. <TITLE IN "
        "CAPITALS>')."
    ),
}

_LEVEL_INSTRUCTIONS = (
    "Assume the block in `block.text` is a title in the book's table of contents, which has at "
    "most three levels. How deep is it? Compare it with the titles in `open_path`."
)
_LEVELS = {"deeper": DEEPER, "level_3": 3, "level_2": 2, "level_1": 1}
_LEVEL_CRITERIA = {
    # Plan 4c T4: ví dụ chỉ tả định dạng -- tên mục là chỗ trống `<...>`, tiêu đề con là một câu
    # mô tả kiểu chữ -- không phải tên mục của một chương Toán. Bản trước dùng *"1. HỆ THẬP PHÂN"*,
    # *"2. SỐ LA MÃ"* (hai mục) và tiêu đề con *"Cách ghi số tự nhiên trong hệ thập phân"*, đều của
    # SGK Toán 6 tập 1, cuốn cây vàng duy nhất của `pageindex_bench` -- và Jev bám nguyên văn: gỡ ví
    # dụ ấy thì chính tiêu đề con ấy lật từ `deeper` sang `level_3` ở `jev@0` (plan 4c, T4).
    "deeper": (
        "A smaller subheading inside a numbered section, or anything numbered deeper than three "
        "levels: e.g. an unnumbered heading in sentence case under a numbered section, "
        "'Hoạt động 1', 'a) ...', 'I.1.1.1'."
    ),
    "level_3": (
        "A numbered section inside a lesson: '1. <TITLE IN CAPITALS>', '2. <TITLE IN "
        "CAPITALS>', or numbering like 'I.1.1' or 'A.I.1'."
    ),
    "level_2": (
        "A unit directly under a chapter: a lesson ('Bài 3 ...' or a capitalised lesson title), "
        "'LUYỆN TẬP CHUNG', 'BÀI TẬP CUỐI CHƯƠNG ...', an activity project, or numbering "
        "like 'I.1' or 'A.I'."
    ),
    "level_1": (
        "A chapter or a major part of the book: 'CHƯƠNG I ...', 'PHẦN A', 'I.', 'A.', or a part "
        "such as 'HOẠT ĐỘNG THỰC HÀNH TRẢI NGHIỆM'."
    ),
}

_QUESTIONS = {
    "role": Choice(instructions=_ROLE_INSTRUCTIONS, criteria=_ROLE_CRITERIA),
    "level": Choice(instructions=_LEVEL_INSTRUCTIONS, criteria=_LEVEL_CRITERIA),
}

# Trần chữ của khối gửi đi: một tiêu đề dài nhất ~120 ký tự, phần dư chỉ là token.
_TEXT_CHARS = 160


class JevUnavailable(RuntimeError):
    """Jev không trả lời được sau khi SDK đã tự retry. Người gọi đi đường luật (D5)."""


@dataclass(frozen=True)
class JevRun:
    """Kết quả một lượt hỏi Jev cho cả tài liệu.

    Attributes:
        decisions: Một quyết định mỗi ứng viên, cùng thứ tự.
        tokens: Tổng token vào.
        model: Phiên bản Jev đã trả lời (`jev-1.13.0`).
    """

    decisions: list[Decision]
    tokens: int
    model: str | None


def state_of(candidate: Candidate, open_path: dict[str, str]) -> dict:
    """`state` gửi Jev cho một ứng viên. Hàm thuần.

    Args:
        candidate: Ứng viên.
        open_path: Tiêu đề đang mở ở từng cấp ngay trước ứng viên, khoá `level_1`..`level_3`.

    Returns:
        Một object nhỏ: khối, nhãn số, mức lặp, đường đang mở, chữ kế tiếp, trang.
    """
    block = {
        "text": candidate.unit.text.strip()[:_TEXT_CHARS],
        "ocr_label": candidate.unit.kind,
        "position": candidate.position,
        "repeated": candidate.repeated,
    }
    if candidate.markdown_level:
        block["markdown_heading_level"] = "#" * candidate.markdown_level
    return {
        "block": block,
        "numbering": candidate.numbering.label if candidate.numbering else None,
        "open_path": open_path,
        "next_text": candidate.next_text,
        "page": f"{candidate.unit.ref.page} of {candidate.page_count}",
    }


def decision_from(role: dict[str, float], level: dict[str, float], confidences: tuple) -> Decision:
    """Dựng `Decision` từ hai phân phối Jev trả. Hàm thuần.

    Args:
        role: Phân phối của câu `role`.
        level: Phân phối của câu `level`.
        confidences: `(confidence của role, confidence của level)`.

    Returns:
        Quyết định, `decided_by = JEV`.
    """
    chosen_role = max(role, key=role.__getitem__)
    chosen_level = max(level, key=level.__getitem__)
    if chosen_role not in ROLES or chosen_level not in _LEVELS:
        raise KeyError(f"unknown choice {chosen_role!r} / {chosen_level!r}")
    is_section = chosen_role == BOOK_SECTION
    confidence = min(confidences) if is_section else confidences[0]
    return Decision(
        role=chosen_role,
        level=_LEVELS[chosen_level] if is_section else None,
        confidence=float(confidence),
        decided_by=DecidedBy.JEV,
        role_probabilities=dict(role),
        level_probabilities=dict(level),
    )


class JevClassifier:
    """Một client Jev, dùng lại cho mọi ứng viên của một job.

    Attributes:
        _client: Client async của TypeSafe.
        _limit: Số lời gọi đang bay cùng lúc.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        concurrency: int,
        timeout: float,
        limit: asyncio.Semaphore | None = None,
    ):
        """Dựng client. Chưa gọi mạng.

        Args:
            api_key: Khoá Jev, từ `Settings`.
            model: Phiên bản ghim, ví dụ `jev-1.13.0`.
            concurrency: Số lời gọi song song, khi không có `limit` dùng chung.
            timeout: Trần giây cho một lời gọi.
            limit: Semaphore **của cả worker** (`index_worker` dựng một cái lúc khởi động): bốn job
                song song mà mỗi job tự mở `concurrency` lời gọi là 64 lời gọi cùng lúc, sát rate
                limit mà bên thứ ba ghi (review Task 4). `None` thì mỗi client một cái riêng.
        """
        self._client = AsyncTypeSafeClient(
            api_key=api_key, model=model, timeout=timeout, retry=RetryPolicy(max_retries=3)
        )
        self._limit = limit or asyncio.Semaphore(concurrency)

    async def decide_all(self, states: list[dict]) -> JevRun:
        """Hỏi Jev cho mọi ứng viên.

        Args:
            states: Một `state_of(...)` mỗi ứng viên.

        Returns:
            Các quyết định, cùng thứ tự với `states`.

        Raises:
            JevUnavailable: Khi một lời gọi hỏng sau retry. Không trả nửa cây: luật quyết cả cây.
        """
        # `TaskGroup`, không `gather`: một lời gọi hỏng thì **huỷ** mọi lời gọi còn bay -- `gather`
        # để ~490 lời gọi kia tiếp tục trả tiền và retry trên một client sắp đóng (review Task 3).
        try:
            async with asyncio.TaskGroup() as group:
                tasks = [group.create_task(self._ask(state)) for state in states]
        except* JevUnavailable as failed:
            raise failed.exceptions[0] from None
        answers = [task.result() for task in tasks]
        decisions = [decision for decision, _, _ in answers]
        tokens = sum(used for _, used, _ in answers)
        model = next((name for _, _, name in answers if name), None)
        return JevRun(decisions, tokens, model)

    async def _ask(self, state: dict) -> tuple[Decision, int, str | None]:
        async with self._limit:
            try:
                response = await self._client.system_one(state=state, questions=_QUESTIONS)
            except TypeSafeError as exc:
                # Gồm cả timeout và lỗi kết nối: SDK dịch `httpx` thành lớp con của `TypeSafeError`.
                logger.warning("jev could not answer: %s", exc)
                raise JevUnavailable(str(exc)) from exc
        try:
            role, level = response.answers["role"], response.answers["level"]
            decision = decision_from(
                dict(role.probabilities),
                dict(level.probabilities),
                (role.confidence, level.confidence),
            )
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            # Một câu trả lời thiếu câu hỏi, phân phối rỗng, hay khoá lạ: không đoán bù, cả cây
            # đi đường luật -- cùng một đường lùi với Jev không với tới được.
            raise JevUnavailable(f"jev answered in an unexpected shape: {exc!r}") from exc
        used = (response.usage.input_tokens or 0) if response.usage else 0
        return decision, used, response.model

    async def aclose(self) -> None:
        """Đóng client."""
        await self._client.aclose()


def open_paths(
    candidates: list[Candidate], provisional: list[Decision], chapters: dict[int, str]
) -> list[dict[str, str]]:
    """Tiêu đề đang mở ngay trước mỗi ứng viên, theo quyết định **tạm** của luật. Hàm thuần.

    Jev hỏi song song, nên không ứng viên nào biết Jev trả gì cho ứng viên trước nó. Đường mở dựng
    từ luật -- rẻ, tất định, và đủ để Jev thấy *"đang ở trong Bài 2, mục 1"*.

    Args:
        candidates: Các ứng viên, thứ tự đọc.
        provisional: Quyết định của luật cho từng ứng viên.
        chapters: Trang mở chương → tên chương (từ banner), để đường mở có cấp 1 trên SGK.

    Returns:
        Một dict `level_1`..`level_3` mỗi ứng viên; cấp chưa mở thì vắng mặt.
    """
    opened: dict[int, str] = {}
    out = []
    for candidate, decision in zip(candidates, provisional, strict=True):
        chapter = _chapter_at(chapters, candidate.unit.ref.page)
        if chapter and opened.get(1) != chapter:
            opened = {1: chapter}
        out.append({f"level_{level}": title for level, title in sorted(opened.items())})
        if decision.is_node and decision.level is not None:
            opened = {key: value for key, value in opened.items() if key < decision.level}
            opened[decision.level] = candidate.unit.text.strip()[:_TEXT_CHARS]
    return out


def _chapter_at(chapters: dict[int, str], page: int) -> str | None:
    """Chương chứa một trang: banner gần nhất không sau trang ấy.

    Args:
        chapters: Trang mở chương → tên.
        page: Trang.

    Returns:
        Tên chương, `None` khi trang đứng trước chương đầu.
    """
    starts = [start for start in chapters if start <= page]
    return chapters[max(starts)] if starts else None
