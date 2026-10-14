# [CODE CHẾT 2026-10-11] công thức đọc bằng gpt-4.1-mini lúc ra đề — xem
# `document-ocr-text-and-latex`
#
# Cả module này đã chết, và được giữ lại dưới dạng comment thay vì xoá để sau này không ai đi tìm
# lại nó, hay dựng lại nó, mà không biết vì sao nó bị bỏ.
#
# Vì sao bỏ: benchmark 50 trang Lớp 6 tập 1 (`data/results/run-1`, 11/10/2026), 58 công thức
# nhãn vàng.
# PP-FormulaNet `plus-S` chỉ đúng 9; layout làm hỏng 24 (15 công thức không có khối nào, 9 khung
# cắt thiếu hoặc gộp), model hỏng 21 -- kể cả **mọi** công thức có chữ Việt (`ƯCLN`, "với",
# "người"), vì từ điển của nó không có chữ Việt. `plus-M` chính xác hơn chút (13 so với 9 trên 40
# cặp) mà chậm hơn 3,7 lần. Không model nào cùng họ cứu được phần lỗi của layout.
#
# Thay thế: đường upload chỉ đọc chữ (`page.py`). Công thức được đọc lúc ra đề, chỉ ở phần tài
# liệu được tham chiếu, bằng gpt-4.1-mini qua API, với **cả ảnh trang** chứ không với khung layout
# cắt -- sẽ nằm ở `services/agent/src/agent/vision.py` (chưa viết).
#
# """PP-FormulaNet: một khối công thức thành LaTeX.
#
# Đây là chặng duy nhất đọc được **cấu trúc hai chiều**, và đó không phải một tiện nghi. OCR theo
# dòng xé một phân số làm đôi theo đúng nghĩa đen -- đo ngày 10/10/2026 trên trang 40 của Lớp 12
# tập 1, nơi một engine dòng trả về `"lap-100="` rồi `"（x-27000),hayp-100="` ở hai dòng rời nhau,
# trong khi PP-FormulaNet trả về:
#
#     p-100=\\frac{100-90}{27\\;000-30\\;000}(x-27\\;000)
#
# Một luật của chặng này, và nó là thứ plan 3c dựa vào: đọc hỏng thì khối **ở lại** với
# `latex=None`, không bị bỏ đi. *Có một công thức ở đây mà chưa đọc được* khác hẳn *không có công
# thức nào*, và chỉ cái thứ nhất mới là việc của bước kiểm bằng sympy.
# """
#
# import logging
#
# import numpy as np
# from paddleocr import FormulaRecognition
# from PIL import Image
#
# from document.ocr.model import BBox
# from document.ocr.recognize import too_small
#
# logger = logging.getLogger(__name__)
#
#
# class FormulaReader:
#     """Giữ PP-FormulaNet đã nạp.
#
#     Attributes:
#         _model: Predictor của PaddleOCR.
#     """
#
#     def __init__(
#         self, use_mkldnn: bool = False, model: str = "PP-FormulaNet_plus-S", threads: int = 4
#     ):
#         """Nạp model.
#
#         Args:
#             model: Tên model. Bản `plus-S` chứ không `plus-M` (mặc định của thư viện), và đó là
#                 một đánh đổi **lấy tốc độ**, không phải vì nó chính xác hơn. Đo đối đầu
#                 11/10/2026 trên 50 trang, cùng hộp layout, 58 công thức: `plus-S` khớp đúng 10,3%
#                 với khoảng cách trung vị 0,644, `plus-M` khớp 13,8% với 0,608 -- nhưng `plus-M`
#                 chậm hơn 3,7 lần (156 s so với 42 s cho 50 trang). Sản phẩm ưu tiên tốc độ, nên
#                 chọn `S`. Một lượt đo 10 trang trước đó từng cho `S` thắng; 50 trang bác nó.
#             threads: Số luồng CPU. Xem `page.PageReader`.
#             use_mkldnn: Bật oneDNN. Mặc định tắt -- xem `layout.LayoutReader`.
#         """
#         self._model = FormulaRecognition(
#             model_name=model, enable_mkldnn=use_mkldnn, cpu_threads=threads
#         )
#
#     def read(self, image: np.ndarray, box: BBox) -> str | None:
#         """Đọc một khối công thức.
#
#         Args:
#             image: Ảnh trang, dạng mảng `numpy` RGB.
#             box: Hộp của khối công thức.
#
#         Returns:
#             Chuỗi LaTeX, hoặc `None` khi model không đọc được. `None` **không** có nghĩa là
#             không có công thức: nó có nghĩa là có một công thức chưa đọc được, và người gọi phải
#             giữ khối lại.
#         """
#         if too_small(box):
#             return None
#
#         crop = np.array(Image.fromarray(image).crop((box.left, box.top, box.right, box.bottom)))
#         try:
#             for one in self._model.predict(crop):
#                 latex = one.json["res"].get("rec_formula")
#                 if latex and latex.strip():
#                     return str(latex).strip()
#         except Exception:
#             # Một công thức không đọc được là một **kết quả**, không phải một lỗi của hệ thống:
#             # bỏ cả trang vì một khối là trả giá sai hẳn. Stack trace vào log để còn chẩn đoán.
#             logger.exception("formula recognition failed on a %sx%s box", box.width, box.height)
#         return None
