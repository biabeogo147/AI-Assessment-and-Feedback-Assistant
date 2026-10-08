"""Dựng lại database của máy dev từ đầu: xoá sạch, tạo lại theo model, seed lại.

Chạy bằng:  python -m be.reset_db   (hoặc `.\\dev.ps1 db-reset`)

Vì sao tồn tại: repo này **không giữ migration** (xem `be/db.py`), nên một model thêm cột
không có đường nào đi vào một database đã tạo — `create_all` chỉ tạo bảng còn thiếu. Ở local
thì lối thoát rẻ nhất là vứt dữ liệu đi và dựng lại, và dữ liệu ở đây là thứ `seed_if_empty`
sinh ra được. Ngày có dữ liệu thật thì đánh đổi này đảo chiều và Alembic vào thay chỗ.

Nó **xoá hết, không hỏi lại**. Đó là chủ ý: một lệnh tên `db-reset` mà hỏi *"bạn chắc chứ"*
rồi vẫn xoá thì chỉ thêm một bước; cái bảo vệ thật nằm ở chỗ nó chỉ chạy khi có người gõ.
"""

import asyncio
import logging

from be.config import get_settings
from be.db import bind_sessions, create_engine, get_session
from be.seed import seed_if_empty
from be.storage import create_store
from schema.ddl import reset_schema

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    """Xoá schema, dựng lại, rồi seed.

    Side effects:
        **Xoá toàn bộ** dữ liệu trong database đã cấu hình, rồi ghi lại dữ liệu demo, rồi
        **xoá sạch bucket** tài liệu.
    """
    settings = get_settings()
    engine = create_engine(settings)
    store = create_store(settings)
    try:
        logger.info("dropping and recreating the schema at %s", settings.database_url)
        await reset_schema(engine)
        bind_sessions(engine)
        async for session in get_session():
            if await seed_if_empty(session):
                logger.info("seeded the demo class, roster and published assessment")
        # Hàng trước, object sau -- **ngược** với đường ghi, và cố ý. Đường ghi chọn
        # "object mồ côi rẻ hơn hàng trỏ vào hư không"; cùng một ưu tiên ấy, trên đường
        # xoá, bắt phải bỏ hàng trước: hỏng giữa chừng thì còn lại rác dọn được, chứ
        # không phải một bảng `documents` trỏ vào một bucket đã sạch.
        await store.ensure_ready()
        await store.clear()
        logger.info("done — database and document bucket now match the models in code")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
