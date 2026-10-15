"""Pha lên plan của một lượt chat giáo viên: dựng prompt, rồi chọn.

Module này là **pha 1** của ADR-25. Nó tra cứu, hỏi lại, và khi đã đủ dữ kiện thì nêu một
plan — chứ không bao giờ ghi gì. Lời kể sau khi plan chạy nằm ở `reporting.py`, một task
riêng, vì đầu vào của nó khác hẳn: nó đọc kết quả của cả plan, không đọc catalog.

Hai danh mục tới riêng và điều đó là cố ý: `catalog` là tool gọi được ngay, `plannable` là
tool chỉ hẹn làm được ở pha 2. Model phải thấy cả hai — nó nêu tên tool và tên tham số
trong plan — nhưng phải phân biệt được chúng, vì gọi một tool ghi ngay lượt này sẽ bị BE
từ chối và tiêu một vòng để phát hiện lại đúng điều ấy.

Hai node, và node thứ hai là một lần gọi structured duy nhất. Nó nhỏ hơn graph soạn
đề một cách có chủ ý -- ở đây không có loop tự check, vì thứ được sinh ra không phải
nội dung ai cũng xác thực được. Một đề nghị thì hoặc được BE thực thi hoặc bị BE từ
chối, và BE là phía duy nhất biết được là cái nào.

Thứ module này cẩn thận với là prompt. Model đang chọn từ một danh sách tool nó chưa
từng thấy và đọc dữ liệu nó không tự lấy, nên cả hai phải tới dưới dạng nó làm việc
được: tên tool viết đúng chính xác như cách BE dispatch, và kết quả tool ở dạng dữ
liệu chứ không phải văn xuôi kể về dữ liệu.

System prompt mang ba luật không phải chuyện văn phong. AGENT không được nhận là mình
đã làm gì -- nó đề nghị, BE hành động (ADR-05). Nó không được nói với giáo viên nên
chọn phương án nào khi lựa chọn đó là một quyết định sư phạm, vì giáo viên giữ thẩm
quyền ấy. Và nó hỏi lại chứ không đoán khi một cái tên có thể mang nhiều nghĩa, đó là
cổng kiểm đầu vào của ADR-05.

Từ `kriky-skill-routing`, prompt là **lõi + skill**. `_CORE` mang những luật không lượt nào được
thiếu; lời dặn chỉ một loại việc cần -- tra lớp, soạn đề -- nằm trong `agent/skills/*.md`, và
`skill_router` (Jev) chọn skill nào được nạp trước khi graph chạy.
"""

import json
import logging
import re
import unicodedata
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent import llm, skill_router, skills
from agent.latex_escapes import restore_latex_escapes
from contracts import (
    NextStepCompleted,
    NextStepRequested,
    OutlineItem,
    PlanStep,
    ToolSpec,
    TurnRecord,
)

logger = logging.getLogger(__name__)

# Câu *"Giáo viên vừa chọn "Khác" thì hỏi lại bằng một câu mở"* ở dưới không còn bao giờ bắn: từ
# 13/10/2026 lối "Khác" mở ô cho giáo viên ghi, và câu họ ghi -- không phải chữ "Khác" -- tới đây.
# Nó **được giữ nguyên văn** vì đo ra prompt nhạy theo đúng chỗ ấy (`unbiased-model-text`, sau T5):
# bỏ nó thì *"kiểm tra nhanh phần logarit"* → *"lớp 11, 10 câu"* tụt 23 → 6/24 (run-93, run-92),
# thay bằng một câu đúng với hành vi mới (*"Giáo viên ghi câu trả lời của riêng họ thì dùng đúng câu
# ấy"*) thì 0/24 (run-94). Đổi câu này phải đo lại ca ấy.
_CORE = r"""Bạn là trợ lý Kriky, làm việc cùng giáo viên phổ thông Việt Nam.

Lượt này bạn đang ở PHA LÊN PLAN. Bạn tra cứu, hỏi lại, và khi đã đủ dữ kiện thì nêu một plan —
danh sách những việc sẽ làm. Hệ thống chạy plan ấy ở pha sau, rồi hỏi bạn kể lại kết quả.

Mỗi lượt bạn chọn ĐÚNG MỘT trong năm việc:
- say: trả lời bằng lời. Dùng khi câu vừa rồi chỉ cần một câu trả lời, không cần làm gì.
- call_tool: nhờ hệ thống chạy một tool TRA CỨU trong danh sách "tool dùng ngay", rồi bạn sẽ được
  hỏi lại với kết quả. Dùng khi bạn cần dữ liệu mà mình chưa có.
- ask_clarify: hỏi lại giáo viên. CHỈ dùng khi thiếu một tham số BẮT BUỘC của tool bạn sắp nêu,
  hoặc khi câu vừa rồi có thể hiểu theo nhiều cách. Một câu hỏi dạng CÓ/KHÔNG — "bạn có muốn…",
  "bạn có cần…", "mình đặt tên nhé?" — KHÔNG BAO GIỜ là ask_clarify: nó không lấp một chỗ trống
  nào, nó chỉ bắt giáo viên gõ thêm một lượt. Nếu bạn định hỏi một câu mà câu trả lời "tuỳ bạn"
  cũng xong việc, thì đừng hỏi, cứ làm. Hỏi thì kèm ít nhất 3 lựa chọn trong choices; hệ thống tự
  thêm "Khác". Giáo viên vừa chọn "Khác" thì hỏi lại bằng một câu mở.
- plan: nêu các việc sẽ làm, mỗi việc một tool trong danh sách "tool nêu được trong plan". text là
  câu bạn nói với giáo viên trước khi bắt tay, ví dụ "Được, mình soạn đề ngay."
- outline: đề xuất DÀN Ý đề cho giáo viên duyệt, TRƯỚC khi soạn câu hỏi. Mỗi mục trong outline:
  questions (mục phủ bao nhiêu câu), knowledge (kiến thức câu kiểm, viết lại gọn và sạch), formulas
  (công thức sẽ dùng, mỗi công thức một cặp $), approach (dạng câu và các bước giải), source_nodes
  (số node của bài nguồn; rỗng khi không có tài liệu). Hai câu chung một mục thì cùng kiến thức,
  khác cách hỏi. Mỗi lần tối đa 10 câu. text là một câu mở đầu ngắn; hệ thống tự in dàn ý và hỏi
  giáo viên có đồng ý không. tool_args: for = new (đề mới) hoặc more (soạn thêm cho đề đang có).

Về plan:
- Các bước chạy TUẦN TỰ và một bước hỏng thì DỪNG cả plan. Vì thế plan phải đủ: khi xong, việc
  giáo viên nhờ phải XONG trọn, không dừng ở nửa đường.
- title của mỗi bước là câu tiếng Việt giáo viên đọc trên màn hình, nói VIỆC chứ không
  nói tên tool: "Tạo đề trống", "Soạn <số câu> câu hỏi".
- Một tham số lấy giá trị từ kết quả của bước trước thì viết là {k.ten_field}, với k là số thứ tự
  bước, đếm từ 1. Ví dụ bước 2 cần id của đề mà bước 1 vừa mở: assessment_id = {1.assessment_id}.
  Chỉ viết đúng khuôn đó, không thêm chữ nào quanh nó, và chỉ trỏ về một bước ĐỨNG TRƯỚC nó.
- Một plan là một lời hứa, nên đừng nêu plan khi còn thiếu một mục bắt buộc — hỏi trước. Sau khi
  plan đã nêu thì KHÔNG còn chỗ nào để hỏi lại nữa.
- Plan soạn câu hỏi (start_drafting) chỉ nêu SAU KHI giáo viên đã đồng ý một dàn ý ở lượt trước;
  số câu là tổng của dàn ý ấy. Giáo viên muốn đổi gì trong dàn ý thì nêu lại outline ĐỦ mọi mục,
  chỉ sửa đúng chỗ họ nói.
- TUYỆT ĐỐI không nêu một tool tra cứu trong plan, và không gọi call_tool với một tool chỉ nêu
  được trong plan. Hai danh sách là hai quyền khác nhau.

Bốn điều không thương lượng:
- Bạn KHÔNG tự làm gì cả. call_tool là một lời đề nghị; hệ thống mới là người chạy. Vì thế TUYỆT ĐỐI
  không nói rằng bạn đã tạo, đã sửa, đã phát hành, đã lưu — chừng nào kết quả tool chưa nói vậy.
- ask_clarify chỉ để hỏi THÔNG TIN còn thiếu, trước một việc còn sửa lại được. TUYỆT ĐỐI không dùng
  nó để xin phép một việc không thu hồi được. Phát hành đề, xoá dữ liệu, đặt lại mật khẩu — những
  việc đó đi qua biểu mẫu riêng và hộp xác nhận, không bao giờ qua khung chat. Câu "phát hành cho
  lớp nào?" cũng vậy: đừng đưa lựa chọn, hãy nói rằng việc phát hành làm ở biểu mẫu phát hành.
- Khi việc phải chọn là quyết định sư phạm — chọn nguồn câu hỏi, chọn độ khó — bạn đưa thông tin và
  KHÔNG đánh dấu phương án nào là nên chọn. Giáo viên có thẩm quyền đó.
- Không đoán khi một cái tên có thể trỏ tới nhiều thứ. Hỏi lại; hỏi về một tên -- lớp, tài liệu,
  mục -- thì chỉ đưa những lựa chọn có trong dữ liệu bạn được cấp. Không bịa tên lớp, tên đề hay
  con số nào về dữ liệu.

Hai việc bạn KHÔNG làm được, và không có tool nào cho chúng: duyệt đề, và phát hành đề. Giáo viên tự
làm ở panel bên phải. Nếu họ nhờ bạn duyệt hay phát hành, hãy nói rằng chỗ làm việc đó là panel và
biểu mẫu phát hành — đừng hứa, và đừng nói là đã làm.

Cách viết:
- Tiếng Việt, gọn, như nói với đồng nghiệp. Tự gọi mình là "mình", gọi giáo viên là "bạn".
- KHÔNG dùng Markdown: không **in đậm**, không *nghiêng*, không `mã`, không bảng.
- Toán viết trong cặp `$`, mỗi biểu thức một cặp: `$\frac{a}{b}$`, `$x^{2}$`,
  `$\sqrt{x}$`, `$a \le b$`.
  Màn hình dựng hình phần nằm giữa hai dấu `$`. Chữ thường thì viết thường, **đừng** bọc
  cả câu trong `$`. Và đừng dùng dấu ngoặc kiểu \( \) hay \[ \] — chỉ `$`."""


# Thủ tục soạn theo sách, chỉ chèn ở lượt **có** sách (`unbiased-model-text`). Nằm trong skill
# `soan-de` thì mọi lượt soạn đề đều đọc thấy chữ "tài liệu", và gpt-4o-mini hỏi lại "bạn có tài
# liệu nào không" ở khoảng 7/108 lượt không có sách (run-13) -- dù skill có dòng dặn đừng hỏi. Thứ
# không nhìn thấy thì không hỏi được, cùng cách `catalog_for` giấu `list_chapters` khi lượt không có
# sách.
#
# Câu chữ là bản đã đo ở run-15; từ ADR-29 (`draft-outline`) đầu thủ tục nói *"nêu dàn ý"* thay
# *"nêu plan"*, bước 4 đọc chữ bằng `read_section` và câu *"rải đều theo độ dài"* thôi tồn tại --
# chưa đo, phải đo lại các ca sách trước khi đóng plan.
#
# Review T2 thử hai chỗ, cả hai làm `tai-lieu-khop-chuong` tụt từ 5/6
# xuống 0–1/6 (run-16, run-17) -- model hỏi *"cả chương hay một phần?"* cho một chương khớp đúng:
# nói thẳng *"đủ bốn mục vẫn CHƯA nêu plan"* (để thắng câu *"nêu plan ngay"* của skill), rồi chỉ
# đổi đầu thành *"Mở đề mới…"* kèm luật nối mục bằng `;`. Mô tả `topic_scope` riêng cho lượt có sách
# cũng thử rồi bỏ (comment trên `teacher_tools._with_document`), nên luật nối mục bằng `;` không còn
# nằm trong chữ nào model đọc: model bỏ `nodes` thì `bind_book` chỉ đỡ được khi `topic_scope` trùng
# đúng một tên mục, hay các tên mục nối bằng `;`.
_BOOK_PROCEDURE = """Soạn đề theo tài liệu -- lượt này có tài liệu, nên TRƯỚC khi nêu dàn ý:
1. call_tool list_chapters — document_id. Cần bài hay mục bên trong một chương thì
   call_tool get_chapter — document_id, node. document_id đã có ở dòng tài liệu đính kèm thì
   không gọi list_documents. Kết quả list_documents có nhiều tài liệu cùng hợp → ask_clarify
   hỏi tài liệu nào.
2. Khớp phạm vi giáo viên nói với các node vừa đọc. Không khớp, hay khớp nhiều cách →
   ask_clarify, choices chép đúng label của các mục có thể hợp. Giáo viên muốn
   cả cuốn thì chọn mọi chương.
3. Môn và khối suy được từ tên tài liệu thì dùng luôn -- trong known, chữ trích của chúng là
   tên tài liệu. topic_scope là label của mục nói về đúng điều giáo viên nói --
   mục KHỚP lời giáo viên, không phải một mục khác thay vào; không label nào trong kết quả tool
   nói về điều ấy thì topic_scope=?.
4. Đọc phạm vi: call_tool read_section — document_id, nodes (các node đã chọn), questions (số
   câu giáo viên xin), part 1; rồi part 2, 3, … tới khi more là false. Viết dàn ý từ chữ đã
   đọc, source_nodes lấy từ nodes của các phần đọc. Chữ đọc từ ảnh quét nên công thức và hình
   không có: công thức trong dàn ý là bạn tự viết.
5. Giáo viên đồng ý dàn ý → plan như quy trình soạn đề, create_draft thêm document_id và nodes
   (các số node đã chọn)."""

# Mở thư viện khi giáo viên nhắc sách mà **không** đính kèm (`unbiased-model-text` T2b). Chỉ đúng ở
# lượt không có sách, mà chỉ có tác dụng khi đứng **giữa** các nhánh quyết định của `soan-de` -- nên
# skill để một chỗ trống, `_compose` điền hay xoá theo lượt. Đo:
# - dòng cố định trong skill: nó thắng cả lượt **có** chip -- `tai-lieu-chua-doc` 24 lần, bản đã
#   commit 22/24, bản có `known` 10/24: model gọi `list_documents` dù `document_id` ở ngay dòng
#   đính kèm;
# - một đoạn riêng sau skill: lượt có chip 6/6, nhưng `tai-lieu-khong-dinh` (nhắc sách, không chip)
#   0/6 -- model ghi khối bịa vào `known` rồi nêu plan, như thể không đọc thấy đoạn ấy;
# - sau nhánh *còn ? → hỏi lại* (T3): khi model thôi bịa khối thì nhánh hỏi lại thắng --
#   `tai-lieu-khong-dinh` 11--14/24, hỏi khối rồi soạn đề không sách. Đứng **trước** nhánh ấy thì
#   nó thắng, nhưng đứng đầu ở mọi lượt soạn đề thì model gọi `list_documents` cả khi giáo viên
#   không nhắc sách (run-26: 0/6 ở mọi ca đủ mục). Nên dòng này chỉ được điền khi chính câu của
#   giáo viên nhắc tới sách hay tệp (`_BOOK_WORDS`). Từ T5, chữ không còn quyết một mình: lượt có
#   dòng này mà model hỏi lại hay soạn đề không sách thì `_library_first` gọi `list_documents`.
_LIBRARY_SLOT = re.compile(r"^([ \t]*)\{thư viện\}[ \t]*\n?", re.MULTILINE)
_LIBRARY = (
    "- giáo viên nhắc tới một cuốn sách hay tệp đã tải lên để soạn theo mà không đính kèm → "
    "call_tool list_documents TRƯỚC, kể cả khi còn ? -- khối, môn có thể đọc ra từ tên tài liệu;"
)
# Chữ cho biết giáo viên đang nói về một tài liệu. *"Danh sách"* bị bỏ trước khi tìm: *"danh sách
# lớp"* không phải một cuốn sách.
_BOOK_WORDS = re.compile(
    r"\b(sách|tài liệu|tệp|file|giáo trình|giáo án|đề cương|bài giảng|cuốn|quyển|pdf|docx|"
    r"slide|sgk)\b",
    re.IGNORECASE,
)
_NOT_A_BOOK = re.compile(r"danh\s+sách", re.IGNORECASE)


def _mentions_book(request: NextStepRequested) -> bool:
    """Giáo viên có nhắc tới một tài liệu, kể từ plan gần nhất, không.

    Mọi câu của giáo viên từ plan gần nhất, không chỉ câu cuối (review T3, `unbiased-model-text`):
    nhắc sách ở lượt này rồi trả lời *"lớp 8"* ở lượt sau thì việc soạn đề vẫn là việc soạn theo
    sách. Plan đã nêu thì việc ấy xong -- một đề mới không nhắc sách là đề không sách.

    Args:
        request: Lượt đang hỏi.

    Returns:
        True khi một câu ấy có một chữ trong `_BOOK_WORDS`, không tính *"danh sách"*.
    """
    for turn in reversed(request.history):
        if turn.kind == "plan":
            return False
        if turn.kind != "teacher":
            continue
        # NFC trước khi tìm: macOS gửi chữ có dấu dạng phân rã, "sách" phân rã không khớp (ADR-23).
        said = _NOT_A_BOOK.sub(" ", unicodedata.normalize("NFC", turn.text))
        if _BOOK_WORDS.search(said):
            return True
    return False


# Tool đọc tài liệu; kết quả của một trong số chúng trong lịch sử là *đoạn chat đang chọn sách*.
# Cùng bộ với `teacher_chat._DOCUMENT_READS` bên BE.
_DOCUMENT_READS = frozenset({"list_documents", "list_chapters", "get_chapter", "read_section"})


def _book_in_view(request: NextStepRequested) -> bool:
    """Lượt này có một cuốn sách để soạn theo không -- tức `_BOOK_PROCEDURE` có được chèn không.

    Đọc **sự kiện**, không đọc catalog (review T2, `unbiased-model-text`). BE mở tool mục lục cho
    mọi lượt sau khi đoạn chat từng đọc tài liệu (`teacher_chat._read_documents_before`), nên
    *"`list_chapters` có trong catalog"* đúng cả ở một lượt soạn đề không dính gì tới sách -- và thủ
    tục sẽ bắt model đọc mục lục, hay bịa `document_id`.

    Có sách khi: chip sẵn sàng; hoặc, không có chip, lịch sử có kết quả của một tool đọc tài liệu
    mà **chưa** có plan nào nêu sau nó -- việc chọn sách còn dở (hỏi lại chương nào, giáo viên trả
    lời ở lượt sau). Plan đã nêu thì việc ấy đã xong; một đề mới không nhắc sách là đề không sách,
    còn giáo viên nhắc sách thì skill `soan-de` mở thư viện lại. Chip chưa sẵn sàng thì không: chưa
    có mục lục, và dòng báo chip đã dặn đừng soạn.

    Args:
        request: Lượt đang hỏi.

    Returns:
        True khi thủ tục sách áp dụng cho lượt này.
    """
    if request.attached_document is not None:
        return request.attached_document.state == "ready"
    for turn in reversed(request.history):
        if turn.kind == "plan":
            return False
        if turn.kind == "tool_result" and turn.tool_name in _DOCUMENT_READS:
            return True
    return False


def _opens_library(request: NextStepRequested, chosen: tuple[str, ...]) -> bool:
    """Lượt này có dòng mở thư viện (`_LIBRARY`) không. Hàm thuần.

    Không chip, chưa đọc sách: lượt duy nhất mà mở thư viện là một bước có nghĩa. Chip chưa sẵn
    sàng thì không -- dòng báo chip đã dặn đừng soạn. Và chỉ khi một skill được chọn có chỗ trống
    cho dòng ấy, tức đang soạn đề.

    Args:
        request: Lượt đang hỏi.
        chosen: Tên các skill Jev chọn cho lượt này.

    Returns:
        True khi `_compose` điền `_LIBRARY` vào chỗ trống.
    """
    return (
        request.attached_document is None
        and not _book_in_view(request)
        and any(tool.name == "list_documents" for tool in request.catalog)
        and _mentions_book(request)
        and any(_LIBRARY_SLOT.search(skill.body) for skill in skills.named(chosen))
    )


def _read_before_outline(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Ở lượt có sách, một dàn ý nêu khi chưa đọc chữ phạm vi thành lời gọi `read_section`.

    Hàm thuần.

    `_BOOK_PROCEDURE` dặn đọc trước khi nêu dàn ý, và chữ không giữ được model (review đợt 4,
    `draft-outline`): nó chép `source_nodes` từ mục lục, BE nhận vì nút có thật, và dàn ý viết từ
    tóm tắt chứ không từ bài. Phạm vi đọc là chính các nút dàn ý trỏ tới, số câu là tổng của dàn
    ý -- model nêu lại với chữ trong tay. Đã đọc từ plan gần nhất thì để nguyên.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        `call_tool read_section` khi lượt có sách mà chưa đọc chữ; không thì `step`.
    """
    if step.kind != "outline" or not _book_in_view(request):
        return step
    since = _since_plan(request)
    if any(turn.kind == "tool_result" and turn.tool_name == "read_section" for turn in since):
        return step
    nodes = sorted({node for item in step.outline for node in item.source_nodes})
    attached = request.attached_document
    document = attached.document_id if attached is not None else ""
    if not document:
        reads = [
            str(turn.tool_args.get("document_id") or "")
            for turn in since
            if turn.kind == "tool_call" and turn.tool_name in _DOCUMENT_READS
        ]
        document = next((one for one in reversed(reads) if one), "")
    if not nodes or not document:
        return step
    total = min(10, sum(item.questions for item in step.outline))
    logger.info("model outlined before reading -- reading %s first", nodes)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name="read_section",
        tool_args={
            "document_id": document,
            "nodes": ",".join(str(node) for node in nodes),
            "questions": str(total),
            "part": "1",
        },
        model_tokens=step.model_tokens,
    )


def _library_first(
    step: NextStepCompleted, request: NextStepRequested, chosen: tuple[str, ...]
) -> NextStepCompleted:
    """Ở lượt có dòng mở thư viện, một câu hỏi lại hay một đề mở không tài liệu thành lời gọi
    `list_documents`. Hàm thuần.

    Dòng ấy dặn đúng điều này, và chữ không giữ được nó (`unbiased-model-text` T5): nhánh *"còn ? →
    hỏi lại"* thắng mỗi khi model suy được thêm một mục -- *"cụm suy ra môn vẫn là phạm vi"* chữa
    *"kiểm tra nhanh phần logarit"* (5 → 24/24) mà kéo `tai-lieu-khong-dinh` 24 → 16/24, model hỏi
    khối thay vì mở thư viện nơi khối nằm sẵn trong tên tài liệu.

    Chỉ hai hình dạng ấy (review T5): `_BOOK_WORDS` có lúc báo nhầm -- *"soạn thêm 5 câu, bám sát
    sách giáo khoa"* là plan `start_drafting` hợp lệ, *"xuất file Word"* không nhờ soạn theo sách --
    nên lời nói (`say`), plan không mở đề mới, và mọi lời gọi tool (`list_class`…) để nguyên.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.
        chosen: Tên các skill Jev chọn cho lượt này.

    Returns:
        `call_tool list_documents` khi lượt mở thư viện mà `step` là `ask_clarify`, hay plan có
        `create_draft` không `document_id`; không thì `step`.
    """
    unbooked = step.kind == "plan" and any(
        one.tool_name == "create_draft" and not str(one.args.get("document_id") or "").strip()
        for one in step.steps
    )
    # Từ ADR-29 nước đi đầu là dàn ý, không phải plan: một dàn ý không trỏ về bài nào ở lượt mở thư
    # viện là dàn ý soạn không sách -- cùng lỗi, hình dạng mới (review đợt 4, `draft-outline`).
    unbooked = unbooked or (
        step.kind == "outline" and not any(item.source_nodes for item in step.outline)
    )
    if not (step.kind == "ask_clarify" or unbooked) or not _opens_library(request, chosen):
        return step
    logger.info("model chose %s on a turn that opens the library -- listing first", step.kind)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name="list_documents",
        model_tokens=step.model_tokens,
    )


class _AskAgain(ValueError):
    """Một đề nghị hỏng theo kiểu hỏi lại model một lần thường là sửa được."""


class _NothingToSay(_AskAgain):
    """Model chọn `say` hay `ask_clarify` mà để `text` rỗng."""


class _Flawed(_AskAgain):
    """Một đề nghị dùng được nhưng thiếu một thứ: mang nó theo, để lần hỏi lại hỏng thì còn nó.

    Lưới hỏi lại không bao giờ được làm kết quả tệ hơn khi chưa có nó (review T2b,
    `unbiased-model-text`): lần hai hỏng kiểu khác -- im lặng, provider lỗi -- thì giữ đề nghị lần
    đầu. Lần hai cũng thiếu thì giữ lần hai cho plan, vì cả hai đều tới BE và BE tự xét; với câu hỏi
    thì giữ lần có nhiều lựa chọn hơn (review T3: lần hai có thể còn ít hơn lần đầu).
    """

    def __init__(self, flaw: str, step: NextStepCompleted) -> None:
        super().__init__(flaw)
        self.step = step


class _IncompletePlan(_Flawed):
    """Model nêu plan mà một bước thiếu tham số bắt buộc của tool ấy.

    Đo được khi `soan-de` bắt ghi giá trị bốn mục vào `known` (`unbiased-model-text` T2b): hỏi thừa
    giảm từ 80/192 xuống 1/192, nhưng ~11/192 plan nêu `create_draft` không kèm tham số nào -- giá
    trị đã nằm ở `known`, model không chép sang. BE `vet_plan` từ chối đúng những plan ấy, và giáo
    viên nhận một lời từ chối cho một câu đã đủ ý. Hỏi lại ở đây rẻ hơn.
    """


class _NoOutline(_AskAgain):
    """Model chọn `outline` mà không nêu mục nào, hay một mục không đọc được (`draft-outline`)."""


class _FewChoices(_Flawed):
    """Model hỏi lại mà đưa ít lựa chọn hơn mức người dùng chốt (`unbiased-model-text` T3: ít nhất
    3)."""


def _answers(choices: tuple[str, ...], question: str) -> tuple[str, ...]:
    """Những lựa chọn thật sự là một câu trả lời để bấm, gộp trùng.

    Ba thứ trông như lựa chọn mà không phải, đều đo được ở ca thiếu cả bốn mục
    (`unbiased-model-text` T3):

    - kết bằng "?" -- một câu hỏi (*"Môn học là gì?"*, run-41);
    - không chữ số nào và nằm nguyên trong chính câu hỏi -- tên một mục mà câu hỏi vừa kể
      (*"Môn học"*, *"Khối lớp"* cho câu *"cho mình biết môn học, khối lớp…"*: 15/30 lượt, run-52 và
      run-53). Có chữ số thì giữ: *"12A"*, *"15 câu"* là giá trị, dù câu hỏi có nhắc tới chúng;
    - "Khác" -- hệ thống tự có lối ấy (FE vẽ "Khác…" để giáo viên tự ghi), nên model viết nó không
      làm đủ ba (review T3: 58/158 câu hỏi có nó).

    Args:
        choices: `choices` model trả về.
        question: `text` của câu hỏi.

    Returns:
        Các lựa chọn còn lại, theo thứ tự, không trùng.
    """
    asked = " ".join(question.casefold().split())
    kept: dict[str, str] = {}
    for one in choices:
        text = one.strip()
        folded = " ".join(text.casefold().split())
        if not text or text.endswith("?") or folded == _OTHER.casefold():
            continue
        if not any(char.isdigit() for char in text) and folded in asked:
            continue
        kept.setdefault(folded, text)
    return tuple(kept.values())


# [CODE CHẾT 2026-10-13] "Khác" thôi là một nút gửi đi chữ "Khác": FE mở ô để giáo viên ghi rõ, và
# câu họ ghi mới tới AGENT (người dùng chốt). Lối ấy không còn gửi chữ "Khác"; giáo viên tự gõ đúng
# chữ ấy thì chỉ tốn một lần hỏi lại model (`_FewChoices`).
# def _after_other(request: NextStepRequested) -> bool:
#     """Câu mới nhất của giáo viên là nút "Khác". Hàm thuần.
#
#     Args:
#         request: Lượt đang hỏi.
#
#     Returns:
#         True khi giáo viên vừa nói không lựa chọn nào đúng.
#     """
#     said = next((turn.text for turn in reversed(request.history) if turn.kind == "teacher"), "")
#     return said.strip().casefold() == _OTHER.casefold()


def _choices_wanted(request: NextStepRequested) -> int:
    """Một câu hỏi lại lượt này cần ít nhất bao nhiêu lựa chọn.

    Ba, theo luật người dùng chốt -- trừ khi số ba không đúng:

    - Kết quả tool gần nhất có `candidates` ít hơn ba dòng: câu hỏi về một dòng thì chỉ có bấy nhiêu
      lựa chọn **thật**, và đòi ba là mời model bịa dòng thứ ba. Gần nhất tính từ plan gần nhất,
      **qua** các câu của giáo viên (review T3, `unbiased-model-text`): câu hỏi về hai lớp kéo sang
      lượt sau khi giáo viên gõ một tên khác, và lượt ấy không gọi lại tool -- đòi ba ở đó là ép
      model bịa lớp.

    Args:
        request: Lượt đang hỏi.

    Returns:
        Số lựa chọn tối thiểu, có thể là 0.
    """
    # [CODE CHẾT 2026-10-13] Lối "Khác" không còn gửi chữ "Khác" (xem `_after_other`).
    # if _after_other(request):
    #     return 0
    for turn in reversed(request.history):
        if turn.kind == "plan":
            break
        if turn.kind == "tool_result":
            listed = turn.tool_result.get("candidates")
            if isinstance(listed, list):
                return min(3, len(listed))
    return 3


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


# Ký tự điều khiển, trừ tab và xuống dòng. Tham số plan không đi qua `_unmangled` -- chúng là giá
# trị, không phải chữ để dựng toán -- nên một ký tự như vậy là chữ hỏng, không phải LaTeX bị nuốt.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _reads_first(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Plan mở đầu bằng một tool chỉ gọi được ngay -- không nêu được trong plan -- là lời gọi tool
    ấy, chưa phải plan. Hàm thuần.

    Đo ở `unbiased-model-text` T5: giáo viên nhắc sách mà không đính kèm và nói đủ bốn mục (*"Lấy
    cuốn Toán 10 mình mới tải lên, ra 8 câu phần mệnh đề"*) thì nhánh *"không còn ? → nêu plan
    ngay"* thắng dòng mở thư viện: 16/24 lượt model nêu plan `list_documents → create_draft →
    start_drafting` -- biết phải mở thư viện, chỉ chọn sai `kind` -- và BE từ chối cả plan
    (`list_documents` không có trong catalog pha thực hiện), giáo viên nhận câu lùi. Bản đã commit
    12/24 gọi tool, bản hiện tại trước luật này 4/24. Đổi chữ đã thua nhiều lần ở chính chỗ này
    (T2b, T3); đây là cấu trúc. Các bước sau bị bỏ: ở bước kế trong cùng vòng gọi tool của BE, model
    đọc kết quả rồi nêu lại plan.

    Args:
        step: Đề nghị model vừa nêu.
        request: Request lượt này, mang hai danh sách tool.

    Returns:
        `call_tool` cho bước đầu khi bước ấy là tool `catalog` mà không phải tool `plannable`, và
        chưa được gọi với đúng tham số ấy từ plan gần nhất (review T5: không thì BE hỏi lại tới trần
        `max_tool_steps` rồi báo lỗi); không thì chính `step`.
    """
    if step.kind != "plan":
        return step
    first = step.steps[0]
    callable_now = {tool.name for tool in request.catalog}
    plannable = {tool.name for tool in request.plannable}
    if first.tool_name not in callable_now or first.tool_name in plannable:
        return step
    if _called_since_plan(request, first.tool_name, first.args):
        return step
    logger.info("plan opens with %s, a read -- calling it first", first.tool_name)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name=first.tool_name,
        tool_args=dict(first.args),
        model_tokens=step.model_tokens,
    )


def _since_plan(request: NextStepRequested) -> list[TurnRecord]:
    """Các lượt từ sau plan gần nhất, cũ nhất trước. Hàm thuần."""
    turns: list[TurnRecord] = []
    for turn in reversed(request.history):
        if turn.kind == "plan":
            break
        turns.append(turn)
    return turns[::-1]


def _called_since_plan(request: NextStepRequested, tool: str, args: dict[str, object]) -> bool:
    """`tool` đã được gọi với đúng `args` (so bằng chữ) từ plan gần nhất chưa. Hàm thuần."""
    wanted = {key: str(value) for key, value in args.items()}
    return any(
        turn.kind == "tool_call"
        and turn.tool_name == tool
        and {key: str(value) for key, value in turn.tool_args.items()} == wanted
        for turn in _since_plan(request)
    )


def _tables_read(request: NextStepRequested) -> set[str]:
    """`document_id` của các tài liệu đã đọc mục lục (`list_chapters`, `get_chapter`) từ plan gần
    nhất. Đọc lượt `tool_call`: lượt `tool_result` không chở tham số. Một lời gọi trả lỗi
    (`document_id` bịa) vẫn tính -- gọi lại cũng ra đúng lỗi ấy. Hàm thuần."""
    return {
        str(turn.tool_args.get("document_id") or "").strip()
        for turn in _since_plan(request)
        if turn.kind == "tool_call" and turn.tool_name in {"list_chapters", "get_chapter"}
    }


def _toc_first(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Plan tạo đề theo một tài liệu chưa đọc mục lục là lời gọi `list_chapters` của tài liệu ấy.
    Hàm thuần.

    Đo ở `unbiased-model-text` T5: không chip, giáo viên nhắc sách -- `list_documents`, hỏi *"cuốn
    này chứ?"*, giáo viên bấm tên cuốn -- rồi model nêu `create_draft` với `document_id` mà không
    đọc mục lục bao giờ. Thiếu `nodes` thì BE dừng ở bước 1; có `nodes` thì đó là số **bịa**
    (*"1,2,3"*, *"5"*: 4/24 lượt, run-87) mà BE nhận -- không chip thì `nodes` tuỳ chọn,
    `_document_scope` chỉ kiểm nút có trong cây -- và đề soạn trên mục sai. Điều kiện vì thế là
    *chưa đọc mục lục*, không phải *thiếu `nodes`* (review T5); đọc rồi thì không gọi lại, plan đi
    tiếp cho BE xét. Chỉ lượt không chip: có chip thì thủ tục sách đọc mục lục từ trước, và
    `bind_book` điền `nodes`.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        `call_tool list_chapters` cho tài liệu của `create_draft` khi mục lục của nó chưa được đọc
        từ plan gần nhất và `list_chapters` gọi được lượt này; không thì chính `step`.
    """
    if step.kind != "plan" or request.attached_document is not None:
        return step
    if not any(tool.name == "list_chapters" for tool in request.catalog):
        return step
    read = _tables_read(request)
    for one in step.steps:
        if one.tool_name != "create_draft":
            continue
        document = str(one.args.get("document_id") or "").strip()
        # `{1.document_id}` là tham chiếu tới kết quả một bước trước (ADR-25), chưa phải một id.
        if document and not document.startswith("{") and document not in read:
            logger.info("plan drafts from %s before reading its chapters -- reading them", document)
            return NextStepCompleted(
                request_id=step.request_id,
                kind="call_tool",
                tool_name="list_chapters",
                tool_args={"document_id": document},
                model_tokens=step.model_tokens,
            )
    return step


def _listed_documents(request: NextStepRequested) -> list[dict] | None:
    """`candidates` của `list_documents` gần nhất từ plan gần nhất, khi sau nó **chưa** đọc mục
    lục nào; `None` khi không có hay đã đọc. Hàm thuần."""
    for turn in reversed(_since_plan(request)):
        if turn.kind == "tool_result" and turn.tool_name in {"list_chapters", "get_chapter"}:
            return None
        if turn.kind == "tool_result" and turn.tool_name == "list_documents":
            listed = turn.tool_result.get("candidates")
            if not isinstance(listed, list):
                return []
            return [one for one in listed if isinstance(one, dict)]
    return None


def _picked_document(request: NextStepRequested) -> str:
    """`document_id` của tài liệu giáo viên vừa chọn: câu mới nhất của họ, đến **sau** kết quả
    `list_documents`, trùng đúng một `label` trong đó (nút BE bày gửi đúng chữ ấy). Rỗng khi
    không. Hàm thuần."""
    listed = _listed_documents(request)
    if not listed:
        return ""
    turns = _since_plan(request)
    answered = next(
        (turn for turn in reversed(turns) if turn.kind in {"teacher", "tool_result"}), None
    )
    if answered is None or answered.kind != "teacher":
        return ""
    said = _nfc(answered.text).strip().casefold()
    matched = [
        str(one.get("document_id") or "")
        for one in listed
        if _nfc(str(one.get("label") or "")).strip().casefold() == said
    ]
    return matched[0] if len(matched) == 1 and matched[0] else ""


def _picked_book_first(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Giáo viên vừa chọn một tài liệu trong danh sách: đọc mục lục của nó, bằng code. Hàm thuần.

    Đo ở `unbiased-model-text` T5: sau khi giáo viên bấm tên cuốn, model tự gọi `list_chapters` 0/24
    lượt (run-87; 20/24 lượt đạt đều do `_toc_first`), còn lại nêu plan -- có lúc `nodes` bịa, có
    lúc không `document_id` (âm thầm soạn đề không sách). Giáo viên đã chọn, nên đây không phải chọn
    hộ; và không còn phụ thuộc model ở đúng bước model hỏng (review T5, hướng iii).

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        `call_tool list_chapters` cho tài liệu vừa chọn khi mục lục của nó chưa đọc và `step` chưa
        tự đọc nó; không thì chính `step`.
    """
    if request.attached_document is not None:
        return step
    if not any(tool.name == "list_chapters" for tool in request.catalog):
        return step
    picked = _picked_document(request)
    if not picked or picked in _tables_read(request):
        return step
    if (
        step.kind == "call_tool"
        and step.tool_name in {"list_chapters", "get_chapter"}
        and str(step.tool_args.get("document_id") or "").strip() == picked
    ):
        return step
    logger.info("teacher picked %s -- reading its chapters", picked)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name="list_chapters",
        tool_args={"document_id": picked},
        model_tokens=step.model_tokens,
    )


def _misfiled_read(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Câu hỏi lại ngay sau `list_documents` mà mang `list_chapters` của một tài liệu trong danh
    sách là lời gọi ấy, nộp nhầm `kind`. Hàm thuần.

    Đo ở `unbiased-model-text` T5 (run-88): ngay sau `list_documents`, 16/24 lượt model chọn
    `ask_clarify` mà điền `tool_name=list_chapters` với `document_id` của một tài liệu trong danh
    sách (15 lượt là cuốn Lớp 10 giáo viên nhắc) -- nó đã chọn sách, chỉ chọn sai `kind`. Bản đã
    commit tự gọi `list_chapters` 17/24: đây là trả lại đúng lựa chọn của model, không phải code
    chọn hộ. Hẹp có chủ ý: câu hỏi về khối mang `tool_name=list_class` (`thieu-khoi-co-so-cau`, 9
    lượt đúng) và câu hỏi chương mang `list_chapters` **sau** khi đã đọc mục lục
    (`tai-lieu-khong-khop`, 36 lượt đúng) là câu hỏi thật.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        `call_tool list_chapters` khi điều kiện trên đúng và tài liệu ấy chưa đọc mục lục; không thì
        chính `step`.
    """
    if step.kind != "ask_clarify" or step.tool_name != "list_chapters":
        return step
    if request.attached_document is not None:
        return step
    if not any(tool.name == "list_chapters" for tool in request.catalog):
        return step
    listed = _listed_documents(request) or []
    document = str(step.tool_args.get("document_id") or "").strip()
    if not document or document not in {str(one.get("document_id") or "") for one in listed}:
        return step
    if document in _tables_read(request):
        return step
    logger.info("question names list_chapters of %s -- calling it", document)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name="list_chapters",
        tool_args={"document_id": document},
        model_tokens=step.model_tokens,
    )


# Câu hỏi lại ngay sau `list_documents` (`unbiased-model-text` T5, review T5 hướng ii). Nút của câu
# ấy luôn là tên tài liệu -- BE coi câu hỏi đến sau một danh sách `candidates` là câu hỏi về dòng
# (ADR-23) -- mà chữ model viết lệch nút 5--17/24 lượt (*"phần mệnh đề nằm ở mục nào?"*, run-83,
# run-87).
_WHICH_BOOK = "Bạn soạn theo tài liệu nào?"


def _which_book(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Câu hỏi lại ngay sau một danh sách tài liệu hỏi đúng điều nút của nó trả lời. Hàm thuần.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        `step` với `text` là `_WHICH_BOOK` khi nó là `ask_clarify`, không chip, và lượt **ngay
        trước** nó là kết quả một `list_documents` có ít nhất một tài liệu -- chưa câu nào của giáo
        viên chen vào; không thì chính `step`. Review chung sau T5 (`unbiased-model-text`): bản đầu
        đè mọi câu hỏi cho tới khi đọc mục lục, kể cả sau khi giáo viên đã ghi *"thôi, không dùng
        sách"* qua lối "Khác" -- câu hỏi khối hay số câu thành câu hỏi tài liệu.
    """
    if step.kind != "ask_clarify" or request.attached_document is not None:
        return step
    if not _listed_documents(request):
        return step
    spoken = [turn for turn in _since_plan(request) if turn.kind in {"teacher", "tool_result"}]
    last = spoken[-1] if spoken else None
    if last is None or last.kind != "tool_result" or last.tool_name != "list_documents":
        return step
    return step.model_copy(update={"text": _WHICH_BOOK})


def _garbled(steps: tuple[PlanStep, ...]) -> str:
    """Bước đầu tiên có tham số mang ký tự điều khiển, gọi tên ra; rỗng khi không bước nào.

    Đo được ở `unbiased-model-text` T3: hai lượt trong ~1100 trả *"tỉ lệ th\\x13"*, *"tỉ lệ
    th\\x1c"* làm `topic_scope` (run-53, run-54; nguồn chưa rõ) -- chữ ấy thành tên đề giáo viên
    đọc. Hỏi lại model một lần như một plan thiếu tham số.

    Args:
        steps: Các bước model nêu.

    Returns:
        Một dòng cho log, hoặc chuỗi rỗng.
    """
    for index, step in enumerate(steps, start=1):
        for key, value in step.args.items():
            if _CONTROL.search(str(value)):
                return f"step {index} ({step.tool_name}) has a control character in {key}"
    return ""


def _lacking(steps: tuple[PlanStep, ...], request: NextStepRequested) -> str:
    """Bước đầu tiên thiếu một tham số bắt buộc, gọi tên ra; rỗng khi không bước nào thiếu.

    Luật của `vet_plan` bên BE -- tham số khai trong catalog, trừ `optional`, phải **có mặt** -- trừ
    đúng một chỗ BE tự lo: đoạn chat gắn một cuốn sách sẵn sàng thì `bind_book` điền `document_id`
    **trước** `vet_plan`, nên thiếu nó không phải lý do hỏi lại (review T2b, `unbiased-model-text`).
    `nodes` thì vẫn tính: `bind_book` chỉ điền nó khi `topic_scope` trùng đúng tên mục. Tool không
    có trong catalog thì để BE nói: đó là lời từ chối của nó.

    Args:
        steps: Các bước model nêu.
        request: Lượt đang hỏi -- catalog pha thực hiện, và chip của đoạn chat.

    Returns:
        Một dòng cho log, hoặc chuỗi rỗng.
    """
    attached = request.attached_document
    filled_by_be = {"document_id"} if attached is not None and attached.state == "ready" else set()
    specs = {spec.name: spec for spec in request.plannable}
    for index, step in enumerate(steps, start=1):
        spec = specs.get(step.tool_name)
        if spec is None:
            continue
        missing = set(spec.arguments) - set(step.args) - set(spec.optional) - filled_by_be
        if missing:
            return f"step {index} ({step.tool_name}) lacks {sorted(missing)}"
    return ""


# Câu nói khi model hai lần liền để trống lời. Trung tính có chủ ý: **không** lùi về mock của
# `handlers.next_step`, vì mock đoán việc bằng từ khoá và đoán sai đúng ca đo được -- *"ra đề Toán
# lớp 10 về mệnh đề"* thành câu hỏi *"bạn muốn xem lớp nào?"* (review A1). Một câu hỏi sai việc
# trông như hợp lệ và kéo cả đoạn chat lạc hướng; một câu nhờ nói lại thì không.
_UNCLEAR = "Mình chưa rõ ý bạn lắm. Bạn nói lại giúp mình nhé?"

# Chữ của lối "Khác" mà thẻ hỏi lại tự vẽ (FE, người dùng chốt 13/10/2026): model viết nó vào
# `choices` thì không phải một lựa chọn (`_answers`). Cùng chữ với `teacher_chat.OTHER_CHOICE` bên
# BE và `OTHER` trong `Chat.tsx` -- ba nơi không import nhau, một test giữ chúng khớp.
_OTHER = "Khác"


class _Argument(BaseModel):
    """Một argument của tool, dưới dạng một tên và một giá trị.

    Một cặp chứ không phải một mapping, vì mapping với key tuỳ ý là một JSON object
    mở và structured output ở chế độ strict từ chối những thứ đó. Giá trị là string:
    mọi argument các tool nhận hôm nay đều là string, và một union có kiểu ở đây sẽ
    là một nhánh schema mà model phải chọn giữa, chẳng được lợi gì.
    """

    model_config = ConfigDict(extra="forbid")

    param: str = Field(description="Tên tham số, viết đúng như trong danh sách tool.")
    value: str = Field(description="Giá trị của tham số.")


class _OutlineItem(BaseModel):
    """Một mục dàn ý đề (ADR-29, `draft-outline`), dưới hình dạng model trả lời được.

    Object đóng, như `_Step`: structured output chặt nhận một tuple object có field cố định.
    `contracts.OutlineItem` mới là hình dạng BE đọc, và `completed` dịch sang nó.
    """

    model_config = ConfigDict(extra="forbid")

    questions: int = Field(description="Mục này phủ bao nhiêu câu.")
    knowledge: str = Field(description="Kiến thức câu kiểm, viết lại sạch bằng lời của bạn.")
    formulas: tuple[str, ...] = Field(
        description="Công thức sẽ dùng, mỗi công thức một cặp $. Rỗng khi không có công thức."
    )
    approach: str = Field(description="Dạng câu và các bước giải dự kiến.")
    source_nodes: tuple[int, ...] = Field(
        description="Số node của bài nguồn, lấy từ nodes của read_section. Rỗng khi không có "
        "tài liệu."
    )


class _Step(BaseModel):
    """Một bước của plan, dưới hình dạng model trả lời được.

    Cùng lý do với `_Argument`: `args` là một dãy cặp tên–giá trị chứ không phải một mapping, vì
    một JSON object với key tuỳ ý bị structured output chế độ strict từ chối. `contracts.PlanStep`
    mới là hình dạng BE đọc, và `completed` dịch sang nó.
    """

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    args: tuple[_Argument, ...] = ()
    title: str


def _unmangled(proposal: "_Proposal") -> "_Proposal":
    r"""Trả lại dấu gạch chéo mà bộ giải mã JSON đã nuốt của lời model nói.

    **Chỗ thứ hai, cùng một hỏng hóc.** `authoring` không phải ống structured-output duy
    nhất: `_Proposal.text` cũng ra từ `with_structured_output`, cũng đi qua cùng bộ giải mã
    JSON, và cũng kết thúc trong `<MathText>` -- `Chat.tsx` dựng hình nó ở năm chỗ
    (`block.said`, `live.opening`, `live.report`, `said.opening`, `said.conclusion`).

    Nghĩa là Kriky giải thích một công thức trong khung chat thì `\frac` thành form-feed y
    hệt, rồi luật pandoc `\$(?![\s$])` từ chối nhận cả cụm là toán và dấu đô la lọt ra màn
    hình. Cùng nguyên nhân, cùng hậu quả, cùng người nhìn thấy (ADR-26).

    `title` của mỗi bước plan cũng đi qua: nó hiện trong khối bước ngay dưới câu Kriky nói.
    `tool_name` và `args` thì **không** -- chúng là identifier và giá trị, không phải chữ
    cho người đọc, và một dấu gạch chéo mọc thêm trong đó là một id hỏng.

    Args:
        proposal: Thứ model vừa trả lời, ngay sau khi qua bộ giải mã JSON.

    Returns:
        Một bản mới với mọi chữ dành cho người đọc đã dựng lại.
    """
    return proposal.model_copy(
        update={
            "text": restore_latex_escapes(proposal.text),
            "steps": tuple(
                step.model_copy(update={"title": restore_latex_escapes(step.title)})
                for step in proposal.steps
            ),
            # Mục dàn ý (`draft-outline`): BE in nguyên văn ba trường chữ ra chat, trong
            # `MathText`, và job soạn câu đọc đúng chúng -- `\frac` thành form-feed ở đây là
            # hỏng ở cả hai chỗ.
            "outline": tuple(
                item.model_copy(
                    update={
                        "knowledge": restore_latex_escapes(item.knowledge),
                        "approach": restore_latex_escapes(item.approach),
                        "formulas": tuple(restore_latex_escapes(one) for one in item.formulas),
                    }
                )
                for item in proposal.outline
            ),
        }
    )


class _Proposal(BaseModel):
    """Đúng những gì model được hỏi -- và không gì khác.

    Cố ý không phải `NextStepCompleted`. Type đó là hợp đồng giữa các service và mang
    hai field không model nào trả lời được: `request_id`, do BE phát ra, và
    `model_tokens`, do provider báo lại sau đó. Đưa cả hợp đồng cho
    `with_structured_output` đặt cả hai field ấy trước mặt model như hai câu hỏi, và
    biến `tool_args` -- một `dict[str, object]` -- thành một object mở mà OpenAI từ
    chối thẳng:

        400 Invalid schema for response_format: In context=('properties',
        'tool_args'), 'additionalProperties' is required to be supplied and to
        be false.

    Thế là mọi lần gọi thật đều thất bại rồi lùi về nội dung dọn trước, với độ trễ
    trông như thật và một câu trả lời nghe hợp lý che đi chuyện đó. Schema này là bản
    sửa và cũng là bài học: một field trong schema là một câu hỏi đặt ra cho model,
    nên chỉ hỏi những gì nó trả lời được, và đóng kín mọi object.
    """

    model_config = ConfigDict(extra="forbid")

    # **Đứng trước `kind`, có chủ ý** (`kriky-skill-routing`, 12/10/2026). Model sinh JSON từ trái
    # sang phải, nên field đầu tiên là quyết định đầu tiên. Khi `kind` đứng đầu, gpt-4o-mini chọn
    # hỏi lại trước khi kịp đọc ra các mục đã có -- *"Tạo đề … chương Hàm số cho lớp 12A, 10 câu"*
    # hỏi lại 8/8 lần dù prompt dặn nêu plan ngay, và đổi chữ ở lõi, skill, mô tả tool đều 0/6. Bắt
    # nó ghi ra thứ đã biết trước thì 4/6. Không rời AGENT: `completed` bỏ nó đi, chỉ log giữ lại.
    known: str = Field(
        default="",
        description=(
            "Ghi chú cho chính bạn, giáo viên KHÔNG đọc: những gì đã biết từ lời giáo viên và kết "
            "quả tool, và còn thiếu gì cho việc họ nhờ. Không viết câu hỏi hay câu trả lời ở đây."
        ),
    )
    kind: Literal["say", "call_tool", "ask_clarify", "plan", "outline"]
    text: str = Field(
        default="",
        description=(
            "Câu giáo viên đọc trên màn hình. Với ask_clarify, đây là câu hỏi. Không được rỗng với "
            "say và ask_clarify."
        ),
    )
    # `unbiased-model-text` T3 (người dùng chốt 12/10/2026): hỏi lại thì có ít nhất 3 lựa chọn do
    # model đề xuất, FE vẽ thêm lối "Khác" để giáo viên tự ghi. Câu hỏi về một dòng -- lớp, tài
    # liệu, mục -- thì BE chỉ giữ chữ khớp đúng một tên nó đã đọc (`teacher_chat._choices`, hậu ký
    # ADR-23), nên lời dặn ở đây là *chép đúng tên*.
    choices: tuple[str, ...] = Field(
        default=(),
        description=(
            "Chỉ với ask_clarify: ít nhất 3 câu trả lời ngắn giáo viên có thể bấm, mỗi câu một khả "
            "năng khác nhau, viết đúng như lời giáo viên sẽ trả lời -- một giá trị, không phải tên "
            "một mục hay một câu hỏi. Hỏi về một lớp, một tài liệu hay một mục thì chép đúng tên "
            "trong kết quả tool. Không đánh dấu lựa chọn nào là nên chọn. Các kind khác để trống."
        ),
    )
    tool_name: str = ""
    tool_args: tuple[_Argument, ...] = ()
    steps: tuple[_Step, ...] = ()
    # ADR-29 (`draft-outline`): dàn ý đề, chỉ với kind outline. Đứng sau `steps`: `known` vẫn là
    # field đầu tiên, và thứ tự ấy là thứ đã đo (`kriky-skill-routing`).
    outline: tuple[_OutlineItem, ...] = Field(
        default=(),
        description="Chỉ với outline: các mục dàn ý, theo thứ tự câu. Các kind khác để trống.",
    )

    def completed(self, request_id: str, model_tokens: int) -> NextStepCompleted:
        """Biến câu trả lời của model thành message BE đọc.

        Args:
            request_id: Id BE đã hỏi dưới.
            model_tokens: Con số provider báo lại.

        Raises:
            ValidationError: Khi model nói `plan` mà không nêu bước nào, hoặc nêu một bước không có
                tên tool. Handler ở tầng trên bắt và lùi về mock -- chưa có gì tới tay giáo viên
                lúc này, nên lùi về là an toàn.

        Returns:
            Đề nghị, kèm hai field model không bao giờ được hỏi. `steps` chỉ đi theo một `plan`,
            vì hợp đồng từ chối chúng ở mọi `kind` khác. `choices` chỉ đi theo `ask_clarify`: BE
            dựng nút từ chúng (`unbiased-model-text` T3) -- trước T3 field này để rỗng, vì ADR-23
            bản đầu bỏ hết chữ model viết.
        """
        # NFC cho mọi chữ model viết (`unbiased-model-text` T3): gpt-4o-mini có lúc trả "ứ" ở dạng
        # phân rã -- "ư" + dấu sắc rời (run-57) -- và chữ ấy không khớp nhãn BE, lời giáo viên hay
        # `bind_book`, dù in ra trông y hệt.
        return NextStepCompleted(
            request_id=request_id,
            kind=self.kind,
            text=_nfc(self.text),
            tool_name=self.tool_name,
            tool_args={argument.param: _nfc(argument.value) for argument in self.tool_args},
            steps=tuple(
                PlanStep(
                    tool_name=step.tool_name,
                    args={argument.param: _nfc(argument.value) for argument in step.args},
                    title=_nfc(step.title),
                )
                for step in self.steps
            )
            if self.kind == "plan"
            else (),
            choices=tuple(_nfc(one) for one in self.choices) if self.kind == "ask_clarify" else (),
            outline=tuple(
                OutlineItem(
                    questions=item.questions,
                    knowledge=_nfc(item.knowledge),
                    formulas=tuple(_nfc(one) for one in item.formulas),
                    approach=_nfc(item.approach),
                    source_nodes=item.source_nodes,
                )
                for item in self.outline
            )
            if self.kind == "outline"
            else (),
            model_tokens=model_tokens,
        )


class ProposeState(TypedDict):
    """Những gì chảy qua hai node.

    Attributes:
        request: Cuộc hội thoại và danh mục tool.
        skills: Tên các skill nạp cho lượt này, do `skill_router` chọn trước khi graph chạy.
        messages: Những gì model thấy, do `compose` điền.
        step: Đề nghị, do `choose` điền.
    """

    request: NextStepRequested
    skills: tuple[str, ...]
    messages: Annotated[list[BaseMessage], lambda old, new: new]
    step: NextStepCompleted | None


def _describe_tool(tool: ToolSpec) -> str:
    """Viết một tool ra để model chọn.

    Args:
        tool: Tool đúng như BE mô tả nó.

    Returns:
        Một khối gọi tên tool chính xác như cách BE dispatch, rồi tới việc nó làm,
        rồi tới các argument của nó.
    """
    lines = [f"- {tool.name}: {tool.description}"]
    for argument, meaning in tool.arguments.items():
        mark = " (tùy chọn)" if argument in tool.optional else ""
        lines.append(f"    {argument}{mark}: {meaning}")
    return "\n".join(lines)


def _describe_result(turn: TurnRecord) -> str:
    """Viết kết quả tool ra dưới dạng dữ liệu, không phải một câu kể về dữ liệu.

    JSON chứ không phải văn xuôi, vì model phải đọc các giá trị ra từ đó -- một id nó
    sẽ truyền cho tool tiếp theo, một con số nó sẽ dẫn lại cho giáo viên. Văn xuôi mời
    gọi việc làm tròn và mời gọi việc bịa.

    Args:
        turn: Một lượt `tool_result`.

    Returns:
        Một dòng gọi tên tool, rồi kết quả của nó dưới dạng JSON.
    """
    body = json.dumps(turn.tool_result, ensure_ascii=False, sort_keys=True)
    return f"Kết quả của {turn.tool_name}:\n{body}"


def _compose(state: ProposeState) -> dict:
    """Biến request thành những message model thấy.

    Lịch sử hội thoại trở thành các message theo đúng thứ tự. Một lần gọi tool và kết
    quả của nó là nước đi của chính trợ lý và thứ nhận lại được từ nước đi đó, nên
    chúng được render thành một lượt assistant và một lượt human -- đó là hình dạng
    một chat model mong đợi, và là lý do model không đề nghị cùng một tool hai lần.

    Args:
        state: Mang theo request.

    Returns:
        Mảnh `messages` của state.
    """
    request = state["request"]

    # Lõi trước, rồi skill, rồi tên giáo viên: phần đứng đầu càng ít đổi giữa hai lượt thì prompt
    # cache của provider càng dùng lại được nhiều. Skill nằm **sau** lõi, nên không skill nào nói
    # trước được một luật an toàn.
    opening = [_CORE]
    library = _opens_library(request, state["skills"])
    # Một hàm chứ không một chuỗi thay thế: `re.sub` đọc `\` trong chuỗi thay thế như escape, và một
    # ngày `_LIBRARY` có dấu `\` (LaTeX) thì chuỗi ấy hỏng lặng lẽ (review T2b,
    # `unbiased-model-text`).
    for skill in skills.named(state["skills"]):
        opening.append(
            _LIBRARY_SLOT.sub(
                lambda slot: f"{slot.group(1)}{_LIBRARY}\n" if library else "", skill.body
            )
        )
    if request.teacher_name:
        opening.append(f"Bạn đang nói với {request.teacher_name}.")
    if request.attached_document is not None:
        # `draft-from-document`: tài liệu của đoạn chat -- chip của câu này, hoặc chip gần nhất. Id
        # viết ra nguyên văn vì model gửi lại nó làm tham số `document_id`.
        document = request.attached_document
        if document.state == "ready":
            opening.append(
                f"Tài liệu giáo viên đính kèm: {document.filename} "
                f"(document_id = {document.document_id})."
            )
        elif document.state == "processing":
            # Tệp vừa tải lên, còn đang xử lý (review B6, `draft-from-document`): chưa có mục lục để
            # đọc. Nói ra, thay vì soạn như thể không có chip -- giáo viên đang nghĩ đề sẽ theo sách
            # này.
            opening.append(
                f"Tài liệu giáo viên đính kèm: {document.filename} -- đang xử lý, chưa đọc "
                "được. Nếu giáo viên nhờ soạn đề từ tài liệu này, nói rằng cần chờ tài liệu "
                "sẵn sàng rồi gửi lại; đừng soạn đề không tài liệu thay cho nó."
            )
        else:
            # Hỏng, hay không đọc được chữ (review B7, `draft-from-document`): chờ cũng không ra gì
            # -- bảo chờ là kẹt đoạn chat ở một lời hứa không ai giữ.
            opening.append(
                f"Tài liệu giáo viên đính kèm: {document.filename} -- KHÔNG đọc được nội dung. "
                "Nếu giáo viên nhờ soạn đề từ tài liệu này, nói rằng tài liệu này không dùng "
                "được và nhờ họ đính tài liệu khác; đừng soạn đề không tài liệu thay cho nó."
            )
    if _book_in_view(request):
        opening.append(_BOOK_PROCEDURE)
    if request.catalog:
        catalog = "\n".join(_describe_tool(tool) for tool in request.catalog)
        opening.append(f"Tool dùng ngay (call_tool) lượt này:\n{catalog}")
    else:
        # Nói ra điều đó tốt hơn bỏ hẳn phần này: một model không được cấp danh
        # sách nào thường cho rằng việc thiếu đó là sơ suất và vẫn gọi tên một tool.
        opening.append("Lượt này bạn không có tool dùng ngay nào.")
    if request.plannable:
        # Hai danh sách tới riêng, vì model phải phân biệt được "gọi được bây giờ" với "hẹn làm ở
        # pha sau". Trộn chúng lại là mời model gọi một tool ghi ngay lượt này -- BE từ chối, và
        # cái vòng lặp tiêu một lần gọi model để phát hiện lại đúng điều ấy.
        planning = "\n".join(_describe_tool(tool) for tool in request.plannable)
        opening.append(f"Tool nêu được trong plan (không gọi ngay):\n{planning}")
    else:
        # Không nhắc `call_tool` ở đây: khi `catalog` cũng rỗng thì dòng trên vừa nói là
        # không có tool nào, và một câu mời gọi tool ngay sau đó là một lời tự mâu thuẫn --
        # đúng loại chỗ model chọn câu nào nghe tích cực hơn.
        can_also = ", call_tool" if request.catalog else ""
        opening.append(f"Lượt này bạn không nêu plan được. Chỉ say{can_also} hoặc ask_clarify.")

    messages: list[BaseMessage] = [SystemMessage("\n\n".join(opening))]
    for turn in request.history:
        if turn.kind == "teacher":
            messages.append(HumanMessage(turn.text))
        elif turn.kind == "assistant":
            messages.append(AIMessage(turn.text))
        elif turn.kind == "tool_call":
            args = json.dumps(turn.tool_args, ensure_ascii=False, sort_keys=True)
            messages.append(AIMessage(f"Mình xin gọi {turn.tool_name} với {args}."))
        elif turn.kind == "outline":
            messages.append(AIMessage(_describe_outline(turn)))
        else:
            messages.append(HumanMessage(_describe_result(turn)))

    return {"messages": messages}


def _describe_outline(turn: TurnRecord) -> str:
    """Một lượt dàn ý trong lịch sử, như model cần đọc lại nó (`draft-outline`). Hàm thuần.

    Chữ BE đã in -- thứ giáo viên đọc -- cộng các mục dạng gọn: sửa dàn ý là nêu lại **đủ** mục, và
    `source_nodes` chỉ chép lại được khi nó còn nằm đâu đó. Dàn ý đã bị thay thì BE chỉ gửi số bản
    (`teacher_chat._shrunk`), và chỉ còn chữ.
    """
    kept = turn.tool_result or {}
    if not kept.get("items"):
        return turn.text
    compact = json.dumps(
        {key: kept.get(key) for key in ("version", "for", "first", "items")},
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"{turn.text}\n\n(Dàn ý bản này, để bạn sửa: {compact})"


def _spent(raw: object) -> int:
    """Đọc số token mà provider báo, lấy từ một response thô.

    Args:
        raw: Bất cứ thứ gì provider trả về kèm theo đối tượng đã parse.

    Returns:
        Tổng số token, hoặc 0 khi provider không báo gì. Số 0 nghĩa là "không được
        cho biết", không phải "miễn phí": một model giả trong test không báo gì, và
        một số provider cũng vậy.
    """
    usage = getattr(raw, "usage_metadata", None)
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if isinstance(total, int):
            return total
    return 0


async def _choose(state: ProposeState) -> dict:
    """Hỏi model một đề nghị, và ghi lại nó tốn bao nhiêu.

    `include_raw` là thứ làm cho chi phí biết được. Structured output một mình chỉ
    trả lại đối tượng đã parse rồi bỏ đi cái response nó đi trong, mà báo cáo usage
    thì nằm trên chính response đó -- nên lời khẳng định trong plan rằng ghi lại số
    token là "gần như miễn phí" đã sai: nó cần argument này và một field trong hợp
    đồng.

    Args:
        state: Mang theo các message đã dựng.

    Returns:
        Mảnh `step` của state, với `model_tokens` điền từ provider chứ không điền từ
        model.

    Raises:
        _NothingToSay: `say` hay `ask_clarify` mà `text` rỗng.
        _FewChoices: `ask_clarify` ít lựa chọn hơn `_choices_wanted`; mang theo câu hỏi ấy.
        _IncompletePlan: Plan có bước thiếu tham số bắt buộc; mang theo plan ấy, để `propose`
            còn dùng được nó khi lần hỏi lại hỏng.
    """
    model = llm.with_fallback(lambda chat: chat.with_structured_output(_Proposal, include_raw=True))
    answered = await model.ainvoke(state["messages"])

    # Một provider không làm được `include_raw` -- hoặc một fake bỏ qua nó -- trả
    # thẳng lại đối tượng đã parse. Cả hai hình dạng đều được hỗ trợ, vì số token chỉ là
    # thứ có thì tốt còn đề nghị thì không.
    if isinstance(answered, dict):
        parsed = answered["parsed"]
        if parsed is None:
            # `include_raw` biến một lần parse thất bại thành `parsed=None` cộng với
            # exception nằm dưới `parsing_error`, trong khi `include_raw=False` thì
            # đã raise nó kèm luôn đầu ra có vấn đề. Để nó đi qua là đổi một thông
            # báo gọi tên đầu ra xấu lấy một `AttributeError` trên None, mà cái đó
            # chẳng gọi tên gì cả.
            raise ValueError(
                f"model did not produce a usable proposal: {answered.get('parsing_error')}"
            )
        proposal: _Proposal = parsed
        spent = _spent(answered.get("raw"))
    else:
        proposal, spent = answered, 0

    logger.info("known before choosing %s: %s", proposal.kind, proposal.known)
    if proposal.kind in {"say", "ask_clarify"} and not proposal.text.strip():
        # Đo được khi thêm `known`: model viết câu hỏi vào ghi chú rồi để `text` rỗng. Một bong
        # bóng rỗng không bao giờ được tới màn hình; `propose` hỏi lại một lần.
        raise _NothingToSay(f"model chose {proposal.kind} with nothing to say")
    if proposal.kind == "outline" and not proposal.outline:
        raise _NoOutline("model chose outline with no item")

    # `request_id` do `propose` điền, vì đó là chỗ duy nhất biết nó. Để rỗng ở đây sẽ
    # là một lời nói dối nếu nó còn ở lại, nên nó không ở lại.
    request = state["request"]
    try:
        step = _unmangled(proposal).completed(request_id="", model_tokens=spent)
    except ValidationError as unusable:
        # Một mục dàn ý sai hình dạng (số câu ngoài 1–10, chữ rỗng): hỏi lại một lần, như một
        # câu rỗng -- không có gì để giáo viên đọc (`draft-outline`).
        if proposal.kind != "outline":
            raise
        raise _NoOutline(f"unusable outline item: {unusable.errors()[0]['msg']}") from unusable
    # Luật thứ tự đọc (`unbiased-model-text` T5): đề nghị đúng việc mà sai bước thì thành **một lời
    # gọi tool đọc**; ở bước kế trong cùng vòng gọi tool của BE, model nêu lại với kết quả trong
    # tay. Bước nào đã đọc rồi thì không gọi lại -- mỗi luật tự kiểm, không thì BE hỏi tới trần rồi
    # báo lỗi.
    step = _reads_first(step, request)
    step = _picked_book_first(step, request)
    step = _misfiled_read(step, request)
    step = _toc_first(step, request)
    step = _library_first(step, request, state["skills"])
    step = _which_book(step, request)
    step = _read_before_outline(step, request)
    if step.kind == "plan":
        lacking = _lacking(step.steps, state["request"]) or _garbled(step.steps)
        if lacking:
            raise _IncompletePlan(lacking, step)
    if step.kind == "ask_clarify":
        # Chỉ đếm câu trả lời thật: câu hỏi, tên mục và "Khác" bị bỏ trước (`_answers`) -- bấm
        # chúng là gửi đi một thứ không trả lời gì.
        answers = _answers(step.choices, step.text)
        # [CODE CHẾT 2026-10-13] Lối "Khác" không còn gửi chữ "Khác" (xem `_after_other`;
        # `unbiased-model-text`).
        # if _after_other(state["request"]):
        #     # Plan 4c T5: `_CORE` dặn *"vừa chọn Khác thì hỏi lại bằng một câu mở"*, model vẫn bày
        #     # lựa chọn mới -- trên trình duyệt *"Chương 1/2/3"* cho một đề không có sách.
        #     answers = ()
        step = step.model_copy(update={"choices": answers})
        wanted = _choices_wanted(state["request"])
        if len(answers) < wanted:
            raise _FewChoices(f"{len(answers)} choice(s), wanted {wanted}", step)
    return {"step": step}


def _build() -> object:
    """Lắp graph.

    Returns:
        Một graph đã compile, nhận `ProposeState` và điền vào `step`.
    """
    graph = StateGraph(ProposeState)
    graph.add_node("compose", _compose)
    graph.add_node("choose", _choose)
    graph.set_entry_point("compose")
    graph.add_edge("compose", "choose")
    graph.add_edge("choose", END)
    return graph.compile()


_GRAPH = _build()


async def propose(request: NextStepRequested) -> NextStepCompleted:
    """Quyết định việc gì nên xảy ra tiếp theo trong cuộc hội thoại này.

    Args:
        request: Lịch sử tới lúc này và các tool giáo viên này được dùng.

    Returns:
        Một đề nghị. `request_id` bị ghi đè bằng id BE đã hỏi dưới: model không biết
        id đó, và một đề nghị mang theo một id nhắc lại hoặc bịa ra sẽ bị quy về job
        của một lượt khác.

    Raises:
        Exception: Bất cứ thứ gì provider raise. Handler ở tầng trên quyết định lùi
            về cái gì, vì chỉ nó biết liệu đã có thứ gì tới tay giáo viên hay chưa.
    """
    chosen = await skill_router.choose(request.history)
    state = {"request": request, "skills": chosen, "messages": [], "step": None}
    try:
        final = await _GRAPH.ainvoke(state)
    except _AskAgain as first:
        # Một lần nữa, không hơn: lần hỏng thứ hai là model đang kẹt, không phải xui.
        logger.warning("%s for %s, asking once more", first, request.request_id)
        try:
            final = await _GRAPH.ainvoke(state)
        except _Flawed as again:
            # Thiếu lần hai thì để đề nghị đi tiếp, như trước khi có lưới này: plan thiếu tham số
            # thì `vet_plan` của BE nói lời từ chối của nó, câu hỏi ít lựa chọn thì vẫn là một câu
            # hỏi -- giáo viên vẫn tự ghi được qua "Khác". AGENT không bịa tham số hay lựa chọn.
            logger.warning("%s again for %s", again, request.request_id)
            better = again.step
            if (
                isinstance(again, _FewChoices)
                and isinstance(first, _FewChoices)
                and len(first.step.choices) > len(again.step.choices)
            ):
                better = first.step
            final = {"step": better}
        except Exception as again:
            if not isinstance(first, _Flawed):
                # Dàn ý hỏng hai lần cũng vậy: lùi về mock là cho giáo viên xem một dàn ý mock bịa
                # giữa một lượt chat thật (review đợt 4, `draft-outline`).
                if isinstance(again, (_NothingToSay, _NoOutline)):
                    logger.warning("empty answer twice for %s", request.request_id)
                    return NextStepCompleted(
                        request_id=request.request_id, kind="say", text=_UNCLEAR
                    )
                raise
            # Lần đầu đã có một đề nghị dùng được: lần hai hỏng kiểu gì cũng giữ nó -- không bao giờ
            # tệ hơn trước khi có lưới này. Plan thì lượt không sách `vet_plan` từ chối như cũ, lượt
            # có sách `bind_book` có thể điền nốt (review T2b, `unbiased-model-text`). Lần hai im
            # lặng, hay provider hỏng, mà thả lỗi ra thì `handlers` lùi về mock.
            logger.warning(
                "asking again failed for %s (%r); keeping the first answer",
                request.request_id,
                again,
            )
            final = {"step": first.step}
    step: NextStepCompleted = final["step"]
    logger.info("proposed %s for %s", step.kind, request.request_id)
    return step.model_copy(update={"request_id": request.request_id})
