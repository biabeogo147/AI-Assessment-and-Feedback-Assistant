/**
 * Đăng nhập của học sinh (việc 22, plan `sign-in-and-accounts`, Figma 12): cổng phiên của `App`,
 * màn đăng nhập, nút *Đăng xuất* chạy thật, và 401 giữa chừng đưa về màn đăng nhập.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const ANH = {
  student_id: "s1",
  full_name: "Nguyễn Minh Anh",
  class_name: "12A",
  student_code: "HS2026-1204",
};

const BAO = { ...ANH, student_id: "s2", full_name: "Trần Gia Bảo", student_code: "HS2026-1205" };

interface Sent {
  url: string;
  method: string;
  body: string;
  headers: Record<string, string>;
}

function backend(start = false) {
  const sent: Sent[] = [];
  const state = { signedIn: start, who: ANH, signOutBroken: false };
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
      if (url === "/api/sign-in") {
        const asked = JSON.parse(body) as { username: string; password: string };
        if (asked.password !== "dung") {
          return answer(401, { detail: "Tên đăng nhập hoặc mật khẩu không đúng." });
        }
        state.signedIn = true;
        state.who = asked.username === "baotg" ? BAO : ANH;
        return answer(204, null);
      }
      if (url === "/api/sign-out") {
        if (state.signOutBroken) return answer(503, { detail: "BE chưa trả lời." });
        state.signedIn = false;
        return answer(204, null);
      }
      if (!state.signedIn) return answer(401, { detail: "Bạn cần đăng nhập." });
      if (url === "/api/me") return answer(200, state.who);
      return answer(200, []);
    }),
  );
  return { sent, state };
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

describe("đăng nhập học sinh (việc 22)", () => {
  it("chưa đăng nhập: màn 12, dải trên không có danh tính hay Đăng xuất", async () => {
    backend();
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Đăng nhập để làm bài" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Đăng xuất" })).toBeNull();
    // Hộp đăng nhập chỉ có hai ô và nút: không còn dòng nhắc ai phát mật khẩu.
    expect(screen.queryByText(/do thầy cô phát cho em/)).toBeNull();
  });

  it("sai thì câu của BE ngay trên nút; đúng thì vào Bài của tôi, không gửi X-Actor", async () => {
    const { sent } = backend();
    render(<App />);
    await screen.findByRole("heading", { name: "Đăng nhập để làm bài" });

    fireEvent.change(screen.getByLabelText("Tên đăng nhập"), { target: { value: "anhnm" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "sai" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Tên đăng nhập hoặc mật khẩu không đúng.",
    );

    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "dung" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByText("Nguyễn Minh Anh")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Đăng nhập để làm bài" })).toBeNull();
    const signIn = sent.filter((one) => one.url === "/api/sign-in").at(-1);
    expect(JSON.parse(signIn?.body ?? "{}")).toEqual({ username: "anhnm", password: "dung" });
    expect(sent.every((one) => !("X-Actor" in one.headers))).toBe(true);
  });

  it("Đăng xuất chạy thật: BE xoá phiên, màn về đăng nhập", async () => {
    const { sent } = backend(true);
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Đăng xuất" }));
    expect(await screen.findByRole("heading", { name: "Đăng nhập để làm bài" })).toBeTruthy();
    expect(sent.some((one) => one.url === "/api/sign-out" && one.method === "POST")).toBe(true);
  });

  it("phiên hết giữa chừng: một 401 bất kỳ đưa về màn đăng nhập", async () => {
    const { state } = backend(true);
    render(<App />);
    await screen.findByRole("button", { name: "Đăng xuất" });
    state.signedIn = false;
    window.location.hash = "#/attempt/a1";
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Đăng nhập để làm bài" })).toBeTruthy(),
    );
  });

  it("em khác vào sau khi phiên hết: về Bài của tôi, bỏ lượt chữa đã chép của em trước", async () => {
    const { state } = backend(true);
    window.sessionStorage.setItem("round:r1", JSON.stringify({ round_id: "r1" }));
    render(<App />);
    await screen.findByRole("button", { name: "Đăng xuất" });

    state.signedIn = false;
    window.location.hash = "#/attempt/a1";
    await screen.findByRole("heading", { name: "Đăng nhập để làm bài" });
    fireEvent.change(screen.getByLabelText("Tên đăng nhập"), { target: { value: "baotg" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "dung" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));

    expect(await screen.findByText("Trần Gia Bảo")).toBeTruthy();
    await waitFor(() => expect(window.location.hash).toBe("#/"));
    expect(window.sessionStorage.getItem("round:r1")).toBeNull();
  });

  it("đăng xuất hỏng thì nói ra, phiên còn nguyên", async () => {
    const { state } = backend(true);
    render(<App />);
    state.signOutBroken = true;
    fireEvent.click(await screen.findByRole("button", { name: "Đăng xuất" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Chưa đăng xuất được, hãy thử lại.");
    expect(screen.queryByRole("heading", { name: "Đăng nhập để làm bài" })).toBeNull();
  });
});
