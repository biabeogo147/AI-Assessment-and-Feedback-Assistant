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
    [ValidateSet('install', 'infra-up', 'infra-down', 'db-reset', 'be', 'be-worker', 'agent', 'document', 'fe', 'test', 'check', 'typecheck', 'fmt', 'report', 'help')]
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
        Invoke-Step 'install document' { & $Python -m pip install -e "$RepoRoot\services\document[test]" }
        Invoke-Step 'install dev tooling' { & $Python -m pip install ruff import-linter pre-commit }
        Invoke-Step 'install frontend' { pnpm install }
        Write-Host "Done. Run '.\dev.ps1 check' to verify the import boundary." -ForegroundColor Green
    }

    'infra-up' {
        Invoke-Step 'start redis, postgres and minio' { docker compose -f "$RepoRoot\docker-compose.infra.yml" up -d }
    }

    'infra-down' {
        Invoke-Step 'stop redis, postgres and minio' { docker compose -f "$RepoRoot\docker-compose.infra.yml" down }
    }

    'db-reset' {
        # Xoá sạch rồi dựng lại theo model hiện tại. Repo không giữ migration, nên đây là
        # đường duy nhất đưa một database cũ về khớp với code — và ở local thì dữ liệu là
        # thứ seed lại được. BE phải TẮT lúc chạy lệnh này.
        Invoke-Step 'reset database' { & $Python -m be.reset_db }
    }

    'be' {
        & $Python -m uvicorn be.main:app --reload --host 127.0.0.1 --port 8000
    }

    'be-worker' {
        # Process thứ hai của BE. Nó tiêu thụ kết quả xử lý tài liệu và ghi chúng vào
        # Postgres -- việc mà không ai đang chờ, nên nó không sống được trong một
        # request. Tách khỏi `be` chứ không nhúng vào lifespan của uvicorn: `be` chạy
        # với --reload, nên mỗi lần sửa một file Python là một lần cắt ngang job.
        & "$Scripts\arq.exe" be.worker.WorkerSettings
    }

    'agent' {
        & "$Scripts\arq.exe" agent.worker.WorkerSettings
    }

    'document' {
        & "$Scripts\arq.exe" document.worker.WorkerSettings
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
        # `PYTHONIOENCODING` không phải thừa. `rich` -- thứ import-linter dùng để vẽ --
        # nhìn stdout: nối vào console thì nó nói UTF-8, còn nối vào **pipe** thì nó rơi
        # về bộ render Windows cũ và encode bằng cp1252, rồi chết vì cái emoji trong
        # chuỗi "Building graph...". Đo được ngày 06/10/2026: `.\dev.ps1 check 2>&1 | ...`
        # báo đỏ trong khi cả hai hợp đồng đều KEPT.
        #
        # Và đó mới là phần đáng sợ: lỗi encode xảy ra **sau** khi check đã chạy, nên nó
        # nuốt kết quả thật và trả về exit 1 bất kể hợp đồng còn hay vỡ. Một cổng báo đỏ
        # khi mọi thứ đúng sẽ dạy người ta bỏ qua nó, rồi nó im lặng lúc có vi phạm thật.
        Invoke-Step 'lint-imports' {
            $before = $env:PYTHONIOENCODING
            $env:PYTHONIOENCODING = 'utf-8'
            try { & "$Scripts\lint-imports.exe" --config "$RepoRoot\pyproject.toml" }
            finally { $env:PYTHONIOENCODING = $before }
        }
        # Những invariant ở tầm repo mà không service nào tự kiểm được về chính nó.
        Invoke-Step 'repo contracts' { & $Python "$RepoRoot\tools\check_contract.py" }
    }

    'fmt' {
        Invoke-Step 'ruff format' { & $Python -m ruff format $RepoRoot }
        Invoke-Step 'ruff fix' { & $Python -m ruff check --fix $RepoRoot }
    }

    'report' {
        # XeLaTeX, không phải pdfLaTeX: báo cáo là tiếng Việt. `-cd` bắt latexmk chuyển vào
        # thư mục của file, nhờ đó \input{preamble} và \graphicspath{{figures/}} giải được, và
        # mọi file phụ nằm gọn trong docs/report thay vì rải ra gốc repo.
        Invoke-Step 'latexmk' {
            & latexmk -xelatex -cd -interaction=nonstopmode -halt-on-error `
                "$RepoRoot\docs\report\report.tex"
        }
    }

    default {
        Write-Host @'
Usage: .\dev.ps1 <task>

  install      Install Python packages editable and frontend dependencies
  infra-up     Start Redis, Postgres and MinIO in Docker
  infra-down   Stop them
  db-reset     Wipe the database and rebuild it from the models, then seed (BE must be off)
  be           Run the BE API on http://localhost:8000
  be-worker    Run the BE worker that writes what DOCUMENT reports
  agent        Run the AGENT worker
  document     Run the DOCUMENT worker that reads uploaded files
  fe           Run the FE dev server on http://localhost:5173
  test         Run pytest and vitest
  typecheck    Run tsc over the frontend without building
  check        Run ruff, the import boundary check and the repo contract checks
  fmt          Format and autofix
  report       Build docs/report/report.pdf with XeLaTeX

First run in a session may need:
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
'@
    }
}
