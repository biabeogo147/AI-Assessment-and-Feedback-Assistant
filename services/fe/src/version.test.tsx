import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VERSION, VersionTag, useVersionCheck } from "./Version";

/** BE trả tên bản `version`, hay hỏng khi `version` là `null`. */
function backend(version: string | null) {
  const fetch = vi.fn(async () =>
    version === null
      ? new Response("", { status: 502 })
      : new Response(JSON.stringify({ version }), { status: 200 }),
  );
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

beforeEach(() => window.sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("VersionTag", () => {
  it("hiện tên bản của FE", () => {
    render(<VersionTag />);
    expect(screen.getByRole("button").textContent).toBe(VERSION);
  });

  it("bấm thì chép tên bản để dán vào ticket, chữ trên màn không đổi", async () => {
    const writeText = vi.fn(async () => {});
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    render(<VersionTag corner />);

    fireEvent.click(screen.getByRole("button"));

    expect(writeText).toHaveBeenCalledWith(`Phiên bản ${VERSION}`);
    expect(screen.getByRole("button").textContent).toBe(VERSION);
  });
});

describe("useVersionCheck", () => {
  it("cùng tên với BE thì không tải lại", async () => {
    const fetch = backend(VERSION);
    const reload = vi.fn();
    renderHook(() => useVersionCheck(reload));

    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/version"));
    expect(reload).not.toHaveBeenCalled();
  });

  it("lệch BE thì tải lại đúng một lần cho mỗi tên bản BE", async () => {
    backend("lab-2099.0.1");
    const reload = vi.fn();
    const first = renderHook(() => useVersionCheck(reload));
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    first.unmount();

    // Trang vừa tải lại mà BE vẫn lệch đúng tên ấy (BE lên trước FE lúc deploy): không quay vòng.
    const again = renderHook(() => useVersionCheck(reload));
    await act(async () => {});
    expect(reload).toHaveBeenCalledTimes(1);
    again.unmount();

    // Một tên BE khác nữa thì là một lần deploy khác: tải lại một lần nữa.
    backend("lab-2099.0.2");
    renderHook(() => useVersionCheck(reload));
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(2));
  });

  it("trình duyệt chặn bộ nhớ thì không tải lại, để không quay vòng", async () => {
    const fetch = backend("lab-2099.0.1");
    const blocked = () => {
      throw new DOMException("blocked", "SecurityError");
    };
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(blocked);
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(blocked);
    const reload = vi.fn();
    try {
      renderHook(() => useVersionCheck(reload));
      await waitFor(() => expect(fetch).toHaveBeenCalled());
      await act(async () => {});
      expect(reload).not.toHaveBeenCalled();
    } finally {
      setItem.mockRestore();
      getItem.mockRestore();
    }
  });

  it("BE trả thứ không phải tên bản thì không làm gì", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200 })));
    const reload = vi.fn();
    renderHook(() => useVersionCheck(reload));
    await act(async () => {});
    expect(reload).not.toHaveBeenCalled();
  });

  it("BE hỏng thì không làm gì", async () => {
    const fetch = backend(null);
    const reload = vi.fn();
    renderHook(() => useVersionCheck(reload));

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    await act(async () => {});
    expect(reload).not.toHaveBeenCalled();
  });

  it("hỏi lại khi tab hiện lại", async () => {
    const fetch = backend(VERSION);
    renderHook(() => useVersionCheck(vi.fn()));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
