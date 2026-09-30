# Mô hình hai pha — tầng quyết định

## Goal

Mọi luật của mô hình hai pha có chỗ trong `docs/decisions/`, mọi ADR bị va chạm được khoanh phạm vi
thay vì âm thầm sai, và mọi thứ cố ý chưa làm nằm trong `backlog.md` kèm câu trả lời *cái gì đang
chặn nó*.

## Bối cảnh

Tám artboard chat và ba màn hình vật thể hiện có đều là bề mặt **giáo viên**.
[ADR-10](../../decisions/adr-10-pham-vi-dot-dau.md) chốt đợt đầu *chỉ giáo viên*, và ghi rõ nửa sau
vòng nghiệp vụ *"có tài liệu và có code nhưng không có thiết kế"*.

Đợt này mở nửa sau đó ra, và mô hình mới **không phải phần mở rộng**. Nó đổi một thứ nằm ở gốc:
**nộp bài không còn là điểm kết thúc của một bài kiểm tra.**

Hệ quả lan **ngược** lên phía giáo viên đã dựng xong — biểu mẫu phát hành thiếu hai trường, `ĐÃ NỘP`
thôi là trạng thái cuối, điểm trên bảng lớp chỉ đi lên chứ không đứng yên — và đụng **mười một** ADR
đang có, tức mọi ADR từ 01 tới 11. Dựng màn hình trước khi ghi những luật này xuống là dựng lên trên
một tài liệu đã sai.

## Mô hình

```text
GIÁO VIÊN  soạn đề — mỗi câu kèm LỜI GIẢI NHIỀU CÁCH, mỗi nhiễu gắn MỘT LỖI
           duyệt (khoá nội dung, nay gồm cả lời giải)
           phát hành: lớp · thời gian làm bài · giờ mở · giờ đóng
                    · PHÚT MỖI CÂU Ở PHA 2 · HẠN KẾT THÚC PHA 2

PHA 1 — có đồng hồ (ADR-03 giữ nguyên)
  vào (tới hết giờ đóng) → chọn đáp án → nộp
  chấm: đúng/sai là phép so, xác định
  chẩn đoán: nhiễu đã chọn → lỗi đã soạn sẵn (tra cứu, không suy đoán)

PHA 2 — bắt buộc, đồng hồ riêng
  mỗi câu sai sinh biến thể của CHÍNH NÓ, đếm vòng RIÊNG, tối đa 3
  một lượt gom mọi câu còn dở:
      Kriky giải thích từng lỗi · học sinh hỏi lại        KHÔNG tính giờ
      (báo cáo "giải thích chưa rõ" được phép ở đây)
      [Làm bài mới] ← đồng hồ = phút-mỗi-câu × số câu trong lượt, dùng CHUNG
      đúng → câu gốc chốt 0,5đ · sai → vòng tiếp · hết 3 vòng → 0đ
  hết hạn giữa chừng → CẮT, câu còn dở 0đ

  KẾT THÚC (của từng em). Mỗi câu 1 / 0,5 / 0.
```

Bài 10 câu, sai câu 3 và 7, tỉ lệ 5 phút/câu: lượt 1 làm 3' và 7' trong **10 phút chung**; 3' đúng nên
câu 3 chốt 0,5đ; lượt 2 chỉ còn 7'' nên **5 phút**; hết vòng 3 vẫn sai thì câu 7 = 0đ. Tổng **8,5**.

## Scope

**Trong:** sáu ADR mới; khoanh phạm vi mười một ADR đã có; `backlog.md`; `docs/decisions/README.md`.

**Ngoài, và là đợt kế tiếp:** `docs/overview/` (ba file) và `docs/diagrams/` (ba file). Sau đợt này
hai nhóm đó **đang sai** ở khoảng mười lăm chỗ; xem `## Decision Records`.

**Ngoài, xa hơn:** Figma, code, contract, test, và ba màn hình học sinh.

## Files

| File | Việc |
| --- | --- |
| `docs/plans/backlog.md` | mười một mục về luồng học sinh — **làm trước**, vì ADR trỏ vào |
| `docs/decisions/adr-14-hai-pha-lam-bai.md` | tạo |
| `docs/decisions/adr-15-thoi-gian-pha-hai.md` | tạo |
| `docs/decisions/adr-16-thang-diem-ba-muc.md` | tạo |
| `docs/decisions/adr-17-ba-vong-moi-cau.md` | tạo |
| `docs/decisions/adr-18-cau-hoi-phai-kem-loi-giai.md` | tạo |
| `docs/decisions/adr-19-bao-cao-giai-thich-chua-ro.md` | tạo |
| `docs/decisions/adr-01` … `adr-11` | sửa — mười một file, phần lớn một đoạn khoanh phạm vi |
| `docs/decisions/README.md` | bảng ADR và mục *Còn thiếu* |
| `AGENTS.md` | **không sửa** — xem `## Decision Records` |

## Ordered Tasks

- [x] Viết mười một mục nợ vào `backlog.md`, trước mọi ADR trỏ tới chúng.
- [x] Viết ADR-14 — hai pha; nộp bài không phải điểm kết thúc.
- [x] Viết ADR-15 — thời gian ở pha 2.
- [x] Viết ADR-16 — thang 1 / 0,5 / 0, và 0,5 nghĩa là gì.
- [x] Viết ADR-17 — ba vòng, đếm riêng mỗi câu.
- [x] Viết ADR-18 — câu hỏi phải kèm lời giải nhiều cách và nhiễu gắn lỗi.
- [x] Viết ADR-19 — kênh báo cáo *giải thích chưa rõ*.
- [x] Khoanh phạm vi ADR-01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11.
- [x] Cập nhật `docs/decisions/README.md`.
- [x] Kiểm lại **mọi** trích dẫn `file:dòng` — không tin vào lúc viết.
- [x] `.\dev.ps1 check`; link Markdown resolve; LF; `AGENTS.md` vẫn 170 dòng.
- [x] Gọi 1 subagent review, chỉ đọc. Sửa theo phát hiện, hoặc phản bác có lý do.

## Validation Checks

- Sáu ADR mới đủ năm mục; **tất cả** mang `đã chốt, chưa thi hành`.
- Không dòng nào trong *Hệ quả* trả lời "sửa file nào" thay vì "cái gì trở nên khó hơn".
- Không ADR nào còn khẳng định phát hành có **bốn** tham số.
- Không ADR nào khẳng định một luật rồi trỏ vào chỗ thi hành trái luật đó mà không ghi *chưa thi hành*.
- Mọi trích dẫn `file:dòng` khớp nội dung thật; không node id Figma mới nào được thêm.
- Không lý do nào là *"người dùng chốt"*.
- `AGENTS.md` đúng 170 dòng; nhóm invariant chưa-enforce vẫn đúng ba dòng.
- Mỗi mục trong `backlog.md` trả lời *cái gì đang chặn*.

## Decision Records

### Decision: Tách tầng quyết định khỏi tầng mô tả

options considered: một đợt làm tất cả (ADR + `docs/overview/` + ba diagram); tách theo số lượng file;
tách theo **loại việc** — quyết định trước, mô tả sau.

selected option: tách theo loại việc.

reason: thứ dễ vỡ ở đây là tính nhất quán chéo giữa mười bảy file ADR, không phải khối lượng. Đợt ADR
vòng hai đã cho thấy một sửa đổi ngoài lề — rewrap `.env.example` — làm sai trích dẫn của hai ADR vừa
viết xong. Trộn thêm ba bản viết lại prose và ba diagram vào cùng một pass là mời đúng lỗi đó quay lại.
Cái giá phải trả và phải nói thẳng: sau đợt này `docs/overview/` và `docs/diagrams/` đang sai ở khoảng
mười lăm chỗ — *ba mốc thời gian*, vòng lặp dừng theo *mastery*, *dự đoán* lỗi sai thay vì tra cứu — và
đợt kế tiếp phải chạy ngay, không để trôi.

### Decision: Sáu ADR mới thay vì gộp thành ba

options considered: gộp hai pha và cơ chế thời gian vào một ADR, gộp thang điểm và số vòng vào một ADR;
tách thành sáu.

selected option: sáu.

reason: tiền lệ của repo là ADR-03 tách khỏi ADR-02 — cùng một lần phát hành, nhưng *ranh giới thời
gian* đứng riêng vì nó bị hiểu nhầm theo cách khác hẳn. Ở đây cũng vậy: *bài có hai pha* và *pha 2 tính
giờ thế nào* hỏng theo hai kiểu khác nhau, và người đọc cần tra được từng cái. Gộp lại thì mục *Vì sao*
phải phục vụ hai lý lẽ và sẽ phục vụ kém cả hai.

### Decision: Trần ba vòng — phần chi phí

options considered: ghi cả lý do sư phạm lẫn chi phí vào ADR-17; ghi lý do sư phạm vào ADR và chi phí
vào đây.

selected option: chi phí ghi ở đây.

reason: hai lý do có tuổi thọ khác nhau. Lý do sư phạm — sai ba lần cùng một dạng thì em cần người,
không cần thêm bài — đứng yên. Chi phí sinh câu hỏi thì đổi khi giá model đổi, và một ADR nghiệp vụ
không phải chỗ cho con số sẽ trôi. Ghi ở đây để người sau biết rằng nới trần lên bốn là **được phép**
nếu lý do duy nhất còn lại là tiền, và **không được phép** nếu nó chạm vào lý do sư phạm.

### Decision: Không sửa bảng Invariants của `AGENTS.md` đợt này

options considered: chỉnh lời ba dòng ngay; để nguyên và ghi nợ.

selected option: để nguyên, ghi nợ.

reason: ba dòng đó (`AGENTS.md:50-52`) nay đều lệch với mô hình — *Teacher approves an assessment
before release* có ngoại lệ chưa ghi, *A low-confidence result is not shown to the Student* không còn
instance nào sau khi bỏ confidence của chẩn đoán, và *Practice questions keep the same learning
objective* nay yếu hơn sự thật. Nhưng sửa lời chúng buộc phải quét cả bốn `AGENTS.md` con và
`CLAUDE.md`, và câu chữ đúng phụ thuộc vào một quyết định chưa có: câu luyện tập có qua cổng duyệt hay
không. Sửa bây giờ là viết một lời sẽ phải sửa lại.

## Status

Đã xong. `docs/overview/` và `docs/diagrams/` được đưa về khớp ở đợt kế tiếp:
`2026-09-10-two-phase-diagrams-plan.md`.

---

**Đóng ngày 2026-09-30** khi dọn `docs/plans/active/`. Người dùng xác nhận đã hoàn thành. Các ô kiểm
chứng máy móc được chạy lại tại thời điểm đóng: `.\dev.ps1 check` xanh 5/5. Những ô cần một người
xác nhận — vòng subagent review, manual test trên trình duyệt — tick theo xác nhận đó, và bằng chứng
là lời xác nhận ấy chứ không phải một lần chạy tôi quan sát được.
