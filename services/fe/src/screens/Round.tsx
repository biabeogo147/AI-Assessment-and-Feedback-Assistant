import { useEffect, useState } from "react";

import { api, type Me, type OpenRound } from "../api";
import { go } from "../App";
import { ErrorStrip, TimeCard, TopBar } from "../components";

/**
 * Screen 21 — answering the questions of one remediation round.
 *
 * Same shape as the phase 1 screen on purpose: a student who just sat the
 * paper should not have to learn a second way of answering a question. What
 * differs is the heading, which names the original question and which round
 * this is, and the ceiling that comes with it (ADR-17).
 *
 * The round is read back from where it was created rather than re-requested,
 * because opening a round is what spends one: a reload must not cost the
 * student one of their three. The clock is the server's, and when it reaches
 * zero the round is stopped, not extended (ADR-15).
 */
export default function Round({
  me,
  attemptId,
  roundId,
}: {
  me: Me;
  attemptId: string;
  roundId: string;
}) {
  const [round, setRound] = useState<OpenRound | null>(null);
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [current, setCurrent] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .remediation(attemptId)
      .then((panel) => {
        if (panel.open_round_id !== roundId) setError("Lượt này đã kết thúc.");
      })
      .catch((cause: Error) => setError(cause.message));
  }, [attemptId, roundId]);

  useEffect(() => {
    const cached = window.sessionStorage.getItem(`round:${roundId}`);
    if (cached) setRound(JSON.parse(cached) as OpenRound);
  }, [roundId]);

  if (round === null) {
    return (
      <>
        <TopBar me={me} />
        <main className="page">
          <ErrorStrip message={error ?? "Không đọc được lượt này."} />
          <button
            className="btn-secondary"
            type="button"
            style={{ marginTop: 16 }}
            onClick={() => go(`/attempt/${attemptId}/tutor`)}
          >
            Về phần chữa bài
          </button>
        </main>
      </>
    );
  }

  const item = round.items[current];

  async function choose(label: string) {
    if (round === null) return;
    setChosen((previous) => ({ ...previous, [item.round_item_id]: label }));
    try {
      await api.saveRoundAnswer(round.round_id, item.round_item_id, label);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function submit() {
    if (round === null) return;
    setBusy(true);
    try {
      await api.submitRound(round.round_id);
      window.sessionStorage.removeItem(`round:${round.round_id}`);
      go(`/attempt/${attemptId}/result`);
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
          <div className="muted">Làm lại dạng bài sai · {round.items.length} câu</div>
          <h1 style={{ fontSize: "var(--type-heading)", margin: "4px 0 20px" }}>
            Câu {item.origin_order} — Lượt làm lại thứ {round.index} / tối đa 3
          </h1>
          <p
            style={{
              fontSize: "var(--type-display)",
              lineHeight: 1.25,
              margin: "0 0 24px",
              fontWeight: 400,
            }}
          >
            {item.stem}
          </p>

          <ErrorStrip message={error} />

          {item.options.map((option) => (
            <button
              key={option.label}
              type="button"
              className={`option ${chosen[item.round_item_id] === option.label ? "chosen" : ""}`}
              onClick={() => choose(option.label)}
            >
              <span className="radio" aria-hidden />
              <span className="label">{option.label}</span>
              <span>{option.text}</span>
            </button>
          ))}
        </section>

        <aside style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <TimeCard endsAt={round.ends_at} />

          <div>
            <div className="label-caps">CÂU CÒN PHẢI LÀM LẠI TRONG LƯỢT NÀY</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
              {round.items.map((other, index) => {
                const answered = Boolean(chosen[other.round_item_id]);
                const tone = index === current ? "current" : answered ? "answered" : "";
                return (
                  <button
                    key={other.round_item_id}
                    type="button"
                    className={`nav-chip ${tone}`}
                    onClick={() => setCurrent(index)}
                  >
                    {other.origin_order}
                  </button>
                );
              })}
            </div>
          </div>

          <button className="btn-commit" type="button" disabled={busy} onClick={submit}>
            Nộp bài
          </button>
        </aside>
      </main>
    </>
  );
}
