/**
 * Chỗ nhớ của bề mặt giáo viên: `localStorage`, có kiểu, và nuốt lỗi ở đúng một nơi.
 *
 * Bề mặt này nhớ bốn thứ — bề rộng hai cột, chiều cao ngăn tài liệu, nấc thu của từng
 * ngăn rail, và bản nháp cài đặt phát hành. Ba thứ đầu từng có ba bản `try/catch` chép
 * tay giống hệt nhau ở hai file; thứ thứ tư cần JSON, nên chép lần thứ tư là chép một
 * khuôn đã biết là chép.
 *
 * **Mọi hàm ở đây nuốt lỗi, và đó là luật chứ không phải sự cẩu thả.** `localStorage`
 * ném thật: cửa sổ ẩn danh, storage bị chặn bởi chính sách trình duyệt, hoặc quota đầy.
 * Mất một bề rộng cột hay một nấc thu không đáng làm trắng màn hình của giáo viên. Cái
 * giá phải trả là nó **im lặng** khi hỏng — nên không được để thứ gì quan trọng ở đây:
 * chỗ này giữ *tiện nghi*, còn sự thật thì ở BE.
 *
 * Mọi khoá mang tiền tố `kriky.teacher.` để không đụng chạm thứ gì khác cùng origin.
 */

/**
 * Đọc một chuỗi đã nhớ.
 *
 * @param key - Khoá đầy đủ.
 * @returns Chuỗi đã lưu, hoặc `null` khi chưa có hoặc không đọc được.
 */
function readRaw(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    /* ẩn danh hoặc storage bị chặn; chỗ gọi đều có đường mặc định */
    return null;
  }
}

/**
 * Ghi một chuỗi. Hỏng thì im lặng.
 *
 * @param key - Khoá đầy đủ.
 * @param value - Giá trị.
 */
function writeRaw(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* không ghi được thì giá trị chỉ sống trong phiên này */
  }
}

/**
 * Một con số đã nhớ, **trong khoảng cho phép**.
 *
 * Số ngoài biên bị bỏ chứ không bị kẹp lại: nó chỉ tới từ một lần đổi biên trong code
 * hoặc từ một bàn tay sửa `localStorage`, và khi ấy con số cũ là ý của một bản cũ, không
 * phải ý của giáo viên. Kẹp lại là giữ một nửa ý ấy; bỏ đi là trả về con số của thiết kế.
 *
 * @param key - Khoá đầy đủ.
 * @param fallback - Dùng khi chưa có, không đọc được, hoặc ngoài khoảng.
 * @param min - Biên dưới, tính cả.
 * @param max - Biên trên, tính cả.
 * @returns Một con số chắc chắn nằm trong khoảng.
 */
export function readNumber(
  key: string,
  fallback: number,
  min: number,
  max: number,
): number {
  // Khoá vắng phải ra `fallback`, không ra 0. `Number(null)` và `Number("")` đều cho
  // **0**, nên thiếu dòng này thì một khoá chưa từng ghi sẽ lọt qua phép kiểm biên bất kỳ
  // lúc nào `min <= 0`. Ba chỗ gọi hôm nay đều có `min > 0` nên chưa ai thấy; hàm thì
  // dùng chung, và một cái bẫy chỉ chờ đúng tham số để nổ thì vẫn là một cái bẫy.
  const raw = readRaw(key);
  if (raw === null || raw === "") return fallback;

  const saved = Number(raw);
  if (Number.isFinite(saved) && saved >= min && saved <= max) return saved;
  return fallback;
}

/**
 * Ghi một con số.
 *
 * @param key - Khoá đầy đủ.
 * @param value - Con số.
 */
export function writeNumber(key: string, value: number): void {
  writeRaw(key, String(value));
}

/**
 * Một cờ đã nhớ.
 *
 * Mặc định **bật**, và chiều mặc định ấy là một quyết định: khoá chỉ được ghi khi người
 * dùng tự tắt một thứ gì đó, nên vắng khoá nghĩa là chưa ai tắt. Một rail mới mở ra phải
 * cho thấy nó có gì.
 *
 * @param key - Khoá đầy đủ.
 * @returns `false` chỉ khi đã ghi đúng `"0"`; mọi trường hợp khác là `true`.
 */
export function readFlag(key: string): boolean {
  return readRaw(key) !== "0";
}

/**
 * Ghi một cờ.
 *
 * @param key - Khoá đầy đủ.
 * @param on - Giá trị.
 */
export function writeFlag(key: string, on: boolean): void {
  writeRaw(key, on ? "1" : "0");
}

/**
 * Khoá này **đã từng** được ghi chưa?
 *
 * `readFlag` không trả lời được câu ấy: nó cho `true` cho cả *"đã ghi bật"* lẫn *"chưa ai
 * ghi"*, vì mặc định của nó là bật. Hai trạng thái ấy khác nhau ở đúng một chỗ — một mặc
 * định **phụ thuộc ngữ cảnh**. Tấm trượt phát hành muốn mở sẵn ở đề thường và thu sẵn ở đề
 * đã khoá; mà "thu sẵn" chỉ được phép áp khi giáo viên **chưa** tự quyết bao giờ, nếu không
 * nó sẽ đóng sập một tấm trượt mà chính họ vừa bung ra.
 *
 * @param key - Khoá đầy đủ.
 * @returns `true` khi khoá có mặt, kể cả khi giá trị của nó là `"0"`.
 */
export function knows(key: string): boolean {
  return readRaw(key) !== null;
}

/**
 * Một object đã nhớ.
 *
 * `JSON.parse` ném trên chuỗi rác, và chuỗi rác có thật: một bản cũ của app đã ghi một
 * hình dạng khác vào đúng khoá này. Nên hỏng thì trả `null` chứ không ném — chỗ gọi đọc
 * `null` là *"chưa có gì"*, một trạng thái nó vốn đã phải xử lý.
 *
 * Không kiểm hình dạng ở đây: kiểu `T` là lời hứa của chỗ gọi, và chỗ gọi là nơi duy nhất
 * biết hình dạng nào là đúng.
 *
 * @param key - Khoá đầy đủ.
 * @returns Object đã lưu, hoặc `null`.
 */
export function readJson<T>(key: string): T | null {
  const raw = readRaw(key);
  if (raw === null) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    /* một bản cũ đã ghi hình dạng khác vào đúng khoá này */
    return null;
  }
}

/**
 * Ghi một object.
 *
 * @param key - Khoá đầy đủ.
 * @param value - Object.
 */
export function writeJson(key: string, value: unknown): void {
  try {
    writeRaw(key, JSON.stringify(value));
  } catch {
    /* object có vòng lặp tham chiếu; không đáng làm hỏng gì */
  }
}

/**
 * Quên một khoá.
 *
 * @param key - Khoá đầy đủ.
 */
export function forget(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* như trên */
  }
}
