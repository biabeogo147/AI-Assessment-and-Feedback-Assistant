# Chương 7 của báo cáo: chi tiết ba service, và phần nền của nó

## Goal

Viết chương 7 của báo cáo (`docs/report/`) đi vào bên trong `backend`, `agent`, `document`. Trước đó
sửa nền mà chương ấy đứng lên: tám chỗ chương 03/06 nói ngược code, bốn mục từ điển mới,
`docs/overview/architecture.md` cho đúng code, và hai hình mới. Những gì còn lại vào `backlog.md`.

## Scope

- Trong phạm vi: `docs/report/` (chương 03, 06, chương 7 mới, tài liệu tham khảo đổi số, `report.tex`,
  `preamble.tex`, `rules.md`, `figures/`), `docs/diagrams/` (hai `.drawio` mới),
  `docs/overview/architecture.md`, `docs/plans/backlog.md`.
- Ngoài phạm vi: mọi tệp code, `AGENTS.md`, ADR. Chỗ sai ở đó chỉ ghi backlog.
- Không commit trong plan này; người dùng duyệt sau cả plan.

## Files

- `docs/report/chapters/03-actor-va-khai-niem.tex`, `06-kien-truc-va-du-lieu.tex`
- `docs/report/chapters/07-chi-tiet-cac-service.tex` (mới), `08-tai-lieu-tham-khao.tex` (đổi tên từ `07-`)
- `docs/report/report.tex`, `preamble.tex`, `rules.md`, `figures/sources.json`
- `docs/diagrams/document-pipeline.drawio`, `teacher-chat-turn.drawio` (mới) và hai PDF xuất ra
- `docs/overview/architecture.md`, `docs/plans/backlog.md`

## Ordered Tasks

- [x] Pha 0: chụp mốc gốc các tệp sẽ sửa; `.\dev.ps1 check` mốc (23/23 xanh, 16/10/2026).
- [x] Pha 1: tám chỗ 03/06; bốn mục từ điển (`Graph`, `Chunk`, Bản thô, Thu hoạch); 31 chỗ
      `architecture.md`; bảng chữ vào `rules.md` §2. Review: đúng và tự nhiên (hai reviewer).
- [x] Pha 2: `document-pipeline` và `teacher-chat-turn`; kiểm hình học trên XML và trên PDF; review
      bằng ảnh chụp (hai vòng, vòng hai sạch trừ bảy điểm nhỏ đã sửa).
- [x] Pha 3: chương 7 — khung, rồi mục `backend`, `agent`, `document`; mỗi mục một lần review.
- [x] Pha 4: backlog nhận mọi việc còn lại (mục *Lộ ra khi viết chương 7 của báo cáo*).
- [x] Pha 5: `rules.md` §2, §6–§10 đo lại trên tám chương; đo độ dài chương 7; review cuối cả chương.

## Decision Records

### Decision: Bảng chữ cho bên trong service

options considered: node của graph gọi là "bước" (như docstring `index/graph.py`), "chặng", hay "khâu".
selected option: node của graph là **khâu**; công đoạn OCR là **chặng**; **bước** giữ nghĩa bước của
một lượt hội thoại; phần tử của plan là **việc**.
reason: chương 06 đã dùng "bước" cho bước của một lượt hội thoại (06:145, :166, :278). Năm tệp trong
`document/ocr/` và `contracts/content.py` đã gọi công đoạn OCR là "chặng", nên báo cáo theo code ở
đó. "Khâu" không đụng tên nào trong code. Mục `Graph` của từ điển định nghĩa chữ ấy, vì `rules.md`
nói từ điển là nơi duy nhất đặt tên khái niệm.

### Decision: Mỗi service trả lời cùng năm câu hỏi

options considered: chia theo module; theo ADR; theo task; một khung chung.
selected option: một khung chung gồm năm câu hỏi. Ba tiêu đề cố định là *Vào và ra*, *Luật và chỗ
canh luật*, *Khi hỏng*; hai tiêu đề giữa đặt tên theo hình dạng của từng service.
reason: chia theo module bắt người đọc học tên tệp. Chia theo ADR làm mất bức tranh một lời gọi đi
qua. Chia theo task kể lại cùng một khuôn sáu lần. Ba service có tiêu đề cố định thì so được với
nhau.

### Decision: Hai hình, cả hai trên trang dọc

options considered: mỗi service một hình; một hình sequence trang ngang.
selected option: chỉ hai hình. `document-pipeline` là hình rộng `[htbp]` cao tối đa nửa trang;
`teacher-chat-turn` là sequence trọn một trang dọc `[p]`.
reason: hình bên trong `backend` chỉ lặp lại bảng khối và `system-architecture`. Môi trường
`landscape` của `pdflscape` ép `\clearpage`, nên một hình ngang giữa mục sẽ để lại nửa trang trống.
Sequence vốn dài theo chiều dọc.

### Decision: Trần độ dài

options considered: ba đề xuất ban đầu cộng lại khoảng 17–18 trang.
selected option: `backend` khoảng 4,4 trang, `agent` khoảng 3,5, `document` khoảng 3,5 kể cả hình,
cộng một trang sequence.
reason: thân báo cáo hiện có khoảng 27 trang, và `fe`/`ingest` còn đến sau.

## Validation Checks

- `.\dev.ps1 report`; khẳng định dương trên log: XeTeX, có dòng `Output written`, số trang khớp PDF,
  không `Fatal`, không lỗi `file:line`, không `undefined`, không `Missing character`, không `??`.
- `.\dev.ps1 check` xanh, kể cả check hình phải xuất từ `.drawio` hiện tại.
- Hình: XML parse được; không chồng lấn; không cạnh nào xuyên qua hình; số đường cắt in ra; mọi
  chữ có mặt trong PDF; chữ nhỏ nhất trên giấy ≥ 7pt; review bằng ảnh chụp.
- Markdown: link trỏ tới tệp có thật; mỗi `.drawio` được ít nhất một tệp Markdown nhắc tới.

## Completion Criteria

Chương 7 build sạch, mọi khẳng định có chỗ tương ứng trong code, không nói ngược chương 03/06 và
`architecture.md`. Mỗi pha có một lần review đã được xử lí.

## Status

Xong mọi pha, 16/10/2026. Người dùng duyệt và cho commit cùng ngày, kèm những chỗ họ tự sửa ở
chương 06.

- Build sạch (XeTeX, 47 trang, không `Overfull` nào), `.\dev.ps1 check` 23/23 xanh.
- Chương 7 dài 14 trang (33–46), vượt trần khoảng 12,5 trang chừng một trang rưỡi: đặt mọi bảng
  ngay trong mục của nó, thay vì để LaTeX đẩy bảng qua tiêu đề mục kế, tốn thêm khoảng một trang.
- Một cảnh báo có từ trước, ngoài phạm vi: hình `activity-overview` ở chương 04 vượt trang 23,8 pt
  (đã ghi backlog).
- Không có tệp code nào đổi; đã chạy `test_no_routing_decision` (an toàn, mô hình giả) để xác nhận
  một khẳng định của chương 7.
