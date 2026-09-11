import { useEffect, useState } from "react";

import { api, moment, type Assignment, type Me } from "../api";
import { go } from "../App";
import { ErrorStrip, TopBar } from "../components";

/**
 * Vietnamese wording for each status BE can return.
 *
 * BE sends a state, not a sentence: the wording belongs here so it can change
 * without touching an endpoint, and the states stay countable.
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

/** Which statuses read as live work rather than a settled record. */
const OPEN_STATES = new Set(["đang-mở", "đang-làm", "cần-chữa"]);

const ACTION_LABEL: Record<string, string> = {
  start: "Bắt đầu",
  continue: "Tiếp tục",
  result: "Xem kết quả",
  remediate: "Hỏi trợ lý và làm lại dạng bài sai",
};

/**
 * Screen 13 — the student's own assignments.
 *
 * Every verdict on this screen arrives decided: which chip to show, and which
 * buttons a row offers. Deriving either from the dates would put the clock of
 * whichever machine the student sits at in charge of the rules.
 *
 * The four columns are fixed widths, not proportions, because a list is read
 * down a column and ragged columns make that impossible.
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
