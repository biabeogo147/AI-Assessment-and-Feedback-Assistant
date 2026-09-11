import { useEffect, useState, type ReactNode } from "react";

import { api, moment, type AttemptResult, type Me } from "../api";
import { go } from "../App";
import { ErrorStrip, ScoreMark, TopBar } from "../components";

/**
 * Why a mark stands where it does, in words, chosen by the client.
 *
 * BE sends an enum. The two sentences for a zero differ by whether phase 2 is
 * still open, and promising "you can still raise this" after the deadline
 * would be a lie -- so the choice is made here, where the deadline is already
 * on screen (ADR-16).
 *
 * @param reason - The enum BE returned.
 * @param stillOpen - Whether the remediation deadline is in the future.
 * @returns The hover sentence, or undefined when a mark needs no explanation.
 */
function markTip(reason: string, stillOpen: boolean): ReactNode {
  if (reason === "chữa-được") {
    return "Làm đúng câu mới có dạng tương tự câu sai ở bài kiểm tra.";
  }
  if (reason === "chưa-chữa" && stillOpen) {
    // The action is set apart here for the same reason it is in the banner:
    // it names the one thing the student can do about this mark.
    return (
      <>
        Làm sai, có thể nâng điểm bằng cách{" "}
        <strong style={{ fontWeight: 600 }}>Hỏi trợ lý và làm lại dạng bài sai</strong>.
      </>
    );
  }
  if (reason === "hết-vòng") {
    return "Đã dùng hết ba lượt làm lại cho câu này.";
  }
  return undefined;
}

/**
 * Screens 15 and 22 — the score sheet, in its two shapes.
 *
 * One component, two shapes, chosen by the state BE returns rather than by
 * counting rows here. While phase 2 is open the sheet says the score is a
 * floor and offers the way in; once it is closed it offers a way to read the
 * conversation back instead.
 *
 * Each fixed question prints the question of every round it took, because a
 * retry is a different question (ADR-17) and 0.5 with no visible reason is a
 * claim a student cannot check.
 */
export default function Result({ me, attemptId }: { me: Me; attemptId: string }) {
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .result(attemptId)
      .then(setResult)
      .catch((cause: Error) => setError(cause.message));
  }, [attemptId]);

  if (result === null) {
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

  const stillOpen = result.state === "cần-chữa";
  // A question is still open while BE says its mark is "chưa-chữa": having
  // spent a round does not close it, and counting rounds here got the number
  // wrong the moment a student used one.
  const openCount = result.items.filter((item) => item.mark_reason === "chưa-chữa").length;

  return (
    <>
      <TopBar me={me} />
      <main className="page">
        <div style={{ display: "flex", alignItems: "flex-start", gap: 24, marginBottom: 20 }}>
          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: "var(--type-heading)" }}>{result.title}</h1>
            <div className="muted" style={{ marginTop: 4 }}>
              {stillOpen
                ? `Đã nộp lúc ${result.submitted_at ? moment(result.submitted_at) : "—"} · còn ${openCount} câu cần chữa`
                : `Bài đã kết thúc · ${result.total_score.toFixed(1).replace(".", ",")} trên ${result.question_count} câu`}
            </div>
          </div>
          <button
            className="btn-cta"
            type="button"
            onClick={() => go(`/attempt/${attemptId}/tutor`)}
          >
            {stillOpen ? "Hỏi trợ lý và làm lại dạng bài sai" : "Xem lại phần chữa các câu sai"}
          </button>
        </div>

        {stillOpen ? (
          <div className="banner" style={{ marginBottom: 20 }}>
            Bạn có thể nâng điểm các câu sai bằng cách{" "}
            <strong style={{ color: "var(--ink)" }}>Hỏi trợ lý và làm lại dạng bài sai</strong> tới
            hết {moment(result.remediation_deadline)}.
          </div>
        ) : null}

        <ErrorStrip message={error} />

        {result.items.map((item) => (
          <div className="row result" key={item.question_id}>
            <div className="col-num">
              <span className="muted" style={{ fontWeight: 600 }}>
                Câu {item.order}
              </span>
            </div>
            <div className="col-body">
              <div>{item.stem}</div>
              {item.rounds.length > 0 ? (
                <div
                  style={{
                    marginTop: 8,
                    paddingLeft: 12,
                    borderLeft: "2px solid var(--line)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 5,
                  }}
                >
                  <div className="faint" style={{ fontWeight: 600 }}>
                    Lượt làm lại
                  </div>
                  {item.rounds.map((round) => (
                    <div key={round.index} style={{ display: "flex", gap: 10 }}>
                      <span className="faint" style={{ width: 10 }}>
                        {round.index}
                      </span>
                      <span
                        className="muted"
                        style={{
                          width: 36,
                          fontWeight: 600,
                          color:
                            round.outcome === "đúng"
                              ? "var(--answer-correct)"
                              : "var(--answer-incorrect)",
                        }}
                      >
                        {round.outcome}
                      </span>
                      <span className="muted" style={{ color: "var(--ink)" }}>
                        {round.stem}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="col-mark">
              <ScoreMark mark={item.mark} tip={markTip(item.mark_reason, stillOpen)} />
            </div>
          </div>
        ))}
      </main>
    </>
  );
}
