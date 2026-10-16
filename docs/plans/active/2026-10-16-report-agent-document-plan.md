# Chương 7 của báo cáo: viết lại mục Agent và Document theo khuôn của mục Backend

## Goal

Viết lại `\section{Agent}` và `\section{Document}` của
`docs/report/chapters/07-chi-tiet-cac-service.tex` theo đúng khuôn mục Backend vừa viết: vai trò và
trách nhiệm → cơ chế → luồng hay nghiệp vụ → các ràng buộc và cơ chế kiểm soát → xử lý lỗi → các
giới hạn hiện tại. Nội dung đúng với code, văn tự nhiên, theo `docs/report/rules.md`. Xong lượt
này, chương 7 hết mang hai bộ chữ cho bảng luật và bảng lỗi.

## Scope

- Trong phạm vi: hai mục Agent và Document của chương 7; nhãn của hình `document-pipeline`
  (`docs/diagrams/document-pipeline.drawio` và PDF xuất ra, `figures/sources.json`); `rules.md`;
  `docs/plans/backlog.md`; `docs/report/report.pdf`.
- Ngoài phạm vi: mục Backend và dòng 1–10 của chương 7; chương 03, 06; mọi tệp code. Chỗ code nói
  sai chỉ ghi backlog.
- Dừng sau Agent để người dùng duyệt; Document chỉ làm khi người dùng cho. Không commit khi chưa hỏi.

## Files

- `docs/report/chapters/07-chi-tiet-cac-service.tex`, `docs/report/report.pdf`
- `docs/report/rules.md`, `docs/plans/backlog.md`
- `docs/diagrams/document-pipeline.drawio`, `docs/report/figures/document-pipeline.pdf`,
  `docs/report/figures/sources.json` (pha D1)

## Ordered Tasks

- [x] Pha 0: commit phần Backend (`2cd8eaa`); mốc; tạo plan này.
- [x] A1: dàn ý Agent, kiểm sự thật với code; review.
- [x] A2: viết *Vai trò và trách nhiệm* và mục cơ chế, đổi tiêu đề thành `\section{Agent}`; review.
- [x] A3: viết mục các task chính; review.
- [x] A4: viết ràng buộc, xử lý lỗi, giới hạn; review.
- [x] A5: kiểm toàn mục; `rules.md` §2 (*hàm*); backlog; Status. **Dừng, chờ người dùng duyệt.**
- [ ] D1: đổi nhãn *"khâu"* trong hình `document-pipeline`, xuất lại; dàn ý Document; review.
- [ ] D2: viết *Vai trò và trách nhiệm* và mục cơ chế, đổi tiêu đề thành `\section{Document}`; review.
- [ ] D3: viết mục luồng một tệp; review.
- [ ] D4: viết ràng buộc, xử lý lỗi, giới hạn; review.
- [ ] D5: kiểm toàn chương; `rules.md`, backlog; Status; hỏi commit.

## Decision Records

### Decision: Tiêu đề Agent và Document

options considered: giữ `\section{\texttt{agent}}` và `\section{\texttt{document}}`; viết hoa như
`\section{Backend}`.
selected option: `\section{Agent}` và `\section{Document}`.
reason: người dùng đã đổi tiêu đề mục đầu thành `Backend`, nên ba mục cùng một kiểu. `rules.md` §1
miễn tên service viết hoa ở đầu tiêu đề; chữ *Document* trùng mặt chữ với mục *Document* (tài liệu)
của từ điển, nhưng ở vị trí tiêu đề một mục service thì nó là tên service.

### Decision: Phần cố định của graph gọi là "hàm"

options considered: giữ **khâu** (chữ `rules.md` §2 chốt khi viết chương 7) và giải nghĩa tại chỗ;
theo mục *Graph* của từ điển, nay viết **hàm**.
selected option: **hàm**, theo từ điển; *"hàm nhận job"* giữ nguyên.
reason: người dùng chọn (16/10/2026) và đã tự sửa mục *Graph* thành *"một chuỗi các hàm cố định"*;
từ điển là nơi duy nhất quyết định một khái niệm mang chữ gì (`rules.md` §1). Hệ quả biết trước:
"hàm" tạm mang hai nghĩa trong chương 7 (phần của graph, và hàm nhận job) — người dùng sẽ tự sửa
chữ thứ hai sau; chỗ lệch ghi ở `rules.md` và backlog. Hình `document-pipeline` vẽ chữ *"khâu"*
nên phải đổi trước văn bản (`rules.md` §6).

### Decision: Commit phần Backend trước

options considered: commit Backend trước khi làm Agent; để chung, commit sau.
selected option: commit trước (`2cd8eaa`).
reason: người dùng chọn; diff của Agent và Document tách bạch khỏi Backend đã duyệt.

## Validation Checks

- `.\dev.ps1 report` sạch; chuỗi dò của tiêu đề mới có trong PDF; không `??`.
- `.\dev.ps1 check` xanh.
- Mục vừa viết không còn `chờ`, `đợi`, `tác vụ`, `streaming`, `timeout`, `retry`, `luồng SSE`,
  `khâu`, `Luật và chỗ canh luật`, `Khi hỏng`; "khoá" chỉ mang nghĩa khoá đoạn hội thoại.
- Mọi chữ tiếng Anh lần đầu trong văn xuôi chương 7 có chú thích; không lần nào in đậm lại.
- Mục Backend và dòng 1–10 của chương 7 giống mốc từng byte.

## Status

Phần Agent xong ngày 16/10/2026; dừng chờ người dùng duyệt trước khi sang Document. Chưa commit
phần Agent.

- Năm pha A1–A5, mỗi pha một subagent review và đã sửa theo: dàn ý (mười chỗ phải sửa, phần lớn là số
  dòng và các khẳng định nói quá mang theo từ bản cũ), 7.2.1–7.2.2, 7.2.3, 7.2.4–7.2.6.
- Build sạch (53 trang), `.\dev.ps1 check` 23/23. Phần ngoài mục Agent giống mốc `moc4` từng byte.
- Những chỗ bản cũ nói sai đã sửa: khuôn JSON chỉ ở hai graph; Jev đọc bốn tin nhắn, không phải bốn
  "lượt"; trong tám luật sửa, sáu đổi đề xuất thành lời gọi tool tra cứu; trần hai mươi giây là
  của một lần gửi, nên một lần gọi có thể quá sáu mươi giây; đề xuất dọn trước không còn tự nêu plan
  soạn đề; giới hạn đồng ý dàn ý nằm ở mô hình chứ không ở luật so chữ.
- `rules.md` §2: phần của graph là **hàm**; *Những chỗ đã biết là còn sai* thêm "hàm" hai nghĩa và
  thu hẹp "hai bộ chữ" về mục Document. `backlog.md`: hai bộ chữ, "khoá", "hàm", bốn docstring sai
  của `agent`, mảnh chữ phát hỏng.
- Trang 49 (mục Document cũ) trống khoảng một phần tư, vì bảng `[H]` *Bảy khâu* bị đẩy sang trang
  sau khi mục Agent dài ra; phần Document sẽ viết lại chỗ ấy.
- Trong lúc làm, một thay đổi khác (`claude-provider-option`) sửa code `agent` và `document` mà
  chưa commit. Lượt này không đụng tới nó; câu về thư viện của OpenAI tự gửi lại ở 7.2.4 cần xem lại
  nếu Model Provider mặc định đổi sang Claude.
