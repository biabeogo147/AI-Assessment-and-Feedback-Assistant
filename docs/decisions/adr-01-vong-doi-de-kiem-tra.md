# ADR-01 — Vòng đời đề kiểm tra có bốn trạng thái

- **Trạng thái:** đã mở rộng bởi ADR-02 và ADR-18
- **Ngày:** 2026-09-06

## Bối cảnh

Tài liệu nghiệp vụ ban đầu coi duyệt và phát hành là **một** bước, nên đề chỉ có hai trạng thái: chưa
duyệt và đã phát hành. Thiết kế thực tế tách chúng ra, và thêm một trạng thái trung gian mà mô hình cũ
không có chỗ chứa.

## Quyết định

Một đề đi qua bốn trạng thái:

```
trống  ->  có câu hỏi  ->  đã duyệt  ->  đã phát hành
```

[ADR-02](adr-02-phat-hanh-va-cua-so-thu-hoi.md) chia trạng thái cuối thành hai trạng thái con —
*đã phát hành, chưa mở* và *đã mở* — vì thu hồi chỉ được phép ở trạng thái đầu.

- Đề **sinh ra trống**. Thêm câu hỏi là một bước riêng, không phải một phần của việc tạo.
- Ở trạng thái nháp, thêm và sửa câu hỏi được.
- Duyệt **khoá nội dung**: ở trạng thái đã duyệt, không thêm và không sửa câu hỏi được.
- Từ [ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md), *nội dung* gồm cả **lời giải nhiều cách** và
  **ánh xạ phương án nhiễu sang lỗi**. Duyệt khoá luôn hai thứ đó.
- Bỏ duyệt đưa đề **về lại nháp**, và được phép chừng nào chưa phát hành.
- Bỏ duyệt **giữ nguyên** cài đặt phát hành đã nhập.

## Vì sao

Duyệt là lúc giáo viên nhận trách nhiệm về nội dung. Nếu nội dung còn sửa được sau khi duyệt thì việc
duyệt không có nghĩa gì.

Nhưng duyệt **phải đảo ngược được**, vì đây không phải cổng cuối. Nếu cả duyệt lẫn phát hành đều một
chiều thì giáo viên gặp hai cổng nặng liên tiếp, và sẽ học cách bấm qua cả hai cho nhanh — làm hỏng
đúng cái cổng thật sự cần sức nặng.

## Hệ quả

- Giao diện **không được** mời thêm câu hỏi khi đề đã duyệt. Nút "Sửa" trên từng câu phải biến mất,
  nếu không thì "nội dung đã khoá" là lời nói suông.
- Bỏ duyệt phải để lại **bằng chứng** trong luồng chat như mọi thao tác khác — nó là thao tác duy nhất
  hạ cấp trạng thái, nên càng phải có dấu vết.
- Trạng thái trống cần một trạng thái rỗng riêng cho panel, và phải chặn phát hành.
- Không có đường đi ngược từ `đã phát hành`. Thu hồi là cạnh do ADR-02 định nghĩa, không phải bỏ duyệt.

## Nơi luật này đang được thi hành

- Figma `mOe2ZmrqOq1Uix45v6PNGD`, component set `Action result card` (`10:63`) — variant `tạo-đề-trống`, `thêm-câu-hỏi`,
  `đã-duyệt`, `bỏ-duyệt`.
- Figma artboard `6 · Soi từng câu trong panel` (nút "Duyệt đề", "Sửa" hiện) so với
  `7 · Đã duyệt — cài đặt phát hành` ("Sửa" đặt `visible = false` trên cả năm thẻ câu hỏi).
- Chuỗi trên thẻ `đã-duyệt`: *"10 câu · nội dung đã khoá, muốn sửa thì bỏ duyệt trước"*.
- Figma `Question card` (`267:30`) — thuộc tính boolean **Sửa được**, tắt trên artboard 7 (đã duyệt)
  và bật trên artboard 6. Nút Sửa **biến mất** chứ không mờ đi, đúng như mục *Hệ quả* đòi.
- **Chưa có ở backend**: không model, không endpoint, không test nào biết tới bốn trạng thái này.
