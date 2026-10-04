# Báo cáo đồ án bằng LaTeX — `docs/report`

## Context

Repo có 2.688 dòng docs tiếng Việt và 25 ADR, nhưng không tài liệu nào đọc được liền mạch từ
đầu đến cuối bởi người ngoài dự án. Mỗi file `docs/overview/*` sở hữu đúng một chủ đề và chỉ
nói về chủ đề đó; `docs/decisions/` là 25 bản ghi rời; `raw-idea/` thì bị cấm viện dẫn như sự
thật hiện tại. Người cần một bản trình bày tổng thể hiện không có chỗ nào để đọc.

Việc này viết một **báo cáo đồ án môn học** bằng LaTeX, khoảng 25–35 trang, bảy chương, phủ ý
tưởng sản phẩm, các luồng nghiệp vụ, use case, các quyết định nghiệp vụ đáng chú ý, và kiến
trúc cùng mô hình dữ liệu.

Hai ràng buộc do người dùng chốt, và chúng định hình gần hết plan:

- **Không dùng mermaid.** Mục Documentation Rules của `AGENTS.md` quy định `.drawio` là source
  of truth cho mọi diagram, và Markdown *"never becomes a second diagram source"*. Mermaid sẽ
  tạo đúng cái nguồn thứ hai bị cấm đó. Report dùng hình xuất từ năm `.drawio` đang có.
- **Chữ tự đứng một mình.** Người đọc chỉ cần file PDF, không cần mở repo.

Ràng buộc thứ hai mở ra một rủi ro thật và plan này **không** giả vờ giải được nó: report trở
thành chỗ thứ sáu nói cùng những luật đã nằm ở `project-overview.md`,
`business-workflows.md`, `use-case-specification.md`, `architecture.md`, `data-model.md` và 25
ADR — rồi lệch khi một ADR đổi. Phần lệch **đo được** là phần hình, và plan này đóng đúng phần
đó bằng một check. Phần lệch chữ vẫn mở; decision record cuối nói rõ cách đóng nếu sau này muốn.

## Scope

**Làm:** bảy chương chữ; năm hình xuất từ `docs/diagrams/`; khung LaTeX và `.\dev.ps1 report`;
một check tầm repo chống lệch hình; sửa `AGENTS.md` cho hai thứ mới ấy.

**Không làm:** vẽ ERD (sẽ là diagram thứ sáu, cần quyết định riêng — `architecture.md` có mục
*"Vì sao chưa có các diagram khác"* giải thích vì sao chưa có); dịch report sang tiếng Anh;
chương hiện trạng và hướng phát triển; đối chiếu tự động giữa chữ report và chữ docs.

## Toolchain — đã đo

| Thứ | Kết quả |
| --- | --- |
| `xelatex` + `polyglossia` tiếng Việt + Times New Roman | biên dịch sạch, exit 0, ra PDF |
| TeX Live 2025 | full: `tcolorbox`, `booktabs`, `hyperref`, `minted`, `svg`, `pdflscape` |
| `inkscape`, `rsvg-convert`, `magick` | không có cả ba, nên `\includesvg` dùng không được |
| `cairosvg` | có, trong Anaconda |
| drawio desktop hoặc CLI | không có |
| `ipydrawio-export` trên conda-forge | có, 1.3.0; deps `ipydrawio` + `nodejs >=12` + `pypdf` |
| `.drawio` trong repo | XML phẳng không nén, nên băm và diff được |

Hệ quả: hình vào LaTeX phải là **PDF** — `\includegraphics` ăn PDF nguyên bản. Bản SVG đã xuất
rồi bỏ: năm file nặng 3,2MB vì drawio nhúng font, chúng không phải đường vào LaTeX, và sơ đồ thì
xem trên GitHub được ngay từ chính file `.drawio`. Mỗi lần xuất lại sẽ là 3,2MB diff đổi lấy
không gì cả.

## Năm hình, không phải sáu

| `.drawio` | Tên trang | Chương |
| --- | --- | --- |
| `domain-context.drawio` | Domain Context | 1 |
| `activity-overview.drawio` | Activity Overview | 4 |
| `business-workflows.drawio` | Business Workflows | 4 |
| `use-case.drawio` | Use Case Diagram | 5 |
| `system-architecture.drawio` | System Architecture | 7 |

Phần dữ liệu của chương 7 mô tả 13 bảng bằng bảng `booktabs`, không bằng hình.

## Bố cục report

| Chương | Nội dung | Hình |
| --- | --- | --- |
| Bìa, mục lục, danh mục hình / bảng / thuật ngữ | | |
| 1. Đặt vấn đề | bối cảnh, vấn đề, mục tiêu, phạm vi và ngoài phạm vi giai đoạn đầu | Domain Context |
| 2. Ý tưởng sản phẩm | hai pha làm–chữa, pha 2 bắt buộc, nhãn lỗi trên distractor, ba cổng, thang 1 / 0,5 / 0 | — |
| 3. Actor và khái niệm nghiệp vụ | Teacher, Student, vì sao AI không phải actor; glossary | — |
| 4. Các luồng nghiệp vụ | năm workflow: mục tiêu, luồng chính, điểm kiểm soát, ngoại lệ | Activity Overview, Business Workflows |
| 5. Use case | bảng UC-01→UC-07 và đặc tả rút gọn | Use Case Diagram |
| 6. Quyết định nghiệp vụ đáng chú ý | sáu ADR có đánh đổi thật, kèm vì sao và hy sinh gì | — |
| 7. Kiến trúc và mô hình dữ liệu | ba service, ranh giới quyền quyết định và dữ liệu, 13 bảng theo năm nhóm | System Architecture |

Hai chương chịu lực:

**Chương 2 phải trả lời "khác gì một chatbot ra đề".** Câu trả lời có thật trong repo: pha 2 là
bắt buộc, học sinh không rời bài sau khi biết điểm mà phải chữa từng câu sai qua tối đa ba vòng
với câu biến thể (ADR-14, ADR-17); mỗi distractor mang một nhãn lỗi nên "sai" trả về được
nguyên nhân chứ không phải một dấu X (ADR-18); trợ lý phát bằng chứng còn giáo viên quyết, nên
không có gì tự đến tay học sinh (ADR-05, ADR-06).

**Chương 6 phân biệt một đồ án đã suy nghĩ với một đồ án kể tính năng.** Sáu ADR được chọn:
ADR-01 (duyệt là chốt nội dung), ADR-03 (giờ đóng là hạn **vào**, không phải hạn **nộp**),
ADR-05 (ba cổng), ADR-15 (hạn pha 2 **có** cắt lượt đang làm — nghịch với ADR-03 một cách có
chủ ý), ADR-18, ADR-22 (id của giáo viên khác đọc y như id không tồn tại). Giải thích được chỗ
nghịch giữa ADR-03 và ADR-15 là chỗ chứng minh đã hiểu bài toán.

## Files

- Tạo `docs/report/report.tex`, `docs/report/preamble.tex`
- Tạo `docs/report/chapters/01-dat-van-de.tex` … `07-kien-truc-va-du-lieu.tex`
- Tạo `docs/report/figures/*.pdf` (năm file, tên ASCII) và `figures/sources.json`
- Sửa `tools/check_contract.py` — check mới, thêm vào `CHECKS`, nâng `AGENTS_MD_MAX_LINES`
- Sửa `dev.ps1` — `ValidateSet` ở dòng 25 và một nhánh `report`
- Sửa `AGENTS.md` — một dòng ownership, một dòng invariant, sửa dòng Validation của `.drawio`
- Sửa `.gitignore` — file phụ của LaTeX

Một chương một file để diff đọc được. Tên file hình **phải ASCII**: `graphicx` của xelatex hỏng
với dấu tiếng Việt trong đường dẫn.

## Chống lệch hình — check thứ mười

Xuất hình bằng tay thì sẽ có lúc quên xuất lại, và report in hình cũ mà không gì đỏ. Theo châm
ngôn của repo, một luật không có chỗ thi hành là một ý định.

`tools/check_contract.py` thêm `check_every_figure_matches_the_diagram_it_came_from()`:

- Đọc `docs/report/figures/sources.json`, dạng
  `{"domain-context.pdf": {"source": "docs/diagrams/domain-context.drawio", "sha256": "..."}}`
- Đỏ khi: hash của `.drawio` khác hash trong manifest; một `.drawio` trong `docs/diagrams/`
  không có entry nào; `source` trỏ tới file không tồn tại; file hình trong manifest đã mất;
  `sources.json` thiếu hoặc không parse được JSON.
- Mọi thông báo thất bại nêu tên file, và không ném traceback.

Tên hàm **không** chứa chữ `report`: file này đã có `check_the_report_is_a_job_of_its_own`,
trong đó "report" là báo cáo của agent ở ADR-25. Hai luật khác hẳn nhau không được cùng tên.

## Ordered Tasks

- [x] **Task 0 — plan này.** Viết plan và bốn decision record kỹ thuật. Commit.

- [x] **Task 1 — xuất năm hình.** Spike có điều kiện bỏ.
  - [x] `conda create -n drawio-export -c conda-forge ipydrawio-export` — env riêng, không
        chạm Anaconda base, không chạm `.venv` của project.
  - [x] Provision rồi xuất **một** hình thật trước: `domain-context.drawio` sang PDF.
  - [x] Điều kiện bỏ: nếu sau một lần thử giới hạn mà không ra được PDF mở được, dừng, báo
        người dùng, rơi về drawio desktop (có `--export --format pdf --crop`). Không đào tiếp.
        Check ở Task 3 không quan tâm ai xuất, nên đổi công cụ không phá gì.
  - [x] Xuất cả năm ra PDF; `--crop` để lề trắng của drawio không ăn vào bố cục trang.
  - [x] Mở từng PDF xác nhận có nội dung và chữ tiếng Việt trong hình không mất dấu.
  - [x] Commit năm file.

- [x] **Task 2 — khung LaTeX và task build.**
  - [x] `preamble.tex`: `fontspec`, `polyglossia` với `\setmainlanguage{vietnamese}`,
        `\setmainfont{Times New Roman}`, `graphicx`, `booktabs`, `hyperref`, `pdflscape`.
        Comment đầu file ghi rõ font hệ thống mà bản build cần.
  - [x] `report.tex`: `\documentclass[12pt,a4paper]{report}`, bìa, `\tableofcontents`,
        `\listoffigures`, `\listoftables`, rồi `\input` bảy chương rỗng.
  - [x] `dev.ps1`: thêm `report` vào `ValidateSet` dòng 25 và một nhánh dùng `Invoke-Step`
        theo đúng nếp các task sẵn có.
  - [x] `.\dev.ps1 report` ra `report.pdf`, log không lỗi font hay ngôn ngữ.
  - [x] Nhúng thử một hình khổ ngang (`pageWidth=1800`) với `width=\linewidth`, mở PDF xác
        nhận không tràn lề và không bị cắt; nếu tràn thì dùng `pdflscape` cho trang đó.
  - [x] `.gitignore` cho file phụ của LaTeX. **Không** ignore `report.pdf`: nó là sản phẩm.
  - [x] Commit.

- [x] **Task 3 — check thứ mười và sửa hợp đồng.**
  - [x] Sinh `figures/sources.json` từ năm `.drawio` thật.
  - [x] Viết check, phủ đủ năm trường hợp đỏ ở mục trên, thêm vào tuple `CHECKS`.
  - [x] `.\dev.ps1 check` báo `All 10 repo checks passed.`
  - [x] Đo luật: thêm một dấu cách vào `docs/diagrams/use-case.drawio`, chạy lại, xác nhận đỏ
        và nêu đúng tên file đó, rồi hoàn nguyên.
  - [x] Đo luật lần hai: đổi tên tạm một file trong `figures/`, xác nhận đỏ, hoàn nguyên.
  - [x] `AGENTS.md`: một dòng ownership cho `docs/report/`; một dòng invariant cho check mới;
        **sửa** dòng Validation sẵn có của `.drawio` để nó cũng đòi xuất lại hình và nêu tên
        `.\dev.ps1 report` — sửa dòng cũ thì không tốn dòng mới.
  - [x] Nâng `AGENTS_MD_MAX_LINES` 179 lên 181, kèm comment theo giọng các comment cap sẵn có:
        hai dòng ấy mua gì, và decision record nằm ở plan nào.
  - [x] `.\dev.ps1 check` lại, 10/10. Commit.

- [ ] **Task 4 — chương 1 và 2.** Nguồn: `project-overview.md`; ADR-05, 06, 14, 15, 16, 17, 18.
      Nhúng `domain-context.pdf` với caption và `\label`. Build, đọc PDF, commit.

- [ ] **Task 5 — chương 3 và 4.** Nguồn: `project-overview.md` mục khái niệm, và
      `business-workflows.md`. Nhúng `activity-overview.pdf`, `business-workflows.pdf`. Nói rõ
      vì sao `System/AI` là lane xử lý chứ không phải actor nghiệp vụ. Build, đọc, commit.

- [ ] **Task 6 — chương 5 và 6.** Nguồn: `use-case-specification.md` (UC-01 tới UC-07) và sáu
      ADR đã chọn. Nhúng `use-case.pdf`. Mỗi ADR viết bối cảnh, quyết định, hy sinh gì.
      Build, đọc, commit.

- [ ] **Task 7 — chương 7.** Nguồn: `architecture.md` và `data-model.md`. Nhúng
      `system-architecture.pdf`. 13 bảng theo năm nhóm dạng `booktabs`. Không vẽ ERD.
      Build, đọc, commit.

- [ ] **Task 8 — hoàn thiện.** Danh mục thuật ngữ; tài liệu tham khảo có link repo
      `https://github.com/biabeogo147/AI-Assessment-and-Feedback-Assistant`; đọc soát cả PDF
      (mọi `\ref` giải được, không `??` nào sót, caption đánh số liền mạch); đếm trang và xác
      nhận trong 25–35, nếu mỏng thì nói rõ chương nào chứ không nhồi chữ; cổng đầy đủ; chuyển
      plan sang `completed/`.

## Đã đo: hình nào khổ dọc, hình nào khổ ngang

Kích thước thật của khối chữ: `textwidth` 441pt (15,5cm), `textheight` 702,8pt (24,7cm). Kích
thước thật của năm hình, đọc từ `MediaBox` của chính file xuất ra:

| Hình | `MediaBox` | Tỉ lệ | Đặt |
| --- | --- | --- | --- |
| `domain-context` | 1053 × 376 | 2,80 | khổ ngang |
| `system-architecture` | 923 × 598 | 1,54 | khổ ngang |
| `use-case` | 1240 × 585 | 2,12 | khổ ngang |
| `activity-overview` | 1182 × 909 | 1,30 | khổ ngang |
| `business-workflows` | 981 × 793 | 1,24 | khổ ngang |

Cả năm hình **đều vừa** khổ dọc, không hình nào tràn lề. Vấn đề thật không phải tràn lề mà là
**đọc được hay không**: ở khổ dọc, tỉ lệ co là 0,37–0,48 và khối chú thích của mọi sơ đồ bé tới
mức không đọc nổi trên giấy. Đã kiểm bằng mắt, bằng cách rasterize trang in ra. Người dùng nhìn
trang in rồi chốt: **cả năm hình đặt trang ngang**, chịu việc người đọc phải xoay giấy, đổi lấy
tỉ lệ co 0,67–0,74.

Một cái bẫy, đã đo bằng `\typeout` chứ không suy ra — và lần đầu tôi suy ra thì **sai ngược**.
Bên trong `\begin{landscape}` của `pdflscape`:

| | khổ dọc | trong `landscape` |
| --- | --- | --- |
| `\textwidth` | 441,0pt | 441,0pt (không đổi) |
| `\textheight` | 702,8pt | 441,0pt (bị gán thành bề rộng cũ) |
| `\linewidth` | 441,0pt | **702,8pt** |

Nên bề rộng của hình khổ ngang là `\linewidth`, và trần chiều cao là `\textheight`:

```latex
\begin{landscape}
\begin{figure}[p]
  \centering
  \includegraphics[width=\linewidth,height=\textheight,keepaspectratio]{activity-overview.pdf}
  \caption{...}
\end{figure}
\end{landscape}
```

Lấy `\textheight` làm bề rộng — cái tên nghe có vẻ đúng, và đó là thứ tôi viết lần đầu — cho
ra hình hẹp hơn đáng có 37%, mà vẫn build sạch không một cảnh báo. Chỉ nhìn trang in mới thấy.

## Review sau mỗi đợt chương

Mỗi task viết chương — Task 4, 5, 6, 7 — kết thúc bằng **một subagent review**, trước khi
commit. Người dùng đã cho phép trước ở đây, nên không phải xin lại từng lần; nhưng chỉ một
subagent mỗi đợt, không hơn.

Việc cần giao cho reviewer, và đây là phần đáng giá: **đọc chương vừa viết, đối chiếu với file
docs sở hữu chủ đề đó, và nêu từng chỗ chữ report nói khác docs**. Đó chính là loại lệch mà
`check_contract.py` không đo được — decision record *"report tự đứng một mình"* đã nói rõ vì
sao: một check so chữ sẽ đỏ vì mọi lần sửa câu văn, nên nó sẽ bị tắt. Con mắt của một
reviewer là lưới duy nhất ở đây, nên đừng để nó đi soát chính tả.

Nguồn đối chiếu cho từng đợt: Task 4 soi `project-overview.md` và bảy ADR được nhắc; Task 5
soi `business-workflows.md`; Task 6 soi `use-case-specification.md` và sáu ADR của chương 6;
Task 7 soi `architecture.md` và `data-model.md`.

Phát hiện của reviewer được **đo lại** trước khi sửa, không nhận mặt. Một reviewer đọc docs mà
không chạy code vẫn có thể nói sai, và ngược lại nó đã từng bắt được lỗi nặng mà tôi tự gây.

## Những chỗ dễ cắn, và task nào đo chúng

1. Thêm một `.drawio` mới mà không xuất hình — check phải đỏ vì **thiếu entry**, không chỉ vì
   hash lệch. Task 3.
2. `sources.json` hỏng hoặc thiếu — check phải trả thông báo người đọc hiểu, không ném
   `JSONDecodeError`. Task 3.
3. Hình khổ ngang tràn lề — `pageWidth=1800` trên A4 dọc bị cắt nếu `\includegraphics` trần.
   Đo ở Task 2 bằng một hình thật, **trước** khi viết chữ.
4. Dấu tiếng Việt trong tên file hình làm `graphicx` hỏng — giữ tên ASCII, chốt ở Task 1.
5. `report.pdf` không build lại được trên máy không có Times New Roman — ghi font yêu cầu vào
   comment đầu `preamble.tex`. Task 2.

## Validation Checks

| Việc | Lệnh | Kỳ vọng |
| --- | --- | --- |
| Repo contracts | `.\dev.ps1 check` | `All 10 repo checks passed.` |
| Check thứ mười đỏ được thật | sửa một `.drawio` một dấu cách rồi `check` | đỏ, nêu đúng tên file |
| Report build | `.\dev.ps1 report` | ra `docs/report/report.pdf`, log không lỗi font hay ngôn ngữ |
| Không hồi quy | `.\dev.ps1 test`, `.\dev.ps1 typecheck` | như trước |

## Decision Records

### Decision: XeLaTeX thay vì pdfLaTeX

options considered: pdflatex với `vntex`; xelatex với `polyglossia` và font hệ thống; lualatex
với `babel`.

selected option: xelatex với `polyglossia`, `\setmainlanguage{vietnamese}` và
`\setmainfont{Times New Roman}`.

reason: tiếng Việt cần Unicode đầy đủ và một font có đủ dấu tổ hợp. Đã đo: một file thử chứa
`ữỡẳệụỹĐ` biên dịch exit 0 và PDF ra đúng chữ. pdflatex đi đường encoding 8-bit, cần gói riêng
cho tiếng Việt và vỡ ngay khi gặp một ký tự ngoài bảng mã; lualatex làm được nhưng chậm hơn và
không mua thêm gì cho một tài liệu không có đồ hoạ sinh bằng Lua. Chọn thứ đã chứng minh chạy
được trên chính máy này, không phải thứ đọc thấy là chạy được.

### Decision: hình là PDF, và một manifest băm `.drawio`

options considered: `\includesvg` từ SVG; nhúng PNG; nhúng PDF; vẽ lại bằng mermaid hoặc TikZ.

selected option: nhúng PDF xuất từ `.drawio`, kèm `figures/sources.json` ghi sha256 của file
`.drawio` tại thời điểm xuất, và một check tầm repo đối chiếu lại.

reason: `\includesvg` gọi Inkscape, mà máy này không có Inkscape, rsvg-convert hay magick — đã
đo cả ba. PNG thì mờ khi phóng. Vẽ lại bằng mermaid tạo đúng cái nguồn diagram thứ hai mà
`AGENTS.md` cấm. Còn manifest tồn tại vì bước xuất là bằng tay: không có nó thì "nhớ xuất lại
hình" là kỷ luật cá nhân, và kỷ luật cá nhân không phải một chỗ thi hành. Có nó thì sửa một
`.drawio` mà quên xuất là một lần `check` đỏ, nêu tên file.

### Decision: xuất hình bằng drawio desktop, sau khi đường conda chết

options considered: `ipydrawio-export` trong một env conda riêng; `ipydrawio-export` trong
Anaconda base hoặc trong `.venv` của project; drawio desktop; xuất tay qua app.diagrams.net.

selected option: **drawio desktop** (`JGraph.Draw` 31.7.0, cài qua winget), gọi bằng
`--export --format pdf --crop`.

reason: lựa chọn đầu là env conda riêng, và nó **đã được thử rồi chết**. Ba lần, mỗi lần một
chỗ không tương thích khác của một package 2023: `PdfMerger` đã bị bỏ khỏi pypdf 5; `JLPM`
phân giải ra `jlpm` của Anaconda base, vốn là yarn berry, nên nuốt phải cờ của yarn 1; và bước
tải Chromium vỡ vì `yargs` cũ không chạy nổi dưới Node hiện tại. Phép thử dứt điểm cho ra
`No PDF text was created`. Hai lần đầu sửa được bằng một dòng, lần thứ ba thì phải vá
`node_modules` của chính package — đó là lúc điều kiện bỏ nổ.

Bài học đáng giữ: **có mặt trên conda-forge không có nghĩa là chạy được.** Một package noarch
từ 2023 pin `nodejs >=12` thì mọi thứ quanh nó đã đi tiếp ba năm.

Env riêng vẫn là quyết định đúng dù nó không về đích: ba lần hỏng ấy không chạm tới Anaconda
base lẫn `.venv` của project, và xoá env là sạch. Drawio desktop thì đổi lại là một phần mềm
246MB thật trên máy — đắt hơn một package Python, nhưng nó xuất cả năm hình ngay lần đầu,
không cấu hình gì. Và công cụ xuất không nằm trong đường build của report: check ở Task 3 đối
chiếu hash chứ không gọi công cụ, nên nếu sau này có đường xuất tốt hơn thì đổi không phá gì.

### Decision: report tự đứng một mình, và phần lệch chữ vẫn để mở

options considered: report ngắn trỏ về docs; report viết lại nhưng mỗi mục dẫn file sở hữu;
report tự đứng một mình.

selected option: tự đứng một mình.

reason: người dùng chốt — người đọc chỉ cần PDF. Đánh đổi được nói ra chứ không giấu: report
thành chỗ thứ sáu nói cùng những luật đã nằm ở năm file docs và 25 ADR, và nó sẽ lệch khi một
ADR đổi. Phần hình đóng được bằng hash nên plan này đóng. Phần chữ thì không có cách đo rẻ nào:
một check so chữ report với chữ docs sẽ đỏ vì mọi lần sửa câu văn, tức nó sẽ bị tắt. Thứ rẻ và
đáng làm, nếu sau này muốn, là đối chiếu **mã ADR**: mỗi `ADR-NN` mà report nhắc tên phải tồn
tại trong `docs/decisions/`. Nó không bắt được nội dung lệch, chỉ bắt được một ADR bị xoá hoặc
đổi số — và đó là một quyết định riêng, không nằm trong plan này.

## Completion Criteria

`docs/report/report.pdf` build được bằng một lệnh, dài 25–35 trang, bảy chương có nội dung thật,
năm hình nhúng đúng chỗ và không tràn lề, mọi tham chiếu chéo giải được. `.\dev.ps1 check` 10/10,
và check thứ mười đã được chứng minh đỏ được bằng hai phép mutation.

## Status

Task 0, 1, 2, 3 xong, chưa commit. Task 4 chưa bắt đầu.
