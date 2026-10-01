/**
 * Mốc thời gian gửi lên khi phát hành.
 *
 * Đây là chỗ thứ tư mà giao diện có thể giành một quyết định khỏi tay BE, và là chỗ duy nhất
 * trong số đó mà sai thì **không có lỗi nào xuất hiện**: một mốc thiếu offset vẫn là HTTP 200,
 * chỉ có câu luật đọc lên sai giờ. Nên nó được kiểm bằng test chứ không bằng cách nhìn.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { isoWithOffset } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

/** Giả lập một máy đặt ở múi giờ nào, qua số phút mà JS dùng để chỉ múi giờ đó. */
function machineAt(minutes: number) {
  vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(minutes);
}

describe("isoWithOffset", () => {
  it("in ra offset địa phương, không bao giờ in Z", () => {
    machineAt(-420); // Việt Nam
    const sent = isoWithOffset("2026-10-02T08:45");
    expect(sent).toBe("2026-10-02T08:45:00+07:00");
    expect(sent.endsWith("Z")).toBe(false);
  });

  it("đảo dấu của getTimezoneOffset, vì nó trả số phút cần cộng để ra UTC", () => {
    machineAt(300); // New York mùa đông: -05:00
    expect(isoWithOffset("2026-01-15T09:00")).toBe("2026-01-15T09:00:00-05:00");
  });

  it("in cả phần phút của offset", () => {
    machineAt(-345); // Nepal: +05:45
    expect(isoWithOffset("2026-10-02T08:45")).toBe("2026-10-02T08:45:00+05:45");
  });

  it("giữ nguyên giây khi ô nhập đã có giây", () => {
    machineAt(0);
    expect(isoWithOffset("2026-10-02T08:45:30")).toBe("2026-10-02T08:45:30+00:00");
  });

  it("gửi đúng mốc mà giáo viên gõ, đọc theo đồng hồ của máy đang gõ", () => {
    // Phép kiểm thật: chuỗi gửi lên và chuỗi gõ vào phải chỉ về CÙNG một thời điểm. Một
    // offset sai dấu vẫn đúng khuôn, nhưng lệch mười bốn giờ ở đây.
    const typed = "2026-10-02T08:45";
    expect(new Date(isoWithOffset(typed)).getTime()).toBe(new Date(typed).getTime());
  });
});
