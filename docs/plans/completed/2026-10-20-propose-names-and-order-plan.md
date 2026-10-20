# Plan — package `propose/`: tên public/private đúng chỗ, hàm trên gọi hàm dưới

- **Mở:** 20/10/2026 · **Đóng:** 20/10/2026 (`d66bfab`)

## Context

Lần chia `propose.py` thành 13 file (`615b153`) giữ nguyên tên và thứ tự của file gốc. Vì thế:
- các file import `_x` của nhau: 45 tên riêng tư bị dùng chéo file (mùi `import-private-name`);
- trong mỗi file, helper đứng trước hàm gọi nó, nên người đọc gặp chi tiết trước ý chính.

Người dùng muốn ba quy tắc (đã bàn, hợp quy ước chung — PEP 8 về `_`, stepdown rule):
1. Tên chỉ dùng trong file của nó → `_x`.
2. Tên được file khác dùng → không `_`.
3. Trong một file, hàm trên gọi hàm dưới.

Vẫn là **không đổi logic**, chứng minh bằng máy. Plan đã qua một vòng review của subagent (sửa thứ tự
topo, chỗ dùng qua thuộc tính package, đổi chữ có tiền tố, phép chứng minh vòng tròn).

Đã chốt với người dùng 20/10/2026:
- **"Dùng ở file khác" chỉ tính code sản phẩm.** Test import `_x` để thử hàm nội bộ thì `_x` vẫn private.
- **Năm lớp pydantic giữ `_`**: `_Proposal`, `_Argument`, `_Step`, `_OutlineItem`, `_Question`. Tên lớp
  là tên tool (`_Proposal`) và tên `$defs` trong schema gửi model; `test_no_routing_decision.py` cũng
  khoá theo `"_Proposal"`. Thêm một comment ở `proposal.py` nói vì sao.

## Ràng buộc

- Thân hàm, regex, chuỗi prompt, chuỗi lỗi, hint: **nguyên văn**. Chỉ đổi định danh (tên def, import,
  chỗ dùng, ba biến cục bộ của `_choose`) và chữ trong comment/docstring nhắc tên ấy.
- Hai dòng `# TODO: Cần xem lại` (`prompt.py`, `compose.py`): không xoá, không stage, không commit; khi
  dời code, đi theo câu lệnh ngay dưới nó. Stage hai file ấy bằng blob đã bỏ đúng hai dòng.
- Chỉ đổi tham chiếu **trỏ đúng vào package `propose`** (xem mục 3).
- Không đụng `docs/report/`, plan trong `completed/`, biên bản `docs/testing/ket-qua/` (lịch sử).
- File ghi bằng Python `newline="\n"`. Commit chỉ khi người dùng duyệt; trước commit `.\dev.ps1 check`.

## 1. Đổi tên: 45 tên, chỉ bỏ `_` đầu

Tên được một submodule khác (hay code sản phẩm ngoài package) import. Review đã tính lại bằng AST trên
mọi file `.py` không phải test: đúng 45 tên, không va chạm nào ngoài ba biến cục bộ của
`choose._choose`. Với ba chỗ ấy **đổi biến cục bộ**, không đổi tên hàm, để quy tắc thuần "bỏ `_`":
`answers` → `choices`, `lacking` và `miscounted` → `flaw` (khớp `_Flawed.__init__(self, flaw, step)`);
`choices`, `flaw` chưa có trong `_choose`.

| File | Đổi (bỏ `_`) | Giữ `_` |
|---|---|---|
| `prompt.py` | `CORE`, `BOOK_PROCEDURE`, `LIBRARY`, `LIBRARY_SLOT` | — |
| `proposal.py` | `unmangled`, `nfc` | 5 lớp pydantic |
| `ask_again.py` | `AskAgain`, `NothingToSay`, `Flawed`, `IncompletePlan`, `NoOutline`, `UncountedOutline`, `PlanOverRevision`, `WrongQuestion`, `TooManyQuestions`, `FewChoices` | `_WANTED` |
| `clarify.py` | `answers`, `choices_wanted`, `choices_in`, `row_names` | `_OTHER` |
| `history.py` | 5 hàm | — |
| `books.py` | `DOCUMENT_READS`, `book_in_view`, `opens_library` | `_mentions_book`, 3 regex |
| `read_order.py` | 7 luật (`reads_first` … `read_before_outline`) | `_asks_which_book`, 2 regex |
| `outline.py` | `AGREES`, `approved_plan`, `brief_in`, `right_purpose`, `miscounted` | regex, `_count_said`, `_count_revised` |
| `plan_checks.py` | `garbled`, `drafts_over_a_revision`, `lacking` | regex |
| `compose.py` | `compose` (`ProposeState` đã public) | 4 helper |
| `choose.py` | `choose` | `_spent` |
| `graph.py` | (`propose` đã public) | `_UNCLEAR`, `_build`, `_GRAPH` |

`__init__.py` re-export **chỉ** `propose`; `handlers.py` import `AGREES` thẳng từ
`agent.graphs.propose.outline`. Một dòng comment ở `__init__` dặn không re-export `compose`/`choose` (tên
trùng submodule: re-export là che mất submodule). Test và tool import từ submodule, kể cả chỗ dùng qua
thuộc tính package: `tools/tests/test_propose_bench.py:105-143` (`propose._CORE` →
`propose.prompt.CORE`, `propose._Proposal` → `propose.proposal._Proposal`).

## 2. Thứ tự trong mỗi file

Mỗi file: docstring → import → `logger` → hằng, regex, lớp (**giữ thứ tự gốc**: chúng chạy lúc import —
`_AGREES` dựng từ `_AGREE_WORD`, `_NO_CHANGE` từ các regex trợ từ, `_Step` dùng `_Argument`, `_Proposal`
dùng bốn lớp kia) → **hàm theo thứ tự topo**: với mọi cạnh gọi f → g trong cùng file, f đứng trên g;
giữa các hàm không ràng buộc nhau, xếp theo lần đầu nơi gọi dùng chúng. Câu lệnh tầng module gọi hàm lúc
import (`_GRAPH = _build()`) xuống cuối file. Comment ngay trên một câu lệnh đi theo nó.

Review đã kiểm an toàn lúc import: không decorator, không default argument trỏ hàm của package, chú thích
kiểu chỉ dùng kiểu import hay `ProposeState` (một lớp, ở trên), `"_Proposal"` trong `_unmangled` là chuỗi.

| File | Thứ tự hàm |
|---|---|
| `graph.py` | `propose` → `_build`, rồi `_GRAPH = _build()` |
| `choose.py` | `choose` → `_spent` |
| `compose.py` | `compose` → `_describe_tool` → `_asked_back` → `_outline_items` → `_describe_result` |
| `read_order.py` | `reads_first` → `picked_book_first` → `misfiled_read` → `toc_first` → `library_first` → `which_book` → `_asks_which_book` → `read_before_outline` |
| `outline.py` | `approved_plan` → `right_purpose` → `brief_in` → `miscounted` → `_count_said` → `_count_revised` |
| `plan_checks.py` | `lacking` → `garbled` → `drafts_over_a_revision` |
| `clarify.py` | `answers` → `row_names` → `choices_wanted` → `choices_in` |
| `history.py` | `called_since_plan` → `picked_document` → `listed_documents` → `tables_read` → `since_plan` |
| `books.py` | `opens_library` → `book_in_view` → `_mentions_book` |
| `proposal.py` | lớp trước; rồi `unmangled` → `nfc` |
| `prompt.py`, `ask_again.py` | chỉ hằng/lớp, giữ thứ tự |

Script tính lại thứ tự từ đồ thị gọi thật, rồi so với bảng này; lệch thì dừng.

## 3. Ngoài package

- **Đổi chữ có tiền tố:** chỉ đổi token **không tiền tố, hay có tiền tố `propose` / tên một submodule**.
  **Không đổi**: `teacher_chat._DOCUMENT_READS` (`books.py:54`), `authoring._unmangled` (docstring
  `check_contract.py` ~870, `test_authoring_graph.py:327`), `explain._compose`, `rules._garbled`
  (document), `gold._nfc`. Script in **mọi chữ đổi trong comment/docstring** để rà tay; phần ấy không
  được "chứng minh" bằng chính bộ ánh xạ.
- **Code sản phẩm:** `handlers.py` (`AGREES` từ `propose.outline`); comment `worker.py:95` (`_Flawed`),
  `be/teacher_chat.py:708` (`_approved_plan`), docstring `__init__` (`_Flawed`, `_CORE`),
  `skill_router.py:19`, `skills.py`, `be/teacher_tools.py`.
- **Check** `tools/check_contract.py`, `escape-repair-is-wired-in`: đòi `unmangled` cho
  `propose/choose.py` và `_unmangled` cho `authoring.py`, **theo từng file** (không nới một tập tên chung);
  guard `propose/choose.py:_choose` → `propose/choose.py:choose`. Rà `tools/tests/test_check_contract.py`.
  `kriky-says-nothing-fixed` tự dựng tập hằng từ file, không phải sửa.
- **Test và tool:** `test_propose_graph.py`, `test_propose_outline.py` (monkeypatch
  `read_order, "opens_library"`), `test_draft_from_document.py`, `test_skills.py` (gồm dòng 229),
  `test_revision_words.py`, `test_no_routing_decision.py`, `tools/tests/test_propose_bench.py` (gồm dòng
  263 *"Hai bản `_DOCUMENT_READS`"*, sửa tay), `tools/propose_bench/run.py` (gồm dòng 166).
- **Tài liệu còn sống** (ADR: bảng *Nơi thi hành* và hậu ký; `docs/plans/backlog.md`;
  `docs/testing/cases/`): một cách viết duy nhất `propose/<file>.<tên>` (vd. `propose/outline.AGREES`),
  vì `propose._x` không còn là thuộc tính package. Chỗ mơ hồ rà tay. Một hậu ký ngắn ở ADR-30 (nhiều tên
  nhất) dẫn tới bảng đổi tên của plan.

## 4. Cách làm và chứng minh

1. Plan trong repo `docs/plans/completed/2026-10-20-propose-names-and-order-plan.md`.
2. Script scratchpad (mở rộng `split_propose.py`): đọc package hiện tại (working tree, có TODO); đổi
   định danh qua AST + vị trí token (không thay chữ thô); xếp lại câu lệnh theo mục 2; ghi file; `ruff
   check --fix`, `ruff format`.
3. Script chứng minh (mở rộng `prove_split.py`), so với `HEAD`:
   - ánh xạ tên chỉ áp lên `Name`, alias import, tên def/class, và `Attribute` trên một module propose;
     ba biến cục bộ của `_choose` ánh xạ riêng;
   - **mọi hằng chuỗi không phải docstring giống từng byte, không ánh xạ** (review: không chuỗi nào model
     đọc chứa tên cũ; chỉ `__all__` và chuỗi trong `check_contract.py`, sửa tay);
   - import so như tập (isort xếp lại tên khi bỏ `_`);
   - bytecode đệ quy qua mọi code object con (genexpr, lambda, hàm lồng `scope` của
     `read_before_outline`, thân lớp, method): bỏ qua `co_firstlineno`, `co_linetable`, vị trí; ánh xạ
     `co_names`, `co_name`, `co_qualname`, và `co_varnames` của `_choose`; docstring so riêng (mục 3);
   - comment: multiset bằng nhau sau khi bỏ các dòng đã in ra để rà tay; hai dòng TODO còn, mỗi dòng vẫn
     ngay trên câu lệnh cũ của nó;
   - `_Proposal.model_json_schema()` và tên tool (`convert_to_openai_tool`) giống từng byte;
     `_GRAPH.get_graph()` cùng node, cùng cạnh;
   - thứ tự: mọi cạnh gọi f → g trong một file có pos(f) < pos(g); câu lệnh tầng module không phải def
     giữ thứ tự tương đối;
   - đầu-cuối rẻ: chạy `compose()` trên các fixture test với `HEAD` (một `git worktree` trong scratchpad)
     và với cây mới, so messages từng byte.
4. `.\dev.ps1 test`, `.\dev.ps1 check`; đột biến: bỏ lời gọi `unmangled(` trong `choose.py` →
   `escape-repair-is-wired-in` đỏ; bỏ `notice=True` ở `graph.py` → `kriky-says-nothing-fixed` đỏ.
5. Tài liệu (mục 3).
6. **Subagent review** đọc code thật sau khi xong; sửa theo review.
7. Khởi động lại AGENT (TaskStop, kiểm không còn tiến trình worker, `dev.ps1 agent` ở nền), kiểm log
   khởi động sạch. Không chạy model thật.
8. Stage hai commit (code; tài liệu + đóng plan), báo người dùng, **chờ duyệt rồi mới commit**. Commit
   message nói một thay đổi thấy được: log `asking again failed for … (%r)` in `NothingToSay(...)` thay
   cho `_NothingToSay(...)`.

## Verification

- Script chứng minh in "khớp" cho mọi câu lệnh; schema `_Proposal` giống từng byte; `compose()` ra cùng
  messages với `HEAD`.
- `.\dev.ps1 test`, `.\dev.ps1 check` xanh; hai đột biến đỏ đúng chỗ.
- Đi AST qua `ImportFrom` và `Attribute` của mọi file sản phẩm: không tên `_x` nào của package được dùng
  ngoài file nhà của nó, trừ 5 lớp pydantic.
- `git diff --cached | grep "TODO: Cần xem lại"` rỗng; working tree vẫn còn hai dòng.
- AGENT khởi động lại không lỗi import.
