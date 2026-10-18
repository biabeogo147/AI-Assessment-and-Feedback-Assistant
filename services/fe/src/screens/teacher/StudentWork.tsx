import { moment, teacher } from "../../api";
import MathText from "../../MathText";
import { BoardHead, BoardWaiting, classLabel, NONE, useBoard, vn } from "./Board";
import { StatTile } from "./ClassResults";

/**
 * Màn 23 · *Bài làm của một học sinh* (`656:4089`), plan `teacher-rail-screens`, việc 18.
 *
 * Bốn thẻ số (điểm, đúng ngay lần đầu, lượt chữa đã làm, số lần báo *giải thích chưa rõ*), và từng
 * câu: em chọn gì, đáp án là gì, điểm bao nhiêu. Mọi con số là của BE.
 *
 * @param classId - Lớp.
 * @param assessmentId - Đề.
 * @param studentId - Học sinh.
 */
export default function StudentWork({
  classId,
  assessmentId,
  studentId,
}: {
  classId: string;
  assessmentId: string;
  studentId: string;
}) {
  const { data, trouble } = useBoard(
    () => teacher.studentWork(classId, assessmentId, studentId),
    `${classId}/${assessmentId}/${studentId}`,
  );
  const results = `/teacher/lop/${classId}/de/${assessmentId}`;

  if (data === null) {
    return (
      <div className="board">
        <BoardHead back={{ label: "Kết quả", to: results }} title="" sub="" />
        <BoardWaiting trouble={trouble} />
      </div>
    );
  }

  return (
    <div className="board">
      <BoardHead
        back={{ label: `${data.title} · ${classLabel(data.class_name)}`, to: results }}
        title={data.full_name}
        sub={[
          `Mã học sinh ${data.student_code}`,
          data.submitted_at === null ? "chưa nộp" : `nộp lúc ${moment(data.submitted_at)}`,
          // Chữ của BE, cùng bảng với ghi chú màn kết quả; viết thường vì đứng giữa câu.
          data.note.charAt(0).toLowerCase() + data.note.slice(1),
        ]
          .filter(Boolean)
          .join(" · ")}
      />

      <div className="stat-tiles wide">
        <StatTile label="ĐIỂM" text={`${vn(data.mark, true)} / ${data.question_count}`} />
        <StatTile label="ĐÚNG NGAY LẦN ĐẦU" text={`${data.first_try} / ${data.question_count}`} />
        <StatTile label="LƯỢT CHỮA ĐÃ LÀM" text={String(data.rounds_done)} />
        <StatTile label="GIẢI THÍCH CHƯA RÕ" text={String(data.reports)} />
      </div>

      <div className="board-table work fill" role="table">
        <div className="board-row head" role="row">
          <span>CÂU</span>
          <span>EM CHỌN</span>
          <span>ĐÁP ÁN</span>
          <span className="num">ĐIỂM</span>
          <span />
        </div>
        {data.items.map((one) => (
          <div className="board-row" role="row" key={one.order}>
            <span className="stem-cell">
              <span className="small">Câu {one.order}</span>
              <MathText>{one.stem}</MathText>
            </span>
            <span className="cell-muted">{one.chosen === "" ? NONE : <MathText>{one.chosen}</MathText>}</span>
            <span className="cell-muted">
              <MathText>{one.correct}</MathText>
            </span>
            <span className="num">{vn(one.mark)}</span>
            <span />
          </div>
        ))}
      </div>
    </div>
  );
}
