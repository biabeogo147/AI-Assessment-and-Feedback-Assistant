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
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ActionCard, {
  cardState,
  cardTurns,
  stepFor,
} from "./screens/teacher/ActionCard";
import Chat, { grow } from "./screens/teacher/Chat";
import Panel from "./screens/teacher/Panel";
import PublishSettings from "./screens/teacher/PublishSettings";
import Steps from "./screens/teacher/Steps";
import { moment, teacher, type TurnEvent } from "./api";

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
  // Hai lớp, không một. Một biểu mẫu chỉ có một lớp thì mọi luật về **tập** lớp đều
  // không đo được: `picked` và `picked.slice(0, 1)` ra cùng một kết quả, nên một đột
  // biến bỏ rơi lớp thứ hai vẫn xanh.
  classes: [
    { class_id: "c1", name: "12A", student_count: 40, published: false },
    { class_id: "c2", name: "12B", student_count: 32, published: false },
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
    // Ba lời từ chối, sao đúng từ `publication_wording.FAULT_*`. Biểu mẫu mượn chúng để
    // nói TRƯỚC cú bấm, nên chúng phải là chữ của BE chứ không phải chữ viết lại ở FE.
    opens_in_the_past: "giờ mở phải ở tương lai",
    closes_before_opens: "giờ đóng phải sau giờ mở",
    phase_two_too_early: "hạn pha 2 phải sau giờ nộp cuối của pha 1",
  },
  // Rỗng là *còn lùi được*. Câu chặn do BE viết, và biểu mẫu hiện nó TRƯỚC cú bấm.
  undo_blocked: "",
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

/**
 * Một mốc `datetime-local` cách **bây giờ** bao nhiêu giờ.
 *
 * Tính tương đối chứ không viết cứng, vì một trong sáu tham số là *giờ mở phải ở tương
 * lai* (ADR-02). Fixture cũ ghi `2026-10-02T14:00`, và nó đúng cho tới ngày 02/10 rồi
 * lặng lẽ thành một bộ tham số **không hợp lệ** — một test của luật "phải ở tương lai"
 * mà tự hết hạn là một test hẹn ngày đỏ mà không ai hẹn.
 */
function inHours(hours: number): string {
  const when = new Date(Date.now() + hours * 3_600_000);
  const two = (n: number) => String(n).padStart(2, "0");
  return (
    `${when.getFullYear()}-${two(when.getMonth() + 1)}-${two(when.getDate())}` +
    `T${two(when.getHours())}:${two(when.getMinutes())}`
  );
}

function fill() {
  const boxes = document.querySelectorAll(".publish-settings input");
  const values = ["15", inHours(24), inHours(26), "5", inHours(32)];
  boxes.forEach((box, index) => {
    fireEvent.change(box, { target: { value: values[index] } });
  });
}

/**
 * Một lớp đang giữ đề, với giờ đã đặt — hình dạng của `PublishedTo`.
 *
 * Hai câu note là chữ của BE, dựng bằng `publication_wording`. Chúng mang dấu riêng ở
 * đây để không nhầm được với bất kỳ câu nào FE tự dựng.
 */
function heldBy(
  classId: string,
  name: string,
  opens: string,
  closes: string,
  deadline: string,
) {
  return {
    class_id: classId,
    class_name: name,
    student_count: 40,
    opens_at: opens,
    closes_at: closes,
    phase1_minutes: 15,
    phase2_minutes_per_question: 5,
    remediation_deadline: deadline,
    withdrawable_until: opens,
    phase_one_note: `NOTE-MỘT-${name}-TỪ-BE`,
    phase_two_note: `NOTE-HAI-${name}-TỪ-BE`,
  };
}

/**
 * Biểu mẫu phát hành, không có cú POST nào.
 *
 * Định tuyến theo đường dẫn chứ không trả một payload cho mọi lời gọi: biểu mẫu nay hỏi
 * **hai** endpoint, và một fixture trả `publish-form` cho cả `publications` sẽ làm màn
 * hình đọc một hình dạng sai mà test vẫn xanh.
 *
 * @param form - Ghi đè vài trường của `FORM`, ví dụ `classes` đã phát hành.
 * @param live - Các lớp đang giữ đề. Mặc định: chưa lớp nào.
 */
function serveForm(
  form: Record<string, unknown> = {},
  live: ReturnType<typeof heldBy>[] = [],
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const payload = String(path).endsWith("/publications")
        ? { assessment_id: "p1", classes: live, rules: FORM.rules }
        : { ...FORM, ...form };
      return new Response(JSON.stringify(payload), { status: 200 });
    }),
  );
}

/**
 * Mỗi test bắt đầu từ một `localStorage` trống.
 *
 * Bề mặt giáo viên nhớ bốn thứ, và từ đợt này có cả **bản nháp cài đặt phát hành** — nên
 * một test gõ sáu ô rồi để lại nháp sẽ làm test sau mở ra một biểu mẫu đã điền sẵn, và nó
 * đỏ ở một chỗ chẳng liên quan gì. Đã có hai lời `clear()` rải rác trong file này từ
 * trước; chúng là dấu hiệu của cùng một chuyện, chỉ chưa đủ rộng.
 *
 * Luật thật là: thứ tự test không được đổi kết quả test.
 */
beforeEach(() => window.localStorage.clear());

/**
 * Mở một tầng của thẻ đang sửa.
 *
 * Từ 06/10/2026 thẻ mở **một lúc một tầng**, nên một test muốn chạm vào phương án hay
 * cách giải phải đi qua thanh đầu của tầng ấy — đúng như ngón tay thật. Trước đó cả hai
 * mươi ô cùng hiện, và chính điều đó là thứ được sửa: đo ở density Teacher, thẻ phẳng
 * cao 774 trong một khung 658.
 */
function openTang(name: "Đề bài" | "Phương án" | "Cách giải") {
  fireEvent.click(screen.getByText(name));
}

describe("hộp xác nhận phát hành", () => {
  it("chỉ in những chuỗi của response preview, không tự viết lại câu luật", async () => {
    const sent: { body: unknown; path: string; method: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, init?: RequestInit) => {
        sent.push({
          path,
          method: init?.method ?? "GET",
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

    // Và hộp thoại **không** kể hai câu chuyện cùng lúc. Đo được trên trình duyệt ngày
    // 06/10/2026: câu mở đầu hứa thu hồi "cho tới giờ mở của TỪNG LỚP" trong khi dòng luật
    // ngay dưới nó — do BE viết — nói "cho tới hết giờ mở", và dòng `Thu hồi` in đúng một
    // giờ. Một lần phát hành có một khung giờ, nên "từng lớp" không còn thứ gì để chỉ tới.
    expect(document.querySelector(".confirm")?.textContent).not.toContain("từng lớp");

    // Và lần gọi xem trước mang đúng cờ `preview`, vì nếu không thì cái "xem trước" ấy
    // đã phát hành thật rồi.
    // Lọc theo **method**, không chỉ theo đường dẫn: `/publications` nay mang cả một
    // lời GET đọc lại giờ đã đặt, và nó bay tới trước cú POST. Tìm theo đường dẫn thôi
    // là bắt nhầm lời GET, rồi đọc `preview` của một thân rỗng.
    const asked = sent.find(
      (one) => one.path.endsWith("/publications") && one.method === "POST",
    );
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
    // **Hai** lớp, vì luật cần đo là *cùng một tập lớp đi cả hai lần*. Với một lớp thì
    // mọi cách bỏ sót đều trùng với cách làm đúng.
    fireEvent.click(screen.getByText("12A"));
    fireEvent.click(screen.getByText("12B"));
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
    //
    // Dòng này từng đọc `shown.schedules` — một khoá đã đổi tên thành `schedule` ở Pha 5.
    // `JSON.stringify(undefined)` là `undefined` ở **cả hai** vế, nên phép so vẫn xanh
    // trong khi nó không còn so cái gì nữa. Một test xanh vì cả hai vế đều rỗng là một
    // test đã chết mà không ai báo tang, nên ở đây có thêm một khẳng định rằng vế trái
    // thật sự có nội dung.
    expect(shown.schedule).toBeTruthy();
    expect(JSON.stringify(shown.schedule)).toBe(JSON.stringify(done.schedule));
    expect(JSON.stringify(shown.class_ids)).toBe(JSON.stringify(done.class_ids));
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
    // Một khung giờ cho cả lần phát hành, nên `schedule` là một object chứ không
    // phải một mảng — và `class_ids` đi riêng.
    expect(bodies[0].class_ids).toEqual(["c1"]);
    const when = (bodies[0].schedule as { opens_at: string }).opens_at;
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
    // Đầu đề KHÔNG chở tên lớp. `Đã phát hành cho 12A và 12B` là một trạng thái thứ tư
    // trá hình: nó đổi chữ theo dữ liệu, nên hai lần phát hành cho hai bộ lớp đọc ra như
    // hai nấc khác nhau của cùng một đề. Danh sách lớp thuộc về hộp xác nhận và bảng kết
    // quả, không thuộc một dòng tiêu đề.
    expect(screen.getByText("Đã phát hành")).toBeTruthy();
    expect(screen.queryByText(/12A/)).toBeNull();
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
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Đã tạo xong đề.")).toBeTruthy(),
    );

    // Bấm *Đoạn chat mới*: màn trắng, và không còn đoạn nào đang nằm trên màn hình.
    rerender(
      <Chat conversationId={null} fresh openPaper={null} />,
    );
    expect(screen.queryByText("Đã tạo xong đề.")).toBeNull();

    // Bấm lại ĐÚNG đoạn vừa rời đi. Nó phải hiện lại — không phải một màn trắng vì ai đó
    // tưởng nó vẫn đang ở trên màn hình.
    rerender(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
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
  it("cho ra ĐÚNG MỘT thẻ, và nó là bước đã đợi xong", () => {
    // Bản trước của test này lấy `draft_progress` làm thẻ. Tool ấy đã bỏ, nên ca đo được
    // bây giờ là ca thật của một plan hai bước: `create_draft` bị loại vì bước sau đã thay
    // nó, và `start_drafting` lên thẻ **khi và chỉ khi** nó mang con số thật về.
    const turns = [
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: { created: true },
      }),
      blank({
        kind: "tool_result",
        tool_name: "start_drafting",
        tool_result: { started: true, written: 3, asked_for: 3, still_drafting: 0 },
      }),
    ];

    expect(cardTurns(turns).map((o) => o.tool_name)).toEqual(["start_drafting"]);
  });

  it("KHÔNG thẻ nào khi các câu còn đang chạy", () => {
    // `asked_for` vắng nghĩa là bước soạn trả về ngay, chưa đợi câu nào. Một thẻ ở đó nói
    // với giáo viên rằng việc đã xong trong khi nó vừa bắt đầu — và `create_draft` cũng
    // không được lên thẻ, vì trạng thái "đề trống" đã bị chính bước sau thay thế.
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
    ];

    expect(cardTurns(turns)).toEqual([]);
  });

  it("KHÔNG mọc thẻ đề trống khi câu hỏi đang được đổ vào đề ấy", () => {
    // Đúng hình dạng một plan hai bước của ADR-25: mở đề, rồi soạn câu. Lúc lượt kết thúc,
    // các câu còn đang chạy trong hàng đợi, nên bước soạn chưa mang con số thật về.
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
    expect(cardTurns(turns)).toEqual([]);
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
    expect(cardTurns(turns)[0]?.tool_name).toBe("create_draft");
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
    expect(cardTurns(turns)[0]?.tool_name).toBe("create_draft");

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

    // Trước đợt này `cardTurns` loại `start_drafting` vô điều kiện, `create_draft` bị loại vì
    // có bước soạn phía sau, và tool kiểm tiến độ đã bỏ nên không plan nào gọi
    // nó — ba lần loại trừ giao nhau đúng ở đường đi hạnh phúc, và một lượt soạn đề THÀNH
    // CÔNG kết thúc không thẻ nào. Mà panel đề chỉ mở được từ một nút trên thẻ, nên Kriky
    // nói "đã soạn xong" và màn hình không có cửa nào vào xem. Đo được trên hội thoại thật.
    const card = cardTurns(turns)[0] ?? null;
    expect(card?.tool_name).toBe("start_drafting");

    const opened: string[] = [];
    render(
      <ActionCard
        turn={card!}
        onOpen={(paper) => opened.push(paper)}
        onCompose={() => undefined}
      />,
    );
    // Thẻ thôi kể con số: khối `Thinking` ngay trên nó đã in "đã soạn 3/3 câu". Thẻ trả
    // lời câu khác — đề này đang ở nấc nào — và nấc ấy là "đã tạo đề".
    expect(screen.getByText("Đã tạo đề")).toBeTruthy();
    // Không nút nào: `Duyệt đề`, `Xem đề` và `Xem` đều gọi đúng một hàm, nên năm nhãn
    // cho một việc rút về chính cái thẻ.
    expect(screen.queryByText("Duyệt đề")).toBeNull();
    expect(screen.queryByText("Xem đề")).toBeNull();

    fireEvent.click(screen.getByText("Đã tạo đề"));
    expect(opened).toEqual(["p1"]);
  });

  it("đề thiếu câu vẫn đứng ở nấc một, và vẫn KHÔNG mời duyệt", () => {
    // Cùng một luật đã đứng trong `reporting._progress` của AGENT: duyệt một đề thiếu câu là
    // phát hành một bài kiểm tra dở. Lời kể và thẻ phải nói cùng một câu.
    //
    // Luật ấy **đổi chỗ** hai lần, và chỗ cuối là chỗ chắc nhất. Đầu tiên nó sống trong
    // nhãn nút (`Xem đề` thay vì `Duyệt đề`); nút bỏ thì nó sang chữ đầu đề (`Dừng ở 2/10
    // câu`); từ 06/10/2026 đầu đề chỉ còn bốn chuỗi cố định, nên nó sống ở chỗ nó đáng
    // sống từ đầu: **thẻ không có cổng duyệt nào cả**. Cổng thật ở chân panel, nơi duy
    // nhất đọc được trạng thái hiện tại của đề, và con số thì ở khối `Thinking` ngay trên
    // thẻ — hỏi nó thì được một câu đúng tại thời điểm hỏi, chứ không phải một con số
    // đóng băng trong một biên bản cũ.
    const card = cardTurns(drafted(2, 10).turns)[0] ?? null;

    render(
      <ActionCard
        turn={card!}
        onOpen={() => undefined}
        onCompose={() => undefined}
      />,
    );
    expect(screen.getByText("Đã tạo đề")).toBeTruthy();
    expect(screen.queryByText("Duyệt đề")).toBeNull();
    // Và không con số nào trên thẻ: hai chỗ cho một thông tin thì một chỗ sẽ cũ đi.
    expect(screen.queryByText(/2\/10/)).toBeNull();
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
    expect(cardTurns(turns)).toEqual([]);
  });

  it("đề còn câu đang soạn cũng đứng ở nấc một, và KHÔNG mời duyệt", () => {
    // Đường ra có thật: hết hạn im lặng thì `_wait_for_questions` rời vòng nghe với
    // `still_drafting > 0`. Bản đầu coi "thiếu câu" là `written < asked && running === 0`,
    // nên ca này rơi vào nhánh còn lại — thẻ in `Đã thêm 3 câu vào đề`, giấu mất số 10, và
    // mời **Duyệt đề** cho một đề mới có 3/10 câu. Lời kể của AGENT trong cùng ca ấy chỉ
    // được nói "đang soạn": hai câu ngược nhau trên cùng một màn hình.
    const card = cardTurns(drafted(3, 10, 7).turns)[0] ?? null;

    render(
      <ActionCard
        turn={card!}
        onOpen={() => undefined}
        onCompose={() => undefined}
      />,
    );
    expect(screen.getByText("Đã tạo đề")).toBeTruthy();
    expect(screen.queryByText("Duyệt đề")).toBeNull();
    expect(screen.queryByText(/3\/10/)).toBeNull();
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

  /**
   * Bấm như một ngón tay thật: `pointerdown`, rồi `pointerup`, rồi `click`.
   *
   * `fireEvent.click` một mình **không** dựng ra chuỗi ấy, và đúng khe hở đó đã giấu một
   * lỗi làm chết cả hai mục của menu `⋯` trong suốt thời gian các test trên vẫn xanh.
   */
  function bamThat(node: Element) {
    fireEvent.pointerDown(node, { bubbles: true });
    fireEvent.pointerUp(node, { bubbles: true });
    fireEvent.click(node);
  }

  it("menu ⋯ sống qua pointerdown — cả hai mục, không chỉ cái nhìn thấy", async () => {
    // Rail đóng menu ở `pointerdown` và miễn trừ cho `closest(".conversation")`. Menu lại
    // dựng qua `createPortal(document.body)` để thoát `mask-image` của vùng cuộn, nên với
    // chính các mục của nó `closest(".conversation")` là `null`: `pointerdown` tháo menu,
    // `click` rơi vào một node đã tháo, và không gì xảy ra.
    //
    // Đo trên trình duyệt thật ngày 06/10/2026: sau `pointerdown` thì
    // `menuStillThere: false`, `itemConnected: false`, `input.rename` không hiện.
    routes(SPOKEN, THREADS);
    render(<Chat conversationId="c1" fresh={false} openPaper={null} />);
    await waitFor(() =>
      expect(screen.getByText("Tên model đặt sai")).toBeTruthy(),
    );

    bamThat(screen.getByLabelText("Tuỳ chọn cho Tên model đặt sai"));
    expect(document.querySelector(".row-menu")).toBeTruthy();

    bamThat(screen.getByText("Đổi tên"));

    expect(screen.getByLabelText("Tên đoạn chat")).toBeTruthy();
  });

  it("và mục Xoá cũng vậy — nó chết cùng một đường", async () => {
    routes(SPOKEN, THREADS);
    render(<Chat conversationId="c1" fresh={false} openPaper={null} />);
    await waitFor(() => expect(screen.getByText("Đoạn khác")).toBeTruthy());

    bamThat(screen.getByLabelText("Tuỳ chọn cho Đoạn khác"));
    bamThat(screen.getByText("Xoá"));

    expect(screen.getByText("Xoá đoạn chat này?")).toBeTruthy();
  });

  it("bấm ra NGOÀI menu thì menu vẫn phải đóng", async () => {
    // Nửa kia của cùng một luật: nới chỗ miễn trừ mà nới quá tay thì menu thành thứ chỉ
    // đóng bằng cách chọn một mục — đúng cái bệnh `pointerdown` sinh ra để chữa.
    routes(SPOKEN, THREADS);
    render(<Chat conversationId="c1" fresh={false} openPaper={null} />);
    await waitFor(() => expect(screen.getByText("Đoạn khác")).toBeTruthy());

    bamThat(screen.getByLabelText("Tuỳ chọn cho Đoạn khác"));
    expect(document.querySelector(".row-menu")).toBeTruthy();

    fireEvent.pointerDown(document.body, { bubbles: true });

    expect(document.querySelector(".row-menu")).toBeNull();
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
      state: "ready",
      page_count: 12,
      fault: "",
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

    await waitFor(() =>
      expect(container.querySelector(".scope-strip")).toBeTruthy(),
    );
    // Dải chỉ nói **tên tệp**. Chữ "Đã tải lên" bị bỏ: rail đã đẩy tệp vừa lên đầu danh
    // sách, nên câu ấy kể lại một việc màn hình vừa nói — và nó là nghĩa thứ hai nhét vào
    // cùng một biến, thứ làm cho không luật dọn nào đúng được.
    expect(container.querySelector(".scope-strip .what")?.textContent).toBe(
      "de-cuong.pdf",
    );
    expect(screen.queryByText("Đã tải lên: de-cuong.pdf")).toBeNull();
    expect(screen.queryByText("Đổi phạm vi")).toBeNull();
    // Tải lên có **một** cửa: cái icon cạnh nhãn TÀI LIỆU. Dải này không phải một cửa thứ
    // hai — hai cửa cho cùng một việc thì cửa nào cũng thành chỗ phải đoán. Nút duy nhất
    // trên dải là đường lùi, và nó mang đúng một chữ.
    expect(screen.queryByText("Tải tệp khác")).toBeNull();
    expect(
      [...container.querySelectorAll(".scope-strip button")].map(
        (one) => one.textContent,
      ),
    ).toEqual(["Bỏ"]);
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
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText("Duyệt đề")).toBeTruthy());
    expect(screen.queryByText("Hoàn tác")).toBeNull();
    expect(screen.queryByText("Phát hành đề")).toBeNull();
  });

  it("đề đã duyệt mở THẲNG cài đặt phát hành, không qua chặng nào", async () => {
    // Chặng ở giữa — nội dung đề cộng một nút `Phát hành đề` — thu đúng một cú bấm mà
    // không trả lại gì. Nó tới được bằng **mọi** đường: thẻ trong chat luôn đi `/de/{id}`
    // không hậu tố, nên một đề đã duyệt mở ra luôn rơi vào đó. Đo trên trình duyệt ngày
    // 06/10/2026: `.panel` có `panel-head`, `panel-questions`, `panel-foot`, CTA
    // `Phát hành đề`. Nay nấc đọc từ `state`, nên không còn chặng nào để rơi vào.
    serving("approved");
    const { container } = render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );

    await waitFor(() =>
      expect(container.querySelector(".publish-settings")).toBeTruthy(),
    );
    // `Phát hành đề` vẫn còn trên màn — nhưng là nút chính **của biểu mẫu**. Thứ phải
    // biến mất là chân panel, nên đo chân panel chứ đừng đo cái nhãn: hai chỗ khác nhau
    // dùng chung một chuỗi, và một phép so theo chữ sẽ bắt nhầm chỗ.
    expect(container.querySelector(".panel-foot")).toBeNull();
  });

  it("đề ĐÃ PHÁT HÀNH mời đúng một việc: phát hành đề", async () => {
    // Chân panel của một đề đã phát hành **không** mời thêm lớp. Muốn đổi lớp thì hoàn
    // tác trước — người dùng chốt ngày 06/10/2026 — và `Hoàn tác` sống ở màn cài đặt
    // phát hành, một chỗ chứ không hai.
    //
    // Bản trước của test này ghim một luật đã hết đúng: `POST .../unapprove` khi ấy chỉ
    // nhận `APPROVED`, nên nút `Hoàn tác` cho một đề đã phát hành chắc chắn trả 409. Nay
    // endpoint ấy thu hồi mọi lớp rồi hạ hai nấc, nên đường lùi là một đường.
    serving("published");
    const { container } = render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );

    await waitFor(() =>
      expect(container.querySelector(".publish-settings")).toBeTruthy(),
    );
    expect(screen.queryByText("Phát hành thêm lớp")).toBeNull();
    // `Phát hành đề` vẫn còn trên màn — nhưng là nút chính **của biểu mẫu**. Thứ phải
    // biến mất là chân panel, nên đo chân panel chứ đừng đo cái nhãn: hai chỗ khác nhau
    // dùng chung một chuỗi, và một phép so theo chữ sẽ bắt nhầm chỗ.
    expect(container.querySelector(".panel-foot")).toBeNull();
  });

  it("duyệt xong là sang THẲNG cài đặt phát hành, không dừng ở giữa", async () => {
    // Trước đợt này cú bấm `Duyệt đề` chỉ đổi chân panel thành hai nút rồi đứng im — một
    // chặng dừng không có việc gì của riêng nó. Luồng thiết kế là màn 6 → màn 7.
    //
    // Và nay không một cú điều hướng nào chở việc ấy: `state` đổi sang `approved`, panel
    // đọc `state`, biểu mẫu hiện ra. Bản trước của test này đo `onPublish` có được gọi
    // không — tức đo cái **cách** đi tới, nên nó vẫn xanh khi đích đến không hiện ra.
    let state = "has_questions";
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const method = (init?.method ?? "GET").toUpperCase();
        if (method === "POST" && url.endsWith("/approve")) state = "approved";
        const body = url.includes("/publish-form") ? FORM : paper(state);
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }),
    );
    const { container } = render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("Duyệt đề")).toBeTruthy());
    expect(container.querySelector(".publish-settings")).toBeNull();

    fireEvent.click(screen.getByText("Duyệt đề"));

    await waitFor(() =>
      expect(container.querySelector(".publish-settings")).toBeTruthy(),
    );
  });

  it("bấm Hoàn tác ở màn cài đặt phát hành gọi đúng endpoint bỏ duyệt", async () => {
    // `teacher.unapprove` có trong `api.ts` từ lâu và chưa một dòng nào gọi nó. Nay nó
    // được gọi từ màn 7 — chỗ giáo viên nhìn thấy ngay sau cú bấm duyệt.
    const calls = serving("approved");
    render(
      <Panel
        assessmentId="p1"
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

  it("hết cửa lùi thì Hoàn tác KHOÁ, kèm câu của BE", async () => {
    // Biểu mẫu nói trước cú bấm, cùng khuôn với cách nó chặn một cửa sổ thời gian vô lý.
    // Giấu nút đi thì giáo viên đi tìm một đường lùi không còn tồn tại; để nó bấm được thì
    // cú bấm nhận 409 — mà `Panel` từng nuốt mất câu ấy, nên màn hình im lặng hoàn toàn.
    const shut = "Đã qua giờ mở của lớp 12A nên không hoàn tác được nữa.";
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(
              url.includes("/publish-form")
                ? { ...FORM, undo_blocked: shut }
                : paper("published"),
            ),
        }),
      ),
    );

    render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );

    const button = await screen.findByText("Hoàn tác");
    expect((button as HTMLButtonElement).disabled).toBe(true);
    // Và câu nói ra, nguyên văn của BE: một nút khoá mà không nói vì sao là một nút hỏng.
    expect(screen.getByText(shut)).toBeTruthy();
  });

  it("lỗi của Hoàn tác hiện ra Ở MÀN cài đặt phát hành, không im lặng", async () => {
    // Đo được trên trình duyệt thật ngày 06/10/2026: bấm `Hoàn tác` trên một đề đã phát
    // hành, BE trả 409, và màn hình **không nói một chữ nào**. `trouble` vốn chỉ sống trong
    // nhánh `panel-foot`, mà màn 7 vẽ nhánh kia — nên mọi lỗi phát ra ở đây đều rơi vào
    // khoảng không.
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if ((init?.method ?? "GET").toUpperCase() === "POST") {
          return Promise.resolve({
            ok: false,
            status: 409,
            json: () => Promise.resolve({ detail: "Một lớp vừa qua giờ mở." }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(
              url.includes("/publish-form") ? FORM : paper("published"),
            ),
        });
      }),
    );

    render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );

    fireEvent.click(await screen.findByText("Hoàn tác"));

    await waitFor(() =>
      expect(screen.getByText("Một lớp vừa qua giờ mở.")).toBeTruthy(),
    );
  });
});

describe("lời giải mở thành hộp thoại", () => {
  /** Stub `fetch` trả về một đề đã duyệt với một câu đủ lời giải và nhãn lỗi.
   *
   * Phải trả **cả** `/publish-form`: đề đã duyệt thì panel dựng luôn cài đặt phát hành
   * (màn 6.5 đã bỏ), nên một stub chỉ biết đường đọc đề sẽ làm biểu mẫu nổ ở chỗ render —
   * và cú nổ ấy nói về cái stub chứ không nói về hộp lời giải đang được đo.
   */
  function serving() {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(
              url.includes("/publish-form") ? FORM : paper("approved"),
            ),
        }),
      ),
    );
  }

  async function opened() {
    serving();
    const view = render(
      <Panel
        assessmentId="p1"
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

    render(<Chat conversationId="c1" fresh={false} openPaper="p1" />);
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
      state: "ready",
      page_count: 12,
      fault: "",
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
      <Chat conversationId="c1" fresh={false} openPaper={null} />,
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
      <Chat conversationId="c1" fresh={false} openPaper={null} />,
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
    await waitFor(() =>
      expect(container.querySelector(".scope-strip .what")?.textContent).toBe(
        "de-cuong.pdf",
      ),
    );
    expect((container.querySelector(".composer-bar") as HTMLElement).className).not.toContain(
      "dropping",
    );
  });

  /**
   * Thả một chip vào ô nhập, rồi trả về khung đang dựng.
   *
   * `DataTransfer` giả, vì jsdom không dựng sẵn cái thật.
   */
  async function attach(view: ReturnType<typeof render>) {
    const chip = view.container.querySelector(
      ".pane.documents .document",
    ) as HTMLElement;
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
    fireEvent.drop(
      view.container.querySelector(".composer-bar") as HTMLElement,
      { dataTransfer },
    );
    await waitFor(() =>
      expect(view.container.querySelector(".scope-strip")).toBeTruthy(),
    );
  }

  it("bấm Bỏ thì tệp đính rời khỏi câu đang gõ", async () => {
    // Đính nhầm mà không gỡ ra được thì chỉ còn cách gõ lại cả câu.
    serving();
    const view = render(<Chat conversationId="c1" fresh={false} openPaper={null} />);
    await waitFor(() => expect(screen.getByText("de-cuong.pdf")).toBeTruthy());
    await attach(view);

    fireEvent.click(screen.getByText("Bỏ"));

    expect(view.container.querySelector(".scope-strip")).toBeNull();
    // Nhưng tệp vẫn ở trong thư viện: bỏ đính không phải xoá tài liệu (ADR-04).
    expect(view.container.querySelector(".pane.documents .document")).toBeTruthy();
  });

  it("đổi sang đoạn chat khác thì tệp đính KHÔNG đi theo", async () => {
    // Lỗi đo được ngày 07/10/2026, và nó là lỗi của **tuổi thọ**: `scope` có hai đường
    // ghi và không đường xoá nào, còn `App.tsx` mount `<Chat>` ở ba chỗ mà không chỗ nào
    // truyền `key` — nên React tái dùng đúng một instance qua mọi chuyển cảnh. Thả chip
    // rồi bấm *Đoạn chat mới* cho ra một đoạn rỗng 0 lượt mà dải còn nguyên chữ cũ.
    //
    // Test này đổi prop **tại chỗ** chứ không `unmount()`: `unmount` dựng lại state và do
    // đó đi vòng qua đúng cái lỗi — đó là đường mà test cũ đi, và vì thế nó xanh suốt.
    serving();
    const view = render(<Chat conversationId="c1" fresh={false} openPaper={null} />);
    await waitFor(() => expect(screen.getByText("de-cuong.pdf")).toBeTruthy());
    await attach(view);

    view.rerender(<Chat conversationId="c2" fresh={false} openPaper={null} />);

    await waitFor(() =>
      expect(view.container.querySelector(".scope-strip")).toBeNull(),
    );
  });

  it("bấm Đoạn chat mới thì tệp đính cũng không đi theo", async () => {
    // Đúng đường người dùng đã đi lúc phát hiện ra lỗi: route sang `/teacher/moi`, tức
    // `conversationId` thành `null` và `fresh` thành `true`.
    serving();
    const view = render(<Chat conversationId="c1" fresh={false} openPaper={null} />);
    await waitFor(() => expect(screen.getByText("de-cuong.pdf")).toBeTruthy());
    await attach(view);

    view.rerender(<Chat conversationId={null} fresh openPaper={null} />);

    await waitFor(() =>
      expect(view.container.querySelector(".scope-strip")).toBeNull(),
    );
  });

  it("gửi câu đi rồi thì tệp đính được dọn", async () => {
    // Tệp thuộc về **câu vừa gửi**, nên nó chết cùng câu ấy. Giữ lại là để một câu sau
    // thừa hưởng một phạm vi không ai chọn cho nó.
    serving();
    const sent = vi.spyOn(teacher, "stream").mockResolvedValue(undefined);
    const view = render(<Chat conversationId="c1" fresh={false} openPaper={null} />);
    await waitFor(() => expect(screen.getByText("de-cuong.pdf")).toBeTruthy());
    await attach(view);

    fireEvent.change(screen.getByLabelText("Nhắn cho Kriky"), {
      target: { value: "soạn cho tôi một đề" },
    });
    fireEvent.click(screen.getByText("Gửi"));

    await waitFor(() => expect(sent).toHaveBeenCalled());
    await waitFor(() =>
      expect(view.container.querySelector(".scope-strip")).toBeNull(),
    );
    sent.mockRestore();
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
        // Đề đã duyệt thì panel dựng luôn cài đặt phát hành, nên đường này phải có.
        const body = url.includes("/publish-form") ? FORM : paper(state);
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }),
    );
    return calls;
  }

  function mount() {
    return render(
      <Panel
        assessmentId="p1"
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

    // Tầng ĐỀ BÀI mở sẵn; phương án nằm sau một cú bấm, như mọi tầng khác.
    expect(screen.getByLabelText("Đề bài")).toBeTruthy();
    openTang("Phương án");
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

  /**
   * Mở thẻ câu 1 ở trạng thái đang sửa, và mở sẵn một tầng.
   *
   * @param tang - Tầng cần làm việc. Mặc định `Phương án`, vì phần lớn test ở đây nói
   *   về phương án.
   */
  async function editing(tang: "Phương án" | "Cách giải" = "Phương án") {
    const view = render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());
    fireEvent.click(screen.getByText("Sửa"));
    await waitFor(() => expect(screen.getByText("Lưu")).toBeTruthy());
    openTang(tang);
    return view;
  }

  it("mỗi phương án nhiễu có ô gõ nhãn lỗi", async () => {
    // Không có ô này thì nút *Thêm phương án* chỉ dẫn tới một lần 422: ADR-18 bắt mọi
    // phương án nhiễu phải có nhãn lỗi, và `validate_question` thi hành đúng luật ấy.
    serving();
    await editing();

    expect(screen.getByLabelText("Lỗi của B")).toBeTruthy();
    // Đáp án đúng thì không: `error_label` null ở đúng dòng của nó (`models.py`).
    expect(screen.queryByLabelText("Lỗi của A")).toBeNull();
  });

  it("thêm một phương án thì nó lấy chữ cái còn trống đầu tiên", async () => {
    serving();
    await editing();

    fireEvent.click(screen.getByText("+ Thêm phương án"));

    expect(screen.getByText("Phương án C")).toBeTruthy();
    expect(screen.getByLabelText("Lỗi của C")).toBeTruthy();
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
    const { container } = await editing("Cách giải");

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
    await editing("Cách giải");

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
    fireEvent.change(screen.getByLabelText("Lỗi của C"), {
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

describe("ký tự điều khiển ẩn trong ô sửa", () => {
  afterEach(() => vi.unstubAllGlobals());

  /** Một đề còn mở, với đúng bộ byte đã đo được trong database ngày 05/10/2026. */
  function mangled() {
    const FF = String.fromCharCode(0x0c);
    const TAB = String.fromCharCode(0x09);
    const one = paper("has_questions");
    one.questions[0].stem = `Tính $I = ${FF}rac{1}{2} ${TAB}imes 3$`;
    one.questions[0].methods = [
      { title: "Cách 1", body: "Bước một.\nBước hai." },
      { title: "Cách 2", body: "Dùng định nghĩa." },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(one) })),
    );
    return one;
  }

  async function open() {
    const view = render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());
    fireEvent.click(screen.getByText("Sửa"));
    await waitFor(() => expect(screen.getByText("Lưu")).toBeTruthy());
    return view;
  }

  it("ký tự hỏng hiện ra bằng ký hiệu đọc được, và ô nhập vẫn giữ nguyên byte gốc", async () => {
    // Chính sách đã chốt là *"giáo viên tự sửa tay"*. Đo được trên trình duyệt rằng nó
    // không đi được: 7 trong 12 ô chứa ký tự điều khiển, mà chúng VÔ HÌNH trong textarea.
    // Giáo viên nhìn thấy `$rac{1}{6}$`, gõ thêm dấu gạch chéo vào trước, và vẫn hỏng.
    const data = mangled();
    const { container } = await open();

    const note = container.querySelector(".mangled");
    expect(note).not.toBeNull();
    expect(note!.textContent).toContain("2 ký tự hỏng");
    expect(note!.textContent).toContain("␌");
    expect(note!.textContent).toContain("␉");

    // Và đây là nửa quan trọng hơn: ô nhập KHÔNG bị đổi. Nếu đổi, ký hiệu sẽ theo nút
    // Lưu xuống database và một lỗi hiển thị thành một lỗi dữ liệu.
    const stem = screen.getByLabelText("Đề bài") as HTMLTextAreaElement;
    expect(stem.value).toBe(data.questions[0].stem);
    expect(stem.value).toContain(String.fromCharCode(0x0c));

  });

  it("DEL hiện ra ␡, không phải một ký hiệu vô nghĩa", async () => {
    // Khối Control Pictures đặt ký hiệu của `c` tại `U+2400 + c` cho 0x00–0x1F, nhưng
    // DEL (0x7F) nằm **riêng** ở U+2421. Bỏ ca riêng thì `0x2400 + 0x7f` ra `U+247F` —
    // ký hiệu "khoanh số 12", vô nghĩa hoàn toàn trước mặt giáo viên.
    const one = paper("has_questions");
    one.questions[0].stem = `Tính $x${String.fromCharCode(0x7f)}$`;
    one.questions[0].methods = [
      { title: "Cách 1", body: "Đạo hàm." },
      { title: "Cách 2", body: "Định nghĩa." },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(one) })),
    );
    const { container } = await open();

    expect(container.querySelector(".mangled")!.textContent).toContain("␡");
  });

  it("xuống dòng thật không bị gọi là ký tự hỏng", async () => {
    // Lời giải nào cũng có xuống dòng. Cảnh báo ở mọi ô là cảnh báo không ai đọc.
    mangled();
    const { container } = await open();

    const notes = [...container.querySelectorAll(".mangled")];
    const bodies = notes.filter((n) => n.textContent?.includes("Bước một"));
    expect(bodies.length).toBe(0);
  });

  it("chữ sạch thì không có cảnh báo nào", async () => {
    const one = paper("has_questions");
    one.questions[0].methods = [
      { title: "Cách 1", body: "Đạo hàm." },
      { title: "Cách 2", body: "Định nghĩa." },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(one) })),
    );
    const { container } = await open();

    expect(container.querySelectorAll(".mangled").length).toBe(0);
  });
});

describe("thẻ kể TRẠNG THÁI của đề, không kể từng cú bấm", () => {
  it("duyệt rồi hoàn tác cho ra MỘT thẻ, và nó quay về nấc đã tạo đề", () => {
    // Một đợt xử lí cho đúng một thẻ. Duyệt → hoàn tác → duyệt lại là một trạng thái đi
    // qua bốn bước, không phải bốn kết quả — đo được trên hội thoại thật: bốn lượt trong
    // database cho ra bốn thẻ chồng nhau nói luân phiên hai câu.
    //
    // Và bỏ duyệt đưa đề VỀ nấc một — chính lượt `teacher.unapprove` vẽ ra thẻ ấy, chứ
    // không phải một lượt cũ nào đó của model. Bản trước trả thẻ của model ở đây và nó
    // **mất thẻ** ở ca không có việc model nào trong khối; test ngay dưới đo đúng ca đó.
    const base = [
      blank({ kind: "plan", tool_result: { steps: ["Soạn 3 câu"], total: 1 } }),
      blank({
        kind: "tool_result",
        tool_name: "start_drafting",
        entity_kind: "assessment",
        entity_id: "p1",
        tool_result: { started: true, assessment_id: "p1", asked_for: 3, written: 3 },
      }),
    ];
    const approve = blank({
      kind: "tool_result",
      tool_name: "teacher.approve",
      entity_kind: "assessment",
      entity_id: "p1",
      tool_result: { approved: true, assessment_id: "p1", questions: 3 },
    });
    const undo = blank({
      kind: "tool_result",
      tool_name: "teacher.unapprove",
      entity_kind: "assessment",
      entity_id: "p1",
      tool_result: { unapproved: true, assessment_id: "p1", questions: 3 },
    });

    // Nấc hai.
    expect(cardTurns([...base, approve]).map((o) => o.tool_name)).toEqual([
      "teacher.approve",
    ]);

    // Hoàn tác → về nấc một, vẫn đúng một thẻ, và nấc đọc được là `drafted`.
    const after = cardTurns([...base, approve, undo]);
    expect(after.map((o) => o.tool_name)).toEqual(["teacher.unapprove"]);
    expect(cardState(after[0])).toBe("drafted");

    // Và bấm bốn lần cũng vẫn một thẻ.
    expect(
      cardTurns([...base, approve, undo, approve, undo]).map((o) => o.tool_name),
    ).toEqual(["teacher.unapprove"]);
  });

  it("hoàn tác trong một khối KHÔNG có việc nào của model vẫn còn thẻ", () => {
    // Ca có thật, và bản trước mất thẻ ở đúng đây. `blocks()` chỉ cắt khối ở lượt
    // `teacher` **gõ tay**, mà hai cú bấm trên panel không sinh lượt nào như thế — nên
    // một giáo viên gõ "cảm ơn", mở một đề cũ từ danh sách, bấm Duyệt rồi bấm Hoàn tác
    // có cả hai cú bấm rơi vào một khối không có `tool_result` nào của model.
    //
    // Bản trước trả thẻ của model ở nhánh `teacher.unapprove`, mà ở đây model không có
    // thẻ nào, nên màn hình còn **0 thẻ**: thẻ `Đã duyệt đề` biến mất cùng với cửa duy
    // nhất vào panel đề.
    const approve = blank({
      kind: "tool_result",
      tool_name: "teacher.approve",
      entity_kind: "assessment",
      entity_id: "p1",
      tool_result: { approved: true, assessment_id: "p1", title: "Tích phân" },
    });
    const undo = blank({
      kind: "tool_result",
      tool_name: "teacher.unapprove",
      entity_kind: "assessment",
      entity_id: "p1",
      tool_result: { unapproved: true, assessment_id: "p1", title: "Tích phân" },
    });

    const only = cardTurns([approve, undo]);
    expect(only.length).toBe(1);
    expect(cardState(only[0])).toBe("drafted");

    render(
      <ActionCard
        turn={only[0]}
        onOpen={() => undefined}
        onCompose={() => undefined}
      />,
    );
    expect(screen.getByText('Đã tạo đề "Tích phân"')).toBeTruthy();
  });

  it("một lượt của model vẫn chỉ cho ra MỘT thẻ", () => {
    // Luật cũ không bị nới ra cho model: một lượt là một việc được nhờ, dù nó đi qua năm
    // bước tool, nên nó có một kết quả.
    const turns = [
      blank({
        kind: "tool_result",
        tool_name: "create_draft",
        tool_result: { created: true, title: "Tích phân", question_count: 0 },
      }),
      blank({
        kind: "tool_result",
        tool_name: "start_drafting",
        tool_result: { started: true, written: 1, asked_for: 1, still_drafting: 0 },
      }),
    ];

    expect(cardTurns(turns).length).toBe(1);
  });
});

describe("ranh giới của một lượt là lượt plan, không phải số bước đã có", () => {
  afterEach(() => vi.unstubAllGlobals());

  /** Đúng chuỗi lượt đã đo trong database: một tool TRƯỢT trước khi plan kịp tồn tại. */
  const MISSED = [
    blank({ kind: "teacher", text: "Soạn 3 câu vào đề đi" }),
    blank({
      kind: "tool_result",
      tool_name: "start_drafting",
      tool_result: { error: "start_drafting chỉ nêu được trong plan, không gọi ngay" },
    }),
    blank({ kind: "assistant", text: "Mình sẽ soạn 3 câu cho đề đã tạo." }),
    blank({ kind: "plan", tool_result: { steps: ["Soạn 3 câu hỏi"], total: 1 } }),
    blank({
      kind: "tool_result",
      tool_name: "start_drafting",
      entity_kind: "assessment",
      entity_id: "p1",
      tool_result: { started: true, asked_for: 3, written: ["a", "b", "c"] },
    }),
    blank({ kind: "assistant", text: "Mình đã soạn xong đề với đủ 3 câu hỏi." }),
  ];

  it("câu mở đầu không bị câu kết nuốt mất khi một tool trượt trước plan", async () => {
    // Đo được trên hội thoại thật: câu "Mình sẽ soạn 3 câu cho đề đã tạo." có trong
    // database mà KHÔNG có trên màn hình. Bản trước phân biệt lời mở với câu kết bằng
    // `steps.length === 0`, và bước trượt ở trên làm `steps` tăng lên 1 trước khi câu ấy
    // tới — nên nó rơi vào `conclusion` rồi bị câu kết đè.
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(
              url.startsWith("/api/teacher/chat")
                ? { ...SPOKEN, turns: MISSED }
                : [],
            ),
        }),
      ),
    );

    render(
      <Chat
        conversationId="c1"
        fresh={false}
        openPaper={null}
      />,
    );

    await waitFor(() =>
      expect(document.querySelectorAll(".reply-text").length).toBeGreaterThan(0),
    );

    const said = [...document.querySelectorAll(".reply-text")].map(
      (one) => one.textContent ?? "",
    );
    expect(said.some((one) => one.includes("Mình sẽ soạn 3 câu"))).toBe(true);
    expect(said.some((one) => one.includes("đã soạn xong"))).toBe(true);
  });
});

describe("đường về từ màn cài đặt phát hành", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("Hoàn tác xong là panel tự quay về nội dung đề", async () => {
    // Việc này từng cần một cú điều hướng (`onUnpublish`) chỉ để gỡ hậu tố `/phat-hanh`
    // khỏi hash — một việc sinh ra vì màn hình đọc nấc từ route. Nay nấc đọc từ `state`,
    // nên bỏ duyệt xong là biểu mẫu biến mất và chân panel quay lại, không URL nào phải
    // đổi. Test đo **màn hình**, không đo cách đi tới nó.
    let state = "approved";
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const method = (init?.method ?? "GET").toUpperCase();
        if (method === "POST" && url.endsWith("/unapprove")) state = "has_questions";
        const body = url.includes("/publish-form") ? FORM : paper(state);
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }),
    );

    const { container } = render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );

    await waitFor(() => expect(screen.getByText("Hoàn tác")).toBeTruthy());
    fireEvent.click(screen.getByText("Hoàn tác"));

    await waitFor(() => expect(screen.getByText("Duyệt đề")).toBeTruthy());
    expect(container.querySelector(".publish-settings")).toBeNull();
  });
});

describe("đổi đáp án đúng, và chặn cửa sổ thời gian vô lý", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("bấm radio của B rồi Lưu: payload có ĐÚNG MỘT đáp án đúng, và nó là B", async () => {
    // Trước đợt này phương án đúng chỉ có một cái nhãn và không control nào, nên thứ duy
    // nhất hỏng ở một câu model soạn sai lại là thứ duy nhất giáo viên không sửa được.
    // Đo được trên dữ liệu thật: một câu có đáp án đúng là 1/2, bốn phương án không chứa
    // 1/2, và 1/3 đang đeo dấu đúng.
    const calls: { url: string; method: string; body: string }[] = [];
    const one = paper("has_questions");
    one.questions[0].methods = [
      { title: "Cách 1", body: "Đạo hàm." },
      { title: "Cách 2", body: "Định nghĩa." },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        calls.push({
          url,
          method: (init?.method ?? "GET").toUpperCase(),
          body: typeof init?.body === "string" ? init.body : "",
        });
        return Promise.resolve({ ok: true, json: () => Promise.resolve(one) });
      }),
    );

    render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());
    fireEvent.click(screen.getByText("Sửa"));
    await waitFor(() => expect(screen.getByText("Lưu")).toBeTruthy());
    openTang("Phương án");

    fireEvent.click(screen.getByLabelText("Đặt phương án B làm đáp án đúng"));

    // A vừa thôi là đáp án đúng, nên nó thành một phương án nhiễu CHƯA có nhãn lỗi —
    // ADR-18 cấm, và nút Lưu khoá lại kèm một câu tiếng Việt thay vì để giáo viên bấm
    // rồi nhận `distractors ['A'] carry no error label: <cả đề bài>` từ BE.
    expect(
      (screen.getByText("Lưu").closest("button") as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(document.querySelector(".refused")?.textContent).toContain(
      "Phương án A chưa có nhãn lỗi",
    );

    fireEvent.change(screen.getByLabelText("Lỗi của A"), {
      target: { value: "nhầm hệ số" },
    });
    fireEvent.click(screen.getByText("Lưu"));

    await waitFor(() =>
      expect(calls.some((c) => c.method === "PATCH")).toBe(true),
    );
    const sent = JSON.parse(calls.find((c) => c.method === "PATCH")!.body);
    const right = sent.options.filter(
      (o: { is_correct: boolean }) => o.is_correct,
    );
    expect(right.length).toBe(1);
    expect(right[0].label).toBe("B");

    // Và nhãn lỗi cũ của B KHÔNG bị xoá. `OptionEdit` nói thẳng rằng nhãn gửi kèm đáp án
    // đúng thì bị bỏ, không bị từ chối — nên xoá nó ở FE chỉ mua được một thứ: bấm nhầm
    // rồi bấm lại là mất chữ giáo viên đã gõ tay, không có undo nào.
    const b = sent.options.find((o: { label: string }) => o.label === "B");
    expect(b.error_label).not.toBe("");
  });

  it("chip lớp nói ra trạng thái chọn của nó, không chỉ đổi màu", async () => {
    // Đây là nút quyết định AI NHẬN ĐỀ (ADR-02). Thiếu `aria-pressed` thì trình đọc màn
    // hình đọc "12A, button" y hệt dù đã chọn hay chưa — dấu ✓ đã `aria-hidden`, và
    // `class-chip on` là chuyện của CSS.
    serveForm();
    render(<PublishSettings assessmentId="p1" onPublished={() => undefined} onUndo={() => undefined} undoing={false} />);
    await waitFor(() => expect(screen.getByText("12A")).toBeTruthy());

    const chip = screen.getByText("12A").closest("button")!;
    expect(chip.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(chip);
    expect(chip.getAttribute("aria-pressed")).toBe("true");
  });

  it("mở sau đóng: nút khoá, và câu từ chối là câu của BE", async () => {
    // Cổng thật vẫn ở BE. Chỗ này chỉ nói SỚM HƠN, bằng đúng chữ BE sẽ dùng — vì hai câu
    // luật ngay trên đang khẳng định một sự thật bất khả thi bằng giọng bình thản.
    serveForm();
    render(<PublishSettings assessmentId="p1" onPublished={() => undefined} onUndo={() => undefined} undoing={false} />);
    await waitFor(() => expect(screen.getByText("12A")).toBeTruthy());
    fireEvent.click(screen.getByText("12A").closest("button")!);

    const values = ["15", inHours(26), inHours(24), "5", inHours(32)];
    document.querySelectorAll(".publish-settings input").forEach((box, i) => {
      if (i < values.length) fireEvent.change(box, { target: { value: values[i] } });
    });

    await waitFor(() =>
      expect(document.querySelector(".trouble")?.textContent).toBe(
        "giờ đóng phải sau giờ mở",
      ),
    );
    const cta = screen.getByText("Phát hành đề").closest("button") as HTMLButtonElement;
    expect(cta.disabled).toBe(true);
  });
});


describe("ba lời từ chối, mỗi lời một lưới", () => {
  afterEach(() => vi.unstubAllGlobals());

  /** Mở biểu mẫu, chọn lớp, rồi gõ năm ô theo thứ tự của màn hình. */
  async function filled(values: string[]) {
    serveForm();
    render(<PublishSettings assessmentId="p1" onPublished={() => undefined} onUndo={() => undefined} undoing={false} />);
    await waitFor(() => expect(screen.getByText("12A")).toBeTruthy());
    fireEvent.click(screen.getByText("12A").closest("button")!);
    document.querySelectorAll(".publish-settings input").forEach((box, i) => {
      if (i < values.length) fireEvent.change(box, { target: { value: values[i] } });
    });
    return () =>
      (screen.getByText("Phát hành đề").closest("button") as HTMLButtonElement);
  }

  it("giờ mở ở quá khứ", async () => {
    const cta = await filled(["15", inHours(-2), inHours(24), "5", inHours(48)]);
    await waitFor(() =>
      expect(document.querySelector(".trouble")?.textContent).toBe(
        "giờ mở phải ở tương lai",
      ),
    );
    expect(cta().disabled).toBe(true);
  });

  it("hạn pha 2 nằm giữa giờ đóng và giờ NỘP CUỐI", async () => {
    // Mốc là `closes_at + phase1_minutes`, không phải giờ đóng — người vào đúng giây giờ
    // đóng vẫn còn cả thời gian làm bài (ADR-15). Đây là con số mà ADR-03 dành cả tài
    // liệu để chống, và BE vừa phải sửa đúng nó. Hạn dưới đây sau giờ đóng 10 phút nhưng
    // TRƯỚC giờ nộp cuối (đóng + 30), nên so với giờ đóng thì nó lọt.
    const cta = await filled([
      "30",
      inHours(24),
      inHours(26),
      "5",
      inHours(26 + 10 / 60),
    ]);
    await waitFor(() =>
      expect(document.querySelector(".trouble")?.textContent).toBe(
        "hạn pha 2 phải sau giờ nộp cuối của pha 1",
      ),
    );
    expect(cta().disabled).toBe(true);
  });

  it("số phút ngoài khoảng BE nhận thì KHÔNG đoán bừa là dùng được", async () => {
    // `-15` kéo mốc nộp cuối về TRƯỚC giờ đóng, nên một hạn pha 2 vô lý lọt qua phép so,
    // nút sáng lên, và BE trả một ValidationError của pydantic mà `.detail` là một mảng —
    // màn hình in ra `[object Object]`.
    const cta = await filled(["-15", inHours(24), inHours(26), "5", inHours(25)]);
    await waitFor(() => expect(cta().disabled).toBe(true));
  });
});


describe("shimmer chỉ ở bước đang chạy", () => {
  /** Một sự kiện SSE, mọi field có mặt — `grow` đọc cả những field nó không dùng. */
  function sse(some: Record<string, unknown>) {
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

  it("đúng MỘT hàng mang class running, và nó là bước đang chạy", () => {
    // Khối `Thinking` là bằng chứng đọc lại được (ADR-05): giáo viên mở nó ra SAU khi mọi
    // thứ xong để biết câu hỏi từ đâu ra. Cho cả khối động thì phần đã xong cũng trông như
    // đang xảy ra, và chỗ thật sự đang chạy chìm vào đó.
    //
    // jsdom không áp CSS nên nó không thấy dải sáng; thứ ghim được ở đây là CÁI TÊN — và
    // tên là thứ CSS bám vào. Hiệu ứng thật đo trên trình duyệt.
    const { container } = render(
      <Steps
        steps={[
          { mark: "done", title: "Tạo đề trống", result: "" },
          { mark: "running", title: "Soạn câu hỏi", result: "" },
          { mark: "done", title: "Chưa tới lượt", result: "" },
        ]}
        total={3}
      />,
    );

    const running = container.querySelectorAll(".step.running");
    expect(running.length).toBe(1);
    expect(running[0].textContent).toContain("Soạn câu hỏi");
  });

  it("shimmer ĐI XUỐNG theo bước: bước một xong thì bước hai sáng", () => {
    // Đây là phần mà một ảnh tĩnh không nói được, và cũng là phần dễ hỏng nhất: không
    // phải "có shimmer" mà là "shimmer ở ĐÚNG bước đang chạy tại mỗi lúc".
    //
    // Dựng chuỗi bằng chính `grow` — bộ dựng lượt-đang-chạy từ sự kiện SSE — nên test này
    // đi qua đúng đường mà một lượt thật đi, không phải một mảng `steps` bịa ra.
    let live = grow(null, sse({ kind: "plan", total: 2, titles: ["Tạo đề trống", "Soạn câu"] }));
    live = grow(live, sse({ kind: "step_started", title: "Tạo đề trống", index: 1, total: 2 }));

    const one = render(<Steps steps={live!.steps} total={live!.total} />);
    const sang = (view: { container: HTMLElement }) =>
      [...view.container.querySelectorAll(".step.running")].map((r) =>
        (r.textContent ?? "").replace(/^[○✓✕]/, ""),
      );
    expect(sang(one)).toEqual(["Tạo đề trống"]);
    one.unmount();

    live = grow(live, sse({ kind: "step_done", title: "Tạo đề trống", index: 1, total: 2 }));
    live = grow(live, sse({ kind: "step_started", title: "Soạn câu", index: 2, total: 2 }));

    const two = render(<Steps steps={live!.steps} total={live!.total} />);
    const rows = [...two.container.querySelectorAll(".step")];
    expect(rows.map((r) => r.className.includes("running"))).toEqual([false, true]);
    expect(sang(two)).toEqual(["Soạn câu"]);
  });

  it("lượt đã xong thì KHÔNG hàng nào sáng", () => {
    // Một khối mở lại sau khi xong mà vẫn nhấp nháy là một màn hình nói dối về thì.
    const { container } = render(
      <Steps
        steps={[
          { mark: "done", title: "Tạo đề trống", result: "" },
          { mark: "done", title: "Soạn câu hỏi", result: "— đã soạn 3/3 câu" },
        ]}
      />,
    );

    fireEvent.click(screen.getByText("Đã làm 2 bước"));
    expect(container.querySelectorAll(".step.running").length).toBe(0);
    expect(container.querySelectorAll(".step.done").length).toBe(2);
  });
});

describe("thẻ kết quả là một máy trạng thái ba nấc", () => {
  /**
   * Mọi tool có thể tới được một thẻ, kèm **đúng hình dạng `tool_result` mà BE ghi** và
   * đầu đề phải ra.
   *
   * Hình dạng thật, không phải hình dạng tiện tay. Bản trước của bảng này cho
   * `teacher.approve` một field `title` mà `_note` chưa bao giờ ghi, nên nó khẳng định
   * một đầu đề `Đã duyệt đề "Tích phân"` mà production **không dựng nổi** — thẻ duyệt
   * thật ra im lặng về tên đề. Một test dựng dữ liệu bịa thì đo chính nó.
   */
  const EVERY_TOOL: [string, Record<string, unknown>, string][] = [
    ["create_draft", { created: true, title: "Tích phân" }, 'Đã tạo đề "Tích phân"'],
    ["create_draft", { created: false, reason: "thiếu môn" }, "Không tạo được đề"],
    [
      "start_drafting",
      { started: true, title: "Tích phân", written: 3, asked_for: 3, still_drafting: 0 },
      'Đã tạo đề "Tích phân"',
    ],
    [
      "start_drafting",
      { started: true, title: "Tích phân", written: 2, asked_for: 10, still_drafting: 0 },
      'Đã tạo đề "Tích phân"',
    ],
    [
      "teacher.approve",
      { approved: true, assessment_id: "p1", title: "Tích phân", questions: 3 },
      'Đã duyệt đề "Tích phân"',
    ],
    [
      "teacher.unapprove",
      { unapproved: true, assessment_id: "p1", title: "Tích phân", questions: 3 },
      'Đã tạo đề "Tích phân"',
    ],
    [
      "teacher.publish",
      { published: true, assessment_id: "p1", classes: ["12A", "12B"] },
      "Đã phát hành",
    ],
  ];

  it("mỗi tool cho ra ĐÚNG đầu đề của nấc nó tới", () => {
    // Đây là nơi thi hành của luật người dùng chốt, và nó khẳng định **đẳng thức** chứ
    // không phải *thuộc một tập*. Bản trước dùng `toContain` trên một danh sách bốn
    // chuỗi, nên một tool bị gán sai nấc vẫn xanh miễn chuỗi kết quả còn nằm trong tập:
    // đột biến `?? "drafted"` thành `?? "published"` — mọi tool lạ nói *đã phát hành*,
    // tức bài đã tới tay học sinh — đi lọt qua cả test lẫn check thứ 12.
    for (const [tool, result, head] of EVERY_TOOL) {
      const { container, unmount } = render(
        <ActionCard
          turn={blank({ kind: "tool_result", tool_name: tool, tool_result: result })}
          onOpen={() => undefined}
          onCompose={() => undefined}
        />,
      );
      expect(
        container.querySelector(".action-card .head .what")?.textContent,
        tool,
      ).toBe(head);
      unmount();
    }
  });

  it("một tool không có nấc nào thì KHÔNG vẽ thẻ", () => {
    // Mặc định an toàn. Bản trước mặc định `drafted`, nên một tool chưa ai biết làm gì
    // cho ra một thẻ khẳng định *một cái đề đã tồn tại và đang chờ duyệt*. Một thẻ vắng
    // mặt tệ hơn — nhưng tệ theo cách nhìn thấy được.
    const stranger = blank({
      kind: "tool_result",
      tool_name: "mot_tool_nao_do",
      tool_result: { created: true },
    });

    expect(cardState(stranger)).toBeNull();
    // Và `cardTurns` không chọn nó làm thẻ, nên đường kia không tới được.
    expect(cardTurns([stranger])).toEqual([]);

    const { container } = render(
      <ActionCard
        turn={stranger}
        onOpen={() => undefined}
        onCompose={() => undefined}
      />,
    );
    expect(container.querySelector(".action-card")).toBeNull();
  });

  it("đề vừa mở còn rỗng thì thẻ mời bước tiếp theo", () => {
    // Variant `tạo-đề-trống` của Figma: cùng nấc `drafted`, khác ở chỗ đề chưa có câu
    // nào nên có một nút mời. Không có test này thì đột biến `const empty = false` xoá
    // sạch nút và câu an toàn ấy mà cả 130 test lẫn check thứ 12 đều xanh — đo được.
    render(
      <ActionCard
        turn={blank({
          kind: "tool_result",
          tool_name: "create_draft",
          tool_result: { created: true, title: "Tích phân" },
        })}
        onOpen={() => undefined}
        onCompose={() => undefined}
      />,
    );

    expect(screen.getByText("Thêm câu hỏi")).toBeTruthy();
    expect(screen.getByText("Đề trống, chưa phát hành được")).toBeTruthy();
  });

  it("một việc KHÔNG xảy ra thì không đưa đề đi đâu cả", () => {
    // `failed` thắng mọi nấc khác. Thiếu điều này, một `create_draft` bị từ chối đọc ra là
    // `Đã tạo đề` — đo được trên trình duyệt thật, cho một cái đề không hề được tạo.
    for (const tool of ["create_draft", "start_drafting", "teacher.publish"]) {
      expect(
        cardState(
          blank({
            kind: "tool_result",
            tool_name: tool,
            tool_result: { error: "nổ ở đâu đó" },
          }),
        ),
      ).toBe("failed");
    }
  });

  it("bỏ duyệt đưa đề VỀ nấc một, không sinh nấc thứ tư", () => {
    expect(
      cardState(
        blank({
          kind: "tool_result",
          tool_name: "teacher.unapprove",
          tool_result: { unapproved: true },
        }),
      ),
    ).toBe("drafted");
  });
});

describe("tấm trượt phát hành thu được từ lề dưới", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("mở ra là BUNG, và thanh đầu nói ra nấc của nó", async () => {
    // Người dùng chốt ngày 06/10/2026: mặc định bung. Phát hành là việc giáo viên vừa
    // bấm để tới đây, nên mở ra đã thu là bắt họ bấm thêm một cú để thấy việc mình xin.
    serveForm();
    const { container } = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());

    expect(
      container.querySelector(".sheet-head")?.getAttribute("aria-expanded"),
    ).toBe("true");
    expect(container.querySelectorAll(".publish-settings input").length).toBe(5);
  });

  it("bấm thanh đầu thì ruột biểu mẫu RỜI khỏi cây DOM, không chỉ ẩn đi", async () => {
    // Đo trên trình duyệt ngày 06/10/2026: panel cao 911, biểu mẫu ăn 661,5 và phần câu
    // hỏi còn **111** — 19,5% cái đề đang được duyệt. Rời khỏi cây chứ không `hidden`:
    // năm ô nhập còn trong cây thì tab vẫn tới được, và tab vào một thứ không thấy là
    // một cái bẫy.
    serveForm();
    const { container } = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());

    fireEvent.click(screen.getByText("Cài đặt phát hành"));

    expect(container.querySelector(".publish-settings.thu")).toBeTruthy();
    expect(container.querySelectorAll(".publish-settings input").length).toBe(0);
    expect(
      container.querySelector(".sheet-head")?.getAttribute("aria-expanded"),
    ).toBe("false");
  });

  it("và bung lại ở ĐÚNG chỗ bấm đã thu nó", async () => {
    // Một chỗ bấm mở ra được thì phải đóng lại được ở đúng chỗ ấy — thanh đầu có mặt ở
    // cả hai nấc chính vì thế.
    serveForm();
    const { container } = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());

    fireEvent.click(screen.getByText("Cài đặt phát hành"));
    fireEvent.click(screen.getByText("Cài đặt phát hành"));

    expect(container.querySelectorAll(".publish-settings input").length).toBe(5);
  });

  it("biểu mẫu là HÀNG XÓM của phần câu hỏi, không phải một lớp nổi lên che", async () => {
    // Đây là phương án **A** của frame `519:1603`, và nó là một luật về cấu trúc chứ
    // không về CSS: hai khối là con trực tiếp của cùng một cột flex, câu hỏi đứng trước.
    // Nhờ thế phần câu hỏi lấy lại chỗ mà không cần biết gì về tấm trượt — `flex: 1` gặp
    // `flex: none`. Phương án B (nổi lên che) sẽ cần một `position: absolute` cộng một
    // `padding-bottom` bù đúng 53px, tức để lại 53px vĩnh viễn sau thanh đầu.
    //
    // jsdom không dựng bố cục nên nó không đo được pixel nào; thứ nó đo được là quan hệ
    // cha-con, và quan hệ ấy chính là chỗ hai phương án khác nhau.
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve(
              url.includes("/publish-form") ? FORM : paper("approved"),
            ),
        }),
      ),
    );
    const { container } = render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() =>
      expect(container.querySelector(".publish-settings")).toBeTruthy(),
    );

    const panel = container.querySelector(".panel");
    const kids = [...(panel?.children ?? [])];
    const questions = kids.findIndex((one) =>
      one.classList.contains("panel-questions"),
    );
    const sheet = kids.findIndex((one) =>
      one.classList.contains("publish-settings"),
    );
    expect(questions).toBeGreaterThanOrEqual(0);
    expect(sheet).toBeGreaterThan(questions);
  });
});

describe("hai ngăn của rail thu được bằng chính tiêu đề của chúng", () => {
  const THREADS = [
    {
      conversation_id: "c1",
      title: "Đề giữa kỳ",
      started_at: "2026-10-01T00:00:00+00:00",
      last_spoke_at: "2026-10-03T00:00:00+00:00",
    },
  ];

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("bấm tiêu đề khung thì CẢ khung đóng lại", async () => {
    // Ghi chú `129:2` trên Figma nói đúng câu này từ lâu: *"Thu gọn là thao tác CHÍNH,
    // kéo là tinh chỉnh. Bấm tiêu đề khung để đóng cả khung."* Bốn luật của ghi chú chưa
    // có dòng code nào, vì rail được sao chép theo artboard chứ không dựng thành
    // component. Đo trên trình duyệt ngày 06/10/2026: `.pane-head` là một `DIV`,
    // `cursor: auto`, không handler nào, và `.caret` có `transform: none` — cái mũi nhọn
    // hứa đúng việc này rồi lặng lẽ không làm.
    routes(SPOKEN, THREADS);
    const { container } = render(
      <Chat conversationId="c1" fresh={false} openPaper={null} />,
    );
    await waitFor(() => expect(screen.getByText("Đề giữa kỳ")).toBeTruthy());
    expect(container.querySelector(".pane.history .scroll")).toBeTruthy();

    fireEvent.click(screen.getByText("ĐOẠN CHAT"));

    expect(container.querySelector(".pane.history.thu")).toBeTruthy();
    expect(container.querySelector(".pane.history .scroll")).toBeNull();
    expect(
      container
        .querySelector(".pane.history .pane-toggle")
        ?.getAttribute("aria-expanded"),
    ).toBe("false");
  });

  it("nút tải lên đứng CẠNH nút thu, không nằm trong nó", async () => {
    // Một `<button>` trong một `<button>` là HTML không hợp lệ: trình duyệt tự gỡ lồng và
    // cú bấm vào nút trong rơi vào nút ngoài, nên bấm *tải lên* sẽ thu ngăn lại. Hàng
    // đoạn chat đã sập đúng cái bẫy này một lần — ở đó bấm *Xoá* mở đoạn chat.
    routes(SPOKEN, THREADS);
    const { container } = render(
      <Chat conversationId="c1" fresh={false} openPaper={null} />,
    );
    await waitFor(() => expect(screen.getByText("Đề giữa kỳ")).toBeTruthy());

    const upload = container.querySelector(".pane.documents .upload");
    expect(upload).toBeTruthy();
    expect(upload?.closest(".pane-toggle")).toBeNull();
    expect(container.querySelectorAll(".pane.documents button").length).toBe(2);
  });

  it("thu ngăn TÀI LIỆU thì thanh kéo IM", async () => {
    // `SPLIT_MIN` 120 tồn tại để không ngăn nào biến mất. Một ngăn đã thu thì con số ấy
    // không còn gì để bảo vệ, và kéo đường biên giữa một ngăn và một thanh đầu cao 27 là
    // kéo một thứ không có nghĩa.
    routes(SPOKEN, THREADS);
    const { container } = render(
      <Chat conversationId="c1" fresh={false} openPaper={null} />,
    );
    await waitFor(() => expect(screen.getByText("Đề giữa kỳ")).toBeTruthy());
    expect(container.querySelector(".split-handle")).toBeTruthy();

    fireEvent.click(screen.getByText("TÀI LIỆU"));

    expect(container.querySelector(".split-handle")).toBeNull();
  });

  it("thu một ngăn thì ngăn kia lấy hết chỗ trống — ở CẢ HAI chiều", async () => {
    // Chiều thu `TÀI LIỆU` đúng miễn phí vì `.pane.history` là `flex: 1`. Chiều kia thì
    // không: `.pane.documents` nhận một `style="flex: 0 0 225px"` từ JSX, và một chiều cao
    // ghim thì ghim cả lúc không còn ai tranh chỗ. Đo trên trình duyệt ngày 06/10/2026:
    // thu `ĐOẠN CHAT` để ngăn tài liệu đứng yên ở 225 và bỏ lại **368px** trắng dưới nó,
    // trong khi chiều ngược lại cho 568/27 kín chỗ.
    //
    // Lỗi chỉ lộ ra ở một trong hai chiều, và Figma vẽ đúng chiều kia — nên không phép so
    // hình nào thấy được nó. jsdom cũng không đo được pixel, nhưng nó đọc được thứ gây ra:
    // cái chiều cao inline có còn đó hay không.
    routes(SPOKEN, THREADS);
    const { container } = render(
      <Chat conversationId="c1" fresh={false} openPaper={null} />,
    );
    await waitFor(() => expect(screen.getByText("Đề giữa kỳ")).toBeTruthy());
    const docs = () => container.querySelector(".pane.documents") as HTMLElement;
    expect(docs().style.flex).not.toBe("");

    fireEvent.click(screen.getByText("ĐOẠN CHAT"));

    expect(docs().style.flex).toBe("");
  });

  it("nấc của TỪNG ngăn sống qua một lần tải lại, và không dùng chung một cờ", async () => {
    // Hai ngăn, hai khoá. Một cờ dùng chung thì thu một ngăn là thu cả hai, và đột biến
    // ấy vẫn xanh với một test chỉ đo một ngăn.
    routes(SPOKEN, THREADS);
    const first = render(
      <Chat conversationId="c1" fresh={false} openPaper={null} />,
    );
    await waitFor(() => expect(screen.getByText("Đề giữa kỳ")).toBeTruthy());
    fireEvent.click(screen.getByText("TÀI LIỆU"));
    first.unmount();

    const { container } = render(
      <Chat conversationId="c1" fresh={false} openPaper={null} />,
    );
    await waitFor(() => expect(screen.getByText("Đề giữa kỳ")).toBeTruthy());

    expect(container.querySelector(".pane.documents.thu")).toBeTruthy();
    expect(container.querySelector(".pane.history.thu")).toBeNull();
  });
});

describe("cài đặt phát hành nhớ cái giáo viên vừa gõ", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  /** Mở biểu mẫu và chờ nó dựng xong. */
  async function open(key = "p1") {
    const view = render(
      <PublishSettings
        assessmentId={key}
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());
    return view;
  }

  function values(): string[] {
    return [...document.querySelectorAll(".publish-settings input")].map(
      (box) => (box as HTMLInputElement).value,
    );
  }

  it("sáu ô sống qua một lần tải lại trang", async () => {
    // F5 từng là mất sạch. Lời cũ bảo đó là chủ ý theo ADR-02, nhưng ADR-02 cấm **hệ
    // thống tự nghĩ ra** một mốc giờ — khôi phục đúng chữ giáo viên vừa gõ không thêm
    // thông tin nào vào biểu mẫu, nó chỉ thôi vứt đi thông tin đã có.
    serveForm();
    const first = await open();
    fireEvent.click(screen.getByText("12A"));
    fill();
    const typed = values();
    first.unmount();

    await open();

    expect(values()).toEqual(typed);
    expect(
      screen.getByRole("button", { name: /12A/ }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("và nói ra rằng nó vừa khôi phục, kèm mốc đã gõ", async () => {
    // Khôi phục im lặng là khôi phục không hỏi. Mốc in bằng `moment()` — đúng hàm mọi
    // màn hình khác dùng — nên không có cách định dạng giờ thứ hai nào sinh ra ở đây.
    serveForm();
    const at = new Date(Date.now() - 3_600_000).toISOString();
    window.localStorage.setItem(
      "kriky.teacher.publish-draft.p1",
      JSON.stringify({
        picked: ["c1"],
        minutes: "15",
        opensAt: inHours(24),
        closesAt: inHours(26),
        perQuestion: "5",
        deadline: inHours(32),
        at,
      }),
    );

    const { container } = await open();

    const mark = container.querySelector(".draft-mark");
    expect(mark).toBeTruthy();
    expect(mark?.textContent).toContain(moment(at));
  });

  it("bỏ bản nháp thì sáu ô về trống VÀ khoá bị xoá", async () => {
    // Bỏ mà chỉ xoá trên màn thì lần mở sau nháp cũ sống lại — một nút nói dối.
    //
    // Nháp phải là nháp **đã khôi phục**, không phải nháp đang gõ: dòng báo chỉ có nghĩa
    // cho một thứ tới từ phiên trước. Kể lại việc giáo viên vừa làm một giây trước thì
    // nó thành tiếng ồn, và nút bỏ thành một cái bẫy ngay cạnh chỗ đang gõ.
    serveForm();
    window.localStorage.setItem(
      "kriky.teacher.publish-draft.p1",
      JSON.stringify({
        picked: ["c1"],
        minutes: "15",
        opensAt: inHours(24),
        closesAt: inHours(26),
        perQuestion: "5",
        deadline: inHours(32),
        at: new Date(Date.now() - 3_600_000).toISOString(),
      }),
    );
    await open();

    fireEvent.click(screen.getByText("Bỏ bản nháp"));

    expect(values()).toEqual(["", "", "", "", ""]);
    expect(
      screen.getByRole("button", { name: /12A/ }).getAttribute("aria-pressed"),
    ).toBe("false");
    expect(window.localStorage.getItem("kriky.teacher.publish-draft.p1")).toBeNull();
  });

  it("một nháp mang giờ mở đã quá khứ thì ĐỎ, bằng chữ của BE", async () => {
    // Đây là hàng rào của việc khôi phục hết: một bản nháp từ ba hôm trước mang một giờ
    // mở đã qua, và giáo viên sẽ bấm qua nó. `faultOf` so với `Date.now()` và mượn
    // nguyên `rules.opens_in_the_past` — chuỗi dưới đây lấy từ fixture, không gõ lại.
    serveForm();
    window.localStorage.setItem(
      "kriky.teacher.publish-draft.p1",
      JSON.stringify({
        picked: ["c1"],
        minutes: "15",
        opensAt: inHours(-48),
        closesAt: inHours(-46),
        perQuestion: "5",
        deadline: inHours(-40),
        at: new Date(Date.now() - 172_800_000).toISOString(),
      }),
    );

    await open();

    expect(screen.getByText(FORM.rules.opens_in_the_past)).toBeTruthy();
  });

  it("nháp của đề này KHÔNG chảy sang đề khác", async () => {
    // Sáu tham số là của một lần phát hành MỘT đề. Một khoá chung sẽ mang giờ của đề
    // tuần trước sang đề hôm nay, và hai thứ ấy không liên quan gì nhau.
    serveForm();
    const first = await open("p1");
    fireEvent.click(screen.getByText("12A"));
    fill();
    first.unmount();

    await open("p2");

    expect(values()).toEqual(["", "", "", "", ""]);
    expect(document.querySelector(".draft-mark")).toBeNull();
  });

  it("nấc thu/bung cũng sống qua một lần tải lại", async () => {
    // Lý do cũ cho việc nấc KHÔNG nhớ là biểu mẫu không nhớ giờ nào. Lý do ấy chết theo
    // đợt này, nên nấc đi theo.
    serveForm();
    const first = await open();
    fireEvent.click(screen.getByText("Cài đặt phát hành"));
    expect(document.querySelector(".publish-settings.thu")).toBeTruthy();
    first.unmount();

    const { container } = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );

    expect(container.querySelector(".publish-settings.thu")).toBeTruthy();
  });

  it("một biểu mẫu chưa ai gõ thì KHÔNG ghi nháp nào", async () => {
    // Ghi một bản nháp rỗng thì lần mở sau hiện một dòng *"bản nháp bạn gõ lúc…"* cho
    // một thứ không đáng nói, và nó chôn mất nháp thật nếu component mount lại trước khi
    // giáo viên kịp gõ.
    serveForm();
    await open();

    expect(window.localStorage.getItem("kriky.teacher.publish-draft.p1")).toBeNull();
    expect(document.querySelector(".draft-mark")).toBeNull();
  });
});

describe("cài đặt phát hành đọc lại giờ đã đặt, và khoá lại", () => {
  afterEach(() => vi.unstubAllGlobals());

  const OPENS = "2026-10-07T01:00:00+00:00";
  const CLOSES = "2026-10-07T02:30:00+00:00";
  const ENDS = "2026-10-08T15:00:00+00:00";

  /**
   * Gieo sẵn nấc **bung** rồi mở biểu mẫu.
   *
   * Từ 07/10/2026 một đề đã khoá mặc định **thu**. Các test ở đây hỏi *"tấm trượt nói gì"*,
   * không hỏi *"nó mở hay thu"* — nên chúng cần một trạng thái xác định, và `"1"` đúng là
   * trạng thái thật của một giáo viên đã từng tự bung. Chính cái mặc định có test riêng, và
   * test ấy **không** dùng helper này.
   */
  async function open() {
    window.localStorage.setItem("kriky.teacher.publish-open.p1", "1");
    const view = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());
    return view;
  }

  function boxes(): HTMLInputElement[] {
    return [...document.querySelectorAll(".publish-settings input")] as HTMLInputElement[];
  }

  it("một lớp đang giữ đề thì nói ĐỦ SÁU thông số của lớp đó", async () => {
    // `publish-form` chỉ nói lớp nào ĐANG giữ đề, không nói giữ với giờ nào. Giáo viên
    // muốn biết "12A mở lúc mấy giờ" trước đợt này chỉ còn cách đi hỏi học sinh —
    // endpoint trả lời câu ấy đã có từ lâu và **không chỗ nào trong FE gọi nó**.
    //
    // **Sáu, không ba.** Bản trước nói ba — giờ mở, giờ đóng, thu hồi tới — và biện minh
    // rằng ba cái kia nằm trong năm ô nhập. Lời biện minh ấy sập đúng lúc năm ô không
    // dựng, và nó đã sập mà **không test nào thấy**: đo 07/10/2026 trên đề `d3f40a77`,
    // phút làm bài, phút mỗi câu và hạn chữa của một đề ĐANG CHẠY không xuất hiện ở đâu
    // trên panel.
    serveForm({}, [heldBy("c1", "12A", OPENS, CLOSES, ENDS)]);
    const { container } = await open();

    await waitFor(() =>
      expect(container.querySelector(".published-to")).toBeTruthy(),
    );
    const said = container.querySelector(".published-row")?.textContent ?? "";
    expect(said).toContain("12A");
    // Tham số thô: giờ mở và phút làm bài. Hai câu luật của BE **không** nói hai thứ này
    // (câu pha 1 nói giờ đóng và mốc nộp cuối), nên chúng phải được nêu riêng.
    expect(said).toContain(`Mở ${moment(OPENS)} · làm bài 15 phút`);
    // Hai câu LUẬT, nguyên văn của BE. Khớp nguyên chuỗi chứ không `toContain` một mẩu:
    // một phép khớp chuỗi con ở đây sống sót được cả một cú đảo hai con số, vì "15 phút"
    // là chuỗi con của "15 phút/câu".
    expect(said).toContain("NOTE-MỘT-12A-TỪ-BE");
    expect(said).toContain("NOTE-HAI-12A-TỪ-BE");
    // Thu hồi được tới **giờ mở**, và con số ấy do BE nêu riêng chứ không do FE suy ra.
    expect(said).toContain(`Thu hồi được tới ${moment(OPENS)}`);
  });

  it("chip của lớp đang giữ đề thì THẤY nhưng KHOÁ", async () => {
    // Bỏ chip đi là giấu mất đúng thông tin giáo viên cần: 12A đang giữ đề.
    serveForm(
      {
        classes: [
          { class_id: "c1", name: "12A", student_count: 40, published: true },
          { class_id: "c2", name: "12B", student_count: 32, published: false },
        ],
      },
      [heldBy("c1", "12A", OPENS, CLOSES, ENDS)],
    );
    await open();

    expect(
      (screen.getByRole("button", { name: /12A/ }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(
      (screen.getByRole("button", { name: /12B/ }) as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it("còn lớp chưa nhận đề thì năm ô VẪN gõ được, và CTA còn đó", async () => {
    // Cách 1: khối chỉ đọc ở trên, biểu mẫu bên dưới vẫn làm việc cho lớp chưa nhận.
    serveForm(
      {
        classes: [
          { class_id: "c1", name: "12A", student_count: 40, published: true },
          { class_id: "c2", name: "12B", student_count: 32, published: false },
        ],
      },
      [heldBy("c1", "12A", OPENS, CLOSES, ENDS)],
    );
    await open();

    expect(boxes().every((box) => !box.disabled)).toBe(true);
    expect(screen.getByText("Phát hành đề")).toBeTruthy();
  });

  it("mọi lớp đã nhận đề thì năm ô KHOÁ, và KHÔNG có CTA", async () => {
    // Không còn lớp nào để phát hành thì không có việc nào để mời. Vắng mặt chứ không
    // khoá-kèm-lời-giải-thích: BE không có câu từ chối cho ca này, và ADR-03 giữ chỗ ấy
    // cho BE — bịa một câu tiếng Việt vào đây là dựng một nguồn chữ thứ hai.
    serveForm(
      {
        classes: [
          { class_id: "c1", name: "12A", student_count: 40, published: true },
          { class_id: "c2", name: "12B", student_count: 32, published: true },
        ],
      },
      [
        heldBy("c1", "12A", OPENS, CLOSES, ENDS),
        heldBy("c2", "12B", OPENS, CLOSES, ENDS),
      ],
    );
    await open();

    await waitFor(() => expect(boxes().every((box) => box.disabled)).toBe(true));
    expect(screen.queryByText("Phát hành đề")).toBeNull();
  });

  it("đã khoá thì KHÔNG ô nào, kể cả khi mọi lớp TRÙNG khung giờ", async () => {
    // Bản trước điền giá trị đã phát hành vào năm ô khoá, và nó chỉ đúng **tình cờ**:
    // năm cái ô diễn tả được MỘT khung giờ, còn `publications` khoá theo `(đề, lớp)` và
    // trả về một khung **mỗi lớp**. Ca trùng giờ là đúng cái ca mà sự tình cờ ấy xảy ra —
    // và đó cũng đúng là đường mà test cũ đi, nên nó xanh suốt trong khi ca thường gặp
    // hơn (hai lớp phát hành ở hai thời điểm, vì giờ mở mặc định là *ngay bây giờ*) thì
    // giấu mất ba thông số.
    serveForm(
      {
        classes: [
          { class_id: "c1", name: "12A", student_count: 40, published: true },
          { class_id: "c2", name: "12B", student_count: 32, published: true },
        ],
      },
      [
        heldBy("c1", "12A", OPENS, CLOSES, ENDS),
        heldBy("c2", "12B", OPENS, CLOSES, ENDS),
      ],
    );
    const { container } = await open();

    await waitFor(() =>
      expect(container.querySelectorAll(".published-row").length).toBe(2),
    );
    expect(boxes().length).toBe(0);
    expect(container.querySelector(".rules")).toBeNull();
    // Và mọi con số vẫn còn — cho TỪNG lớp, chứ không một bộ cho cả hai. Hai câu luật
    // mang tên lớp trong fixture, nên chúng cũng chứng minh "theo từng lớp".
    for (const [at, row] of [...container.querySelectorAll(".published-row")].entries()) {
      const lop = at === 0 ? "12A" : "12B";
      expect(row.textContent).toContain(`làm bài 15 phút`);
      expect(row.textContent).toContain(`NOTE-MỘT-${lop}-TỪ-BE`);
      expect(row.textContent).toContain(`NOTE-HAI-${lop}-TỪ-BE`);
    }
  });

  it("đề đã khoá thì tấm trượt mặc định THU", async () => {
    // Một biểu mẫu không bấm được là một biên bản, không phải chỗ làm việc — nên nó không
    // giữ chỗ của việc đang làm. Đo 07/10/2026, cửa sổ 854: đã khoá thì tấm trượt cao 455
    // và vùng câu hỏi còn 260.
    //
    // Không dùng `open()` ở đây: helper ấy gieo sẵn nấc bung, tức đi vòng qua đúng cái
    // đang được đo.
    serveForm(
      {
        classes: [
          { class_id: "c1", name: "12A", student_count: 40, published: true },
          { class_id: "c2", name: "12B", student_count: 32, published: true },
        ],
      },
      [heldBy("c1", "12A", OPENS, CLOSES, ENDS)],
    );
    const { container } = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );

    await waitFor(() =>
      expect(container.querySelector(".publish-settings.thu")).toBeTruthy(),
    );
    expect(screen.queryByText("LỚP")).toBeNull();
    // Thu là một **mặc định**, không phải một lựa chọn của ai — nên không ghi gì xuống.
    // Ghi nó là bịa ra một quyết định rồi gán cho giáo viên.
    expect(window.localStorage.getItem("kriky.teacher.publish-open.p1")).toBeNull();
  });

  it("nhưng giáo viên đã tự bung thì nó vẫn bung", async () => {
    // Ranh giới của luật trên, và là lý do `knows()` tồn tại: `readFlag` cho `true` cho cả
    // "đã ghi bật" lẫn "chưa ai ghi", nên nếu chỉ đọc cờ thì mỗi lần mở lại một đề đã khoá
    // sẽ đóng sập đúng tấm trượt mà họ vừa bung ra, và không có cách nào bắt nó mở.
    window.localStorage.setItem("kriky.teacher.publish-open.p1", "1");
    serveForm(
      {
        classes: [
          { class_id: "c1", name: "12A", student_count: 40, published: true },
        ],
      },
      [heldBy("c1", "12A", OPENS, CLOSES, ENDS)],
    );
    const { container } = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );

    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());
    expect(container.querySelector(".publish-settings.thu")).toBeNull();
  });

  it("đề CHƯA khoá thì vẫn mở sẵn như cũ", async () => {
    // Mặc định mới chỉ áp cho đề đã khoá. Một đề còn gõ được mà mở ra đã thu thì giáo viên
    // phải bấm một lần nữa cho mỗi lần soạn.
    serveForm();
    const { container } = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );

    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());
    expect(container.querySelector(".publish-settings.thu")).toBeNull();
  });

  it("publications hỏng thì tấm trượt KHÔNG thu, vì lời báo nằm trong thân nó", async () => {
    // Hai việc của đợt này triệt tiêu nhau nếu thiếu hàng rào thứ tư. Dòng "chưa đọc được
    // giờ" nằm **trong** thân tấm trượt; mà mọi ca nó sinh ra để nói đều là ca đề đã có
    // lớp giữ, và *mọi lớp đều giữ* — tức `locked`, tức mặc định **thu** — là ca thường
    // gặp nhất trong số đó. Thu khi ấy cho ra đúng trạng thái mà dòng này vừa được thêm
    // vào để chấm dứt. Một thông báo cần một cú bấm mới thấy thì không phải thông báo.
    //
    // Cố ý **không** gieo khoá: gieo là đi vòng qua đúng cái đang được đo.
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) =>
        String(path).endsWith("/publications")
          ? new Response("boom", { status: 500 })
          : new Response(
              JSON.stringify({
                ...FORM,
                classes: [
                  { class_id: "c1", name: "12A", student_count: 40, published: true },
                ],
              }),
              { status: 200 },
            ),
      ),
    );

    const { container } = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );

    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain(
        "Chưa đọc được giờ đã phát hành",
      ),
    );
    expect(container.querySelector(".publish-settings.thu")).toBeNull();
  });

  it("hai lớp lệch giờ thì mỗi lớp một khối, mỗi khối đủ sáu", async () => {
    // Ca thường gặp, và là ca đã lộ ra khuyết tật. Bản đầu dựng năm ô khoá RỖNG ở đây;
    // bản thứ hai bỏ năm ô đi nhưng để khối `ĐÃ PHÁT HÀNH` chỉ nói ba thông số, nên ba
    // thông số kia biến mất khỏi màn hình. Bản này: không ô nào, và mỗi lớp nói đủ sáu.
    //
    // Đo ngày 06/10/2026 trên đề `d3f40a77` đã phát hành cho 12A lúc 14:21 và 12B lúc
    // 15:26: tấm trượt ăn **805,5 trên 911** của panel, vùng câu hỏi còn **24 pixel**.
    // Ba trăm pixel để nói đúng một điều — *"có năm cái ô, và bạn không được chạm vào"* —
    // trong khi khối `ĐÃ PHÁT HÀNH` ngay trên đã nói đủ cho từng lớp. Sau khi sửa:
    // tấm trượt **381**, vùng câu hỏi **391**. (428/344 là mốc giữa, trước khi sửa thêm
    // một lớp CSS trùng tên; con số cuối là 381/391.)
    //
    // Hai câu luật đi theo cùng lý do: chúng điền từ chữ đang gõ, mà ở đây không ai gõ
    // gì, nên chúng in `--:--` ngay dưới một đề đang thật sự chạy.
    const late = "2026-10-07T07:00:00+00:00";
    serveForm(
      {
        classes: [
          { class_id: "c1", name: "12A", student_count: 40, published: true },
          { class_id: "c2", name: "12B", student_count: 32, published: true },
        ],
      },
      [
        heldBy("c1", "12A", OPENS, CLOSES, ENDS),
        heldBy("c2", "12B", late, ENDS, ENDS),
      ],
    );
    const { container } = await open();

    await waitFor(() =>
      expect(container.querySelectorAll(".published-row").length).toBe(2),
    );
    expect(boxes().length).toBe(0);
    expect(container.querySelector(".rules")).toBeNull();
    // Nhưng khối nói đủ thì vẫn còn, và chip vẫn cho thấy lớp nào đang giữ đề.
    expect(container.querySelectorAll(".class-chip").length).toBe(2);
    // Hai khối mang HAI giờ mở khác nhau — đúng cái mà một bộ năm ô không diễn tả nổi.
    const rows = [...container.querySelectorAll(".published-row")];
    expect(rows[0].textContent).toContain(`Mở ${moment(OPENS)}`);
    expect(rows[1].textContent).toContain(`Mở ${moment(late)}`);
    for (const [at, row] of rows.entries()) {
      const lop = at === 0 ? "12A" : "12B";
      expect(row.textContent).toContain("làm bài 15 phút");
      expect(row.textContent).toContain(`NOTE-MỘT-${lop}-TỪ-BE`);
      expect(row.textContent).toContain(`NOTE-HAI-${lop}-TỪ-BE`);
    }
  });

  it("một lời gọi publications hỏng KHÔNG được chặn biểu mẫu", async () => {
    // Nó thêm thông tin chứ không mở cổng nào. Và hình dạng lạ cũng phải sống sót: một
    // response 200 mang hình dạng khác từng đi thẳng vào `live` và làm TRẮNG cả biểu mẫu.
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) =>
        String(path).endsWith("/publications")
          ? new Response("{}", { status: 200 })
          : new Response(JSON.stringify(FORM), { status: 200 }),
      ),
    );
    const { container } = await open();

    expect(container.querySelector(".published-to")).toBeNull();
    expect(screen.getByText("Phát hành đề")).toBeTruthy();
    expect(boxes().length).toBe(5);
  });
});

describe("thẻ đang sửa mở một lúc một tầng", () => {
  afterEach(() => vi.unstubAllGlobals());

  function serving() {
    const one = paper("has_questions");
    one.questions[0].methods = [
      { title: "Cách 1", body: "Đạo hàm từng hạng tử." },
      { title: "Cách 2", body: "Dùng định nghĩa." },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(one) })),
    );
  }

  async function editing() {
    const view = render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("Sửa")).toBeTruthy());
    fireEvent.click(screen.getByText("Sửa"));
    await waitFor(() => expect(screen.getByText("Lưu")).toBeTruthy());
    return view;
  }

  it("vào màn thì ĐỀ BÀI mở, hai tầng kia đóng", async () => {
    // Bấm `Sửa` thường là vì đọc thấy một chữ sai trong đề bài, và tầng ấy cũng là tầng
    // nhẹ nhất nên nó không bắt ai cuộn ngay cú bấm đầu tiên.
    serving();
    const { container } = await editing();

    expect(screen.getByLabelText("Đề bài")).toBeTruthy();
    expect(container.querySelectorAll(".edit-option").length).toBe(0);
    expect(container.querySelectorAll(".edit-method").length).toBe(0);

    const heads = [...container.querySelectorAll(".tang-head")];
    expect(heads.map((one) => one.getAttribute("aria-expanded"))).toEqual([
      "true",
      "false",
      "false",
    ]);
  });

  it("mở CÁCH GIẢI thì PHƯƠNG ÁN RỜI khỏi cây DOM — đó là luật chặn chiều cao", async () => {
    // Đây là cả lý do của việc vẽ lại màn này. Đo ngày 06/10/2026 ở density Teacher,
    // trong khung `panel-questions` cao 658: bản phẳng **774**, tức tràn 116 — sửa một
    // câu là chắc chắn không thấy hết thẻ đang gõ, kể cả khi đề chỉ có một câu. Ba tầng
    // cho 226 / 647 / 363, và con số chặn trên là 647 CHỈ CHỪNG NÀO một lúc một tầng
    // còn đúng. Cho mở cả ba là về lại đúng 774.
    //
    // Rời khỏi cây chứ không `hidden`: một ô còn trong cây thì tab vẫn tới được, và tab
    // vào một thứ không nhìn thấy là một cái bẫy — cùng lý lẽ với tấm trượt phát hành.
    serving();
    const { container } = await editing();

    fireEvent.click(screen.getByText("Phương án"));
    expect(container.querySelectorAll(".edit-option").length).toBe(2);

    fireEvent.click(screen.getByText("Cách giải"));

    expect(container.querySelectorAll(".edit-option").length).toBe(0);
    expect(container.querySelectorAll(".edit-method").length).toBe(2);
    expect(container.querySelectorAll(".tang-head[aria-expanded='true']").length).toBe(1);
  });

  it("KHÔNG ô nào sống bằng `aria-label` trần", async () => {
    // Luật vừa đổi là *nhãn nhìn thấy được*, nên phép đo phải đo đúng cái đó. Một test
    // `getByLabelText` sẽ xanh y hệt với `aria-label` — tức xanh cho đúng cái bug: bản
    // phẳng có hai mươi ô nhập và **không** nhãn nào trên màn.
    //
    // Mỗi ô hoặc có một `<label for>` thật, hoặc trỏ `aria-labelledby` vào một chữ đang
    // hiện ra (tên tầng, hay chữ `Phương án B` trên hàng đầu của khối).
    serving();
    const { container } = await editing();

    // Cả BA tầng, kể cả tầng mở sẵn.
    for (const name of ["Phương án", "Cách giải", "Đề bài"]) {
      fireEvent.click(screen.getByText(name));
      const boxes = [...container.querySelectorAll(".qcard.editing textarea")];
      expect(boxes.length).toBeGreaterThan(0);
      for (const box of boxes) {
        expect(box.getAttribute("aria-label")).toBeNull();

        // Và nhãn phải **tồn tại và có chữ**. Một `aria-labelledby` trỏ vào id không có
        // thật vẫn là một chuỗi truthy, nên phép kiểm cũ xanh y hệt khi ô mất sạch tên —
        // tức xanh cho đúng cái bug nó sinh ra để chặn.
        // `getElementById`, không `querySelector`: `useId()` sinh id dạng `:r3:`, và dấu
        // hai chấm làm chuỗi ấy **không phải** một selector CSS hợp lệ — `#:r3:` ném
        // `SyntaxError` chứ không trả `null`, nên phép kiểm sẽ chết chứ không đỏ.
        const points = box.getAttribute("aria-labelledby");
        const named = points
          ? document.getElementById(points)
          : [...container.querySelectorAll("label")].find(
              (one) => one.getAttribute("for") === box.id,
            );
        expect(named).toBeTruthy();
        expect((named?.textContent ?? "").trim().length).toBeGreaterThan(0);
      }
    }
  });

  it("câu tóm trên thanh đầu đếm từ BẢN ĐANG GÕ, không từ câu gốc", async () => {
    // Một con số của một phút trước nằm ngay trên chỗ đang sửa thì tệ hơn hẳn không có
    // con số nào.
    serving();
    await editing();

    fireEvent.click(screen.getByText("Phương án"));
    expect(screen.getByText("· 2 · đúng: A")).toBeTruthy();

    fireEvent.click(screen.getByText("+ Thêm phương án"));
    expect(screen.getByText("· 3 · đúng: A")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("Đặt phương án B làm đáp án đúng"));
    expect(screen.getByText("· 3 · đúng: B")).toBeTruthy();
  });

  it("lời từ chối ở NGOÀI ba tầng, nên nó đọc được cả khi tầng gây ra nó đã thu", async () => {
    // Nút `Lưu` khoá theo dòng này. Để nó trong tầng `PHƯƠNG ÁN` thì thu tầng ấy lại là
    // màn hình khoá mà không nói vì sao — một biểu mẫu từ chối trong im lặng.
    serving();
    const { container } = await editing();

    fireEvent.click(screen.getByText("Phương án"));
    fireEvent.click(screen.getByLabelText("Đặt phương án B làm đáp án đúng"));
    expect(container.querySelector(".refused")?.textContent).toContain(
      "Phương án A chưa có nhãn lỗi",
    );

    fireEvent.click(screen.getByText("Đề bài"));

    expect(container.querySelectorAll(".edit-option").length).toBe(0);
    expect(container.querySelector(".refused")?.textContent).toContain(
      "Phương án A chưa có nhãn lỗi",
    );
    expect(
      (screen.getByText("Lưu").closest("button") as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("tên của một ô KHÔNG đổi khi bấm radio ở hàng khác", async () => {
    // `Phương án B` là tên của ô; `· đáp án đúng` là trạng thái, và trạng thái đã có
    // `aria-checked` của chính nhóm radio. Gộp cả hai vào tên thì tên một ô nhập đổi mỗi
    // lần giáo viên chạm vào một hàng khác.
    serving();
    await editing();
    fireEvent.click(screen.getByText("Phương án"));

    const before = screen.getByLabelText("Phương án B");
    fireEvent.click(screen.getByLabelText("Đặt phương án B làm đáp án đúng"));

    expect(screen.getByLabelText("Phương án B")).toBe(before);
    expect(screen.getByLabelText("Phương án A")).toBeTruthy();
  });
});

describe("icon rail đứng trên baseline của chữ", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("mực của MỌI icon chạm đáy khung 12", async () => {
    // Đây là bất biến mà luật nâng 1px của rail dựa vào, và nó là thứ duy nhất ở đây
    // jsdom đo được — luật kia là CSS thuần, canh bởi check 13.
    //
    // Vì sao luật ấy tồn tại: icon cao **12** còn thân chữ hoa chỉ cao **10**, nên một
    // icon căn giữa hộp dòng thò xuống dưới **baseline** đúng 1px. Baseline là đường mạnh
    // nhất trong một hàng chữ, nên cái gì chúi xuống dưới nó đọc ra là xệ — dù ba phép đo
    // tâm đều nói 0,00. Đo 06/10/2026: cột +1, tập giấy +1, lưới ô +1, ba chấm 0, và số 0
    // của ba chấm chỉ vì hình nó **hụt 1px ở đáy**, không phải vì nó đúng.
    //
    // Nên một icon vẽ hụt đáy sẽ đứng cao hơn baseline khi luật chung nâng nó lên. Test
    // này bắt đúng cái đó, bằng toạ độ trong `viewBox` chứ không bằng bố cục.
    routes(SPOKEN, [
      {
        conversation_id: "c1",
        title: "Đề giữa kỳ",
        started_at: "2026-10-01T00:00:00+00:00",
        last_spoke_at: "2026-10-03T00:00:00+00:00",
      },
    ]);
    const { container } = render(
      <Chat conversationId="c1" fresh={false} openPaper={null} />,
    );
    await waitFor(() => expect(screen.getByText("Đề giữa kỳ")).toBeTruthy());

    /** Mép dưới của mực một hình, tính cả nửa nét viền. */
    const inkBottom = (shape: Element): number => {
      const num = (name: string) => Number(shape.getAttribute(name) ?? 0);
      const half = shape.getAttribute("stroke") ? num("stroke-width") / 2 : 0;
      if (shape.tagName === "circle") return num("cy") + num("r") + half;
      return num("y") + num("height") + half;
    };

    const rows = [...container.querySelectorAll(".rail .destination")].map((one) => {
      const svg = one.querySelector(".icon svg") as SVGElement;
      const bottom = Math.max(...[...svg.children].map(inkBottom));
      return { label: one.querySelector(".label")?.textContent, bottom };
    });

    expect(rows.length).toBe(4);
    for (const row of rows) {
      // Chặn **hai** đầu. `>= 12` một mình thì một icon vẽ tràn (`cy 11 + r 2 = 13`)
      // vẫn xanh, dù nó cũng lệch baseline — chỉ lệch về phía kia.
      //
      // Biên trên là 12,5 chứ không 12, và lý do có thật: icon tập giấy là một khung **có
      // nét viền**, nên mực của nó là `0,5 + 11 + 0,625` = **12,125** — tràn đúng nửa nét
      // rồi bị SVG cắt ở mép. Nửa nét là cách vẽ một khung chạm mép, không phải một hình
      // vẽ sai.
      expect(row.bottom).toBeGreaterThanOrEqual(12);
      expect(row.bottom).toBeLessThanOrEqual(12.5);
    }
  });
});

describe("bốn chỗ review tìm ra, mỗi chỗ một đường test cũ không đi", () => {
  afterEach(() => vi.unstubAllGlobals());

  const OPENS = "2026-10-07T01:00:00+00:00";
  const CLOSES = "2026-10-07T02:30:00+00:00";
  const ENDS = "2026-10-08T15:00:00+00:00";
  const KEY = "kriky.teacher.publish-draft.p1";

  /**
   * Gieo sẵn nấc **bung** rồi mở biểu mẫu.
   *
   * Từ 07/10/2026 một đề đã khoá mặc định **thu**. Các test ở đây hỏi *"tấm trượt nói gì"*,
   * không hỏi *"nó mở hay thu"* — nên chúng cần một trạng thái xác định, và `"1"` đúng là
   * trạng thái thật của một giáo viên đã từng tự bung. Chính cái mặc định có test riêng, và
   * test ấy **không** dùng helper này.
   */
  function mount(id = "p1") {
    window.localStorage.setItem(`kriky.teacher.publish-open.${id}`, "1");
    return render(
      <PublishSettings
        assessmentId={id}
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );
  }

  function boxes(): HTMLInputElement[] {
    return [...document.querySelectorAll(".publish-settings input")] as HTMLInputElement[];
  }

  function seed(at: string) {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({
        picked: ["c1"],
        minutes: "15",
        opensAt: inHours(24),
        closesAt: inHours(26),
        perQuestion: "5",
        deadline: inHours(32),
        at,
      }),
    );
  }

  it("chỉ MỞ RA XEM thì mốc nháp không nhảy", async () => {
    // Effect ghi nháp cũng chạy lúc mount, và lúc ấy sáu giá trị đúng bằng bản vừa khôi
    // phục. Ghi lại ở đó là đóng một mốc mới cho một thứ giáo viên **không** vừa gõ: mở
    // màn lúc 15:00 thì lần F5 sau dòng báo nói "bản nháp bạn gõ 15:00", trong khi họ gõ
    // lúc 14:03. Test cũ chỉ đọc DOM nên không thấy — lời nói dối nằm trong
    // `localStorage`, và nó chỉ lộ ra ở lần mở **thứ ba**.
    const at = "2026-10-06T07:03:00.000Z";
    serveForm();
    seed(at);

    const view = mount();
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());
    view.unmount();

    expect(JSON.parse(window.localStorage.getItem(KEY)!).at).toBe(at);
  });

  it("nhưng gõ thêm một chữ thì mốc ĐƯỢC cập nhật", async () => {
    // Ranh giới của luật trên: im lặng khi không đổi gì, không phải im lặng mãi mãi.
    const at = "2026-10-06T07:03:00.000Z";
    serveForm();
    seed(at);

    mount();
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());
    fireEvent.change(boxes()[0], { target: { value: "25" } });

    await waitFor(() =>
      expect(JSON.parse(window.localStorage.getItem(KEY)!).minutes).toBe("25"),
    );
    expect(JSON.parse(window.localStorage.getItem(KEY)!).at).not.toBe(at);
  });

  it("phát hành xong là KHOÁ ngay, không đợi tải lại trang", async () => {
    // `form` chỉ tải một lần theo `assessmentId`, nên sau một lần phát hành thành công
    // `form.classes[].published` đứng im và `locked` không bật. Mọi test khác của khối
    // này mount với `published: true` **sẵn**, nên không test nào đi qua đường
    // phát-hành-rồi-khoá — và đó đúng là đường người dùng đi.
    let published = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, init?: RequestInit) => {
        const url = String(path);
        if (init?.method === "POST") {
          const body = JSON.parse(String(init.body));
          if (!body.preview) published = true;
          return new Response(
            JSON.stringify({
              assessment_id: "p1",
              state: "published",
              preview: Boolean(body.preview),
              classes: [
                {
                  class_id: "c1",
                  class_name: "12A",
                  published: true,
                  reason: "",
                  opens_at: OPENS,
                  closes_at: CLOSES,
                  remediation_deadline: ENDS,
                  withdrawable_until: OPENS,
                  phase_one_note: "NOTE-MOT",
                  phase_two_note: "NOTE-HAI",
                },
              ],
              rules: FORM.rules,
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/publications")) {
          return new Response(
            JSON.stringify({
              assessment_id: "p1",
              classes: published ? [heldBy("c1", "12A", OPENS, CLOSES, ENDS)] : [],
              rules: FORM.rules,
            }),
            { status: 200 },
          );
        }
        return new Response(
          JSON.stringify({
            ...FORM,
            classes: [{ class_id: "c1", name: "12A", student_count: 40, published }],
          }),
          { status: 200 },
        );
      }),
    );

    mount();
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());
    fireEvent.click(screen.getByText("12A"));
    fill();
    fireEvent.click(screen.getByText("Phát hành đề"));
    await waitFor(() => expect(screen.getByText("Phát hành đề kiểm tra?")).toBeTruthy());
    fireEvent.click(screen.getByText(/Phát hành cho \d+ học sinh/));

    // Khoá phải tới mà KHÔNG cần dựng lại component.
    await waitFor(() => expect(screen.queryByText("Phát hành đề")).toBeNull());
    expect(
      (screen.getByRole("button", { name: /12A/ }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("phát hành xong thì tấm trượt KHÔNG tự thu, vì thẻ kết quả nằm trong nó", async () => {
    // Mặc định "đã khoá thì thu" đọc sai ca này nếu không có hàng rào thứ ba. Đường đi có
    // thật: `publish` gọi `setDone(result.classes)` rồi `setReread(+1)`, `form` được đọc
    // lại, `locked` bật **giữa tay người đang dùng** — và thu lúc ấy thì thẻ `Outcome`
    // biến mất cùng khối `ĐÃ PHÁT HÀNH` mà giáo viên vừa tạo ra. Cú bấm quan trọng nhất
    // của màn hình trả lời bằng cách đóng sập chính nó.
    //
    // Cố ý **không** dùng `mount()`: helper ấy gieo sẵn nấc bung, tức đi vòng qua đúng
    // cái đang được đo. Đây là cách lỗi này lọt qua lần đầu.
    let published = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, init?: RequestInit) => {
        const url = String(path);
        if (init?.method === "POST") {
          const body = JSON.parse(String(init.body));
          if (!body.preview) published = true;
          return new Response(
            JSON.stringify({
              assessment_id: "p1",
              state: "published",
              preview: Boolean(body.preview),
              classes: [
                {
                  class_id: "c1",
                  class_name: "12A",
                  published: true,
                  reason: "",
                  opens_at: OPENS,
                  closes_at: CLOSES,
                  remediation_deadline: ENDS,
                  withdrawable_until: OPENS,
                  phase_one_note: "NOTE-MOT",
                  phase_two_note: "NOTE-HAI",
                },
              ],
              rules: FORM.rules,
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/publications")) {
          return new Response(
            JSON.stringify({
              assessment_id: "p1",
              classes: published ? [heldBy("c1", "12A", OPENS, CLOSES, ENDS)] : [],
              rules: FORM.rules,
            }),
            { status: 200 },
          );
        }
        return new Response(
          JSON.stringify({
            ...FORM,
            classes: [{ class_id: "c1", name: "12A", student_count: 40, published }],
          }),
          { status: 200 },
        );
      }),
    );

    const { container } = render(
      <PublishSettings
        assessmentId="p1"
        onPublished={() => undefined}
        onUndo={() => undefined}
        undoing={false}
      />,
    );
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());
    fireEvent.click(screen.getByText("12A"));
    fill();
    fireEvent.click(screen.getByText("Phát hành đề"));
    await waitFor(() => expect(screen.getByText("Phát hành đề kiểm tra?")).toBeTruthy());
    fireEvent.click(screen.getByText(/Phát hành cho \d+ học sinh/));

    // Khoá tới nơi…
    await waitFor(() => expect(screen.queryByText("Phát hành đề")).toBeNull());
    // …nhưng tấm trượt vẫn mở, và thứ giáo viên vừa làm vẫn còn trên màn hình.
    expect(container.querySelector(".publish-settings.thu")).toBeNull();
    await waitFor(() =>
      expect(container.querySelector(".published-to")).toBeTruthy(),
    );
  });

  it("đổi sang đề khác thì nháp của đề cũ KHÔNG chảy sang", async () => {
    // Test cũ `unmount()` trước khi mở đề thứ hai, nên nó không chạm ca này. `Panel` sống
    // qua một lần đổi `assessmentId` — mở một đề khác trong khi panel đang mở là đường
    // thật — và khi ấy sáu `useState` không khởi tạo lại, còn effect ghi (có
    // `assessmentId` trong deps) ghi giá trị của đề cũ vào khoá của đề mới.
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) => {
        const url = String(path);
        if (url.endsWith("/publications")) {
          return new Response(
            JSON.stringify({ assessment_id: "p1", classes: [], rules: FORM.rules }),
            { status: 200 },
          );
        }
        if (url.includes("/publish-form")) {
          return new Response(JSON.stringify(FORM), { status: 200 });
        }
        return new Response(JSON.stringify(paper("approved")), { status: 200 });
      }),
    );
    const view = render(
      <Panel
        assessmentId="p1"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());
    fireEvent.click(screen.getByText("12A"));
    fill();
    await waitFor(() => expect(window.localStorage.getItem(KEY)).toBeTruthy());

    view.rerender(
      <Panel
        assessmentId="p2"
        onClose={() => undefined}
        onApproved={() => undefined}
      />,
    );
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());

    expect(boxes().map((one) => one.value)).toEqual(["", "", "", "", ""]);
    expect(window.localStorage.getItem("kriky.teacher.publish-draft.p2")).toBeNull();
  });

  it("publications hỏng mà đề đã phát hành thì panel NÓI RA, bằng chữ của BE", async () => {
    // Luật ở chỗ này đã đổi **hai lần**, và lần nào cũng vì thứ chở sự thật đã dời chỗ.
    // Bản đầu: *"biểu mẫu vẫn còn thân"* — đúng khi năm ô còn kể được giờ. Bản hai: đã
    // khoá thì không dựng ô nào, nên khối `ĐÃ PHÁT HÀNH` là nguồn **duy nhất** — mà nó
    // dựng từ `live`, nên một lời gọi hỏng cho ra một panel **im lặng hoàn toàn** về một
    // đề đang chạy. Bản này: hỏng thì nói ra.
    //
    // Chữ sau dấu chấm là `detail` của BE **nguyên văn** — `call()` ném nó, và BE không
    // nói gì thì nó là `Lỗi {status}`. Không bịa một câu từ chối nào, đúng chỗ ADR-03 giữ.
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) =>
        String(path).endsWith("/publications")
          ? new Response("boom", { status: 500 })
          : new Response(
              JSON.stringify({
                ...FORM,
                classes: [
                  { class_id: "c1", name: "12A", student_count: 40, published: true },
                ],
              }),
              { status: 200 },
            ),
      ),
    );

    const { container } = mount();
    await waitFor(() => expect(screen.getByText("LỚP")).toBeTruthy());

    // Không khối nào, vì không biết gì để nói — nhưng màn hình **nói rằng** nó không biết.
    expect(container.querySelector(".published-to")).toBeNull();
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain(
        "Chưa đọc được giờ đã phát hành",
      ),
    );
    // `boom` không phải JSON nên không có `detail`; `call()` lùi về mã trạng thái.
    expect(screen.getByRole("status").textContent).toContain("Lỗi 500");
    // Và không ô nào, vì đề đã khoá. Chip vẫn cho thấy lớp nào đang giữ đề, và `Hoàn tác`
    // vẫn là đường lùi — hai thứ ấy không cần `publications` mới biết được.
    expect(boxes().length).toBe(0);
    expect(
      (screen.getByRole("button", { name: /12A/ }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(screen.getByText("Hoàn tác")).toBeTruthy();
  });
});

/**
 * Chip tài liệu: bốn trạng thái, và một kênh nói khi chúng đổi.
 *
 * ADR-27 gọi tên thứ mấy test này canh: *"Một chip trông dùng được mà chưa dùng được là một
 * chip nói dối."* Không test nào ở đây kiểm chip trông có đẹp không — việc ấy đo với Figma.
 * Chúng kiểm bốn điều khoản: mỗi trạng thái nói đúng câu của nó, số trang không bị bịa ra,
 * chỉ tài liệu sẵn sàng mới kéo được, và kênh chỉ **hích** chứ không chở dữ liệu.
 */
describe("rail: chip tài liệu bốn trạng thái", () => {
  const SIZE = 2_411_724;

  function paper(
    state: string,
    extra: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      document_id: "d1",
      filename: "SGK Giải tích 12.pdf",
      kind: "PDF",
      byte_size: SIZE,
      state,
      page_count: 184,
      fault: "",
      uploaded_at: "2026-10-08T00:00:00+00:00",
      ...extra,
    };
  }

  /**
   * Dựng `fetch` giả cho rail, có thể đẩy một tiếng hích vào kênh bất cứ lúc nào.
   *
   * @param library - Danh sách tài liệu; mỗi lần gọi lại trả phần tử kế tiếp, phần tử cuối
   *   lặp lại mãi. Nhờ vậy một test đo được *đọc lại sau khi nghe hích* mà không cần mock.
   * @param channel - `null` thì kênh gãy ngay, ngược lại là một stream điều khiển được.
   */
  function rail(
    library: Record<string, unknown>[][],
    channel: "open" | "broken" = "broken",
  ) {
    const reads: string[] = [];
    let nudge: (() => void) | null = null;
    let round = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.startsWith("/api/teacher/documents/stream")) {
          if (channel === "broken") return Promise.resolve({ ok: false });
          const body = new ReadableStream<Uint8Array>({
            start(controller) {
              nudge = () => controller.enqueue(new TextEncoder().encode("data: 1\n\n"));
            },
          });
          return Promise.resolve({ ok: true, body });
        }
        let out: unknown = [];
        if (url.startsWith("/api/teacher/documents")) {
          reads.push(url);
          out = library[Math.min(round++, library.length - 1)];
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(out),
          text: () => Promise.resolve(""),
        });
      }),
    );
    Element.prototype.scrollIntoView = vi.fn();
    return { reads, push: () => nudge?.() };
  }

  function show() {
    render(<Chat conversationId={null} fresh={true} openPaper={null} />);
  }

  it("mỗi trạng thái nói đúng câu của nó, và sẵn sàng thì không nói gì", async () => {
    for (const [state, say] of [
      ["processing", "Đang xử lý…"],
      ["no_text_layer", "Không đọc được chữ"],
      ["failed", "Xử lí lỗi. Hãy tải lại"],
    ] as const) {
      rail([[paper(state)]]);
      const screenOne = render(
        <Chat conversationId={null} fresh={true} openPaper={null} />,
      );
      await waitFor(() => expect(screen.getByText(say)).toBeTruthy());
      screenOne.unmount();
      vi.unstubAllGlobals();
    }

    rail([[paper("ready")]]);
    show();
    await waitFor(() =>
      expect(screen.getByText("SGK Giải tích 12.pdf")).toBeTruthy(),
    );
    // Không câu nào trong ba câu kia được xuất hiện: số trang trên dòng meta đã là bằng
    // chứng đã đọc được chữ, nên một dòng "Sẵn sàng" chỉ là nhiễu lặp lại.
    expect(screen.queryByText("Đang xử lý…")).toBeNull();
    expect(screen.queryByText("Không đọc được chữ")).toBeNull();
  });

  it("lý do cụ thể nằm trong title, không nằm trên chip", async () => {
    rail([
      [paper("no_text_layer", { fault: "Tệp PDF này không có trang nào." })],
    ]);
    show();
    await waitFor(() =>
      expect(screen.getByText("Không đọc được chữ")).toBeTruthy(),
    );

    // Chip in nhãn; `fault` — sáu giá trị chẩn đoán khác nhau — đi vào title. Mất chỗ này
    // là mất khả năng phân biệt "ảnh scan" với "không có trang nào".
    const chip = document.querySelector(".rail .document") as HTMLElement;
    expect(chip.title).toBe("Tệp PDF này không có trang nào.");
  });

  it("không có số trang thì không in ra, và không bao giờ in 0 trang", async () => {
    rail([[paper("ready", { page_count: null, filename: "ghi-chú.txt", kind: "TXT" })]]);
    show();
    await waitFor(() => expect(screen.getByText("ghi-chú.txt")).toBeTruthy());

    const meta = document.querySelector(".rail .document .meta") as HTMLElement;
    expect(meta.textContent).toBe("2,3 MB");
    expect(meta.textContent).not.toContain("trang");
  });

  it("chỉ tài liệu sẵn sàng mới kéo được", async () => {
    rail([[paper("ready"), paper("processing", { document_id: "d2" })]]);
    show();
    await waitFor(() =>
      expect(document.querySelectorAll(".rail .document")).toHaveLength(2),
    );

    const chips = document.querySelectorAll(".rail .document");
    expect(chips[0].getAttribute("draggable")).toBe("true");
    // ADR-27: màn hình đã có đủ thông tin để nói trước, nên thả một tài liệu chưa đọc xong
    // vào ô chat rồi nhận một câu từ chối khó hiểu là một lần im lặng có chủ ý.
    expect(chips[1].getAttribute("draggable")).toBe("false");
  });

  it("nghe một tiếng hích thì đọc lại danh sách", async () => {
    const { reads, push } = rail(
      [[paper("processing")], [paper("ready")]],
      "open",
    );
    show();
    await waitFor(() => expect(screen.getByText("Đang xử lý…")).toBeTruthy());
    expect(reads).toHaveLength(1);

    push();

    // Kênh **chỉ hích**: khung không chở hàng nào, nên màn hình phải tự đọc lại. Đó là thứ
    // làm nó tự lành — pub/sub của Redis không giữ lịch sử, nên một khung chở dữ liệu mà
    // mất đi là một chip sai vĩnh viễn.
    await waitFor(() => expect(reads.length).toBeGreaterThan(1));
    await waitFor(() => expect(screen.queryByText("Đang xử lý…")).toBeNull());
  });

  it("tệp quá trần thì không request nào rời trình duyệt", async () => {
    const { reads } = rail([[]]);
    show();
    await waitFor(() => expect(reads).toHaveLength(1));

    // Trình duyệt biết cỡ tệp ngay từ `file.size`. Đẩy hết 200 MB lên rồi mới nhận 413 là
    // bắt giáo viên chờ hàng chục giây để nghe một câu từ chối đã biết trước.
    const huge = new File(["x"], "to.pdf", { type: "application/pdf" });
    Object.defineProperty(huge, "size", { value: 101 * 1024 * 1024 });
    const picker = document.querySelector("input[type=file]") as HTMLInputElement;
    Object.defineProperty(picker, "files", { value: [huge] });
    fireEvent.change(picker);

    await waitFor(() => expect(screen.getByText(/lớn hơn 100 MB/)).toBeTruthy());
    expect(reads).toHaveLength(1);
  });

  it("kênh gãy thì rail vẫn vẽ thư viện đã đọc lúc mở", async () => {
    rail([[paper("ready")]], "broken");
    show();
    // Mất kênh chỉ là mất việc tự mới lại. Một lần F5 vẫn ra đúng, nên màn hình không được
    // phép trống hay báo lỗi vì chuyện ấy.
    await waitFor(() =>
      expect(screen.getByText("SGK Giải tích 12.pdf")).toBeTruthy(),
    );
  });
});
