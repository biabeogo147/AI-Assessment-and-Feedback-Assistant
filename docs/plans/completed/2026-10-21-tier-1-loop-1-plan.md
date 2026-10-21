# Plan — Tier 1, vòng 1: dọn chín dòng Tier 1 của backlog

- **Mở:** 21/10/2026 · **Đóng:** 21/10/2026

## Context

Người dùng muốn Tier 1 của artifact "Backlog theo tier" (`docs/plans/backlog.md` là nguồn) hết sạch.
Cách làm: mỗi vòng có một plan, làm xong thì subagent review cả code lẫn ảnh chụp thử tay trên trình
duyệt. Lỗi review tìm ra thì ghi vào backlog (md và artifact). Tier 1 còn việc thì sang vòng kế, với plan
kế. Người dùng đã cho phép trước hai việc: gọi subagent, và **commit sau mỗi vòng**.

Tier 1 hiện có 9 dòng (đọc artifact rev 164, đối chiếu code 21/10/2026):

| # | Việc | Trạng thái thật |
|---|---|---|
| 1 | Avatar Kriky cách khối bước (code 6px dọc qua `.voice`/`.thinking { gap: 6px }`), Figma 20px | **Code theo Figma** (người dùng chọn) |
| 2 | Thẻ sửa ba tầng: `.qcard.editing { gap: 8px }`, `.tang-head .label` cao 16.5→17; Figma 531:181 là 6 và 15 | **Code theo Figma** |
| 3 | Chân panel đề trống: dòng `_note` (`Panel.tsx:778`) Figma 18 không vẽ; `.panel-foot .cta:disabled` thiếu `opacity: 1` | **Bỏ dòng nhắc theo Figma 18** (người dùng chọn). Lần đọc đầu thấy câu *"Đề chưa có câu nào nên chưa duyệt được."* trong `653:2917` nên code in câu ấy; review chỉ ra node đó bị ẩn, nên đề trống nay không in dòng nào; nút tắt `opacity: 1` |
| 4 | BE treo sau `--reload` (WinError 10038) | Mở, cần tái hiện |
| 5 | Giới hạn số lần thử đăng nhập | Mở; chưa có bộ đếm nào trong BE |
| 6 | Cookie chưa có cờ `Secure` | **Đã làm ở `b0c5ac0`** (`SESSION_COOKIE_SECURE`), chỉ gỡ khỏi backlog/artifact |
| 7 | Vite phục vụ bản cũ của module vừa sửa | Mở, cần tái hiện |
| 8 | `.split-handle` tự nhảy lên khi vừa bấm | Đã tìm ra gốc (dưới) |
| 9 | Không có đường kẻ giữa `.lists` và `.account-box` | Mở |

**Gốc của #8 (tính từ CSS, sẽ đo lại trên trình duyệt):** `Rail.tsx:220-228` đặt chiều cao ngăn tài liệu
bằng `innerHeight − clientY − 26`. Số 26 có từ trước khi có ô tài khoản. Nay dưới ngăn tài liệu còn:
`.rail` gap 16, `.account` 44, padding đáy 20. Nên lần pointermove đầu tiên nhảy khoảng 60px.

## Ràng buộc thường trực

- Không đụng `docs/report/`. `services/fe/src/screens/teacher/Dashboard.tsx` có thay đổi riêng của người
  dùng (bỏ hai đoạn mô tả dưới *Cần bạn xem* và *Điểm gộp theo lớp*): người dùng dặn 21/10 cho vào commit
  của vòng này; Figma 20 bỏ hai đoạn ấy cho khớp (`657:4130`, `657:4133`).
- Hai dòng `# TODO: Cần xem lại` (`propose/prompt.py`, `propose/compose.py`): không xoá, không stage.
- Mọi đổi FE: chụp ảnh trình duyệt, subagent so ảnh với Figma. Figma và code đổi cùng nhau.
- Trước mỗi commit: `.\dev.ps1 check`, `.\dev.ps1 test`. Không commit `data/`, `.env`, ảnh. Đuôi
  commit: `Plan: <file>.md`, Co-Authored-By, Claude-Session.
- Không chạy LLM thật (Tier 1 không cần).
- Khởi động lại BE/FE chỉ khi việc #4/#7 cần, bằng `dev.ps1` ở nền. Kiểm tiến trình đang chạy code nào.

## Vòng 1 — `docs/plans/active/2026-10-21-tier-1-loop-1-plan.md`

Mỗi pha: làm → `.\dev.ps1 test` → subagent review (code + ảnh) → sửa theo review.

### Pha 0 — Dọn sổ
- Gỡ #6 khỏi `backlog.md:28` và khỏi bảng Tier 1 của artifact (đã xong ở `b0c5ac0`). Sửa câu đếm.

### Pha 1 — Rail (#8, #9)
- **#8 (TDD):**
  - Test trước trong `teacher.test.tsx`: bấm rồi rê 1px thì chiều cao ngăn tài liệu đổi ≤ 1px; kéo lên
    40px thì ngăn cao thêm 40px.
  - Shim pointer theo mẫu `teacher.test.tsx:3359-3390` (`PointerEvent` = `MouseEvent`,
    `setPointerCapture`).
  - Sửa: lúc `pointerdown` lưu `clientY` và chiều cao đang có (ref). Lúc `pointermove`:
    `height = startHeight + (startY − clientY)`, kẹp `SPLIT_MIN`/`SPLIT_MAX`. Bỏ hằng 26.
  - Không còn phụ thuộc gì ở dưới (ô tài khoản, chưa đăng nhập).
- **#9:**
  - `.rail .account-box` có đường kẻ trên `var(--line)`, theo kiểu `box-shadow: inset 0 1px 0`
    của `.panel-foot`, hay `border-top` nếu Figma vẽ vậy.
  - Ô "Đăng nhập" lúc chưa đăng nhập cũng kẻ như vậy.
  - Figma: thêm đường kẻ vào rail ở artboard 1 và mọi màn có rail (component rail nếu có).
  - Chụp ảnh, đo cho hai bên bằng nhau.

### Pha 2 — Ba chỗ lệch Figma (#1, #2, #3)
- **#1:** đo `Thinking`/`.voice`/`.steps-block` trên Figma (artboard 16 và các lượt có bước) bằng
  `get_design_context`/`get_metadata`. Đổi CSS (`.voice`, `.thinking`, `.turn-body`) về số Figma một lần.
  Chụp lượt có bước, lượt đang nghĩ, lượt xong.
- **#2:** `.qcard.editing { gap: 6px }`. Đầu tầng cao 14 (`line-height` của `.tang-head .label`): số 15 của backlog đo ở trang Components; artboard 14 và 22b (density Teacher) vẽ 14. Kiểm ở
  panel đề và màn 22b.
- **#3:**
  - `Panel.tsx`: đề không có câu (`question_count === 0`) thì `_note` in câu của Figma 18 (`653:2917`)
    thay cho câu về phát hành. Giữ `trouble`; đề có câu giữ câu cũ (Figma 19 vẽ nó).
  - `.panel-foot .cta:disabled { opacity: 1 }`, comment như ở `teacher.css:3241`.
  - Test: đề trống không có dòng nhắc.

### Pha 3 — Giới hạn thử đăng nhập (#5)
- `services/be/src/be/sign_in_limit.py` mới: bộ đếm trong bộ nhớ, đủ cho một tiến trình BE. Lab và dev
  đều chạy một uvicorn, không `--workers`.
  - Cửa sổ trượt 15 phút. Hai khoá:
    - tên đăng nhập đã chuẩn hoá: 5 lần sai thì khoá tới khi cửa sổ trôi qua;
    - IP (`request.client.host`, sau `--proxy-headers` ở lab): ngưỡng cao, 50, vì cả lớp có thể chung
      một IP qua NAT.
  - Đăng nhập đúng thì xoá bộ đếm của tên ấy.
- Hai handler ở `account_routes.py:155`, `:205`:
  - kiểm trước khi chạy `scrypt`: bị khoá thì trả `429`, câu tiếng Việt *"Bạn nhập sai quá nhiều lần.
    Thử lại sau N phút."*, cùng một câu cho tên có hay không có;
  - sai thì đếm, kể cả tên không tồn tại, để không lộ tên nào có thật.
- Đồng hồ tiêm được để test. Test trong `test_accounts.py`:
  - giáo viên và học sinh;
  - sai lần 6 thì 429, kể cả khi mật khẩu đúng;
  - hết cửa sổ thì mở lại;
  - đúng thì đếm lại từ đầu;
  - tên không tồn tại cũng bị khoá;
  - ngưỡng IP.
- FE: hai hộp đăng nhập hiện `detail` của 429 ở chỗ báo lỗi sẵn có (kiểm xem hiện nay có đọc `detail`
  không). Chụp ảnh. Figma: thêm trạng thái lỗi này nếu chữ lỗi chưa có variant.
- ADR-36 thêm hậu ký. `docs/local-development.md`: một dòng về cách mở khoá (khởi động lại BE).

### Pha 4 — Môi trường dev (#4, #7). Theo `superpowers:systematic-debugging`: tái hiện trước, sửa sau
- **#4:**
  - Script scratchpad: mở một kênh SSE `teacher_documents.watch`, `touch` một file BE N lần, mỗi lần chờ
    `/api/health` (hay route tương đương) lên lại. Ghi lần nào gãy và gãy ra sao.
  - Gãy được thì so với chạy không có kênh SSE.
  - Hướng sửa dự kiến: `dev.ps1 be` chạy uvicorn **không** `--reload`, và để `watchfiles` (có sẵn
    trong `uvicorn[standard]`) khởi động lại cả tiến trình. Như vậy không còn chia socket giữa tiến
    trình cha và con trên Windows, là chỗ sinh WinError 10038.
  - Chạy lại script để chứng minh.
  - Không tái hiện được sau ~30 lần thì ghi số liệu vào backlog, chuyển dòng sang Tier 3 (P8), không
    sửa mò.
- **#7:**
  - Script: sửa `teacher.css`/một `.tsx` bằng Python `write_text` (cách đã gây lỗi). Sau mỗi lần, fetch
    module qua Vite (`/src/...?import`) xem nội dung mới chưa.
  - Gãy được thì thử `server.watch.awaitWriteFinish` ở `vite.config.ts`. Nghi ghi cụt/ghi hai nhịp nên
    watcher đọc file giữa chừng.
  - Không tái hiện được thì làm như #4.
- `docs/local-development.md` cập nhật (cả câu `--timeout-graceful-shutdown 5` cũ ở backlog).

### Cuối vòng
1. Subagent review cả vòng: đọc diff thật, xem ảnh chụp từng pha, so với Figma.
2. Lỗi mới:
   - làm được ngay → Tier 1 (backlog md + artifact);
   - cần quyết định → Tier 2;
   - chạm AGENT/document → tier tương ứng.
3. Gỡ khỏi md và artifact mọi dòng đã xong. Đóng plan sang `completed/`.
4. `.\dev.ps1 check` + `test` xanh, rồi commit theo pha (code từng pha; docs + plan).
5. **Tier 1 còn dòng thì sang vòng 2**: viết `docs/plans/active/2026-10-21-tier-1-loop-2-plan.md` chỉ
   cho các dòng ấy, rồi lặp lại.

**Chặn vòng lặp:**
- Dừng và báo người dùng khi một lỗi quay lại hai vòng liền, khi cần một quyết định của người dùng, hay
  sau vòng 4 mà Tier 1 vẫn còn.
- Lỗi review tìm ra mà không thuộc phạm vi Tier 1 thì chỉ ghi, không làm.

## Verification

- Vitest: test kéo split-handle (đỏ trước, xanh sau), test chân panel đề trống. Pytest: test giới hạn
  đăng nhập.
- Trình duyệt (`127.0.0.1:5173`):
  - kéo split-handle: bấm không nhảy, kéo theo đúng con trỏ;
  - ảnh rail có đường kẻ;
  - lượt chat có bước;
  - thẻ sửa ở panel đề và 22b;
  - chân panel đề trống;
  - hộp đăng nhập báo 429.
  - Subagent so từng ảnh với node Figma.
- Script tái hiện #4/#7 trước và sau khi sửa, có số lần chạy.
- `.\dev.ps1 check`, `.\dev.ps1 test` xanh trước mỗi commit. `git diff --cached` không có TODO và không
  có `Dashboard.tsx`.
- Artifact Tier 1 rỗng, hay chỉ còn dòng đã giải thích lý do cuối vòng.

## Kết quả (21/10/2026)

- **Code:** cả chín dòng xong. #6 đã có từ `b0c5ac0`. #7 không tái hiện được sau 150 lần thăm dò,
  nên chuyển sang Tier 3 (P8).
- **Thử tay trên trình duyệt** (BE thật, dữ liệu mẫu chặn `fetch` cho lượt chat và đề, vì DB dev
  chưa có lượt nào và tạo lượt thật thì phải gọi LLM):
  - avatar → khối bước 20;
  - rail: viền 1 + đệm 8 = 9, cả lúc đăng nhập lẫn chưa;
  - thẻ sửa: gap 6, ba đầu tầng 14/14/14 ở panel đề và ở 22b. `.tang-head .summary` còn 16,5, phải
    sửa thêm lúc đo;
  - chân đề trống cao 78, nút ở y=16, khớp `653:2917`;
  - split-handle: bấm tại chỗ không nhảy, kéo 40px thì ngăn cao thêm 40;
  - 429 hiện trong hộp đăng nhập giáo viên;
  - Bảng theo dõi khớp Figma 20 mới.
- **BE nạp lại** (`dev.ps1 be` qua `watchfiles`): 10/10 lần với kênh SSE tài liệu mở, 2,4–2,6 s mỗi
  lần, một process giữ cổng 8000.
- **Review của subagent** (code và ảnh):
  - đề trống phải bỏ dòng nhắc (node Figma ẩn): đã sửa;
  - tên đăng nhập dài tuỳ ý làm khoá của bộ đếm: đã sửa, `Field(max_length)`, 422 trước khi vào sổ,
    có test;
  - comment `dev.ps1` nói quá (watchfiles giết cứng, process con mồ côi, shlex, số 0,7 s): đã viết
    lại, thêm mục chẩn đoán ở `docs/local-development.md`;
  - giáo viên có hai tên nên chịu được 10 lần sai: ghi vào ADR-36;
  - tên tầng in hoa so với Figma viết thường (có từ trước): vào Tier 1, cho vòng 2.
- **Còn cho vòng 2:**
  - split-handle kẹt khi pointer bị huỷ;
  - tên tầng in hoa.
- **Kiểm:** `.\dev.ps1 check` 26/26; pytest 1863 xanh, vitest 348 xanh.
