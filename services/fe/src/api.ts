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
  options: {
    label: string;
    text: string;
    is_correct: boolean;
    error_label: string | null;
  }[];
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

/* --- Bề mặt giáo viên -----------------------------------------------------
 *
 * Chép tay từ `teacher_routes.py` và `teacher_chat.py`, cùng một luật như phần
 * học sinh ở trên: sửa một bên là sửa cả hai bên trong cùng một đợt.
 *
 * Mốc thời gian là `string` chứ không phải `Date`, giống hệt phần học sinh. BE
 * trả ISO 8601 có offset, và `new Date()` ngay tại biên sẽ làm mất chính cái
 * offset đó — thứ mà mọi câu luật của ADR-03 đọc ra để in giờ.
 */

/** Giáo viên đang đăng nhập, cho dải trên cùng. */
export interface TeacherMe {
  teacher_id: string;
  full_name: string;
  teacher_code: string;
}

/** Một phương án, bản của giáo viên: có cả đáp án và nhãn lỗi. */
export interface TeacherOption {
  label: string;
  text: string;
  is_correct: boolean;
  error_label: string | null;
}

export interface Method {
  title: string;
  body: string;
}

export interface TeacherQuestion {
  question_id: string;
  order: number;
  stem: string;
  learning_objective: string;
  options: TeacherOption[];
  methods: Method[];
}

/** Chữ của một câu, như giáo viên vừa sửa. Đủ bộ, không từng mảnh. */
export interface QuestionEdit {
  stem: string;
  learning_objective: string;
  options: TeacherOption[];
  methods: Method[];
}

/** Một đề, đủ để vẽ cả panel bên phải. `state` là nguồn duy nhất cho *sửa được hay không*. */
export interface AssessmentDetail {
  assessment_id: string;
  title: string;
  subject: string;
  grade: string;
  state: string;
  question_count: number;
  still_drafting: number;
  topic_scope: string;
  difficulty: string;
  /** Đoạn chat đã sinh ra đề. Rỗng với đề seed hoặc đề tạo tay — panel vẫn mở được. */
  conversation_id: string;
  questions: TeacherQuestion[];
}

/** Ba câu luật, cùng string mà biểu mẫu, biên bản và trang phát hành trả về (ADR-03). */
export interface TimingRules {
  phase_one: string;
  phase_two: string;
  recall: string;
  /**
   * Khuôn của hai câu trên, với chỗ trống `{closes}` / `{last}` và `{deadline}` / `{rate}`.
   *
   * Chỉ biểu mẫu dùng tới. Ở đó chưa có giờ nào lúc mở màn, nên câu dựng sẵn chỉ có thể là
   * câu `--:--` — và nó đứng ngay dưới mấy ô nhập, trông như sắp đổi theo con số vừa gõ mà
   * về cấu trúc thì không bao giờ đổi được. Chữ nghĩa vẫn chỉ có một nơi: BE dựng câu thật
   * bằng đúng khuôn này (`publication_wording.py`).
   *
   * Hai đường kia (hộp xác nhận, biên bản) **không** dùng khuôn: chúng có số thật và nhận
   * câu đã dựng từ BE.
   *
   * **Bắt buộc, không optional.** BE và FE ở repo này deploy cùng nhau, nên một field
   * optional kèm `?? form.rules.phase_one` chỉ mua được một thứ: khi BE thôi gửi khuôn,
   * màn hình lặng lẽ quay về đúng câu `--:--` đứng mãi dưới mấy ô nhập — chính cái bug cả
   * đợt này tồn tại để chữa — mà không một lỗi hay một test nào kêu lên.
   */
  phase_one_form: string;
  phase_two_form: string;

  /**
   * Ba lời từ chối của `_schedule_fault`, gửi lên để biểu mẫu nói được **trước** cú bấm.
   *
   * Cổng thật vẫn ở BE — FE không bao giờ là nơi duy nhất kiểm — nhưng một cổng chỉ nói
   * ra sau cú bấm thì giáo viên đã gõ xong sáu ô rồi mới biết mình gõ sai. Và tệ hơn:
   * câu luật ngay dưới mấy ô ấy vẫn in ra một sự thật bất khả thi bằng giọng khẳng định.
   *
   * Lấy chữ từ BE chứ không viết lại ở đây, cùng lý lẽ với hai khuôn trên: hai cách diễn
   * đạt cho một luật là hai luật (ADR-03).
   */
  opens_in_the_past: string;
  closes_before_opens: string;
  phase_two_too_early: string;
}

export interface ClassOption {
  class_id: string;
  name: string;
  student_count: number;
  published: boolean;
}

/** Biểu mẫu phát hành. Cố ý **không** gợi giờ nào: sáu tham số đều do giáo viên gõ. */
export interface PublishForm {
  assessment_id: string;
  title: string;
  state: string;
  question_count: number;
  can_publish: boolean;
  reason: string;
  classes: ClassOption[];
  rules: TimingRules;
}

/** Sáu tham số cho **một** lớp. Mọi mốc phải mang offset — xem `isoWithOffset`. */
export interface ClassSchedule {
  class_id: string;
  opens_at: string;
  closes_at: string;
  phase1_minutes: number;
  phase2_minutes_per_question: number;
  remediation_deadline: string;
}

/**
 * Một lớp trong kết quả phát hành.
 *
 * `published: false` kèm `reason` là một **hàng**, không phải một ngoại lệ: ADR-02 cho phép
 * một lớp nhận được trong khi lớp khác không. Nên màn hình in `reason` nguyên văn, và lớp
 * trượt giữ nguyên tick để sửa giờ gửi lại.
 */
export interface ClassResult {
  class_id: string;
  class_name: string;
  published: boolean;
  reason: string;
  opens_at: string | null;
  closes_at: string | null;
  remediation_deadline: string | null;
  withdrawable_until: string | null;
  phase_one_note: string;
  phase_two_note: string;
}

export interface PublishResult {
  assessment_id: string;
  state: string;
  preview: boolean;
  classes: ClassResult[];
  rules: TimingRules;
}

/** Một lớp **đang** giữ đề, với giờ đã đặt. Đọc lại được sau F5. */
export interface PublishedTo {
  class_id: string;
  class_name: string;
  student_count: number;
  opens_at: string;
  closes_at: string;
  phase1_minutes: number;
  phase2_minutes_per_question: number;
  remediation_deadline: string;
  withdrawable_until: string;
  phase_one_note: string;
  phase_two_note: string;
}

export interface Publications {
  assessment_id: string;
  classes: PublishedTo[];
  rules: TimingRules;
}

/** Một tài liệu trong thư viện của giáo viên. */
export interface TeacherDocument {
  document_id: string;
  filename: string;
  /** Đuôi file viết hoa, thứ nhãn vuông bên trái chip in ra. */
  kind: string;
  byte_size: number;
  uploaded_at: string;
}

export interface Approval {
  assessment_id: string;
  state: string;
  question_count: number;
  still_drafting: number;
}

/**
 * Một dòng trong hội thoại của giáo viên.
 *
 * `kind` là `"teacher"`, `"assistant"`, `"tool_call"` hay `"tool_result"`. Luật render nằm ở
 * màn hình, không ở đây: `tool_call` không hiện gì (nó không mang kết quả), `tool_result` ra
 * một thẻ chọn theo `tool_name`.
 */
export interface Turn {
  kind: string;
  text: string;
  tool_name: string;
  tool_result: Record<string, unknown>;
  entity_kind: string;
  entity_id: string;
  /** Các phương án bày ra cùng bước này, nếu nó là một câu hỏi lại. BE viết chúng (ADR-23). */
  choices: string[];
  more_choices: number;
  model_tokens: number;
  duration_ms: number;
}

/**
 * Một lượt trả lời đã xong.
 *
 * `choices` là các câu **đã format sẵn**, và bấm một nút nghĩa là gửi lại đúng chuỗi đó.
 * Chúng nay được lưu cùng bước đã hỏi, nên một lần F5 **không** còn lấy mất các nút: lúc đọc
 * lại, BE chở `choices` của bước cuối cùng lên đây.
 */
export interface Answered {
  kind: string;
  text: string;
  /** Lượt vừa rồi nằm trong đoạn chat nào. Thứ FE cần sau khi bấm *Đoạn chat mới*. */
  conversation_id: string;
  choices: string[];
  more_choices: number;
  turns: Turn[];
}

/**
 * Một đoạn chat trên rail.
 *
 * `last_spoke_at` chứ không phải `started_at` là thứ quyết định nó nằm dưới nhãn ngày
 * nào: một đoạn mở từ tuần trước mà hôm nay vừa nói tiếp thì thuộc về *Hôm nay*, và đó
 * là chỗ người ta đi tìm nó.
 */
export interface TeacherConversation {
  conversation_id: string;
  title: string;
  started_at: string;
  last_spoke_at: string;
}

/**
 * Đứng thay cho màn hình đăng nhập, thứ mà ADR-10 để ra ngoài vòng đầu.
 *
 * BE phân quyền thật dựa trên giá trị này; chỉ phần chứng minh danh tính là tạm.
 * Nó nằm trong đúng một constant, để ngày đăng nhập thật xuất hiện thì chỉ có
 * đúng một chỗ phải sửa.
 *
 * Hai khoá vì một app phục vụ hai bề mặt. Vai được chọn **tại chỗ khai tên
 * endpoint** ở dưới, không suy từ route đang mở: một request bay ra giữa lúc
 * chuyển route sẽ mang sai vai, và triệu chứng là một 403 ở rất xa nguyên nhân.
 * Chọn tại chỗ khai thì một dòng gắn sai vai là một dòng không chạy được ngay
 * lần đầu — `/api/teacher/*` vốn trả 403 với actor học sinh.
 */
export const ACTOR = {
  student: "student:HS2026-1204",
  teacher: "teacher:GV-001",
} as const;

type Role = keyof typeof ACTOR;

function headers(role: Role): HeadersInit {
  return { "Content-Type": "application/json", "X-Actor": ACTOR[role] };
}

/**
 * Header cho một request mang `FormData`.
 *
 * Khác `headers` ở đúng một chỗ, và chỗ đó là lý do nó tồn tại: **không** có
 * `Content-Type`. Một upload multipart cần một boundary, mà boundary thì do
 * trình duyệt sinh ra lúc gửi; khai tay `multipart/form-data` sẽ gửi đi một
 * content type không có boundary, và server đọc được một body rỗng mà không có
 * lỗi nào ở giữa.
 */
function formHeaders(role: Role): HeadersInit {
  return { "X-Actor": ACTOR[role] };
}

/**
 * Gửi một request và biến thất bại thành một lỗi đáng hiện ra.
 *
 * @param role - Bề mặt nào đang gọi. Nó quyết định header actor, và nó được
 *   khai ngay cạnh tên endpoint để không thể gắn nhầm trong im lặng.
 * @param path - Path nằm dưới `/api`.
 * @param init - Tuỳ chọn cho fetch; header actor được thêm ở đây.
 * @returns Body đã parse.
 * @throws Error mang `detail` của BE khi response không ok, vì mọi lời từ chối
 *   trong API này đều tự giải thích bằng tiếng Việt, và câu đó có ích cho học
 *   sinh hơn một status code.
 */
async function call<T>(
  role: Role,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    // Nơi gọi đưa header thì nó SỞ HỮU cả bộ, không phải trộn thêm: đường upload
    // tồn tại chính vì nó cần BỎ `Content-Type`, mà trộn thì không bỏ được gì.
    headers: init.headers ?? headers(role),
  });
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

/**
 * Một request **không có thân trả về**: `204`.
 *
 * Không dùng `call` được, và lý do là cơ học: `call` kết bằng `response.json()`, mà một
 * `204` không có một byte nào để parse — nên một lần xoá thành công sẽ ném đúng như một lần
 * xoá thất bại. Phần đọc lỗi thì giữ y nguyên: một `404` vẫn phải nói câu tiếng Việt của BE.
 *
 * @param role - Ai đang gọi.
 * @param path - Đường dẫn, không gồm `/api`.
 * @param init - Phần còn lại của request.
 */
async function silent(
  role: Role,
  path: string,
  init: RequestInit = {},
): Promise<void> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: init.headers ?? headers(role),
  });
  if (response.ok) return;
  let detail = `Lỗi ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    /* một error body không phải JSON thì vẫn là lỗi; giữ lại phần status text */
  }
  throw new Error(detail);
}

export const api = {
  me: () => call<Me>("student", "/me"),
  assignments: () => call<Assignment[]>("student", "/me/assignments"),
  startAttempt: (assignmentId: string) =>
    call<Attempt>("student", `/assignments/${assignmentId}/attempts`, {
      method: "POST",
    }),
  attempt: (attemptId: string) =>
    call<Attempt>("student", `/attempts/${attemptId}`),
  saveAnswer: (attemptId: string, questionId: string, optionId: string) =>
    call<{ saved_at: string }>(
      "student",
      `/attempts/${attemptId}/answers/${questionId}`,
      {
        method: "PUT",
        body: JSON.stringify({ option_id: optionId }),
      },
    ),
  submit: (attemptId: string) =>
    call<SubmitResult>("student", `/attempts/${attemptId}/submit`, {
      method: "POST",
    }),
  result: (attemptId: string) =>
    call<AttemptResult>("student", `/attempts/${attemptId}/result`),
  remediation: (attemptId: string) =>
    call<Remediation>("student", `/attempts/${attemptId}/remediation`),
  solution: (questionId: string) =>
    call<Solution>("student", `/questions/${questionId}/solution`),
  chat: (attemptId: string) =>
    call<ChatHistory>("student", `/attempts/${attemptId}/chat`),
  postChat: (attemptId: string, text: string) =>
    call<{ message_id: string; stream_url: string }>(
      "student",
      `/attempts/${attemptId}/chat/messages`,
      {
        method: "POST",
        body: JSON.stringify({ text }),
      },
    ),
  startRound: (attemptId: string) =>
    call<OpenRound>("student", `/attempts/${attemptId}/rounds`, {
      method: "POST",
    }),
  saveRoundAnswer: (roundId: string, itemId: string, label: string) =>
    call<{ saved_at: string }>(
      "student",
      `/rounds/${roundId}/answers/${itemId}`,
      {
        method: "PUT",
        body: JSON.stringify({ label }),
      },
    ),
  submitRound: (roundId: string) =>
    call<RoundVerdict>("student", `/rounds/${roundId}/submit`, {
      method: "POST",
    }),
  report: (attemptId: string, note: string | null) =>
    call<{ report_id: string }>("student", `/attempts/${attemptId}/reports`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
};

/**
 * Các đường của bề mặt giáo viên.
 *
 * Tách khỏi `api` thành một object riêng chứ không trộn vào cùng một chỗ: hai bề mặt gửi hai
 * actor khác nhau, và một tên gọi nằm sai object là thứ `tsc` không bắt được. Đứng riêng thì
 * `teacher.` ở đầu mỗi lời gọi tự nói nó mang vai nào.
 */
/**
 * Một việc vừa xảy ra trong một lượt, đúng hình dạng BE phát ra.
 *
 * `kind` là trục duy nhất: khung SSE không mang `event:` theo loại, vì hai nguồn sự thật
 * cho cùng một câu hỏi là hai thứ sẽ lệch nhau.
 */
export interface TurnEvent {
  kind: string;
  text: string;
  choices: string[];
  more_choices: number;
  conversation_id: string;
  ended_as: string;
  title: string;
  detail: string;
  index: number;
  total: number;
  titles: string[];
  began: number;
}

/**
 * Gửi một lượt và đọc từng sự kiện ngay khi nó tới.
 *
 * Parser SSE ở đây cố tình nhỏ: BE chỉ gửi khung `data:` một dòng, nên thứ duy nhất cần
 * đúng là **ranh giới khung** (một dòng trống) và việc giữ lại phần đuôi chưa đủ một khung.
 * Bỏ phần giữ đuôi ấy thì mọi thứ chạy tốt trên máy nhanh và vỡ khi mạng cắt một khung làm
 * đôi — đúng loại lỗi chỉ xuất hiện ở nhà người dùng.
 *
 * @param text - Chữ giáo viên gõ.
 * @param into - Đoạn chat nào, hoặc mở một đoạn mới.
 * @param onEvent - Gọi cho **mỗi** sự kiện, theo đúng thứ tự tới.
 * @param signal - Để màn hình cắt được một lượt treo.
 */
async function streamTurn(
  text: string,
  into: { conversationId?: string; startNew?: boolean },
  onEvent: (event: TurnEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/teacher/chat/messages/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor": ACTOR.teacher },
    body: JSON.stringify({
      text,
      conversation_id: into.conversationId ?? null,
      start_new: into.startNew ?? false,
    }),
    signal,
  });
  if (!response.ok || response.body === null) {
    throw new Error(`Lỗi ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let rest = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    rest += decoder.decode(value, { stream: true });
    const frames = rest.split("\n\n");
    rest = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((one) => one.startsWith("data: "));
      if (line === undefined) continue;
      onEvent(JSON.parse(line.slice(6)) as TurnEvent);
    }
  }
}

export const teacher = {
  me: () => call<TeacherMe>("teacher", "/teacher/me"),
  documents: () => call<TeacherDocument[]>("teacher", "/teacher/documents"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return call<TeacherDocument>("teacher", "/teacher/documents", {
      method: "POST",
      body: form,
      headers: formHeaders("teacher"),
    });
  },
  // Sửa chữ của một câu. Gửi **cả câu** chứ không từng mảnh: ADR-18 là một luật về quan hệ
  // giữa các mảnh (đúng một phương án đúng, mọi phương án nhiễu có nhãn lỗi, hơn một lời
  // giải), nên gửi từng mảnh rời là cho câu hỏi đi qua những trạng thái không ai kiểm được.
  editQuestion: (assessmentId: string, questionId: string, question: QuestionEdit) =>
    call<TeacherQuestion>(
      "teacher",
      `/teacher/assessments/${assessmentId}/questions/${questionId}`,
      { method: "PATCH", body: JSON.stringify(question) },
    ),
  assessment: (assessmentId: string) =>
    call<AssessmentDetail>("teacher", `/teacher/assessments/${assessmentId}`),
  publications: (assessmentId: string) =>
    call<Publications>(
      "teacher",
      `/teacher/assessments/${assessmentId}/publications`,
    ),
  conversations: () =>
    call<TeacherConversation[]>("teacher", "/teacher/conversations"),
  renameConversation: (conversationId: string, title: string) =>
    call<TeacherConversation>(
      "teacher",
      `/teacher/conversations/${encodeURIComponent(conversationId)}`,
      { method: "PATCH", body: JSON.stringify({ title }) },
    ),
  // Xoá mềm bên BE: đoạn rời rail và đọc lại ra 404, các lượt của nó vẫn nằm trong bảng vì
  // ADR-24 đòi biên bản duyệt đề giữ được. Màn hình không cần biết chuyện đó — với nó thì
  // đoạn ấy đã không còn.
  deleteConversation: (conversationId: string) =>
    silent(
      "teacher",
      `/teacher/conversations/${encodeURIComponent(conversationId)}`,
      {
        method: "DELETE",
      },
    ),
  // Thiếu id thì BE trả đoạn **đang chạy**, y như trước khi giáo viên có nhiều đoạn.
  conversation: (conversationId?: string) =>
    call<Answered>(
      "teacher",
      conversationId === undefined
        ? "/teacher/chat"
        : `/teacher/chat?conversation_id=${encodeURIComponent(conversationId)}`,
    ),
  // `conversationId` và `startNew` loại trừ nhau, và BE trả 422 khi gửi cả hai — nên
  // chỗ này không được "tiện tay" gửi kèm cả hai cho chắc.
  // `signal` vì một lượt có thể mất tới 90 giây bên BE: màn hình đặt hạn riêng và
  // phải cắt được, nếu không thì một request treo sẽ khoá ô nhập vĩnh viễn.
  say: (
    text: string,
    into: { conversationId?: string; startNew?: boolean } = {},
    signal?: AbortSignal,
  ) =>
    call<Answered>("teacher", "/teacher/chat/messages", {
      method: "POST",
      body: JSON.stringify({
        text,
        conversation_id: into.conversationId ?? null,
        start_new: into.startNew ?? false,
      }),
      signal,
    }),
  // Cùng một lượt với `say`, chỉ khác cửa ra: BE phát từng việc ngay khi nó xảy ra, nên
  // khối bước sống thay vì hiện cả cục lúc xong. Dùng `fetch` chứ không `EventSource` —
  // lượt gửi bằng POST và mang một body, mà `EventSource` chỉ biết GET.
  stream: (
    text: string,
    into: { conversationId?: string; startNew?: boolean } = {},
    onEvent: (event: TurnEvent) => void,
    signal?: AbortSignal,
  ) => streamTurn(text, into, onEvent, signal),
  approve: (assessmentId: string) =>
    call<Approval>("teacher", `/teacher/assessments/${assessmentId}/approve`, {
      method: "POST",
    }),
  unapprove: (assessmentId: string) =>
    call<Approval>(
      "teacher",
      `/teacher/assessments/${assessmentId}/unapprove`,
      { method: "POST" },
    ),
  publishForm: (assessmentId: string) =>
    call<PublishForm>(
      "teacher",
      `/teacher/assessments/${assessmentId}/publish-form`,
    ),
  // `preview` là một cờ trên CHÍNH endpoint phát hành, không phải một endpoint khác. Hộp xác
  // nhận gửi object này với cờ bật, nút trong hộp gửi lại CÙNG object với cờ tắt — nên "hộp
  // xác nhận đọc lại đúng cái sắp xảy ra" là một tính chất của code, không phải một lời hứa.
  publish: (
    assessmentId: string,
    schedules: ClassSchedule[],
    preview: boolean,
  ) =>
    call<PublishResult>(
      "teacher",
      `/teacher/assessments/${assessmentId}/publications`,
      {
        method: "POST",
        body: JSON.stringify({ schedules, preview }),
      },
    ),
  withdraw: (assessmentId: string, classId: string) =>
    call<PublishResult>(
      "teacher",
      `/teacher/assessments/${assessmentId}/publications/${classId}/withdraw`,
      { method: "POST" },
    ),
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
  const response = await fetch(`/api/attempts/${attemptId}/chat/stream`, {
    headers: headers("student"),
  });
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
      const name = lines
        .find((part) => part.startsWith("event: "))
        ?.slice("event: ".length);
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
      if (name === "error")
        throw new Error(data || "Trợ lý chưa trả lời được.");
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

/**
 * Biến giá trị của một ô `datetime-local` thành chuỗi ISO **mang offset địa phương**.
 *
 * Tồn tại vì `toISOString()` sai ở đây, và sai trong im lặng. Nó trả hậu tố `Z`, còn
 * `publication_wording._clock` bên BE in `%H:%M` theo đúng tzinfo nó nhận được — nên gửi `Z`
 * thì giáo viên gõ 14:00 và câu luật đáp lại *"tới hết 07:00"*. HTTP 200, không lỗi nào, và
 * con số sai nằm trên đúng câu mà ADR-03 dành cả tài liệu để chống hiểu nhầm.
 *
 * Offset lấy từ `getTimezoneOffset()`, thứ trả về số phút **cần cộng** để ra UTC — nên dấu
 * ngược với dấu người ta viết: Việt Nam là `-420` và phải in ra `+07:00`.
 *
 * @param local - Giá trị thô của ô nhập, dạng `YYYY-MM-DDTHH:MM`.
 * @returns Cùng mốc đó kèm offset, ví dụ `2026-10-02T08:45:00+07:00`.
 */
export function isoWithOffset(local: string): string {
  const minutes = new Date(local).getTimezoneOffset();
  const sign = minutes <= 0 ? "+" : "-";
  const away = Math.abs(minutes);
  const two = (value: number) => String(value).padStart(2, "0");
  // Giây là bắt buộc: Pydantic nhận được cả hai, nhưng một chuỗi không có giây đọc lên
  // như một mốc thiếu phần, và đây là giá trị đi vào sổ sách phát hành.
  const seconds = local.length === 16 ? ":00" : "";
  return `${local}${seconds}${sign}${two(Math.floor(away / 60))}:${two(away % 60)}`;
}
