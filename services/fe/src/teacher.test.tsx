/**
 * Năm chỗ bề mặt giáo viên có thể giành một quyết định khỏi tay BE, hoặc tự nói sai về
 * chính nó.
 *
 * Không test nào ở đây kiểm một màn hình trông có đúng không — việc đó làm bằng cách đo
 * với Figma. Chúng kiểm ba điều khoản mà một lần sửa vô ý có thể phá mà không ai thấy:
 * hộp xác nhận không được tự viết lại câu luật, một hành động đã xảy ra không được đọc ra
 * như lời model, và một câu vừa gửi không được hiện hai lần.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ActionCard, { cardTurn, stepFor } from "./screens/teacher/ActionCard";
import Chat, { grow } from "./screens/teacher/Chat";
import Panel from "./screens/teacher/Panel";
import PublishSettings from "./screens/teacher/PublishSettings";
import Steps from "./screens/teacher/Steps";
import type { TurnEvent } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

const FORM = {
  assessment_id: "p1",
  title: "Kiểm tra 15 phút — Hàm số",
  state: "approved",
  question_count: 6,
  can_publish: true,
  reason: "",
  classes: [
    { class_id: "c1", name: "12A", student_count: 40, published: false },
  ],
  rules: {
    phase_one: "Vào tham gia tới hết --:--",
    phase_two: "Chữa bài tới hết --:--",
    recall: "Thu hồi được cho tới hết giờ mở.",
    // Khuôn, sao đúng từ `publication_wording.PHASE_ONE` / `PHASE_TWO`.
    phase_one_form:
      "Vào tham gia tới hết {closes} - có thể nộp lúc {last}, và không dừng người đang làm.",
    phase_two_form:
      "Chữa bài tới hết {deadline} - mỗi lượt {rate} phút một câu, và hết hạn thì lượt đang làm bị DỪNG.",
  },
};

// Hai câu này KHÔNG phải câu mà biểu mẫu trả về, và cũng không phải thứ FE dựng nổi từ
// mấy con số đã gõ. Nếu chúng hiện ra trong hộp xác nhận thì hộp ấy đang in đúng chuỗi
// của response `preview`, chứ không tự tính lại.
const PREVIEW = {
  assessment_id: "p1",
  state: "approved",
  preview: true,
  classes: [
    {
      class_id: "c1",
      class_name: "12A",
      published: true,
      reason: "",
      opens_at: "2026-10-02T07:00:00+00:00",
      closes_at: "2026-10-02T09:00:00+00:00",
      remediation_deadline: "2026-10-02T15:00:00+00:00",
      withdrawable_until: "2026-10-02T07:00:00+00:00",
      phase_one_note: "CÂU-LUẬT-MỘT-TỪ-BE",
      phase_two_note: "CÂU-LUẬT-HAI-TỪ-BE",
    },
  ],
  rules: { phase_one: "x", phase_two: "y", recall: "CÂU-THU-HỒI-TỪ-BE" },
};

function fill() {
  const boxes = document.querySelectorAll(".publish-settings input");
  const values = [
    "15",
    "2026-10-02T14:00",
    "2026-10-02T16:00",
    "5",
    "2026-10-02T22:00",
  ];
  boxes.forEach((box, index) => {
    fireEvent.change(box, { target: { value: values[index] } });
  });
}

describe("hộp xác nhận phát hành", () => {
  it("chỉ in những chuỗi của response preview, không tự viết lại câu luật", async () => {
    const sent: { body: unknown; path: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, init?: RequestInit) => {
        sent.push({
          path,
          body: init?.body ? JSON.parse(String(init.body)) : null,
        });
        const payload = init?.method === "POST" ? PREVIEW : FORM;
        return new Response(JSON.stringify(payload), { status: 200 });
      }),
    );

    render(<PublishSettings
        assessmentId="p1"
        onPublished={() => {}}
        onUndo={() => {}}
        undoing={false}
      />);
    await waitFor(() =>
      expect(screen.getByText("Cài đặt phát hành")).toBeTruthy(),
    );

    fireEvent.click(screen.getByText("12A"));
    fill();
    fireEvent.click(screen.getByText("Phát hành đề"));

    await waitFor(() =>
      expect(screen.getByText("Phát hành đề kiểm tra?")).toBeTruthy(),
    );
    expect(screen.getByText("CÂU-LUẬT-MỘT-TỪ-BE")).toBeTruthy();
    expect(screen.getByText("CÂU-LUẬT-HAI-TỪ-BE")).toBeTruthy();
    expect(screen.getByText("CÂU-THU-HỒI-TỪ-BE")).toBeTruthy();

    // Và lần gọi xem trước mang đúng cờ `preview`, vì nếu không thì cái "xem trước" ấy
    // đã phát hành thật rồi.
    const asked = sent.find((one) => one.path.endsWith("/publications"));
    expect((asked?.body as { preview: boolean }).preview).toBe(true);
  });

  it("gửi đi đúng object đã xem trước, chỉ khác mỗi cờ", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_path: string, init?: RequestInit) => {
        if (init?.method === "POST") bodies.push(JSON.parse(String(init.body)));
        const payload = init?.method === "POST" ? PREVIEW : FORM;
        return new Response(JSON.stringify(payload), { status: 200 });
      }),
    );

    render(<PublishSettings
        assessmentId="p1"
        onPublished={() => {}}
        onUndo={() => {}}
        undoing={false}
      />);
    await waitFor(() =>
      expect(screen.getByText("Cài đặt phát hành")).toBeTruthy(),
    );
    fireEvent.click(screen.getByText("12A"));
    fill();
    fireEvent.click(screen.getByText("Phát hành đề"));
    await waitFor(() =>
      expect(screen.getByText("Phát hành đề kiểm tra?")).toBeTruthy(),
    );
    // Nút trong hộp thoại, không phải nút của biểu mẫu: hai nút cùng chữ, và chỉ nút
    // trong hộp mới gửi đi lần thật.
    fireEvent.click(
      document.querySelector(".confirm .btn.primary") as HTMLElement,
    );

    await waitFor(() => expect(bodies.length).toBe(2));
    const [shown, done] = bodies;
    expect(shown.preview).toBe(true);
    expect(done.preview).toBe(false);
    // Byte-identical trừ một cờ. Đây là cách duy nhất để "hộp xác nhận đọc lại đúng cái
    // sắp xảy ra" là một tính chất của code chứ không phải một lời hứa.
    expect(JSON.stringify(shown.schedules)).toBe(
      JSON.stringify(done.schedules),
    );
  });

  it("gửi giờ kèm offset, không phải Z", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_path: string, init?: RequestInit) => {
        if (init?.method === "POST") bodies.push(JSON.parse(String(init.body)));
        return new Response(
          JSON.stringify(init?.method === "POST" ? PREVIEW : FORM),
          {
            status: 200,
          },
        );
      }),
    );

    render(<PublishSettings
        assessmentId="p1"
        onPublished={() => {}}
        onUndo={() => {}}
        undoing={false}
      />);
    await waitFor(() =>
      expect(screen.getByText("Cài đặt phát hành")).toBeTruthy(),
    );
    fireEvent.click(screen.getByText("12A"));
    fill();
    fireEvent.click(screen.getByText("Phát hành đề"));

    await waitFor(() => expect(bodies.length).toBe(1));
    const when = (bodies[0].schedules as { opens_at: string }[])[0].opens_at;
    expect(when.endsWith("Z")).toBe(false);
    expect(/[+-]\d{2}:\d{2}$/.test(when)).toBe(true);
  });
});

describe("một bước đã xảy ra", () => {
  it("ra thẻ kết quả chứ không ra một bong bóng lời model", () => {
    const { container } = render(
      <ActionCard
        turn={{
          kind: "tool_result",
          text: "",
          tool_name: "teacher.publish",
          tool_result: {
            published: true,
            assessment_id: "p1",
            classes: ["12A", "12B"],
          },
          entity_kind: "assessment",
          entity_id: "p1",
          choices: [],
          more_choices: 0,
          model_tokens: 0,
          duration_ms: 0,
        }}
        onOpen={() => {}}
        onCompose={() => {}}
      />,
    );

    expect(container.querySelector(".action-card")).toBeTruthy();
    expect(container.querySelector(".reply-text")).toBeNull();
    expect(screen.getByText(/Đã phát hành cho 12A và 12B/)).toBeTruthy();
  });

  it("nói hậu quả của việc phát hành, và không nói nó chưa tới học sinh", () => {
    // Thẻ phát hành là thẻ có hậu quả lớn nhất, nên nó là thẻ **không được phép** im lặng.
    // Variant `đã-phát-hành` của Figma mang ba dòng luật; câu ở đây nói đúng nửa còn kiểm
    // được từ `tool_result`: thu hồi còn mở, và mốc chấm dứt nó. Không bao giờ nói "chưa
    // phát hành" — ở đây thì đó là lời nói dối ngược chiều với mọi thẻ khác.
    const { container } = render(
      <ActionCard
        turn={{
          kind: "tool_result",
          text: "",
          tool_name: "teacher.publish",
          tool_result: {
            published: true,
            assessment_id: "p1",
            classes: ["12A"],
          },
          entity_kind: "assessment",
          entity_id: "p1",
          choices: [],
          more_choices: 0,
          model_tokens: 0,
          duration_ms: 0,
        }}
        onOpen={() => {}}
        onCompose={() => {}}
      />,
    );
    const safety = container.querySelector(".safety");
    expect(safety).toBeTruthy();
    expect(safety?.textContent ?? "").toMatch(/[Tt]hu hồi/);
    expect(safety?.textContent ?? "").not.toMatch(/[Cc]hưa phát hành/);
  });
});

/**
 * Một lượt của Kriky gồm nhiều dòng trong `turns`: các bước tool trước, câu trả lời sau.
 * Màn hình phải gộp chúng thành một khối và mở đầu bằng hàng avatar — một avatar nằm
 * **dưới** các thẻ kết quả đọc ra như Kriky nói sau khi việc đã xong, và không ai biết
 * mấy thẻ kia của ai.
 */
const SPOKEN = {
  kind: "assistant",
  text: "Đã tạo xong đề.",
  conversation_id: "c1",
  choices: [],
  more_choices: 0,
  turns: [
    blank({ kind: "teacher", text: "Tạo đề cho 12A" }),
    blank({ kind: "tool_call", tool_name: "create_draft" }),
    blank({
      kind: "tool_result",
      tool_name: "create_draft",
      tool_result: { assessment_id: "p1", title: "Hàm số", question_count: 6 },
    }),
    blank({ kind: "assistant", text: "Đã tạo xong đề." }),
  ],
};

function blank(some: Record<string, unknown>) {
  return {
    kind: "",
    text: "",
    tool_name: "",
    tool_result: {},
    entity_kind: "",
    entity_id: "",
    choices: [] as string[],
    more_choices: 0,
    model_tokens: 0,
    duration_ms: 0,
    ...some,
  };
}

/** Trả `SPOKEN` cho đường hội thoại, rỗng cho tài liệu và danh sách đoạn chat. */
function serve() {
  const asked: string[] = [];
  // jsdom không có `scrollIntoView`, và effect cuộn-xuống-đáy gọi nó ở mỗi lượt mới.
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      asked.push(url);
      const body = url.startsWith("/api/teacher/chat") ? SPOKEN : [];
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    }),
  );
  return asked;
}

describe("một lượt của Kriky trên dòng hội thoại", () => {
  it("mở đầu bằng avatar, rồi câu trả lời, rồi thẻ kết quả", async () => {
    serve();
    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );

    await waitFor(() =>
      expect(document.querySelector(".action-card")).not.toBeNull(),
    );

    // Đúng MỘT hàng avatar cho cả lượt, không một hàng cho mỗi dòng.
    expect(document.querySelectorAll(".exchange .who")).toHaveLength(1);

    const who = document.querySelector(".exchange .who") as Element;
    const card = document.querySelector(".action-card") as Element;
    const said = document.querySelector(".reply-text") as Element;

    // DOCUMENT_POSITION_FOLLOWING = 4: thứ được so nằm SAU phần tử gọi. Thứ tự phải là
    // avatar → câu trả lời → thẻ kết quả, đúng `thread` của artboard `5 · Đã có đề nháp`.
    expect(who.compareDocumentPosition(said) & 4).toBe(4);
    expect(said.compareDocumentPosition(card) & 4).toBe(4);
  });

  it("vẫn chỉ MỘT avatar khi lượt có cả câu mở đầu lẫn câu kết", async () => {
    // Đây là hình dạng đầy đủ của một lượt hai pha: Kriky nói trước khi bắt tay, chạy plan,
    // rồi kể lại. Bản trước dựng avatar lần thứ hai cho câu kết, nên cùng một người nói
    // được giới thiệu hai lần trong một lượt — thấy rõ trên hội thoại thật, và đọc rất ồn.
    Element.prototype.scrollIntoView = vi.fn();
    const full = {
      ...SPOKEN,
      turns: [
        blank({ kind: "teacher", text: "Tạo đề 10 câu cho 12A" }),
        blank({ kind: "assistant", text: "Được, mình soạn đề ngay." }),
        blank({ kind: "tool_call", tool_name: "create_draft" }),
        blank({
          kind: "tool_result",
          tool_name: "create_draft",
          tool_result: {
            assessment_id: "p1",
            title: "Hàm số",
            question_count: 10,
          },
        }),
        blank({ kind: "assistant", text: "Đã tạo xong đề." }),
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(url.startsWith("/api/teacher/chat") ? full : []),
        }),
      ),
    );

    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy(),
    );

    expect(document.querySelectorAll(".exchange .who")).toHaveLength(1);

    // Và thứ tự đọc giữ nguyên: câu mở → khối bước → câu kết.
    const opening = screen.getByText("Được, mình soạn đề ngay.");
    const block = document.querySelector(".steps-block") as Element;
    const ending = screen.getByText("Đã tạo xong đề.");
    expect(opening.compareDocumentPosition(block) & 4).toBe(4);
    expect(block.compareDocumentPosition(ending) & 4).toBe(4);
  });

  it("tải lại một đoạn vừa rời đi vì bấm Đoạn chat mới", async () => {
    const asked = serve();
    const { rerender } = render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy(),
    );

    // Bấm *Đoạn chat mới*: màn trắng, và không còn đoạn nào đang nằm trên màn hình.
    rerender(
      <Chat conversationId={null} fresh openPaper={null} publishing={false} />,
    );
    expect(screen.queryByText("Đã tạo xong đề.")).toBeNull();

    // Bấm lại ĐÚNG đoạn vừa rời đi. Nó phải hiện lại — không phải một màn trắng vì ai đó
    // tưởng nó vẫn đang ở trên màn hình.
    rerender(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy(),
    );
    expect(
      asked.filter((one) => one.startsWith("/api/teacher/chat")).length,
    ).toBeGreaterThan(1);
  });
});

describe("khối bước lúc đang chạy", () => {
  it("hiện bước k/n với n LẤY TỪ PLAN, không phải số bước đã bắt đầu", () => {
    // `bước 1/3` nói thật được vì plan có trước khi chạy (ADR-25). Đếm theo số bước đã bắt
    // đầu thì `n` luôn bằng `k`, và con số ấy không nói gì cả. Trước test này, `Steps` chưa
    // bao giờ được render với một bước đang chạy — nên cả nhãn ấy chưa từng được đo.
    render(
      <Steps
        steps={[
          { mark: "done", title: "Tạo đề trống", result: "" },
          {
            mark: "running",
            title: "Soạn 3 câu hỏi",
            result: "— đã soạn 2/3 câu",
          },
        ]}
        total={3}
      />,
    );

    expect(screen.getByText("bước 2/3")).toBeTruthy();
    // Khối đang chạy mở sẵn, nên dòng tiến độ đọc được ngay.
    expect(screen.getByText("— đã soạn 2/3 câu")).toBeTruthy();
    expect(screen.getByText("Soạn 3 câu hỏi…")).toBeTruthy();
  });
});

describe("một lượt của Kriky", () => {
  it("cho ra ĐÚNG MỘT thẻ, và start_drafting không bao giờ là thẻ", () => {
    const turns = [
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: { created: true },
      }),
      blank({
        kind: "tool_result",
        tool_name: "start_drafting",
        tool_result: { started: true },
      }),
      blank({
        kind: "tool_result",
        tool_name: "draft_progress",
        tool_result: {
          found: true,
          written: ["a", "b"],
          asked_for: 2,
          still_drafting: 0,
        },
      }),
    ];
    const card = cardTurn(turns);
    expect(card?.tool_name).toBe("draft_progress");
  });

  it("KHÔNG mọc thẻ đề trống khi câu hỏi đang được đổ vào đề ấy", () => {
    // Đúng hình dạng một plan hai bước của ADR-25: mở đề, rồi soạn câu. Lúc lượt kết thúc,
    // các câu còn đang chạy trong hàng đợi, nên chưa có `draft_progress` nào.
    const turns = [
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: {
          created: true,
          title: "Tích phân 12A1",
          question_count: 10,
        },
      }),
      blank({
        kind: "tool_result",
        tool_name: "start_drafting",
        tool_result: { started: true, queued: 10 },
      }),
    ];

    // Không thẻ nào. "Đã tạo đề — Chưa có câu hỏi nào" ở đây là một lời khẳng định sai: giáo
    // viên nhờ một đề CÓ câu hỏi, và việc ấy đang chạy, không phải vừa xong với đề rỗng.
    expect(cardTurn(turns)).toBeNull();
  });

  it("vẫn mọc thẻ đề trống khi không có bước nào đổ câu vào nó", () => {
    // Một lượt chỉ mở đề — giáo viên nói "mở cho tôi một đề trống" — thì trạng thái trống
    // **là** kết quả của lượt, và thẻ ấy nói đúng.
    const turns = [
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: { created: true, title: "Tích phân 12A1" },
      }),
    ];
    expect(cardTurn(turns)?.tool_name).toBe("create_draft");
  });

  it("đọc một bước ném exception là HỎNG, không phải xong", () => {
    // BE nuốt exception của một bước và ghi `{"error": …}` — không có cờ `created`/`started`
    // nào cả. Một phép kiểm chỉ nhìn ba cờ ấy đọc nó thành *đã xong*: dấu ✓ cho một việc
    // chưa xảy ra, và dòng kết quả bịa ra `đề "", cần 0 câu` từ các field không tồn tại.
    // Cả hai đã thấy trên trình duyệt thật.
    const step = stepFor(
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: { error: "bước 1 chạy không xong" },
      }),
    );
    expect(step.mark).toBe("failed");
    expect(step.result).toBe("— bước 1 chạy không xong");
  });

  it("một bước ném exception cho thẻ THẤT BẠI, không phải thẻ đề trống", () => {
    const turns = [
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: { error: "bước 1 chạy không xong" },
      }),
    ];
    expect(cardTurn(turns)?.tool_name).toBe("create_draft");

    render(
      <ActionCard
        turn={turns[0]}
        onOpen={() => undefined}
        onCompose={() => undefined}
      />,
    );
    // "Đã tạo đề" ở đây là nói rằng một cái đề đã tồn tại. Không có cái đề nào.
    expect(screen.getByText("Không tạo được đề")).toBeTruthy();
    expect(screen.queryByText("Chưa có câu hỏi nào")).toBeNull();
    expect(screen.getByText("Chưa có gì được thay đổi")).toBeTruthy();
  });

  it("để start_drafting lại làm một bước chứ không bỏ nó đi", () => {
    const step = stepFor(
      blank({
        kind: "tool_result",
        tool_name: "start_drafting",
        tool_result: { started: true, queued: 5 },
      }),
    );
    expect(step.mark).toBe("done");
    expect(step.title).toBe("Soạn câu hỏi");
    expect(step.result).toBe("— 5 câu bắt đầu soạn");
  });

  it("một bước hỏng mang dấu ✕ và câu của BE", () => {
    const step = stepFor(
      blank({
        kind: "tool_result",
        tool_name: "start_drafting",
        tool_result: { started: false, reason: "đề này đang soạn dở" },
      }),
    );
    expect(step.mark).toBe("failed");
    expect(step.result).toBe("— đề này đang soạn dở");
  });
});

describe("một lượt đang chạy, dựng từ các sự kiện", () => {
  function event(some: Record<string, unknown>) {
    return {
      kind: "",
      text: "",
      choices: [],
      more_choices: 0,
      conversation_id: "c1",
      ended_as: "",
      title: "",
      detail: "",
      index: 0,
      total: 0,
      titles: [],
      began: 0,
      ...some,
    } as TurnEvent;
  }

  it("vẽ theo đúng thứ tự nhận được, và `n` lấy từ plan", () => {
    // Cốt lõi của ADR-25: `bước 1/2` nói thật được vì plan có TRƯỚC khi chạy. Nếu `n` đếm
    // theo số bước đã bắt đầu thì nó luôn bằng `k`, và con số ấy không nói gì cả.
    let live = grow(
      null,
      event({ kind: "say", text: "Được, mình soạn đề ngay." }),
    );
    live = grow(
      live,
      event({ kind: "plan", total: 2, titles: ["Tạo đề trống", "Soạn câu"] }),
    );
    live = grow(
      live,
      event({
        kind: "step_started",
        title: "Tạo đề trống",
        index: 1,
        total: 2,
      }),
    );

    expect(live.opening).toBe("Được, mình soạn đề ngay.");
    expect(live.total).toBe(2);
    expect(live.steps).toHaveLength(1);
    expect(live.steps[0].mark).toBe("running");
  });

  it("đóng bước đang chạy khi nó xong, và giữ dòng kết quả của BE", () => {
    let live = grow(
      null,
      event({ kind: "step_started", title: "Tạo đề trống", total: 2 }),
    );
    live = grow(
      live,
      event({
        kind: "step_done",
        title: "Tạo đề trống",
        detail: 'đề "X", cần 10 câu',
      }),
    );

    expect(live.steps[0].mark).toBe("done");
    expect(live.steps[0].result).toBe('— đề "X", cần 10 câu');
  });

  it("số câu đã soạn là dòng của bước đang chạy, không phải con số thứ hai trên header", () => {
    // Hai con số, hai chỗ đứng (ADR-25): `bước k/n` đếm bước của plan, số câu là tiến độ
    // bên trong MỘT bước. Gộp chúng vào một chỗ là nói sai cả hai.
    let live = grow(null, event({ kind: "plan", total: 2 }));
    live = grow(
      live,
      event({ kind: "step_started", title: "Soạn 10 câu hỏi", total: 2 }),
    );
    live = grow(live, event({ kind: "progress", index: 4, total: 10 }));

    expect(live.total).toBe(2);
    expect(live.steps[0].result).toBe("— đã soạn 4/10 câu");
    expect(live.steps[0].mark).toBe("running");
  });

  it("gắn dòng tiến độ vào bước soạn câu — đúng dãy sự kiện BE phát", () => {
    // Dãy THẬT: bước một mở rồi đóng, bước hai mở, rồi `progress` tới trong lúc nó vẫn
    // đang chạy. Test đầu tiên của Pha E nạp `step_started → progress` không có `step_done`
    // ở giữa — một dãy BE không bao giờ phát — nên nó xanh trong khi màn hình thật bỏ con
    // số đi lặng lẽ. Review bắt được.
    let live = grow(
      null,
      event({ kind: "say", text: "Được, mình soạn đề ngay." }),
    );
    live = grow(live, event({ kind: "plan", total: 2 }));
    live = grow(
      live,
      event({ kind: "step_started", title: "Tạo đề trống", total: 2 }),
    );
    live = grow(
      live,
      event({ kind: "step_done", title: "Tạo đề trống", detail: 'đề "X"' }),
    );
    live = grow(
      live,
      event({ kind: "step_started", title: "Soạn 3 câu hỏi", total: 2 }),
    );
    live = grow(live, event({ kind: "progress", index: 2, total: 3 }));

    expect(live.steps).toHaveLength(2);
    expect(live.steps[0].mark).toBe("done");
    expect(live.steps[1].mark).toBe("running");
    expect(live.steps[1].result).toBe("— đã soạn 2/3 câu");
  });

  it("một bước hỏng TRƯỚC khi nó bắt đầu vẫn hiện ra", () => {
    // BE phát `step_failed` không kèm `step_started` khi một tham chiếu `{k.field}` không
    // giải được. Bỏ qua nó thì màn hình sống im lặng về đúng cái bước đã làm lượt dừng lại.
    let live = grow(null, event({ kind: "plan", total: 2 }));
    live = grow(
      live,
      event({
        kind: "step_failed",
        title: "Soạn câu hỏi",
        detail: "chưa ghép được dữ liệu",
      }),
    );

    expect(live.steps).toHaveLength(1);
    expect(live.steps[0].mark).toBe("failed");
    expect(live.steps[0].title).toBe("Soạn câu hỏi");
  });

  it("một bước hỏng đọc ra là hỏng, kèm lý do", () => {
    let live = grow(
      null,
      event({ kind: "step_started", title: "Soạn câu hỏi" }),
    );
    live = grow(
      live,
      event({
        kind: "step_failed",
        title: "Soạn câu hỏi",
        detail: "chưa làm được bước này",
      }),
    );

    expect(live.steps[0].mark).toBe("failed");
    expect(live.steps[0].result).toBe("— chưa làm được bước này");
  });
});

describe("khối các bước", () => {
  it("thu lại khi mọi bước đã xong, mở lại được", () => {
    render(
      <Steps
        steps={[
          { mark: "done", title: "Tạo đề trống", result: '— đề "X"' },
          { mark: "done", title: "Soạn câu hỏi", result: "" },
        ]}
      />,
    );
    expect(screen.getByText("Đã làm 2 bước")).toBeTruthy();
    expect(screen.queryByText("Tạo đề trống")).toBeNull();

    fireEvent.click(screen.getByText("Đã làm 2 bước"));
    expect(screen.getByText("Tạo đề trống")).toBeTruthy();
  });

  it("KHÔNG thu một lượt hỏng lại — thu một lỗi lại là giấu lỗi", () => {
    const { container } = render(
      <Steps
        steps={[
          { mark: "done", title: "Tạo đề trống", result: "" },
          {
            mark: "failed",
            title: "Soạn câu hỏi",
            result: "— hàng đợi đang hỏng",
          },
        ]}
      />,
    );
    // Các bước hiện sẵn, và cái nút thu gọn không mời bấm.
    expect(screen.getByText("Soạn câu hỏi")).toBeTruthy();
    expect(screen.getByText("— hàng đợi đang hỏng")).toBeTruthy();
    expect(
      container.querySelector(".steps-head")?.hasAttribute("disabled"),
    ).toBe(true);
  });
});

describe("một lượt chỉ có lời", () => {
  it("giữ avatar và câu nói trong cùng một khối", async () => {
    // Lượt không gọi tool nào — trả lời một câu hỏi, chốt một lựa chọn — là trường hợp
    // thường gặp nhất. Tách nó làm hai khối sẽ đẩy câu nói xuống 20px dưới avatar của
    // chính nó, vì nhịp giữa hai khối là 20 còn nhịp avatar–lời là 6.
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(
              url.startsWith("/api/teacher/chat")
                ? {
                    kind: "assistant",
                    text: "Mình chưa rõ lớp nào.",
                    conversation_id: "c1",
                    choices: [],
                    more_choices: 0,
                    turns: [
                      blank({ kind: "teacher", text: "Tạo đề" }),
                      blank({
                        kind: "assistant",
                        text: "Mình chưa rõ lớp nào.",
                      }),
                    ],
                  }
                : [],
            ),
        }),
      ),
    );
    Element.prototype.scrollIntoView = vi.fn();
    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Mình chưa rõ lớp nào.")).toBeTruthy(),
    );

    const voices = document.querySelectorAll(".exchange .voice");
    expect(voices).toHaveLength(1);
    const only = voices[0];
    expect(only.querySelector(".who")).toBeTruthy();
    expect(only.querySelector(".reply-text")?.textContent).toBe(
      "Mình chưa rõ lớp nào.",
    );
  });
});

describe("một tool chưa có trong bảng", () => {
  it("không in định danh máy ra bề mặt giáo viên", () => {
    const step = stepFor(
      blank({
        kind: "tool_result",
        tool_name: "teacher.some_new_thing",
        tool_result: {},
      }),
    );
    expect(step.title).not.toMatch(/teacher\.|_/);
    expect(step.title).toBe("Một bước nữa");
  });
});

/**
 * Một `fetch` giả định tuyến theo URL, và ghi lại mọi lời gọi.
 *
 * `serve()` chỉ trả đúng một thân cho đường hội thoại và rỗng cho mọi đường khác, nên nó
 * không đủ cho rail: rail cần một danh sách đoạn chat, và hai endpoint mới thì cần đo được
 * **method** nào đã đi ra.
 *
 * @param answered - Thân cho `GET /teacher/chat`.
 * @param threads - Thân cho `GET /teacher/conversations`.
 * @returns Danh sách các lời gọi đã xảy ra.
 */
function routes(answered: unknown, threads: Record<string, unknown>[] = []) {
  const calls: { url: string; method: string; body: string }[] = [];
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      calls.push({
        url,
        method: (init?.method ?? "GET").toUpperCase(),
        body: typeof init?.body === "string" ? init.body : "",
      });
      let body: unknown = [];
      if (init?.method === "PATCH") {
        // BE trả về **hàng đã đổi**, nên bản giả cũng phải trả một hàng chứ không trả cả
        // danh sách: màn hình đọc `title` của nó để thay đúng một nhãn.
        body = { ...threads[0], ...JSON.parse(String(init.body)) };
      } else if (url.startsWith("/api/teacher/conversations")) body = threads;
      else if (url.startsWith("/api/teacher/chat")) body = answered;
      else if (url.startsWith("/api/teacher/documents")) body = [];
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    }),
  );
  return calls;
}

/** Một lượt soạn đề đã đợi xong: bước soạn mang ba con số thật. */
function drafted(written: number, asked: number, running = 0) {
  return {
    kind: "assistant",
    text: "Mình soạn xong rồi.",
    conversation_id: "c1",
    choices: [] as string[],
    more_choices: 0,
    turns: [
      blank({ kind: "teacher", text: "Tạo đề 3 câu về tích phân" }),
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: {
          created: true,
          assessment_id: "p1",
          title: "Tích phân",
          question_count: asked,
        },
      }),
      blank({
        kind: "tool_result",
        tool_name: "start_drafting",
        tool_result: {
          started: true,
          assessment_id: "p1",
          queued: asked,
          written,
          asked_for: asked,
          still_drafting: running,
        },
        entity_kind: "assessment",
        entity_id: "p1",
      }),
      blank({ kind: "assistant", text: "Mình soạn xong rồi." }),
    ],
  };
}

describe("thẻ kết quả của một lượt soạn đề", () => {
  it("mọc từ bước soạn đã đợi xong, và bấm vào thẻ thì mở đề", () => {
    const turns = drafted(3, 3).turns;

    // Trước đợt này `cardTurn` loại `start_drafting` vô điều kiện, `create_draft` bị loại vì
    // có bước soạn phía sau, và `draft_progress` là tool của pha 1 nên một plan không gọi
    // nó — ba lần loại trừ giao nhau đúng ở đường đi hạnh phúc, và một lượt soạn đề THÀNH
    // CÔNG kết thúc không thẻ nào. Mà panel đề chỉ mở được từ một nút trên thẻ, nên Kriky
    // nói "đã soạn xong" và màn hình không có cửa nào vào xem. Đo được trên hội thoại thật.
    const card = cardTurn(turns);
    expect(card?.tool_name).toBe("start_drafting");

    const opened: string[] = [];
    render(
      <ActionCard
        turn={card!}
        onOpen={(paper) => opened.push(paper)}
        onCompose={() => undefined}
      />,
    );
    expect(screen.getByText("Đã thêm 3 câu vào đề")).toBeTruthy();
    // Không nút nào: `Duyệt đề`, `Xem đề` và `Xem` đều gọi đúng một hàm, nên năm nhãn
    // cho một việc rút về chính cái thẻ.
    expect(screen.queryByText("Duyệt đề")).toBeNull();
    expect(screen.queryByText("Xem đề")).toBeNull();

    fireEvent.click(screen.getByText("Đã thêm 3 câu vào đề"));
    expect(opened).toEqual(["p1"]);
  });

  it("đề thiếu câu thì KHÔNG mời duyệt", () => {
    // Cùng một luật đã đứng trong `reporting._progress` của AGENT: duyệt một đề thiếu câu là
    // phát hành một bài kiểm tra dở. Lời kể và thẻ phải nói cùng một câu.
    const card = cardTurn(drafted(2, 10).turns);

    render(
      <ActionCard
        turn={card!}
        onOpen={() => undefined}
        onCompose={() => undefined}
      />,
    );
    // Luật *"đề thiếu câu thì không mời duyệt"* trước đây sống trong nhãn nút. Nút đã
    // bỏ, nên nó sống ở **chữ đầu đề**: `Dừng ở 2/10 câu` không mời gì cả, và cổng duyệt
    // thật thì nằm ở chân panel, nơi duy nhất đọc được trạng thái hiện tại của đề.
    expect(screen.getByText("Dừng ở 2/10 câu")).toBeTruthy();
    expect(screen.queryByText("Duyệt đề")).toBeNull();
  });

  it("bước soạn CHƯA đợi xong thì không mọc thẻ nào", () => {
    // Cửa `POST` không đợi, nên kết quả ở đó không có con số nào. Một thẻ dựng từ đó sẽ nói
    // "Đã thêm 0 câu vào đề" cho một đề sắp có đủ câu.
    const turns = [
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: { created: true, title: "Tích phân", question_count: 10 },
      }),
      blank({
        kind: "tool_result",
        tool_name: "start_drafting",
        tool_result: { started: true, queued: 10 },
      }),
    ];
    expect(cardTurn(turns)).toBeNull();
  });

  it("đề còn câu đang soạn thì KHÔNG mời duyệt, và nói đủ hai con số", () => {
    // Đường ra có thật: hết hạn im lặng thì `_wait_for_questions` rời vòng nghe với
    // `still_drafting > 0`. Bản đầu coi "thiếu câu" là `written < asked && running === 0`,
    // nên ca này rơi vào nhánh còn lại — thẻ in `Đã thêm 3 câu vào đề`, giấu mất số 10, và
    // mời **Duyệt đề** cho một đề mới có 3/10 câu. Lời kể của AGENT trong cùng ca ấy chỉ
    // được nói "đang soạn": hai câu ngược nhau trên cùng một màn hình.
    const card = cardTurn(drafted(3, 10, 7).turns);

    render(
      <ActionCard
        turn={card!}
        onOpen={() => undefined}
        onCompose={() => undefined}
      />,
    );
    expect(screen.getByText("Đã soạn 3/10 câu")).toBeTruthy();
    expect(screen.queryByText("Duyệt đề")).toBeNull();
  });

  it("dòng dưới bước nói cùng một câu với BE, cả ba nhánh", () => {
    // `detail` do BE gửi lúc lượt đang chạy, `tool_result` đã lưu sau một lần F5 — hai
    // đường, một bước. Lệch một chữ là một lần tải lại làm đổi nghĩa một việc đã xong, nên
    // cả ba nhánh của `_how_many` đều phải được soi lại, không chỉ nhánh đi-đúng-đường.
    const line = (written: number, asked: number, running: number) =>
      stepFor(
        blank({
          kind: "tool_result",
          tool_name: "start_drafting",
          tool_result: {
            started: true,
            written,
            asked_for: asked,
            still_drafting: running,
          },
        }),
      ).result;

    expect(line(3, 3, 0)).toBe("— đã soạn 3/3 câu");
    expect(line(3, 10, 7)).toBe("— đã soạn 3/10 câu, còn 7 câu đang chạy");
    expect(line(2, 10, 0)).toBe("— dừng ở 2/10 câu");
  });
});

describe("câu hỏi lại sau một lần tải lại", () => {
  it("các nút vẫn còn, và câu hỏi không hiện hai lần", async () => {
    // Trước đợt này `choices` chỉ sống trong response: `teacher_turns` không có cột nào cho
    // chúng, nên `GET /teacher/chat` không bao giờ trả chúng — và `asked` được set từ chính
    // đường ấy. Tức thẻ hỏi lại có thể CHƯA BAO GIỜ hiện, không chỉ sau F5.
    routes({
      kind: "say",
      text: "",
      conversation_id: "c1",
      choices: ["12A (3 học sinh)", "12B (1 học sinh)"],
      more_choices: 0,
      turns: [
        blank({ kind: "teacher", text: "lớp 12 thế nào" }),
        blank({
          kind: "assistant",
          text: "Bạn muốn xem lớp nào?",
          choices: ["12A (3 học sinh)", "12B (1 học sinh)"],
        }),
      ],
    });

    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );

    await waitFor(() =>
      expect(document.querySelector(".clarify")).not.toBeNull(),
    );
    expect(screen.getByText("12A (3 học sinh)")).toBeTruthy();
    expect(screen.getByText("12B (1 học sinh)")).toBeTruthy();
    // Câu hỏi là tiêu đề của thẻ, và nó cũng là một lượt trong `turns`. Vẽ cả hai thì cùng
    // một câu hiện hai lần cách nhau 12px.
    expect(screen.getAllByText("Bạn muốn xem lớp nào?")).toHaveLength(1);
  });
});

describe("rail: đổi tên và xoá một đoạn chat", () => {
  const THREADS = [
    {
      conversation_id: "c1",
      title: "Tên model đặt sai",
      started_at: "2026-10-01T00:00:00+00:00",
      last_spoke_at: "2026-10-03T00:00:00+00:00",
    },
    {
      conversation_id: "c2",
      title: "Đoạn khác",
      started_at: "2026-10-01T00:00:00+00:00",
      last_spoke_at: "2026-10-02T00:00:00+00:00",
    },
  ];

  it("gõ tên mới rồi Enter thì gửi PATCH và hàng đổi nhãn", async () => {
    const calls = routes(SPOKEN, THREADS);
    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Tên model đặt sai")).toBeTruthy(),
    );

    fireEvent.click(screen.getByLabelText("Tuỳ chọn cho Tên model đặt sai"));
    fireEvent.click(screen.getByText("Đổi tên"));
    const box = screen.getByLabelText("Tên đoạn chat");
    fireEvent.change(box, { target: { value: "Đề giữa kỳ 12A" } });
    fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() =>
      expect(screen.getByText("Đề giữa kỳ 12A")).toBeTruthy(),
    );
    const patch = calls.find((one) => one.method === "PATCH");
    expect(patch?.url).toBe("/api/teacher/conversations/c1");
    expect(JSON.parse(patch?.body ?? "{}")).toEqual({
      title: "Đề giữa kỳ 12A",
    });
  });

  it("xoá phải qua hộp xác nhận, và chỉ sau khi xác nhận mới gửi DELETE", async () => {
    // Xoá bên BE là xoá mềm, nhưng trên màn hình này không có nút hoàn tác nào — nên với
    // người bấm nút nó là việc một chiều, và nó đi qua hộp xác nhận y như việc phát hành.
    const calls = routes(SPOKEN, THREADS);
    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("Đoạn khác")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Tuỳ chọn cho Đoạn khác"));
    fireEvent.click(screen.getByText("Xoá"));

    // Hộp đã mở, nhưng chưa có gì bị xoá.
    expect(screen.getByText("Xoá đoạn chat này?")).toBeTruthy();
    expect(calls.some((one) => one.method === "DELETE")).toBe(false);

    // Và đường thoát phải thoát thật.
    fireEvent.click(screen.getByText("Giữ lại"));
    expect(screen.queryByText("Xoá đoạn chat này?")).toBeNull();
    expect(calls.some((one) => one.method === "DELETE")).toBe(false);

    fireEvent.click(screen.getByLabelText("Tuỳ chọn cho Đoạn khác"));
    fireEvent.click(screen.getByText("Xoá"));
    fireEvent.click(screen.getByText("Xoá đoạn chat"));

    await waitFor(() => expect(screen.queryByText("Đoạn khác")).toBeNull());
    const erased = calls.find((one) => one.method === "DELETE");
    expect(erased?.url).toBe("/api/teacher/conversations/c2");
    // Đoạn còn lại không bị kéo theo.
    expect(screen.getByText("Tên model đặt sai")).toBeTruthy();
  });
});

describe("rail: khi BE từ chối", () => {
  const THREAD = [
    {
      conversation_id: "c1",
      title: "Đoạn duy nhất",
      started_at: "2026-10-01T00:00:00+00:00",
      last_spoke_at: "2026-10-03T00:00:00+00:00",
    },
  ];

  /** Như `routes`, nhưng mọi request không-GET đều hỏng với câu của BE. */
  function refusing(detail: string, status: number) {
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const method = (init?.method ?? "GET").toUpperCase();
        if (method !== "GET") {
          return Promise.resolve({
            ok: false,
            status,
            json: () => Promise.resolve({ detail }),
          });
        }
        let body: unknown = [];
        if (url.startsWith("/api/teacher/conversations")) body = THREAD;
        else if (url.startsWith("/api/teacher/chat")) body = SPOKEN;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }),
    );
  }

  it("một tên bị từ chối thì hàng trở về tên cũ, và câu của BE hiện ra", async () => {
    // Nhãn được đổi **trước** khi BE trả lời, nên đường lùi lại phải có thật. Không có nó
    // thì rail đứng mãi với một cái tên database không hề có.
    refusing("tên đoạn chat không được để trống", 400);
    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("Đoạn duy nhất")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Tuỳ chọn cho Đoạn duy nhất"));
    fireEvent.click(screen.getByText("Đổi tên"));
    const box = screen.getByLabelText("Tên đoạn chat");
    fireEvent.change(box, { target: { value: "Tên mới" } });
    fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() =>
      expect(
        screen.getByText("tên đoạn chat không được để trống"),
      ).toBeTruthy(),
    );
    expect(screen.getByText("Đoạn duy nhất")).toBeTruthy();
    expect(screen.queryByText("Tên mới")).toBeNull();
  });

  it("xoá hỏng thì đoạn ở lại rail, và hộp xác nhận đóng", async () => {
    refusing("không tìm thấy đoạn chat này", 404);
    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("Đoạn duy nhất")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Tuỳ chọn cho Đoạn duy nhất"));
    fireEvent.click(screen.getByText("Xoá"));
    fireEvent.click(screen.getByText("Xoá đoạn chat"));

    await waitFor(() =>
      expect(screen.getByText("không tìm thấy đoạn chat này")).toBeTruthy(),
    );
    expect(screen.getByText("Đoạn duy nhất")).toBeTruthy();
    expect(screen.queryByText("Xoá đoạn chat này?")).toBeNull();
  });

  it("chỉ MỘT menu mở một lúc, và bấm ra ngoài thì nó đóng", async () => {
    const calls = routes(SPOKEN, [
      ...THREAD,
      {
        conversation_id: "c2",
        title: "Đoạn thứ hai",
        started_at: "2026-10-01T00:00:00+00:00",
        last_spoke_at: "2026-10-02T00:00:00+00:00",
      },
    ]);
    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("Đoạn thứ hai")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Tuỳ chọn cho Đoạn duy nhất"));
    fireEvent.click(screen.getByLabelText("Tuỳ chọn cho Đoạn thứ hai"));
    // Hai menu mở cùng lúc là hai lần chữ *Xoá* trên màn hình.
    expect(screen.getAllByText("Xoá")).toHaveLength(1);

    fireEvent.pointerDown(document.body);
    await waitFor(() => expect(screen.queryByText("Xoá")).toBeNull());
    expect(calls.some((one) => one.method !== "GET")).toBe(false);
  });
});

describe("tải một tài liệu lên", () => {
  it("tệp vừa tải lên hiện trên rail, và dải dưới ô nhập nói đúng việc đã xảy ra", async () => {
    // Dải này từng in "Đổi phạm vi", và chữ ấy hứa một việc không xảy ra: thân request gửi
    // đi đúng ba field và không có `document_id` nào, chưa đoạn code nào mở tệp ra đọc.
    const saved = {
      document_id: "d1",
      filename: "de-cuong.pdf",
      kind: "PDF",
      byte_size: 2048,
      uploaded_at: "2026-10-03T00:00:00+00:00",
    };
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        let body: unknown = [];
        if (url.startsWith("/api/teacher/documents") && init?.method === "POST")
          body = saved;
        else if (url.startsWith("/api/teacher/chat")) body = SPOKEN;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }),
    );

    const { container } = render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy(),
    );

    const picker = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    fireEvent.change(picker, {
      target: {
        files: [new File(["x"], "de-cuong.pdf", { type: "application/pdf" })],
      },
    });

    await waitFor(() => expect(screen.getByText("de-cuong.pdf")).toBeTruthy());
    expect(screen.getByText("Đã tải lên: de-cuong.pdf")).toBeTruthy();
    expect(screen.queryByText("Đổi phạm vi")).toBeNull();
    // Tải lên có **một** cửa: cái icon cạnh nhãn TÀI LIỆU. Dải này chỉ nói tệp nào vừa
    // lên, nó không phải một cửa thứ hai — hai cửa cho cùng một việc thì cửa nào cũng
    // thành chỗ phải đoán.
    expect(screen.queryByText("Tải tệp khác")).toBeNull();
    expect(container.querySelectorAll(".scope-strip button").length).toBe(0);
  });
});

/** Một đề đủ để panel vẽ được, ở trạng thái gọi tên. */
function paper(state: string) {
  return {
    assessment_id: "p1",
    title: "Kiểm tra 15 phút — Hàm số",
    subject: "Toán",
    grade: "12",
    state,
    question_count: 1,
    still_drafting: 0,
    topic_scope: "chương Hàm số",
    difficulty: "",
    conversation_id: "c1",
    questions: [
      {
        question_id: "q1",
        order: 1,
        stem: "Đạo hàm của y = x² + 3x là gì?",
        learning_objective: "đạo hàm đa thức",
        options: [
          { label: "A", text: "2x + 3", is_correct: true, error_label: null },
          {
            label: "B",
            text: "x + 3",
            is_correct: false,
            error_label: "quên hệ số",
          },
        ],
        methods: [{ title: "Cách 1", body: "Đạo hàm từng hạng tử." }],
      },
    ],
  };
}

describe("chân panel đề", () => {
  /** Stub `fetch` trả về một đề ở trạng thái cho trước, và ghi lại mọi lời gọi. */
  function serving(state: string) {
    const calls: { url: string; method: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        calls.push({ url, method: (init?.method ?? "GET").toUpperCase() });
        // Màn cài đặt phát hành đọc một hình dạng khác hẳn. Trả đề cho cả hai đường thì
        // nó nổ ở chỗ render, và cú nổ ấy nói về cái stub chứ không nói về panel.
        const body = url.includes("/publish-form") ? FORM : paper(state);
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(body),
        });
      }),
    );
    return calls;
  }

  it("đề chưa duyệt: một nút Duyệt đề, không có đường lùi nào", async () => {
    serving("has_questions");
    render(
      <Panel
        assessmentId="p1"
        publishing={false}
        onPublish={() => {}}
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText("Duyệt đề")).toBeTruthy());
    expect(screen.queryByText("Hoàn tác")).toBeNull();
    expect(screen.queryByText("Phát hành đề")).toBeNull();
  });

  it("đề đã duyệt: đúng MỘT nút, và đường lùi không còn ở chân panel", async () => {
    // Duyệt xong là sang thẳng cài đặt phát hành, nên trạng thái "đã duyệt mà chưa mở
    // cài đặt" thôi làm một chặng dừng. Nó vẫn tới được — mở lại một đề đã duyệt từ đoạn
    // chat cũ, hoặc đóng màn 7 — và khi ấy chân panel chỉ còn một việc: mở lại màn 7.
    // `Hoàn tác` sống ở màn 7, một việc một chỗ.
    serving("approved");
    const opened: string[] = [];
    const { container } = render(
      <Panel
        assessmentId="p1"
        publishing={false}
        onPublish={() => opened.push("phát hành")}
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText("Phát hành đề")).toBeTruthy());
    expect(screen.queryByText("Hoàn tác")).toBeNull();
    expect(container.querySelectorAll(".panel-foot button").length).toBe(1);

    fireEvent.click(screen.getByText("Phát hành đề"));
    expect(opened).toEqual(["phát hành"]);
  });

  it("đề ĐÃ PHÁT HÀNH không mời Hoàn tác, vì bỏ duyệt ở đó chắc chắn 409", async () => {
    // `POST .../unapprove` chỉ nhận đúng `APPROVED` (`teacher_routes.py:403`). Gộp
    // `published` vào `approved` làm nút `Hoàn tác` hiện ra cho một đề đã tới tay học
    // sinh, và cú bấm ấy chắc chắn trả 409 — đúng khuyết điểm mà đợt này đi sửa, chỉ dịch
    // sang một trạng thái khác. Đường lùi của đề đã phát hành là **thu hồi**.
    serving("published");
    render(
      <Panel
        assessmentId="p1"
        publishing={false}
        onPublish={() => {}}
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText("Phát hành thêm lớp")).toBeTruthy());
    expect(screen.queryByText("Hoàn tác")).toBeNull();
    // Và câu dưới chân nói đúng đường mở lại.
    expect(screen.getByText(/thu hồi khỏi mọi lớp/)).toBeTruthy();
  });

  it("duyệt xong là sang THẲNG cài đặt phát hành, không dừng ở giữa", async () => {
    // Trước đợt này cú bấm `Duyệt đề` chỉ đổi chân panel thành hai nút rồi đứng im — một
    // chặng dừng không có việc gì của riêng nó, và giáo viên phải bấm thêm một lần nữa
    // để tới đúng chỗ họ đang đi tới. Luồng thiết kế là màn 6 → màn 7.
    serving("has_questions");
    const went: string[] = [];
    render(
      <Panel
        assessmentId="p1"
        publishing={false}
        onPublish={() => went.push("màn 7")}
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("Duyệt đề")).toBeTruthy());

    fireEvent.click(screen.getByText("Duyệt đề"));

    await waitFor(() => expect(went).toEqual(["màn 7"]));
  });

  it("bấm Hoàn tác ở màn cài đặt phát hành gọi đúng endpoint bỏ duyệt", async () => {
    // `teacher.unapprove` có trong `api.ts` từ lâu và chưa một dòng nào gọi nó. Nay nó
    // được gọi từ màn 7 — chỗ giáo viên nhìn thấy ngay sau cú bấm duyệt.
    const calls = serving("approved");
    render(
      <Panel
        assessmentId="p1"
        publishing
        onPublish={() => {}}
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("Hoàn tác")).toBeTruthy());

    fireEvent.click(screen.getByText("Hoàn tác"));

    await waitFor(() =>
      expect(
        calls.some(
          (one) => one.url.endsWith("/unapprove") && one.method === "POST",
        ),
      ).toBe(true),
    );
  });
});

describe("lời giải mở thành hộp thoại", () => {
  /** Stub `fetch` trả về một đề đã duyệt với một câu đủ lời giải và nhãn lỗi. */
  function serving() {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(paper("approved")),
        }),
      ),
    );
  }

  async function opened() {
    serving();
    const view = render(
      <Panel
        assessmentId="p1"
        publishing={false}
        onPublish={() => {}}
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText(/Lời giải · 1 cách/)).toBeTruthy(),
    );
    fireEvent.click(screen.getByText(/Lời giải · 1 cách/));
    await waitFor(() =>
      expect(document.querySelector(".confirm.wide")).not.toBeNull(),
    );
    return view;
  }

  it("hiện đủ cách giải VÀ ánh xạ nhiễu — thứ panel chưa bao giờ vẽ", async () => {
    // `error_label` nằm trong response từ lâu mà không chỗ nào hiện nó. Đó là phần nói cho
    // giáo viên biết mỗi phương án sai sai ở đâu, tức phần đáng đọc nhất của lời giải —
    // và nó không vừa một cột rộng 380, nên nó là lý do hộp thoại tồn tại.
    await opened();

    expect(screen.getByText("Lời giải — Câu 1")).toBeTruthy();
    expect(screen.getByText("Đạo hàm từng hạng tử.")).toBeTruthy();
    expect(screen.getByText("MỖI PHƯƠNG ÁN NHIỄU GẮN MỘT LỖI")).toBeTruthy();
    expect(screen.getByText("quên hệ số")).toBeTruthy();
    expect(screen.getByText("✓ đúng")).toBeTruthy();
  });

  // Ba đường đóng dưới đây **không có ở bất kỳ hộp thoại nào** của bề mặt giáo viên trước
  // đợt này — ba bản sao cùng thiếu cùng ba thứ, tức một khuôn chưa được rút ra. Mỗi đường
  // một test, vì ba lần `render` trong một test để lại ba cây DOM và phép tìm bắt nhầm cây.
  it("đóng bằng nút Đóng", async () => {
    await opened();
    // Panel-head cũng có một nút `Đóng`, nên phải nhắm vào nút trong hộp.
    fireEvent.click(document.querySelector(".confirm.wide .close") as Element);
    await waitFor(() =>
      expect(document.querySelector(".confirm.wide")).toBeNull(),
    );
  });

  it("đóng bằng Esc", async () => {
    await opened();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() =>
      expect(document.querySelector(".confirm.wide")).toBeNull(),
    );
  });

  it("đóng bằng cách bấm ra ngoài", async () => {
    await opened();
    fireEvent.click(document.querySelector(".veil") as Element);
    await waitFor(() =>
      expect(document.querySelector(".confirm.wide")).toBeNull(),
    );
  });

  it("bấm TRONG hộp thì hộp ở lại", async () => {
    await opened();
    fireEvent.click(screen.getByText("Lời giải — Câu 1"));
    expect(document.querySelector(".confirm.wide")).not.toBeNull();
  });
});


describe("Chat mở panel đề", () => {
  it("duyệt xong thì đọc lại ĐÚNG đoạn đang mở, không phải đoạn đang chạy", async () => {
    // Đây là sửa chính của Pha 2 cho `Chat.tsx`, và nó chưa có một dòng test nào: mọi lần
    // `teacher.test.tsx` render `Chat` đều truyền `openPaper={null}`, nên `Panel` chưa bao
    // giờ được mount từ `Chat` và cả dây nối nằm ngoài lưới.
    //
    // Hỏng ra sao: `teacher.conversation()` không id nghĩa là *đoạn đang chạy*. Duyệt một
    // đề mở từ một đoạn cũ sẽ ghi lượt của đoạn khác đè lên màn hình.
    const calls: string[] = [];
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        calls.push(`${(init?.method ?? "GET").toUpperCase()} ${url}`);
        let body: unknown = [];
        if (url.includes("/teacher/assessments/")) body = paper("has_questions");
        else if (url.startsWith("/api/teacher/chat")) body = SPOKEN;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }),
    );

    render(<Chat conversationId="c1" fresh={false} openPaper="p1" publishing={false} />);
    await waitFor(() => expect(screen.getByText("Duyệt đề")).toBeTruthy());

    fireEvent.click(screen.getByText("Duyệt đề"));

    await waitFor(() =>
      expect(calls.some((one) => one.includes("/approve"))).toBe(true),
    );
    await waitFor(() =>
      expect(
        calls.some((one) => one.includes("/teacher/chat?conversation_id=c1")),
      ).toBe(true),
    );
    // Và **không** được gọi đường không-id, vì đường ấy trả đoạn đang chạy.
    expect(calls.filter((one) => one === "GET /api/teacher/chat")).toEqual([]);
  });
});


describe("tài liệu thuộc về giáo viên, không thuộc đoạn chat", () => {
  const FILES = [
    {
      document_id: "d1",
      filename: "de-cuong.pdf",
      kind: "PDF",
      byte_size: 2048,
      uploaded_at: "2026-10-03T00:00:00+00:00",
    },
  ];

  function serving() {
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        let body: unknown = [];
        if (url.startsWith("/api/teacher/documents")) body = FILES;
        else if (url.startsWith("/api/teacher/chat")) body = SPOKEN;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }),
    );
  }

  it("nút tải lên nằm trên đầu ngăn TÀI LIỆU, không nằm ở thanh chat", async () => {
    // Tài liệu thuộc về **giáo viên** và nằm trong kho chung (ADR-04) — nó không thuộc về
    // một đoạn chat nào. Đặt nút tải lên ở composer là nói ngược lại điều đó.
    serving();
    const { container } = render(
      <Chat conversationId="c1" fresh={false} openPaper={null} publishing={false} />,
    );
    await waitFor(() => expect(screen.getByText("de-cuong.pdf")).toBeTruthy());

    const upload = screen.getByLabelText("Tải tài liệu lên");
    expect(upload.closest(".pane.documents")).not.toBeNull();
    expect(upload.closest(".composer-bar")).toBeNull();
    expect(screen.queryByText("＋ Tài liệu")).toBeNull();
    expect(container.querySelector(".composer-bar .attach")).toBeNull();
  });

  it("kéo một chip tài liệu thả vào ô nhập thì nó được đính vào câu", async () => {
    serving();
    const { container } = render(
      <Chat conversationId="c1" fresh={false} openPaper={null} publishing={false} />,
    );
    await waitFor(() => expect(screen.getByText("de-cuong.pdf")).toBeTruthy());

    const chip = container.querySelector(".pane.documents .document") as HTMLElement;
    expect(chip.getAttribute("draggable")).toBe("true");

    // Một `DataTransfer` giả: jsdom không dựng sẵn cái thật.
    const held: Record<string, string> = {};
    const dataTransfer = {
      types: ["text/kriky-document"],
      setData: (kind: string, value: string) => {
        held[kind] = value;
      },
      getData: (kind: string) => held[kind] ?? "",
      effectAllowed: "",
      dropEffect: "",
    };

    fireEvent.dragStart(chip, { dataTransfer });
    expect(held["text/kriky-document"]).toBe("d1");

    const bar = container.querySelector(".composer-bar") as HTMLElement;
    fireEvent.dragOver(bar, { dataTransfer });
    expect(bar.className).toContain("dropping");

    fireEvent.drop(bar, { dataTransfer });
    await waitFor(() => expect(screen.getByText("Đã tải lên: de-cuong.pdf")).toBeTruthy());
    expect((container.querySelector(".composer-bar") as HTMLElement).className).not.toContain(
      "dropping",
    );
  });
});


describe("sửa chữ của một câu", () => {
  /** Stub `fetch`; `refuse` khác rỗng thì PATCH trả 422 với câu ấy. */
  function serving(state: string, refuse = "") {
    const calls: { url: string; method: string; body: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const method = (init?.method ?? "GET").toUpperCase();
        calls.push({ url, method, body: typeof init?.body === "string" ? init.body : "" });
        if (method === "PATCH" && refuse) {
          return Promise.resolve({
            ok: false,
            status: 422,
            json: () => Promise.resolve({ detail: refuse }),
          });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve(paper(state)) });
      }),
    );
    return calls;
  }

  function mount() {
    return render(
      <Panel
        assessmentId="p1"
        publishing={false}
        onPublish={() => {}}
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
  }

  it("nút Sửa thôi là nút chết: nó mở một ô soạn tại chỗ", async () => {
    // Nút này đã nằm trên panel từ lâu **không có `onClick`**.
    serving("has_questions");
    mount();
    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());

    fireEvent.click(screen.getByText("Sửa"));

    expect(screen.getByLabelText("Đề bài")).toBeTruthy();
    expect(screen.getByLabelText("Phương án A")).toBeTruthy();
    expect(screen.getByText("Đang sửa")).toBeTruthy();
    // Chip nguồn **ở lại**: biết câu này lấy từ đâu là thứ cần nhất đúng lúc đang sửa nó.
    expect(document.querySelector(".qcard.editing .source-chip")).not.toBeNull();
  });

  it("đề đã duyệt thì không có nút Sửa nào (ADR-01)", async () => {
    serving("approved");
    mount();
    await waitFor(() => expect(screen.getByText("Phát hành đề")).toBeTruthy());
    expect(screen.queryByText("Sửa")).toBeNull();
  });

  it("Lưu gửi CẢ câu đi, không gửi từng mảnh", async () => {
    // ADR-18 là một luật về quan hệ giữa các mảnh, nên gửi từng mảnh rời là cho câu hỏi đi
    // qua những trạng thái không ai kiểm được.
    const calls = serving("has_questions");
    mount();
    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());
    fireEvent.click(screen.getByText("Sửa"));

    fireEvent.change(screen.getByLabelText("Đề bài"), {
      target: { value: "Đạo hàm của $y = x^3$ là gì?" },
    });
    fireEvent.click(screen.getByText("Lưu"));

    await waitFor(() => expect(calls.some((one) => one.method === "PATCH")).toBe(true));
    const sent = calls.find((one) => one.method === "PATCH")!;
    expect(sent.url).toBe("/api/teacher/assessments/p1/questions/q1");
    const body = JSON.parse(sent.body);
    expect(body.stem).toBe("Đạo hàm của $y = x^3$ là gì?");
    expect(body.options).toHaveLength(2);
    expect(body.methods).toHaveLength(1);
  });

  it("BE từ chối thì câu từ chối hiện NGAY DƯỚI ô gõ, và ô vẫn mở", async () => {
    // Đẩy nó lên dòng chung ở chân panel thì nó đứng xa chỗ gõ và không nói nó nói về câu
    // nào — mà panel có thể đang hiện mười thẻ.
    serving("has_questions", "math in stem is not delimited");
    mount();
    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());
    fireEvent.click(screen.getByText("Sửa"));
    fireEvent.click(screen.getByText("Lưu"));

    await waitFor(() =>
      expect(screen.getByText("math in stem is not delimited")).toBeTruthy(),
    );
    expect(screen.getByLabelText("Đề bài")).toBeTruthy();
  });

  it("Huỷ đóng ô soạn và không gửi gì", async () => {
    const calls = serving("has_questions");
    mount();
    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());
    fireEvent.click(screen.getByText("Sửa"));
    fireEvent.change(screen.getByLabelText("Đề bài"), { target: { value: "bỏ đi" } });
    fireEvent.click(screen.getByText("Huỷ"));

    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());
    expect(screen.queryByLabelText("Đề bài")).toBeNull();
    expect(calls.some((one) => one.method === "PATCH")).toBe(false);
  });
});

describe("việc giáo viên tự làm không phải một bước của model", () => {
  /** Một đoạn chat trong đó giáo viên đã bấm *Duyệt đề* trên panel. */
  const APPROVED = {
    kind: "assistant",
    text: "Đã tạo xong đề.",
    conversation_id: "c1",
    choices: [],
    more_choices: 0,
    turns: [
      blank({ kind: "teacher", text: "Tạo đề cho 12A" }),
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: { assessment_id: "p1", title: "Hàm số" },
      }),
      blank({ kind: "assistant", text: "Đã tạo xong đề." }),
      blank({
        kind: "tool_result",
        tool_name: "teacher.approve",
        tool_result: { assessment_id: "p1", title: "Hàm số", questions: 10 },
        entity_kind: "assessment",
        entity_id: "p1",
      }),
    ],
  };

  afterEach(() => vi.unstubAllGlobals());

  function serving() {
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        let body: unknown = [];
        if (url.startsWith("/api/teacher/chat")) body = APPROVED;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }),
    );
  }

  it("lượt duyệt KHÔNG mọc một dòng trong khối bước", async () => {
    // Đo được trên trình duyệt: một cú bấm *Duyệt đề* hiện **hai lần** — một dòng `Duyệt
    // đề` trong khối `Thinking` và một cái thẻ. Khối ấy là bằng chứng **model** đã làm gì;
    // một dòng của giáo viên nằm trong đó nói rằng Kriky tự duyệt đề.
    serving();
    const { container } = render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText(/Đã duyệt đề/)).toBeTruthy(),
    );

    // Khối đã xong thì tự thu lại còn một dòng đếm, nên con số ấy **là** thứ giáo viên
    // nhìn thấy. Hai bước nghĩa là lượt duyệt đã lọt vào; một bước là đúng.
    expect(screen.getByText("Đã làm 1 bước")).toBeTruthy();
    expect(screen.queryByText("Đã làm 2 bước")).toBeNull();

    fireEvent.click(screen.getByText("Đã làm 1 bước"));
    const steps = [...container.querySelectorAll(".step-said .title")].map(
      (one) => one.textContent,
    );
    expect(steps).toEqual(["Tạo đề trống"]);
  });

  it("nhưng biên bản vẫn còn: nó lên thẻ (ADR-24)", async () => {
    // Nửa kia của cùng một luật. Bỏ lượt duyệt khỏi khối bước mà cũng bỏ luôn cái thẻ thì
    // việc giáo viên vừa làm biến mất khỏi dòng hội thoại — đúng thứ ADR-24 cấm.
    serving();
    const { container } = render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText(/Đã duyệt đề/)).toBeTruthy(),
    );
    expect(container.querySelector(".action-card")).toBeTruthy();
  });
});

describe("thẻ của một việc giáo viên tự làm là biên bản, không phải bộ điều khiển", () => {
  /**
   * Dựng thẻ cho một tool bất kỳ.
   *
   * @param name - Tên tool.
   * @param result - Thân `tool_result`.
   * @param onOpen - Chỗ nhận cú bấm, nếu test cần đo.
   */
  function card(
    name: string,
    result: Record<string, unknown>,
    onOpen: (paper: string) => void = () => {},
    paper = "p1",
  ) {
    return render(
      <ActionCard
        turn={blank({
          kind: "tool_result",
          tool_name: name,
          tool_result: result,
          entity_kind: "assessment",
          entity_id: paper,
        })}
        onOpen={onOpen}
        onCompose={() => {}}
      />,
    );
  }

  it("thẻ đã duyệt không còn nút nào, và chính nó mở đề", () => {
    // Ba nút cũ (*Phát hành*, *Hoàn tác*, *Duyệt đề*) đều **không chạy**, đo được: duyệt
    // thì bấm từ trong panel, nên lúc thẻ hiện ra route đã là `.../de/{paper}`, và cả ba
    // chỉ gọi `go()` tới đúng route ấy — gán lại một hash không đổi thì trình duyệt không
    // bắn `hashchange` nào. Sửa không phải nối lại dây: chỗ đổi trạng thái một đề là chân
    // panel, nơi duy nhất nói trạng thái **hiện tại**.
    const opened: string[] = [];
    const { container } = card(
      "teacher.approve",
      { assessment_id: "p1", title: "Hàm số", questions: 10 },
      (paper) => opened.push(paper),
    );

    expect(container.querySelectorAll(".actions .btn").length).toBe(0);
    // Thẻ là cái nút. `role="button"` + `tabIndex` chứ không phải một `<button>` bọc
    // ngoài: thẻ chứa nút, và một nút lồng trong nút là HTML sai.
    const shown = container.querySelector(".action-card")!;
    expect(shown.getAttribute("role")).toBe("button");
    expect(shown.getAttribute("tabindex")).toBe("0");

    fireEvent.click(shown);
    expect(opened).toEqual(["p1"]);

    // Và bàn phím đi được cùng đường.
    fireEvent.keyDown(shown, { key: "Enter" });
    expect(opened).toEqual(["p1", "p1"]);
  });

  it("thẻ bỏ duyệt cũng vậy", () => {
    const { container } = card("teacher.unapprove", {
      assessment_id: "p1",
      title: "Hàm số",
    });
    expect(container.querySelectorAll(".actions .btn").length).toBe(0);
    expect(container.querySelector(".action-card.open-able")).toBeTruthy();
  });

  it("thẻ KHÔNG có đề thì nằm yên, không giả làm nút", () => {
    // Một thẻ bấm được mà chẳng mở gì tệ hơn hẳn một thẻ nằm yên: nó hứa một cửa rồi
    // nuốt cú bấm. `paper` rỗng là ca ấy.
    const { container } = card("teacher.approve", {}, () => {}, "");
    const one = container.querySelector(".action-card")!;
    expect(one.getAttribute("role")).toBeNull();
    expect(one.classList.contains("open-able")).toBe(false);
  });

  it("và không thẻ nào còn dòng chi tiết người dùng đã bỏ", () => {
    for (const [name, gone] of [
      ["teacher.approve", "nội dung đã khoá"],
      ["teacher.unapprove", "Sửa lại được rồi"],
    ]) {
      const { container, unmount } = card(name, {
        assessment_id: "p1",
        title: "Hàm số",
        questions: 10,
      });
      expect(container.querySelector(".detail")).toBeNull();
      expect(container.textContent).not.toContain(gone);
      // Câu an toàn thì **ở lại**: nó nói đề đã tới tay học sinh chưa, và đó là thứ duy
      // nhất trên thẻ mà giáo viên không đoán được từ chỗ khác.
      expect(container.querySelector(".safety")).toBeTruthy();
      unmount();
    }
  });
});

describe("kéo để đổi bề rộng hai cột", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  function serving() {
    Element.prototype.scrollIntoView = vi.fn();
    // jsdom không có Pointer Capture. Không có hai hàm này thì `onPointerDown` ném, và
    // cú ném ấy nói về jsdom chứ không nói gì về thanh kéo.
    Element.prototype.setPointerCapture = vi.fn();
    Element.prototype.releasePointerCapture = vi.fn();
    // Và nó cũng không có `PointerEvent`. Thiếu lớp ấy thì `fireEvent.pointerMove` rơi về
    // một `Event` trần, `clientX` không đi theo, và phép đo nhận `NaN` — một cái bẫy của
    // môi trường test, không phải một lời nói gì về thanh kéo.
    vi.stubGlobal("PointerEvent", MouseEvent);
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        let body: unknown = [];
        if (url.includes("/teacher/assessments/")) body = paper("has_questions");
        else if (url.startsWith("/api/teacher/chat")) body = SPOKEN;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }),
    );
  }

  /**
   * Kéo một thanh từ `x` tới `to`.
   *
   * @param bar - Chính cái thanh.
   * @param to - Toạ độ ngang lúc thả tay.
   */
  function drag(bar: Element, to: number) {
    fireEvent.pointerDown(bar, { pointerId: 1, clientX: 260 });
    fireEvent.pointerMove(bar, { pointerId: 1, clientX: to });
    fireEvent.pointerUp(bar, { pointerId: 1, clientX: to });
  }

  it("kéo thanh bên trái thì rail rộng ra, và bề rộng ấy được nhớ", async () => {
    serving();
    const { container } = render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy(),
    );

    const shell = container.querySelector(".teacher") as HTMLElement;
    expect(shell.style.getPropertyValue("--rail-w")).toBe("260px");

    drag(container.querySelector(".split-x")!, 330);

    expect(shell.style.getPropertyValue("--rail-w")).toBe("330px");
    // Ghi lúc **thả tay**, và ghi từ ref. Ba bản của thanh kéo ngang trong rail đều sai
    // đúng chỗ này: handler đọc state là đọc giá trị của lần render cũ.
    expect(window.localStorage.getItem("kriky.teacher.rail-width")).toBe("330");
  });

  it("biên là thật: kéo quá tay không làm cột biến mất", async () => {
    // Không có `min` thì kéo hết cỡ sang trái làm rail rộng 0 — và khi ấy không còn gì
    // để kéo trở lại. Cái biên là đường lùi duy nhất.
    serving();
    const { container } = render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy(),
    );
    const shell = container.querySelector(".teacher") as HTMLElement;
    const bar = container.querySelector(".split-x")!;

    drag(bar, 10);
    expect(shell.style.getPropertyValue("--rail-w")).toBe("200px");

    drag(bar, 9000);
    expect(shell.style.getPropertyValue("--rail-w")).toBe("420px");
  });

  it("thanh của panel chỉ tồn tại khi panel có mặt", async () => {
    serving();
    const { container, rerender } = render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy(),
    );
    expect(container.querySelectorAll(".split-x").length).toBe(1);

    rerender(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper="p1"
        publishing={false}
      />,
    );
    await waitFor(() =>
      expect(container.querySelectorAll(".split-x").length).toBe(2),
    );
  });
});

describe("số phương án và số lời giải không cố định", () => {
  /** Một đề còn mở với một câu hai phương án và hai cách giải. */
  function serving() {
    const calls: { url: string; method: string; body: string }[] = [];
    const one = paper("has_questions");
    one.questions[0].methods = [
      { title: "Cách 1", body: "Đạo hàm từng hạng tử." },
      { title: "Cách 2", body: "Dùng định nghĩa." },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const method = (init?.method ?? "GET").toUpperCase();
        calls.push({
          url,
          method,
          body: typeof init?.body === "string" ? init.body : "",
        });
        return Promise.resolve({ ok: true, json: () => Promise.resolve(one) });
      }),
    );
    return calls;
  }

  afterEach(() => vi.unstubAllGlobals());

  /** Mở thẻ câu 1 ở trạng thái đang sửa. */
  async function editing() {
    const view = render(
      <Panel
        assessmentId="p1"
        publishing={false}
        onPublish={() => {}}
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());
    fireEvent.click(screen.getByText("Sửa"));
    await waitFor(() => expect(screen.getByText("Lưu")).toBeTruthy());
    return view;
  }

  it("mỗi phương án nhiễu có ô gõ nhãn lỗi", async () => {
    // Không có ô này thì nút *Thêm phương án* chỉ dẫn tới một lần 422: ADR-18 bắt mọi
    // phương án nhiễu phải có nhãn lỗi, và `validate_question` thi hành đúng luật ấy.
    serving();
    await editing();

    expect(screen.getByLabelText("Lỗi của phương án B")).toBeTruthy();
    // Đáp án đúng thì không: `error_label` null ở đúng dòng của nó (`models.py`).
    expect(screen.queryByLabelText("Lỗi của phương án A")).toBeNull();
  });

  it("thêm một phương án thì nó lấy chữ cái còn trống đầu tiên", async () => {
    serving();
    await editing();

    fireEvent.click(screen.getByText("+ Thêm phương án"));

    expect(screen.getByText("Phương án C")).toBeTruthy();
    expect(screen.getByLabelText("Lỗi của phương án C")).toBeTruthy();
  });

  it("đáp án ĐÚNG không xoá được", async () => {
    // Xoá nó là bỏ luật tính điểm của câu — một việc khác hẳn việc sửa chữ, và nó cần
    // một quyết định riêng về những lượt đã làm.
    serving();
    const { container } = await editing();

    fireEvent.click(screen.getByText("+ Thêm phương án"));
    const heads = [...container.querySelectorAll(".edit-option-head")];
    const right = heads.find((one) => one.textContent?.includes("đáp án đúng"))!;
    expect(right.querySelector("button")).toBeNull();
    // Còn phương án nhiễu thì có, vì giờ đã hơn hai phương án.
    expect(heads[1].querySelector("button")).toBeTruthy();
  });

  it("dưới hai phương án thì nút xoá biến mất, không phải bấm rồi bị từ chối", async () => {
    serving();
    const { container } = await editing();

    // Hai phương án: không nút xoá nào.
    expect(container.querySelectorAll(".edit-option-head button").length).toBe(0);

    fireEvent.click(screen.getByText("+ Thêm phương án"));
    expect(container.querySelectorAll(".edit-option-head button").length).toBe(2);
  });

  it("lời giải thêm và bớt được, nhưng không xuống dưới hai", async () => {
    // ADR-18 đòi **hơn một** lời giải: một câu một cách giải dạy được một lối nghĩ, mà
    // cả việc này sinh ra là để dạy nhiều lối.
    serving();
    const { container } = await editing();

    expect(container.querySelectorAll(".edit-method").length).toBe(2);
    expect(container.querySelectorAll(".edit-method-head button").length).toBe(0);

    fireEvent.click(screen.getByText("+ Thêm cách giải"));
    expect(container.querySelectorAll(".edit-method").length).toBe(3);

    fireEvent.click(container.querySelectorAll(".edit-method-head button")[2]);
    expect(container.querySelectorAll(".edit-method").length).toBe(2);
    expect(container.querySelectorAll(".edit-method-head button").length).toBe(0);
  });

  it("tên cách giải sửa được, không chỉ thân nó", async () => {
    serving();
    await editing();

    const title = screen.getByLabelText("Tên cách giải 1");
    fireEvent.change(title, { target: { value: "Cách 1 — xét dấu" } });
    expect((title as HTMLTextAreaElement).value).toBe("Cách 1 — xét dấu");
  });

  it("bản gửi đi mang đủ phương án mới, nhãn lỗi và tên cách giải", async () => {
    const calls = serving();
    await editing();

    fireEvent.click(screen.getByText("+ Thêm phương án"));
    fireEvent.change(screen.getByLabelText("Phương án C"), {
      target: { value: "3x" },
    });
    fireEvent.change(screen.getByLabelText("Lỗi của phương án C"), {
      target: { value: "nhân nhầm hệ số" },
    });
    fireEvent.click(screen.getByText("Lưu"));

    await waitFor(() =>
      expect(calls.some((one) => one.method === "PATCH")).toBe(true),
    );
    const sent = JSON.parse(calls.find((one) => one.method === "PATCH")!.body);
    expect(sent.options).toHaveLength(3);
    expect(sent.options[2]).toEqual({
      label: "C",
      text: "3x",
      is_correct: false,
      error_label: "nhân nhầm hệ số",
    });
    expect(sent.methods[0].title).toBe("Cách 1");
  });
});

describe("câu luật trên biểu mẫu nói đúng số đang gõ", () => {
  afterEach(() => vi.unstubAllGlobals());

  function serving() {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(FORM) })),
    );
  }

  async function mount() {
    const view = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => {}}
        onUndo={() => {}}
        undoing={false}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Cài đặt phát hành")).toBeTruthy(),
    );
    return view;
  }

  /** Gõ vào một ô theo nhãn của nó. */
  function type(label: string, value: string) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }

  it("chưa gõ gì thì câu ấy là câu `--:--` y như BE dựng", async () => {
    // Trạng thái rỗng của hai bên phải là **cùng một câu**, nếu không thì chúng đã khác
    // nhau ngay từ chỗ chưa ai gõ gì.
    serving();
    const { container } = await mount();

    const rules = [...container.querySelectorAll(".rules div")].map(
      (one) => one.textContent,
    );
    expect(rules[0]).toBe(
      "Vào tham gia tới hết --:-- - có thể nộp lúc --:--, và không dừng người đang làm.",
    );
    expect(rules[1]).toContain("mỗi lượt -- phút một câu");
  });

  it("gõ giờ đóng và thời gian làm bài thì câu ấy nói ra GIỜ NỘP CUỐI", async () => {
    // Đây là bug: câu luật tải một lần lúc mở màn nên `--:--` đứng mãi, ngay dưới chính
    // mấy ô vừa gõ. Và con số nó phải nói ra là một **phép tính** — giờ đóng cộng thời
    // gian làm bài — tức chính con số diễn đạt ra luật của ADR-03.
    serving();
    const { container } = await mount();

    type("Đóng lúc", "2026-09-15T18:00");
    type("Làm bài", "15");

    expect(container.querySelectorAll(".rules div")[0].textContent).toBe(
      "Vào tham gia tới hết 18:00 - có thể nộp lúc 18:15, và không dừng người đang làm.",
    );
  });

  it("câu pha 2 nói đúng hạn và đúng tỉ lệ phút mỗi câu", async () => {
    serving();
    const { container } = await mount();

    type("Hạn chữa xong", "2026-09-15T22:00");
    type("Phút mỗi câu", "5");

    expect(container.querySelectorAll(".rules div")[1].textContent).toBe(
      "Chữa bài tới hết 22:00 - mỗi lượt 5 phút một câu, và hết hạn thì lượt đang làm bị DỪNG.",
    );
  });

  it("giờ nộp cuối cộng qua nửa đêm vẫn đúng", async () => {
    // `23:50 + 20` là ca mà một phép cộng viết ẩu cho ra `23:70`.
    serving();
    const { container } = await mount();

    type("Đóng lúc", "2026-09-15T23:50");
    type("Làm bài", "20");

    expect(container.querySelectorAll(".rules div")[0].textContent).toContain(
      "có thể nộp lúc 00:10",
    );
  });

  it("vạch ngăn KHÔNG mang class `rule` — hộp xác nhận đã dùng tên ấy", async () => {
    // `Confirm` dùng `.rule` cho ba câu luật của nó từ lâu, và `Veil` không dựng qua
    // portal — nên cả hộp nằm *bên trong* `.publish-settings`. Một luật
    // `.publish-settings .rule { height: 1px }` vì thế bóp ba câu ấy xuống cao một pixel,
    // chữ tràn ra ngoài và chồng lên nhau. jsdom không áp CSS nên không test nào thấy hậu
    // quả; thứ ghim được là **cái tên**.
    serving();
    const { container } = await mount();

    expect(container.querySelectorAll(".publish-settings > .divider").length).toBe(2);
    expect(container.querySelectorAll(".publish-settings > .rule").length).toBe(0);
  });

  it("biểu mẫu thôi đếm lớp đã chọn", async () => {
    serving();
    const { container } = await mount();
    expect(container.querySelector(".field-note")).toBeNull();
    expect(screen.queryByText(/Đã chọn/)).toBeNull();
  });
});
