# Plan — chia `propose.py` thành package `propose/`, không đổi logic

- **Mở:** 20/10/2026 · **Đóng:** 20/10/2026 (`615b153`)

## Context

`services/agent/src/agent/graphs/propose.py` dài 2111 dòng, gồm prompt, schema câu trả lời model,
các luật thứ tự đọc, luật dàn ý, luật plan, node compose/choose và vòng hỏi lại. Người dùng muốn
đọc code dễ hơn khi phân tích lỗi V6 (hỏi lại rỗng): chia thành package nhiều file, **không đổi một
dòng logic**. Thiết kế dưới đây đã qua một vòng tranh luận với subagent Plan, nó đọc trọn file và
dựng đồ thị phụ thuộc bằng AST.

Kèm theo:
- Hai dòng `# TODO: Cần xem lại` (ghi chú riêng của người dùng) đã lỡ vào commit `abed4a2`. **Gỡ
  khỏi repo nhưng giữ trong working tree**; khi chia file, mỗi dòng đi theo code ngay dưới nó.
- Ghi vào backlog (file `.md` **và** artifact *Backlog theo tier*
  `https://claude.ai/artifact/GNrWBaJmMRSKJsFeRqscJK`) lỗi V6 vừa tìm và các lỗi lộ ra khi chia.

## Ràng buộc

- Mọi thân hàm, regex, chuỗi prompt, comment chuyển **nguyên văn**; chỉ import đổi. Thứ tự tương
  đối của các symbol trong mỗi file giữ như gốc.
- Không sửa lỗi nào tìm thấy: chỉ ghi backlog.
- Không đụng `docs/report/`, `services/document`. File ghi bằng Python `newline="\n"`.
- Commit chỉ khi người dùng duyệt; trước commit chạy `.\dev.ps1 check`.

## Cấu trúc package `services/agent/src/agent/graphs/propose/`

Phân tầng không vòng (L0 → L5); submodule import tuyệt đối từ anh em, **không bao giờ**
`from agent.graphs.propose import …`.

| File | Symbol (theo thứ tự gốc) | Việc |
|---|---|---|
| `__init__.py` | docstring gốc (dòng 1–33), `__all__` 28 tên dùng từ ngoài | chỉ re-export |
| `prompt.py` (L0) | khối comment 60–66 **kèm TODO 1**, `_CORE`, `_BOOK_PROCEDURE`, `_LIBRARY_SLOT`, `_LIBRARY` | chữ cố định model đọc |
| `proposal.py` (L0) | `_nfc`, `_Argument`, `_OutlineItem`, `_Step`, `_unmangled`, `_Question`, `_Proposal` | hình dạng câu trả lời model → `NextStepCompleted` |
| `ask_again.py` (L0) | `_AskAgain` … `_FewChoices`, `_WANTED` | tín hiệu hỏi model lại một lần |
| `clarify.py` (L0) | `_answers`, `_choices_wanted`, `_choices_in`, `_row_names`, `_OTHER` | nút của câu hỏi lại |
| `history.py` (L1) | `_since_plan`, `_called_since_plan`, `_tables_read`, `_listed_documents`, `_picked_document` | đọc lịch sử từ plan gần nhất |
| `books.py` (L1) | `_BOOK_WORDS`, `_NOT_A_BOOK`, `_NO_BOOK`, `_mentions_book`, `_DOCUMENT_READS`, `_book_in_view`, `_opens_library` | lượt có sách không, có mở thư viện không |
| `read_order.py` (L2) | `_read_before_outline`, `_library_first`, `_reads_first`, `_toc_first`, `_picked_book_first`, `_misfiled_read`, `_ASKS_WHICH_BOOK`, `_MARKUP`, `_asks_which_book`, `_which_book` | luật thứ tự đọc |
| `outline.py` (L2) | regex đếm/đồng ý (`_COUNT_IN_KNOWN` … `_KNOWN_FIELD`), `_brief_in`, `_approved_plan`, `_HAS_DRAFT`, `_right_purpose`, `_count_said`, `_count_revised`, `_GRADE_NUMBER`, `_TRIMS`, `_miscounted` | đồng ý dàn ý, đúng việc, đếm câu (ADR-29) |
| `plan_checks.py` (L3) | `_CONTROL`, `_garbled`, `_REVISES`, `_drafts_over_a_revision`, regex trợ từ … `_NO_CHANGE`, `_lacking` | kiểm hình dạng plan |
| `compose.py` (L3) | `ProposeState`, `_describe_tool`, `_describe_result`, `_compose` (**kèm TODO 2** tại chỗ), `_asked_back`, `_outline_items` | node 1: dựng messages |
| `choose.py` (L4) | `_spent`, `_choose` | node 2: gọi model, áp luật |
| `graph.py` (L5) | `_UNCLEAR`, `_build`, `_GRAPH`, `propose` | lắp graph, vòng hỏi lại |

Quyết định đi kèm:
- `from agent import llm, skill_router, skills` và gọi qua thuộc tính, như gốc — giữ mọi
  `monkeypatch.setattr(llm|skill_router, …)` của test.
- `choose.py` import `_unmangled` bằng tên (check `escape-repair-is-wired-in` chỉ nhận `ast.Name`).
- Logger: `logging.getLogger("agent.graphs.propose")` ở `read_order`, `outline`, `choose`, `graph`,
  để log giữ nguyên tên như trước (worker in `%(name)s`; bench gắn handler vào tên ấy).
- Mỗi file mới có một docstring tiếng Việt ngắn 1–3 dòng nói file làm gì (chữ mới, không phải logic).
- Không đặt tên `schema.py` (trùng package `packages/schema`).

## Thay đổi ngoài package

- `services/agent/tests/test_propose_outline.py:12, :282`: monkeypatch `_opens_library` trên
  `agent.graphs.propose.read_order` (patch thuộc tính package không tới được globals của submodule).
- `tools/check_contract.py`:
  - `:892` `graphs.glob("*.py")` → `rglob`, `:916` dùng đường dẫn tương đối; đỏ khi không tìm thấy
    chỗ `with_structured_output` nào (để check không mù).
  - `:2221` thay `graphs/propose.py` bằng mọi file trong `graphs/propose/`; đỏ khi danh sách rỗng;
    hợp `_module_strings` của các file trong package vào tập hằng (`_UNCLEAR` nằm ở `graph.py`).
- Đường dẫn cũ: `skills.py:14`, `skill_router.py:18`, `packages/contracts/tests/test_teacher_plan.py:41`
  (comment), `docs/testing/cases/06-soan-them-cau.md:42`, `13-tai-lieu-scan.md:50`; hậu ký ngắn
  20/10/2026 ở ADR-23, ADR-25, ADR-29 (đường dẫn mới). Plan cũ trong `completed/` giữ nguyên.

## Hai dòng TODO

1. Commit riêng *gỡ hai dòng TODO*: đặt vào index bản `propose.py` không có hai dòng ấy
   (`git hash-object -w` + `git update-index --cacheinfo`), working tree giữ nguyên.
2. Khi chia, script cắt mỗi câu lệnh top-level **kèm các dòng comment ngay trên nó**, chạy trên file
   working tree, nên TODO 1 vào `prompt.py` trên `_CORE`, TODO 2 ở yên trong `_compose`
   (`compose.py`). Stage `prompt.py` và `compose.py` bằng blob đã bỏ đúng hai dòng ấy.
3. Backlog dòng *"Hai dòng `# TODO: Cần xem lại` trong `propose.py` chưa stage"* sửa thành vị trí mới
   (`propose/prompt.py`, `propose/compose.py`), ghi theo tên symbol.

## Backlog (`docs/plans/backlog.md` và artifact)

Thêm vào mục *Lộ ra khi chạy kịch bản thử tay đầu-cuối*:
- **V6: Kriky hỏi lại mà không có câu hỏi** — `known` đủ bốn mục vẫn chọn `ask_clarify`, 0 lựa
  chọn hai lần; `_FewChoices` hỏi lại không `hint`; `propose` vẫn giữ câu hỏi ít nút; FE
  `questionIn` trả `null` khi 0 nút nên không có ô "Khác". Ba hướng A/B/C đã báo, chưa chọn. Log
  không ghi câu trả lời thô của model.

Mục mới *Lộ ra khi chia `propose.py` (20/10/2026)* — lỗi tiềm ẩn, không sửa:
- lượt `plan` tới model như kết quả tool không tên (nhánh `else` của `_compose`, chỗ TODO 2);
- NFC không đồng đều: `_count_said`, `_count_revised`, `_drafts_over_a_revision` (và
  `handlers` `_AGREES.search`) khớp chữ thô, các luật khác chuẩn hoá NFC trước;
- lời mở của plan đã đồng ý (`_approved_plan`) bỏ qua `_unmangled`/`_nfc`;
- `_read_before_outline` ghép lời gọi với kết quả theo chỉ số; `int(node)` có thể ném
  `ValueError` không phải `_AskAgain`;
- `_UncountedOutline` chọn hint bằng cách đọc chuỗi log tiếng Anh của `_miscounted`;
- `handlers.py` import `_AGREES` riêng tư xuyên module.

Sửa luôn các dòng backlog trỏ số dòng đã trôi (`propose.py:1360`, `:820-824`) thành tên symbol.
Artifact: đọc bản hiện tại, thêm cùng các dòng, publish lại cùng URL.

## Các bước

1. Plan trong repo: `docs/plans/active/2026-10-20-split-propose-package-plan.md`.
2. Commit gỡ TODO (mục *Hai dòng TODO*, bước 1) — sau khi người dùng duyệt plan này.
3. Script sinh package từ file working tree theo bảng trên; assert mỗi câu lệnh vào đúng một file;
   `git rm` file cũ; sửa test và `check_contract`; `ruff check --fix`, `ruff format`.
4. Chứng minh không đổi logic (script scratchpad, so với `propose.py` gốc):
   - AST và đoạn source của từng câu lệnh bằng nhau ở nhà mới;
   - multiset comment (`tokenize.COMMENT`) bằng nhau, trừ docstring đầu file mới;
   - bytecode từng hàm/method (`co_code`, `co_consts`, `co_names`, …) bằng nhau;
   - regex `.pattern`/`.flags`, hằng chuỗi, `.hint` từng lớp, `_Proposal.model_json_schema()` bằng
     nhau; mỗi tên trong `__all__` là cùng object với nhà của nó.
5. `.\dev.ps1 test`, `.\dev.ps1 check`. Thử đột biến rồi hoàn: bỏ `_unmangled(` trong `choose.py`
   → `escape-repair-is-wired-in` đỏ; bỏ `notice=True` ở `graph.py` → `kriky-says-nothing-fixed` đỏ;
   hoàn sửa test `:282` → test ấy đỏ.
6. Tài liệu, backlog `.md`, artifact.
7. Subagent review đọc code thật (theo memory *subagent review sau mỗi plan*); sửa theo review.
8. Khởi động lại AGENT (TaskStop `bp4vw5g0s`, kiểm không còn tiến trình, `dev.ps1 agent` ở nền) để
   tiến trình chạy package mới; kiểm log khởi động sạch. Không chạy model thật.
9. Stage theo hai commit (refactor; docs + backlog), báo người dùng, **chờ duyệt rồi mới commit**;
   plan chuyển `completed/` trong commit cuối.

## Verification

- Script ở bước 4 in "khớp" cho mọi câu lệnh; không câu lệnh nào thiếu hay trùng.
- `.\dev.ps1 test` và `.\dev.ps1 check` xanh; ba phép đột biến đỏ đúng chỗ.
- `git diff --cached` của các file package không có dòng `TODO: Cần xem lại`; working tree vẫn có.
- AGENT khởi động lại không lỗi import.
