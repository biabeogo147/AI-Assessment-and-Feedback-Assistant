# Plan 4b — soạn đề theo tài liệu: mỗi câu một mục kiến thức

Plan con của `2026-10-07-doc-pdf-vao-ngu-canh-plan.md`, sau 4a
(`completed/2026-10-12-kriky-skill-routing-plan.md`).

## Goal

Soạn đề hôm nay **không dùng tài liệu**: chip thả vào ô chat chỉ hiện trên màn hình
(`services/fe/src/api.ts` `streamTurn` không gửi `document_id`), và mỗi job `DraftQuestionRequested`
chỉ nhận `subject/grade/topic_scope` bằng lời -- mười job song song không thấy nhau nên dễ hỏi trùng
một kiến thức. Cây (`IndexNode`) và chunk (`IndexChunk`) đã nằm trong Mongo từ plan 3c, chưa ai đọc.

Sau plan này: giáo viên đính chip một cuốn sách, gõ *"soạn 10 câu chương 1"* → Kriky đọc mục lục,
khớp *"chương 1"* với nút thật (hoặc hỏi lại bằng tên chương/bài), mở đề với phạm vi là các nút ấy,
và **mỗi câu đứng trên một mục kiến thức khác nhau** của tài liệu.

## Scope

Trong: chip đi kèm tin nhắn; BE đọc Mongo (chỉ đọc); ba tool đọc; phương án `ask_clarify` từ cây;
phạm vi đóng băng trong `DraftBrief`; gán mục cho từng câu trong `DraftItem`; job soạn câu nhận đoạn
nội dung của mục mình. Ngoài: bày nhiều cách chia số câu (ADR-27, hoãn -- `backlog.md`); câu luyện
tập pha 2 (**không** nhận nội dung tài liệu -- hậu ký ADR-27); VLM đọc công thức (3a); sympy (3d).

## Decision Records

### Decision: BE đọc Mongo, chỉ đọc

**options considered:** (a) **BE đọc thẳng `nodes`/`chunks` qua một module chỉ đọc** · (b)
`services/document` mở HTTP cho BE gọi · (c) AGENT đọc Mongo.

**selected option:** (a).

**reason:** tool của Kriky chạy ở BE, và ranh giới đã chốt ở plan 3b -- Mongo là *kho nội dung* như
MinIO, sự thật (`documents.state`) vẫn chỉ ở Postgres -- nên BE đọc nội dung cũng như đã đọc byte từ
MinIO. (b) là mũi HTTP đầu tiên giữa hai service, cần xác thực service-to-service chưa có (record
*document đẩy job cho BE* của plan ô). (c) phá luật *AGENT không giữ credential kho nào*. Một module
duy nhất (`be/content_reader.py`) và một check không cho lời gọi ghi giữ chữ *chỉ đọc* thành luật.

### Decision: mục kiến thức là nút lá; thiếu thì chia theo nhóm chunk

**options considered:** (a) **nút lá trong phạm vi, câu rải theo độ dài nội dung; nhiều câu hơn số
mục thì tách mục thành nhóm chunk liên tiếp** · (b) mỗi câu một chunk · (c) model tự nêu trọng tâm
từng câu trong plan.

**selected option:** (a) -- người dùng chọn 12/10/2026.

**reason:** nút lá là cách sách tự chia kiến thức (bài, mục), nên hai câu trên hai nút là hai kiến
thức thật; chunk (b) cắt ở 1 500 ký tự, có thể chặt đôi một khái niệm. (c) là lời dặn, thứ repo đã đo
là không giữ được model. Gán **ghi vào `DraftItem` trước khi job chạy** (record *gán chunk đóng băng*
của plan ô): `fire` bắn lại ô `retry` và soạn thêm câu thì tổng đổi, một phép gán tính lại sẽ xáo mục
của câu đã xong.

### Decision: phạm vi đóng băng kèm phiên bản cây

**options considered:** (a) đóng băng nút và chunk theo `ordinal` · (b) **kèm `IndexHeader.built_at`
của cây lúc mở đề**.

**selected option:** (b).

**reason:** đọc lại một tài liệu xoá cây cũ và đánh số lại (`content_store.begin`, D7 plan 3c). Một
`ordinal` đóng băng mà không kèm phiên bản cây sẽ trỏ sang nội dung khác sau lần đọc lại -- câu bắn
lại ô `retry` nhận nhầm mục. `fire` so `built_at`: lệch thì ô ấy `failed` với lý do, không soạn trên
cây mới.

### Decision: chip đi kèm tin nhắn, và đoạn chat nhớ chip gần nhất

**options considered:** (a) mỗi tin nhắn mang `document_id` của chip, chỉ sống một lượt · (b) **chip
lưu cùng câu của giáo viên (`TeacherTurn.document_id`); lượt không chip dùng chip gần nhất của đoạn
chat** · (c) cột tài liệu trên `TeacherConversation`.

**selected option:** (b). Bản đầu chọn (a) và hai lần review bắt lỗi của nó.

**reason:** FE xoá chip ngay khi gửi (`Chat.tsx`, có chủ ý), nên lượt kế -- giáo viên trả lời một
câu hỏi lại -- không còn chip. Với (a), lượt ấy mở một đề **không tài liệu** mà không lời từ chối nào
(review B3 với nút chương, review B4 với *"lớp 6"*). Suy từ lịch sử tool thì không đủ: một lượt có
chip mà không gọi tool nào để lại không dấu vết, và cửa sổ `_HISTORY_STEPS` làm đoạn chat dài quên
sách. (b) đọc từ database, không từ cửa sổ, và luật *khi nào quên* đơn giản: chip mới thay chip cũ;
muốn bỏ sách thì mở đoạn chat mới. (c) tương đương nhưng mất dấu vết *chip nào ở câu nào*.

## Files

| File | Việc |
|---|---|
| `packages/contracts/.../teacher_chat.py` | `AttachedDocument`; `NextStepRequested.attached_document` (tuỳ chọn) |
| `packages/contracts/.../authoring.py` | `DraftQuestionRequested.focus_title`, `focus_text`, `other_foci` (mặc định rỗng) |
| `packages/schema/.../models.py` | `DraftBrief.document_id`, `scope_nodes`, `index_built_at`; `DraftItem.node_ordinal`, `chunk_ordinals`; `TeacherTurn.document_id` |
| `services/be/src/be/content_reader.py` (mới), `config.py`, `main.py`, `pyproject.toml` | đọc Mongo |
| `services/be/src/be/teacher_tools.py`, `teacher_chat.py` | `list_documents`, `list_chapters`, `get_chapter`; `_offered` từ nút; `create_draft` nhận tài liệu; `attached_document` |
| `services/be/src/be/coverage.py` (mới), `drafting.py` | gán mục, đóng băng, dựng `focus_*` |
| `services/agent/src/agent/graphs/authoring.py`, `propose.py`, `skills/soan-de.md` | dùng `focus_*`; in tài liệu đính kèm; nhánh tài liệu của quy trình |
| `services/fe/src/api.ts`, `Chat.tsx` | gửi `document_id` của chip |
| `tools/check_contract.py` | cửa pymongo thứ hai, không lời gọi ghi |
| `docs/overview/architecture.md` ("BE không chạm" Mongo), `docs/overview/data-model.md` ("BE không đọc nó"; cột mới của `DraftBrief`/`DraftItem`) | sửa cùng B1/B2 |
| `docs/decisions/adr-27-…md`, `README.md`, plan ô, `backlog.md` | hậu ký, cổng cả đợt |
| `tools/skill_bench/cases.json` | hai ca có tài liệu cho bộ chọn skill (đo lại: 40/40, recall 100%) |
| `packages/contracts/.../__init__.py`, các file test | export `AttachedDocument`; test của từng task |

## Ordered Tasks

Mỗi task: xong → subagent review → sửa → task kế.

- [x] B0. Plan này; hậu ký ADR-27; plan ô; backlog.
- [x] B1. Contracts + schema. Review: đạt. Ghi cho B3/B4: `rebrief` (`drafting.py`) phải ghi đè cả
      phạm vi tài liệu; `fire` dùng lại `DraftItem` cũ nên phải gán lại mục khi `brief_version` đổi;
      cột JSON không phải `MutableList` -- gán list mới, không `.append()`.
- [x] B2. BE đọc Mongo, chỉ đọc. Review: document lệch hình dạng ném `ValidationError` thành 500 --
      nay thành `ContentUnavailable`; check chỉ-đọc chặn thêm `.command(`, `$out`, `$merge`. Ghi cho B4:
      `index_built_at` lấy **đúng** `IndexHeader.built_at` đọc từ Mongo (ms), không `datetime.now()`.
- [x] B3. Tool đọc, `_offered` từ nút, `create_draft` nhận tài liệu, `attached_document`. Hai điều đo
      được lúc làm: `vet_plan` coi **mọi** tham số là bắt buộc, nên `ToolSpec` có thêm `optional`
      (tường minh, mặc định rỗng); và test *"thứ không nhìn thấy thì không hỏi được"* bắt buộc tham
      số tài liệu cùng `list_chapters`/`get_chapter` **chỉ hiện** khi lượt có chip hoặc vừa gọi
      `list_documents` -- `catalog_for(..., documents=)`. Review B3: FE xoá chip sau khi gửi, nên lượt
      sau (giáo viên bấm *"Chương I…"*) dựng catalog không tài liệu và pha 2 cắt `document_id` -- đề mở
      ra trơn. Sửa: cờ tài liệu tính từ **lịch sử** đoạn chat (`_touched_documents`); test hai lượt.
- [x] B4. `coverage.assign` + `fire` đóng băng mục trong `DraftItem`. Đơn vị = nút có đoạn **của
      riêng nó** (cả phần mở đầu chương), không chỉ nút lá. Cây dựng lại (`built_at` lệch) thì
      `start_drafting` từ chối nói lý do, `_refire` đánh `failed` kèm lý do. Review B4: lượt có chip mà
      không gọi tool vẫn để lượt sau mất sách -- chip nay lưu ở `TeacherTurn.document_id` (Decision
      *chip … đoạn chat nhớ chip gần nhất*); thêm test `fire` lần hai giữ ô cũ và `_refire` trên cây
      mới, cả hai đã đột biến thử.
- [x] B5. AGENT dùng `focus_*` (dặn viết câu **mới**, không chép); skill `soan-de` có nhánh tài liệu,
      và lời nêu plan **nói ra** phép rải số câu theo mục (hậu ký ADR-27).
      Review B5: bước *NÊU PLAN NGAY* đứng trước bước đọc mục lục, nên có chip mà đủ bốn mục thì
      model bỏ qua mục lục và thiếu `nodes` thành *cả cuốn*. Sửa hai tầng: skill đọc tài liệu
      **trước**, và `create_draft` **từ chối** tài liệu không kèm `nodes`. Thêm: chip mới không dùng
      được thì không lùi về chip cũ; cờ tài liệu đọc từ database, không từ cửa sổ 40 bước.
- [x] B6. FE gửi chip: `streamTurn` mang `document_id`, `Chat.tsx` truyền chip đang đính. Không đổi
      giao diện. `teacher.say` (cửa POST) chưa mang chip -- màn hình chỉ dùng cửa SSE.
      Review B6: chip của tệp vừa tải lên (còn xử lý) bị bỏ lặng lẽ và mất luôn -- nay BE lưu chip của
      giáo viên ở **mọi** trạng thái, AGENT nhận `ready=False` và nói ra; và đoạn chat gắn với sách sẵn
      sàng thì `document_id`/`nodes` của `create_draft` là **bắt buộc** (`catalog_for(..., bound=)`).
- [x] B7. Thử đầu-cuối trên trình duyệt; đóng plan.

## Validation Checks

- Mỗi task: `.\dev.ps1 check`, `test`, `typecheck` xanh; đột biến một dòng ở luật mới làm test đỏ.
- `coverage.assign`: không hai câu chung một mục khi số câu ≤ số mục; khi số câu > số mục, không hai
  câu chung một nhóm chunk; soạn thêm không đổi mục của câu cũ.
- Đầu-cuối (gpt-4o-mini, BE và AGENT chạy code mới): `db-reset`, tải một tài liệu đã có cây, đính
  chip, *"soạn 10 câu chương 1"* → 10 câu, `DraftItem` 10 mục khác nhau, câu bám nội dung; *"chương
  7"* không có → hỏi lại bằng tên chương thật.

## Status

**Xong 12/10/2026.** Cổng đạt: mười câu trên mười mục khác nhau, đề gắn tài liệu, câu bám nội dung.
`check` 21/21, pytest 796, vitest 193, `typecheck` xanh (`test_a_turn_that_outlived_its_lock…` vẫn
chập chờn, nợ đã ghi ở `backlog.md`).

B0 xong. Review B0: hậu ký ADR-27 ban đầu viện cổng duyệt làm lưới cho cả pha 2
-- sai, pha 2 không qua duyệt; nay luật lọc chỉ rút cho prompt soạn đề. Thêm luật *mỗi câu một mục*
vào hậu ký, phiên bản cây vào phạm vi đóng băng, hai tài liệu overview vào bảng Files.

**Thử đầu-cuối 12/10/2026** (gpt-4o-mini; `db-reset`; BE, AGENT, ba worker chạy code mới): tải
*Kết nối tri thức Lớp 6 tập 1 (tr6-28).pdf* (24 trang scan) qua nút tải lên -- OCR + cây xong ~2 phút,
1 chương, 20 nút con, 35 đoạn.

- *"Soạn đề 10 câu trắc nghiệm Toán lớp 6 chương 1 từ sách này"* kèm chip → lượt sau không chip
  (*"Chương I. Tập hợp các số tự nhiên"*) → plan, đề mở **gắn tài liệu** (`scope_nodes=[0]`,
  `index_built_at` đóng băng), **10 câu trên 10 mục khác nhau** (nút 2, 4, 5, 6, 11, 12, 13, 16, 18,
  19), mỗi câu bám đúng mục: mô tả tập hợp, hệ thập phân, số La Mã, thứ tự, phép nhân, chia có dư,
  luyện tập, lũy thừa, thứ tự phép tính. Hai câu bị ADR-18 loại một lần rồi soạn lại được.
- *"Soạn 5 câu … chương 7 trong sách này"* → `list_chapters` rồi hỏi lại, nút là *"Chương I. TẬP HỢP
  CÁC SỐ TỰ NHIÊN (tr. 5–28)"* do BE dựng.
- **Đo được, sửa trong B7:** lượt đầu, gpt-4o-mini nêu `create_draft` **không** kèm `document_id` /
  `nodes` hai lần liền, và rào *bắt buộc* của review B6 từ chối đúng -- nhưng giáo viên nhận *"chưa
  dựng được các bước"*. Dựng lại payload thật từ kết quả arq: cùng payload, ~1/5 lần model quên. Sửa:
  `bind_book` điền `document_id` của cuốn đang gắn (cả khi model gửi `""`), và `nodes` khi
  `topic_scope` khớp **đúng một** mục theo nhãn BE đã dựng, tên kèm số, hay tên trần. Review B7 bắt
  ba lỗ của bản đầu, đã sửa và có test: khớp trên cây của cuốn đang gắn khi model đã chọn cuốn khác
  (nay bỏ qua bước ấy); hai mục cùng tên *"LUYỆN TẬP CHUNG"* thì lấy mục đầu (nay khoá trùng bị bỏ,
  nhãn đầy đủ giữ khoảng trang để phân biệt); `document_id: ""` lọt qua `vet_plan`. Thêm: đọc mục lục
  giữa lượt làm tham số tài liệu tuỳ chọn lại (nay `bound` đi theo), và chip của tài liệu **hỏng**
  bị báo *"đang xử lý, chờ"* mãi (nay `AttachedDocument.state`; AGENT nói tài liệu không dùng được).
- **Review lần cuối (các bản sửa B7)**, năm lỗi, đã sửa, có test và đột biến thử: `nodes` đọc từ
  mục lục của **cuốn khác** bị gắn vào cuốn đang gắn (nay không điền khi lượt đã đọc cuốn khác);
  chip của job **đã chết** -- cột còn `processing` -- bị báo *"chờ"* (nay `believed_state`, cùng phép
  so với thư viện); chip chưa dùng được vẫn mở được đề không sách (nay `create_draft` rời catalog
  lượt ấy); xin đề không sách trong đoạn chat gắn sách nhận câu chung *"nói lại"* (nay nói lý do và
  đường ra: mở đoạn chat mới); nhãn *"1.. MÔ TẢ"* (nay `coverage.heading`).
- **Giới hạn đã biết:** đoạn chat chọn sách **chỉ** qua `list_documents` (không chip nào) thì không có
  cuốn *đang gắn*, nên `bind_book` không chạy và tham số tài liệu vẫn tuỳ chọn -- model bỏ
  `document_id` thì đề mở không sách. Đóng được bằng cách nhớ cuốn model chọn ở `create_draft` trước,
  chưa làm.
- **Còn lại, ghi nhận:** model đôi khi hỏi lại *"tên chương 1"* mà chưa gọi `list_chapters` (một lần
  trong ba lượt mở đầu), hoặc hỏi một câu thừa khi sách chỉ có một chương; một lần trong bảy lượt dựng
  lại, plan thiếu bước `start_drafting` (đề mở ra không câu). Bộ nhãn router 40 ca: recall 100%.

