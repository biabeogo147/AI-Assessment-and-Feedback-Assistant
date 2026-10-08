"""Hai luật của lúc INGEST khởi động, và cả hai từng không có lưới nào.

Plan 2c sinh ra vì process worker làm khác process API mà không chỗ nào nói ra. Hai chỗ khác
ấy nằm đúng trong `startup`, nên chúng được canh ở đây:

1. **Mức log đọc từ `Settings`, không viết cứng.** Bản trước của worker — hồi nó còn là
   `be/worker.py` — gọi `logging.basicConfig(level=logging.INFO)`, nên `LOG_LEVEL=WARNING`
   làm process API im nhưng worker vẫn nói. Không cổng nào bắt được, vì không có cổng nào.
2. **`check_schema`, và không bao giờ `prepare_schema`.** Dựng schema là việc của process API;
   một worker chạy êm trên schema lệch sẽ hỏng ở lần `UPDATE` đầu tiên, cách rất xa nguyên
   nhân.

Khuôn lấy từ `services/be/tests/test_logging_config.py`, kể cả test đọc cây cú pháp, và lý do
của nó thì đúng y nguyên ở đây: hai test đầu đo **hàm**, test sau đo **lời gọi**. Xoá dòng gọi
khỏi `startup` thì hàm vẫn đúng, chỉ là không ai gọi — và một hàm cấu hình không ai gọi hỏng
hệt một hàm viết sai, nhưng không test nào đỏ.
"""

import ast
import logging
import pathlib

from ingest.worker import _hear_our_own_loggers

_WORKER = pathlib.Path("services/ingest/src/ingest/worker.py")


def _startup_tree() -> ast.AsyncFunctionDef:
    """Cây cú pháp của `startup`.

    Đọc cây chứ không grep: một lần grep `"_hear_our_own_loggers"` khớp cả chính `def` của
    nó, nên nó xanh với một hàm không ai gọi — đúng cái nó định chặn.

    Returns:
        Node của `async def startup`.
    """
    tree = ast.parse(_WORKER.read_text(encoding="utf-8"))
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "startup"
    )


def test_an_ingest_logger_has_somewhere_to_write() -> None:
    """Sau khi cấu hình, một dòng của `ingest.handlers` thật sự tới được một handler.

    Không dùng `caplog`: nó gắn handler của chính nó lên root và tự nâng mức, nên nó sẽ bắt
    được dòng log kể cả khi hàm này không làm gì cả — tức nó đo pytest, không đo ta.
    """
    _hear_our_own_loggers("INFO")

    caught: list[str] = []

    class Catching(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            caught.append(record.getMessage())

    ours = logging.getLogger("ingest")
    listening = Catching()
    ours.addHandler(listening)
    try:
        logging.getLogger("ingest.handlers").info("document=abc is now ready")
    finally:
        ours.removeHandler(listening)

    assert caught == ["document=abc is now ready"]


def test_the_level_comes_from_the_setting_not_from_a_hardcoded_info() -> None:
    """Mức phải **đọc từ tham số**, và đây là nửa chữa đúng lỗi đã đo.

    `basicConfig(level=logging.INFO)` của bản cũ đi qua được test trên — logger vẫn có chỗ
    ghi — nhưng `LOG_LEVEL=WARNING` thì không có tác dụng gì. Test này đỏ vào đúng ngày ai đó
    viết cứng một mức trở lại.
    """
    _hear_our_own_loggers("WARNING")
    ours = logging.getLogger("ingest")
    assert ours.handlers
    assert ours.getEffectiveLevel() == logging.WARNING

    _hear_our_own_loggers("INFO")
    assert ours.getEffectiveLevel() == logging.INFO


def test_startup_actually_calls_it_with_the_configured_level() -> None:
    """Đo **lời gọi**, và nó khẳng định cả tham số.

    Gọi mà viết cứng `"INFO"` thì `Settings.log_level` thành một field không có tác dụng —
    đúng tình trạng của `be/worker.py` trước plan 2c, chỉ khác là lúc ấy nó không gọi gì cả.
    """
    calls = [
        node
        for node in ast.walk(_startup_tree())
        if isinstance(node, ast.Call)
        if isinstance(node.func, ast.Name) and node.func.id == "_hear_our_own_loggers"
    ]

    assert len(calls) == 1
    (passed,) = calls[0].args
    assert isinstance(passed, ast.Attribute)
    assert passed.attr == "log_level"


def test_startup_checks_the_schema_and_never_builds_it() -> None:
    """`check_schema` có người gọi, `prepare_schema` thì không — ở đây, và ở cả module.

    Hai nửa, và nửa thứ hai là nửa đáng giá: `prepare_schema` nay nằm trong một package dùng
    chung, nên nó là thứ service này **import được**. Luật *API dựng, worker kiểm* chỉ sống
    trong văn bản cho tới khi có dòng dưới.

    Bỏ `await check_schema(engine)` khỏi `startup` thì worker khởi động êm trên một schema
    lệch rồi hỏng ở lần `UPDATE` đầu tiên — một lỗi cách rất xa nguyên nhân, và đó đúng là
    thứ `check_schema` sinh ra để không có.
    """
    called = {
        node.func.id
        for node in ast.walk(_startup_tree())
        if isinstance(node, ast.Call)
        if isinstance(node.func, ast.Name)
    }
    assert "check_schema" in called


def test_the_worker_takes_nothing_from_schema_ddl_but_check_schema() -> None:
    """Chỉ `check_schema`, và **chỉ dưới cái tên ấy**.

    Đây là nửa mạnh của luật, và nó mạnh vì nó liệt kê cái **được phép** chứ không liệt kê cái
    bị cấm. Bản đầu của test này khẳng định `"prepare_schema" not in ...`, và một lượt review
    đã chỉ ra bốn đường vòng đi qua được — hai trong số đó không phải mẹo:

    - `from schema.ddl import prepare_schema as build` rồi `await build(engine)`: cái tên bị
      cấm không xuất hiện ở đâu cả.
    - `await reset_schema(engine)`: nó gọi `prepare_schema` hộ, **và `DROP SCHEMA public
      CASCADE` trước đó**. Một worker gọi nhầm hàm ấy xoá sạch database, im lặng, và bản đầu
      của test này cho nó đi qua ngay dưới mũi mình.

    Liệt kê cái được phép thì cả bốn đường vòng đâm vào cùng một dòng assert, và một đường
    vòng thứ năm chưa ai nghĩ ra cũng vậy. `tools/check_contract.py` canh cùng luật này từ
    phía repo, theo **hành vi** (`metadata.create_all`) chứ không theo tên; hai cái bù nhau.
    """
    whole = ast.parse(_WORKER.read_text(encoding="utf-8"))
    taken = {
        (alias.name, alias.asname)
        for node in ast.walk(whole)
        if isinstance(node, ast.ImportFrom) and node.module == "schema.ddl"
        for alias in node.names
    }
    assert taken == {("check_schema", None)}

    # Và không lấy cả module để đi vòng bằng thuộc tính: `import schema.ddl` rồi
    # `schema.ddl.prepare_schema(...)`.
    assert not [
        alias.name
        for node in ast.walk(whole)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.startswith("schema")
    ]
