"""Những phép kiểm ở tầm repo mà không service nào tự kiểm được về chính mình.

Chạy bởi `.\\dev.ps1 check`. Mỗi check ở đây thi hành một dòng trong bảng Invariants của AGENTS.md
-- dòng mà nếu không có nó thì sẽ phụ thuộc vào việc có ai còn nhớ hay không.

Script này import settings của **cả hai** service, điều mà code của service bị cấm làm. Đó là có chủ
ý và an toàn: `tools/` nằm ngoài `services/` và ngoài root_packages của `import-linter`, mà soi cả
hai phía chính là toàn bộ công việc của nó. Không đoạn code nào được ship phép làm như vậy.
"""

from __future__ import annotations

import io
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
AGENTS_MD_MAX_LINES = 174
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

# Hai hàm đưa một đề đi qua vòng đời của ADR-01, cộng với đường đi vòng qua
# chúng. Một tool của giáo viên mà nhắc tên một trong hai hàm đó là đang với tay
# qua đúng cái cổng nó phải đứng sau -- còn `assessment.state = ...` là cùng cái
# với tay ấy nhưng bỏ hẳn cổng, và đó mới là phiên bản mà một bản sửa có ý tốt dễ
# viết hơn nhiều. `==` thì tha: đọc state chính là cách một tool quyết định từ
# chối.
LIFECYCLE_VERBS = re.compile(r"\b(advance|withdraw)\s*\(|\.state\s*=[^=]")


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


CHECKS = (
    check_env_example_has_no_orphans,
    check_agent_holds_no_database_credentials,
    check_model_call_fits_inside_the_job_waiting_for_it,
    check_contract_files_stay_short,
    check_named_dev_tasks_exist,
    check_no_tool_changes_an_assessment_state,
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
