# Plan — rà ADR cho khớp code, bỏ cổng độ tin thấp

## Goal

Một dev mới đọc `docs/decisions/` thì thấy đúng sản phẩm đang chạy. Hai việc:

1. Ghi quyết định ngày 19/10/2026: **bỏ cổng thứ hai của ADR-05** (kết quả chấm độ tin thấp chờ giáo
   viên rồi mới tới học sinh). Hàng đợi giáo viên vẫn còn, là hàng đợi *Cần bạn xem* của ADR-34.
2. Rà mọi ADR: dòng trạng thái khớp `README.md` và khớp code; mục *Nơi luật này đang được thi hành*
   không trỏ vào file, hàm, test hay plan đã mất mà không có hậu ký nói ra.

## Scope

- Trong:
  - `docs/decisions/`: ADR và `README.md`;
  - tài liệu còn kể cổng độ tin thấp hay hàng đợi review theo nghĩa cũ:
    - `docs/overview/project-overview.md`, `business-workflows.md`, `use-case-specification.md`,
      `teacher-surface.md`;
    - `docs/local-development.md`;
    - `docs/plans/backlog.md`: gỡ việc *bật lại confidence của chẩn đoán*;
    - `docs/testing/kich-ban-thu-tay-giao-vien.md`;
  - docstring đầu tệp `services/be/src/be/routes.py`.
- Ngoài:
  - `docs/report/` (người dùng đang viết);
  - code chạy;
  - Figma;
  - `AGENTS.md`: dòng *chưa enforce* về câu luyện tập (ADR-17) có thể đã lỗi thời, nhưng sửa
    `AGENTS.md` cần plan riêng, và người dùng chưa quyết.
- Cách sửa: phần thân ADR giữ làm lịch sử. Sự thật mới đi vào **hậu ký 19/10/2026** và dòng trạng thái,
  như các hậu ký trước, và trỏ theo **tên hàm** chứ không theo số dòng.
- Số thứ tự cổng giữ nguyên: cổng thứ nhất là duyệt đề, cổng thứ ba là hỏi lại, không có cổng thứ hai.

## Files

- Mới: `docs/decisions/adr-37-bo-cong-do-tin-thap.md`.
- Hậu ký 19/10/2026: ADR-05, 06, 07, 08, 09, 10, 11, 14, 17, 18, 19, 20, 21, 23, 26, 27, 29.
- Chỉ dòng trạng thái: ADR-15, 16, 22, 24, 28. ADR-34 đổi đường dẫn plan.
- `docs/decisions/README.md`: bảng và mục *Còn thiếu*.
- Các tệp ở mục Scope.

## Ordered Tasks

- [x] Pha 1 — ADR-37; hậu ký ADR-05, 06, 07, 08; hậu ký ngắn *ba cổng* ở ADR-10, 14, 18, 19, 26, 27,
  29; `README.md`; tài liệu tổng quan.
- [x] Pha 2 — dòng trạng thái lệch `README.md` ở 18 ADR; tham chiếu chết ở ADR-09, 11, 14, 17, 20, 21,
  23, 34.
- [x] Subagent review; sửa theo review: số cổng ở `project-overview.md`, `be/routes.py` còn `/health`,
  ADR-05 câu luyện tập đã có, ADR-10, ADR-20 invariant, ADR-37 trỏ vào `backlog.md`, `backlog.md`,
  `local-development.md`, `teacher-surface.md`, UC-05, Workflow 3.
- [x] Hai script dò (đường dẫn, tên trong backtick): mọi thứ còn bị cờ nằm trong phần lịch sử đã có hậu
  ký nói ra; `.\dev.ps1 check` xanh.

## Validation Checks

- Script dò đường dẫn và tên: mọi file, hàm, test, hằng trong backtick hoặc còn sống, hoặc có hậu ký
  nói nó đã xoá.
- Dòng trạng thái của mọi ADR khớp cột trạng thái của `README.md`.
- `.\dev.ps1 check` xanh.
- Subagent đọc code thật, đối từng câu hậu ký.

## Status

Xong. Commit `bbabbdd` ngày 19/10/2026.
