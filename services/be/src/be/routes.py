"""Bề mặt HTTP chung của BE.

Hai endpoint vận hành ở đây: `/health` và `/api/version`. Mọi đường nghiệp vụ nằm ở
`student_routes.py`, `teacher_routes.py` và `teacher_documents.py`, mỗi tệp một bên gọi.

Tệp này từng chở thêm `POST /api/submissions` và `GET /api/jobs/{id}` -- đường chấm bài đi
qua hàng đợi, kèm quyết định đưa kết quả vào hàng đợi review của giáo viên. ADR-20 đã thay
đường ấy bằng một phép so chạy thẳng trong `student_routes.submit_attempt`. Hàng đợi chặn kết
quả chấm thì chưa bao giờ được dựng và nay đã bỏ (ADR-37); hàng đợi *Cần bạn xem* của giáo
viên (ADR-34) không chặn gì. Giữ một
đường API không ai gọi là giữ một thứ mà người đọc code sẽ tưởng là luồng chính, nên nó đã
được gỡ.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from be.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Payload báo còn sống."""

    status: str


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    """Báo rằng process BE đang chạy.

    Returns:
        Một payload có status "ok". Cố ý không thăm dò Redis, nhờ vậy endpoint này vẫn
        dùng được để phân biệt một process chết với một dependency chết.
    """
    return HealthResponse(status="ok")


class VersionResponse(BaseModel):
    """Tên bản lab BE đang chạy."""

    version: str


@router.get("/api/version", response_model=VersionResponse, tags=["ops"])
async def version() -> VersionResponse:
    """Tên bản lab (`lab-YYYY.z.x`, plan `lab-version`) của BE.

    Không cần đăng nhập: màn đăng nhập cũng hiện tên bản. FE so tên này với tên dựng vào chính nó,
    và lệch thì tự tải lại. Dưới `/api` vì Caddy và proxy của Vite chỉ chuyển đường ấy tới BE;
    `/health` ở ngoài `/api` là cho healthcheck của docker.

    Returns:
        `AIAFA_VERSION` của settings; `chưa có phiên bản` khi không đặt.
    """
    return VersionResponse(version=get_settings().aiafa_version)
