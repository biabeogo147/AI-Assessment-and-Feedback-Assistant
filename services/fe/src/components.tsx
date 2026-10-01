import { useEffect, useState, type ReactNode } from "react";

import { countdown, type Me } from "./api";
import { go } from "./App";

/**
 * Dải danh tính mà mọi màn hình của học sinh đều mang.
 *
 * ADR-13: sản phẩm chạy trong phòng máy dùng chung, nên mỗi màn hình phải trả
 * lời được "ai đang đăng nhập" và cho một đường ra ngay tại đó. Cao 57px, brand
 * cỡ 16 semibold, danh tính cỡ 14 muted — số đo lấy từ file design, không phải
 * từ cảm nhận.
 */
export function TopBar({ me }: { me: Me }) {
  return (
    <header className="topbar">
      <span className="mark" aria-hidden />
      <button
        className="brand"
        type="button"
        style={{ background: "none", padding: 0, cursor: "pointer" }}
        onClick={() => go("/")}
      >
        Kriky
      </button>
      <span className="spacer" />
      <span className="identity">
        <span className="who">{me.full_name}</span>
        <span>·</span>
        <span>Lớp {me.class_name}</span>
        <span>·</span>
        <span className="code">{me.student_code}</span>
      </span>
      <button className="btn-signout" type="button">
        Đăng xuất
      </button>
    </header>
  );
}

/**
 * Điểm của một câu hỏi, ở một trong ba mức của ADR-16.
 *
 * Hình dạng mang nghĩa — đầy, nửa, rỗng — nên điểm vẫn đọc được khi in đen
 * trắng. Mức 0,5 dùng màu mực chứ không có màu riêng, vì ADR-12 chưa cấp cho nó
 * một màu nào.
 *
 * @param mark - 1, 0.5 hoặc 0.
 * @param tip - Câu giải thích lý do, hiện khi hover. ADR-16 giữ nó ngoài phần
 *   thân trang: in dưới mỗi dòng thì nó lặp lại mà không cho thêm thông tin gì.
 *   Nó là một node chứ không phải string, vì design đặt phần hành động bên trong
 *   ở SemiBold, giống như banner trên cùng màn hình đó.
 */
export function ScoreMark({ mark, tip }: { mark: number; tip?: ReactNode }) {
  const level = mark === 1 ? "full" : mark === 0.5 ? "half" : "zero";
  const text = mark === 0.5 ? "0,5" : String(mark);
  return (
    <span className="hoverable" tabIndex={0}>
      <span className={`mark ${level}`}>
        <span className="glyph" aria-hidden />
        {text}
      </span>
      {tip ? <span className="tip">{tip}</span> : null}
    </span>
  );
}

/**
 * Một đồng hồ đếm ngược tới mốc thời gian do server quyết định.
 *
 * Nó là trang trí, không phải thứ cưỡng chế: về không thì không thay đổi gì, và
 * BE từ chối một câu trả lời muộn bất kể đồng hồ này đang hiện gì (ADR-15).
 *
 * @param endsAt - Mốc thời gian ISO mà đồng hồ chạy tới.
 * @param onExpire - Được gọi đúng một lần khi đồng hồ về không.
 */
export function Countdown({ endsAt, onExpire }: { endsAt: string; onExpire?: () => void }) {
  const [left, setLeft] = useState(() => new Date(endsAt).getTime() - Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => {
      const remaining = new Date(endsAt).getTime() - Date.now();
      setLeft(remaining);
      if (remaining <= 0) {
        window.clearInterval(timer);
        onExpire?.();
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [endsAt, onExpire]);

  return <span style={{ fontVariantNumeric: "tabular-nums" }}>{countdown(left)}</span>;
}

/**
 * Thẻ đồng hồ trên một màn hình đang có đồng hồ chạy.
 *
 * @param endsAt - Lúc đồng hồ dừng.
 */
export function TimeCard({ endsAt }: { endsAt: string }) {
  return (
    <div className="time-card">
      <span className="muted" style={{ flex: 1 }}>
        Còn lại
      </span>
      <Countdown endsAt={endsAt} />
    </div>
  );
}

/** Dải báo lỗi. Trả lời sai không phải là lỗi, nên chỗ này chỉ dành cho thất bại thật. */
export function ErrorStrip({ message }: { message: string | null }) {
  if (message === null) return null;
  return (
    <div className="error" role="alert">
      {message}
    </div>
  );
}
