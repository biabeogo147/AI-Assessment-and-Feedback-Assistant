# ADR-24 — Một giáo viên có nhiều đoạn chat, và biên bản rơi vào đoạn đã tạo ra đề

- **Trạng thái:** đã chốt
- **Ngày:** 2026-10-02

## Bối cảnh

Platform giáo viên dựng xong với **đúng một** luồng hội thoại cho mỗi giáo viên. Đó không phải một
thiếu sót bỏ quên: `teacher_conversations` mang `UniqueConstraint("teacher_id")`, và comment cạnh nó
viết thẳng rằng luật ấy thuộc về schema chứ không thuộc về niềm hy vọng rằng hai request không bao
giờ tới cùng lúc.

Một luồng là đủ cho tới khi nó không đủ. Một giáo viên soạn đề giữa kỳ, nhập danh sách lớp, rồi hỏi
về lỗi sai của 12A — ba việc không liên quan nằm trong một dòng thời gian, và trợ lý đọc cả ba mỗi
lần trả lời. Thứ hỏng không phải giao diện mà là **ngữ cảnh**: history càng dài thì phần liên quan
tới câu vừa hỏi càng loãng.

Mở luồng thứ hai thì đẻ ra một câu hỏi không tồn tại trước đó. **Duyệt** và **phát hành** xảy ra
ngoài khung chat — chúng nằm sau một nút và một hộp xác nhận (ADR-05) — nhưng chúng vẫn ghi một biên
bản vào hội thoại, vì thứ giáo viên đọc lại sau một tuần là *đã xảy ra những gì*. Với một luồng thì
*"ghi vào hội thoại đang chạy"* là một câu rõ nghĩa. Với nhiều luồng thì không.

## Quyết định

**Một giáo viên có nhiều đoạn chat**, và mở một đoạn mới là một việc họ xin được.

- Mở luồng mới có **đúng một** đường: cờ `start_new` trên `POST /api/teacher/chat/messages`. Nói
  tiếp không bao giờ âm thầm mở luồng mới.
- Không có đoạn chat rỗng. Bấm *Đoạn chat mới* không tạo hàng nào; hàng xuất hiện khi có câu đầu
  tiên, và danh sách chỉ trả những đoạn đã có ít nhất một bước.
- *"Đoạn đang chạy"* nghĩa là đoạn **vừa nói trong đó**, không phải đoạn **vừa mở**.
- Mỗi đoạn có một tiêu đề do model đặt sau lượt đầu tiên. Model hỏng, hoặc `LLM_ENABLED=false`, thì
  tiêu đề là câu đầu cắt còn 60 ký tự.

**Biên bản của một hành động rơi vào đoạn chat đã sinh ra đề**, không phải đoạn mới nhất và không
phải đoạn client khai. BE suy ra nó từ `teacher_turns.entity_id`. Đề không sinh ra từ đoạn nào — đề
seed, đề tạo bằng tay — thì lùi về đoạn đang chạy.

**Panel đề sống bên trong đoạn chat của nó.** Route là `#/teacher/chat/{đoạn}/de/{đề}`.

## Vì sao

**Vì sao không phải "đoạn mới nhất".** Giáo viên đang đọc lại một đoạn chat tuần trước, bấm *Duyệt*,
và biên bản rơi vào đoạn họ nói sáng nay. Họ sẽ không tìm thấy nó, và không có gì trên màn hình nói
rằng điều đó vừa xảy ra. Đây là loại sai tệ nhất trong các loại sai có thể xảy ra ở đây: **im lặng,
và chỉ lộ ra sau nhiều ngày**.

**Vì sao không phải một id do client gửi.** Nó rẻ hơn về code và đắt hơn về trách nhiệm: BE thôi
không còn là bên biết biên bản thuộc về đâu. Mà cái id ấy cũng không thêm thông tin gì — panel chỉ
mở được từ bên trong đoạn chat của đề, nên hai câu trả lời luôn trùng nhau. Suy ra từ dữ liệu đã có
thì không có gì để gửi sai.

**Vì sao suy ra được mà không cần cột mới.** `_subject` đã ghi `entity_kind` và `entity_id` lên mỗi
bước `tool_result` từ Pha 2, cho một mục đích khác hẳn. Sự thật *"đề này sinh ra từ đoạn kia"* đã nằm
trong bảng từ lâu; đợt này chỉ đọc nó.

**Vì sao tiêu đề do model đặt.** Câu đầu cắt ngắn đọc được nhưng không **gọi tên** việc: *"Soạn cho
tôi 2 câu trắc nghiệm về đạo hàm của đa thức, lớp 12, mức"* so với *"Tạo đề đạo hàm đa thức 12"*.
Trên một hàng rộng 228px, phần bị cắt là phần phân biệt hai đoạn chat với nhau. Cái giá là một lời
gọi model nhỏ cho mỗi đoạn mới — chỉ lượt đầu, và nó chạy **sau** câu trả lời nên không ai phải chờ
thêm.

**Vì sao không có đoạn chat rỗng.** Một cú bấm nhầm để lại một hàng không có gì để vẽ, và rail chỉ
hiện những đoạn đã có ít nhất một bước — `JOIN` thay cho `LEFT JOIN` là cách rẻ nhất để rác đó không
bao giờ lên màn hình.

**Xoá là xoá mềm.** Câu chặn của ADR này — *"xoá một đoạn thì biên bản duyệt trong đó đi đâu"* —
trả bằng một cột `deleted_at`, không bằng một câu `DELETE`. Hai đòi hỏi kéo ngược nhau: giáo viên
muốn một đoạn gõ nhầm biến khỏi mắt mình, còn biên bản duyệt là một row `teacher_turns` của chính
đoạn ấy và ADR này đòi nó giữ được. Xoá thật thì một cú dọn nhà phá mất bằng chứng cho một cuộc đi
tìm của tháng sau, mà cuộc đi tìm ấy không phải việc của người đang bấm nút. Nên đoạn đã xoá **đọc
ra y như một đoạn không tồn tại** — rời rail, `GET` ra 404, không nhận câu mới nào, và không còn là
*"đoạn đang chạy"* — còn các lượt của nó nằm nguyên trong bảng.

Hệ quả phải nói ra: một đề sinh ra từ một đoạn đã xoá thì biên bản duyệt của nó rơi vào đoạn đang
chạy, và nếu giáo viên không còn đoạn nào thì một đoạn mới được mở ra để chứa biên bản ấy. Ghi nó
vào đoạn đã ẩn thì ADR này đạt về chữ và hỏng về việc: không ai mở được ra đọc.

**Đổi tên.** Tên vốn do model đặt một lần sau lượt đầu. Rail là chỗ giáo viên đi tìm lại việc cũ,
nên một cái tên model đặt sai là một đoạn chat mất tích — giáo viên sửa được, qua cùng hàm dọn mà
đường đặt tên tự động dùng. Tên rỗng bị từ chối: cột rỗng đã có nghĩa riêng của nó (*chưa đặt*).

## Nơi luật này đang được thi hành

- `services/be/src/be/teacher_chat.py` — `_conversation(start_new=...)` là đường duy nhất mở luồng
  mới; `conversation_of` trả lời *"đề này sinh ra từ đoạn nào"*; `_latest_conversation` sắp theo
  `COALESCE(lần nói cuối, started_at)`; `_name_the_thread` đặt tên sau lượt đầu và nuốt mọi lỗi.
- `services/be/src/be/models.py` — `TeacherConversation` **không còn** `UniqueConstraint`, và có hai
  cột `title`, `deleted_at`.
- `services/be/src/be/teacher_chat.py` — `_owned_conversation` canh **cả hai** cửa của một đoạn đã
  xoá (đọc lại ra 404, và câu mới không rơi vào đó) bằng một mệnh đề; `_latest_conversation`,
  `conversations` và `conversation_of` lọc cùng cột ấy; `rename_conversation` dọn tên bằng `_tidy`.
- `services/be/tests/test_teacher_memory.py` — `test_a_deleted_conversation_keeps_its_turns`,
  `test_a_new_turn_never_lands_in_a_deleted_conversation`,
  `test_a_deleted_conversation_is_not_the_running_one`,
  `test_a_record_never_lands_in_a_deleted_conversation`.
- `services/be/tests/test_teacher_memory.py` — *"nói tiếp không mở luồng mới"* và *"xin thì được"* là
  hai nửa của cùng một luật, mỗi nửa một test.
- `services/be/tests/test_approval.py` —
  `test_the_record_lands_in_the_conversation_that_made_the_paper`.
- `services/fe/src/App.tsx` — `#/teacher/chat/{đoạn}/de/{đề}`, và link cũ tự chuyển về đó.
- `packages/contracts/src/contracts/teacher_chat.py` — `NAME_CONVERSATION_TASK`.

## Thứ luật này **chưa** nói

- **Khôi phục một đoạn đã xoá.** `deleted_at` giữ đủ dữ liệu để làm, nhưng không có đường nào trên
  màn hình, và hộp xác nhận nói thẳng với giáo viên rằng họ sẽ không mở lại được.
- **Lưu trữ.** Danh sách trả về mọi đoạn, không phân trang. Một giáo viên dùng một năm sẽ có vài
  trăm hàng, và lúc ấy rail cần một đường tìm kiếm chứ không phải một danh sách dài hơn.
