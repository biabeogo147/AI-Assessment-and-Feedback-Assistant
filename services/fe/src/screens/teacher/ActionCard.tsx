import { type Turn } from "../../api";

/**
 * Một bước `tool_result`, kể lại bằng một thẻ.
 *
 * Mọi chữ trên thẻ lấy từ **chính `tool_result` ấy**. Thiết kế có tám variant; sáu trong
 * số đó dựng được từ một bước đã lưu, và hai thì không:
 *
 * - *tạo-lớp* không có đường nào sinh ra — `catalog_for` không cấp tool nào tạo lớp, và
 *   `find_class` chỉ tìm lớp đã có.
 * - *phát-hành-thất-bại* không bao giờ tới đây: `_note_publication` chỉ ghi các lớp
 *   **thành công**, nên khi mọi lớp trượt thì không có bước nào được ghi cả. Biểu mẫu
 *   phát hành phải tự hiện phần thất bại tại chỗ, và đó là việc của màn hình phát hành.
 *
 * Mỗi thẻ mang một **câu an toàn** nói thẳng rằng việc vừa xong chưa tới tay học sinh.
 * ADR-05 đặt ba cổng cho con người bước qua; một thẻ kể rằng máy vừa làm xong một việc
 * mà im lặng về phần còn lại là một thẻ mời người ta tưởng là xong.
 *
 * @param turn - Bước đã lưu.
 * @param onOpen - Mở panel của một đề.
 * @param onPublish - Mở biểu mẫu phát hành của một đề.
 */
export default function ActionCard({
  turn,
  onOpen,
  onPublish,
}: {
  turn: Turn;
  onOpen: (assessmentId: string) => void;
  onPublish: (assessmentId: string) => void;
}) {
  const result = turn.tool_result;
  const paper = String(result.assessment_id ?? turn.entity_id ?? "");
  const title = String(result.title ?? "");

  // Một tool trả `found: false` hoặc `created: false` là một lời từ chối, và `reason` là
  // câu của BE. In nguyên văn: viết hoa hay thêm dấu chấm vào đó là viết lại lời người
  // khác, và câu gốc là câu đã được cân nhắc.
  const refused = result.found === false || result.created === false || result.started === false;
  if (refused) {
    return (
      <Card tone="refused" head="Chưa làm được" detail={String(result.reason ?? "")} safety="Chưa có gì được thay đổi" />
    );
  }

  if (turn.tool_name === "create_draft") {
    const asked = Number(result.question_count ?? 0);
    return (
      <Card
        tone=""
        head={`Đã tạo đề "${title}"`}
        detail={asked > 0 ? `Đã đặt chỗ cho ${asked} câu` : "Chưa có câu hỏi nào"}
        safety="Đề trống, chưa phát hành được"
        actions={paper !== "" ? [{ label: "Xem", onClick: () => onOpen(paper) }] : []}
      />
    );
  }

  if (turn.tool_name === "start_drafting") {
    return (
      <Card
        tone=""
        head="Đã bắt đầu soạn câu hỏi"
        detail={`${Number(result.queued ?? 0)} câu đang chạy`}
        safety="Chưa duyệt · chưa phát hành"
        actions={paper !== "" ? [{ label: "Xem", onClick: () => onOpen(paper) }] : []}
      />
    );
  }

  if (turn.tool_name === "draft_progress") {
    const written = Array.isArray(result.written) ? result.written.length : 0;
    const asked = Number(result.asked_for ?? 0);
    const running = Number(result.still_drafting ?? 0);
    return (
      <Card
        tone=""
        head={`Đề "${title}" có ${written}/${asked} câu`}
        detail={running > 0 ? `Còn ${running} câu đang soạn` : "Đã soạn xong"}
        safety="Chưa duyệt · chưa phát hành"
        actions={paper !== "" ? [{ label: "Xem", onClick: () => onOpen(paper) }] : []}
      />
    );
  }

  if (turn.tool_name === "teacher.approve") {
    return (
      <Card
        tone=""
        head={`Đã duyệt đề${title === "" ? "" : ` "${title}"`}`}
        detail={`${Number(result.questions ?? 0)} câu · nội dung đã khoá, muốn sửa thì bỏ duyệt trước`}
        safety="Chưa phát hành cho học sinh"
        actions={
          paper === ""
            ? []
            : [
                { label: "Phát hành", onClick: () => onPublish(paper), primary: true },
                { label: "Xem", onClick: () => onOpen(paper) },
              ]
        }
      />
    );
  }

  if (turn.tool_name === "teacher.unapprove") {
    return (
      <Card
        tone=""
        head="Đã bỏ duyệt đề"
        detail="Sửa lại được rồi · cài đặt phát hành vẫn giữ nguyên"
        safety="Chưa duyệt · chưa phát hành"
        actions={paper !== "" ? [{ label: "Xem", onClick: () => onOpen(paper) }] : []}
      />
    );
  }

  if (turn.tool_name === "teacher.publish") {
    const classes = Array.isArray(result.classes) ? result.classes.map(String) : [];
    return (
      <Card
        tone="settled"
        head={`Đã phát hành cho ${classes.length > 0 ? classes.join(" và ") : "lớp đã chọn"}`}
        detail="Nội dung đã khoá. Thu hồi được cho tới giờ mở của từng lớp."
        actions={paper !== "" ? [{ label: "Xem", onClick: () => onOpen(paper) }] : []}
      />
    );
  }

  // Một tool khác đã chạy. Nói ra là nó đã chạy chứ không im lặng: một hành động đã xảy
  // ra mà màn hình không nhắc tới là một hành động giáo viên không có cách nào đọc lại.
  return <Card tone="" head="Đã chạy một bước" detail={turn.tool_name} />;
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
