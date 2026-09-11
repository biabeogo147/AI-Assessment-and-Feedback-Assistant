<#
.SYNOPSIS
  Single entry point for local development tasks.

.DESCRIPTION
  Replaces a Makefile, because `make` is not installed and the services run
  natively rather than inside a container that could provide it.

  Calls the conda environment's interpreter by absolute path instead of running
  `conda activate`. That command needs conda-hook.ps1 to be sourced first, which
  is not guaranteed in a child PowerShell session or in PyCharm's terminal.

  Override the interpreter with the AIAFA_PYTHON environment variable if your
  conda environment lives somewhere else.

.EXAMPLE
  .\dev.ps1 install
  .\dev.ps1 be
  .\dev.ps1 check
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'infra-up', 'infra-down', 'be', 'agent', 'fe', 'test', 'check', 'typecheck', 'fmt', 'help')]
    [string]$Task = 'help'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot

if ($env:AIAFA_PYTHON) {
    $Python = $env:AIAFA_PYTHON
} else {
    $Python = 'D:\Anaconda\envs\AI-Assessment-and-Feedback-Assistant\python.exe'
}

if (-not (Test-Path $Python)) {
    Write-Error "Python interpreter not found at '$Python'. Set AIAFA_PYTHON to your conda env's python.exe."
}

$Scripts = Split-Path $Python -Parent | Join-Path -ChildPath 'Scripts'

function Invoke-Step {
    param([string]$Label, [scriptblock]$Body)
    Write-Host "==> $Label" -ForegroundColor Cyan

    # Windows PowerShell 5.1 wraps a native command's stderr in an ErrorRecord,
    # and docker compose, pip and pnpm all write ordinary progress there. Under
    # ErrorActionPreference = Stop that aborts a step which actually succeeded --
    # `dev.ps1 infra-up` reported failure while Redis came up healthy. Exit code
    # is the only reliable verdict for a native command, so judge by that.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Body } finally { $ErrorActionPreference = $previous }

    if ($LASTEXITCODE -ne 0) { Write-Error "$Label failed with exit code $LASTEXITCODE" }
}

switch ($Task) {
    'install' {
        # contracts goes first and on its own: BE and AGENT declare aiafa-contracts
        # as a dependency, and installing it beforehand keeps pip from reaching
        # for an index that has no such project.
        Invoke-Step 'install contracts' { & $Python -m pip install -e "$RepoRoot\packages\contracts" }
        Invoke-Step 'install be' { & $Python -m pip install -e "$RepoRoot\services\be[test]" }
        Invoke-Step 'install agent' { & $Python -m pip install -e "$RepoRoot\services\agent[test]" }
        Invoke-Step 'install dev tooling' { & $Python -m pip install ruff import-linter pre-commit }
        Invoke-Step 'install frontend' { pnpm install }
        Write-Host "Done. Run '.\dev.ps1 check' to verify the import boundary." -ForegroundColor Green
    }

    'infra-up' {
        Invoke-Step 'start redis and postgres' { docker compose -f "$RepoRoot\docker-compose.infra.yml" up -d }
    }

    'infra-down' {
        Invoke-Step 'stop redis and postgres' { docker compose -f "$RepoRoot\docker-compose.infra.yml" down }
    }

    'be' {
        & $Python -m uvicorn be.main:app --reload --host 127.0.0.1 --port 8000
    }

    'agent' {
        & "$Scripts\arq.exe" agent.worker.WorkerSettings
    }

    'fe' {
        pnpm --filter fe dev
    }

    'test' {
        Invoke-Step 'pytest' { & $Python -m pytest }
        Invoke-Step 'vitest' { pnpm --filter fe test }
    }

    'typecheck' {
        # tsc is otherwise only reachable through `fe build`, which also bundles.
        Invoke-Step 'tsc' { pnpm --filter fe exec tsc --noEmit }
    }

    'check' {
        Invoke-Step 'ruff' { & $Python -m ruff check $RepoRoot }
        Invoke-Step 'lint-imports' { & "$Scripts\lint-imports.exe" --config "$RepoRoot\pyproject.toml" }
        # Repo-level invariants no single service can check about itself.
        Invoke-Step 'repo contracts' { & $Python "$RepoRoot\tools\check_contract.py" }
    }

    'fmt' {
        Invoke-Step 'ruff format' { & $Python -m ruff format $RepoRoot }
        Invoke-Step 'ruff fix' { & $Python -m ruff check --fix $RepoRoot }
    }

    default {
        Write-Host @'
Usage: .\dev.ps1 <task>

  install      Install Python packages editable and frontend dependencies
  infra-up     Start Redis and Postgres in Docker
  infra-down   Stop them
  be           Run the BE API on http://localhost:8000
  agent        Run the AGENT worker
  fe           Run the FE dev server on http://localhost:5173
  test         Run pytest and vitest
  typecheck    Run tsc over the frontend without building
  check        Run ruff, the import boundary check and the repo contract checks
  fmt          Format and autofix

First run in a session may need:
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
'@
    }
}
