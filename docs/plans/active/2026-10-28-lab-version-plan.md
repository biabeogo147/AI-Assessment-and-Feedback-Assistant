# Plan — phiên bản lab hiện trên trình duyệt (`lab-2026.z.x`)

## Goal

Tester lên ticket thì người dùng biết lỗi ấy thuộc bản nào. Mọi màn hiện tên bản (`lab-2026.0.1`) ở
một chỗ cố định, nên ảnh chụp nào cũng mang tên bản; bấm vào thì chép được tên. FE và BE chung một
tên. Tab cũ chạy FE khác BE thì tự tải lại.

Người dùng chốt ngày 28/10/2026:

- Tên dạng `lab-YYYY.z.x`, bản đầu `lab-2026.0.1`. `lab` là tên môi trường. Không kèm mã commit.
- Mặc định tăng x; người dùng yêu cầu tăng z thì `YYYY.(z+1).0`; sang năm mới thì `YYYY+1.0.1`.
- Máy dev hiện tên lab mới nhất.
- `deploy.sh` từ chối ref không phải tag `lab-*`.
- Có changelog. Đặt tên bằng `.\dev.ps1 release`, không dùng CI.
- Figma vẽ trước, duyệt rồi mới code (duyệt 28/10/2026: chỉ một nấc `state=default`; bấm chép không
  báo; lệch bản thì FE tự tải lại).

## Scope

- Một nguồn: biến `AIAFA_VERSION`. FE nhận lúc build (Vite `define`), BE đọc lúc chạy.
- Lab: `deploy.sh` đặt biến bằng tag vừa deploy. Máy dev: `git describe --tags --abbrev=0 --match
  "lab-*"`. Không có tag: `chưa có phiên bản`.
- Endpoint mới `GET /api/version`, không cần đăng nhập. `/health` giữ nguyên.
- Không đổi contract, không đổi schema.
- `deploy/` chỉ đụng `deploy.sh`, `docker-compose.lab.yml`, `caddy.Dockerfile`, `smoke.sh`.

## Files

- `CHANGELOG.md` (mới), `AGENTS.md`, `docs/operation/deploy-lab.md`, `docs/operation/infrastructure.md`,
  `docs/local-development.md`, `docs/plans/backlog.md`
- `tools/release.py` (mới), `tools/tests/test_release.py` (mới), `dev.ps1`
- `deploy/lab/deploy.sh`, `deploy/lab/docker-compose.lab.yml`, `deploy/lab/caddy.Dockerfile`,
  `deploy/lab/smoke.sh`, `tools/tests/test_lab_deploy.py`
- `services/be/src/be/routes.py`, settings của BE, test BE
- `services/fe/vite.config.ts`, `services/fe/src/api.ts`, component `VersionTag` và test,
  `services/fe/src/screens/teacher/Rail.tsx`, `services/fe/src/App.tsx`, CSS
- Figma `mOe2ZmrqOq1Uix45v6PNGD`: component set `Version tag` `810:6501`, màn `9v` `810:6503`,
  `13v` `810:7200`, `12v` `810:7215`; rải sang rail và góc các màn còn lại

## Ordered Tasks

- [x] Pha 0 — Figma: component `Version tag` một nấc `state=default` `810:6492`; ba màn mẫu. Người
      dùng duyệt 28/10/2026.
- [x] Pha 1 — `CHANGELOG.md`; `AGENTS.md` (bảng ownership, luật đặt tên); `deploy-lab.md`;
      `infrastructure.md`; `local-development.md`; backlog md + artifact (*CI deploy khi đẩy tag*,
      máy lab có thể chưa là bản clone). Subagent review: không lỗi nặng; đã sửa luồng in tên kế
      tiếp, hàng chẩn đoán, chữ xoá lớp, chỗ hiện tên bản.
- [x] Pha 2 — `tools/release.py` (`next_version`; in tên kế tiếp và commit từ bản trước trước mọi
      phép kiểm; cây bẩn chỉ cảnh báo; kiểm `main` / đã push / HEAD chưa có tên / mục changelog), `.\dev.ps1 release [-Minor]`, `tools/tests/test_release.py`. Subagent review: mục changelog đọc từ HEAD chứ không từ
      đĩa (lỗi nặng, đã sửa), giờ VN bằng offset cố định (không `tzdata`), tag lấy từ `origin` có
      test, regex không nhận số 0 đứng đầu, HEAD tách nhánh, lời lỗi khi fetch hỏng.
- [x] Pha 3 — `deploy.sh` từ chối ref không phải tag, fetch `refs/tags/<ref>`, ghi
      `deploy/lab/.env.version`; compose truyền `AIAFA_VERSION` cho caddy (build arg) và mọi app (env
      file); `caddy.Dockerfile` `ARG`/`ENV` trước `pnpm build`; `smoke.sh` kiểm `/api/version`; test.
      Subagent review: `.env.version` chỉ gắn cho be (gắn `x-app` thì mỗi deploy dựng lại cả
      `document`); smoke chỉ *chú ý* khi BE chưa có tên; tài liệu dặn chạy `deploy.sh` hai lần ở lần
      đầu dùng tag và `source .env.version` trước khi dựng tay; `lib.sh` nạp file ấy ghi backlog
      (ngoài các file được sửa).
- [x] Pha 4 — BE `GET /api/version`, settings `aiafa_version`; `dev.ps1` hàm `Set-LabVersion` cho `be`
      và `fe`; test. Subagent review: `AGENTS.md` quá trần 184 dòng (nặng) — luật tag gộp vào
      hàng `CHANGELOG.md`, trần nâng 185 kèm lý do ở `check_contract.py`; không có tag thì bỏ biến;
      test không đọc `.env` thật.
- [x] Pha 5 — FE: `define __AIAFA_VERSION__`, `api.version()`, `VersionTag` (so với BE lúc mở và mỗi
      khi tab hiện lại; tự tải lại một lần mỗi tên bản BE; bấm chép), gắn ở rail giáo viên và vỏ ngoài màn học sinh; vitest; ảnh ở
      `docs/report/screenshot/28_10/phien-ban/`; rải Figma sang các màn còn lại; subagent chấm ảnh so
      Figma và review code. Đo DOM khớp Figma từng px (rail 26/823, 71×16, 11/16, khe 8; góc học
      sinh cách phải 24, đáy 16, 78×16, 12/16); tự tải lại đúng một lần khi FE lệch BE. Figma: thêm
      vào 45 màn giáo viên và 20 màn học sinh (dưới `scrim` ở màn có hộp). Review: bộ nhớ bị chặn thì
      tải lại mãi (vừa, đã sửa: không nhớ được thì không tải), kiểm kiểu `version`. Ảnh `01`–`03` ở
      `docs/report/screenshot/28_10/phien-ban/` (chụp lại sau khi mở cửa sổ Chrome); subagent chấm cả
      ba khớp Figma.
- [ ] Pha 6 — mục `lab-2026.0.1` của changelog; `.\dev.ps1 check`, `test`, `typecheck`; commit (chờ
      duyệt); người dùng push; `.\dev.ps1 release` tạo tag ở máy; người dùng tự push tag và deploy.

## Decision Records

### Decision: Đặt tên bằng `dev.ps1 release`, không dùng CI

options considered: GitHub Actions tạo tag và deploy khi merge; lệnh `.\dev.ps1 release` ở máy.
selected option: `.\dev.ps1 release`.
reason: repo chưa có `.github/`, và deploy lab vẫn chạy tay qua SSM; CI deploy cần một role OIDC vào
AWS mà lab chưa có. Một lệnh ở máy kiểm được cùng các điều (cây sạch, đã push, có mục changelog) mà
không thêm hạ tầng. CI deploy ghi vào backlog.

### Decision: BE nhận tên bản qua `deploy/lab/.env.version`, không qua `${AIAFA_VERSION:?}`

options considered: `${AIAFA_VERSION:?}` trong `environment` của be; `deploy.sh` ghi một env file mà
compose đọc ở mọi lần `up`.
selected option: env file `.env.version` (đã nằm dưới luật `.env.*` của `.gitignore`), khai
`required: false` trong anchor `x-app`.
reason: compose thay `${…}` ở **mọi** lệnh, kể cả `ps`, `logs` và lần `up -d` của unit systemd lúc máy
khởi động, vốn chạy không có biến ấy trong shell. `:?` làm lab không lên được sau một lần reboot. Env
file thì đọc lại ở mỗi lần `up`, nên tên bản sống qua reboot và qua `render-env.sh`. Image caddy chỉ
dựng ở `--build` của `deploy.sh`, nên build arg dùng `${AIAFA_VERSION:-chưa có phiên bản}`.

### Decision: Lệch bản thì tự tải lại một lần cho mỗi tên bản BE

options considered: hộp báo kèm nút *Tải lại*; tự tải lại mỗi lần lệch; tự tải lại một lần cho mỗi tên
bản BE (ghi tên ấy vào `sessionStorage` trước khi tải).
selected option: tự tải lại một lần cho mỗi tên bản BE.
reason: người dùng bỏ trạng thái lệch ở Figma. Lúc deploy BE có thể lên trước khi Caddy phục vụ FE mới;
tải lại vô điều kiện thì tab quay vòng. Sau một lần, chữ vẫn ghi tên bản FE, nên ảnh của tester vẫn
đúng bản họ đang chạy.

### Decision: Cây còn sửa dở thì `release` chỉ cảnh báo

options considered: từ chối khi `git status` không sạch; chỉ cảnh báo.
selected option: chỉ cảnh báo (file tracked; file untracked không nhắc).
reason: tag trỏ vào HEAD và không chở phần chưa commit, nên cây bẩn không làm tag sai; điều làm tag
sai là HEAD chưa push, và điều ấy vẫn bị từ chối. Máy dev của người dùng luôn giữ hai dòng ghi chú
riêng không bao giờ commit (`propose/prompt.py`, `propose/compose.py`), nên một phép kiểm cây sạch sẽ
chặn mọi lần đặt tên.

### Decision: Vite chỉ đọc `AIAFA_VERSION`, không tự gọi git

options considered: `vite.config.ts` gọi `git describe` qua `execSync` khi biến trống; chỉ đọc biến
qua `loadEnv`.
selected option: chỉ đọc biến.
reason: gọi `child_process` trong `vite.config.ts` cần `@types/node`, một dependency mới mà FE chưa
khai (và image lab cài bằng `--frozen-lockfile`). `.\dev.ps1 fe` đã đặt biến bằng tag, Dockerfile lab
đặt bằng tag của `deploy.sh`. Chạy `pnpm --filter fe dev` thẳng thì FE ghi `chưa có phiên bản`.

## Validation Checks

- `pytest tools/tests/test_release.py tools/tests/test_lab_deploy.py services/be/tests` xanh; bẻ một
  luật (tăng z ra `.1`) thấy đỏ.
- `.\dev.ps1 release` khi chưa push bị từ chối, cây bẩn chỉ cảnh báo; thiếu mục changelog thì không tạo tag.
- `bash -n deploy/lab/deploy.sh`; `deploy.sh main` in lời từ chối.
- Thử tay ở `127.0.0.1:5173`: chưa có tag thì ghi `chưa có phiên bản`; sau `release` ghi
  `lab-2026.0.1` ở rail và màn học sinh; `curl 127.0.0.1:8000/api/version` trả cùng tên; vá `fetch`
  cho BE trả tên khác thì trang tự tải lại một lần.
- `.\dev.ps1 check`, `.\dev.ps1 test`, `.\dev.ps1 typecheck` xanh trước commit.

## Status

Pha 0 duyệt 28/10/2026; Pha 1–5 xong và đã review; `check`, `test`, `typecheck` xanh. Còn Pha 6 (commit chờ người dùng duyệt, rồi `release`).
