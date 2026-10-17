/**
 * Lời Kriky dựng Markdown, và toán trong lời dựng y như ở `MathText` (ADR-30,
 * `kriky-writes-every-word`).
 */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import KrikyText from "./KrikyText";

/** Số cụm KaTeX đã dựng. */
function drawn(container: HTMLElement) {
  return container.querySelectorAll(".katex").length;
}

describe("KrikyText", () => {
  it("dựng Markdown: đậm, danh sách, tiêu đề, bảng — không còn ký tự Markdown nguyên văn", () => {
    const { container } = render(
      <KrikyText>
        {[
          "### Dàn ý 5 câu",
          "",
          "- **Câu 1–2:** tỉ lệ thức",
          "- **Câu 3:** dãy tỉ số bằng nhau",
          "",
          "| Câu | Kiến thức |",
          "| --- | --- |",
          "| 1 | tỉ lệ thức |",
        ].join("\n")}
      </KrikyText>,
    );
    expect(container.querySelector("h3")?.textContent).toBe("Dàn ý 5 câu");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.querySelector("strong")?.textContent).toBe("Câu 1–2:");
    expect(container.querySelector("table")).not.toBeNull();
    expect(container.textContent).not.toMatch(/\*\*|###|\| ---/);
  });

  it("toán trong lời dựng hình, kể cả gạch dưới và dấu gạch chéo mà Markdown hiểu khác", () => {
    // `_` giữa hai `$` là chỉ số dưới, không phải chữ nghiêng; `\\` của LaTeX không mất nửa.
    const { container } = render(
      <KrikyText>{"Công thức $u_n = u_1 + (n-1)d$ và $a_1 \\cdot a_2$ nhé"}</KrikyText>,
    );
    expect(drawn(container)).toBe(2);
    expect(container.querySelector("em")).toBeNull();
    for (const one of container.querySelectorAll(".katex")) one.remove();
    expect(container.textContent).toBe("Công thức  và  nhé");
  });

  it("toán nằm trong mục danh sách và trong chữ đậm vẫn dựng hình", () => {
    const { container } = render(
      <KrikyText>{"- **Câu 1:** $\\frac{a}{b}=\\frac{c}{d}$\n- Câu 2: $ad=bc$"}</KrikyText>,
    );
    expect(drawn(container)).toBe(2);
    expect(container.querySelectorAll("li")).toHaveLength(2);
  });

  it("giữ đúng luật tiền tệ của MathText: `20$` không mở công thức", () => {
    const { container } = render(
      <KrikyText>{"Một quyển 20$, hai quyển 40$. Tính giá."}</KrikyText>,
    );
    expect(drawn(container)).toBe(0);
    expect(container.textContent).toBe("Một quyển 20$, hai quyển 40$. Tính giá.");
  });

  it("nhận cả bốn kiểu dấu toán như MathText", () => {
    for (const one of ["$x^2$", "$$x^2$$", "\\(x^2\\)", "\\[x^2\\]"]) {
      const { container } = render(<KrikyText>{one}</KrikyText>);
      expect(drawn(container), one).toBe(1);
    }
  });

  it("không chạy HTML thô model viết ra", () => {
    const { container } = render(
      <KrikyText>{'Xin chào <img src=x onerror="alert(1)"> <script>alert(1)</script> nhé'}</KrikyText>,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });

  it("chữ trơn không có Markdown nào thì đi qua nguyên vẹn", () => {
    const { container } = render(<KrikyText>{"Lớp 12A chưa có học sinh nào nộp bài."}</KrikyText>);
    expect(container.textContent).toBe("Lớp 12A chưa có học sinh nào nộp bài.");
  });

  // ------------------------------------------------------------- review pha 3

  it("ảnh không tự tải: chỉ chữ alt ở lại", () => {
    // Một ảnh từ URL model viết là đường rò dữ liệu không cần ai bấm.
    const { container } = render(<KrikyText>{"Xem ![hình minh hoạ](http://evil.example/x.png) nhé"}</KrikyText>);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("hình minh hoạ");
  });

  it("link mở tab mới; link trong trang thành chữ", () => {
    const { container } = render(<KrikyText>{"Xem [SGK](https://example.org) và [ghi chú](#x)"}</KrikyText>);
    const links = container.querySelectorAll("a");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("target")).toBe("_blank");
    expect(links[0].getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("khối `$$` đặt trên dòng riêng vẫn dựng hình", () => {
    const { container } = render(<KrikyText>{"Công thức:\n\n$$\n\\int_0^1 x\\,dx\n$$\n\nnhé"}</KrikyText>);
    expect(drawn(container)).toBe(1);
  });

  it("danh sách lỏng không in thêm dòng trống trong mục", () => {
    // mdast→hast chèn `\n` giữa các khối; `pre-line` của `li` sẽ in chúng thành dòng trống.
    const { container } = render(<KrikyText>{"- Một\n\n- Hai\n  - con"}</KrikyText>);
    for (const li of container.querySelectorAll("li")) {
      for (const node of li.childNodes) {
        if (node.nodeType === Node.TEXT_NODE) expect(node.textContent).not.toMatch(/^\s*\n\s*$/);
      }
    }
  });

  it("ký tự giữ chỗ model viết sẵn bị bỏ, không thành một công thức khác", () => {
    const { container } = render(<KrikyText>{"Trước \uE0000\uE001 sau $x^2$"}</KrikyText>);
    expect(drawn(container)).toBe(1);
    for (const one of container.querySelectorAll(".katex")) one.remove();
    expect(container.textContent).toBe("Trước 0 sau ");
  });

  it("lời trong một dòng (tiêu đề thẻ hỏi lại) không sinh đoạn, danh sách hay tiêu đề", () => {
    const { container } = render(
      <h3>
        <KrikyText inline>{"Bạn chọn **khối** nào?\n\n- Lớp 6\n- Lớp 7\n\n# To"}</KrikyText>
      </h3>,
    );
    expect(container.querySelector("p, ul, li, h1")).toBeNull();
    expect(container.querySelector("strong")?.textContent).toBe("khối");
  });

  it("lời trong một dòng giữ mỗi đoạn, mỗi mục trên một dòng riêng, mục có dấu của nó", () => {
    // Thử tay 17/10/2026: gỡ thẳng danh sách làm các mục dính liền nhau trong tiêu đề thẻ.
    const { container } = render(
      <h3>
        <KrikyText inline>{"Bạn cho mình biết:\n\n- **Khối** nào?\n- Số câu?\n\n1. Một\n2. Hai"}</KrikyText>
      </h3>,
    );
    const shown = [...container.querySelectorAll(".line")];
    expect(shown.map((one) => one.textContent)).toEqual([
      "Bạn cho mình biết:",
      "Khối nào?",
      "Số câu?",
      "Một",
      "Hai",
    ]);
    expect(shown.map((one) => one.getAttribute("data-marker"))).toEqual([
      null,
      "•",
      "•",
      "1.",
      "2.",
    ]);
  });
});
