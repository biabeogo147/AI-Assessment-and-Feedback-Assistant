# Cửa nộp bài, khung cuộn, và một lượt gọi model bỏ đi được

## Goal

Năm sửa chữa trên bề mặt học sinh, gom một đợt vì chúng đụng cùng những file: một cổng trước cửa
nộp bài, ba khung cuộn độc lập thay cho một trang cuộn chung, và câu chào của trợ lý thôi tốn tiền.

## Scope

**Trong:** hộp xác nhận nộp bài; cuộn trong panel và trong khung chat; header dính khi cuộn; câu mở
đầu do BE viết chứ không hỏi model; prompt đổi xưng hô.

**Ngoài:** bề mặt giáo viên — đợt sau.

## Năm việc

### 1. Cửa một chiều thứ hai có cổng

`backlog.md` đã ghi nợ này: học sinh có **ba** cửa một chiều — bắt đầu làm bài, nộp bài, mở lượt
chữa — và chỉ cửa thứ ba có cổng. Cửa nộp bài đáng có nhất trong hai cửa còn lại, vì dải nhảy câu
đã đếm sẵn con số mà hộp xác nhận cần đọc lại.

Hộp đọc lại **giá trị thật** chứ không phải con số ghi cứng, cùng nguyên tắc
[ADR-02](../../decisions/adr-02-phat-hanh-va-cua-so-thu-hoi.md) dùng cho hộp xác nhận phát hành. Và
nó phải nói đúng cái hậu quả không lùi được: nộp là hết pha 1, điểm lúc đó thành **điểm sàn**
([ADR-14](../../decisions/adr-14-hai-pha-lam-bai.md), [ADR-16](../../decisions/adr-16-thang-diem-ba-muc.md)).

### 2 & 3. Ba khung cuộn, không phải một trang cuộn

Hôm nay `.split` cao `min-height: 100vh - 57px` và cả trang cuộn. Nhiều câu sai thì panel đẩy dài
toàn trang, và để đọc thẻ cuối cùng học sinh phải cuộn cả khung chat đi mất.

Đổi thành: `.split` cao **đúng** một màn hình và không cuộn; bên trong, hai vùng cuộn riêng —
danh sách thẻ trong panel, và dòng hội thoại trong khung chat. Thanh nhập và ô tiến độ **không**
cuộn theo: chúng là chỗ để hành động, không phải nội dung để đọc.

### 4. Header dính, mọi lúc

`position: sticky` trên `.topbar`. Ở các màn cuộn cả trang (danh sách, kết quả) nó dính theo tài
liệu; ở màn chia đôi thì trang vốn không cuộn nên nó đứng yên sẵn.

### 5. Câu chào không gọi model

Hôm nay lượt mở đầu đi qua đúng đường như mọi lượt khác: bắn job, đợi model, stream về. Để sinh ra
một câu gần như cố định. **Một lượt gọi model lãng phí trên mỗi bài làm.**

BE tự viết câu ấy và lưu thẳng. Phần duy nhất thay đổi giữa hai học sinh là danh sách số câu sai,
và đó là phép nối chuỗi, không phải việc của model.

Prompt đổi xưng hô: trợ lý xưng **"mình"**, gọi người đối diện là **"bạn"** — không phải "em".

## Files

| File | Việc |
| --- | --- |
| `services/fe/src/screens/Sitting.tsx` | hộp xác nhận nộp bài |
| `services/fe/src/screens/Tutor.tsx` | bọc dòng hội thoại vào một vùng cuộn |
| `services/fe/src/tokens.css` | `.split` cao cố định, `.thread`/`.panel-cards` cuộn, `.topbar` dính |
| `services/be/src/be/student_routes.py` | `_greeting()` và nhánh lượt mở đầu |
| `services/agent/src/agent/graphs/explain.py` | xưng hô trong prompt |
| `services/agent/src/agent/handlers.py` | xưng hô trong nội dung soạn sẵn |
| Figma `Screen — Student` | artboard mới cho hộp nộp bài; sửa lời chào ở `17` và `24` |

## Ordered Tasks

- [x] BE viết câu chào, không bắn job cho lượt mở đầu
- [x] Prompt và nội dung soạn sẵn đổi sang "bạn"
- [x] `.split` cao đúng một màn hình; `.thread` và `.panel-cards` cuộn riêng; `.topbar` dính
- [x] Hộp xác nhận nộp bài, đọc lại số câu chưa trả lời
- [x] Figma: artboard hộp nộp bài, và lời chào mới trên `17`, `24`
- [x] `dev.ps1 check` + pytest + vitest + tsc
- [x] Gọi 1 subagent review
- [x] Manual test trên trình duyệt theo kịch bản 11 bước

## Validation Checks

- `.\dev.ps1 check` · `pytest services packages -q` · `vitest run` · `tsc --noEmit`
- Một test khoá lại rằng lượt mở đầu **không** chạm hàng đợi — đây là phần tiết kiệm, và nó sẽ bị
  một lần dọn dẹp vô tình xoá mất nếu không có gì canh.
- Đo bằng số đo, không bằng mắt: `.split` đúng `100vh - 57px`, `.thread` và `.panel-cards` có
  `overflow-y: auto`, tài liệu không cuộn ngang.

## Ghi chú khi làm

**Đánh số Figma dịch đi một bậc.** Hộp nộp bài nằm giữa `14 · Làm bài` và màn kết quả theo luồng
nghiệp vụ, nên nó là `15` và mười artboard sau đó lên một số: cũ `15…24` thành `16…25`. Giữ đúng
luật thứ tự luồng đã chốt, thay vì thêm vào cuối cho tiện.

**Hộp nộp bài không phải một `Round gate`.** Nó mượn hình dạng của cổng mở lượt, nên tôi nhân bản
rồi **tách khỏi component** — vừa vì Figma không cho thêm con vào instance, vừa vì nói nó là một
`Round gate` thì sai: hai cổng khác nhau, chỉ giống nhau ở dáng.

**Xưng hô đổi có ranh giới.** Trợ lý gọi người đối diện là "bạn". Nhưng `Em đã chọn` trên thẻ panel
thì giữ nguyên — đó là **app nói về** học sinh, không phải **trợ lý nói với** họ. Hai giọng khác
nhau, và đổi nhầm sẽ lệch với thiết kế.

**Luật cuộn không vào được Figma.** Frame không có `description`, chỉ component mới có; và artboard
tĩnh thì không vẽ được hành vi cuộn. Luật header dính vào đúng chỗ của nó — mô tả component
`Student top bar`. Luật cuộn ở lại `tokens.css` và plan này, vì nó không thuộc component nào.

## Status

Xong phần code và Figma, chờ review rồi manual test.

---

**Đóng ngày 2026-09-30** khi dọn `docs/plans/active/`. Người dùng xác nhận đã hoàn thành. Các ô kiểm
chứng máy móc được chạy lại tại thời điểm đóng: `.\dev.ps1 check` xanh 5/5. Những ô cần một người
xác nhận — vòng subagent review, manual test trên trình duyệt — tick theo xác nhận đó, và bằng chứng
là lời xác nhận ấy chứ không phải một lần chạy tôi quan sát được.
