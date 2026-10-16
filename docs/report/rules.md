# Luật viết báo cáo

Luật về **câu chữ và cách trình bày** của `docs/report/`. Quy trình build, cổng kiểm và invariant của
repo nằm ở `AGENTS.md` gốc; tài liệu này không nhắc lại.

Mỗi luật kèm vụ việc đã sinh ra nó. Một luật không có vụ việc thì người đọc sau không biết nó đắt ở
đâu mà tuân. Mọi số đo trong tài liệu này lấy từ tám chương hiện có, đo lại ngày 16/10/2026 — nếu
sửa lớn thì đo lại.

## 1. Chọn chữ: tiếng Anh hay tiếng Việt

Từ điển khái niệm (`chapters/03-actor-va-khai-niem.tex`, `\label{sec:tu-dien}`) là nơi duy nhất
quyết định một khái niệm được gọi bằng chữ gì. Ngoài nó, không tự đặt thêm chữ tiếng Anh.

**Một thuật ngữ tiếng Anh chỉ vào từ điển khi nó neo vào một tên thật** — trong code, trong một sơ
đồ của báo cáo, trong tài liệu nghiệp vụ mà chương 04, 05 rút từ đó (`docs/overview/`, nơi có
*metadata*), hay trong ngôn ngữ mô hình hoá mà báo cáo dùng (*actor*, *use case*, *workflow*). Không
dịch ngược từ tiếng Việt sang một chữ nghe có vẻ kỹ thuật. Đã có lượt đề nghị `grading` cho "chấm
bài" và lấy làm bằng chứng đúng cái tên mà mã nguồn tự gọi là đã mục ruỗng; và đã có lượt định thêm
`embedding`, `retrieval`, `chunk` cho một tính năng hệ thống chưa làm. (`chunk` về sau mới thành tên
thật -- collection `chunks` của content store -- và chỉ từ lúc ấy mới vào từ điển.)

**Đừng Anh hoá một từ tiếng Việt thường chỉ vì nó trùng mặt chữ với một thuật ngữ.** Đây là lỗi dễ
mắc nhất khi đi theo một danh sách thay chữ:

| Chỗ | Trông như | Thật ra là |
|---|---|---|
| `01` "khối lượng công việc" | `job` | việc của giáo viên |
| `02:14`, `04:91` "học sinh hỏi lại đến khi hiểu" | `polling` | học sinh đặt câu hỏi |
| `04:36` `\paragraph{Điểm kiểm soát.}` | `mark` / `score` | *control point* |
| "Luồng chính", "Điều kiện trước", "Ngoại lệ" | thuật ngữ UML | từ vựng tiếng Việt đã chuẩn |

**Chữ hiện trên màn hình người dùng thì giữ nguyên tiếng Việt**, kể cả khi có chữ tiếng Anh tương
ứng. Trạng thái của đề được dịch sang tiếng Việt một cách có chủ ý để hiện lên giao diện; Anh hoá
chúng trong báo cáo là làm báo cáo lệch khỏi thứ giáo viên nhìn thấy.

**Không Anh hoá nửa một cặp.** *Vòng* và *lượt* dùng chung một chữ `round` trong hệ thống, mà từ điển
đã gán mục **Lượt** cho nghĩa thứ hai — đổi một nửa sẽ làm hai mục đụng nhau. Cả hai giữ tiếng Việt.

**Mọi chữ tiếng Anh trong báo cáo phải có mục trong từ điển, trừ tên riêng.** Luật tính cả ô bảng,
tiêu đề và caption, dù ở đó không cần chú thích (§3). Tới ngày 16/10/2026, `actor`, `use case`,
`workflow`, `metadata`, `api`, `byte`, `VPC`, `subnet`, `collection`, `event` vẫn được dùng mà không có
mục, và đoạn này từng ghi rằng *để yên là chấp nhận được*. Lượt sửa ngày ấy cho mỗi chữ một trong hai
đường: thêm mục, hoặc đổi sang tiếng Việt ở **mọi** chỗ, kể cả ô bảng — `code` thành *mã nguồn*,
`test` thành *kiểm thử*, `tab` thành *thẻ trình duyệt*, `refresh` thành *làm mới*, cùng `logic`,
`import`, `CPU`, `end-to-end`, `generalize`. Muốn dùng một chữ tiếng Anh mới thì thêm mục trước.

**Tên riêng không có mục**, vì một tên riêng chỉ trỏ tới đúng một thứ, không có nghĩa nào cần chốt.
Có bốn loại: tên sản phẩm, thư viện, công ty (Kriky, postgres, redis, LangGraph, Jev, OpenAI…); tên
ngôn ngữ và định dạng (Python, LaTeX, PDF, JSON, UTF-8, BOM); tên một hình (Domain Context,
Activity Overview, Business Workflows, System Architecture, Use Case Diagram); và tên một use case
(*Review và phát hành đề*). JSON là tên một định dạng: câu ở chương 07 nói đúng cách định dạng ấy xử
lí dấu gạch chéo, nên đổi nó sang tiếng Việt là mất ý.

Luật cũng không tính chữ trong `\texttt` (tên trong code, kể cả nhãn `System/AI` ở chương 04), tên
service viết hoa ở đầu một tiêu đề (*Frontend*, *Backend*), và lời trích nguyên văn (*"ok"* ở
chương 07). Chữ **vẽ trong hình** thì có tính, nhưng hình chỉ sửa được bằng một việc riêng (§6);
những chữ còn sót trong hình được ghi ở `docs/plans/backlog.md`.

## 2. Một chữ, một nghĩa — và một nghĩa, một chữ

Đây là lý do từ điển tồn tại, nên nó là luật nặng nhất ở đây.

**Một chữ không được phủ hai khái niệm.** Những chỗ đã phải tách:

| Chữ cũ | Phủ hai thứ | Tách thành |
|---|---|---|
| "việc" | một lần chạy, và *tên* loại việc | `job` / `task` |
| "kho" | bốn thứ khác loại hẳn nhau | `database` / `object store` / `content store` / `queue` |
| "điểm" | điểm một câu, và điểm cả bài | `mark` / `score` |
| "hỏi lại" | agent hỏi khi thiếu thông tin, và học sinh hỏi cho hiểu | hai câu khác nhau |
| "hạn" | hạn mở, hạn đóng, hạn giai đoạn 2 | `opens_at` / `closes_at` / `remediation_deadline` |
| "hích", "tiếng hích" | thứ phát lên channel chỉ để báo có gì vừa đổi, và thứ `backend` gửi xuống màn hình qua SSE | **thông báo** / **event** |
| "bước" | bước của một lượt hội thoại, một phần của graph, một công đoạn OCR | **bước** / **hàm** / **chặng** |
| "lượt" | lượt làm lại, và một tin nhắn cùng mọi thứ trợ lí làm để đáp lại nó | **Lượt** / **lượt hội thoại** |
| "chờ" | `backend` đợi kết quả một job, và thứ làm chậm một worker | **lấy kết quả** / nói thẳng bộ xử lí hay mô hình |
| "lớp" | lớp học, tầng của code, và lớp chữ của một tệp PDF | **lớp** chỉ cho lớp học / **phần** / **có sẵn chữ** |
| "tầng" | phần của code, và tầng phòng thủ trải qua nhiều service | **phần** / **tầng** |
| "luồng" | luồng nghiệp vụ, và kết nối SSE mà `backend` giữ mở | **luồng** chỉ cho luồng nghiệp vụ / **kết nối SSE** |
| "đoạn chữ" | phần chữ hiện dần, và đoạn văn hay *đoạn hội thoại* | **mảnh chữ** cho phần chữ hiện dần |

Năm hàng từ "bước" tới "tầng" được chốt khi viết chương 7 (16/10/2026); hàng "hích" ngay trên chúng
được chốt cùng ngày, ở lượt sửa từ điển sau đó (đoạn *Pub/sub* dưới đây); hai hàng cuối được chốt ở
lượt viết lại mục backend của chương 7, cũng ngày ấy, khi review bắt được "luồng SSE" đứng ngay cạnh
"luồng nghiệp vụ", và "đoạn chữ" ở mục backend trong khi mục agent gọi đúng thứ ấy là "mảnh chữ".

Chương 06 đã dùng "bước" cho bước của một lượt hội thoại, và code của `document/ocr/` đã gọi công
đoạn OCR là "chặng", nên phần của graph từng mang chữ thứ ba, **khâu**. Sau đó người dùng sửa mục
*Graph* của từ điển thành *"một chuỗi các hàm cố định"*, và từ điển là nơi duy nhất quyết định chữ
(§1): từ lượt viết lại mục Agent (16/10/2026), phần của graph là **hàm**. Hệ quả biết trước: *hàm
nhận job* cũng là "hàm", nên chữ ấy tạm mang hai nghĩa (xem *Những chỗ đã biết là còn sai*). Từ điển
cũng không còn định nghĩa *chặng* — mục *OCR* nay chỉ một câu — nên chương 7 giải nghĩa nó tại
chỗ.

"Chờ" vẫn dùng được theo nghĩa thường — *người đang chờ* (chương 06), *job đang chờ* (mục *Store*)
— chỉ không dùng cho cách `backend` nhận kết quả một job. **"Đợi" cũng không**: đổi sang một từ
đồng nghĩa là né luật, không phải theo luật — bản cũ của chương 7 viết *"giao đi mà không đứng
đợi"* đúng ở chỗ ấy.

Hai chữ nữa đi kèm. **Việc** đếm được — *một việc*, *các việc của plan* — là một phần tử của plan
(mục *Plan*); *việc* theo nghĩa thường (*loại việc*, *mất việc*) không tính. Và **nội
dung dọn trước** — thứ `agent` trả khi mô hình tắt hay hỏng, đúng chữ code dùng — khác **mô hình
dự phòng**, một mô hình thứ hai được gọi khi mô hình chính hỏng.

**Ngược lại, một khái niệm không được mang hai chữ trong cùng một chương.** Chương 06 từng viết
`tool` ở hai chỗ rồi "công cụ" ở chỗ thứ ba cho cùng khái niệm.

Pub/sub là ví dụ nặng hơn. Thứ `ingest` và `agent` phát lên channel để báo có gì vừa đổi (không
kể chữ hiện dần) từng mang bốn chữ: "tiếng" (chương 03 và 06), "tín hiệu" (chương 06), "chuông" và
"tiếng hích" (chương 07). Thứ `backend` gửi xuống màn hình qua SSE thì mang "hích" và "đẩy". Ngày
16/10/2026 chốt **thông báo** cho cái đầu (mục *Pub/sub và Channel*) và **event** cho cái sau (mục
*Event*).

Cái đầu giữ tiếng Việt vì code không có tên nào để neo một chữ tiếng Anh: `ring_bell`
(`agent/handlers.py`) cũng là ẩn dụ, chính là "chuông" vừa bỏ; `publish` đã thuộc về phát hành đề;
còn tên của redis, *message*, thì đụng *tin nhắn* (`chat_messages`). *Event* thì neo được vào phía
SSE: `TurnEvent` (`be/teacher_chat.py`) và chính `text/event-stream`. Phía pub/sub của tài liệu
thì code đặt trong hai tệp tên *events*: nửa phát `announce` ở `ingest/events.py`, nửa nghe
`open_changes` ở `be/document_events.py`. Báo cáo không theo tên tệp ấy, vì *event* đã thuộc về
phía SSE.

Cùng lượt ấy, "chở" đổi thành **mang** khi nói một job mang gì; ở câu khác nó thành *chứa*, *đưa
vào* hay *giữ*.

**Và một chữ tiếng Anh đã gán nghĩa thì không được dùng cho nghĩa khác.** Từ điển gán `publish` =
*phát hành một đề cho một lớp*. Có lượt in đậm đúng chữ ấy cho động tác pub/sub của redis, nên người
đọc vừa học xong ở chương 3 sẽ hiểu redis đang phát hành đề.

## 3. Chú thích thuật ngữ

- **Lần nhắc đầu tiên trong *văn xuôi* của mỗi chương** phải có chú thích. Theo từng chương, vì người
  đọc có thể mở giữa báo cáo.
- **Chương đứng trước từ điển** (01, 02) chú thích kèm một tham chiếu —
  `\textbf{actor} (tác nhân, mục~\ref{sec:tu-dien})` — vì người đọc chưa tới chương 3.
- **Tiêu đề mục, caption và ô bảng không tính là một lần nhắc**, và ở đó Anh hoá trần không ngoặc.
  Một ngoặc giải thích trong ô bảng hẹp đọc rất tệ, và `\textbf` bên trong một tiêu đề vốn đã in đậm
  thì **vô hình** — có lượt đặt chú thích vào `\paragraph` và việc đánh dấu "lần nhắc đầu" không hiện
  ra trên trang. Vì luật này, `gateway` trần ở ô bảng `06:19` rồi in đậm kèm ngoặc ở `06:30` là
  **đúng**, không phải in đậm lại.
- **Mọi lần sau trong cùng chương**: dùng thẳng tiếng Anh, **không in đậm lại**.
- **Hai dạng chú thích được phép**: ngoặc đơn ngay sau chữ — `\textbf{queue} (hàng đợi)` — hoặc giải
  thích ngay trong cùng câu — *"kèm `\textbf{task}` là tên của loại việc ấy"*.
- **Không bao giờ chú thích bằng một cặp gạch ngang.** Trong tám chương, `---` được dùng **51 lần**
  cho mệnh đề phụ, nên một bản dịch kẹp giữa hai gạch ngang không phân biệt được với một mệnh đề
  phụ. (Một gạch ngang **đơn** sau nhãn đầu `\item` — `\item \textbf{Nội dung} --- câu hỏi và lời
  giải` — là văn phong của báo cáo, không phải chú thích.)
- **Chú thích phải ở hoặc trước lần dùng đầu trong văn xuôi.** Có lượt chú thích `store` ở dòng 80
  trong khi chữ ấy dùng lần đầu ở dòng 45: người đọc gặp chữ trước khi gặp nghĩa. Chương 07 từng mắc
  đúng lỗi ấy với `queue`.
- **Trong từ điển, một mục chỉ dùng những chữ tiếng Anh đã có mục ở phía trên nó.** Thứ tự cũ có
  khoảng mười tham chiếu xuôi: mục *Bản thô* dùng *content store* trước mục *Store*, mục *Graph* dùng
  *plan* và *tool* trước mục của chúng. Từ 16/10/2026 từ điển chia bốn nhóm theo thứ tự phụ thuộc;
  thêm mục mới thì đặt nó dưới mọi mục nó dùng. Chữ tiếng Việt của từ điển (*cây mục lục*, *dàn ý*)
  dùng trước mục của nó thì được.
- **Trong ngoặc bao giờ cũng là tiếng Việt** — không phải tên sản phẩm, không phải một chữ tiếng Anh
  khác.
  `\textbf{database} (postgres)` đọc ra *"database = postgres"*, vì cả chương đã dạy rằng ngoặc là
  bản dịch.
- **Gỡ tên sản phẩm ra khỏi ngoặc thì phải đặt bản dịch vào, không để trống.** Một lượt sửa gỡ
  `(postgres)` và `(minio)` rồi để `database` với `object store` không còn chú thích nào — luật
  "trong ngoặc là tiếng Việt" được thoả bằng cách xoá ngoặc.
- **Một chú thích không bao giờ thay cho một định nghĩa.** Mục `Question Bank` từng chỉ có ba chữ
  *"Ngân hàng đề."* — ít thông tin hơn chính câu ở chương 01 trỏ sang nó. Mỗi mục từ điển phải nói
  khái niệm ấy **là gì** và **đứng cạnh cái gì**, không chỉ dịch tên nó.

## 4. Câu

**Dấu hai chấm phải sát trước danh sách nó dẫn** — khi câu dẫn là văn xuôi. Có lượt chèn hai câu định
nghĩa vào giữa mệnh đề dẫn và `\begin{itemize}`, nên dấu hai chấm treo vào *"là phương án hệ thống
không dùng:"* và ba gạch đầu dòng đọc thành **ba thứ hệ thống không dùng** — ngược hẳn nội dung của
chính danh sách.

Có hai trường hợp không cần dấu hai chấm, và chúng là văn phong có sẵn. Thứ nhất, một danh sách mở
**ngay sau** một tiêu đề. Trong 23 danh sách của báo cáo, tám danh sách thuộc dạng này: năm ở chương
04, ngay sau `\paragraph{Luồng chính.}` và họ hàng; ba ở từ điển chương 3, ngay sau `\subsection` của
nhóm (nhóm *Tài liệu* thì vẫn mở bằng một câu dẫn). Thứ hai, danh mục ở chương tham khảo: một
`description` đứng sau một đoạn văn trọn vẹn, không sau một câu dẫn.

**Tiêu đề phải nói đúng cái thân bài nói.** `\paragraph{Ba mốc thời gian}` đứng trên một đoạn liệt kê
*ba tham số*, trong đó cái thứ nhất là một **thời lượng** chứ không phải một mốc. Và
`\paragraph{Hai điều kiện mà việc chấm dựa vào}` từng đứng trên hai gạch đầu dòng mà gạch thứ hai tự
phủ định tiêu đề.

**Chủ thể của câu phải đúng.** *"Tài liệu hiển thị trạng thái trên frontend"* — tài liệu không hiển
thị gì; màn hình hiển thị.

**Đừng phá một câu đúng để áp một thuật ngữ.** Chương 06 vốn viết *"Sáu tham số phát hành"* — đúng,
vì sáu tham số của *hành động phát hành* có tính cả lớp. Một lượt đổi thành *"Sáu tham số của một
Publication"* và biến nó thành sai, vì một dòng `publications` chỉ giữ năm.

**Một câu, một ý.** `04:79-81` là một câu ghép dài thiếu chỗ ngắt, và nó khó đọc không vì thuật
ngữ mà vì độ dài.

## 5. Con số là một khẳng định kiểm được

Mỗi con số trong báo cáo đếm một thứ có thật. Đã sai bốn lần, nên đáng một mục riêng:

| Câu | Thực tế |
|---|---|
| "Một `Publication` … **sáu** tham số thời gian" | năm cột, vì tham số thứ nhất của *sáu* là **lớp** — câu cũ đếm lớp hai lần |
| mục `Service` kể **bốn** service | có **năm**; `frontend` cũng là một service |
| `01:52` "**bốn** mục tiêu nghiệp vụ" trên ba `\item` | đã sửa thành "ba mục tiêu" |
| "các thuật ngữ tiếng Anh của chương này được định nghĩa ở mục…" | thiếu `VPC`, `subnet`, `credential`; từng phải nói "phần lớn", tới khi từ điển có đủ mục (16/10/2026) |

Luật rút ra: **sửa một item trong danh sách thì đếm lại câu dẫn**, và đừng để một câu hứa nhiều hơn
thứ nó trỏ tới. Comment trong `preamble.tex` và `report.tex` cũng là chữ, cũng phải đúng — xem danh
sách cuối tài liệu.

## 6. Văn bản và hình phải nói cùng một thứ

Hình là nguồn chữ thứ hai của báo cáo, và nó không sửa được từ `.tex`.

**Một chữ được *vẽ* trong hình thì không được đổi trong văn bản trước.** Đổi hình là một việc riêng,
làm trước. Đây là lý do năm chữ `đề nháp`, `nháp`, `duyệt`, `phát hành`, `điểm` giữ tiếng Việt ở
chương 01, 02, 04, 05:

| Hình | Chương nhúng | Chứa chữ nào trong năm chữ |
|---|---|---|
| `activity-overview` | 04 | đề nháp, nháp, duyệt, phát hành, điểm |
| `business-workflows` | 04 | đề nháp, nháp, điểm |
| `domain-context` | 01 | nháp, duyệt, phát hành, điểm |
| `use-case` | 05 | đề nháp, nháp, phát hành |
| `vong-hoc` | 02 | duyệt, điểm |
| `system-architecture` | 06 | **không chữ nào** |
| `teacher-chat-turn` | 07 | **không chữ nào** |
| `document-pipeline` | 07 | **không chữ nào** |

Chương 06 và 07 nhúng hình không chứa chữ nào trong năm chữ ấy, nên chỉ ở hai chương ấy mới Anh
hoá được. Chương 06 dùng giấy phép ấy; chương 07 không cần, và vẫn viết "duyệt" bằng tiếng Việt.
**Giấy phép chỉ gồm `draft` và `approve`**: "phát hành" và "điểm" giữ tiếng Việt ở **mọi**
chương, kể cả 06. Đừng đọc mục này rồi đi đổi `06:250` thành *"Sáu tham số
publish"* — đó đúng là câu đã bị phá một lần.

**Tên use case còn khó hơn**: mỗi tên sống ở bốn chỗ cùng lúc — bảng `tab:sau-use-case` (`05:14-19`),
tiêu đề `\subsection` (`05:38`, `:51`, …), các `\emph{...}` trong `\paragraph{Quan hệ.}` (`05:47`,
`:59`), **và** nhãn vẽ trong `figures/use-case.pdf`. Ba chỗ đầu grep được, chỗ thứ tư thì không.

## 7. Nơi đặt lời giải thích

**Giải thích ở chỗ người đọc đang đứng.** Đừng hứa rằng một chương khác sẽ nói — một chương bị bỏ đi
sẽ để lại bốn câu trỏ vào hư không, và đó đúng là việc đã phải dọn khi chương 6 cũ bị xoá.

**Một tham chiếu phải đáng công đi.** Chỉ `\ref` sang chỗ nói **nhiều hơn** chỗ đang đứng; `\ref` tới
một mục nói ít hơn là bắt người đọc đi không.

**Nhưng đừng đòi mọi `\label` phải có ai `\ref`.** Hiện 44 nhãn, 28 được trỏ tới, và phần lớn số
còn lại có việc riêng: `ch:` và `tab:`/`fig:` phục vụ mục lục, `\listoffigures` và `\listoftables`.
Thứ thật sự là gánh nặng là một `sec:` không ai trỏ — hiện có **7** cái; chương 7 không thêm cái
nào, vì hai nhãn mục không ai trỏ tới đã bị bỏ, và mục backend viết lại của nó trỏ tới
`sec:hang-doi`, vốn chưa ai trỏ. Và `fig:use-case` không được `\ref` từ văn xuôi
nào, tức chương 05 nhúng một hình mà không có câu nào dẫn vào nó, khác hẳn 01, 02, 04, 06, 07 đều
mở bằng `Hình~\ref{...}`.

**Bảng cũng cần một câu dẫn.** Một tiêu đề mục đứng ngay trên một bảng, không câu nào ở giữa, là
một mục không có thân bài: lần đầu viết chương 7, hai bảng luật đứng như vậy, và tiêu đề kế tiếp
rơi ngay dưới bảng.

## 8. Hình và bảng

**Một cái bẫy im lặng, và `preamble.tex:29-33` đã đo sẵn:** bên trong `\begin{landscape}`,
`\textwidth` vẫn 441pt, `\textheight` **bị gán thành** 441pt, và thứ rộng 702,8pt là `\linewidth`.
Nên bề rộng hình khổ ngang là `width=\linewidth`, trần chiều cao là `height=\textheight`. Dùng
`\textheight` làm bề rộng — cái tên nghe có vẻ đúng — cho ra hình **hẹp hơn đáng có 37%**, và build
vẫn xanh.

Khuôn hình ngang, 5/8 hình dùng:

```latex
\begin{landscape}
\begin{figure}[p]
  \centering
  \includegraphics[width=\linewidth,height=\textheight,keepaspectratio]{tên.pdf}
  \caption[Tên ngắn]{Tên dài}
  \label{fig:...}
\end{figure}
\end{landscape}
```

Ba ngoại lệ, mỗi cái một lý do:

- `business-workflows` (`04:133`): `[htbp]`, không landscape, vì khối hình chỉ cao 425pt và trang
  trước còn 585pt trống, nên nó chia trang được với văn xuôi.
- `document-pipeline` (chương 07): `[htbp]` với `height=0.5\textheight` — một hình rộng chia trang
  với văn xuôi.
- `teacher-chat-turn` (chương 07): `[p]` trên trang **dọc**, không landscape. `landscape` ép
  `\clearpage`, nên một hình ngang giữa một mục để lại nửa trang trống; mọi hình ngang hiện có đều
  đứng đầu chương. Sequence lại cao hơn rộng, nên trang dọc hợp với nó hơn.

**Chữ trong hình đọc được trên giấy**: chữ nhỏ nhất ≥ 7pt *sau khi* hình bị co vào khổ — đo trên
PDF, không đo trên `.drawio`. Chữ không chạm viền làn hay viền khung, và đường sống của sequence
nằm *dưới* hộp, không gạch qua chữ. Một chữ HTML dạng `<id>` trong ô phải viết `&lt;id&gt;`, vì
draw.io đọc nó như một thẻ và nuốt mất.

**Bảng lớn đặt `[htb]`, không `[htbp]`.** Với `p`, LaTeX có thể đẩy một bảng ra trang riêng, ngồi
giữa một khoảng trắng — chương 7 đã gặp hai lần. Một bảng mà trôi xuống dưới tiêu đề của mục kế thì
đặt `[H]`, như bảng cuối của chương 7. Nhưng `[H]` không co lại: bảng không vừa phần trang còn lại
thì tràn xuống lề, và log ghi `Overfull \vbox` chứ không báo lỗi.

**Bảng có nhóm mà cao quá 70% trang thì dùng `longtable`.** `[htb]` chỉ đặt một bảng ở đầu trang khi
nó không cao quá 70% trang (`\topfraction` mặc định); cao hơn thì nó chỉ đứng được đúng chỗ khai báo
(`h`), hụt chỗ là trôi tới tận cuối chương, và build vẫn sạch. Bảng ràng buộc và bảng lỗi của mục
backend chương 7 đã trôi như vậy, hai lần, khi ô bảng dài thêm sau review (16/10/2026). Nay chúng là
`longtable` theo khuôn `tab:bang-du-lieu` của chương 06: chạy ngay sau câu dẫn và ngắt qua trang.
Rút chữ để bảng thấp hơn 70% chỉ là chữa tạm: lượt sửa sau làm ô dài ra là bảng lại trôi.

**`\caption[ngắn]{dài}` không phải tuỳ chọn.** `report.tex` in `\listoffigures` và `\listoftables`;
bỏ phần ngoặc vuông thì Danh mục hình vẽ nhận cả phần giải thích dài phía sau.

**Bảng** dùng `booktabs`, không `\hline`: `\toprule` / `\midrule` / `\bottomrule`, và `@{}` ở hai đầu
`\begin{tabular}` để cắt đệm. Độ dày ba loại gạch giảm dần — `\heavyrulewidth` > `\lightrulewidth` >
`\cmidrulewidth`, đo trong PDF là 0,96 / 0,60 / 0,36 pt — nên:

- `\addlinespace` giữa các hàng của một `tabular`, và giữa **hai nhóm** của `longtable`;
- `\cmidrule{1-2}` giữa các hàng **cùng một nhóm** của `longtable`, vì cột *Giữ gì* tràn nhiều dòng
  và người đọc dễ lầm dòng này thuộc model dưới. Hàng cuối mỗi nhóm đã có `\addlinespace` nên không
  thêm gạch ở đó — vẽ hai lần cùng một đường;
- tiêu đề nhóm là `\multicolumn{2}{@{}l@{}}{\textbf{...}}`;
- `longtable` cần đủ `\endfirsthead` / `\endhead` / `\endfoot` / `\endlastfoot` và dòng *tiếp trang
  sau*, và `\label` của nó phải nằm trên dòng `\label{...}\\` ngay sau `\caption` — đặt sai chỗ là
  lỗi biên dịch;
- cột `L{...cm}` có bề rộng **đo bằng tay** cho vừa khổ; đổi nội dung một cột thì đo lại.

## 9. Trình bày nguồn

Văn phong đo được từ tám chương hiện có — theo nó, đừng đặt ra kiểu mới:

| Thứ | Luật | Số đo |
|---|---|---|
| Độ dài dòng văn xuôi | gói quanh **100**, không quá ~110 | p90 của mọi chương: 95–106 |
| Dòng của bảng | **một dòng một hàng**, không gói | hàng dài nhất 375 ký tự |
| Dòng tiếp của `\item` | thụt **8 cách** | 113 lần |
| Gạch ngang | luôn `---`, không bao giờ `--` | 51 so với 0 |
| Ngoặc kép | kiểu LaTeX ```...''`, không dùng `"` | 14 so với 0 |
| Số đếm trong văn xuôi | **viết chữ**: "năm service", "hai mươi mốt bảng" | "một" 408, "hai" 84, "ba" 64 |
| Chữ số | chỉ cho điểm (`0,5`), số giai đoạn, mã UC | — |
| `\paragraph{...}` | **kết bằng dấu chấm** | 54/55; thiếu ở `06:105` |
| Newline cuối tệp | phải có | `04` đang thiếu |
| Khoảng trắng cuối dòng | không có | 15 dòng đang vi phạm |

## 10. Cách gọi người

- **`Teacher` / `Student`** chỉ dùng khi đang nói về **actor** và trong sơ đồ.
- **"giáo viên" / "học sinh"** trong văn xuôi kể. Đây là mặc định: "học sinh" 98 lần so với
  `Student` 24, "giáo viên" 86 so với `Teacher` 20 (không tính tên trong `\texttt`).
- **"em"** dùng được khi câu đang nói về **một** học sinh cụ thể (11 lần).
- **"họ"** thì đừng — chỉ còn 1 lần (`04:86`) và nó lạc giọng so với phần còn lại.

## Những chỗ đã biết là còn sai

1. **Bốn nhãn trạng thái có ba bộ chữ khác nhau.** Hàng `assessments` của chương 06 viết "rỗng, có câu hỏi, đã duyệt, đã phát
   hành"; `docs/decisions/adr-01-vong-doi-de-kiem-tra.md` viết "trống → có câu hỏi → …" và có cả
   "đang soạn"; giao diện dùng "chưa có câu hỏi" và "đang soạn". Sửa báo cáo theo một bộ là làm nó
   lệch khỏi hai bộ kia, nên **đây là một quyết định nghiệp vụ, không phải một lượt sửa câu chữ** —
   ADR-01 là nơi chốt, và nó đã có một hậu ký ngày 13/10/2026.
2. **`04:116`** viết *"Hết hạn thì dừng… câu chưa xong nhận 0 điểm"* — đây là một luật **hệ thống
   chưa ép**, nên câu này đang hứa hơn thực tế.
3. **`figures/Logo_DHBK_HN.png`** không có trong `figures/sources.json` và cũng không xuất từ
   `.drawio`. Cổng hash chỉ canh hình `.drawio`, nên logo được miễn — nhưng chỗ miễn ấy không được
   ghi ở đâu.
4. **`04` thiếu newline cuối tệp**; 15 dòng ở `01`, `02`, `04`, `05` còn khoảng trắng cuối dòng; và
   chín dòng văn xuôi ở `01`, `02`, `04`, `05` dài quá 112 ký tự (dài nhất `04:79`, 140 ký tự).
5. **Chương 07 mang hai bộ chữ cho bảng luật và bảng lỗi**, trái §2. Mục Backend và Agent dùng
   *Các ràng buộc và cơ chế kiểm soát*, *Xử lý lỗi*, cột *Ràng buộc / Cơ chế thực thi / Kiểm
   chứng*; mục document vẫn dùng *Luật và chỗ canh luật*, *Khi hỏng*, cột *Luật / Nơi thi hành /
   Loại lưới*, tới khi lượt viết lại mục ấy xong.
6. **"Hàm" mang hai nghĩa trong chương 07**, trái §2: phần của một graph (theo mục *Graph* của từ
   điển), và *hàm nhận job*, chỗ worker gọi vào khi lấy một job xuống. Người dùng giữ *hàm nhận
   job* ngày 16/10/2026 và sẽ tự chọn chữ khác cho nó.
