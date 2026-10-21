import { type PointerEvent as ReactPointerEvent, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { type TeacherConversation, type TeacherDocument } from "../../api";
import { AccountCell, useSession } from "./Account";
import { readFlag, readNumber, writeFlag, writeNumber } from "./remember";

/** Chiều cao ngăn tài liệu, nhớ lại giữa các lần mở. Thiết kế vẽ 225. */
const SPLIT_KEY = "kriky.teacher.documents-height";
const SPLIT_DEFAULT = 225;
// Chặn hai đầu để không ngăn nào biến mất. Dưới 120 thì ngăn tài liệu chỉ còn cái tiêu
// đề; trên 520 thì danh sách đoạn chat không còn chỗ cho một hàng nào.
const SPLIT_MIN = 120;
const SPLIT_MAX = 520;

/**
 * Nấc thu của **từng** ngăn, nhớ lại giữa các lần mở.
 *
 * Nhớ, khác với nấc của tấm trượt phát hành — và lý do là nội dung: một ngăn đã thu không
 * mất gì khi thu tiếp, còn một biểu mẫu nhớ nấc mà không nhớ giờ là nhớ nửa vời. Rail là
 * chỗ đứng yên của mọi màn hình, nên một người đã đóng ngăn `TÀI LIỆU` lại thì mỗi lần F5
 * mở lại nó là bắt người ta đóng lại một lần nữa.
 *
 * Thiếu khoá thì **bung** — một rail mới mở ra phải cho thấy nó có gì.
 */
const PANE_KEY = (which: string) => `kriky.teacher.pane-open.${which}`;

/**
 * Dải bên trái của mọi màn hình giáo viên.
 *
 * Bề mặt giáo viên **không có dải trên cùng**. Học sinh thì có, vì ADR-13 nói phòng máy
 * dùng chung nên mỗi màn hình phải trả lời được *"ai đang đăng nhập"*. Thiết kế của giáo
 * viên không đặt câu hỏi đó ở đâu cả.
 *
 * Bốn đích đến dẫn tới màn thật từ 18/10/2026 (plan `teacher-rail-screens`): chúng là nút, và
 * đích ứng với route đang mở sáng lên (`place`). Danh sách đoạn chat và ngăn tài liệu thì thật từ
 * trước.
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
 * @param onUpload - Mở ô chọn tệp. Nút tải lên nằm trên **đầu ngăn TÀI LIỆU**, không nằm ở
 *   thanh chat: tài liệu thuộc về giáo viên và nằm trong kho chung (ADR-04), nó không
 *   thuộc về một đoạn chat nào. Đặt nút ở composer là nói ngược lại điều đó.
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
  onUpload,
  place = null,
  onGo = () => undefined,
}: {
  conversations: TeacherConversation[];
  current: string | null;
  documents: TeacherDocument[];
  starting: boolean;
  onOpen: (conversationId: string) => void;
  onNew: () => void;
  onRename: (conversationId: string, title: string) => void;
  onDelete: (conversationId: string) => void;
  onUpload: () => void;
  /** Đích đến đang mở (`theo-doi`, `lop`, `de-kiem-tra`, `ngan-hang`), hay `null` khi đang ở chat. */
  place?: string | null;
  /** Đi tới một đích đến, bằng route (plan `teacher-rail-screens`). */
  onGo?: (route: string) => void;
}) {
  // Hàng nào đang mở menu `⋯`, nếu có. Ở đây chứ không trong từng hàng: *chỉ một menu mở
  // một lúc* là một luật giữa các hàng.
  const [menuOn, setMenuOn] = useState<string | null>(null);
  const [documentsHeight, setDocumentsHeight] = useState(readSplit);
  const [historyOpen, setHistoryOpen] = useState(() => readPaneOpen("history"));
  const [documentsOpen, setDocumentsOpen] = useState(() =>
    readPaneOpen("documents"),
  );
  const { out } = useSession();
  const dragging = useRef(false);
  // Chiều cao **đang kéo tới**, cập nhật ngay trong `pointermove`. State thì không đủ:
  // `pointermove` cuối và `pointerup` rơi vào cùng một task, React chưa render lại, nên
  // handler lúc thả tay vẫn là handler của render cũ và nó ghi lại con số **trước** cú
  // kéo. Một ref thì không chờ render.
  const wanted = useRef(documentsHeight);
  const below = useRef(0);

  // Thanh kéo chỉ có mặt khi cả hai ngăn bung. Nó rời DOM giữa cú kéo thì cú kéo hết theo nó: không
  // còn ai nhận `pointerup`, và giữ chuột từ chỗ khác rồi rê qua thanh mới (`buttons` 1) vẫn kéo
  // ngăn theo (review vòng 3 Tier 1, 21/10/2026). Effect chứ không ref callback: ref viết tại chỗ
  // được gọi lại với `null` ở mỗi lần vẽ, tức mỗi bước của chính cú kéo.
  useEffect(() => {
    if (!(historyOpen && documentsOpen)) dragging.current = false;
  }, [historyOpen, documentsOpen]);

  /** Kết thúc cú kéo, dù bằng thả tay hay bằng trình duyệt huỷ pointer. */
  function endDrag(event: ReactPointerEvent<HTMLDivElement>) {
    // `releasePointerCapture` ở dưới tự bắn `lostpointercapture`, tức gọi lại hàm này: lần sau
    // không còn gì để làm.
    if (!dragging.current) return;
    dragging.current = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    // Ghi khi thả tay, và ghi từ **ref** chứ không từ state. Hai bản trước đều sai ở đây: bản
    // đầu ghi trong một effect nghe `documentsHeight` và effect không chạy lại vì giá trị không
    // đổi; bản thứ hai ghi trong handler này nhưng đọc state của render cũ. Một phép đo có
    // `await` giữa `pointermove` và `pointerup` làm cả hai bản *trông như* chạy được — chuột
    // thật thì hai sự kiện rơi vào cùng một task.
    writeNumber(SPLIT_KEY, wanted.current);
  }

  // Một menu đang mở thì bấm chỗ khác, hoặc Esc, phải đóng nó. Không có đường này thì menu
  // chỉ đóng bằng cách chọn một mục — tức bấm nhầm `⋯` là kẹt một menu trên màn hình.
  // `pointerdown` chứ không `click`: `click` của chính mục menu nổ sau, và bắt ở `click`
  // thì đóng menu trước khi mục kịp chạy.
  //
  // **Và chỗ miễn trừ phải kể cả `.row-menu`.** Nó từng chỉ kể `.conversation`, đúng vào
  // lúc menu còn nằm trong hàng — rồi menu chuyển sang `createPortal(document.body)` để
  // thoát `mask-image` của vùng cuộn, và từ đó `closest(".conversation")` trả `null` cho
  // chính các mục của nó. Hậu quả: `pointerdown` tháo menu khỏi cây, `click` rơi vào một
  // node đã tháo, nên **cả hai** mục chết — `Đổi tên` lẫn `Xoá`. Dựng lại bằng chuỗi sự
  // kiện thật ngày 06/10/2026: sau `pointerdown` thì `menuStillThere: false`,
  // `itemConnected: false`, và `input.rename` không bao giờ hiện ra.
  //
  // Không test nào bắt được vì không test nào bắn `pointerdown`: gọi `.click()` thẳng thì
  // chuỗi sự kiện của chuột không xảy ra, và phép đo xanh trong khi ngón tay thật thì không.
  useEffect(() => {
    if (menuOn === null) return;
    const shut = (event: Event) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event.type === "pointerdown") {
        const inside = (event.target as HTMLElement | null)?.closest(
          ".conversation, .row-menu",
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
        {PLACES.map((one) => (
          <Destination
            key={one.place}
            icon={one.icon}
            label={one.label}
            here={place === one.place}
            onGo={() => onGo(`/teacher/${one.place}`)}
          />
        ))}
      </div>

      {out ? (
        // Chưa đăng nhập (Figma 26): không có đoạn chat hay tài liệu nào của ai để liệt kê.
        <div className="lists">
          <p className="lists-hint">Đăng nhập để thấy các đoạn chat và tài liệu của bạn.</p>
        </div>
      ) : (
      <div className="lists">
        <Pane
          title="ĐOẠN CHAT"
          className="history"
          open={historyOpen}
          onToggle={() => {
            setHistoryOpen(!historyOpen);
            writePaneOpen("history", !historyOpen);
          }}
        >
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

        {/* Thanh kéo chỉ có mặt khi **cả hai** ngăn đang bung.
            `SPLIT_MIN` 120 tồn tại để không ngăn nào biến mất; một ngăn đã thu thì con số
            ấy không còn thứ gì để bảo vệ, và kéo một đường biên giữa một ngăn và một thanh
            đầu cao 27 là kéo một thứ không có nghĩa. Chiều cao đã nhớ **giữ nguyên** trong
            `documentsHeight` cho lúc bung lại — thanh kéo đi mất, con số thì không. */}
        {historyOpen && documentsOpen && (
        <div
          className="split-handle"
          role="separator"
          aria-orientation="horizontal"
          onPointerDown={(event) => {
            dragging.current = true;
            // Khoảng từ mép dưới cửa sổ tới con trỏ mà **không** thuộc ngăn tài liệu (ô tài
            // khoản, gap, padding của rail), đo lúc bấm. Bản cũ ghi cứng 26, có từ trước khi
            // ô tài khoản đứng dưới ngăn, nên vừa bấm mà rê 1px thanh đã nhảy lên ~60px
            // (người dùng, 20/10/2026).
            below.current = window.innerHeight - event.clientY - documentsHeight;
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (!dragging.current) return;
            // Không nút nào đang bấm: cú kéo đã hết ở một chỗ React không nghe được (review vòng 2
            // Tier 1, 21/10/2026). Lưới cuối, sau `pointerup`/`pointercancel`/`lostpointercapture`
            // và effect dọn cú kéo khi thanh rời DOM.
            if (event.buttons === 0) {
              endDrag(event);
              return;
            }
            // Đo từ **mép dưới cửa sổ** chứ không cộng dồn delta: cộng dồn thì mỗi lần
            // chạm biên 120/520 là một pixel bị nuốt mất, và sau vài lần kéo thanh ngăn
            // trôi khỏi con trỏ.
            const asked = window.innerHeight - event.clientY - below.current;
            wanted.current = Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, asked));
            setDocumentsHeight(wanted.current);
          }}
          onPointerUp={endDrag}
          // Trình duyệt huỷ pointer (cử chỉ hệ thống, mất focus) thì không có `pointerup`:
          // không nghe hai sự kiện này thì `dragging` đứng mãi, và lần rê sau, không bấm, vẫn
          // kéo ngăn theo (review vòng 1 Tier 1, 21/10/2026). Cú kéo dừng ở chỗ đã tới.
          onPointerCancel={endDrag}
          onLostPointerCapture={endDrag}
        >
          <div className="grip" />
        </div>
        )}

        <Pane
          title="TÀI LIỆU"
          className="documents"
          // Chiều cao cố định **chỉ** khi cả hai ngăn đang bung — tức đúng lúc thanh kéo
          // có mặt. Thu `ĐOẠN CHAT` mà vẫn ghim 225 ở đây thì ngăn tài liệu đứng yên và
          // để lại một khoảng trắng cao ~368px dưới nó: đo trên trình duyệt ngày
          // 06/10/2026. Chiều ngược lại vốn đã đúng vì `.pane.history` là `flex: 1`, nên
          // lỗi này **chỉ** lộ ra ở một trong hai chiều — và Figma chỉ vẽ chiều kia.
          // Con số đã nhớ không mất: nó còn trong `documentsHeight`.
          height={historyOpen && documentsOpen ? documentsHeight : undefined}
          open={documentsOpen}
          onToggle={() => {
            setDocumentsOpen(!documentsOpen);
            writePaneOpen("documents", !documentsOpen);
          }}
          action={
            <button
              className="upload"
              type="button"
              aria-label="Tải tài liệu lên"
              onClick={onUpload}
            >
              <Upload />
            </button>
          }
        >
          {documents.map((one) => (
            // Kéo được **chỉ khi sẵn sàng**: ADR-27 nói màn hình đã có đủ thông tin để nói
            // trước, nên thả một tài liệu chưa đọc xong vào ô chat rồi nhận một câu từ chối
            // khó hiểu là một lần im lặng có chủ ý. Chip mang `document_id` chứ không mang
            // tên tệp — tên tệp trùng nhau được, id thì không.
            //
            // `title` chở `fault` đầy đủ: chip in một nhãn ngắn, còn lý do cụ thể —
            // *ảnh scan* hay *không có trang nào* — nằm ở đây cho người cần chẩn đoán.
            <div
              className={`document ${CHIP[one.state].tone}`}
              key={one.document_id}
              title={one.fault || undefined}
              draggable={one.state === "ready"}
              onDragStart={(event) => {
                event.dataTransfer.setData(
                  "text/kriky-document",
                  one.document_id,
                );
                event.dataTransfer.effectAllowed = "copy";
              }}
            >
              <span className="kind">{one.kind}</span>
              <span className="about">
                <span className="name">{one.filename}</span>
                <span className="meta">{measure(one)}</span>
                {say(one) !== "" && <span className="status">{say(one)}</span>}
              </span>
            </div>
          ))}
        </Pane>
      </div>
      )}
      <AccountCell />
    </nav>
  );
}

/**
 * Bốn trạng thái của một tài liệu, đúng bằng `DocumentState` bên `packages/contracts`.
 *
 * `tools/check_contract.py` so hai danh sách ấy với nhau — hai ngôn ngữ, một bảng từ vựng —
 * nên một trạng thái thứ năm ở BE mà chip không vẽ sẽ làm build đỏ, và đổi tên một nấc ở đây
 * cũng vậy.
 */
export type ChipState = "processing" | "ready" | "no_text_layer" | "failed";

/**
 * Chip nói gì ở mỗi trạng thái.
 *
 * Nhãn là **cố định theo trạng thái** — trừ `processing` đã có tiến độ, xem `say` — không phải
 * `fault` từ API. `fault` là một câu chẩn đoán cho **mỗi** cách hỏng — của `document`, cộng
 * phép suy 300 s ở BE — nên số câu mọc theo code, và — *"Tệp PDF này không có trang nào"*, *"Không mở được tệp PDF này"* — chứ
 * không phải nhãn; in thẳng lên một cột rộng 165px thì chúng xuống dòng và chip phình lên.
 * `fault` không mất: nó đi vào `title` của chip.
 *
 * `ready` không có dòng nào, và đó là chủ ý: **số trang trên dòng meta chính là bằng chứng đã
 * đọc được chữ** — nó chỉ xuất hiện sau khi đọc xong. Một thư viện bình thường toàn chip sẵn
 * sàng, nên một dòng xanh lặp lại hai mươi lần là nhiễu.
 *
 * Hai trạng thái xấu dùng **chung** một màu. Foundations của Figma cố ý chỉ có ba màu trạng
 * thái và ghi thẳng *"ba màu cùng trọng lượng, cố ý không xếp hạng nghiêm trọng"*; cái phân
 * biệt chúng là chữ, không phải màu.
 */
/** Chip nói gì, và tô màu nào. Một kiểu có tên, để bảng `CHIP` dưới đây đếm được. */
interface ChipLook {
  say: string;
  tone: string;
  /** Trạng thái này nói tiến độ thay nhãn khi đã nghe tiếng báo (chỉ `processing`). */
  progress: boolean;
  /** Dòng meta in số trang: chỉ khi tệp **đã đọc xong** (`ready`, `no_text_layer`). */
  counted: boolean;
}

const CHIP: Record<ChipState, ChipLook> = {
  processing: { say: "Đang xử lý…", tone: "processing", progress: true, counted: false },
  ready: { say: "", tone: "settled", progress: false, counted: true },
  no_text_layer: {
    say: "Không đọc được chữ",
    tone: "needs-human",
    progress: false,
    counted: true,
  },
  failed: {
    say: "Xử lí lỗi. Hãy tải lại",
    tone: "needs-human",
    progress: false,
    counted: false,
  },
};

/**
 * Dòng trạng thái của một chip: nhãn cố định của trạng thái, trừ khi đang xử lý và đã có tiến độ.
 *
 * Tiến độ là **chữ** của trạng thái `processing`, không phải một trạng thái thứ năm (người dùng
 * chốt 14/10/2026; Figma `Document chip`, variant `đang đọc trang` và `đang dựng mục lục`). Job
 * dựng cây báo tiến độ bằng đúng tổng số trang, nên `pages_read === page_count` nghĩa là đã đọc
 * hết và đang dựng mục lục — kể cả `1/1` của một tệp văn bản thuần.
 *
 * @param one - Tài liệu.
 * @returns Câu in trên dòng trạng thái, hoặc chuỗi rỗng khi không có dòng ấy.
 */
function say(one: TeacherDocument): string {
  const read = one.pages_read;
  const total = one.page_count;
  const look = CHIP[one.state];
  if (!look.progress || typeof read !== "number" || typeof total !== "number")
    return look.say;
  if (read >= total) return "Đang dựng mục lục…";
  return `Đang đọc ${read}/${total} trang…`;
}

/**
 * Chiều cao ngăn tài liệu đã lưu, hoặc con số của thiết kế.
 *
 * @returns Một chiều cao nằm trong khoảng cho phép. Một giá trị rác trong `localStorage`
 *   — tay người sửa, hoặc một phiên bản cũ — không được phép làm vỡ rail.
 */
function readSplit(): number {
  return readNumber(SPLIT_KEY, SPLIT_DEFAULT, SPLIT_MIN, SPLIT_MAX);
}

/**
 * Ngăn này đang bung hay không, theo cái đã nhớ.
 *
 * @param which - Tên ngăn.
 * @returns `true` khi bung. Thiếu khoá, hoặc không đọc được `localStorage`, thì bung.
 */
function readPaneOpen(which: string): boolean {
  return readFlag(PANE_KEY(which));
}

/**
 * Ghi lại nấc của một ngăn.
 *
 * @param which - Tên ngăn.
 * @param open - Nấc mới.
 */
function writePaneOpen(which: string, open: boolean): void {
  writeFlag(PANE_KEY(which), open);
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
/**
 * Dòng meta của một chip: kích thước, cộng số trang khi con số ấy tồn tại.
 *
 * `page_count` là `null` ở hai ca khác nhau — tệp văn bản thuần **không có** trang, và một
 * tài liệu chưa đọc xong thì **chưa đo được** — nhưng cả hai cho ra cùng một dòng, vì màn
 * hình không có gì thật để nói thêm. In `0 trang` cho ca thứ nhất là bịa, và giáo viên sẽ tin.
 *
 * Số trang chỉ in khi tệp **đã đọc xong** (`ready`, `no_text_layer`). Lúc đang xử lý cột ấy có
 * thể đã mang tổng do tiếng báo tiến độ ghi — `1` cho một tệp `.md` đang dựng cây — và một chip
 * *xử lý hỏng* suy ra lúc đọc vẫn giữ con số tạm ấy. In nó ra là in `1 trang` cho một tệp không
 * có trang. Tổng của tiến độ đã nằm trên dòng trạng thái.
 *
 * @param one - Tài liệu.
 * @returns `2,4 MB · 184 trang`, hoặc `2,4 MB`.
 */
function measure(one: TeacherDocument): string {
  const size = weight(one.byte_size);
  return !CHIP[one.state].counted || one.page_count === null
    ? size
    : `${size} · ${one.page_count} trang`;
}

function weight(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

/** Bốn đích đến của rail, theo thứ tự của Figma, cùng đoạn route của từng cái. */
const PLACES = [
  { place: "theo-doi", label: "Bảng theo dõi", icon: <Dashboard /> },
  { place: "lop", label: "Danh sách lớp học", icon: <Classes /> },
  { place: "de-kiem-tra", label: "Các bài kiểm tra", icon: <Papers /> },
  { place: "ngan-hang", label: "Ngân hàng câu hỏi", icon: <Bank /> },
];

/**
 * Một đích đến của dải điều hướng: một nút dẫn tới màn của nó (plan `teacher-rail-screens`).
 *
 * Không có huy hiệu số: con số *"3"* trên *Bảng theo dõi* từng là chữ bịa, không đường nào đếm nó,
 * và đã gỡ 18/10/2026 (plan `wave-1-small-fixes`).
 *
 * @param icon - Hình 12×12.
 * @param label - Chữ.
 * @param here - Đang ở màn này: variant `đang chọn` của `Rail destination`.
 * @param onGo - Đi tới màn này.
 */
function Destination({
  icon,
  label,
  here,
  onGo,
}: {
  icon: React.ReactNode;
  label: string;
  here: boolean;
  onGo: () => void;
}) {
  return (
    <button
      className="destination"
      type="button"
      aria-current={here ? "page" : undefined}
      onClick={onGo}
    >
      <span className="icon">{icon}</span>
      <span className="label">{label}</span>
    </button>
  );
}

/**
 * Một ngăn có tiêu đề và một vùng cuộn riêng, thu được.
 *
 * **Thu gọn là thao tác chính, kéo là tinh chỉnh** — ghi chú `129:2` trên Figma nói đúng câu
 * ấy từ lâu, và nó chỉ tồn tại ở đó: rail được sao chép theo artboard chứ không dựng thành
 * component, nên bốn luật của ghi chú chưa có dòng code nào. Cái mũi nhọn trong thanh đầu đã
 * đứng ở đây từ đầu mà không bấm được, tức nó hứa đúng việc này rồi lặng lẽ không làm.
 *
 * Thanh đầu là một **hàng chứa hai nút ngang hàng**, không phải một nút bọc mọi thứ: nút tải
 * lên của ngăn `TÀI LIỆU` là một `<button>`, và một `<button>` trong một `<button>` thì
 * trình duyệt tự gỡ lồng — cú bấm vào nút trong rơi vào nút ngoài, nên bấm *tải lên* sẽ thu
 * ngăn lại. Đây là đúng cái bẫy mà hàng đoạn chat đã sập một lần (xem `Row`).
 *
 * @param title - Tên ngăn, in hoa.
 * @param className - Tên riêng của ngăn, cho luật bố cục.
 * @param height - Chiều cao cố định, cho ngăn kéo được. Thiếu thì ngăn chiếm phần còn lại.
 * @param action - Một việc của riêng ngăn này, đứng cạnh nút thu.
 * @param open - Đang bung. Thu thì vùng cuộn **rời khỏi cây DOM**, không chỉ ẩn đi: một
 *   danh sách còn trong cây vẫn tab tới được, và tab vào một thứ không thấy là một cái bẫy.
 * @param onToggle - Xin đổi nấc.
 */
function Pane({
  title,
  className,
  height,
  action,
  open,
  onToggle,
  children,
}: {
  title: string;
  className: string;
  height?: number;
  action?: React.ReactNode;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <section
      className={`pane ${className}${open ? "" : " thu"}`}
      style={
        height === undefined || !open ? undefined : { flex: `0 0 ${height}px` }
      }
    >
      <div className="pane-head">
        <button
          className="pane-toggle"
          type="button"
          aria-expanded={open}
          onClick={onToggle}
        >
          <svg className="caret" viewBox="0 0 8 6" aria-hidden="true">
            <path d="M0 0h8L4 6z" fill="currentColor" />
          </svg>
          <span className="label">{title}</span>
        </button>
        {action}
      </div>
      {open && <div className="scroll">{children}</div>}
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

/** Mũi tên đi lên khỏi một vạch — 16×16, vẽ lại từ Figma. */
function Upload() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 3 L12 8 H9.5 V12 H6.5 V8 H4 Z" fill="currentColor" />
      <rect
        x="2"
        y="13"
        width="12"
        height="1.5"
        rx="0.75"
        fill="currentColor"
      />
    </svg>
  );
}

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
      {/* Mực chạm **đáy** khung 12, như ba icon kia: `cy 10 + r 2 = 12`. Bản trước
          dừng ở 11, nên dưới luật nâng chung nó sẽ đứng cao hơn baseline đúng 1px. Luật
          nâng là một luật của rail; bất biến *"mực chạm đáy"* là phần hình vẽ phải giữ để
          luật ấy đúng với mọi icon. */}
      <circle cx="6" cy="2" r="2" fill="currentColor" />
      <circle cx="2.5" cy="10" r="2" fill="currentColor" />
      <circle cx="9.5" cy="10" r="2" fill="currentColor" />
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
