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
    [ValidateSet('install', 'infra-up', 'infra-down', 'db-reset', 'be', 'ingest', 'agent', 'document', 'index', 'fe', 'test', 'check', 'typecheck', 'fmt', 'report', 'lab-ui', 'help')]
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
        # Hai package dùng chung đi trước, và đi một mình: BE khai cả aiafa-contracts
        # lẫn aiafa-schema như dependency, nên cài chúng trước giữ cho pip khỏi với tay
        # sang một index không có project nào như vậy. `schema` sau `contracts` vì nó
        # khai `contracts` là dependency của chính nó.
        Invoke-Step 'install contracts' { & $Python -m pip install -e "$RepoRoot\packages\contracts" }
        Invoke-Step 'install schema' { & $Python -m pip install -e "$RepoRoot\packages\schema" }
        Invoke-Step 'install be' { & $Python -m pip install -e "$RepoRoot\services\be[test]" }
        Invoke-Step 'install agent' { & $Python -m pip install -e "$RepoRoot\services\agent[test]" }
        Invoke-Step 'install document' { & $Python -m pip install -e "$RepoRoot\services\document[test]" }
        Invoke-Step 'install ingest' { & $Python -m pip install -e "$RepoRoot\services\ingest[test]" }
        Invoke-Step 'install dev tooling' { & $Python -m pip install ruff import-linter pre-commit pyyaml }
        Invoke-Step 'install frontend' { pnpm install }
        Write-Host "Done. Run '.\dev.ps1 check' to verify the import boundary." -ForegroundColor Green
    }

    'infra-up' {
        Invoke-Step 'start redis, postgres, minio, mongo and their admin UIs' { docker compose -f "$RepoRoot\docker-compose.infra.yml" up -d }
    }

    'infra-down' {
        Invoke-Step 'stop redis, postgres, minio, mongo and their admin UIs' { docker compose -f "$RepoRoot\docker-compose.infra.yml" down }
    }

    'lab-ui' {
        # Bốn UI như của infra-up, nhưng nhìn vào dữ liệu LAB: UI chạy ở máy này
        # (deploy/lab/admin-ui.yml) và đi vào lab qua một SSH tunnel; máy lab không chạy UI
        # nào ngoài FE. Chạy tới khi Ctrl+C, rồi tắt UI và đóng tunnel. Plan `lab-admin-ui`.
        $Key = if ($env:AIAFA_LAB_SSH_KEY) { $env:AIAFA_LAB_SSH_KEY } else { "$HOME\.ssh\aiafa-lab" }
        $Region = if ($env:AIAFA_LAB_REGION) { $env:AIAFA_LAB_REGION } else { 'ap-southeast-1' }
        $UiCompose = @('compose', '-p', 'aiafa-lab-ui', '-f', "$RepoRoot\deploy\lab\admin-ui.yml")
        # Kho -> (cổng tunnel ở máy này, cổng trong container). Cổng khác cổng của infra-up để
        # hai bên chạy song song (D3).
        $Stores = [ordered]@{ postgres = 15432, 5432; redis = 16379, 6379; minio = 19000, 9000; mongo = 27018, 27017 }
        $Secrets = [ordered]@{ POSTGRES_PASSWORD = 'LAB_POSTGRES_PASSWORD'; MONGO_PASSWORD = 'LAB_MONGO_PASSWORD'; MINIO_SECRET_KEY = 'LAB_MINIO_SECRET_KEY' }

        # Mật khẩu nằm trong một biến cục bộ và chỉ vào môi trường của phiên trong lúc một lệnh
        # compose đang chạy (D2): một Ctrl+C rơi vào chỗ khác không bỏ chúng lại trong phiên gọi
        # `.\dev.ps1`. Chưa đọc được thì điền giá trị giả -- `down` cũng nội suy `${…:?}` nhưng
        # không dùng tới mật khẩu, nên vẫn dọn được UI sót từ một lần chạy bị ngắt.
        $values = @{}
        $withSecrets = {
            param([string[]]$Command)
            foreach ($name in $Secrets.Values) {
                Set-Item "env:$name" $(if ($values[$name]) { $values[$name] } else { 'unset' })
            }
            try { & docker @UiCompose @Command } finally {
                foreach ($name in $Secrets.Values) { Remove-Item "env:$name" -ErrorAction SilentlyContinue }
            }
        }

        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $tunnel = $null
        try {
            Write-Host '==> find the lab' -ForegroundColor Cyan
            $ip = & terraform "-chdir=$RepoRoot\deploy\lab\terraform" output -raw public_ip
            if ($LASTEXITCODE -ne 0) { throw 'terraform output public_ip failed' }
            $ssh = @('-i', $Key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=accept-new')

            # IP container đổi mỗi lần container được tạo lại, nên tra ngay trước khi mở tunnel
            # (D1): compose của lab không publish cổng hạ tầng nào, kể cả trên 127.0.0.1.
            $names = $Stores.Keys | ForEach-Object { "aiafa-lab-$_-1" }
            $inspect = & ssh @ssh "ubuntu@$ip" sudo docker inspect @names
            if ($LASTEXITCODE -ne 0) { throw 'docker inspect over ssh failed: is every lab container running?' }
            $address = @{}
            foreach ($container in ($inspect -join "`n" | ConvertFrom-Json)) {
                $network = $container.NetworkSettings.Networks.PSObject.Properties | Select-Object -First 1
                $name = $container.Name.TrimStart('/')
                # Container dừng mà chưa xoá vẫn qua `docker inspect`, chỉ là không có IP.
                if (-not $container.State.Running -or -not $network.Value.IPAddress) { throw "$name is not running on the lab" }
                $address[$name] = $network.Value.IPAddress
            }

            Write-Host '==> read the lab passwords from SSM' -ForegroundColor Cyan
            $parameters = $Secrets.Keys | ForEach-Object { "/aiafa/lab/$_" }
            $pairs = & aws ssm get-parameters --region $Region --names @parameters --with-decryption --query 'Parameters[].[Name,Value]' --output json
            if ($LASTEXITCODE -ne 0) { throw 'aws ssm get-parameters failed' }
            foreach ($pair in ($pairs -join "`n" | ConvertFrom-Json)) {
                $values[$Secrets[$pair[0].Split('/')[-1]]] = $pair[1]
            }
            # Tên không có trong SSM nằm ở InvalidParameters, và aws vẫn trả exit code 0.
            $missing = $Secrets.Keys | Where-Object { -not $values[$Secrets[$_]] }
            if ($missing) { throw "missing in SSM: $(($missing | ForEach-Object { "/aiafa/lab/$_" }) -join ', ')" }

            Write-Host '==> open the ssh tunnel' -ForegroundColor Cyan
            $forwards = foreach ($store in $Stores.Keys) {
                $local, $remote = $Stores[$store]
                '-L'; "127.0.0.1:${local}:$($address["aiafa-lab-$store-1"]):$remote"
            }
            # Start-Process nối mảng bằng dấu cách mà không thêm nháy: đường dẫn khoá có dấu cách
            # phải tự bọc, khác với `& ssh` ở trên.
            $arguments = $ssh + @('-N', '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=30') + $forwards + "ubuntu@$ip" |
                ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }
            $tunnel = Start-Process ssh -ArgumentList $arguments -NoNewWindow -PassThru
            # Giữ handle ngay: thiếu nó thì ExitCode của một Start-Process -PassThru là rỗng.
            $null = $tunnel.Handle
            # Chờ tới khi cả bốn cổng nghe: UI bật trước tunnel thì kết nối đầu của chúng hỏng.
            foreach ($store in $Stores.Keys) {
                $port = $Stores[$store][0]
                for ($try = 0; ; $try++) {
                    if ($tunnel.HasExited) { throw "ssh tunnel exited with code $($tunnel.ExitCode)" }
                    $probe = New-Object Net.Sockets.TcpClient
                    try { $probe.Connect('127.0.0.1', $port); break } catch { if ($try -ge 30) { throw "tunnel port $port never opened" } } finally { $probe.Close() }
                    Start-Sleep -Milliseconds 500
                }
            }
            # Một tunnel cũ còn giữ cổng thì vòng trên qua ngay, còn ssh mới thoát vì
            # ExitOnForwardFailure: hỏi lại sau khi ssh kịp thử bind.
            Start-Sleep -Seconds 1
            if ($tunnel.HasExited) { throw "ssh tunnel exited with code $($tunnel.ExitCode): is another lab-ui still holding the ports?" }

            Write-Host '==> start the admin UIs' -ForegroundColor Cyan
            & $withSecrets -Command up, -d, --quiet-pull
            if ($LASTEXITCODE -ne 0) { throw 'docker compose up failed: is Docker Desktop running?' }

            Write-Host @'

Lab data, no sign-in -- every UI can write to the real lab:
  Postgres  http://127.0.0.1:18081
  Redis     http://127.0.0.1:18082
  Mongo     http://127.0.0.1:18083
  MinIO     http://127.0.0.1:18084

Ctrl+C to stop the UIs and close the tunnel.
'@ -ForegroundColor Green
            # Ngủ từng nhịp chứ không WaitForExit(): Ctrl+C không ngắt được một lời gọi .NET đang chặn.
            while (-not $tunnel.HasExited) { Start-Sleep -Milliseconds 500 }
            Write-Host "ssh tunnel exited with code $($tunnel.ExitCode)" -ForegroundColor Yellow
        } finally {
            Write-Host '==> stop the admin UIs and close the tunnel' -ForegroundColor Cyan
            if ($tunnel -and -not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force }
            & $withSecrets -Command down 2>$null | Out-Null
            $ErrorActionPreference = $previous
        }
    }

    'db-reset' {
        # Xoá sạch rồi dựng lại theo model hiện tại. Repo không giữ migration, nên đây là
        # đường duy nhất đưa một database cũ về khớp với code — và ở local thì dữ liệu là
        # thứ seed lại được. BE phải TẮT lúc chạy lệnh này.
        Invoke-Step 'reset database' { & $Python -m be.reset_db }
        # Bản thô trong kho nội dung trỏ về `documents.id` của database vừa xoá, nên giữ nó lại
        # là giữ trang mồ côi. Xoá qua `docker exec` chứ không qua `be.reset_db`: BE chỉ ĐỌC kho
        # nội dung (`content_reader`, check `the-content-reader-only-reads`), không xoá gì trong
        # đó. Tên database là mặc định của MONGO_DATABASE.
        Invoke-Step 'reset content store' { docker exec aiafa-mongo mongosh --quiet aiafa_content --eval 'db.dropDatabase()' }
    }

    'be' {
        # Nạp lại bằng `watchfiles`, không bằng `uvicorn --reload`. Trên Windows reloader của
        # uvicorn tắt worker cũ bằng `CTRL_C_EVENT`, mà tín hiệu ấy chỉ tới được process con khi
        # hai bên chung một console: chạy nền (không console) thì worker cũ không bao giờ nhận
        # lệnh tắt, vẫn phục vụ code cũ, và process con mồ côi còn giữ cổng sau khi cha chết. Đo
        # 21/10/2026 trên một app tối giản cùng cờ: --reload treo ngay lần nạp đầu, có hay không
        # có kênh SSE; watchfiles qua 15/15 lần với 30 kênh SSE mở. Trên BE thật (21/10/2026): 10/10
        # lần với kênh tài liệu của một tab đang mở, 2,4-2,6 s mỗi lần, một process giữ cổng.
        # watchfiles dừng và chạy lại **cả** uvicorn, nên không có socket nào chia giữa cha và con.
        # Trên Windows nó dừng uvicorn bằng `TerminateProcess` (`os.kill` với SIGINT), tức giết
        # cứng: phần tắt của lifespan không chạy lúc nạp lại. Ở dev thì được -- BE không giữ gì
        # phải ghi ra lúc tắt.
        # Chỉ theo dõi code BE chạy: theo cả repo thì sửa một test của AGENT cũng làm BE nạp lại.
        # --timeout-graceful-shutdown cho lần Ctrl+C trong một console (lúc ấy uvicorn nhận tín
        # hiệu thật): kênh SSE của mỗi tab không tự đóng, nên không có trần thì nó đứng mãi ở
        # "Waiting for connections to close" (đo 12/10/2026).
        # Giết process watchfiles bằng Stop-Process thì uvicorn con vẫn sống và giữ cổng: dừng cả
        # cây (`taskkill /T`), như mục "BE không lên lại" của docs/local-development.md.
        # Lệnh con được tách bằng shlex không theo POSIX: AIAFA_PYTHON có khoảng trắng sẽ vỡ.
        & $Python -m watchfiles --filter python `
            "$Python -m uvicorn be.main:app --timeout-graceful-shutdown 3 --host 127.0.0.1 --port 8000" `
            "$RepoRoot\services\be\src" "$RepoRoot\packages\contracts\src" "$RepoRoot\packages\schema\src"
    }

    'ingest' {
        # Service thứ năm. Nó tiêu thụ kết quả xử lý tài liệu và ghi chúng vào Postgres --
        # việc mà không ai đang chờ, nên nó không sống được trong một request. Nó giữ
        # credential database, khác `agent` và `document`, và không sở hữu một quyết định
        # nào. Trước plan 2c nó là process thứ hai của `be`, và không chỗ nào nói được
        # process nào được làm gì.
        & "$Scripts\arq.exe" ingest.worker.WorkerSettings
    }

    'agent' {
        & "$Scripts\arq.exe" agent.worker.WorkerSettings
    }

    'document' {
        & "$Scripts\arq.exe" document.ocr_worker.WorkerSettings
    }

    'index' {
        # Process thứ hai của `services/document`: document agent dựng cây mục lục rồi mới báo
        # tài liệu 'sẵn sàng' (plan 3c). Không chạy nó thì mọi tệp đứng ở 'đang xử lý' rồi
        # thành 'xử lý hỏng' sau 300 s -- bản thô đã có, nhưng không ai dựng cây.
        & "$Scripts\arq.exe" document.index_worker.WorkerSettings
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
  infra-up     Start Redis, Postgres, MinIO, MongoDB and their admin UIs in Docker
  infra-down   Stop them
  db-reset     Wipe the database and the content store, rebuild from the models, seed (BE off)
  be           Run the BE API on http://localhost:8000
  ingest       Run INGEST, the worker that writes what DOCUMENT reports
  agent        Run the AGENT worker
  document     Run the DOCUMENT worker that reads uploaded files
  index        Run the DOCUMENT INDEX worker that builds each document's tree
  fe           Run the FE dev server on http://localhost:5173
  test         Run pytest and vitest
  typecheck    Run tsc over the frontend without building
  check        Run ruff, the import boundary check and the repo contract checks
  fmt          Format and autofix
  report       Build docs/report/report.pdf with XeLaTeX
  lab-ui       Open the lab's Postgres, Redis, Mongo and MinIO in local admin UIs over ssh

First run in a session may need:
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
'@
    }
}
