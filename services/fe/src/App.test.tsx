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
import Result from "./screens/Result";

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

describe("formatting", () => {
  it("writes an instant the way every screen writes it", () => {
    expect(moment("2026-09-15T22:00:00")).toBe("22:00 · 15/9");
  });

  it("clamps a finished countdown at zero rather than going negative", () => {
    expect(countdown(-5000)).toBe("00:00");
    expect(countdown(65000)).toBe("01:05");
  });
});
