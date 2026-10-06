"""Những phép kiểm ở tầm repo mà không service nào tự kiểm được về chính mình.

Chạy bởi `.\\dev.ps1 check`. Mỗi check ở đây thi hành một dòng trong bảng Invariants của AGENTS.md
-- dòng mà nếu không có nó thì sẽ phụ thuộc vào việc có ai còn nhớ hay không.

Script này import settings của **cả hai** service, điều mà code của service bị cấm làm. Đó là có chủ
ý và an toàn: `tools/` nằm ngoài `services/` và ngoài root_packages của `import-linter`, mà soi cả
hai phía chính là toàn bộ công việc của nó. Không đoạn code nào được ship phép làm như vậy.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import sys
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 173: hơn con số 172 bên dưới một dòng, mua ngày 2026-10-01 bằng luật rằng
# không tool nào của agent được đổi state của một đề. Nó xứng một dòng vì nó là
# nửa chịu lực của cổng thứ nhất trong ADR-05: trợ lý được viết nội dung, còn
# giáo viên quyết nội dung đó có đến tay học sinh hay không. Check đứng sau nó
# là một phép grep, thô có chủ ý -- thất bại đáng ngăn là việc có người với tay
# lấy cái import cho tiện trong lúc thêm một tool. Decision record nằm ở
# 2026-09-30-teacher-write-path-plan.md.
#
# 172: hơn con số 171 bên dưới một dòng, mua ngày 2026-09-30 bằng luật rằng
# các lựa chọn trong một câu hỏi làm rõ do BE viết ra từ những hàng nó đã đọc,
# không bao giờ do model viết (ADR-23). Nó xứng một dòng vì đây là loại luật mà
# một thay đổi sau này vô tình tái lập -- bản cài đặt đầu tiên đi lọc thứ model
# viết, và phép lọc đó rò cả hai chiều. Decision record nằm ở
# 2026-09-30-teacher-harness-foundation-plan.md.
#
# 171: hơn con số 170 bên dưới một dòng, mua ngày 2026-09-29 bằng một invariant
# mới cắt qua hai service -- trần của một lời gọi model phải nằm gọn trong độ
# kiên nhẫn của BE cho một job -- và nó xứng một dòng trong bảng Invariants. Luật
# nâng cap đã được tuân thủ: một decision record trong plan nói dòng đó mua gì.
#
# 170 được chốt **sau** khi viết xong hợp đồng, không phải trước. Con số đoán
# đầu tiên là 140, nhưng mọi mục sống qua được đợt cắt gọt đều là một luật, và
# hai mục dài nhất là bảng ownership và bảng invariant -- phần đặc nhất của file.
# Cắt luật thật để vừa một con số bịa ra là một đánh đổi sai. Cap tồn tại để
# chặn drift kể từ đây, nên chỉ nâng nó kèm một decision record nói rõ luật mới
# nào biện minh cho phần dài thêm.
# 174: hơn con số 173 bên dưới một dòng, mua ngày 2026-10-01 bằng một Repo-Specific
# Trap mới: một file `.ps1` không có BOM thì PowerShell 5.1 đọc nó theo cp1252. Nó xứng
# một dòng vì nó là **hệ quả trực tiếp** của luật ngôn ngữ vừa đổi -- comment tiếng Việt
# trong `dev.ps1` làm `Get-Help` in ra mojibake, tức khối `.SYNOPSIS` tồn tại để đọc qua
# `Get-Help` thôi đọc được, trong khi mọi task vẫn chạy đúng. Một lỗi chỉ hiện ở đường
# đọc chính thức và im lặng ở mọi check là đúng loại thứ cần một dòng viết ra. Decision
# record nằm ở 2026-09-30-teacher-write-path-plan.md.
#
# 175: hơn con số 174 bên dưới một dòng, mua ngày 2026-10-01 bằng bất biến
# *trạng thái ↔ số câu hỏi*. Nó xứng một dòng vì nó là bất biến duy nhất ở đây mà
# **không** có constraint nào của database đỡ được: `state` và số dòng `questions` là
# hai thứ, không gì buộc chúng khớp. Và chính việc viết dòng này ra đã làm lộ một lỗ
# -- endpoint bỏ duyệt nâng được một đề 0 câu lên `đang soạn` -- nên nó là một dòng
# đã trả tiền cho chính nó. Decision record nằm ở
# 2026-09-30-teacher-write-path-plan.md.
#
# 178: hai dòng nữa, mua ngày 2026-10-03 lúc chốt chặng A. Dòng thứ nhất gộp cả ba vế
# của xoá mềm: một đoạn đã xoá đọc ra như không có, không nhận lượt mới, **và** giữ
# nguyên các lượt nó đang có. Vế thứ ba là thứ ADR-24 đòi và là thứ dễ mất nhất trong
# một lần dọn code sau này -- đổi `deleted_at` thành một câu `DELETE` thì hai vế đầu
# vẫn đúng. Dòng thứ hai: *chỉ một câu hỏi lại mới mang nút bấm*. Nó mua bằng một lỗi
# đo được -- một lời thông báo sau `find_class` mọc ra hai cái nút, và bấm một nút gửi
# đi một câu giáo viên không hề gõ. Luật ấy chỉ đứng được ở BE, nơi duy nhất biết
# `step.kind`. Decision record nằm ở 2026-10-03-chot-chang-a-plan.md.
#
# 179: một dòng mua ngày 2026-10-03 cho hàng ownership của
# `docs/kich-ban-thu-tay-giao-vien.md`. Kịch bản thử tay là thứ chạy lại nhiều lần,
# không phải phần phụ của một plan rồi chết theo plan -- và một file ở gốc `docs/`
# không có chủ là đúng loại drift mà bảng ấy tồn tại để chặn. Decision record nằm ở
# 2026-10-03-bay-cai-tien-plan.md.
#
# 181: hơn con số 179 bên trên hai dòng, mua ngày 2026-10-04 bởi báo cáo đồ án ở
# `docs/report/`. Hai dòng ấy là một hàng ownership và một hàng invariant, và chúng mua hai
# thứ khác nhau. Hàng ownership tồn tại vì `docs/report/` là thư mục đầu tiên dưới `docs/`
# chứa **sản phẩm sinh ra từ** một thư mục khác: hình trong đó là bản xuất của
# `docs/diagrams/`, nên không có chủ thì sẽ có người sửa hình thay vì sửa sơ đồ. Hàng
# invariant tồn tại vì luật mới ấy có một chỗ thi hành thật, và bảng Invariants là chỉ mục
# của những chỗ thi hành -- một luật không được nêu ở đó thì không ai biết để trông. Dòng
# Validation của `.drawio` thì được **sửa** chứ không thêm, nên nó không tốn gì. Decision
# record nằm ở 2026-10-04-bao-cao-latex-plan.md.
AGENTS_MD_MAX_LINES = 181
CHILD_AGENTS_MD_MAX_LINES = 25

CHILD_AGENTS_FILES = (
    "services/be/AGENTS.md",
    "services/agent/AGENTS.md",
    "services/fe/AGENTS.md",
    "packages/contracts/AGENTS.md",
)

# Bất cứ thứ gì cho AGENT chạm trực tiếp tới một database. Redis không nằm trong
# danh sách này: AGENT cần queue, và REDIS_URL là một DSN nhưng không phải DSN
# của database.
DB_CREDENTIAL_PATTERN = re.compile(
    r"POSTGRES|MONGO|DATABASE_URL|\bDSN\b|PASSWORD|psycopg|sqlalchemy|motor|pymongo",
    re.IGNORECASE,
)

ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=")

# Hai hàm đưa một đề đi qua vòng đời của ADR-01, cộng hai đường đi vòng qua
# chúng. Một tool của giáo viên mà nhắc tên một trong hai hàm đó là đang với tay
# qua đúng cái cổng nó phải đứng sau -- còn `assessment.state = ...` là cùng cái
# với tay ấy nhưng bỏ hẳn cổng, và đó mới là phiên bản mà một bản sửa có ý tốt dễ
# viết hơn nhiều. `==` thì tha: đọc state chính là cách một tool quyết định từ
# chối.
#
# `teacher_routes` là đường đi vòng thứ hai, và nó chỉ mở ra ở Pha 4: hai endpoint
# duyệt/bỏ duyệt là coroutine public, nên một tool chỉ cần
# `from be.teacher_routes import approve` rồi `await` nó là đạt đúng kết quả mà hai
# pattern trên cấm, bằng một cái tên không có trong hai pattern đó. Cấm cả tên module
# thì rẻ hơn là đi đoán xem nó được import kiểu gì.
LIFECYCLE_VERBS = re.compile(r"\b(advance|withdraw)\s*\(|\.state\s*=[^=]|\bteacher_routes\b")


# Những token KHÔNG phải code: chúng được xoá trắng trước khi mọi phép grep ở dưới
# chạy. `FSTRING_MIDDLE` chỉ tồn tại từ Python 3.12 nên nó được tra mềm.
_PROSE_TOKENS = frozenset(
    {tokenize.COMMENT, tokenize.STRING}
    | {code for name in ("FSTRING_MIDDLE",) if (code := getattr(tokenize, name, None)) is not None}
)


def _fail(check: str, detail: str) -> str:
    return f"FAIL {check}\n      {detail}"


def check_env_example_has_no_orphans() -> str | None:
    """Mọi biến trong .env.example phải được Settings của một service đọc tới.

    Returns:
        None khi check đạt, ngược lại là một thông báo thất bại.

    Raises:
        ImportError: Khi các service chưa được cài. Chạy `.\\dev.ps1 install`.
    """
    from agent.config import Settings as AgentSettings
    from be.config import Settings as BeSettings

    declared = {
        match.group(1)
        for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if (match := ENV_LINE.match(line.strip()))
    }
    readable = {
        name.upper() for settings in (BeSettings, AgentSettings) for name in settings.model_fields
    }

    if not declared:
        return _fail("env-example", ".env.example declares no variables at all")

    orphans = sorted(declared - readable)
    if orphans:
        return _fail(
            "env-example",
            f"{orphans} declared but no config.py reads them. Wire them up or delete them.",
        )
    return None


def check_agent_holds_no_database_credentials() -> str | None:
    """AGENT phải không có đường tới database, để một job tự chở theo thứ nó cần.

    Returns:
        None khi check đạt, ngược lại là một thông báo thất bại kèm tên các file.
    """
    offenders = []
    for path in (REPO_ROOT / "services" / "agent").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if DB_CREDENTIAL_PATTERN.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}")

    if offenders:
        return _fail(
            "agent-no-db",
            f"database access appears in AGENT: {offenders}. "
            "AGENT reports evidence; data it needs travels in the job payload.",
        )
    return None


def check_model_call_fits_inside_the_job_waiting_for_it() -> str | None:
    """Cả một job của AGENT phải hết giờ **trước** cái job mà BE đang chờ.

    Không service nào tự kiểm được điều này: trần của một lời gọi model và số lần thử một job được
    phép làm nằm trong settings của AGENT, độ kiên nhẫn cho một job nằm trong settings của BE, và
    không bên nào import bên nào. Đặt sai thứ tự thì một model chậm sinh ra hình dạng thất bại tệ
    nhất -- BE bỏ cuộc và trả 503 trong khi worker vẫn đang làm, nên học sinh thấy một lỗi cho một
    câu trả lời rồi sẽ về và bị ném đi.

    Số lần thử là nửa dễ quên. Check này so **một** lời gọi với độ kiên nhẫn của BE cho tới khi vòng
    lặp authoring xuất hiện, và nó âm thầm sai suốt thời gian vòng lặp đó tồn tại: một job đã thành
    ba lời gọi mà không gì nói ra.

    Rồi nó sai y như vậy lần thứ hai, và tệ hơn: `draft_assessment` nhận tới năm mươi câu trong một
    job, mỗi câu một lời gọi model, nên trường hợp xấu nhất thật sự là 50 x LLM_MAX_ATTEMPTS lời gọi
    trong khi hàm này so với một. Task đó bị khai tử chứ không phải con số được nâng lên -- một job
    được cho năm mươi phút là một job BE thôi phân biệt được với một worker đã chết -- và nay mọi
    task đều nằm gọn trong số lần thử của đúng một câu.

    Thứ hàm này **không** thấy được là một vòng lặp **mới**. Hai lần rồi, lời nói dối đều đến từ một
    handler nhân số lời gọi model lên bằng một thứ mà phép tính ở đây không biết, nên một handler
    lặp theo một con số là một phát hiện của review, không phải một check đỏ.

    Returns:
        None khi job ở trường hợp xấu nhất vẫn nằm gọn trong độ kiên nhẫn của BE, ngược lại là một
        thông báo thất bại kèm mọi con số liên quan.
    """
    from agent.config import Settings as AgentSettings
    from be.config import Settings as BeSettings

    agent = AgentSettings()
    worst_case = agent.llm_timeout_seconds * agent.llm_max_attempts
    job_patience = BeSettings().agent_job_timeout_seconds

    if worst_case >= job_patience:
        return _fail(
            "timeout-order",
            f"a job may take LLM_TIMEOUT_SECONDS={agent.llm_timeout_seconds} x "
            f"LLM_MAX_ATTEMPTS={agent.llm_max_attempts} = {worst_case}s, which is not under "
            f"AGENT_JOB_TIMEOUT_SECONDS={job_patience}; a slow model would look "
            "like a dead one to BE while the worker is still busy",
        )
    return None


def check_contract_files_stay_short() -> str | None:
    """Cap số dòng là phép đo gián tiếp duy nhất dùng được cho luật "đừng kể lại file gốc".

    Một file đã sát cap thì không còn chỗ để chép một luật từ AGENTS.md sang.

    Returns:
        None khi mọi file đều trong cap của nó, ngược lại là một thông báo thất bại.
    """
    problems = []

    root = REPO_ROOT / "AGENTS.md"
    root_lines = len(root.read_text(encoding="utf-8").splitlines())
    if root_lines > AGENTS_MD_MAX_LINES:
        problems.append(f"AGENTS.md is {root_lines} lines, cap is {AGENTS_MD_MAX_LINES}")

    for relative in CHILD_AGENTS_FILES:
        path = REPO_ROOT / relative
        if not path.is_file():
            problems.append(f"{relative} is missing")
            continue
        count = len(path.read_text(encoding="utf-8").splitlines())
        if count > CHILD_AGENTS_MD_MAX_LINES:
            problems.append(f"{relative} is {count} lines, cap is {CHILD_AGENTS_MD_MAX_LINES}")

    if problems:
        return _fail("contract-length", "; ".join(problems))
    return None


def check_named_dev_tasks_exist() -> str | None:
    """Mọi task của dev.ps1 được AGENTS.md nêu tên phải thật sự chạy được.

    Canh cho bảng Validation không trôi xa khỏi chính script mà nó nêu tên.

    Returns:
        None khi mọi task được nêu tên đều tồn tại, ngược lại là một thông báo thất bại.
    """
    script = (REPO_ROOT / "dev.ps1").read_text(encoding="utf-8")
    match = re.search(r"\[ValidateSet\(([^)]*)\)\]", script)
    if match is None:
        return _fail("dev-tasks", "could not find ValidateSet in dev.ps1")

    available = set(re.findall(r"'([a-z-]+)'", match.group(1)))
    named = set(re.findall(r"dev\.ps1 ([a-z-]+)", (REPO_ROOT / "AGENTS.md").read_text("utf-8")))

    missing = sorted(named - available)
    if missing:
        return _fail("dev-tasks", f"AGENTS.md names {missing}, which dev.ps1 does not accept")
    return None


def _code_only(source: str) -> list[str]:
    """Trả lại từng dòng của một file Python với comment và string bị xoá trắng.

    Giữ nguyên số dòng và số cột -- mỗi ký tự bị bỏ thay bằng một dấu cách -- để cái
    regex chạy sau đó còn báo đúng số dòng cho người đọc.

    Tồn tại vì luật trước đó bỏ qua những dòng **bắt đầu** bằng `#` hay một dấu nháy,
    và một dòng ở giữa docstring thì không bắt đầu bằng cái nào cả. Comment của chính
    luật đó lại hứa rằng comment và docstring được miễn, nên luật và lời hứa của nó
    lệch nhau ở đúng chỗ đau nhất: một người sửa comment viết `advance(` trong một
    docstring cho tự nhiên, rồi thấy một đợt sửa chữ làm đỏ một invariant. Lọc bằng
    tokenize thì không còn khoảng cách đó -- và một tên hàm nằm trong string literal
    cũng thôi bị tính.

    Args:
        source: Nội dung một file Python đọc được.

    Returns:
        Các dòng, chỉ còn phần code.

    Raises:
        tokenize.TokenError: Nếu file không tokenize được, tức nó đã hỏng từ trước.
    """
    lines = source.splitlines()
    blanked = [list(line) for line in lines]

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in _PROSE_TOKENS:
            continue
        (start_row, start_col), (end_row, end_col) = token.start, token.end
        for row in range(start_row, end_row + 1):
            chars = blanked[row - 1]
            first = start_col if row == start_row else 0
            last = end_col if row == end_row else len(chars)
            for column in range(first, min(last, len(chars))):
                chars[column] = " "

    return ["".join(chars) for chars in blanked]


def check_no_tool_changes_an_assessment_state() -> str | None:
    """Trợ lý viết nội dung; giáo viên quyết nội dung đó có được phát hành hay không.

    ADR-05 đặt ba cổng quanh agent, và cổng thứ nhất là giáo viên duyệt một đề trước khi nó tới tay
    học sinh. ADR-02 thêm rằng phát hành cần sáu tham số đi qua một biểu mẫu và một hộp xác nhận,
    không bao giờ qua khung chat. Cả hai đều là lời hứa về những việc trợ lý **không thể** làm, và
    một lời hứa như thế đáng giá đúng bằng thứ đang thi hành nó.

    Vậy nên tool của agent được viết nội dung -- tạo một đề nháp và lấp câu vào đó đều đảo ngược
    được khi đề chưa duyệt -- nhưng không được chạm vào vòng đời. `advance` và `withdraw` trong
    `be/assessment_state.py` là hai đường duy nhất một đề đổi state, và check này từ chối một file
    tool chỉ cần **nhắc tên** chúng. Nó cũng từ chối `.state =`, vì một cổng không ai buộc phải đi
    qua thì không phải cổng: gán thẳng vào cột là đạt đúng kết quả ADR-01 cấm, mà còn bỏ qua luôn cả
    bảng cạnh.

    Thô hơn việc đọc call graph, và thô có chủ ý: thất bại đáng ngăn là việc có người với tay lấy
    cái import cho tiện trong lúc thêm một tool, mà một phép grep bắt được đúng lúc commit chứ không
    phải lúc review.

    Phép grep chỉ chạy trên **phần code**: `_code_only` xoá trắng mọi comment và mọi string trước.
    Nghĩa là một docstring được phép gọi tên luật mà nó đang giải thích, kể cả có dấu ngoặc đơn, và
    một tên hàm nằm trong string literal thì không bị tính.

    Returns:
        None khi file tool sạch, ngược lại là một thông báo thất bại kèm mọi dòng vi phạm.
    """
    tools = REPO_ROOT / "services" / "be" / "src" / "be" / "teacher_tools.py"
    if not tools.exists():
        return _fail("tools-decide-nothing", f"{tools} is missing; the check cannot run")

    offenders = [
        f"{tools.name}:{number}"
        for number, line in enumerate(_code_only(tools.read_text(encoding="utf-8")), 1)
        if LIFECYCLE_VERBS.search(line)
    ]

    if offenders:
        return _fail(
            "tools-decide-nothing",
            f"a teacher tool reaches for the assessment lifecycle at {offenders}. "
            "AGENT proposes and writes content; approving and publishing belong to "
            "the teacher endpoints (ADR-01, ADR-02, ADR-05). A state a tool needs "
            "to change is a state the teacher should be changing.",
        )
    return None


def check_invented_data_lives_in_one_file() -> str | None:
    """Thứ màn hình nói mà backend không biết là đúng thì chỉ được sống ở một chỗ.

    Panel của giáo viên in một chip nguồn cho mỗi câu hỏi -- *"Lấy từ ngân hàng câu hỏi"*,
    *"Thêm mới · chưa kiểm"*. `Question` có năm cột và không cột nào nói nguồn hay trạng thái kiểm,
    nên mấy cái chip ấy không suy ra được từ bất cứ dữ liệu nào: chúng là chữ **bịa**, nhận vào có
    chủ ý để dựng được màn hình, và ghi nợ trong `docs/plans/backlog.md`.

    Một món nợ như vậy trả được chừng nào nó còn nằm một chỗ. Sao chép chuỗi ấy sang một component
    thứ hai là lúc nó thôi là món nợ và thành một **luật của sản phẩm**: ngày BE biết nguồn thật,
    người sửa sẽ sửa một chỗ rồi tin rằng xong, trong khi chỗ thứ hai vẫn nói chữ cũ.

    `AGENTS.md` cấm một màn hình *suy ra* một luật từ dữ liệu; chỗ này nặng hơn một bậc và vì thế
    cần một hàng rào cứng chứ không chỉ một dòng tài liệu.

    Returns:
        None khi mọi chuỗi bịa chỉ xuất hiện trong module tự tố cáo, ngược lại là thông báo thất
        bại kèm tên file vi phạm.
    """
    home = REPO_ROOT / "services" / "fe" / "src" / "screens" / "teacher" / "invented-not-from-be.ts"
    if not home.exists():
        return _fail("invented-data-stays-put", f"{home} is missing; the check cannot run")

    marks = ("Lấy từ ngân hàng câu hỏi", "Thêm mới · chưa kiểm", "Thêm mới · đã kiểm")
    offenders = []
    for path in sorted((REPO_ROOT / "services" / "fe" / "src").rglob("*.ts*")):
        if path == home:
            continue
        body = path.read_text(encoding="utf-8")
        # Chỉ báo tên file, không in lại chính chuỗi đó. Console của Windows đọc cp1252
        # và một thông báo thất bại mang dấu tiếng Việt sẽ **nổ** thay vì in ra -- lúc đó
        # người ta thấy một traceback encoding chứ không thấy luật nào vừa bị vi phạm.
        if any(mark in body for mark in marks):
            offenders.append(str(path.relative_to(REPO_ROOT)))

    if offenders:
        return _fail(
            "invented-data-stays-put",
            f"invented screen data was copied out of its one module: {offenders}. "
            "Import it from invented-not-from-be.ts instead. The filename is the warning, "
            "and a second copy is how a debt quietly becomes a product rule.",
        )
    return None


def check_the_report_is_a_job_of_its_own() -> str | None:
    """Lời kể cuối lượt là một task riêng, và nó **không cầm tool nào**.

    ADR-25 dựng cả vòng chạy quanh một ranh giới: pha 1 lên plan với một catalog tool, pha 2 chạy
    plan, rồi **một lời gọi model riêng** kể lại. Câu quyết định của ADR là vế sau: *"lời gọi ấy
    đọc kết quả của cả plan và **không** đọc catalog — đó là lý do nó không thể đề nghị thêm một
    bước nữa."*

    Bản đầu của check này chỉ đếm xem lời gọi có nằm trong một vòng `for` hay không. Review đo
    được bảy cách phá luật mà nó vẫn xanh, trong đó có cách đúng-chữ-ADR nhất: thêm một field
    `catalog` vào `PlanReportRequested`, nhồi catalog pha 2 vào đó, và dặn model *"còn có thể gọi
    các tool sau"*. Không một test nào đỏ. Nên check nay nhìn vào thứ chịu lực:

    1. `worker.py` **đăng ký** `report_plan` dưới `REPORT_PLAN_TASK` — một task riêng thật.
    2. `PlanReportRequested` **không có field nào chở tool**: không `catalog`, không `tools`,
       không `plannable`. Hợp đồng là nơi duy nhất một cái catalog đi được sang AGENT.
    3. Graph viết lời kể **không chạm `ToolSpec`** và không import gì từ catalog.

    Thứ check này cố ý **không** làm: đếm vòng lặp quanh lời gọi. Luật *"báo cáo viết ở lần quan
    sát kế tiếp"* của cùng ADR gần như chắc chắn sẽ là một vòng lặp qua những lượt chưa báo cáo,
    và một check chặn nó là một check chặn chính ADR mình đang giữ.

    Returns:
        None khi luật còn đứng, ngược lại là một thông báo thất bại gọi tên chỗ hỏng.
    """
    import ast

    worker = (REPO_ROOT / "services" / "agent" / "src" / "agent" / "worker.py").read_text(
        encoding="utf-8"
    )
    registered = False
    for node in ast.walk(ast.parse(worker)):
        if not isinstance(node, ast.Call) or getattr(node.func, "id", "") != "func":
            continue
        first = node.args[0] if node.args else None
        named = next((one for one in node.keywords if one.arg == "name"), None)
        if (
            isinstance(first, ast.Name)
            and first.id == "report_plan"
            and named is not None
            and getattr(named.value, "id", "") == "REPORT_PLAN_TASK"
        ):
            registered = True
    if not registered:
        return _fail(
            "report-is-its-own-job",
            "worker.py no longer registers report_plan under REPORT_PLAN_TASK. BE would keep "
            "enqueueing the job, nobody would consume it, and every closing line would quietly "
            "fall back to a sentence BE wrote (ADR-25).",
        )

    contracts = (
        REPO_ROOT / "packages" / "contracts" / "src" / "contracts" / "teacher_chat.py"
    ).read_text(encoding="utf-8")
    asked = next(
        (
            node
            for node in ast.walk(ast.parse(contracts))
            if isinstance(node, ast.ClassDef) and node.name == "PlanReportRequested"
        ),
        None,
    )
    if asked is None:
        return _fail(
            "report-is-its-own-job",
            "PlanReportRequested is gone; the closing line no longer has a payload of its own.",
        )
    carries_tools = sorted(
        node.target.id
        for node in asked.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and any(word in node.target.id for word in ("catalog", "tool", "plannable"))
    )
    if carries_tools:
        return _fail(
            "report-is-its-own-job",
            f"PlanReportRequested now carries {carries_tools}. The closing call reads the plan's "
            "results and NOT the catalog -- that is the whole reason it cannot propose one more "
            "step (ADR-25). A tool list in this payload removes the boundary without failing a "
            "single test.",
        )

    graphs = REPO_ROOT / "services" / "agent" / "src" / "agent" / "graphs"
    telling = (graphs / "reporting.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(telling)):
        named = [one.name for one in node.names] if isinstance(node, ast.ImportFrom) else []
        if any(one in {"ToolSpec", "NextStepRequested"} for one in named):
            return _fail(
                "report-is-its-own-job",
                "reporting.py imports a tool type. The model that writes the closing line must "
                "not be handed a catalog at the one moment there is nothing left to call "
                "(ADR-25).",
            )
    return None


def check_the_form_fills_the_slots_the_wording_declares() -> str | None:
    """Khuôn câu luật ở BE và chỗ điền ở biểu mẫu phải nói cùng một thứ.

    ADR-03 đòi bốn nơi phát biểu luật thời gian **giống hệt nhau từng chữ**, và
    `publication_wording.py` tồn tại để chỉ có một nơi viết chữ ấy. Biểu mẫu phát hành là
    ngoại lệ có chủ ý: ở đó chưa có giờ nào lúc mở màn, nên nó nhận **khuôn** rồi điền con
    số giáo viên đang gõ. Chữ nghĩa vẫn một nơi — nhưng ba thứ nhỏ hơn thành hợp đồng giữa
    hai file: tên các chỗ trống, chỗ trống của một mốc giờ, và chỗ trống của một con số.

    Không có check này thì đổi `{last}` thành `{last_submission}` ở BE là một thay đổi
    **xanh hết mọi lưới**: BE tự sửa cùng lúc, test BE so khuôn với chính nó nên vẫn khớp,
    `tsc` không biết gì về nội dung chuỗi, và test FE dùng khuôn trong fixture của chính
    nó. Thứ duy nhất đổi là biểu mẫu thật in ra `{last_submission}` nguyên văn.

    Returns:
        None khi hai bên khớp, ngược lại là một thông báo thất bại.
    """
    wording = REPO_ROOT / "services" / "be" / "src" / "be" / "publication_wording.py"
    form = REPO_ROOT / "services" / "fe" / "src" / "screens" / "teacher" / "PublishSettings.tsx"
    for path in (wording, form):
        if not path.exists():
            return _fail("publish-wording", f"{path} is missing; the check cannot run")

    said = wording.read_text(encoding="utf-8")
    filled = form.read_text(encoding="utf-8")

    # Chỗ trống mà hai khuôn khai báo, lấy từ chính hai hằng số chứ không từ một danh sách
    # chép tay -- một danh sách chép tay ở đây lại là bản sao thứ ba của cùng một thứ.
    templates = re.findall(r"^(PHASE_ONE|PHASE_TWO) = (.+?)(?=^\S|\Z)", said, re.M | re.S)
    if len(templates) != 2:
        return _fail("publish-wording", "could not read PHASE_ONE and PHASE_TWO from the wording")
    declared = {slot for _, body in templates for slot in re.findall(r"\{([a-z_]+)\}", body)}

    # Chỗ biểu mẫu điền: khoá của hai object truyền vào `fill(...)`.
    used = set(re.findall(r"^\s{4}([a-z_]+):\s", filled, re.M))
    missing = declared - used
    if missing:
        return _fail(
            "publish-wording",
            f"the publish form never fills {sorted(missing)}, which the wording templates declare",
        )

    # Và hai chỗ trống phải là cùng một chuỗi ở hai bên.
    for name, pattern in (
        ("_BLANK", r'_BLANK = "(.+?)"'),
        ("_BLANK_RATE", r'_BLANK_RATE = "(.+?)"'),
    ):
        found = re.search(pattern, said)
        if found is None:
            return _fail("publish-wording", f"could not read {name} from the wording")
        if f'"{found.group(1)}"' not in filled:
            return _fail(
                "publish-wording",
                f"{name} is {found.group(1)!r} in the wording but the publish form never uses it",
            )

    # Và ba lời từ chối phải được **mượn**, không viết lại.
    #
    # Biểu mẫu nay nói trước cú bấm rằng một cửa sổ thời gian không dùng được, bằng đúng
    # chữ `_schedule_fault` sẽ trả về. Chép ba câu ấy sang FE là cách diễn đạt thứ hai cho
    # một luật, đúng thứ ADR-03 gọi là hai luật -- và nó hỏng **im lặng**: đổi chữ ở BE thì
    # cổng thật đổi theo, còn biểu mẫu vẫn nói câu cũ, và không test nào ở hai phía thấy.
    #
    # Check theo **tên field**, không theo nội dung chuỗi: nội dung là thứ được phép sửa,
    # còn việc FE đọc nó từ payload thay vì tự gõ mới là luật.
    faults = re.findall(r"^(FAULT_[A-Z_]+) = ", said, re.M)
    if len(faults) != 3:
        return _fail(
            "publish-wording",
            f"expected three FAULT_* sentences in the wording, found {faults}",
        )
    for constant in faults:
        field = constant.removeprefix("FAULT_").lower()
        if f"rules.{field}" not in filled:
            return _fail(
                "publish-wording",
                f"{constant} is declared in the wording but the publish form never reads "
                f"`rules.{field}`. The form must borrow the refusal BE will give, not write "
                "its own — two phrasings of one rule are two rules (ADR-03).",
            )
    return None


def check_every_figure_matches_the_diagram_it_came_from() -> str | None:
    """Mỗi hình trong báo cáo phải được xuất lại từ `.drawio` hiện tại, không phải bản cũ.

    `AGENTS.md` để `.drawio` làm source of truth cho mọi diagram, nên báo cáo LaTeX không vẽ
    lại sơ đồ mà nhúng hình **xuất ra** từ chúng. Bước xuất ấy là một lệnh riêng, chạy tay:
    không có gì buộc nó chạy lại sau khi một sơ đồ đổi.

    Không có check này thì sửa một `.drawio` là một thay đổi **xanh hết mọi lưới**: XML vẫn
    parse, `tsc` và pytest không biết `docs/` tồn tại, và báo cáo vẫn build ra PDF -- chỉ là
    nó in bản hình cũ. Người đọc không có cách nào biết, kể cả người viết. Nên lưới ở đây là
    một manifest ghi sha256 của `.drawio` tại thời điểm xuất, và phép so lại chính nó.

    Tên hàm cố ý không có chữ `report`: `check_the_report_is_a_job_of_its_own` ở trên nói về
    báo cáo của agent trong ADR-25, một thứ khác hẳn.

    Returns:
        None khi mọi hình khớp sơ đồ của nó, ngược lại là một thông báo thất bại.
    """
    diagrams = REPO_ROOT / "docs" / "diagrams"
    figures = REPO_ROOT / "docs" / "report" / "figures"
    manifest_path = figures / "sources.json"

    if not manifest_path.exists():
        return _fail("report-figures", f"{manifest_path} is missing; no figure can be trusted")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as broken:
        return _fail("report-figures", f"sources.json does not parse: {broken}")

    if not isinstance(manifest, dict) or not manifest:
        return _fail("report-figures", "sources.json must be a non-empty object keyed by figure")

    problems: list[str] = []
    accounted: set[str] = set()

    for figure, entry in sorted(manifest.items()):
        if not isinstance(entry, dict) or "source" not in entry or "sha256" not in entry:
            problems.append(f"{figure}: entry needs both 'source' and 'sha256'")
            continue

        source = REPO_ROOT / entry["source"]
        if not source.exists():
            problems.append(f"{figure}: source {entry['source']} does not exist")
            continue
        accounted.add(entry["source"].replace("\\", "/"))

        if not (figures / figure).exists():
            problems.append(f"{figure}: named in sources.json but the file is gone")
            continue

        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            problems.append(
                f"{figure}: {entry['source']} changed since it was exported -- re-export it"
            )

    # Chiều ngược lại, và đây là chiều dễ quên: thêm một sơ đồ mới mà không xuất hình thì
    # không hash nào lệch, vì không có entry nào để lệch cả.
    for diagram in sorted(diagrams.glob("*.drawio")):
        relative = diagram.relative_to(REPO_ROOT).as_posix()
        if relative not in accounted:
            problems.append(f"{relative}: no figure in the report was exported from it")

    if problems:
        return _fail("report-figures", "\n      ".join(problems))
    return None


def check_the_model_text_passes_through_the_escape_repair() -> str | None:
    r"""Chữ model vừa viết phải đi qua bộ dựng lại dấu gạch chéo trước khi đi tiếp.

    JSON có đúng tám escape hợp lệ, và `\b \f \n \r \t` nằm trong đó. Model viết toán bằng LaTeX,
    nên khi nó đặt `\frac` vào một chuỗi JSON mà không nhân đôi dấu gạch chéo, bộ giải mã đọc `\f`
    thành form-feed và nuốt luôn chữ `f`. Đo được trên database ngày 05/10/2026: phương án A của
    một câu vừa soạn là `24 0c 72 61 63 ...` -- `$` rồi `0x0C` rồi `rac`.

    Hậu quả không dừng ở chỗ xấu mã. `0x0C` đứng ngay sau `$` **là khoảng trắng** theo `\s` của
    regex, nên luật pandoc trong `MathText` từ chối nhận cả cụm là toán và dấu đô la lọt nguyên ra
    màn hình giáo viên. Một hỏng hóc ở ranh giới JSON hiện ra như một lỗi hiển thị ở đầu kia của
    hệ thống, cách đó ba service -- và đó là lý do nó tốn một buổi để tìm.

    Thứ dễ mất không phải bản thân phép thay chữ: `test_latex_escapes.py` ghim nó kỹ. Thứ dễ mất là
    **lời gọi** -- một lần dọn dẹp thấy `_unmangled` trông như một lớp bọc thừa và gỡ nó đi, rồi mọi
    test của hàm vẫn xanh trong khi dữ liệu thật lại hỏng. Check này đứng ở đúng chỗ ấy.

    **Hỏi bằng `ast` chứ không bằng grep**, và khác biệt ấy đo được: bản grep đầu tiên tìm chuỗi
    `_unmangled(` trong file, mà chuỗi ấy khớp luôn với dòng `def _unmangled(` -- nên gỡ lời gọi đi
    thì check vẫn xanh. Một luật không đỏ khi bị vi phạm thì không phải luật. Ở đây câu hỏi đúng là
    *"thân hàm `_write` có một lời gọi tới `_unmangled` không"*, và chỉ cây cú pháp trả lời được.

    Returns:
        None khi lời gọi còn đó, ngược lại là một thông báo thất bại.
    """
    graphs = REPO_ROOT / "services" / "agent" / "src" / "agent" / "graphs"
    repair = REPO_ROOT / "services" / "agent" / "src" / "agent" / "latex_escapes.py"

    if not repair.exists():
        return _fail(
            "escape-repair-is-wired-in",
            f"{repair} is missing; model text would reach the database with the "
            "backslashes JSON ate still missing.",
        )

    faults = []
    for file in sorted(graphs.glob("*.py")):
        source = file.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Chỗ nào gọi `with_structured_output` là chỗ nào đi qua bộ giải mã JSON. Tìm
        # theo **hành vi** chứ không theo tên hàm: thêm một graph mới mà quên nối dây thì
        # check này phải đỏ, và nó chỉ đỏ được nếu nó tự đi tìm chứ không đọc một danh
        # sách viết tay -- một danh sách như thế chỉ đúng tới lần thêm graph kế tiếp.
        holders = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
            and any(
                isinstance(inner, ast.Attribute) and inner.attr == "with_structured_output"
                for inner in ast.walk(node)
            )
        ]
        for node in holders:
            called = {
                inner.func.id
                for inner in ast.walk(node)
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
            }
            if not called & {"_unmangled", "restore_latex_escapes"}:
                faults.append(f"{file.name}:{node.name}")

    if faults:
        return _fail(
            "escape-repair-is-wired-in",
            f"{faults} ask the model through with_structured_output but never repair what "
            "comes back. That text must pass through restore_latex_escapes, or `\\frac` "
            "arrives as a form-feed and the teacher sees `$rac{1}{2}$` on screen (ADR-26).",
        )
    return None


def _block_after(body: str, marker: str) -> str:
    """Thân của khối `{...}` đầu tiên sau `marker`, hoặc chuỗi rỗng khi không có."""
    opened = body.find(marker)
    if opened == -1:
        return ""
    brace = body.find("{", opened)
    if brace == -1:
        return ""
    depth = 0
    for index in range(brace, len(body)):
        if body[index] == "{":
            depth += 1
        elif body[index] == "}":
            depth -= 1
            if depth == 0:
                return body[brace + 1 : index]
    return ""


def _top_level_keys(table: str) -> list[str]:
    """Các khoá ở **mức một** của một object literal TypeScript.

    Quét ký tự chứ không neo đầu dòng, và đó là cả điểm của hàm này. Bản trước dùng
    `re.findall(r"^\\s*(\\w+):", ..., re.MULTILINE)`, nên một khoá thứ năm viết **chung dòng**
    với khoá thứ tư không được đếm -- đo được: thêm `recalled: () => "..."` ngay sau
    `published` trên cùng một dòng thì check vẫn xanh với một bảng năm nấc. `dev.ps1 check`
    không chạy prettier trên TS, nên không có gì bẻ lại dòng ấy.
    """
    without = _no_comments(table)
    keys: list[str] = []
    depth = 0
    token: list[str] = []
    for char in without:
        if char in "{[(":
            depth += 1
            token = []
        elif char in "}])":
            depth -= 1
            token = []
        elif depth == 0 and char == ":":
            name = "".join(token).strip().strip("\"'")
            if name:
                keys.append(name)
            token = []
        elif depth == 0 and char == ",":
            token = []
        else:
            token.append(char)
    return keys


# Số nấc của thẻ: ba trạng thái của đề, cộng một cho việc KHÔNG xảy ra.
_CARD_STATES = 4

# Những cách dựng giao diện theo tên tool. `===` chỉ là cách viết hiển nhiên nhất; một
# `switch`, một `==`, một `.includes` hay một phép tra bảng tại chỗ đều dựng lại đúng cái
# dãy `if` mà luật này bỏ đi. Đo được: đổi phần vẽ sang `switch (turn.tool_name)` thì bản
# trước của check vẫn xanh.
# Một phép so bằng, và chỉ một: `create_draft` phân biệt một đề vừa mở còn rỗng.
_ONE_COMPARISON = (
    r"tool_name\s*===",
    r"tool_name\s*==[^=]",
    r"tool_name\s*!==",
)

# Những cách rẽ **nhiều** nhánh từ một tên tool. Ngân sách là **không**, vì mỗi cái đều chở
# được cả bảy nhánh cũ trong một câu lệnh -- đo được: đổi phần vẽ sang `switch
# (turn.tool_name)` thì một ngân sách "nhiều nhất một phép so" vẫn đếm ra 1 và vẫn xanh.
_NEVER_DISPATCH = (
    r"switch\s*\(\s*\w*\.?tool_name",
    r"\.includes\(\s*\w*\.?tool_name",
    r"tool_name\s*\.\s*(?:startsWith|endsWith|includes|match)",
    # Một phép tra bảng tại chỗ, trừ đúng `STATE_OF[...]` -- bảng dịch tool -> nấc là thứ
    # luật này dựng lên, không phải thứ nó cấm.
    r"(?<!STATE_OF)\[\s*\w*\.?tool_name\s*\]",
)


def check_the_result_card_has_exactly_three_states() -> str | None:
    """Thẻ kết quả là một máy trạng thái ba nấc, và số nấc phải đếm được.

    Người dùng chốt ngày 06/10/2026: *"thẻ chỉ xuất hiện một lần trong một đợt xử lí, không được
    phép xuất hiện hai lần liên tiếp. Trên đó chỉ hiện ba trạng thái: đã tạo đề -> đã duyệt đề ->
    đã phát hành. Nếu chọn bỏ duyệt đề thì quay lại 'đã tạo đề'."* Cộng một nấc cho việc **không**
    xảy ra, là bốn.

    Luật này mất một lần rồi, và nó mất theo cách không ai thấy: `ActionCard` dựng giao diện bằng
    một dãy `if (turn.tool_name === ...)`, nên **thêm một tool là thêm một trạng thái**. Đếm được
    hôm 06/10/2026: bảy đầu đề cho một thiết kế ba nấc -- `Đã tạo đề "X"`, `Đã tạo đề`,
    `Đã soạn k/n câu`, `Dừng ở k/n câu`, `Đã thêm N câu vào đề`, `Đã duyệt đề`, `Đã bỏ duyệt đề`,
    `Đã phát hành cho 12A và 12B`. Không dòng code nào sai; cái sai là không chỗ nào đếm.

    Nên nay các đầu đề sống trong **ba** chỗ phải khớp nhau -- union `CardState`, bảng `HEAD`,
    bảng `SAFETY` -- và check đếm cả ba rồi so chúng với nhau. Bản đầu chỉ đếm `HEAD`, và một
    đợt review tìm ra ngay cái khe ấy: thêm một nấc vào `CardState` cộng `SAFETY` mà viết dòng
    `HEAD` thứ năm **chung dòng** với dòng thứ tư thì check vẫn xanh.

    Nó cũng từ chối mọi cách dựng giao diện theo tên tool trong **vùng vẽ thẻ** -- từ bảng `HEAD`
    tới hết file -- chứ không chỉ trong thân `ActionCard`. Bản đầu neo vào `export default function
    ActionCard`, nên một helper có bảy nhánh đặt ngay phía trên component rồi gọi từ JSX là tái tạo
    đúng cái bệnh cũ ở một chỗ check không nhìn tới. Trên vùng vẽ thì `switch`, `==` và `.includes`
    cũng bị từ chối, không chỉ `===`.

    Vùng ấy **không** gồm `outcome()` và `modelCardTurn()`: chúng nằm trên `HEAD` và chúng trả lời
    hai câu khác -- *dòng kết quả của một bước trong khối `Thinking` nói con số gì*, và *lượt nào
    trong khối được chọn làm thẻ*. Cả hai đều phải biết tool là gì, và không cái nào viết ra một
    đầu đề.

    Và một chốt nữa: thuộc tính `head` của component phải lấy từ chính bảng `HEAD`. Thiếu nó thì
    bảng còn đúng bốn dòng trong khi JSX dựng chuỗi theo một đường khác, và check đếm một bảng
    không ai đọc.

    Ngân sách còn **một** phép so, và nó có tên: `create_draft` phân biệt một đề vừa mở còn rỗng
    -- cùng nấc `drafted`, thêm một nút mời. Một cái nút không phải một trạng thái.

    Returns:
        None khi ba bảng còn khớp và đúng bốn nấc, ngược lại là một thông báo thất bại.
    """
    card = REPO_ROOT / "services" / "fe" / "src" / "screens" / "teacher" / "ActionCard.tsx"
    if not card.exists():
        return _fail("card-has-three-states", f"{card} is missing; the check cannot run")

    body = card.read_text(encoding="utf-8")

    heads = _top_level_keys(_block_after(body, "const HEAD"))
    safeties = _top_level_keys(_block_after(body, "const SAFETY"))
    declared = re.search(r"export type CardState\s*=\s*([^;]+);", body)
    if not heads or not safeties or declared is None:
        return _fail(
            "card-has-three-states",
            "ActionCard.tsx must declare the union `CardState` and the tables `HEAD` and "
            "`SAFETY`. The card's heads live in tables so their number can be counted; a chain "
            "of if-branches cannot be.",
        )
    states = re.findall(r'"(\w+)"', declared.group(1))

    for name, found in (("CardState", states), ("HEAD", heads), ("SAFETY", safeties)):
        if len(found) != _CARD_STATES:
            return _fail(
                "card-has-three-states",
                f"ActionCard.tsx {name} has {len(found)} entries ({', '.join(found)}), expected "
                f"{_CARD_STATES}: three states of a paper (drafted -> approved -> published) plus "
                "one for the thing that did NOT happen. A fifth is a fourth state on the "
                "teacher's screen.",
            )
    if not set(states) == set(heads) == set(safeties):
        return _fail(
            "card-has-three-states",
            f"ActionCard.tsx CardState {sorted(states)}, HEAD {sorted(heads)} and SAFETY "
            f"{sorted(safeties)} disagree. All three describe the same ladder, so a state named "
            "in one and missing from another is a head or a safety line nobody can reach.",
        )

    drawing = _no_comments(body[body.index("const HEAD") :])

    branching = [one for pattern in _NEVER_DISPATCH for one in re.findall(pattern, drawing)]
    if branching:
        return _fail(
            "card-has-three-states",
            f"ActionCard branches on tool_name through {branching[0].strip()}. A switch, a lookup "
            "or an includes() carries all seven old branches inside one statement, so a budget of "
            "'at most one comparison' does not see it. The card is built from a STATE.",
        )

    compared = [one for pattern in _ONE_COMPARISON for one in re.findall(pattern, drawing)]
    if len(compared) > 1:
        return _fail(
            "card-has-three-states",
            f"ActionCard.tsx dispatches on tool_name {len(compared)} times, at most 1 allowed. "
            "The card must be built from a STATE, not from a tool name -- that is exactly how "
            "seven heads grew out of a three-state design. The one allowed comparison tells an "
            "empty new paper from a filled one; it adds a button, not a state.",
        )

    if not re.search(r"head=\{HEAD\[", drawing) or not re.search(r"SAFETY\[", drawing):
        return _fail(
            "card-has-three-states",
            "ActionCard must read its head from HEAD[state] and its safety line from "
            "SAFETY[state]. Building either string any other way leaves the tables correct and "
            "unread, so counting their rows measures nothing.",
        )
    return None


def _no_comments(source: str) -> str:
    """Bỏ comment `//` và `/* */` của một file TypeScript, giữ nguyên độ dài dòng."""
    without_block = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//.*", "", without_block)


CHECKS = (
    check_env_example_has_no_orphans,
    check_agent_holds_no_database_credentials,
    check_model_call_fits_inside_the_job_waiting_for_it,
    check_contract_files_stay_short,
    check_named_dev_tasks_exist,
    check_no_tool_changes_an_assessment_state,
    check_invented_data_lives_in_one_file,
    check_the_report_is_a_job_of_its_own,
    check_the_form_fills_the_slots_the_wording_declares,
    check_every_figure_matches_the_diagram_it_came_from,
    check_the_model_text_passes_through_the_escape_repair,
    check_the_result_card_has_exactly_three_states,
)


def main() -> int:
    """Chạy mọi check tầm repo và báo **tất cả** thất bại, không chỉ cái đầu tiên.

    Returns:
        0 khi mọi thứ đạt, ngược lại 1.

    Side effects:
        Ghi kết quả ra stdout.
    """
    failures = [message for check in CHECKS if (message := check()) is not None]

    for message in failures:
        print(message)

    if failures:
        print(f"\n{len(failures)} of {len(CHECKS)} repo checks failed.")
        return 1

    print(f"All {len(CHECKS)} repo checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
