import { useEffect, useState } from "react";

import { api, type Me, type OpenRound } from "../api";
import { go } from "../App";
import { Countdown, ErrorStrip, TopBar } from "../components";

/**
 * Screen 21 — answering the questions of one remediation round.
 *
 * The round is fetched from the panel that opened it rather than re-created,
 * because opening a round is what spends a round: a reload here must not cost
 * the student one of their three (ADR-17).
 *
 * The clock is the server's. When it reaches zero the round is stopped, not
 * extended -- and BE refuses a late answer whether or not this screen noticed
 * (ADR-15).
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
        if (panel.open_round_id !== roundId) {
          setError("Lượt này đã kết thúc.");
        }
      })
      .catch((cause: Error) => setError(cause.message));
  }, [attemptId, roundId]);

  // The round's questions arrive with the response that created it; a reload
  // of this screen reads them back from the session store rather than asking
  // for a new round.
  useEffect(() => {
    const cached = window.sessionStorage.getItem(`round:${roundId}`);
    if (cached) setRound(JSON.parse(cached) as OpenRound);
  }, [roundId]);

  if (round === null) {
    return (
      <>
        <TopBar me={me} />
        <main className="page">
          <ErrorStrip message={error ?? "Không đọc được lượt này. Quay lại phần chữa bài."} />
          <button className="btn-secondary" type="button" onClick={() => go(`/attempt/${attemptId}/tutor`)}>
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
      <main className="page" style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 40 }}>
        <section>
          <div className="muted">
            Làm lại dạng bài sai · {round.items.length} câu
          </div>
          <h1 style={{ fontSize: "var(--type-label)", margin: "2px 0 20px" }}>
            Câu {item.order} — Lượt làm lại thứ {round.index} / tối đa 3
          </h1>
          <h2 style={{ fontSize: "var(--type-heading)", marginTop: 0 }}>{item.stem}</h2>

          <ErrorStrip message={error} />

          {item.options.map((option) => (
            <button
              key={option.label}
              type="button"
              className={`option ${chosen[item.round_item_id] === option.label ? "chosen" : ""}`}
              onClick={() => choose(option.label)}
            >
              <span className="label">{option.label}</span>
              <span>{option.text}</span>
            </button>
          ))}
        </section>

        <aside>
          <div className="card" style={{ padding: 16, marginBottom: 16 }}>
            <div className="muted">Còn lại</div>
            <Countdown endsAt={round.ends_at} />
          </div>

          <div className="muted" style={{ marginBottom: 8 }}>
            CÂU CÒN PHẢI LÀM LẠI TRONG LƯỢT NÀY
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
            {round.items.map((other, index) => (
              <button
                key={other.round_item_id}
                type="button"
                className={index === current ? "btn-primary" : "btn-secondary"}
                style={{ width: 34, padding: "4px 0", textAlign: "center" }}
                onClick={() => setCurrent(index)}
              >
                {other.order}
              </button>
            ))}
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
