import { useEffect } from "react";

import { api } from "./api";

/**
 * Tên bản lab của FE (plan `lab-version`), dựng vào bundle lúc build từ `AIAFA_VERSION`
 * (`vite.config.ts`). Cùng chữ với BE khi chưa có tag nào.
 */
export const VERSION = __AIAFA_VERSION__;

// Tên bản BE mà tab này đã tải lại vì nó một lần. Ghi trước khi tải: còn lệch đúng tên ấy sau lần
// tải (lúc deploy, BE có thể lên trước khi Caddy phục vụ FE mới) thì thôi, không quay vòng.
const RELOADED_FOR = "version:reloaded-for";

// Một hàm cố định: hàm mới ở mỗi lần vẽ sẽ chạy lại effect, tức hỏi BE ở mỗi lần đổi route.
const reloadPage = () => window.location.reload();

/**
 * So tên bản của FE với BE; lệch thì tự tải lại trang **một lần** cho mỗi tên bản BE.
 *
 * Tab mở từ trước một lần deploy chạy FE cũ trên BE mới, và tester chụp ảnh tab ấy thì ticket mang
 * tên bản sai. So lúc mở và mỗi khi tab hiện lại (`visibilitychange`), vì tab nằm nền qua một lần
 * deploy là ca thường. BE lỗi hay không trả lời thì không làm gì: chữ trên màn vẫn là tên FE.
 *
 * Gọi **một lần** ở gốc app, không ở từng chỗ hiện chữ.
 *
 * @param reload Cách tải lại; test thay bằng một hàm đếm.
 */
export function useVersionCheck(reload: () => void = reloadPage): void {
  useEffect(() => {
    let live = true;
    const check = () => {
      if (document.visibilityState === "hidden") return;
      api
        .version()
        .then(({ version }) => {
          if (!live || typeof version !== "string" || version === VERSION) return;
          if (remembered() === version) return;
          // Không ghi nhớ được (trình duyệt chặn bộ nhớ) thì không tải lại: tải mà không nhớ là
          // quay vòng mãi. Chữ trên màn vẫn là tên FE, đúng bản tab này đang chạy.
          if (remember(version)) reload();
        })
        .catch(() => {
          /* BE chưa lên hay đang deploy: giữ nguyên, lần hiện tab sau hỏi lại */
        });
    };
    check();
    document.addEventListener("visibilitychange", check);
    return () => {
      live = false;
      document.removeEventListener("visibilitychange", check);
    };
  }, [reload]);
}

function remembered(): string | null {
  try {
    return window.sessionStorage.getItem(RELOADED_FOR);
  } catch {
    return null;
  }
}

/** Ghi tên bản BE vừa tải lại vì nó; `true` khi đọc lại thấy đúng tên ấy. */
function remember(version: string): boolean {
  try {
    window.sessionStorage.setItem(RELOADED_FOR, version);
    return window.sessionStorage.getItem(RELOADED_FOR) === version;
  } catch {
    return false;
  }
}

/**
 * Chữ tên bản (Figma `Version tag` `810:6501`, một nấc `state=default`). Bấm thì chép
 * "Phiên bản lab-…" để dán vào ticket; chữ trên màn không đổi (người dùng chốt 28/10/2026).
 *
 * @param corner Góc dưới phải của màn học sinh (Figma `13v` `810:7200`, `12v` `810:7215`); không có
 *   thì là dòng ở chân rail giáo viên (`9v` `810:6503`).
 */
export function VersionTag({ corner = false }: { corner?: boolean }) {
  return (
    <button
      type="button"
      className={corner ? "version-tag corner" : "version-tag"}
      title="Bấm để chép tên bản"
      onClick={() => {
        void navigator.clipboard?.writeText(`Phiên bản ${VERSION}`).catch(() => {
          /* trang không được phép chép: tester vẫn đọc được chữ */
        });
      }}
    >
      {VERSION}
    </button>
  );
}
