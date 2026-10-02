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

import ActionCard from "./screens/teacher/ActionCard";
import Chat from "./screens/teacher/Chat";
import PublishSettings from "./screens/teacher/PublishSettings";

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
      />,
    );

    expect(container.querySelector(".action-card")).toBeTruthy();
    expect(container.querySelector(".reply-text")).toBeNull();
    expect(screen.getByText(/Đã phát hành cho 12A và 12B/)).toBeTruthy();
  });

  it("không bịa ra một câu an toàn cho việc đã tới tay học sinh", () => {
    // Phát hành xong thì đề ĐÃ tới học sinh, nên thẻ này là thẻ duy nhất không mang câu
    // "chưa phát hành". In nó ở đây sẽ là một lời nói dối ngược chiều với mọi thẻ khác.
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
      />,
    );
    expect(container.querySelector(".safety")).toBeNull();
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
