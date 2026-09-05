# AGENTS Contract Rewrite Plan

## Goal

Đưa bộ tài liệu điều hành khớp với repo đã có code, gom về một nguồn sự thật duy nhất, và biến luật "mọi thay đổi đều cần plan" từ ý chí thành thứ kiểm được bằng diff.

## Scope

Trong phạm vi:

- Viết lại `AGENTS.md` theo mười một mục, mục tiêu không quá 170 dòng.
- Rút gọn `CLAUDE.md` còn phần trỏ sang `AGENTS.md`.
- Tạo bốn `AGENTS.md` con cho ba service và `packages/contracts`, mỗi file không quá 25 dòng.
- Xoá `docs/raw-idea/doc-structure.md` sau khi chuyển bốn khối nội dung còn giá trị.
- Xoá thư mục rỗng `.agents/`.
- Ba thay đổi code nhỏ để hợp đồng không nói dối: bỏ ba biến môi trường không ai đọc, thêm `tools/check_contract.py` đối chiếu `.env.example` với `Settings`, và thêm `typecheck` cùng hai cưỡng chế mới vào `dev.ps1`.

Ngoài phạm vi:

- Đổi bố cục thư mục `docs/`.
- Tạo `data-model.md` hoặc `grading-design.md`; plan này chỉ đặt sẵn tên.
- Đổi logic nghiệp vụ.
- Đổi cấu hình `import-linter` hoặc pre-commit.

## Files

```text
docs/plans/active/2026-09-05-agents-contract-rewrite-plan.md
docs/plans/completed/2026-09-05-agents-contract-rewrite-plan.md
AGENTS.md
CLAUDE.md
services/be/AGENTS.md
services/agent/AGENTS.md
services/fe/AGENTS.md
packages/contracts/AGENTS.md
docs/overview/architecture.md
docs/raw-idea/doc-structure.md
.env.example
dev.ps1
services/be/src/be/config.py
tools/check_contract.py
```

## Decision Records

### Decision: Keep The Plan-Per-Change Rule

options considered:

- Phân tầng theo quy mô, chỉ thay đổi lớn mới cần plan.
- Giữ nguyên luật áp dụng cho mọi thay đổi repo-tracked.
- Bỏ plan file và thay bằng issue hoặc TODO.

selected option: Giữ nguyên luật áp dụng cho mọi thay đổi repo-tracked.

reason: Ưu tiên nhất quán tuyệt đối hơn là phải phán đoán từng lần xem việc này có cần plan hay không. Rủi ro đã biết là luật nặng khi nhịp commit dày, nên phản ứng đúng không phải nới luật mà là làm nó rẻ đi bằng một danh sách trigger theo đường dẫn, một danh sách miễn trừ, và một mẫu plan tối thiểu. Bỏ plan file thì mất luôn Decision Record, vốn là nơi duy nhất repo này ghi lý do của các quyết định kỹ thuật.

### Decision: AGENTS.md As The Only Contract

options considered:

- Gộp hết vào `AGENTS.md` và xoá `CLAUDE.md`.
- `AGENTS.md` là nguồn duy nhất, `CLAUDE.md` rút còn phần trỏ sang.
- Chia theo đối tượng đọc, `AGENTS.md` cho người và `CLAUDE.md` cho agent.

selected option: `AGENTS.md` là nguồn duy nhất, `CLAUDE.md` rút còn phần trỏ sang.

reason: Claude Code tự nạp `CLAUDE.md` vào context mỗi phiên còn `AGENTS.md` thì không, nên xoá `CLAUDE.md` là mất đường dẫn tự động. Chia theo đối tượng đọc nghe gọn nhưng hai bên cần biết gần như cùng một thứ nên sẽ trùng lại rất nhanh, đúng tình trạng đang phải sửa.

### Decision: Delete doc-structure.md After Moving Four Blocks

options considered:

- Giữ nguyên trong `docs/raw-idea/`.
- Chuyển ra `docs/` và duy trì như tài liệu sống.
- Xoá sau khi chuyển phần còn giá trị sang `AGENTS.md` và `architecture.md`.

selected option: Xoá sau khi chuyển phần còn giá trị.

reason: Nội dung file chia làm ba loại. Loại là luật thì thuộc `AGENTS.md`, loại giải thích thiết kế thì thuộc `architecture.md`, loại còn lại là roadmap Phase 0/1/2 đã hết nhiệm vụ. Giữ nó như tài liệu sống nghĩa là bảo trì thêm một chỗ nữa mô tả cùng chủ đề với `AGENTS.md`.

### Decision: Child AGENTS.md Files Carry Constraints, Never State

options considered:

- Không có file con, mọi luật ở root.
- File con mô tả cả ràng buộc lẫn trạng thái hiện tại của thư mục.
- File con chỉ chứa ràng buộc bất biến, trạng thái để ở `README.md` và `architecture.md`.

selected option: File con chỉ chứa ràng buộc bất biến.

reason: Luật quan trọng nhất về AGENT nằm cách xa file người ta đang sửa nên file con là đúng. Nhưng câu mô tả trạng thái sẽ sai ngay tuần đầu làm MVP, và một tài liệu luật nói sai còn tệ hơn không có. Ràng buộc thì bất biến, trạng thái thì không.

### Decision: Replace Work Unit With A Path-Based Trigger List

options considered:

- Định nghĩa đơn vị của plan là một đơn vị công việc.
- Liệt kê trigger và miễn trừ theo đường dẫn, áp dụng bằng cách nhìn diff.

selected option: Liệt kê trigger và miễn trừ theo đường dẫn.

reason: Đơn vị công việc là định nghĩa vòng tròn vì đơn vị công việc chính là thứ cần một plan, nên nó chỉ dời sự mơ hồ chứ không khử. Danh sách theo đường dẫn thì một agent áp dụng nhất quán được, và đi kèm trailer `Plan:` trong commit thì luật trở thành thứ grep được thay vì phải tin nhau.

### Decision: Raise The AGENTS.md Line Cap From 140 To 170

options considered:

- Giữ cap 140 và cắt bớt luật cho vừa.
- Nâng cap lên đúng kích thước thật sau khi đã cắt hết phần không phải luật.
- Bỏ cap, chỉ dựa vào review.

selected option: Nâng cap lên 170.

reason: Con số 140 được đặt trước khi viết nội dung. Sau khi cắt hết phần diễn giải, file còn 166 dòng và mọi mục còn lại đều là luật; hai mục dài nhất là hai bảng ownership và invariants, vốn có mật độ giá trị cao nhất. Cắt luật thật để vừa một con số tự đặt là đánh đổi sai. Bỏ cap thì mất cơ chế chống phình. Cap mới đặt sát kích thước thật để nó vẫn chặn được tăng trưởng, và `tools/check_contract.py` ghi rõ rằng nâng tiếp phải kèm decision record.

### Decision: Commit Trailer Carries A Filename, Not A Path

options considered:

- Trailer ghi `Plan: docs/plans/active/<file>.md`.
- Trailer ghi tên file trần.

selected option: Trailer ghi tên file trần.

reason: Plan chuyển từ `active/` sang `completed/` khi hoàn tất, nên mọi commit trước đó sẽ trỏ vào một đường dẫn không còn tồn tại. Tên file không đổi qua lần chuyển đó, nên nó là thứ duy nhất grep được ổn định. Lỗi này chỉ lộ ra khi áp dụng luật vào chính commit của plan này.

## Ordered Tasks

- [x] Create this active plan before other repo-tracked changes.
- [x] Remove the three unread environment variables from `.env.example` and `be/config.py`.
- [x] Add `tools/check_contract.py` comparing `.env.example` against both settings classes.
- [x] Add `typecheck`, the agent credential grep and the child file line cap to `dev.ps1`.
- [x] Rewrite `AGENTS.md` in eleven sections.
- [x] Move four blocks out of `doc-structure.md` and rewrite the diagram rationale in `architecture.md`.
- [x] Delete `docs/raw-idea/doc-structure.md` and the empty `.agents/` directory.
- [x] Trim `CLAUDE.md` down to a pointer.
- [x] Write the four child `AGENTS.md` files.
- [x] Run validation checks.
- [x] Move this plan to `docs/plans/completed/` after validation passes.

## Validation Checks

- Run `.\dev.ps1 test` and confirm it passes, and confirm the repo contract checks pass.
- Run `.\dev.ps1 check` and confirm ruff, the import boundary, the agent credential grep and the child file line cap all pass.
- Run `.\dev.ps1 typecheck` and confirm it succeeds.
- Confirm `AGENTS.md` is at most 170 lines and every child file at most 25 lines.
- Confirm every `dev.ps1` task named in `AGENTS.md` exists in the script's `ValidateSet`.
- Confirm every test name and file path named in the Invariants section exists as written.
- Confirm no reference to `doc-structure.md` remains outside `docs/plans/completed/`, which is a closed historical record.
- Confirm no file still claims the repository has no source code.
- Confirm no sentence in a child file describes current state instead of a constraint.
- Confirm Markdown files are non-empty and internal links resolve.

## Completion Criteria

- `AGENTS.md` is the only file describing the workflow, and its Invariants section is an enforcement index that points at `architecture.md` for reasoning.
- The planning rule carries a path-based trigger list, an exemption list and a minimal plan template.
- An `Amending This Contract` section answers what changing the contract requires and whether changing the root forces a sweep of the child files.
- The Invariants table has eight automated rows and at most three unenforced rows, each unenforced row naming a use case.
- The four child files exist and contain constraints only.
- `doc-structure.md` and `.agents/` are gone, and the four salvaged blocks have a new owner.
- `.env.example` contains no variable that nothing reads.

## Status

Completed.
