"""Bảng điểm của một đề trong một lớp, dựng thành tệp `.xlsx` (việc 20, plan `results-xlsx-export`).

Một trang tính, một dòng đầu, rồi mỗi học sinh của lớp một dòng theo mã học sinh: *Mã học sinh*,
*Họ tên*, *Câu 1*…*Câu N*, *Tổng*. Bảng phẳng để dán thẳng lên sổ điểm; khớp mẫu vnEdu/SMAS khi có
tệp mẫu thật.

Em chưa nộp bài vẫn có dòng, và các ô điểm **để trống**: trống và 0 là hai sự thật khác nhau -- 0 là
em ấy làm bài và sai hết (Decision 1 của plan).

Hàm ở đây thuần: nhận dữ liệu đã đọc, trả byte. Route và quyền (chỉ tác giả, ADR-22) ở
`teacher_reads.results_xlsx`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

# Excel giới hạn tên trang tính ở 31 ký tự và cấm vài ký tự.
_SHEET_NAME_LIMIT = 31
_SHEET_FORBIDDEN = str.maketrans({one: " " for one in "[]:*?/\\"})

# Chuỗi mở đầu bằng một trong các ký tự này thì Excel đọc như công thức (chèn công thức, CSV/XLSX
# injection): một họ tên *"=HYPERLINK(...)"* thành một link. Ô ấy được ghi là chữ, có dấu nháy ẩn.
_FORMULA_START = ("=", "+", "-", "@")


@dataclass(frozen=True)
class ResultLine:
    """Một học sinh trong bảng điểm.

    Attributes:
        student_code: Mã học sinh.
        full_name: Họ tên.
        marks: Điểm từng câu theo thứ tự câu, hay `None` khi em chưa nộp. Một câu không có
            dòng sổ điểm là `None` ở ô của câu ấy: trống, không phải 0.
    """

    student_code: str
    full_name: str
    marks: Sequence[float | None] | None


def build_workbook(class_name: str, question_count: int, lines: Sequence[ResultLine]) -> bytes:
    """Dựng tệp `.xlsx` của một bảng điểm.

    Args:
        class_name: Tên lớp -- tên trang tính.
        question_count: Số câu của đề, tức số cột *Câu k*.
        lines: Mỗi học sinh một dòng, đã sắp.

    Returns:
        Byte của tệp.
    """
    book = Workbook()
    sheet = book.active
    # Dấu nháy ở hai đầu tên làm Excel đòi *sửa tệp*.
    sheet.title = (class_name.translate(_SHEET_FORBIDDEN).strip(" '") or "Bảng điểm")[
        :_SHEET_NAME_LIMIT
    ]
    head = ["Mã học sinh", "Họ tên", *(f"Câu {n}" for n in range(1, question_count + 1)), "Tổng"]
    sheet.append(head)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for line in lines:
        if line.marks is None:
            sheet.append([line.student_code, line.full_name])
        else:
            total = round(sum(one for one in line.marks if one is not None), 2)
            sheet.append([line.student_code, line.full_name, *line.marks, total])
        for cell in sheet[sheet.max_row][:2]:
            if isinstance(cell.value, str) and cell.value.startswith(_FORMULA_START):
                cell.data_type = "s"
                cell.quotePrefix = True
    sheet.freeze_panes = "C2"
    sheet.column_dimensions["A"].width = 14
    sheet.column_dimensions["B"].width = 28
    for index in range(3, question_count + 4):
        sheet.column_dimensions[get_column_letter(index)].width = 8
    out = BytesIO()
    book.save(out)
    return out.getvalue()
