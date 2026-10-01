import { CONVERSATIONS, DASHBOARD_WAITING, DOCUMENTS } from "./invented-not-from-be";

/**
 * Dải bên trái của mọi màn hình giáo viên.
 *
 * Bề mặt giáo viên **không có dải trên cùng**. Học sinh thì có, vì ADR-13 nói
 * phòng máy dùng chung nên mỗi màn hình phải trả lời được *"ai đang đăng nhập"*.
 * Thiết kế của giáo viên không đặt câu hỏi đó ở đâu cả: không artboard nào in
 * tên hay mã giáo viên. Nên ở đây không có dải tên, và `GET /api/teacher/me`
 * hiện **chưa có chỗ nào vẽ** — xem Status của plan.
 *
 * Gần như toàn bộ dải này đang trơ, và nó trơ một cách lộ liễu chứ không giả
 * vờ: bốn đích đến là bốn artboard chưa dựng, danh sách đoạn chat là chữ bịa
 * (BE có đúng một luồng cho mỗi giáo viên), và tài liệu thì chờ model
 * `Document`. Dựng chúng bằng `div` chứ không bằng `button` là có chủ đích —
 * một `button` hứa một việc, và không có việc nào xảy ra.
 */
export default function Rail() {
  return (
    <nav className="rail" aria-label="Điều hướng">
      <div className="brand">
        <div className="mark" />
        <div className="brand-name">Kriky</div>
      </div>

      <div className="new-chat">
        <span className="plus" aria-hidden="true">
          ＋
        </span>
        Đoạn chat mới
      </div>

      <div className="nav">
        <Destination icon={<Dashboard />} label="Bảng theo dõi" badge={DASHBOARD_WAITING} />
        <Destination icon={<Classes />} label="Danh sách lớp học" />
        <Destination icon={<Papers />} label="Các bài kiểm tra" />
        <Destination icon={<Bank />} label="Ngân hàng câu hỏi" />
      </div>

      <div className="lists">
        <Pane title="ĐOẠN CHAT" className="history">
          {CONVERSATIONS.map((one, index) => (
            <Row key={one.title} group={one.group} previous={CONVERSATIONS[index - 1]?.group}>
              {one.title}
            </Row>
          ))}
        </Pane>

        <div className="split-handle">
          <div className="grip" />
        </div>

        <Pane title="TÀI LIỆU" className="documents">
          {DOCUMENTS.map((one) => (
            <div className="document" key={one.name}>
              <span className="kind">{one.kind}</span>
              <span className="about">
                <span className="name">{one.name}</span>
                <span className="meta">{one.meta}</span>
              </span>
            </div>
          ))}
        </Pane>
      </div>
    </nav>
  );
}

/** Một đích đến của dải điều hướng. Chưa đích nào có màn hình, nên chưa đích nào bấm được. */
function Destination({
  icon,
  label,
  badge,
}: {
  icon: React.ReactNode;
  label: string;
  badge?: number;
}) {
  return (
    <div className="destination">
      <span className="icon">{icon}</span>
      <span className="label">{label}</span>
      {badge !== undefined && <span className="badge">{badge}</span>}
    </div>
  );
}

/** Một ngăn có tiêu đề và một vùng cuộn riêng. */
function Pane({
  title,
  className,
  children,
}: {
  title: string;
  className: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`pane ${className}`}>
      <div className="pane-head">
        <svg className="caret" viewBox="0 0 8 6" aria-hidden="true">
          <path d="M0 0h8L4 6z" fill="currentColor" />
        </svg>
        {title}
      </div>
      <div className="scroll">{children}</div>
    </section>
  );
}

/**
 * Một hàng đoạn chat, kèm nhãn nhóm khi nhóm vừa đổi.
 *
 * Nhãn do hàng đầu tiên của nhóm tự in ra, thay vì gom trước thành từng khối:
 * danh sách tới đây đã sắp xếp rồi, và một vòng gom nữa chỉ dựng lại cấu trúc mà
 * thứ tự đã nói.
 */
function Row({
  group,
  previous,
  children,
}: {
  group: string;
  previous?: string;
  children: React.ReactNode;
}) {
  return (
    <>
      {group !== previous && <div className="group">{group}</div>}
      <div className="conversation">{children}</div>
    </>
  );
}

/* Bốn icon 12×12, vẽ lại từ Figma. Chúng dùng `currentColor` nên không có hex
 * thô nào ở đây, và màu do CSS quyết định. */

function Dashboard() {
  return (
    <svg viewBox="0 0 12 12" aria-hidden="true">
      <rect x="0.5" y="6.5" width="2.5" height="5.5" rx="1" fill="currentColor" />
      <rect x="4.75" y="3.5" width="2.5" height="8.5" rx="1" fill="currentColor" />
      <rect x="9" y="0.5" width="2.5" height="11.5" rx="1" fill="currentColor" />
    </svg>
  );
}

function Classes() {
  return (
    <svg viewBox="0 0 12 12" aria-hidden="true">
      <circle cx="6" cy="2.5" r="2" fill="currentColor" />
      <circle cx="2.5" cy="9" r="2" fill="currentColor" />
      <circle cx="9.5" cy="9" r="2" fill="currentColor" />
    </svg>
  );
}

function Papers() {
  return (
    <svg viewBox="0 0 12 12" aria-hidden="true">
      <rect
        x="1.5"
        y="0.5"
        width="9"
        height="11"
        rx="1.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
      />
      <rect x="3.75" y="3.6" width="4.5" height="1.25" rx="0.6" fill="currentColor" />
      <rect x="3.75" y="6.6" width="4.5" height="1.25" rx="0.6" fill="currentColor" />
    </svg>
  );
}

function Bank() {
  return (
    <svg viewBox="0 0 12 12" aria-hidden="true">
      <rect x="0" y="0" width="5.2" height="5.2" rx="1.2" fill="currentColor" />
      <rect x="6.8" y="0" width="5.2" height="5.2" rx="1.2" fill="currentColor" />
      <rect x="0" y="6.8" width="5.2" height="5.2" rx="1.2" fill="currentColor" />
      <rect x="6.8" y="6.8" width="5.2" height="5.2" rx="1.2" fill="currentColor" />
    </svg>
  );
}
