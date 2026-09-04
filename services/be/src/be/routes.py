"""HTTP surface of BE.

Grading is asynchronous because an LLM call is slow enough that holding a
request open for it would time out. The client therefore posts a submission,
receives a job id, and polls for the result.
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
    """Liveness payload."""

    status: str


class SubmissionAccepted(BaseModel):
    """Acknowledgement that a submission was queued for grading."""

    job_id: str
    submission_id: str


class GradedResult(BaseModel):
    """AGENT's evidence combined with BE's routing decision.

    The review fields are absent from what AGENT returns; they are added here.
    """

    submission_id: str
    score: float
    confidence: float
    misconception_code: str | None
    feedback_text: str
    needs_teacher_review: bool
    review_reason: ReviewReason | None


class JobStatusResponse(BaseModel):
    """Current state of a grading job, with the result once it exists."""

    job_id: str
    status: str
    result: GradedResult | None = None


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    """Report that the BE process is up.

    Returns:
        A payload with status "ok". Deliberately does not probe Redis, so this
        endpoint stays usable for telling a dead process from a dead dependency.
    """
    return HealthResponse(status="ok")


@router.post("/api/submissions", response_model=SubmissionAccepted, status_code=202)
async def submit(request: Request, submission: GradingRequested) -> SubmissionAccepted:
    """Accept a student submission and queue it for grading.

    Args:
        request: Incoming request, used to reach the shared arq pool.
        submission: The answer to grade.

    Returns:
        The job id the client polls, alongside the submission id it belongs to.

    Raises:
        HTTPException: 503 when the queue refuses the job, which in practice
            means Redis is unreachable.

    Side effects:
        Writes a job onto the shared Redis queue.
    """
    settings = get_settings()
    try:
        job_id = await enqueue_grading(request.app.state.queue_pool, settings, submission)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=f"Could not queue submission: {exc}") from exc

    return SubmissionAccepted(job_id=job_id, submission_id=submission.submission_id)


@router.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def job_status(request: Request, job_id: str) -> JobStatusResponse:
    """Report the state of a grading job and its result once finished.

    Applies the Teacher Review policy at read time rather than storing the
    decision, so changing the threshold takes effect without regrading anything.

    Args:
        request: Incoming request, used to reach the shared arq pool.
        job_id: Identifier returned by the submission endpoint.

    Returns:
        The job status, plus the graded result and review decision when the job
        has completed.

    Raises:
        HTTPException: 404 when arq has no record of the job, which also happens
            once a completed result has passed its retention window.
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
