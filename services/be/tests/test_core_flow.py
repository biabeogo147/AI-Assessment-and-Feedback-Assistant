"""The two-phase flow, end to end, against an in-memory database.

AGENT is stubbed at the gateway rather than imported: BE and AGENT may not
depend on each other, and a test that reached into the worker to get a question
back would be the first crack in that wall. The stub returns the same shape the
real task does, built from `contracts`, which both services share.

What these tests assert is deliberately not the wording of anything. They check
the rules that outlive both the mock and the model: the floor, the ceiling of
three rounds, who may read what, and what never appears in a student payload.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import student_routes
from be.db import bind_sessions, prepare_schema
from be.models import Publication, QuestionOutcome
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


@pytest_asyncio.fixture
async def client(monkeypatch) -> AsyncClient:
    """Build an app on a fresh in-memory database with AGENT stubbed."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)

    monkeypatch.setattr(student_routes, "run_task", _fake_run_task)

    app = FastAPI()
    app.include_router(student_router)
    app.state.queue_pool = object()

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

    monkeypatch.setattr(student_routes, "run_task", echo_the_origin)

    refused = await client.post(f"/api/attempts/{attempt_id}/rounds", headers=STUDENT)
    assert refused.status_code == 503
    assert wrong["stem"][:20] in refused.json()["detail"]

    # The refusal must not have spent a round.
    panel = (await client.get(f"/api/attempts/{attempt_id}/remediation", headers=STUDENT)).json()
    assert panel["remaining"][0]["rounds_used"] == 0


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

    async def capture(pool, settings, task_name, payload) -> dict:
        seen.update(payload)
        return {"schema_version": 1, "request_id": payload["request_id"], "text": "…"}

    monkeypatch.setattr(student_routes, "run_task", capture)
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
