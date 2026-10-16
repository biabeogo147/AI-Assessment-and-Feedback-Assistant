# Từ điển chương 3 của báo cáo: "thông báo", xếp lại, thêm mục, chú thích lần nhắc đầu

## Goal

Mọi chữ tiếng Anh trong báo cáo (`docs/report/`) có định nghĩa ở từ điển chương 3 trước khi được
dùng, trừ tên riêng. Ở các chương khác, lần nhắc đầu trong văn xuôi viết dạng "tiếng Anh (tiếng
Việt)"; chương đứng trước chương 3 thì trỏ sang chương 3. Đồng thời đóng lượt đổi "hích / chở /
chuông": thứ phát lên channel gọi là **thông báo**, thứ `backend` gửi xuống màn hình qua SSE gọi là
**event**.

## Scope

- Trong phạm vi: `docs/report/chapters/` (01, 03–08), `docs/report/rules.md`,
  `docs/diagrams/teacher-chat-turn.drawio` cùng PDF xuất ra và `figures/sources.json`,
  `docs/plans/backlog.md`.
- Ngoài phạm vi: mọi tệp code, `docs/overview/architecture.md`, sáu hình của người dùng (mọi hình
  trừ `teacher-chat-turn` và `document-pipeline`), chương 02. Chỗ sai ở đó chỉ ghi backlog.
- Không đụng hai dòng `% Chú ý đoạn này` của người dùng ở chương 06.
- Không commit khi người dùng chưa duyệt.

## Files

- `docs/report/chapters/01-dat-van-de.tex`, `03-actor-va-khai-niem.tex`, `04-luong-nghiep-vu.tex`,
  `05-use-case.tex`, `06-kien-truc-va-du-lieu.tex`, `07-chi-tiet-cac-service.tex`,
  `08-tai-lieu-tham-khao.tex`
- `docs/report/rules.md`, `docs/report/figures/sources.json`, `docs/report/figures/teacher-chat-turn.pdf`,
  `docs/report/report.pdf`
- `docs/diagrams/teacher-chat-turn.drawio`
- `docs/plans/backlog.md`

## Ordered Tasks

- [x] Pha 0: chụp mốc các tệp sẽ sửa; plan này.
- [x] Pha 1: "thông báo" thay "notify" ở chương 07 và hình `teacher-chat-turn`; 06:103 "giao việc";
      `rules.md` §2. Review.
- [x] Pha 2: chương 3 — chú thích actor; từ điển chia bốn nhóm theo thứ tự phụ thuộc; chín mục mới
      (Actor, Use case, Workflow, Metadata, API, VPC và Subnet, Byte, Collection, Event), và
      Pub/sub gộp Channel; bỏ các tham chiếu xuôi. Từ điển từ 41 lên 50 mục. Review.
- [x] Pha 3: lần nhắc đầu ở 01, 04–08; 01 trỏ sang từ điển; các chữ B2 đổi sang tiếng Việt ở mọi
      chỗ (end-to-end, generalize, refresh, tab, logic, import, code, test, CPU). Review.
- [x] Pha 4: `rules.md` §1, §2, §3, §4, §5, §6, §9, §10; backlog; review cuối.

## Decision Records

### Decision: Thứ phát lên channel gọi là "thông báo"

options considered: giữ "tiếng" / "chuông" / "hích" như các chương đang viết; `notify`; `message`
theo tên của redis; "thông báo".
selected option: **thông báo**; thứ `backend` gửi xuống màn hình qua SSE giữ chữ **event**.
reason: bốn chữ cũ là ẩn dụ, và mỗi chương dùng một chữ khác cho cùng một thứ. Code không có tên
nào để neo một chữ tiếng Anh: `bell`, `ring_bell` cũng là ẩn dụ; `publish` đã thuộc về phát hành
đề; `message` đụng `chat_messages`. "Thông báo" là chữ tiếng Việt thường, người đọc hiểu ngay,
nên không cần ngoại lệ cho luật neo tên của `rules.md` §1. *Event* thì đã có chỗ neo ở phía SSE
(`TurnEvent`, `text/event-stream`).

### Decision: Từ điển xếp theo thứ tự phụ thuộc, chia bốn nhóm

options considered: giữ thứ tự cũ và chỉ thêm mục; xếp theo chữ cái; xếp theo thứ tự phụ thuộc.
selected option: bốn nhóm (người dùng, đề và bài làm; service và cách chúng trao đổi; tài liệu;
trợ lí); trong mỗi nhóm, một mục chỉ dùng những chữ tiếng Anh đã có mục phía trên nó.
reason: thứ tự cũ có khoảng mười tham chiếu xuôi — mục *Bản thô* dùng content store trước mục
*Store*, mục *Graph* dùng plan và tool trước mục của chúng. Xếp theo chữ cái không sửa được điều
đó. Với năm mươi mục, chia nhóm giúp người đọc tìm được mục mình cần.

### Decision: Tên riêng không vào từ điển

options considered: mỗi tên riêng một mục; miễn hẳn.
selected option: miễn hẳn — tên sản phẩm, thư viện, công ty; tên ngôn ngữ và định dạng (Python,
LaTeX, PDF, JSON, UTF-8); tên hình (Domain Context, …); tên use case.
reason: từ điển tồn tại để chốt một chữ cho một khái niệm. Một tên riêng chỉ trỏ tới đúng một thứ,
nên không có nghĩa nào cần chốt; một mục cho nó sẽ là lời giới thiệu sản phẩm, không phải định
nghĩa.

### Decision: Thêm mục hay đổi sang tiếng Việt

options considered: thêm mục cho mọi chữ tiếng Anh đang dùng; đổi hết sang tiếng Việt; chọn theo luật
neo tên của `rules.md` §1.
selected option: chữ neo được vào một tên thật — trong code, trong sơ đồ, trong tài liệu nghiệp vụ
`docs/overview/`, hay trong ngôn ngữ mô hình hoá — thì thêm mục (actor, use case, workflow, metadata,
API, VPC, subnet, byte, collection, event). Chữ chỉ là từ thông dụng của dân lập trình thì đổi sang
tiếng Việt ở mọi chỗ, kể cả ô bảng (code, test, tab, refresh, logic, import, CPU, end-to-end,
generalize).
reason: từ điển là nơi chốt một chữ cho một khái niệm của hệ thống, không phải bảng thuật ngữ tin
học. Thêm mục cho *code* hay *tab* không chốt được nghĩa nào mà người đọc chưa có; ngược lại
*metadata*, *workflow* đã là chữ của chính tài liệu nghiệp vụ mà chương 04, 05 rút từ đó, nên đổi
chúng sẽ làm báo cáo lệch khỏi nguồn.

## Validation Checks

- `.\dev.ps1 report` sạch: không lỗi, không `undefined`, không `??`; chuỗi dò của từng pha có trong PDF.
- `.\dev.ps1 check` xanh, gồm check manifest hình.
- Kiểm thứ tự từ điển và kiểm kê chữ tiếng Anh: mọi chữ ASCII ngoài `\texttt` ở 01–08 hoặc có mục
  trong từ điển, hoặc là tên riêng.
- Lần nhắc đầu trong văn xuôi ở mỗi chương có chú thích.
- Hình `teacher-chat-turn`: 0 chồng lấn, 0 đường cắt, chữ nhỏ nhất ≥ 7pt trên giấy; sha khớp.
- Line ending giữ nguyên (01, 02, 05 CRLF; còn lại LF).

## Status

Bốn pha xong ngày 16/10/2026, mỗi pha một lần review và đã sửa theo; review cuối cho cả lượt cũng đã
sửa theo. Build sạch (48 trang), `.\dev.ps1 check` 23/23. Kiểm kê chữ tiếng Anh: không mục nào trong
từ điển dùng chữ của mục phía dưới, và mọi chữ ASCII ngoài `\texttt` ở 01–08 hoặc có mục, hoặc là
tên riêng. Bảng 6.2 (`[H]`) vẫn vừa trang như trước lượt này. Chưa commit: chờ người dùng duyệt.
Những gì còn lại nằm ở `backlog.md`, mục *Lộ ra khi sửa từ điển chương 3 của báo cáo*.

Sau review cuối, người dùng tự sửa chương 3 (rút gọn nhiều mục; bỏ Metadata, Mastery, Thu hoạch),
chương 5, chương 6 và hình `use-case`. Những thay đổi ấy là của người dùng và được commit nguyên
trạng; plan này chỉ xuất lại `use-case.pdf` cho khớp `sources.json`. Vì vậy các số đếm ở trên
(50 mục) tả từ điển lúc plan xong, không phải lúc commit.
