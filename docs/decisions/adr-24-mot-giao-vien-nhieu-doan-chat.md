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

**Vì sao không có đoạn chat rỗng.** Chưa có đường xoá. Một cú bấm nhầm để lại một hàng không có gì
để vẽ và không có cách nào dọn, và sau một tuần rail đầy những hàng như thế.

## Nơi luật này đang được thi hành

- `services/be/src/be/teacher_chat.py` — `_conversation(start_new=...)` là đường duy nhất mở luồng
  mới; `conversation_of` trả lời *"đề này sinh ra từ đoạn nào"*; `_latest_conversation` sắp theo
  `COALESCE(lần nói cuối, started_at)`; `_name_the_thread` đặt tên sau lượt đầu và nuốt mọi lỗi.
- `services/be/src/be/models.py` — `TeacherConversation` **không còn** `UniqueConstraint`, và có cột
  `title`.
- `services/be/tests/test_teacher_memory.py` — *"nói tiếp không mở luồng mới"* và *"xin thì được"* là
  hai nửa của cùng một luật, mỗi nửa một test.
- `services/be/tests/test_approval.py` —
  `test_the_record_lands_in_the_conversation_that_made_the_paper`.
- `services/fe/src/App.tsx` — `#/teacher/chat/{đoạn}/de/{đề}`, và link cũ tự chuyển về đó.
- `packages/contracts/src/contracts/teacher_chat.py` — `NAME_CONVERSATION_TASK`.

## Thứ luật này **chưa** nói

- **Xoá hay đổi tên một đoạn chat.** Chưa có đường nào, và vì thế cũng chưa có câu trả lời cho *"xoá
  một đoạn thì biên bản duyệt trong đó đi đâu"*.
- **Lưu trữ.** Danh sách trả về mọi đoạn, không phân trang. Một giáo viên dùng một năm sẽ có vài
  trăm hàng, và lúc ấy rail cần một đường tìm kiếm chứ không phải một danh sách dài hơn.
