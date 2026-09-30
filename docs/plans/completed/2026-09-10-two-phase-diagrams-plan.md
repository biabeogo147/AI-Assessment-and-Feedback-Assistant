# Diagram và tài liệu overview — đưa về đúng mô hình hai pha

## Goal

Bốn diagram và ba tài liệu `docs/overview/` nhất quán với ADR-14 … ADR-19; mỗi diagram đọc được trong
một ảnh chụp, không node nào chồng nhau và không cạnh nào giao nhau.

## Bối cảnh

Đợt [ghi luật](2026-09-10-two-phase-assessment-decisions-plan.md) cố ý để lại `docs/overview/` và
`docs/diagrams/`, vì trộn chúng vào cùng một pass là mời lỗi trích dẫn quay lại. Đợt này trả món nợ đó.

Đếm thật thì hỏng ở **bốn** diagram, không phải ba, và hơn hai mươi chỗ trong ba tài liệu overview.

Hai lỗi phát hiện lúc đo hình học, **không phải** do mô hình hai pha gây ra:

- `business-workflows.drawio` đặt `t-publish` — *Teacher phát hành assessment* — giữa **lane
  System/AI**. Đó là điều [ADR-02](../../decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md) mục *Hệ quả*
  cấm thẳng, và điều khoản ấy chưa từng được thi hành. Thêm ba node mang `parent` trỏ sai lane, chỉ
  được đẩy toạ độ âm cho *trông như* đúng chỗ.
- `activity-overview.drawio` có hai cạnh ngược chiều nhau giữa *chấm bài* và *nhận feedback*, không
  nhãn, không điều kiện — một vòng lặp vô nghĩa.

## Scope

**Trong:** bốn `.drawio`, ba `.md` trong `docs/overview/`, chia thành ba cặp vì `AGENTS.md` buộc
diagram và prose mô tả nó đi cùng change set.

**Ngoài:** Figma, code, contract, test, ADR nội dung mới, ba màn hình học sinh.

## Files

| File | Việc | Cặp |
| --- | --- | --- |
| `docs/diagrams/use-case.drawio` | dựng lại bố cục; `<<extend>>` → `<<include>>` cho pha 2; gỡ extend giải thích khỏi `uc-submit`; đổi tên *Xem feedback*; thêm `uc-report-unclear` | 1 |
| `docs/overview/use-case-specification.md` | actor Student; UC-02 sáu tham số; UC-03; UC-04 viết lại; UC-06 viết lại; **UC-07 mới**; nguyên tắc chung | 1 |
| `docs/diagrams/activity-overview.drawio` | dựng lại thành **hai băng ngang**; bỏ vòng lặp vô nghĩa; kênh báo cáo vẽ nét đứt tách rời | 2 |
| `docs/diagrams/business-workflows.drawio` | dựng lại với **mọi node `parent="1"`, toạ độ tuyệt đối**; `t-publish` về lane Teacher | 2 |
| `docs/overview/business-workflows.md` | sơ đồ tổng quan; WF2 và WF5 viết lại; WF3 *dự đoán* → tra cứu; distractor *nên* → *phải* | 2 |
| `docs/diagrams/domain-context.drawio` | luồng vào/ra của cả hai actor; dựng lại hình học cho nhãn dài | 3 |
| `docs/overview/project-overview.md` | vòng khép kín; mục tiêu 4; hành vi Student; glossary thêm năm khái niệm | 3 |
| `docs/decisions/adr-02, 14, 17, 18, 19`, `README.md` | cập nhật mục *Nơi luật này đang được thi hành* | — |

## Luật bố cục — áp cho cả bốn diagram

1. Toạ độ nằm trong hệ của chủ thật. Không node nào `parent` vào một lane nó không thuộc về.
2. Không toạ độ âm; mọi thứ trong `pageWidth × pageHeight` đã khai.
3. Bám lưới 10; cùng cột thì cùng `width`.
4. Cạnh orthogonal, waypoint tường minh khi cần. Không cạnh nào đi xuyên một node.
5. Không cặp node nào chồng nhau, trừ container chứa con thật.
6. **0 giao cắt cạnh** ở cả bốn diagram.
7. Legend ở góc trống, không chồng nội dung.
8. Khổ ngang; không diagram nào cao hơn rộng, trừ `activity-overview` vốn có hai băng.
9. Nhãn điều kiện nằm trên chính cạnh đó, không phải một text node thả gần.

## Ordered Tasks

- [x] Viết `diagram_check.py` ở scratchpad; chạy trước khi sửa để có số nền.
- [x] Viết `diagram_preview.py` ở scratchpad (SVG → PDF → PNG).
- [x] Cặp 1 — `use-case.drawio` + `use-case-specification.md`.
- [x] Cặp 2 — `activity-overview.drawio`, `business-workflows.drawio`, `business-workflows.md`.
- [x] Cặp 3 — `domain-context.drawio` + `project-overview.md`.
- [x] Cập nhật mục *Nơi thi hành* của ADR-02, 14, 17, 18, 19 và `decisions/README.md`.
- [x] Chạy lại `diagram_check.py`; dựng ảnh xem trước cho cả bốn; gửi ảnh cho người dùng.
- [x] Gọi 1 subagent review: đúng nghiệp vụ, và dễ nhìn từ góc người dùng.
- [x] Sửa theo phát hiện, hoặc phản bác có lý do.

## Validation Checks

- Bốn `.drawio` parse được như XML.
- `diagram_check.py`: 0 node ngoài trang, 0 node chồng nhau, 0 cạnh xuyên node, **0 giao cắt cạnh**,
  0 nhãn trôi tự do, 0 node lệch lưới — cho cả bốn file.
- Không node nào còn `parent` sai lane; `t-publish` nằm trong lane Teacher.
- Không file nào trong `docs/overview/` hay `docs/diagrams/` còn nói phát hành kèm *ba mốc thời gian*,
  còn nói vòng luyện tập dừng theo *mastery*, hay còn mô tả việc *dự đoán* lỗi sai.
- Mỗi `.drawio` được ít nhất một Markdown trỏ tới, và ngược lại.
- `.\dev.ps1 check` xanh; link Markdown resolve; LF; `AGENTS.md` vẫn 170 dòng.

## Decision Records

### Decision: Script đo và script dựng ảnh ở scratchpad, không vào repo

options considered: thêm `tools/check_diagrams.py` và nối vào `.\dev.ps1 check`; để cả hai ở scratchpad.

selected option: scratchpad.

reason: script dựng ảnh là bản **xấp xỉ** draw.io — đưa vào repo là hứa một thứ nó không giữ được, và
người sau sẽ tin ảnh nó vẽ hơn file thật. Script đo thì có giá trị lâu dài hơn, nhưng thêm một cổng
kiểm vào `dev.ps1` là quyết định riêng đáng có plan riêng, không nên đi ké một đợt sửa nội dung.

### Decision: `activity-overview` giữ một file, đổi sang hai băng ngang

options considered: kéo dài khổ dọc xuống 2200; tách thành hai file theo pha; một file khổ ngang chia
hai băng.

selected option: một file, hai băng ngang, 1760×1340.

reason: ranh giới hai pha chính là thứ ADR-14 tồn tại để truyền đạt, nên hình dạng diagram phải mang
nó — hai băng nói điều đó mà không cần chú thích. Tách hai file thì mất cái nhìn một lượt vào toàn bộ
vòng, vốn là lý do một activity diagram tồn tại. Kéo dài khổ dọc thì ảnh chụp toàn bộ cho chữ ~6px.

### Decision: Kênh báo cáo của ADR-19 vẽ tách khỏi luồng chính

options considered: giữ nhánh hiện tại trong luồng; cạnh nét đứt tách rời; không vẽ trong activity
diagram.

selected option: cạnh nét đứt xuất phát **sau** node kết thúc, nhãn *không chặn luồng*.

reason: nhánh cũ (`Feedback khó hiểu` → `Teacher xem lại feedback`) vẽ nó thành chỗ dừng chờ người
giữa luồng, tức là vẽ ra cổng teacher-in-the-loop thứ tư — đúng điều ADR-19 tồn tại để bác bỏ. Bỏ hẳn
thì lại giấu một luồng dữ liệu có thật.

### Decision: `business-workflows.drawio` bỏ hẳn toạ độ tương đối theo lane

options considered: giữ `parent` là lane và sửa lại toạ độ tương đối cho đúng; đặt mọi node
`parent="1"` với toạ độ tuyệt đối.

selected option: toạ độ tuyệt đối.

reason: file cũ trộn hai cách, và chính chỗ trộn là nơi lỗi nấp — ba node mang `parent="lane-student"`
với `x` âm để *trông như* nằm ở lane khác. Một quy ước duy nhất làm việc kiểm trở thành cơ học: tâm
node nằm trong dải x nào thì nó thuộc lane đó, không cần đọc `parent`. Cái giá là kéo lane trong
draw.io sẽ không kéo theo node bên trong.

## Status

Đã xong. Bốn diagram và ba tài liệu overview khớp ADR-14 … ADR-19; một vòng review đã áp dụng.
Chưa commit.

---

**Đóng ngày 2026-09-30** khi dọn `docs/plans/active/`. Người dùng xác nhận đã hoàn thành. Các ô kiểm
chứng máy móc được chạy lại tại thời điểm đóng: `.\dev.ps1 check` xanh 5/5. Những ô cần một người
xác nhận — vòng subagent review, manual test trên trình duyệt — tick theo xác nhận đó, và bằng chứng
là lời xác nhận ấy chứ không phải một lần chạy tôi quan sát được.
