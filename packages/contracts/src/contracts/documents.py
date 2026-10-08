"""Hai message của vòng xử lý tài liệu, cộng bốn trạng thái mà màn hình phải nói được.

Vòng việc đi hai chiều và vì thế có hai message: BE giao một tệp cho `services/document` đọc,
rồi `services/document` giao kết quả về cho BE ghi. Không bên nào gọi HTTP sang bên nào, và
không bên nào đọc database của bên nào -- payload chở đủ mọi thứ, đúng như `GradingRequested`
đã làm cho AGENT.

Module này chỉ là dữ liệu. Ngưỡng quyết định một tệp có đọc được chữ hay không **không** ở đây:
nó thuộc `services/document`, nơi duy nhất mở tệp ra đếm. Đặt nó ở đây là làm hai service cùng
sở hữu một luật mà không service nào chịu trách nhiệm.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from contracts.messages import SCHEMA_VERSION

# Tên task của arq, mỗi cái cho một chiều. Chúng ở đây vì cùng một lý do như
# GRADE_SUBMISSION_TASK: hai bên thống nhất trên một string, nên không bên nào phải import
# package của bên kia.
PROBE_DOCUMENT_TASK = "probe_document"
DOCUMENT_PROBED_TASK = "document_probed"


def documents_channel(teacher_id: str) -> str:
    """Tên channel pub/sub chở tiếng hích "thư viện của giáo viên này vừa đổi".

    Ở đây vì **hai service phải nói cùng một string**: `services/ingest` phát sau khi ghi
    xong một hàng, `services/be` nghe và đẩy xuống trình duyệt qua SSE. Không bên nào import
    bên nào, nên cái string là ranh giới -- đúng vai mà `GRADE_SUBMISSION_TASK` đã nhận.

    Một hàm chứ không phải một hằng, vì channel mang `teacher_id`: rail vẽ **cả thư viện** của
    một giáo viên, nên một màn hình đang mở là một subscription. Một channel cho mỗi tài liệu
    bắt trình duyệt đăng ký N kênh rồi huỷ từng cái khi chúng xong -- N lần phức tạp cho đúng
    một thông tin.

    Args:
        teacher_id: Giáo viên nào.

    Returns:
        Tên channel.
    """
    return f"documents:{teacher_id}"


class DocumentState(StrEnum):
    """Một tài liệu đang ở đâu trong vòng xử lý.

    Bốn giá trị, không ba, và ADR-27 chốt đúng con số ấy: *"màn hình nói rõ nó đang ở đâu trong
    bốn trạng thái: đang xử lý - sẵn sàng - không đọc được chữ - xử lý hỏng."*

    Hai trạng thái cuối trông giống nhau từ xa nhưng là hai câu khác nhau với giáo viên.
    `NO_TEXT_LAYER` là một **phán quyết**: tệp đã được đọc xong, và nó không dùng được -- tải
    lại cùng tệp ấy sẽ cho đúng kết quả ấy. `FAILED` là một **lần không trả lời được**: tệp có
    thể vẫn tốt, chỉ là job đã chết, nên thử lại là việc có nghĩa. Gộp hai cái lại là nói với
    một người rằng cuốn sách của họ vô dụng trong khi thật ra worker vừa bị tắt.

    `PROCESSING` là trạng thái một hàng mới sinh ra mang, và nó **không bao giờ được là trạng
    thái cuối**: một chip đứng mãi ở đó vì job đã chết cũng là một chip nói dối, đúng như ADR-27
    nói, nên BE suy ra `FAILED` lúc đọc khi một hàng đứng quá lâu.
    """

    PROCESSING = "processing"
    READY = "ready"
    NO_TEXT_LAYER = "no_text_layer"
    FAILED = "failed"


class DocumentProbeRequested(BaseModel):
    """Việc BE giao cho `services/document`: mở tệp này ra xem có đọc được chữ không.

    Chở `storage_key` chứ không chở byte. Nhét cả tệp vào payload là bắt Redis chuyên chở một
    cuốn sách cho mỗi lần tải lên, và trần của BE là 100 MB một tệp.

    `filename` có mặt vì phần mở rộng quyết định đường đọc: `.pdf` đi qua PyMuPDF, còn `.txt` và
    `.md` thì chữ **là** toàn bộ tệp và không có khái niệm trang nào. Suy từ `storage_key` ra
    cũng được -- khoá mang đúng phần mở rộng ấy -- nhưng làm vậy là biến sơ đồ đặt tên khoá
    thành một hợp đồng mà không ai khai, và ngày đổi tiền tố là ngày đường đọc chọn sai nhánh.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    document_id: str
    storage_key: str
    filename: str


class DocumentProbed(BaseModel):
    """Kết quả `services/document` giao về cho BE ghi.

    `page_count` là `None` khi con số không tồn tại, không phải khi nó chưa biết -- `.txt` và
    `.md` không có trang. Một số `0` ở đây hợp lệ về kiểu và sai về nghĩa, và
    `teacher_documents.py` đã ghi sẵn luật cho đúng ca này: *"một con số trang bịa ra thì tệ hơn
    hẳn việc không có nó: giáo viên sẽ tin."*

    `fault` là một câu **tiếng Việt cho giáo viên đọc**, không phải một mã lỗi: nó đi thẳng lên
    chip. Rỗng khi `state` là `READY`.

    `state` không bao giờ là `PROCESSING` trên đường này. Message này tồn tại vì việc đã xong --
    xong tốt, xong với một phán quyết, hay xong vì hỏng.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    document_id: str
    state: DocumentState
    page_count: int | None = None
    fault: str = ""
