# Lần chạy 20/10/2026 — kịch bản đầu-cuối trên Claude Haiku 5.5, bốn vòng

- **Ngày:** 20/10/2026, 09:05–10:40.
- **Code:** BE, AGENT, FE khởi động 09:05 trên `4809ce7`; code đổi lần cuối ở `02f54fb`. Riêng FE: nhãn ô
  đăng nhập đổi thành *Số điện thoại / email* lúc 09:57 (`48919a3`), giữa vòng 2 và vòng 3.
- **Model:** `anthropic/claude-haiku-5-5` (dòng `model=` trong log AGENT lúc khởi động).
- **Kịch bản:** `docs/testing/kich-ban-thu-tay-giao-vien.md`, viết lại thành kịch bản đầu-cuối ngày
  20/10. Bản 1 viết theo code, rồi sửa sau mỗi vòng và sau review (xem *Các vòng*).
- **Database:** giữ nguyên, không `db-reset` (người dùng chốt). Mỗi vòng một mã: `V1` … `V4`.
- **Người chạy:** Claude, trên Chrome headless qua CDP. Màn hình đọc bằng DOM và ảnh chụp; đáp án và
  lượt Kriky đối chiếu trong database. Script làm nhanh hơn người: mỗi chặng học sinh xong trong vài
  chục giây.
- **Ảnh chụp:** 207 ảnh, tên `v<vòng>-<bước>-<mô tả>.png`, giữ ngoài repo cho người dùng review. Không ảnh
  và không mật khẩu nào vào repo.
- **Token và chi phí:** chat soạn đề của bốn vòng tốn 712 nghìn token (V1 154 nghìn, V2 268 nghìn, V3 97
  nghìn, V4 192 nghìn), phần lớn đốt vào các lần dàn ý hỏng. Cộng 18 job soạn câu, 3 lượt trợ lý, 6 câu
  làm lại. Ước 0,25–0,35 USD.

## Kết quả

| Chặng | V1 | V2 | V3 | V4 |
| --- | --- | --- | --- | --- |
| 1. Tài khoản giáo viên | đạt | đạt | **đạt** | **đạt** |
| 2. Lớp và học sinh | đạt | đạt | **đạt** | **đạt** |
| 3. Soạn đề với Kriky | đạt, dàn ý hỏng 5 lần | đạt, dàn ý hỏng 7 lần | **đạt**, dàn ý hỏng 2 lần | **không đạt**: dàn ý hỏng 7 lần, quá 6 lần thử lại |
| 4. Duyệt và phát hành | đạt | đạt | **đạt** | — |
| 5. Châu sai hai câu, chữa | đạt | đạt | **đạt** | — |
| 6. Dũng đúng hết | đạt | đạt | **đạt** | — |
| 7. Giáo viên đọc kết quả | đạt | đạt | **đạt** | — |
| 8. Sau hạn chữa | đạt | đạt | **đạt** | — |

*Đạt* ở đây là luồng đi hết theo chữ của kịch bản. Các lỗi sản phẩm gặp trên đường ghi ở bảng dưới,
không làm trượt chặng nào, trừ dàn ý ở V4.

**Kết luận.** Vòng V3 đi trọn tám chặng; chặng 1–2 và 4–8 không phải sửa chữ nào. Vòng V4 chạy bản cuối của
kịch bản: chặng 1–2 đạt, và ở 3.2 nút *Toán* được chọn đúng theo bảng dữ kiện mới. Nhưng V4 dừng ở 3.3
vì lỗi dàn ý của model. Từ 3.4 trở đi, bản cuối chỉ được chạy ở V3, trước ba thay đổi review đòi:
giờ phát hành rộng hơn, dòng phụ 3.4, và các dòng *đã biết*. Những thay đổi này không đổi đường đi
của luồng. **Chừng nào lỗi dàn ý chưa sửa, không vòng nào bảo đảm đi qua 3.3.**

## Các vòng

**V1 — bản 1.** Đi hết tám chặng, nhưng kịch bản sai hay thiếu ở hơn hai mươi chỗ:
- chữ nguyên văn: câu báo sai mật khẩu; tên nút (*Xem trước*, *Tạo 3 tài khoản*, *Đã lưu, đóng*, *Xuất
  file Excel (.xlsx)*, *Thêm 1 câu vào đề*, *Phát hành cho N học sinh*, *Làm bài mới · 2 câu · 4
  phút*…); hàng *Lớp 12A* thay vì *12A*;
- luật tên đăng nhập: mã vòng đứng cuối họ tên nên thành phần tên (`v1kmc`);
- đóng hộp xem trước bằng *Quay lại* rồi *Đóng*;
- tên đề: Kriky không truyền tên cho `create_draft`, BE tự đặt *Đề chương Hàm số*; lời nhắn bỏ tên, thêm
  bước *Đổi tên* ở panel;
- nút báo cáo của học sinh chỉ hiện sau lượt trả lời đầu của trợ lý;
- mẫu số *2/N* là sĩ số hiện tại, kể cả em thêm sau khi phát hành.

**V2 — bản 2.** Chặng 1, 2, 4–8 đi đúng chữ. Ở 3.3 dàn ý hỏng 7 lần. Lúc ấy kịch bản cho thử lại 3 lần;
người dùng chọn nâng lên 6 giữa vòng. V2 qua ở lần *thử lại* thứ 7, tức theo luật cuối là **không đạt ở
3.3**; nó được chạy tiếp để kiểm phần còn lại. Thêm vào bản 3: Kriky hỏi lại *khối nào* dù lời nhắn đã
ghi *lớp 12*; ô gõ tự do chỉ hiện sau nút *Khác…*.

**V3 — bản 3.** Chặng 1, 2, 4–8 không phải sửa chữ nào. Ở 3.2 Kriky hỏi một câu mới (*môn nào*): script
đi đúng chữ bản 3 (bấm *Khác…*, gõ tự do), nhưng người thật sẽ bấm *Toán*. Bản 4 thay danh sách nút
bằng một bảng dữ kiện trả lời cho mọi câu hỏi lại, và ghi tên đề tự đặt chỉ là ví dụ (*Đề Hàm số* ở V3).

**Review (subagent, sau V3).** Một lỗi chặn: với giờ đóng `T + 10 phút`, người thật không kịp cho Dũng vào
làm sau khi Châu chữa xong. Script làm nhanh nên không lộ ra. Bản cuối đặt giờ mở `T + 5`, giờ đóng
`T + 30`, hạn chữa `T + 50`, và cho phép Dũng làm ngay sau khi Châu nộp. Cộng các chỗ chữ: dòng phụ
3.4, chip của thẻ *Đã phát hành*, câu SQL đọc phương án khoá, cột *MỞ LÚC* ở 7.2, các lỗi *đã biết*.

**V4 — bản cuối.** Chặng 1–2 đạt; 3.2 chọn *Toán* đúng bảng mới; 3.3 dàn ý hỏng 7 lần, dừng vòng.

## Lỗi sản phẩm tìm thấy

| # | Lỗi | Ở đâu | Đã ghi |
| --- | --- | --- | --- |
| 1 | **Dàn ý chương Hàm số hỏng gần như mọi lần**: V1 5 lần, V2 7, V3 2, V4 7. Log BE ghi 35 lần trả về trong V1–V2, 25 lần cùng một dạng: mệnh đề có chữ ngoài cặp `$` trong `formulas` | AGENT (khoá), luật ADR-29/30 | backlog Tier 4, artifact backlog |
| 2 | Kriky không truyền tên đề dù dàn ý nói *"đề **Hàm số V1**"*; đề mang tên BE tự đặt | AGENT | backlog |
| 3 | Kriky hỏi lại điều lời nhắn đã nói (*khối nào*, *môn nào*) | AGENT | đã có (Tier 4 *hỏi lại dù đủ mục*) |
| 4 | Câu trong ngân hàng *"Đạo hàm của y = x² + 3x"* khoá *2x + 5* (đúng là 2x + 3) | dữ liệu model soạn ở phiên trước | backlog |
| 5 | Câu làm lại có **hai phương án cùng đúng** (V1, V2); câu soạn có tới 5 phương án (V3 câu 1) | AGENT, Tier 4 *toán sai* | backlog |
| 6 | Công thức trong mục kiến thức hiện nguyên `$f'(x)$`: Ngân hàng, hộp *Thêm câu từ ngân hàng*, biểu đồ ở Bảng theo dõi | FE | backlog |
| 7 | Học sinh không sai câu nào vẫn có link *Xem lại phần chữa các câu sai* | FE `Result.tsx` | backlog |
| 8 | Màn trống của **đoạn chat** ghi *"Kriky sẽ tạo lớp…"* trong khi chưa có đường tạo lớp | FE `Chat.tsx` | backlog |
| 9 | Lệch Figma: thanh trên học sinh ghi mã trần (*· 12*), Figma ghi *Mã 1204* | FE `components.tsx` ↔ Figma | backlog |
| 10 | Đề bài có công thức vỡ thành nhiều dòng ở màn bài làm của một học sinh (23) | FE `teacher.css` `.stem-cell` | backlog |
| 11 | *Đã gửi báo cáo tới giáo viên.* hiện trong dải lỗi đỏ | FE `Tutor.tsx` | backlog |

## Không phải lỗi sản phẩm (đã kiểm)

- Hộp ngân hàng và dòng hàng đợi *không ăn cú bấm* ở V1: helper của script để lại dấu chọn cũ.
- Học sinh *còn đăng nhập sau khi bấm Đăng xuất*: script tắt Chrome đột ngột nên cookie chưa ghi. Đăng
  xuất thật sự huỷ phiên ở BE (cookie cũ trả 401).
- *THỜI GIAN LÀM 0 phút*: script làm bài dưới nửa phút.
