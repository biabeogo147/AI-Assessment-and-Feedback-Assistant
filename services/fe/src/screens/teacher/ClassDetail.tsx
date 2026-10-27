import { useState } from "react";

import { moment, teacher, type RosterAccount, type StudentRow } from "../../api";
import { go } from "../../App";
import { BoardHead, BoardWaiting, classLabel, NONE, useBoard } from "./Board";
import Roster, { Passwords } from "./Roster";
import Veil from "./Veil";

/**
 * Màn 10 · *Chi tiết lớp* (`183:874`), plan `teacher-rail-screens`, việc 18.
 *
 * Hai bảng: các đề đã phát hành cho lớp (chặng theo giờ BE, mở lúc, đóng lúc, đã nộp), và học sinh.
 * Bấm một đề là sang kết quả của đề ấy trong lớp này (màn 11).
 *
 * Cột *Tên đăng nhập*, nút *Đặt lại mật khẩu* và *Thêm học sinh* có từ việc 22 (plan
 * `sign-in-and-accounts`): thêm học sinh mở hộp ba bước (`Roster`), đặt lại mật khẩu thì hỏi lại một
 * lần (Tier 2 câu 30, 21/10/2026: một cú bấm nhầm hàng làm mất mật khẩu cũ của em), rồi hiện mật khẩu
 * mới một lần (10b). Dòng phụ không có *năm học* vì không dữ liệu nào chở nó.
 *
 * Nút *Xoá lớp* chỉ hiện ở lớp rỗng, theo cờ `erasable` của BE (plan `erase-empty-class`, Figma
 * 10e/10f): hỏi lại một lần, xoá xong thì về màn 9. Kriky không xoá lớp.
 *
 * @param classId - Lớp nào.
 */
export default function ClassDetail({ classId }: { classId: string }) {
  const { data, trouble, setData } = useBoard(() => teacher.classDetail(classId), classId);
  const [adding, setAdding] = useState(false);
  const [reset, setReset] = useState<RosterAccount | null>(null);
  // Em đang được đặt lại mật khẩu. Trong lúc chờ, mọi nút *Đặt lại mật khẩu* đều khoá: một hộp mật
  // khẩu một lúc, và cú bấm thứ hai không được nuốt im lặng (review pha 4).
  const [resetting, setResetting] = useState<string | null>(null);
  const [refused, setRefused] = useState("");
  // Em đang được hỏi lại trước khi đặt lại mật khẩu (hộp xác nhận 10b).
  const [asking, setAsking] = useState<StudentRow | null>(null);
  // Hộp *Xoá lớp*: đang mở, đang gửi, và câu BE từ chối (lớp vừa có học sinh từ tab khác).
  const [erasing, setErasing] = useState(false);
  const [eraseBusy, setEraseBusy] = useState(false);
  const [eraseRefused, setEraseRefused] = useState("");

  /** Đọc lại lớp sau khi thêm học sinh hay cấp tên đăng nhập: bảng phía sau hộp phải đúng. */
  function reread() {
    void teacher
      .classDetail(classId)
      .then(setData)
      .catch((cause: Error) => setRefused(`Chưa đọc lại được danh sách lớp: ${cause.message}`));
  }

  /**
   * *Đặt lại mật khẩu* (10b): BE đặt ngay và trả mật khẩu mới một lần; hộp mật khẩu hiện nó.
   *
   * @param one - Em nào. Em chưa có tên đăng nhập thì BE cấp luôn, nên màn đọc lại lớp.
   */
  function resetPassword(one: StudentRow) {
    if (resetting !== null) return;
    setResetting(one.student_id);
    setRefused("");
    teacher
      .resetPassword(classId, one.student_id)
      .then((account) => {
        setReset(account);
        if (one.username === null) reread();
      })
      .catch((cause: Error) => setRefused(cause.message))
      .finally(() => setResetting(null));
  }

  /** Xoá lớp rỗng này. Bị từ chối thì hộp ở lại kèm lý do, và màn đọc lại lớp. */
  async function eraseClass() {
    setEraseRefused("");
    setEraseBusy(true);
    try {
      await teacher.eraseClass(classId);
    } catch (cause) {
      setEraseRefused((cause as Error).message);
      setEraseBusy(false);
      reread();
      return;
    }
    go("/teacher/lop");
  }

  const back = { label: "Danh sách lớp học", to: "/teacher/lop" };

  if (data === null) {
    return (
      <div className="board">
        <BoardHead back={back} title="" sub="" />
        <BoardWaiting trouble={trouble} />
      </div>
    );
  }

  return (
    <div className="board">
      <BoardHead
        back={back}
        title={classLabel(data.name)}
        sub={[`${data.student_count} học sinh`, data.courses].filter(Boolean).join(" · ")}
        action={
          <div className="board-actions">
            {data.erasable && (
              <button
                className="board-erase"
                type="button"
                onClick={() => {
                  setEraseRefused("");
                  setErasing(true);
                }}
              >
                Xoá lớp
              </button>
            )}
            <button className="board-export" type="button" onClick={() => setAdding(true)}>
              Thêm học sinh
            </button>
          </div>
        }
      />
      {refused !== "" && (
        <p className="refused" role="alert">
          {refused}
        </p>
      )}

      <h2 className="board-section">Bài kiểm tra đã phát hành cho lớp này</h2>
      <div className="board-table class-papers" role="table">
        <div className="board-row head" role="row">
          <span>TÊN ĐỀ</span>
          <span>TRẠNG THÁI</span>
          <span>MỞ LÚC</span>
          <span>ĐÓNG LÚC</span>
          <span className="num">ĐÃ NỘP</span>
          <span />
        </div>
        {data.papers.length === 0 && (
          <div className="board-row empty" role="row">
            Lớp này chưa nhận đề nào.
          </div>
        )}
        {data.papers.map((one) => {
          // Đề chưa tới giờ mở chưa có kết quả nào để xem: dòng không mở được, như màn 21.
          const to =
            one.phase === "not_yet" ? null : `/teacher/lop/${classId}/de/${one.assessment_id}`;
          return (
            <div
              className={`board-row ${to === null ? "" : "open-able"}`}
              role="row"
              key={one.assessment_id}
              tabIndex={to === null ? undefined : 0}
              onClick={to === null ? undefined : () => go(to)}
              onKeyDown={(event) => {
                if (to !== null && event.key === "Enter") go(to);
              }}
            >
              <span className="name">{one.title}</span>
              <span className={`phase ${phaseTone(one.phase)}`}>{one.status}</span>
              <span className="cell-muted">{moment(one.opens_at)}</span>
              <span className="cell-muted">{moment(one.closes_at)}</span>
              <span className={`num ${one.submitted === 0 ? "cell-faint" : ""}`}>
                {one.submitted === 0 ? NONE : `${one.submitted}/${one.student_count}`}
              </span>
              <span className="chevron" aria-hidden="true">
                {to === null ? "" : "›"}
              </span>
            </div>
          );
        })}
      </div>

      <h2 className="board-section">Học sinh</h2>
      <div className="board-table class-students fill" role="table">
        <div className="board-row head" role="row">
          <span>HỌ TÊN</span>
          <span>MÃ HỌC SINH</span>
          <span>TÊN ĐĂNG NHẬP</span>
          <span />
        </div>
        {data.students.length === 0 && (
          <div className="board-row empty" role="row">
            Lớp này chưa có học sinh nào.
          </div>
        )}
        {data.students.map((one) => (
          <div className="board-row" role="row" key={one.student_id}>
            <span className="name">{one.full_name}</span>
            <span className="code">{one.student_code}</span>
            <span className={one.username === null ? "cell-faint" : "code"}>
              {one.username ?? NONE}
            </span>
            <button
              className="reset-password"
              type="button"
              disabled={resetting !== null}
              onClick={() => setAsking(one)}
            >
              Đặt lại mật khẩu
            </button>
          </div>
        ))}
      </div>

      {adding && (
        <Roster
          classId={classId}
          name={data.name}
          onCreated={reread}
          onClose={() => setAdding(false)}
        />
      )}
      {asking !== null && (
        <Veil onClose={() => setAsking(null)} inert>
          <h3>Đặt lại mật khẩu cho {asking.full_name}?</h3>
          <p className="lead">
            Mật khẩu cũ của em sẽ không dùng được nữa. Nếu em đang làm bài, em phải đăng nhập lại bằng
            mật khẩu mới.
          </p>
          <div className="confirm-actions">
            {/* Focus vào đường huỷ: Enter ngay sau khi hộp mở không đổi mật khẩu của ai. */}
            <button className="btn" type="button" autoFocus onClick={() => setAsking(null)}>
              Giữ mật khẩu cũ
            </button>
            <button
              className="btn primary"
              type="button"
              onClick={() => {
                resetPassword(asking);
                setAsking(null);
              }}
            >
              Đặt lại mật khẩu
            </button>
          </div>
        </Veil>
      )}
      {erasing && (
        // Cùng khuôn với hộp xoá đề nháp trống (`652:3899`): lớp rỗng không có gì để mất, nên chỉ
        // câu hỏi, một dòng nói lớp đi đâu, và hai nút. Đang gửi thì không đóng được.
        <Veil onClose={() => !eraseBusy && setErasing(false)} inert>
          <h3>Xoá lớp “{data.name}”?</h3>
          {/* Bị từ chối thì câu của BE thay lời dẫn: *"chưa có học sinh"* nằm trên *"Lớp còn 1 học
              sinh"* là hai câu trái nhau (review plan `erase-empty-class`). */}
          {eraseRefused === "" ? (
            <p className="lead">
              Lớp chưa có học sinh và chưa nhận đề nào. Xoá rồi thì không lấy lại được.
            </p>
          ) : (
            <p className="refused" role="alert">
              {eraseRefused}
            </p>
          )}
          <div className="confirm-actions">
            <button
              className="btn"
              type="button"
              autoFocus
              disabled={eraseBusy}
              onClick={() => setErasing(false)}
            >
              Giữ lại
            </button>
            <button
              className="btn primary"
              type="button"
              disabled={eraseBusy}
              onClick={() => void eraseClass()}
            >
              Xoá lớp
            </button>
          </div>
        </Veil>
      )}
      {reset !== null && (
        <Passwords
          title={`Đã đặt lại mật khẩu cho ${reset.full_name}`}
          accounts={[reset]}
          onClose={() => setReset(null)}
        />
      )}
    </div>
  );
}

/**
 * Sắc chữ của một chặng, theo **mã** BE gửi kèm nhãn: đang diễn ra thì teal (`state/processing`), đã
 * xong thì nhạt, chưa tới thì mực thường. Chỉ là màu -- nhãn là chữ của BE.
 */
export function phaseTone(phase: string): string {
  if (phase === "open" || phase === "remediating") return "live";
  if (phase === "over") return "over";
  return "";
}
