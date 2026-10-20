/**
 * Đăng nhập của giáo viên (việc 22, plan `sign-in-and-accounts`): cổng phiên của `App`, hộp đăng
 * nhập / tạo tài khoản, ô tài khoản và menu, và 401 giữa chừng đưa về màn đăng nhập.
 *
 * `fetch` giả đứng thay BE: nó nhớ phiên như cookie thật, nên `GET /api/teacher/me` trả 401 cho tới
 * lúc một lần đăng nhập đúng.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import App from "./App";
import { initials } from "./screens/teacher/Account";

const LAN = { teacher_id: "t1", full_name: "Phạm Thu Lan", teacher_code: "GV-001" };

interface Sent {
  url: string;
  method: string;
  body: string;
  headers: Record<string, string>;
}

/** BE giả có phiên: `signedIn` bật bởi một lần đăng nhập đúng, tắt khi đăng xuất. */
function backend(start = false) {
  const sent: Sent[] = [];
  const state = { signedIn: start, signOutBroken: false };
  const answer = (status: number, body: unknown) =>
    Promise.resolve(
      new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init: RequestInit = {}) => {
      const method = (init.method ?? "GET").toUpperCase();
      const body = String(init.body ?? "");
      sent.push({ url, method, body, headers: (init.headers ?? {}) as Record<string, string> });
      if (url === "/api/teacher/sign-in") {
        const { password } = JSON.parse(body) as { password: string };
        if (password !== "dung-mat-khau") {
          return answer(401, { detail: "Số điện thoại, email hoặc mật khẩu không đúng." });
        }
        state.signedIn = true;
        return answer(204, null);
      }
      if (url === "/api/teacher/sign-up") {
        state.signedIn = true;
        return answer(204, null);
      }
      if (url === "/api/teacher/sign-out") {
        if (state.signOutBroken) return answer(503, { detail: "BE chưa trả lời, hãy thử lại." });
        state.signedIn = false;
        return answer(204, null);
      }
      if (!state.signedIn) return answer(401, { detail: "Bạn cần đăng nhập." });
      if (url === "/api/teacher/me") return answer(200, LAN);
      if (url.startsWith("/api/teacher/chat")) {
        return answer(200, { kind: "", text: "", conversation_id: "", choices: [], more_choices: 0, turns: [] });
      }
      return answer(200, []);
    }),
  );
  return { sent, state };
}

beforeAll(() => {
  // jsdom không dựng bố cục, nên không có `scrollIntoView`; dòng chat gọi nó sau mỗi lượt.
  Element.prototype.scrollIntoView = () => undefined;
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

describe("đăng nhập giáo viên (việc 22)", () => {
  it("chưa đăng nhập: hộp đăng nhập mở, rail chỉ còn dòng nhắc, không đọc dữ liệu nào", async () => {
    const { sent } = backend();
    window.location.hash = "#/teacher";
    const { container } = render(<App />);

    expect(await screen.findByRole("heading", { name: "Đăng nhập vào Kriky" })).toBeTruthy();
    expect(container.querySelector(".rail .lists-hint")?.textContent).toBe(
      "Đăng nhập để thấy các đoạn chat và tài liệu của bạn.",
    );
    expect(container.querySelector(".rail .account.signed-out")?.textContent).toBe("Đăng nhập");
    // Chỉ một lời hỏi phiên: không đoạn chat, thư viện hay kênh nào đi ra để nhận 401.
    expect(sent.map((one) => one.url)).toEqual(["/api/teacher/me"]);
  });

  it("đăng nhập sai thì hiện câu của BE; đúng thì vào màn và không còn gửi X-Actor", async () => {
    const { sent } = backend();
    window.location.hash = "#/teacher";
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: "Đăng nhập vào Kriky" });

    fireEvent.change(screen.getByLabelText("Số điện thoại / email"), { target: { value: "0912345001" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "sai" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Số điện thoại, email hoặc mật khẩu không đúng.",
    );

    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "dung-mat-khau" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    await waitFor(() => expect(container.querySelector(".sign-in")).toBeNull());
    expect(container.querySelector(".rail .account-name")?.textContent).toBe("Phạm Thu Lan");
    expect(container.querySelector(".rail .avatar")?.textContent).toBe("PL");

    const signIn = sent.filter((one) => one.url === "/api/teacher/sign-in").at(-1);
    expect(JSON.parse(signIn?.body ?? "{}")).toEqual({
      login: "0912345001",
      password: "dung-mat-khau",
    });
    // Sau khi vào, màn đọc đoạn chat và thư viện -- bằng cookie, không bằng header.
    await waitFor(() => expect(sent.some((one) => one.url === "/api/teacher/conversations")).toBe(true));
    expect(sent.every((one) => !("X-Actor" in one.headers))).toBe(true);
  });

  it("một ô SĐT hoặc email; tạo tài khoản gửi đủ bốn ô rồi vào thẳng", async () => {
    const { sent } = backend();
    window.location.hash = "#/teacher";
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: "Đăng nhập vào Kriky" });

    // Một ô cho cả hai, không còn tab chọn (người dùng chốt 19/10/2026).
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.getByLabelText("Số điện thoại / email")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Chưa có tài khoản? Tạo tài khoản" }));
    expect(screen.getByRole("heading", { name: "Tạo tài khoản giáo viên" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Google/ })).toBeNull();
    fireEvent.change(screen.getByLabelText("Họ và tên"), { target: { value: "Phạm Thu Lan" } });
    fireEvent.change(screen.getByLabelText("Số điện thoại"), { target: { value: "0912 345 678" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "lan@example.com" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "mat-khau-dai" } });
    fireEvent.click(screen.getByRole("button", { name: "Tạo tài khoản" }));

    await waitFor(() => expect(container.querySelector(".sign-in")).toBeNull());
    const signUp = sent.find((one) => one.url === "/api/teacher/sign-up");
    expect(JSON.parse(signUp?.body ?? "{}")).toEqual({
      full_name: "Phạm Thu Lan",
      phone: "0912 345 678",
      email: "lan@example.com",
      password: "mat-khau-dai",
    });
  });

  it("Google chỉ là giao diện: bấm thì nói thẳng là chưa có", async () => {
    backend();
    window.location.hash = "#/teacher";
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /Tiếp tục với Google/ }));
    expect((await screen.findByRole("alert")).textContent).toContain("Google chưa có");
  });

  it("menu tài khoản: bốn mục chưa có không bấm được, Đăng xuất đưa về hộp đăng nhập", async () => {
    const { sent } = backend(true);
    window.location.hash = "#/teacher";
    const { container } = render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Phạm Thu Lan" }));

    const items = screen.getAllByRole("menuitem");
    expect(items.map((one) => one.textContent)).toEqual([
      "Cài đặt",
      "Mức sử dụng",
      "Ngôn ngữ",
      "Trợ giúp",
      "Đăng xuất",
    ]);
    expect(items.slice(0, 4).every((one) => one.getAttribute("aria-disabled") === "true")).toBe(true);

    fireEvent.click(screen.getByRole("menuitem", { name: "Đăng xuất" }));
    expect(await screen.findByRole("heading", { name: "Đăng nhập vào Kriky" })).toBeTruthy();
    expect(sent.some((one) => one.url === "/api/teacher/sign-out" && one.method === "POST")).toBe(true);
    expect(container.querySelector(".rail .account-box")).toBeNull();
  });

  it("phiên hết giữa chừng: một 401 bất kỳ đưa về hộp đăng nhập", async () => {
    const { state } = backend(true);
    window.location.hash = "#/teacher";
    render(<App />);
    await screen.findByRole("button", { name: "Phạm Thu Lan" });

    state.signedIn = false;
    window.location.hash = "#/teacher/lop";
    expect(await screen.findByRole("heading", { name: "Đăng nhập vào Kriky" })).toBeTruthy();
  });
});

describe("phiên hết giữa chừng (review pha 3)", () => {
  it("lượt chat nhận 401 thì về hộp đăng nhập, kèm câu của BE", async () => {
    const { state } = backend(true);
    window.location.hash = "#/teacher";
    render(<App />);
    await screen.findByRole("button", { name: "Phạm Thu Lan" });

    state.signedIn = false;
    fireEvent.change(screen.getByLabelText("Nhắn cho Kriky"), { target: { value: "Soạn đề" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
    expect(await screen.findByRole("heading", { name: "Đăng nhập vào Kriky" })).toBeTruthy();
  });

  it("đăng nhập lại đúng người thì ở nguyên route; phía sau hộp không nhận focus", async () => {
    const { state } = backend(true);
    window.location.hash = "#/teacher";
    const { container } = render(<App />);
    await screen.findByRole("button", { name: "Phạm Thu Lan" });

    state.signedIn = false;
    window.location.hash = "#/teacher/de-kiem-tra";
    await screen.findByRole("heading", { name: "Đăng nhập vào Kriky" });
    expect(container.querySelector(".rail")?.hasAttribute("inert")).toBe(true);

    fireEvent.change(screen.getByLabelText("Số điện thoại / email"), { target: { value: "0912345001" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "dung-mat-khau" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    await waitFor(() => expect(container.querySelector(".sign-in")).toBeNull());
    expect(window.location.hash).toBe("#/teacher/de-kiem-tra");
    expect(container.querySelector(".rail")?.hasAttribute("inert")).toBe(false);
  });

  it("Esc đóng menu; đăng xuất hỏng thì nói ra và phiên còn nguyên", async () => {
    const { state } = backend(true);
    window.location.hash = "#/teacher";
    render(<App />);
    const cell = await screen.findByRole("button", { name: "Phạm Thu Lan" });

    fireEvent.click(cell);
    expect(screen.getByRole("menu")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();

    state.signOutBroken = true;
    fireEvent.click(cell);
    fireEvent.click(screen.getByRole("menuitem", { name: "Đăng xuất" }));
    expect((await screen.findByRole("alert")).textContent).toBe("BE chưa trả lời, hãy thử lại.");
    expect(screen.queryByRole("heading", { name: "Đăng nhập vào Kriky" })).toBeNull();
  });
});

describe("chữ của avatar", () => {
  it.each([
    ["Phạm Thu Lan", "PL"],
    ["Cô Phạm Thu Lan", "PL"],
    ["Thầy Nguyễn Văn Bình", "NB"],
    ["Hà", "H"],
    ["", ""],
  ])("%s → %s", (name, expected) => {
    expect(initials(name)).toBe(expected);
  });
});
