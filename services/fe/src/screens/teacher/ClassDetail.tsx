import { moment, teacher } from "../../api";
import { go } from "../../App";
import { BoardHead, BoardWaiting, classLabel, NONE, useBoard } from "./Board";

/**
 * Màn 10 · *Chi tiết lớp* (`183:874`), plan `teacher-rail-screens`, việc 18.
 *
 * Hai bảng: các đề đã phát hành cho lớp (chặng theo giờ BE, mở lúc, đóng lúc, đã nộp), và học sinh.
 * Bấm một đề là sang kết quả của đề ấy trong lớp này (màn 11).
 *
 * Cột *Tên đăng nhập*, nút *Đặt lại mật khẩu* và *Thêm học sinh* thuộc việc 22 (đăng nhập); dòng phụ
 * không có *năm học* vì không dữ liệu nào chở nó (Decision 1 của plan).
 *
 * @param classId - Lớp nào.
 */
export default function ClassDetail({ classId }: { classId: string }) {
  const { data, trouble } = useBoard(() => teacher.classDetail(classId), classId);
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
      />

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
        </div>
        {data.students.map((one) => (
          <div className="board-row" role="row" key={one.student_id}>
            <span className="name">{one.full_name}</span>
            <span className="code">{one.student_code}</span>
          </div>
        ))}
      </div>
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
