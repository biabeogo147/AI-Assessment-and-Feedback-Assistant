/**
 * Mọi thứ màn hình giáo viên hiện ra mà **BE không có**.
 *
 * Tên file tự tố cáo, và đó là chủ ý: mỗi `import` của nó đều in ra dòng chữ ấy
 * ngay trong file đi mượn. `services/fe/AGENTS.md` cấm một màn hình *suy ra* một luật
 * từ dữ liệu; chữ BE không có cột nào để lưu còn nặng hơn một bậc — nó là **phát minh**.
 * Thứ như vậy, nếu còn, phải dồn vào đúng module này, để khi BE có thật thì chỗ phải
 * sửa là một chỗ chứ không phải một cuộc đi tìm. `tools/check_contract.py` canh điều ấy.
 *
 * Nay chỉ còn ba gợi ý mở đầu, và chúng không khẳng định gì về hệ thống.
 *
 * Con số *"3"* trên huy hiệu *Bảng theo dõi* từng nằm ở đây, không đường nào đếm nó; đã **gỡ**
 * 18/10/2026 cùng huy hiệu (plan `wave-1-small-fixes`). Chip nguồn trên từng câu (*"Lấy từ ngân hàng
 * câu hỏi"*, *"Thêm mới · đã kiểm"*) từng nằm ở đây, chọn theo hash id; đã **gỡ** 17/10/2026 thay
 * vì giữ tới khi có cột nguồn (plan `backlog-tier-1`).
 *
 * Danh sách đoạn chat từng nằm ở đây và nay đã **thật**: `teacher_conversations`
 * chứa nhiều luồng, và `GET /api/teacher/conversations` trả chúng kèm tiêu đề do
 * model đặt. Một món nợ của `backlog.md` được trả.
 */

/**
 * Ba gợi ý mở đầu.
 *
 * **Không bịa đặt gì**: đây là chữ sẵn để điền vào ô
 * nhập, không phải một khẳng định về trạng thái của hệ thống. Nó nằm đây vì
 * thiết kế ghi đúng ba câu này, và chúng thuộc về thiết kế chứ không thuộc về
 * dữ liệu.
 */
export const OPENERS = [
  "Tạo đề kiểm tra 15 phút chương Hàm số cho lớp 12A",
  "Thêm 5 câu mức vận dụng vào đề này",
  "Lớp 12A câu nào sai nhiều nhất?",
];
