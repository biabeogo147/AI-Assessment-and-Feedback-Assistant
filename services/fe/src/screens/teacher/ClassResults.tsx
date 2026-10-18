import { useState } from "react";

import { moment, teacher } from "../../api";
import { go } from "../../App";
import { BoardHead, BoardWaiting, classLabel, NONE, oneDecimal, useBoard, vn } from "./Board";

/**
 * Màn 11 · *Kết quả bài kiểm tra trong lớp* (`205:1000`), plan `teacher-rail-screens`, việc 18.
 *
 * Bốn thẻ số (cao nhất, trung bình, trung vị, thấp nhất), biểu đồ phân bố điểm, và mỗi bài đã nộp một
 * dòng, điểm cao trước. Điểm là tổng trên thang số câu (ADR-16: mỗi câu 1 / 0,5 / 0), nên dòng phụ
 * nói rõ thang. Nút *Xuất bảng điểm (.xlsx)* (việc 20, plan `results-xlsx-export`) tải một tệp gồm
 * mã học sinh, họ tên, điểm từng câu và tổng; lỗi thì câu của BE hiện ngay dưới đầu màn.
 *
 * @param classId - Lớp nào.
 * @param assessmentId - Đề nào.
 */
export default function ClassResults({
  classId,
  assessmentId,
}: {
  classId: string;
  assessmentId: string;
}) {
  const { data, trouble } = useBoard(
    () => teacher.classResults(classId, assessmentId),
    `${classId}/${assessmentId}`,
  );
  const [exporting, setExporting] = useState(false);
  const [refused, setRefused] = useState("");

  /** Tải bảng điểm; bị từ chối thì giữ câu của BE để hiện dưới đầu màn. */
  async function exportSheet() {
    setExporting(true);
    setRefused("");
    try {
      await teacher.exportResults(classId, assessmentId);
    } catch (cause) {
      setRefused((cause as Error).message);
    } finally {
      setExporting(false);
    }
  }

  if (data === null) {
    return (
      <div className="board">
        <BoardHead back={{ label: "Lớp", to: `/teacher/lop/${classId}` }} title="" sub="" />
        <BoardWaiting trouble={trouble} />
      </div>
    );
  }

  // Chênh lệch giữa **hai số đang in** (một chữ số lẻ), để dòng ghi chú khớp đúng hai thẻ.
  const gap =
    data.mean !== null && data.median !== null
      ? oneDecimal(oneDecimal(data.mean) - oneDecimal(data.median))
      : 0;
  const tallest = Math.max(1, ...data.distribution);

  return (
    <div className="board">
      <BoardHead
        back={{ label: classLabel(data.class_name), to: `/teacher/lop/${classId}` }}
        title={data.title}
        sub={[
          classLabel(data.class_name),
          `${data.submitted}/${data.student_count} đã nộp`,
          `thang ${data.question_count} điểm`,
          `đóng lúc ${moment(data.closes_at)}`,
        ].join(" · ")}
        action={
          <button
            className="board-export"
            type="button"
            disabled={exporting}
            onClick={() => void exportSheet()}
          >
            Xuất bảng điểm (.xlsx)
          </button>
        }
      />
      {refused !== "" && (
        <p className="refused" role="alert">
          {refused}
        </p>
      )}

      <div className="result-top">
        <div className="stat-tiles">
          <StatTile label="CAO NHẤT" value={data.highest} />
          <StatTile
            label="TRUNG BÌNH"
            value={data.mean}
            note={
              Math.abs(gap) < 0.05
                ? undefined
                : `${gap < 0 ? "thấp" : "cao"} hơn trung vị ${vn(Math.abs(gap))}`
            }
          />
          <StatTile label="TRUNG VỊ" value={data.median} />
          <StatTile label="THẤP NHẤT" value={data.lowest} />
        </div>
        <div className="chart-card">
          <div className="chart-head">PHÂN BỐ ĐIỂM · {data.submitted} BÀI</div>
          {data.distribution.length === 0 ? (
            <div className="chart-empty">Chưa có bài nào nộp.</div>
          ) : (
            <div className="bars" role="img" aria-label="Phân bố điểm">
              {data.distribution.map((count, mark) => (
                <div className="bar-col" key={mark}>
                  <span className="bar-count">{count === 0 ? "\u00a0" : count}</span>
                  <span
                    className="bar"
                    style={{ height: `${Math.max(count === 0 ? 0 : 6, (count / tallest) * 96)}px` }}
                  />
                  <span className="bar-mark">{mark}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="board-table results fill" role="table">
        <div className="board-row head" role="row">
          <span>HỌ TÊN</span>
          <span className="num sorted">▾ ĐIỂM</span>
          <span className="num">SỐ CÂU ĐÚNG</span>
          <span className="num">THỜI GIAN LÀM</span>
          <span>NỘP LÚC</span>
          <span>GHI CHÚ</span>
          <span />
        </div>
        {data.rows.length === 0 && (
          <div className="board-row empty" role="row">
            Chưa có học sinh nào nộp bài.
          </div>
        )}
        {data.rows.map((one) => {
          const to = `/teacher/lop/${classId}/de/${assessmentId}/hs/${one.student_id}`;
          return (
            <div
              className="board-row open-able"
              role="row"
              key={one.student_id}
              tabIndex={0}
              onClick={() => go(to)}
              onKeyDown={(event) => {
                if (event.key === "Enter") go(to);
              }}
            >
              <span className="name">{one.full_name}</span>
              <span className="num name">{vn(one.mark, true)}</span>
              <span className="num muted-body">
                {one.first_try}/{data.question_count}
              </span>
              <span className="num muted-body">{one.minutes} phút</span>
              <span className="cell-muted">{moment(one.submitted_at)}</span>
              <span className="cell-faint small-row">{one.note}</span>
              <span className="chevron" aria-hidden="true">
                ›
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Một thẻ số (`Stat tile`): nhãn in hoa, con số 24/600, đôi khi một dòng ghi chú.
 *
 * @param value - Con số; `null` khi chưa ai nộp -- thẻ ghi *"—"*.
 */
export function StatTile({
  label,
  value,
  note,
  text,
}: {
  label: string;
  value?: number | null;
  note?: string;
  text?: string;
}) {
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{text ?? (value === null || value === undefined ? NONE : vn(value, true))}</div>
      {note !== undefined && <div className="stat-note">{note}</div>}
    </div>
  );
}
