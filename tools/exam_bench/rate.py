"""Panel ba rater LLM chấm dàn ý và câu hỏi của `exam_bench` (plan `exam-quality-bench`).

Đa số phiếu của panel là nhãn vàng (người dùng chốt 12/11/2026). Ba rater khác hạng và khác thế
hệ để lỗi ít tương quan; không rater nào là model sinh đề. Mọi tiêu chí là một câu **có/không kèm
lý do**, không thang điểm: LLM đồng thuận với người tốt hơn ở phán đoán nhị phân.

Ba loại lời gọi:

- `outline`: ánh xạ từng mục dàn ý vào các dòng vàng (độ phủ) và bốn câu D1–D4 cho mỗi mục.
- `solve` (**mù**): giải câu khi không thấy đáp án khoá, xét từng phương án đúng hay sai.
- `review` (thấy đáp án): lỗi viết câu nghiêm trọng, câu có bám mục dàn ý không, và từng phương án
  nhiễu có tái tạo được bằng đúng lỗi ghi kèm không.
- `split` (nhánh `agent`, ADR-38; plan `agent-split-bench`): mỗi job AGENT chia có trung thành
  với lời dàn ý giáo viên đã đọc không, và dàn ý có được phủ đủ, đúng số câu không.

Lời chấm được cache theo hash của (model, loại, phiên bản prompt, system prompt, schema, tham số
gọi, nội dung): chạy lại không tốn tiền, và đổi bất cứ thứ gì rater đọc là chấm lại.
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger("exam_bench.rate")

# Đổi khi đổi nghĩa của một tiêu chí mà chữ prompt không đổi (vd. cách đọc phiếu).
PROMPT_VERSION = "2"

RATERS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-4-8")

# Giá USD mỗi triệu token (vào, ra, hệ số đọc cache) -- bảng của skill `claude-api`, cập nhật
# 03/11/2026. Ghi cache 1,25 lần giá vào.
_PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.05),
    "claude-sonnet-5-5": (2.0, 10.0, 0.05),
    "claude-opus-4-8": (5.0, 25.0, 0.1),
    "claude-haiku-5-5": (0.10, 0.50, 0.1),
}

# Tham số mọi lời chấm. Thinking adaptive tường minh: Opus 4.8 bỏ trống thì chạy **không**
# thinking, và ba rater phải chấm cùng một cách. Effort `medium` cho cả ba (mặc định khác nhau giữa
# các model).
_CALL = {
    "max_tokens": 16000,
    "thinking": {"type": "adaptive"},
    "output_config": {"effort": "medium"},
}

# Chi phí xấu nhất của một lời chấm (Opus 4.8 dùng hết 16k token ra): trần được giữ một khoảng dự
# phòng bằng số lời gọi song song nhân số này, vì chi phí chỉ biết **sau** khi lời gọi xong.
_WORST_CALL_USD = 0.45

_CACHE = Path("data") / "cache" / "exam_bench"


class BudgetSpent(RuntimeError):
    """Tổng chi phí panel đã chạm trần: dừng, không gọi thêm."""


@dataclass
class Spend:
    """Chi phí đã tiêu, cộng từ `usage` thật của từng lời gọi; trần cứng có khoảng dự phòng."""

    cap: float
    reserve: float = 0.0
    usd: float = 0.0
    calls: int = 0
    cached: int = 0
    by_model: dict[str, float] = field(default_factory=dict)

    def add(self, model: str, usage: object) -> float:
        """Cộng chi phí của một lời gọi. Trả số USD vừa cộng."""
        price_in, price_out, read_share = _PRICES[model]
        read = getattr(usage, "cache_read_input_tokens", 0) or 0
        wrote = getattr(usage, "cache_creation_input_tokens", 0) or 0
        fresh = getattr(usage, "input_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or 0
        usd = (fresh + read * read_share + wrote * 1.25) * price_in / 1e6
        usd += out * price_out / 1e6
        self.usd += usd
        self.calls += 1
        self.by_model[model] = self.by_model.get(model, 0.0) + usd
        return usd

    def check(self) -> None:
        """Ném `BudgetSpent` khi đã tiêu tới trần trừ khoảng dự phòng."""
        if self.usd >= self.cap - self.reserve:
            raise BudgetSpent(
                f"đã tiêu {self.usd:.2f} USD, trần {self.cap:.2f} USD "
                f"(dừng sớm {self.reserve:.2f} USD cho các lời gọi đang bay)"
            )


# ----------------------------------------------------------------------------- schema lời chấm


class ItemVerdict(BaseModel):
    """Lời chấm một mục dàn ý."""

    index: int = Field(description="Số thứ tự mục, bắt đầu từ 1, đúng như đề bài cho.")
    gold: list[int] = Field(
        description=(
            "Số thứ tự các dòng yêu cầu cần đạt mà mục này kiểm tra; rỗng nếu không dòng nào."
        )
    )
    specific: bool = Field(description="D1: đọc mục là biết các câu của nó hỏi gì, giải ra sao.")
    formulas_right: bool = Field(description="D2: mọi công thức của mục đúng và dùng đúng chỗ.")
    fits: bool = Field(description="D3: vừa sức khối lớp và nằm trong phạm vi giáo viên xin.")
    distinct: bool = Field(
        description="D4: không có mục khác cùng kiến thức VÀ cùng dạng câu với mục này."
    )
    why: str = Field(description="Một hai câu lý do cho những tiêu chí bị đánh false.")


class OutlineVerdict(BaseModel):
    """Lời chấm cả dàn ý."""

    items: list[ItemVerdict]


class OptionTruth(BaseModel):
    """Một phương án có là câu trả lời đúng của đề không."""

    label: str
    correct: bool


class SolveVerdict(BaseModel):
    """Lời giải mù của một câu. Phương án đúng đọc từ `options`, một nguồn duy nhất."""

    work: str = Field(description="Lời giải ngắn gọn, đủ các bước chính.")
    options: list[OptionTruth] = Field(
        description="MỌI phương án của đề, mỗi phương án một dòng: có phải câu trả lời đúng không."
    )


Flaw = Literal[
    "de-mo-ho-hoac-thieu-du-kien",
    "hai-yeu-cau-trong-mot-cau",
    "de-bai-goi-y-dap-an",
    "hai-phuong-an-tuong-duong",
    "phuong-an-vo-ly",
    "ngoai-pham-vi-khoi-lop",
    "loi-ki-hieu-lam-sai-nghia",
]

FLAWS: tuple[str, ...] = Flaw.__args__


class DistractorVerdict(BaseModel):
    """Một phương án nhiễu có tái tạo được bằng đúng lỗi ghi kèm không."""

    label: str
    reproduces: bool = Field(
        description="Học sinh mắc đúng lỗi được ghi thì chọn ra đúng phương án này."
    )


class ReviewVerdict(BaseModel):
    """Lời chấm một câu khi đã thấy đáp án."""

    flaws: list[Flaw] = Field(description="Các lỗi nghiêm trọng có trong câu; rỗng nếu không có.")
    follows_item: bool | None = Field(
        description=(
            "Câu kiểm một phần kiến thức của mục dàn ý, theo cách làm của mục; null nếu không có "
            "mục."
        )
    )
    distractors: list[DistractorVerdict]
    why: str = Field(
        description="Một hai câu lý do cho các lỗi và các phương án không tái tạo được."
    )


class JobVerdict(BaseModel):
    """Lời chấm một job của bước phân việc (ADR-38, plan `agent-split-bench`)."""

    index: int = Field(description="Số thứ tự job, bắt đầu từ 1, đúng như đề bài cho.")
    faithful: bool = Field(
        description=(
            "Job khớp một phần của dàn ý: không thêm kiến thức, công thức hay dạng câu dàn ý không "
            "có, và không đổi điều dàn ý nói."
        )
    )
    single: bool = Field(
        description="Job chỉ tả đúng một câu, đủ để soạn câu ấy mà không phải chọn giữa hai dạng."
    )
    distinct: bool = Field(
        description=(
            "Job khác các job cùng phần dàn ý về dạng câu hay cách làm; true nếu phần ấy chỉ một "
            "câu."
        )
    )
    why: str = Field(description="Một câu lý do cho mỗi tiêu chí false; rỗng nếu đều true.")


class SplitVerdict(BaseModel):
    """Lời chấm cả bước phân việc của một đề."""

    jobs: list[JobVerdict]
    covered: bool = Field(
        description="Mọi phần của dàn ý đều có job, và mỗi phần đúng số câu dàn ý ghi."
    )
    why: str = Field(description="Một hai câu lý do khi covered là false; rỗng nếu true.")


# ----------------------------------------------------------------------------------- prompt chấm

# Trung tính: không nói ai soạn đề, không dặn chấm khắt khe hay dễ dãi (review pha 3, plan
# `exam-quality-bench`).
_ROLE = (
    "Bạn là giáo viên Toán phổ thông giàu kinh nghiệm ở Việt Nam, đang thẩm định một đề kiểm tra "
    "trắc nghiệm trước khi phát cho học sinh. Chấm như khi duyệt đề thật. Chỉ trả lời theo đúng "
    "schema."
)

OUTLINE_SYSTEM = (
    _ROLE
    + "\n\nBạn nhận yêu cầu của giáo viên, các dòng yêu cầu cần đạt của bài trong sách giáo khoa, "
    "và dàn ý đề xuất (mỗi mục là một nhóm câu cùng kiến thức; một mục có thể phủ nhiều câu). Với "
    "từng mục:\n"
    "- gold: những dòng yêu cầu cần đạt mà câu hỏi của mục này thực sự kiểm tra. Mục ngoài mọi "
    "dòng thì để rỗng.\n"
    "- specific (D1): đọc mục là biết các câu của nó hỏi gì và học sinh giải ra sao, đủ để giáo "
    "viên duyệt. Mục chỉ nêu tên chủ đề chung chung là false.\n"
    "- formulas_right (D2): mọi công thức đúng về toán và đúng với kiến thức của mục. Không có "
    "công thức nào thì true.\n"
    "- fits (D3): vừa sức khối lớp đã cho và nằm trong phạm vi giáo viên xin.\n"
    "- distinct (D4): false chỉ khi có một mục khác cùng kiến thức VÀ cùng dạng câu với mục này. "
    "Cùng kiến thức nhưng khác dạng câu hay cách làm thì vẫn là true.\n"
    "- why: lý do ngắn cho mỗi tiêu chí false; rỗng nếu tất cả đều true."
)

SOLVE_SYSTEM = (
    _ROLE
    + "\n\nBạn nhận một câu trắc nghiệm, KHÔNG kèm đáp án. Tự giải cẩn thận. Rồi xét TỪNG phương "
    "án độc lập: correct là true khi phương án ấy là một câu trả lời đúng của đề. Liệt kê đủ mọi "
    "phương án. Có thể có không hoặc nhiều phương án đúng nếu đề sai -- hãy nói đúng như vậy."
)

REVIEW_SYSTEM = (
    _ROLE
    + "\n\nBạn nhận một câu trắc nghiệm kèm đáp án khoá, lỗi sai mà mỗi phương án nhiễu đại diện, "
    "và (nếu có) mục dàn ý giáo viên đã duyệt cho câu này.\n"
    "- flaws: chỉ những lỗi nghiêm trọng khiến giáo viên phải sửa trước khi phát đề:\n"
    "  de-mo-ho-hoac-thieu-du-kien: đề hiểu được nhiều cách, hoặc thiếu dữ kiện để giải;\n"
    "  hai-yeu-cau-trong-mot-cau: một câu đòi trả lời hai việc;\n"
    "  de-bai-goi-y-dap-an: chữ hay ngữ pháp của đề chỉ khớp một phương án;\n"
    "  hai-phuong-an-tuong-duong: hai phương án cùng giá trị hay cùng nghĩa;\n"
    "  phuong-an-vo-ly: phương án nhiễu vô lý đến mức không học sinh nào chọn;\n"
    "  ngoai-pham-vi-khoi-lop: cần kiến thức ngoài chương trình của khối lớp;\n"
    "  loi-ki-hieu-lam-sai-nghia: kí hiệu hay công thức viết sai làm đề đọc sai.\n"
    "- follows_item: một mục dàn ý có thể phủ nhiều câu, mỗi câu kiểm MỘT PHẦN kiến thức của mục. "
    "true khi câu này kiểm một phần kiến thức ấy theo cách làm mục đã nêu; false khi câu kiểm kiến "
    "thức khác hay làm trái cách làm của mục. Không có mục thì null.\n"
    "- distractors: với MỖI phương án nhiễu có ghi lỗi, reproduces là true khi một học sinh mắc "
    "đúng lỗi được ghi sẽ chọn ra đúng phương án ấy (với câu tính toán: ra đúng giá trị của nó).\n"
    "- why: lý do ngắn cho các lỗi và các phương án nhiễu không tái tạo được."
)


# Tên khác `agent.graphs.propose.split.SYSTEM` (prompt của bước chia việc) cho khỏi nhầm (review
# pha 1, plan `agent-split-bench`).
SPLIT_RATER_SYSTEM = (
    _ROLE
    + "\n\nBạn nhận dàn ý đề giáo viên đã đọc và đồng ý, rồi danh sách câu hỏi được chia ra từ "
    "dàn ý ấy. Mỗi câu sẽ giao cho một người soạn KHÔNG thấy dàn ý và không thấy các câu khác, "
    "nên thứ người soạn làm theo là đúng phần chữ của câu ấy. Bạn kiểm việc chia so với dàn ý "
    "giáo viên đã duyệt. Với TỪNG câu:\n"
    "- faithful: true khi câu ấy khớp một phần của dàn ý. False khi câu thêm kiến thức, công thức, "
    "cách tính hay dạng câu mà dàn ý không nêu cho phần ấy, lấn sang nội dung của phần khác, hay "
    "đổi điều dàn ý nói. Chọn số liệu cụ thể cho đúng dạng câu dàn ý nêu thì không phải thêm.\n"
    "- single: true khi phần chữ chỉ tả đúng một câu. False khi nó tả cả câu khác, hay để người "
    "soạn chọn giữa hai dạng câu.\n"
    "- distinct: true khi câu khác các câu cùng phần dàn ý về dạng câu hay cách làm (phần chỉ có "
    "một câu thì true). False khi hai câu cùng phần nhận lời dặn như nhau.\n"
    "Với cả đề:\n"
    "- covered: true khi mọi phần của dàn ý đều có câu lo, và mỗi phần được đúng số câu dàn ý "
    "ghi.\n"
    "- why: lý do ngắn cho mỗi false."
)


def _options(question: dict, keyed: bool) -> str:
    lines = []
    for one in question.get("options") or []:
        line = f"{one.get('label')}. {one.get('text')}"
        if keyed:
            line += (
                "   [ĐÁP ÁN]"
                if one.get("is_correct")
                else f"   [lỗi: {one.get('error_label') or '—'}]"
            )
        lines.append(line)
    return "\n".join(lines)


def outline_prompt(case: dict, items: list[dict]) -> str:
    """Nội dung gửi rater cho một dàn ý."""
    gold = "\n".join(f"{at}. {line}" for at, line in enumerate(case["gold"], start=1))
    shown = []
    for at, item in enumerate(items, start=1):
        formulas = "; ".join(item.get("formulas") or []) or "(không có)"
        shown.append(
            f"Mục {at} ({item.get('questions')} câu)\n  Kiến thức: {item.get('knowledge')}\n"
            f"  Công thức: {formulas}\n  Cách làm: {item.get('approach')}"
        )
    return (
        f"Khối lớp: {case['grade']}\nYêu cầu của giáo viên: {case['ask']}\n\n"
        f"Các dòng yêu cầu cần đạt của bài (sách giáo khoa):\n{gold}\n\n"
        "Dàn ý đề xuất:\n" + "\n".join(shown)
    )


def solve_prompt(case: dict, question: dict) -> str:
    """Nội dung gửi rater cho lời giải mù -- không đáp án, không lỗi ghi kèm, không lời giải."""
    options = _options(question, False)
    return f"Khối lớp: {case['grade']}\n\nĐề bài:\n{question.get('stem')}\n\n{options}"


def review_prompt(case: dict, question: dict, item: dict | None, part: int = 1) -> str:
    """Nội dung gửi rater khi đã thấy đáp án."""
    text = (
        f"Khối lớp: {case['grade']}\nYêu cầu của giáo viên: {case['ask']}\n\n"
        f"Đề bài:\n{question.get('stem')}\n\n{_options(question, True)}"
    )
    if item:
        formulas = "; ".join(item.get("formulas") or []) or "(không có)"
        text += (
            f"\n\nMục dàn ý của câu này (mục phủ {item.get('questions')} câu, đây là câu thứ "
            f"{part}):\n  Kiến thức: {item.get('knowledge')}\n"
            f"  Công thức: {formulas}\n  Cách làm: {item.get('approach')}"
        )
    else:
        text += "\n\n(Câu này không có mục dàn ý.)"
    return text


def split_rating_prompt(case: dict, said: str, jobs: list[dict]) -> str:
    """Nội dung gửi rater cho bước phân việc: lời dàn ý giáo viên đã đọc và các job."""
    shown = []
    for at, job in enumerate(jobs, start=1):
        formulas = "; ".join(job.get("formulas") or []) or "(không có)"
        line = (
            f"Câu {at} (phần dàn ý: {job.get('part')})\n  Kiến thức: {job.get('knowledge')}\n"
            f"  Công thức: {formulas}\n  Cách làm: {job.get('approach')}"
        )
        if str(job.get("differs") or "").strip():
            line += f"\n  Khác các câu cùng phần: {job['differs']}"
        shown.append(line)
    return (
        f"Khối lớp: {case['grade']}\nYêu cầu của giáo viên: {case['ask']}\n\n"
        f"Dàn ý giáo viên đã đọc và đồng ý:\n\n{said}\n\n"
        "Các câu được chia ra:\n" + "\n".join(shown)
    )


_KINDS = {
    "outline": (OUTLINE_SYSTEM, OutlineVerdict),
    "solve": (SOLVE_SYSTEM, SolveVerdict),
    "review": (REVIEW_SYSTEM, ReviewVerdict),
    "split": (SPLIT_RATER_SYSTEM, SplitVerdict),
}


def cache_key(model: str, kind: str, content: str) -> str:
    """Khoá cache của một lời chấm: mọi thứ rater đọc hay cách nó được gọi. Hàm thuần."""
    system, schema = _KINDS[kind]
    parts = [
        model,
        kind,
        PROMPT_VERSION,
        system,
        json.dumps(schema.model_json_schema(), ensure_ascii=False, sort_keys=True),
        json.dumps(_CALL, sort_keys=True),
        content,
    ]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()[:32]


# ------------------------------------------------------------------------------------ lời gọi


class Panel:
    """Ba rater, một client, một trần chi phí, một cache trên đĩa."""

    def __init__(self, api_key: str, spend: Spend, concurrency: int = 6) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=2)
        self._spend = spend
        self._spend.reserve = max(self._spend.reserve, concurrency * _WORST_CALL_USD)
        self._gate = asyncio.Semaphore(concurrency)
        _CACHE.mkdir(parents=True, exist_ok=True)

    async def ask(self, model: str, kind: str, content: str) -> dict | None:
        """Lời chấm của một rater, hay `None` khi rater từ chối hoặc trả hỏng hai lần.

        Args:
            model: Một trong `RATERS`.
            kind: `outline`, `solve` hay `review`.
            content: Nội dung đã dựng bằng `*_prompt`.

        Returns:
            Lời chấm đã dump, kèm `_model` (model thật đã trả lời) và `_usd`.

        Raises:
            BudgetSpent: Khi đã chạm trần trước một lần thử.
        """
        system, schema = _KINDS[kind]
        cached = _CACHE / f"{cache_key(model, kind, content)}.json"
        if cached.exists():
            self._spend.cached += 1
            return json.loads(cached.read_text(encoding="utf-8"))
        async with self._gate:
            for attempt in range(2):
                self._spend.check()
                try:
                    response = await self._client.messages.parse(
                        model=model,
                        system=system,
                        messages=[{"role": "user", "content": content}],
                        output_format=schema,
                        **_CALL,
                    )
                except Exception as exc:  # noqa: BLE001 -- một phiếu trống, không dừng cả bench
                    logger.warning("%s %s failed (%d): %r", model, kind, attempt + 1, exc)
                    continue
                usd = self._spend.add(model, response.usage)
                if response.stop_reason == "refusal" or response.parsed_output is None:
                    logger.warning("%s %s: %s", model, kind, response.stop_reason)
                    continue
                verdict = response.parsed_output.model_dump(mode="json")
                verdict["_model"] = response.model
                verdict["_usd"] = round(usd, 6)
                cached.write_text(
                    json.dumps(verdict, ensure_ascii=False), encoding="utf-8", newline="\n"
                )
                return verdict
        return None

    async def all_three(self, kind: str, content: str) -> list[dict | None]:
        """Lời chấm của cả ba rater, cùng nội dung, chạy song song.

        Raises:
            BudgetSpent: Khi một rater chạm trần; lời chấm của hai rater kia (nếu có) đã vào cache.
        """
        votes = await asyncio.gather(
            *(self.ask(model, kind, content) for model in RATERS), return_exceptions=True
        )
        for vote in votes:
            if isinstance(vote, BaseException):
                raise vote
        return list(votes)
