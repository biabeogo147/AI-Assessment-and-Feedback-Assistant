"""Che khoá API trước khi một dòng log rời process.

Lab 11/11/2026: khoá model trong `.env` dính `\\r`, `httpcore` từ chối header ấy và đưa **nguyên giá
trị header** vào thông báo lỗi -- traceback ấy vào `docker compose logs`, tức khoá nằm trên đĩa máy
lab và trong mọi lần ai đó dán log đi hỏi. Che ở formatter, không ở `Filter`: traceback chỉ thành
chữ lúc formatter chạy, một `Filter` không thấy nó.
"""

import logging
import re
from collections.abc import Iterable

_HIDDEN = "[đã che]"

# Hình dạng khoá ai cũng nhận ra: `sk-…` của OpenAI và Anthropic (`sk-proj-…`, `sk-ant-…`), giá trị
# sau `Bearer`, và giá trị của header `x-api-key`. Lưới cho khoá **chưa** có trong cấu hình --
# khoá có trong cấu hình thì che theo đúng giá trị (`Redacting`).
# `sk-` phải đứng đầu một từ: *"ask-the-document"*, *"risk-assessment"* không phải khoá. Sau
# `Bearer` chỉ che một chuỗi đủ dài để là token -- *"Bearer token expired"* là chữ thường (review
# pha 1).
_SHAPES = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?<=Bearer )[^\s'\",)]{16,}", re.IGNORECASE),
    re.compile(r"(?<=x-api-key)(['\"]?\s*[:=,]\s*b?['\"]?)[^\s'\",)]+", re.IGNORECASE),
)

# Ngắn hơn chừng này thì không phải một khoá, và che nó là che bừa chữ thường trong log.
_SHORTEST_SECRET = 8


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Thay mọi khoá trong một đoạn chữ bằng `[đã che]`. Hàm thuần.

    Args:
        text: Một dòng log đã định dạng, có thể kèm traceback.
        secrets: Giá trị khoá đang cấu hình. Che theo giá trị trước, kể cả khi khoá không mang hình
            dạng quen nào; giá trị rỗng hay quá ngắn bị bỏ qua.

    Returns:
        Chữ đã che.
    """
    for secret in secrets:
        clean = secret.strip()
        if len(clean) >= _SHORTEST_SECRET:
            text = text.replace(clean, _HIDDEN)
    for shape in _SHAPES:
        if shape.groups:
            text = shape.sub(lambda found: found.group(1) + _HIDDEN, text)
        else:
            text = shape.sub(_HIDDEN, text)
    return text


class Redacting(logging.Formatter):
    """Formatter che khoá trên **cả dòng đã định dạng**, traceback lẫn `exc_text` đã cache."""

    def __init__(self, fmt: str, secrets: Iterable[str] = (), datefmt: str | None = None) -> None:
        super().__init__(fmt, datefmt)
        self._secrets = tuple(secrets)

    def format(self, record: logging.LogRecord) -> str:
        """Định dạng như thường rồi che.

        Args:
            record: Bản ghi log.

        Returns:
            Dòng log không còn khoá.
        """
        return redact(super().format(record), self._secrets)


def hide_secrets_in_logs(secrets: Iterable[str]) -> None:
    """Gắn `Redacting` vào mọi handler đang có -- của root **và** của mọi logger có handler riêng
    (`arq` gắn một cái qua `dictConfig`) --, giữ nguyên khuôn dòng và định dạng giờ của handler ấy.
    Gọi lại được: handler đã che thì chỉ nhận lại danh sách khoá.

    Hai giới hạn (review pha 2, plan `tier-1`): formatter dựng lại là kiểu `%` -- một handler dùng
    `style="{"` hay lớp Formatter riêng sẽ mất khuôn (nay chỉ có `basicConfig` và arq, đều `%`); và
    `logging.Formatter.format` cache `record.exc_text` **chưa che** trên bản ghi, nên một handler
    không bọc gắn **sau** lần gọi cuối vẫn in traceback thô. Gắn handler mới thì gọi lại hàm này.

    Args:
        secrets: Giá trị khoá đang cấu hình.

    Side effects:
        Thay formatter của các handler đang có.
    """
    kept = tuple(secrets)
    loggers = [logging.getLogger()] + [
        one for one in logging.Logger.manager.loggerDict.values() if isinstance(one, logging.Logger)
    ]
    for owner in loggers:
        for handler in owner.handlers:
            old = handler.formatter
            fmt = old._fmt if old is not None else None
            datefmt = old.datefmt if old is not None else None
            handler.setFormatter(Redacting(fmt or "%(message)s", kept, datefmt))
