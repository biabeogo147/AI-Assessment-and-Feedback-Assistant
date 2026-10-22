# Plan — Chia authoring, explain, naming thành package

- **Mở:** 22/10/2026 · **Đóng:** 22/10/2026

## Context

- `services/agent/src/agent/graphs/` mới có `propose/` là package; bốn file còn lại nằm phẳng:
  `authoring.py` 456 dòng, `reporting.py` 199, `explain.py` 191, `naming.py` 121.
- Người dùng muốn hai việc, mỗi việc một plan:
  1. Tách các graph còn lại thành package như `propose/`.
  2. Bỏ bước báo cáo cứng cuối lượt (ADR-25).
     - Lượt đã chạy plan thì BE gọi `propose` thêm một lần, có thêm một **tool đọc mới**: tool này kể
       gọn plan vừa chạy, bước nào xong, bước nào hỏng, bước nào không chạy.
     - Quy trình kể lại nằm ở **bước 6 của `soan-de.md`**. Model xử lý mềm theo tình huống, không bắt
       buộc phải nói.
- Sau plan 2, chạy lại toàn bộ thử tay trên trình duyệt: 16 ca ở `docs/testing/cases/` và kịch bản
  `docs/testing/kich-ban-thu-tay-giao-vien.md`.
  - Người dùng chốt: **thiết kế lại để không phải `db-reset`** mỗi lần thử.
  - Dòng `# TODO: Cần xem lại` ở `reporting.py` được xoá cùng file.

## Ràng buộc chung

- Không đụng `docs/report/` và `deploy/`.
- Hai dòng TODO ở `propose/prompt.py` và `propose/compose.py` giữ nguyên, không stage. Sửa
  `compose.py` thì stage bằng blob đã bỏ dòng ấy.
- Trước mỗi commit chạy `.\dev.ps1 check` và `.\dev.ps1 test`. Đuôi commit có `Plan:`, Co-Authored-By
  và Claude-Session. Người dùng đã cho commit sau mỗi plan.
- Sau mỗi pha, subagent review code thật. Mọi đổi FE thì chụp ảnh và so Figma.
- LLM thật chỉ dùng ở pha thử tay của plan 2, model `claude-haiku-5-5` (`.env` dev). Báo chi phí ước
  lượng trước.

## Plan này

Chia file, **không đổi logic**, theo đúng luật của `completed/2026-10-20-split-propose-package-plan.md`
và `completed/2026-10-20-propose-names-and-order-plan.md`:

- **Chuyển nguyên văn:** thân hàm, regex, chuỗi prompt và comment giữ nguyên chữ; chỉ đổi import.
  Thứ tự trong file theo luật của `propose-names-and-order` (review 22/10: hai câu cũ tự mâu thuẫn).
- **Không vòng import:** các file con import nhau bằng đường tuyệt đối. Không file nào
  `from agent.graphs.<pkg> import …`.
- **Gọi `llm` qua thuộc tính:** giữ `from agent import llm` và gọi `llm.with_fallback`, để mọi
  `monkeypatch.setattr(llm, …)` trong test còn tác dụng.
- **Ghim tên logger:** `authoring` ghim `logging.getLogger("agent.graphs.authoring")`.
- **Đặt tên:**
  - tên chỉ dùng trong file của nó giữ `_`;
  - tên dùng ở file product khác thì bỏ `_` (vd. `SYSTEM`, `unmangled`);
  - lớp pydantic giữ `_`;
  - hàm gọi đứng trên hàm bị gọi; `_GRAPH = _build()` đứng cuối `graph.py`.
- **`__init__.py`:** giữ docstring cũ, chỉ export hàm công khai.
- **Docstring cho file mới:** 1–3 dòng tiếng Việt.
- **Lỗi thấy khi chia:** chỉ ghi vào backlog, không sửa.

### Bố cục

| Package | File | Nội dung |
|

## Status

Đóng 22/10/2026. `check` 26/26, pytest và vitest xanh.

- Ba package dựng bằng script chia theo AST (mỗi lệnh cấp đầu chuyển nguyên văn kèm comment ngay trên).
  So với `HEAD` sau khi áp bảng đổi tên: mọi định nghĩa cùng AST, không mất comment, docstring module
  giữ ở `__init__.py`.
- Đổi tên vì dùng chéo file: `authoring` `SYSTEM`, `faults`, `unmangled`, `parsed`; `explain` `SYSTEM`,
  `compose`; `naming` `SYSTEM`. Script đổi nhầm `_check` (chỉ vì một docstring nhắc tên ấy), đã trả lại.
- Review: thứ tự theo luật *hàm gọi đứng trên hàm bị gọi* (plan cũ viết hai câu mâu thuẫn, đã sửa câu);
  tên cũ sót trong comment ở `handlers.py`, docstring check và backlog đã sửa.
- Check `escape-repair-is-wired-in` nhận `unmangled` ở mọi package; bẻ lời gọi trong
  `authoring/graph.py:_write` thì check đỏ.
- Ghi backlog: biến cục bộ `faults` che tên hàm; `propose/` lệch luật thứ tự ở hai chỗ.
