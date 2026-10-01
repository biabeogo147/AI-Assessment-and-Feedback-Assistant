<#
.SYNOPSIS
  Một cửa duy nhất cho mọi task phát triển ở máy local.

.DESCRIPTION
  Thay cho một Makefile, vì `make` không được cài và các service chạy native chứ
  không phải trong một container có thể cung cấp nó.

  Gọi interpreter của conda environment bằng đường dẫn tuyệt đối thay vì chạy
  `conda activate`. Lệnh đó cần conda-hook.ps1 được source trước, mà điều đó
  không chắc chắn trong một phiên PowerShell con hay trong terminal của PyCharm.

  Ghi đè interpreter bằng biến môi trường AIAFA_PYTHON nếu conda environment của
  bạn nằm ở chỗ khác.

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

    # Windows PowerShell 5.1 bọc stderr của một lệnh native vào một ErrorRecord,
    # mà docker compose, pip và pnpm đều ghi tiến độ bình thường ra đó. Dưới
    # ErrorActionPreference = Stop thì điều đó bỏ dở một bước đã thật sự thành
    # công -- `dev.ps1 infra-up` báo thất bại trong khi Redis lên healthy. Exit
    # code là phán quyết đáng tin duy nhất cho một lệnh native, nên hãy xử theo
    # nó.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Body } finally { $ErrorActionPreference = $previous }

    if ($LASTEXITCODE -ne 0) { Write-Error "$Label failed with exit code $LASTEXITCODE" }
}

switch ($Task) {
    'install' {
        # contracts đi trước và đi một mình: BE và AGENT khai aiafa-contracts như
        # một dependency, và cài nó trước giữ cho pip khỏi với tay sang một index
        # không có project nào như vậy.
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
        # Nếu không có đây thì tsc chỉ với tới được qua `fe build`, mà lệnh đó
        # bundle luôn.
        Invoke-Step 'tsc' { pnpm --filter fe exec tsc --noEmit }
    }

    'check' {
        Invoke-Step 'ruff' { & $Python -m ruff check $RepoRoot }
        Invoke-Step 'lint-imports' { & "$Scripts\lint-imports.exe" --config "$RepoRoot\pyproject.toml" }
        # Những invariant ở tầm repo mà không service nào tự kiểm được về chính nó.
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
