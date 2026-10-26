# Plan — Câu làm lại ở pha 2 nhận mục dàn ý của câu gốc

- **Mở:** 26/10/2026 · Việc cuối của đợt B10 (plan 3 của bộ ba người dùng chốt 26/10/2026)

## Goal

Học sinh làm sai một câu thì pha 2 soạn câu làm lại (ADR-17). Hôm nay AGENT chỉ nhận **câu gốc**.
Câu gốc soạn từ một mục dàn ý giáo viên đã duyệt (ADR-29), nhưng mục ấy không đi theo: câu làm lại
không biết câu gốc kiểm kiến thức gì, dùng công thức nào, giải theo cách nào. Người dùng chốt ngày
26/10/2026: *"pha 2 … prompt a + tài liệu b + câu x"*, rồi *"pha 2 và pha 1 chỉ cần prompt a"*. Prompt a
là mục dàn ý Kriky lọc từ tài liệu.

Plan này cho `RetryQuestionRequested` mang thêm kiến thức, công thức và cách làm của mục dàn ý mà câu
gốc soạn từ đó. Pha 2 vẫn **không** nhận chữ tài liệu thô.

## Scope

- Trong:
  - ba trường mới của contract;
  - BE tìm mục của câu gốc, dùng chung hàm với `drafting.item_fields`;
  - AGENT `retry_brief` in mục;
  - hậu ký ADR-17 và ADR-29;
  - check *`student_routes.py` không đọc kho nội dung*;
  - thử tay case 16.
- Ngoài: câu biến thể giữ cấu trúc câu gốc (P5 của Tier 3); FE.

## Decision Records

### Decision: tìm mục theo ô soạn của câu gốc

**options considered:**

- (a) thêm cột `outline_item` vào `questions`;
- (b) tìm `DraftItem` theo `(assessment_id, ordinal = order_index)` rồi lấy
  `brief.outline[outline_item]`.

**selected option:** (b).

**reason:** `draft_items` đã giữ `outline_item` của từng ô, và ô `ready` có `ordinal` trùng
`order_index` của câu nó soạn (đo trên đề case 04/06 ngày 26/10/2026: 7/7 khớp). (a) đòi đổi schema
và đổi đường ghi câu. Một số câu không có ô nào và sẽ chạy như hôm nay, với ba trường rỗng:

- câu lấy từ ngân hàng;
- câu seed;
- câu soạn trước ADR-29.

## Files

- `packages/contracts/src/contracts/authoring.py` (`RetryQuestionRequested`; không nâng
  `SCHEMA_VERSION`: ba trường có mặc định, theo `packages/contracts/AGENTS.md`)
- `services/be/src/be/student_routes.py` (`_retry_ask` và hai nơi gọi), `drafting.py` (hàm thuần
  dùng chung)
- `services/agent/src/agent/graphs/authoring/brief.py` (`retry_brief`)
- `tools/check_contract.py`
- test: `packages/contracts/tests/test_draft_outline.py`, test BE và AGENT liên quan
- `docs/decisions/adr-17-*.md`, `adr-29-*.md`

## Ordered Tasks

- [x] Pha 1 — hậu ký ADR-17, ADR-29; check `student_routes.py` không đọc kho nội dung. Review
      subagent.
- [x] Pha 2 — contract và BE; test. Review subagent.
- [x] Pha 3 — AGENT `retry_brief`; test. Review subagent.
- [x] Pha 4 — thử tay case 16, soi câu biến thể có bám mục không; biên bản. Review subagent.

## Validation Checks

- `.\dev.ps1 check` và `.\dev.ps1 test` xanh; check mới đỏ khi bẻ thử.
- Payload pha 2 trong test mang đúng mục của ô; câu không có ô thì trường rỗng.
- Case 16 đạt; câu biến thể bám mục dàn ý.

## Status

Mở và đóng ngày 26/10/2026. `check` và `test` xanh. Check `outline-only` nay quét cả
`student_routes.py`; bẻ thử (một dòng `get_reader()`) thì đỏ.

**Code:**
- ba trường `item_*` của `RetryQuestionRequested`;
- `drafting.outline_item_fields`, tách từ `item_fields`;
- `student_routes._outline_items`, nối vào `_retry_ask` và hai nơi gọi;
- `retry_brief` in mục trước câu gốc.

Mục của một câu là mục của ô soạn cùng đề, cùng số thứ tự, đã `ready`, chỉ với câu `source = kriky`.

**Review pha 1–2** tìm ra một lỗi thật. Thay câu mà job hỏng tới hết lượt thì `_keep_the_old` trả ô
về `ready` nhưng ô vẫn trỏ mục mới, trong khi câu cũ còn trong đề. Câu làm lại khi ấy nhận sai mục.
Đã sửa: ô bỏ mục (`outline_item = None`), có test. Thêm nữa:
- test payload thật của `_write_ahead`;
- `_write_ahead` chỉ tra mục cho câu cần.

**Review pha 3:** thêm dòng dặn chỉ kiểm phần câu gốc kiểm, vì một mục có thể phủ hai câu.

**Pha 4, thử tay** (`docs/testing/ket-qua/2026-10-26-b11190d-pha-2-claude-haiku-5-5.md`): case 16
**chấp nhận được**.
- Đủ năm bước, và payload thật trong Redis của cả 7 job mang `item_knowledge`, `item_formulas`,
  `item_approach` đúng mục.
- Câu biến thể giữ chữ câu gốc, đổi số. Chưa có đối chứng nào cho thấy mục đổi câu ra sao.
- Review pha 4 tìm ra đáp án khoá sai ở hai biến thể và ở một câu gốc giáo viên đã duyệt (Tier 4
  *toán sai*). Đây không phải lỗi của plan này, nhưng mục dàn ý cũng không chữa được nó.

**Chưa làm**, ghi ở `backlog.md` mục *Lộ ra khi làm plan câu làm lại nhận mục dàn ý*:
- dòng dặn của review pha 3 chưa thử tay;
- đường soạn tại chỗ chưa test;
- giáo viên sửa tay thì mục cũ ở lại;
- đáp án khoá sai;
- biến thể lượt 2 gần trùng lượt 1.
