# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Read `AGENTS.md` before changing anything tracked by git.** It is the single operating contract:
planning rules, invariants, validation commands, documentation ownership. Nothing is duplicated here,
so anything this file said and `AGENTS.md` did not has been moved there.

Three pointers, and nothing else:

- How to run the project, and the PowerShell execution-policy step needed once per session: `README.md`.
- Why the system is shaped this way, and how to name a new service: `docs/overview/architecture.md`.
- Rules for a specific directory: the `AGENTS.md` inside it. Four exist, one per service plus
  `packages/contracts`. They add to the root contract and never contradict it.

Run `.\dev.ps1 check` before claiming a change is done. It is the only thing standing between this
repo and a silently broken service boundary.
