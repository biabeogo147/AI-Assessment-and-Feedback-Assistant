/**
 * Những hành vi của frontend mà một luật phụ thuộc vào.
 *
 * Mấy test này không kiểm tra xem một màn hình trông có đúng không; chúng kiểm
 * tra ba chỗ mà giao diện có thể giành một quyết định khỏi tay BE. Mọi thứ còn
 * lại của các màn hình thì được kiểm bằng cách nhìn vào chúng.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { countdown, listed, moment } from "./api";
import { surfaceFor } from "./App";
import AssignmentList from "./screens/student/AssignmentList";
import Result from "./screens/student/Result";
import Round from "./screens/student/Round";
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

describe("choosing the surface", () => {
  // Trên lab tên máy thắng hash (plan `lab-subdomains`); ở mọi tên khác, hash quyết định như trước.
  it.each([
    ["teacher.example.com", "/", "teacher", "/teacher"],
    ["teacher.example.com", "/bai/a1", "teacher", "/teacher"],
    ["teacher.example.com", "/teacher/lop", "teacher", null],
    ["student.example.com", "/teacher", "student", "/"],
    ["student.example.com", "/teacher/lop/c1", "student", "/"],
    ["student.example.com", "/", "student", null],
    ["127.0.0.1", "/teacher", "teacher", null],
    ["127.0.0.1", "/", "student", null],
    ["127.0.0.1", "/teachers", "student", null],
  ])("on %s at %s draws %s and moves to %s", (hostname, route, surface, redirect) => {
    expect(surfaceFor(hostname, route)).toEqual({ surface, redirect });
  });
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

  it("says the last remediation round ran out, when BE says so", async () => {
    // Artboard 16b (plan `wave-2-time-marks-titles`): màn này vừa được lượt chữa tự nộp vì hết giờ.
    stubFetch({ ...resultPayload("cần-chữa", "chưa-chữa"), last_round_ran_out: true });
    render(<Result me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText(/Câu 4/)).toBeTruthy());
    expect(screen.getByRole("status").textContent).toBe(
      "Lượt chữa vừa rồi đã hết giờ nên được nộp luôn. Câu bỏ trống trong lượt ấy tính là sai.",
    );
  });

  it("says nothing about a round when none ran out", async () => {
    stubFetch(resultPayload("cần-chữa", "chưa-chữa"));
    render(<Result me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText(/Câu 4/)).toBeTruthy());
    expect(screen.queryByText(/đã hết giờ nên được nộp luôn/)).toBeNull();
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

describe("the score sheet's link to the tutor", () => {
  it("is offered while a question is below full marks", async () => {
    stubFetch(resultPayload("hết-hạn-chữa", "chưa-chữa"));
    render(<Result me={ME} attemptId="a1" />);
    await waitFor(() => expect(screen.getByText(/Câu 4/)).toBeTruthy());
    expect(screen.getByRole("button", { name: "Xem lại phần chữa các câu sai" })).toBeTruthy();
  });

  it("is gone when no question was wrong", async () => {
    // Thử tay đầu-cuối 20/10/2026: Dũng 6,0/6 vẫn có link, mở ra thì "Bài này không có câu nào sai."
    const payload = resultPayload("hết-hạn-chữa", "đúng");
    payload.items[0].mark = 1;
    stubFetch(payload);
    render(<Result me={ME} attemptId="a1" />);
    await waitFor(() => expect(screen.getByText(/Câu 4/)).toBeTruthy());
    expect(screen.queryByRole("button", { name: /Xem lại phần chữa|Hỏi trợ lý/ })).toBeNull();
  });

  it("labels the student code in the top bar (Figma HS 12–23)", async () => {
    stubFetch(resultPayload("cần-chữa", "chưa-chữa"));
    render(<Result me={ME} attemptId="a1" />);
    expect(await screen.findByText("Mã HS2026-1204")).toBeTruthy();
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

  it("turns the report button into a quiet done mark, not a red strip", async () => {
    // Thử tay đầu-cuối 20/10/2026: câu xác nhận đi qua `setError`, nên hiện thành dải lỗi đỏ.
    stubTwo({ attempt_id: "a1", locked: true, messages: [] });
    render(<Tutor me={ME} attemptId="a1" />);
    fireEvent.click(await screen.findByRole("button", { name: /Báo cáo Trợ lý giải thích khó hiểu/ }));
    const done = await screen.findByRole("button", { name: "Đã báo cho giáo viên" });
    expect((done as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("names three open questions the way a person would", async () => {
    // Plan `backlog-tier-1` (review ảnh): "câu 1 và câu 2 và câu 3" -> "câu 1, câu 2 và câu 3".
    const one = PANEL.items[0];
    const three = [1, 2, 3].map((order) => ({ ...one, question_id: `q${order}`, order }));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const body = String(url).includes("/chat")
          ? { attempt_id: "a1", locked: false, messages: [] }
          : { ...PANEL, open_count: 3, items: three };
        return new Response(JSON.stringify(body), { status: 200 });
      }),
    );
    render(<Tutor me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getAllByText(/câu 1, câu 2 và câu 3/).length).toBeGreaterThan(0));
    expect(screen.queryByText(/câu 1 và câu 2/)).toBeNull();
  });
});

describe("formatting", () => {
  it("joins names the way Vietnamese says them", () => {
    expect(listed(["12A"])).toBe("12A");
    expect(listed(["12A", "12B"])).toBe("12A và 12B");
    expect(listed(["12A", "12B", "12C"])).toBe("12A, 12B và 12C");
  });

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

  it("asks before starting phase 1, and reads back the row it starts", async () => {
    // Plan `backlog-tier-1`: bắt đầu là đồng hồ chạy và không ai dừng được -- cửa một chiều thứ
    // nhất của học sinh từng là một nút trơn.
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? "GET"} ${url}`);
        return new Response(
          JSON.stringify([
            {
              assignment_id: "as2",
              attempt_id: null,
              title: "Bài tập tuần 6 — Lượng giác",
              subject: "Toán",
              question_count: 8,
              phase1_minutes: 20,
              opens_at: "2026-09-15T11:00:00+00:00",
              closes_at: "2026-09-15T14:00:00+00:00",
              remediation_deadline: "2026-09-16T16:00:00+00:00",
              status: "đang-mở",
              wrong_count: null,
              actions: ["start"],
            },
          ]),
          { status: 200 },
        );
      }),
    );
    render(<AssignmentList me={ME} />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Bắt đầu" })).toBeTruthy());
    screen.getByRole("button", { name: "Bắt đầu" }).click();

    await waitFor(() => expect(screen.getByText("Bắt đầu làm bài?")).toBeTruthy());
    expect(calls.some((call) => call.startsWith("POST"))).toBe(false);
    expect(screen.getByText("8 câu")).toBeTruthy();
    expect(screen.getByText("20 phút")).toBeTruthy();

    screen.getByRole("button", { name: "Để sau" }).click();
    await waitFor(() => expect(screen.queryByText("Bắt đầu làm bài?")).toBeNull());
    expect(calls.some((call) => call.startsWith("POST"))).toBe(false);
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

describe("a round open in another tab", () => {
  // Plan `backlog-tier-1`: câu của lượt chỉ sống trong `sessionStorage` của tab đã mở nó, nên tab
  // mới thấy "Không đọc được lượt này", còn nút xin lượt mới thì xám (BE trả 409).
  const ROUND = {
    round_id: "r1",
    index: 1,
    started_at: "2098-12-31T23:55:00+00:00",
    ends_at: "2099-01-01T00:00:00+00:00",
    items: [
      {
        round_item_id: "i1",
        origin_question_id: "q4",
        origin_order: 4,
        order: 1,
        stem: "Cho hàm số y = x³ − 12x. Hàm số nghịch biến trên khoảng nào?",
        options: [
          { option_id: "A", label: "A", text: "(−2; 2)" },
          { option_id: "B", label: "B", text: "(2; +∞)" },
        ],
        chosen_label: "B",
      },
    ],
    // Không phải 0,5: hộp nộp lượt phải in số BE gửi, không một bản sao của luật điểm.
    mark_when_right: 0.75,
  };

  afterEach(() => {
    window.sessionStorage.clear();
  });

  it("reads the round back from the server, with the choice already saved", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        new Response(
          JSON.stringify(
            String(url).endsWith("/rounds/r1") ? ROUND : { open_round_id: "r1", items: [] },
          ),
          { status: 200 },
        ),
      ),
    );

    const { container } = render(<Round me={ME} attemptId="a1" roundId="r1" />);

    await waitFor(() => expect(screen.getByText(/nghịch biến/)).toBeTruthy());
    expect(screen.queryByText("Không đọc được lượt này.")).toBeNull();
    await waitFor(() => expect(container.querySelector(".option.chosen")).toBeTruthy());
    expect(container.querySelector(".option.chosen")?.textContent).toContain("(2; +∞)");
  });

  it("names the round's length, and asks before handing it in", async () => {
    // Plan `backlog-tier-1`: đầu màn từng in thời gian *còn lại* như thể là độ dài lượt; nộp lượt
    // là cửa một chiều mà từng không có cổng.
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? "GET"} ${url}`);
        return new Response(
          JSON.stringify(
            String(url).endsWith("/rounds/r1") ? ROUND : { open_round_id: "r1", items: [] },
          ),
          { status: 200 },
        );
      }),
    );
    render(<Round me={ME} attemptId="a1" roundId="r1" />);

    await waitFor(() => expect(screen.getByText(/1 câu · 5 phút/)).toBeTruthy());
    screen.getByRole("button", { name: "Nộp bài" }).click();

    await waitFor(() => expect(screen.getByText("Nộp lượt này?")).toBeTruthy());
    expect(calls.some((call) => call.includes("/submit"))).toBe(false);
    expect(screen.getByText("1 trên 1 câu")).toBeTruthy();
    expect(screen.getByText("câu làm đúng được 0,75 điểm")).toBeTruthy();
  });

  describe("at zero", () => {
    // Tier 2 câu 18 (plan `wave-2-time-marks-titles`): đồng hồ về 0 thì màn hình hỏi lại BE, và chỉ
    // lời đáp của BE dời màn. `ends_at` cố định như BE thật: BE không bao giờ gia hạn một lượt.
    afterEach(() => {
      vi.useRealTimers();
      window.location.hash = "";
    });

    /**
     * Dựng một BE giả cho lượt `r1` đã sắp hết giờ.
     *
     * @param read - Lời đáp của lần đọc lượt thứ `n` (đếm từ 1): `stopped` hay một status lỗi.
     * @param submitStatus - Status của lần nộp.
     */
    function stubRound(read: (n: number) => boolean | number, submitStatus = 200) {
      const calls: string[] = [];
      const endsAt = new Date(Date.now() + 500).toISOString();
      window.location.hash = "#/round/a1/r1";
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string, init?: RequestInit) => {
          calls.push(`${init?.method ?? "GET"} ${url}`);
          const reply = (body: object, status = 200) =>
            new Response(JSON.stringify(body), { status });
          if (url.endsWith("/submit")) {
            const body =
              submitStatus === 200 ? { round_id: "r1", per_question: [] } : { detail: "BE đang bận" };
            return reply(body, submitStatus);
          }
          if (url.endsWith("/rounds/r1")) {
            const answer = read(calls.filter((one) => one === "GET /api/rounds/r1").length);
            return typeof answer === "number"
              ? reply({ detail: "Lượt này đã nộp" }, answer)
              : reply({ ...ROUND, ends_at: endsAt, stopped: answer });
          }
          return reply({ open_round_id: "r1", items: [] });
        }),
      );
      return calls;
    }

    const reads = (calls: string[]) => calls.filter((one) => one === "GET /api/rounds/r1").length;
    const submits = (calls: string[]) => calls.filter((one) => one.endsWith("/submit")).length;

    it("hands in and leaves only once BE says the round stopped", async () => {
      vi.useFakeTimers();
      const calls = stubRound((n) => n > 1);
      render(<Round me={ME} attemptId="a1" roundId="r1" />);

      await vi.advanceTimersByTimeAsync(1000);
      // Hỏi lại trước, nộp sau: lần đọc thứ hai mới nói lượt đã dừng.
      expect(reads(calls)).toBe(2);
      expect(calls.at(-1)).toBe("POST /api/rounds/r1/submit");
      expect(window.location.hash).toBe("#/attempt/a1/result");
    });

    it("stays, and asks again only a bounded number of times, while BE says it runs", async () => {
      vi.useFakeTimers();
      const calls = stubRound(() => false);
      render(<Round me={ME} attemptId="a1" roundId="r1" />);

      await vi.advanceTimersByTimeAsync(1000);
      expect(reads(calls)).toBe(2);
      // Lần đầu khi mở màn, một lần khi về 0, rồi năm lần hỏi lại cách nhau một giây; thế là thôi.
      await vi.advanceTimersByTimeAsync(30_000);
      expect(reads(calls)).toBe(7);
      expect(submits(calls)).toBe(0);
      expect(window.location.hash).toBe("#/round/a1/r1");
    });

    it("goes to the score sheet when BE says the round was handed in elsewhere", async () => {
      vi.useFakeTimers();
      const calls = stubRound((n) => (n > 1 ? 409 : false));
      render(<Round me={ME} attemptId="a1" roundId="r1" />);

      await vi.advanceTimersByTimeAsync(1000);
      expect(submits(calls)).toBe(0);
      expect(window.location.hash).toBe("#/attempt/a1/result");
    });

    it("stays and says so when BE cannot be reached or refuses the hand-in", async () => {
      vi.useFakeTimers();
      const calls = stubRound((n) => n > 1, 500);
      render(<Round me={ME} attemptId="a1" roundId="r1" />);

      await vi.advanceTimersByTimeAsync(1000);
      expect(submits(calls)).toBe(1);
      expect(window.location.hash).toBe("#/round/a1/r1");
      expect(screen.getByText("BE đang bận")).toBeTruthy();
    });
  });

  it("offers to go back into the open round instead of a greyed-out new one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        new Response(
          JSON.stringify(
            String(url).includes("/chat")
              ? { attempt_id: "a1", locked: false, messages: [] }
              : {
                  attempt_id: "a1",
                  state: "cần-chữa",
                  deadline: "2099-01-01T00:00:00+00:00",
                  minutes_per_question: 5,
                  round_budget_minutes: 10,
                  open_count: 1,
                  can_start_round: false,
                  warn_cut: false,
                  open_round_id: "r1",
                  items: [],
                },
          ),
          { status: 200 },
        ),
      ),
    );

    render(<Tutor me={ME} attemptId="a1" />);

    await waitFor(() => expect(screen.getByText("Làm tiếp lượt đang mở")).toBeTruthy());
    expect(screen.queryByText(/Làm bài mới/)).toBeNull();
  });
});
