import { createContext, useContext, useEffect, useRef, useState } from "react";

import { teacher, type TeacherMe } from "../../api";
import { useInert } from "./Veil";

/**
 * Phiên đăng nhập của giáo viên, cho mọi màn của bề mặt (việc 22, plan `sign-in-and-accounts`).
 *
 * `App.tsx` hỏi `GET /api/teacher/me` một lần rồi đặt context này. `out` chỉ đúng khi BE **đã
 * trả lời** 401: lúc chưa ai hỏi (test dựng một màn lẻ) thì không phải *chưa đăng nhập*, nên màn
 * vẫn đọc dữ liệu như cũ và ô tài khoản không vẽ gì.
 */
export interface Session {
  /** Người đang đăng nhập, hay `null` khi chưa biết hoặc chưa đăng nhập. */
  me: TeacherMe | null;
  /** BE đã nói *chưa đăng nhập*: rail thu về, hộp đăng nhập mở và không đóng được. */
  out: boolean;
  /** Đăng nhập hay đăng ký vừa xong. */
  signedIn: (me: TeacherMe) => void;
  /** Đăng xuất: BE xoá phiên, màn về trạng thái chưa đăng nhập. Ném khi BE chưa xoá được. */
  signOut: () => Promise<void>;
}

export const SessionContext = createContext<Session>({
  me: null,
  out: false,
  signedIn: () => undefined,
  signOut: () => Promise.resolve(),
});

export function useSession(): Session {
  return useContext(SessionContext);
}

// Cách gọi đứng trước tên trong `full_name` của dữ liệu demo (*Cô Phạm Thu Lan*): không phải chữ
// của tên, nên không vào avatar.
const TITLES = new Set(["cô", "thầy", "thày"]);

/**
 * Hai chữ của avatar: chữ đầu của họ và của tên (*Phạm Thu Lan* → `PL`, Figma 27).
 *
 * @param fullName - Họ và tên.
 */
export function initials(fullName: string): string {
  const words = fullName.split(/\s+/).filter((one) => one && !TITLES.has(one.toLowerCase()));
  if (words.length === 0) return "";
  const first = words[0][0];
  const last = words.length > 1 ? words[words.length - 1][0] : "";
  return (first + last).toUpperCase();
}

/**
 * Ô tài khoản ở góc dưới rail (Figma 26, 27).
 *
 * Chưa đăng nhập: chữ *Đăng nhập*, nằm dưới màn che của hộp đăng nhập. Đã đăng nhập: avatar và họ
 * tên; bấm mở menu tài khoản. Trong menu chỉ *Đăng xuất* bấm được (người dùng chốt 18/10/2026);
 * bốn mục kia vẽ mờ và không làm gì -- chúng là chỗ của những việc chưa có.
 */
export function AccountCell() {
  const { me, out, signOut } = useSession();
  const [open, setOpen] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);

  // Bấm ra ngoài hay `Esc` thì đóng, như menu `⋯` của rail. `pointerdown` chứ không `click`: xem
  // ghi chú cùng chỗ ở `Rail.tsx`.
  useEffect(() => {
    if (!open) return;
    const shut = (event: Event) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event.type === "pointerdown" && box.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", shut);
    document.addEventListener("keydown", shut);
    return () => {
      document.removeEventListener("pointerdown", shut);
      document.removeEventListener("keydown", shut);
    };
  }, [open]);

  if (out) {
    return (
      <div className="account-box">
        <div className="account signed-out">
          <span className="icon" aria-hidden="true">
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 2H9.5a.5.5 0 0 1 .5.5v7a.5.5 0 0 1-.5.5H6" />
              <path d="M1.5 6H7" />
              <path d="M5 4L7 6L5 8" />
            </svg>
          </span>
          Đăng nhập
        </div>
      </div>
    );
  }
  if (me === null) return null;

  return (
    <div className="account-box" ref={box}>
      {open && (
        <div className="account-menu" role="menu" aria-label="Tài khoản">
          {SOON.map((one) => (
            <div className="account-item" role="menuitem" aria-disabled="true" key={one.label}>
              <span className="icon" aria-hidden="true">
                {one.icon}
              </span>
              {one.label}
            </div>
          ))}
          <div className="account-rule" role="separator" />
          <button
            className="account-item sign-out"
            type="button"
            role="menuitem"
            onClick={() => {
              setRefused(null);
              signOut().catch((cause: Error) => setRefused(cause.message));
            }}
          >
            <span className="icon" aria-hidden="true">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M6.5 2H2.5a.5.5 0 0 0-.5.5v7a.5.5 0 0 0 .5.5h4" />
                <path d="M5 6H10.5" />
                <path d="M8.5 4L10.5 6L8.5 8" />
              </svg>
            </span>
            Đăng xuất
          </button>
          {refused !== null && (
            <p className="account-refused" role="alert">
              {refused}
            </p>
          )}
        </div>
      )}
      <button
        className="account"
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
          setRefused(null);
        }}
      >
        <span className="avatar" aria-hidden="true">
          {initials(me.full_name)}
        </span>
        <span className="account-name">{me.full_name}</span>
      </button>
    </div>
  );
}

const STROKE = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/** Bốn mục chưa có của menu tài khoản, đúng thứ tự và hình của Figma 27 (`659:5590`). */
const SOON = [
  {
    label: "Cài đặt",
    icon: (
      <svg viewBox="0 0 12 12" {...STROKE}>
        <path d="M1.5 3.5H10.5M1.5 8.5H10.5" />
        <circle cx="4.5" cy="3.5" r="1.4" />
        <circle cx="7.5" cy="8.5" r="1.4" />
      </svg>
    ),
  },
  {
    label: "Mức sử dụng",
    icon: (
      <svg viewBox="0 0 12 12" {...STROKE}>
        <path d="M2.5 10.5V7M6 10.5V4M9.5 10.5V1.5" />
      </svg>
    ),
  },
  {
    label: "Ngôn ngữ",
    icon: (
      <svg viewBox="0 0 12 12" {...STROKE}>
        <circle cx="6" cy="6" r="4.5" />
        <ellipse cx="6" cy="6" rx="2" ry="4.5" />
        <path d="M1.5 6H10.5" />
      </svg>
    ),
  },
  {
    label: "Trợ giúp",
    icon: (
      <svg viewBox="0 0 12 12" {...STROKE}>
        <circle cx="6" cy="6" r="4.5" />
        <path d="M4.6 4.7a1.4 1.4 0 1 1 1.9 1.3c-.4.2-.5.5-.5.9" />
        <circle cx="6" cy="8.6" r=".55" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
];

type Mode = "in" | "up";

/**
 * Hộp đăng nhập và hộp tạo tài khoản giáo viên (Figma 26 `659:5160`, 26b `659:5311`). Đăng nhập
 * chỉ có **một** ô *Số điện thoại / email*.
 *
 * Mở suốt lúc chưa đăng nhập và **không đóng được**: mọi màn giáo viên cần một người, nên không có
 * gì phía sau để quay về. Không có `Esc`, không bấm ra ngoài để đóng -- khác `Veil`.
 *
 * Lời từ chối của BE hiện ngay trên nút chính, cùng kiểu với lời từ chối trong mọi hộp khác.
 * *Tiếp tục với Google* chỉ là giao diện (người dùng chốt 18/10/2026): bấm thì nói thẳng là chưa
 * có, không im lặng.
 */
export function SignIn() {
  const { signedIn } = useSession();
  const [mode, setMode] = useState<Mode>("in");
  const [login, setLogin] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [refused, setRefused] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const veil = useRef<HTMLDivElement>(null);

  // Phía sau màn che thôi nhận focus: không thì Tab tới ô nhắn chat và gửi được một lượt từ một màn
  // chưa có ai đăng nhập (review pha 3).
  useInert(veil);

  /**
   * Gửi hộp: đăng nhập hay tạo tài khoản, rồi đọc `me` và báo cho `App`.
   *
   * @param event - Lần gửi form; chặn tải lại trang.
   * @remarks Gọi BE; bị từ chối thì giữ hộp mở với câu của BE.
   */
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setRefused(null);
    try {
      if (mode === "in") await teacher.signIn(login, password);
      else await teacher.signUp({ full_name: fullName, phone, email, password });
      signedIn(await teacher.me());
    } catch (cause) {
      setRefused((cause as Error).message);
      setBusy(false);
    }
  }

  function switchTo(next: Mode) {
    setMode(next);
    setRefused(null);
    setPassword("");
  }

  const title = mode === "in" ? "Đăng nhập vào Kriky" : "Tạo tài khoản giáo viên";
  return (
    <div className="veil" role="dialog" aria-modal="true" aria-labelledby="sign-in-title" ref={veil}>
      <form className="sign-in" onSubmit={(event) => void submit(event)} noValidate>
        <h2 id="sign-in-title">{title}</h2>
        {/* Đăng nhập: một ô cho cả hai (người dùng chốt 19/10/2026) -- có `@` thì BE đọc là email,
            không thì là số điện thoại (`account_routes.teacher_sign_in`). */}
        {mode === "in" ? (
          <Field
            label="Số điện thoại / email"
            value={login}
            onChange={setLogin}
            autoComplete="username"
            autoFocus
            plain
          />
        ) : (
          <>
            <Field label="Họ và tên" value={fullName} onChange={setFullName} autoComplete="name" autoFocus />
            <Field label="Số điện thoại" type="tel" value={phone} onChange={setPhone} autoComplete="tel" />
            <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
          </>
        )}
        <Field
          label="Mật khẩu"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete={mode === "in" ? "current-password" : "new-password"}
        />
        {refused !== null && (
          <p className="refused" role="alert">
            {refused}
          </p>
        )}
        <button className="sign-primary" type="submit" disabled={busy}>
          {mode === "in" ? "Đăng nhập" : "Tạo tài khoản"}
        </button>
        {mode === "in" && (
          <>
            <div className="sign-or" aria-hidden="true">
              <span />
              hoặc
              <span />
            </div>
            <button
              className="sign-google"
              type="button"
              onClick={() => setRefused("Đăng nhập bằng Google chưa có. Hãy dùng số điện thoại hoặc email.")}
            >
              G&nbsp;&nbsp;&nbsp;Tiếp tục với Google
            </button>
          </>
        )}
        <button className="sign-switch" type="button" onClick={() => switchTo(mode === "in" ? "up" : "in")}>
          {mode === "in" ? "Chưa có tài khoản? Tạo tài khoản" : "Đã có tài khoản? Đăng nhập"}
        </button>
      </form>
    </div>
  );
}

/** Một ô của hộp đăng nhập: nhãn 11 trên một ô nhập 40 (Figma `field …`). */
function Field({
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
  autoFocus = false,
  plain = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  autoComplete?: string;
  autoFocus?: boolean;
  /** Ô gõ SĐT hay email: bàn phím điện thoại không viết hoa chữ đầu, không tự sửa chính tả. */
  plain?: boolean;
}) {
  return (
    <label className="sign-field">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        autoCapitalize={plain ? "none" : undefined}
        autoCorrect={plain ? "off" : undefined}
        spellCheck={plain ? false : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
