# Business ADR Plan

## Goal

Lập `docs/decisions/` làm chỗ ở cho quyết định nghiệp vụ, viết sáu ADR nền tảng, và sửa `AGENTS.md`
để luật mới không mâu thuẫn với luật cũ.

## Bối cảnh

Repo có 20 decision record và **không cái nào là nghiệp vụ** — tất cả đều về thư viện, build backend,
cấu trúc thư mục, cách viết tài liệu. Toàn bộ luật nghiệp vụ của sản phẩm đang sống trong mô tả
component Figma và trong hội thoại thiết kế.

Hậu quả đo được: `business-workflows.md` viết *"Hệ thống phát hành đề cho Student"* trong khi thiết kế
nói chỉ giáo viên phát hành được; `project-overview.md` nói hai cổng teacher-in-the-loop trong khi
thiết kế có ba. Bốn khái niệm cốt lõi — `Class`, `Question Bank`, `Document`, `Scope` — xuất hiện khắp
tám artboard mà không có trong glossary.

## Files

- `docs/decisions/adr-00-template.md` và `adr-01` … `adr-06` — mới
- `AGENTS.md` — bảng ownership, mục `### Decision Records`, mục `Repo-Specific Traps`
- `README.md` — thêm dòng trỏ tới `docs/decisions/`
- `docs/overview/project-overview.md` — ba cổng thay vì hai; thêm bốn mục glossary
- `docs/overview/business-workflows.md`, `use-case-specification.md` — Teacher phát hành, không phải hệ thống

## Ordered Tasks

- [x] Kiểm kê quyết định nghiệp vụ từ hội thoại và từ hiện vật.
- [x] Tạo `docs/decisions/` với template và sáu ADR nền tảng.
- [x] Sửa `AGENTS.md` ba chỗ, giữ dưới trần 170 dòng.
- [x] Thêm dòng `docs/decisions/` vào bảng tài liệu của `README.md`.
- [x] Sửa mâu thuẫn trực tiếp trong `docs/overview/`.
- [x] Chạy `.\dev.ps1 check`; xác nhận link Markdown resolve; xác nhận LF.
- [x] Gọi một subagent review.
- [x] Sửa theo phát hiện, hoặc phản bác có lý do.

## Decision Records

### Decision: Business Decisions Get A Directory Of Their Own

options considered: giữ nguyên luật cũ và để quyết định nghiệp vụ nằm trong `## Decision Records` của
plan; tạo một tài liệu nghiệp vụ duy nhất chứa mọi luật; tạo `docs/decisions/` với một file một quyết
định.

selected option: `docs/decisions/`, một file một quyết định.

reason: một plan chạy xong thì chuyển sang `docs/plans/completed/`, mà chính `AGENTS.md` cấm sửa thư
mục đó — nên một luật nghiệp vụ thay đổi thì không có chỗ nào cập nhật được. Quyết định nghiệp vụ cũng
không thuộc về một thay đổi cụ thể; nó thuộc về sản phẩm và sống lâu hơn mọi plan. Một tài liệu gộp thì
không nói được luật nào thay luật nào, và không cho phép đánh dấu một quyết định đã bị thay thế.

### Decision: Name It `docs/decisions/`, Not `docs/adr/`

options considered: `docs/adr/` theo tên phổ biến trong ngành; `docs/decisions/`.

selected option: `docs/decisions/`.

reason: `AGENTS.md` đã có một dòng cấm tạo `docs/adr/`, và dòng đó được quyết trong decision record
`Single Architecture Document`. Dùng lại đúng tên bị cấm sẽ buộc phải lật một quyết định cũ mà lý do
của nó — quyết định **kỹ thuật** sống trong plan — vẫn còn đúng. Tên khác giữ được cả hai luật: kỹ
thuật ở trong plan, nghiệp vụ ở `docs/decisions/`.

### Decision: Every ADR Must Name Where The Rule Is Enforced

options considered: khuôn bốn mục theo kiểu ADR truyền thống (bối cảnh, quyết định, lý do, hệ quả);
thêm một mục thứ năm bắt buộc chỉ ra nơi luật đang được thi hành.

selected option: năm mục, mục thứ năm bắt buộc.

reason: 20 record hiện có đều thiếu mục này, và đó là lý do chúng không ngăn được việc thiết kế tự mâu
thuẫn với tài liệu. Bắt buộc chỉ ra chỗ thi hành cũng là một bộ lọc: luật nào không chỉ được ra chỗ nào
đang thi hành nó thì đó là ý tưởng chứ chưa phải quyết định, và chưa nên viết thành ADR.

### Decision: Fit Under The 170-Line Cap Instead Of Raising It

options considered: nâng `AGENTS_MD_MAX_LINES` trong `tools/check_contract.py` vì có luật mới thật;
cắt bớt chữ ở chỗ khác để luật mới vừa trần cũ.

selected option: cắt bớt, giữ trần 170.

reason: chính comment trong `check_contract.py` nói trần tồn tại để chặn trôi. Luật mới dài 8 dòng
nhưng phần bị cắt là chữ thừa — một câu lặp lại nguyên văn luật đã có ở mục `Documentation Rules`, và
một câu quấn dòng lỏng. Nâng trần ngay lần đầu gặp sức ép sẽ dạy rằng trần là gợi ý.

## Validation Checks

- `.\dev.ps1 check` xanh, đặc biệt `check_contract_files_stay_short`.
- `AGENTS.md` đúng 170 dòng.
- Mọi link nội bộ trong Markdown resolve.
- Mọi file mới và sửa giữ LF.
- Không file nào trong `docs/plans/completed/` bị đụng.

## Status

Xong. Vòng review chỉ ra hai điều được xử lý ở đợt sau (plan
`2026-09-06-business-adr-round-two-plan.md`): bốn luật nghiệp vụ đang chạy trong code mà chưa có ADR, và
việc tôi đã đưa quyết định giao diện vào ADR nghiệp vụ.
