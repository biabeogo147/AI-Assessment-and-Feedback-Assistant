import { useEffect, useState, type ReactNode } from "react";

import { api, moment, type AttemptResult, type Me } from "../api";
import { go } from "../App";
import { ErrorStrip, ScoreMark, TopBar } from "../components";

/**
 * Vì sao một điểm đứng ở chỗ nó đang đứng, bằng lời, do client chọn.
 *
 * BE gửi một giá trị enum. Hai câu dành cho điểm 0 khác nhau ở chỗ pha 2 còn mở
 * hay không, và hứa "em vẫn nâng được điểm này" sau khi đã hết hạn là nói sai —
 * nên việc chọn câu nào làm ở đây, nơi mà cái hạn đã có sẵn trên màn hình
 * (ADR-16).
 *
 * @param reason - Giá trị enum BE trả về.
 * @param stillOpen - Hạn làm lại có còn ở phía trước hay không.
 * @returns Câu hiện khi hover, hoặc undefined khi một điểm không cần giải thích.
 */
function markTip(reason: string, stillOpen: boolean): ReactNode {
  if (reason === "chữa-được") {
    return "Làm đúng câu mới có dạng tương tự câu sai ở bài kiểm tra.";
  }
  if (reason === "chưa-chữa" && stillOpen) {
    // Phần hành động được tách riêng ở đây vì đúng cái lý do nó được tách
    // riêng trong banner: nó gọi tên đúng một việc học sinh làm được với điểm
    // này.
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
 * Màn 15 và 22 — bảng điểm, ở hai dạng của nó.
 *
 * Một component, hai dạng, chọn theo state BE trả về chứ không theo việc đếm
 * dòng ở đây. Khi pha 2 còn mở, bảng nói rằng điểm này là điểm sàn và mở đường
 * vào; khi pha 2 đã đóng, nó mở đường đọc lại cuộc trò chuyện.
 *
 * Mỗi câu đã chữa xong đều in ra đề của từng lượt nó đã đi qua, vì một lượt làm
 * lại là một câu hỏi khác (ADR-17), và 0,5 mà không thấy lý do là một lời khẳng
 * định học sinh không kiểm được.
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
  // Một câu còn mở chừng nào BE còn nói điểm của nó là "chưa-chữa": đã dùng một
  // lượt không có nghĩa là câu đó đóng, và việc tự đếm lượt ở đây làm sai con số
  // ngay từ lúc một học sinh dùng hết một lượt.
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
