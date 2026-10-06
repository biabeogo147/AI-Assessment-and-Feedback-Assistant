# ADR-02 — Chỉ giáo viên phát hành, và phát hành có cửa sổ thu hồi

- **Trạng thái:** đã mở rộng bởi ADR-15
- **Ngày:** 2026-09-06

## Bối cảnh

`docs/overview/business-workflows.md` dòng 57 ghi *"Hệ thống phát hành đề cho Student"*, và diagram vẽ
hành động đó bằng màu cam — theo legend là *hành vi hệ thống bắt buộc*. Thiết kế thực tế thì ngược lại.

Đồng thời, suốt quá trình thiết kế, phát hành được coi là hành động **tuyệt đối** không thu hồi được.
Điều đó không đúng: một đề đã phát hành nhưng **chưa tới giờ mở** thì chưa ai chạm vào được.

## Quyết định

- **Chỉ giáo viên phát hành.** Hệ thống không bao giờ tự phát hành đề cho học sinh.
- Phát hành bắt buộc **sáu** tham số: **lớp** (chỉ chọn được lớp đã tạo trước), **thời gian làm bài**,
  **giờ mở**, **giờ đóng**, **số phút mỗi câu ở pha 2** và **hạn kết thúc pha 2**. Hai tham số cuối do
  [ADR-15](adr-15-thoi-gian-pha-hai.md) thêm vào. Vì cần sáu thứ, phát hành là một **biểu mẫu**, không
  phải câu hỏi có/không.
- **Thu hồi được cho tới hết giờ mở**, bao gồm cả đúng thời điểm đó. Sau giờ mở — khi học sinh đã có
  thể vào làm — phát hành trở thành không đảo ngược được.
- Thu hồi đưa đề về **đã duyệt**, không về nháp. Nội dung vẫn khoá; chỉ cài đặt phát hành bị gỡ.
- **Giờ mở phải ở tương lai** so với lúc bấm phát hành, và phải trước giờ đóng. Không có ràng buộc này
  thì cửa sổ thu hồi dài không giây nào mà chẳng ai vi phạm luật gì.
- Hộp xác nhận **đọc lại đúng giá trị vừa nhập**, không dùng con số ghi cứng.
- Phát hành có thể **thất bại một phần**: một lớp nhận được đề, lớp khác không.

## Vì sao

Đề kiểm tra ảnh hưởng trực tiếp tới đánh giá học sinh, nên quyền phát hành không thể nằm ở hệ thống.

Cửa sổ thu hồi tồn tại vì **một sai lầm bị bắt trước khi có ai vào làm thì không tốn gì cả**. Cấm thu
hồi trong khoảng đó là nghiêm khắc mà không bảo vệ ai.

Ranh giới đặt ở **giờ mở** chứ không phải lúc bấm nút, vì thứ làm cho hành động không đảo ngược được là
**học sinh đã có thể nhìn thấy đề**, không phải thao tác của giáo viên.

Hộp xác nhận đọc lại giá trị thật làm cổng **mạnh lên**: nó nói lại con số giáo viên vừa chọn, thay vì
một con số dựng sẵn.

## Hệ quả

- Câu *"Sau khi phát hành, bạn không sửa và không thu hồi đề được nữa"* trong hộp xác nhận **đang sai**
  và phải viết lại thành một hạn thu hồi cụ thể. Cổng xác nhận vì thế **nhẹ đi**: nó không còn nói
  "vĩnh viễn", nên phải nói cho đúng khoảnh khắc nào mới thành vĩnh viễn.
- Thẻ `đã-phát-hành` cần hành động **Thu hồi** khi chưa tới giờ mở, và mất nó khi đã qua.
- Cần phân biệt hai trạng thái con: *đã phát hành, chưa mở* và *đã mở*. ADR-01 chưa có hai trạng thái
  này và sẽ phải mở rộng.
- Thất bại một phần cần trạng thái riêng và phải nói rõ lớp nào đã nhận bản ghi phát hành — với những
  lớp đó, thu hồi vẫn được nếu chưa qua giờ mở.
- Chiều cao khối chọn lớp **phải bị chặn**: chọn chín lớp mà khối phình ra sẽ đẩy danh sách câu hỏi
  xuống dưới chiều cao một thẻ, tức là làm hỏng chính cổng này. Luật này **khó hơn** kể từ ADR-15:
  biểu mẫu dài thêm hai trường ngay cả khi chưa chọn lớp nào, nên phần dư để co giãn đã hẹp lại.
- Mọi diagram vẽ phát hành nằm trong lane hệ thống đều sai và phải chuyển sang lane Teacher.

## Nơi luật này đang được thi hành

- **Chip lớp trên biểu mẫu phát hành mang `aria-pressed`** (từ 06/10/2026). Việc chọn lớp là
  tham số **thứ nhất** trong sáu, và là tham số quyết định ai nhận đề — nhưng nút ấy từng chỉ nói
  ra trạng thái của mình bằng màu và một dấu ✓ đã `aria-hidden`, nên trình đọc màn hình đọc
  *"12A, button"* y hệt dù đã chọn hay chưa. Một luật về *ai* nhận đề mà người dùng không biết
  mình vừa chọn ai thì không có cổng nào cả.

- `services/be/src/be/models.py` — `Publication` có khoá chính **kép** `(assessment_id, class_id)`,
  nên một đề phát hành được cho nhiều lớp và **thu hồi được từng lớp một**: `recalled_at` của 12B
  không đụng tới 12A. Tham số **thứ nhất** trong sáu tham số ở mục trên là **lớp**, và ở bảng này
  nó là nửa còn lại của khoá chứ không phải một cột cài đặt. Đây là thứ làm cho điều khoản
  *phát hành có thể thất bại một phần* ở mục **Quyết định** trở nên **biểu diễn được**: trước đó model
  chỉ giữ nổi một bộ hạn cho một đề, nên "một lớp nhận được, lớp khác không" không có chỗ để tồn tại.

  **Sửa đổi 06/10/2026 — một lần phát hành, một khung giờ.** Bản đầu của ADR này cho mỗi lớp một
  bộ năm cài đặt riêng, với lý lẽ *12A học tiết sáng, 12B học sau trưa*. Lý lẽ ấy chưa bao giờ
  được dựng: biểu mẫu phát hành chỉ có **một** bộ ô nhập và vẫn luôn gửi cùng một bộ giá trị cho
  mọi lớp. Hợp đồng cũ vì thế cho phép diễn tả một thứ không màn hình nào dựng được, và cái giá
  là thật — hộp xác nhận phải hứa thu hồi được *"cho tới giờ mở của từng lớp"* cho một con số
  chung, tức một mốc mà giáo viên không đọc ra nổi là mốc nào. `PublishRequest` nay là một
  `Schedule` cộng `class_ids`. Muốn hai lớp hai đồng hồ thì phát hành hai lần — và bảng vẫn chở
  được điều đó, vì khoá kép không đổi.
- `services/be/src/be/teacher_routes.py` — `POST /api/teacher/assessments/{id}/publications` nhận
  **một khung giờ cùng một danh sách lớp**, nên điều khoản *phát hành có thể thất bại một phần* là
  một hàng trong kết quả chứ không phải một ngoại lệ. Cái **cớ** để một lớp hỏng đã đổi cùng với
  sửa đổi ở trên, còn luật thì không: một khung giờ sai làm **mọi** lớp trượt — đúng câu trả lời
  đúng — nhưng một lớp của giáo viên khác (ADR-22), một lớp đã qua giờ mở, hay một lớp đang có
  người làm bài thì vẫn hỏng riêng nó và những lớp còn lại vẫn nhận được đề. Ba điều kiện giờ được
  kiểm riêng từng cái — giờ mở ở tương lai, trước giờ đóng, và hạn pha 2 sau giờ nộp cuối của pha 1
  — vì một câu từ chối chung buộc giáo viên đoán xem cái nào sai trong những con số họ vừa gõ.
- `services/be/src/be/teacher_routes.py` — `POST .../publications/{class_id}/withdraw` là nơi cửa sổ
  thu hồi được thi hành, qua `may_withdraw(opens_at, now)`. Thu hồi **mềm**: hàng ở lại với
  `recalled_at` đã đặt, vì `published_at`/`recalled_at` là sổ sách. Đề chỉ về **đã duyệt** khi không
  lớp nào còn giữ nó — thu hồi 12B trong lúc 12A đang làm thì đề vẫn đang phát hành.
- `services/be/src/be/teacher_routes.py` — `_take_back_every_class` là đường lùi **trọn vẹn**, dùng
  bởi `POST .../unapprove` khi đề đang ở `đã phát hành` (từ 06/10/2026). Nó thu hồi mọi lớp rồi hạ
  state, và nó **hoặc tất cả hoặc không gì cả**: một lớp đã qua giờ mở thì cả thao tác dừng lại,
  kèm một câu từ chối **gọi tên lớp** ấy. Để lại một đề nửa thu hồi nửa không là để lại đúng cái
  trạng thái không màn hình nào đọc ra nổi, trong khi giáo viên tin rằng mình đã hoàn tác.

  Trước đợt ấy đường này trả 409 với lý lẽ *"thu hồi trước đã"* — mà màn hình vẫn vẽ nút `Hoàn
  tác`, và `Panel` nuốt mất câu 409, nên cú bấm không làm gì và **không nói gì**. Lý lẽ ấy cũng
  bắt giáo viên làm hai việc cho một ý định: muốn sửa một đề đã phát hành thì đường duy nhất là
  hoàn tác, nên bắt họ thu hồi từng lớp trước là bắt họ tự dựng lại một thao tác mà hệ thống biết
  cách làm trọn. `_ALLOWED[PUBLISHED]` vẫn để **rỗng**: cửa duy nhất xuống từ `đã phát hành` vẫn
  là `withdraw`, thao tác có tên tự chở điều kiện của nó. Luật không nới ra, chỉ có thêm một
  caller biết cách đi qua nó cho đúng.
- `services/be/src/be/assessment_state.py` — `_ALLOWED[PUBLISHED]` để **trống**, và `withdraw()` là
  thao tác có tên duy nhất đi vòng qua bảng cạnh. Lý do: cạnh `đã phát hành → đã duyệt` có **điều
  kiện**, nên để nó thành một hàng vô điều kiện sẽ cho bất kỳ caller tương lai nào quên kiểm giờ thu
  hồi được một bài học sinh đang ngồi làm.
- `services/be/src/be/student_routes.py` — một hàng đã thu hồi đọc lên **y như chưa bao giờ phát
  hành**, ở cả hai cửa: `_publication()` và câu query liệt kê bài được giao. Thiếu nửa này thì thu
  hồi chỉ đổi một cột mà không đổi gì học sinh thấy.
- `services/be/src/be/teacher_routes.py` — một đề **đã phát hành** vẫn nhận thêm lớp được, vì ADR này
  nói *một đề đi tới nhiều lớp* chứ không nói *trong một request*. Cái giá là một phép kiểm phải đi
  kèm: `_already_running()` từ chối ghi đè cài đặt của một lớp **đã qua giờ mở** hoặc **đã có bài
  làm** — nếu không thì việc nới cổng mở một đường đi vòng qua chính cửa sổ thu hồi, bằng cách đặt
  `recalled_at = None` cộng một giờ mở mới ở tương lai.
- `services/be/src/be/teacher_routes.py` — `ClassSchedule` dùng `AwareDatetime`, và `_publish_one`
  chuẩn hoá về UTC trước khi ghi. Không có hai thứ đó thì một giờ gửi kèm offset địa phương bị lưu
  mất offset trên SQLite (lệch bảy giờ ở Việt Nam) và một giờ naive bị đoán là UTC — cả hai âm thầm,
  và hộp xác nhận **che** chúng vì nó đọc lại đúng chuỗi vừa gõ.
- `services/be/src/be/publication_wording.py` — ba câu luật, mỗi câu một hằng số, trả về ở **cả ba**
  payload: lúc mở biểu mẫu, lúc xem trước để xác nhận, và trong biên bản. Hộp xác nhận đọc lại giá
  trị thật vì `preview` đi qua **đúng** đoạn code mà lần ghi thật đi qua.
- `services/be/tests/test_publishing.py` — hai mươi ba test, tất cả qua HTTP. Bảy call site được kiểm
  bằng cách phá từng cái rồi xem test nào đỏ.
- `services/be/src/be/models.py` — `Attempt.class_id` ghi lớp lúc bắt đầu làm bài, vì "hạn của đề
  này" nay là một câu hỏi có nhiều câu trả lời và bài làm phải nói nó theo bộ nào.
- `services/be/tests/test_multi_class_publication.py` — năm test: một đề giữ hai bộ hạn; mỗi lớp đọc
  đồng hồ của mình và nhận `status` khác nhau ở cùng một thời điểm; bài làm nhớ lớp đã bắt đầu;
  chuyển lớp **không** khoá học sinh khỏi bài đang làm (ADR-03: *đã vào rồi thì không bị dừng giữa
  chừng*); và hạn pha 2 đi theo bài làm chứ không theo lớp hiện tại của học sinh — revert đúng một
  call site làm hạn ấy nhảy mười hai tiếng, nên test này có răng chứ không chỉ có tên.
- Figma `mOe2ZmrqOq1Uix45v6PNGD`, `Publish settings` (`67:41`) — **sáu** trường, nhóm theo hai pha,
  cả hai variant; mô tả component ghi luật chặn chiều cao.
- Figma `Consequence dialog` (`11:41`) — khối đọc lại **sáu** giá trị.
- Figma `Action result card` (`10:63`) — variant `đã-phát-hành`, `phát-hành-thất-bại`.
- Figma artboard `1 · Bắt đầu`: *"Kriky sẽ tạo lớp, soạn đề, thêm câu hỏi — nhưng chỉ bạn mới phát hành
  được đề cho học sinh."*
- `docs/diagrams/business-workflows.drawio` — `t-publish` nằm trong **lane Teacher**. Điều khoản
  *mọi diagram vẽ phát hành nằm trong lane hệ thống đều sai* ở mục **Hệ quả** trước đây chưa từng
  được thi hành: node này vốn nằm giữa lane System/AI, và ba node khác bị gắn `parent` sai lane. Nay
  mọi node dùng toạ độ tuyệt đối nên vị trí không lệch khỏi lane được nữa.
- **Cửa sổ thu hồi: mới thi hành một nửa.** Câu *"không sửa và không thu hồi đề được nữa"* — thứ mục
  *Hệ quả* ở trên tuyên là sai — đã bị thay ở **cả ba** chỗ nó xuất hiện: `Consequence dialog`
  (`11:41`), `Action result card` variant `đã-phát-hành` (`10:45`), và variant
  `phát-hành-thất-bại` (`76:23`), nơi nó còn mâu thuẫn thẳng với luật thất bại một phần ở trên.
  Thẻ `đã-phát-hành` nay có hành động **Thu hồi**.
- **Nửa chưa thi hành:** nút Thu hồi phải **mất đi khi đã qua giờ mở**, và `Action result card`
  (`10:63`) không có trục trạng thái *chưa mở* / *đã mở* nên nút luôn hiện. Đừng đọc thẻ đó như bằng
  chứng rằng thu hồi lúc nào cũng được. Xem `docs/plans/backlog.md`.
- **Chưa có ở backend:** không đường nào **đọc lại** sáu tham số đã đặt cho một lớp, và
  `ClassOption` của biểu mẫu chỉ nói lớp đó đã giữ đề hay chưa — không nói còn thu hồi được không.
  Nên điều khoản *nút Thu hồi mất đi khi đã qua giờ mở* ở mục **Hệ quả** vẫn chưa làm được mà không
  bắt FE tự so đồng hồ, tức tự cài lại `may_withdraw`. Xem `docs/plans/backlog.md`.
