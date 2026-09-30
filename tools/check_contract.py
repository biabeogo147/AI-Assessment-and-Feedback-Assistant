"""Repo-level checks that no single service can make about itself.

Run by `.\\dev.ps1 check`. Each check here enforces one row of the Invariants
table in AGENTS.md that would otherwise depend on somebody remembering.

This script imports both services' settings, which service code is forbidden to
do. That is deliberate and safe: `tools/` sits outside `services/` and outside
`import-linter`'s root_packages, and auditing both sides is the whole job. No
code that ships is allowed to do the same.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 172: one line above the 171 below, bought on 2026-09-30 by the rule that the
# options in a clarifying question are written by BE from rows it read, never by
# the model (ADR-23). It earned a row because it is the kind of rule a later
# change reintroduces by accident -- the first implementation filtered what the
# model wrote, and that leaked in both directions. The decision record is in
# 2026-09-30-teacher-harness-foundation-plan.md.
#
# 171: one line above the 170 below, bought on 2026-09-29 by a new cross-service
# invariant -- the model-call ceiling must sit inside BE's patience for a job --
# which earned a row in the Invariants table. The rule for raising this has been
# followed: a decision record in the plan says what the line was spent on.
#
# 170 was set after writing the contract, not before. The first guess was 140,
# but every section that survived trimming is a rule, and the two longest are the
# ownership and invariant tables -- the densest content in the file. Cutting real
# rules to satisfy an invented number is the wrong trade. The cap exists to stop
# drift from here, so raise it only alongside a decision record explaining what
# new rule justified the growth.
AGENTS_MD_MAX_LINES = 172
CHILD_AGENTS_MD_MAX_LINES = 25

CHILD_AGENTS_FILES = (
    "services/be/AGENTS.md",
    "services/agent/AGENTS.md",
    "services/fe/AGENTS.md",
    "packages/contracts/AGENTS.md",
)

# Anything that would let AGENT reach a database directly. Redis is not on this
# list: AGENT needs the queue, and REDIS_URL is a DSN but not a database one.
DB_CREDENTIAL_PATTERN = re.compile(
    r"POSTGRES|MONGO|DATABASE_URL|\bDSN\b|PASSWORD|psycopg|sqlalchemy|motor|pymongo",
    re.IGNORECASE,
)

ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=")


def _fail(check: str, detail: str) -> str:
    return f"FAIL {check}\n      {detail}"


def check_env_example_has_no_orphans() -> str | None:
    """Every variable in .env.example must be read by a service's Settings.

    Returns:
        None when the check passes, otherwise a failure message.

    Raises:
        ImportError: If the services are not installed. Run `.\\dev.ps1 install`.
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
    """AGENT must stay free of database access so a job carries what it needs.

    Returns:
        None when the check passes, otherwise a failure message naming the files.
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
    """A whole AGENT job must time out before the job BE is waiting on does.

    Neither service can check this alone: the ceiling on one model call and the
    number of attempts a job may make live in AGENT's settings, the patience
    for a job lives in BE's, and neither imports the other. Get the order wrong
    and a slow model produces the worst shape of failure -- BE gives up and
    answers 503 while the worker is still working, so the student sees an error
    for an answer that then arrives and is thrown away.

    The attempt count is the half that is easy to forget. This check compared a
    *single* call against BE's patience until the authoring loop appeared, and
    was quietly wrong for as long as that loop existed: one job had become
    three calls and nothing said so.

    Returns:
        None when the worst-case job fits inside BE's patience, otherwise a
        failure message naming every number involved.
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
    """Length caps are the only workable proxy for "do not restate the root".

    A file already at its cap has no room to copy a rule from AGENTS.md.

    Returns:
        None when every file is within its cap, otherwise a failure message.
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
    """Every dev.ps1 task named in AGENTS.md must actually be runnable.

    Guards the Validation table against drifting away from the script it names.

    Returns:
        None when every named task exists, otherwise a failure message.
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


CHECKS = (
    check_env_example_has_no_orphans,
    check_agent_holds_no_database_credentials,
    check_model_call_fits_inside_the_job_waiting_for_it,
    check_contract_files_stay_short,
    check_named_dev_tasks_exist,
)


def main() -> int:
    """Run every repo-level check and report all failures, not just the first.

    Returns:
        0 when everything passes, 1 otherwise.

    Side effects:
        Writes results to stdout.
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
