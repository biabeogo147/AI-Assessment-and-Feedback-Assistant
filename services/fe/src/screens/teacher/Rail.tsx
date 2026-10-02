import { useRef, useState } from "react";

import { type TeacherConversation, type TeacherDocument } from "../../api";
import { DASHBOARD_WAITING } from "./invented-not-from-be";

/** Chiều cao ngăn tài liệu, nhớ lại giữa các lần mở. Thiết kế vẽ 225. */
const SPLIT_KEY = "kriky.teacher.documents-height";
const SPLIT_DEFAULT = 225;
// Chặn hai đầu để không ngăn nào biến mất. Dưới 120 thì ngăn tài liệu chỉ còn cái tiêu
// đề; trên 520 thì danh sách đoạn chat không còn chỗ cho một hàng nào.
const SPLIT_MIN = 120;
const SPLIT_MAX = 520;

/**
 * Dải bên trái của mọi màn hình giáo viên.
 *
 * Bề mặt giáo viên **không có dải trên cùng**. Học sinh thì có, vì ADR-13 nói phòng máy
 * dùng chung nên mỗi màn hình phải trả lời được *"ai đang đăng nhập"*. Thiết kế của giáo
 * viên không đặt câu hỏi đó ở đâu cả.
 *
 * Bốn đích đến vẫn trơ, và trơ một cách lộ liễu: chúng là bốn artboard chưa dựng, nên
 * chúng là `div` chứ không `button` — một `button` hứa một việc không xảy ra. Danh sách
 * đoạn chat thì **thật** từ đợt này, và ngăn tài liệu đã thật từ đợt trước.
 *
 * @param conversations - Các đoạn chat, mới nói nhất trước. BE đã sắp sẵn.
 * @param current - Đoạn đang mở, để tô hàng của nó.
 * @param documents - Thư viện tài liệu.
 * @param onOpen - Mở một đoạn chat cũ.
 * @param onNew - Bắt đầu một đoạn chat mới. Chưa tạo gì ở BE — dòng chỉ xuất hiện khi
 *   có câu đầu tiên, nên một cú bấm nhầm không để lại rác.
 */
export default function Rail({
  conversations,
  current,
  documents,
  onOpen,
  onNew,
}: {
  conversations: TeacherConversation[];
  current: string | null;
  documents: TeacherDocument[];
  onOpen: (conversationId: string) => void;
  onNew: () => void;
}) {
  const [documentsHeight, setDocumentsHeight] = useState(readSplit);
  const dragging = useRef(false);

  return (
    <nav className="rail" aria-label="Điều hướng">
      <div className="brand">
        <div className="brand-mark" />
        <div className="brand-name">Kriky</div>
      </div>

      <button className="new-chat" type="button" onClick={onNew}>
        <span className="plus" aria-hidden="true">
          ＋
        </span>
        Đoạn chat mới
      </button>

      <div className="nav">
        <Destination icon={<Dashboard />} label="Bảng theo dõi" badge={DASHBOARD_WAITING} />
        <Destination icon={<Classes />} label="Danh sách lớp học" />
        <Destination icon={<Papers />} label="Các bài kiểm tra" />
        <Destination icon={<Bank />} label="Ngân hàng câu hỏi" />
      </div>

      <div className="lists">
        <Pane title="ĐOẠN CHAT" className="history">
          {conversations.map((one, index) => (
            <Row
              key={one.conversation_id}
              group={bucket(one.last_spoke_at)}
              previous={index === 0 ? undefined : bucket(conversations[index - 1].last_spoke_at)}
              chosen={one.conversation_id === current}
              onClick={() => onOpen(one.conversation_id)}
            >
              {one.title || "Đoạn chat"}
            </Row>
          ))}
        </Pane>

        <div
          className="split-handle"
          role="separator"
          aria-orientation="horizontal"
          onPointerDown={(event) => {
            dragging.current = true;
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (!dragging.current) return;
            // Đo từ **mép dưới cửa sổ** chứ không cộng dồn delta: cộng dồn thì mỗi lần
            // chạm biên 120/520 là một pixel bị nuốt mất, và sau vài lần kéo thanh ngăn
            // trôi khỏi con trỏ.
            const wanted = window.innerHeight - event.clientY - 26;
            setDocumentsHeight(Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, wanted)));
          }}
          onPointerUp={(event) => {
            dragging.current = false;
            event.currentTarget.releasePointerCapture(event.pointerId);
            // Ghi ở đây chứ không trong một effect nghe `documentsHeight`. Bản trước làm
            // thế và nó **không ghi gì**: lần `set` cuối cùng của một cú kéo đưa đúng giá
            // trị đang có, React bỏ qua, effect không chạy lại. Ghi khi thả tay cũng là
            // chỗ đúng về số lượng — một cú kéo là hàng trăm `pointermove`, mà
            // `localStorage` ghi đồng bộ trên luồng chính.
            try {
              window.localStorage.setItem(SPLIT_KEY, String(documentsHeight));
            } catch {
              /* ẩn danh hoặc storage đầy; vị trí thanh kéo không đáng làm hỏng gì */
            }
          }}
        >
          <div className="grip" />
        </div>

        <Pane title="TÀI LIỆU" className="documents" height={documentsHeight}>
          {documents.map((one) => (
            <div className="document" key={one.document_id}>
              <span className="kind">{one.kind}</span>
              <span className="about">
                <span className="name">{one.filename}</span>
                <span className="meta">{weight(one.byte_size)}</span>
              </span>
            </div>
          ))}
        </Pane>
      </div>
    </nav>
  );
}

/**
 * Chiều cao ngăn tài liệu đã lưu, hoặc con số của thiết kế.
 *
 * @returns Một chiều cao nằm trong khoảng cho phép. Một giá trị rác trong `localStorage`
 *   — tay người sửa, hoặc một phiên bản cũ — không được phép làm vỡ rail.
 */
function readSplit(): number {
  try {
    const saved = Number(window.localStorage.getItem(SPLIT_KEY));
    if (Number.isFinite(saved) && saved >= SPLIT_MIN && saved <= SPLIT_MAX) return saved;
  } catch {
    /* không đọc được thì dùng con số của thiết kế */
  }
  return SPLIT_DEFAULT;
}

/**
 * Nhãn ngày của một đoạn chat.
 *
 * Bốn nhóm, không phải ba. Thiết kế vẽ ba vì bộ mẫu của nó chỉ có ba; một đoạn chat của
 * tháng trước vẫn phải nằm ở đâu đó, và *"30 ngày qua"* là một lời nói sai về nó.
 *
 * @param iso - Lần nói cuối.
 * @returns Nhãn nhóm.
 */
function bucket(iso: string): string {
  const days = (Date.now() - new Date(iso).getTime()) / 86_400_000;
  if (days < 1) return "Hôm nay";
  if (days < 7) return "7 ngày qua";
  if (days < 30) return "30 ngày qua";
  return "Cũ hơn";
}

/**
 * Kích thước file, cho mắt người.
 *
 * Làm tròn ở đây chứ không ở BE: con số byte là sự thật và nó đi nguyên qua đường truyền;
 * cái chip chỉ cần một thứ đọc được. Làm tròn phía server thì không ai lấy lại được số gốc.
 *
 * @param bytes - Kích thước thật.
 * @returns Ví dụ `1,2 MB` — dấu phẩy thập phân, vì đây là bản tiếng Việt.
 */
function weight(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
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

/**
 * Một ngăn có tiêu đề và một vùng cuộn riêng.
 *
 * @param height - Chiều cao cố định, cho ngăn kéo được. Thiếu thì ngăn chiếm phần còn lại.
 */
function Pane({
  title,
  className,
  height,
  children,
}: {
  title: string;
  className: string;
  height?: number;
  children: React.ReactNode;
}) {
  return (
    <section
      className={`pane ${className}`}
      style={height === undefined ? undefined : { flex: `0 0 ${height}px` }}
    >
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
 * Nhãn do hàng đầu tiên của nhóm tự in ra, thay vì gom trước thành từng khối: danh sách
 * tới đây đã sắp xếp rồi, và một vòng gom nữa chỉ dựng lại cấu trúc mà thứ tự đã nói.
 */
function Row({
  group,
  previous,
  chosen,
  onClick,
  children,
}: {
  group: string;
  previous?: string;
  chosen: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <>
      {group !== previous && <div className="group">{group}</div>}
      <button
        className="conversation"
        type="button"
        aria-current={chosen ? "true" : undefined}
        onClick={onClick}
      >
        {children}
      </button>
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
