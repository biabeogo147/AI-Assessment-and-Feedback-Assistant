import { useEffect, useState } from "react";

import { api, type Me, type OpenRound } from "../api";
import { go } from "../App";
import { ErrorStrip, TimeCard, TopBar } from "../components";

/**
 * Màn 21 — trả lời các câu hỏi của một lượt làm lại.
 *
 * Cùng hình dạng với màn pha 1, và đó là cố ý: một học sinh vừa làm đề xong
 * không phải học thêm cách thứ hai để trả lời một câu hỏi. Khác nhau ở phần tiêu
 * đề, chỗ gọi tên câu gốc và cho biết đây là lượt thứ mấy, cùng cái mức trần đi
 * kèm theo đó (ADR-17).
 *
 * Lượt này được đọc lại từ nơi nó đã được tạo ra chứ không request lại, vì mở một
 * lượt chính là tiêu một lượt: reload không được phép làm học sinh mất một trong
 * ba lượt của mình. Đồng hồ là đồng hồ của server, và khi nó về không thì lượt bị
 * dừng, không phải được gia hạn (ADR-15).
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
          <div className="muted">
            Làm lại dạng bài sai · {round.items.length} câu ·{" "}
            {Math.max(
              1,
              Math.round((new Date(round.ends_at).getTime() - Date.now()) / 60000),
            )}{" "}
            phút
          </div>
          <h1 style={{ fontSize: "var(--type-heading)", margin: "4px 0 20px" }}>
            Câu {item.origin_order} — Lượt làm lại thứ {round.index} / tối đa 3
          </h1>
          <p
            style={{
              fontSize: "var(--type-display)",
              lineHeight: 1.25,
              margin: "0 0 20px",
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
