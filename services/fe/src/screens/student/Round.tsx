import { useEffect, useState } from "react";

import { api, type Me, type OpenRound } from "../../api";
import { go } from "../../App";
import { ErrorStrip, TimeCard, TopBar } from "../../components";
import MathText from "../../MathText";

/**
 * Màn 21 — trả lời các câu hỏi của một lượt làm lại.
 *
 * Cùng hình dạng với màn pha 1, và đó là cố ý: một học sinh vừa làm đề xong
 * không phải học thêm cách thứ hai để trả lời một câu hỏi. Khác nhau ở phần tiêu
 * đề, chỗ gọi tên câu gốc và cho biết đây là lượt thứ mấy, cùng cái mức trần đi
 * kèm theo đó (ADR-17).
 *
 * Lượt này được **đọc lại** chứ không mở lại, vì mở một lượt chính là tiêu một lượt:
 * reload không được phép làm học sinh mất một trong ba lượt của mình. Bản trong
 * `sessionStorage` vẽ ngay; bản đọc từ server (`GET /rounds/{id}`) là bản đúng, có cả lựa
 * chọn đã lưu -- tab mới hay máy khác chỉ có bản ấy (plan `backlog-tier-1`). Đồng hồ là đồng
 * hồ của server, và khi nó về không thì lượt bị dừng, không phải được gia hạn (ADR-15).
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
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    api
      .remediation(attemptId)
      .then((panel) => {
        if (panel.open_round_id !== roundId) setError("Lượt này đã kết thúc.");
      })
      .catch((cause: Error) => setError(cause.message));
  }, [attemptId, roundId]);

  useEffect(() => {
    let current = true;
    const cached = window.sessionStorage.getItem(`round:${roundId}`);
    if (cached) setRound(JSON.parse(cached) as OpenRound);
    api
      .round(roundId)
      .then((stored) => {
        if (!current) return;
        setRound(stored);
        // Lựa chọn đã lưu ở lần trước (tab khác, trước F5) sáng lại. Lựa chọn vừa bấm ở tab này
        // trong lúc chờ lời đáp thắng (review ảnh pha 2): ghi đè thì nó biến mất khỏi màn dù đã lưu.
        const saved = Object.fromEntries(
          stored.items
            .filter((one) => one.chosen_label !== null)
            .map((one) => [one.round_item_id, one.chosen_label as string]),
        );
        setChosen((picked) => ({ ...saved, ...picked }));
      })
      .catch((cause: Error) => {
        if (current && !cached) setError(cause.message);
      });
    return () => {
      current = false;
    };
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
  const unanswered = round.items.filter((one) => !chosen[one.round_item_id]).length;
  // Độ dài lượt, không phải thời gian còn lại -- còn lại là việc của `TimeCard` ngay bên phải.
  // Bản cũ trong `sessionStorage` có thể chưa mang `started_at`: khi ấy bỏ con số còn hơn đoán.
  const minutes = round.started_at
    ? Math.round((new Date(round.ends_at).getTime() - new Date(round.started_at).getTime()) / 60000)
    : null;

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
      // Dải báo lỗi nằm sau hộp, nên để hộp mở là che mất lời giải thích (như `Sitting`).
      setConfirming(false);
    }
  }

  return (
    <>
      <TopBar me={me} />
      <main className="page two-column">
        <section>
          <div className="muted">
            Làm lại dạng bài sai · {round.items.length} câu
            {minutes !== null ? ` · ${minutes} phút` : ""}
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
            <MathText>{item.stem}</MathText>
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
              <span>
                <MathText>{option.text}</MathText>
              </span>
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

      {/* Nộp lượt là một cửa một chiều như nộp bài pha 1 (artboard 22b, cùng khuôn `Sitting`):
          lượt đã nộp không sửa lại được, và mỗi câu chỉ có ba lượt (ADR-17). */}
      {confirming ? (
        <div className="scrim">
          <div className="dialog gate">
            <h2 style={{ fontSize: "var(--type-heading)" }}>Nộp lượt này?</h2>
            <p style={{ margin: "16px 0", lineHeight: 1.25, color: "var(--ink-muted)" }}>
              Nộp là kết thúc lượt làm lại. Bạn không sửa được câu nào trong lượt này nữa.
            </p>

            <div className="panel-card plain" style={{ padding: "12px 14px" }}>
              <div className="stat">
                <span className="key">Đã trả lời</span>
                <span className="value">
                  {round.items.length - unanswered} trên {round.items.length} câu
                </span>
              </div>
              <div className="stat">
                <span className="key">Chưa trả lời</span>
                <span className="value">
                  {unanswered === 0 ? "không còn câu nào" : `${unanswered} câu`}
                </span>
              </div>
              <div className="stat">
                <span className="key">Sau khi nộp</span>
                <span className="value">câu làm đúng được 0,5 điểm</span>
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
