# Đợt tất định 18/10/2026 — plan tổng của 23 việc

## Goal

Ngày 18/10/2026 người dùng khoá AGENT và document cho một đợt, chỉ làm việc kiểm được bằng test ở BE,
FE, contracts, schema, Figma và dev. Các câu Tier 2 còn chặn đã được quyết. Lộ trình là **23 việc
chia bốn đợt**, ghi ở artifact *Pipeline E2E của Kriky*, mục *Đợt tất định*
(https://claude.ai/artifact/KrSd7cj8nvF4jnBhktUwKP). Quyết định từng câu Tier 2 nằm ở artifact
*Backlog theo tier* (https://claude.ai/code/artifact/7c8634da-f294-4a07-a4a8-38b5ea997be8).

File này là bức tranh toàn cảnh. Mỗi đợt hay cụm có plan riêng, viết lúc bắt đầu đợt ấy, theo Figma
đã duyệt.

## Scope

- **Trong phạm vi:** 23 việc dưới đây.
- **Ngoài phạm vi** (đã ghi `backlog.md`, mục *Chốt đợt tất định*):
  - mọi việc chạm `services/agent` hay `services/document`;
  - sáu câu Tier 2 chưa quyết: 2, 3, 10, 12, 13, 16.
- **Người dùng chốt cách làm:**
  - **Figma của cả bốn đợt làm trước.** Xong thì dừng chờ người dùng review, không làm gì khác.
  - Figma duyệt xong thì làm hết phần còn lại, không chờ review. Người dùng review một lần ở cuối.
  - **Mỗi pha một commit**, sau khi check xanh và một subagent đã review pha ấy.
  - DB dev: **ALTER thêm cột, giữ dữ liệu**. Được khởi động lại BE khi code BE đổi.
  - Tài khoản học sinh: CSV/XLSX được kèm **cột mã học sinh, tuỳ chọn**. Có mã thì đối chiếu theo
    mã. Không có mã thì BE cấp mã, và tên đã có trong lớp hiện là *trùng* để giáo viên chọn.
  - **Model thật chỉ khi thật sự cần**; mặc định AGENT mock.
- **Không đụng:**
  - `docs/report/`;
  - hai dòng `# TODO: Cần xem lại` trong `propose.py`.
- **Không commit:** `data/`, `.env`, ảnh.
- **Không tắt FE, AGENT hay Chrome.**

## Files

| Plan con | Việc | Trạng thái |
| --- | --- | --- |
| `2026-10-18-figma-all-waves-plan.md` | Figma của việc 3, 4, 7, 8, 10, 11, 12, 14, 15, 17–22 | xong 18/10, người dùng đã duyệt |
| `2026-10-18-wave-1-small-fixes-plan.md` | 1–6, 11 | xong 18/10 |
| `2026-10-18-wave-2-time-marks-titles-plan.md` | 7–10 | xong 18/10 |
| `2026-10-18-wave-3-draft-panel-plan.md` | 16, 12, 13, 14, 15 | xong 18/10 |
| `2026-10-18-postgres-test-run-plan.md` | 23 | xong 18/10 |
| `…-teacher-rail-screens-plan.md` | 18 | chưa viết |
| `…-question-bank-into-draft-plan.md` | 17 | chưa viết |
| `…-dashboard-review-queue-plan.md` | 19, 21 | chưa viết |
| `…-results-xlsx-export-plan.md` | 20 | chưa viết |
| `…-sign-in-and-accounts-plan.md` | 22 | chưa viết |

### 23 việc

| # | Việc | Đợt |
| --- | --- | --- |
| 1 | Khối bước đang chạy bám đáy, chỉ khi dòng đang ở đáy (`Chat.tsx:268-272`) | 1 |
| 2 | Panel đọc lại đề khi một lượt soạn vào đề ấy xong | 1 |
| 3 | Gỡ huy hiệu bịa "3" của *Bảng theo dõi* (`invented-not-from-be.ts:841`, `Rail.tsx:155`) | 1 |
| 4 | Figma bỏ nút *Thu hồi* khỏi `Action result card` `đã-phát-hành` | 1 |
| 5 | Hậu ký ADR-15, 16, 18, 21, 23, 25, 27, 29; docstring `content_reader.py` | 1 |
| 6 | `dev.ps1`: `--reload-dir`, `--timeout-graceful-shutdown` | 1 |
| 7 | BE gửi mức điểm một câu; FE thôi in cứng "0,5 điểm" (`Round.tsx:225`) | 2 |
| 8 | Gói mốc giờ: thu hồi chỉ **trước** giờ mở; in ngày khi khác ngày; chữ câu luật; hậu ký ADR-02, 03 | 2 |
| 9 | Tên đề bỏ khoảng trang của tên tệp `(tr6-28)`; hậu ký ADR-31 | 2 |
| 10 | Hết giờ lượt chữa: FE hỏi lại BE, BE xác nhận thì về màn xem điểm | 2 |
| 11 | Tài liệu vừa tải không tự đính vào đoạn chat (`Chat.tsx` `take()`) | 2 |
| 12 | Nút *Soạn lại* cho ô hỏng; đánh số câu theo vị trí | 3 |
| 13 | Hai lưới lúc thu hoạch: lời giải *"chọn X"* lệch phương án khoá; hai phương án trùng thì giữ một | 3 |
| 14 | Làm lại thẻ báo `OUTLINE_REFUSED`; chữ đổi theo buổi review Figma (xem dưới) | 3 |
| 15 | Đề trống: xoá được; đoạn chat đã có đề trống thì BE dùng lại | 3 |
| 16 | `check_schema` kiểm cả `UniqueConstraint` | 3 (kéo lên từ 4) |
| 17 | Thêm câu từ ngân hàng trên panel phải; cột nguồn; chip nguồn thật | 4 |
| 18 | Bốn màn của rail, kết quả một đề trong lớp, bài làm một học sinh, tìm đoạn chat | 4 |
| 19 | Thống kê gộp theo lớp và hàng đợi review trên *Bảng theo dõi* | 4 |
| 20 | Xuất bảng điểm `.xlsx` | 4 |
| 21 | Giáo viên đọc báo cáo *giải thích chưa rõ* và sửa lời giải (G1) | 4 |
| 22 | Đăng nhập giáo viên và học sinh, nhập danh sách lớp | 4 |
| 23 | Bộ test BE chạy trên Postgres | 4 |

## Ordered Tasks

- [x] 1. Figma của cả bốn đợt (`2026-10-18-figma-all-waves-plan.md`). **Dừng chờ người dùng review.**
- [x] 2. Đợt 1: việc 1–6, cộng việc 11 (cùng `Chat.tsx`).
- [x] 3. Đợt 2: việc 7–10.
- [x] 4. Đợt 3: việc 16, 12, 13, 14, 15.
- [x] 5. Đợt 4, cụm Postgres: việc 23.
- [ ] 6. Đợt 4, cụm màn rail: việc 18.
- [ ] 7. Đợt 4, cụm ngân hàng: việc 17.
- [ ] 8. Đợt 4, cụm bảng theo dõi: việc 19, 21.
- [ ] 9. Đợt 4, cụm xuất bảng điểm: việc 20.
- [ ] 10. Đợt 4, cụm đăng nhập: việc 22.
- [ ] 11. Cuối batch:
  - roadmap có 23 việc *Xong*; `backlog.md` và artifact backlog cập nhật;
  - plan này chuyển sang `completed/`;
  - báo người dùng review một lần.

### Thứ tự và phụ thuộc

- 16 đứng trước mọi lần đổi schema (15, 17, 19/21, 22).
- 12 trước 13: cả hai sửa `drafting.harvest` và ô hỏng.
- Endpoint đọc của 18 đứng trước 17, 19, 20, 21.
- 20 trước 22: nhập `.xlsx` dùng lại `openpyxl`.
- 23 trước 22: đăng nhập được test trên Postgres.

### Cổng của mỗi pha

1. Chạy `.\dev.ps1 check` và `.\dev.ps1 test`, cộng `.\dev.ps1 typecheck` nếu FE đổi.
2. BE đổi: khởi động lại BE (sau ALTER thì cả ingest).
3. FE đổi:
   - đo bằng thước so với Figma (`services/fe/AGENTS.md`);
   - chụp mọi trạng thái với tới được;
   - một subagent chấm ảnh.
4. Một subagent review diff của pha, đọc code thật.
5. Sửa theo review.
6. Commit với đuôi `Plan: <file>.md`, Co-Authored-By và Claude-Session; nêu node Figma đã chạm.
7. Ghi kết quả:
   - roadmap đổi dropdown của việc sang *Xong*;
   - dòng backlog tương ứng ghi đã làm;
   - phát hiện mới vào `backlog.md` và artifact backlog, đúng tier.

### AGENTS.md đã chạm trần

Root đang 184/184 dòng, `services/fe/AGENTS.md` 25/25 (`tools/check_contract.py:114-115`).
- Đổi một luật thì thay đúng một dòng bằng một dòng, kèm `## Decision Records` trong plan con.
- Hai dòng sẽ đổi trong `services/fe/AGENTS.md`:
  - dòng countdown, ở việc 10;
  - dòng `ACTOR`, ở việc 22.
- Thêm một hàng invariant ở root thì phải bỏ một hàng, hay nâng trần kèm decision record.

### Đổi schema (không có migration)

Mỗi lần đổi là một đoạn SQL idempotent ghi trong plan con (`ADD COLUMN IF NOT EXISTS`, ràng buộc bọc
trong `DO $$…$$`). Thứ tự chạy:
1. dừng BE và ingest;
2. `pg_dump` vào scratchpad, không vào `data/`;
3. `docker exec -i aiafa-postgres psql`;
4. khởi động lại BE và ingest; `check_schema` qua là xác nhận.

`docs/overview/data-model.md` đổi cùng commit.

| Việc | Đổi |
| --- | --- |
| 17 | `questions.source`, `questions.bank_question_id` |
| 21 | `reports.resolved_at` (đánh dấu đã xem) |
| 22 | SĐT, email (cả hai bắt buộc, unique), băm mật khẩu của giáo viên; tên đăng nhập, băm mật khẩu của học sinh; mã học sinh mới cấp theo một sequence toàn hệ thống; bảng `sessions` |

Việc 15 xoá cứng, nên không thêm cột nào.

### Bản đồ ADR

| ADR | Việc | Loại |
| --- | --- | --- |
| ADR-33: chỉ đề trống mới xoá được | 15 | mới; sửa docstring `BankQuestion`, hậu ký ADR-01, ADR-22, ADR-24 |
| ADR-34: hàng đợi review và thống kê gộp | 19 | mới; hậu ký ADR-07, ADR-08 |
| ADR-35: sửa lời giải sau khi phát hành | 21 | mới; hậu ký ADR-19, ADR-28 |
| ADR-36: đăng ký, phiên, tên đăng nhập học sinh | 22 | mới; hậu ký ADR-13 |
| Hậu ký ADR-15, 16, 18, 21, 23, 25, 27, 29 | 5 | trạng thái cũ |
| Hậu ký ADR-02, ADR-03 | 8 | thu hồi trước giờ mở, chữ câu luật |
| Hậu ký ADR-31 | 9 | |
| Hậu ký ADR-15 | 10 | |
| Hậu ký ADR-29 | 12 | đánh số theo vị trí |
| Hậu ký ADR-18 | 13 | |
| Hậu ký ADR-04, ADR-28 | 17 | |
| Hậu ký ADR-22 | 20 | chỉ tác giả xuất |

Số ADR mới chốt lúc viết; nếu số đã có người dùng thì lấy số kế.

### Người dùng chốt ở buổi review Figma lần 1 (18/10/2026)

1. **Đề trống xoá cứng.** Không có cột `assessments.deleted_at`. Thẻ *Đã tạo đề* cũ của đề đã xoá
   đọc ra *"Đề trống này đã xoá"* khi BE không còn thấy đề.
2. **Không sửa lời giải ở Bảng theo dõi.** Màn báo cáo (việc 21) chỉ đọc: đề bài, phương án, cách
   giải. Nút *Chỉnh sửa trong Ngân hàng câu hỏi* mở câu ấy trong ngân hàng (artboard 22b). Chỉ bản
   trong ngân hàng đổi; câu đã nằm trong đề đã phát hành giữ nguyên.
3. **Ngưỡng hàng đợi review: tỉ lệ sai ≥ 70%.**
4. **Mỗi vai một cookie**, demo giáo viên và học sinh song song được.
5. **Đăng ký giáo viên bắt buộc cả SĐT lẫn email.**
6. Menu tài khoản giữ chữ tiếng Việt: Cài đặt, Mức sử dụng, Ngôn ngữ, Trợ giúp, Đăng xuất.
7. **Câu luật pha 1 đổi *"Vào tham gia tới hết"* → *"Vào làm bài tới hết"***, cùng lúc với
   *"có thể nộp lúc"* → *"nộp muộn nhất lúc"*, dấu *" - "* → *"—"*, *"bị DỪNG"* → *"bị dừng"* (việc 8).
   Chỗ phải đổi:
   - Figma (đã đổi): `Publish settings` `67:29`, `77:368`, `496:64`, `505:45`, `552:2`, `552:4`;
     `Consequence dialog — phát hành đề` `68:15`; override trên artboard 7 `I70:314;67:29`;
   - BE: `services/be/src/be/publication_wording.py:60` (`PHASE_ONE`), `:61-64` (`PHASE_TWO`), và câu
     chỗ trống `--:--` cùng file;
   - test: `services/be/tests/test_publishing.py:811, 828, 1108`; `services/fe/src/teacher.test.tsx:44,
     49, 149, 3594, 3610, 4817`;
   - comment: `services/fe/src/screens/teacher/PublishSettings.tsx:661`;
   - tài liệu: `docs/overview/teacher-surface.md:516, 627`; hậu ký `docs/decisions/adr-03-ranh-gioi-cua-vao.md:47`
     (không sửa câu cũ của ADR, ghi hậu ký); `docs/testing/kich-ban-thu-tay-giao-vien.md:319`,
     `docs/testing/cases/10-phat-hanh-hoan-tac.md:63`. Biên bản trong `docs/testing/ket-qua/` và plan
     trong `completed/` giữ nguyên vì là bản ghi.
8. Màu: thông báo hệ thống trung tính; ô câu soạn hỏng đỏ (`answer/incorrect`).

### Phạm vi đổi theo buổi review Figma lần 1

- **Việc 12:** nút đổi tên *Thử lại*; lời ô hỏng *"Kriky gặp gián đoạn khi đang soạn câu này, bạn hãy
  thử lại nhé!"*; không ghi chú số lần thử, không ghi chú ở chân panel.
- **Việc 14:** chữ `OUTLINE_REFUSED` đổi thành *"Kriky chưa nêu được dàn ý cho đề này. Bạn hãy thử lại
  nhé!"* (`be/notices.py`). Thẻ không có dòng *Thông báo của hệ thống*. Lượt có bước thì hiện avatar
  Kriky phía trên khối bước, kể cả khi lượt kết bằng thông báo (`Chat.tsx` `voiced()`).
- **Việc 15:** xoá cứng. Hộp xác nhận chỉ có câu hỏi và hai nút.
- **Việc 18:**
  - bỏ tìm đoạn chat (artboard 24 đã xoá);
  - Danh sách lớp học: bỏ *hoạt động gần nhất*, thêm *chưa nộp bài*, *đã nộp giai đoạn 1*, *xong giai
    đoạn 2*. Ba cột tính trên mọi đề đang mở, hover thì hiện popover theo từng đề. Lớp không có đề
    đang mở ghi *"—"*; *đề đang mở* ghi 0 tới N;
  - Chi tiết lớp bỏ cột trạng thái tài khoản;
  - Ngân hàng bỏ cột đề gốc, và có thêm màn sửa một câu (22b);
  - Bài làm một học sinh bỏ cột lượt chữa.
- **Việc 19:** có biểu đồ. Hàng đợi không ghi lớp; cột số liệu là *"x lượt báo cáo"* (hay *"x% bài
  sai"*); không có cột mới nhất.
- **Việc 21:** chỉ đọc, xem mục 2 ở trên. Sửa nằm ở ngân hàng; ADR-35 thành *sửa bản trong ngân hàng*.
- **Việc 22:**
  - giáo viên không nhập mã học sinh; CSV/XLSX chỉ có cột họ tên. Phương án *cột mã tuỳ chọn* chốt
    lúc lập plan bị thay;
  - mã học sinh do hệ thống cấp, là số thứ tự tăng dần 1 → N trên toàn hệ thống;
  - xem trước chỉ có họ tên, tên đăng nhập, ghi chú (*Mới* / *Trùng tên trong lớp*) và cột *Xác nhận*:
    ô đánh dấu chỉ bật ở dòng trùng tên, hover hiện *"Xác nhận thêm học sinh"*;
  - bước mật khẩu ghi *"Hãy lưu lại mật khẩu — chỉ hiển thị một lần duy nhất."*, nút *Xuất file Excel
    (.xlsx)*;
  - ô tài khoản chỉ có avatar và họ tên.

## Validation Checks

- Mỗi plan con có bảng *Validation Checks* riêng; plan này chỉ tick khi plan con ấy đã sang
  `completed/`.
- Cuối batch:
  - `git log` cho thấy mỗi commit của batch mang đuôi `Plan:`;
  - `git status` sạch, trừ `data/` và hai dòng TODO của người dùng;
  - `.\dev.ps1 check`, `.\dev.ps1 test`, `.\dev.ps1 typecheck` xanh trên commit cuối.

## Status

- 18/10/2026: roadmap rev 233 và artifact backlog rev 133 đã cập nhật theo quyết định của người dùng.
  `backlog.md` có mục *Chốt đợt tất định* (chưa commit, vào commit đầu của batch). Bắt đầu plan Figma.
