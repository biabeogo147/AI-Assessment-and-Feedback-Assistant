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
  classes: [{ class_id: "c1", name: "12A", student_count: 40, published: false }],
  rules: {
    phase_one: "Vào tham gia tới hết --:--",
    phase_two: "Chữa bài tới hết --:--",
    recall: "Thu hồi được cho tới hết giờ mở.",
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
  const values = ["15", "2026-10-02T14:00", "2026-10-02T16:00", "5", "2026-10-02T22:00"];
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
        sent.push({ path, body: init?.body ? JSON.parse(String(init.body)) : null });
        const payload = init?.method === "POST" ? PREVIEW : FORM;
        return new Response(JSON.stringify(payload), { status: 200 });
      }),
    );

    render(<PublishSettings assessmentId="p1" onPublished={() => {}} />);
    await waitFor(() => expect(screen.getByText("Cài đặt phát hành")).toBeTruthy());

    fireEvent.click(screen.getByText("12A"));
    fill();
    fireEvent.click(screen.getByText(/Phát hành cho/));

    await waitFor(() => expect(screen.getByText("Phát hành đề kiểm tra?")).toBeTruthy());
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

    render(<PublishSettings assessmentId="p1" onPublished={() => {}} />);
    await waitFor(() => expect(screen.getByText("Cài đặt phát hành")).toBeTruthy());
    fireEvent.click(screen.getByText("12A"));
    fill();
    fireEvent.click(screen.getByText(/Phát hành cho/));
    await waitFor(() => expect(screen.getByText("Phát hành đề kiểm tra?")).toBeTruthy());
    // Nút trong hộp thoại, không phải nút của biểu mẫu: hai nút cùng chữ, và chỉ nút
    // trong hộp mới gửi đi lần thật.
    fireEvent.click(document.querySelector(".confirm .btn.primary") as HTMLElement);

    await waitFor(() => expect(bodies.length).toBe(2));
    const [shown, done] = bodies;
    expect(shown.preview).toBe(true);
    expect(done.preview).toBe(false);
    // Byte-identical trừ một cờ. Đây là cách duy nhất để "hộp xác nhận đọc lại đúng cái
    // sắp xảy ra" là một tính chất của code chứ không phải một lời hứa.
    expect(JSON.stringify(shown.schedules)).toBe(JSON.stringify(done.schedules));
  });

  it("gửi giờ kèm offset, không phải Z", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_path: string, init?: RequestInit) => {
        if (init?.method === "POST") bodies.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify(init?.method === "POST" ? PREVIEW : FORM), {
          status: 200,
        });
      }),
    );

    render(<PublishSettings assessmentId="p1" onPublished={() => {}} />);
    await waitFor(() => expect(screen.getByText("Cài đặt phát hành")).toBeTruthy());
    fireEvent.click(screen.getByText("12A"));
    fill();
    fireEvent.click(screen.getByText(/Phát hành cho/));

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
          tool_result: { published: true, assessment_id: "p1", classes: ["12A", "12B"] },
          entity_kind: "assessment",
          entity_id: "p1",
          model_tokens: 0,
          duration_ms: 0,
        }}
        onOpen={() => {}}
        onPublish={() => {}}
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
          tool_result: { published: true, assessment_id: "p1", classes: ["12A"] },
          entity_kind: "assessment",
          entity_id: "p1",
          model_tokens: 0,
          duration_ms: 0,
        }}
        onOpen={() => {}}
        onPublish={() => {}}
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
    render(<Chat conversationId="c1" fresh={false} openPaper={null} publishing={false} />);

    await waitFor(() => expect(document.querySelector(".action-card")).not.toBeNull());

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
          tool_result: { assessment_id: "p1", title: "Hàm số", question_count: 10 },
        }),
        blank({ kind: "assistant", text: "Đã tạo xong đề." }),
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(url.startsWith("/api/teacher/chat") ? full : []),
        }),
      ),
    );

    render(<Chat conversationId="c1" fresh={false} openPaper={null} publishing={false} />);
    await waitFor(() => expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy());

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
      <Chat conversationId="c1" fresh={false} openPaper={null} publishing={false} />,
    );
    await waitFor(() => expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy());

    // Bấm *Đoạn chat mới*: màn trắng, và không còn đoạn nào đang nằm trên màn hình.
    rerender(<Chat conversationId={null} fresh openPaper={null} publishing={false} />);
    expect(screen.queryByText("Đã tạo xong đề.")).toBeNull();

    // Bấm lại ĐÚNG đoạn vừa rời đi. Nó phải hiện lại — không phải một màn trắng vì ai đó
    // tưởng nó vẫn đang ở trên màn hình.
    rerender(<Chat conversationId="c1" fresh={false} openPaper={null} publishing={false} />);
    await waitFor(() => expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy());
    expect(asked.filter((one) => one.startsWith("/api/teacher/chat")).length).toBeGreaterThan(1);
  });
});

describe("một lượt của Kriky", () => {
  it("cho ra ĐÚNG MỘT thẻ, và start_drafting không bao giờ là thẻ", () => {
    const turns = [
      blank({ kind: "tool_result", tool_name: "create_draft", tool_result: { created: true } }),
      blank({ kind: "tool_result", tool_name: "start_drafting", tool_result: { started: true } }),
      blank({
        kind: "tool_result",
        tool_name: "draft_progress",
        tool_result: { found: true, written: ["a", "b"], asked_for: 2, still_drafting: 0 },
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
        tool_result: { created: true, title: "Tích phân 12A1", question_count: 10 },
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
        onPublish={() => undefined}
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
      blank({ kind: "tool_result", tool_name: "start_drafting", tool_result: { started: true, queued: 5 } }),
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
    let live = grow(null, event({ kind: "say", text: "Được, mình soạn đề ngay." }));
    live = grow(live, event({ kind: "plan", total: 2, titles: ["Tạo đề trống", "Soạn câu"] }));
    live = grow(live, event({ kind: "step_started", title: "Tạo đề trống", index: 1, total: 2 }));

    expect(live.opening).toBe("Được, mình soạn đề ngay.");
    expect(live.total).toBe(2);
    expect(live.steps).toHaveLength(1);
    expect(live.steps[0].mark).toBe("running");
  });

  it("đóng bước đang chạy khi nó xong, và giữ dòng kết quả của BE", () => {
    let live = grow(null, event({ kind: "step_started", title: "Tạo đề trống", total: 2 }));
    live = grow(
      live,
      event({ kind: "step_done", title: "Tạo đề trống", detail: 'đề "X", cần 10 câu' }),
    );

    expect(live.steps[0].mark).toBe("done");
    expect(live.steps[0].result).toBe('— đề "X", cần 10 câu');
  });

  it("số câu đã soạn là dòng của bước đang chạy, không phải con số thứ hai trên header", () => {
    // Hai con số, hai chỗ đứng (ADR-25): `bước k/n` đếm bước của plan, số câu là tiến độ
    // bên trong MỘT bước. Gộp chúng vào một chỗ là nói sai cả hai.
    let live = grow(null, event({ kind: "plan", total: 2 }));
    live = grow(live, event({ kind: "step_started", title: "Soạn 10 câu hỏi", total: 2 }));
    live = grow(live, event({ kind: "progress", index: 4, total: 10 }));

    expect(live.total).toBe(2);
    expect(live.steps[0].result).toBe("— đã soạn 4/10 câu");
    expect(live.steps[0].mark).toBe("running");
  });

  it("một bước hỏng đọc ra là hỏng, kèm lý do", () => {
    let live = grow(null, event({ kind: "step_started", title: "Soạn câu hỏi" }));
    live = grow(
      live,
      event({ kind: "step_failed", title: "Soạn câu hỏi", detail: "chưa làm được bước này" }),
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
          { mark: "done", title: "Tạo đề trống", result: "— đề \"X\"" },
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
          { mark: "failed", title: "Soạn câu hỏi", result: "— hàng đợi đang hỏng" },
        ]}
      />,
    );
    // Các bước hiện sẵn, và cái nút thu gọn không mời bấm.
    expect(screen.getByText("Soạn câu hỏi")).toBeTruthy();
    expect(screen.getByText("— hàng đợi đang hỏng")).toBeTruthy();
    expect(container.querySelector(".steps-head")?.hasAttribute("disabled")).toBe(true);
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
                      blank({ kind: "assistant", text: "Mình chưa rõ lớp nào." }),
                    ],
                  }
                : [],
            ),
        }),
      ),
    );
    Element.prototype.scrollIntoView = vi.fn();
    render(<Chat conversationId="c1" fresh={false} openPaper={null} publishing={false} />);
    await waitFor(() => expect(screen.getByText("Mình chưa rõ lớp nào.")).toBeTruthy());

    const voices = document.querySelectorAll(".exchange .voice");
    expect(voices).toHaveLength(1);
    const only = voices[0];
    expect(only.querySelector(".who")).toBeTruthy();
    expect(only.querySelector(".reply-text")?.textContent).toBe("Mình chưa rõ lớp nào.");
  });
});

describe("một tool chưa có trong bảng", () => {
  it("không in định danh máy ra bề mặt giáo viên", () => {
    const step = stepFor(
      blank({ kind: "tool_result", tool_name: "teacher.some_new_thing", tool_result: {} }),
    );
    expect(step.title).not.toMatch(/teacher\.|_/);
    expect(step.title).toBe("Một bước nữa");
  });
});
