/**
 * Client for the BE API.
 *
 * Requests go to relative `/api` paths, which the Vite dev server proxies to BE.
 * Nothing here talks to AGENT: the frontend does not know that service exists.
 */

export type ReviewReason =
  | "low_confidence"
  | "answer_explanation_conflict"
  | "insufficient_evidence"
  | "anomaly";

export interface GradedResult {
  submission_id: string;
  score: number;
  confidence: number;
  misconception_code: string | null;
  feedback_text: string;
  needs_teacher_review: boolean;
  review_reason: ReviewReason | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  result: GradedResult | null;
}

export interface SubmissionInput {
  selectedOptionId: string;
  explanation: string;
}

/** Human-readable labels for the four Teacher Review control points. */
export const REVIEW_REASON_LABELS: Record<ReviewReason, string> = {
  low_confidence: "Độ tin cậy thấp",
  answer_explanation_conflict: "Đáp án và cách làm không khớp",
  insufficient_evidence: "Không đủ căn cứ",
  anomaly: "Trường hợp bất thường",
};

const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 30000;

/**
 * Send a submission to BE and get back the id of its grading job.
 *
 * @param input - The chosen option and the student's explanation. An empty
 *   explanation is sent as null, because "did not explain" and "explained
 *   nothing" are different cases to the grader.
 * @returns The job id to poll.
 * @throws Error when BE rejects the submission, typically because Redis is down.
 */
export async function submitAnswer(input: SubmissionInput): Promise<string> {
  const response = await fetch("/api/submissions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      submission_id: crypto.randomUUID(),
      assessment_id: "asm-demo",
      question_id: "q-1",
      student_id: "stu-demo",
      assessment_type: "routine",
      selected_option_id: input.selectedOptionId,
      student_explanation: input.explanation.length > 0 ? input.explanation : null,
      learning_objective: "fraction-addition",
    }),
  });

  if (!response.ok) {
    throw new Error(`Không gửi được bài: ${response.status}`);
  }

  const body = (await response.json()) as { job_id: string };
  return body.job_id;
}

/**
 * Read a grading job once.
 *
 * @param jobId - Identifier returned by submitAnswer.
 * @returns The job's current status, plus its result once complete.
 * @throws Error when BE has no record of the job.
 */
export async function fetchJob(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(`Không đọc được job: ${response.status}`);
  }
  return (await response.json()) as JobStatusResponse;
}

/**
 * Poll a grading job until it produces a result.
 *
 * Grading runs through a queue, so the result is not available on the response
 * to the submission itself.
 *
 * @param jobId - Identifier returned by submitAnswer.
 * @param sleep - Injectable delay, so tests need not wait in real time.
 * @returns The graded result.
 * @throws Error if the job has not completed within the timeout, which usually
 *   means the AGENT worker is not running.
 */
export async function waitForResult(
  jobId: string,
  sleep: (ms: number) => Promise<void> = defaultSleep,
): Promise<GradedResult> {
  const deadline = Date.now() + POLL_TIMEOUT_MS;

  while (Date.now() < deadline) {
    const job = await fetchJob(jobId);
    if (job.result !== null) {
      return job.result;
    }
    await sleep(POLL_INTERVAL_MS);
  }

  throw new Error("Hết thời gian chờ chấm bài. Kiểm tra xem AGENT worker có đang chạy không.");
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
