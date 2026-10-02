# Nhiều đoạn chat cho một giáo viên, và một thanh kéo có thật

Plan bắt buộc theo `AGENTS.md`: đợt này chạm hai service, sửa `packages/contracts`, bỏ một ràng
buộc schema, và thêm một ADR.

## Goal

Giáo viên mở được **nhiều** đoạn chat, mỗi đoạn một tiêu đề đọc được, và bấm vào một đoạn cũ thì
đọc lại được nó. Hai ngăn trên rail kéo giãn được và nhớ vị trí sau khi tải lại trang.

Hai thứ đang giả, và đợt này trả cả hai: danh sách đoạn chat trên rail là chữ bịa trong
`invented-not-from-be.ts`, còn thanh kéo là một vạch không làm gì.

## Scope

BE có đúng một luồng cho mỗi giáo viên, và đó **không** phải tình cờ: `models.py` có
`UniqueConstraint("teacher_id")` cưỡng chế nó. Code đã viết sẵn lời chỉ dẫn cho ngày hôm nay ở hai
chỗ — comment cạnh chính constraint ấy (*"Ngày mà giáo viên mở được luồng thứ hai, constraint này
được bỏ đi một cách có chủ ý"*) và docstring của `_conversation` (*"Khi nó trở thành một thứ xin
được thì đây là hàm duy nhất phải đổi"*).

Ngoài phạm vi: bốn đích đến trên rail vẫn trơ, và huy hiệu *Bảng theo dõi* vẫn là một con số bịa.
Chúng ở lại trong `backlog.md`.

## Bốn điều người dùng đã chốt

1. **Tiêu đề do model đặt.** Câu đầu cắt ngắn là **đường lùi**, không phải phương án chính.
2. **Bấm "Đoạn chat mới" không tạo dòng nào.** Dòng xuất hiện khi có câu đầu tiên, nên danh sách
   không bao giờ chứa một đoạn chat rỗng — và một cú bấm nhầm không để lại rác mà chưa có đường xoá.
3. **Panel đề sống bên trong đoạn chat đã tạo ra nó.** Đây là câu trả lời làm thiết kế gọn hơn, xem
   Decision Records.
4. **Vị trí thanh kéo nhớ bằng `localStorage`.** Không cột nào ở BE.

## Ordered Tasks

- [x] **Bước 0 — plan này.** Cổng: `.\dev.ps1 check` xanh.
- [x] **Bước 1 — bỏ ràng buộc, thêm cột.** Gỡ `UniqueConstraint("teacher_id")` khỏi
      `TeacherConversation`, thêm `title: str` (mặc định rỗng). Viết lại
      `test_a_teacher_keeps_one_conversation_across_messages`: nó đang khẳng định đúng cái luật vừa
      bị bỏ, nên phải nói luật mới. Cổng: năm test còn lại của `test_teacher_memory.py` **không**
      phải sửa một dòng nào.
- [x] **Bước 2 — `_conversation_of`.** Tìm đoạn chat đã sinh ra một đề qua `teacher_turns`. Cho
      `note_action` dùng nó thay cho "đoạn mới nhất". Cổng: đột biến trả nó về "mới nhất" làm đúng
      một test đỏ.
- [x] **Bước 3 — `GET /api/teacher/conversations`.** Trả `conversation_id`, `title`, `started_at`,
      `last_spoke_at`. Cổng: đoạn chat của giáo viên khác đọc ra y như một đoạn không tồn tại.
- [x] **Bước 4 — chọn đoạn chat.** `GET /teacher/chat` nhận `conversation_id`; `Said` nhận
      `conversation_id` và cờ `start_new`, loại trừ nhau. Cổng: hai đoạn song song cho hai lịch sử
      khác nhau, và gửi kèm cả hai tham số trả 422.
- [x] **Bước 5 — `AssessmentDetail.conversation_id`.** Cổng: đề sinh từ chat trả đúng id; đề seed
      trả `null`.
- [x] **Bước 6 — task `name_conversation`.** Contract, graph, handler, một dòng ở worker. Cổng: test
      AGENT xanh mà không gọi model thật.
- [x] **Bước 7 — BE đặt tiêu đề.** Sau lượt đầu của một hội thoại mới, kèm đường lùi. Cổng: tắt
      `LLM_ENABLED` vẫn có tiêu đề; model ném lỗi không làm hỏng lượt nói.
- [x] **Bước 8 — FE: rail thật và route lồng nhau.** `api.ts`, danh sách đoạn chat, nút *Đoạn chat
      mới*, `#/teacher/chat/{id}/de/{paper}`. Cổng: mở hai đoạn, bấm qua lại, F5 đúng chỗ.
- [x] **Bước 9 — FE: thanh kéo.** `pointer` events + `localStorage` + `cursor: row-resize`. Cổng:
      kéo được, F5 nhớ vị trí.
- [x] **Bước 10 — tài liệu.** ADR-24, `backlog.md`, `local-development.md` (kèm câu `ALTER`), đóng
      plan.

## Decision Records

### Panel sống trong đoạn chat đã tạo ra đề, và vì thế BE tự suy ra được

Duyệt và phát hành xảy ra **ngoài** khung chat, nên khi một giáo viên có nhiều đoạn chat thì câu
*"biên bản rơi vào đoạn nào"* trở thành một câu hỏi thật. Ba câu trả lời khả dĩ: đoạn mới nhất (hiện
nay), đoạn đang mở trên màn hình (client gửi id lên), hoặc đoạn đã sinh ra đề.

Chọn cái thứ ba, và nó **rẻ hơn** cái thứ hai chứ không đắt hơn. Panel chỉ mở được từ bên trong đoạn
chat của nó, nên hai thứ trùng nhau — mà suy ra từ `teacher_turns.entity_id` thì không phải thêm
tham số vào hai endpoint duyệt/phát hành, và không phải tin một id do client gửi. Một hàm
`_conversation_of`, ba người gọi: `note_action`, `AssessmentDetail.conversation_id`, và đường chuyển
hướng của link cũ.

Cái thứ nhất bị loại vì nó sai một cách im lặng: giáo viên đang đọc một đoạn chat cũ, bấm *Duyệt*,
và biên bản rơi vào một đoạn khác — họ sẽ không tìm thấy nó, và không có gì trên màn hình nói đã xảy
ra chuyện đó.

Đề không thuộc đoạn chat nào — seed, hoặc tạo tay — thì `_conversation_of` trả `None` và
`note_action` lùi về đoạn mới nhất. Lùi, chứ không nổ: một đề vẫn phải duyệt được.

### Mặc định cũ giữ nguyên nghĩa

`GET /teacher/chat` không kèm id, và `POST` không kèm cờ, vẫn là *"đoạn mới nhất"*. Nhờ vậy sáu test
hiện có không phải sửa dòng nào, và sáu test ấy chính là thứ chứng minh đợt này không làm vỡ hành vi
cũ. Chỉ một test phải viết lại, và nó phải viết lại vì nó khẳng định đúng cái luật vừa bị bỏ.

### Tiêu đề: chờ model, không bắn rồi quên

BE **không có worker chạy nền**. Một job bắn đi mà không ai thu thì tiêu đề không bao giờ được ghi,
nên `run_task` chờ kết quả ngay trong request. Giá phải trả là một lời gọi model nhỏ cộng vào **lượt
đầu tiên** của mỗi hội thoại mới — chỉ lượt đầu, và chỉ khi hội thoại chưa có tên.

Payload tự chứa: chở nguyên câu đầu của giáo viên, không chở `conversation_id`. AGENT không có
credential database và sẽ không bao giờ có.

Hỏng thì nuốt `AgentError` và ghi log. Một tiêu đề không đặt được là một dòng chữ xấu trên rail;
làm hỏng lượt nói vì nó là mất cả việc giáo viên vừa nhờ.

### Nhóm ngày tính theo lần nói cuối

Không theo `started_at`. Một đoạn chat mở từ tuần trước mà hôm nay vừa nói tiếp thì thuộc về *Hôm
nay* — đó là thứ người ta đi tìm khi mở rail.

## Files

| File | Việc |
| --- | --- |
| `services/be/src/be/models.py` | bỏ `UniqueConstraint("teacher_id")`, thêm `TeacherConversation.title` |
| `services/be/src/be/teacher_chat.py` | `_conversation_of`, `note_action`, hai endpoint chat, phần đặt tiêu đề |
| `services/be/src/be/teacher_routes.py` | `AssessmentDetail.conversation_id` |
| `packages/contracts/src/contracts/teacher_chat.py` | `NAME_CONVERSATION_TASK` và cặp model của nó |
| `packages/contracts/src/contracts/__init__.py` | import block và `__all__` |
| `services/agent/src/agent/graphs/naming.py` | **mới** — graph một node |
| `services/agent/src/agent/handlers.py` | hàm mock sync + handler |
| `services/agent/src/agent/worker.py` | hai import, một dòng `func(...)` |
| `services/fe/src/api.ts` | type hội thoại, `teacher.conversations()`, tham số cho `say` |
| `services/fe/src/screens/teacher/Rail.tsx` | danh sách thật, nhóm ngày, hàng đang chọn, thanh kéo |
| `services/fe/src/screens/teacher/Chat.tsx` | nhận `conversationId`, nút *Đoạn chat mới* |
| `services/fe/src/App.tsx` | route lồng nhau, chuyển hướng link cũ |
| `services/fe/src/teacher.css` | `cursor: row-resize`, chiều cao ngăn theo biến |
| `services/fe/src/screens/teacher/invented-not-from-be.ts` | bỏ `CONVERSATIONS` |
| `docs/decisions/adr-24-...` | **mới** |

## Validation Checks

- [x] `.\dev.ps1 check` và `.\dev.ps1 test` xanh sau **mỗi** bước
- [x] Năm ca của *Review Focus* dưới đây, mỗi ca một test
- [x] Break-to-test ba chỗ, mỗi lần đúng một test đỏ: bỏ lọc `teacher_id` khỏi đường đọc hội thoại;
      trả `note_action` về "đoạn mới nhất"; bỏ `try/except` quanh phần đặt tiêu đề
- [x] Một lượt chạy thật qua giao diện trên Postgres với `gpt-4o-mini`: mở đoạn chat mới, nói một
      câu, đợi tiêu đề hiện trên rail, mở lại đoạn cũ, kiểm hai lịch sử không lẫn nhau, và kiểm nút
      *Xem* mở panel **trong** đoạn chat đang đứng
- [x] Kéo thanh ngăn, F5, vị trí giữ nguyên
- [x] Rail trên Figma đã vẽ sẵn nhóm ngày và hàng đang chọn, nên **không phải sửa Figma**. Chỗ nào
      lệch thì đo rồi sửa code
- [x] Mỗi commit mang trailer `Plan: 2026-10-02-nhieu-doan-chat-plan.md`

## Review Focus

Năm ca thiết kế này ngụ ý mà đường đi hạnh phúc không chạm tới:

1. **`conversation_id` của giáo viên khác** → trả lời y hệt một id không tồn tại (ADR-22). Bước 3, 4.
2. **Gửi kèm cả `conversation_id` lẫn `start_new`** → 422, không phải một trong hai bị bỏ qua trong
   im lặng. Bước 4.
3. **`LLM_ENABLED=false`** → tiêu đề vẫn có, là câu đầu cắt ngắn. Bước 7.
4. **Model trả tiêu đề rỗng, dài ba trăm ký tự, hoặc kèm dấu ngoặc kép** → dọn và cắt; rỗng thì dùng
   đường lùi. Bước 7.
5. **Một đề không thuộc đoạn chat nào** → `conversation_id` là `null`, panel vẫn mở được,
   `note_action` lùi về đoạn mới nhất. Bước 2, 5.

## Một câu SQL cho database đang chạy

Repo không có migration: `prepare_schema` chỉ `create_all`, và `create_all` không bao giờ sửa một
bảng đã tồn tại. Database dev sẽ giữ ràng buộc cũ và đoạn chat thứ hai nổ `IntegrityError`:

```sql
ALTER TABLE teacher_conversations DROP CONSTRAINT teacher_conversations_teacher_id_key;
ALTER TABLE teacher_conversations ADD COLUMN title VARCHAR(120) NOT NULL DEFAULT '';
```

Plan này ban đầu chỉ ghi câu thứ nhất, và câu thứ hai lộ ra khi chạy thật: `create_all` không thêm
**cột** vào một bảng đã có, y như nó không bỏ một constraint. Cùng một cái bẫy, hai mặt.

Câu này đi vào `local-development.md` ở bước 10.

## Status

**Xong cả mười một bước.** Một giáo viên nay mở được nhiều đoạn chat, mỗi đoạn một tiêu đề do model
đặt, và hai ngăn trên rail kéo giãn được.

### Ba thứ chỉ tìm ra bằng cách chạy

1. **`_latest_conversation` phân giải hoà bằng một UUID.** Vô hại suốt thời gian mỗi giáo viên một
   luồng; hại ngay ở luồng thứ hai, vì `datetime.now()` trên Windows nhảy từng bước ~15ms nên hai
   luồng mở sát nhau có `started_at` bằng nhau. Nay khoá sắp xếp là lần nói cuối — đúng hơn về
   nghĩa, không chỉ chữa được hoà.
2. **Nút *Đoạn chat mới* không làm gì khi đang ở `#/teacher`.** Hash không đổi thì `hashchange`
   không bắn. Nay màn trống là một route riêng.
3. **Thanh kéo kéo được nhưng không lưu.** Lần `set` cuối của một cú kéo đưa đúng giá trị đang có,
   React bỏ qua, effect không chạy lại. Nay ghi thẳng khi thả tay.

Thêm một bẫy cũ cắn lần nữa: `create_all` không thêm **cột** vào bảng đã có, y như nó không bỏ một
constraint. `local-development.md` nay nói cả hai.

### Thứ đợt này đẻ ra

Hai món nợ mới trong `backlog.md`: chưa xoá hay đổi tên được một đoạn chat, và danh sách chưa phân
trang. Cả hai đều đã được ADR-24 nêu thẳng ở mục *Thứ luật này chưa nói*.

249 pytest, 21 vitest, 7 repo check, 2 import contract xanh.

## Status cũ

Xong bước 0 và 1. Constraint đã đi, cột `title` đã có, và `_conversation` nhận `start_new` — đúng
một tham số, không thêm một đường thứ hai, y như docstring cũ của nó đã hẹn.

Test khẳng định "một giáo viên một luồng" **không bị xoá**: nó giữ nguyên phần kiểm và đổi thứ nó
đang canh, từ một constraint sang một hàm. Nói tiếp vẫn không bao giờ được âm thầm mở luồng mới, vì
một luồng mới nghĩa là trợ lý quên sạch những gì vừa nói. Một test thứ hai nói nửa còn lại: xin thì
được, và luồng cũ ở nguyên đó.

Năm test khác của `test_teacher_memory.py` không phải sửa một dòng nào, đúng như plan dự tính.

Bước 2 xong, và nó tìm ra một lỗi plan không đoán trước. `_latest_conversation` phân giải hoà bằng
`id DESC` — một UUID, tức **xác định nhưng tuỳ tiện**. Điều đó vô hại suốt thời gian mỗi giáo viên
chỉ có một luồng, và hại ngay ở luồng thứ hai: `datetime.now()` trên Windows nhảy từng bước ~15ms,
nên hai luồng mở sát nhau có `started_at` bằng nhau và luồng thắng là luồng có UUID lớn hơn. Bấm
*Đoạn chat mới* rồi gõ một câu, một nửa số lần câu ấy rơi vào luồng cũ.

Nay khoá sắp xếp là `COALESCE(lần nói cuối, started_at)`, và nó đúng hơn về nghĩa chứ không chỉ chữa
được hoà: *"luồng đang chạy"* là luồng **vừa nói**, không phải luồng **vừa mở**. Một giáo viên mở
luồng mới hôm qua rồi quay lại luồng cũ nói tiếp thì luồng cũ mới là luồng họ đang ở.

Bước 3 và 4 xong. Danh sách đoạn chat chỉ trả những đoạn **đã có ít nhất một bước** — một hàng rỗng
không có gì để vẽ và không có đường nào xoá, nên `JOIN` thay cho `LEFT JOIN` là cách rẻ nhất để rác
không bao giờ lên màn hình.

`conversation_id` là id **đầu tiên trong file này đi ngược chiều**: mọi id trước đây đều do BE tự tìm
từ `teacher_id`, nên luật sở hữu là cấu trúc; cái này do client gửi, nên nó phải được kiểm. Một id
của người khác trả về y hệt một id không tồn tại, và có test so **nguyên body** của hai ca đó.

`Answered` nay mang `conversation_id`. Không có nó thì FE bấm *Đoạn chat mới*, gửi câu đầu, rồi
không biết mình vừa nói vào đâu — và phải đoán bằng "đoạn mới nhất", đúng thứ vừa sửa ở bước 2.

Bước 5 xong. `conversation_of` thành public vì nay có hai module gọi nó — và điều đó đúng về nghĩa:
*"đề này sinh ra từ đoạn chat nào"* là một câu hỏi của sản phẩm, không phải chi tiết nội bộ của
module chat. Đề không thuộc đoạn nào thì trả **rỗng** chứ không đoán: panel vẫn mở được, nhưng nó
không được bịa ra một nguồn gốc.

Bước 6 xong. Task thứ sáu của AGENT, và nó nhỏ vì nó **được phép** nhỏ: không đọc lịch sử, không
gọi tool, không quyết định gì — nhận một chuỗi, trả một chuỗi ngắn hơn. Vẫn dựng thành graph, vì
luật của repo nói graph là nơi **duy nhất** gọi model; giữ đúng ranh giới ấy đáng hơn mười lăm dòng
tiết kiệm được.

Ba đường ra đều trả về một `ConversationNameCompleted` hợp lệ, và test đáng giá nhất là đường hỏng:
task này chạy ở **cuối một lượt nói**, sau khi giáo viên đã chờ xong và mọi bước đã commit, nên một
exception thoát ra từ đây sẽ biến một lượt đã thành công thành lỗi 500 — mất cả việc vừa làm, vì
một cái tên.

Bước 7 xong, và nó lộ ra một điều về chính các test: `run_task` là **một cái cửa, nhiều loại việc**.
Từ khi BE nhờ AGENT đặt tên, bản giả trong test phải phân việc theo `task_name` y như cái cửa thật
— nếu không thì job đặt tên ăn mất một bước của kịch bản. Hai test đỏ vì đúng lý do ấy, và cách sửa
là làm cho bản giả **giống cái thật hơn**, không phải nới lỏng phần kiểm.

Năm ca dọn tiêu đề đều có test: dấu ngoặc kép, dấu chấm cuối, khoảng trắng thừa, ba trăm ký tự, và
chuỗi rỗng. Prompt đã bảo model đừng làm bốn chuyện đầu — prompt là một lời nhờ, không phải một
ràng buộc, nên chỗ ràng buộc là BE.

Bước 8 và 9 xong, và **một lượt chạy thật tìm ra hai lỗi mà không test nào thấy** — lần thứ năm
trong dự án này.

**Nút *Đoạn chat mới* không làm gì khi đang đứng ở `#/teacher`.** Nó gọi `go("/teacher")`, hash
không đổi, `hashchange` không bắn, effect không chạy lại. Màn hình giữ nguyên đoạn cũ, và câu gõ
tiếp theo rơi vào đó — không có gì báo. Nay màn trống là một **route** riêng (`#/teacher/moi`), nên
cú bấm luôn đổi hash, F5 giữ đúng trạng thái, và nút back quay lại được.

**Thanh kéo kéo được nhưng không lưu.** Bản đầu ghi `localStorage` trong một effect nghe
`documentsHeight`; lần `set` cuối của một cú kéo đưa đúng giá trị đang có, React bỏ qua, effect
không chạy lại. Nay ghi thẳng khi thả tay — và đó cũng là chỗ đúng về số lượng, vì một cú kéo là
hàng trăm `pointermove` còn `localStorage` ghi đồng bộ trên luồng chính.

Đo lại rail sau cả hai: mọi con số trùng khớp đợt đo trước, không xê dịch một pixel.

Và `create_all` cắn lần thứ hai: nó không thêm **cột** vào bảng đã có, y như nó không bỏ một
constraint. Câu `ALTER` nay có hai dòng.

