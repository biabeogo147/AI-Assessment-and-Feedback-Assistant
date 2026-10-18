# Đợt 1 của đợt tất định — sáu sửa nhỏ

## Goal

Làm việc 1–6 của `2026-10-18-deterministic-batch-master-plan.md`. Đây là những sửa không cần quyết
định nghiệp vụ nào. Figma của việc 3 và 4 đã vẽ và đã duyệt (`completed/2026-10-18-figma-all-waves-plan.md`).

## Scope

- **Trong phạm vi:**
  - `dev.ps1` nạp lại BE gọn hơn (6);
  - khối bước bám đáy (1); panel đọc lại đề (2); tài liệu vừa tải không tự đính (11, kéo từ Đợt 2 lên vì
    cùng `Chat.tsx`);
  - gỡ huy hiệu bịa (3);
  - hậu ký ADR và docstring `content_reader.py` (5).
- Việc 4 không có code: Figma vốn không có nút *Thu hồi* trên `đã-phát-hành`. Plan Figma đã ghi điều ấy.
- **Ngoài phạm vi:** mọi thứ khác của plan tổng.
- Cổng mỗi pha theo plan tổng; mỗi pha một commit.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `dev.ps1`, `docs/local-development.md` | 6 |
| `services/fe/src/screens/teacher/Chat.tsx`, `Panel.tsx`, `services/fe/src/teacher.test.tsx` | 1, 2, 11 |
| `services/fe/src/screens/teacher/Rail.tsx`, `invented-not-from-be.ts` | 3 |
| `docs/decisions/adr-18-*.md`, `adr-21-*`, `adr-23-*`, `adr-25-*`, `adr-27-*`, `adr-29-*`, `services/be/src/be/content_reader.py` | 5 |
| `docs/plans/backlog.md`, artifact roadmap | ghi kết quả |

## Ordered Tasks

### Pha 0 — plan và backlog
- [x] 1. Commit plan tổng, plan này, và `backlog.md` (mục *Chốt đợt tất định* cùng các dòng đã dọn
  18/10). Plan Figma đã nằm ở `completed/`.

### Pha 1 — `dev.ps1` (việc 6)
- [x] 2. `dev.ps1:99`:
  - thêm `--reload-dir services/be/src --reload-dir packages/contracts/src --reload-dir
    packages/schema/src` để sửa test hay service khác không làm BE nạp lại;
  - thêm `--timeout-graceful-shutdown 3` để kênh SSE đang mở không giữ process cũ mãi.
  - Giữ UTF-8 BOM của file.
- [x] 3. `docs/local-development.md`: một dòng cạnh lệnh `.\dev.ps1 be` nói BE tự nạp lại khi sửa
  `services/be` hay hai package, không khi sửa chỗ khác. `backlog.md`, mục *BE kẹt khi `--reload`*: ghi
  đã làm.
- [x] 4. Kiểm: khởi động lại BE bằng lệnh mới (task BE đang chạy được phép khởi động lại). Sửa một
  file trong `packages/schema`, xem log có *"Reloading"*. Sửa một file test AGENT, xem log **không**
  nạp lại. Mở một tab giáo viên, sửa file BE, BE trả lời lại trong vài giây.

### Pha 2 — `Chat.tsx` và `Panel.tsx` (việc 1, 2, 11)
- [x] 5. Việc 1: dòng chat chỉ cuộn theo khối bước đang chạy khi người đọc đang ở đáy. Theo dõi *đang ở
  đáy* bằng sự kiện cuộn của khung dòng (ngưỡng ~48px). Effect cuộn chạy cả khi `live` đổi, nhưng chỉ
  khi đang ở đáy; lượt mới (`turns.length`, `pending`) vẫn luôn kéo xuống như nay.
- [x] 6. Việc 2: `Panel` nhận prop `revision` (số). `Chat` tăng nó khi một lượt vừa xong có bước ghi
  vào đúng đề đang mở: `create_draft`, `start_drafting` hay `replace_question` với `entity_id` là đề ấy,
  đọc từ các lượt đã tải lại sau stream. Effect tải đề của `Panel` chạy theo
  `[assessmentId, revision]`. Không đổi `key` của `Panel`, vì đổi `key` là mất trạng thái đang sửa.
  Đang sửa một câu thì vẫn tải lại? Không: khi `editing` mở thì hoãn, đóng thẻ sửa thì tải.
- [x] 7. Việc 11: `take()` (`Chat.tsx:438-454`) thôi gọi `setScope(saved)`. Tài liệu vẫn vào danh sách
  và vẫn kéo vào ô nhập được.
- [x] 8. Vitest:
  - lượt có bước soạn vào đề đang mở làm panel đọc lại;
  - lượt không chạm đề ấy thì không;
  - tải tệp lên không làm hiện chip phạm vi;
  - cuộn: khi không ở đáy, thêm bước không gọi `scrollIntoView`.
- [x] 9. Trình duyệt bằng AGENT mock:
  - một lượt soạn thêm vào đề đang mở, panel tự lên số câu mới;
  - tải một tệp `.txt`, ô nhập không có chip;
  - cuộn lên giữa một lượt, dòng không giật.

  Chụp các trạng thái; một subagent chấm ảnh với artboard `4`, `5`, `2`.

### Pha 3 — huy hiệu bịa (việc 3)
- [x] 10. `Rail.tsx`: bỏ `badge={DASHBOARD_WAITING}` và import. `invented-not-from-be.ts`: bỏ
  `DASHBOARD_WAITING` và đoạn docstring nói về nó. Giữ prop `badge` của `Destination` nếu nó còn chỗ
  dùng thật (việc 19 có thể cần), không thì bỏ luôn. Sửa `backlog.md:17`.
- [x] 11. Vitest: rail không có huy hiệu. Trình duyệt: chụp rail; một subagent so với rail của
  artboard `5`.

### Pha 4 — hậu ký ADR và docstring (việc 5)
- [x] 12. Hậu ký có ngày 18/10/2026, không sửa câu cũ:
  - ADR-18: trạng thái *"chưa có ở backend"* đã cũ. BE ép ở `agent_gateway.validate_question`:
    một đáp án đúng, nhãn lỗi cho mỗi phương án nhiễu, ít nhất hai cách giải. Hàm này chạy lúc thu
    hoạch, lúc giáo viên sửa câu và lúc dựng câu luyện tập;
  - ADR-21: *"chưa thi hành"* đã cũ. Bài làm, điểm từng câu và lượt chữa nằm trong Postgres
    (`attempts`, `question_outcomes`, `rounds`), từ plan `core-two-phase-backend`;
  - ADR-23:114: `_SYSTEM` nay là `_CORE` trong `propose.py`;
  - ADR-25: lời sửa 10/10 định bỏ job kể lại, nhưng code vẫn chạy nó (`graphs/reporting.py`). Gỡ nó
    chạm AGENT nên hoãn, đã ghi backlog;
  - ADR-27: Jev không còn là bộ định tuyến của `document`. Nay Jev chỉ xếp vai trò và cấp cho từng ứng
    viên đề mục (`document/index/jev.py`). *"Chưa thi hành"* cũng đã cũ: đường tài liệu → Kriky →
    dàn ý → job (ADR-29) và `check_drafting_reads_no_document_text` thi hành phần còn hiệu lực;
  - ADR-29:68: lời đồng ý dàn ý được đọc bằng regex (`propose._REVISES`, `_NO_CHANGE`), không bằng
    model.
- [x] 13. `content_reader.py:1-6`: BE đọc đoạn chữ cho tool `read_section` của Kriky lúc nêu dàn ý.
  Job soạn câu không bao giờ nhận đoạn chữ (ADR-29, `check_drafting_reads_no_document_text`).
- [x] 14. Ghi đã làm ở `backlog.md`: dòng *ADR ghi trạng thái cũ*, dòng *Docstring đầu
  `be/content_reader.py`*.

### Pha 5 — đóng
- [ ] 15. Roadmap: việc 1, 2, 3, 4, 5, 6, 11 sang *Xong*. Tick plan tổng. Plan này sang `completed/`.

## Validation Checks

| Kiểm | Lệnh |
| --- | --- |
| Python và repo checks | `.\dev.ps1 check`, `.\dev.ps1 test` |
| FE | `.\dev.ps1 typecheck`, vitest trong `.\dev.ps1 test` |
| BE nạp lại đúng thư mục | pha 1, task 4 |
| Màn hình | ảnh chụp + subagent chấm, pha 2 và 3 |
| Markdown | file không rỗng, link nội bộ mở được |

## Status

- 18/10/2026: plan mở.
- Pha 0: commit `1992023`.
- Pha 1, kiểm tay 18/10/2026:
  - log khởi động ghi đúng ba thư mục theo dõi;
  - `touch` một test AGENT: BE không phản ứng;
  - `touch packages/schema/src/schema/ddl.py`: BE báo *"WatchFiles detected changes … Reloading"*.
  - **Phần khởi động lại không kiểm được ở đây.** Uvicorn 0.52.4 trên Windows dừng process con bằng
    `CTRL_C_EVENT`, mà BE do công cụ của tôi chạy nền thì không có console, nên process con không nhận
    tín hiệu và `join()` đứng. Trong terminal của người dùng (có console) thì đường ấy chạy. Vì vậy
    `--timeout-graceful-shutdown 3` cũng chưa đo được trên một tab đang mở. Trong phiên này, sửa code
    BE thì khởi động lại BE bằng tay.
- Pha 1: subagent review chỉ ra `--reload-dir` là đường dẫn tương đối. Đã đổi sang `$RepoRoot`; BE
  khởi động từ `services/fe` vẫn theo dõi đúng ba thư mục.
- Pha 2, thử tay 18/10/2026:
  - Chrome extension không kết nối, nên dùng Chrome headless riêng điều khiển qua CDP (script trong
    scratchpad, profile riêng, 1440×900); Chrome của người dùng không bị đụng tới;
  - lần thử đầu bắt được một race: sự kiện cuộn do chính `scrollIntoView` sinh ra tới muộn, khối
    bước lớn thêm hơn 48px trong lúc chờ, và dòng thôi bám đáy (khối bước chui dưới ô nhập, cách đáy
    157px). Đã sửa: chỉ `scrollTop` **giảm** mới là người đọc kéo lên, và có test riêng cho race;
  - đo lại: ở đáy thì khoảng cách tới đáy giữ 0 trong suốt lượt; cuộn chuột lên giữa lượt thì
    `scrollTop` đứng yên tới khi lượt xong. Lượt xong vẫn kéo xuống đáy, đúng luật có từ trước;
  - tải `de-cuong-thu.txt` lên: tệp vào ngăn TÀI LIỆU, không chip nào dưới ô nhập;
  - ca *panel tự đọc lại khi Kriky soạn thêm vào đúng đề đang mở* chưa thử tay được: AGENT mock
    luôn mở đề mới. Vitest che ca ấy; thử tay lại ở Đợt 3, khi `create_draft` dùng lại đề trống;
  - **dữ liệu thử lọt vào một đoạn chat thật:** lượt thử đầu chạy trong đoạn chat dài *"Soạn đề kiểm
    tra 15 phút"* (58 lượt, có thể là đoạn chat quay GIF), thêm 4 lượt và một đề nháp *"Đề Tạo đề Toán
    15 phút…"*. Chưa xoá gì; báo người dùng ở cuối. Các lượt thử sau đều mở đoạn chat mới.
- Pha 2, subagent review: sửa theo bảy điểm:
  - đề đang mở đọc lúc lượt xong (ref), không lúc gửi;
  - lượt gãy giữa chừng vẫn báo panel đọc lại;
  - panel tự đọc lại sau 4 giây khi còn câu đang soạn;
  - lần đọc lặng lẽ bỏ lời đáp nếu panel vừa ghi gì;
  - không đọc thừa lúc dựng panel;
  - hộp lời giải đang mở theo câu mới;
  - bỏ bắt sự kiện bánh xe, vuốt, phím, vì `scrollTop` giảm đã đủ.

  Thêm ba test: lượt cũ có bước soạn vào đề đang mở, đề mở giữa lượt, và tự đọc lại khi còn câu
  đang soạn.
- Pha 3 và 4: code xong, check và vitest (268) xanh, commit. Subagent review hai pha này **đang chạy khi phiên chạm giới hạn sử dụng**: phiên sau đọc kết quả và sửa theo trước khi sang Pha 5 (roadmap, đóng plan).
