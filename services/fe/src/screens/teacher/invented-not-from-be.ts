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

/**
 * Nguồn của một câu hỏi, và việc nó đã được kiểm hay chưa.
 *
 * **Đây là chỗ nặng nhất trong file này.** Hai món trên chỉ là chữ chưa có dữ liệu;
 * món này thì nói với giáo viên một điều mà hệ thống **không biết là đúng**. `Question`
 * có năm cột và không cột nào nói nguồn hay trạng thái kiểm; `drafting._write` còn
 * không nối `DraftItem` với `Question`, nên ngay cả *"do model viết"* cũng không truy
 * được. Ba cái chip dưới đây không suy ra được từ bất cứ cột nào.
 *
 * Nhận vào với ba điều kiện, và đây là điều kiện thứ nhất: đúng **một** module chứa
 * nó, và tên module tự tố cáo. Điều kiện thứ hai là `tools/check_contract.py` làm
 * build đỏ nếu nó bị sao chép sang chỗ thứ hai. Thứ ba là một dòng trong
 * `docs/plans/backlog.md` và một dòng trong mục *Nơi luật này đang được thi hành* của
 * ADR-04 ghi rằng FE hiện **giả vờ** thi hành nó.
 *
 * Nhãn chọn theo id chứ không theo thứ tự hay ngẫu nhiên, vì một chip nhảy sang màu
 * khác sau mỗi lần tải lại trang sẽ dạy giáo viên rằng mấy cái chip này vô nghĩa — mà
 * điều đó thì đúng, chỉ là không nên dạy bằng cách ấy.
 */
export interface Provenance {
  label: string;
  /** `""` cho ngân hàng, `"checked"` cho đã kiểm, `"unchecked"` cho chưa kiểm. */
  tone: "" | "checked" | "unchecked";
}

const PROVENANCES: Provenance[] = [
  { label: "Lấy từ ngân hàng câu hỏi", tone: "" },
  { label: "Thêm mới · đã kiểm", tone: "checked" },
  { label: "Thêm mới · chưa kiểm", tone: "unchecked" },
];

/**
 * Chip nguồn của một câu hỏi. **Bịa, một cách có kiểm soát.**
 *
 * @param questionId - Id của câu hỏi, dùng làm hạt giống.
 * @returns Một trong ba nhãn, cố định theo id.
 */
export function provenanceOf(questionId: string): Provenance {
  let seed = 0;
  for (const ch of questionId) seed = (seed * 31 + ch.charCodeAt(0)) % 9973;
  return PROVENANCES[seed % PROVENANCES.length];
}
