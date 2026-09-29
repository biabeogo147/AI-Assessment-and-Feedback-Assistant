"""The two-phase flow, end to end, against an in-memory database.

AGENT is stubbed at the gateway rather than imported: BE and AGENT may not
depend on each other, and a test that reached into the worker to get a question
back would be the first crack in that wall. The stub returns the same shape the
real task does, built from `contracts`, which both services share.

What these tests assert is deliberately not the wording of anything. They check
the rules that outlive both the mock and the model: the floor, the ceiling of
three rounds, who may read what, and what never appears in a student payload.
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
from be.db import bind_sessions, prepare_schema
from be.models import Publication, QuestionOutcome, RemediationRound
from be.seed import seed_if_empty
from be.student_routes import router as student_router
from contracts import GeneratedOption, GeneratedQuestion, RetryQuestionCompleted, SolutionMethod

STUDENT = {"X-Actor": "student:HS2026-1204"}
OTHER_STUDENT = {"X-Actor": "student:HS2026-1205"}

_RETRY = GeneratedQuestion(
    stem="Đề của lượt làm lại",
    options=(
        GeneratedOption(label="A", text="sai", is_correct=False, error_label="lỗi A"),
        GeneratedOption(label="B", text="đúng", is_correct=True),
        GeneratedOption(label="C", text="sai", is_correct=False, error_label="lỗi C"),
    ),
    methods=(
        SolutionMethod(title="Cách 1", body="..."),
        SolutionMethod(title="Cách 2", body="..."),
    ),
    learning_objective="mock",
)


async def _fake_run_task(pool, settings, task_name, payload) -> dict:
    """Stand in for AGENT, returning the shape each task promises.

    The retry stem carries its round number because BE refuses a retry that
    repeats the question it replaces or an earlier round (ADR-17). A stub
    returning one fixed stem would be rejected on round two -- correctly, which
    is why the stub varies rather than the rule bending.
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
    """Get past the opening turn so the next stream is a real model turn.

    The greeting is written by BE and never reaches AGENT, so a test that wants
    to watch a model answer has to ask it something first.
    """
    await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    await client.post(
        f"/api/attempts/{attempt_id}/chat/messages",
        json={"text": "câu 5 mình chưa hiểu vì sao sai"},
        headers=STUDENT,
    )


async def _fake_stream_task(pool, settings, task_name, payload, channel, silence=None):
    """Stand in for AGENT on the streaming path, publishing nothing.

    A worker that does not stream -- prepared content, or a provider without
    token streaming -- is a supported case, not a degraded one, so this is the
    stub the rest of the suite runs against. The live path has its own test.
    """
    yield "result", await _fake_run_task(pool, settings, task_name, payload)


async def _nothing_finished_yet(pool, settings, job_id) -> tuple[str, object]:
    """Default reading of a queued job: still running."""
    return "pending", None


class FakeQueue:
    """A queue that accepts jobs and remembers them.

    `object()` used to stand in here, which meant `enqueue_task` raised,
    swallowed it, and pre-generation quietly did nothing -- the suite passed
    because the system correctly fell back to writing questions on the spot.
    Green for the wrong reason is worse than red.
    """

    def __init__(self) -> None:
        self.jobs: list[tuple[str, str, dict]] = []

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        job_id = f"job-{len(self.jobs)}"
        self.jobs.append((job_id, name, payload))
        return SimpleNamespace(job_id=job_id)

    def payload_for(self, job_id: str) -> dict:
        """The payload a job was queued with."""
        return next(payload for queued, _, payload in self.jobs if queued == job_id)


@pytest_asyncio.fixture
async def client(monkeypatch) -> AsyncClient:
    """Build an app on a fresh in-memory database with AGENT stubbed."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)

    # Patched inside the gateway rather than at the route, so `start_round`
    # still runs the real ask-and-recheck loop: the ADR-18 and ADR-17 checks
    # and the re-ask on rejection stay under test instead of being stubbed out.
    monkeypatch.setattr(agent_gateway, "run_task", _fake_run_task)
    monkeypatch.setattr(student_routes, "stream_task", _fake_stream_task)
    # Nothing is collected unless a test says a job finished. The three-way
    # reading of a job's state is the gateway's business and is tested there.
    monkeypatch.setattr(student_routes, "collect_result", _nothing_finished_yet)

    app = FastAPI()
    app.include_router(student_router)
    app.state.queue_pool = FakeQueue()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _sessionmaker():
    """Reach the same session factory the app uses, for arranging state."""
    assert db_module._SESSION_MAKER is not None
    return db_module._SESSION_MAKER


async def _start_and_submit(client: AsyncClient, correct_count: int) -> dict:
    """Run phase 1, answering the first `correct_count` questions correctly."""
    assignments = (await client.get("/api/me/assignments", headers=STUDENT)).json()
    assessment_id = assignments[0]["assignment_id"]
    attempt = (
        await client.post(f"/api/assignments/{assessment_id}/attempts", headers=STUDENT)
    ).json()

    for index, question in enumerate(attempt["questions"]):
        # The payload hides which option is right, so pick by position: the
        # seed puts the correct option first on every question.
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
    """A running attempt must not tell the student which option is correct."""
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
    """ADR-08: confidence, misconception and review reason never reach a student."""
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
    """Four right out of six scores 4.0, and the two wrong ones stay open."""
    submitted = await _start_and_submit(client, correct_count=4)
    assert submitted["phase1_score"] == 4.0
    assert len(submitted["wrong_question_ids"]) == 2

    attempt_id = submitted["attempt_id"]
    result = (await client.get(f"/api/attempts/{attempt_id}/result", headers=STUDENT)).json()
    assert result["state"] == "cần-chữa"
    assert result["total_score"] == 4.0


@pytest.mark.asyncio
async def test_submitting_twice_is_refused(client: AsyncClient) -> None:
    """Submitting ends phase 1; a one-way door pressed twice is not idempotent."""
    submitted = await _start_and_submit(client, correct_count=6)
    again = await client.post(f"/api/attempts/{submitted['attempt_id']}/submit", headers=STUDENT)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_another_student_cannot_read_this_attempt(client: AsyncClient) -> None:
    """Ownership is enforced, and a stranger is told 404 rather than 403."""
    submitted = await _start_and_submit(client, correct_count=6)
    response = await client.get(
        f"/api/attempts/{submitted['attempt_id']}/result", headers=OTHER_STUDENT
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_solution_is_closed_until_the_paper_is_submitted(client: AsyncClient) -> None:
    """The dialog carries the correct option, so it waits for submission."""
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
    """Submit an attempt without answering anything."""
    response = await client.post(f"/api/attempts/{attempt['attempt_id']}/submit", headers=STUDENT)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_a_round_lifts_a_wrong_question_to_half_credit(client: AsyncClient) -> None:
    """Getting the retry right closes the question at 0.5, never at 1.0."""
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
    """ADR-17 caps remediation at three rounds, and a fourth is refused."""
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
    """Phase 1 sets a floor: no path in phase 2 may lower a mark."""
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
    """ADR-17: handing back the same stem tests memory, not understanding."""
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

    # The refusal must not have spent a round.
    panel = (await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)).json()
    assert panel["items"][0]["rounds_used"] == 0


@pytest.mark.asyncio
async def test_only_one_round_may_be_open(client: AsyncClient) -> None:
    """Two tabs must not buy two clocks."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    first = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert first.status_code == 201
    second = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_the_panel_warns_when_a_round_would_be_cut(client: AsyncClient) -> None:
    """ADR-15: BE compares the budget with the time left, not the client."""
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
    """Past the deadline phase 2 is over, whatever the screen still shows."""
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
    """The refusal must survive concurrency, not just a tidy sequence of calls.

    A review on 2026-09-11 fired two of these together and got two rounds: the
    route checked first and wrote second, and both requests passed the check.
    Sequential tests never touch that gap, which is why this one runs them with
    `gather`.
    """
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    first, second = await asyncio.gather(
        client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT),
        client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT),
    )

    codes = sorted([first.status_code, second.status_code])
    assert codes == [201, 409], f"expected one round and one refusal, got {codes}"

    # The count is the invariant. Which of the two survived is not: an
    # in-memory SQLite keeps one connection for every session, so the loser's
    # rollback can take the winner's uncommitted row with it. That artefact
    # belongs to the test database, and never happens on Postgres.
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
    """Whose turn it is is decided server side, not by how often a client asks."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    first = await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    second = await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    assert first.status_code == 200
    assert second.status_code == 200

    history = (await client.get(f"/api/attempts/{attempt_id}/chat", headers=STUDENT)).json()
    assert len(history["messages"]) == 1

    # Once the student speaks, it is the assistant's turn again.
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
    """The assistant says "câu 5" out loud, so the number has to travel."""
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    seen: dict = {}

    async def capture(pool, settings, task_name, payload, channel, silence=None):
        seen.update(payload)
        yield "result", {"schema_version": 1, "request_id": payload["request_id"], "text": "…"}

    monkeypatch.setattr(student_routes, "stream_task", capture)
    await _ask_something(client, attempt_id)
    await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)

    # The seed's last two questions are the ones answered wrongly.
    assert seen["question_numbers"] == [5, 6]


@pytest.mark.asyncio
async def test_chat_history_locks_when_the_attempt_ends(client: AsyncClient) -> None:
    """A finished attempt keeps its conversation readable and refuses new turns."""
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
    """ADR-19: the unit of a report is the attempt's conversation, not one turn."""
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
    """Pieces published by AGENT are forwarded, and the whole is still stored.

    The two halves matter together. Forwarding alone would be an animation over
    nothing; storing alone is what the system had before. A reader who reloads
    must find the same sentence they watched appear.
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
    # The piece with a line break in it is written as two `data:` lines, which
    # is what the format says. One line would have truncated the sentence.
    assert "data: em chọn B,\ndata: \n" in body
    assert body.count("event: done") == 1

    history = (await client.get(f"/api/attempts/{attempt_id}/chat", headers=STUDENT)).json()
    assert history["messages"][-1]["text"] == "Câu 5 em chọn B,\nmà B là khoảng nghịch biến."


@pytest.mark.asyncio
async def test_a_model_failure_arrives_in_the_stream_not_as_a_status_code(
    client: AsyncClient, monkeypatch
) -> None:
    """Once the stream is open the status line is already sent.

    So a failure has to be told in-band. The turn must not be stored: the
    student's own message is still the last word, which is what makes the next
    request generate a fresh answer rather than replay a broken one.
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
    # The greeting and the question stand; no broken answer was stored after
    # them, so the student's message is still the last word and the next
    # request generates a fresh turn.
    assert [m["role"] for m in history["messages"]] == ["assistant", "student"]


@pytest.mark.asyncio
async def test_submitting_starts_writing_the_next_round(client: AsyncClient) -> None:
    """The head start begins the moment the paper is handed in.

    Not when the student presses "Làm bài mới" -- by then they are watching a
    blank screen for as long as a model takes.
    """
    submitted = await _start_and_submit(client, correct_count=4)

    queue = client._transport.app.state.queue_pool
    asked = [payload for _, name, payload in queue.jobs if name.endswith("retry_question")]

    assert len(asked) == len(submitted["wrong_question_ids"]) == 2
    assert {payload["round_index"] for payload in asked} == {1}
    # AGENT is told what the student picked, or the retry cannot aim at the
    # mistake it is supposed to test (ADR-17).
    assert all(payload["wrong_option_label"] for payload in asked)


@pytest.mark.asyncio
async def test_a_question_written_ahead_opens_the_round_without_asking_again(
    client: AsyncClient, monkeypatch
) -> None:
    """The whole point: pressing the button costs no model call.

    `run_task` is replaced by something that fails the test if it runs, so a
    regression that quietly reverts to writing on the spot cannot pass.
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

    # Visiting the tutoring screen is what collects the finished work.
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
    """Job results live an hour; a phase 2 deadline can be days away.

    A student who closes the tab and comes back tomorrow finds the answer gone.
    The row must not sit on `pending` forever waiting for something that no
    longer exists -- it is dropped, and the next visit queues a replacement.
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
    """Pre-generation is an optimisation. Submitting a paper is not.

    So a queue that is down costs the head start and nothing else, and the
    round still opens the old way.
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
    """Writing ahead must not become a way around ADR-18.

    The rules were enforced inside `ask_for_retry_question`, which only the
    write-on-the-spot path goes through. From this phase on, writing ahead is
    the normal path -- so a question with two correct answers would reach the
    student, and BE grades a round by exactly that flag.
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
    """The round screen asks this endpoint on mount, and that must cost nothing.

    `rounds_used` does not move until a round is submitted, so during one the
    next index still reads as the current round's -- which already has its
    questions. Every job queued here would be answered, stored, never used,
    and orphaned the moment the round is handed in.
    """
    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]
    queue = client._transport.app.state.queue_pool

    await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    during = len(queue.jobs)

    # What Round.tsx does when it mounts, and again on every refresh.
    await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)
    await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)

    assert len(queue.jobs) == during, "opening the round screen queued work nobody can use"


@pytest.mark.asyncio
async def test_a_job_that_failed_is_not_asked_again_forever(
    client: AsyncClient, monkeypatch
) -> None:
    """A job that ran and raised will raise the same way next time.

    Deleting its row would re-queue it on every screen the student opens, for
    as long as the bug lasts, silently. "Aged out" and "failed" are different
    endings and only the first is worth repeating.
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
    """The opening turn never reaches AGENT.

    It used to: a job, a wait, a stream, to produce a sentence that barely
    varies. One wasted model call on every paper handed in. Nothing about that
    saving is visible on screen, so a tidy-up could put it back without anybody
    noticing -- which is what this test is for.
    """

    async def must_not_run(*args, **kwargs):
        raise AssertionError("the greeting asked the model")
        yield  # pragma: no cover -- keeps this an async generator

    monkeypatch.setattr(student_routes, "stream_task", must_not_run)

    submitted = await _start_and_submit(client, correct_count=4)
    attempt_id = submitted["attempt_id"]

    response = await client.get(f"/api/attempts/{attempt_id}/chat/stream", headers=STUDENT)
    assert response.status_code == 200

    history = (await client.get(f"/api/attempts/{attempt_id}/chat", headers=STUDENT)).json()
    greeting = history["messages"][0]["text"]

    assert greeting.startswith("Mình là trợ lý Kriky")
    # It names what is on offer, so the student knows what to ask about before
    # they have read the panel.
    assert "câu 5 và câu 6" in greeting
    assert "bạn" in greeting and " em " not in greeting
