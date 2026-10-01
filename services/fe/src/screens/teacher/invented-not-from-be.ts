/**
 * Mọi thứ màn hình giáo viên hiện ra mà **backend không biết là đúng**.
 *
 * Tên file tự tố cáo, và đó là chủ ý: mỗi `import` của nó đều in ra dòng chữ ấy
 * ngay trong file đi mượn. `AGENTS.md:7-8` cấm một màn hình *suy ra* một luật từ
 * dữ liệu; chỗ này nặng hơn một bậc — nó **phát minh** ra thứ BE không có cột
 * nào để lưu. Nên nó bị dồn vào đúng một module, và khi BE có thật thì chỗ phải
 * sửa là một chỗ chứ không phải một cuộc đi tìm.
 *
 * Ba món, và lý do từng món chưa có thật:
 *
 * - **Danh sách đoạn chat.** BE có đúng **một** luồng cho mỗi giáo viên:
 *   `GET /api/teacher/chat` không nhận id nào và `teacher_threads` khoá theo
 *   `teacher_id`. Không có "đoạn chat thứ hai" để liệt kê, nên cả nhóm ngày lẫn
 *   tiêu đề đều là chữ bịa.
 * - **Tài liệu.** Model `Document` là việc của bước sau trong plan. Khi nó có
 *   thật thì `DOCUMENTS` dưới đây biến mất, không phải đổi hình.
 * - **Con số trên huy hiệu Bảng theo dõi.** Chưa có đường đếm nào trả về nó.
 *
 * Vì chúng là chữ bịa, chúng **không bấm được**: `Rail` dựng chúng ở dạng trơ.
 * Một hàng bấm vào không mở ra gì thì thà đừng mời bấm.
 */

/** Một đoạn chat giả, xếp dưới một nhãn thời gian giả. */
export interface InventedConversation {
  group: string;
  title: string;
}

/** Một tài liệu giả, đúng hình dạng mà chip trên rail vẽ. */
export interface InventedDocument {
  kind: string;
  name: string;
  meta: string;
}

export const CONVERSATIONS: InventedConversation[] = [
  { group: "Hôm nay", title: "Đề cuối kỳ — Hình học 11" },
  { group: "Hôm nay", title: "Lớp 11B — nhập danh sách" },
  { group: "7 ngày qua", title: "Giữa kỳ I — Đại số tổ hợp" },
  { group: "7 ngày qua", title: "Thống kê lỗi sai Toán 12" },
  { group: "7 ngày qua", title: "Ôn tập chương Giới hạn" },
  { group: "7 ngày qua", title: "Lớp 12B — nhập danh sách" },
  { group: "30 ngày qua", title: "Đề tuần 3 — Đạo hàm" },
  { group: "30 ngày qua", title: "Phân tích lỗi sai giữa kỳ" },
];

export const DOCUMENTS: InventedDocument[] = [
  { kind: "PDF", name: "SGK Giải tích 12.pdf", meta: "184 trang · đọc được chữ" },
  { kind: "PDF", name: "Đề cương ôn tập.pdf", meta: "12 trang · đọc được chữ" },
  { kind: "PDF", name: "Chuyên đề Hàm số.pdf", meta: "184 trang · đọc được chữ" },
  { kind: "PDF", name: "Ma trận đề cuối kỳ.pdf", meta: "6 trang · đọc được chữ" },
  { kind: "PDF", name: "Bài tập chương III.pdf", meta: "28 trang · đọc được chữ" },
];

/** Số việc đang chờ người xem trên Bảng theo dõi. Không có đường nào đếm nó. */
export const DASHBOARD_WAITING = 3;

/**
 * Ba gợi ý mở đầu.
 *
 * Khác ba món trên ở chỗ **không bịa đặt gì**: đây là chữ sẵn để điền vào ô
 * nhập, không phải một khẳng định về trạng thái của hệ thống. Nó nằm đây vì
 * thiết kế ghi đúng ba câu này, và chúng thuộc về thiết kế chứ không thuộc về
 * dữ liệu.
 */
export const OPENERS = [
  "Tạo đề kiểm tra 15 phút chương Hàm số cho lớp 12A",
  "Thêm 5 câu mức vận dụng vào đề này",
  "Lớp 12A câu nào sai nhiều nhất?",
];
