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
  /** Lượt chữa nộp gần nhất đã chạm hết giờ: màn xem điểm báo điều ấy (artboard 16b). */
  last_round_ran_out?: boolean;
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
  /** Lúc lượt mở. Đầu màn in `ends_at − started_at` -- độ dài lượt, không phải thời gian còn lại. */
  started_at: string;
  ends_at: string;
  items: RoundItem[];
  /**
   * Mức điểm của một câu làm đúng trong lượt này (`scoring.MARK_REMEDIATED` của BE). Tuỳ chọn chỉ vì
   * bản lượt lưu trong `sessionStorage` từ trước 18/10/2026 không có nó; BE luôn gửi.
   */
  mark_when_right?: number;
  /** Lượt đã hết giờ theo đồng hồ của BE. Chỉ cờ này cho màn hình nộp rồi chuyển đi khi về 0. */
  stopped?: boolean;
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
  /**
   * Câu có bản trong ngân hàng câu hỏi: đề từng được duyệt khi có câu này (ADR-28), hay câu lấy
   * từ ngân hàng ra. Hộp xoá câu đọc nó để nói đúng điều sắp xảy ra.
   */
  in_bank: boolean;
  /** Câu từ đâu tới (ADR-04, việc 17). Chip nguồn trên thẻ đọc nó. */
  source: "kriky" | "bank";
}

/** Một câu trong hộp *Thêm câu từ ngân hàng* (artboard 19b, plan `question-bank-into-draft`). */
export interface PickerRow {
  bank_id: string;
  stem: string;
  learning_objective: string;
  /** Tên đề câu được duyệt cùng: dòng phụ của hàng. */
  from_title: string;
  /** Câu đã có trong đề đang mở: hàng mờ, không chọn được. */
  in_this_paper: boolean;
}

export interface BankPicker {
  questions: PickerRow[];
}

/** Chữ của một câu, như giáo viên vừa sửa. Đủ bộ, không từng mảnh. */
export interface QuestionEdit {
  stem: string;
  learning_objective: string;
  options: TeacherOption[];
  methods: Method[];
}

/**
 * Một ô panel vẽ dù chưa có câu (component `Failed slot`): đã hỏng, hay đang soạn lại sau khi hỏng.
 * `order` cùng dãy số với `TeacherQuestion.order`, nên câu và ô xếp chung (plan `wave-3-draft-panel`).
 */
export interface FailedSlot {
  order: number;
  redrafting: boolean;
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
  failed_slots: FailedSlot[];
  /** Đề xoá được không -- chỉ đề trống (ADR-33). BE quyết; panel chỉ hiện link khi cờ bật. */
  erasable: boolean;
  /** Lấy câu từ ngân hàng được không (việc 17). BE quyết; panel chỉ hiện nút khi cờ bật. */
  bank_pick_open: boolean;
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
  /**
   * Vì sao `Hoàn tác` không bấm được, hoặc rỗng khi còn lùi được.
   *
   * Câu do BE viết, và biểu mẫu hiện nó **trước** cú bấm — cùng khuôn với cách nó
   * chặn một cửa sổ thời gian vô lý. Một nút bấm được rồi mới nhận 409 là một nút
   * hứa một việc hệ thống đã biết là không làm được.
   */
  undo_blocked: string;
}

/**
 * Năm tham số thời gian, dùng chung cho **mọi** lớp của một lần phát hành.
 *
 * Không có `class_id`: một lần phát hành có một khung giờ, và danh sách lớp đi riêng.
 * Biểu mẫu vốn chỉ có **một** bộ ô nhập và vẫn luôn gửi cùng một bộ giá trị cho mọi
 * lớp; từ 06/10/2026 hợp đồng nói đúng điều đó thay vì cho phép diễn tả một thứ màn
 * hình không dựng được. Mọi mốc phải mang offset — xem `isoWithOffset`.
 */
export interface Schedule {
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
  /** Còn thu hồi được không, theo đồng hồ của BE -- FE không tự so giờ máy mình. */
  recallable: boolean;
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
  /**
   * Một trong bốn giá trị của `DocumentState` bên BE. Rail vẽ bốn hình dạng theo nó, và
   * `tools/check_contract.py` so danh sách này với bảng từ vựng trong `packages/contracts`.
   */
  state: "processing" | "ready" | "no_text_layer" | "failed";
  /**
   * Số trang, hoặc `null` khi con số **không tồn tại** (`.txt`, `.md`) hoặc **chưa đo được**.
   * Không bao giờ là `0` cho một tệp không có khái niệm trang. Lúc đang xử lý nó có thể đã mang
   * tổng do tiếng báo tiến độ ghi, nên dòng meta chỉ in nó ở `ready` và `no_text_layer`.
   */
  page_count: number | null;
  /**
   * Tiến độ lúc đang xử lý: số trang đã OCR xong, hoặc bằng `page_count` khi đã đọc hết và đang
   * dựng mục lục. `null` khi chưa nghe tiếng báo nào.
   */
  pages_read: number | null;
  /**
   * Vì sao không dùng được, bằng một câu tiếng Việt. Rỗng khi không có gì sai.
   *
   * Chip **không** in chuỗi này — nó in một nhãn cố định theo `state`, vì `fault` là một câu
   * chẩn đoán cho mỗi cách hỏng (số câu mọc theo code), không phải nhãn. `fault` đi vào `title`, nên rê chuột vẫn
   * phân biệt được *ảnh scan* với *không có trang nào*.
   */
  fault: string;
  uploaded_at: string;
}

export interface Approval {
  assessment_id: string;
  state: string;
  question_count: number;
  still_drafting: number;
}

/**
 * Một câu của một lượt hỏi lại nhiều câu (ADR-32). Lượt `assistant` ấy chở chúng trong
 * `tool_result.questions`, nên đọc lại sau F5 vẫn có.
 */
export interface ClarifyQuestion {
  label: string;
  text: string;
  choices: string[];
}

/**
 * Một dòng trong hội thoại của giáo viên.
 *
 * `kind` là `"teacher"`, `"assistant"`, `"outline"` (dàn ý đề, lời Kriky — vẽ như lời trợ lý),
 * `"notice"` (thông báo hệ thống khi model không có mặt để nói, ADR-30 — dòng riêng, không
 * avatar), `"tool_call"` hay `"tool_result"`. Luật render nằm ở
 * màn hình, không ở đây: `tool_call` không hiện gì (nó không mang kết quả), còn `tool_result`
 * ra một thẻ chọn theo **nấc của đề** — `ActionCard.STATE_OF` dịch `tool_name` thành nấc, và
 * đó là chỗ duy nhất phép dịch ấy xảy ra.
 */
export interface Turn {
  kind: string;
  text: string;
  tool_name: string;
  tool_result: Record<string, unknown>;
  entity_kind: string;
  entity_id: string;
  /**
   * Các phương án bày ra cùng bước này, nếu nó là một câu hỏi lại. BE dựng chúng (ADR-23, hậu ký
   * `unbiased-model-text` T3). Lối "Khác" không nằm ở đây -- thẻ hỏi lại tự vẽ nó; các đoạn chat cũ
   * còn chữ "Khác" cuối danh sách, và `questionIn` lọc nó ra.
   */
  choices: string[];
  more_choices: number;
  model_tokens: number;
  duration_ms: number;
  /**
   * Đề mà bước này nói tới đã bị xoá (chỉ đề trống mới xoá được, ADR-33). Thẻ cũ đọc cờ này để
   * thôi mời mở một đề không còn (plan `wave-3-draft-panel`). Tuỳ chọn vì lượt đang chạy do FE
   * dựng từ sự kiện SSE, và một đề vừa tạo trong lượt ấy thì chưa thể đã xoá.
   */
  entity_gone?: boolean;
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
 * Bề mặt nào đang gọi. Vai được chọn **tại chỗ khai tên endpoint** ở dưới, không suy từ route
 * đang mở: một request bay ra giữa lúc chuyển route sẽ mang sai vai.
 *
 * Từ việc 22 (plan `sign-in-and-accounts`) không header nào chở danh tính: trình duyệt chứng minh
 * bằng cookie phiên `HttpOnly` -- mỗi vai một cookie -- mà BE đặt khi đăng nhập, và `fetch` cùng
 * nguồn tự gửi nó. Vai chỉ còn quyết định **ai bị đưa về màn đăng nhập** khi BE trả 401
 * (`onSignedOut`).
 */
type Role = "student" | "teacher";

const JSON_HEADERS: HeadersInit = { "Content-Type": "application/json" };

/**
 * Header cho một request mang `FormData`: **không** có gì, kể cả `Content-Type`.
 *
 * Một upload multipart cần một boundary, mà boundary thì do trình duyệt sinh ra lúc gửi; khai tay
 * `multipart/form-data` sẽ gửi đi một content type không có boundary, và server đọc được một body
 * rỗng mà không có lỗi nào ở giữa. Rỗng mà vẫn khai, vì `call` dùng `JSON_HEADERS` khi nơi gọi
 * không đưa header nào.
 */
const FORM_HEADERS: HeadersInit = {};

/** Kênh báo *phiên của vai này đã hết* -- một 401 ở bất cứ lời gọi nào (việc 22). */
const signedOut = new EventTarget();

/**
 * Nghe 401 của một vai: phiên hết hạn hay bị đóng giữa lúc đang dùng thì màn hình phải về màn
 * đăng nhập, không đứng yên với một câu lỗi ở một góc.
 *
 * @param role - Vai cần nghe.
 * @param then - Gọi mỗi lần một lời gọi của vai ấy nhận 401.
 * @returns Hàm thôi nghe, cho cleanup của `useEffect`.
 */
export function onSignedOut(role: Role, then: () => void): () => void {
  const heard = () => then();
  signedOut.addEventListener(role, heard);
  return () => signedOut.removeEventListener(role, heard);
}

/** Một response 401 thì báo cho vai của nó. Gọi ở mọi đường đọc lỗi. */
function noticeSignedOut(role: Role, response: Response): void {
  if (response.status === 401) signedOut.dispatchEvent(new Event(role));
}

/**
 * Một lời từ chối của BE: câu tiếng Việt của nó, cộng status.
 *
 * Status đi kèm vì có chỗ phải phân biệt *BE đã trả lời "không"* với *không nói được với BE*:
 * màn lượt chữa chỉ rời đi khi BE nói lượt đã nộp (409), không phải khi mạng chập (plan
 * `wave-2-time-marks-titles`).
 */
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/**
 * Lời từ chối của BE, đọc từ một response không ok: `detail` tiếng Việt nếu có, không thì status.
 * Một chỗ cho ba đường gọi (`call`, `silent`, `download`).
 *
 * @param response - Response không ok.
 */
async function refusal(response: Response): Promise<ApiError> {
  let detail = `Lỗi ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    /* một error body không phải JSON thì vẫn là lỗi; giữ lại phần status text */
  }
  return new ApiError(detail, response.status);
}

/**
 * Gửi một request và biến thất bại thành một lỗi đáng hiện ra.
 *
 * @param role - Bề mặt nào đang gọi. Nó quyết định ai bị đưa về màn đăng nhập khi BE trả 401,
 *   và nó được khai ngay cạnh tên endpoint để không thể gắn nhầm trong im lặng.
 * @param path - Path nằm dưới `/api`.
 * @param init - Tuỳ chọn cho fetch; không đưa header thì là `JSON_HEADERS`.
 * @returns Body đã parse.
 * @throws ApiError mang `detail` của BE khi response không ok, vì mọi lời từ chối
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
    headers: init.headers ?? JSON_HEADERS,
  });
  if (!response.ok) {
    noticeSignedOut(role, response);
    throw await refusal(response);
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
    headers: init.headers ?? JSON_HEADERS,
  });
  if (response.ok) return;
  noticeSignedOut(role, response);
  throw await refusal(response);
}

/**
 * Tải một tệp BE dựng (bảng điểm `.xlsx`, việc 20, plan `results-xlsx-export`) về máy giáo viên.
 *
 * Qua `fetch` chứ không qua một link thường: một tệp bị từ chối phải hiện được câu của BE trên
 * màn, không phải một trang lỗi trong tab mới. Tên tệp lấy từ `filename*` UTF-8 của `Content-Disposition`, để tên tiếng Việt
 * của đề ở nguyên; giải mã hỏng thì lấy `fallback` -- tệp đã tải xong, một tên lạ không đáng một
 * câu lỗi.
 *
 * @param role - Ai đang gọi.
 * @param path - Đường dẫn, không gồm `/api`.
 * @param fallback - Tên tệp khi BE không gửi tên, hay tên không giải mã được.
 * @param init - Phần còn lại của request, cho tệp dựng từ một thân gửi lên (tệp mật khẩu, việc 22,
 *   plan `sign-in-and-accounts`). Header thì luôn là `JSON_HEADERS`.
 * @throws ApiError mang câu của BE khi bị từ chối.
 */
async function download(
  role: Role,
  path: string,
  fallback: string,
  init: RequestInit = {},
): Promise<void> {
  const response = await fetch(`/api${path}`, { ...init, headers: JSON_HEADERS });
  if (!response.ok) {
    noticeSignedOut(role, response);
    throw await refusal(response);
  }
  const named = /filename\*=UTF-8''([^;]+)/.exec(response.headers.get("Content-Disposition") ?? "");
  let name = fallback;
  try {
    if (named) name = decodeURIComponent(named[1]);
  } catch {
    /* `%` sai: giữ tên dự phòng */
  }
  const href = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = href;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Thu hồi **sau** một nhịp: Firefox và Safari cũ huỷ lượt tải nếu URL mất ngay sau `click()`.
  window.setTimeout(() => URL.revokeObjectURL(href), 1000);
}

export const api = {
  /**
   * Tên bản lab của BE (plan `lab-version`), không cần đăng nhập. Gọi thẳng `fetch`, không qua
   * `call`: không có vai nào, và một lần hỏng không được đẩy ai ra màn đăng nhập.
   */
  version: async (): Promise<{ version: string }> => {
    const response = await fetch("/api/version");
    if (!response.ok) throw new Error(`/api/version: ${response.status}`);
    return response.json();
  },
  me: () => call<Me>("student", "/me"),
  /**
   * Đăng nhập học sinh (Figma 12) bằng tên đăng nhập và mật khẩu giáo viên phát. BE đặt cookie
   * phiên; lời đáp không có thân, nên người gọi đọc `me()` ngay sau.
   */
  signIn: (username: string, password: string) =>
    silent("student", "/sign-in", { method: "POST", body: JSON.stringify({ username, password }) }),
  /** Đăng xuất học sinh: BE xoá phiên và cookie. */
  signOut: () => silent("student", "/sign-out", { method: "POST" }),
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
  /** Đọc lại một lượt đang mở -- câu và lựa chọn đã lưu -- cho tab mới hay sau F5. */
  round: (roundId: string) => call<OpenRound>("student", `/rounds/${roundId}`),
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
  /** Tool của bước, cho ba sự kiện `step_*`: tên bước lấy từ `STEP_TITLE` như sau F5. */
  tool_name?: string;
  /** Kết quả của một bước tra cứu ở pha lên plan — đúng thứ đọc lại được sau F5; `null` cho bước của plan. */
  result?: Record<string, unknown> | null;
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
/**
 * Đọc một `text/event-stream` và nhả ra từng khung một.
 *
 * Tồn tại vì vòng lặp này từng có **hai** bản sao trong file, và bản thứ ba là lúc phải rút
 * nó ra. Hai bản ấy không giống hệt nhau — một bản chỉ đọc `data:`, bản kia đọc cả `event:`
 * và nối nhiều dòng `data:` — nên thứ dùng chung được là *khung*, không phải cách hiểu khung.
 * Người gọi tự quyết định làm gì với `name` và `data`.
 *
 * Khung chỉ có comment (dòng mở đầu bằng `:`) bị **bỏ qua** tại đây, đúng như đặc tả SSE nói.
 * Nhịp tim của kênh tài liệu đi theo đường ấy, nên nó không bao giờ tới tay người gọi -- muốn
 * biết kênh còn sống thì nghe `onBytes`.
 *
 * @param body - Thân response đang stream.
 * @param onBytes - Gọi mỗi lần có byte tới, kể cả byte chỉ mang nhịp tim.
 * @param stop - Huỷ thì nhả reader, để một kênh câm cũng kết thúc được vòng lặp.
 * @returns Một async iterator các khung đã tách.
 */
async function* sseFrames(
  body: ReadableStream<Uint8Array>,
  onBytes?: () => void,
  stop?: AbortSignal,
): AsyncGenerator<{ name?: string; data: string }> {
  const reader = body.getReader();
  stop?.addEventListener("abort", () => void reader.cancel().catch(() => undefined), {
    once: true,
  });
  const decoder = new TextDecoder();
  let rest = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    onBytes?.();
    rest += decoder.decode(value, { stream: true });

    const frames = rest.split("\n\n");
    rest = frames.pop() ?? "";
    for (const frame of frames) {
      const lines = frame.split("\n");
      const name = lines
        .find((part) => part.startsWith("event: "))
        ?.slice("event: ".length);
      // Mọi dòng `data:`, nối lại bằng ký tự xuống dòng — đúng như định dạng quy định cho
      // một field lặp lại. Chỉ đọc dòng đầu tiên thì mọi nội dung có dấu xuống dòng đều bị
      // cắt ngắn mà không báo gì.
      const carrying = lines.filter((part) => part.startsWith("data: "));
      if (carrying.length === 0 && name === undefined) continue;
      yield { name, data: carrying.map((part) => part.slice("data: ".length)).join("\n") };
    }
  }
}

async function streamTurn(
  text: string,
  into: { conversationId?: string; startNew?: boolean; documentId?: string },
  onEvent: (event: TurnEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/teacher/chat/messages/stream", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      text,
      conversation_id: into.conversationId ?? null,
      start_new: into.startNew ?? false,
      // Chip đang đính (`draft-from-document`). BE chỉ dùng nó khi tài liệu thuộc giáo viên và đã
      // sẵn sàng, và lưu nó cùng câu này -- nên câu sau, khi chip đã rời ô nhập, vẫn nói về cùng
      // cuốn sách.
      document_id: into.documentId ?? null,
    }),
    signal,
  });
  if (!response.ok || response.body === null) {
    // 401 ở đây là phiên vừa hết giữa lúc đang soạn: về hộp đăng nhập như mọi lời gọi khác
    // (review pha 3 của `sign-in-and-accounts`), kèm câu của BE thay cho một *"Lỗi 401"*.
    noticeSignedOut("teacher", response);
    if (!response.ok) throw await refusal(response);
    throw new Error(`Lỗi ${response.status}`);
  }

  for await (const frame of sseFrames(response.body)) {
    onEvent(JSON.parse(frame.data) as TurnEvent);
  }
}

// ---------------------------------------------------------------- các màn của rail giáo viên
// Plan `teacher-rail-screens` (việc 18). Mọi nhãn, mọi con số phụ thuộc giờ hay vòng đời đề đều do BE
// dựng (`be/teacher_reads.py`); các màn chỉ vẽ.

/** Ba con số tiến độ của một đề đang mở trong một lớp -- một dòng của popover. */
export interface PaperProgress {
  assessment_id: string;
  title: string;
  not_submitted: number;
  phase_one: number;
  phase_two: number;
}

/** Một dòng của màn *Danh sách lớp học*. Ba cột tiến độ là `null` khi lớp không có đề đang mở. */
export interface ClassRow {
  class_id: string;
  name: string;
  student_count: number;
  /** *Khối / môn*, suy từ các đề đã phát hành cho lớp; rỗng khi lớp chưa nhận đề nào. */
  courses: string;
  open_count: number;
  not_submitted: number | null;
  phase_one: number | null;
  phase_two: number | null;
  by_paper: PaperProgress[];
}

export interface ClassList {
  classes: ClassRow[];
  student_total: number;
}

export interface PaperInClass {
  assessment_id: string;
  title: string;
  status: string;
  /** Mã chặng của nhãn: `not_yet`, `open`, `remediating`, `over`. */
  phase: string;
  opens_at: string;
  closes_at: string;
  submitted: number;
  student_count: number;
}

export interface StudentRow {
  student_id: string;
  full_name: string;
  student_code: string;
  /** Trống ở em có từ trước việc 22, tới lần *Đặt lại mật khẩu* đầu tiên. */
  username: string | null;
}

/**
 * Một dòng của bảng xem trước khi thêm học sinh (Figma 28b, việc 22, plan `sign-in-and-accounts`).
 * `username` là tên **sẽ** cấp; `duplicate` khi lớp -- hay dòng trên của loạt này -- đã có em cùng
 * họ tên.
 */
export interface RosterRow {
  full_name: string;
  username: string;
  note: "new" | "duplicate";
}

/** Một tài khoản vừa tạo hay vừa đặt lại mật khẩu: mật khẩu rõ, **chỉ lần này** (Figma 28c, 10b). */
export interface RosterAccount {
  student_id: string;
  full_name: string;
  student_code: string;
  username: string;
  password: string;
}

export interface ClassDetail {
  class_id: string;
  name: string;
  student_count: number;
  courses: string;
  papers: PaperInClass[];
  students: StudentRow[];
  /** Lớp xoá được không: chỉ lớp rỗng (plan `erase-empty-class`). Luật là của BE. */
  erasable: boolean;
}

/** Một đề trên màn *Các bài kiểm tra*. `status` là nhãn BE dựng theo vòng đời và giờ BE. */
export interface PaperRow {
  assessment_id: string;
  title: string;
  status: string;
  /** Mã chặng khi đề đã phát hành; rỗng khi chưa. */
  phase: string;
  classes: string[];
  first_class_id: string;
  opens_at: string | null;
  remediation_deadline: string | null;
  recallable: boolean;
  shows_results: boolean;
  conversation_id: string;
}

export interface PaperList {
  papers: PaperRow[];
  running: number;
}

export interface ResultRow {
  student_id: string;
  full_name: string;
  /** Tổng điểm, trên thang `question_count` (ADR-16). */
  mark: number;
  first_try: number;
  minutes: number;
  submitted_at: string;
  note: string;
}

export interface ClassResults {
  assessment_id: string;
  title: string;
  class_id: string;
  class_name: string;
  question_count: number;
  submitted: number;
  student_count: number;
  closes_at: string;
  highest: number | null;
  mean: number | null;
  median: number | null;
  lowest: number | null;
  /** `question_count` ô: ô `k` đếm bài trong [k, k+1), bài trọn điểm gộp vào ô cuối. */
  distribution: number[];
  rows: ResultRow[];
}

export interface WorkItem {
  order: number;
  stem: string;
  chosen: string;
  correct: string;
  mark: number;
}

export interface StudentWork {
  student_id: string;
  full_name: string;
  student_code: string;
  assessment_id: string;
  title: string;
  class_id: string;
  class_name: string;
  question_count: number;
  submitted_at: string | null;
  state: string | null;
  /** Chữ của trạng thái giai đoạn 2, cùng bảng với ghi chú của màn kết quả; rỗng khi chưa nộp. */
  note: string;
  mark: number;
  first_try: number;
  rounds_done: number;
  reports: number;
  items: WorkItem[];
}

export interface BankRow {
  bank_id: string;
  stem: string;
  learning_objective: string;
  course: string;
}

export interface BankList {
  questions: BankRow[];
  approvals: number;
}

/** Một dòng của hàng đợi *Cần bạn xem* (màn 20, plan `dashboard-review-queue`). */
export interface ReviewItem {
  /** `reports`: giải thích chưa rõ, một dòng mỗi đề. `wrong_rate`: một dòng mỗi câu. */
  kind: "reports" | "wrong_rate";
  assessment_id: string;
  /** Câu của dòng `wrong_rate`; rỗng ở dòng `reports`. */
  question_id: string;
  title: string;
  meta: string;
  /** Cột số liệu: *"3 lượt báo cáo"*, *"72% bài sai"*. */
  figure: string;
}

/** Điểm gộp của một lớp, thang 10, chỉ đề đã hết hạn chữa. */
export interface ClassStat {
  class_id: string;
  name: string;
  papers: number;
  mean: number | null;
  highest: number | null;
  lowest: number | null;
  /** Mục kiến thức sai nhiều nhất, kèm tỉ lệ; rỗng khi chưa có bài. */
  weakest: string;
}

export interface Board {
  queue: ReviewItem[];
  classes: ClassStat[];
  objectives: { learning_objective: string; percent: number }[];
}

/** Một báo cáo trên màn 25. */
export interface ReportCard {
  report_id: string;
  student: string;
  class_name: string;
  created_at: string;
  note: string;
  /** Số các câu em ấy làm sai ở lần đầu. */
  wrong: number[];
}

export interface ReportedQuestion {
  question_id: string;
  order: number;
  stem: string;
  /** Bao nhiêu em báo cáo làm sai câu này. */
  wrong_by: number;
  /** Dòng ngân hàng của câu; rỗng thì không có nút sửa. */
  bank_id: string;
}

export interface PaperReports {
  assessment_id: string;
  title: string;
  classes: string[];
  reporters: number;
  reports: ReportCard[];
  questions: ReportedQuestion[];
}

/** Màn 29: một câu có tỉ lệ sai cao, chỉ đọc. */
export interface WrongRateQuestion {
  question_id: string;
  assessment_id: string;
  order: number;
  title: string;
  stem: string;
  methods: Method[];
  options: (TeacherOption & { percent: number })[];
  /** Tỉ lệ bài bỏ trống câu này, cùng mẫu số với các phương án. */
  unanswered: number;
  submitted: number;
  wrong_percent: number;
  classes: string[];
  bank_id: string;
  seen: boolean;
}

/** Hộp đọc đoạn chat hỏi trợ lý của lượt có báo cáo (artboard 25b). */
export interface ReportChat {
  student: string;
  title: string;
  class_name: string;
  messages: { role: "student" | "assistant"; text: string; created_at: string }[];
}

export interface BankDetail {
  bank_id: string;
  stem: string;
  learning_objective: string;
  course: string;
  options: TeacherOption[];
  methods: Method[];
}

export const teacher = {
  me: () => call<TeacherMe>("teacher", "/teacher/me"),
  /**
   * Đăng nhập bằng SĐT **hoặc** email (Figma 26). BE đặt cookie phiên; lời đáp không có thân,
   * nên người gọi đọc `me()` ngay sau.
   */
  signIn: (login: string, password: string) =>
    silent("teacher", "/teacher/sign-in", {
      method: "POST",
      body: JSON.stringify({ login, password }),
    }),
  /** Tạo tài khoản rồi đăng nhập luôn (Figma 26b). Cả SĐT lẫn email đều bắt buộc. */
  signUp: (account: { full_name: string; phone: string; email: string; password: string }) =>
    silent("teacher", "/teacher/sign-up", { method: "POST", body: JSON.stringify(account) }),
  /** Đăng xuất: BE xoá phiên và cookie. */
  signOut: () => silent("teacher", "/teacher/sign-out", { method: "POST" }),
  documents: () => call<TeacherDocument[]>("teacher", "/teacher/documents"),
  /**
   * Nghe kênh thư viện và gọi `onChange` mỗi lần có gì đó đổi.
   *
   * **Kênh chỉ hích, không chở dữ liệu**: mỗi khung chỉ nói *có gì đó đổi*, nên `onChange`
   * phải tự gọi lại `documents()`. Nghe có vẻ vòng vo, nhưng nó là thứ làm kênh tự lành —
   * pub/sub của Redis không giữ lịch sử, nên một khung chở dữ liệu mà mất đi là một chip sai
   * vĩnh viễn, còn một tiếng hích mất đi thì tiếng sau sửa luôn.
   *
   * Dùng `fetch` chứ không `EventSource`: khi còn header `X-Actor`, `EventSource` không gửi
   * được nó; nay cookie phiên đi theo cả hai, nhưng `fetch` còn cho đọc status -- một 401 phải
   * đưa về hộp đăng nhập chứ không nối lại mãi (việc 22, plan `sign-in-and-accounts`).
   *
   * Không ném khi kênh gãy, mà **nối lại**, mãi tới khi `signal` huỷ. Byte **đầu tiên** của mỗi
   * lần nối -- BE gửi khung `: mở` ngay sau khi đã subscribe -- làm `onChange` chạy một lần: tiếng
   * hích bắn ra lúc kênh gãy, hay trước lúc BE kịp subscribe, không ai nghe, và một chip đứng ở
   * *đang xử lý* cho tới khi giáo viên tự F5 là đúng thứ ADR-27 cấm (gặp ngày 12/10/2026, khi tab
   * mở đúng lúc BE đứng).
   *
   * Kênh **câm** quá `silenceMs` cũng bị coi là gãy. BE phát nhịp tim mỗi 15 s; khi BE chết, proxy
   * của Vite ghi `ECONNRESET` nhưng không đóng phía trình duyệt, nên không im lặng nào kết thúc
   * cả -- một lần *Rerun* BE trong PyCharm là đủ để mọi tab mất kênh mãi.
   *
   * Lần chờ giữa hai lần nối gấp đôi sau mỗi lần hỏng, tới trần 30 s, và chỉ về lại `retryMs`
   * khi một lần nối sống qua được một nhịp tim. Không có Redis thì BE mở kênh rồi đóng ngay;
   * nối lại đều đặn mỗi 3 s là hai request mỗi 3 s từ mỗi tab, mãi mãi.
   *
   * @param onChange - Gọi một lần cho mỗi tiếng hích, và một lần ở byte đầu của mỗi lần nối.
   * @param signal - Đóng kênh khi màn hình rời đi.
   * @param retryMs - Lần chờ ngắn nhất giữa hai lần nối.
   * @param silenceMs - Không byte nào trong chừng ấy thì cắt kênh; hơn hai nhịp tim của BE.
   * @returns Một promise kết thúc khi `signal` huỷ.
   */
  watchDocuments: async (
    onChange: () => void,
    signal?: AbortSignal,
    retryMs = 3_000,
    silenceMs = 40_000,
  ): Promise<void> => {
    let failures = 0;
    while (!signal?.aborted) {
      // Một controller cho mỗi lần nối: bộ canh im lặng cắt đúng lần nối này, còn `signal`
      // của màn hình thì cắt cả vòng.
      const dial = new AbortController();
      const cut = () => dial.abort();
      signal?.addEventListener("abort", cut, { once: true });
      let silence = setTimeout(cut, silenceMs);
      let heard = false;
      const alive = () => {
        clearTimeout(silence);
        silence = setTimeout(cut, silenceMs);
        if (!heard && !dial.signal.aborted) onChange();
        heard = true;
      };
      const opened = Date.now();
      try {
        const response = await fetch("/api/teacher/documents/stream", {
          headers: JSON_HEADERS,
          signal: dial.signal,
        });
        if (response.status === 401) {
          noticeSignedOut("teacher", response);
          return;
        }
        if (response.ok && response.body) {
          for await (const _ of sseFrames(response.body, alive, dial.signal)) {
            if (dial.signal.aborted) break;
            onChange();
          }
        }
      } catch {
        // Huỷ bỏ lúc rời màn hình, hay bộ canh im lặng cắt, cũng rơi vào đây; không phải lỗi.
      } finally {
        clearTimeout(silence);
        signal?.removeEventListener("abort", cut);
      }
      if (signal?.aborted) return;
      // Sống qua một nhịp tim của BE (15 s) mới tính là một lần nối lành.
      failures = heard && Date.now() - opened >= 15_000 ? 0 : failures + 1;
      const wait = Math.min(retryMs * 2 ** Math.max(failures - 1, 0), 30_000);
      await new Promise<void>((resolve) => {
        const stop = () => {
          clearTimeout(timer);
          resolve();
        };
        const timer = setTimeout(() => {
          signal?.removeEventListener("abort", stop);
          resolve();
        }, wait);
        signal?.addEventListener("abort", stop, { once: true });
      });
    }
  },
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return call<TeacherDocument>("teacher", "/teacher/documents", {
      method: "POST",
      body: form,
      headers: FORM_HEADERS,
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
  // Xoá một câu khỏi đề còn mở. Bản trong ngân hàng câu hỏi, nếu có, ở lại (ADR-28); các câu
  // sau dồn số lên, nên nơi gọi đọc lại cả đề chứ không tự bỏ một thẻ.
  deleteQuestion: (assessmentId: string, questionId: string) =>
    silent(
      "teacher",
      `/teacher/assessments/${assessmentId}/questions/${questionId}`,
      { method: "DELETE" },
    ),
  assessment: (assessmentId: string) =>
    call<AssessmentDetail>("teacher", `/teacher/assessments/${assessmentId}`),
  // Ngân hàng nhìn từ một đề đang mở, và chép các câu đã chọn vào cuối đề (việc 17). BE trả lại cả
  // đề, nên panel vẽ ngay mà không đọc thêm lần nào.
  bankPicker: (assessmentId: string) =>
    call<BankPicker>("teacher", `/teacher/assessments/${assessmentId}/bank-picker`),
  addFromBank: (assessmentId: string, bankIds: string[]) =>
    call<AssessmentDetail>("teacher", `/teacher/assessments/${assessmentId}/bank-questions`, {
      method: "POST",
      body: JSON.stringify({ bank_ids: bankIds }),
    }),
  // Các màn của rail (plan `teacher-rail-screens`). Chỉ đọc, trừ sửa bản ngân hàng.
  classes: () => call<ClassList>("teacher", "/teacher/classes"),
  classDetail: (classId: string) => call<ClassDetail>("teacher", `/teacher/classes/${classId}`),
  /**
   * Xoá cứng một lớp **rỗng** (plan `erase-empty-class`, hậu ký ADR-13). 409 khi lớp còn học sinh
   * hay đã nhận đề, mang câu tiếng Việt của BE trong `message`.
   */
  eraseClass: (classId: string) =>
    silent("teacher", `/teacher/classes/${classId}`, { method: "DELETE" }),
  /**
   * Mở một lớp rỗng (plan `tao-lop`). 409 khi giáo viên đã có lớp cùng tên, 422 khi tên rỗng hay
   * quá dài; cả hai mang câu tiếng Việt của BE trong `message`.
   */
  createClass: (name: string) =>
    call<{ class_id: string; name: string }>("teacher", "/teacher/classes", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  /**
   * Bảng xem trước khi thêm học sinh (việc 22, plan `sign-in-and-accounts`, Figma 28b), từ các tên
   * đã gõ. Không ghi gì ở BE.
   */
  rosterPreview: (classId: string, names: string[]) =>
    call<{ rows: RosterRow[] }>("teacher", `/teacher/classes/${classId}/roster/preview`, {
      method: "POST",
      body: JSON.stringify({ names }),
    }),
  /** Như `rosterPreview`, từ một tệp `.csv`/`.xlsx` một cột họ tên. `FormData`, không `Content-Type`. */
  rosterPreviewFile: (classId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return call<{ rows: RosterRow[] }>(
      "teacher",
      `/teacher/classes/${classId}/roster/preview-file`,
      { method: "POST", body: form, headers: FORM_HEADERS },
    );
  },
  /**
   * Tạo tài khoản (Figma 28c). BE tính lại mọi thứ và chỉ tạo dòng mới hay dòng trùng đã xác nhận;
   * mật khẩu rõ chỉ có trong lời đáp này.
   */
  rosterCreate: (classId: string, rows: { full_name: string; confirmed: boolean }[]) =>
    call<{ accounts: RosterAccount[]; skipped: number }>(
      "teacher",
      `/teacher/classes/${classId}/roster`,
      { method: "POST", body: JSON.stringify({ rows }) },
    ),
  // Tệp mật khẩu dựng từ chính các dòng đang hiện -- BE không giữ mật khẩu nào (Decision 3 của plan
  // `sign-in-and-accounts`).
  rosterPasswords: (classId: string, rows: RosterAccount[]) =>
    download("teacher", `/teacher/classes/${classId}/roster/passwords.xlsx`, "mat-khau.xlsx", {
      method: "POST",
      body: JSON.stringify({
        rows: rows.map(({ full_name, username, password }) => ({ full_name, username, password })),
      }),
    }),
  /** *Đặt lại mật khẩu* (Figma 10b): mật khẩu mới một lần; BE đóng mọi phiên cũ của em. */
  resetPassword: (classId: string, studentId: string) =>
    call<RosterAccount>("teacher", `/teacher/classes/${classId}/students/${studentId}/password`, {
      method: "POST",
    }),
  papers: () => call<PaperList>("teacher", "/teacher/assessments"),
  // Bảng điểm `.xlsx` của một đề trong một lớp (việc 20). Chỉ tác giả; BE từ chối người khác.
  exportResults: (classId: string, assessmentId: string) =>
    download(
      "teacher",
      `/teacher/classes/${classId}/assessments/${assessmentId}/results.xlsx`,
      "bang-diem.xlsx",
    ),
  classResults: (classId: string, assessmentId: string) =>
    call<ClassResults>(
      "teacher",
      `/teacher/classes/${classId}/assessments/${assessmentId}/results`,
    ),
  studentWork: (classId: string, assessmentId: string, studentId: string) =>
    call<StudentWork>(
      "teacher",
      `/teacher/classes/${classId}/assessments/${assessmentId}/students/${studentId}`,
    ),
  bank: () => call<BankList>("teacher", "/teacher/bank"),
  bankQuestion: (bankId: string) => call<BankDetail>("teacher", `/teacher/bank/${bankId}`),
  // Sửa **bản trong ngân hàng**; câu đã nằm trong đề giữ nguyên (người dùng chốt 18/10/2026).
  editBankQuestion: (bankId: string, question: QuestionEdit) =>
    call<BankDetail>("teacher", `/teacher/bank/${bankId}`, {
      method: "PATCH",
      body: JSON.stringify(question),
    }),
  // Bảng theo dõi (plan `dashboard-review-queue`). Chỉ đọc, trừ hai lần *đánh dấu đã xem*.
  board: () => call<Board>("teacher", "/teacher/board"),
  boardReports: (assessmentId: string) =>
    call<PaperReports>("teacher", `/teacher/board/reports/${assessmentId}`),
  // Chỉ các báo cáo màn hình đã hiện: một báo cáo đến trong lúc đang đọc thì ở lại.
  seeReports: (assessmentId: string, reportIds: string[]) =>
    silent("teacher", `/teacher/board/reports/${assessmentId}/seen`, {
      method: "POST",
      body: JSON.stringify({ report_ids: reportIds }),
    }),
  boardQuestion: (questionId: string) =>
    call<WrongRateQuestion>("teacher", `/teacher/board/questions/${questionId}`),
  seeQuestion: (questionId: string) =>
    silent("teacher", `/teacher/board/questions/${questionId}/seen`, { method: "POST" }),
  reportChat: (reportId: string) =>
    call<ReportChat>("teacher", `/teacher/board/chat/${reportId}`),
  // Xoá cứng một đề nháp **trống** (ADR-33, plan `wave-3-draft-panel`). BE từ chối đề còn câu hay
  // ô đang soạn; nơi gọi đọc lại đoạn chat để thẻ cũ thành *"Đề trống này đã xoá"*.
  eraseDraft: (assessmentId: string) =>
    silent("teacher", `/teacher/assessments/${assessmentId}`, { method: "DELETE" }),
  // Soạn lại một câu đã hỏng -- nút *Thử lại* của ô hỏng. BE bắn lại đúng mục dàn ý của ô; nơi
  // gọi đọc lại đề để thấy ô sang *đang soạn lại* (plan `wave-3-draft-panel`).
  redraft: (assessmentId: string, order: number) =>
    silent("teacher", `/teacher/assessments/${assessmentId}/slots/${order}/redraft`, {
      method: "POST",
    }),
  // Đổi tên một đề chưa duyệt (ADR-31). BE từ chối tên trống, quá 60 ký tự, hay đề đã khoá; mọi
  // chỗ khác đọc tên lúc hiện, nên đổi ở đây là đổi cả thẻ cũ trong đoạn chat.
  renameAssessment: (assessmentId: string, title: string) =>
    call<{ assessment_id: string; title: string }>(
      "teacher",
      `/teacher/assessments/${assessmentId}`,
      { method: "PATCH", body: JSON.stringify({ title }) },
    ),
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
    into: { conversationId?: string; startNew?: boolean; documentId?: string } = {},
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
    schedule: Schedule,
    classIds: string[],
    preview: boolean,
  ) =>
    call<PublishResult>(
      "teacher",
      `/teacher/assessments/${assessmentId}/publications`,
      {
        method: "POST",
        body: JSON.stringify({ schedule, class_ids: classIds, preview }),
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
 * sự thật: BE stream chữ trong lúc model viết và chỉ lưu lượt khi model xong, ngay
 * trước `done`. Nơi gọi tải lại lịch sử sau đó chứ không tin vào thứ nó tự ghép ở
 * đây -- mất kết nối giữa chừng thì lượt có thể chưa được lưu.
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
    headers: JSON_HEADERS,
  });
  if (!response.ok || response.body === null) {
    // 401 là phiên vừa hết: về màn đăng nhập như mọi lời gọi khác (review pha 5).
    noticeSignedOut("student", response);
    // 429 của bộ chặn request dồn (`be/burst_limit.py`) mang câu riêng cho học sinh: đọc nó.
    if (response.status === 429) {
      const said = await response.json().catch(() => null);
      if (typeof said?.detail === "string") throw new Error(said.detail);
    }
    throw new Error("Trợ lý chưa trả lời được.");
  }

  for await (const { name, data } of sseFrames(response.body)) {
    if (name === "chunk") onChunk(data);
    // Stream bắt đầu trước khi BE biết model có trả lời được hay không, nên
    // thất bại về tới đây chứ không về dưới dạng một status code.
    if (name === "error") throw new Error(data || "Trợ lý chưa trả lời được.");
  }
}

/**
 * Nối một danh sách theo cách nói tiếng Việt: *"a và b"*, *"a, b và c"* — không phải *"a và b và
 * c"* (review ảnh, plan `backlog-tier-1`). Một chỗ cho mọi màn hình đọc tên lên.
 */
export function listed(names: string[]): string {
  if (names.length < 3) return names.join(" và ");
  return `${names.slice(0, -1).join(", ")} và ${names[names.length - 1]}`;
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
