import { useCallback, useEffect, useState } from "react";

import {
  api,
  moment,
  streamReply,
  type ChatHistory,
  type Me,
  type Remediation,
  type Solution,
} from "../api";
import { go } from "../App";
import { BackToList, ErrorStrip, TopBar } from "../components";

/**
 * Screens 17, 18, 19, 20 and 24 — asking the assistant, and the gate into a round.
 *
 * One component, because they are one screen in five states: fresh, with a
 * solution open, with the round gate open in its two forms, and read-only
 * after the attempt has ended. Splitting them would duplicate the panel four
 * times and let the four copies drift.
 *
 * The panel lists **every** wrong question, not the one being discussed: phase
 * 2 receives an assessment, not a question (ADR-14, ADR-17). It shows what was
 * picked and what was right, and nothing else -- the mistake's name and the
 * worked solutions live one click away, in the dialog, so the list stays a
 * list.
 */
/**
 * One turn of the conversation.
 *
 * The assistant gets the mascot; the student gets an empty column of the same
 * width, so both speakers' words start at the same place down the page and the
 * eye can follow one thread instead of two.
 *
 * @param role - "student" or "assistant".
 * @param text - What was said.
 */
function Turn({ role, text }: { role: string; text: string }) {
  const student = role === "student";
  return (
    <div className="turn">
      {student ? <span style={{ width: 40, flex: "none" }} /> : <span className="avatar">🐝</span>}
      <div className="said">
        <span className="faint">{student ? "Bạn" : "Kriky"}</span>
        <div className={`bubble ${student ? "student" : ""}`}>{text}</div>
      </div>
    </div>
  );
}


export default function Tutor({ me, attemptId }: { me: Me; attemptId: string }) {
  const [panel, setPanel] = useState<Remediation | null>(null);
  const [history, setHistory] = useState<ChatHistory | null>(null);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState("");
  const [solution, setSolution] = useState<Solution | null>(null);
  const [gateOpen, setGateOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [nextPanel, nextHistory] = await Promise.all([
        api.remediation(attemptId),
        api.chat(attemptId),
      ]);
      setPanel(nextPanel);
      setHistory(nextHistory);
      return nextHistory;
    } catch (cause) {
      setError((cause as Error).message);
      return null;
    }
  }, [attemptId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  /**
   * Ask for the next assistant turn and let it type itself out.
   *
   * The reply is already stored server side before the first chunk arrives, so
   * the reload at the end is what the screen trusts; the streamed text is only
   * what it showed while waiting.
   */
  const pull = useCallback(async () => {
    setStreaming("");
    setBusy(true);
    try {
      await streamReply(attemptId, (chunk) => setStreaming((text) => text + chunk));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setStreaming("");
      setBusy(false);
      await reload();
    }
  }, [attemptId, reload]);

  // The assistant speaks first and then waits: one greeting, no lecture.
  useEffect(() => {
    if (history !== null && history.messages.length === 0 && !history.locked && !busy) {
      void pull();
    }
  }, [history, pull, busy]);

  async function send() {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    try {
      await api.postChat(attemptId, text);
      await reload();
      await pull();
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function openRound() {
    setBusy(true);
    try {
      const round = await api.startRound(attemptId);
      // The round's questions exist only in this response: asking again would
      // open a second round and spend another of the three (ADR-17).
      window.sessionStorage.setItem(`round:${round.round_id}`, JSON.stringify(round));
      go(`/round/${attemptId}/${round.round_id}`);
    } catch (cause) {
      setError((cause as Error).message);
      setBusy(false);
    }
  }

  if (panel === null || history === null) {
    return (
      <>
        <TopBar me={me} />
        <main className="page">
          <ErrorStrip message={error} />
          {error === null ? "Đang tải…" : null}
        </main>
      </>
    );
  }

  const locked = history.locked;

  return (
    <>
      <TopBar me={me} />
      <div className="split">
        <section className="chat">
          <BackToList />
          <div className="banner">
            {locked
              ? "Bài đã kết thúc. Em vẫn đọc lại được phần chữa và báo cáo chỗ khó hiểu, nhưng không nhắn thêm được nữa."
              : "Phần này không tính giờ. Hỏi đến khi hiểu rồi hãy bấm làm bài mới."}
          </div>

          <ErrorStrip message={error} />

          {history.messages.map((message) => (
            <Turn key={message.message_id} role={message.role} text={message.text} />
          ))}

          {streaming ? <Turn role="assistant" text={streaming} /> : null}

          <div style={{ flex: 1 }} />

          <div className={`composer ${locked ? "locked" : ""}`}>
            <input
              value={draft}
              disabled={locked || busy}
              placeholder={
                locked
                  ? "Bài đã kết thúc — không nhắn thêm được."
                  : "Hỏi Kriky về bất kỳ câu nào em làm sai…"
              }
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void send();
              }}
            />
            {locked ? null : (
              <button className="btn-quiet" type="button" onClick={() => void send()}>
                Gửi
              </button>
            )}
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
            <button
              className="btn-quiet"
              type="button"
              onClick={() =>
                api
                  .report(attemptId, null)
                  .then(() => setError("Đã gửi báo cáo tới giáo viên."))
                  .catch((cause: Error) => setError(cause.message))
              }
            >
              ⚑ Báo cáo Trợ lý giải thích khó hiểu
            </button>
            {locked ? null : (
              <button
                className="btn-commit"
                type="button"
                style={{ width: "auto" }}
                disabled={!panel.can_start_round || busy}
                onClick={() => setGateOpen(true)}
              >
                Làm bài mới · {panel.remaining.length} câu · {panel.round_budget_minutes} phút
              </button>
            )}
          </div>
        </section>

        <aside className="panel">
          <div className="label-caps">CÁC CÂU EM LÀM SAI</div>

          {panel.remaining.map((item) => (
            <div key={item.question_id} className="panel-card">
              <div className="title-14">Câu {item.order}</div>
              <div style={{ fontSize: "var(--type-label)", lineHeight: 1.35 }}>{item.stem}</div>
              {item.chosen ? (
                <div
                  className="muted"
                  style={{ color: "var(--answer-incorrect)", fontWeight: 600 }}
                >
                  Em đã chọn {item.chosen.label}. {item.chosen.text}
                </div>
              ) : (
                <div className="muted">Em chưa chọn phương án nào.</div>
              )}
              <div className="muted" style={{ color: "var(--answer-correct)", fontWeight: 600 }}>
                Đáp án đúng {item.correct.label}. {item.correct.text}
              </div>
              <button
                className="btn-quiet"
                type="button"
                style={{ alignSelf: "flex-start" }}
                onClick={() =>
                  api
                    .solution(item.question_id)
                    .then(setSolution)
                    .catch((cause: Error) => setError(cause.message))
                }
              >
                Xem lời giải đầy đủ ›
              </button>
            </div>
          ))}

          {panel.remaining.length === 0 ? (
            <div className="muted">Không còn câu nào phải làm lại.</div>
          ) : null}

          <div className="panel-card" style={{ padding: "12px 14px" }}>
            <div className="stat">
              <span className="key">Còn phải làm lại</span>
              <span className="value">{panel.remaining.length} câu</span>
            </div>
            <div className="stat">
              <span className="key">Hạn làm lại</span>
              <span className="value">{moment(panel.deadline)}</span>
            </div>
          </div>
        </aside>
      </div>

      {solution !== null ? (
        <div className="scrim" onClick={() => setSolution(null)}>
          <div className="dialog" onClick={(event) => event.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "baseline" }}>
              <h2 style={{ flex: 1, fontSize: "var(--type-heading)", margin: 0 }}>Lời giải</h2>
              <button className="btn-quiet" type="button" onClick={() => setSolution(null)}>
                Đóng
              </button>
            </div>
            <p>{solution.stem}</p>

            <div className="panel-card" style={{ gap: 10, marginBottom: 16 }}>
              {solution.methods.map((method) => (
                <div key={method.title}>
                  <div className="title-14">{method.title}</div>
                  <div className="muted" style={{ marginTop: 2, lineHeight: 1.4 }}>
                    {method.body}
                  </div>
                </div>
              ))}
            </div>

            <div className="faint" style={{ fontWeight: 600, marginBottom: 6 }}>
              ĐỐI CHIẾU TỪNG PHƯƠNG ÁN
            </div>
            {solution.options.map((option) => (
              <div key={option.label} style={{ display: "flex", gap: 12, marginBottom: 4 }}>
                <span
                  style={{
                    width: 120,
                    fontWeight: 600,
                    fontSize: "var(--type-caption)",
                    color: option.is_correct
                      ? "var(--answer-correct)"
                      : "var(--answer-incorrect)",
                  }}
                >
                  {option.label}. {option.text}
                </span>
                <span className="muted">
                  {option.is_correct ? "✓ đúng" : option.error_label}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {gateOpen ? (
        <div className="scrim">
          <div className="dialog gate">
            <h2 style={{ fontSize: "var(--type-heading)" }}>Bắt đầu lượt làm lại?</h2>
            <p className="muted" style={{ margin: "8px 0 16px", lineHeight: 1.4 }}>
              Bấm là đồng hồ chạy ngay. Đóng trình duyệt cũng không dừng nó.
            </p>

            <div className="panel-card" style={{ padding: "12px 14px" }}>
              <div className="stat">
                <span className="key">Lượt này</span>
                <span className="value">{panel.remaining.length} câu</span>
              </div>
              <div className="stat">
                <span className="key">Thời gian</span>
                <span className="value">
                  {panel.minutes_per_question} phút mỗi câu — {panel.round_budget_minutes} phút
                </span>
              </div>
              <div className="stat">
                <span className="key">Hạn làm lại</span>
                <span className="value">{moment(panel.deadline)}</span>
              </div>
            </div>

            {panel.warn_cut ? (
              <div className="banner" style={{ marginTop: 12 }}>
                Lượt này {panel.round_budget_minutes} phút mà hạn làm lại đã gần, nên có thể bị{" "}
                <strong>DỪNG</strong> giữa chừng.
              </div>
            ) : null}

            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 16 }}>
              <button
                className="btn-dialog quiet"
                type="button"
                onClick={() => setGateOpen(false)}
              >
                Để sau
              </button>
              <button
                className="btn-dialog"
                type="button"
                disabled={busy}
                onClick={() => void openRound()}
              >
                Làm bài mới
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
