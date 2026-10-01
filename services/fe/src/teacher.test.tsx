/**
 * Ba chỗ bề mặt giáo viên có thể giành một quyết định khỏi tay BE.
 *
 * Không test nào ở đây kiểm một màn hình trông có đúng không — việc đó làm bằng cách đo
 * với Figma. Chúng kiểm ba điều khoản mà một lần sửa vô ý có thể phá mà không ai thấy:
 * hộp xác nhận không được tự viết lại câu luật, một hành động đã xảy ra không được đọc ra
 * như lời model, và một câu vừa gửi không được hiện hai lần.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ActionCard from "./screens/teacher/ActionCard";
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
      vi.fn(async (path: string, init?: RequestInit) => {
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
      vi.fn(async (path: string, init?: RequestInit) => {
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
