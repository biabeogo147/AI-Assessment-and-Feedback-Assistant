import { useEffect, useState, type ReactNode } from "react";

import { go } from "../../App";

/**
 * Những mảnh chung của các màn rail (plan `teacher-rail-screens`): đầu trang, bảng, ô số.
 *
 * Mọi màn rail là một trang đọc: một đầu trang (link quay về, tiêu đề, dòng phụ, có khi một nút), rồi
 * một hay nhiều bảng trắng viền mảnh. Số đo lấy từ artboard 9 (`180:753`): cột giữa padding 32/40,
 * tiêu đề 24/600, dòng phụ 13 ink/muted; bảng bo 8, đầu bảng 11/600 ink/faint, hàng 44.
 */

/**
 * Đầu trang của một màn rail.
 *
 * @param back - Link quay về: chữ và route; bỏ trống ở màn gốc của một đích đến.
 * @param title - Tiêu đề.
 * @param sub - Dòng phụ, các ý nối bằng *" · "*.
 * @param action - Nút ở mép phải, nếu có.
 */
export function BoardHead({
  back,
  title,
  sub,
  action,
}: {
  back?: { label: string; to: string };
  title: string;
  sub: string;
  action?: ReactNode;
}) {
  return (
    <div className="board-head">
      <div className="titles">
        {back !== undefined && (
          <button className="crumb" type="button" onClick={() => go(back.to)}>
            ‹&nbsp; {back.label}
          </button>
        )}
        {title !== "" && <h1>{title}</h1>}
        <div className="sub">{sub}</div>
      </div>
      {action}
    </div>
  );
}

/**
 * Đọc một tài nguyên của màn rail, với ba trạng thái: đang đọc, lỗi, có dữ liệu.
 *
 * @param read - Lời gọi BE; đổi khi `key` đổi.
 * @param key - Chuỗi định danh lần đọc (thường là route): đổi thì đọc lại và bỏ lời đáp muộn.
 */
export function useBoard<T>(read: () => Promise<T>, key: string) {
  const [data, setData] = useState<T | null>(null);
  const [trouble, setTrouble] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    setData(null);
    setTrouble(null);
    read()
      .then((found) => {
        if (current) setData(found);
      })
      .catch((cause: Error) => {
        if (current) setTrouble(cause.message);
      });
    return () => {
      current = false;
    };
    // `read` là một closure mới mỗi lần vẽ; `key` mới là thứ nói lần đọc đã đổi.
  }, [key]);
  return { data, trouble, setData };
}

/** Trạng thái chờ hay lỗi của một màn rail, ở đúng chỗ bảng sẽ đứng. */
export function BoardWaiting({ trouble }: { trouble: string | null }) {
  return (
    <div className={trouble === null ? "board-wait" : "board-wait trouble"} role="status">
      {trouble ?? "Đang tải…"}
    </div>
  );
}

/**
 * Một con số theo kiểu Việt: dấu phẩy thập phân, tối đa hai chữ số lẻ (*"7,5"*, *"10"*, *"6,75"*).
 *
 * @param value - Con số.
 * @param fixed - Luôn in một chữ số lẻ (*"10,0"*) -- cho cột điểm, như Figma.
 */
export function vn(value: number, fixed = false): string {
  // Làm tròn **trước** khi in: `toFixed` làm tròn theo số nhị phân, nên 1,45 ra *"1,4"* mà 5,25 ra
  // *"5,3"* (review FE).
  const text = fixed ? (Math.round(value * 10) / 10).toFixed(1) : String(Math.round(value * 100) / 100);
  return text.replace(".", ",");
}

/** Một con số làm tròn một chữ số lẻ, đúng như thẻ số in nó -- cho phép trừ giữa hai thẻ. */
export function oneDecimal(value: number): number {
  return Math.round(value * 10) / 10;
}

/** Chữ *"—"* cho một ô không có số, như Figma: không phải *"0"*, vì không có gì để đếm. */
export const NONE = "—";

/**
 * Tên một lớp như Figma in: *"Lớp 12A"* cho tên bắt đầu bằng khối, nguyên văn cho tên tự đặt
 * (*"Ôn thi HSG 12"*, artboard 9).
 */
export function classLabel(name: string): string {
  return /^\d/.test(name) ? `Lớp ${name}` : name;
}
