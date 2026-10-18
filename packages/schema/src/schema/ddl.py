"""Câu lệnh về schema: dựng nó, đối chiếu nó, dựng lại nó.

Bảng được tạo từ metadata của model lúc startup chứ không qua công cụ migration: schema này
chưa có dữ liệu nào đã deploy, nên thêm Alembic vào lúc này là dựng nghi lễ quanh một file
chưa ai phải sửa tới lần thứ hai. Ngay khi có dữ liệu thật, cái đánh đổi đó đảo chiều --
ADR-21 đã ghi migration là một khoản chi mà dự án này nhận lấy.

Ba hàm này ở **cùng chỗ với metadata**, không ở trong một service, và lý do đọc được ngay
trong thân `check_schema`: nó lặp trên `Base.metadata.tables`, nên nó không nói được gì nếu
nằm cách xa `Base`. Hai service cùng ghi database này, và nhân đôi phép đối chiếu ấy vào cả
hai là nhân đôi đúng cái thứ phải không bao giờ lệch.

**Ai được gọi cái gì** -- luật của `ingest-service-split`, và `tools/check_contract.py` canh nó:

- `prepare_schema` chỉ có **một** chỗ gọi trong code chạy thật: `be/main.py`. Process API sở
  hữu việc dựng. (Test thì gọi nó để tự dựng một sqlite trong bộ nhớ; đó là database của
  riêng test, không phải schema của ai.)
- `check_schema` thì process nào cũng gọi lúc khởi động, và chết ngay nếu lệch.

Vì sao không để process thứ hai dựng luôn: `create_all` không bao giờ `ALTER`, nên hai process
cùng dựng là hai process cùng tin mình đúng về một schema chỉ một bên nhìn đủ. Và một worker
khởi động được **trước** API, nên nó sẽ dựng theo bản metadata nó đang có.
"""

from sqlalchemy import Table, UniqueConstraint, inspect, text
from sqlalchemy.engine import Inspector
from sqlalchemy.ext.asyncio import AsyncEngine

from schema.models import Base


async def prepare_schema(engine: AsyncEngine) -> None:
    """Tạo mọi bảng còn thiếu.

    Args:
        engine: Engine để chạy lên.

    Side effects:
        Phát CREATE TABLE cho những bảng chưa tồn tại. Bảng đã có thì để nguyên,
        nên hàm này không bao giờ cứu được một cột đã đổi hình dạng.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


class SchemaDrifted(RuntimeError):
    """Database đang có không khớp với model trong code.

    Một exception riêng chứ không phải một `RuntimeError` trần, vì chỗ bắt nó là `main` và
    câu nó mang theo là câu một người đọc rồi gõ một lệnh.
    """


# Hai đường sửa. Nằm trong chuỗi lỗi vì một thông báo nói "schema lệch" mà không nói phải làm gì là
# một thông báo bắt người ta đi tìm. `ALTER` đứng trước: DB dev nay giữ dữ liệu thử tay, và
# `db-reset` xoá sạch nó (plan `wave-3-draft-panel`).
_HOW_TO_FIX = (
    "Giữ dữ liệu thì ALTER theo docs/local-development.md, mục *Database cũ hơn model*; "
    "dữ liệu bỏ được thì dựng lại bằng: .\\dev.ps1 db-reset"
)


def _model_uniques(table: Table) -> set[tuple[str, ...]]:
    """Mọi bộ cột model khai là unique trên một bảng: constraint và index unique.

    Cột `unique=True` không cần nhánh riêng: SQLAlchemy đã đổi nó thành một `UniqueConstraint`,
    hay một `Index` unique khi cột có thêm `index=True`. Bộ cột đã sắp, vì database không giữ thứ
    tự khai và hai phía phải so được với nhau.
    """
    found = {
        tuple(sorted(column.name for column in one.columns))
        for one in table.constraints
        if isinstance(one, UniqueConstraint)
    }
    found |= {
        tuple(sorted(column.name for column in one.columns)) for one in table.indexes if one.unique
    }
    return found


def _database_uniques(looker: Inspector, name: str) -> set[tuple[str, ...]]:
    """Mọi bộ cột database đang giữ unique trên một bảng: constraint và index unique.

    Index không mang tên cột (index trên biểu thức) bị bỏ qua: model không khai index nào như thế.
    """
    found = {tuple(sorted(one["column_names"])) for one in looker.get_unique_constraints(name)}
    for one in looker.get_indexes(name):
        columns = [column for column in one["column_names"] if column]
        if one.get("unique") and columns:
            found.add(tuple(sorted(columns)))
    return found


async def check_schema(engine: AsyncEngine) -> None:
    """Đối chiếu bảng thật với model, và **chết ngay** khi chúng lệch.

    `create_all` chỉ tạo bảng còn thiếu; nó không bao giờ `ALTER` một bảng đã có. Nên một
    model thêm cột rồi chạy trên database cũ sẽ khởi động sạch sẽ, rồi hỏng ở lần ghi đầu
    tiên — và hỏng dưới dạng một chuỗi lỗi 500 từ những route không liên quan gì tới nhau.
    Đúng chuyện đã xảy ra: `assessments` thiếu `teacher_id`, nên mọi lần tạo đề đều ném, và
    trên màn hình nó đọc ra như lỗi của khung chat.

    Kiểm **cột còn thiếu** và **ràng buộc unique lệch**, không kiểm kiểu hay index thường: đó là
    phần `create_all` không cứu được mà sai thì sai dữ liệu. Unique so theo **bộ cột**, hai chiều
    (plan `wave-3-draft-panel`):

    - model có mà database thiếu: một `UniqueConstraint("assessment_id", "order_index")` thêm sau
      khi bảng đã có thì chỉ có hiệu lực với ai xoá volume, và luật *"database phân xử"* chỉ đứng
      trên giấy;
    - database còn mà model đã bỏ: `teacher_conversations.teacher_id` từng chặn mọi lần mở đoạn
      chat thứ hai, dưới dạng một `IntegrityError` không ai đoán ra.

    So bộ cột chứ không so tên: tên do database tự đặt khi model không đặt. Partial index chỉ so
    bộ cột, không so điều kiện `WHERE` -- hai index cùng bộ cột khác điều kiện là ca chưa có trong
    model nào.

    Args:
        engine: Engine để soi.

    Raises:
        SchemaDrifted: Khi một bảng của model có cột mà database không có, hoặc khi bộ ràng buộc
            unique của hai bên khác nhau.

    Side effects:
        Đọc catalog của database.
    """

    def missing(connection) -> list[str]:
        looker = inspect(connection)
        found = set(looker.get_table_names())
        gaps = []
        for name, table in Base.metadata.tables.items():
            if name not in found:
                # Bảng chưa có là việc của `create_all`, không phải lệch.
                continue
            columns = {one["name"] for one in looker.get_columns(name)}
            for column in table.columns:
                if column.name not in columns:
                    gaps.append(f"thiếu cột {name}.{column.name}")
            wanted, held = _model_uniques(table), _database_uniques(looker, name)
            gaps += [f"thiếu unique {name}({', '.join(one)})" for one in sorted(wanted - held)]
            gaps += [f"thừa unique {name}({', '.join(one)})" for one in sorted(held - wanted)]
        return gaps

    async with engine.begin() as connection:
        gaps = await connection.run_sync(missing)

    if gaps:
        raise SchemaDrifted(
            "database lệch so với model: " + "; ".join(sorted(gaps)) + f". {_HOW_TO_FIX}"
        )


async def reset_schema(engine: AsyncEngine) -> None:
    """Xoá sạch rồi dựng lại schema theo model hiện tại.

    Đây là **đường của máy dev**, và nó xoá hết dữ liệu — một đánh đổi đã được chọn: ở local
    thì dữ liệu là thứ seed lại được, còn một schema lệch thì không sửa được bằng gì khác khi
    repo không giữ migration (xem docstring của module).

    Trên Postgres: `DROP SCHEMA public CASCADE` chứ không `drop_all`. `drop_all` chỉ biết
    những bảng model còn khai, nên một bảng đã bị xoá khỏi code sẽ ở lại mãi trong database —
    đúng loại rác làm lần đối chiếu sau nói dối. Các dialect khác (sqlite của test) không có
    schema để xoá, nên ở đó `drop_all` là thứ duy nhất có.

    Args:
        engine: Engine để chạy lên.

    Side effects:
        **Xoá toàn bộ** schema `public` rồi tạo lại mọi bảng. Không hỏi lại.
    """
    async with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
        else:
            # sqlite không có schema để xoá. Dùng `drop_all`, và chấp nhận giới hạn của
            # nó -- một bảng không còn trong model sẽ ở lại; file database của test thì
            # sinh ra mới mỗi lần nên giới hạn ấy không chạm tới ai.
            await connection.run_sync(Base.metadata.drop_all)
    await prepare_schema(engine)
