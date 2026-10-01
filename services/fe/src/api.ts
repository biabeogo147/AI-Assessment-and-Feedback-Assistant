/**
 * Client cho API của BE.
 *
 * Request đi tới các path `/api` tương đối, và Vite dev server proxy chúng sang
 * BE. Không có gì ở đây nói chuyện với AGENT: frontend không biết là có service
 * đó.
 *
 * Các type ở đây là bản chép tay của response model bên BE. TypeScript không
 * phát hiện được chênh lệch qua đường truyền, nên sửa một bên là phải sửa cả
 * hai bên trong cùng một đợt thay đổi.
 *
 * Hai việc module này cố ý KHÔNG làm. Nó không tự kết luận gì về hạn:
 * `warn_cut` và `can_start_round` về tới đây là đã có kết luận rồi, vì so sánh
 * hai mốc thời gian là luật của ADR-15 và việc đó thuộc BE. Và nó không suy ra
 * status từ ngày tháng, vì hai máy lệch đồng hồ sẽ hiện cùng một đề ở hai state
 * khác nhau.
 */

/** Danh tính cho dải thông tin mà mọi màn hình đều mang (ADR-13). */
export interface Me {
  student_id: string;
  full_name: string;
  class_name: string;
  student_code: string;
}

/** Một dòng của danh sách bài được giao. `status` và `actions` về tới đây là đã có kết luận. */
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

/** Một lượt làm lại của một câu hỏi, in trên bảng điểm. */
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
  /** Câu hỏi này kết lại ở đâu; chỉ có nghĩa khi đã `closed`. */
  mark: number;
  closed: boolean;
}

export interface Remediation {
  attempt_id: string;
  state: string;
  deadline: string;
  minutes_per_question: number;
  round_budget_minutes: number;
  /** Bao nhiêu câu trong `items` còn cần một lượt nữa. Quyết định chữ trên nút. */
  open_count: number;
  can_start_round: boolean;
  warn_cut: boolean;
  open_round_id: string | null;
  /** Mọi câu làm sai ở cuối pha 1, kể cả những câu đã `closed`. */
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
  /** Số thứ tự câu này mang trên đề, và đó là số được hiện ra. */
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
 * Đứng thay cho màn hình đăng nhập, thứ mà ADR-10 để ra ngoài vòng đầu.
 *
 * BE phân quyền thật dựa trên giá trị này; chỉ phần chứng minh danh tính là tạm.
 * Nó nằm trong đúng một constant, để ngày đăng nhập thật xuất hiện thì chỉ có
 * đúng một chỗ phải sửa.
 */
export const ACTOR = "student:HS2026-1204";

function headers(): HeadersInit {
  return { "Content-Type": "application/json", "X-Actor": ACTOR };
}

/**
 * Gửi một request và biến thất bại thành một lỗi đáng hiện ra.
 *
 * @param path - Path nằm dưới `/api`.
 * @param init - Tuỳ chọn cho fetch; header actor được thêm ở đây.
 * @returns Body đã parse.
 * @throws Error mang `detail` của BE khi response không ok, vì mọi lời từ chối
 *   trong API này đều tự giải thích bằng tiếng Việt, và câu đó có ích cho học
 *   sinh hơn một status code.
 */
async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, headers: headers() });
  if (!response.ok) {
    let detail = `Lỗi ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* một error body không phải JSON thì vẫn là lỗi; giữ lại phần status text */
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
 * Đọc lượt nói tiếp theo của trợ lý ngay khi nó về tới.
 *
 * Server-sent events chỉ làm câu trả lời *cảm giác* nhanh hơn, không phải nguồn
 * sự thật: BE lưu lượt nói trước khi chunk đầu tiên rời đi, nên mất kết nối thì
 * mất phần chạy chữ, không bao giờ mất tin nhắn. Nơi gọi sẽ tải lại lịch sử sau
 * đó chứ không tin vào thứ nó tự ghép ở đây.
 *
 * @param attemptId - Cuộc trò chuyện của ai.
 * @param onChunk - Được gọi với từng mảnh, theo đúng thứ tự.
 * @returns Một promise kết thúc khi stream hết.
 * @throws Error khi không mở được stream.
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
      // Mọi dòng `data:`, nối lại bằng ký tự xuống dòng — đúng như định dạng
      // quy định cho một field lặp lại. Chỉ đọc dòng đầu tiên thì mọi câu trả
      // lời có dấu xuống dòng đều bị cắt ngắn mà không báo gì.
      const data = lines
        .filter((part) => part.startsWith("data: "))
        .map((part) => part.slice("data: ".length))
        .join("\n");

      if (name === "chunk") onChunk(data);
      // Stream bắt đầu trước khi BE biết model có trả lời được hay không, nên
      // thất bại về tới đây chứ không về dưới dạng một status code.
      if (name === "error") throw new Error(data || "Trợ lý chưa trả lời được.");
    }
  }
}

/** Định dạng một mốc thời gian ISO theo đúng cách mọi màn hình hiện nó: `HH:MM · DD/MM`. */
export function moment(iso: string): string {
  const at = new Date(iso);
  const two = (value: number) => String(value).padStart(2, "0");
  return `${two(at.getHours())}:${two(at.getMinutes())} · ${two(at.getDate())}/${at.getMonth() + 1}`;
}

/** Định dạng số giây còn lại thành `MM:SS`, chặn ở mức không. */
export function countdown(msLeft: number): string {
  const seconds = Math.max(0, Math.floor(msLeft / 1000));
  const two = (value: number) => String(value).padStart(2, "0");
  return `${two(Math.floor(seconds / 60))}:${two(seconds % 60)}`;
}
