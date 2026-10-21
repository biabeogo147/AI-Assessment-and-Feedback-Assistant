/**
 * Thêm học sinh và đặt lại mật khẩu ở màn 10 (việc 22, plan `sign-in-and-accounts`).
 *
 * `fetch` giả đứng thay BE: bảng xem trước có một dòng trùng, bước tạo trả mật khẩu, và mọi lời
 * gọi được ghi lại để kiểm thân gửi đi.
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ClassDetail from "./screens/teacher/ClassDetail";

const DETAIL = {
  class_id: "c12a",
  name: "12A",
  student_count: 2,
  courses: "Toán 12",
  papers: [],
  students: [
    { student_id: "s1", full_name: "Nguyễn Minh Anh", student_code: "HS2026-1204", username: "anhnm" },
    { student_id: "s2", full_name: "Đỗ Văn Hùng", student_code: "HS2026-1300", username: null },
  ],
};

const PREVIEW = {
  rows: [
    { full_name: "Lê Kim Tính", username: "tinhlk", note: "new" },
    { full_name: "Nguyễn Minh Anh", username: "anhnm2", note: "duplicate" },
  ],
};

interface Sent {
  url: string;
  method: string;
  body: BodyInit | null | undefined;
  headers: Record<string, string>;
}

function backend(overrides: Record<string, () => Response> = {}) {
  const sent: Sent[] = [];
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init: RequestInit = {}) => {
      sent.push({
        url,
        method: (init.method ?? "GET").toUpperCase(),
        body: init.body,
        headers: (init.headers ?? {}) as Record<string, string>,
      });
      const path = url.replace("/api", "");
      if (overrides[path]) return Promise.resolve(overrides[path]());
      if (path === "/teacher/classes/c12a") return Promise.resolve(json(DETAIL));
      if (path.endsWith("/roster/preview") || path.endsWith("/roster/preview-file")) {
        return Promise.resolve(json(PREVIEW));
      }
      if (path.endsWith("/roster")) {
        const rows = JSON.parse(String(init.body)).rows as { full_name: string; confirmed: boolean }[];
        const accounts = rows
          .filter((one) => one.full_name !== "Nguyễn Minh Anh" || one.confirmed)
          .map((one, index) => ({
            student_id: `n${index}`,
            full_name: one.full_name,
            student_code: String(index + 1),
            username: one.full_name === "Lê Kim Tính" ? "tinhlk" : "anhnm2",
            password: `abc-def-g${index}`,
          }));
        return Promise.resolve(json({ accounts, skipped: rows.length - accounts.length }));
      }
      if (path.endsWith("/password")) {
        const id = path.split("/").at(-2);
        const one = DETAIL.students.find((row) => row.student_id === id);
        return Promise.resolve(
          json({ ...one, username: one?.username ?? "hungdv", password: "xyz-mnp-qr" }),
        );
      }
      if (path.endsWith("passwords.xlsx")) {
        return Promise.resolve(new Response(new Blob(["x"]), { status: 200 }));
      }
      return Promise.resolve(json([]));
    }),
  );
  return sent;
}

const realCreate = URL.createObjectURL;
const realRevoke = URL.revokeObjectURL;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  URL.createObjectURL = realCreate;
  URL.revokeObjectURL = realRevoke;
});

describe("màn 10: tên đăng nhập và đặt lại mật khẩu", () => {
  it("cột tên đăng nhập; em chưa có thì hiện —", async () => {
    backend();
    const { container } = render(<ClassDetail classId="c12a" />);
    await screen.findByText("Đỗ Văn Hùng");
    const rows = [...container.querySelectorAll(".class-students .board-row:not(.head)")];
    expect(rows.map((one) => one.children[2].textContent)).toEqual(["anhnm", "—"]);
    expect(within(rows[0] as HTMLElement).getByRole("button").textContent).toBe("Đặt lại mật khẩu");
  });

  it("đặt lại mật khẩu: hiện mật khẩu mới một lần; em chưa có tên thì màn đọc lại lớp", async () => {
    const sent = backend();
    render(<ClassDetail classId="c12a" />);
    await screen.findByText("Đỗ Văn Hùng");
    const before = sent.filter((one) => one.url === "/api/teacher/classes/c12a").length;

    const row = screen.getByText("Đỗ Văn Hùng").closest(".board-row") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Đặt lại mật khẩu" }));
    // Tier 2 câu 30 (21/10/2026): hỏi lại trước, chưa gửi gì.
    const asked = screen.getByRole("heading", { name: "Đặt lại mật khẩu cho Đỗ Văn Hùng?" });
    expect(sent.some((one) => one.url.endsWith("/password"))).toBe(false);
    fireEvent.click(
      within(asked.closest(".confirm") as HTMLElement).getByRole("button", { name: "Đặt lại mật khẩu" }),
    );

    expect(await screen.findByRole("heading", { name: "Đã đặt lại mật khẩu cho Đỗ Văn Hùng" })).toBeTruthy();
    expect(screen.getByText("xyz-mnp-qr")).toBeTruthy();
    expect(screen.getByText("hungdv")).toBeTruthy();
    // 10b không có nút xuất tệp.
    expect(screen.queryByRole("button", { name: "Xuất file Excel (.xlsx)" })).toBeNull();
    await waitFor(() =>
      expect(sent.filter((one) => one.url === "/api/teacher/classes/c12a").length).toBe(before + 1),
    );

    fireEvent.click(screen.getByRole("button", { name: "Đã lưu, đóng" }));
    expect(screen.queryByText("xyz-mnp-qr")).toBeNull();
  });

  it("BE từ chối đặt lại thì câu của BE đứng dưới đầu màn", async () => {
    backend({
      "/teacher/classes/c12a/students/s1/password": () =>
        new Response(JSON.stringify({ detail: "Không tìm thấy học sinh này trong lớp." }), {
          status: 404,
        }),
    });
    render(<ClassDetail classId="c12a" />);
    const row = (await screen.findByText("Nguyễn Minh Anh")).closest(".board-row") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Đặt lại mật khẩu" }));
    const asked = screen.getByRole("heading", { name: "Đặt lại mật khẩu cho Nguyễn Minh Anh?" });
    fireEvent.click(
      within(asked.closest(".confirm") as HTMLElement).getByRole("button", { name: "Đặt lại mật khẩu" }),
    );
    expect((await screen.findByRole("alert")).textContent).toBe("Không tìm thấy học sinh này trong lớp.");
  });

  it("hộp hỏi lại: Giữ mật khẩu cũ thì không gửi gì", async () => {
    const sent = backend();
    render(<ClassDetail classId="c12a" />);
    const row = (await screen.findByText("Nguyễn Minh Anh")).closest(".board-row") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Đặt lại mật khẩu" }));
    fireEvent.click(screen.getByRole("button", { name: "Giữ mật khẩu cũ" }));
    expect(screen.queryByRole("heading", { name: "Đặt lại mật khẩu cho Nguyễn Minh Anh?" })).toBeNull();
    expect(sent.some((one) => one.url.endsWith("/password"))).toBe(false);
  });
});

describe("thêm học sinh: ba bước (28, 28b, 28c)", () => {
  async function open() {
    render(<ClassDetail classId="c12a" />);
    fireEvent.click(await screen.findByRole("button", { name: "Thêm học sinh" }));
    return screen.getByRole("heading", { name: "Thêm học sinh vào lớp 12A" });
  }

  it("gõ tên → xem trước: chỉ dòng trùng bật ô xác nhận; chưa xác nhận thì không tạo", async () => {
    const sent = backend();
    await open();
    const preview = screen.getByRole("button", { name: "Xem trước" }) as HTMLButtonElement;
    expect(preview.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Họ và tên, mỗi dòng một học sinh"), {
      target: { value: "Lê Kim Tính\nNguyễn Minh Anh\n" },
    });
    fireEvent.click(preview);

    await screen.findByRole("heading", { name: "Kiểm tra lại trước khi tạo tài khoản" });
    const ask = sent.find((one) => one.url.endsWith("/roster/preview"));
    expect(JSON.parse(String(ask?.body))).toEqual({ names: ["Lê Kim Tính", "Nguyễn Minh Anh", ""] });

    const fresh = screen.getByLabelText("Xác nhận thêm Lê Kim Tính") as HTMLInputElement;
    const twin = screen.getByLabelText("Xác nhận thêm Nguyễn Minh Anh") as HTMLInputElement;
    expect(fresh.disabled).toBe(true);
    expect(twin.disabled).toBe(false);
    expect(screen.getByText("Trùng tên trong lớp")).toBeTruthy();
    expect(screen.getByText("Sẽ tạo 1 tài khoản · 1 học sinh cần xác nhận")).toBeTruthy();

    fireEvent.click(twin);
    expect(screen.getByText("Sẽ tạo 2 tài khoản")).toBeTruthy();
    fireEvent.click(twin);
    fireEvent.click(screen.getByRole("button", { name: "Tạo 1 tài khoản" }));

    await screen.findByRole("heading", { name: "Đã tạo 1 tài khoản" });
    const made = sent.find((one) => one.url.endsWith("/roster"));
    expect(JSON.parse(String(made?.body))).toEqual({
      rows: [
        { full_name: "Lê Kim Tính", confirmed: false },
        { full_name: "Nguyễn Minh Anh", confirmed: false },
      ],
    });
    expect(document.querySelector(".roster-lead")?.textContent).toBe(
      "Hãy lưu lại mật khẩu — chỉ hiển thị một lần duy nhất.",
    );
    expect(screen.getByText("abc-def-g0")).toBeTruthy();
  });

  it("xuất tệp mật khẩu gửi đúng các dòng đang hiện; Đã lưu, đóng thì mật khẩu mất", async () => {
    const sent = backend();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    await open();
    fireEvent.change(screen.getByLabelText("Họ và tên, mỗi dòng một học sinh"), {
      target: { value: "Lê Kim Tính" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Xem trước" }));
    fireEvent.click(await screen.findByRole("button", { name: "Tạo 1 tài khoản" }));
    fireEvent.click(await screen.findByRole("button", { name: "Xuất file Excel (.xlsx)" }));

    await waitFor(() => expect(sent.some((one) => one.url.endsWith("passwords.xlsx"))).toBe(true));
    const sheet = sent.find((one) => one.url.endsWith("passwords.xlsx"));
    expect(sheet?.method).toBe("POST");
    // Thiếu header này thì `fetch` gửi `text/plain` và FastAPI trả 422 (review pha 4).
    expect(sheet?.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(String(sheet?.body))).toEqual({
      rows: [{ full_name: "Lê Kim Tính", username: "tinhlk", password: "abc-def-g0" }],
    });

    fireEvent.click(screen.getByRole("button", { name: "Đã lưu, đóng" }));
    expect(screen.queryByText("abc-def-g0")).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("tab tải tệp gửi tệp bằng FormData; BE từ chối thì câu của BE hiện trong hộp", async () => {
    const sent = backend({
      "/teacher/classes/c12a/roster/preview-file": () =>
        new Response(JSON.stringify({ detail: "Chỉ nhận tệp .csv hoặc .xlsx." }), { status: 422 }),
    });
    await open();
    fireEvent.click(screen.getByRole("radio", { name: "Tải tệp .csv / .xlsx" }));
    expect(screen.getByText("Chưa chọn tệp nào · tối đa 1 MB")).toBeTruthy();
    const input = document.querySelector(".roster-file input[type=file]") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a"], "lop.txt")] } });
    expect(screen.getByText("lop.txt")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Xem trước" }));

    expect((await screen.findByRole("alert")).textContent).toBe("Chỉ nhận tệp .csv hoặc .xlsx.");
    const ask = sent.find((one) => one.url.endsWith("/preview-file"));
    expect(ask?.body).toBeInstanceOf(FormData);
    // Boundary của multipart do trình duyệt đặt: khai `Content-Type` tay là gửi một thân rỗng.
    expect(ask?.headers["Content-Type"]).toBeUndefined();
    expect(screen.getByRole("heading", { name: "Thêm học sinh vào lớp 12A" })).toBeTruthy();
  });

  it("xác nhận dòng trùng thì gửi confirmed: true và tạo cả hai em", async () => {
    const sent = backend();
    await open();
    fireEvent.change(screen.getByLabelText("Họ và tên, mỗi dòng một học sinh"), {
      target: { value: "Lê Kim Tính\nNguyễn Minh Anh" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Xem trước" }));
    fireEvent.click(await screen.findByLabelText("Xác nhận thêm Nguyễn Minh Anh"));
    fireEvent.click(screen.getByRole("button", { name: "Tạo 2 tài khoản" }));

    await screen.findByRole("heading", { name: "Đã tạo 2 tài khoản" });
    const made = sent.find((one) => one.url.endsWith("/roster"));
    expect(JSON.parse(String(made?.body)).rows[1]).toEqual({ full_name: "Nguyễn Minh Anh", confirmed: true });
    expect(screen.getByText("anhnm2")).toBeTruthy();
  });

  it("bước tạo bị từ chối thì ở lại bước 2; Quay lại giữ chữ đã gõ", async () => {
    backend({
      "/teacher/classes/c12a/roster": () =>
        new Response(JSON.stringify({ detail: "Có giáo viên khác vừa thêm học sinh cùng lúc. Hãy bấm lại." }), {
          status: 409,
        }),
    });
    await open();
    fireEvent.change(screen.getByLabelText("Họ và tên, mỗi dòng một học sinh"), {
      target: { value: "Lê Kim Tính" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Xem trước" }));
    fireEvent.click(await screen.findByRole("button", { name: "Tạo 1 tài khoản" }));

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Có giáo viên khác vừa thêm học sinh cùng lúc. Hãy bấm lại.",
    );
    expect(screen.getByRole("heading", { name: "Kiểm tra lại trước khi tạo tài khoản" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Quay lại" }));
    expect((screen.getByLabelText("Họ và tên, mỗi dòng một học sinh") as HTMLTextAreaElement).value).toBe(
      "Lê Kim Tính",
    );
  });

  it("BE không tạo được em nào thì không sang bảng mật khẩu rỗng", async () => {
    backend({
      "/teacher/classes/c12a/roster": () =>
        new Response(JSON.stringify({ accounts: [], skipped: 1 }), { status: 200 }),
    });
    await open();
    fireEvent.change(screen.getByLabelText("Họ và tên, mỗi dòng một học sinh"), {
      target: { value: "Lê Kim Tính" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Xem trước" }));
    fireEvent.click(await screen.findByRole("button", { name: "Tạo 1 tài khoản" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Chưa tạo tài khoản nào");
    expect(screen.queryByRole("heading", { name: /Đã tạo/ })).toBeNull();
  });

  it("Đóng ở bước đầu thì thôi, không gọi BE", async () => {
    const sent = backend();
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Đóng" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(sent.some((one) => one.url.includes("/roster"))).toBe(false);
  });
});
