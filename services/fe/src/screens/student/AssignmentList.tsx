import { useEffect, useState } from "react";

import { api, moment, type Assignment, type Me } from "../../api";
import { go } from "../../App";
import { ErrorStrip, TopBar } from "../../components";

/**
 * Cách diễn đạt bằng tiếng Việt cho từng status BE có thể trả về.
 *
 * BE gửi một state, không phải một câu: phần chữ nghĩa thuộc về đây, để nó đổi
 * được mà không phải chạm vào endpoint nào, và để các state vẫn đếm được.
 */
const STATUS_LABEL: Record<string, string> = {
  "chưa-tới-giờ-mở": "Chưa tới giờ mở",
  "đang-mở": "Đang mở",
  "đang-làm": "Đang làm",
  "cần-chữa": "Cần làm lại",
  "đã-hoàn-thành": "Đã hoàn thành",
  "hết-hạn-chữa": "Hết hạn làm lại",
  "đã-đóng": "Đã đóng",
};

/** Những status nào đọc ra là việc đang chạy, chứ không phải một bản ghi đã chốt. */
const OPEN_STATES = new Set(["đang-mở", "đang-làm", "cần-chữa"]);

const ACTION_LABEL: Record<string, string> = {
  start: "Bắt đầu",
  continue: "Tiếp tục",
  result: "Xem kết quả",
  remediate: "Hỏi trợ lý và làm lại dạng bài sai",
};

/**
 * Màn 13 — những bài được giao cho chính học sinh này.
 *
 * Mọi kết luận trên màn này về tới đây là đã quyết rồi: hiện chip nào, và một
 * dòng cho những nút nào. Tự suy ra một trong hai từ ngày tháng là trao luật cho
 * cái đồng hồ của bất kỳ máy nào học sinh đang ngồi.
 *
 * Bốn cột là độ rộng cố định, không phải tỷ lệ, vì một danh sách được đọc dọc
 * theo cột, mà cột so le thì không đọc dọc được.
 */
export default function AssignmentList({ me }: { me: Me }) {
  const [rows, setRows] = useState<Assignment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .assignments()
      .then(setRows)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  async function act(row: Assignment, action: string) {
    try {
      if (action === "start" || action === "continue") {
        const attempt = await api.startAttempt(row.assignment_id);
        go(`/attempt/${attempt.attempt_id}`);
      } else if (action === "result") {
        go(`/attempt/${row.attempt_id}/result`);
      } else {
        go(`/attempt/${row.attempt_id}/tutor`);
      }
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  return (
    <>
      <TopBar me={me} />
      <main className="page">
        <h1 style={{ fontSize: "var(--type-heading)", marginBottom: 20 }}>Bài của tôi</h1>
        <ErrorStrip message={error} />

        {rows === null ? <p className="muted">Đang tải…</p> : null}
        {rows?.length === 0 ? <p className="muted">Chưa có bài nào được giao.</p> : null}

        {rows?.map((row) => (
          <div className="row" key={row.assignment_id}>
            <div className="col-name">
              <div className="title-14">{row.title}</div>
              <div className="muted" style={{ marginTop: 4 }}>
                {row.subject} · {row.question_count} câu · làm bài {row.phase1_minutes} phút
              </div>
            </div>
            <div className="col-dates muted">
              <div>Vào tới {moment(row.closes_at)}</div>
              <div style={{ marginTop: 4 }}>Chữa tới {moment(row.remediation_deadline)}</div>
            </div>
            <div className="col-status">
              <span
                className={`chip ${OPEN_STATES.has(row.status) ? "open" : row.status === "đã-hoàn-thành" ? "settled" : ""}`}
              >
                {row.wrong_count
                  ? `Cần làm lại ${row.wrong_count} câu`
                  : (STATUS_LABEL[row.status] ?? row.status)}
              </span>
            </div>
            <div className="col-action">
              {row.actions.map((action, index) => (
                <button
                  key={action}
                  type="button"
                  className={index === row.actions.length - 1 ? "btn-primary" : "btn-secondary"}
                  onClick={() => act(row, action)}
                >
                  {ACTION_LABEL[action] ?? action}
                </button>
              ))}
            </div>
          </div>
        ))}

        <p className="faint" style={{ marginTop: 20 }}>
          Bài đóng quá 30 ngày không hiện ở đây nữa.
        </p>
      </main>
    </>
  );
}
