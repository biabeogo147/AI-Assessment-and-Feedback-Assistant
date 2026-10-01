import { useEffect, useState } from "react";

import "./tokens.css";
import "./teacher.css";
import { api, type Me } from "./api";
import AssignmentList from "./screens/student/AssignmentList";
import Result from "./screens/student/Result";
import Round from "./screens/student/Round";
import Sitting from "./screens/student/Sitting";
import Tutor from "./screens/student/Tutor";
import Chat from "./screens/teacher/Chat";

/**
 * Đọc route hiện tại từ hash của location.
 *
 * Dùng hash router thay vì một thư viện routing: năm màn hình, không có layout
 * lồng nhau, thì không đáng thêm một dependency — mà nút back vẫn chạy.
 *
 * @returns Phần hash sau khi bỏ dấu `#` ở đầu, mặc định là `/`.
 */
function useRoute(): string {
  const [route, setRoute] = useState(() => window.location.hash.slice(1) || "/");
  useEffect(() => {
    const onChange = () => setRoute(window.location.hash.slice(1) || "/");
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

/** Đưa trình duyệt sang một route mà không reload lại cả trang. */
export function go(route: string): void {
  window.location.hash = route;
}

/**
 * Chọn bề mặt theo route, trước khi bất cứ request nào bay ra.
 *
 * Phải là nhánh **đầu tiên**, không phải một `if` nằm giữa các màn hình học
 * sinh: một `#/teacher` đi qua phần dưới sẽ gọi `GET /api/me` với actor học
 * sinh chỉ để rồi vứt kết quả đi, và trên một BE chưa có dữ liệu học sinh thì
 * màn hình giáo viên hiện ra một câu lỗi của người khác.
 *
 * Hai vai không chia sẻ state nào. Đó là chủ ý: `ACTOR` trong `api.ts` nói hai
 * người này là hai phiên khác nhau, và một `me` dùng chung sẽ là chỗ đầu tiên
 * điều đó bị quên.
 */
export default function App() {
  const route = useRoute();
  if (route === "/teacher" || route.startsWith("/teacher/")) return <Teacher />;
  return <Student />;
}

/**
 * Bề mặt giáo viên.
 *
 * Panel là một **route**, không phải một state cục bộ: `#/teacher/de/{id}` mở nó, nút back
 * đóng nó, và một lần F5 dựng lại đúng màn hình đang mở. Một state cục bộ thì mất cả ba.
 */
function Teacher() {
  const route = useRoute();
  const paper = /^\/teacher\/de\/([^/]+)/.exec(route);
  return (
    <Chat
      openPaper={paper ? paper[1] : null}
      publishing={/^\/teacher\/de\/[^/]+\/phat-hanh$/.test(route)}
    />
  );
}

/**
 * Phần giao diện dành cho học sinh.
 *
 * Danh tính được lấy một lần rồi truyền xuống, vì mọi màn hình đều mang dải tên,
 * lớp và mã học sinh mà ADR-13 đòi phải có trên một máy nhiều học sinh dùng
 * chung.
 */
function Student() {
  const route = useRoute();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  if (error !== null) {
    return (
      <div className="page">
        <div className="error" role="alert">
          {error}
        </div>
      </div>
    );
  }
  if (me === null) {
    return <div className="page">Đang tải…</div>;
  }

  const attempt = /^\/attempt\/([^/]+)$/.exec(route);
  if (attempt) return <Sitting me={me} attemptId={attempt[1]} />;

  const result = /^\/attempt\/([^/]+)\/result$/.exec(route);
  if (result) return <Result me={me} attemptId={result[1]} />;

  const tutor = /^\/attempt\/([^/]+)\/tutor$/.exec(route);
  if (tutor) return <Tutor me={me} attemptId={tutor[1]} />;

  const round = /^\/round\/([^/]+)\/([^/]+)$/.exec(route);
  if (round) return <Round me={me} attemptId={round[1]} roundId={round[2]} />;

  return <AssignmentList me={me} />;
}
