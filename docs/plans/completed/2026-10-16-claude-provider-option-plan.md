# Chọn được model Claude bằng `.env`, cho Kriky và document agent

## Goal

Thêm Claude làm một provider chọn được, chỉ bằng `.env`, cho mọi lời gọi model của AGENT (Kriky:
lên plan, dàn ý, soạn câu, giải thích, báo cáo, đặt tên) và của document agent (tóm tắt nút cây,
đọc banner). Rồi chạy bộ 14 ca thử tay (`docs/testing/`) trên Claude Haiku 5.5 để so với mốc
gpt-4o-mini `docs/testing/ket-qua/2026-10-15-6287fc3.md`.

Người dùng chốt 16/10/2026, sau khảo sát giá và model: Haiku 5.5 (`claude-haiku-5-5`, $0,10/$0,50
mỗi MTok) là hạng của gpt-4o-mini; key Claude gắn workspace, biến `CLAUDE_API_KEY`; effort thấp
nhất (tắt thinking nếu model cho) để gần gpt-4o-mini; phạm vi AGENT + document; subagent review sau
mỗi đợt; thử trên trình duyệt sau cùng.

## Scope

- Trong phạm vi: `agent/llm.py`, `agent/config.py`, `document/index/llm.py`, `document/config.py`,
  `document/index_worker.py`, hai `pyproject.toml`, `.env.example`, `docs/local-development.md`,
  test của các module ấy; biên bản thử tay và `backlog.md`.
- Ngoài phạm vi: FE (chưa có chỗ chọn model); đường đọc công thức bằng ảnh (`agent/vision.py`, chưa
  có code); sửa schema structured output. Gặp việc ngoài phạm vi thì dừng và báo.
- Mặc định không đổi: không đặt gì thì vẫn là OpenAI như trước.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `services/agent/pyproject.toml`, `services/document/pyproject.toml` | extras `langchain[anthropic]` |
| `services/agent/src/agent/config.py`, `llm.py` | `CLAUDE_API_KEY`, `LLM_EFFORT`; provider `anthropic` |
| `services/document/src/document/config.py`, `index/llm.py`, `index_worker.py` | provider riêng cho tóm tắt và banner; đọc `.text` |
| `.env.example`, `docs/local-development.md` | Cách bật Claude |
| `services/agent/tests/test_llm.py`, test của `document/index/llm.py` | Không gọi mạng |
| `docs/testing/ket-qua/2026-10-16-<commit>-claude-haiku-5-5.md` | Biên bản so với mốc gpt-4o-mini |

## Ordered Tasks

### Đợt 1 — chuẩn bị
- [x] 1. Plan vào `docs/plans/active/`.
- [x] 2. Extras `anthropic` ở hai `pyproject.toml`, `pip install -e` (langchain-anthropic 1.7.6).
  Đọc chữ ký `ChatAnthropic`; Models API (miễn phí) xem capability của Haiku 5.5. Người dùng bảo
  không gọi thử model riêng: làm xong một lượt rồi chạy 14 ca trên trình duyệt.

### Đợt 2 — AGENT
- [x] 3. `config.py`: `claude_api_key`, `llm_effort`. `llm.py`: `_CREDENTIAL["anthropic"]`; effort
  hay thinking chỉ truyền cho `anthropic`. Test.
- [x] 4. `.env.example` khối model. Subagent review → sửa → commit.

### Đợt 3 — document
- [x] 5. `summary_provider`, `banner_provider`, `claude_api_key`, `llm_effort`; `chat_model` chọn
  provider và key; `read_banner`/`summarise` đọc `.text`; `startup` dựng mỗi model khi provider của
  nó có key. Test.
- [x] 6. `.env.example` khối document, `docs/local-development.md`. Subagent review → sửa → commit.

### Đợt 4 — so chất lượng trên trình duyệt
- [x] 7. Người dùng bảo làm xong một lượt rồi chạy 14 ca. `.env` sang Claude (bản sao lưu ở
  scratchpad), khởi động lại BE/AGENT/index worker, `db-reset`; log khởi động ghi
  `anthropic/claude-haiku-5-5` và `{'thinking': {'type': 'disabled'}, 'effort': 'low'}`.
- [x] 8. Chuẩn bị theo `huong-dan.md`. Banner Claude đọc đúng `Chương I. TẬP HỢP CÁC SỐ TỰ NHIÊN` và
  `Bài 1. TẬP HỢP`; nhãn mục (OCR) trùng mốc. `parse_banner` không vấp lần nào.
- [x] 9. 14 ca: Haiku 5.5 7 đạt · 3 chấp nhận được · 4 không đạt (mốc 3 · 4 · 7). Biên bản
  `docs/testing/ket-qua/2026-10-16-d6c82d4-claude-haiku-5-5.md`; lỗi mới vào `backlog.md`.
- [x] 10. Người dùng chọn giữ `.env` ở Claude.

## Validation Checks

- `.\dev.ps1 check` xanh, gồm `check_env_example_has_no_orphans` và `timeout-order`.
- pytest AGENT và document xanh; không test nào gọi mạng.
- `LLM_PROVIDER=openai` chạy y như trước.
- Log AGENT và index worker ghi đúng provider và model đang dùng.
- Biên bản đủ 14 dòng, mỗi dòng cạnh kết quả gpt-4o-mini.

## Decisions

- **Thinking tắt + effort `low` cho Haiku 5.5** (`LLM_THINKING=disabled`, `LLM_EFFORT=low`). Models
  API 16/10/2026: Haiku 5.5 nhận `thinking: disabled` và mọi mức effort; Sonnet 5.5, Opus 5.5 không
  tắt được thinking. Thinking tắt thì `with_structured_output` (mặc định `function_calling`) **ép**
  model gọi tool của `_Proposal`/`GeneratedQuestion`, nhận nguyên schema có ràng buộc Pydantic; bật
  thì langchain bỏ ép và model có thể không gọi tool. Không đổi sang `method="json_schema"`: Claude
  không nhận `minLength`, `maximum`, `maxItems`, nên phải sửa schema -- ngoài phạm vi.
- **Hai biến dùng chung cho AGENT và document** (`CLAUDE_API_KEY`, `LLM_THINKING`, `LLM_EFFORT`), như
  `LLM_TIMEOUT_SECONDS` đã dùng chung. `claude_options` có hai bản (AGENT, document) vì hai service
  không import nhau; luật là một.
- **Document: provider theo từng lời gọi** (`SUMMARY_PROVIDER`, `BANNER_PROVIDER`), khoá theo provider;
  thiếu khoá thì chỉ model ấy tắt. Chữ trả về đọc bằng `.text` (Claude trả list block).
- **Log khởi động** của AGENT và index worker ghi provider/model và tham số Claude: đổi `.env` mà
  worker chưa khởi động lại thì lượt chat vẫn trả lời bằng model cũ.

## Còn ngoài phạm vi (từ review)

- `max_tokens` của `ChatAnthropic` lấy 128000 từ profile; workspace hạng thấp có thể bị 429 nếu giới
  hạn tính theo `max_tokens`. Chưa đặt -- cần người dùng duyệt.
- `AGENTS.md:17`, `services/document/AGENTS.md:23`, `docs/overview/architecture.md` còn gọi OpenAI là
  provider duy nhất của mô tả lỗi; sửa `AGENTS.md` cần plan và decision record riêng.
- `parse_banner` chỉ gỡ JSON khi cả câu trả lời là một khối; Haiku viết thêm câu dẫn thì banner lùi
  về nhãn số. Task 8 đo: không vấp lần nào trên SGK Lớp 6 và tệp scan, nên chưa sửa.

## Status

Xong 16/10/2026. Claude chọn được bằng `.env` cho AGENT và document; mặc định vẫn OpenAI. Hai
subagent review (AGENT, document) không có lỗi chặn; các phát hiện nên sửa đã sửa trước commit.
Check 23/23, pytest AGENT, document, tools xanh, không test nào gọi mạng.

Chạy 14 ca trên Haiku 5.5 (thinking tắt, effort low): 7 · 3 · 4 so với 3 · 4 · 7 của gpt-4o-mini,
khoảng 487 nghìn token cho các bước Kriky, ước 0,06–0,09 USD. Tốt hơn ở chữ (nút hỏi lại, công thức
trong dàn ý, nói thật khi tệp còn xử lý, đi hết đường tra kết quả); kém hơn ở ba chỗ ghi
`backlog.md` mục *Lộ ra khi chạy bộ ca thử tay trên Claude Haiku 5.5*: `known` rỗng từ lượt hai,
một tool call sai hình dạng làm câu mock vào đề, hai câu cùng mục trùng nhau. Không sửa code sản
phẩm nào trong plan này.

`.env` của máy dev giữ ở Claude theo lời người dùng.
