"""Bộ đo chất lượng OCR trên sách giáo khoa thật.

Không phải một phần của service nào: nó sống ở `tools/` vì nó chạy trên `data/` -- thư mục nằm
ngoài git -- và vì không dòng nào của nó được chạy lúc sản phẩm chạy. `.\\dev.ps1 check` không
gọi tới đây; thứ `check` canh là **test của thước đo**, và chúng dựng dữ liệu của riêng mình.
"""
