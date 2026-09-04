# Monorepo Foundation Plan

## Goal

Dựng khung monorepo cho FE, BE và AGENT chạy được một luồng end-to-end trên máy local, với ranh giới giữa các service được cưỡng chế tự động thay vì bằng quy ước.

## Scope

Trong phạm vi:

- Cấu trúc `services/` và `packages/` kèm manifest riêng cho từng service.
- `packages/contracts` chứa message contract giữa BE và AGENT.
- Luồng end-to-end tối giản qua Redis: FE gọi BE, BE enqueue job, AGENT xử lý, kết quả quay lại FE.
- `import-linter` cấu hình trong `pyproject.toml` và chạy tự động qua pre-commit.
- `dev.ps1` làm điểm vào lệnh cho Windows.
- `docker-compose.infra.yml` chỉ chứa Redis.
- `docs/overview/architecture.md` và `docs/diagrams/system-architecture.drawio`.
- Sửa `.gitignore` đang hỏng và bổ sung mục cho Node.

Ngoài phạm vi:

- Postgres, MongoDB, ORM model và migration.
- Container hoá FE, BE, AGENT.
- Auth và phân quyền.
- Công thức `Confidence`, cập nhật `Mastery`, sinh `Distractor` và prompt LLM thật.
- API contract đầy đủ và data model.
- CI/CD.

## Files

```text
docs/plans/active/2026-09-05-monorepo-foundation-plan.md
docs/plans/completed/2026-09-05-monorepo-foundation-plan.md
docs/overview/architecture.md
docs/diagrams/system-architecture.drawio
docs/raw-idea/doc-structure.md
README.md
.gitignore
.env.example
pyproject.toml
pnpm-workspace.yaml
package.json
dev.ps1
docker-compose.infra.yml
.pre-commit-config.yaml
packages/contracts/pyproject.toml
packages/contracts/src/contracts/__init__.py
packages/contracts/src/contracts/enums.py
packages/contracts/src/contracts/messages.py
packages/contracts/tests/test_messages.py
services/be/pyproject.toml
services/be/src/be/__init__.py
services/be/src/be/config.py
services/be/src/be/main.py
services/be/src/be/queue.py
services/be/src/be/review_policy.py
services/be/src/be/routes.py
services/be/tests/test_health.py
services/be/tests/test_review_policy.py
services/agent/pyproject.toml
services/agent/src/agent/__init__.py
services/agent/src/agent/config.py
services/agent/src/agent/handlers.py
services/agent/src/agent/worker.py
services/agent/tests/test_handlers.py
services/fe/package.json
services/fe/index.html
services/fe/vite.config.ts
services/fe/tsconfig.json
services/fe/src/main.tsx
services/fe/src/App.tsx
services/fe/src/api.ts
services/fe/src/App.test.tsx
```

## Decision Records

### Decision: Native Processes Instead Of Containerized Services

options considered:

- Container hoá cả ba service với bind mount và dùng Docker Compose làm môi trường chạy duy nhất.
- Chạy cả ba service native trên host và chỉ dùng Docker cho hạ tầng phụ trợ.

selected option: Chạy cả ba service native trên host và chỉ dùng Docker cho hạ tầng phụ trợ.

reason: Repo nằm trên ổ NTFS. Bind mount từ NTFS vào container Linux qua Docker Desktop đi qua lớp chuyển đổi virtiofs, làm I/O chậm với nhiều file nhỏ và khiến inotify không propagate đáng tin cậy. Máy cũng không có `make`, nên container hoá thêm chi phí mà chưa đổi lại lợi ích nào ở giai đoạn MVP.

### Decision: One Shared Conda Environment For BE And AGENT

options considered:

- Mỗi service một môi trường riêng để import chéo thất bại ngay lúc chạy.
- Một conda env dùng chung cho cả BE và AGENT.

selected option: Một conda env dùng chung cho cả BE và AGENT.

reason: Ưu tiên thao tác hằng ngày đơn giản và chỉ cần một interpreter trong PyCharm. Đánh đổi được ghi nhận rõ là môi trường chung không chặn được import chéo lúc chạy, nên hàng rào chuyển hoàn toàn sang `import-linter` gắn vào pre-commit để không phụ thuộc vào việc nhớ gõ lệnh.

### Decision: Per-Service pyproject.toml Despite A Shared Environment

options considered:

- Một `pyproject.toml` duy nhất ở root khai báo toàn bộ dependency.
- Mỗi service giữ `pyproject.toml` riêng và root chỉ chứa cấu hình tooling.

selected option: Mỗi service giữ `pyproject.toml` riêng và root chỉ chứa cấu hình tooling.

reason: Môi trường chung là quyết định về thao tác, không phải về kiến trúc. Giữ khai báo dependency tách theo service làm tài liệu ranh giới luôn đúng, và khi tách service ra hoặc chuyển sang môi trường riêng thì không phải viết lại gì.

### Decision: arq As The Queue Library

options considered:

- `rq` với worker dựa trên tiến trình con.
- `celery` với broker và cấu hình đầy đủ.
- `arq` chạy trên asyncio và Redis.

selected option: `arq`.

reason: `arq` chạy async đúng mô hình của FastAPI, chỉ cần Redis, và có sẵn result store nên giải quyết luôn nhu cầu tra trạng thái job mà không phải tự viết job store. `rq` bị loại vì worker của nó dựa trên `os.fork()` vốn không có trên Windows. `celery` nặng và nhiều cấu hình hơn mức cần cho một luồng stub. Rủi ro đã biết của `arq` trên Windows là `loop.add_signal_handler` ném `NotImplementedError` khiến shutdown không graceful, chấp nhận được ở giai đoạn MVP.

### Decision: PowerShell Script Instead Of Makefile

options considered:

- Dùng `Makefile` và cài `make` lên Windows hoặc chạy nó bên trong container.
- Dùng `dev.ps1` viết bằng PowerShell.

selected option: Dùng `dev.ps1` viết bằng PowerShell.

reason: `make` không có trên máy, và khi các service chạy native thì không còn container nào để chạy `make` bên trong. PowerShell có sẵn và là shell chính đang dùng. Script gọi thẳng interpreter tuyệt đối của conda env thay vì `conda activate`, vì lệnh đó cần `conda-hook.ps1` mới hoạt động trong PowerShell con.

### Decision: setuptools As The Build Backend

options considered:

- `hatchling` làm build backend cho ba package Python.
- `setuptools` với cấu hình tìm package trong thư mục `src`.

selected option: `setuptools`.

reason: Editable install theo PEP 660 của `hatchling` dùng MetaPathFinder, và `grimp` là lõi của `import-linter` có tiền sử không liệt kê được submodule trong trường hợp đó rồi im lặng báo không có vi phạm. Với hàng rào chỉ còn một lớp, một false pass là hỏng toàn bộ cơ chế. `setuptools` với layout `src` sinh đường dẫn phẳng nên an toàn hơn.

### Decision: Single Architecture Document

options considered:

- Tạo `architecture.md`, một tài liệu ranh giới riêng, và thư mục `docs/adr/`.
- Chỉ tạo `architecture.md` và giữ decision record bên trong plan.

selected option: Chỉ tạo `architecture.md` và giữ decision record bên trong plan.

reason: `AGENTS.md` cấm tạo tài liệu trùng chủ đề, và repo chưa từng có `docs/adr/` vì mọi quyết định kỹ thuật đều sống trong mục Decision Records của plan. Với một người bảo trì, các tài liệu có cùng người cập nhật và cùng thời điểm cập nhật nên là một file.

### Decision: Teacher Review Routing Belongs To BE

options considered:

- AGENT tính `Confidence` rồi tự quyết định kết quả nào cần Teacher review.
- AGENT chỉ phát bằng chứng, còn BE áp ngưỡng và quyết định routing.

selected option: AGENT chỉ phát bằng chứng, còn BE áp ngưỡng và quyết định routing.

reason: `business-workflows.md` tách bước hệ thống tạo kết quả khỏi bước hệ thống quyết định đưa vào `Teacher Review Queue`. Nếu AGENT tự quyết thì cổng teacher-in-the-loop nằm bên trong AI service, trái nguyên tắc trong `project-overview.md`. Vì vậy `GradingCompleted` chỉ mang `score`, `confidence`, `misconception_code` và hai cờ bằng chứng, còn `review_policy.py` bên BE mới sinh `needs_teacher_review` và `review_reason`.

## Ordered Tasks

- [x] Create this active plan before other repo-tracked changes.
- [x] Fix `.gitignore` and add Node, ruff and pytest cache entries.
- [x] Create root `pyproject.toml`, `pnpm-workspace.yaml`, `package.json` and `.env.example`.
- [x] Create `packages/contracts` with messages, enums, task name constant and schema tests.
- [x] Create `services/be` with health, submission, job status and review policy.
- [x] Create `services/agent` with the arq worker and an evidence-only handler.
- [x] Create `services/fe` with the Vite proxy, job polling and result rendering.
- [x] Install the three Python packages as editable and run `pnpm install`.
- [x] Create `docker-compose.infra.yml`, `dev.ps1` and `.pre-commit-config.yaml`, then run `pre-commit install`.
- [x] Verify the import boundary with a deliberate violation and revert it.
- [x] Create `README.md`, `docs/overview/architecture.md` and `docs/diagrams/system-architecture.drawio`.
- [x] Update `docs/raw-idea/doc-structure.md` to record that Phase 2 started.
- [x] Run validation checks.
- [x] Move this plan to `docs/plans/completed/` after validation passes.

## Validation Checks

- Set process execution policy to bypass, otherwise `dev.ps1` is blocked.
- Start Redis with `docker compose -f docker-compose.infra.yml up -d` and confirm it is running.
- Run `.\dev.ps1 install` and confirm the editable installs and `pnpm install` finish without error.
- Run `python -c "import be, agent, contracts"` and confirm it succeeds.
- Start BE, AGENT and FE, then confirm a submission from FE returns `score`, `confidence` and `needs_teacher_review`.
- Submit a case below the confidence threshold and confirm `review_reason` is `LOW_CONFIDENCE`.
- Run `.\dev.ps1 test` and confirm pytest and vitest pass.
- Run `.\dev.ps1 check` and confirm `ruff` and `lint-imports` pass.
- Add a temporary `import be` inside the AGENT worker, confirm `lint-imports` fails, then revert it.
- Commit a small change and confirm pre-commit runs `ruff` and `lint-imports`.
- Validate that the new `.drawio` parses as XML, Markdown files are non-empty and diagram links resolve.

## Completion Criteria

- FE, BE and AGENT run at the same time and Redis runs through Docker.
- A submission from FE reaches AGENT through Redis and its result returns to FE.
- `GradingCompleted` carries evidence only, while `be/review_policy.py` decides Teacher review.
- `ReviewReason` covers the four review conditions described in `business-workflows.md`.
- `lint-imports` passes when clean and fails on a cross import, verified manually.
- The pre-commit hook uses the conda interpreter through `language: system` and creates no isolated venv.
- Each service declares its own dependencies in its own `pyproject.toml`.
- Every variable in `.env.example` is read by `be/config.py` or `agent/config.py` with no hardcoded value.
- Every new public function carries a docstring or JSDoc as required by `AGENTS.md`.
- `.gitignore` ignores `__pycache__/` and `node_modules/`.
- `architecture.md` describes the three services, the communication path and the decision boundary, and links the diagram.
- `system-architecture.drawio` parses as valid XML.
- The completed plan is moved to `docs/plans/completed/`.

## Notes

Ba vấn đề chỉ lộ ra khi chạy thật, đã sửa và ghi lại vì chúng sẽ tái diễn với người tiếp theo:

- `python -m importlinter.cli` thoát 0 mà không kiểm tra gì. Chỉ console script `lint-imports` mới chạy thật. Cấu hình sai ở đây là một false pass, và nó sẽ vô hiệu hoá cơ chế giữ ranh giới duy nhất mà không báo lỗi.
- `pre-commit` tách `entry` bằng shlex nên nuốt dấu gạch chéo ngược của đường dẫn Windows. Phải dùng dấu gạch chéo xuôi.
- `localhost` trên máy này phân giải ra `::1` trước, và cổng IPv6 Docker Desktop publish không nhận kết nối, nên cả BE lẫn AGENT chết lúc khởi động. `REDIS_URL` phải dùng `127.0.0.1`. `Test-NetConnection` của PowerShell che lỗi này vì nó tự fallback sang IPv4. Đồng thời `conn_timeout` mặc định của arq là 1 giây, quá ngắn cho Docker Desktop lúc khởi động nguội, đã nâng lên 5.

## Status

Completed.
