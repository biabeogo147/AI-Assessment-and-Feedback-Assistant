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
# Nâng 181 -> 182 ngày 08/10/2026, tiêu đúng một dòng: hàng `services/document` trong bảng
# ownership. Cap là phép đo gián tiếp duy nhất cho luật *đừng kể lại file gốc*, nên nó chỉ
# còn nghĩa khi mỗi dòng mới phải trả giá bằng một lần sửa hằng số kèm một decision record --
# nâng rộng ra cho thoải mái là tự cho mình mấy dòng chưa có lý do. Decision record nằm ở
# 2026-10-08-document-service-text-layer-gate-plan.md.
# Nâng 182 -> 186 ngày 08/10/2026, tiêu đúng bốn dòng, và từng dòng nói nó mua gì: hai hàng
# ownership (`services/ingest`, `packages/schema` -- service thứ năm và package dùng chung thứ
# hai) và hai hàng invariant, cho hai check mà plan 2c vừa dựng. Hai hàng invariant ấy không
# phải trang trí: bảng Invariants là **chỉ mục** của những chỗ thi hành, nên một check tồn tại
# mà không có hàng ở đó là một cái lưới không ai biết để trông. Decision record nằm ở
# 2026-10-08-ingest-service-split-plan.md.
# Hạ 186 -> 181 ngày 09/10/2026. Đây là chiều ngược lại của cùng một luật: đường chấm bài cũ
# bị xoá khỏi code, nên ba hàng invariant canh nó và hai hàng nói về confidence không còn gì
# để canh. Cap phải đi xuống theo, nếu không nó để lại năm dòng tín dụng mà không ai trả giá
# -- và lần sau sẽ có người tiêu chúng mà không cần một decision record nào.
# Nâng 181 -> 182 ngày 10/10/2026, tiêu đúng một dòng: hàng invariant *một đoạn chat chạy nhiều
# nhất một lượt*. Cùng luật như hai lần trên — bảng Invariants là chỉ mục của những chỗ thi hành,
# nên một khoá vừa dựng mà không có hàng ở đó là một cái lưới không ai biết để trông. Decision
# record nằm ở 2026-10-10-one-turn-per-conversation-plan.md.
# Nâng 182 -> 184 ngày 13/10/2026, tiêu đúng hai dòng cho luật *tên bền không mang mã task
# của plan* (người dùng chốt): một Repo-Specific Trap, và hàng invariant chỉ tới chỗ thi hành
# (`task_code_in`, test quét id ca đo, `propose_bench` từ chối `--label`). Một id ca đo hay nhãn
# lượt đo như *"t5-…"* sống lâu hơn plan, và khi plan đã đóng thì không ai giải được nó. Decision
# record nằm ở 2026-10-12-unbiased-model-text-plan.md.
AGENTS_MD_MAX_LINES = 184
CHILD_AGENTS_MD_MAX_LINES = 25

CHILD_AGENTS_FILES = (
    "services/be/AGENTS.md",
    "services/agent/AGENTS.md",
    "services/document/AGENTS.md",
    "services/fe/AGENTS.md",
    "packages/contracts/AGENTS.md",
    "packages/schema/AGENTS.md",
    "services/ingest/AGENTS.md",
)

# Bất cứ thứ gì cho AGENT chạm trực tiếp tới một database. Redis không nằm trong
# danh sách này: AGENT cần queue, và REDIS_URL là một DSN nhưng không phải DSN
# của database.
DB_CREDENTIAL_PATTERN = re.compile(
    r"POSTGRES|MONGO|DATABASE_URL|\bDSN\b|PASSWORD|psycopg|sqlalchemy|motor|pymongo",
    re.IGNORECASE,
)

ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=")

# Một lời gọi SDK của MinIO là **sync**. BE thì async, nên mỗi lời gọi phải đi qua
# `run_in_threadpool`, và một chỗ quên là một event loop bị chặn suốt thời gian đẩy một
# cuốn sách lên -- thứ không bao giờ hiện ra dưới dạng exception, chỉ dưới dạng "sao hôm
# nay chậm thế".
MINIO_IMPORT = re.compile(r"^\s*(?:from|import)\s+minio\b", re.MULTILINE)

# Cùng hình dạng, và ở `services/document` còn gắt hơn: arq chạy tới `max_jobs` job đồng thời
# trên một event loop, nên một lời gọi PyMuPDF quên `asyncio.to_thread` chặn cả những job kia
# -- và nó không ném gì cả, chỉ làm mọi thứ chậm đi trong lúc ai đó tải một cuốn sách lên.
PYMUPDF_IMPORT = re.compile(r"^\s*(?:from|import)\s+(?:pymupdf|fitz)\b", re.MULTILINE)

# PaddleOCR: sync, CPU-bound, 3,6–5,3 giây một trang (`LayoutReader.read`), nặng hơn PyMuPDF nhiều.
# Hai model không liên quan nhau dùng nó, nên danh sách cho phép là **hai** file chứ không một
# (Tier 2 câu 16 = A, 21/10/2026): gom về một cửa là thêm một lớp gián tiếp chỉ để giữ chữ "một".
PADDLE_IMPORT = re.compile(r"^\s*(?:from|import)\s+(?:paddleocr|paddle)\b", re.MULTILINE)

# Client của kho nội dung (MongoDB). Async thuần nên không chặn event loop như hai SDK trên, nhưng
# luật "một module, một cửa" vẫn áp: một chỗ ghi Mongo thì một chỗ phải hỏi *"có ghi đúng thứ tự
# nội dung trước, `state` sau không"*.
PYMONGO_IMPORT = re.compile(r"^\s*(?:from|import)\s+(?:pymongo|motor)\b", re.MULTILINE)

# Hai SDK model của document agent (`document-agent-hierarchy`), và mọi SDK model nói chung cho BE
# và `ingest`.
TYPESAFE_IMPORT = re.compile(r"^\s*(?:from|import)\s+typesafe_sdk\b", re.MULTILINE)
LANGCHAIN_IMPORT = re.compile(r"^\s*(?:from|import)\s+langchain\w*\b", re.MULTILINE)
MODEL_SDK_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+"
    r"(?:langchain\w*|langgraph|openai|anthropic|google\.genai|google\.generativeai|typesafe_sdk"
    r"|google\s+import\s+genai)\b",
    re.MULTILINE,
)
_INDEX = REPO_ROOT / "services" / "document" / "src" / "document" / "index"

# Bản nới của `DB_CREDENTIAL_PATTERN` cho `services/document`: bỏ Mongo ra. Người dùng chốt ngày
# 11/10/2026 (`mongo-content-store`, D1) rằng **Mongo là kho nội dung, như MinIO** -- nơi thứ đọc
# được từ tệp nằm, không phải nơi sự thật về tệp nằm. Mọi thứ còn lại -- Postgres, `DATABASE_URL`,
# mật khẩu, `sqlalchemy` -- vẫn bị cấm y như cũ.
DB_CREDENTIAL_PATTERN_CONTENT_STORE_ALLOWED = re.compile(
    r"POSTGRES|DATABASE_URL|\bDSN\b|PASSWORD|psycopg|sqlalchemy",
    re.IGNORECASE,
)

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
    """Mọi biến trong .env.example phải được Settings của một service đọc tới -- và ngược lại.

    Chiều ngược (plan `backlog-tier-1`): một trường `config.py` đọc mà `.env.example` không khai
    là một núm vặn không ai biết có. `DEV_IDENTITY_HEADER` đã sống như vậy từ lâu, và ba núm của
    `document` cũng thế.

    Returns:
        None khi check đạt, ngược lại là một thông báo thất bại.

    Raises:
        ImportError: Khi các service chưa được cài. Chạy `.\\dev.ps1 install`.
    """
    from agent.config import Settings as AgentSettings
    from be.config import Settings as BeSettings
    from document.config import Settings as DocumentSettings
    from ingest.config import Settings as IngestSettings

    declared = {
        match.group(1)
        for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if (match := ENV_LINE.match(line.strip()))
    }
    # Cả **bốn** service. Thiếu một cái thì check này xanh bằng sự tình cờ: lúc
    # `services/ingest` ra đời, `INGEST_QUEUE_NAME` đi qua được chỉ vì `document` cũng
    # đọc đúng tên trường ấy để biết đẩy kết quả về đâu -- và ngày `document` thôi cần
    # nó, biến ấy thành mồ côi thật mà cổng vẫn im.
    readable = {
        name.upper()
        for settings in (BeSettings, AgentSettings, DocumentSettings, IngestSettings)
        for name in settings.model_fields
    }

    if not declared:
        return _fail("env-example", ".env.example declares no variables at all")

    orphans = sorted(declared - readable)
    if orphans:
        return _fail(
            "env-example",
            f"{orphans} declared but no config.py reads them. Wire them up or delete them.",
        )
    hidden = sorted(readable - declared)
    if hidden:
        return _fail(
            "env-example",
            f"{hidden} are read by a config.py but .env.example does not declare them. "
            "Declare each with its default and one line on what it does.",
        )
    return None


def check_agent_and_document_hold_no_database_credentials() -> str | None:
    """Hai service đọc-và-báo phải không có đường tới database nào.

    AGENT soạn nội dung, `document` đọc một tệp, và cả hai đều **báo lại** chứ không quyết
    định gì -- nên mọi thứ chúng cần phải đi tới trong payload của job. Đó là lý do
    `ExplainTurnRequested` chở sẵn lời giải thay vì một id, và `DocumentProbeRequested` chở
    `storage_key` thay vì một hàng.

    Khoá của object storage **không** tính, và `services/document` có nó: object storage là
    nơi byte nằm, không phải nơi sự thật nằm. Một tài liệu đã xử lý xong hay chưa thì chỉ
    Postgres biết, và Postgres ở phía bên kia tường. Đó cũng là lý do khoá ấy phải tên
    `MINIO_SECRET_KEY`: pattern dưới khớp chữ `PASSWORD` không phân biệt hoa thường.

    **Mongo cũng không tính, nhưng chỉ ở `services/document`.** Người dùng chốt ngày 11/10/2026
    (`mongo-content-store`, D1): Mongo là **kho nội dung, như MinIO** -- bản thô đọc ra từ tệp nằm ở
    đó, còn sự thật vẫn chỉ ở Postgres. `services/document` ghi bản thô, nên với nó Mongo được phép,
    qua đúng một module (`content_store.py`, canh bởi
    `check_only_one_module_per_service_talks_to_a_sync_sdk`). AGENT **chưa** được: *document agent*
    đọc Mongo là việc của `document-agent-hierarchy`, và mở cửa ấy là quyết định của plan ấy --
    không phải một thứ mở sẵn cho tiện.

    Returns:
        None khi check đạt, ngược lại là một thông báo thất bại kèm tên các file.
    """
    offenders = []
    roots = (
        (REPO_ROOT / "services" / "agent", DB_CREDENTIAL_PATTERN),
        (REPO_ROOT / "services" / "document", DB_CREDENTIAL_PATTERN_CONTENT_STORE_ALLOWED),
    )
    for path, pattern in ((one, rule) for root, rule in roots for one in root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if pattern.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}")

    if offenders:
        return _fail(
            "agent-no-db",
            f"database access appears in a reporting service: {offenders}. "
            "They report; the data they need travels in the job payload.",
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
    # Lần thứ ba một lời gọi mới xuất hiện trước model (`kriky-skill-routing`): Jev chọn skill trước
    # mỗi lần propose, có trần riêng, nên trường hợp xấu nhất cộng thêm trần ấy.
    # Mỗi lần thử có thể chạy hai model nối nhau (`llm.with_fallback`) khi có model dự phòng; SDK
    # không tự thử lại (`llm._build`, `max_retries=0`, Tier 2 câu 14 = A, 21/10/2026).
    models = 2 if agent.llm_fallback_provider and agent.llm_fallback_model else 1
    worst_case = (
        agent.skill_router_timeout_seconds
        + agent.llm_timeout_seconds * agent.llm_max_attempts * models
    )
    job_patience = BeSettings().agent_job_timeout_seconds

    if worst_case >= job_patience:
        return _fail(
            "timeout-order",
            f"a job may take SKILL_ROUTER_TIMEOUT_SECONDS={agent.skill_router_timeout_seconds} + "
            f"LLM_TIMEOUT_SECONDS={agent.llm_timeout_seconds} x "
            f"LLM_MAX_ATTEMPTS={agent.llm_max_attempts} x {models} model(s) = {worst_case}s, "
            "which is not under "
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


def assessments_made_past_empty(source: str) -> list[int]:
    """Các dòng tạo `Assessment(...)` với một `state=` khác `AssessmentState.EMPTY`.

    Bắt cả `models.Assessment(...)`, và cả `Assessment(**fields)`: khoá trải ra thì không ai đọc
    được state nó mang, nên tính là vi phạm (review code pha 5, plan `backlog-tier-1`).

    Args:
        source: Mã nguồn Python.

    Returns:
        Số dòng của từng lời gọi như thế; rỗng khi không có.
    """

    def named(func: ast.expr) -> bool:
        return (isinstance(func, ast.Name) and func.id == "Assessment") or (
            isinstance(func, ast.Attribute) and func.attr == "Assessment"
        )

    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and named(node.func)
        for keyword in node.keywords
        if keyword.arg is None
        or (keyword.arg == "state" and ast.unparse(keyword.value) != "AssessmentState.EMPTY")
    ]


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

    Đường vòng thứ ba là constructor: `Assessment(state=AssessmentState.APPROVED)` tạo thẳng một
    đề đã duyệt mà không qua `.state =` nào. Một lượt đọc AST bắt nó -- grep từng dòng không thấy
    được một lời gọi trải nhiều dòng. Tool tạo đề chỉ được mang state đầu, `EMPTY` (plan
    `backlog-tier-1`).

    Returns:
        None khi file tool sạch, ngược lại là một thông báo thất bại kèm mọi dòng vi phạm.
    """
    tools = REPO_ROOT / "services" / "be" / "src" / "be" / "teacher_tools.py"
    if not tools.exists():
        return _fail("tools-decide-nothing", f"{tools} is missing; the check cannot run")

    source = tools.read_text(encoding="utf-8")
    offenders = [
        f"{tools.name}:{number}"
        for number, line in enumerate(_code_only(source), 1)
        if LIFECYCLE_VERBS.search(line)
    ]
    offenders += [f"{tools.name}:{number}" for number in assessments_made_past_empty(source)]

    if offenders:
        return _fail(
            "tools-decide-nothing",
            f"a teacher tool reaches for the assessment lifecycle at {offenders}. "
            "AGENT proposes and writes content; approving and publishing belong to "
            "the teacher endpoints (ADR-01, ADR-02, ADR-05). A state a tool needs "
            "to change is a state the teacher should be changing.",
        )
    return None


# Đường đọc kho nội dung và ba trường chở chữ tài liệu thô của job soạn câu (`draft-outline`).
DOCUMENT_TEXT_READS = re.compile(
    r"\bget_reader\b|\.chunks\s*\(|\bcontent_reader\b|\b(focus_text|focus_title|other_foci)\s*="
)


def check_drafting_reads_no_document_text() -> str | None:
    """Job soạn câu chỉ nhận mục dàn ý giáo viên đã xem, không bao giờ nhận chữ tài liệu thô.

    ADR-29: tài liệu tới Kriky, Kriky tới dàn ý, BE in dàn ý ra chat, dàn ý tới job. Luật *job nhận
    đúng thứ giáo viên đã thấy* chỉ đứng được khi `drafting.py` -- nơi dựng mọi payload soạn câu --
    không có đường nào đọc kho nội dung. Một lời gọi `get_reader`, `.chunks(` hay một phép gán
    `focus_text=` trở lại là chữ OCR bẩn trở lại prompt của job, ở chỗ giáo viên không thấy.

    Chỉ quét **phần code** (`_code_only`): code chết comment lại và docstring kể lịch sử thì được.
    Giới hạn đã biết: `_code_only` xoá trắng mọi chuỗi, nên một khoá dict `"focus_text": …` không bị
    bắt -- đường chính vẫn bị, vì không có `get_reader`/`.chunks(`/`content_reader` thì không có
    chữ tài liệu nào để đặt vào khoá ấy.

    Returns:
        None khi `drafting.py` sạch, ngược lại là một thông báo thất bại kèm mọi dòng vi phạm.
    """
    drafting = REPO_ROOT / "services" / "be" / "src" / "be" / "drafting.py"
    if not drafting.exists():
        return _fail("outline-only", f"{drafting} is missing; the check cannot run")
    offenders = [
        f"{drafting.name}:{number}"
        for number, line in enumerate(_code_only(drafting.read_text(encoding="utf-8")), 1)
        if DOCUMENT_TEXT_READS.search(line)
    ]
    if offenders:
        return _fail(
            "outline-only",
            f"drafting reads document text at {offenders}. A drafting job receives the "
            "outline item the teacher saw, never raw document text (ADR-29).",
        )
    return None


def check_invented_data_lives_in_one_file() -> str | None:
    """Thứ màn hình nói mà backend không biết là đúng thì chỉ được sống ở một chỗ.

    Panel của giáo viên từng in một chip nguồn cho mỗi câu hỏi -- *"Lấy từ ngân hàng câu hỏi"*,
    *"Thêm mới · chưa kiểm"* -- chọn theo hash id: `Question` không có cột nguồn nào, nên chúng là
    chữ **bịa**. Chip đã gỡ 17/10/2026 (plan `backlog-tier-1`); check ở lại để mấy chuỗi ấy không
    quay về một component nào trước khi BE có nguồn thật.

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


def check_the_telling_turn_only_reads() -> str | None:
    """Lượt kể lại sau plan chỉ đọc: không tool ghi nào, không tool nào để nêu plan (ADR-25).

    Từ 22/10/2026 (plan `report-into-propose`, ADR-25 hậu ký) lời kể sau plan là một lượt `propose`
    nữa, không còn là job `report_plan` riêng không cầm tool. Ranh giới cũ -- *"lời kể không đề nghị
    thêm việc được"* -- nay đứng trên hai tham số của đúng một lời gọi, `_tell_after_plan` gọi
    `_ask_agent`: catalog lấy từ `catalog_for(..., PHASE_PLAN)` (chỉ tool đọc, gồm `last_plan`) và
    `plannable` là `()`. Đổi một trong hai là lượt kể lại mở được một vòng ghi thứ hai sau plan mà
    giáo viên chưa duyệt, và bản `_ask_agent` giả trong test BE không thấy được điều đó.

    Returns:
        None khi check đạt, ngược lại là một thông báo thất bại.
    """
    chat = REPO_ROOT / "services" / "be" / "src" / "be" / "teacher_chat.py"
    tree = ast.parse(chat.read_text(encoding="utf-8"))
    telling = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_tell_after_plan"
        ),
        None,
    )
    if telling is None:
        return _fail(
            "telling-turn-only-reads",
            f"{chat.name} has no _tell_after_plan: the check no longer sees the turn that tells "
            "about a plan. Point it at where that turn lives now.",
        )
    calls = [
        node
        for node in ast.walk(telling)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"_ask_agent", "catalog_for", "execute"}
    ]
    asks = [one for one in calls if one.func.id == "_ask_agent"]
    catalogs = [one for one in calls if one.func.id == "catalog_for"]
    runs = [one for one in calls if one.func.id == "execute"]
    problems = []
    if not asks:
        problems.append("it never calls _ask_agent")
    for one in asks:
        named = {word.arg: word.value for word in one.keywords}
        plannable = one.args[4] if len(one.args) > 4 else named.get("plannable")
        if not (isinstance(plannable, ast.Tuple) and not plannable.elts):
            problems.append(f"line {one.lineno}: plannable is not ()")
    if not catalogs or any(
        not (len(one.args) > 1 and getattr(one.args[1], "id", "") == "PHASE_PLAN")
        for one in catalogs
    ):
        problems.append("its catalog is not catalog_for(..., PHASE_PLAN)")
    # Cổng quyền ghi thật là `execute(..., phase=…)`: catalog chỉ là thứ model được kể.
    for one in runs:
        phase = {word.arg: word.value for word in one.keywords}.get("phase")
        if getattr(phase, "id", "") != "PHASE_PLAN":
            problems.append(f"line {one.lineno}: execute is not given phase=PHASE_PLAN")
    if any(isinstance(node, ast.Name) and node.id == "PHASE_WORK" for node in ast.walk(telling)):
        problems.append("it names PHASE_WORK")
    if problems:
        return _fail(
            "telling-turn-only-reads",
            f"_tell_after_plan in {chat.name}: {'; '.join(problems)}. The turn after a plan reads "
            "and speaks; it must not be handed a write tool or a way to plan (ADR-25).",
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

    Tên hàm cố ý không có chữ `report`: lời kể sau plan của ADR-25
    (`check_the_telling_turn_only_reads` ở trên) là một thứ khác hẳn.

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
    **lời gọi** -- một lần dọn dẹp thấy `unmangled` trông như một lớp bọc thừa và gỡ nó đi, rồi mọi
    test của hàm vẫn xanh trong khi dữ liệu thật lại hỏng. Check này đứng ở đúng chỗ ấy.

    **Hỏi bằng `ast` chứ không bằng grep**, và khác biệt ấy đo được: bản grep đầu tiên tìm chuỗi
    `unmangled(` trong file, mà chuỗi ấy khớp luôn với dòng `def unmangled(` -- nên gỡ lời gọi đi
    thì check vẫn xanh. Một luật không đỏ khi bị vi phạm thì không phải luật. Ở đây câu hỏi đúng là
    *"thân hàm `_write` có một lời gọi tới `unmangled` không"*, và chỉ cây cú pháp trả lời được.

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
    asking = []
    # `rglob`: graph `propose` là một package từ 20/10/2026 (plan `split-propose-package`); quét
    # nông thì `propose/choose.py` -- chỗ gọi model -- rơi khỏi check mà check vẫn xanh.
    for file in sorted(graphs.rglob("*.py")):
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
        asking += [f"{file.relative_to(graphs).as_posix()}:{node.name}" for node in holders]
        # Hàm sửa chữ tên `unmangled` ở mọi package: từ 22/10/2026 cả `authoring` cũng là package,
        # và hàm sửa ở file `repair.py` dùng chéo file nên bỏ `_` (plan `split-agent-graphs`, theo
        # luật đặt tên của `propose-names-and-order`).
        repairs = {"unmangled", "restore_latex_escapes"}
        for node in holders:
            called = {
                inner.func.id
                for inner in ast.walk(node)
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
            }
            if not called & repairs:
                faults.append(f"{file.relative_to(graphs).as_posix()}:{node.name}")

    if "propose/choose.py:choose" not in asking:
        return _fail(
            "escape-repair-is-wired-in",
            f"propose/choose.py:choose is not among the functions under {graphs} that call "
            f"with_structured_output ({asking}): the check no longer sees where Kriky's chat "
            "asks the model. Point it at where that call lives now.",
        )
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


# Những cách rẽ nhánh theo trạng thái tài liệu trong vùng vẽ chip. Phép tra bảng
# `CHIP[one.state]` **không** nằm ở đây: nó chính là thứ luật này dựng lên. Ngoại lệ duy nhất
# là `state === "ready"` — cổng kéo thả, và kéo được không phải một hình dạng thứ năm.
_CHIP_NEVER_DISPATCH = (
    r"switch\s*\(\s*\w*\.?state\b",
    r"\.state\s*===\s*\"(?!ready\")",
    r"\.state\s*!==\s*\"",
    r"\.state\s*==[^=]",
)


def _block_after_class(source: str, marker: str) -> str:
    """Thân của một class Python sau `marker`, tới chỗ thụt lề quay về mức không.

    Args:
        source: Toàn bộ file.
        marker: Dòng mở đầu class, ví dụ `class DocumentState`.

    Returns:
        Phần thân, hoặc chuỗi rỗng khi không tìm thấy.
    """
    opened = source.find(marker)
    if opened == -1:
        return ""
    rest = source[opened:].splitlines()
    kept = [rest[0]]
    for line in rest[1:]:
        if line and not line.startswith((" ", "\t")):
            break
        kept.append(line)
    return "\n".join(kept)


def check_the_document_chip_draws_every_state_the_backend_can_send() -> str | None:
    """Chip tài liệu phải vẽ **đúng** tập trạng thái mà BE gửi được — không thừa, không thiếu.

    Đây là phép so **hai ngôn ngữ**: `ChipState` trong `Rail.tsx` là TypeScript, `DocumentState`
    trong `packages/contracts` là Python, và không service nào tự kiểm được rằng hai bảng từ
    vựng ấy còn khớp. Đó chính là loại luật mà `tools/` tồn tại để canh.

    Hình dạng thất bại nó bắt, và nó im lặng cả hai chiều: BE thêm một trạng thái thứ năm thì
    chip rơi vào `CHIP[one.state]` không có khoá và vẽ ra `undefined`; FE đổi tên một nấc thì
    đúng nấc ấy không bao giờ hiện ra nữa. Cả hai đều chạy, đều không ném, và đều chỉ lộ ra khi
    một giáo viên nhìn vào một chip trống.

    Cộng một luật về hình dạng, lấy từ `check_the_result_card_has_exactly_three_states`: vùng
    vẽ chip không được rẽ nhánh bằng một dãy `if` trên `state`. Một dãy `if` thì thêm một nấc
    là thêm một dòng, và không chỗ nào đếm được. Chip được dựng từ một **bảng**.

    Returns:
        None khi hai bảng từ vựng còn khớp, ngược lại là một thông báo thất bại.
    """
    rail = REPO_ROOT / "services" / "fe" / "src" / "screens" / "teacher" / "Rail.tsx"
    spoken = REPO_ROOT / "packages" / "contracts" / "src" / "contracts" / "documents.py"
    for path in (rail, spoken):
        if not path.is_file():
            return _fail("chip-states", f"{path} is missing; the check cannot run")

    body = rail.read_text(encoding="utf-8")
    declared = re.search(r"export type ChipState\s*=\s*([^;]+);", body)
    table = _top_level_keys(_block_after(body, "const CHIP"))
    if declared is None or not table:
        return _fail(
            "chip-states",
            "Rail.tsx must declare the union `ChipState` and the table `CHIP`. The chip's "
            "words live in a table so their number can be counted; a chain of if-branches "
            "cannot be.",
        )
    drawn = re.findall(r'"([a-z_]+)"', declared.group(1))

    # Ben Python: cac thanh vien cua StrEnum DocumentState.
    enum = _block_after_class(spoken.read_text(encoding="utf-8"), "class DocumentState")
    sent = re.findall(r'^\s{4}[A-Z_]+ = "([a-z_]+)"', enum, re.MULTILINE)
    if not sent:
        return _fail("chip-states", "could not read DocumentState from contracts/documents.py")

    if not set(drawn) == set(table) == set(sent):
        return _fail(
            "chip-states",
            f"the document chip and the backend disagree: ChipState {sorted(drawn)}, CHIP "
            f"{sorted(table)}, DocumentState {sorted(sent)}. Every state the backend can store "
            "must have a shape on the rail, and a shape nobody can reach is dead paint.",
        )

    drawing = _no_comments(body[body.index("const CHIP") :])
    branching = [one for pattern in _CHIP_NEVER_DISPATCH for one in re.findall(pattern, drawing)]
    if branching:
        return _fail(
            "chip-states",
            f"Rail.tsx branches on a document state through {branching[0].strip()}. The chip is "
            "built from the CHIP table; the one comparison allowed is the drag gate "
            '(`state === "ready"`), because being draggable is not a fourth shape.',
        )

    return None


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


def check_rail_icons_do_not_sit_on_the_text_baseline() -> str | None:
    """Trong rail, một `<svg>` không được đứng trên baseline của chữ.

    Mặc định của một `<svg>` là `display: inline` cộng `vertical-align: baseline`, tức nó
    ngồi trên đường baseline của phần tử bọc nó thay vì lấp cái hộp đã định cỡ sẵn. Hộp thì
    căn giữa đúng, hình bên trong thì không -- và chênh lệch nhỏ tới mức không ai gọi tên
    được, chỉ thấy "nhìn hơi lệch".

    Đo được ngày 06/10/2026 trên `Rail destination`: hộp `.icon` ở y 122->134 (tâm 128), svg
    bên trong ở y 124->136 (tâm 130), chữ title tâm 128,05 -- icon thấp hơn title đúng
    **2px**. Trên Figma hai tâm trùng khít ở 3093, vì ở đó icon là một frame 12x12 và không
    có baseline nào. Figma đúng, FE lệch.

    **Vì sao là một check chứ không phải một test.** jsdom không dựng bố cục: nó trả 0 cho
    mọi `getBoundingClientRect`, nên không một test FE nào đo được 2px này. Đó chính là lý
    do lỗi sống sót qua từng ấy đợt review. Thứ kiểm được rẻ là *luật CSS có mặt hay không*,
    và luật ấy phải đặt ở **mức rail** -- `.rail svg` -- chứ không ở từng icon: `.caret` và
    icon tải lên đang đúng chỉ vì mỗi cái có một dòng riêng, nên icon thứ ba thêm vào mai
    này sẽ lệch y như hôm nay. Một luật chữa cả lớp lỗi; ba luật chữa ba chỗ rồi quên chỗ
    thứ tư.

    Returns:
        None khi `teacher.css` còn luật ấy, ngược lại là một thông báo thất bại.
    """
    sheet = REPO_ROOT / "services" / "fe" / "src" / "teacher.css"
    if not sheet.exists():
        return _fail("rail-icons-off-the-baseline", f"{sheet} is missing; the check cannot run")

    body = sheet.read_text(encoding="utf-8")
    block = re.search(r"\.rail\s+svg\s*\{([^}]*)\}", body)
    if block is None:
        return _fail(
            "rail-icons-off-the-baseline",
            "teacher.css must carry a `.rail svg` rule. Without it every icon in the rail "
            "sits on the text baseline instead of filling its sized box, which put the "
            "destination icons 2px below their titles -- measured in a real browser on "
            "06/10/2026, and invisible to jsdom, which lays nothing out.",
        )

    declared = block.group(1)
    # `in` trên hai chuỗi rời thì `display: inline-block` thoả **cả hai**, mà `inline-block`
    # vẫn ngồi trên baseline -- đúng cái bug check này sinh ra để chặn.
    if re.search(r"display\s*:\s*block\s*;", declared) is None:
        return _fail(
            "rail-icons-off-the-baseline",
            "`.rail svg` must set `display: block` exactly -- `inline-block` still sits on "
            "the text baseline. That is the one declaration that takes the icon off the "
            "baseline; sizing it alone leaves the offset in place.",
        )

    # Và phần bù BASELINE, thêm 06/10/2026 sau hai lượt người dùng vẫn thấy lệch.
    #
    # `display: block` ở trên chữa phần hình học, và sau nó ba phép đo tâm đều nói icon đã
    # cân: tâm icon, tâm hộp dòng và tâm thân chữ hoa đều 128, lệch 0,00. Mắt vẫn thấy xệ,
    # và đường gây ra là một đường khác: icon cao **12** còn thân chữ hoa chỉ cao **10**,
    # nên một icon căn giữa hộp dòng **thò xuống dưới baseline đúng 1px**. Baseline là
    # đường mạnh nhất trong một hàng chữ; cái gì chúi xuống dưới nó đọc ra là xệ.
    #
    # Lượt đầu tôi nâng theo *trọng tâm mực* và chỉ nâng hai icon. Mô hình ấy sai: nó nói
    # tập giấy và lưới ô đã cân, mà chính hai cái đó là hai cái người dùng chỉ ra lần thứ
    # hai. Luật đúng không phụ thuộc hình dạng, nên nó nằm ở mức rail chứ không ở chỗ gọi.
    #
    # Bất biến mà luật này dựa vào -- mực mỗi icon chạm đáy khung 12 -- do `teacher.test.tsx`
    # giữ, vì nó đọc được bằng toạ độ `viewBox` mà không cần bố cục.
    # `findall` chứ không `search`: selector này có **hai** khối -- một khối định cỡ hộp
    # 12x12 và một khối mang phần bù. `search` dừng ở khối đầu và báo thiếu một luật đang
    # có thật.
    blocks = re.findall(r"\.rail\s+\.destination\s+\.icon\s*\{([^}]*)\}", body)
    # Đòi đúng một phép tịnh tiến **lên**: `transform: none`, `translateY(0)` hay
    # `scale(1)` đều mang chuỗi `transform` mà không bù một pixel nào.
    nudged = any(
        re.search(r"transform\s*:\s*translateY\(\s*-\s*[0-9.]+px\s*\)", one) for one in blocks
    )
    if not nudged:
        return _fail(
            "rail-icons-off-the-baseline",
            "`.rail .destination .icon` must carry the 1px baseline nudge "
            "(`transform: translateY(-1px)`). Centring is not enough: the icon box is 12 "
            "tall and the cap band only 10, so a centred icon hangs 1px BELOW the text "
            "baseline -- measured 06/10/2026, and reported as 'icons look low' twice. "
            "jsdom lays nothing out, so no test can measure this.",
        )
    return None


def check_collapsed_panes_shrink_to_their_own_head() -> str | None:
    """Một ngăn rail đã thu, và tấm trượt phát hành đã thu, phải co về thanh đầu của nó.

    Hai nấc thu dựng ngày 06/10/2026 đều là **một class cộng một luật CSS**, và jsdom chỉ
    thấy được nửa đầu: test FE đo được rằng `.pane.thu` có mặt và vùng cuộn đã rời khỏi cây,
    nhưng không đo được rằng cái ngăn ấy **co lại**. Mà đúng chỗ đó có hai cái bẫy.

    `.rail .pane.history` là `flex: 1`. Thu nó mà không nói gì thì nó vẫn chiếm hết chỗ còn
    lại, và thanh đầu của nó trôi lên giữa một khoảng trắng cao 300px -- một ngăn "đã thu"
    chiếm đúng bằng lúc chưa thu. Nên `.rail .pane.thu` phải đặt lại `flex`.

    Và `.rail .pane` có `gap: 8px` giữa thanh đầu và vùng cuộn. Vùng cuộn đi rồi thì khoảng
    cách ấy thành 8px đệm chân không ai đặt, nên con số đo được là 35 chứ không phải **27**
    của Figma (`521:1767`). Nên luật ấy phải đặt lại `gap` nữa.

    Tấm trượt phát hành cùng một chuyện: `.teacher .publish-settings` có `padding: 20px`,
    còn variant `Trạng thái=thu` (`517:17`) đo 420x52 ở density Teacher, với padding 16/20.
    Thiếu luật thu thì thanh đầu cao 59,5 thay vì 51,5 đo được trên trình duyệt.

    Returns:
        None khi `teacher.css` còn cả hai luật, ngược lại là một thông báo thất bại.
    """
    sheet = REPO_ROOT / "services" / "fe" / "src" / "teacher.css"
    if not sheet.exists():
        return _fail("collapsed-panes-shrink", f"{sheet} is missing; the check cannot run")

    body = sheet.read_text(encoding="utf-8")

    pane = re.search(r"\.rail\s+\.pane\.thu\s*\{([^}]*)\}", body)
    if pane is None:
        return _fail(
            "collapsed-panes-shrink",
            "teacher.css must carry a `.rail .pane.thu` rule. `.pane.history` is `flex: 1`, "
            "so a collapsed pane keeps every pixel it had and its head floats in the middle "
            "of the empty space it still owns.",
        )
    declared = pane.group(1)
    for what, why in (
        (
            "flex",
            "`.pane.history` is `flex: 1`, so without `flex: none` a collapsed pane "
            "still fills the rail",
        ),
        (
            "gap",
            "`.rail .pane` has `gap: 8px` between the head and the scroller; with the "
            "scroller gone that gap becomes 8px of footer nobody asked for, and the "
            "pane measures 35 instead of the 27 Figma approved (`521:1767`)",
        ),
    ):
        if what not in declared:
            return _fail("collapsed-panes-shrink", f"`.rail .pane.thu` must set `{what}`: {why}.")

    if re.search(r"\.pane\.history\.thu\s*~\s*\.pane\.documents", body) is None:
        return _fail(
            "collapsed-panes-shrink",
            "teacher.css must give the still-open pane the leftover room in BOTH "
            "directions: `.rail .pane.history.thu ~ .pane.documents:not(.thu)` must set "
            "`flex: 1`. Collapsing the history pane otherwise leaves the documents pane "
            "pinned at 225 with ~368px of dead space under it -- measured in a real "
            "browser on 06/10/2026. The other direction is correct for free, because "
            "`.pane.history` is already `flex: 1`, so the bug shows up in one direction "
            "only and Figma drew the other one.",
        )

    if re.search(r"\.publish-settings\.thu\s*\{([^}]*)\}", body) is None:
        return _fail(
            "collapsed-panes-shrink",
            "teacher.css must carry a `.publish-settings.thu` rule carrying the padding of "
            "the approved `Trang thai=thu` variant (`517:17`, 420x52 at Teacher density, "
            "padding 16/20). Without it the collapsed sheet keeps `padding: 20px` and stands "
            "59,5 tall instead of the 51,5 measured in a real browser.",
        )
    return None


def check_a_locked_control_looks_locked() -> str | None:
    """Chip lớp đã khoá phải **nhìn thấy được** là đã khoá.

    Chip của một lớp đang giữ đề bị khoá, trong khi chip của lớp chưa nhận thì bấm được.
    `disabled` là một sự thật của DOM -- bàn phím bỏ qua, trình đọc màn hình đọc ra --
    nhưng **mắt thì không thấy gì cả**: một chip trông bấm được mà bấm không được là một
    chip nói dối, và lớp là tham số THỨ NHẤT của ADR-02 nên đó là chỗ tệ nhất để nói dối.

    jsdom không dựng bố cục và không tính style, nên không test FE nào đo nổi "mờ đi".
    Test chỉ khẳng định được `disabled === true`. Đây là cùng một khoảng mù đã sinh ra
    check 13 và 14.

    **Phạm vi hẹp lại ngày 07/10/2026.** Luật này từng phủ cả `input:disabled`, vì biểu
    mẫu khoá năm ô khi mọi lớp đã giữ đề. Nay đã khoá thì **không dựng ô nào**: năm cái ô
    diễn tả được một khung giờ, còn `publications` trả một khung **mỗi lớp**, nên việc
    điền ô chỉ đúng tình cờ lúc các lớp trùng giờ. Sự thật nay nằm ở khối `ĐÃ PHÁT HÀNH`,
    một khối mỗi lớp, đủ sáu thông số -- và `teacher.test.tsx` test được chỗ ấy vì nó là
    chữ, không phải style.

    Chip là control khoá duy nhất mà check **này** canh, không phải control khoá duy nhất
    của biểu mẫu: `Hoàn tác` và CTA cũng `disabled` được, và chúng đã có luật riêng
    (`.publish-settings .quiet:disabled`, `.publish-settings .cta:disabled`). Chúng không
    gộp vào đây vì một nút mờ đọc ra khác một ô mờ -- nút nói *"chưa tới lúc"*, còn ô và
    chip nói *"không phải chỗ của bạn"*.

    Luật tương ứng trên Figma: variant `Trạng thái=đã phát hành — khoá` của `Publish
    settings` (`67:41`), 420x456 ở density Teacher, chip trỏ `surface/sunken` +
    `ink/faint`.

    Returns:
        None khi `teacher.css` còn luật `:disabled`, ngược lại là một thông báo thất bại.
    """
    sheet = REPO_ROOT / "services" / "fe" / "src" / "teacher.css"
    if not sheet.exists():
        return _fail("locked-looks-locked", f"{sheet} is missing; the check cannot run")

    body = sheet.read_text(encoding="utf-8")

    rule = re.search(
        r"\.publish-settings[^{]*:disabled[^{]*\{([^}]*)\}",
        body,
    )
    if rule is None:
        return _fail(
            "locked-looks-locked",
            "teacher.css must style the publish form's locked controls, e.g. "
            "`.teacher .publish-settings .class-chip:disabled`. Without it a locked chip "
            "is indistinguishable from a live one, and the teacher clicks a class that "
            "silently refuses them.",
        )

    declared = rule.group(1)
    # Đòi đúng hai biến, không chỉ đòi hai tên thuộc tính: `background: transparent;
    # color: inherit` thoả phép kiểm cũ mà không có gì mờ đi.
    for what, token, why in (
        (
            "background",
            "--sunken",
            "the locked chip must sink into the surface the way the approved variant does",
        ),
        (
            "color",
            "--ink-faint",
            "the text of a locked chip must go faint, otherwise it reads as clickable",
        ),
    ):
        if re.search(rf"{what}\s*:[^;]*var\(\s*{token}\s*\)", declared) is None:
            return _fail(
                "locked-looks-locked",
                f"the `:disabled` rule of the publish form must set `{what}` to "
                f"`var({token})`: {why}. Naming the property without the token lets "
                "`transparent`/`inherit` pass while nothing actually dims.",
            )

    # Và chip lớp phải nằm trong cùng luật ấy: chip là tham số THỨ NHẤT của ADR-02, nên
    # một chip khoá mà trông bấm được là chỗ tệ nhất để nói dối.
    # Trong phạm vi `.publish-settings`, không phải ở bất kỳ đâu trong file: một khối rỗng
    # `.class-chip:disabled {}` ở cuối `teacher.css` cũng qua được phép kiểm cũ.
    if re.search(r"\.publish-settings\s+\.class-chip:disabled", body) is None:
        return _fail(
            "locked-looks-locked",
            "the locked treatment must cover `.class-chip:disabled` too. The class is the "
            "FIRST parameter of ADR-02 -- a chip that looks clickable but is not is the "
            "worst place in this form to lie.",
        )
    return None


def check_no_document_repeats_itself() -> str | None:
    """Không tài liệu `docs/` nào được lặp lại chính nó.

    Ngày 06/10/2026 một script sửa tài liệu cắt lát bằng hai `str.index()` mà **không** kiểm
    số lần xuất hiện. Một trong hai mốc có mặt ở hai chỗ, `index` trả về cái đầu tiên, lát
    cắt thành **rỗng** -- và `str.replace("", block)` chèn `block` vào giữa **mọi ký tự** của
    file. `docs/kich-ban-thu-tay-giao-vien.md` thành **81 MB / 889.029 dòng**, với một khối
    1.729 ký tự lặp 37.013 lần.

    Cả `check`, `pytest`, `vitest` lẫn `typecheck` đều xanh suốt. Không cổng nào nhìn vào
    `docs/`, nên cách duy nhất phát hiện là có người mở file ra đọc. Đó là một lớp lỗi, không
    phải một lần sơ ý: mọi script sửa tài liệu trong repo này đều dùng `str.replace`, và một
    `old` rỗng luôn cho ra cùng một thảm hoạ.

    Phép kiểm rẻ nhất bắt được đúng hình dạng ấy: chia file thành các khối 400 ký tự và đếm
    khối trùng. Một tài liệu viết tay có lặp -- mẫu câu, bảng, khối code -- nhưng không tài
    liệu nào lặp **quá nửa** số khối của nó.

    Kèm một trần kích thước, vì một file vài chục MB thì ngay cả phép đếm trên cũng đã chậm.

    Returns:
        None khi mọi tài liệu còn lành, ngược lại là một thông báo thất bại.
    """
    docs = REPO_ROOT / "docs"
    if not docs.is_dir():
        return _fail("documents-do-not-repeat", f"{docs} is missing; the check cannot run")

    CEILING = 400_000
    WINDOW = 400

    for path in sorted(docs.rglob("*.md")):
        size = path.stat().st_size
        where = path.relative_to(REPO_ROOT).as_posix()
        if size > CEILING:
            return _fail(
                "documents-do-not-repeat",
                f"{where} is {size:,} bytes, over the {CEILING:,} ceiling. No hand-written "
                "document in this repo is that long; a size like this means a script wrote "
                "it in a loop.",
            )

        body = path.read_text(encoding="utf-8")
        blocks = [body[at : at + WINDOW] for at in range(0, len(body), WINDOW)]
        if len(blocks) < 8:
            continue
        unique = len(set(blocks))
        if unique * 2 < len(blocks):
            return _fail(
                "documents-do-not-repeat",
                f"{where} has only {unique} distinct {WINDOW}-character blocks out of "
                f"{len(blocks)}: more than half of the file is a copy of itself. That is "
                'the shape a `str.replace("", block)` leaves behind when a slice meant to '
                "select the old text came out empty.",
            )
    return None


def _no_comments(source: str) -> str:
    """Bỏ comment `//` và `/* */` của một file TypeScript, giữ nguyên độ dài dòng."""
    without_block = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//.*", "", without_block)


def _service_sources() -> list[Path]:
    """Mọi file Python **của chúng ta** dưới `services/` và `packages/`.

    Lọc `node_modules` chứ không tin rằng nó không có Python: `services/fe/node_modules` có
    năm file `.py` của katex, và chúng đã từng lọt vào vùng quét của hai check dưới. Lúc ấy
    không ai thấy gì vì năm file kia tokenize được — nhưng một `npm install` kéo về một
    package kèm script py2 hay một file không phải utf-8 là `dev.ps1 check` **chết bằng stack
    trace**, không phải bằng một dòng FAIL, và người đọc sẽ tưởng `check_contract.py` hỏng.

    Chỉ lấy dưới `src/`, nên `tests/` nằm ngoài vùng quét của mọi luật dùng hàm này.

    Returns:
        Đường dẫn tuyệt đối, đã sắp xếp.
    """
    roots = (REPO_ROOT / "services", REPO_ROOT / "packages")
    return sorted(
        path
        for root in roots
        for path in root.rglob("src/**/*.py")
        if "node_modules" not in path.parts and "__pycache__" not in path.parts
    )


def check_one_process_builds_the_schema_and_the_rest_only_check_it() -> str | None:
    """Dựng schema, và xoá nó, mỗi việc có đúng những chỗ được phép.

    Luật này mới cần tới một cái lưới từ `ingest-service-split`, và nó cần vì một lý do cụ thể:
    trước đó `prepare_schema` nằm trong `be/db.py`, một module mà chỉ `services/be` import được, nên
    "ai được dựng schema" là một câu hỏi ranh giới service đã trả lời hộ. Nay nó ở
    `packages/schema`, dùng chung — và `services/ingest` import được nó như BE.

    Vì sao chỉ một process dựng: `create_all` không bao giờ `ALTER`, nên hai process cùng dựng
    là hai process cùng tin mình đúng về một schema chỉ một bên nhìn đủ. Và worker khởi động
    được **trước** API, nên nó sẽ dựng theo bản metadata nó đang có. Process nào cũng gọi
    `check_schema` rồi chết ngay nếu lệch; nửa ấy được canh bằng test, không bằng check này.

    **Canh ba thứ, không một.** Bản đầu chỉ canh cái tên `prepare_schema`, và một lượt review
    đã chỉ ra hai đường vòng đi qua được mà hậu quả thì nặng hơn hẳn:

    - `await reset_schema(engine)` — nó gọi `prepare_schema` hộ, **và `DROP SCHEMA public
      CASCADE` trước đó**. Một worker gọi nhầm hàm ấy là một database bị xoá sạch, im lặng.
    - `Base.metadata.create_all` viết tay — đúng *chính xác* thứ `prepare_schema` làm, chỉ là
      không mang cái tên ấy. Canh một cái tên thì không canh được một hành vi.

    Vùng quét **không gồm `tests/`** (chỉ `src/`), và đó không phải lỗ hổng: một test dựng một
    sqlite trong bộ nhớ của riêng nó, và cái database ấy không phải schema của ai. Mười sáu
    file test làm đúng thế, trong đó có cả `services/ingest/tests/` — tức chính service bị cấm
    dựng schema. Miễn trừ ấy là chỗ đắt nhất của luật này, nên nó được bù bằng một test riêng
    ở `services/ingest/tests/test_worker.py`: `ingest.worker` chỉ được lấy `check_schema` từ
    `schema.ddl` và không được lấy gì khác, kể cả dưới một cái tên khác.

    Returns:
        None khi check đạt, ngược lại là một thông báo thất bại kèm tên các file.
    """
    ddl = Path("packages") / "schema" / "src" / "schema" / "ddl.py"
    seams = (
        # (tên luật, cái cần tìm, những chỗ được phép)
        (
            "prepare_schema",
            re.compile(r"\bprepare_schema\s*\("),
            (Path("services") / "be" / "src" / "be" / "main.py", ddl),
        ),
        (
            "reset_schema",
            re.compile(r"\breset_schema\s*\("),
            (Path("services") / "be" / "src" / "be" / "reset_db.py", ddl),
        ),
        (
            "metadata.create_all / metadata.drop_all",
            re.compile(r"\bmetadata\.(create_all|drop_all)\b"),
            (ddl,),
        ),
    )

    problems = []
    for path in _service_sources():
        relative = path.relative_to(REPO_ROOT)
        try:
            lines = _code_only(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, tokenize.TokenError, SyntaxError) as unreadable:
            # Một dòng FAIL, không một traceback: cái hỏng là một file, không phải check này.
            problems.append(f"{relative}: cannot be read as Python ({unreadable})")
            continue
        for name, pattern, allowed in seams:
            if relative in allowed:
                continue
            for number, line in enumerate(lines, 1):
                if pattern.search(line):
                    problems.append(f"{relative}:{number} uses {name}")

    if problems:
        return _fail(
            "one-schema-builder",
            "\n      ".join(problems)
            + "\n      The API process builds the schema; every other process calls "
            "check_schema and dies on drift.",
        )
    return None


def check_both_sides_of_the_document_channel_read_its_name_from_contracts() -> str | None:
    """Tên channel pub/sub sống ở `contracts`, và hai bên **gọi** nó chứ không viết lại.

    `services/ingest` phát, `services/be` nghe, và hai service ấy **không import nhau được**.
    Nên cái string là ranh giới, và `packages/contracts/AGENTS.md` ghi thẳng:
    *"that constant is the boundary, not a convenience."*

    Vì sao đáng một cái lưới riêng thay vì tin vào review: một bản sao ở mỗi bên là hai chuỗi
    lệch nhau được, và **lúc lệch thì không có lỗi nào** — `publish` vào một channel không ai
    nghe thành công y như một channel có người nghe. Triệu chứng duy nhất là chip thôi tự đổi
    mặt, tức một màn hình trông như đang chạy đúng, và đó là loại hỏng đắt nhất để truy.

    **Hai nửa, vì một nửa thì thủng.** Nửa đầu cấm viết chuỗi `documents:` ra ngoài
    `contracts`. Một lượt review đã chỉ ra nó chỉ bắt đúng một hình dạng: tách dấu hai chấm ra
    khỏi chữ — một hằng số tiền tố rồi nối, một phép `+`, một `":".join(...)` — là đi qua hết,
    và cách đầu tiên là cách một người **sẽ** viết nếu họ muốn cho gọn. Nên nửa sau canh chiều
    ngược lại: hai module chạm kênh phải **còn gọi** `documents_channel`. Mọi cách viết tay
    đều phải bỏ lời gọi ấy đi, nên nửa sau bắt được cả bảy cách mà nửa đầu bỏ sót.

    **Hệ quả phải biết trước:** tên channel không được viết ra trong `services/` hay
    `packages/` kể cả **trong một comment hay docstring**. Check này đọc dòng thô, vì
    `_code_only` xoá trắng string literal — tức xoá đúng thứ cần tìm. Muốn nhắc tới kênh trong
    một lời giải thích thì gọi tên hàm `documents_channel`, đừng chép giá trị của nó.

    Vùng quét **không gồm `tests/`**: một test khẳng định `documents_channel` trả ra đúng chuỗi
    nào thì **phải** viết chuỗi ấy ra, nếu không nó chỉ so một hàm với chính nó.

    Returns:
        None khi check đạt, ngược lại là một thông báo thất bại kèm tên các file.
    """
    home = Path("packages") / "contracts" / "src" / "contracts" / "documents.py"
    written = re.compile(r"""["']documents:""")
    # Hai module chạm kênh, mỗi bên một đầu. Thêm một bên thứ ba thì thêm một dòng ở đây.
    touching = (
        Path("services") / "ingest" / "src" / "ingest" / "events.py",
        Path("services") / "be" / "src" / "be" / "document_events.py",
    )

    problems = []
    for path in _service_sources():
        relative = path.relative_to(REPO_ROOT)
        if relative == home:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if written.search(line):
                problems.append(f"{relative}:{number} writes the channel name out")

    for relative in touching:
        path = REPO_ROOT / relative
        if not path.is_file():
            problems.append(f"{relative} is gone; this check names the modules that touch it")
            continue
        if "documents_channel(" not in path.read_text(encoding="utf-8"):
            problems.append(f"{relative} no longer calls documents_channel")

    if problems:
        return _fail(
            "one-channel-name",
            "\n      ".join(problems)
            + f"\n      Call contracts.documents_channel, defined in {home}; a second copy of "
            "the string is a channel that goes quiet without an error.",
        )
    return None


def check_only_one_module_per_service_talks_to_a_sync_sdk() -> str | None:
    """Hai SDK sync, mỗi cái đúng một module được import nó.

    SDK của MinIO là **sync**, còn BE là async, nên mỗi lời gọi phải đi qua
    `run_in_threadpool`. Một lời gọi quên bọc không ném gì cả: nó chặn event loop suốt
    thời gian đẩy một file lên, và triệu chứng duy nhất là cả process chậm đi trong lúc
    một người nào đó tải sách. Không có lưới nào khác bắt được hình dạng ấy -- test chạy
    trên bản in-memory thì không có gì để chặn.

    Gom mọi lời gọi vào một module biến luật "nhớ bọc thread" thành luật "nhớ đừng import",
    và luật thứ hai thì grep được.

    PyMuPDF cùng hình dạng và gắt hơn một chút: nó **sync và CPU-bound**, còn arq chạy tới
    `max_jobs` job đồng thời, nên một lần quên là chín job kia đứng chờ một cuốn sách được
    quét xong.

    Vùng quét **không gồm `tests/`**, và đó không phải một lỗ hổng: luật này nói về việc chặn
    một event loop lúc chạy, mà một test thì sync và không có event loop nào để chặn. Nó cũng
    không phải một lựa chọn cho tiện tay -- `test_probe.py` **phải** import `pymupdf`, vì nó
    dựng cả PDF chữ lẫn PDF scan ngay lúc chạy thay vì cất hai file nhị phân vào git.

    Chủ của seam pymupdf đổi ngày 10/10/2026: từ `probe.py` sang `pdf.py`. Đường OCR cần dựng ảnh
    một trang, và việc ấy không thuộc một module chính sách. Danh sách vẫn **đúng một** file --
    nới nó thành hai là đổi một luật grep được thành một luật phải nhớ.

    `pymongo` vào danh sách ngày 11/10/2026 (`mongo-content-store`, D2), dù client async của nó
    **không** chặn event loop: tên của check này hẹp hơn luật nó canh. Luật thật là *một SDK chạm
    kho, một module* -- và với kho nội dung, module ấy là nơi duy nhất phải trả lời câu *"nội dung
    có được ghi trước khi `state` đổi không"*.

    `document-agent-hierarchy` thêm ba cửa nữa theo cùng luật: `typesafe_sdk` (Jev) chỉ ở
    `index/jev.py`, `langchain` trong `document` chỉ ở `index/llm.py` -- nơi duy nhất truyền khoá
    vào client -- và BE cùng `ingest` **không** import SDK model nào: chỉ `agent` và `document` gọi
    model provider.

    Returns:
        None khi check đạt, ngược lại là một thông báo thất bại kèm tên các file.
    """
    seams = (
        (
            "minio",
            MINIO_IMPORT,
            (
                REPO_ROOT / "services" / "be" / "src" / "be" / "storage.py",
                REPO_ROOT / "services" / "document" / "src" / "document" / "storage.py",
            ),
            ("be", "document"),
        ),
        (
            "pymupdf",
            PYMUPDF_IMPORT,
            (REPO_ROOT / "services" / "document" / "src" / "document" / "pdf.py",),
            ("document",),
        ),
        (
            # Hai file, cả hai được gọi qua `asyncio.to_thread` (`ocr_handlers.py`). File thứ ba
            # import paddle là check đỏ: đi qua một trong hai (Tier 2 câu 16 = A, 21/10/2026).
            "paddleocr",
            PADDLE_IMPORT,
            (
                REPO_ROOT / "services" / "document" / "src" / "document" / "ocr" / "layout.py",
                REPO_ROOT / "services" / "document" / "src" / "document" / "ocr" / "textline.py",
            ),
            ("document",),
        ),
        (
            "pymongo",
            PYMONGO_IMPORT,
            (
                REPO_ROOT / "services" / "document" / "src" / "document" / "content_store.py",
                REPO_ROOT / "services" / "be" / "src" / "be" / "content_reader.py",
            ),
            # Quét **cả bốn** service, không chỉ `document`: `ingest` và AGENT không giữ khoá Mongo
            # (`mongo-content-store`, D1), và review Task 1 chỉ ra không gì canh điều đó --
            # `agent-no-db` chỉ quét AGENT và `document`. `document-agent-hierarchy` mở thêm một cửa
            # cho document agent ở đây; `draft-from-document` mở cửa **chỉ đọc** cho BE
            # (`content_reader.py`), và `check_the_content_reader_only_reads` giữ chữ *chỉ đọc*.
            ("be", "agent", "document", "ingest"),
        ),
        (
            # Jev (`document-agent-hierarchy`, D1): một module hỏi Jev, nên một chỗ giữ thứ tự lựa
            # chọn và tiêu chí -- thứ bộ đo đã hiệu chỉnh ngưỡng trên đó. `kriky-skill-routing` mở
            # cửa thứ hai, cùng luật: một module **mỗi service** -- AGENT hỏi Jev chọn skill cho
            # Kriky ở `skill_router.py`.
            "typesafe_sdk",
            TYPESAFE_IMPORT,
            (
                _INDEX / "jev.py",
                REPO_ROOT / "services" / "agent" / "src" / "agent" / "skill_router.py",
            ),
            ("be", "agent", "document", "ingest"),
        ),
        (
            # Model sinh chữ của document agent (D6, `document-agent-hierarchy`, D9): một module
            # truyền khoá vào client, đúng bài học của `agent/llm.py`. Chỉ quét `document`: AGENT có
            # seam của riêng nó.
            "langchain",
            LANGCHAIN_IMPORT,
            (_INDEX / "llm.py",),
            ("document",),
        ),
        (
            # BE và `ingest` không gọi model nào -- *"chỉ `agent` và `document` gọi model
            # provider"*, Decision Record Jev của plan ô. Không có nhà nào được phép.
            "a model SDK",
            MODEL_SDK_IMPORT,
            (),
            ("be", "ingest"),
        ),
    )

    problems = []
    for sdk, pattern, allowed, services in seams:
        offenders = []
        for service in services:
            for path in (REPO_ROOT / "services" / service).rglob("*.py"):
                if "__pycache__" in path.parts or "tests" in path.parts or path in allowed:
                    continue
                if pattern.search(path.read_text(encoding="utf-8")):
                    offenders.append(str(path.relative_to(REPO_ROOT)))
        if offenders and not allowed:
            problems.append(f"{sdk} is imported in {', '.join(services)}: {sorted(offenders)}")
        elif offenders:
            homes = ", ".join(str(one.relative_to(REPO_ROOT)) for one in allowed)
            problems.append(f"{sdk} is imported outside {homes}: {sorted(offenders)}")

    if problems:
        return _fail(
            "sync-sdk-seam",
            f"{'; '.join(problems)}. Go through the seam: one SDK, one module -- and no model SDK"
            " in BE or ingest.",
        )
    return None


# Mọi phương thức ghi của collection `pymongo`. Module đọc kho nội dung của BE không được gọi cái
# nào.
_MONGO_WRITE = re.compile(
    r"\.(?:insert_one|insert_many|update_one|update_many|replace_one|delete_one|delete_many"
    r"|find_one_and_\w+|bulk_write|drop|drop_collection|drop_database|create_index|create_indexes"
    r"|drop_index|rename|command)\s*\("
    # `aggregate` đọc được, trừ khi pipeline của nó ghi ra một collection (review B2,
    # `draft-from-document`).
    r"|[\"']\$(?:out|merge)[\"']"
)


def check_the_content_reader_only_reads() -> str | None:
    """BE đọc kho nội dung, không bao giờ ghi (`draft-from-document`).

    Kho nội dung do `services/document` ghi; sự thật về tài liệu ở Postgres, do `ingest` ghi.
    `draft-from-document` cho BE **đọc** mục lục và đoạn để soạn đề, qua đúng một module
    (`sync-sdk-seam` giữ chữ *một module*). Check này giữ chữ *đọc*: một lời gọi ghi trong module ấy
    làm BE thành người ghi thứ hai của một kho mà nó không sở hữu, và cây mục lục sẽ có hai tác giả
    không biết nhau.

    Returns:
        None khi check đạt, ngược lại là một thông báo thất bại.
    """
    reader = REPO_ROOT / "services" / "be" / "src" / "be" / "content_reader.py"
    if not reader.exists():
        return _fail("content-reader", f"{reader.relative_to(REPO_ROOT)} is missing")
    found = sorted(
        {
            match.group(0).strip(".( ")
            for match in _MONGO_WRITE.finditer(reader.read_text(encoding="utf-8"))
        }
    )
    if found:
        return _fail(
            "content-reader",
            f"be/content_reader.py calls {found}: BE only reads the content store,"
            " services/document writes it",
        )
    return None


# Luật của `document-debts-and-comment-codes` (người dùng chốt 14/10/2026): bốn dạng mã chỉ người
# đã đọc plan mới giải được -- mã task (*"T4"*, *"review Task 3"*), nhãn ô đợt (*"plan 3c"*), mã
# quyết định (*"D9"*), mã pipeline hay mã review (*"B10"*, *"C4"*).
_PLAN_CODE = re.compile(
    r"\b(?:Task \d+[a-z]?|T\d+[a-z]?|[Pp]lan \d[a-z]?|D\d{1,2}|[BC]\d{1,2})\b(?![-.]\d)"
)
_PLAN_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)-plan\.md$")


def _plan_slugs() -> set[str]:
    """Tên ngắn của mọi plan có file: tên file bỏ ngày và `-plan.md`.

    Returns:
        Các slug, vd. `document-agent-hierarchy`.
    """
    return {
        found.group(1)
        for path in (REPO_ROOT / "docs" / "plans").rglob("*.md")
        if (found := _PLAN_FILE.match(path.name))
    }


def comment_blocks(source: str, suffix: str) -> list[tuple[int, list[str]]]:
    """Các khối comment của một file nguồn, mỗi khối là một lời dẫn liền mạch. Hàm thuần.

    - Python: các dòng comment `#` liền nhau gộp một khối; mỗi **docstring thật** (câu đầu của
      module, class, hàm -- đọc bằng `ast`) là một khối. Chuỗi ba nháy khác -- prompt gửi model,
      dữ liệu test -- **không** phải comment: bắt người ta nhét slug vào chữ model đọc là đổi
      prompt.
    - TypeScript, CSS: mỗi `/* */` một khối; các dòng `//` liền nhau gộp một khối. `//` đứng sau
      `:` không tính, để một URL trong chuỗi không thành comment.

    Args:
        source: Nội dung file.
        suffix: Đuôi file, `.py`, `.ts`, `.tsx` hay `.css`.

    Returns:
        (số dòng đầu, các dòng của khối), theo thứ tự trong file.
    """
    lines = source.splitlines()
    blocks: list[tuple[int, list[str]]] = []
    if suffix == ".py":
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(
                node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            ):
                continue
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                blocks.append((first.lineno, lines[first.lineno - 1 : first.end_lineno]))
        run: list[str] = []
        start = 0
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type != tokenize.COMMENT:
                continue
            row = token.start[0]
            if run and row == start + len(run):
                run.append(token.string)
                continue
            if run:
                blocks.append((start, run))
            start, run = row, [token.string]
        if run:
            blocks.append((start, run))
        return sorted(blocks)
    for block in re.finditer(r"/\*.*?\*/", source, flags=re.DOTALL):
        first = source.count("\n", 0, block.start()) + 1
        blocks.append((first, block.group(0).splitlines()))
    if suffix != ".css":
        run, start = [], 0
        for number, line in enumerate(lines, 1):
            inline = re.search(r"(?<![:\w])//.*", line)
            if inline is not None and run and number == start + len(run):
                run.append(inline.group(0))
            elif inline is not None:
                if run:
                    blocks.append((start, run))
                start, run = number, [inline.group(0)]
        if run:
            blocks.append((start, run))
    return sorted(blocks)


def codes_without_a_plan(
    blocks: list[tuple[int, list[str]]], slugs: set[str]
) -> list[tuple[int, str]]:
    """Những khối comment có mã plan mà không có slug plan nào. Hàm thuần.

    Đơn vị là **khối**, không phải dòng: một lời dẫn có thể bị cắt xuống dòng giữa *"plan"* và
    *"4b"*, hay giữa mã và tên plan, nên các dòng được nối lại trước khi so. Một khối nêu tên plan
    một lần là đủ cho mọi mã trong nó.

    Args:
        blocks: Kết quả của `comment_blocks`.
        slugs: Slug của mọi plan có file.

    Returns:
        (số dòng của mã đầu tiên, mã ấy) cho mỗi khối vi phạm.
    """
    bad = []
    for start, lines in blocks:
        # Gộp mọi khoảng trắng: một nhãn bị cắt dòng trong docstring thụt lề thành chữ *"plan"*,
        # một dải khoảng trắng, rồi số -- còn mẫu mã chỉ chờ đúng một dấu cách.
        joined = re.sub(
            r"\s+", " ", " ".join(re.sub(r"^\s*(#|//|/?\*+/?)\s?", "", line) for line in lines)
        )
        if any(slug in joined for slug in slugs):
            continue
        for offset, line in enumerate(lines):
            if (found := _PLAN_CODE.search(line)) is not None:
                bad.append((start + offset, found.group(0)))
                break
        else:
            if (found := _PLAN_CODE.search(joined)) is not None:
                bad.append((start, found.group(0)))
    return bad


def _commented_sources() -> list[Path]:
    """Mọi file nguồn của chúng ta có comment: Python ở `services/`, `packages/`, `tools/`, và
    TypeScript, CSS của FE. Gồm cả `tests/`: một test sống lâu như code nó canh.

    Returns:
        Đường dẫn tuyệt đối, đã sắp xếp.
    """
    found = [
        path
        for root in ("services", "packages", "tools")
        for path in (REPO_ROOT / root).rglob("*.py")
        if "node_modules" not in path.parts and "__pycache__" not in path.parts
    ]
    fe = REPO_ROOT / "services" / "fe" / "src"
    found += [path for pattern in ("*.ts", "*.tsx", "*.css") for path in fe.rglob(pattern)]
    return sorted(found)


def check_plan_codes_in_comments_name_their_plan() -> str | None:
    """Một mã plan trong comment phải đi kèm tên plan của nó.

    Luật tên bền của `AGENTS.md` từng chỉ nói về **tên** -- id ca đo, nhãn lượt đo, tên file.
    Người dùng chốt 14/10/2026 (`document-debts-and-comment-codes`) áp nó cho cả lời dẫn trong
    comment: *"(review Task 4)"* hay *"(plan 3c, D3)"* chỉ giải được khi biết đó là plan nào, và
    khi plan đã đóng thì không ai nhớ. Kèm slug -- tên file plan bỏ ngày -- là đủ để mở đúng file
    ra đọc.

    Returns:
        None khi mọi khối có mã đều nêu tên plan, ngược lại là một thông báo thất bại.
    """
    slugs = _plan_slugs()
    bad = []
    for path in _commented_sources():
        blocks = comment_blocks(path.read_text(encoding="utf-8"), path.suffix)
        where = path.relative_to(REPO_ROOT).as_posix()
        bad += [f"{where}:{number} {code}" for number, code in codes_without_a_plan(blocks, slugs)]
    if not bad:
        return None
    shown = "\n  ".join(bad[:20])
    more = f"\n  ... and {len(bad) - 20} more" if len(bad) > 20 else ""
    return _fail(
        "plan-codes-name-their-plan",
        f"{len(bad)} comment blocks carry a plan code but no plan slug (write the plan file name "
        f"without its date, e.g. `document-agent-hierarchy`):\n  {shown}{more}",
    )


# Kind nào của mỗi lời gọi là **lời Kriky** -- chỗ ADR-30 cấm code đặt chữ cố định. `notice` và
# `done` không nằm đây: `notice` là thông báo hệ thống (ngoại lệ 1), `done` chỉ chở lại chữ của sự
# kiện trước nó. `NextStepCompleted` là lời model viết, nên mọi kind đều tính -- trừ khi lời gọi tự
# khai `notice=True`.
_KRIKY_KINDS = {
    "TurnEvent": {"say", "clarify", "outline", "report"},
    "TurnRecord": {"assistant", "outline"},
    "NextStepCompleted": None,
}

# Đường lùi về chế độ demo: gọi chúng trong một `except` của handler gọi model là để mock nói thay
# model đang hỏng (ADR-30). Gọi khi `LLM_ENABLED=false` thì đúng là chế độ demo, không bị soi.
_MOCK_SPEAKERS = {"next_step"}


def _module_strings(tree: ast.Module) -> set[str]:
    """Tên các hằng chữ ở tầng module: `_X = "..."`, kể cả chuỗi nối trong ngoặc."""
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(value, (ast.Constant, ast.JoinedStr)) and (
                isinstance(value, ast.JoinedStr) or isinstance(value.value, str)
            ):
                found |= {one.id for one in targets if isinstance(one, ast.Name)}
    return found


def _assigned(function: ast.AST) -> dict[str, list[ast.expr]]:
    """Mọi giá trị từng gán cho mỗi tên cục bộ của một hàm: `x = ...` và `x: T = ...`."""
    found: dict[str, list[ast.expr]] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.setdefault(target.id, []).append(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and isinstance(node.target, ast.Name)
        ):
            found.setdefault(node.target.id, []).append(node.value)
    return found


def _fixed(node: ast.expr | None, constants: set[str], local: dict, seen: frozenset = frozenset()):
    """Biểu thức có thể cho ra một câu cố định không: literal khác rỗng, f-string, hằng chữ, hằng
    ấy `.format(...)`, hay một nhánh `or` / `if…else` / `+` là một trong số đó -- kể cả qua một biến
    cục bộ từng được gán như vậy."""
    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and node.value != ""
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Name):
        if node.id in constants:
            return True
        if node.id in seen:
            return False
        return any(
            _fixed(one, constants, local, seen | {node.id}) for one in local.get(node.id, ())
        )
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "format" and _fixed(node.func.value, constants, local, seen)
    if isinstance(node, ast.BoolOp):
        return any(_fixed(one, constants, local, seen) for one in node.values)
    if isinstance(node, ast.IfExp):
        return _fixed(node.body, constants, local, seen) or _fixed(
            node.orelse, constants, local, seen
        )
    if isinstance(node, ast.BinOp):
        return _fixed(node.left, constants, local, seen) or _fixed(
            node.right, constants, local, seen
        )
    return False


def _kinds_named(node: ast.expr | None, local: dict) -> set[str] | None:
    """Mọi chuỗi kind một biểu thức có thể cho ra -- `"a" if x else "b"` cho cả hai, một biến cục bộ
    cho mọi giá trị từng gán. `None` khi không đọc ra được chuỗi nào: kind không biết thì có thể là
    lời Kriky."""
    if node is None:
        return None
    found: set[str] = set()
    pending = [node]
    names_seen: set[str] = set()
    while pending:
        current = pending.pop()
        for one in ast.walk(current):
            if isinstance(one, ast.Constant) and isinstance(one.value, str):
                found.add(one.value)
            elif isinstance(one, ast.Name) and one.id not in names_seen:
                names_seen.add(one.id)
                pending += local.get(one.id, [])
    return found or None


def _text_given(node: ast.Call) -> tuple[str, ast.expr | None, dict[str, ast.expr]] | None:
    """Tên lời gọi, `text` nó nhận, và các keyword của nó -- cho constructor của lời Kriky, hay
    `x.model_copy(update={"text": ...})`. `None` khi lời gọi không chở lời nào."""
    given = {one.arg: one.value for one in node.keywords if one.arg}
    called = getattr(node.func, "id", getattr(node.func, "attr", ""))
    if called in _KRIKY_KINDS:
        return called, given.get("text"), given
    update = given.get("update")
    if called == "model_copy" and isinstance(update, ast.Dict):
        for key, value in zip(update.keys, update.values, strict=True):
            if isinstance(key, ast.Constant) and key.value == "text":
                return "model_copy", value, {}
    return None


def fixed_kriky_words(
    source: str, notices: set[str], within: set[str] | None = None
) -> list[tuple[int, str]]:
    """Những chỗ code đặt một câu cố định vào lời Kriky (ADR-30). Hàm thuần.

    Bắt: một `TurnEvent`/`TurnRecord` với kind có thể là lời Kriky (kể cả kind không đọc ra được),
    một `NextStepCompleted` không khai `notice=True`, hay một
    `model_copy(update={"text": ...})`, mà `text` có thể là câu cố định (`_fixed`); và một lời gọi
    mock (`_MOCK_SPEAKERS`) trong một `except`. Câu của `notices` cũng là câu cố định: chúng chỉ
    được đi dưới `kind="notice"`.

    Không bắt -- chấp nhận được cho một check thô có chủ ý: câu cố định một hàm khác **trả về** rồi
    mới tới constructor (`_report` cũ trả `written or fallback`), `**kwargs`, và biến gán qua nhiều
    hàm. Test của mỗi hàm ấy giữ phần còn lại.

    Args:
        source: Mã nguồn Python.
        notices: Tên các câu hệ thống (`be/notices.py`).
        within: Chỉ soi thân các hàm tầng module mang những tên này; `None` là mọi hàm.

    Returns:
        `(dòng, chữ dẫn)` cho mỗi chỗ vi phạm.
    """
    tree = ast.parse(source)
    constants = _module_strings(tree) | notices
    functions = [
        one
        for one in (tree.body if within is not None else ast.walk(tree))
        if isinstance(one, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (within is None or one.name in within)
    ]
    bad = set()
    for function in functions:
        local = _assigned(function)
        for node in ast.walk(function):
            if isinstance(node, ast.ExceptHandler):
                for inner in ast.walk(node):
                    if (
                        isinstance(inner, ast.Call)
                        and getattr(inner.func, "id", "") in _MOCK_SPEAKERS
                    ):
                        bad.add((inner.lineno, f"{inner.func.id}() in an except: the mock speaks"))
            if not isinstance(node, ast.Call):
                continue
            found = _text_given(node)
            if found is None:
                continue
            called, text, given = found
            notice = given.get("notice")
            if isinstance(notice, ast.Constant) and notice.value is True:
                continue
            wanted = _KRIKY_KINDS.get(called)
            kinds = _kinds_named(given.get("kind"), local)
            if wanted is not None and kinds is not None and not kinds & wanted:
                continue
            if _fixed(text, constants, local):
                bad.add((node.lineno, f"{called}(text={ast.unparse(text)[:40]})"))
    return sorted(bad)


def _notice_names() -> set[str]:
    """Các câu hệ thống của `be/notices.py` -- chỉ được đi dưới `kind="notice"`."""
    notices = REPO_ROOT / "services" / "be" / "src" / "be" / "notices.py"
    return _module_strings(ast.parse(notices.read_text(encoding="utf-8")))


def check_kriky_says_nothing_fixed() -> str | None:
    """Mọi lời Kriky do model viết; code chỉ nói được bằng thông báo hệ thống (ADR-30).

    Người dùng chốt 17/10/2026 (`kriky-writes-every-word`): câu cố định nói dưới giọng Kriky là code
    nói thay model. Chỗ một câu như thế quay lại là các hàm dựng lượt -- `_go` của BE, graph
    `propose`, và handler gọi model của AGENT. Ngoại lệ có tên: câu của `be/notices.py` dưới
    `kind="notice"`, và lời AGENT tự khai `notice=True` khi model không có mặt. Chế độ demo không
    model (`handlers.next_step`, kể cả `_telling` của lượt kể lại, khi `LLM_ENABLED=false`) là
    ngoại lệ ADR-30 ghi, nên của `handlers.py` chỉ `propose_next_step` bị soi. Dạng nào check không
    bắt: xem `fixed_kriky_words`.

    Returns:
        None khi luật còn đứng, ngược lại là một thông báo thất bại gọi tên từng chỗ.
    """
    notices = _notice_names()
    agent = REPO_ROOT / "services" / "agent" / "src" / "agent"
    # Graph `propose` là một package (plan `split-propose-package`): soi mọi file của nó, và một
    # hằng chữ khai ở file này mà dùng ở file kia vẫn là câu cố định.
    package = sorted((agent / "graphs" / "propose").rglob("*.py"))
    if not package:
        return _fail(
            "kriky-says-nothing-fixed",
            f"{agent / 'graphs' / 'propose'} has no Python file: the check would skip the graph "
            "that speaks for Kriky. Point it at where propose lives now.",
        )
    shared = set().union(
        *(_module_strings(ast.parse(one.read_text(encoding="utf-8"))) for one in package)
    )
    files = (
        (REPO_ROOT / "services" / "be" / "src" / "be" / "teacher_chat.py", None, notices),
        *((one, None, notices | shared) for one in package),
        (agent / "handlers.py", {"propose_next_step"}, notices),
    )
    bad = []
    for path, within, known in files:
        where = path.relative_to(REPO_ROOT).as_posix()
        found = fixed_kriky_words(path.read_text(encoding="utf-8"), known, within)
        bad += [f"{where}:{line} {what}" for line, what in found]
    if not bad:
        return None
    shown = "\n  ".join(bad)
    return _fail(
        "kriky-says-nothing-fixed",
        "code puts a fixed sentence in Kriky's mouth (ADR-30). Let the model write it, or make it "
        f"a system notice in be/notices.py under kind='notice' / mark it notice=True:\n  {shown}",
    )


# Thư viện mở một cổng HTTP. `document` nhận việc qua queue và trả lời qua queue, nên không file
# nào của nó được import một trong số này (`services/document/AGENTS.md`).
HTTP_SERVERS = frozenset(
    {
        "fastapi",
        "starlette",
        "uvicorn",
        "flask",
        # `aiohttp.web` chứ không cả `aiohttp`: client của nó gọi ra ngoài, không mở cổng nào.
        "aiohttp.web",
        "http.server",
        "socketserver",
        "wsgiref",
        "tornado",
        "hypercorn",
        "prometheus_client.start_http_server",
        "prometheus_client.start_wsgi_server",
        "prometheus_client.exposition",
        "asyncio.start_server",
    }
)
# Lời gọi mở một cổng mà không cần import thư viện server nào (`asyncio.start_server`).
SERVER_CALLS = frozenset(
    {"start_server", "create_server", "start_http_server", "start_wsgi_server", "run_app"}
)


def http_servers_imported(source: str) -> list[int]:
    """Các dòng import một thư viện mở cổng HTTP (`HTTP_SERVERS`), hay một module con của nó, hay
    gọi một hàm mở cổng (`SERVER_CALLS`).

    Args:
        source: Mã nguồn Python.

    Returns:
        Số dòng của từng import như thế; rỗng khi không có.
    """

    def serving(name: str) -> bool:
        return any(name == one or name.startswith(f"{one}.") for one in HTTP_SERVERS)

    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import) and any(serving(alias.name) for alias in node.names):
            lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
            if any(serving(name) for name in names):
                lines.append(node.lineno)
        elif isinstance(node, ast.Call) and _opens_a_port(node.func):
            lines.append(node.lineno)
    return lines


def _opens_a_port(func: ast.expr) -> bool:
    """Lời gọi mở cổng: `asyncio.start_server(...)`,
    `asyncio.get_running_loop().create_server(...)`, `web.run_app(...)`,
    `prometheus_client.start_http_server(...)`, hay lời gọi trần sau một import.
    Mọi đối tượng gọi đều tính, **trừ** `self`/`cls` -- một lớp tự viết có hàm cùng tên (review code
    vòng 2); chỉ nhận vài đối tượng quen thì lọt `get_running_loop().create_server` (vòng 3, plan
    `backlog-tier-1`)."""
    if isinstance(func, ast.Name):
        return func.id in SERVER_CALLS
    if not isinstance(func, ast.Attribute) or func.attr not in SERVER_CALLS:
        return False
    owner = func.value
    return not (isinstance(owner, ast.Name) and owner.id in {"self", "cls"})


def check_document_opens_no_port() -> str | None:
    """`document` không mở cổng HTTP nào: việc tới qua queue, lời đáp đi qua queue.

    Luật này từng chỉ sống trong `services/document/AGENTS.md` và docstring của worker (plan
    `backlog-tier-1`). Một server nhỏ để *"xem trạng thái OCR"* là thứ dễ thêm nhất, và là đúng thứ
    biến `document` thành một service thứ hai mà BE phải biết địa chỉ.

    Returns:
        None khi không file nào của `document` import một thư viện server, ngược lại là một thông
        báo thất bại kèm từng dòng.
    """
    root = REPO_ROOT / "services" / "document" / "src"
    offenders = [
        f"{path.relative_to(REPO_ROOT).as_posix()}:{line}"
        for path in sorted(root.rglob("*.py"))
        for line in http_servers_imported(path.read_text(encoding="utf-8"))
    ]
    if offenders:
        return _fail(
            "document-opens-no-port",
            f"{offenders} import an HTTP server library. DOCUMENT takes work from a queue and "
            "answers on a queue; a port makes it a second service BE has to find.",
        )
    return None


# Chữ của máy trong một `reason`: tên tool hay khoá tham số (snake_case), và bốn tham số một chữ
# của các tool đọc tài liệu.
MACHINE_WORDS = re.compile(r"\b[a-z]+_[a-z_]+\b|\b(?:nodes?|part|questions)\b")


def _literal_text(node: ast.AST) -> str:
    """Chữ của một biểu thức chuỗi: hằng, f-string, phép nối `+`.

    Chỗ điền của f-string được đọc bằng **mã nguồn** của nó: `{step.tool_name}` đưa một tên tool
    lên màn hình, và `step.tool_name` khớp `MACHINE_WORDS` (review code vòng 2, plan
    `backlog-tier-1` -- bỏ chỗ điền thì lưới không thấy gì ở `teacher_chat.py`).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            one.value
            if isinstance(one, ast.Constant) and isinstance(one.value, str)
            else ast.unparse(one.value)
            if isinstance(one, ast.FormattedValue)
            else ""
            for one in node.values
        )
    if isinstance(node, ast.BinOp):
        return _literal_text(node.left) + _literal_text(node.right)
    if isinstance(node, ast.IfExp):
        # `a if … else b`: một trong hai nhánh lên màn hình, nên soi cả hai.
        return _literal_text(node.body) + " " + _literal_text(node.orelse)
    return ""


def reasons_for_the_model_only(source: str) -> list[int]:
    """Các dòng có một lời từ chối mà `reason` chở chữ của máy và không kèm `said`.

    Lời từ chối là một dict mang khoá `"reason"` hay `"error"`, hay một lời gọi `_refusal(reason)`
    một tham số.

    Args:
        source: Mã nguồn Python.

    Returns:
        Số dòng của từng lời từ chối như thế; rỗng khi không có.
    """
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Dict):
            # `**rest` là một khoá `None`: dict ấy vẫn được soi, chỉ khoá trải ra là không đọc được.
            keys = [key.value if isinstance(key, ast.Constant) else None for key in node.keys]
            told = [node.values[at] for at, key in enumerate(keys) if key in {"reason", "error"}]
            if "said" not in keys and any(
                MACHINE_WORDS.search(_literal_text(value)) for value in told
            ):
                lines.append(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_refusal"
            and len(node.args) == 1
            and MACHINE_WORDS.search(_literal_text(node.args[0]))
        ):
            lines.append(node.lineno)
    return lines


def check_a_refusal_the_teacher_reads_names_no_tool() -> str | None:
    """Lời từ chối của tool giáo viên chở tên tool hay tên tham số thì phải kèm `said`.

    `reason` là chữ cho model sửa lời gọi, nên nó được gọi tên tool. Dòng `✕` của khối bước in
    `said` trước `reason`, nên một `reason` như thế không kèm `said` là tên tool hiện lên màn
    hình giáo viên (luật 7). Plan `backlog-tier-1` rà tay mọi chỗ; check này giữ cho một tool viết
    sau không quên.

    Returns:
        None khi mọi lời từ chối như thế có `said`, ngược lại là một thông báo thất bại.
    """
    # Hai file dựng kết quả bước mà dòng ✕ in: tool của giáo viên, và vòng chạy bước của chat.
    be = REPO_ROOT / "services" / "be" / "src" / "be"
    offenders = [
        f"{path.name}:{line}"
        for path in (be / "teacher_tools.py", be / "teacher_chat.py")
        for line in reasons_for_the_model_only(path.read_text(encoding="utf-8"))
    ]
    if offenders:
        return _fail(
            "refusal-said",
            f"refusals at {offenders} name a tool or an argument in `reason` with no `said`. "
            "The step's x-line prints `said` first; give the teacher a sentence without the "
            "machine words.",
        )
    return None


CHECKS = (
    check_the_content_reader_only_reads,
    check_document_opens_no_port,
    check_a_refusal_the_teacher_reads_names_no_tool,
    check_env_example_has_no_orphans,
    check_agent_and_document_hold_no_database_credentials,
    check_one_process_builds_the_schema_and_the_rest_only_check_it,
    check_both_sides_of_the_document_channel_read_its_name_from_contracts,
    check_only_one_module_per_service_talks_to_a_sync_sdk,
    check_model_call_fits_inside_the_job_waiting_for_it,
    check_contract_files_stay_short,
    check_named_dev_tasks_exist,
    check_no_tool_changes_an_assessment_state,
    check_drafting_reads_no_document_text,
    check_invented_data_lives_in_one_file,
    check_the_telling_turn_only_reads,
    check_the_form_fills_the_slots_the_wording_declares,
    check_every_figure_matches_the_diagram_it_came_from,
    check_the_model_text_passes_through_the_escape_repair,
    check_the_result_card_has_exactly_three_states,
    check_the_document_chip_draws_every_state_the_backend_can_send,
    check_rail_icons_do_not_sit_on_the_text_baseline,
    check_collapsed_panes_shrink_to_their_own_head,
    check_a_locked_control_looks_locked,
    check_no_document_repeats_itself,
    check_plan_codes_in_comments_name_their_plan,
    check_kriky_says_nothing_fixed,
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
