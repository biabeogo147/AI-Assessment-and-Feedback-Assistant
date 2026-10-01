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
- `services/be/src/be/models.py` — `AssessmentState` mang đúng bốn giá trị, và cột `Assessment.state`
  là một `Enum` có check constraint, nên một trạng thái ngoài ADR này không vào được bảng kể cả qua
  đường bỏ qua `advance`.
- `services/be/src/be/assessment_state.py` — `_ALLOWED` là bốn trạng thái ấy cùng các cạnh giữa
  chúng, viết thành dữ liệu. `advance()` là cửa cho mọi cạnh **vô điều kiện**; `withdraw()` là thao
  tác có tên duy nhất đi vòng qua bảng, vì cạnh *đã phát hành → đã duyệt* có **điều kiện** (chưa tới
  giờ mở, và không lớp nào còn giữ đề). Hai chỗ đó là **hai** chỗ duy nhất gán `state`, kiểm được
  bằng một phép grep. `assert_editable()` thi
  hành luật *duyệt khoá nội dung*.
- `services/be/tests/test_assessment_lifecycle.py` — mười hai test. Trong đó
  `test_unapproving_reopens_the_content` giữ tính đảo ngược, và
  `test_a_published_assessment_never_returns_to_editing` giữ việc **bỏ duyệt** không đưa một đề đã
  phát hành về trạng thái soạn được — không phải *"không có đường ra khỏi đã phát hành"*: từ Pha 5 thì
  có một đường, là `withdraw()`, và chính docstring của test ấy nói nó cố ý không khẳng định điều
  mạnh hơn. Dòng Invariants của `AGENTS.md` nay trỏ vào
  `test_an_unapproved_assessment_cannot_be_published_over_http`, vì luật đó nói về *release* và từ
  Pha 5 mới có một đường HTTP phát hành để nó có gì mà canh.
- `services/be/src/be/teacher_routes.py` — `POST /api/teacher/assessments/{id}/approve` và
  `.../unapprove`, hai caller của `advance()` **trên đường HTTP**. Endpoint duyệt thi hành bất biến
  *trạng thái ↔ số câu hỏi*: không duyệt được một đề trống, và không duyệt được một đề còn câu đang
  soạn. Endpoint bỏ duyệt phải **tự nêu tiền đề** rằng đề đang `đã duyệt`, vì bảng cạnh biết *cạnh
  nào tồn tại* mà không biết *ai đang xin đi*: cạnh `trống → có câu hỏi` tồn tại cho việc thu hoạch,
  nên một lần bỏ duyệt giao hết cho bảng sẽ đi lậu qua nó và nâng một đề 0 câu lên `đang soạn`. Chỗ đếm là endpoint chứ không phải `advance()`, vì đếm cần một session còn `advance()` thuần
  trên một hàng — đọc `assessment.questions` bên trong nó sẽ là một lazy-load trong ngữ cảnh async.
- `services/be/src/be/teacher_routes.py` — endpoint bỏ duyệt ghi một hàng `teacher_turns` kèm
  `entity_kind = assessment`, vì ADR này chỉ riêng việc bỏ duyệt ra như **thao tác duy nhất hạ một
  trạng thái xuống**.
- `services/be/src/be/drafting.py` — `fire()` gọi `assert_editable()` trước khi đẩy job nào vào hàng
  đợi, nên luật *duyệt khoá nội dung* chặn trước khi tốn một lượt gọi model. Và `harvest()` hỏi lại
  cùng câu đó qua `editable()` trước khi ghi, vì một phép kiểm lúc bắn job không đủ: giữa lúc bắn và
  lúc thu có một khoảng, và trong khoảng đó giáo viên bấm Duyệt được. Thiếu nó thì `harvest()` là một
  đường ghi câu hỏi đi vòng qua cả hai.
- `services/be/tests/test_approval.py` — chín test đi qua HTTP. Mỗi call site được kiểm bằng cách phá
  nó rồi xem test nào đỏ: bỏ `harvest`, bỏ phép kiểm đang-soạn, bỏ lọc chủ sở hữu, bỏ việc ghi bằng
  chứng — bốn lần, bốn test, đúng cái test dự định.
- **Chưa có ở backend: cạnh từ `có câu hỏi` về `trống`.** Nó chỉ cần khi có đường xoá câu hỏi, mà
  đường đó chưa dựng.
