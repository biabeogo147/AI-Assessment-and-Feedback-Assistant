"""Đọc chữ từ một trang sách đã scan. **Chỉ chữ** -- công thức không được đọc ở đây.

Chia ba chặng vì chúng hỏng khác nhau và tốn khác nhau, nên gộp lại là mất cả hai thông tin:

- `layout` -- PP-DocLayout: ảnh thành các khối có nhãn, hộp bao và thứ tự đọc.
- `textline` -- detector của PaddleOCR: cả trang thành từng dòng.
- `recognize` -- EasyOCR hoặc VietOCR: một dòng thành chữ tiếng Việt có dấu.

Vì sao hai hệ: PaddleOCR *nhìn* rất tốt nhưng **thủng từ điển ký tự** -- nó không bao giờ phát ra tổ
hợp hai dấu, nên `Kết nối tri thức` ra `Kt ni tri thc`. Bộ nhận dạng tiếng Việt đọc đúng dấu nhưng
không có detector tốt. Lấy nửa mạnh của mỗi bên. Decision Record đầy đủ nằm trong
`document-ocr-text-and-latex`.

Công thức được đọc **lúc ra đề**, chỉ ở phần tài liệu được tham chiếu, bằng gpt-4.1-mini qua API --
sẽ nằm ở `services/agent/src/agent/vision.py` (chưa viết; `document-ocr-text-and-latex`, chờ người
dùng duyệt chi phí). PP-FormulaNet (`formula.py`) đã gỡ khỏi package.
"""

# PHẢI đứng đây, và phải đứng **trước** mọi thứ chạm paddle. Đo trên Windows ngày 10/10/2026:
#
#     import torch, paddle   -> chạy
#     import paddle, torch   -> OSError [WinError 127] ... shm.dll
#
# PaddlePaddle nạp một bộ DLL che mất thứ torch cần, nên thứ tự nạp là một ràng buộc thật chứ
# không phải một sở thích. Đặt nó ở `__init__` của package là chỗ duy nhất chắc chắn chạy trước
# mọi module con, dù ai import module nào trước. `test_ocr_loads_torch_first` canh dòng này; bỏ
# nó đi thì cả đường OCR chết bằng một lỗi DLL không nói được nguyên nhân.
import torch  # noqa: F401
