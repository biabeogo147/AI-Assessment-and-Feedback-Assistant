import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

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
 * @param starting - Đang đứng ở màn *Đoạn chat mới*. Nó quyết định nút nào mang nền accent,
 *   và nền accent nghĩa là **đang ở chức năng này** — không phải "đây là nút chính". Một nút
 *   lúc nào cũng xanh thì màu ấy thôi không còn nói gì.
 * @param onNew - Bắt đầu một đoạn chat mới. Chưa tạo gì ở BE — dòng chỉ xuất hiện khi
 *   có câu đầu tiên, nên một cú bấm nhầm không để lại rác.
 * @param onRename - Đổi tên một đoạn. Tên vốn do model đặt **một lần** sau lượt đầu, nên
 *   trước đợt này một cái tên đặt sai đứng đó mãi — và rail là chỗ người ta đi tìm lại việc
 *   cũ, nên một cái tên sai là một đoạn chat mất tích.
 * @param onDelete - Xin xoá một đoạn. Rail **không** tự xoá: nó mở hộp xác nhận của màn
 *   hình, vì xoá là việc một chiều với người bấm nút.
 */
export default function Rail({
  conversations,
  current,
  documents,
  starting,
  onOpen,
  onNew,
  onRename,
  onDelete,
}: {
  conversations: TeacherConversation[];
  current: string | null;
  documents: TeacherDocument[];
  starting: boolean;
  onOpen: (conversationId: string) => void;
  onNew: () => void;
  onRename: (conversationId: string, title: string) => void;
  onDelete: (conversationId: string) => void;
}) {
  // Hàng nào đang mở menu `⋯`, nếu có. Ở đây chứ không trong từng hàng: *chỉ một menu mở
  // một lúc* là một luật giữa các hàng.
  const [menuOn, setMenuOn] = useState<string | null>(null);
  const [documentsHeight, setDocumentsHeight] = useState(readSplit);
  const dragging = useRef(false);
  // Chiều cao **đang kéo tới**, cập nhật ngay trong `pointermove`. State thì không đủ:
  // `pointermove` cuối và `pointerup` rơi vào cùng một task, React chưa render lại, nên
  // handler lúc thả tay vẫn là handler của render cũ và nó ghi lại con số **trước** cú
  // kéo. Một ref thì không chờ render.
  const wanted = useRef(documentsHeight);

  // Một menu đang mở thì bấm chỗ khác, hoặc Esc, phải đóng nó. Không có đường này thì menu
  // chỉ đóng bằng cách chọn một mục — tức bấm nhầm `⋯` là kẹt một menu trên màn hình.
  // `pointerdown` chứ không `click`: `click` của chính mục menu nổ sau, và bắt ở `click`
  // thì đóng menu trước khi mục kịp chạy.
  useEffect(() => {
    if (menuOn === null) return;
    const shut = (event: Event) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event.type === "pointerdown") {
        const inside = (event.target as HTMLElement | null)?.closest(
          ".conversation",
        );
        if (inside) return;
      }
      setMenuOn(null);
    };
    document.addEventListener("pointerdown", shut);
    document.addEventListener("keydown", shut);
    return () => {
      document.removeEventListener("pointerdown", shut);
      document.removeEventListener("keydown", shut);
    };
  }, [menuOn]);

  return (
    <nav className="rail" aria-label="Điều hướng">
      <div className="brand">
        <div className="brand-mark" />
        <div className="brand-name">Kriky</div>
      </div>

      {/*
        Nút mở đoạn chat cùng một nhóm với bốn đích đến, nhịp 4px. Một hành động và bốn chỗ
        đi tới đọc thành **một** danh sách; để nó cách ra 16px thì mắt đọc thành hai nhóm
        mà chúng không phải hai nhóm.
      */}
      <div className="nav">
        <button
          className="new-chat"
          type="button"
          aria-current={starting ? "page" : undefined}
          onClick={onNew}
        >
          <span className="plus" aria-hidden="true">
            ＋
          </span>
          Đoạn chat mới
        </button>
        <Destination
          icon={<Dashboard />}
          label="Bảng theo dõi"
          badge={DASHBOARD_WAITING}
        />
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
              previous={
                index === 0
                  ? undefined
                  : bucket(conversations[index - 1].last_spoke_at)
              }
              chosen={one.conversation_id === current}
              label={one.title || "Đoạn chat"}
              open={menuOn === one.conversation_id}
              onToggle={(show) => setMenuOn(show ? one.conversation_id : null)}
              onClick={() => onOpen(one.conversation_id)}
              onRename={(title) => onRename(one.conversation_id, title)}
              onDelete={() => onDelete(one.conversation_id)}
            />
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
            const asked = window.innerHeight - event.clientY - 26;
            wanted.current = Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, asked));
            setDocumentsHeight(wanted.current);
          }}
          onPointerUp={(event) => {
            dragging.current = false;
            event.currentTarget.releasePointerCapture(event.pointerId);
            // Ghi khi thả tay, và ghi từ **ref** chứ không từ state. Hai bản trước đều
            // sai ở đây: bản đầu ghi trong một effect nghe `documentsHeight` và effect
            // không chạy lại vì giá trị không đổi; bản thứ hai ghi trong handler này
            // nhưng đọc state của render cũ. Một phép đo có `await` giữa `pointermove`
            // và `pointerup` làm cả hai bản *trông như* chạy được — chuột thật thì hai
            // sự kiện rơi vào cùng một task.
            try {
              window.localStorage.setItem(SPLIT_KEY, String(wanted.current));
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
    if (Number.isFinite(saved) && saved >= SPLIT_MIN && saved <= SPLIT_MAX)
      return saved;
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
 *
 * Cả hàng **từng là một `<button>`**, và nó phải hết là thế từ đợt này: một nút lồng trong
 * một nút là HTML không hợp lệ, browser tự gỡ lồng, và cú bấm vào nút trong rơi vào nút
 * ngoài — tức bấm *Xoá* sẽ mở đoạn chat. Nên hàng là một `div`, và hai việc trong nó là hai
 * nút ngang hàng.
 *
 * Trạng thái *đang đổi tên* ở lại trong hàng này; *menu đang mở* thì **không**. Bản đầu giữ
 * cả hai ở đây với lý do *"không ai ngoài hàng ấy cần biết"* — sai, vì **chỉ một menu được
 * mở một lúc** là một luật mà hàng khác cần biết, và không có nó thì bấm `⋯` hàng A rồi hàng
 * B để lại hai menu mở cùng lúc. Nên `Rail` giữ một id, và cũng chính nó đóng menu khi bấm
 * ra ngoài hay bấm Esc.
 *
 * Menu dùng `position: fixed` với toạ độ đo từ nút `⋯`. Dùng `absolute` trong hàng thì vùng
 * cuộn của rail (`overflow-y: auto`, cộng một `mask-image`) **cắt** nó: ở hàng cuối danh
 * sách, mục *Xoá* nằm ngoài khung và không bấm được.
 *
 * @param group - Nhãn nhóm ngày của hàng này.
 * @param previous - Nhãn nhóm của hàng trên, để biết có phải in nhãn hay không.
 * @param chosen - Hàng này là đoạn đang mở.
 * @param label - Tên hiện ra, đã có nhãn dự phòng.
 * @param open - Menu của hàng này đang mở.
 * @param onToggle - Xin mở hoặc đóng menu của hàng này.
 * @param onClick - Mở đoạn.
 * @param onRename - Lưu tên mới.
 * @param onDelete - Xin xoá.
 */
function Row({
  group,
  previous,
  chosen,
  label,
  open,
  onToggle,
  onClick,
  onRename,
  onDelete,
}: {
  group: string;
  previous?: string;
  chosen: boolean;
  label: string;
  open: boolean;
  onToggle: (wanted: boolean) => void;
  onClick: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const [typing, setTyping] = useState<string | null>(null);
  // Chỗ menu sẽ đứng, đo từ chính nút `⋯` lúc nó được bấm. Menu dùng `position: fixed`, nên
  // nó cần toạ độ màn hình chứ không phải toạ độ trong hàng.
  const [spot, setSpot] = useState<{ top: number; right: number } | null>(null);
  const button = useRef<HTMLButtonElement | null>(null);

  function save() {
    const wanted = (typing ?? "").trim();
    setTyping(null);
    // Rỗng, hoặc y như cũ: không gửi gì. BE từ chối tên rỗng, nhưng để nó từ chối ở đây là
    // đổi một cú bấm Enter vô hại thành một câu lỗi đỏ trên màn hình.
    if (wanted !== "" && wanted !== label) onRename(wanted);
  }

  function toggle() {
    const box = button.current?.getBoundingClientRect();
    if (box)
      setSpot({ top: box.bottom + 4, right: window.innerWidth - box.right });
    onToggle(!open);
  }

  return (
    <>
      {group !== previous && <div className="group">{group}</div>}
      <div className="conversation" aria-current={chosen ? "true" : undefined}>
        {typing === null ? (
          <button className="open" type="button" onClick={onClick}>
            {label}
          </button>
        ) : (
          <input
            className="rename"
            aria-label="Tên đoạn chat"
            autoFocus
            value={typing}
            onChange={(event) => setTyping(event.target.value)}
            onBlur={save}
            onKeyDown={(event) => {
              if (event.key === "Enter") save();
              // Esc là đường **huỷ**, nên nó không đi qua `save`. Gộp hai đường lại thì
              // không có cách nào bỏ một cái tên đã gõ dở.
              if (event.key === "Escape") setTyping(null);
            }}
          />
        )}
        <button
          className="more"
          type="button"
          ref={button}
          aria-label={`Tuỳ chọn cho ${label}`}
          aria-expanded={open}
          onClick={toggle}
        >
          ⋯
        </button>
        {open &&
          spot !== null &&
          // Dựng thẳng vào `body`. `position: fixed` đã đủ để thoát khỏi `overflow` của vùng
          // cuộn, nhưng **chưa** đủ để nằm trên: `mask-image` của vùng ấy dựng một stacking
          // context, nên `z-index` của menu chỉ xếp hạng *bên trong* vùng cuộn, và ngăn TÀI
          // LIỆU vẫn vẽ đè lên. Đo bằng `elementFromPoint` ở giữa mục *Xoá*: điểm ấy trả về
          // một chip tài liệu, tức mục nhìn thấy mà không bấm được.
          createPortal(
            <div
              className="row-menu"
              role="menu"
              style={{ top: spot.top, right: spot.right }}
            >
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onToggle(false);
                  setTyping(label);
                }}
              >
                Đổi tên
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onToggle(false);
                  onDelete();
                }}
              >
                Xoá
              </button>
            </div>,
            document.body,
          )}
      </div>
    </>
  );
}

/* Bốn icon 12×12, vẽ lại từ Figma. Chúng dùng `currentColor` nên không có hex
 * thô nào ở đây, và màu do CSS quyết định. */

function Dashboard() {
  return (
    <svg viewBox="0 0 12 12" aria-hidden="true">
      <rect
        x="0.5"
        y="6.5"
        width="2.5"
        height="5.5"
        rx="1"
        fill="currentColor"
      />
      <rect
        x="4.75"
        y="3.5"
        width="2.5"
        height="8.5"
        rx="1"
        fill="currentColor"
      />
      <rect
        x="9"
        y="0.5"
        width="2.5"
        height="11.5"
        rx="1"
        fill="currentColor"
      />
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
      <rect
        x="3.75"
        y="3.6"
        width="4.5"
        height="1.25"
        rx="0.6"
        fill="currentColor"
      />
      <rect
        x="3.75"
        y="6.6"
        width="4.5"
        height="1.25"
        rx="0.6"
        fill="currentColor"
      />
    </svg>
  );
}

function Bank() {
  return (
    <svg viewBox="0 0 12 12" aria-hidden="true">
      <rect x="0" y="0" width="5.2" height="5.2" rx="1.2" fill="currentColor" />
      <rect
        x="6.8"
        y="0"
        width="5.2"
        height="5.2"
        rx="1.2"
        fill="currentColor"
      />
      <rect
        x="0"
        y="6.8"
        width="5.2"
        height="5.2"
        rx="1.2"
        fill="currentColor"
      />
      <rect
        x="6.8"
        y="6.8"
        width="5.2"
        height="5.2"
        rx="1.2"
        fill="currentColor"
      />
    </svg>
  );
}
