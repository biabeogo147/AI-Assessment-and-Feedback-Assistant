"""Log của `be.*` có đi ra được màn hình hay không.

Một hệ thống ghi log mà không ai bật thì không phải ghi log, nó là chú thích. Trước đợt
này BE **không cấu hình logging gì cả**: uvicorn dựng logger của chính nó, nên
`logging.getLogger("be.drafting")` không có handler nào và mọi `logger.info` của chúng ta
rơi vào hư không.

Cái giá đo được ngày 06/10/2026: một đề 3 câu về 2 câu, và dòng nói **vì sao** —
*"đề trùng một câu đã có"* — không tồn tại ở bất cứ đâu. Phải đọc bốn nhánh của `harvest`
rồi loại trừ mới đoán ra nguyên nhân.
"""

import ast
import logging
import pathlib

from be.main import _hear_our_own_loggers


def test_a_be_logger_has_somewhere_to_write() -> None:
    """Sau khi cấu hình, một dòng của `be.drafting` thật sự tới được một handler.

    Không dùng `caplog`: nó gắn handler của chính nó lên root và tự nâng mức, nên nó sẽ
    bắt được dòng log kể cả khi hàm này không làm gì cả — tức nó đo pytest, không đo ta.
    Chỗ này gắn một handler riêng vào đúng chỗ cấu hình nhắm tới và đọc những gì rơi vào
    đó.
    """
    _hear_our_own_loggers("INFO")

    caught: list[str] = []

    class Catching(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            caught.append(record.getMessage())

    ours = logging.getLogger("be")
    listening = Catching()
    ours.addHandler(listening)
    try:
        logging.getLogger("be.drafting").info("đề trùng một câu đã có")
    finally:
        ours.removeHandler(listening)

    assert caught == ["đề trùng một câu đã có"]


def test_the_be_tree_is_configured_at_info_not_warning() -> None:
    """Mức phải là `INFO`, không phải mặc định `WARNING` thừa hưởng từ root.

    Đây là nửa còn lại, và nó là nửa dễ mất. Một logger **có** handler mà mức ở `WARNING`
    thì vẫn ăn mất đúng những dòng nói vì sao một câu hỏi bị loại -- tức vẫn đúng cái
    hỏng mà cấu hình này sinh ra để chữa. Một đột biến đổi `INFO` thành `WARNING` phải
    đỏ ở đây.
    """
    _hear_our_own_loggers("INFO")

    ours = logging.getLogger("be")
    assert ours.handlers
    assert ours.getEffectiveLevel() <= logging.INFO
    # Và mức đọc từ tham số, không viết cứng: `Settings.log_level` phải thật sự có tác dụng.
    _hear_our_own_loggers("WARNING")
    assert ours.getEffectiveLevel() == logging.WARNING
    _hear_our_own_loggers("INFO")


def test_the_lifespan_actually_calls_it_with_the_configured_level() -> None:
    """Hai test trên đo **hàm**; test này đo **lời gọi**, và thiếu nó thì hàm là chữ chết.

    Xoá dòng ấy khỏi `lifespan` thì cả hai test trên vẫn xanh — hàm vẫn đúng, chỉ là không
    ai gọi — và BE quay về đúng tình trạng im lặng mà Pha 3 sinh ra để chữa. Một hàm cấu
    hình không ai gọi hỏng hệt như một hàm cấu hình viết sai, nhưng không test nào đỏ.

    Đọc cây cú pháp chứ không grep: một lần grep `"_hear_our_own_loggers"` khớp cả chính
    `def` của nó, nên nó xanh với một hàm không ai gọi — đúng cái nó định chặn. Và nó
    khẳng định cả **tham số**: gọi mà viết cứng `"INFO"` thì `Settings.log_level` thành
    một field không có tác dụng.
    """
    tree = ast.parse(pathlib.Path("services/be/src/be/main.py").read_text(encoding="utf-8"))
    inside = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan"
    )
    calls = [
        node
        for node in ast.walk(inside)
        if isinstance(node, ast.Call)
        if isinstance(node.func, ast.Name) and node.func.id == "_hear_our_own_loggers"
    ]

    assert len(calls) == 1
    (passed,) = calls[0].args
    assert isinstance(passed, ast.Attribute)
    assert passed.attr == "log_level"
