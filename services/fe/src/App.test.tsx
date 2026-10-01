/**
 * Những hành vi của frontend mà một luật phụ thuộc vào.
 *
 * Mấy test này không kiểm tra xem một màn hình trông có đúng không; chúng kiểm
 * tra ba chỗ mà giao diện có thể giành một quyết định khỏi tay BE. Mọi thứ còn
 * lại của các màn hình thì được kiểm bằng cách nhìn vào chúng.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { countdown, moment } from "./api";
import AssignmentList from "./screens/student/AssignmentList";
import Result from "./screens/student/Result";
import Sitting from "./screens/student/Sitting";
import Tutor from "./screens/student/Tutor";

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
    // Hai lần là cố ý: banner gọi tên hành động, còn phần hover của điểm thì
    // giải thích con số 0. Cả hai mất đi cùng lúc khi pha 2 đóng.
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
    // Lời giải thích vẫn tồn tại nhưng bị ẩn cho tới khi hover vào điểm (ADR-16).
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
    state: "cần-chữa",
    deadline: "2026-09-15T15:00:00+00:00",
    minutes_per_question: 5,
    round_budget_minutes: 10,
    open_count: 1,
    can_start_round: true,
    warn_cut: false,
    open_round_id: null,
    items: [
      {
        question_id: "q4",
        order: 4,
        stem: "Cho hàm số y = x³ − 3x.",
        chosen: { label: "B", text: "Khoảng (−1; 1)" },
        correct: { label: "A", text: "Khoảng (−∞; −1)" },
        rounds_used: 0,
        rounds_max: 3,
        mark: 0,
        closed: false,
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
    // Tên của cái sai và các lời giải chi tiết nằm sau dialog.
    expect(screen.queryByText(/đọc ngược/)).toBeNull();
  });

  it("locks the composer and drops the new-round button once the attempt ends", async () => {
    stubTwo({ attempt_id: "a1", locked: true, messages: [] });
    render(<Tutor me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText("CÁC CÂU EM LÀM SAI")).toBeTruthy());
    expect(screen.queryByText(/Làm bài mới/)).toBeNull();
    // Việc báo cáo sống lâu hơn `Attempt`: nó không chặn gì cả (ADR-19).
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

describe("the one-way doors", () => {
  const ATTEMPT = {
    attempt_id: "a1",
    title: "Kiểm tra 15 phút — Hàm số",
    started_at: "2026-09-15T07:00:00+00:00",
    ends_at: "2026-09-15T07:15:00+00:00",
    questions: [
      {
        question_id: "q1",
        order: 1,
        stem: "Đạo hàm của y = x² + 3x là gì?",
        options: [
          { option_id: "o1", label: "A", text: "2x + 3" },
          { option_id: "o2", label: "B", text: "x + 3" },
        ],
        chosen_option_id: null,
      },
      {
        question_id: "q2",
        order: 2,
        stem: "Hàm số y = 2x + 1 đồng biến trên khoảng nào?",
        options: [
          { option_id: "o3", label: "A", text: "(−∞; +∞)" },
          { option_id: "o4", label: "B", text: "(0; +∞)" },
        ],
        chosen_option_id: null,
      },
    ],
  };

  it("asks before ending phase 1, and reads back the count it shows", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? "GET"} ${url}`);
        return new Response(JSON.stringify(ATTEMPT), { status: 200 });
      }),
    );
    render(<Sitting me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText(/Câu 1 \/ 2/)).toBeTruthy());
    screen.getByRole("button", { name: "Nộp bài" }).click();

    // Nộp bài là kết thúc pha 1 và không thể hoàn lại (ADR-14), nên cái nút mở
    // ra một cửa chắn chứ không phải chính cánh cửa.
    await waitFor(() => expect(screen.getByText("Nộp bài?")).toBeTruthy());
    expect(calls.some((call) => call.startsWith("POST"))).toBe(false);
    // Con số lấy từ đúng cái chỗ mà dải điều hướng lấy, không phải từ một câu
    // ai đó gõ tay vào.
    expect(screen.getAllByText(/2 câu/).length).toBeGreaterThan(0);
  });
});

describe("what scrolls", () => {
  const PANEL = {
    attempt_id: "a1",
    state: "cần-chữa",
    deadline: "2026-09-15T15:00:00+00:00",
    minutes_per_question: 5,
    round_budget_minutes: 10,
    open_count: 1,
    can_start_round: true,
    warn_cut: false,
    open_round_id: null,
    items: [
      {
        question_id: "q4",
        order: 4,
        stem: "Cho hàm số y = x³ − 3x.",
        chosen: { label: "B", text: "Khoảng (−1; 1)" },
        correct: { label: "A", text: "Khoảng (−∞; −1)" },
        rounds_used: 0,
        rounds_max: 3,
        mark: 0,
        closed: false,
      },
    ],
  };

  it("keeps the composer out of the scrolling region", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        new Response(
          JSON.stringify(
            String(url).includes("/chat")
              ? { attempt_id: "a1", locked: true, messages: [] }
              : PANEL,
          ),
          { status: 200 },
        ),
      ),
    );
    const { container } = render(<Tutor me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText("CÁC CÂU EM LÀM SAI")).toBeTruthy());

    const thread = container.querySelector(".thread");
    expect(thread).not.toBeNull();
    // Khung soạn tin là một chỗ để hành động. Một hành động cuộn đi mất cùng
    // cuộc trò chuyện là một hành động học sinh phải đi tìm mới thấy.
    expect(thread?.querySelector(".composer")).toBeNull();
    expect(container.querySelector(".composer")).not.toBeNull();
  });
});

describe("asking for the opening turn", () => {
  const PANEL = {
    attempt_id: "a1",
    state: "cần-chữa",
    deadline: "2026-09-15T15:00:00+00:00",
    minutes_per_question: 5,
    round_budget_minutes: 10,
    open_count: 1,
    can_start_round: true,
    warn_cut: false,
    open_round_id: null,
    items: [
      {
        question_id: "q4",
        order: 4,
        stem: "Cho hàm số y = x³ − 3x.",
        chosen: { label: "B", text: "Khoảng (−1; 1)" },
        correct: { label: "A", text: "Khoảng (−∞; −1)" },
        rounds_used: 0,
        rounds_max: 3,
        mark: 0,
        closed: false,
      },
    ],
  };

  it("asks once, not forever, when the turn cannot be produced", async () => {
    // Một tab bị bỏ ở màn này trong lúc `Attempt` chưa nộp — BE trả 409 và lịch
    // sử vẫn rỗng. Effect đi xin lượt nói mở đầu phụ thuộc vào lịch sử đó, mà nó
    // cũng làm cho lịch sử đó bị thay, nên không có chốt thì nó bắn lại nhanh
    // bằng mức mạng cho phép: đo được khoảng 1.500 request một giây, làm một Vite
    // dev server phình lên 69 GB qua một buổi chiều và lôi luôn bộ nhớ của máy đi
    // theo.
    let streams = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const path = String(url);
        if (path.includes("/chat/stream")) {
          streams += 1;
          return new Response("Phần chữa mở sau khi nộp bài", { status: 409 });
        }
        if (path.includes("/chat")) {
          return new Response(
            JSON.stringify({ attempt_id: "a1", locked: false, messages: [] }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify(PANEL), { status: 200 });
      }),
    );

    render(<Tutor me={ME} attemptId="a1" />);
    await waitFor(() => expect(screen.getByText("CÁC CÂU EM LÀM SAI")).toBeTruthy());
    await new Promise((resolve) => setTimeout(resolve, 600));

    expect(streams).toBeLessThanOrEqual(1);
  });
});
