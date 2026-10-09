"""Bề mặt HTTP chung của BE.

Chỉ còn một endpoint ở đây: `/health`. Mọi đường nghiệp vụ nằm ở `student_routes.py`,
`teacher_routes.py` và `teacher_documents.py`, mỗi tệp một bên gọi.

Tệp này từng chở thêm `POST /api/submissions` và `GET /api/jobs/{id}` -- đường chấm bài đi
qua hàng đợi, kèm quyết định đưa kết quả vào hàng đợi review của giáo viên. ADR-20 đã thay
đường ấy bằng một phép so chạy thẳng trong `student_routes.submit_attempt`, và hàng đợi
review thì chưa bao giờ được dựng: không màn hình, không chỗ giáo viên chốt lại. Giữ một
đường API không ai gọi là giữ một thứ mà người đọc code sẽ tưởng là luồng chính, nên nó đã
được gỡ.
"""

from fastapi import APIRouter
from pydantic import BaseModel

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
