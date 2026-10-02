import { type Turn } from "../../api";
import { type Step } from "./Steps";

/**
 * Việc mỗi tool hiện thành gì: một **bước** trong khối `Thinking`, hay một **thẻ** kết quả.
 *
 * Đây là bản cài đặt của bảng trong `docs/overview/teacher-surface.md`, và là chỗ duy nhất
 * được phép quyết chuyện đó. Luật: một lượt sinh ra **tối đa một thẻ** — chỉ kết quả cuối
 * cùng có hậu quả cho giáo viên mới lên thẻ, mọi bước trung gian ở lại trong `Thinking`.
 * Thiếu một dòng ở đây thì tool mới chỉ là một bước, và đó là mặc định an toàn: một bước
 * không hứa gì.
 */
const STEP_TITLE: Record<string, string> = {
  find_class: "Tìm lớp",
  class_assessment_summary: "Xem các đề của lớp",
  create_draft: "Tạo đề trống",
  start_drafting: "Soạn câu hỏi",
  draft_progress: "Kiểm tiến độ soạn",
  "teacher.approve": "Duyệt đề",
  "teacher.unapprove": "Bỏ duyệt",
  "teacher.publish": "Phát hành",
};

/**
 * Một bước đã lưu, đọc thành một dòng trong khối `Thinking`.
 *
 * Dòng kết quả chỉ nói lại những con số **chính `tool_result` ấy mang theo**. Không có con
 * số nào thì không có dòng nào: một bước im lặng vẫn thật, còn một dòng bịa thì không.
 *
 * @param turn - Lượt `tool_result` đã lưu.
 * @returns Bước để vẽ, với dấu `done` hoặc `failed`.
 */
export function stepFor(turn: Turn): Step {
  const result = turn.tool_result;
  const refused = refusal(result);
  return {
    mark: refused ? "failed" : "done",
    // Tool chưa có trong bảng vẫn phải đọc được bằng tiếng người. In `turn.tool_name` ra
    // đây là thả một định danh máy lên bề mặt giáo viên, đúng thứ `teacher-surface.md` cấm.
    title: STEP_TITLE[turn.tool_name] ?? "Một bước nữa",
    result: refused ? dash(String(result.reason ?? "")) : dash(outcome(turn)),
  };
}

/** Lời từ chối của một tool: ba cờ, cùng một nghĩa. */
function refusal(result: Record<string, unknown>): boolean {
  return result.found === false || result.created === false || result.started === false;
}

/** `— ` đứng trước dòng kết quả, đúng như thiết kế; chuỗi rỗng thì vẫn rỗng. */
function dash(text: string): string {
  return text === "" ? "" : `— ${text}`;
}

/** Con số của một bước đã xong, lấy từ chính kết quả của nó. */
function outcome(turn: Turn): string {
  const result = turn.tool_result;
  if (turn.tool_name === "find_class") {
    return `${String(result.name ?? "")}, ${Number(result.student_count ?? 0)} học sinh`;
  }
  if (turn.tool_name === "create_draft") {
    return `đề "${String(result.title ?? "")}", cần ${Number(result.question_count ?? 0)} câu`;
  }
  if (turn.tool_name === "start_drafting") {
    return `${Number(result.queued ?? 0)} câu bắt đầu soạn`;
  }
  if (turn.tool_name === "draft_progress") {
    const written = Array.isArray(result.written) ? result.written.length : 0;
    const asked = Number(result.asked_for ?? 0);
    const running = Number(result.still_drafting ?? 0);
    const base = `${written}/${asked} câu đã về`;
    return running > 0 ? `${base}, còn ${running} đang soạn` : base;
  }
  return "";
}

/**
 * Lượt nào trong một khối được lên thẻ, hay không lượt nào cả.
 *
 * Quét **ngược** và lấy cái đầu tiên đủ tư cách: thẻ kể kết quả của lượt, mà kết quả thì là
 * thứ xảy ra sau cùng. `start_drafting` không bao giờ đủ tư cách — Figma không có variant
 * nào cho nó, và một thẻ ở đó nói với giáo viên rằng một việc đã xong trong khi nó vừa mới
 * bắt đầu.
 *
 * @param turns - Các lượt của một khối Kriky, theo thứ tự đã xảy ra.
 * @returns Lượt được lên thẻ, hoặc `null`.
 */
export function cardTurn(turns: Turn[]): Turn | null {
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    const turn = turns[index];
    if (turn.kind !== "tool_result") continue;
    if (turn.tool_name === "start_drafting") continue;
    if (turn.tool_name === "find_class" || turn.tool_name === "class_assessment_summary") continue;
    // Đề chưa có câu nào thì `draft_progress` chưa phải một kết quả, nó mới là một lần ngó.
    if (turn.tool_name === "draft_progress") {
      const written = Array.isArray(turn.tool_result.written) ? turn.tool_result.written.length : 0;
      if (written === 0) continue;
    }
    return turn;
  }
  return null;
}

/**
 * Biên bản một hành động đã xảy ra, đặt trong luồng chat.
 *
 * Mọi chữ lấy từ **chính `tool_result` ấy**, và mọi nhãn nút lấy từ component
 * `Action result card` (`10:63`). Hai luật của cả tám variant:
 *
 * - **Mỗi thẻ mang một câu an toàn** nói việc vừa xong chưa tới tay học sinh. ADR-05 đặt ba
 *   cổng cho con người bước qua; một thẻ kể rằng máy vừa làm xong một việc mà im lặng về
 *   phần còn lại là một thẻ mời người ta tưởng là xong.
 * - **Nút mời bước tiếp theo**, không phải `Xem`. `Xem` luôn là nút phụ.
 *
 * Hai variant chưa dựng được, và lý do nằm ở dữ liệu chứ không ở màn hình: *tạo-lớp* không
 * có tool nào sinh ra, còn *phát-hành-thất-bại* không bao giờ tới đây vì `_note_publication`
 * chỉ ghi các lớp **thành công** — biểu mẫu phát hành phải tự hiện phần thất bại tại chỗ.
 *
 * @param turn - Bước đã lưu.
 * @param onOpen - Mở panel của một đề.
 * @param onPublish - Mở biểu mẫu phát hành của một đề.
 * @param onCompose - Điền sẵn một câu vào ô nhập. Đây là cách một nút *mời bước tiếp theo*
 *   khi bước ấy làm bằng lời nói chứ không bằng một endpoint — chuỗi rỗng là chỉ đặt con
 *   trỏ vào ô nhập.
 */
export default function ActionCard({
  turn,
  onOpen,
  onPublish,
  onCompose,
}: {
  turn: Turn;
  onOpen: (assessmentId: string) => void;
  onPublish: (assessmentId: string) => void;
  onCompose: (text: string) => void;
}) {
  const result = turn.tool_result;
  const paper = String(result.assessment_id ?? turn.entity_id ?? "");
  const title = String(result.title ?? "");
  const named = title === "" ? "" : ` "${title}"`;
  const see = paper === "" ? [] : [{ label: "Xem", onClick: () => onOpen(paper) }];

  // Một tool từ chối: `reason` là câu của BE, in nguyên văn. Viết hoa hay thêm dấu chấm vào
  // đó là viết lại lời người khác, và câu gốc là câu đã được cân nhắc.
  if (refusal(result)) {
    return (
      <Card
        tone="refused"
        head="Không tạo được đề"
        detail={String(result.reason ?? "")}
        safety="Chưa có gì được thay đổi"
        actions={[{ label: "Thử lại", onClick: () => onCompose(""), primary: true }]}
      />
    );
  }

  if (turn.tool_name === "create_draft") {
    return (
      <Card
        tone=""
        head={`Đã tạo đề${named}`}
        detail="Chưa có câu hỏi nào"
        safety="Đề trống, chưa phát hành được"
        actions={[
          { label: "Thêm câu hỏi", onClick: () => onCompose("Soạn câu hỏi cho đề này"), primary: true },
        ]}
      />
    );
  }

  if (turn.tool_name === "draft_progress") {
    const written = Array.isArray(result.written) ? result.written.length : 0;
    const running = Number(result.still_drafting ?? 0);
    return (
      <Card
        tone=""
        head={`Đã thêm ${written} câu vào đề`}
        detail={running > 0 ? `${title} · còn ${running} câu đang soạn` : title}
        safety="Chưa duyệt · chưa phát hành"
        // Chỉ một nút: cổng duyệt nằm trong panel, nên `Duyệt đề` và `Xem` sẽ mở đúng
        // cùng một chỗ. Hai nhãn khác nhau cho một hành vi là một lời hứa rỗng.
        actions={
          paper === "" ? [] : [{ label: "Duyệt đề", onClick: () => onOpen(paper), primary: true }]
        }
      />
    );
  }

  if (turn.tool_name === "teacher.approve") {
    return (
      <Card
        tone=""
        head={`Đã duyệt đề${named}`}
        detail={`${Number(result.questions ?? 0)} câu · nội dung đã khoá, muốn sửa thì bỏ duyệt trước`}
        safety="Chưa phát hành cho học sinh"
        actions={
          paper === ""
            ? []
            : [
                { label: "Phát hành", onClick: () => onPublish(paper), primary: true },
                // Figma gọi nút này là `Hoàn tác`, và nó đi tới chỗ bỏ duyệt — chỗ ấy nằm
                // trong panel. Nhãn giữ nguyên của thiết kế, đích là cổng thật.
                { label: "Hoàn tác", onClick: () => onOpen(paper) },
              ]
        }
      />
    );
  }

  if (turn.tool_name === "teacher.unapprove") {
    return (
      <Card
        tone=""
        head={`Đã bỏ duyệt đề${named}`}
        detail="Sửa lại được rồi · cài đặt phát hành vẫn giữ nguyên"
        safety="Chưa duyệt · chưa phát hành"
        actions={
          paper === "" ? [] : [{ label: "Duyệt đề", onClick: () => onOpen(paper), primary: true }]
        }
      />
    );
  }

  if (turn.tool_name === "teacher.publish") {
    const classes = Array.isArray(result.classes) ? result.classes.map(String) : [];
    return (
      <Card
        tone="settled"
        head={`Đã phát hành cho ${classes.length > 0 ? classes.join(" và ") : "lớp đã chọn"}`}
        detail="Nội dung đã khoá"
        // Thẻ có hậu quả lớn nhất mà im lặng về hậu quả thì là lỗi nặng nhất trong nhóm
        // này. Thu hồi **chỉ** được cho tới giờ mở của từng lớp (ADR-02), nên câu này nói
        // cả hai nửa: còn thu hồi được, và cái mốc chấm dứt việc đó.
        safety="Thu hồi được cho tới giờ mở của từng lớp, sau giờ mở thì không"
        actions={see}
      />
    );
  }

  // Không rơi vào đây được: `cardTurn` đã lọc, và mọi tool còn lại là một bước. Nếu có ngày
  // nó rơi vào thì **không vẽ gì** — một thẻ in tên tool ra màn hình giáo viên là một chuỗi
  // kỹ thuật lọt ra bề mặt, tệ hơn hẳn một thẻ vắng mặt.
  return null;
}

/** Hình dạng chung của tám variant: một đầu đề có chấm, một dòng chi tiết, một câu an toàn, vài nút. */
function Card({
  tone,
  head,
  detail,
  safety,
  actions = [],
}: {
  tone: "" | "settled" | "refused";
  head: string;
  detail: string;
  safety?: string;
  actions?: { label: string; onClick: () => void; primary?: boolean }[];
}) {
  return (
    <div className={`action-card ${tone}`}>
      <div className="head">
        <span className="dot" aria-hidden="true" />
        {head}
      </div>
      {detail !== "" && <div className="detail">{detail}</div>}
      {safety !== undefined && <div className="safety">{safety}</div>}
      {actions.length > 0 && (
        <div className="actions">
          {actions.map((one) => (
            <button
              className={`btn ${one.primary === true ? "primary" : ""}`}
              key={one.label}
              type="button"
              onClick={one.onClick}
            >
              {one.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
