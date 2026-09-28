/**
 * Client for the BE API.
 *
 * Requests go to relative `/api` paths, which the Vite dev server proxies to
 * BE. Nothing here talks to AGENT: the frontend does not know that service
 * exists.
 *
 * These types are a hand-written mirror of BE's response models. TypeScript
 * cannot detect drift across the wire, so changing one side means changing
 * both in the same change set.
 *
 * Two things this module deliberately does NOT do. It computes no deadline
 * verdict -- `warn_cut` and `can_start_round` arrive decided, because
 * comparing instants is ADR-15's rule and it belongs to BE. And it derives no
 * status from dates, because two machines with different clocks would then
 * show one assignment in two states.
 */

/** Identity for the strip every screen carries (ADR-13). */
export interface Me {
  student_id: string;
  full_name: string;
  class_name: string;
  student_code: string;
}

/** One row of the assignment list. `status` and `actions` arrive decided. */
export interface Assignment {
  assignment_id: string;
  attempt_id: string | null;
  title: string;
  subject: string;
  question_count: number;
  phase1_minutes: number;
  opens_at: string;
  closes_at: string;
  remediation_deadline: string;
  status: string;
  wrong_count: number | null;
  actions: string[];
}

export interface Option {
  option_id: string;
  label: string;
  text: string;
}

export interface Question {
  question_id: string;
  order: number;
  stem: string;
  options: Option[];
  chosen_option_id: string | null;
}

export interface Attempt {
  attempt_id: string;
  title: string;
  started_at: string;
  ends_at: string;
  questions: Question[];
}

export interface SubmitResult {
  attempt_id: string;
  submitted_at: string;
  phase1_score: number;
  question_count: number;
  wrong_question_ids: string[];
}

/** One remediation round of one question, printed on the score sheet. */
export interface RoundEntry {
  index: number;
  stem: string;
  outcome: string;
}

export interface ResultItem {
  question_id: string;
  order: number;
  stem: string;
  mark: number;
  mark_reason: string;
  rounds: RoundEntry[];
}

export interface AttemptResult {
  attempt_id: string;
  title: string;
  state: string;
  total_score: number;
  question_count: number;
  submitted_at: string | null;
  remediation_deadline: string;
  items: ResultItem[];
}

export interface RemediationItem {
  question_id: string;
  order: number;
  stem: string;
  chosen: { label: string; text: string } | null;
  correct: { label: string; text: string };
  rounds_used: number;
  rounds_max: number;
  /** Where the question ended up; only meaningful once `closed`. */
  mark: number;
  closed: boolean;
}

export interface Remediation {
  attempt_id: string;
  state: string;
  deadline: string;
  minutes_per_question: number;
  round_budget_minutes: number;
  /** How many of `items` still need a round. Drives the button's label. */
  open_count: number;
  can_start_round: boolean;
  warn_cut: boolean;
  open_round_id: string | null;
  /** Every question wrong at the end of phase 1, closed ones included. */
  items: RemediationItem[];
}

export interface Solution {
  question_id: string;
  stem: string;
  methods: { title: string; body: string }[];
  options: { label: string; text: string; is_correct: boolean; error_label: string | null }[];
}

export interface ChatMessage {
  message_id: string;
  role: string;
  text: string;
  created_at: string;
}

export interface ChatHistory {
  attempt_id: string;
  locked: boolean;
  messages: ChatMessage[];
}

export interface RoundItem {
  round_item_id: string;
  origin_question_id: string;
  /** The number this question carries on the paper, which is what is shown. */
  origin_order: number;
  order: number;
  stem: string;
  options: Option[];
  chosen_label: string | null;
}

export interface OpenRound {
  round_id: string;
  index: number;
  ends_at: string;
  items: RoundItem[];
}

export interface RoundVerdict {
  round_id: string;
  per_question: {
    question_id: string;
    outcome: string;
    new_mark: number;
    rounds_used: number;
    rounds_left: number;
  }[];
  attempt_state: string;
}

/**
 * Stand-in for a sign-in screen, which ADR-10 left out of the first round.
 *
 * BE authorises for real on the strength of this value; only the proof of
 * identity is temporary. It lives in one constant so the day sign-in arrives,
 * there is exactly one call site to change.
 */
export const ACTOR = "student:HS2026-1204";

function headers(): HeadersInit {
  return { "Content-Type": "application/json", "X-Actor": ACTOR };
}

/**
 * Send one request and turn a failure into an error worth showing.
 *
 * @param path - Path below `/api`.
 * @param init - Fetch options; the actor header is added here.
 * @returns The parsed body.
 * @throws Error carrying BE's `detail` when the response is not ok, because
 *   every refusal in this API explains itself in Vietnamese and that sentence
 *   is more useful to a student than a status code.
 */
async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, headers: headers() });
  if (!response.ok) {
    let detail = `Lỗi ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* a non-JSON error body is still an error; keep the status text */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const api = {
  me: () => call<Me>("/me"),
  assignments: () => call<Assignment[]>("/me/assignments"),
  startAttempt: (assignmentId: string) =>
    call<Attempt>(`/assignments/${assignmentId}/attempts`, { method: "POST" }),
  attempt: (attemptId: string) => call<Attempt>(`/attempts/${attemptId}`),
  saveAnswer: (attemptId: string, questionId: string, optionId: string) =>
    call<{ saved_at: string }>(`/attempts/${attemptId}/answers/${questionId}`, {
      method: "PUT",
      body: JSON.stringify({ option_id: optionId }),
    }),
  submit: (attemptId: string) =>
    call<SubmitResult>(`/attempts/${attemptId}/submit`, { method: "POST" }),
  result: (attemptId: string) => call<AttemptResult>(`/attempts/${attemptId}/result`),
  remediation: (attemptId: string) => call<Remediation>(`/attempts/${attemptId}/remediation`),
  solution: (questionId: string) => call<Solution>(`/questions/${questionId}/solution`),
  chat: (attemptId: string) => call<ChatHistory>(`/attempts/${attemptId}/chat`),
  postChat: (attemptId: string, text: string) =>
    call<{ message_id: string; stream_url: string }>(`/attempts/${attemptId}/chat/messages`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  startRound: (attemptId: string) =>
    call<OpenRound>(`/attempts/${attemptId}/rounds`, { method: "POST" }),
  saveRoundAnswer: (roundId: string, itemId: string, label: string) =>
    call<{ saved_at: string }>(`/rounds/${roundId}/answers/${itemId}`, {
      method: "PUT",
      body: JSON.stringify({ label }),
    }),
  submitRound: (roundId: string) =>
    call<RoundVerdict>(`/rounds/${roundId}/submit`, { method: "POST" }),
  report: (attemptId: string, note: string | null) =>
    call<{ report_id: string }>(`/attempts/${attemptId}/reports`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
};

/**
 * Read the assistant's next turn as it arrives.
 *
 * Server-sent events are an accelerant for how the answer feels, not a source
 * of truth: BE stores the turn before the first chunk leaves, so a dropped
 * connection costs the animation and never the message. Callers reload the
 * history afterwards rather than trusting what they assembled here.
 *
 * @param attemptId - Whose conversation.
 * @param onChunk - Called with each fragment, in order.
 * @returns A promise settling when the stream ends.
 * @throws Error when the stream cannot be opened.
 */
export async function streamReply(
  attemptId: string,
  onChunk: (text: string) => void,
): Promise<void> {
  const response = await fetch(`/api/attempts/${attemptId}/chat/stream`, { headers: headers() });
  if (!response.ok || response.body === null) {
    throw new Error("Trợ lý chưa trả lời được.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const event of events) {
      const lines = event.split("\n");
      const name = lines.find((part) => part.startsWith("event: "))?.slice("event: ".length);
      // Every `data:` line, joined with newlines -- that is what the format
      // says a repeated field means. Reading only the first one silently
      // truncated any answer that contained a line break.
      const data = lines
        .filter((part) => part.startsWith("data: "))
        .map((part) => part.slice("data: ".length))
        .join("\n");

      if (name === "chunk") onChunk(data);
      // The stream starts before BE knows whether the model will answer, so a
      // failure arrives here rather than as a status code.
      if (name === "error") throw new Error(data || "Trợ lý chưa trả lời được.");
    }
  }
}

/** Format an ISO instant the way every screen shows it: `HH:MM · DD/MM`. */
export function moment(iso: string): string {
  const at = new Date(iso);
  const two = (value: number) => String(value).padStart(2, "0");
  return `${two(at.getHours())}:${two(at.getMinutes())} · ${two(at.getDate())}/${at.getMonth() + 1}`;
}

/** Format the seconds left as `MM:SS`, clamped at zero. */
export function countdown(msLeft: number): string {
  const seconds = Math.max(0, Math.floor(msLeft / 1000));
  const two = (value: number) => String(value).padStart(2, "0");
  return `${two(Math.floor(seconds / 60))}:${two(seconds % 60)}`;
}
