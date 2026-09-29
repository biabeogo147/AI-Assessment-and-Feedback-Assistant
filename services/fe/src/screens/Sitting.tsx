import { useEffect, useState } from "react";

import { api, type Attempt, type Me } from "../api";
import { go } from "../App";
import { ErrorStrip, TimeCard, TopBar } from "../components";

/**
 * Screen 14 — sitting the paper, phase 1.
 *
 * The payload carries no answer key, so nothing on this screen could reveal a
 * correct option even by accident. Choices are saved one at a time rather than
 * gathered until submit: losing the network then costs one click.
 *
 * The question is set at 28px because it is the thing being read; everything
 * else on the screen is smaller than it. Submitting ends phase 1, not the
 * attempt (ADR-14).
 */
export default function Sitting({ me, attemptId }: { me: Me; attemptId: string }) {
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [current, setCurrent] = useState(0);
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    api
      .attempt(attemptId)
      .then((loaded) => {
        setAttempt(loaded);
        const saved: Record<string, string> = {};
        for (const question of loaded.questions) {
          if (question.chosen_option_id) saved[question.question_id] = question.chosen_option_id;
        }
        setChosen(saved);
      })
      .catch((cause: Error) => setError(cause.message));
  }, [attemptId]);

  if (attempt === null) {
    return (
      <>
        <TopBar me={me} />
        <main className="page">
          <ErrorStrip message={error} />
          {error === null ? <p className="muted">Đang tải…</p> : null}
        </main>
      </>
    );
  }

  const question = attempt.questions[current];
  const unanswered = attempt.questions.filter((q) => !chosen[q.question_id]).length;

  async function choose(optionId: string) {
    if (attempt === null) return;
    setChosen((previous) => ({ ...previous, [question.question_id]: optionId }));
    try {
      await api.saveAnswer(attempt.attempt_id, question.question_id, optionId);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function submit() {
    if (attempt === null) return;
    setBusy(true);
    try {
      await api.submit(attempt.attempt_id);
      go(`/attempt/${attempt.attempt_id}/result`);
    } catch (cause) {
      setError((cause as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
      <TopBar me={me} />
      <main className="page two-column">
        <section>
          <div className="muted">{attempt.title}</div>
          <h1 style={{ fontSize: "var(--type-heading)", margin: "4px 0 20px" }}>
            Câu {question.order} / {attempt.questions.length}
          </h1>
          <p
            style={{
              fontSize: "var(--type-display)",
              lineHeight: 1.25,
              margin: "0 0 20px",
              fontWeight: 400,
            }}
          >
            {question.stem}
          </p>

          <ErrorStrip message={error} />

          {question.options.map((option) => (
            <button
              key={option.option_id}
              type="button"
              className={`option ${chosen[question.question_id] === option.option_id ? "chosen" : ""}`}
              onClick={() => choose(option.option_id)}
            >
              <span className="radio" aria-hidden />
              <span className="label">{option.label}</span>
              <span>{option.text}</span>
            </button>
          ))}
        </section>

        <aside style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <TimeCard endsAt={attempt.ends_at} />

          <div>
            <div className="label-caps">CÒN {unanswered} CÂU CHƯA TRẢ LỜI</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
              {attempt.questions.map((item, index) => {
                // Three states, because the line above counts the unanswered
                // ones and a strip that cannot show which is a strip that
                // makes the student open every question to find them.
                const answered = Boolean(chosen[item.question_id]);
                const tone = index === current ? "current" : answered ? "answered" : "";
                return (
                  <button
                    key={item.question_id}
                    type="button"
                    className={`nav-chip ${tone}`}
                    onClick={() => setCurrent(index)}
                  >
                    {item.order}
                  </button>
                );
              })}
            </div>
          </div>

          <button
            className="btn-commit"
            type="button"
            disabled={busy}
            onClick={() => setConfirming(true)}
          >
            Nộp bài
          </button>
        </aside>
      </main>

      {confirming ? (
        <div className="scrim">
          <div className="dialog gate">
            <h2 style={{ fontSize: "var(--type-heading)" }}>Nộp bài?</h2>
            <p style={{ margin: "16px 0", lineHeight: 1.25, color: "var(--ink-muted)" }}>
              Nộp là kết thúc phần làm bài. Bạn không sửa được câu nào nữa.
            </p>

            <div className="panel-card plain" style={{ padding: "12px 14px" }}>
              <div className="stat">
                <span className="key">Đã trả lời</span>
                <span className="value">
                  {attempt.questions.length - unanswered} trên {attempt.questions.length} câu
                </span>
              </div>
              {/* Read back, not written down: the same count the navigation
                  strip shows. A confirmation that states a number the screen
                  does not is a confirmation nobody can check. */}
              <div className="stat">
                <span className="key">Chưa trả lời</span>
                <span className="value">
                  {unanswered === 0 ? "không còn câu nào" : `${unanswered} câu`}
                </span>
              </div>
              <div className="stat">
                <span className="key">Sau khi nộp</span>
                <span className="value">điểm này là điểm sàn, còn nâng được</span>
              </div>
            </div>

            {unanswered > 0 ? (
              <div className="warn-strip">
                Còn <strong>{unanswered} câu</strong> chưa trả lời. Câu bỏ trống tính là sai.
              </div>
            ) : null}

            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 16 }}>
              <button
                className="btn-dialog quiet"
                type="button"
                onClick={() => setConfirming(false)}
              >
                Quay lại làm tiếp
              </button>
              <button className="btn-dialog" type="button" disabled={busy} onClick={submit}>
                Nộp bài
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
