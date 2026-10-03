import { useEffect, type ReactNode } from "react";

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
 * @param children - Ruột của hộp.
 */
export default function Veil({
  onClose,
  wide = false,
  children,
}: {
  onClose: () => void;
  wide?: boolean;
  children: ReactNode;
}) {
  useEffect(() => {
    const shut = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", shut);
    return () => document.removeEventListener("keydown", shut);
  }, [onClose]);

  return (
    <div className="veil" role="dialog" aria-modal="true" onClick={onClose}>
      <div
        className={wide ? "confirm wide" : "confirm"}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
