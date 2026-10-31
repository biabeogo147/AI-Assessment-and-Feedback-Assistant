# Báo cáo chương 5–7: đổi văn xuôi dày thành sơ đồ và bảng (`report-diagrams`)

## Goal

Các đoạn văn xuôi dày ở chương 5–7 được thay bằng sơ đồ hay bảng. Chỉ thay khi hình hay bảng giúp
người đọc hơn văn. Câu của người dùng giữ nguyên chữ, trừ những chỗ đã báo trước và được duyệt.

## Context

Rà chương 5–7 (31/10/2026, cùng một subagent, ba vòng tranh luận) thấy nhiều đoạn văn xuôi dài
không có hình hay bảng nào. Người dùng chốt:
- Ưu tiên **sơ đồ > bảng > văn xuôi**. Sơ đồ chỉ dùng khi nó thêm thông tin hay dễ hiểu hơn; rối thì
  chuyển sang bảng; bảng cũng không xử lí được mới giữ văn xuôi.
- **Hạn chế viết lại câu của người dùng.** Được xoá câu để thay bằng hình/bảng; câu mới chỉ là câu
  dẫn. Mọi câu xoá/thêm/đổi phải báo trước (danh sách dưới đây là bản đã báo và được duyệt).
- `fig:teacher-chat-turn` tách thành nhiều hình nhỏ đặt cạnh đoạn văn; bản đầy đủ chuyển xuống cuối
  section Backend.
- Sau mỗi bước có **subagent review**; ảnh chụp của mỗi sơ đồ có **một subagent khác** review.
- Sơ đồ **không có object chồng nhau, hạn chế đường cắt nhau**.

Đây là ngoại lệ có phép của memory *Không đụng vào báo cáo*: chỉ sửa đúng các chỗ kể dưới đây.

## Công cụ và luật có sẵn (dùng lại, không thêm mới)

- Nguồn hình: `docs/diagrams/*.drawio` (AGENTS.md: source of truth). Xuất bằng draw.io desktop:
  `"$LOCALAPPDATA/Programs/draw.io/draw.io.exe" -x -f pdf --crop -o docs/report/figures/<tên>.pdf
  docs/diagrams/<tên>.drawio`; ảnh duyệt/review xuất `-f png --scale 2` vào scratchpad.
- `docs/report/figures/sources.json`: thêm entry `{source, sha256}` cho mỗi hình;
  `tools/check_contract.py::check_every_figure_matches_the_diagram_it_came_from` bắt hash lệch và
  `.drawio` chưa xuất.
- Mọi `.drawio` mới phải được link từ `docs/overview/architecture.md` (mục "Diagram liên quan" và
  "Diagram nào đã có…", cập nhật con số "tám diagram").
- Khuôn vẽ sequence: chính `teacher-chat-turn.drawio` (làn, loop/alt/opt, đường sống dưới hộp).
- `docs/report/rules.md`: §6 chữ trong hình = chữ trong văn bản; §7 mỗi hình/bảng có câu dẫn
  `Hình~\ref{}`/`Bảng~\ref{}`; §8 hình dọc `[htbp]`/`[p]`, chữ ≥ 7pt trên PDF, `&lt;id&gt;`, bảng
  `booktabs`, `[htb]`, `longtable` khi > 70% trang, `\caption[ngắn]{dài}`; §9 một dòng bảng một hàng.
- Build: `.\dev.ps1 report`; cổng: `.\dev.ps1 check`.

## Quy trình cho mỗi sơ đồ (áp cho mọi bước có hình)

1. **Dựng `.drawio` bản nháp** theo khuôn có sẵn: lưới 10px, mọi nút căn lưới, cạnh orthogonal,
   nhãn cạnh đặt ngoài nút. Chạy kiểm hình học (bước 3), xuất **PNG gửi người dùng duyệt** (người
   dùng chọn PNG thay cho phác bằng chữ), dừng chờ duyệt.
2. Sửa theo ý người dùng (nếu có) trước khi đi tiếp.
3. **Kiểm hình học tự động** bằng script trong scratchpad (đọc XML `.drawio`): không cặp vertex nào
   giao nhau (trừ cha–con của container/làn), không nhãn nào tràn khỏi hộp, đếm số cặp cạnh cắt nhau
   — mục tiêu 0, có thì ghi lý do. Chạy lại sau mỗi lần sửa.
4. **Xuất PDF + PNG**, cập nhật `sources.json`, nhúng vào `.tex`, `.\dev.ps1 report`; đo cỡ chữ nhỏ
   nhất trên PDF (≥ 7pt).
5. **Subagent A (review ảnh):** chỉ nhận PNG + đoạn văn tương ứng, không nhận kết luận của tôi;
   chấm chồng lấn, đường cắt, chữ đọc được, hình có nói đúng văn bản, có thêm thông tin không.
6. **Subagent B (review bước):** đọc diff `.tex`/`.drawio` so với danh sách xoá/giữ/thêm của plan và
   `rules.md`; báo câu nào của người dùng bị đổi ngoài danh sách.
7. Sửa theo review, lặp 3–6 tới khi sạch; rồi sang bước kế.

Bước chỉ có bảng: bỏ 1–5, giữ 6 (subagent B), cộng đọc PDF trang bảng.

## Ordered Tasks

- [x] Bước 0 — Mốc: plan vào `active/`, ghi mốc `check`, `report`.
- [x] Bước 1 — Bảng và lỗi nhỏ: `\bottomrule`, hai vế trỏ `tab:be-rang-buoc`, T1, T2, T4, câu
  dẫn `fig:use-case`.
- [x] Bước 2 — Tách `teacher-chat-turn`: ba hình con propose, plan-check, execute; hình đầy đủ vẽ
  lại dạng tổng quan, đặt `[H]` cuối section Backend.
- [x] Bước 3 — D1 `document-upload` (Hình 6.2).
- [x] Bước 4 — D2 `submit-and-remediate`.
- [x] Bước 5 — D3 `propose-three-layers`; khôi phục nguyên chữ hai đoạn.
- [x] Bước 6 — D4 `draft-question-life`.
- [x] Bước 7 — T3 `tab:be-thao-tac-de` (Bảng 7.2); D6 ghi backlog, chờ ADR-01.
- [x] Bước 8 — D7 `document-false-failure` (Hình 7.9). Bước này nhúng thẳng, không gửi ảnh cho
  người dùng duyệt trước, vì người dùng đã bảo làm tiếp.
- [x] Bước 9 — `architecture.md` (mười sáu diagram), `rules.md` §6–§8, backlog cùng artifact
  *Backlog theo tier*, subagent review cuối.
- [x] Ngoài danh sách ban đầu, người dùng bảo thêm: sửa những câu của chương 7 lệch với code. Các
  chỗ đã sửa:
  - `tab:be-hong`;
  - đoạn "Ba lối ra";
  - đoạn "Soạn câu hỏi…";
  - `tab:agent-hong`;
  - ca kiểm thử "không mang quyết định";
  - thứ tự phép kiểm;
  - bỏ ba mục giới hạn của agent mà code đã đóng.

## Chi tiết các bước

### Bước 0 — Mốc
- Chép plan vào `docs/plans/active/2026-10-31-report-diagrams-plan.md`.
- Ghi mốc: `.\dev.ps1 check`, `.\dev.ps1 report` (số trang, cảnh báo sẵn có). Diff sẵn có của
  người dùng ở `07-chi-tiet-cac-service.tex` giữ nguyên.

### Bước 1 — Bảng và lỗi nhỏ (chỉ bảng, không hình)
- **Lỗi** `07:69` `b\bottomrule` → `\bottomrule`.
- **Lỗi** `tab:be-rang-buoc` ở `07:557`, `07:885`: người dùng chốt **bỏ vế trỏ bảng** — xoá vế
  "Cột cuối dùng hai trong ba loại đã giải thích trước bảng~\ref{tab:be-rang-buoc}" ở hai chỗ, phần
  còn lại của câu giữ nguyên chữ.
- **T1** `tab:be-lay-ket-qua`: người dùng đã tự xoá cột *Giới hạn mặc định* (chưa commit) và chốt
  31/10 giữ bảng hai cột → chỉ khai lại `tabular` thành hai cột; **không** xoá `07:73-86`.
- **T2** `tab:agent-vao-ra`: thêm cột *Các hàm*; **xoá** `07:437-442` trừ câu "Hàm nhận job, nói ở
  đoạn dưới, không thuộc graph nào…" (giữ nguyên chữ).
- **T4** bảng mới service × store ở `06`: **xoá** `06:85-90` và câu đầu `06:92-94`; **giữ**
  `06:80-83`, câu "content store giữ *thứ đọc được từ tệp*…" (`06:94-96`), `06:98`. Thêm một câu dẫn.
- **Chương 5:** một câu dẫn vào `fig:use-case`.
- Review: subagent B.

### Bước 2 — Tách `teacher-chat-turn`
- Ba hình nhỏ mới (cùng khuôn, cắt từ hình gốc, không vẽ thêm nội dung ngoài văn bản):
  - (a) `teacher-chat-turn-propose`: khoá → vòng `propose_next_step` → tra cứu / kết thúc / plan;
    ghi chú 8 bước, 90 giây. Đặt sau `07:172`.
  - (b) `teacher-chat-turn-plan-check`: hai cửa kiểm (khớp dàn ý → trả về pha đề xuất; hợp lệ →
    từ chối cả plan). Đặt sau `07:194`.
  - (c) `teacher-chat-turn-execute`: chạy từng việc, dừng ở việc hỏng; nhánh soạn đề; `report_plan`,
    `name_conversation`, mở khoá. Đặt sau `07:206`.
- Hình đầy đủ giữ `fig:teacher-chat-turn`, chuyển xuống sau `tab:be-hong`, trước `\section{Agent}`.
- Đổi chữ trỏ hình ở `07:153` (chỉ phần `\ref`); ba câu dẫn mới + một câu dẫn hình đầy đủ.
- Quy trình sơ đồ đầy đủ (phác → duyệt → … → subagent A, B).

### Bước 3 — D1 "Tải lên một tài liệu" (sequence, 7 bên, chương 6)
- Bên: `frontend`, `backend`, minio, postgres, `redis` (queue + channel), `document`, `ingest`.
  Thứ tự byte → bản ghi → giao job; content store là ghi chú ở `document`; event không mang dữ liệu
  → `frontend` gọi lại API; ghi chú luật 300 giây.
- **Xoá** `06:118-124`; **giữ** `06:103-116`, `07:264-277` (chỉ thêm `\ref` ở `07:264`).

### Bước 4 — D2 "Nộp bài → giai đoạn 2" (sequence, 5 bên)
- Chấm ngay → giao job chuẩn bị trước (đẩy queue hỏng vẫn nộp được) → hỏi trợ lí: mảnh chữ qua SSE,
  25 giây → bấm làm bài: kiểm hạn, không có lượt đang chạy → dùng câu chuẩn bị trước, thiếu thì tạo
  ngay và chờ (≤ 3).
- **Xoá** `07:254-262`; **giữ** `07:241-252`.

### Bước 5 — D3 "Ba tầng của đề xuất bước tiếp theo" (luồng)
- Jev chọn tệp lời dặn → mô hình theo khuôn → nhánh "chỉ đồng ý → plan từ dàn ý" → hộp "tám luật
  sửa" → phép kiểm, vấp chạy lại một lần → `backend`.
- **Xoá** `07:506-514`, `07:534-539`; **giữ** `07:501-504`, `07:516-520`, `07:522-532`,
  `07:541-542`.
- **Đổi 31/10 sau review:** hai đoạn xoá mang thông tin hình không mang (ba tệp lời dặn, danh sách
  phép kiểm, "không tự bịa tham số") và để văn gãy ("Khuôn…", thiếu "Tầng một"). Người dùng chốt
  **khôi phục nguyên chữ cả hai đoạn**; hình chỉ còn vai tóm ba tầng.
- Hình đầy đủ `teacher-chat-turn` (Bước 2): ghép nguyên thì chữ xuống ~6pt sau khi sửa theo review;
  người dùng chốt vẽ lại **dạng tổng quan**, chi tiết ở ba hình tách.

### Bước 6 — D4 "Đời một câu hỏi của đề" (luồng)
- Giao job kèm số phiên bản → viết ⇄ tự kiểm (≤ 3) → `redis` → thông báo → thu hoạch (hai lúc kích
  hoạt) → bỏ phiên bản cũ → `backend` kiểm → ghi đúng vị trí / giao lại, câu cũ được giữ. Hai hộp
  phép kiểm `agent` và `backend` đặt cạnh nhau.
- **Xoá** `07:215-223`; **giữ** `07:208-213`, `07:91-112`, `07:480-492` (thêm `\ref` ở `07:480`).

### Bước 7 — T3 "Thao tác trên đề" (bảng tạm cho D6)
- Cột: Thao tác · Điều kiện `backend` kiểm · Phạm vi · Vi phạm thì. Hàng: duyệt, phát hành, phát
  hành lại, bỏ duyệt và thu hồi. Chữ ô lấy từ `07:225-239`; vế "để tránh tình trạng…" vào cột cuối.
- **Xoá** `07:225-239`. D6 (sơ đồ trạng thái) chỉ làm khi người dùng chốt nhãn trạng thái (ADR-01);
  ghi vào backlog.

### Bước 8 — D7 Gantt "báo hỏng oan" (ưu tiên thấp)
- Lô của N cuốn đọc xen kẽ, khoảng cách hai lần báo tiến độ vượt 300 giây. Không xoá câu nào ở
  `07:1008-1014`; thêm một câu dẫn.

### Bước 9 — Khép
- `architecture.md`: link mọi `.drawio` mới, cập nhật đoạn "Diagram nào đã có". `rules.md` §6 bảng
  hình/chương và §8 khuôn hình: thêm các hình mới (đây là tài liệu luật, không phải câu của báo cáo).
- Backlog (`docs/plans/backlog.md` + artifact *Backlog theo tier*): D6 chờ ADR-01, và mọi vấn đề lộ ra.
- Subagent review cuối cả ba chương (PDF + diff). Không commit; người dùng duyệt sau cả plan.

## Files

- `docs/report/chapters/05-use-case.tex`, `06-kien-truc-va-du-lieu.tex`, `07-chi-tiet-cac-service.tex`
- `docs/diagrams/` 3 hình tách + D1, D2, D3, D4, D7 (`.drawio` mới); `docs/report/figures/*.pdf`,
  `sources.json`
- `docs/overview/architecture.md`, `docs/report/rules.md`, `docs/plans/backlog.md`,
  `docs/plans/active/2026-10-31-report-diagrams-plan.md`

## Validation Checks

- Mỗi `.drawio` parse được XML; script hình học: 0 chồng lấn, số đường cắt ghi rõ (mục tiêu 0).
- `.\dev.ps1 report` build sạch, không `??`, không thêm `Overfull` so với mốc; đọc PDF từng trang có
  hình/bảng mới: hình không đè lề, bảng không trôi khỏi mục, chữ nhỏ nhất ≥ 7pt.
- `.\dev.ps1 check` xanh (gồm check hình xuất từ `.drawio` hiện tại).
- `git diff` trên `docs/report/chapters/` chỉ chứa đúng các xoá/thêm đã liệt kê; subagent B xác nhận.
- Mỗi sơ đồ có một lượt subagent A sạch trên ảnh chụp.
- Không stage `docs/report/` trừ khi người dùng bảo; hai dòng TODO giữ ` M`.
- Kết quả lần chạy ngày 31/10/2026, trước khi chuyển plan:
  - `.\dev.ps1 check`: 26/26 xanh;
  - `.\dev.ps1 report`: 63 trang, 0 `Overfull`, không có tham chiếu `undefined`; cảnh báo duy nhất
    là "Float too large 23.8pt" ở chương 04, đã có từ trước plan;
  - `sources.json` khớp sha256 của cả 16 `.drawio`;
  - ba vòng review ảnh, hai vòng review diff, một review cuối; mọi phát hiện nặng hay vừa đã sửa.

## Decision Records

### Decision: Hai đoạn văn của D3 giữ nguyên

options considered: xoá hai đoạn như plan ban đầu và để hình thay; khôi phục nguyên chữ cả hai đoạn.
selected option: khôi phục nguyên chữ.
reason: hai đoạn ấy mang ba thứ hình không vẽ: ba tệp lời dặn, danh sách phép kiểm, và ý "không tự
bịa tham số". Xoá đi thì văn gãy, chẳng hạn đoạn sau mở bằng "Khuôn…" mà không còn đoạn "Tầng một"
đứng trước. Hình chỉ còn việc tóm ba tầng.

### Decision: Hình đầy đủ `teacher-chat-turn` vẽ dạng tổng quan

options considered: ghép nguyên ba hình con; vẽ lại dạng tổng quan.
selected option: tổng quan, có hai khung pha đề xuất và pha thực thi.
reason: sau khi sửa theo review, bản ghép nguyên có chữ chỉ còn khoảng 6pt khi in, dưới mức 7pt mà
`rules.md` §8 đặt ra. Chi tiết đã có ở ba hình con đặt cạnh đoạn văn của chúng.

## Status

Xong 31/10/2026. Chưa commit: người dùng duyệt cả đợt rồi mới commit. Khi commit thì không gồm hai
dòng `# TODO: Cần xem lại`, cũng không gồm `report.pdf`, trừ khi người dùng bảo. Những việc còn lại
đã ghi ở `backlog.md`, mục "Lộ ra khi đổi văn xuôi thành sơ đồ trong báo cáo (31/10/2026)":
- D6 chờ ADR-01;
- văn backend lệch chữ với hình;
- hình D3 đặt mọi phép kiểm sau tám luật;
- các lối ra hình chưa vẽ;
- `sec:hang-doi`.

Một lỗi nhẹ chưa ghi ở đâu: ô Phạm vi ở hàng "Duyệt đề" của Bảng 7.2 có chứa cả kết quả.
