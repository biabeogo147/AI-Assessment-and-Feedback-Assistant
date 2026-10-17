/**
 * Thẻ hỏi lại nhiều câu (ADR-32): từng câu một, không bỏ câu, tóm tắt, gửi gộp một lần.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Chat from "./screens/teacher/Chat";
import ClarifySteps, { merged } from "./screens/teacher/ClarifySteps";

const QUESTIONS = [
  { label: "Khối", text: "Đề dành cho khối nào?", choices: ["Khối 6", "Khối 7", "Khối 8"] },
  { label: "Số câu", text: "Bao nhiêu câu?", choices: ["5 câu", "10 câu", "15 câu"] },
  { label: "Phạm vi", text: "Phần nào?", choices: ["Tỉ lệ thức", "Hàm số", "Đạo hàm"] },
];

function card(onSend = vi.fn()) {
  render(
    <ClarifySteps
      lead="Mình cần biết thêm ba điều:"
      questions={QUESTIONS}
      other="Khác"
      onSend={onSend}
    />,
  );
  return onSend;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("thẻ hỏi lại nhiều câu", () => {
  it("hiện từng câu với Câu k/n; không sang câu sau khi chưa trả lời", () => {
    card();

    expect(screen.getByText("Câu 1/3 · Khối")).toBeTruthy();
    const next = screen.getByText("Câu sau ›") as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    expect((screen.getByText("‹ Câu trước") as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByText("Khối 7"));
    expect(next.disabled).toBe(false);
    fireEvent.click(next);
    expect(screen.getByText("Câu 2/3 · Số câu")).toBeTruthy();
  });

  it("lùi về câu trước giữ lựa chọn đã chọn", () => {
    card();
    fireEvent.click(screen.getByText("Khối 7"));
    fireEvent.click(screen.getByText("Câu sau ›"));

    fireEvent.click(screen.getByText("‹ Câu trước"));

    expect(screen.getByText("Khối 7").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Khối 6").getAttribute("aria-pressed")).toBe("false");
  });

  it("câu cuối mời xem lại; tóm tắt sửa được từng câu rồi gửi gộp một tin", () => {
    const onSend = card();
    fireEvent.click(screen.getByText("Khối 7"));
    fireEvent.click(screen.getByText("Câu sau ›"));
    fireEvent.click(screen.getByText("10 câu"));
    fireEvent.click(screen.getByText("Câu sau ›"));
    fireEvent.click(screen.getByText("Tỉ lệ thức"));
    fireEvent.click(screen.getByText("Xem lại ›"));

    expect(screen.getByText("Kiểm tra lại trước khi gửi")).toBeTruthy();
    // Sửa câu 2 từ màn tóm tắt.
    fireEvent.click(screen.getByText("10 câu"));
    expect(screen.getByText("Câu 2/3 · Số câu")).toBeTruthy();
    fireEvent.click(screen.getByText("5 câu"));
    fireEvent.click(screen.getByText("Câu sau ›"));
    fireEvent.click(screen.getByText("Xem lại ›"));
    fireEvent.click(screen.getByText("Gửi"));

    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("Khối: Khối 7 · Số câu: 5 câu · Phạm vi: Tỉ lệ thức");
  });

  it("lối Khác… ghi một câu trả lời riêng cho câu đang xem", () => {
    card();
    fireEvent.click(screen.getByText("Khác…"));
    fireEvent.change(screen.getByLabelText("Lựa chọn khác"), { target: { value: "khối 9" } });
    fireEvent.click(screen.getByText("Chọn"));

    expect(screen.getByText("Khác: khối 9").getAttribute("aria-pressed")).toBe("true");
    expect((screen.getByText("Câu sau ›") as HTMLButtonElement).disabled).toBe(false);
  });

  it("câu trả lời gộp mang nhãn từng câu", () => {
    expect(merged(QUESTIONS, ["Khối 7", "5 câu", "Hàm số"])).toBe(
      "Khối: Khối 7 · Số câu: 5 câu · Phạm vi: Hàm số",
    );
  });

  it("đọc lại sau F5: lượt hỏi nhiều câu đã lưu ra lại thẻ nhiều câu", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    const stored = {
      kind: "say",
      text: "",
      conversation_id: "c1",
      choices: [],
      more_choices: 0,
      turns: [
        { kind: "teacher", text: "soạn đề", tool_name: "", tool_result: {}, entity_kind: "", entity_id: "", choices: [], more_choices: 0, model_tokens: 0, duration_ms: 0 },
        {
          kind: "assistant",
          text: "Mình cần biết thêm ba điều:",
          tool_name: "",
          tool_result: { questions: QUESTIONS },
          entity_kind: "",
          entity_id: "",
          choices: [],
          more_choices: 0,
          model_tokens: 0,
          duration_ms: 0,
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(url.startsWith("/api/teacher/chat") ? stored : []),
        }),
      ),
    );

    render(<Chat conversationId="c1" fresh={false} openPaper={null} />);

    await waitFor(() => expect(screen.getByText("Câu 1/3 · Khối")).toBeTruthy());
    expect(document.querySelectorAll(".clarify.several")).toHaveLength(1);
  });
});
