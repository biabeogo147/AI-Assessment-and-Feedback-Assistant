/**
 * Toán dựng hình được, và chữ thì vẫn là chữ.
 *
 * Trước `MathText`, **không một chỗ nào** trong app dựng hình toán: 21 vị trí in chữ câu
 * hỏi đều là `{text}` thuần. Đo được trên panel thật, nguyên văn trước mặt giáo viên:
 * `Tính tích phân xác định \int_{0}^{1}(3x^2 - 2x + 1)\, dx.`
 */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MathText from "./MathText";

/** Phần HTML mà KaTeX dựng ra, nếu có. */
function drawn(container: HTMLElement) {
  return container.querySelectorAll(".katex").length;
}

describe("MathText", () => {
  it("chuỗi không có toán thì đi qua nguyên vẹn", () => {
    // Corpus cũ là Unicode và không có dấu nào — nó phải sống y như trước.
    const { container } = render(
      <MathText>{"Cho hàm số y = x³ − 3x, hỏi gì đó"}</MathText>,
    );
    expect(container.textContent).toBe("Cho hàm số y = x³ − 3x, hỏi gì đó");
    expect(drawn(container)).toBe(0);
  });

  it("dựng hình phần nằm giữa hai dấu $, và giữ nguyên phần chữ quanh nó", () => {
    const { container } = render(
      <MathText>{"Tính $\\int_0^1 x\\,dx$ rồi so sánh"}</MathText>,
    );
    expect(drawn(container)).toBe(1);
    expect(container.textContent).toContain("Tính ");
    expect(container.textContent).toContain(" rồi so sánh");
    // Và chuỗi LaTeX thô không còn **nằm ngoài** cụm đã dựng. Trong cụm thì nó vẫn có:
    // KaTeX nhúng nguyên văn nguồn vào MathML cho trình đọc màn hình và cho việc sao
    // chép — đó là tính năng của nó, không phải chữ lọt ra màn hình.
    for (const one of container.querySelectorAll(".katex")) one.remove();
    expect(container.textContent).toBe("Tính  rồi so sánh");
  });

  it("nhận cả bốn kiểu dấu, vì database đã có ba kiểu kia", () => {
    // Hợp đồng mới là `$...$`. Nhưng dữ liệu đã lưu thì mang `\\(...\\)` và `\\[...\\]` —
    // model viết thế suốt thời gian lệnh cấm LaTeX không có nơi thi hành. Nhận cả bốn
    // nghĩa là corpus cũ đọc được ngay, không cần một lần chuyển đổi nào.
    for (const one of ["$x^2$", "$$x^2$$", "\\(x^2\\)", "\\[x^2\\]"]) {
      const { container } = render(<MathText>{one}</MathText>);
      expect(drawn(container), one).toBe(1);
    }
  });

  it("nhiều cụm trong một chuỗi", () => {
    const { container } = render(
      <MathText>{"$a^2$ cộng $b^2$ bằng $c^2$"}</MathText>,
    );
    expect(drawn(container)).toBe(3);
    expect(container.textContent).toContain(" cộng ");
  });

  it("một dấu $ lẻ thì không có gì được dựng, và chữ vẫn còn đủ", () => {
    const { container } = render(<MathText>{"giá 5$ một quyển"}</MathText>);
    expect(drawn(container)).toBe(0);
    expect(container.textContent).toBe("giá 5$ một quyển");
  });

  it("HAI dấu $ tiền tệ cũng không biến đoạn văn ở giữa thành công thức", () => {
    // Ca một dấu là ca dễ. Ca thật là **hai** dấu — số chẵn, nên phép đếm chẵn lẻ không
    // thấy gì, và cả đoạn `, hai quyển 40` bị dựng thành ký hiệu toán. Đề toán về giá tiền
    // là ca thường gặp. Luật cứu nó: dấu mở không được dính một chữ số.
    const { container } = render(
      <MathText>{"Một quyển 20$, hai quyển 40$. Tính giá."}</MathText>,
    );
    expect(drawn(container)).toBe(0);
    expect(container.textContent).toBe(
      "Một quyển 20$, hai quyển 40$. Tính giá.",
    );
  });

  it("công thức ngắt dòng ở giữa vẫn dựng được", () => {
    // Bản đầu cấm xuống dòng trong `$…$`, nên một công thức dài mà model ngắt dòng sẽ hiện
    // ra nguyên văn — đúng cái kết cục việc này đi sửa.
    const { container } = render(
      <MathText>{"Tính $\\int_0^1\nx\\,dx$ nhé"}</MathText>,
    );
    expect(drawn(container)).toBe(1);
  });

  it("công thức hỏng KHÔNG làm trắng màn hình", () => {
    // `throwOnError: false`: một câu hỏi xấu vẫn phải đọc được, và một exception ở đây sẽ
    // giết cả panel vì một dấu ngoặc thiếu.
    const { container } = render(<MathText>{"$\\frac{1}{$"}</MathText>);
    expect(container.textContent).not.toBe("");
  });
});
