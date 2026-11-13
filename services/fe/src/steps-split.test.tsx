/**
 * Lời chia việc trong khối các bước (ADR-38): lượt soạn theo dàn ý có **một** khối `Thinking`, lời
 * Kriky chia dàn ý thành câu đứng trong nó — dưới header, trên các bước — mở và thu cùng khối.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TurnEvent } from "./api";
import { grow } from "./screens/teacher/Chat";
import Steps, { type Step, toldIn } from "./screens/teacher/Steps";

const TOLD = {
  note: "Câu 1–2 lo **liệt kê**, câu 3 lo kí hiệu.",
  questions: 3,
};

function event(some: Record<string, unknown>): TurnEvent {
  return {
    kind: "",
    text: "",
    choices: [],
    more_choices: 0,
    conversation_id: "c",
    ended_as: "",
    title: "",
    detail: "",
    index: 0,
    total: 0,
    titles: [],
    began: 0,
    tool_name: "",
    result: null,
    ...some,
  } as TurnEvent;
}

const DONE: Step[] = [
  { mark: "done", title: "Tạo đề trống", result: "", planned: true },
  {
    mark: "done",
    title: "Soạn câu hỏi",
    result: "— đã soạn 3/3 câu",
    planned: true,
  },
];

describe("lời chia việc", () => {
  it("chỉ đọc ra khi có lời", () => {
    expect(toldIn(TOLD)).toEqual(TOLD);
    expect(toldIn({ note: "x" })).toEqual({ note: "x", questions: 0 });
    expect(toldIn({ note: "  ", questions: 2 })).toBeNull();
    expect(toldIn(undefined)).toBeNull();
    expect(toldIn("chữ")).toBeNull();
  });

  it("tới cùng sự kiện plan, và plan không soạn thì không có", () => {
    const drafted = grow(null, event({ kind: "plan", total: 2, split: TOLD }));
    const plain = grow(null, event({ kind: "plan", total: 1 }));

    expect(drafted.told).toEqual(TOLD);
    expect(plain.told).toBeNull();
  });
});

describe("khối các bước có lời chia việc", () => {
  it("đang soạn: một khối mở, lời chia việc đứng giữa header và các bước", () => {
    const running: Step[] = [
      DONE[0],
      { mark: "running", title: "Soạn câu hỏi", result: "", planned: true },
    ];

    render(<Steps steps={running} total={2} told={TOLD} />);

    expect(document.querySelectorAll(".steps-block")).toHaveLength(1);
    const head = document.querySelector(".steps-head") as Element;
    const note = document.querySelector(".split-note") as Element;
    const list = document.querySelector(".steps-list") as Element;
    expect(head.getAttribute("aria-expanded")).toBe("true");
    expect(head.compareDocumentPosition(note) & 4).toBe(4);
    expect(note.compareDocumentPosition(list) & 4).toBe(4);
    expect(screen.queryByText("liệt kê")).not.toBeNull();
  });

  it("đã xong: thu gọn cùng khối, bấm thì mở lại cả lời lẫn các bước", () => {
    render(<Steps steps={DONE} told={TOLD} />);

    const head = screen.getByRole("button", { name: "Đã làm 2 bước" });
    expect(head.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("liệt kê")).toBeNull();

    fireEvent.click(head);

    expect(screen.queryByText("liệt kê")).not.toBeNull();
    expect(document.querySelector(".steps-list")).not.toBeNull();
  });

  it("dừng giữa chừng: khối mở, không thu được, lời chia việc vẫn đọc được", () => {
    const broken: Step[] = [
      DONE[0],
      {
        mark: "failed",
        title: "Soạn câu hỏi",
        result: "— hỏng",
        planned: true,
      },
    ];

    render(<Steps steps={broken} told={TOLD} />);

    expect(screen.queryByText("liệt kê")).not.toBeNull();
  });

  it("lượt không soạn theo dàn ý thì khối không có phần chia việc", () => {
    render(<Steps steps={DONE} />);
    fireEvent.click(screen.getByRole("button", { name: "Đã làm 2 bước" }));

    expect(document.querySelector(".split-note")).toBeNull();
  });
});
