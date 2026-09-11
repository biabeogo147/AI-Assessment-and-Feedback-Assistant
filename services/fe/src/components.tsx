import { useEffect, useState } from "react";

import { countdown, type Me } from "./api";
import { go } from "./App";

/**
 * The identity strip carried by every student screen.
 *
 * ADR-13: the product runs in a shared computer room, so each screen has to
 * answer "who is signed in" and offer a way out on the spot.
 */
export function TopBar({ me }: { me: Me }) {
  return (
    <header className="topbar">
      <span aria-hidden>🐝</span>
      <span className="brand">Kriky</span>
      <span className="spacer" />
      <span className="identity">
        {me.full_name} · Lớp {me.class_name} · {me.student_code}
      </span>
      <button className="btn-secondary" type="button">
        Đăng xuất
      </button>
    </header>
  );
}

/**
 * One question's mark, at one of the three levels of ADR-16.
 *
 * Shape carries the meaning -- filled, half, hollow -- so the mark survives
 * being printed in black and white. Level 0.5 uses ink rather than a colour of
 * its own, because ADR-12 has not granted it one.
 *
 * @param mark - 1, 0.5 or 0.
 * @param tip - The hover sentence explaining why. ADR-16 keeps this out of the
 *   page body: printed under every row it would repeat without informing.
 */
export function ScoreMark({ mark, tip }: { mark: number; tip?: string }) {
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
 * A countdown towards an instant the server decided.
 *
 * Decoration, not enforcement: reaching zero here changes nothing, and BE
 * refuses a late answer whatever this shows (ADR-15).
 *
 * @param endsAt - ISO instant the clock runs to.
 * @param onExpire - Called once when the clock reaches zero.
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

  return <strong style={{ fontVariantNumeric: "tabular-nums" }}>{countdown(left)}</strong>;
}

/** A link back to the assignment list, for screens a student can leave. */
export function BackToList() {
  return (
    <button className="btn-quiet" type="button" onClick={() => go("/")}>
      ‹ Bài của tôi
    </button>
  );
}

/** An error strip. Wrong answers are not errors, so this is for failures only. */
export function ErrorStrip({ message }: { message: string | null }) {
  if (message === null) return null;
  return (
    <div className="error" role="alert">
      {message}
    </div>
  );
}
