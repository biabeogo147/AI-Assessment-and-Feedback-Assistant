import { Fragment, useEffect, useState, type ReactNode } from "react";

import "./tokens.css";
import "./teacher.css";
import { ApiError, api, onSignedOut, teacher, type Me, type TeacherMe } from "./api";
import { StudentSession } from "./components";
import AssignmentList from "./screens/student/AssignmentList";
import Result from "./screens/student/Result";
import Round from "./screens/student/Round";
import SignIn from "./screens/student/SignIn";
import Sitting from "./screens/student/Sitting";
import Tutor from "./screens/student/Tutor";
import { SessionContext } from "./screens/teacher/Account";
import { VersionTag, useVersionCheck } from "./Version";
import Chat from "./screens/teacher/Chat";
import Bank, { BankEditor } from "./screens/teacher/Bank";
import Dashboard, { BoardQuestion, BoardReports } from "./screens/teacher/Dashboard";
import ClassDetail from "./screens/teacher/ClassDetail";
import ClassResults from "./screens/teacher/ClassResults";
import Classes from "./screens/teacher/Classes";
import Papers from "./screens/teacher/Papers";
import StudentWork from "./screens/teacher/StudentWork";

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

/** Bề mặt mà một trang vẽ: giáo viên hay học sinh. */
export type Surface = "teacher" | "student";

/**
 * Chọn bề mặt từ tên máy và route.
 *
 * Trên lab mỗi vai một tên: `teacher.<tên gốc>` và `student.<tên gốc>` (plan `lab-subdomains`).
 * Hai tên phục vụ cùng một bản build, nên chỉ `location.hostname` cho biết trang đang ở đâu. Ở đó
 * **tên máy thắng hash**: `#/teacher` trên tên học sinh về màn học sinh, và giáo viên gõ tên của
 * mình là vào thẳng màn giáo viên. Đây là giao diện, không phải quyền: quyền là cookie theo vai mà
 * BE cấp. Hai tiền tố là quy ước chung với `deploy/lab/terraform/main.tf`;
 * `tools/tests/test_lab_deploy.py` giữ hai bên khớp nhau.
 *
 * Mọi tên máy khác (`127.0.0.1` ở máy dev, stack lab ở local) chọn theo hash như trước.
 *
 * @param hostname `location.hostname` của trang.
 * @param route Route hiện tại, từ `useRoute`.
 * @returns Bề mặt phải vẽ, và route phải chuyển tới trước khi vẽ (`null` khi route đã đúng).
 */
export function surfaceFor(
  hostname: string,
  route: string,
): { surface: Surface; redirect: string | null } {
  const teacherRoute = route === "/teacher" || route.startsWith("/teacher/");
  if (hostname.startsWith("teacher.")) {
    return { surface: "teacher", redirect: teacherRoute ? null : "/teacher" };
  }
  if (hostname.startsWith("student.")) {
    return { surface: "student", redirect: teacherRoute ? "/" : null };
  }
  return { surface: teacherRoute ? "teacher" : "student", redirect: null };
}

/**
 * Chọn bề mặt theo route, trước khi bất cứ request nào bay ra.
 *
 * Phải là nhánh **đầu tiên**, không phải một `if` nằm giữa các màn hình học
 * sinh: một `#/teacher` đi qua phần dưới sẽ gọi `GET /api/me` với actor học
 * sinh chỉ để rồi vứt kết quả đi, và trên một BE chưa có dữ liệu học sinh thì
 * màn hình giáo viên hiện ra một câu lỗi của người khác.
 *
 * Hai vai không chia sẻ state nào. Đó là chủ ý: mỗi vai một cookie phiên (việc 22), hai
 * người này là hai phiên khác nhau, và một `me` dùng chung sẽ là chỗ đầu tiên điều đó bị
 * quên.
 *
 * Route sai với tên máy thì đổi bằng `location.replace`, không bằng `go`: nút back không được đưa
 * về đúng cái route vừa bị từ chối. Trong nhịp chờ `hashchange` thì chưa vẽ gì, để không bề mặt nào
 * kịp gọi BE.
 */
export default function App() {
  const route = useRoute();
  // Một lần cho cả app, trước mọi lối ra sớm: màn đăng nhập cũng so tên bản (plan `lab-version`).
  useVersionCheck();
  const { surface, redirect } = surfaceFor(window.location.hostname, route);
  useEffect(() => {
    if (redirect !== null) window.location.replace(`#${redirect}`);
  }, [redirect]);
  if (redirect !== null) return null;
  if (surface === "teacher") return <Teacher />;
  // Học sinh không có rail: tên bản ở góc dưới phải, một lần cho mọi màn kể cả màn đăng nhập.
  return (
    <>
      <Student />
      <VersionTag corner />
    </>
  );
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
  // `null`: đang hỏi BE; `"out"`: BE nói chưa đăng nhập (việc 22, plan `sign-in-and-accounts`).
  const [me, setMe] = useState<TeacherMe | "out" | null>(null);
  const [fault, setFault] = useState<string | null>(null);
  // Người đăng nhập gần nhất **trong tab này**. Phiên hết giữa chừng thì cây giữ nguyên dưới hộp
  // đăng nhập -- câu đang sửa, chữ đang gõ còn đó -- và đăng nhập lại đúng người ấy là làm tiếp.
  // Người khác vào thì dựng lại từ đầu, ở màn mở đầu: route của người trước không phải của họ.
  const [last, setLast] = useState<string | null>(null);

  useEffect(() => {
    teacher
      .me()
      .then(setMe)
      .catch((cause: Error) =>
        cause instanceof ApiError && cause.status === 401 ? setMe("out") : setFault(cause.message),
      );
    // Phiên hết hạn hay bị đóng giữa lúc đang dùng: mọi lời gọi giáo viên nhận 401 đều đưa về đây.
    return onSignedOut("teacher", () => setMe("out"));
  }, []);

  if (fault !== null) {
    return (
      <div className="page">
        <div className="error" role="alert">
          {fault}
        </div>
      </div>
    );
  }
  if (me === null) return null;

  const out = me === "out";
  // Nhớ người vừa vào (cập nhật trong lúc vẽ, mẫu *state suy ra* của React: không qua một lần vẽ
  // thừa với key cũ).
  if (!out && me.teacher_id !== last) setLast(me.teacher_id);
  return (
    <SessionContext.Provider
      value={{
        me: out ? null : me,
        out,
        signedIn: (who) => {
          // Người khác với người trước trong tab này: về màn mở đầu, route cũ là của người kia.
          if (last !== null && who.teacher_id !== last) go("/teacher");
          setMe(who);
        },
        // Đăng xuất **hỏng** thì phiên còn sống: ném lại để menu nói ra, không giả vờ đã ra.
        signOut: () =>
          teacher.signOut().then(() => {
            setLast(null);
            setMe("out");
            go("/teacher");
          }),
      }}
    >
      {/* Dựng lại cả cây chỉ khi **người** đổi: các màn đọc dữ liệu một lần lúc mở, và dữ liệu ấy
          là của người trước. Phiên hết rồi đăng nhập lại cùng người thì cây giữ nguyên. */}
      <Fragment key={last ?? "out"}>
        {out && last === null ? (
          <Chat conversationId={null} fresh={false} openPaper={null} />
        ) : (
          <TeacherRoutes />
        )}
      </Fragment>
    </SessionContext.Provider>
  );
}

/** Các màn giáo viên theo route, khi đã đăng nhập. */
function TeacherRoutes() {
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

  // Các màn của rail (plan `teacher-rail-screens`): cột giữa vẽ màn ấy, rail giữ nguyên.
  const board = boardFor(route);
  if (board !== null) {
    return (
      <Chat
        conversationId={null}
        fresh={false}
        openPaper={null}
        view={board.view}
        place={board.place}
        aside={board.aside}
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
 * Màn của rail ứng với một route, cùng đích đến của rail cần sáng lên; `null` khi route không phải
 * một màn rail (plan `teacher-rail-screens`).
 *
 * @param route - Route hiện tại.
 */
function boardFor(
  route: string,
): { view: ReactNode; place: string; aside?: ReactNode } | null {
  // *Bảng theo dõi* và hai màn của hàng đợi (plan `dashboard-review-queue`).
  if (route === "/teacher/theo-doi") return { view: <Dashboard />, place: "theo-doi" };
  const reports = /^\/teacher\/theo-doi\/bao-cao\/([^/]+)$/.exec(route);
  if (reports) {
    return {
      view: <BoardReports key={reports[1]} assessmentId={reports[1]} />,
      place: "theo-doi",
    };
  }
  const rated = /^\/teacher\/theo-doi\/cau\/([^/]+)$/.exec(route);
  if (rated) {
    return { view: <BoardQuestion key={rated[1]} questionId={rated[1]} />, place: "theo-doi" };
  }
  if (route === "/teacher/lop") return { view: <Classes />, place: "lop" };
  if (route === "/teacher/de-kiem-tra") return { view: <Papers />, place: "de-kiem-tra" };
  if (route === "/teacher/ngan-hang") return { view: <Bank key="bank" />, place: "ngan-hang" };

  const bank = /^\/teacher\/ngan-hang\/([^/]+)$/.exec(route);
  if (bank) {
    return {
      view: <Bank key="bank" open={bank[1]} />,
      place: "ngan-hang",
      aside: <BankEditor key={bank[1]} bankId={bank[1]} />,
    };
  }
  const student = /^\/teacher\/lop\/([^/]+)\/de\/([^/]+)\/hs\/([^/]+)$/.exec(route);
  if (student) {
    const [, classId, assessmentId, studentId] = student;
    return {
      view: (
        <StudentWork
          key={student[0]}
          classId={classId}
          assessmentId={assessmentId}
          studentId={studentId}
        />
      ),
      place: "lop",
    };
  }
  const results = /^\/teacher\/lop\/([^/]+)\/de\/([^/]+)$/.exec(route);
  if (results) {
    return {
      view: <ClassResults key={results[0]} classId={results[1]} assessmentId={results[2]} />,
      place: "lop",
    };
  }
  const inClass = /^\/teacher\/lop\/([^/]+)$/.exec(route);
  if (inClass) return { view: <ClassDetail key={inClass[1]} classId={inClass[1]} />, place: "lop" };
  return null;
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
 * Phần giao diện dành cho học sinh, sau cổng phiên (việc 22, plan `sign-in-and-accounts`).
 *
 * Chưa đăng nhập thì màn 12. Đăng nhập xong thì `me` truyền xuống, vì mọi màn hình đều mang dải
 * tên, lớp và mã học sinh mà ADR-13 đòi phải có trên một máy nhiều học sinh dùng chung.
 */
function Student() {
  const route = useRoute();
  // `null`: đang hỏi BE; `"out"`: BE nói chưa đăng nhập (việc 22, plan `sign-in-and-accounts`).
  const [me, setMe] = useState<Me | "out" | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Em đăng nhập gần nhất trong tab này: phiên hết rồi vào lại đúng em ấy thì về lại **route** đang
  // đứng (màn đọc lại từ BE); một em khác vào thì về *Bài của tôi*, màn của em trước không phải của em.
  const [last, setLast] = useState<string | null>(null);
  // Đang chờ hash đổi về `#/` sau khi một em khác vào: `hashchange` tới ở một nhịp sau, và trong nhịp
  // ấy em mới không được vẽ một màn theo id của em trước (review pha 5).
  const [home, setHome] = useState(false);
  if (home && route === "/") setHome(false);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch((cause: Error) =>
        cause instanceof ApiError && cause.status === 401 ? setMe("out") : setError(cause.message),
      );
    return onSignedOut("student", () => setMe("out"));
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
  if (me === "out") {
    return (
      <SignIn
        onSignedIn={(who) => {
          if (last !== null && who.student_id !== last) {
            forgetRounds();
            setHome(true);
            go("/");
          }
          setLast(who.student_id);
          setMe(who);
        }}
      />
    );
  }
  if (me.student_id !== last) setLast(me.student_id);

  return (
    <StudentSession.Provider
      value={{
        signOut: () =>
          api.signOut().then(() => {
            forgetRounds();
            setLast(null);
            setMe("out");
            go("/");
          }),
      }}
    >
      <StudentRoutes me={me} route={home ? "/" : route} key={me.student_id} />
    </StudentSession.Provider>
  );
}

/**
 * Bỏ các lượt chữa đã chép vào `sessionStorage` (`round:{id}`, `Tutor.tsx`). Khoá không mang tên em,
 * nên khi em khác vào trên cùng tab mà không bỏ, nút Back vẽ ngay câu hỏi lượt chữa của em trước dưới
 * tên em sau (review pha 5).
 */
function forgetRounds(): void {
  try {
    for (const key of Object.keys(window.sessionStorage)) {
      if (key.startsWith("round:")) window.sessionStorage.removeItem(key);
    }
  } catch {
    /* trình duyệt chặn bộ nhớ: không có gì để bỏ */
  }
}

/** Các màn của học sinh theo route, khi đã đăng nhập. */
function StudentRoutes({ me, route }: { me: Me; route: string }) {
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
