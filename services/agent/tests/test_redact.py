"""Khoá API không vào log của `agent` (Tier 1, 12/11/2026; lộ ra khi chuyển lab 11/11)."""

import io
import logging

import pytest

from agent.redact import Redacting, redact

_KEY = "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"


def test_a_configured_key_is_hidden_even_without_a_known_shape() -> None:
    secret = "jev-0f3a9c2b7d5e"

    assert secret not in redact(f"Jev từ chối khoá {secret}", (secret,))


def test_a_key_with_a_trailing_cr_is_hidden_by_its_clean_value() -> None:
    """Đúng ca lab: khoá trong `.env` dính `\\r`, thông báo lỗi in phần trước `\\r`."""
    shown = redact(f"Illegal header value b'{_KEY}\\r'", (_KEY + "\r",))

    assert _KEY not in shown
    assert "[đã che]" in shown


def test_known_key_shapes_are_hidden_when_not_configured() -> None:
    line = (
        f"x-api-key: {_KEY} · Authorization: Bearer abc.def-123456789 · "
        "headers=[(b'x-api-key', b'plainsecretvalue')]"
    )

    shown = redact(line)

    assert _KEY not in shown
    assert "abc.def-123456789" not in shown
    assert "plainsecretvalue" not in shown


def test_ordinary_words_are_left_alone() -> None:
    for line in (
        "propose_next_step xong sau 2,4 s, 8892 token, khoá dàn ý ở mục 3",
        "plan ask-the-document và risk-assessment-v2 đã đóng",
        "Bearer token expired",
    ):
        assert redact(line, ("", "short")) == line


@pytest.mark.asyncio
async def test_the_worker_startup_covers_the_handlers_arq_cli_adds(capsys) -> None:
    """Review pha 2: đúng thứ tự của `arq.cli` -- import module worker, rồi `dictConfig` cấu hình
    log của arq, rồi `startup`. Xoá dòng che trong `startup` thì test này đỏ."""
    import logging.config

    from arq.logs import default_log_config

    from agent import worker

    logging.config.dictConfig(default_log_config(False))
    await worker.startup({})
    logging.getLogger("arq.worker").error("job failed, ValueError: Illegal header b'%s'", _KEY)

    shown = capsys.readouterr()
    assert "job failed" in shown.out + shown.err
    assert _KEY not in shown.out + shown.err


def test_a_handler_arq_adds_after_import_is_hidden_too() -> None:
    """Review pha 1: `arq.cli` import module worker **rồi** mới `dictConfig`, gắn handler riêng
    cho logger `arq`. Gọi lại phép che lúc `startup` phải phủ cả handler ấy."""
    import logging.config

    from agent.redact import hide_secrets_in_logs

    out = io.StringIO()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "arq.standard": {"class": "logging.StreamHandler", "stream": out},
            },
            "loggers": {"arq_like": {"handlers": ["arq.standard"], "level": "INFO"}},
        }
    )
    logger = logging.getLogger("arq_like")
    logger.propagate = False
    hide_secrets_in_logs((_KEY,))
    try:
        logger.error("job failed, ValueError: Illegal header value b'%s'", _KEY)
    finally:
        logger.handlers.clear()

    assert "job failed" in out.getvalue()
    assert _KEY not in out.getvalue()


def test_the_traceback_of_a_logged_exception_is_hidden_too() -> None:
    """Che ở formatter: traceback chỉ thành chữ lúc formatter chạy."""
    out = io.StringIO()
    handler = logging.StreamHandler(out)
    handler.setFormatter(Redacting("%(levelname)s %(message)s", (_KEY,)))
    logger = logging.getLogger("test_redact")
    logger.addHandler(handler)
    logger.propagate = False
    try:
        raise ValueError(f"Illegal header value b'{_KEY}'")
    except ValueError:
        logger.exception("model call failed")
    finally:
        logger.removeHandler(handler)

    assert "model call failed" in out.getvalue()
    assert "ValueError" in out.getvalue()
    assert _KEY not in out.getvalue()
