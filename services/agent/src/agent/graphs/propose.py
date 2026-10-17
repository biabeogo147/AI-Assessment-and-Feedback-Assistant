"""Pha lên plan của một lượt chat giáo viên: dựng prompt, rồi chọn.

Module này là **pha 1** của ADR-25. Nó tra cứu, hỏi lại, và khi đã đủ dữ kiện thì nêu một
plan — chứ không bao giờ ghi gì. Lời kể sau khi plan chạy nằm ở `reporting.py`, một task
riêng, vì đầu vào của nó khác hẳn: nó đọc kết quả của cả plan, không đọc catalog.

Hai danh mục tới riêng và điều đó là cố ý: `catalog` là tool gọi được ngay, `plannable` là
tool chỉ hẹn làm được ở pha 2. Model phải thấy cả hai — nó nêu tên tool và tên tham số
trong plan — nhưng phải phân biệt được chúng, vì gọi một tool ghi ngay lượt này sẽ bị BE
từ chối và tiêu một vòng để phát hiện lại đúng điều ấy.

Hai node, và node thứ hai là một lần gọi structured. Nó nhỏ hơn graph soạn đề một cách có
chủ ý: không có loop tự check nhiều vòng, vì một đề nghị thì hoặc được BE thực thi hoặc bị BE
từ chối, và BE là phía duy nhất biết được là cái nào. Có **một** phép kiểm phía AGENT với một
lần gọi lại: đề nghị hỏng hình dạng theo những luật AGENT tự biết (`_Flawed`: plan thiếu bước,
dàn ý không đếm câu, quá ba câu hỏi, câu tham số ít nút, plan soạn ngay sau lời xin sửa dàn ý)
thì model được hỏi lại đúng một lần kèm lý do.

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
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent import llm, skill_router, skills
from agent.latex_escapes import restore_latex_escapes
from contracts import (
    MOST_CLARIFY_QUESTIONS,
    ClarifyQuestion,
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
  thêm "Khác". Giáo viên vừa chọn "Khác" thì hỏi lại bằng một câu mở. Cần hỏi 2 hoặc 3 điều cùng
  lúc thì dùng questions — mỗi điều một câu, có label ngắn (1–3 chữ, như "Khối", "Số câu"), text là
  câu hỏi, choices ít nhất 3 lựa chọn của riêng điều ấy; khi ấy text của bạn là một câu mở ngắn và
  choices để trống. Giáo viên trả lời cả mấy câu trong một tin, dạng "Khối: Khối 7 · Số câu: 5 câu".
  Hỏi về một lớp, một tài liệu hay một mục thì chỉ hỏi một câu.
- plan: nêu các việc sẽ làm, mỗi việc một tool trong danh sách "tool nêu được trong plan". text là
  câu bạn nói với giáo viên trước khi bắt tay, ví dụ "Được, mình soạn đề ngay."
- outline: đề xuất DÀN Ý đề cho giáo viên duyệt, TRƯỚC khi soạn câu hỏi. Mỗi mục trong outline:
  questions (mục phủ bao nhiêu câu), knowledge (kiến thức câu kiểm, viết lại gọn và sạch), formulas
  (công thức sẽ dùng, mỗi công thức một cặp $), approach (dạng câu và các bước giải), source_nodes
  (số node của bài nguồn; rỗng khi không có tài liệu). Hai câu chung một mục thì cùng kiến thức,
  khác cách hỏi. Mỗi lần tối đa 10 câu. text là CẢ LỜI bạn trình bày dàn ý cho giáo viên, bằng
  Markdown và bằng lời của bạn: mỗi mục nêu số câu của nó (**Câu k** hay **Câu k–m**, đánh số từ câu
  đầu tiên của dàn ý), kiến thức, ít nhất một công thức của mục trong cặp $ khi mục có công thức,
  cách làm, và bài nguồn khi có sách -- gọi bằng tên bài, không bao giờ bằng số node. Công thức là
  bạn đề xuất, đừng gọi là công thức của sách.
  Kết bằng một câu hỏi bạn tự viết, xin giáo viên đồng ý hay nói chỗ cần đổi. Lời phải khớp đúng
  các mục trong outline, vì các mục mới là thứ được soạn. tool_args: for = new (đề mới), more
  (soạn thêm cho đề đang có) hoặc replace (thay một câu: một mục một câu, kèm question = số câu
  bị thay).

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
- Viết bằng Markdown gọn (màn hình dựng nó): **đậm** vừa phải cho chỗ cần nhấn, gạch đầu dòng khi
  liệt kê, xuống dòng giữa các ý. Không tiêu đề lớn, không khối mã; bảng chỉ khi so nhiều thứ.
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
# Lời **từ chối** sách: *"ko cần sách"*, *"không dùng tài liệu"*, *"khỏi sách nhé"*. Giáo viên Việt
# gõ tắt *ko*, *k*, *hok* rất thường; bỏ cả cụm trước khi tìm chữ sách (plan `backlog-tier-1`).
_NO_BOOK = re.compile(
    r"\b(?:không|ko|k|hok|hông|khỏi|chẳng|chả)\s+(?:cần\s+|dùng\s+|lấy\s+|theo\s+|có\s+)?"
    r"(?:sách|tài liệu|tệp|file|giáo trình|sgk|cuốn|quyển)\b",
    re.IGNORECASE,
)


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
        said = _NO_BOOK.sub(" ", said)
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
    reads = [turn for turn in since if turn.tool_name == "read_section"]
    results = [turn for turn in reads if turn.kind == "tool_result"]
    if results:
        # Đọc dở (`more`): thử tay 15/10/2026 đọc phần 1/5 của chương rồi viết dàn ý, nên dàn ý chỉ
        # phủ đầu chương. Còn phần chưa đọc thì đọc phần kế, cùng phạm vi, trước khi nêu dàn ý.
        # Chỉ phần đọc **của lượt này**, và chỉ khi dàn ý trỏ vào phạm vi ấy: một lần ngó mục khác,
        # hay lần đọc của lượt trước, không bắt đọc hết phần còn lại (review đợt 6).
        asked_at = max((at for at, turn in enumerate(since) if turn.kind == "teacher"), default=-1)
        current = [turn for turn in since[asked_at + 1 :] if turn.tool_name == "read_section"]
        calls = [turn for turn in current if turn.kind == "tool_call"]
        done = [turn.tool_result for turn in current if turn.kind == "tool_result"]
        last = done[-1] if done else {}
        sources = {node for item in step.outline for node in item.source_nodes}

        # **Cả** phạm vi đã đọc trong lượt -- mọi phần, mọi lời gọi --, không chỉ phần cuối: đọc
        # phần 3/5 xong mà dàn ý trỏ nút của phần 1–2 thì so với phần cuối không giao nhau, và
        # AGENT thôi bắt đọc tiếp dù còn hai phần (thử tay 17/10, case 04; plan `backlog-tier-1`).
        # Chỉ các lần đọc **cùng phạm vi** với lần cuối (cùng tham số, trừ `part`): đọc trọn mục B
        # rồi ngó phần 1 của mục A thì dàn ý trỏ vào B không bắt đọc tiếp A (review code pha 5).
        def scope(call: TurnRecord) -> dict:
            # Chuẩn hoá: `"1, 2"` và `"2,1"` là cùng một phạm vi (review code vòng 2).
            return {
                key: frozenset(int(one) for one in re.findall(r"\d+", str(value)))
                if key == "nodes"
                else str(value).strip()
                for key, value in call.tool_args.items()
                if key != "part"
            }

        same = [at for at, call in enumerate(calls) if calls and scope(call) == scope(calls[-1])]
        read = {int(node) for at in same if at < len(done) for node in done[at].get("nodes") or ()}
        for at in same:
            read |= {
                int(node) for node in re.findall(r"\d+", str(calls[at].tool_args.get("nodes")))
            }
        if (
            last.get("found") is True
            and last.get("more") is True
            and calls
            and (not sources or sources & read)
        ):
            asked = dict(calls[-1].tool_args)
            next_part = int(last.get("part") or 1) + 1
            logger.info(
                "model outlined after part %d of %s -- reading on", next_part - 1, last.get("parts")
            )
            return NextStepCompleted(
                request_id=step.request_id,
                kind="call_tool",
                tool_name="read_section",
                tool_args={
                    **{key: str(value) for key, value in asked.items()},
                    "part": str(next_part),
                },
                model_tokens=step.model_tokens,
            )
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
    """Một đề nghị hỏng theo kiểu hỏi lại model một lần thường là sửa được.

    Attributes:
        hint: Lý do nói với model ở lần hỏi lại, khi lệch có hệ thống -- một lần hỏi lại mù dễ ra
            lại đúng câu cũ (review pha 5, `kriky-writes-every-word`). Rỗng thì hỏi lại y như lần
            đầu.
    """

    hint = ""


class _NothingToSay(_AskAgain):
    """Model chọn `say`, `ask_clarify` hay `outline` mà để `text` rỗng."""


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


class _UncountedOutline(_Flawed):
    """Dàn ý có tổng câu khác số câu model vừa ghi trong `known`, hay dàn ý thay câu không phải đúng
    một mục một câu (`draft-outline`). Đo ở bench run-98: *"6 câu"* ra dàn ý 4 mục × 2 câu; *"thay
    câu 2"* ra dàn ý nêu lại cả đề.

    Lần hỏi lại phải nói **số câu đúng** (review code pha 5, plan `backlog-tier-1`): hint rỗng thì
    model không biết sai ở đâu, và lần hai ra đúng dàn ý ấy.
    """

    def __init__(self, flaw: str, step: NextStepCompleted) -> None:
        super().__init__(flaw, step)
        wanted = _WANTED.search(flaw)
        if flaw.startswith("replace"):
            self.hint = (
                "Dàn ý thay câu chỉ có đúng một mục, mục ấy một câu: chỉ cho câu bị thay. Nêu lại."
            )
        elif wanted and "known says" in flaw:
            # Con số là của **model** (`known`), không phải lời giáo viên: nói đúng nguồn, để model
            # tự xét lại cả `known` khi giáo viên vừa đổi số câu (review code vòng 2).
            n = wanted.group(1)
            self.hint = (
                f"Bạn ghi question_count={n} trong known mà tổng số câu của dàn ý khác {n}. Nêu "
                "lại dàn ý đủ đúng số câu giáo viên xin, và sửa known nếu giáo viên vừa đổi số câu."
            )
        elif wanted:
            n = wanted.group(1)
            self.hint = (
                f"Giáo viên xin {n} câu: tổng số câu của các mục trong dàn ý phải đúng {n}. "
                "Nêu lại dàn ý."
            )


# Số câu đúng trong lý do của `_miscounted` (*"known says 5"*, *"the teacher asked for 5"*).
_WANTED = re.compile(r"(?:says|asked for) (\d+)")


class _PlanOverRevision(_Flawed):
    """Model nêu plan soạn ngay sau lời giáo viên **xin sửa** dàn ý: plan ấy soạn theo dàn ý cũ mà
    giáo viên vừa xin đổi (backlog *Plan soạn … sau một lời xin sửa dàn ý vẫn qua cổng*; cổng BE chỉ
    đòi một dàn ý ở lượt ngay trước, plan `backlog-tier-1`)."""

    hint = (
        "Giáo viên vừa xin SỬA dàn ý, chưa đồng ý soạn. Đừng nêu plan soạn: nêu lại dàn ý đã sửa "
        "đúng lời giáo viên (kind=outline), rồi chờ giáo viên đồng ý."
    )


class _WrongQuestion(_Flawed):
    """Model hỏi lại ngay sau danh sách tài liệu mà không hỏi tài liệu nào -- nút của câu hỏi là các
    tài liệu (`_which_book`, `kriky-writes-every-word`)."""

    hint = (
        "Câu hỏi vừa rồi không hợp: ngay sau danh sách tài liệu, các nút giáo viên bấm là tên tài "
        "liệu, nên câu hỏi phải hỏi giáo viên soạn theo tài liệu nào. Viết lại câu hỏi ấy."
    )


class _TooManyQuestions(_Flawed):
    """Model hỏi hơn `MOST_CLARIFY_QUESTIONS` câu một lượt (ADR-32). Đề nghị mang theo đã giữ đủ
    trần -- lần hai vẫn vậy thì ba câu đầu đi tiếp."""

    hint = (
        f"Một lượt hỏi lại có nhiều nhất {MOST_CLARIFY_QUESTIONS} câu. Gộp hay bỏ bớt câu, giữ "
        "những điều giáo viên thật sự phải trả lời."
    )


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
    for turn in reversed(request.history):
        if turn.kind == "plan":
            break
        if turn.kind == "tool_result":
            listed = turn.tool_result.get("candidates")
            if isinstance(listed, list):
                return min(3, len(listed))
    return 3


def _choices_in(step: NextStepCompleted) -> int:
    """Tổng số lựa chọn một lượt hỏi lại bày ra, một câu hay nhiều câu (ADR-32). Hàm thuần."""
    if step.questions:
        return sum(len(one.choices) for one in step.questions)
    return len(step.choices)


def _row_names(request: NextStepRequested) -> set[str]:
    """Tên các dòng (`candidates`) của kết quả tool gần nhất kể từ plan gần nhất, gộp khoảng trắng,
    không phân biệt hoa thường. Hàm thuần."""
    for turn in reversed(request.history):
        if turn.kind == "plan":
            break
        if turn.kind == "tool_result":
            listed = turn.tool_result.get("candidates")
            if isinstance(listed, list):
                names = set()
                for one in listed:
                    if isinstance(one, dict):
                        for key in ("name", "label"):
                            if one.get(key):
                                names.add(" ".join(str(one[key]).split()).casefold())
                        # Chữ trên nút BE dựng cho một lớp (`teacher_chat._option`): model chép
                        # đúng nhãn ấy thì câu vẫn là câu về dòng (review code pha 5).
                        if one.get("name") and isinstance(one.get("student_count"), int):
                            button = f"{one['name']} ({one['student_count']} học sinh)"
                            names.add(" ".join(button.split()).casefold())
                return names
    return set()


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
# Câu hỏi hỏi **tài liệu nào**: *"bạn soạn theo tài liệu nào?"*, *"cuốn sách giáo khoa nào?"*,
# *"tài liệu Toán 10 gì?"* -- tối đa ba chữ chen giữa. Chữ "sách" một mình thì không: *"phần mệnh
# đề nằm ở mục nào của cuốn sách?"* là đúng ca lệch đã đo (run-83, run-87). Dấu Markdown bỏ trước
# khi so (review pha 5, `kriky-writes-every-word`): từ ADR-30 *"**tài liệu** nào"* là chữ hợp lệ.
_ASKS_WHICH_BOOK = re.compile(
    r"\b(?:tài liệu|giáo trình|cuốn|quyển|sách|tệp|file)(?:\s+\S+){0,3}?\s+(?:nào|gì)\b", re.I
)
_MARKUP = re.compile(r"[*_`]")


def _asks_which_book(text: str, listed: list[dict]) -> bool:
    """Câu hỏi có hỏi giáo viên soạn theo tài liệu nào không. Hàm thuần.

    Hai cách hỏi đúng: một cụm *"tài liệu nào"* (`_ASKS_WHICH_BOOK`), hay nêu thẳng tên các tài liệu
    -- *"bạn dùng Toán 10.pdf hay Đại số.pdf?"*, cách hỏi tự nhiên khi nút là tên tệp.

    Args:
        text: Câu hỏi model viết.
        listed: `candidates` của `list_documents` (`label` là tên tệp).

    Returns:
        True khi câu hỏi hỏi tài liệu nào.
    """
    plain = _MARKUP.sub("", unicodedata.normalize("NFC", text))
    if _ASKS_WHICH_BOOK.search(plain):
        return True
    lowered = plain.casefold()
    names = [unicodedata.normalize("NFC", str(one.get("label") or "")).casefold() for one in listed]
    stems = [name.rsplit(".", 1)[0] if "." in name else name for name in names]
    return any(stem and stem in lowered for stem in stems)


def _which_book(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Câu hỏi lại ngay sau một danh sách tài liệu hỏi đúng điều nút của nó trả lời. Hàm thuần.

    Từ ADR-30 (`kriky-writes-every-word`) code không đè chữ câu hỏi bằng một câu cố định nữa: model
    hỏi sai điều thì được hỏi lại một lần, và lần hai vẫn vậy thì câu của model đi tiếp. Chỉ soi
    câu hỏi **ngay sau** danh sách: review chung sau T5 (`unbiased-model-text`) thấy bản đầu đè mọi
    câu hỏi cho tới khi đọc mục lục, kể cả sau khi giáo viên đã ghi *"thôi, không dùng sách"* qua
    lối "Khác".

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        Chính `step`.

    Raises:
        _WrongQuestion: Khi `step` là `ask_clarify`, không chip, lượt **ngay trước** nó là kết quả
            một `list_documents` có ít nhất một tài liệu, mà câu hỏi không nhắc tài liệu hay sách.
    """
    if step.kind != "ask_clarify" or request.attached_document is not None:
        return step
    listed = _listed_documents(request)
    if not listed:
        return step
    spoken = [turn for turn in _since_plan(request) if turn.kind in {"teacher", "tool_result"}]
    last = spoken[-1] if spoken else None
    if last is None or last.kind != "tool_result" or last.tool_name != "list_documents":
        return step
    if _asks_which_book(" ".join([step.text, *(one.text for one in step.questions)]), listed):
        return step
    raise _WrongQuestion("asked something else right after listing the documents", step)


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


_COUNT_IN_KNOWN = re.compile(r"question_count\s*=\s*(\d+)")
# Số câu giáo viên tự nói: *"tầm 5 câu"*, *"Số câu: 5 câu"* (tin gộp của thẻ hỏi lại). Không khớp
# *"câu 3"* -- đó là số thứ tự, không phải số câu.
_COUNT_SAID = re.compile(r"(\d+)\s*câu\b", re.I)
# Lời giáo viên nói rõ việc của dàn ý: *"thay câu 3 …"*, *"soạn thêm 3 câu"* (`draft-outline`).
_REPLACES = re.compile(r"\b(?:thay|đổi|làm lại|soạn lại)\s+(?:câu|câu hỏi)\s*(?:số\s*)?(\d+)", re.I)
_ADDS = re.compile(r"\b(?:soạn|ra|làm|viết)\s+thêm\b|\bthêm\s+\d+\s+câu\b", re.I)
# *"soạn thêm một đề mới"* là đề khác, không phải câu thêm vào đề đang có (review đợt 6).
_ANOTHER_PAPER = re.compile(r"\bđề\s+(?:mới|khác|nữa)\b", re.I)
# Câu đồng ý của giáo viên ngay sau một dàn ý (`draft-outline`): **cả câu** chỉ là lời đồng ý, cùng
# vài tiếng đệm. Review đợt 6: khớp đầu câu thì *"ok nhưng câu 2 đổi sang tự luận"*, *"được không?"*
# thành đồng ý, và câu hỏi được soạn theo dàn ý giáo viên vừa xin đổi.
_AGREE_WORD = r"(?:ok|oke|okay|được|đồng ý|duyệt|chốt|ừ|vâng|soạn đi|làm đi)"
_AGREES = re.compile(
    rf"^\s*{_AGREE_WORD}(?:[\s,]+(?:{_AGREE_WORD}|nhé|nha|nhá|luôn|đi|rồi|ạ|vậy))*\s*[.!]*\s*$",
    re.IGNORECASE,
)
# Một mục trong `known`: `subject=Toán «Toán»` -- giá trị đứng trước «, hay trước `; mục=` kế tiếp.
# Dấu phẩy ở trong giá trị: *"tỉ lệ thuận, tỉ lệ nghịch"* là một phạm vi (review đợt 6).
_KNOWN_FIELD = re.compile(r"\b(subject|grade|topic_scope)\s*=\s*(.+?)\s*(?=«|;\s*\w+\s*=|;?\s*$)")


def _brief_in(known: str) -> dict[str, str]:
    """Môn, khối, phạm vi model đã ghi trong `known`, bỏ mục ghi `?`. Hàm thuần."""
    found: dict[str, str] = {}
    for key, value in _KNOWN_FIELD.findall(known):
        if value.strip() and value.strip() != "?":
            found.setdefault(key, value.strip())
    return found


def _approved_plan(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Giáo viên đồng ý dàn ý vừa hiện: plan dựng từ chính dàn ý, kể cả khi model nêu plan khác. Hàm
    thuần.

    Thử tay 15/10/2026: sau *"oke"* model dựng lại `known` từ câu vừa gõ, mất phạm vi, rồi hỏi
    lại khối -- lỗi *lời đáp ngắn làm model quên lượt trước* (`backlog.md`), rơi đúng vào bước duyệt
    của ADR-29. Lượt thử sau đó: *"oke"* cho một dàn ý soạn thêm ra plan `create_draft` khối 6 --
    plan của model cũng quên như vậy, nên không giữ nó. Mọi thứ plan cần đã nằm trong lượt dàn ý:
    việc (`for`), đề, câu bị thay, và môn, khối, phạm vi ghi lúc nêu dàn ý (`brief`); nút và tài
    liệu BE điền từ dàn ý. Thiếu một mục thì để model tự xoay.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        Plan soạn theo dàn ý, hoặc `step` nguyên.
    """
    if len(request.history) < 2 or request.history[-1].kind != "teacher":
        return step
    said = request.history[-1]
    # Câu giáo viên gõ mà lượt hỏng trước khi đáp (hàng mồ côi) không chen giữa dàn ý và lời đồng ý:
    # giáo viên gõ lại *"oke"* là đúng việc nên làm (review đợt 6).
    # Thông báo hệ thống cũng vậy: model hỏng sau *"oke"* thì giáo viên được dặn gửi lại, và lần gửi
    # lại ấy vẫn là lời đáp dàn ý (review pha 5, `kriky-writes-every-word`).
    earlier = list(request.history[:-1])
    while earlier and earlier[-1].kind in {"teacher", "notice"}:
        earlier.pop()
    if not earlier:
        return step
    shown = earlier[-1]
    if shown.kind != "outline" or not shown.tool_result.get("items"):
        return step
    if not _AGREES.search(unicodedata.normalize("NFC", said.text)):
        return step
    kept = shown.tool_result
    purpose = str(kept.get("for") or "new")
    if purpose == "replace":
        steps: tuple[PlanStep, ...] = (
            PlanStep(
                tool_name="replace_question",
                args={"assessment_id": "", "question_number": ""},
                title=f"Thay câu {kept.get('first')}",
            ),
        )
    elif purpose == "more":
        steps = (
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "", "question_count": ""},
                title="Soạn thêm câu hỏi",
            ),
        )
    else:
        brief = dict(kept.get("brief") or {})
        if not all(
            str(brief.get(key) or "").strip() for key in ("subject", "grade", "topic_scope")
        ):
            return step
        steps = (
            PlanStep(
                tool_name="create_draft",
                # Sách và các nút để trống: cổng duyệt của BE điền chúng từ chính dàn ý.
                args={
                    **{key: str(brief[key]) for key in ("subject", "grade", "topic_scope")},
                    "document_id": "",
                    "nodes": "",
                },
                title="Tạo đề trống",
            ),
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "{1.assessment_id}", "question_count": ""},
                title="Soạn câu hỏi theo dàn ý",
            ),
        )
    logger.info(
        "teacher agreed to outline %s; planning it (model chose %s)", kept.get("version"), step.kind
    )
    return NextStepCompleted(
        request_id=step.request_id,
        kind="plan",
        # Lời của chính model khi nó vừa nêu plan -- `_choose` chở nó trong một `say` -- không thì
        # không lời mở nào (ADR-30): câu hỏi lại model vừa viết không phải lời mở của plan này.
        text=step.text if step.kind in {"plan", "say"} else "",
        steps=steps,
        model_tokens=step.model_tokens,
    )


# Kết quả tool nói đoạn chat đã có một đề.
_HAS_DRAFT = frozenset({"create_draft", "start_drafting", "replace_question"})


def _right_purpose(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Dàn ý đúng việc giáo viên vừa nói, khi lời họ nói rõ việc ấy. Hàm thuần.

    Thử tay 15/10/2026 (H4) và bench run-98 (`dan-y-thay-cau` 2/6): *"thay câu 3 bằng …"* ra một
    dàn ý **cả đề** `for=new` -- giáo viên gõ *"oke"* là mở một đề mới thay vì thay câu 3. Model
    viết lại cả dàn ý, chỉ mục chứa câu ấy đổi, nên phép sửa không phải đoán: lấy đúng mục chứa câu
    N, một câu, `for=replace`. Tương tự *"soạn thêm"* trong đoạn chat đã có đề mà dàn ý là
    `for=new` thì việc là `for=more`.

    Lời nói rõ việc là câu **gần nhất** nói rõ một việc, kể từ plan gần nhất -- không chỉ câu
    cuối: thử tay sau review đợt 6, *"soạn thêm 1 câu về số La Mã"* rồi hai lần bấm lựa chọn Kriky
    hỏi lại, và dàn ý ra `for=new` vì câu cuối là tên một bài. Câu nhắc *"đề mới"* thì dừng dò:
    việc là đề mới.

    Args:
        step: Dàn ý model nêu.
        request: Lượt đang hỏi.

    Returns:
        Dàn ý đã đúng việc, hoặc `step` nguyên khi lời giáo viên không nói rõ việc gì.
    """
    if step.kind != "outline":
        return step
    said = ""
    for turn in reversed(_since_plan(request)):
        if turn.kind != "teacher":
            continue
        text = unicodedata.normalize("NFC", turn.text)
        if _ANOTHER_PAPER.search(text) or _REPLACES.search(text) or _ADDS.search(text):
            said = text
            break
    purpose = str(step.tool_args.get("for") or "new")
    has_draft = any(
        turn.kind == "tool_result"
        and turn.tool_name in _HAS_DRAFT
        and (turn.tool_result.get("created") or turn.tool_result.get("started"))
        for turn in request.history
    )
    replaces = _REPLACES.search(said)
    if replaces and has_draft and purpose != "replace":
        number = int(replaces.group(1))
        seen = 0
        for item in step.outline:
            seen += item.questions
            if number <= seen:
                logger.info("outline for %s rewritten to replace question %d", purpose, number)
                return step.model_copy(
                    update={
                        "outline": (item.model_copy(update={"questions": 1}),),
                        "tool_args": {**step.tool_args, "for": "replace", "question": str(number)},
                    }
                )
        return step
    if _ADDS.search(said) and not _ANOTHER_PAPER.search(said) and has_draft and purpose == "new":
        logger.info("outline for new on a turn asking for more -- for=more")
        return step.model_copy(update={"tool_args": {**step.tool_args, "for": "more"}})
    return step


def _count_said(request: NextStepRequested) -> int | None:
    """Số câu giáo viên nói gần nhất kể từ plan gần nhất, hay None. Hàm thuần.

    Bỏ câu *"thay câu 3 …"*: con số ấy là số thứ tự (`_REPLACES`). Bỏ số đứng sau *lớp*, *khối*:
    *"ra đề cho lớp 7 câu hỏi …"* không xin bảy câu. Lời *"thêm 2 câu"*, *"bớt 1 câu"* nói **sau**
    một dàn ý là lời sửa dàn ý ấy, không phải tổng mới: gặp nó thì không đối chiếu nữa -- BE vẫn
    chặn quá mười câu (review code pha 5, plan `backlog-tier-1`).
    """
    if _count_revised(request):
        return None
    for turn in reversed(_since_plan(request)):
        if turn.kind != "teacher" or _REPLACES.search(turn.text):
            continue
        said = _COUNT_SAID.findall(_GRADE_NUMBER.sub("", turn.text))
        if said:
            return int(said[-1])
    return None


def _count_revised(request: NextStepRequested) -> bool:
    """Lời giáo viên **gần nhất mang một con số hay một lời *soạn thêm*** kể từ plan là lời
    *thêm/bớt* (`_ADDS`, `_TRIMS`) nói **sau** một dàn ý. Hàm thuần.

    Lời không con số mà cũng không *soạn thêm* (*"câu 3 khó hơn nhé"*) và lời thay câu thì bỏ qua,
    duyệt tiếp về trước. Khi ấy tổng mới là dàn ý cũ cộng trừ lời sửa -- không con số nào đã ghi
    (lời giáo viên trước đó, hay `known` của model) còn là tổng đúng (review code vòng 2, plan
    `backlog-tier-1`).
    """
    since = _since_plan(request)
    # Duyệt ngược **mọi** lời giáo viên tới lời đầu tiên mang một con số hay một lời *soạn thêm*:
    # *"thêm 2 câu"* rồi
    # *"câu 3 khó hơn nhé"* vẫn là dàn ý đã sửa -- chỉ xét lời cuối thì đọc ra tổng 2 (review code
    # vòng 3).
    for at in range(len(since) - 1, -1, -1):
        turn = since[at]
        if turn.kind != "teacher" or _REPLACES.search(turn.text):
            continue
        if (_ADDS.search(turn.text) or _TRIMS.search(turn.text)) and any(
            earlier.kind == "outline" for earlier in since[:at]
        ):
            return True
        if _COUNT_SAID.search(_GRADE_NUMBER.sub("", turn.text)):
            return False
    return False


# *"lớp 7"*, *"khối 11"*: số ấy là khối, không phải số câu (`_count_said`).
_GRADE_NUMBER = re.compile(r"\b(?:lớp|khối)\s*\d+", re.IGNORECASE)
# Lời bớt câu khỏi một dàn ý: *"bớt 1 câu"*, *"bỏ 2 câu"* (`_count_said`).
_TRIMS = re.compile(r"\b(?:bớt|bỏ)\s+\d+\s+câu\b", re.IGNORECASE)


def _miscounted(step: NextStepCompleted, known: str, request: NextStepRequested) -> str:
    """Vì sao số câu của một dàn ý không khớp việc được nhờ; rỗng khi khớp. Hàm thuần.

    Đối chiếu với chính thứ model đã ghi: `question_count=N` trong `known` (quy trình `soan-de` bắt
    ghi nó). `known` không có số câu -- Haiku hay để trống nó từ lượt thứ hai -- thì đối chiếu với
    số câu giáo viên đã nói kể từ plan gần nhất (backlog *Mất số câu sau một lượt hỏi lại*: xin 5
    câu, hỏi lại một lượt, dàn ý ra 10). Không ai nói thì không đối chiếu -- BE vẫn chặn quá mười
    câu. Thay câu thì đúng một mục một câu, vì dàn ý ấy chỉ dành cho đúng câu bị thay.

    Args:
        step: Dàn ý model nêu.
        known: Ghi chú `known` của lần trả lời ấy.
        request: Lượt đang hỏi, để đọc lời giáo viên.

    Returns:
        Lý do, hoặc chuỗi rỗng.
    """
    total = sum(item.questions for item in step.outline)
    if str(step.tool_args.get("for") or "") == "replace":
        if len(step.outline) != 1 or total != 1:
            return f"replace outline has {len(step.outline)} item(s), {total} question(s)"
        return ""
    if _count_revised(request):
        return ""
    found = _COUNT_IN_KNOWN.search(known)
    if found:
        if int(found.group(1)) != total:
            return f"outline totals {total}, known says {found.group(1)}"
        return ""
    said = _count_said(request)
    if said is not None and said != total:
        return f"outline totals {total}, the teacher asked for {said}"
    return ""


# Lời xin sửa dàn ý: *"câu 2 đổi sang tự luận"*, *"thêm một câu hình học"*, *"oke nhưng câu 3 khó
# hơn"*. Lời đồng ý trọn câu (`_AGREES`) thì không phải.
_REVISES = re.compile(
    r"\b(?:đổi|sửa|thay|bỏ|thêm|bớt|chuyển|khó hơn|dễ hơn|nhưng|thay vì)\b", re.IGNORECASE
)


def _drafts_over_a_revision(step: NextStepCompleted, request: NextStepRequested) -> bool:
    """Plan có soạn câu, mà lời giáo viên sau dàn ý gần nhất là lời xin sửa. Hàm thuần."""
    if not any(one.tool_name in {"start_drafting", "replace_question"} for one in step.steps):
        return False
    after: list[TurnRecord] = []
    for turn in reversed(request.history):
        if turn.kind == "outline":
            break
        after.append(turn)
    else:
        return False
    said = [turn.text for turn in after if turn.kind == "teacher"]
    if not said or _AGREES.match(said[0]):
        return False
    return bool(_REVISES.search(_NO_CHANGE.sub(" ", said[0])))


# Lời **không** xin sửa: *"không cần sửa gì"*, *"ko đổi gì nữa"* -- bỏ đi trước khi tìm `_REVISES`,
# như `_NO_BOOK` với chữ *sách* (review code pha 5, plan `backlog-tier-1`).
#
# Chỉ khi động từ **đứng cuối ý**: *"không cần thêm câu hình học"* là lời xin bỏ một mục. Cuối ý là
# một trong ba hình dạng sau động từ (hay hai động từ liền nhau, *"sửa thêm"*):
#   - *gì/nữa/cả/hết/đâu* ngay sau động từ (*"không cần sửa gì nữa"*);
#   - một tiểu từ cuối câu thật, có thể kéo dài (*nhé, nha, nhen, nhaa, ạ*), *luôn/đi* đứng trước
#     cũng được (*"khỏi sửa luôn nha"*);
#   - chuỗi tiểu từ bất kỳ rồi hết câu hay một dấu câu (*"không cần sửa luôn cả"*, *"khỏi sửa đi"*).
# Sau hai hình dạng đầu, đuôi nhận thêm tiểu từ và một *thêm* cuối ý (`_TRAILING_MORE`).
# *luôn/đi* **giữa câu**, trước *cả/hết* rồi một chữ khác, là lời xin sửa (*"sao không bỏ luôn cả
# câu 3?"*). *"sao không …"* là lời gợi ý sửa, không phải lời phủ định. `\b` sau tiểu từ: *nha*
# không ăn đầu chữ *nhanh*.
#
# Bảy vòng review (pha 5) liền ra ca biên mới, nên regex này đi cùng một bộ câu có nhãn
# (`tests/test_revision_words.py`): sửa regex là chạy lại cả bộ. Ca biên còn lại là Tier 2 câu 5.
_CHANGE_VERB = r"(?:thay\s+đổi|chỉnh\s+sửa|sửa|đổi|thay|thêm|bớt|bỏ)"
_END_PARTICLE = r"(?:nh[éeaá]+n?|ạ+)"
_INNER_PARTICLE = r"(?:gì[iì]*|nữa|cả|hết+|đâu)"
_LONG_PARTICLE = r"(?:luôn|đi)"
# *thêm* ở đuôi chỉ khi nó cũng là cuối ý (*"không chỉnh sửa gì thêm"*): theo sau là hết câu, dấu
# câu, hay một tiểu từ khác -- *"không cần sửa nhé thêm 1 câu"* là lời xin thêm câu (vòng 8).
_TRAILING_MORE = (
    rf"thêm(?=\s*(?:[,.!?;:)]|$)|\s+(?:{_END_PARTICLE}|{_INNER_PARTICLE}|{_LONG_PARTICLE})\b)"
)
_ANY_PARTICLE = rf"(?:{_END_PARTICLE}|{_INNER_PARTICLE}|{_LONG_PARTICLE}|{_TRAILING_MORE})"
_NO_CHANGE = re.compile(
    # *"sao không …"* là lời gợi ý sửa, trừ *"không sao không cần sửa"* (vòng 8).
    r"(?<!(?<!\bkhông\s)(?<!\bko\s)\bsao\s)"
    rf"\b(?:không|ko|k|hok|hông|khỏi|chẳng|chả)\s+(?:cần\s+|phải\s+)?{_CHANGE_VERB}"
    rf"(?:\s+{_CHANGE_VERB})?"
    rf"(?:(?:\s+{_INNER_PARTICLE}\b)+(?:\s+{_ANY_PARTICLE}\b)*"
    rf"|(?:\s+{_LONG_PARTICLE}\b)*(?:\s+{_END_PARTICLE}\b)+(?:\s+{_ANY_PARTICLE}\b)*"
    rf"|(?:\s+{_ANY_PARTICLE}\b)*(?=\s*(?:[,.!?;:)]|$)))"
    rf"|\bkhông\s+có\s+gì\s+(?:cần\s+|phải\s+)?{_CHANGE_VERB}\b",
    re.IGNORECASE,
)


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


# Thông báo hệ thống khi model hai lần liền để trống lời (ADR-30, ngoại lệ 1: không giọng Kriky; BE
# lưu nó thành lượt `notice`). Trung tính có chủ ý: **không** lùi về mock của
# `handlers.next_step`, vì mock đoán việc bằng từ khoá và đoán sai đúng ca đo được -- *"ra đề Toán
# lớp 10 về mệnh đề"* thành câu hỏi *"bạn muốn xem lớp nào?"* (review A1). Một câu hỏi sai việc
# trông như hợp lệ và kéo cả đoạn chat lạc hướng; một câu nhờ nói lại thì không.
_UNCLEAR = "Kriky chưa hiểu rõ ý bạn. Bạn nói lại theo cách khác giúp nhé?"

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
            # Mục dàn ý (`draft-outline`): job soạn câu đọc đúng ba trường chữ này, và BE so công
            # thức của chúng với lời Kriky (`outline.check_message`, ADR-30) -- `\frac` thành
            # form-feed ở đây là hỏng ở cả hai chỗ.
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


class _Question(BaseModel):
    """Một câu của một lượt hỏi lại nhiều câu (ADR-32), dưới hình dạng model trả lời được."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(
        description="Nhãn ngắn 1–3 chữ của điều được hỏi, như Khối, Số câu, Phạm vi."
    )
    text: str = Field(description="Câu hỏi.")
    choices: tuple[str, ...] = Field(
        default=(),
        description="Ít nhất 3 câu trả lời ngắn giáo viên có thể bấm cho riêng câu này.",
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
            "Lời giáo viên đọc trên màn hình, Markdown. Với ask_clarify, đây là câu hỏi. Với "
            "outline, đây là cả lời trình bày dàn ý, khớp các mục. Không được rỗng với say, "
            "ask_clarify và outline."
        ),
    )
    # ADR-29 (`draft-outline`): dàn ý đề, chỉ với kind outline. Đứng **ngay sau `text`**, không ở
    # cuối: thử tay và bench run-98/run-100 thấy model chọn `outline` rồi để trống mục -- ở cuối,
    # sau `choices`, `tool_name`, `tool_args`, `steps`, nó đã "nói xong" ở `text` trước khi tới
    # mục. Model sinh JSON từ trái sang phải, cùng lý do `known` đứng đầu (`kriky-skill-routing`).
    outline: tuple[_OutlineItem, ...] = Field(
        default=(),
        description=(
            "Chỉ với outline: các mục dàn ý, theo thứ tự câu. Tổng questions của mọi mục ĐÚNG bằng "
            "số câu giáo viên xin; thay câu thì đúng một mục một câu. Các kind khác để trống."
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
    # ADR-32: hỏi 2–3 điều cùng lúc, mỗi điều một bộ nút. Đứng sau `choices`: một câu hỏi vẫn là
    # đường thường gặp, và hai đường đặt cạnh nhau để model thấy chúng loại trừ nhau.
    questions: tuple[_Question, ...] = Field(
        default=(),
        description=(
            "Chỉ với ask_clarify, khi cần hỏi 2 hoặc 3 điều cùng lúc: mỗi điều một câu. Khi dùng "
            "questions thì text là một câu mở ngắn và choices để trống. Hỏi một điều thì để trống."
        ),
    )
    tool_name: str = ""
    tool_args: tuple[_Argument, ...] = ()
    steps: tuple[_Step, ...] = ()

    def asked(self) -> tuple[tuple[ClarifyQuestion, ...], str, tuple[str, ...]]:
        """Các câu, lời mở và nút của một lượt hỏi lại, đã quy về hợp đồng (ADR-32). Hàm thuần.

        Hai câu trở lên đi thành `questions` (tối đa `MOST_CLARIFY_QUESTIONS`, phần dư bỏ --
        `_choose` đã hỏi lại model khi có dư). Một câu thì là câu hỏi lại thường: lời mở và câu hỏi
        gộp làm `text`, nút của câu thành `choices`.

        Returns:
            `(questions, text, choices)`.
        """
        made = tuple(
            ClarifyQuestion(
                label=_nfc(one.label).strip() or "Câu hỏi",
                text=_nfc(one.text).strip() or _nfc(one.label).strip() or "?",
                choices=tuple(_nfc(choice) for choice in one.choices),
            )
            for one in self.questions
            if one.text.strip() or one.label.strip()
        )
        if len(made) >= 2:
            return made[:MOST_CLARIFY_QUESTIONS], _nfc(self.text), ()
        if len(made) == 1:
            lead = _nfc(self.text).strip()
            joined = f"{lead}\n\n{made[0].text}" if lead and lead != made[0].text else made[0].text
            return (), joined, made[0].choices or tuple(_nfc(one) for one in self.choices)
        return (), _nfc(self.text), tuple(_nfc(one) for one in self.choices)

    def completed(self, request_id: str, model_tokens: int) -> NextStepCompleted:
        """Biến câu trả lời của model thành message BE đọc.

        Args:
            request_id: Id BE đã hỏi dưới.
            model_tokens: Con số provider báo lại.

        Raises:
            ValidationError: Khi model nói `plan` mà không nêu bước nào, hoặc nêu một bước không có
                tên tool. Handler ở tầng trên bắt và trả một thông báo hệ thống (ADR-30) -- không
                lùi về mock, vì mock nói dưới giọng Kriky một việc nó đoán.

        Returns:
            Đề nghị, kèm hai field model không bao giờ được hỏi. `steps` chỉ đi theo một `plan`,
            vì hợp đồng từ chối chúng ở mọi `kind` khác. `choices` chỉ đi theo `ask_clarify`: BE
            dựng nút từ chúng (`unbiased-model-text` T3) -- trước T3 field này để rỗng, vì ADR-23
            bản đầu bỏ hết chữ model viết.
        """
        # NFC cho mọi chữ model viết (`unbiased-model-text` T3): gpt-4o-mini có lúc trả "ứ" ở dạng
        # phân rã -- "ư" + dấu sắc rời (run-57) -- và chữ ấy không khớp nhãn BE, lời giáo viên hay
        # `bind_book`, dù in ra trông y hệt.
        questions, text, choices = (
            self.asked() if self.kind == "ask_clarify" else ((), _nfc(self.text), ())
        )
        return NextStepCompleted(
            request_id=request_id,
            kind=self.kind,
            text=text,
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
            choices=choices,
            questions=questions,
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
        hint: Lý do của lần hỏi lại, `compose` đặt nó cuối cùng như một ghi chú hệ thống; rỗng ở
            lần đầu (`_AskAgain.hint`).
    """

    request: NextStepRequested
    skills: tuple[str, ...]
    messages: Annotated[list[BaseMessage], lambda old, new: new]
    step: NextStepCompleted | None
    hint: NotRequired[str]


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
            messages.append(AIMessage(_asked_back(turn)))
        elif turn.kind == "tool_call":
            args = json.dumps(turn.tool_args, ensure_ascii=False, sort_keys=True)
            messages.append(AIMessage(f"Mình xin gọi {turn.tool_name} với {args}."))
        elif turn.kind == "notice":
            # Thông báo của hệ thống (ADR-30, ngoại lệ 1): không phải lời model đã nói.
            messages.append(HumanMessage(f"(Ghi chú của hệ thống, giáo viên đã thấy: {turn.text})"))
        elif turn.kind == "outline":
            messages.append(AIMessage(turn.text))
            items = _outline_items(turn)
            if items:
                messages.append(HumanMessage(items))
        else:
            messages.append(HumanMessage(_describe_result(turn)))
    if state.get("hint"):
        messages.append(HumanMessage(f"(Ghi chú của hệ thống: {state['hint']})"))

    return {"messages": messages}


def _asked_back(turn: TurnRecord) -> str:
    """Lời của một lượt Kriky trong lịch sử, kèm các câu nếu đó là lượt hỏi nhiều câu (ADR-32).
    Hàm thuần.

    Câu trả lời gộp của giáo viên (*"Khối: Khối 7 · Số câu: 5 câu"*) chỉ đọc được khi model thấy lại
    chính các câu nó đã hỏi; lời mở một mình không nói câu nào hỏi gì.
    """
    asked = (turn.tool_result or {}).get("questions")
    if not isinstance(asked, list) or not asked:
        return turn.text
    lines = [turn.text.strip()] if turn.text.strip() else []
    for index, one in enumerate(asked, start=1):
        if not isinstance(one, dict):
            continue
        choices = "; ".join(str(choice) for choice in one.get("choices") or [])
        lines.append(
            f"{index}. {one.get('label', '')}: {one.get('text', '')} (lựa chọn: {choices})"
        )
    return "\n".join(lines)


def _outline_items(turn: TurnRecord) -> str:
    """Các mục của một lượt dàn ý trong lịch sử, như một ghi chú của hệ thống (`draft-outline`). Hàm
    thuần.

    Sửa dàn ý là nêu lại **đủ** mục, và `source_nodes` chỉ chép lại được khi nó còn nằm đâu đó. Ghi
    chú đi **riêng** khỏi lời Kriky -- một tin nhắn của phía người dùng, không nối vào lời của chính
    model: từ ADR-30 lời ấy là cả dàn ý, và một khối JSON nằm trong lời mình vừa nói là thứ model dễ
    chép lại vào lời sau (review pha 4, `kriky-writes-every-word`). Dàn ý đã bị thay thì BE chỉ gửi
    số bản (`teacher_chat._shrunk`), và không có ghi chú nào.

    Returns:
        Ghi chú các mục, hoặc chuỗi rỗng khi lượt không còn mục.
    """
    kept = turn.tool_result or {}
    if not kept.get("items"):
        return ""
    compact = json.dumps(
        {key: kept.get(key) for key in ("version", "for", "first", "items")},
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"(Ghi chú của hệ thống, giáo viên không thấy: các mục của dàn ý vừa rồi — {compact})"


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
        _NothingToSay: `say`, `ask_clarify` hay `outline` mà `text` rỗng.
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
    # Giáo viên vừa đồng ý dàn ý: plan dựng từ dàn ý, **trước** mọi lần hỏi lại -- một câu trả lời
    # rỗng hay hỏng sau *"oke"* mà thành câu trung tính thì lời duyệt mất, và lần gõ lại không còn
    # đứng ngay sau dàn ý (review đợt 6).
    # Lời mở là lời model vừa viết cho plan, hay không có lời mở nào (ADR-30): không câu cố định.
    agreed = _approved_plan(
        NextStepCompleted(
            request_id="",
            kind="say",
            text=proposal.text.strip() if proposal.kind == "plan" else "",
            model_tokens=spent,
        ),
        state["request"],
    )
    if agreed.kind == "plan":
        return {"step": agreed}
    # Lượt hỏi lại mà mọi chữ nằm trong các câu là một lượt có chữ (review pha 6): `asked()` gộp
    # một câu duy nhất vào `text`, còn nhiều câu thì FE vẽ chúng, không cần lời mở.
    questioned = proposal.kind == "ask_clarify" and any(
        one.text.strip() or one.label.strip() for one in proposal.questions
    )
    if (
        proposal.kind in {"say", "ask_clarify", "outline"}
        and not proposal.text.strip()
        and not questioned
    ):
        # Đo được khi thêm `known`: model viết câu hỏi vào ghi chú rồi để `text` rỗng. Một bong
        # bóng rỗng không bao giờ được tới màn hình; `propose` hỏi lại một lần. Dàn ý cũng vậy
        # từ ADR-30: lời trình bày dàn ý là lời Kriky viết, không còn khuôn BE dựng thay.
        raise _NothingToSay(f"model chose {proposal.kind} with nothing to say")
    if proposal.kind == "outline" and not proposal.outline:
        raise _NoOutline("model chose outline with no item")
    if proposal.kind == "call_tool" and proposal.tool_name.strip() == "outline":
        # Thử tay 15/10/2026: `outline` là một kind, không phải tool; BE từ chối lời gọi ấy và
        # giáo viên thấy *"không có tool nào tên outline"* trong bằng chứng. Hỏi lại một lần.
        raise _NoOutline("model called a tool named outline")

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
    step = _right_purpose(step, request)
    if step.kind == "outline":
        # Môn, khối, phạm vi đi cùng dàn ý, cho lượt duyệt (`_approved_plan`).
        step = step.model_copy(
            update={"tool_args": {**_brief_in(proposal.known), **step.tool_args}}
        )
    if step.kind == "plan":
        lacking = _lacking(step.steps, state["request"]) or _garbled(step.steps)
        if lacking:
            raise _IncompletePlan(lacking, step)
        if _drafts_over_a_revision(step, state["request"]):
            raise _PlanOverRevision("plan drafts right after the teacher asked to change", step)
    if step.kind == "outline":
        miscounted = _miscounted(step, proposal.known, request)
        if miscounted:
            raise _UncountedOutline(miscounted, step)
    if step.kind == "ask_clarify" and step.questions:
        # ADR-32: mỗi câu một bộ nút, cùng lưới với câu hỏi thường -- từng câu đủ lựa chọn thật.
        kept = tuple(
            one.model_copy(update={"choices": _answers(one.choices, one.text)})
            for one in step.questions
        )
        step = step.model_copy(update={"questions": kept})
        # Đếm câu **thật** -- câu trống đã bị `asked()` bỏ: ba câu hợp lệ cộng một câu trống không
        # phải lý do hỏi lại model (review code 17/10, plan `backlog-tier-1`).
        real = sum(1 for one in proposal.questions if one.text.strip() or one.label.strip())
        if real > MOST_CLARIFY_QUESTIONS:
            raise _TooManyQuestions(f"{real} questions", step)
        # Câu về **dòng** (lựa chọn gọi tên một `candidate`) theo số dòng có thật -- chỉ có hai lớp
        # thì đòi ba là mời model bịa lớp thứ ba. Câu về **tham số** vẫn đòi ba (review code 17/10:
        # bản trước áp số dòng cho mọi câu, nên *Khối* hai nút cũng lọt).
        rows = _row_names(state["request"])
        wanted = _choices_wanted(state["request"])
        few = [
            one.label
            for one in kept
            if len(one.choices)
            < (
                wanted
                if any(" ".join(choice.split()).casefold() in rows for choice in one.choices)
                else 3
            )
        ]
        if few:
            raise _FewChoices(f"too few choices for {few}", step)
    elif step.kind == "ask_clarify":
        # Chỉ đếm câu trả lời thật: câu hỏi, tên mục và "Khác" bị bỏ trước (`_answers`) -- bấm
        # chúng là gửi đi một thứ không trả lời gì.
        answers = _answers(step.choices, step.text)
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
        Exception: Bất cứ thứ gì provider raise. Handler ở tầng trên biến nó thành một thông
            báo hệ thống (ADR-30).
    """
    chosen = await skill_router.choose(request.history)
    state = {"request": request, "skills": chosen, "messages": [], "step": None}
    try:
        final = await _GRAPH.ainvoke(state)
    except _AskAgain as first:
        # Một lần nữa, không hơn: lần hỏng thứ hai là model đang kẹt, không phải xui.
        logger.warning("%s for %s, asking once more", first, request.request_id)
        try:
            final = await _GRAPH.ainvoke({**state, "hint": first.hint})
        except _Flawed as again:
            # Thiếu lần hai thì để đề nghị đi tiếp, như trước khi có lưới này: plan thiếu tham số
            # thì `vet_plan` của BE nói lời từ chối của nó, câu hỏi ít lựa chọn thì vẫn là một câu
            # hỏi -- giáo viên vẫn tự ghi được qua "Khác". AGENT không bịa tham số hay lựa chọn.
            logger.warning("%s again for %s", again, request.request_id)
            better = again.step
            if (
                isinstance(again, _FewChoices)
                and isinstance(first, _FewChoices)
                and _choices_in(first.step) > _choices_in(again.step)
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
                        request_id=request.request_id, kind="say", text=_UNCLEAR, notice=True
                    )
                raise
            # Lần đầu đã có một đề nghị dùng được: lần hai hỏng kiểu gì cũng giữ nó -- không bao giờ
            # tệ hơn trước khi có lưới này. Plan thì lượt không sách `vet_plan` từ chối như cũ, lượt
            # có sách `bind_book` có thể điền nốt (review T2b, `unbiased-model-text`). Lần hai im
            # lặng, hay provider hỏng, mà thả lỗi ra thì `handlers` ra một thông báo hệ thống.
            logger.warning(
                "asking again failed for %s (%r); keeping the first answer",
                request.request_id,
                again,
            )
            final = {"step": first.step}
    step: NextStepCompleted = final["step"]
    logger.info("proposed %s for %s", step.kind, request.request_id)
    return step.model_copy(update={"request_id": request.request_id})
