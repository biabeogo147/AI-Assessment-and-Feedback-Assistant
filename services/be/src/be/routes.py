"""Bề mặt HTTP của BE.

Việc chấm là bất đồng bộ vì một lần gọi LLM chậm tới mức giữ một request mở để chờ
nó sẽ bị timeout. Vì vậy client post một bài nộp lên, nhận một job id, rồi poll để
lấy kết quả.
"""

from arq.jobs import JobStatus
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from be.config import get_settings
from be.queue import enqueue_grading, read_job
from be.review_policy import decide_review
from contracts import GradingCompleted, GradingRequested, ReviewReason

router = APIRouter()


class HealthResponse(BaseModel):
    """Payload báo còn sống."""

    status: str


class SubmissionAccepted(BaseModel):
    """Xác nhận rằng một bài nộp đã được đưa vào queue để chấm."""

    job_id: str
    submission_id: str


class GradedResult(BaseModel):
    """Bằng chứng của AGENT ghép với quyết định định tuyến của BE.

    Những field về việc xem lại không có trong thứ AGENT trả về; chúng được thêm vào ở
    đây.
    """

    submission_id: str
    score: float
    confidence: float
    misconception_code: str | None
    feedback_text: str
    needs_teacher_review: bool
    review_reason: ReviewReason | None


class JobStatusResponse(BaseModel):
    """State hiện tại của một job chấm, kèm kết quả khi kết quả đã có."""

    job_id: str
    status: str
    result: GradedResult | None = None


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    """Báo rằng process BE đang chạy.

    Returns:
        Một payload có status "ok". Cố ý không thăm dò Redis, nhờ vậy endpoint này vẫn
        dùng được để phân biệt một process chết với một dependency chết.
    """
    return HealthResponse(status="ok")


@router.post("/api/submissions", response_model=SubmissionAccepted, status_code=202)
async def submit(request: Request, submission: GradingRequested) -> SubmissionAccepted:
    """Nhận một bài nộp của học sinh và đưa nó vào queue để chấm.

    Args:
        request: Request đang vào, dùng để với tới pool arq dùng chung.
        submission: Câu trả lời cần chấm.

    Returns:
        job id mà client sẽ poll, cùng với id bài nộp mà nó thuộc về.

    Raises:
        HTTPException: 503 khi queue từ chối job, mà trên thực tế nghĩa là không tới
            được Redis.

    Side effects:
        Ghi một job lên queue Redis dùng chung.
    """
    settings = get_settings()
    try:
        job_id = await enqueue_grading(request.app.state.queue_pool, settings, submission)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=f"Could not queue submission: {exc}") from exc

    return SubmissionAccepted(job_id=job_id, submission_id=submission.submission_id)


@router.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def job_status(request: Request, job_id: str) -> JobStatusResponse:
    """Báo state của một job chấm, và kết quả của nó khi đã xong.

    Áp chính sách Teacher Review vào lúc đọc chứ không lưu lại quyết định, nhờ vậy đổi
    ngưỡng là có hiệu lực ngay mà không phải chấm lại thứ gì.

    Args:
        request: Request đang vào, dùng để với tới pool arq dùng chung.
        job_id: Identifier do endpoint nộp bài trả về.

    Returns:
        status của job, kèm kết quả đã chấm và quyết định về việc xem lại khi job đã xong.

    Raises:
        HTTPException: 404 khi arq không có bản ghi nào về job, chuyện cũng xảy ra khi
            một kết quả đã xong đi qua khỏi cửa sổ lưu giữ của nó.
    """
    settings = get_settings()
    status, raw_result = await read_job(request.app.state.queue_pool, settings, job_id)

    if status is JobStatus.not_found:
        raise HTTPException(status_code=404, detail=f"No job {job_id}")

    if status is not JobStatus.complete or raw_result is None:
        return JobStatusResponse(job_id=job_id, status=status.value)

    evidence = GradingCompleted.model_validate(raw_result)
    decision = decide_review(evidence, settings.review_confidence_threshold)

    return JobStatusResponse(
        job_id=job_id,
        status=status.value,
        result=GradedResult(
            submission_id=evidence.submission_id,
            score=evidence.score,
            confidence=evidence.confidence,
            misconception_code=evidence.misconception_code,
            feedback_text=evidence.feedback_text,
            needs_teacher_review=decision.needs_teacher_review,
            review_reason=decision.reason,
        ),
    )
