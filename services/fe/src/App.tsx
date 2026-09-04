import { useState } from "react";

import {
  REVIEW_REASON_LABELS,
  submitAnswer,
  waitForResult,
  type GradedResult,
} from "./api";

type Phase = "idle" | "grading" | "done" | "error";

const OPTIONS = [
  { id: "opt-a", label: "A. 5/6" },
  { id: "opt-b", label: "B. 2/5" },
  { id: "opt-c", label: "C. 3/5" },
];

/**
 * Demo screen for the end-to-end grading path.
 *
 * Exists to prove the boundary works: this submission crosses FE, BE, Redis and
 * AGENT, and the review decision comes back attached. It is not the real student
 * experience.
 */
export default function App() {
  const [selectedOptionId, setSelectedOptionId] = useState(OPTIONS[0].id);
  const [explanation, setExplanation] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<GradedResult | null>(null);
  const [error, setError] = useState<string>("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPhase("grading");
    setResult(null);
    setError("");

    try {
      const jobId = await submitAnswer({ selectedOptionId, explanation });
      setResult(await waitForResult(jobId));
      setPhase("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setPhase("error");
    }
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 640, margin: "3rem auto", padding: "0 1rem" }}>
      <h1 style={{ fontSize: "1.35rem" }}>Nộp bài thử</h1>
      <p style={{ color: "#555" }}>
        Câu hỏi: <strong>1/2 + 1/3 bằng bao nhiêu?</strong>
      </p>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <fieldset style={{ border: "1px solid #ccc", padding: "0.75rem" }}>
          <legend>Chọn đáp án</legend>
          {OPTIONS.map((option) => (
            <label key={option.id} style={{ display: "block", padding: "0.15rem 0" }}>
              <input
                type="radio"
                name="option"
                value={option.id}
                checked={selectedOptionId === option.id}
                onChange={() => setSelectedOptionId(option.id)}
              />{" "}
              {option.label}
            </label>
          ))}
        </fieldset>

        <label>
          Giải thích cách làm
          <textarea
            value={explanation}
            onChange={(event) => setExplanation(event.target.value)}
            rows={3}
            style={{ display: "block", width: "100%", marginTop: "0.25rem" }}
            placeholder="Để trống để xem trường hợp độ tin cậy thấp"
          />
        </label>

        <button type="submit" disabled={phase === "grading"} style={{ padding: "0.5rem 1rem" }}>
          {phase === "grading" ? "Đang chấm..." : "Nộp bài"}
        </button>
      </form>

      {phase === "error" && (
        <p role="alert" style={{ color: "#a11" }}>
          {error}
        </p>
      )}

      {result && (
        <section style={{ marginTop: "1.5rem", borderTop: "1px solid #ddd", paddingTop: "1rem" }}>
          <h2 style={{ fontSize: "1.05rem" }}>Kết quả</h2>
          <dl>
            <dt>Điểm</dt>
            <dd>{result.score.toFixed(1)}</dd>
            <dt>Độ tin cậy</dt>
            <dd>{result.confidence.toFixed(2)}</dd>
            <dt>Nhận xét</dt>
            <dd>{result.feedback_text}</dd>
          </dl>

          {result.needs_teacher_review ? (
            <p style={{ background: "#fff3e0", border: "1px solid #e0a75e", padding: "0.6rem" }}>
              Cần giáo viên xem lại
              {result.review_reason ? ` — ${REVIEW_REASON_LABELS[result.review_reason]}` : ""}
            </p>
          ) : (
            <p style={{ color: "#2a6" }}>Không cần giáo viên xem lại.</p>
          )}
        </section>
      )}
    </main>
  );
}
