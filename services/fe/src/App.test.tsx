/**
 * FE behaviour around the grading round trip.
 *
 * `fetch` is stubbed so these tests describe how the UI reacts to BE's
 * responses, without needing BE, Redis or AGENT to be running.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { REVIEW_REASON_LABELS, waitForResult } from "./api";

function stubFetch(result: unknown) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/submissions")) {
      return new Response(JSON.stringify({ job_id: "job-1", submission_id: "sub-1" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({ job_id: "job-1", status: "complete", result }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("review reason labels", () => {
  it("covers every reason BE can return", () => {
    expect(Object.keys(REVIEW_REASON_LABELS).sort()).toEqual([
      "anomaly",
      "answer_explanation_conflict",
      "insufficient_evidence",
      "low_confidence",
    ]);
  });
});

describe("waitForResult", () => {
  it("keeps polling until a result appears", async () => {
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        calls += 1;
        const body =
          calls < 3
            ? { job_id: "job-1", status: "in_progress", result: null }
            : { job_id: "job-1", status: "complete", result: { submission_id: "sub-1" } };
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );

    const result = await waitForResult("job-1", async () => {});
    expect(result.submission_id).toBe("sub-1");
    expect(calls).toBe(3);
  });
});

describe("App", () => {
  it("shows the review banner with its reason when BE flags a submission", async () => {
    stubFetch({
      submission_id: "sub-1",
      score: 0,
      confidence: 0.55,
      misconception_code: null,
      feedback_text: "Chua co phan giai thich.",
      needs_teacher_review: true,
      review_reason: "low_confidence",
    });

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /nộp bài/i }));

    await waitFor(() => {
      expect(screen.getByText(/cần giáo viên xem lại/i)).toBeDefined();
    });
    expect(screen.getByText(/độ tin cậy thấp/i)).toBeDefined();
  });

  it("stays quiet when no review is needed", async () => {
    stubFetch({
      submission_id: "sub-1",
      score: 1,
      confidence: 0.92,
      misconception_code: null,
      feedback_text: "Dap an dung.",
      needs_teacher_review: false,
      review_reason: null,
    });

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /nộp bài/i }));

    await waitFor(() => {
      expect(screen.getByText(/không cần giáo viên xem lại/i)).toBeDefined();
    });
  });
});
