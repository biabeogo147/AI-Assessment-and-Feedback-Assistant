/**
 * Frontend behaviour that a rule depends on.
 *
 * These tests do not check that a screen looks right; they check the three
 * places where the interface could take a decision away from BE. Everything
 * else about the screens is verified by looking at them.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { countdown, moment } from "./api";
import AssignmentList from "./screens/AssignmentList";
import Result from "./screens/Result";
import Tutor from "./screens/Tutor";

const ME = {
  student_id: "s1",
  full_name: "Nguyễn Minh Anh",
  class_name: "12A",
  student_code: "HS2026-1204",
};

function resultPayload(state: string, markReason: string) {
  return {
    attempt_id: "a1",
    title: "Kiểm tra 15 phút — Hàm số",
    state,
    total_score: 4.5,
    question_count: 6,
    submitted_at: "2026-09-15T07:12:00+00:00",
    remediation_deadline: "2026-09-15T15:00:00+00:00",
    items: [
      {
        question_id: "q4",
        order: 4,
        stem: "Cho hàm số y = x³ − 3x.",
        mark: 0,
        mark_reason: markReason,
        rounds: [],
      },
    ],
  };
}

function stubFetch(payload: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the score sheet", () => {
  it("offers to raise a zero only while phase 2 is open", async () => {
    stubFetch(resultPayload("cần-chữa", "chưa-chữa"));
    render(<Result me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText(/Câu 4/)).toBeTruthy());
    // Twice on purpose: the banner names the action, the mark's hover explains
    // the zero. Both disappear together when phase 2 closes.
    expect(screen.getAllByText(/có thể nâng điểm/).length).toBe(2);
  });

  it("promises nothing about a zero once the deadline has passed", async () => {
    stubFetch(resultPayload("hết-hạn-chữa", "chưa-chữa"));
    render(<Result me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText(/Câu 4/)).toBeTruthy());
    expect(screen.queryAllByText(/có thể nâng điểm/).length).toBe(0);
  });

  it("shows no score reason in the page body, only on hover", async () => {
    stubFetch(resultPayload("cần-chữa", "chữa-được"));
    const { container } = render(<Result me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText(/Câu 4/)).toBeTruthy());
    const tip = container.querySelector(".tip");
    expect(tip).not.toBeNull();
    // The explanation exists but is hidden until the mark is hovered (ADR-16).
    expect(tip?.parentElement?.className).toContain("hoverable");
  });
});

describe("the assignment list", () => {
  it("renders the buttons BE said the row has, in BE's order", async () => {
    stubFetch([
      {
        assignment_id: "as1",
        attempt_id: "a1",
        title: "Kiểm tra 15 phút — Hàm số",
        subject: "Toán",
        question_count: 6,
        phase1_minutes: 15,
        opens_at: "2026-09-15T11:00:00+00:00",
        closes_at: "2026-09-15T11:00:00+00:00",
        remediation_deadline: "2026-09-15T15:00:00+00:00",
        status: "cần-chữa",
        wrong_count: 2,
        actions: ["result", "remediate"],
      },
    ]);
    render(<AssignmentList me={ME} />);

    await waitFor(() => expect(screen.getByText(/Kiểm tra 15 phút/)).toBeTruthy());
    expect(screen.getByText("Xem kết quả")).toBeTruthy();
    expect(screen.getByText("Hỏi trợ lý và làm lại dạng bài sai")).toBeTruthy();
    expect(screen.getByText(/Cần làm lại 2 câu/)).toBeTruthy();
  });
});

describe("the tutoring screen", () => {
  const PANEL = {
    attempt_id: "a1",
    deadline: "2026-09-15T15:00:00+00:00",
    minutes_per_question: 5,
    round_budget_minutes: 10,
    can_start_round: true,
    warn_cut: false,
    open_round_id: null,
    remaining: [
      {
        question_id: "q4",
        order: 4,
        stem: "Cho hàm số y = x³ − 3x.",
        chosen: { label: "B", text: "Khoảng (−1; 1)" },
        correct: { label: "A", text: "Khoảng (−∞; −1)" },
        rounds_used: 0,
        rounds_max: 3,
      },
    ],
  };

  function stubTwo(history: unknown) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const body = String(url).includes("/chat") ? history : PANEL;
        return new Response(JSON.stringify(body), { status: 200 });
      }),
    );
  }

  it("lists every wrong question with what was picked and what was right", async () => {
    stubTwo({ attempt_id: "a1", locked: false, messages: [{ message_id: "m", role: "assistant", text: "chào em", created_at: "2026-09-15T11:00:00+00:00" }] });
    render(<Tutor me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText("CÁC CÂU EM LÀM SAI")).toBeTruthy());
    expect(screen.getByText(/Em đã chọn B/)).toBeTruthy();
    expect(screen.getByText(/Đáp án đúng A/)).toBeTruthy();
    // The mistake's name and the worked solutions stay behind the dialog.
    expect(screen.queryByText(/đọc ngược/)).toBeNull();
  });

  it("locks the composer and drops the new-round button once the attempt ends", async () => {
    stubTwo({ attempt_id: "a1", locked: true, messages: [] });
    render(<Tutor me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText("CÁC CÂU EM LÀM SAI")).toBeTruthy());
    expect(screen.queryByText(/Làm bài mới/)).toBeNull();
    // Reporting outlives the attempt: it blocks nothing (ADR-19).
    expect(screen.getByText(/Báo cáo Trợ lý giải thích khó hiểu/)).toBeTruthy();
  });
});

describe("formatting", () => {
  it("writes an instant the way every screen writes it", () => {
    expect(moment("2026-09-15T22:00:00")).toBe("22:00 · 15/9");
  });

  it("clamps a finished countdown at zero rather than going negative", () => {
    expect(countdown(-5000)).toBe("00:00");
    expect(countdown(65000)).toBe("01:05");
  });
});
