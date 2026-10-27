# Lần chạy 27/10/2026 trên Claude Haiku 5.5 — trên 6050d6f (vòng T27: plan tạo lớp)

- **Ngày:** 27/10/2026, 20:55–21:05.
- **Code:** `6050d6f` cộng thay đổi chưa commit của plan `2026-10-27-tao-lop-plan.md`:
  - BE `be.classes`, tool `create_class`;
  - AGENT skill `lop-va-ket-qua` bước 5–6, `history.telling_skill`;
  - FE nút và hộp *Tạo lớp*.
  BE tự nạp lại. AGENT khởi động lại lúc 20:52, sau mọi thay đổi.
- **Model:** `anthropic/claude-haiku-5-5`, `thinking=disabled`, `effort=low`.
- **Database:** dev đang có, không `db-reset`. Giáo viên seed GV-001, có lớp 12A và 12B.
- **Chi phí:**
  - thử tay khoảng 37 nghìn token chat, chừng 0,02–0,03 USD;
  - bench `run-118` (Jev, 0,0023 USD), `run-119`, `run-120` (Haiku, 15 lượt, khoảng 135 nghìn token,
    chừng 0,07 USD).
- **Ảnh:** `docs/report/screenshot/27_10/tao-lop/` 01–08 (không commit).

## Màn 9

| Bước | Kết quả |
| --- | --- |
| Nút *Tạo lớp* ở đầu màn (ảnh `01`) | **Đạt** |
| Hộp *Tạo lớp mới*: ô tên có focus, nút *Tạo lớp* khoá khi tên rỗng (ảnh `02`) | **Đạt** |
| Gõ `lớp 12A`, Enter: hộp ở lại, in *Bạn đã có lớp "12A".* (ảnh `03`) | **Đạt**. So bằng `normalise` nên *"lớp 12A"* trùng *12A* |
| Gõ `12C`, Enter: sang màn 10 của *Lớp 12C*, 0 học sinh, nút *Thêm học sinh* (ảnh `04`) | **Đạt** |

## Chat

| Lượt | Kết quả | Ghi chú |
| --- | --- | --- |
| *"tạo giúp mình lớp 10A3 nhé"* | **Đạt** | Plan một bước *Tạo lớp — lớp "10A3", chưa có học sinh*. Câu kết: *"Đã tạo xong lớp **10A3**. Lớp hiện chưa có học sinh; bạn thêm học sinh ở màn của lớp, mục **Danh sách lớp học**."* (ảnh `05`, `06`). Không thẻ kết quả, đúng hậu ký ADR-13 |
| *"tạo thêm lớp 10A3 nữa giúp mình"* | **Đạt** | *Dừng ở bước 1*, ✕ *Tạo lớp — Bạn đã có lớp "10A3".*; câu kết nói đã có lớp, không tự tạo tên khác (ảnh `07`). Câu thừa *"Mình cũng không đổi tên lớp để tạo bản sao"*: model đọc lại lời dặn của skill thành câu nói |
| *"lớp 10A3 có mấy em"* | **Đạt** | `list_class` tìm ra lớp mới: *"Lớp **10A3** hiện có **0 học sinh**…"* (ảnh `08`) |

Hộp phát hành của đề `72350587…` liệt kê `10A3, 12A, 12B, 12C`.

## Bench

| Đo | Kết quả |
| --- | --- |
| `skill_bench` (`run-118`), ngưỡng 0,3 | Recall 100% cả ba skill. Precision `lop-va-ket-qua` 89% (lần trước 93%): `chung-phat-hanh` nạp thêm skill ở 0,32 |
| `propose_bench` `tao-lop-co-ten`, `tao-lop-chua-ten`, `tra-si-so` × 3 (`run-119`) | 9/9 |
| Bỏ tên lớp ví dụ khỏi skill (`run-120`) | 6/6; ở `run-119` Kriky chép *"Ví dụ 12C, 10A1"* của skill, `run-120` thì không |

`tao-lop-chua-ten` hỏi lại model cả 3 lần: `FewChoices` đòi ba nút, mà câu hỏi tên lớp không có
nút nào thật. Lần hai vẫn không nút. `run-120` cũng xưng *"Cô"*, theo tên giáo viên của bench
(Tier 4 đã có).
