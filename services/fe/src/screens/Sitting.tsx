import { useEffect, useState } from "react";

import { api, type Attempt, type Me } from "../api";
import { go } from "../App";
import { Countdown, ErrorStrip, TopBar } from "../components";

/**
 * Screen 14 — sitting the paper, phase 1.
 *
 * The payload carries no answer key, so nothing on this screen could reveal a
 * correct option even by accident. Choices are saved one at a time rather than
 * gathered until submit: losing the network then costs one click.
 *
 * Submitting ends phase 1, not the attempt (ADR-14).
 */
export default function Sitting({ me, attemptId }: { me: Me; attemptId: string }) {
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [current, setCurrent] = useState(0);
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  if (error !== null && attempt === null) {
    return (
      <>
        <TopBar me={me} />
        <main className="page">
          <ErrorStrip message={error} />
        </main>
      </>
    );
  }
  if (attempt === null) {
    return (
      <>
        <TopBar me={me} />
        <main className="page">Đang tải…</main>
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
      <main className="page" style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 40 }}>
        <section>
          <div className="muted">{attempt.title}</div>
          <h1 style={{ fontSize: "var(--type-label)", margin: "2px 0 20px" }}>
            Câu {question.order} / {attempt.questions.length}
          </h1>
          <h2 style={{ fontSize: "var(--type-heading)", marginTop: 0 }}>{question.stem}</h2>

          <ErrorStrip message={error} />

          {question.options.map((option) => (
            <button
              key={option.option_id}
              type="button"
              className={`option ${chosen[question.question_id] === option.option_id ? "chosen" : ""}`}
              onClick={() => choose(option.option_id)}
            >
              <span className="label">{option.label}</span>
              <span>{option.text}</span>
            </button>
          ))}
        </section>

        <aside>
          <div className="card" style={{ padding: 16, marginBottom: 16 }}>
            <div className="muted">Còn lại</div>
            <Countdown endsAt={attempt.ends_at} />
          </div>

          <div className="muted" style={{ marginBottom: 8 }}>
            CÒN {unanswered} CÂU CHƯA TRẢ LỜI
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
            {attempt.questions.map((item, index) => {
              // Three states, because the banner above counts the unanswered
              // ones and a strip that cannot show which is a strip that makes
              // the student open all six to find them.
              const answered = Boolean(chosen[item.question_id]);
              const tone =
                index === current ? "btn-primary" : answered ? "chip-answered" : "btn-secondary";
              return (
                <button
                  key={item.question_id}
                  type="button"
                  className={tone}
                  style={{ width: 34, padding: "4px 0", textAlign: "center" }}
                  onClick={() => setCurrent(index)}
                >
                  {item.order}
                </button>
              );
            })}
          </div>

          <button
            className="btn-primary"
            type="button"
            style={{ width: "100%" }}
            disabled={busy}
            onClick={submit}
          >
            Nộp bài
          </button>
        </aside>
      </main>
    </>
  );
}
