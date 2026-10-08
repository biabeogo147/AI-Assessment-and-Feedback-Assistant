"""Luồng hai pha, từ đầu tới cuối, chạy trên một database in-memory.

AGENT được stub ở tầng gateway thay vì được import: BE và AGENT không được phụ thuộc
vào nhau, và một test thò tay vào worker để lấy một câu hỏi về sẽ là vết nứt đầu tiên
trên bức tường đó. Bản stub trả về đúng hình dạng mà task thật trả về, dựng từ
`contracts` — thứ cả hai service dùng chung.

Điều các test này khẳng định cố ý không phải câu chữ của bất cứ thứ gì. Chúng kiểm
những luật sống lâu hơn cả bản `mock` lẫn model: cái sàn điểm, mức trần ba vòng, ai
được đọc cái gì, và cái gì không bao giờ xuất hiện trong `payload` của học sinh.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import agent_gateway, student_routes
from be import db as db_module
from be.db import bind_sessions
from be.seed import seed_if_empty
from be.student_routes import router as student_router
from contracts import GeneratedOption, GeneratedQuestion, RetryQuestionCompleted, SolutionMethod
from schema.ddl import prepare_schema
from schema.models import Publication, QuestionOutcome, RemediationRound

STUDENT = {"X-Actor": "student:HS2026-1204"}
OTHER_STUDENT = {"X-Actor": "student:HS2026-1205"}

_RETRY = GeneratedQuestion(
    stem="Đề của lượt làm lại",
    options=(
        GeneratedOption(label="A", text="sai A", is_correct=False, error_label="lỗi A"),
        GeneratedOption(label="B", text="đúng", is_correct=True),
        GeneratedOption(label="C", text="sai C", is_correct=False, error_label="lỗi C"),
    ),
    methods=(
        SolutionMethod(title="Cách 1", body="..."),
        SolutionMethod(title="Cách 2", body="..."),
    ),
    learning_objective="mock",
)


async def _fake_run_task(pool, settings, task_name, payload) -> dict:
    """Đứng thay AGENT, trả về đúng hình dạng mà mỗi task hứa.

    `stem` của lượt làm lại mang theo số vòng, vì BE từ chối một lượt làm lại nhắc lại
    câu nó đang thay thế hoặc một vòng trước đó (ADR-17). Một bản stub trả về đúng một
    `stem` cố định sẽ bị loại ở vòng hai — loại đúng, nên thứ phải thay đổi là bản stub,
    không phải cái luật.
    """
    if task_name.endswith("retry_question"):
        question = _RETRY.model_copy(
            update={"stem": f"{_RETRY.stem} — lượt {payload['round_index']}"}
        )
        return RetryQuestionCompleted(
            request_id=payload["request_id"], question=question
        ).model_dump(mode="json")
    return {"schema_version": 1, "request_id": payload["request_id"], "text": "Trả lời mẫu."}


async def _ask_something(client: AsyncClient, attempt_id: str) -> None:
    """Đi qua lượt mở đầu để lượt `stream` kế tiếp là một lượt model thật.

    Lời chào do BE viết và không bao giờ tới AGENT, nên một test muốn xem model trả lời
    thì phải hỏi nó một câu gì trước đã.
    """
    await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    await client.post(
        f"/api/attempts/{attempt_id}/chat/messages",
        json={"text": "câu 5 mình chưa hiểu vì sao sai"},
        headers=STUDENT,
    )


async def _fake_stream_task(pool, settings, task_name, payload, channel, silence=None):
    """Đứng thay AGENT trên đường `stream`, và không publish gì cả.

    Một worker không `stream` — nội dung soạn trước, hoặc một nhà cung cấp không có
    `stream` theo `token` — là một ca được hỗ trợ, không phải một ca suy giảm, nên đây
    là bản stub mà phần còn lại của bộ test chạy lên. Đường chạy thật có test riêng của
    nó.
    """
    yield "result", await _fake_run_task(pool, settings, task_name, payload)


async def _nothing_finished_yet(pool, settings, job_id) -> tuple[str, object]:
    """Cách đọc mặc định cho một job đã vào queue: vẫn đang chạy."""
    return "pending", None


class FakeQueue:
    """Một queue nhận job và nhớ chúng lại.

    Trước đây chỗ này là một `object()`, nghĩa là `enqueue_task` ném exception, bị nuốt
    đi, và phần sinh câu hỏi trước âm thầm không làm gì — bộ test vẫn xanh vì hệ thống
    đã `fallback` đúng cách sang viết câu hỏi ngay tại chỗ. Xanh vì lý do sai thì tệ hơn
    là đỏ.
    """

    def __init__(self) -> None:
        self.jobs: list[tuple[str, str, dict]] = []

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        job_id = f"job-{len(self.jobs)}"
        self.jobs.append((job_id, name, payload))
        return SimpleNamespace(job_id=job_id)

    def payload_for(self, job_id: str) -> dict:
        """`payload` mà một job được đưa vào queue cùng với nó."""
        return next(payload for queued, _, payload in self.jobs if queued == job_id)


@pytest_asyncio.fixture
async def client(monkeypatch) -> AsyncClient:
    """Dựng một app trên database in-memory mới, với AGENT đã được stub."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)

    # Patch vào bên trong gateway chứ không ở tầng route, để `start_round` vẫn chạy đúng
    # vòng hỏi-rồi-kiểm-lại thật: các lượt kiểm theo ADR-18 và ADR-17, cùng việc hỏi lại
    # khi bị từ chối, vẫn nằm trong vùng được test thay vì bị stub mất.
    monkeypatch.setattr(agent_gateway, "run_task", _fake_run_task)
    monkeypatch.setattr(student_routes, "stream_task", _fake_stream_task)
    # Không thu kết quả nào trừ khi có test nói rằng một job đã xong. Cách đọc ba đường
    # cho state của một job là việc của gateway và được test ở đó.
    monkeypatch.setattr(student_routes, "collect_result", _nothing_finished_yet)

    app = FastAPI()
    app.include_router(student_router)
    app.state.queue_pool = FakeQueue()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _sessionmaker():
    """Lấy đúng session factory mà app đang dùng, để dàn dựng state."""
    assert db_module._SESSION_MAKER is not None
    return db_module._SESSION_MAKER


async def _start_and_submit(client: AsyncClient, correct_count: int) -> dict:
    """Chạy pha 1, trả lời đúng `correct_count` câu đầu tiên."""
    assignments = (await client.get("/api/me/assignments", headers=STUDENT)).json()
    assessment_id = assignments[0]["assignment_id"]
    attempt = (
        await client.post(f"/api/assignments/{assessment_id}/attempts", headers=STUDENT)
    ).json()

    for index, question in enumerate(attempt["questions"]):
        # `payload` che đi phương án nào đúng, nên chọn theo vị trí: bản seed đặt phương
        # án đúng ở đầu trong mọi câu hỏi.
        option = question["options"][0 if index < correct_count else 1]
        response = await client.put(
            f"/api/attempts/{attempt['attempt_id']}/answers/{question['question_id']}",
            json={"option_id": option["option_id"]},
            headers=STUDENT,
        )
        assert response.status_code == 200

    submitted = await client.post(f"/api/attempts/{attempt['attempt_id']}/submit", headers=STUDENT)
    assert submitted.status_code == 200
    return {"attempt_id": attempt["attempt_id"], **submitted.json()}


@pytest.mark.asyncio
async def test_phase_one_payload_hides_the_answer_key(client: AsyncClient) -> None:
    """Một `Attempt` đang chạy không được nói cho học sinh biết phương án nào đúng."""
    assignments = (await client.get("/api/me/assignments", headers=STUDENT)).json()
    attempt = (
        await client.post(
            f"/api/assignments/{assignments[0]['assignment_id']}/attempts", headers=STUDENT
        )
    ).json()

    body = str(attempt)
    assert "is_correct" not in body
    assert "error_label" not in body


@pytest.mark.asyncio
async def test_student_payloads_carry_no_diagnosis_numbers(client: AsyncClient) -> None:
    """ADR-08: `Confidence`, misconception và lý do đưa đi xem lại không bao giờ tới học sinh."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    for path in (
        "/api/me/assignments",
        f"/api/attempts/{attempt_id}/result",
        f"/api/attempts/{attempt_id}/remediation",
    ):
        body = (await client.get(path, headers=STUDENT)).text
        assert "confidence" not in body
        assert "misconception" not in body
        assert "review_reason" not in body


@pytest.mark.asyncio
async def test_phase_one_score_is_the_floor(client: AsyncClient) -> None:
    """Đúng bốn trên sáu thì được 4.0, và hai câu sai vẫn còn để mở."""
    submitted = await _start_and_submit(client, correct_count=4)
    assert submitted["phase1_score"] == 4.0
    assert len(submitted["wrong_question_ids"]) == 2

    attempt_id = submitted["attempt_id"]
    result = (await client.get(f"/api/attempts/{attempt_id}/result", headers=STUDENT)).json()
    assert result["state"] == "cần-chữa"
    assert result["total_score"] == 4.0


@pytest.mark.asyncio
async def test_submitting_twice_is_refused(client: AsyncClient) -> None:
    """Nộp bài là kết thúc pha 1; một cánh cửa một chiều bấm hai lần thì không `idempotent`."""
    submitted = await _start_and_submit(client, correct_count=6)
    again = await client.post(f"/api/attempts/{submitted['attempt_id']}/submit", headers=STUDENT)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_another_student_cannot_read_this_attempt(client: AsyncClient) -> None:
    """Quyền sở hữu được thi hành, và người lạ nhận 404 chứ không nhận 403."""
    submitted = await _start_and_submit(client, correct_count=6)
    response = await client.get(
        f"/api/attempts/{submitted['attempt_id']}/result", headers=OTHER_STUDENT
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_solution_is_closed_until_the_paper_is_submitted(client: AsyncClient) -> None:
    """Hộp thoại mang theo phương án đúng, nên nó đợi tới khi bài được nộp."""
    assignments = (await client.get("/api/me/assignments", headers=STUDENT)).json()
    attempt = (
        await client.post(
            f"/api/assignments/{assignments[0]['assignment_id']}/attempts", headers=STUDENT
        )
    ).json()
    question_id = attempt["questions"][0]["question_id"]

    early = await client.get(f"/api/questions/{question_id}/solution", headers=STUDENT)
    assert early.status_code == 409

    await _finish_phase_one(client, attempt)
    later = await client.get(f"/api/questions/{question_id}/solution", headers=STUDENT)
    assert later.status_code == 200
    assert any(option["is_correct"] for option in later.json()["options"])


async def _finish_phase_one(client: AsyncClient, attempt: dict) -> None:
    """Nộp một `Attempt` mà không trả lời câu nào."""
    response = await client.post(f"/api/attempts/{attempt['attempt_id']}/submit", headers=STUDENT)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_a_round_lifts_a_wrong_question_to_half_credit(client: AsyncClient) -> None:
    """Làm đúng lượt làm lại thì chốt câu đó ở 0.5, không bao giờ ở 1.0."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    opened = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert opened.status_code == 201
    rnd = opened.json()
    assert len(rnd["items"]) == 2

    for item in rnd["items"]:
        await client.put(
            f"/api/rounds/{rnd['round_id']}/answers/{item['round_item_id']}",
            json={"label": "B"},
            headers=STUDENT,
        )

    verdict = (await client.post(f"/api/rounds/{rnd['round_id']}/submit", headers=STUDENT)).json()
    assert {row["outcome"] for row in verdict["per_question"]} == {"đúng"}
    assert {row["new_mark"] for row in verdict["per_question"]} == {0.5}
    assert verdict["attempt_state"] == "đã-hoàn-thành"

    result = (await client.get(f"/api/attempts/{attempt_id}/result", headers=STUDENT)).json()
    assert result["total_score"] == 5.0
    fixed = [item for item in result["items"] if item["mark"] == 0.5]
    assert all(item["rounds"] for item in fixed), "the sheet must print each round's own question"


@pytest.mark.asyncio
async def test_three_wrong_rounds_close_the_question_at_zero(client: AsyncClient) -> None:
    """ADR-17 chặn việc chữa bài ở ba vòng, và vòng thứ tư bị từ chối."""
    submitted = await _start_and_submit(client, correct_count=5)
    attempt_id = submitted["attempt_id"]

    for expected in (1, 2, 3):
        rnd = (await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)).json()
        for item in rnd["items"]:
            await client.put(
                f"/api/rounds/{rnd['round_id']}/answers/{item['round_item_id']}",
                json={"label": "A"},
                headers=STUDENT,
            )
        verdict = (
            await client.post(f"/api/rounds/{rnd['round_id']}/submit", headers=STUDENT)
        ).json()
        assert verdict["per_question"][0]["rounds_used"] == expected

    fourth = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert fourth.status_code == 409

    result = (await client.get(f"/api/attempts/{attempt_id}/result", headers=STUDENT)).json()
    closed = next(item for item in result["items"] if item["mark"] == 0.0)
    assert closed["mark_reason"] == "hết-vòng"
    assert result["state"] == "đã-hoàn-thành"


@pytest.mark.asyncio
async def test_a_mark_never_falls(client: AsyncClient) -> None:
    """Pha 1 đặt ra một cái sàn: không đường nào trong pha 2 được phép hạ điểm xuống."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    rnd = (await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)).json()
    for item in rnd["items"]:
        await client.put(
            f"/api/rounds/{rnd['round_id']}/answers/{item['round_item_id']}",
            json={"label": "B"},
            headers=STUDENT,
        )
    await client.post(f"/api/rounds/{rnd['round_id']}/submit", headers=STUDENT)

    maker = await _sessionmaker()
    async with maker() as session:
        marks = list(
            await session.scalars(
                select(QuestionOutcome.mark).where(QuestionOutcome.attempt_id == attempt_id)
            )
        )
    assert sorted(marks) == [0.5, 0.5, 1.0, 1.0, 1.0, 1.0]


@pytest.mark.asyncio
async def test_a_retry_that_repeats_the_question_is_refused(
    client: AsyncClient, monkeypatch
) -> None:
    """ADR-17: trả lại đúng `stem` cũ là kiểm tra trí nhớ, không phải kiểm tra sự hiểu."""
    submitted = await _start_and_submit(client, correct_count=5)
    attempt_id = submitted["attempt_id"]

    result = (await client.get(f"/api/attempts/{attempt_id}/result", headers=STUDENT)).json()
    wrong = next(item for item in result["items"] if item["mark"] == 0)

    async def echo_the_origin(pool, settings, task_name, payload) -> dict:
        if task_name.endswith("retry_question"):
            question = _RETRY.model_copy(update={"stem": payload["origin"]["stem"]})
            return RetryQuestionCompleted(
                request_id=payload["request_id"], question=question
            ).model_dump(mode="json")
        return {"schema_version": 1, "request_id": payload["request_id"], "text": ""}

    monkeypatch.setattr(agent_gateway, "run_task", echo_the_origin)

    refused = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert refused.status_code == 503
    assert wrong["stem"][:20] in refused.json()["detail"]

    # Lời từ chối không được tiêu mất một vòng nào.
    panel = (await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)).json()
    assert panel["items"][0]["rounds_used"] == 0


@pytest.mark.asyncio
async def test_only_one_round_may_be_open(client: AsyncClient) -> None:
    """Hai tab không được mua về hai cái đồng hồ."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    first = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert first.status_code == 201
    second = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_the_panel_warns_when_a_round_would_be_cut(client: AsyncClient) -> None:
    """ADR-15: BE so ngân sách thời gian với thời gian còn lại, không phải client làm việc đó."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    panel = (await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)).json()
    assert panel["round_budget_minutes"] == 10
    assert panel["warn_cut"] is False
    assert panel["can_start_round"] is True

    maker = await _sessionmaker()
    async with maker() as session:
        publication = await session.scalar(select(Publication))
        publication.remediation_deadline = datetime.now(UTC) + timedelta(minutes=6)
        await session.commit()

    warned = (await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)).json()
    assert warned["warn_cut"] is True
    assert warned["can_start_round"] is True


@pytest.mark.asyncio
async def test_no_round_starts_after_the_deadline(client: AsyncClient) -> None:
    """Qua hạn chót là pha 2 đã hết, bất kể màn hình vẫn còn hiển thị gì."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    maker = await _sessionmaker()
    async with maker() as session:
        publication = await session.scalar(select(Publication))
        publication.remediation_deadline = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    refused = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert refused.status_code == 409

    result = (await client.get(f"/api/attempts/{attempt_id}/result", headers=STUDENT)).json()
    assert result["state"] == "hết-hạn-chữa"


@pytest.mark.asyncio
async def test_two_tabs_cannot_open_two_rounds_at_once(client: AsyncClient) -> None:
    """Lời từ chối phải sống sót qua tình huống song song, không chỉ qua một chuỗi gọi ngăn nắp.

    Một lượt review ngày 2026-09-11 bắn hai request này cùng lúc và nhận về hai vòng:
    route kiểm trước rồi ghi sau, và cả hai request đều qua được lượt kiểm. Test tuần tự
    không bao giờ chạm tới khoảng hở đó, nên test này chạy chúng bằng `gather`.
    """
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    first, second = await asyncio.gather(
        client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT),
        client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT),
    )

    codes = sorted([first.status_code, second.status_code])
    assert codes == [201, 409], f"expected one round and one refusal, got {codes}"

    # Con số đếm mới là invariant. Bên nào trong hai bên sống sót thì không: SQLite
    # in-memory giữ đúng một connection cho mọi session, nên lượt `rollback` của bên thua
    # có thể kéo theo cả dòng chưa `commit` của bên thắng. Hiện tượng đó thuộc về database
    # dùng để test, và không bao giờ xảy ra trên Postgres.
    maker = await _sessionmaker()
    async with maker() as session:
        open_rounds = list(
            await session.scalars(
                select(RemediationRound).where(
                    RemediationRound.attempt_id == attempt_id,
                    RemediationRound.submitted_at.is_(None),
                )
            )
        )
    assert len(open_rounds) <= 1, "two clocks for one student"

    panel = (await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)).json()
    assert panel["can_start_round"] is (not open_rounds)


@pytest.mark.asyncio
async def test_the_assistant_does_not_greet_twice(client: AsyncClient) -> None:
    """Đến lượt ai là chuyện phía server quyết, không phải chuyện client hỏi bao nhiêu lần."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    first = await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    second = await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    assert first.status_code == 200
    assert second.status_code == 200

    history = (await client.get(f"/api/attempts/{attempt_id}/chat", headers=STUDENT)).json()
    assert len(history["messages"]) == 1

    # Khi học sinh đã nói, lại tới lượt trợ lý.
    await client.post(
        f"/api/attempts/{attempt_id}/chat/messages", json={"text": "câu 5 ạ"}, headers=STUDENT
    )
    await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    after = (await client.get(f"/api/attempts/{attempt_id}/chat", headers=STUDENT)).json()
    assert [m["role"] for m in after["messages"]] == ["assistant", "student", "assistant"]


@pytest.mark.asyncio
async def test_the_assistant_is_told_which_question_numbers_are_wrong(
    client: AsyncClient, monkeypatch
) -> None:
    """Trợ lý nói thành tiếng "câu 5", nên con số đó phải đi được tới nơi."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    seen: dict = {}

    async def capture(pool, settings, task_name, payload, channel, silence=None):
        seen.update(payload)
        yield "result", {"schema_version": 1, "request_id": payload["request_id"], "text": "…"}

    monkeypatch.setattr(student_routes, "stream_task", capture)
    await _ask_something(client, attempt_id)
    await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)

    # Hai câu cuối trong bản seed chính là hai câu bị làm sai.
    assert seen["question_numbers"] == [5, 6]


@pytest.mark.asyncio
async def test_chat_history_locks_when_the_attempt_ends(client: AsyncClient) -> None:
    """Một `Attempt` đã xong thì giữ cuộc hội thoại ở dạng đọc được và từ chối lượt mới."""
    submitted = await _start_and_submit(client, correct_count=6)
    attempt_id = submitted["attempt_id"]

    history = (await client.get(f"/api/attempts/{attempt_id}/chat", headers=STUDENT)).json()
    assert history["locked"] is True

    refused = await client.post(
        f"/api/attempts/{attempt_id}/chat/messages", json={"text": "cho em hỏi"}, headers=STUDENT
    )
    assert refused.status_code == 409


@pytest.mark.asyncio
async def test_a_report_needs_no_message_and_blocks_nothing(client: AsyncClient) -> None:
    """ADR-19: đơn vị của một báo cáo là cả cuộc hội thoại của `Attempt`, không phải một lượt."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    filed = await client.post(
        f"/api/attempts/{attempt_id}/reports", json={"note": None}, headers=STUDENT
    )
    assert filed.status_code == 201

    panel = await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)
    assert panel.json()["can_start_round"] is True


@pytest.mark.asyncio
async def test_the_answer_reaches_the_student_as_it_is_written(
    client: AsyncClient, monkeypatch
) -> None:
    """Các mẩu do AGENT publish đều được chuyển tiếp, và trọn câu vẫn được lưu lại.

    Hai nửa đó chỉ có nghĩa khi đi cùng nhau. Chỉ chuyển tiếp thôi thì là một hiệu ứng
    động trên hư không; chỉ lưu thôi là đúng thứ hệ thống đã có từ trước. Một người đọc
    reload lại phải tìm thấy đúng câu họ vừa xem hiện ra.
    """

    async def streaming(pool, settings, task_name, payload, channel, silence=None):
        for piece in ("Câu 5 ", "em chọn B,\n", "mà B là khoảng nghịch biến."):
            yield "chunk", piece
        yield (
            "result",
            {
                "schema_version": 1,
                "request_id": payload["request_id"],
                "text": "Câu 5 em chọn B,\nmà B là khoảng nghịch biến.",
            },
        )

    monkeypatch.setattr(student_routes, "stream_task", streaming)

    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]
    await _ask_something(client, attempt_id)

    response = await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    assert response.status_code == 200

    body = response.text
    assert body.count("event: chunk") == 3, "one event per published piece, no re-splitting"
    # Cái mẩu có ký tự xuống dòng bên trong được viết thành hai dòng `data:`, đúng như
    # định dạng quy định. Gói vào một dòng sẽ cắt cụt câu đó.
    assert "data: em chọn B,\ndata: \n" in body
    assert body.count("event: done") == 1

    history = (await client.get(f"/api/attempts/{attempt_id}/chat", headers=STUDENT)).json()
    assert history["messages"][-1]["text"] == "Câu 5 em chọn B,\nmà B là khoảng nghịch biến."


@pytest.mark.asyncio
async def test_a_model_failure_arrives_in_the_stream_not_as_a_status_code(
    client: AsyncClient, monkeypatch
) -> None:
    """`stream` đã mở thì dòng status đã bay đi rồi.

    Nên một lỗi phải được báo ngay trong chính dòng dữ liệu đó. Lượt ấy không được lưu:
    tin nhắn của chính học sinh vẫn là lời cuối, và chính điều đó làm request kế tiếp sinh
    ra một câu trả lời mới chứ không phát lại một câu trả lời hỏng.
    """

    async def failing(pool, settings, task_name, payload, channel, silence=None):
        yield "chunk", "Câu 5 "
        raise student_routes.AgentError("model chết giữa chừng")

    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]
    await _ask_something(client, attempt_id)
    monkeypatch.setattr(student_routes, "stream_task", failing)

    response = await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)

    assert response.status_code == 200
    assert "event: error" in response.text
    history = (await client.get(f"/api/attempts/{attempt_id}/chat", headers=STUDENT)).json()
    # Lời chào và câu hỏi vẫn còn đó; không có câu trả lời hỏng nào được lưu sau chúng,
    # nên tin nhắn của học sinh vẫn là lời cuối và request kế tiếp sẽ sinh ra một lượt mới.
    assert [m["role"] for m in history["messages"]] == ["assistant", "student"]


@pytest.mark.asyncio
async def test_submitting_starts_writing_the_next_round(client: AsyncClient) -> None:
    """Cú chạy trước bắt đầu ngay khoảnh khắc bài được nộp.

    Không phải lúc học sinh bấm "Làm bài mới" — tới lúc đó thì các em sẽ ngồi nhìn một
    màn hình trắng đúng bằng khoảng thời gian một model cần.
    """
    submitted = await _start_and_submit(client, correct_count=4)

    queue = client._transport.app.state.queue_pool
    asked = [payload for _, name, payload in queue.jobs if name.endswith("retry_question")]

    assert len(asked) == len(submitted["wrong_question_ids"]) == 2
    assert {payload["round_index"] for payload in asked} == {1}
    # AGENT được cho biết học sinh đã chọn gì, nếu không thì lượt làm lại chẳng nhắm được
    # vào đúng cái lỗi mà nó phải kiểm (ADR-17).
    assert all(payload["wrong_option_label"] for payload in asked)


@pytest.mark.asyncio
async def test_a_question_written_ahead_opens_the_round_without_asking_again(
    client: AsyncClient, monkeypatch
) -> None:
    """Đúng trọng tâm: bấm cái nút không tốn một lượt gọi model nào.

    `run_task` bị thay bằng một thứ làm test đỏ nếu nó chạy, nên một regression âm thầm
    quay về lối viết ngay tại chỗ thì không thể qua được.
    """
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]
    queue = client._transport.app.state.queue_pool

    ready = _RETRY.model_copy(update={"stem": "Đề đã soạn sẵn từ lúc nộp bài"})

    async def finished(pool, settings, job_id) -> tuple[str, object]:
        payload = queue.payload_for(job_id)
        return "ready", RetryQuestionCompleted(
            request_id=payload["request_id"], question=ready
        ).model_dump(mode="json")

    monkeypatch.setattr(student_routes, "collect_result", finished)

    # Ghé vào màn hình phụ đạo chính là thứ đi thu phần việc đã xong về.
    await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)

    async def must_not_run(*args, **kwargs):
        raise AssertionError("the round was opened by asking the model again")

    monkeypatch.setattr(agent_gateway, "run_task", must_not_run)

    opened = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)

    assert opened.status_code == 201
    assert [item["stem"] for item in opened.json()["items"]] == [ready.stem, ready.stem]


@pytest.mark.asyncio
async def test_a_head_start_that_aged_out_is_started_again(
    client: AsyncClient, monkeypatch
) -> None:
    """Kết quả job sống một giờ; hạn chót của pha 2 có thể cách đó nhiều ngày.

    Một học sinh đóng tab rồi mai quay lại sẽ thấy câu trả lời không còn. Dòng dữ liệu
    không được nằm mãi ở `pending` mà chờ một thứ đã không còn tồn tại — nó bị bỏ đi, và
    lượt ghé sau sẽ đưa một job thay thế vào queue.
    """
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]
    queue = client._transport.app.state.queue_pool
    first_round = len(queue.jobs)

    async def gone(pool, settings, job_id) -> tuple[str, object]:
        return "gone", None

    monkeypatch.setattr(student_routes, "collect_result", gone)

    await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)

    assert len(queue.jobs) > first_round, "the lost head start was never restarted"


@pytest.mark.asyncio
async def test_a_dead_queue_does_not_stop_a_student_handing_in(
    client: AsyncClient, monkeypatch
) -> None:
    """Sinh trước là một phép tối ưu. Nộp bài thì không.

    Nên một queue đang chết chỉ làm mất cú chạy trước, không mất gì khác, và vòng chữa bài
    vẫn mở ra theo lối cũ.
    """
    monkeypatch.setattr(client._transport.app.state, "queue_pool", None)

    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    assert submitted["phase1_score"] == 4.0
    opened = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert opened.status_code == 201, "the on-the-spot path should still work"


@pytest.mark.asyncio
async def test_a_question_written_ahead_is_checked_like_any_other(
    client: AsyncClient, monkeypatch
) -> None:
    """Viết trước không được phép thành đường đi vòng qua ADR-18.

    Các luật đó được thi hành bên trong `ask_for_retry_question`, nơi mà chỉ đường viết
    ngay tại chỗ đi qua. Từ pha này trở đi, viết trước mới là đường bình thường — nên một
    câu hỏi có hai đáp án đúng sẽ tới được học sinh, mà BE thì chấm một vòng dựa vào đúng
    cái cờ đó.
    """
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]
    queue = client._transport.app.state.queue_pool

    two_right = _RETRY.model_copy(
        update={
            "stem": "Đề hỏng: hai đáp án đúng",
            "options": tuple(
                option.model_copy(update={"is_correct": True}) for option in _RETRY.options[:2]
            )
            + _RETRY.options[2:],
        }
    )

    async def finished(pool, settings, job_id) -> tuple[str, object]:
        payload = queue.payload_for(job_id)
        return "ready", RetryQuestionCompleted(
            request_id=payload["request_id"], question=two_right
        ).model_dump(mode="json")

    monkeypatch.setattr(student_routes, "collect_result", finished)
    await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)

    opened = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)

    assert opened.status_code == 201
    stems = [item["stem"] for item in opened.json()["items"]]
    assert two_right.stem not in stems, "a malformed question reached the student"


@pytest.mark.asyncio
async def test_nothing_is_written_ahead_while_a_round_is_open(
    client: AsyncClient, monkeypatch
) -> None:
    """Màn hình vòng chữa gọi endpoint này lúc mount, và việc đó phải không tốn gì.

    `rounds_used` chưa nhích lên cho tới khi một vòng được nộp, nên trong lúc một vòng đang
    mở thì chỉ số kế tiếp vẫn đọc ra là của vòng hiện tại — vòng vốn đã có câu hỏi rồi. Mọi
    job đẩy vào queue ở đây sẽ được trả lời, được lưu, không bao giờ được dùng, và thành
    mồ côi ngay khoảnh khắc vòng đó được nộp.
    """
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]
    queue = client._transport.app.state.queue_pool

    await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    during = len(queue.jobs)

    # Đúng việc Round.tsx làm khi mount, và làm lại ở mọi lượt refresh.
    await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)
    await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)

    assert len(queue.jobs) == during, "opening the round screen queued work nobody can use"


@pytest.mark.asyncio
async def test_a_job_that_failed_is_not_asked_again_forever(
    client: AsyncClient, monkeypatch
) -> None:
    """Một job đã chạy và ném exception thì lần sau cũng ném đúng như thế.

    Xoá dòng của nó đi sẽ khiến nó được đẩy lại vào queue ở mọi màn hình học sinh mở, suốt
    chừng nào con bug còn đó, và hoàn toàn âm thầm. "Hết hạn" và "hỏng" là hai cái kết khác
    nhau, và chỉ cái đầu mới đáng làm lại.
    """
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]
    queue = client._transport.app.state.queue_pool
    after_submit = len(queue.jobs)

    async def broke(pool, settings, job_id) -> tuple[str, object]:
        return "failed", None

    monkeypatch.setattr(student_routes, "collect_result", broke)

    for _ in range(3):
        await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)

    assert len(queue.jobs) == after_submit, "a broken job was re-queued on every visit"


@pytest.mark.asyncio
async def test_the_greeting_costs_nothing(client: AsyncClient, monkeypatch) -> None:
    """Lượt mở đầu không bao giờ tới AGENT.

    Trước thì có: một job, một lượt chờ, một `stream`, để sinh ra một câu gần như không
    thay đổi. Một lượt gọi model bị vứt đi ở mỗi bài được nộp. Chẳng có gì về khoản tiết
    kiệm đó hiện lên màn hình, nên một lượt dọn dẹp có thể đặt nó lại mà không ai nhận ra —
    và test này tồn tại vì thế.
    """

    async def must_not_run(*args, **kwargs):
        raise AssertionError("the greeting asked the model")
        yield  # pragma: no cover -- giữ cho đây vẫn là một async generator

    monkeypatch.setattr(student_routes, "stream_task", must_not_run)

    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    response = await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    assert response.status_code == 200

    history = (await client.get(f"/api/attempts/{attempt_id}/chat", headers=STUDENT)).json()
    greeting = history["messages"][0]["text"]

    assert greeting.startswith("Mình là trợ lý Kriky")
    # Nó gọi tên những thứ đang có, để học sinh biết nên hỏi về cái gì trước khi kịp đọc
    # cái bảng.
    assert "câu 5 và câu 6" in greeting
    assert "bạn" in greeting and " em " not in greeting


@pytest.mark.parametrize(
    ("numbers", "must_say", "must_not_say"),
    [
        ([3], "sai câu 3 — nó đang", "cả hai"),
        ([3, 5], "câu 3 và câu 5 — cả hai đang", "tất cả"),
        ([3, 5, 7], "câu 3, câu 5 và câu 7 — tất cả đang", "cả hai"),
    ],
)
def test_the_greeting_counts_correctly(
    numbers: list[int], must_say: str, must_not_say: str
) -> None:
    """Ba câu sai thì không phải "cả hai", và cũng không phải "và" giữa từng cặp một.

    Dữ liệu mẫu có đúng hai câu, và đó chính là cách một câu văn chỉ đúng với hai được viết
    ra rồi không bao giờ bị đem ra hỏi lại.
    """
    said = student_routes._greeting(numbers)

    assert must_say in said
    assert must_not_say not in said


def test_one_turn_per_position_is_the_database_s_job() -> None:
    """Hai lượt mở `stream` không được biến thành hai lời chào.

    StrictMode của React cố ý mở `stream` hai lần, và cả hai request đều đọc được cùng một
    history rỗng — nên cái chốt hỏi "đang tới lượt ai" không giúp được gì: nó cần một
    history để mà đọc. Chỉ một unique index mới phân định được, và `stream_reply` biến
    IntegrityError của bên thua thành một lượt phát lại.

    Bản thân cuộc đua thì không test được ở đây: bộ test này chạy trên một SQLite in-memory
    phục vụ mọi session từ cùng một connection, nên lượt `rollback` của bên thua kéo theo
    cả dòng của bên thắng. Thứ test được là thứ làm cho sự bảo vệ đó khả thi, và đó đúng là
    thứ một lượt dọn dẹp về sau sẽ xoá đi mà không nhận ra.
    """
    from schema.models import ChatMessage

    unique = {
        tuple(column.name for column in constraint.columns)
        for constraint in ChatMessage.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("attempt_id", "sequence") in unique
