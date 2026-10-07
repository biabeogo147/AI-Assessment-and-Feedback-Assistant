import { useEffect, useState } from "react";

import "./tokens.css";
import "./teacher.css";
import { api, teacher, type Me } from "./api";
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
 * Cả đoạn chat lẫn panel là **route**, không phải state cục bộ: nút back đóng panel rồi
 * mới rời đoạn chat, và một lần F5 dựng lại đúng màn hình đang mở. Một state cục bộ thì
 * mất cả ba.
 *
 * Panel **lồng trong** đoạn chat đã sinh ra đề, vì đó là nơi nó thuộc về: biên bản duyệt
 * và phát hành rơi vào đoạn chat ấy, nên mở panel từ một đoạn khác sẽ là mở một thứ mà
 * những gì nó ghi ra lại hiện ở chỗ khác.
 */
function Teacher() {
  const route = useRoute();

  // Màn trống sau khi bấm *Đoạn chat mới*. Là một route vì nếu không thì cú bấm ấy không
  // đổi hash khi đang đứng ở `#/teacher`, và một nút không làm gì là một nút nói dối.
  if (route === "/teacher/moi") {
    return <Chat conversationId={null} fresh openPaper={null} />;
  }

  // Hậu tố `/phat-hanh` **không còn là một route**. Nó từng nói *đang ở màn cài đặt
  // phát hành*, tức một nấc của đề — mà vòng đời là luật của BE (ADR-01), nên một cái URL
  // kể nấc là một nguồn thứ hai cho cùng một sự thật, và hai nguồn thì lệch được: thẻ
  // trong chat luôn đi `/de/{id}` không hậu tố, nên một đề đã duyệt mở ra vẫn thấy màn
  // hình của đề chưa duyệt. Panel nay đọc nấc từ `state`.
  //
  // Vẫn **nuốt** hậu tố ấy khi nó còn trong một bookmark hay một tab mở từ hôm qua: link
  // cũ phải mở được, nó chỉ thôi mở ra một màn hình khác.
  const nested = /^\/teacher\/chat\/([^/]+)(?:\/de\/([^/]+?))?(?:\/phat-hanh)?$/.exec(route);
  if (nested) {
    return (
      <Chat
        conversationId={nested[1]}
        fresh={false}
        openPaper={nested[2] ?? null}
      />
    );
  }

  // Link cũ `#/teacher/de/{id}`: không biết đoạn chat nào, nên hỏi BE rồi chuyển. Giữ nó
  // sống vì một bookmark hay một tab mở từ hôm qua không có lỗi gì.
  const bare = /^\/teacher\/de\/([^/]+?)(?:\/phat-hanh)?$/.exec(route);
  if (bare) return <Settle paper={bare[1]} />;

  return <Chat conversationId={null} fresh={false} openPaper={null} />;
}

/**
 * Chuyển một link cũ về route lồng nhau của nó.
 *
 * Màn hình này không vẽ gì ngoài một dòng chờ: nó tồn tại đúng một nhịp, để hỏi BE xem
 * đề ấy sinh ra từ đoạn chat nào. Đề không thuộc đoạn nào — đề seed, đề tạo tay — thì về
 * đoạn đang chạy, vì panel vẫn phải mở được.
 *
 * @param paper - Đề trong link cũ.
 */
function Settle({ paper }: { paper: string }) {
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    teacher
      .assessment(paper)
      .then((found) => {
        const where = found.conversation_id;
        go(where === "" ? "/teacher" : `/teacher/chat/${where}/de/${paper}`);
      })
      .catch((cause: Error) => setFailed(cause.message));
  }, [paper]);

  return <div className="page">{failed ?? "Đang mở…"}</div>;
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
