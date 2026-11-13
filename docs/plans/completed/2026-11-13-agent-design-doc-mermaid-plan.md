# Docs thiết kế AGENT; docs Markdown vẽ bằng Mermaid

- **Mở:** 13/11/2026 · người dùng: repo thiếu docs thiết kế AGENT, nên người dùng và các dev khác
  chưa nắm được AGENT được dựng thế nào; dùng Mermaid ở mọi chỗ có thể thay cho lời văn khó theo dõi.

## Goal

Viết `docs/overview/agent-design.md`, bằng Mermaid, cho cả AGENT và đi sâu nhất vào graph `propose`.
Đổi luật sơ đồ: **báo cáo vẽ bằng drawio, docs Markdown vẽ bằng Mermaid.** Rà toàn bộ docs: link
`.drawio` và sơ đồ ASCII thành Mermaid, đoạn văn kể một luồng thành sơ đồ ở chỗ làm được.

## Scope

Người dùng chốt (13/11/2026):

1. *"report sử dụng drawio nhưng docs markdown chỉ sử dụng mermaid, rà soát lại toàn bộ docs"*.
2. Một file mới cho cả AGENT.

Không đụng:
- `docs/report/` (người dùng đang viết);
- `docs/plans/completed/`;
- nội dung các `.drawio`: chúng vẫn là hình của báo cáo;
- ADR, vì đó là lời ghi lại (các chỗ nhắc tên `.drawio` trong backtick giữ nguyên).

## Files

- `AGENTS.md`: bảng sở hữu, *Documentation Rules*, bảng Validation.
- `tools/check_contract.py`: check mới; `tools/tests/test_markdown_mermaid_check.py`.
- `docs/overview/agent-design.md` (mới).
- `docs/overview/architecture.md`, `project-overview.md`, `business-workflows.md`,
  `use-case-specification.md`, `data-model.md`, `teacher-surface.md`, `grading-design.md`;
  `docs/operation/deploy-lab.md`; những file khác mà pha 4 thấy cần.

## Ordered Tasks

### Pha 1 -- luật sơ đồ

- [x] `AGENTS.md`:
  - hàng `docs/diagrams/*.drawio` chỉ còn là hình báo cáo;
  - thêm hàng `docs/overview/agent-design.md`;
  - *Documentation Rules*: Markdown vẽ bằng Mermaid, không link `.drawio`; một luồng có hai bản thì
    đổi cùng nhau;
  - hàng Validation *A Markdown file* thêm điều kiện: khối Mermaid render được.
- [x] Giữ trần 185 dòng của `AGENTS.md`.
- [x] Quét `CLAUDE.md` và bảy `AGENTS.md` con.
- [x] `check_markdown_draws_in_mermaid` cùng hàm thuần `drawio_links`, và test cho hàm thuần.
- [x] Check, test; subagent review pha 1.

### Pha 2 -- `agent-design.md`

- [x] Các mục và sơ đồ:
  - AGENT đứng ở đâu;
  - năm task;
  - model tắt, model hỏng;
  - `llm` và fallback;
  - chọn skill;
  - một lượt `propose`;
  - prompt;
  - luật sau model;
  - hỏi lại một lần;
  - dàn ý → chia việc;
  - soạn một câu;
  - chuông;
  - lượt kèm học sinh;
  - đặt tên;
  - thêm skill, luật, task;
  - bản đồ module.
- [x] Render mọi khối Mermaid; kiểm link.
- [x] Subagent review pha 2, đối chiếu sơ đồ với code thật.

### Pha 3 -- link drawio và ASCII thành Mermaid

- [x] `architecture.md`:
  - 11 link;
  - ASCII *Đường giao tiếp*;
  - viết lại mục *Diagram nào đã có*.
- [x] `project-overview.md`: 4 link và ASCII.
- [x] `business-workflows.md`: 2 link và ASCII.
- [x] `use-case-specification.md`: 2 link.
- [x] `deploy-lab.md`: ASCII.
- [x] Theo review pha 3: vẽ thêm ba hình tách của lượt chat giáo viên (pha đề xuất, kiểm plan,
  pha thực thi), vì chúng có chi tiết docs chưa có; màu, nhãn, nét khớp drawio.
- [x] Check mới xanh, kèm phép thử phá; subagent review pha 3, so từng cặp drawio và Mermaid.

### Pha 4 -- rà lời văn

- [x] Rà `docs/overview`, `docs/operation`, `docs/testing`, `local-development.md`, `README.md`.
- [x] Thay đoạn kể luồng hay trạng thái bằng sơ đồ.
  - `data-model.md`: ERD 23 bảng (đọc từ `models.py`), vòng đời trạng thái đề; bỏ dòng backlog
    *ERD chưa vẽ*;
  - `grading-design.md`: luồng một ca qua bench;
  - `teacher-surface.md`: trạng thái khối `Thinking`, nấc của thẻ kết quả, các màn của rail;
  - `docs/testing/huong-dan.md`: thứ tự chạy các case;
  - `local-development.md`, `README.md`, kịch bản thử tay: giữ nguyên (lệnh và bước tuần tự, không
    phải luồng nhiều nhánh).
- [x] Check, test; subagent review pha 4; đóng plan.

## Validation Checks

| Check | Lệnh |
| --- | --- |
| Repo checks, gồm check mới | `.\dev.ps1 check` |
| Test, gồm test của check mới | `.\dev.ps1 test` |
| Mọi khối Mermaid render được | trích khối ra scratchpad, `npx -y @mermaid-js/mermaid-cli` |
| Link nội bộ của file đã sửa trỏ tới file có thật | script ở scratchpad |
| Check mới bắt được vi phạm | thêm tạm một link `.drawio` vào một doc, `check` đỏ, hoàn tác |

## Decision Records

### Decision: Markdown vẽ bằng Mermaid, báo cáo vẽ bằng drawio

options considered:
- giữ `.drawio` làm nguồn của mọi sơ đồ (luật cũ);
- Mermaid làm ngoại lệ riêng cho docs AGENT;
- tách hai vùng.

selected option: tách hai vùng.
- `.drawio` chỉ phục vụ báo cáo LaTeX.
- Docs Markdown vẽ bằng khối ` ```mermaid ` ngay trong file và không link `.drawio`.
- Một luồng có cả hai bản thì đổi một bản là đổi bản kia, trong cùng change set.

reason:
- Người đọc docs là dev mở repo trên GitHub hay trong IDE. Một link `.drawio` buộc họ cài drawio
  hoặc mở PDF của báo cáo, nên họ không thấy sơ đồ đúng lúc đang đọc lời văn. Đó là điều người dùng
  phàn nàn: chưa nắm được thiết kế.
- Mermaid render ngay tại chỗ, và sửa trong cùng diff với lời văn, nên luật *đổi sơ đồ là đổi lời*
  kiểm được bằng mắt trong một review.
- Báo cáo LaTeX cần PDF vector có bố cục tay, dàn trang chương 6–7; Mermaid không cho được thứ ấy.
- Ngoại lệ riêng cho docs AGENT thì để `infrastructure.md` (đã dùng Mermaid) lệch luật, và để dev
  đoán file nào theo luật nào.

**Cái giá:** một luồng có hình trong báo cáo thì có hai bản vẽ, có thể lệch nhau. Luật *đổi cùng
nhau* chỉ là luật review: không check nào so được nội dung Mermaid với drawio. Check mới chỉ chặn
được chiều rẻ, tức Markdown quay lại link `.drawio`.

### Decision: Không kiểm cú pháp Mermaid trong `.\dev.ps1 check`

options considered:
- check trong `check_contract.py`, gọi `mermaid-cli` qua `npx`;
- thêm `mermaid` vào devDependencies của FE và viết một script parse;
- kiểm bằng tay khi sửa docs (hàng Validation của `AGENTS.md`).

selected option: kiểm bằng tay.

reason: `mermaid-cli` kéo theo Chromium qua puppeteer, tức vài trăm MB cho mỗi máy chạy `check`,
và `check` hiện chạy không cần mạng. Một khối hỏng cú pháp thì hiện ngay thành chữ lỗi trên GitHub,
nên người sửa thấy được, khác với một ranh giới service vỡ trong im lặng.

### Decision: `AGENTS.md` giữ trần 185 dòng

options considered: nâng trần lên 186; thêm luật Mermaid thành dòng mới và nâng trần lên 187; viết
lại trong trần cũ.

selected option: viết lại trong trần cũ. Hàng sở hữu của `agent-design.md` tiêu dòng cuối còn trống;
luật Mermaid viết lại trong đúng số dòng của luật drawio cũ; điều kiện render gộp vào hàng *A
Markdown file*.

reason: trần có để giữ `AGENTS.md` là chỉ mục chứ không thành tài liệu (decision record ở
`check_contract.py`). Luật mới thay luật cũ, không cộng thêm, nên không có lý do nâng trần.

## Status

Xong 13/11/2026: pha 1–4 và bốn lượt review (đã sửa mọi điểm). Check, test xanh; 41 khối Mermaid
render không lỗi; link nội bộ đúng. Pha 1 và pha 2 commit chung: hàng sở hữu của
`agent-design.md` trong `AGENTS.md` cần file ấy có mặt.

Còn ngỏ, cần người dùng quyết (hình báo cáo nằm ở vùng người dùng đang viết):
- `docs/diagrams/propose-three-layers.drawio` lệch code từ ADR-38: thiếu bước `split_outline`;
  *"Jev không trả lời thì cả ba"* nay là cả bốn tệp; *"bỏ đề xuất của mô hình"* trong khi
  `approved_plan` giữ lời mở model viết; thiếu `telling_skills` ở lượt kể lại.
- `teacher-chat-turn-plan-check.drawio` vẽ trước ADR-38: cửa đầu chưa có điều kiện *mang cách chia đúng
  số câu*. Bản Mermaid ở `architecture.md` ghi chú điều ấy dưới hình.
- Ứng viên sơ đồ review pha 4 nêu mà chưa vẽ, vì cần đọc kỹ code từng cạnh: vòng đời
  `documents.state`, `draft_items.status`, bài làm và chặng của một đề ở một lớp; luồng phát hành,
  thu hồi từng lớp, hoàn tác (`teacher-surface.md`, mục biểu mẫu phát hành).
