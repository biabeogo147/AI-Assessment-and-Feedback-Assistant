import { useRef, useState } from "react";

import { api, type Me } from "../../api";
import { TopBar } from "../../components";

/**
 * Màn 12 · *Đăng nhập của học sinh* (`659:5676`, trang Screen — Student).
 *
 * Tên đăng nhập và mật khẩu do giáo viên phát (Figma 28c); không có đăng ký, không có quên mật
 * khẩu -- dòng chú thích dưới nút nói em phải nhờ ai. Lời từ chối của BE hiện ngay trên nút (12b
 * `713:830`).
 *
 * @param onSignedIn - Đăng nhập xong: `App` nhận người và vẽ màn đang đứng.
 */
export default function SignIn({ onSignedIn }: { onSignedIn: (me: Me) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [refused, setRefused] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const secret = useRef<HTMLInputElement>(null);

  /**
   * Gửi form: đăng nhập rồi đọc `me`.
   *
   * @param event - Lần gửi form; chặn tải lại trang.
   * @remarks Gọi BE; bị từ chối thì giữ màn với câu của BE.
   */
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setRefused(null);
    try {
      await api.signIn(username, password);
      onSignedIn(await api.me());
    } catch (cause) {
      setRefused((cause as Error).message);
      setBusy(false);
      // Nút vừa bị khoá nên focus đã rơi về `body`; đưa về ô mật khẩu để gõ lại ngay.
      secret.current?.select();
    }
  }

  return (
    <>
      <TopBar me={null} />
      <main className="student-sign-in-page">
        <form
          className="student-sign-in"
          onSubmit={(event) => void submit(event)}
          aria-labelledby="student-sign-in-title"
          aria-busy={busy}
          noValidate
        >
          <h1 id="student-sign-in-title">Đăng nhập để làm bài</h1>
          <label className="student-field">
            <span>Tên đăng nhập</span>
            <input
              value={username}
              autoComplete="username"
              autoCapitalize="none"
              autoFocus
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label className="student-field">
            <span>Mật khẩu</span>
            <input
              ref={secret}
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {refused !== null && (
            <p className="refused" role="alert">
              {refused}
            </p>
          )}
          <button className="student-sign-in-button" type="submit" disabled={busy}>
            Đăng nhập
          </button>
          <p className="note">
            Tên đăng nhập và mật khẩu do thầy cô phát cho em. Quên mật khẩu thì nhờ thầy cô đặt lại.
          </p>
        </form>
      </main>
    </>
  );
}
