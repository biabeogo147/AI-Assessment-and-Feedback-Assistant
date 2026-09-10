# ADR-10 — Phạm vi đợt đầu: chỉ giáo viên, chỉ desktop, chat là dòng lệnh

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-06

## Bối cảnh

`docs/overview/` mô tả một sản phẩm có hai actor và năm workflow, phủ cả vòng học sinh làm bài, nhận
feedback và luyện tập thích ứng. Thiết kế thực tế của đợt đầu chỉ dựng **nửa đầu** của vòng đó.

Không tài liệu nào nói ra ranh giới này, nên người đọc `docs/overview/` sẽ tưởng cả năm workflow đều
đang được xây.

## Quyết định

- Đợt đầu **chỉ thiết kế cho giáo viên**. Mọi màn hình học sinh nằm ngoài phạm vi thiết kế. Bề mặt
  học sinh duy nhất đang tồn tại là màn hình demo `services/fe/src/App.tsx`, cố ý không phải trải
  nghiệm thật.
- Sản phẩm là **web dùng trên desktop**. Không thiết kế cho mobile.
- **Chat là dòng lệnh**, không phải nơi chứa vật thể quan trọng. Vật thể có hệ quả — đề kiểm tra, cài
  đặt phát hành — sống trong **panel bên phải**.
- **Luật *chat là dòng lệnh* chỉ áp cho bề mặt giáo viên.** Ở pha 2
  ([ADR-14](adr-14-hai-pha-lam-bai.md)), cuộc hội thoại giữa Kriky và học sinh **chính là nội dung
  học** — nó là thứ có giá trị nhất trên màn hình, không phải một dòng lệnh trôi qua. Bề mặt học sinh
  chưa được thiết kế, nên ADR này **không** nói trước bố cục của nó; nó chỉ chặn việc thừa kế nhầm
  một lý lẽ.
- Nút Phát hành **không bao giờ** xuất hiện trong luồng chat. Luật này thuộc
  [ADR-05](adr-05-ba-cong-teacher-in-the-loop.md); nhắc lại đây vì nó là hệ quả trực tiếp của việc
  chat là dòng lệnh.

## Vì sao

Chỉ giáo viên, vì cả hai cổng teacher-in-the-loop ở đầu ra đều nằm ở phía giáo viên. Xây phía học sinh
trước khi phía giáo viên chạy được nghĩa là xây một luồng chưa ai kiểm soát được.

Desktop, vì giáo viên soạn đề khi ngồi máy, và màn hình phải chứa đồng thời hội thoại lẫn danh sách
mười câu hỏi. Trên điện thoại, một trong hai phải biến mất, và mất cái nào cũng làm hỏng bước duyệt.

Chat là dòng lệnh, vì **duyệt một đề mười câu trong bong bóng chat sẽ thành duyệt lấy lệ**. Bong bóng
chat trôi đi, panel thì đứng yên và cuộn được. Đặt nút Phát hành trong luồng chat sẽ khiến hành động
không thu hồi được nằm cạnh những dòng chữ trôi qua.

## Hệ quả

- Nửa sau của vòng nghiệp vụ — chấm bài, feedback, mastery, luyện tập thích ứng — **có tài liệu và có
  code nhưng không có thiết kế**. Mọi mâu thuẫn giữa hai nửa sẽ chỉ lộ ra khi dựng màn hình học sinh.
- Không có bề mặt học sinh nào **được thiết kế** nghĩa là luật *"kết quả low-confidence không hiện cho
  học sinh"* (ADR-08) chưa có chỗ nào để làm cho đúng. Màn hình demo `App.tsx` hiện đang phá luật đó,
  và sẽ còn phá cho tới khi màn hình thật được dựng.
- Chọn desktop-only khiến mọi component được dựng theo mật độ Teacher. Khi làm mobile, không phải thu
  nhỏ mà phải thiết kế lại quan hệ giữa chat và panel.
- Luật panel nghĩa là mọi hành động có hệ quả mới trong tương lai đều phải tìm chỗ trong panel, kể cả
  khi đặt vào chat thì tiện hơn.
- Vì cùng một widget mang hai vai trò trái ngược ở hai bề mặt, **mọi component chat dùng lại cho học
  sinh phải được kiểm lại từng luật một**. Dùng lại hình dạng thì được; dùng lại lý lẽ thì không.

## Nơi luật này đang được thi hành

- Figma `mOe2ZmrqOq1Uix45v6PNGD`, trang `Screen — Chat` — mười một artboard, tất cả **1440×900**, tất cả chạy Density mode
  `Teacher`, và không artboard nào có bề mặt học sinh.
- Figma `Publish settings` (`67:41`) và `Consequence dialog` (`11:41`) — nút phát hành chỉ tồn tại ở
  hai chỗ này, không ở `Action result card` nào trong luồng chat.
- `AGENTS.md` bảng Invariants — hai trong ba dòng ở nhóm **chưa enforce** (low-confidence với học sinh,
  luyện tập giữ nguyên learning objective) thuộc nửa sau của vòng nghiệp vụ. Dòng thứ ba, *Teacher
  approves an assessment before release*, thuộc nửa đầu và chờ UC-02.
