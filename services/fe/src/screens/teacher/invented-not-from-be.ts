/**
 * Mọi thứ màn hình giáo viên hiện ra mà **backend không biết là đúng**.
 *
 * Tên file tự tố cáo, và đó là chủ ý: mỗi `import` của nó đều in ra dòng chữ ấy
 * ngay trong file đi mượn. `AGENTS.md:7-8` cấm một màn hình *suy ra* một luật từ
 * dữ liệu; chỗ này nặng hơn một bậc — nó **phát minh** ra thứ BE không có cột
 * nào để lưu. Nên nó bị dồn vào đúng một module, và khi BE có thật thì chỗ phải
 * sửa là một chỗ chứ không phải một cuộc đi tìm.
 *
 * Một món, và lý do nó chưa có thật:
 *
 * - **Con số trên huy hiệu Bảng theo dõi.** Chưa có đường đếm nào trả về nó.
 *
 * Chip nguồn trên từng câu (*"Lấy từ ngân hàng câu hỏi"*, *"Thêm mới · đã kiểm"*) từng nằm ở đây,
 * chọn theo hash id; đã **gỡ** 17/10/2026 thay vì giữ tới khi có cột nguồn (plan `backlog-tier-1`).
 *
 * Danh sách đoạn chat từng nằm ở đây và nay đã **thật**: `teacher_conversations`
 * chứa nhiều luồng, và `GET /api/teacher/conversations` trả chúng kèm tiêu đề do
 * model đặt. Một món nợ của `backlog.md` được trả.
 *
 * Vì con số kia là chữ bịa, nó **không bấm được**: `Rail` dựng bốn đích đến ở dạng
 * trơ. Một hàng bấm vào không mở ra gì thì thà đừng mời bấm.
 */

/** Số việc đang chờ người xem trên Bảng theo dõi. Không có đường nào đếm nó. */
export const DASHBOARD_WAITING = 3;

/**
 * Ba gợi ý mở đầu.
 *
 * Khác món trên ở chỗ **không bịa đặt gì**: đây là chữ sẵn để điền vào ô
 * nhập, không phải một khẳng định về trạng thái của hệ thống. Nó nằm đây vì
 * thiết kế ghi đúng ba câu này, và chúng thuộc về thiết kế chứ không thuộc về
 * dữ liệu.
 */
export const OPENERS = [
  "Tạo đề kiểm tra 15 phút chương Hàm số cho lớp 12A",
  "Thêm 5 câu mức vận dụng vào đề này",
  "Lớp 12A câu nào sai nhiều nhất?",
];
