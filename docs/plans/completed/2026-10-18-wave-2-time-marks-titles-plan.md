# Đợt 2 của đợt tất định — mức điểm, mốc giờ, tên đề, hết giờ lượt chữa

## Goal

Làm việc 7–10 của `2026-10-18-deterministic-batch-master-plan.md`. Figma đã duyệt 18/10/2026:
- câu luật đổi chữ ở 4 chỗ, in ngày khi khác ngày giờ mở;
- artboard `16b · Kết quả — lượt chữa vừa hết giờ` (`652:3384`).

## Scope

- **Trong phạm vi:**
  - việc 7: BE gửi mức điểm của một câu đúng trong lượt chữa;
  - việc 8: thu hồi chỉ được **trước** giờ mở; câu luật in ngày khi mốc khác ngày giờ mở; chữ câu
    luật mới; hậu ký ADR-02, ADR-03;
  - việc 9: tên đề bỏ khoảng trang của tên tệp; hậu ký ADR-31;
  - việc 10: đồng hồ lượt chữa về 0 thì FE hỏi lại BE, BE xác nhận đã dừng thì nộp và về màn xem
    điểm có thông báo; thay một dòng của `services/fe/AGENTS.md`.
- **Ngoài phạm vi:** mọi việc khác của plan tổng.
- Cổng mỗi pha theo plan tổng; mỗi pha một commit.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `services/be/src/be/student_routes.py`, `scoring.py`, `services/fe/src/api.ts`, `screens/student/Round.tsx` | 7, 10 |
| `services/be/src/be/assessment_state.py`, `publication_wording.py`, `teacher_routes.py`, `student_routes.py`, `services/fe/src/screens/teacher/PublishSettings.tsx`, `screens/student/Tutor.tsx`, tests | 8 |
| `services/be/src/be/titles.py`, tests | 9 |
| `services/fe/src/components.tsx`, `screens/student/Result.tsx`, `services/fe/AGENTS.md` | 10 |
| `docs/decisions/adr-02-*`, `adr-03-*`, `adr-15-*`, `adr-31-*`, `docs/overview/teacher-surface.md`, `docs/testing/*` | hậu ký và tài liệu |

## Ordered Tasks

### Pha 1 — mức điểm (việc 7)
- [x] 1. `RoundOpenOut` thêm `mark_when_right: float` lấy từ `scoring.MARK_REMEDIATED`; cả
  `start_round` và `read_round` trả nó. `api.ts` `OpenRound` thêm trường. `Round.tsx:225` in
  *"câu làm đúng được {mức} điểm"*, số theo kiểu Việt (`0,5`). Test BE: hai đường đều trả mức;
  vitest: hộp nộp lượt in số BE gửi.

### Pha 2 — gói mốc giờ (việc 8)
- [x] 2. `assessment_state.may_withdraw`: `now < opens_at`, không còn `<=`; đúng giây giờ mở là
  học sinh đã vào được. Test đúng biên. `RECALL_RULE` nói *"trước giờ mở"*. Hậu ký ADR-02.
- [x] 3. Chữ câu luật (`publication_wording.py`):
  - `PHASE_ONE` = *"Vào làm bài tới hết {closes} — nộp muộn nhất lúc {last}, và không dừng người
    đang làm."*;
  - `PHASE_TWO` = *"Chữa bài tới hết {deadline} — mỗi lượt {rate} phút một câu; hết hạn thì lượt
    đang làm bị dừng."*.

  Sửa docstring nói về chữ *DỪNG* viết hoa. *"DỪNG"* ở lời 409 của `save_round_answer` và ở
  `Tutor.tsx` đổi thành chữ thường cho cùng giọng.
- [x] 4. In ngày khi mốc khác ngày giờ mở:
  - BE `_clock(moment, opens)` in `HH:MM · DD/MM` khi ngày của `moment` khác ngày của `opens`;
    `phase_one_note` và `phase_two_note` nhận thêm `opens_at`;
  - FE `PublishSettings.clock` làm cùng phép, cho biểu mẫu và khối ĐÃ PHÁT HÀNH.
  - Ngày so theo giờ địa phương của giáo viên, như số giờ.
  - `check_contract.py` `check_the_form_fills_the_slots_the_wording_declares` vẫn qua (tên chỗ
    trống không đổi).
- [x] 5. Test: biên `opens_at`; câu in ngày khi hạn chữa sang ngày sau; câu không in ngày khi
  cùng ngày; vitest biểu mẫu và khối ĐÃ PHÁT HÀNH.
- [x] 6. Chữ cũ ở test và tài liệu theo danh sách của plan tổng (mục *Người dùng chốt…*, câu 7).
  Hậu ký ADR-03; `teacher-surface.md:516, 627`; `docs/testing/kich-ban-thu-tay-giao-vien.md:319`;
  `docs/testing/cases/10-phat-hanh-hoan-tac.md:63`. Biên bản trong `docs/testing/ket-qua/` giữ
  nguyên.
- [x] 7. Trình duyệt: biểu mẫu phát hành với hạn chữa sang ngày sau, hộp xác nhận, khối ĐÃ PHÁT
  HÀNH. Chụp, đo, subagent chấm so với `Publish settings` `534:20`, `67:39` và artboard 7, 8.

### Pha 3 — tên đề (việc 9)
- [x] 8. `titles._PAGES` bắt *"(tr. 5–9)"*, *"(tr6-28)"*, *"(tr 6-28)"*, không phân biệt hoa thường.
  `default_title` áp nó cho cả tên tệp. Test bằng các tên tệp thật trong `data/` (chỉ đọc tên).
  Hậu ký ADR-31.

### Pha 4 — hết giờ lượt chữa (việc 10)
- [x] 9. BE:
  - `RoundOpenOut` thêm `stopped: bool` (`now > ends_at`, cùng biên với `save_round_answer`; plan
    viết `>=`, review pha 4 chỉ ra hai biên lệch nhau đúng giây `ends_at`);
  - `ResultOut` thêm `last_round_ran_out: bool`: lượt nộp gần nhất có `submitted_at > ends_at`,
    tính từ cột có sẵn.
  - Test cả hai.
- [x] 10. FE: `TimeCard` nhận `onExpire`. `Round.tsx` về 0 thì đọc lại lượt (`api.round`):
  - `stopped` thì nộp rồi về `/attempt/{id}/result`;
  - lượt đã nộp ở tab khác (409) thì về thẳng màn xem điểm;
  - BE nói chưa dừng thì ở lại, hỏi lại sau `max(1 giây, ends_at − giờ máy)`, tối đa năm lần;
  - không nói được với BE hay nộp hỏng vì lỗi khác 409 thì ở lại, hiện lời lỗi.
- [x] 11. `Result.tsx`: `last_round_ran_out` thì hiện thông báo của artboard 16b phía trên dòng
  *"Bạn có thể nâng điểm…"*.
- [x] 12. `services/fe/AGENTS.md`: thay dòng *"A countdown is decoration. Reaching zero changes
  nothing: BE refuses a late answer."* bằng *"A countdown never decides: at zero the screen asks BE,
  and only BE's answer moves it."* Giữ đúng số dòng (25/25). Decision record ở dưới. Hậu ký
  ADR-15.
- [x] 13. Vitest:
  - về 0 mà BE nói đã dừng thì nộp và chuyển màn;
  - BE nói chưa dừng thì không;
  - màn xem điểm có thông báo khi cờ bật.

  Trình duyệt: rút `ends_at` của một lượt trong DB dev về vài giây tới, xem màn tự chuyển; chụp,
  subagent chấm so với 16b.

### Pha 5 — đóng
- [x] 14. Roadmap: việc 7–10 sang *Xong*. Backlog ghi đã làm. Tick plan tổng; plan này sang
  `completed/`.

## Decision Records

### Decision: đồng hồ về 0 thì màn hình hỏi BE
options considered: giữ luật cũ (đồng hồ chỉ là trang trí, học sinh tự bấm nộp); FE tự chuyển màn
khi về 0; FE hỏi lại BE và chỉ BE xác nhận mới chuyển.
selected option: FE hỏi lại BE.
reason: người dùng chốt hết giờ thì tự rời màn làm bài (Tier 2 câu 18). Luật *"không màn hình nào
quyết một luật"* vẫn giữ được nếu màn hình chỉ chuyển khi BE nói lượt đã dừng: đồng hồ của trình
duyệt có thể lệch, BE thì không. Dòng của `services/fe/AGENTS.md` đổi để nói đúng điều ấy.

### Decision: phép in ngày có hai bản, như phép cộng giờ nộp cuối
options considered: chỉ BE dựng câu và FE gọi BE mỗi lần gõ; FE nhận câu đã điền sẵn; BE và FE cùng
một phép, có test ở hai bên.
selected option: hai bản, test ở hai bên.
reason: biểu mẫu điền câu luật theo số **đang gõ**, chưa gửi gì lên BE; gọi BE mỗi phím là một
đường mạng cho một việc định dạng. Đây cùng cách đã chọn cho phép cộng *giờ đóng + phút làm bài*
(`publication_wording` docstring nói rõ có hai bản). Ngày so theo múi giờ giáo viên đang đọc ở cả
hai bên; test BE có ca múi giờ Việt Nam lệch ngày UTC, vitest có ca hạn chữa sang ngày sau.

## Validation Checks

| Kiểm | Lệnh |
| --- | --- |
| Python, repo checks | `.\dev.ps1 test`, `.\dev.ps1 check` |
| FE | `.\dev.ps1 typecheck`, vitest |
| Trình duyệt | ảnh chụp Chrome headless (CDP) + subagent chấm, pha 2 và 4 |
| AGENTS.md | `check_contract` giữ trần 25 dòng |

## Status

- 18/10/2026: plan mở.
- Pha 1–3 xong 18/10/2026:
  - thử trên Chrome headless: biểu mẫu, hộp xác nhận và khối ĐÃ PHÁT HÀNH in *"Chữa bài tới hết
    14:25 · 21/10 — …"* khi hạn chữa sang ngày sau giờ mở. Lần phát hành thử (đề nháp thử của chính
    tôi) đã thu hồi ngay sau đó;
  - hộp nộp lượt (pha 1) thử chung với pha 4, cùng màn lượt chữa;
  - subagent review: sửa câu thu hồi ở hộp xác nhận, ở thẻ kết quả (`ActionCard.tsx`, ngoài danh
    sách file của plan nhưng cùng một luật) và trên Figma (`76:8`, `76:29`, `11:43`, `505:48`, `560:3`);
    ca thử tay `cases/10`; fixture FE; kiểu `mark_when_right` tuỳ chọn; test múi giờ; mốc không múi
    giờ; comment mang slug plan.
- Pha 4 xong 18/10/2026:
  - thử trên Chrome headless với API giả (chặn `/api` bằng CDP, không ghi gì vào DB dev): về 0 thì
    đọc lại lượt, nộp, về `#/attempt/a1/result`, thông báo đúng chữ; hộp nộp lượt in *"0,5 điểm"*
    BE gửi (pha 1). Chưa rút `ends_at` trong DB dev như task 13 viết: lượt chữa thật nằm trong bài
    làm của học sinh seed, và API giả thử được cùng nhánh mà không chạm dữ liệu;
  - subagent review: lỗi mạng hay nộp hỏng từng bị coi như 409 và đẩy học sinh đi (`ApiError`
    mang status); chưa dừng thì hỏi lại có giới hạn; biên `>`; test FE bằng fake timers với
    `ends_at` cố định; ca BE hai lượt; banner cao 38px như artboard; hậu ký đủ bốn nhánh.
- Pha 5 xong 18/10/2026: roadmap việc 7–10 *Xong* (rev 246); backlog và artifact backlog (rev 137)
  ghi đã làm; mục lục ADR ghi hậu ký ADR-02, 03, 15, 31. Plan đóng.
