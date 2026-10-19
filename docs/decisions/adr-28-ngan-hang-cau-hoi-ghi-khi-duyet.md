# ADR-28 — Ngân hàng câu hỏi nhận câu lúc giáo viên duyệt đề

- **Trạng thái:** đã chốt, đang thi hành (đường ghi; đường đọc chưa có)
- **Ngày:** 2026-10-13

## Bối cảnh

ADR-04 chốt câu hỏi của một đề có hai nguồn: ngân hàng câu hỏi, hoặc Kriky soạn mới. Tới ngày
13/10/2026 nguồn thứ nhất **không tồn tại**: không bảng nào chứa nó, không đường nào ghi vào nó. Panel
đề vẫn in *"N câu ngân hàng"* và chip *"Lấy từ ngân hàng câu hỏi"*, nhưng đó là chữ bịa chọn theo hash
id. Trước khi có đường nào **rút** câu từ ngân hàng ra, phải có đường **ghi** câu vào -- và phải quyết
câu nào được vào, vào lúc nào, thuộc về ai.

Cùng lúc, ADR-04 đòi mỗi câu Kriky soạn mang một trạng thái kiểm riêng do giáo viên chuyển bằng tay.
Trạng thái ấy chưa từng được dựng, và một ngân hàng thì cần biết câu nào **đã kiểm**. Hai câu hỏi phải
trả lời cùng nhau.

## Quyết định

- **Duyệt đề là giáo viên đã kiểm mọi câu trong đề** -- cả đề bài, phương án, lời giải và ánh xạ
  nhiễu, đúng phần nội dung mà duyệt khoá lại (ADR-01, ADR-18). Không có thao tác đánh dấu đã kiểm
  cho từng câu. Một câu trong đề là *chưa kiểm* khi đề chưa duyệt, và *đã kiểm* khi đề đã duyệt; bỏ
  duyệt đưa mọi câu trong đề về *chưa kiểm*. ADR-04 được sửa theo (hậu ký 13/10/2026).
- **Câu vào ngân hàng lúc đề được duyệt**: lần duyệt chép mọi câu của đề vào ngân hàng, cùng một giao
  dịch với việc khoá nội dung. Không chờ tới lúc phát hành.
- **Mỗi giáo viên một ngân hàng riêng.** Ngân hàng của người khác đọc ra như không tồn tại, như đề và
  lớp (ADR-22).
- **Ngân hàng giữ bản chép, không giữ tham chiếu.** Bản trong ngân hàng sống tiếp khi câu trong đề đổi
  hay mất.
- **Bỏ duyệt không đụng tới ngân hàng.** Bản trong ngân hàng vẫn là bản đã kiểm của lần duyệt trước,
  dù câu trong đề đã về *chưa kiểm*. **Duyệt lại thì ghi đè** bản của từng câu bằng nội dung lúc duyệt
  lại: mỗi câu trong đề có nhiều nhất một bản trong ngân hàng.
- **Xoá một câu khỏi đề không xoá nó khỏi ngân hàng.** Bản trong ngân hàng ở lại, chỉ thôi trỏ về câu
  đã xoá. Xoá chỉ làm được khi đề chưa duyệt, và không bao giờ đổi trạng thái của đề: câu cuối cùng
  của đề không xoá được.
- **Bấm xoá luôn mở hộp thoại xác nhận, không xoá ngay.** Khi câu đã có bản trong ngân hàng, hộp thoại
  nói rõ bản ấy ở lại; khi chưa có, hộp thoại nói câu sẽ mất hẳn.
- **Xoá xong, các câu sau dồn số lên**: đề mười câu xoá câu 4 thì còn câu 1 tới 9.
- Câu luyện tập pha 2 không qua duyệt, nên không vào ngân hàng.

## Vì sao

**Duyệt là đã kiểm.** Dấu kiểm riêng từng câu của ADR-04 chưa bao giờ tồn tại; chữ *"đã kiểm"* trên
màn hình là chữ bịa. Cổng duyệt thì có thật, và đã mang gần đúng nghĩa ấy: BE từ chối duyệt khi còn
câu đang soạn, với lý do *"để bạn duyệt đúng những câu mình đã đọc"*; và duyệt khoá nội dung, tức giáo
viên nhận trách nhiệm cho cả đề (ADR-01). Đây là một đổi chác có chủ ý: nhận một nghĩa **yếu hơn** --
một cú bấm cho cả đề -- để có một nghĩa **thật**, thay vì giữ một nghĩa mạnh mà không gì thi hành.

**Vào lúc duyệt, không lúc phát hành**, vì ngân hàng là kho câu đã kiểm, và việc kiểm xảy ra lúc
duyệt. Chờ phát hành thì một đề đã duyệt mà chưa giao lớp nào không đóng góp câu nào, dù không thiếu
gì về độ tin cậy.

**Bản chép**, vì đề và ngân hàng có hai vòng đời khác nhau. Đề đã khoá thì nội dung đứng yên, còn bản
trong ngân hàng phải sửa được -- vòng của ADR-19 (*"giáo viên sửa lời giải đã lưu, ngân hàng câu hỏi
tốt lên"*) cần đúng việc ấy. Một ngân hàng chỉ là phép truy vấn trên các đề đã duyệt thì mất câu khi
đề bị bỏ duyệt, và hiện một câu hai lần khi nó được lấy lại sang đề mới.

**Duyệt lại ghi đè**, vì lần duyệt gần nhất là lần kiểm gần nhất. Giáo viên bỏ duyệt thường để sửa một
chỗ sai; giữ bản cũ bên cạnh là giữ chỗ sai trong kho, cạnh bản đã sửa, gần giống nhau tới mức đường
đọc sau này không phân biệt được.

**Xoá trong đề không xoá ngân hàng**, vì hệ thống không phân biệt được hai lý do xoá. Giáo viên có thể
bỏ một câu vì nó sai, hoặc chỉ vì đề quá dài, hai câu cùng ý; cú bấm Xoá trông như nhau ở cả hai ca.
Câu ấy **đã** được kiểm một lần, nên giữ lại là phía không mất gì: một câu thừa trong kho rẻ hơn một
câu tốt biến mất. Hộp thoại có mặt để cái giá của lựa chọn ấy hiện ra -- không có nó, giáo viên tin
rằng mình vừa xoá câu khỏi mọi nơi.

**Xoá không đổi trạng thái của đề**, vì ADR-01 chỉ riêng **bỏ duyệt** ra là thao tác duy nhất hạ một
trạng thái xuống. Cho xoá câu cuối đưa đề về *trống* là thêm thao tác hạ trạng thái thứ hai, đi vòng
qua đúng chỗ ADR-01 đã canh. Giáo viên muốn làm lại cả đề thì ra yêu cầu mới; đề vẫn còn câu cho tới
khi câu mới về.

**Dồn số**, vì số câu là thứ học sinh và giáo viên cùng nhìn thấy, và cùng dùng để gọi tên câu
(*"câu 4 sai"*). Một lỗ trong dãy số đọc ra như một câu bị mất, và lần soạn thêm sau sẽ nối tiếp sau
cái lỗ ấy.

**Riêng từng giáo viên**, vì câu vào ngân hàng qua lần duyệt của một giáo viên -- người nhận trách
nhiệm cho nó (ADR-01) -- và đề chứa nó có đúng một tác giả (ADR-22). Một ngân hàng chung cần một luật
*ai kiểm câu của người khác* mà chưa ai quyết.

## Hệ quả

- **"Đã kiểm" yếu đi một bậc.** Một cú bấm khẳng định cả đề, kể cả khi giáo viên chỉ lướt qua, và ngân
  hàng tin cú bấm ấy. Dòng tổng *"x câu thêm mới đã kiểm · y câu chưa kiểm"* dưới tên đề bị gỡ, vì
  sau luật này nó không còn đếm điều gì.
- **Một câu sai mà giáo viên xoá khỏi đề vẫn nằm trong ngân hàng**, và chưa có đường gỡ nó khỏi ngân
  hàng: chưa có màn ngân hàng nào. Hộp thoại xoá nói ra điều này, nhưng không chữa được.
- **Ghi đè sẽ va với việc sửa trong ngân hàng.** Khi có đường sửa bản trong ngân hàng (vòng ADR-19),
  một lần duyệt lại đề gốc sẽ lặng lẽ ghi đè bản đã sửa ấy. Phải quyết lúc dựng đường sửa: bản sửa
  trong ngân hàng thôi trỏ về câu gốc, hay lần duyệt lại hỏi trước.
- **"Câu đã có bản trong ngân hàng" không phải nguồn "Lấy từ ngân hàng câu hỏi".** Câu đầu là câu
  Kriky soạn đã từng được duyệt và chép vào kho; câu sau là câu rút **từ** kho ra. Hai thứ dễ lẫn vì
  cùng chữ *ngân hàng*.
- **Ngân hàng chưa phải một nguồn thật** cho tới khi có đường đọc. Khi có: một câu lấy từ ngân hàng
  sang đề mới, lúc đề ấy được duyệt, không được sinh thêm một bản trùng.
- **Câu luyện tập pha 2 vẫn không ai kiểm**, như ADR-04 đã ghi. Ngân hàng mở ra một đường bịt lỗ ấy --
  *câu luyện tập chỉ lấy từ ngân hàng* (`docs/plans/backlog.md`) -- nhưng chưa ai chọn đường đó.

## Nơi luật này đang được thi hành

Dựng ở plan `2026-10-13-question-bank-write-path-plan.md`.

- **Bảng:** `packages/schema/src/schema/models.py` -- `BankQuestion` (`bank_questions`): `teacher_id`
  có index, `question_id` unique, nullable, `ondelete="SET NULL"`.
- **Duyệt chép vào ngân hàng, cùng commit:** `services/be/src/be/question_bank.py` `file_approved`,
  gọi trong route duyệt (`teacher_routes.approve`) ngay trước commit ghi `state`, và trong `seed.py` cho đề seed
  đã phát hành. Test ở `services/be/tests/test_approval.py`: mỗi câu một dòng, đúng giáo viên; duyệt
  lại ghi đè mọi phần của câu và giữ `created_at`; hai giáo viên không lẫn; duyệt bị từ chối không ghi
  gì; câu thu hoạch ngay trong request duyệt; đề seed.
- **Xoá trong đề không xoá ngân hàng; xoá không đổi trạng thái; dồn số:** route
  `DELETE /api/teacher/assessments/{id}/questions/{qid}` (`teacher_routes.delete_question`), gọi
  `question_bank.release` trước khi xoá. Test ở `services/be/tests/test_delete_question.py`, SQLite bật
  khoá ngoại: dòng ngân hàng ở lại với `question_id` `NULL` và lần duyệt lại không đụng nó; câu cuối
  bị từ chối và đề vẫn *có câu hỏi*; dồn số cả `questions` lẫn `draft_items`, soạn thêm không lỗ.
- **Hộp xác nhận, hai lời dẫn theo `QuestionRead.in_bank`:** `services/fe/src/screens/teacher/Panel.tsx`;
  vitest *"xoá một câu khỏi đề (ADR-28)"* trong `services/fe/src/teacher.test.tsx`; Figma
  `Consequence dialog — xoá câu khỏi đề` (`592:3180`), artboard 15 (`594:2550`).
- **Dòng tổng *"đã kiểm / chưa kiểm"* đã gỡ:** `Panel.tsx` (code đã xoá 15/10/2026), Figma
  artboard 6, 7, 8, 12, 14.
- **Chưa thi hành:** đường đọc (Kriky rút câu từ ngân hàng); việc sửa bản trong ngân hàng; chip nguồn
  thật trên từng câu.

## Hậu ký 18/10/2026

Hai đường đọc và một đường ghi ngược đã có; chip nguồn thật đã có.

- **Màn *Ngân hàng câu hỏi*** (việc 18, plan `teacher-rail-screens`): đọc và sửa **bản trong ngân
  hàng**; câu trong đề không đổi. Câu hỏi *"ghi đè sẽ va với việc sửa trong ngân hàng"* ở mục Hệ quả
  vẫn mở: duyệt lại đề gốc đè bản đã sửa (`docs/plans/backlog.md`, chờ người dùng).
- **Lấy câu từ ngân hàng vào đề còn mở** (việc 17, plan `question-bank-into-draft`):
  `POST /api/teacher/assessments/{id}/bank-questions` chép câu thành `Question` mang `source="bank"`,
  `bank_question_id`, và một ô `draft_items` đã `ready` để lần soạn thêm nối tiếp số; câu đã có trong
  đề -- lấy vào trước đó, hay chính đề này là nơi câu được duyệt -- bị bỏ qua.
  `GET .../bank-picker` cho hộp chọn (artboard 19b). Luật *"lấy từ ngân hàng sang đề mới thì lúc duyệt
  không sinh thêm một bản trùng"* nay đứng trong `question_bank.file_approved`: câu `bank` bị bỏ qua.
  Test ở `services/be/tests/test_bank_into_draft.py`.
- **Hộp xoá câu** đọc `in_bank` gộp cả hai chiều -- câu đã duyệt từng chép vào kho, và câu lấy từ kho
  ra --, nên lời dẫn *"đã lưu từ lần duyệt trước"* đổi thành *"Câu này có bản trong ngân hàng câu
  hỏi…"*, cùng ở `Consequence dialog` (`592:3180`).
- **19/10/2026, lời dẫn rút gọn** (người dùng chốt): *"Xoá ở đây chỉ gỡ nó khỏi đề này — ngân hàng câu
  hỏi vẫn còn."* và *"Câu này chưa có trong ngân hàng câu hỏi — xoá rồi thì không lấy lại được."*.
- **Còn chưa thi hành:** Kriky rút câu từ ngân hàng khi soạn.

## Hậu ký 18/10/2026 (lần hai)

**Màn đọc báo cáo dẫn tới ngân hàng, không tới đề.** Màn báo cáo và màn câu có tỉ lệ sai cao của *Bảng
theo dõi* chỉ đọc. Nút *Chỉnh sửa trong Ngân hàng câu hỏi* mở bản ngân hàng của câu ở màn 22b, đọc
theo cả hai chiều chép ([ADR-35](adr-35-sua-loi-giai-sau-phat-hanh.md)).
