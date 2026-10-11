"""Hai message của vòng xử lý tài liệu, cộng bốn trạng thái mà màn hình phải nói được.

Vòng việc đi hai chiều và vì thế có hai message: BE giao một tệp cho `services/document` đọc,
rồi `services/document` giao kết quả về cho BE ghi. Không bên nào gọi HTTP sang bên nào, và
không bên nào đọc database của bên nào -- payload chở đủ mọi thứ, đúng như
`DraftQuestionRequested` làm cho AGENT.

Module này chỉ là dữ liệu. Ngưỡng quyết định một tệp có đọc được chữ hay không **không** ở đây:
nó thuộc `services/document`, nơi duy nhất mở tệp ra đếm. Đặt nó ở đây là làm hai service cùng
sở hữu một luật mà không service nào chịu trách nhiệm.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# Số phiên bản của họ message này. Mỗi họ tự khai số của chính nó, như `authoring` và
# `teacher_chat` -- một họ đổi hình dạng thì chỉ số của nó nhích, không kéo theo họ khác.
SCHEMA_VERSION = 1

# Tên task của arq, mỗi cái cho một chiều. Chúng ở đây vì hai bên thống nhất trên một
# string, nên không bên nào phải import
# package của bên kia.
PROBE_DOCUMENT_TASK = "probe_document"
DOCUMENT_PROBED_TASK = "document_probed"
# Từ plan 3b: một PDF scan được đọc bằng OCR theo **lô trang**, mỗi lô một job trên chính queue của
# `services/document`, và sau mỗi lô có một tiếng báo tiến độ đi về `services/ingest`.
OCR_PAGES_TASK = "ocr_pages"
DOCUMENT_PROGRESS_TASK = "document_progress"
# Từ plan 3c: bản thô đã nằm trong kho nội dung thì tài liệu chưa *sẵn sàng* -- nó còn chờ cây. Job
# dựng cây chạy trên queue **riêng** của `services/document` (D4), và chỉ nó gửi `READY`.
INDEX_DOCUMENT_TASK = "index_document"


def documents_channel(teacher_id: str) -> str:
    """Tên channel pub/sub chở tiếng hích "thư viện của giáo viên này vừa đổi".

    Ở đây vì **hai service phải nói cùng một string**: `services/ingest` phát sau khi ghi
    xong một hàng, `services/be` nghe và đẩy xuống trình duyệt qua SSE. Không bên nào import
    bên nào, nên cái string là ranh giới chứ không phải một tiện nghi.

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


class DocumentPagesRequested(BaseModel):
    """Một lô trang của một PDF scan cần OCR -- việc `services/document` tự giao cho chính nó.

    Không phải message giữa hai service: bên đẩy và bên nhận đều là `services/document`. Nó ở đây
    vì đây là chỗ mọi payload của arq được khai, và một payload không khai là một dict mà lần đổi
    tên trường sau làm vỡ âm thầm -- job của lô kế đã nằm trong Redis từ trước lần deploy.

    Vì sao theo lô chứ không cả cuốn trong một job: một cuốn 200 trang ở 4,5 s/trang là ~15 phút,
    gấp bảy lần trần một job. Mỗi lô đọc vài trang, ghi chúng vào kho nội dung, rồi tự đẩy lô kế
    (plan 3b, D3). Nối đuôi chứ không song song: OCR ăn hết CPU, nên hai lô cùng lúc chỉ tranh
    luồng.

    Attributes:
        document_id: Tài liệu đang đọc.
        storage_key: Khoá byte của tệp trong object storage -- mỗi lô đọc lại tệp, không chở byte.
        filename: Tên tệp, cho dòng log và cho câu nói với giáo viên.
        first: Trang đầu của lô, **đếm từ 1** như `RawPage.page`.
        page_count: Tổng số trang của tệp, để lô biết nó có phải lô cuối không mà không phải hỏi
            ai.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    document_id: str
    storage_key: str
    filename: str
    first: int = Field(ge=1)
    page_count: int = Field(ge=1)


class DocumentProgress(BaseModel):
    """Tiếng báo của `services/document` sau mỗi lô OCR: *đã đọc được ngần này trang*.

    Từ plan 3c nó cũng là **nhịp tim** của job dựng cây: gửi ở mỗi chặng với
    `pages_read = page_count`, chỉ để dời `progress_at`.

    Nó tồn tại vì **phép suy *đứng quá lâu*** của BE: một hàng đứng ở `processing` quá 300 s bị đọc
    ra `failed`, và một cuốn sách scan thì đứng ở đó mười lăm phút một cách hợp lệ. Mỗi tiếng báo
    dời mốc đo của phép suy ấy (`documents.progress_at`), nên chỉ một chuỗi lô **ngừng tiến** mới
    bị coi là chết -- lưới cũ còn nguyên cho đúng ca nó sinh ra để bắt (plan 3b, D4).

    Không mang `state`: tiến độ không phải một phán quyết, và tài liệu vẫn `processing`.

    Attributes:
        document_id: Tài liệu đang đọc.
        pages_read: Số trang đã đọc xong và đã nằm trong kho nội dung.
        page_count: Tổng số trang.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    document_id: str
    pages_read: int = Field(ge=0)
    page_count: int = Field(ge=1)


class DocumentIndexRequested(BaseModel):
    """Một tài liệu đã có bản thô trong kho nội dung, cần dựng cây rồi mới được báo *sẵn sàng*.

    Như `DocumentPagesRequested`, đây là việc `services/document` tự giao cho chính nó -- nhưng cho
    **một worker khác** (`document.index_worker`), trên queue riêng: dựng cây là việc chờ mạng (Jev,
    `gpt-4o-mini`), còn worker OCR chạy một job một lúc vì OCR ăn hết CPU (plan 3c, D4).

    Không chở chữ: bản thô nằm trong Mongo, và job đọc nó từ đó. Chở `storage_key` vì tên chương
    nằm trong **ảnh** banner, và `gpt-5.6-luna` cần ảnh ấy (D9).

    Attributes:
        document_id: Tài liệu.
        storage_key: Khoá byte của tệp trong object storage.
        filename: Tên tệp, cho dòng log.
        page_count: Số trang như `DocumentProbed.page_count` -- `None` với tệp văn bản thuần. Job
            gửi lại đúng con số này trong `DocumentProbed(READY)`.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    document_id: str
    storage_key: str
    filename: str
    page_count: int | None = Field(default=None, ge=1)
