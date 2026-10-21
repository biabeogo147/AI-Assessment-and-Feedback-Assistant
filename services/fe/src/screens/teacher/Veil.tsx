import { useEffect, useRef, type ReactNode, type RefObject } from "react";

/**
 * Màn che và cái hộp đứng trên nó — khuôn chung của mọi hộp thoại bề mặt giáo viên.
 *
 * Trước khi có file này, ba hộp thoại dựng `.veil` + `.confirm` bằng tay ở ba chỗ
 * (`PublishSettings`, `Chat`, và nay là `Panel`), và cả ba **cùng thiếu ba thứ**: không
 * đóng được bằng `Esc`, không đóng được bằng cách bấm ra ngoài, và `.veil` không có
 * `z-index` — trong khi menu `⋯` của rail có `z-index: 20` và vẽ qua portal vào `body`,
 * nên một menu đang mở vẽ **đè lên** hộp thoại. Ba bản sao thiếu cùng ba thứ là dấu hiệu
 * của một khuôn chưa được rút ra, không phải của ba lần quên.
 *
 * Bấm ra ngoài đóng hộp, còn bấm **trong** hộp thì không — `stopPropagation` trên hộp là
 * cả cơ chế. Hộp thoại học sinh (`Tutor.tsx`) đã làm đúng thế từ đầu.
 *
 * @param onClose - Đóng hộp. Dùng cho cả `Esc` lẫn cú bấm ra ngoài, nên nó phải là đường
 *   **huỷ**, không phải đường xác nhận.
 * @param wide - Hộp rộng 680 thay vì 460. Lời giải cần chỗ; một hộp xác nhận thì không.
 * @param className - Class thêm cho hộp có khung riêng, như hộp chọn câu ngân hàng (`picker`).
 * @param inert - Cho phần ngoài hộp thôi nhận focus (`useInert`). Bật cho hộp mà một Tab lạc ra ngoài
 *   là đổi đối tượng của chính hộp, như hộp hỏi lại *Đặt lại mật khẩu* (review vòng 1, 21/10/2026).
 * @param children - Ruột của hộp.
 */
export default function Veil({
  onClose,
  wide = false,
  className = "",
  inert = false,
  children,
}: {
  onClose: () => void;
  wide?: boolean;
  className?: string;
  inert?: boolean;
  children: ReactNode;
}) {
  const veil = useRef<HTMLDivElement>(null);
  useInert(veil, inert);
  useEffect(() => {
    const shut = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", shut);
    return () => document.removeEventListener("keydown", shut);
  }, [onClose]);

  return (
    <div className="veil" role="dialog" aria-modal="true" onClick={onClose} ref={veil}>
      <div
        className={["confirm", wide ? "wide" : "", className].filter(Boolean).join(" ")}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

/**
 * Cho mọi thứ **ngoài** một hộp thoại thôi nhận focus và cú bấm (`inert`) trong lúc hộp mở.
 *
 * Màn che chỉ chặn chuột. Không có hook này thì Tab đi xuyên qua nó: tới ô nhắn chat phía sau hộp
 * đăng nhập, hay tới *Đặt lại mật khẩu* của em khác phía sau hộp mật khẩu -- và bấm Enter ở đó là
 * mất mật khẩu chỉ hiện một lần của em trước (review pha 3, 4 của `sign-in-and-accounts`).
 *
 * Đi từ hộp lên tới `body`, đánh dấu anh em của từng tầng; chỉ bỏ dấu những gì chính nó đã đánh.
 *
 * @param dialog - Phần tử màn che của hộp.
 * @param enabled - Tắt thì không đánh dấu gì (cho `Veil`, nơi hook luôn được gọi).
 */
export function useInert(dialog: RefObject<HTMLElement>, enabled = true): void {
  useEffect(() => {
    if (!enabled) return undefined;
    const marked: Element[] = [];
    for (
      let node: HTMLElement | null = dialog.current;
      node !== null && node !== document.body && node.parentElement !== null;
      node = node.parentElement
    ) {
      for (const one of node.parentElement.children) {
        if (one !== node && !one.hasAttribute("inert")) {
          one.setAttribute("inert", "");
          marked.push(one);
        }
      }
    }
    return () => marked.forEach((one) => one.removeAttribute("inert"));
  }, [dialog, enabled]);
}
