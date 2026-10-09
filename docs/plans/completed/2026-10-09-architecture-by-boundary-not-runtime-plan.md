# Plan — Sơ đồ kiến trúc nói thiết kế, không nói nơi chạy

## Goal

Chương 7 và `system-architecture.drawio` đang tổ chức quanh một **ranh giới triển khai**. Hai thứ
to nhất trên hình là hai cái khung `Máy local — tiến trình native, không container hoá` và
`Docker — chỉ hạ tầng, không chứa mã nguồn`; chương 7 nối theo bằng câu *"vạch rõ phần nào chạy
thẳng trên máy, phần nào chạy trong container"*, và cột thứ ba của Bảng 7.1 tên là **"Chạy bằng"**
với nội dung `cổng 5173`, `cổng 8000`.

Hệ thống sẽ đóng gói container toàn bộ và có thể lên k8s. Lúc ấy **mọi thứ vừa kể sai cùng một
lúc**. Nhưng vấn đề nặng hơn là chúng chưa bao giờ là phần đáng vẽ: một người đọc để hiểu *hệ
thống được chia thế nào* đang phải nhìn một hình trả lời câu *hệ thống chạy ở đâu*.

**Kết quả mong đợi:** hình và chương nói **thiết kế service** — vai trò, ranh giới, ai quyết định,
ai cầm chìa khoá, ai nhận việc bằng đường nào — và không một chữ nào về native, Docker hay k8s
ngoài đúng một mục nói rõ kiến trúc **không** nói nơi chạy.

## Scope

**Trong:** `system-architecture.drawio` + hình xuất ra; chương 7 của báo cáo; những câu trong
`docs/overview/architecture.md` **mô tả tấm hình**.

**Ngoài:** phần cổng và native/Docker còn lại trong `architecture.md` — người dùng chốt đường **B**
ngày 09/10/2026. Tài liệu ấy phục vụ người chạy máy local, nên nói cổng ở đó là **đúng chỗ**; chỉ
những câu mô tả tấm hình mới phải theo hình.

## Decision Records

### Decision: sơ đồ kiến trúc tổ chức theo ranh giới thiết kế, không theo nơi chạy

**options considered:** (a) **tổ chức theo ba trục quyền quyết định / chìa khoá / có ai chờ** ·
(b) giữ khung native–Docker, thêm một khung k8s khi lên server · (c) tách làm hai hình, một kiến
trúc một triển khai.

**selected option:** (a). Người dùng chốt 09/10/2026.

**reason:** (b) là thứ đang có và nó hỏng theo lịch — mỗi lần đổi hạ tầng là một lần hình sai, mà
hình thì được nhúng vào một báo cáo đã nộp. (c) đúng về nguyên tắc nhưng sớm: chưa có triển khai
thật để vẽ, và `AGENTS.md` cấm dựng tài liệu kiến trúc trước khi có nội dung thật.

Ba trục của (a) không đổi khi lên container: **quyền quyết định** (được kết luận hay chỉ được báo
lại), **tầm với** (cầm chìa khoá nào), và **có ai đang chờ không** (có người đứng đợi thì là một
request; không ai chờ thì phải là một việc trong hàng đợi, vì một tiến trình đã chết thì không có
ai để trả 503 cho). Năm thành phần **rơi ra từ ba trục ấy**, nên luật này còn sinh ra được thành
phần thứ sáu thay vì chỉ mô tả năm cái đang có.

### Decision: giữ hình ở khổ ngang, không chuyển sang khổ dọc

**selected option:** giữ `landscape`.

**reason:** tôi đã đề xuất khổ dọc và người dùng duyệt, nhưng lúc đọc file thật thì cơ sở của đề
xuất ấy không còn: bề rộng do hàng ba kho (3 × 380) cùng hàng hai package quyết định, **không**
do hai cái khung triển khai vừa bỏ — tức chuyển sang 760 là **vẽ lại bố cục**, không phải thu
nhỏ, và bỏ hai cái khung không làm hình hẹp lại một pixel nào.

**Một câu của bản ghi này đã sai, và lượt review bắt được.** Bản đầu viết *"chín cạnh, không cạnh
nào cắt qua một hộp nào"*. Sai: cạnh `be` → hàng đợi đi thẳng xuống ở x = 700, mà hộp `ingest`
chiếm 430–710 — nó **xuyên qua hộp ấy**, nhìn thấy được cả trên trang in. Tệ hơn, đó đúng là lý
do duy nhất bản ghi đưa ra để giữ khổ ngang, nên lập luận tự đá vào chân mình. Đã đẩy cạnh ấy
sang hành lang trống x = 710–770 và xác nhận lại bằng ảnh render.

Thứ phải trả giá cho một lần vẽ lại ấy là ba cạnh `be` → kho: `be` nằm hàng trên, kho nằm hàng
dưới, worker nằm giữa, nên ở khổ hẹp chúng buộc phải cắt qua hàng worker. Đổi một lần xoay trang
lấy đúng loại lỗi chồng lấn mà chỉ bản render mới chỉ ra là một đổi chác tồi. Việc bỏ hai cái
khung không làm hình rộng ra, nên lý do duy nhất để vẽ lại đã mất.

## Files

| File | Việc |
| --- | --- |
| `docs/diagrams/system-architecture.drawio` | xoá `host-boundary` và `docker-boundary`; tiêu đề nói **kết luận**; bỏ số cổng; `Worker, không mở cổng` → `Không có bề mặt vào`; kho đổi thứ tự *vai trò trước, tên sản phẩm sau*; thêm ba nhãn dải và một chú thích **theo vai trò** |
| `docs/report/chapters/07-kien-truc-va-du-lieu.tex` | Bảng 7.1 đổi cột `Chạy bằng` → `Quyết định` / `Chìa khoá` / `Nhận việc qua`; bỏ câu *"vạch rõ phần nào chạy thẳng trên máy"*; thêm năm mục mới (dưới) |
| `docs/overview/architecture.md` | chỉ những câu **mô tả tấm hình** |
| `docs/report/figures/system-architecture.pdf` + `sources.json` | xuất lại, cập nhật sha256 |

**Năm mục mới của chương 7:** cái gì làm nên một thành phần (luật ba trục) · các thành phần nói
chuyện thế nào · thứ dùng chung và cái giá đã nhận · thành phần nào ngừng thì mất gì · kiến trúc
không nói nơi chạy.

## Ordered Tasks

- [x] **1. Sơ đồ.** Mổ đúng chỗ, không vẽ lại: bản trên đĩa đã tốt, màu đã mã hoá vai trò sẵn.
- [x] **2. Xuất hình, cập nhật `sources.json`.** Rồi **nhìn bản render** trước khi đi tiếp.
- [x] **3. Chương 7.** Bốn mục cũ giữ, năm mục mới, phần native/Docker thay bằng mục cuối.
- [x] **4. `architecture.md`.** Chỉ những câu mô tả hình — đường B.
- [x] **5. Build báo cáo, chạy cổng, một lượt subagent review.**

## Validation Checks

**Cổng của plan này:** `grep -in "native\|docker\|k8s\|container\|cổng 8000\|cổng 5173"` trên
`07-kien-truc-va-du-lieu.tex` và `system-architecture.drawio` chỉ còn khớp **trong đúng mục nói
rằng kiến trúc không nói nơi chạy** — không khớp ở đâu khác.

- `.\dev.ps1 report` build ra PDF, không lỗi LaTeX.
- `.\dev.ps1 check` xanh — gồm `check_every_figure_matches_the_diagram_it_came_from` (sửa `.drawio`
  mà quên xuất lại hình thì nó đỏ) và `check_no_document_repeats_itself`.
- **Nhìn bản render của hình**, không chỉ đọc XML: hai lượt trước đã có ba lỗi chỉ ảnh mới chỉ ra
  (chữ bị nuốt, nhãn đè khối, mũi tên xuyên qua hộp).
- Mục *Thành phần nào ngừng thì mất gì* chỉ được ghi những dòng **đo được hoặc đọc được từ code**;
  dòng `ingest` có số đo thật từ 08/10.

## Status

**Xong, chưa commit.** Cổng của plan: `grep` trên chương 7 và `.drawio` ra **không một chỗ nào**
khớp `native | docker | k8s | container | cổng 8000 | cổng 5173`. `check` **20/20** · báo cáo
build ra **42 trang**, không tham chiếu hỏng, không hộp tràn quá 20pt · năm bảng của chương 7 vào
đúng Danh mục bảng (7.1–7.5).

Đã **nhìn bản render** chứ không chỉ đọc nguồn: ảnh PNG của sơ đồ, và hai trang in có bảng mới.

**Một chỗ đổi so với thiết kế đã duyệt:** giữ hình ở khổ ngang thay vì chuyển sang khổ dọc — lý do
đầy đủ ở `## Decision Records`, gồm cả một câu của chính bản ghi ấy đã sai và đã được sửa.

**Lượt review tìm ra sáu lỗi thật, và không cổng nào bắt được cái nào.** Nặng nhất là một cạnh
**cắt xuyên hộp `ingest`** trên sơ đồ — đúng thứ mà bản ghi quyết định tuyên bố là không có — và
một tham chiếu chéo sai đã in ra trong PDF (`\ref{sec:hang-doi}` ở mục 7.9, trong khi "hai cơ
chế" nằm ở 7.4). Bốn cái còn lại: mục 7.4 tự mâu thuẫn trong hai mươi dòng (*"đúng hai cơ chế,
không có cơ chế thứ ba"* rồi mô tả ngay cơ chế thứ ba); Bảng 7.3 bỏ sót việc **đọc tài liệu cũng
hỏng** khi hàng đợi chết; Bảng 7.3 vẽ ra một tương phản `document`/`ingest` mà màn hình **không
có** (quá ngưỡng là cả hai đọc ra cùng một câu, vì trạng thái ấy được suy ra lúc đọc); và một
trong ba tính chất "mang đi được" ở 7.9 nói sai — cấu hình **có** đọc từ một tệp ở gốc dự án,
biến môi trường chỉ thắng nó.

Cộng ba chỗ nói quá đã hạ giọng: *"không bao giờ giữ một người dùng đứng chờ"*, *"dòng duy nhất
**có thể** kiểm bằng tay"* (sự thật: duy nhất **đã** kiểm — năm dòng kia suy từ mã nguồn), và một
đoạn trùng lặp gần nguyên văn giữa 7.4 và 7.6.

Và một mùi triển khai mà cổng `grep` **không thể** bắt vì nó đi theo từ khoá: hộp `fe` còn ghi
**Vite** — chính cái dev server giữ số cổng vừa bị xoá. Xoá số cổng mà giữ tên thứ mở cổng thì chỉ
xoá được một nửa. Đã đổi thành *React, chạy trong trình duyệt*.

**Một chỗ lệch có từ trước, không sửa vì ngoài đường B:** `architecture.md:252` còn viết *"Class
Diagram hoặc ERD sẽ cần khi có Postgres. Hiện chưa có bảng nào"* — nay đã có 21 bảng. Câu ấy không
mô tả tấm hình nên nó nằm ngoài phạm vi đã chốt.
