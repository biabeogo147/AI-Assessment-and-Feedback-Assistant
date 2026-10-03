import { useRef } from "react";

/**
 * Thanh kéo dọc: đổi bề rộng của cột bên trái hoặc cột bên phải nó.
 *
 * Rail đã có một thanh kéo **ngang** giữa hai ngăn của nó, và ba bản cài đặt trước của
 * thanh ấy đều sai cùng hai chỗ. Chỗ này chép lại kết luận chứ không chép lại đường vòng:
 *
 * - **Đo từ mép cửa sổ, không cộng dồn delta.** Cộng dồn thì mỗi lần chạm biên là một
 *   pixel bị nuốt, và sau vài lần kéo thanh ngăn trôi khỏi con trỏ.
 * - **Ghi lúc thả tay, và ghi từ `ref` chứ không từ state.** Handler đọc state là đọc giá
 *   trị của lần render cũ; `pointermove` và `pointerup` của một con chuột thật rơi vào
 *   cùng một task, nên không có lần render nào xen vào giữa để sửa chuyện đó.
 *
 * @param side - `left` khi thanh này đổi bề rộng cột **bên trái** nó (rail), `right` khi
 *   nó đổi cột bên phải (panel đề).
 * @param min - Bề rộng nhỏ nhất, pixel.
 * @param max - Bề rộng lớn nhất, pixel.
 * @param label - Câu đọc cho trình đọc màn hình.
 * @param onWidth - Bề rộng mới, bắn liên tục trong lúc kéo.
 * @param onSettle - Bề rộng cuối cùng, bắn một lần lúc thả tay. Chỗ để ghi nhớ.
 */
/**
 * Bắt hoặc thả con trỏ, và nuốt mọi lỗi.
 *
 * Pointer capture chỉ là **tối ưu**: nó giữ cho sự kiện vẫn tới khi con trỏ rời khỏi dải
 * 7px. Mất nó thì cú kéo kém mượt; một exception từ nó thì làm mất cả bề rộng giáo viên
 * vừa chọn. Đổi một thứ lấy thứ kia là sai chiều, nên nó không được phép ném.
 *
 * @param node - Chính thanh kéo.
 * @param pointer - Id con trỏ của sự kiện.
 * @param on - Bắt hay thả.
 */
function grab(node: Element, pointer: number, on: boolean): void {
  try {
    if (on) node.setPointerCapture(pointer);
    else node.releasePointerCapture(pointer);
  } catch {
    /* con trỏ đã biến mất, hoặc chưa bao giờ là một con trỏ thật */
  }
}

export default function Split({
  side,
  min,
  max,
  label,
  onWidth,
  onSettle,
}: {
  side: "left" | "right";
  min: number;
  max: number;
  label: string;
  onWidth: (width: number) => void;
  onSettle: (width: number) => void;
}) {
  const dragging = useRef(false);
  const wanted = useRef(0);

  return (
    <div
      className="split-x"
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      onPointerDown={(event) => {
        dragging.current = true;
        grab(event.currentTarget, event.pointerId, true);
      }}
      onPointerMove={(event) => {
        if (!dragging.current) return;
        const asked =
          side === "left"
            ? event.clientX
            : window.innerWidth - event.clientX;
        wanted.current = Math.min(max, Math.max(min, asked));
        onWidth(wanted.current);
      }}
      onPointerUp={(event) => {
        if (!dragging.current) return;
        dragging.current = false;
        // Ghi **trước**, thả bắt sau. Thứ tự ngược lại đã đo là mất bề rộng: một cú ném
        // từ `releasePointerCapture` cắt ngang handler và `onSettle` không bao giờ chạy.
        onSettle(wanted.current);
        grab(event.currentTarget, event.pointerId, false);
      }}
    >
      <i />
    </div>
  );
}
