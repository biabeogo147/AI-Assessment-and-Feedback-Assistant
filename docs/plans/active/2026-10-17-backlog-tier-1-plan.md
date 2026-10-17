# Dọn sạch Tier 1 của backlog, rồi dọn backlog + artifact theo Tier 5

## Goal
Hai subagent tranh luận + một trọng tài (17/10/2026) đã xếp `docs/plans/backlog.md` thành năm tier,
ghi ở artifact **Backlog theo tier** (https://claude.ai/code/artifact/7c8634da-f294-4a07-a4a8-38b5ea997be8,
doc id `7c8634da-f294-4a07-a4a8-38b5ea997be8`). Tier 1 = 20 việc nhanh gọn, không cần quyết định nghiệp vụ;
nhiều việc là lỗi **Nặng** người dùng thấy được (giờ UTC, đổi nhầm tên đề, câu biến thể lặp câu gốc,
câu mock vào đề, lượt pha 2 mất ở tab mới).

Người dùng chốt (17/10):
- Làm hết Tier 1, **kể cả câu mock** (gỡ lệnh hoãn).
- **Gỡ chip nguồn bịa** (Tier 2 câu 1 = A) — làm cùng plan, vì nó gắn với lưới câu gần trùng.
- Cho phép trước thử tay trên **Claude Haiku 5.5** cho các việc có dấu `$` (ước 0,10–0,20 USD; báo
  thật trong biên bản).
- Mỗi pha một commit.
- Luật của đợt: **mọi lượt review bắt được lỗi gì cũng ghi vào backlog + artifact, xếp vào tier
  hợp lý**. Còn Tier 1 thì làm tiếp và review lại. Hết Tier 1 thì làm Tier 5: dọn toàn bộ backlog và
  artifact cho khỏi phình, khỏi rác.

## Scope

- Trong phạm vi: 20 việc Tier 1 của artifact *Backlog theo tier* (kể cả câu mock), gỡ chip nguồn bịa,
  mọi phát hiện Tier 1 mới của các vòng review trong plan, rồi dọn backlog và artifact theo Tier 5.
- Ngoài phạm vi: Tier 2 (trừ câu 1 = A), Tier 3, Tier 4 — chỉ ghi/xếp lại, không làm.
- `.\dev.ps1 check` xanh trước mỗi commit; `ruff format`; không commit `data/`, `.env`, ảnh,
  `docs/report/…pdf`, `docs/report/chapters/07-chi-tiet-cac-service.tex`; propose.py stage bằng
  `stage_propose.py` (bỏ hai dòng `# TODO: Cần xem lại`).
- FE: Figma trước, đo bằng nhau (`services/fe/AGENTS.md`); **mỗi pha có FE kết thúc bằng trình
  duyệt + một subagent chấm ảnh** (luật mới, không cần xin lại).
- Mỗi việc xong: dòng backlog gạch/ghi *đã làm* + commit; hàng artifact chuyển sang *Xong* (hay
  xoá ở pha dọn). Mỗi phát hiện mới: một dòng backlog + một hàng artifact ở tier đúng.
- Comment code tiếng Việt; test không gọi mạng.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `services/agent/src/agent/handlers.py`, `graphs/authoring.py`, `graphs/propose.py` | Câu mock, câu biến thể, `brief`/`known`, lượt dàn ý, `explain` |
| `services/be/src/be/drafting.py`, `agent_gateway.py`, `teacher_tools.py`, `teacher_chat.py`, `teacher_routes.py`, `student_routes.py`, `publication_wording.py`, `titles.py` | Lưới câu gần trùng, `validate_retry`, phạm vi tài liệu, tên đề, khoá, route đọc lại lượt pha 2, giờ |
| `services/fe/src/screens/teacher/{Panel,Chat,PublishSettings,ActionCard}.tsx`, `invented-not-from-be.ts`, `screens/student/{Round,Tutor,AssignmentList}.tsx`, `api.ts` | Đổi tên, giờ, chip, pha 2 làm tiếp, hộp xác nhận |
| `tools/check_contract.py`, `dev.ps1`, tests | Lưới và test nội bộ |
| `docs/plans/backlog.md`, `docs/decisions/*`, `docs/testing/*`, artifact *Backlog theo tier* | Ghi, xếp tier, dọn |

## Ordered Tasks
### Pha 0 — Khung
- [x] 1. Plan vào `docs/plans/active/`. Artifact thêm cột/ghi chú *Trạng thái* cho Tier 1 (Chưa làm /
   Đang làm / Xong) — một enum dropdown như cột *Quyết định* ở Tier 2. Tier 2 câu 1 đặt *A*.

### Pha 1 — Lỗi Nặng ở BE/AGENT (không đụng FE)
- [x] 2. **Câu mock vào đề** — `write_draft_question` (agent `graphs/authoring.py`, handlers): ép tool
   `strict` cho Claude; bỏ đường lùi về câu soạn sẵn khi model trả sai hình dạng → job **hỏng**, BE
   `_give_up_or_retry` (`drafting.py:724`) ghi `last_fault` rồi thử lại/`failed`. Cùng nguyên tắc:
   *Đề xuất dọn trước có thể là một plan thật* (propose) → không lùi về plan dọn trước. Test: tool
   hỏng hình dạng ⇒ không câu nào vào đề, ô `failed` sau 3 lần.
- [x] 3. **Câu biến thể dọn trước lặp câu gốc** (ADR-17:30) — `retry_question` (`handlers.py:408-439`):
   bỏ nhánh *câu gốc + đuôi*; khi LLM hỏng hoặc chạy mock mà câu không có trong `_VARIANT_BANK` thì
   raise. `validate_retry` (`agent_gateway.py:444-463`) từ chối cả *câu gốc + hậu tố* (gần lặp).
   BE vẫn 503 trước commit — không mất vòng (`student_routes.py:1990`, `db.py:78-91`). Chữ 503 thành
   câu cho học sinh (*"Chưa soạn được câu cho lượt này, em thử lại sau ít phút."*), không lộ chi tiết
   máy. Sửa docstring `handlers.py:125-128, 1014-1017`. Ghi rõ trong `local-development.md`: demo pha 2
   bằng mock chỉ chạy với câu của kho mock. Test: câu ngoài kho ⇒ 503, `rounds_used` = 0;
   `validate_retry` bắt câu có đuôi.
- [x] 4. **`_document_scope` đọc "1 2" thành 12** — một helper `_node_list(raw)` dùng chung cho
   `_read_section` (`teacher_tools.py:1009`) và `_document_scope` (`:1078`); test `create_draft` với
   `"1 2"`.
- [x] 5. **Bản vá `brief`/`known`** (gộp *Haiku để trống known*, *Lời đồng ý không thành plan khi brief
   rỗng*, *Mất số câu sau một lượt hỏi lại*): BE `outline_turn` (`teacher_chat.py:665`) lấp khoá rỗng
   của `brief` từ lượt `outline` gần nhất của đoạn chat (DB giữ đủ `tool_result`); AGENT `_miscounted`
   (`propose.py:1078`) khi `known` không có số câu thì tìm `N câu` trong lời giáo viên từ dàn ý gần
   nhất (kiểu `_since_plan`, `:615`; tránh *"thay câu 3"* bằng `_REPLACES`). Test ở
   `test_propose_outline.py` và BE. `$` ở pha 6.
- [x] 6. **Lưới câu gần trùng trong một đề** — `drafting.py` harvest (`:855`): `seen` thành danh sách, so
   gần trùng (chuẩn hoá `_comparable`, giữ phần toán `$…$` và số; trùng ⇒ `_give_up_or_retry(…,
   "đề trùng một câu đã có")`), bỏ chính câu đang được thay. `banned` của `fire` (`:404`) vẫn tính một
   lần — lưới ở harvest bắt được các job song song. Test: hai job ra $\frac{x}{6}=\frac{4}{9}$ khác
   chữ ⇒ một câu vào đề, ô kia thử lại.
- [x] 7. **`list_assessment` lọt đề đã thu hồi** — `_assessments_of` (`teacher_tools.py:277-288`) lọc
   `Publication.recalled_at IS NULL` như `_class_assessment_summary` (`:348`); test.
- [x] 8. Commit pha 1.

### Pha 2 — Lỗi Nặng ở FE (Figma trước)
- [x] 9. **Giờ UTC ở khối ĐÃ PHÁT HÀNH** — FE dựng câu luật của khối đã phát hành từ khuôn `rules`
   (`fill()`, `PublishSettings.tsx:928`) với giờ địa phương như biểu mẫu đang làm; BE bỏ hai câu dựng
   sẵn bằng UTC ở GET `/publications` (`teacher_routes.py:2074-2075`) — đổi `api.ts` cùng change set.
   Test BE + vitest với giờ có offset +07:00.
- [x] 10. **Ô đổi tên sống sang đề khác + Enter gửi nhiều lần** — `Panel.tsx:66-76` dọn `naming`,
  `trouble`, `solving` và bỏ kết quả fetch cũ khi đổi đề; Enter (`:257`) xét `working` và
  `nativeEvent.isComposing` (bộ gõ tiếng Việt). Vitest cho cả hai.
- [x] 11. **Lượt pha 2 không đọc lại được ở tab mới** — BE `GET /student/rounds/{round_id}` dùng
  `_owned_round` (`student_routes.py:2024`): 409 khi đã nộp, mục theo `order_index`, `chosen_label`,
  không lộ `is_correct`; `api.round()`. FE `Round.tsx`: thiếu `sessionStorage` thì đọc route ấy, điền
  `chosen` từ `chosen_label`; `Tutor.tsx`: có `open_round_id` thì nút *Làm tiếp lượt đang mở*. Figma
  artboard lượt pha 2 (trạng thái *làm tiếp*). Test BE (chủ sở hữu, 404 người khác) + vitest.
- [x] 12. **Gỡ chip nguồn bịa** (Tier 2 câu 1 = A) — bỏ `provenanceOf`/`PROVENANCES`
  (`invented-not-from-be.ts:64-80`) khỏi `QuestionCard` (`Panel.tsx:537`); Figma `Question card`
  bỏ chip. Cập nhật `teacher-surface.md`, sửa biên bản 17/10 ca 02 và dòng backlog *Hai ô…* (gốc là
  model viết hai câu gần trùng).
- [x] 13. Trình duyệt + subagent chấm ảnh (các màn đã đổi); sửa theo. Commit pha 2.

### Pha 3 — Lỗi Vừa
- [x] 14. `clipped()` rỗng ⇒ lùi `default_title` (`teacher_tools.py:515`); `_titled` đi vào danh sách lồng
  (`assessments: [{assessment_id, title}]`, `teacher_chat.py:1516`).
- [x] 15. `_owned` thêm `populate_existing` (`teacher_routes.py:174`, như `question_bank.py:46-54`); `fire`
  khoá `DraftBrief`/`Assessment` bằng `with_for_update` (`drafting.py:353-360`). Test đua bằng hai
  session nếu dựng được trên SQLite, không thì test đơn vị khoá được gọi.
- [x] 16. `_TooManyQuestions` đếm câu đã qua `asked()`; mức lựa chọn tối thiểu theo số dòng chỉ áp cho câu
  về dòng (lựa chọn khớp `candidates`), câu tham số vẫn ≥ 3 (`propose.py:1762-1775`).
- [x] 17. `explain` đổi thứ tự: `publish` trước rồi mới `append` (`handlers.py:1072-1074`).
- [x] 18. `Chat.tsx:224-248` gắn số thứ tự cho lời gọi `documents()`, bỏ kết quả cũ.
- [x] 19. Lý do bước ✕: BE viết `reason` cho giáo viên (không tên tool/field) — các chỗ ở
  `teacher_tools.py:231, 257, 1016, 1082, 1093, 1099`; model vẫn nhận bản kỹ thuật nếu cần (tách
  `reason` hiển thị / `hint` cho model nếu hợp đồng cho phép, không thì đổi chữ).
- [x] 20. Bốn lỗi lượt dàn ý: chữ *sách* trong lời phủ định (`propose.py:200`, nhận *ko/không/k/hok*);
  plan soạn sau lời **xin sửa** dàn ý không qua cổng; `_read_before_outline` không để lọt dàn ý đọc
  dở; BE dừng sớm khi dàn ý bị trả về lặp lại (như plan bị từ chối lặp lại). `$` ở pha 6.
- [x] 21. `submit_round`: một test + comment nói rõ hành vi đúng ADR-15 (phần đã lưu trước `ends_at`).
- [x] 22. Commit pha 3.

### Pha 4 — Lỗi Nhẹ: giao diện đi cùng Figma, lưới/test, tài liệu
- [x] 23. Giao diện (Figma trước): tiêu đề panel không bẻ trong ngoặc (`teacher.css:1752`, `min-width:0`,
  gạch nối không ngắt); lượt hỏi nhiều câu đã qua hiện nhãn (`Chat.tsx` `aloud`); hộp xác nhận khi
  **bắt đầu pha 1** (`AssignmentList.tsx:54-58`) và khi **nộp lượt pha 2** (`Round.tsx:162`), theo
  mẫu `Sitting.tsx:153-198`; dòng nhắc khi tên đề chạm 60; `·` trong chữ tự ghi của tin gộp; vạch
  chia rail (đối chiếu artboard); `Question card` bỏ trục một giá trị (chỉ Figma).
  *Variant `phát-hành-thất-bại`*: BE chưa ghi lần phát hành hỏng (`_note_publication`) — không
  phải việc FE; chuyển dòng này sang Tier 3 trong backlog + artifact.
- [x] 24. Lưới và test nội bộ: check timeout-order tính model dự phòng / `max_retries` (`llm.py:129`);
  `check_contract` bắt `Assessment(state=…)`; lưới `config.py` ↔ `.env.example`; canh `document`
  không mở HTTP; `test_no_routing_decision` lượt mô hình bật; test đồng hồ 15,6 ms; seam Paddle; bỏ
  `job_result_ttl_seconds`; `vet_plan` bắt id chuỗi số trần; ba lỗi nhỏ dàn ý (mục của câu bị thay,
  `IntegrityError` cuộn `brief.outline`, `model_tokens`); bench `be_refuses`; nợ 3c (D1, "1.1", khe
  id, chunk > 1 500); chặn tần suất mở stream ở BE (trần rộng); `--reload` (sửa `dev.ps1`); phép ghép
  lời mở + câu hỏi thành một hàm trong `contracts` và `except Exception` ở banner (chạm contracts —
  decision record ngắn trong plan này).
- [x] 25. Tài liệu: hậu ký có ngày cho ADR ghi trạng thái cũ (gồm ADR-15:78-80, ADR-16:26) và ba ADR đường
  chấm cũ; docstring sai (`handlers.py:3-6`, `content_reader.py:5-6`, `index/graph.py:85-86`); FE nói
  `fault` có sáu giá trị (`Rail.tsx:305`); `docs/decisions/README.md`; `02:67`; hình
  `activity-overview` vượt trang; `rules.md` *Những chỗ đã biết là còn sai*; `AGENTS.md` nói sai (có
  decision record). **Không đụng `07-chi-tiet-cac-service.tex`** (phiên khác).
  Ảnh linh vật (PNG khung vuông, hạ bão hoà) là việc người vẽ — không làm bằng code; chuyển khỏi
  Tier 1 (ghi *việc ngoài code*).
- [x] 26. Trình duyệt + subagent chấm ảnh cho các màn đã đổi ở việc 23; sửa theo. Commit pha 4.

### Pha 5 — Vòng review cho tới khi hết Tier 1
- [ ] 27. **Một subagent review code** của cả plan (pha 1–4). Mọi phát hiện → một dòng backlog + một hàng
  artifact, xếp tier (luật tier của artifact). Tier 1 mới ⇒ làm, commit, **review lại**; lặp tới khi
  review không ra Tier 1 nào.

### Pha 6 — Thử tay trên model thật (Haiku 5.5, đã cho phép)
- [ ] 28. `db-reset`, khởi động lại BE/AGENT/worker, kiểm `model=` trong log. Case 01, 02, 03, 04, 07 (dàn
  ý, đồng ý, xin sửa, đếm câu, câu mock/trùng) + luồng học sinh pha 2: mở lượt, đóng tab, mở tab mới
  làm tiếp, nộp (ca mới `16-pha-2-tab-moi.md` trong `docs/testing/cases/`). Ảnh chụp; biên bản
  `docs/testing/ket-qua/2026-10-<dd>-<commit>-claude-haiku-5-5.md` có chi phí thật.
- [ ] 29. **Một subagent chấm ảnh + biên bản.** Phát hiện → backlog + artifact theo tier; còn Tier 1 thì quay
  lại pha 5.

### Pha 7 — Tier 5: dọn backlog + artifact
- [ ] 30. `backlog.md`: xoá các dòng Tier 5 *Đóng* (bằng chứng ghi trong commit message, không giữ lại
  trong file); gạch-và-xoá các dòng Tier 1 đã làm; viết lại mục *Luồng học sinh* (`backlog:174-192`);
  sửa vật chặn sai; gom năm dòng vào một mục *Khi có process/BE thứ hai*; sửa các ghi chép sai
  (biên bản 17/10, *Khối ĐÃ PHÁT HÀNH* là BE, *mốc đạt chưa ai chốt*, ghi chú 30/09
  `class_assessments`). Gộp các dòng trùng gốc. Mục *đã đóng* cũ (gạch ngang) bỏ hẳn.
- [ ] 31. Artifact: xoá bảng Tier 1 đã xong (giữ một dòng tổng *đã làm ở plan này*), Tier 5 thay bằng các
  dòng còn phải dọn (nếu còn); Tier 2–4 cập nhật dòng đã đổi; ngày as-of.
- [ ] 32. Rác file: liệt kê file thừa trong repo (`git status`, file không còn ai tham chiếu, kết quả
  bench cũ trong thư mục đã commit) — **báo danh sách cho người dùng trước khi xoá**. Scratchpad
  không thuộc repo, không đụng.
- [ ] 33. Đóng plan (Status, `completed/`), `.\dev.ps1 check`, commit.

## Decision Records

Các thay đổi mà `AGENTS.md` (*Planning Requirements*) đòi phải có plan và decision record:

- **DR-1 — `AGENTS.md` và `services/be/AGENTS.md` sửa chữ cho khớp code (pha 4).** `agent` không
  chấm bài (*"AI grading"* là đường chấm cũ, xoá 09/10/2026); `withdraw` cũng đặt `Assessment.state`;
  đường ghi câu dùng `assert_editable` hay `editable()`; không client nào poll. Không luật nào đổi.
- **DR-2 — `.env.example` khai thêm năm biến đã được đọc** (`DEV_IDENTITY_HEADER`,
  `READ_STEP_SECONDS`, `JEV_CONCURRENCY`, `JEV_TIMEOUT_SECONDS`, `LLM_CONCURRENCY`) và check
  `env-example` đi cả chiều ngược: trường `config.py` đọc mà `.env.example` không khai thì đỏ.
  `be/config.py` bỏ `job_result_ttl_seconds` (BE không dùng; AGENT vẫn đọc biến ấy).
- **DR-3 — ba lưới mới ở `check_contract`**: `Assessment(state=…)` khác `EMPTY` trong tool;
  `document-opens-no-port`; `refusal-said` (lời từ chối chở tên tool/tham số phải kèm `said`).
- **DR-4 — hai trường mới trên endpoint**: `RoundOpenOut.started_at` (đầu màn lượt chữa in độ dài
  lượt) và `PublishedTo.recallable` (đồng hồ BE nói còn thu hồi được không). `api.ts` đổi cùng
  change set.
- **DR-5 — các món Tier 1 chuyển tier vì cần quyết định hay cần plan riêng** (ghi ở backlog và
  artifact): check `timeout-order` tính lần thử lại của SDK thì đỏ (3 + 20 × 3 × 3 = 183 s so với
  70 s) — chọn bỏ thử lại SDK hay nới ngân sách là quyết định (Tier 2); câu luật ` - ` / `—` và
  chữ *"làm."* rớt dòng chạm nguyên văn ADR-03 (Tier 2); seam Paddle (Tier 2); nợ 3c, `except
  Exception` ở banner (Tier 3 P6); phép ghép lời mở + câu hỏi vào `contracts` (Tier 3 P4); chặn tần
  suất mở stream, `--reload` (Tier 3); bench `be_refuses` (Tier 4); bốn món của báo cáo
  (`docs/report/`) là việc của phiên báo cáo.

## Validation Checks
- `.\dev.ps1 check`, `.\dev.ps1 test`, `.\dev.ps1 typecheck`, `ruff format --check` xanh ở mỗi commit.
- Mỗi lỗi một test chứng minh nó (đỏ trước khi sửa, xanh sau).
- Trình duyệt: khối ĐÃ PHÁT HÀNH ra giờ +07:00 khớp ô giờ mở; đổi đề khi ô đổi tên đang mở thì ô
  đóng; pha 2 đóng tab → tab mới *Làm tiếp* ra đúng câu và lựa chọn đã lưu; panel không còn chip
  nguồn; hai hộp xác nhận mới.
- Model thật (pha 6): *oke* sau dàn ý ra plan; xin 5 câu sau hỏi lại vẫn 5; không câu mock nào vào đề
  (`last_fault` khi hỏng); không hai câu gần trùng trong một đề; câu biến thể pha 2 khác câu gốc.
- Artifact và backlog khớp nhau ở cuối plan (mỗi hàng artifact có dòng backlog, và ngược lại).

## Status

Pha 0–4 đã commit (`c93a482`, `53a8724`, `6bc8daf`, `0fe3a4c`, `6e30e8a`). Pha 5, vòng review 1: 15
phát hiện, 13 Tier 1 đã sửa (chờ commit), #3 phần định nghĩa *gần trùng* và #14 sang Tier 2. Kế
tiếp: commit vòng 1, rồi review lại.
