# 10. Phát hành rồi hoàn tác trước giờ mở

Nhóm: Phát hành · Lượt model: ~0 · Chạy sau: 09 (`09-duyet-sua-xoa-cau.md`)

## Cho người xem thấy gì

Phát hành là cổng của con người: biểu mẫu không gợi sẵn giờ nào, chặn cửa sổ vô lý trước cú bấm,
hộp xác nhận đọc lại đúng lớp, giờ, số câu, và trước giờ mở thì một nút `Hoàn tác` rút đề về hẳn.

## Chuẩn bị

- Chạy tiếp **đúng đoạn chat của case 09**, ngay sau thao tác cuối của nó: đề Toán 7 tỉ lệ thức
  **4 câu, đã duyệt, chưa phát hành**, panel đang mở ở màn `Cài đặt phát hành`. Có hai lớp 12A
  (3 học sinh) và 12B (bước 5 của *Chuẩn bị chung*). Không gõ gì vào ô chat suốt case.
- Tính trước **H** = giờ tròn kế tiếp **cộng một giờ** (đang 14:20 thì H = 16:00). H luôn cách
  lúc chạy 60–120 phút, đủ cho cả case. Chạy trước 19:00 để mọi mốc cùng một ngày.
- Lấy id đề **của case 02** theo tên ở biên bản (case 07 đã tạo đề sau nó) và chụp trạng thái
  **trước**. Chạy trong Git Bash — PowerShell 5.1 có thể làm hỏng chữ có dấu trong `'<tên>'`:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select id, title, state from assessments where title = '<tên>' order by created_at desc limit 1;"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select c.name, p.opens_at at time zone 'Asia/Ho_Chi_Minh' as mo, p.phase1_minutes, p.recalled_at from publications p join classes c on c.id = p.class_id where p.assessment_id = '<ID>';"
  ```

  `state` phải là `approved`, truy vấn thứ hai **0 dòng**. Khác thì case 09 chưa đạt: dừng, ghi lại.

## Lời chat

Không lượt chat nào. Chuỗi thao tác cố định, làm đúng thứ tự (giờ gõ dạng 24h):

```
B1. Nhìn tấm "Cài đặt phát hành" khi chưa chạm gì.
B2. Chưa chọn lớp. Điền: Làm bài 15 · Mở lúc H−3:00 · Đóng lúc H+1:00
    · Phút mỗi câu 3 · Hạn chữa xong H+3:00.
B3. Bấm chip 12A.
B4. Sửa Mở lúc thành H:00.
B5. Bấm "Phát hành đề" → đọc hộp → bấm "Xem lại cài đặt". Chạy lại truy vấn publications.
B6. Bấm "Phát hành đề" lần nữa → "Phát hành cho 3 học sinh".
B7. Đọc thẻ trong chat và khối ĐÃ PHÁT HÀNH. Chạy lại hai truy vấn.
B8. (Trước H) Bấm "Hoàn tác". Đọc panel, thẻ, chạy lại hai truy vấn.
```

Ví dụ H = 16:00: mở thử 13:00, mở thật 16:00, đóng 17:00, hạn chữa 19:00. Không bấm chip 12B.

## Nếu Kriky rẽ

Không có model; nhánh rẽ là của màn hình và đồng hồ.

| Kriky làm gì | Trả lời / phán | Vì sao |
|---|---|---|
| Panel hiện nội dung đề + `Duyệt đề`, không có tấm phát hành | Ghi lại, bấm `Duyệt đề` rồi chạy tiếp. **Chấp nhận được** cho case này, ghi case 09 lỗi | Đề chưa duyệt thì **không có** biểu mẫu nào: đó chính là chỗ chặn phát hành đề chưa duyệt (ADR-01) |
| Tấm trượt đang thu, chỉ còn thanh `Cài đặt phát hành` | Bấm thanh để bung. **Đạt** | Nấc thu/bung nhớ theo đề |
| Ô có giá trị sẵn, kèm dòng `Bản nháp bạn gõ …` | Bấm `Bỏ bản nháp`, làm lại B1. **Chấp nhận được** | Nháp chính tay người gõ trước, màn hình có nói ra |
| Ô có giá trị sẵn, **không** có dòng báo nháp | **Không đạt** | Một giờ gợi sẵn là giờ sẽ bị bấm qua (ADR-02) |
| B2 chưa có dòng đỏ nào | **Đạt** | Chỉ phán khi đủ sáu tham số; lớp là tham số thứ nhất |
| Hộp xác nhận có dòng `Chưa nhận` | **Không đạt** | Khung giờ B4 hợp lệ, 12A phải nhận |
| Lỡ qua H trước B8: nút `Hoàn tác` khoá kèm `Đã qua giờ mở của lớp 12A nên không hoàn tác được nữa. …` (hoặc bấm được rồi hiện đúng câu ấy) | Dừng, ghi lại. **Không chấm** B8; đề đã thật sự phát hành, làm lại cần một đề đã duyệt mới | Đúng luật ADR-02, lỗi của người chạy. Câu khoá đọc khi tấm mở, không tự cập nhật theo đồng hồ |
| Thẻ chat không đổi sau B6/B8 | F5. Đúng sau F5: **chấp nhận được**, ghi lại. Vẫn sai: **không đạt** | Thẻ đọc lại lượt sau mỗi việc ghi của panel |

## Đạt khi

- **B1:** năm ô thời gian/phút **trống**, không chip nào có ✓, nút `Phát hành đề` khoá. Hai câu
  luật in chỗ trống: `Vào làm bài tới hết --:-- — nộp muộn nhất lúc --:--, …` và
  `Chữa bài tới hết --:-- — mỗi lượt -- phút một câu; …`. Có nút `Hoàn tác` trên nút chính.
- **B2:** hai câu luật điền số đang gõ (`… tới hết H+1:00 — nộp muộn nhất lúc H+1:15, …`; mốc nào sang ngày khác giờ mở thì có thêm ` · DD/MM`); nút vẫn
  khoá vì chưa có lớp; chưa có dòng đỏ.
- **B3:** **ngay khi bấm chip**, chưa cần bấm gì thêm: dòng đỏ `giờ mở phải ở tương lai` hiện dưới
  hai câu luật, nút vẫn khoá.
- **B4:** dòng đỏ biến mất, nút `Phát hành đề` sáng.
- **B5:** hộp `Phát hành đề kiểm tra?`, câu mở `Đề sẽ hiển thị cho 3 học sinh của lớp 12A. Bạn còn
  thu hồi được tới trước giờ mở.` Các dòng: `Đề` = `4 câu · <tên đề>`; `Lớp` = `12A · 3 học sinh`;
  `Thời gian` = `mở H:00 · <ngày> · đóng H+1:00 · <ngày>`; `Hạn chữa` = `tới hết H+3:00 · …`;
  `Thu hồi` = `được tới trước H:00 · …`. Ba câu luật cùng số, câu cuối `Thu hồi được tới trước giờ
  mở. …`. Nút `Phát hành cho 3 học sinh`. Sau `Xem lại cài đặt`: publications vẫn **0 dòng** —
  xem trước không ghi gì.
- **B6–B7:** dưới biểu mẫu có hàng kết quả `12A` cùng câu pha 1; khối `ĐÃ PHÁT HÀNH` năm dòng:
  `12A · 3 học sinh`, `Mở H:00 · … · làm bài 15 phút`, hai câu luật, `Thu hồi được tới H:00 · …`.
  Chip 12A khoá. Thẻ trong chat thành `Đã phát hành` (không tên lớp) với dòng
  `Thu hồi được tới trước giờ mở, từ giờ mở thì không`. DB: `state = published`; một dòng 12A,
  `mo` = H:00 đúng ngày, `phase1_minutes = 15`, `recalled_at` rỗng.
- **B8:** panel về nội dung đề, 4 câu, nút `Sửa` hiện lại; chân panel `Bạn duyệt xong mới phát
  hành được. Học sinh chưa nhìn thấy đề này.` + `Duyệt đề` — không còn biểu mẫu phát hành nào.
  Thẻ về `Đã tạo đề "<tên đề>"` · `Chưa duyệt · chưa phát hành`. Vẫn **một** thẻ cho đề này.
  DB: `state = has_questions` (Hoàn tác thu hồi mọi lớp rồi hạ **hai** nấc, ADR-02); dòng 12A
  **còn**, `recalled_at` đã có giờ (thu hồi mềm). Và biên bản đủ ba việc tay:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select tool_name, created_at from teacher_turns where tool_name like 'teacher.%' and tool_args->>'assessment_id' = '<ID>' order by created_at;"
  ```

  thứ tự cuối: `teacher.approve` (case 09), `teacher.publish`, `teacher.unapprove`.
- **Chặn đề chưa duyệt ở BE** (sau B8, PowerShell; `<CLASS>` lấy bằng `docker exec aiafa-postgres
  psql -U aiafa -d aiafa -Atc "select id from classes where name = '12A';"`):

  ```
  $h = @{ "X-Actor" = "teacher:GV-001"; "Content-Type" = "application/json" }
  $b = '{"schedule":{"opens_at":"2030-01-01T08:00:00+07:00","closes_at":"2030-01-01T09:00:00+07:00","phase1_minutes":15,"phase2_minutes_per_question":3,"remediation_deadline":"2030-01-01T12:00:00+07:00"},"class_ids":["<CLASS>"],"preview":true}'
  Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/teacher/assessments/<ID>/publications" -Headers $h -Body $b
  ```

  phải trả 409 `Đề đang ở trạng thái đang soạn nên không phát hành được.`

## Không đạt khi

- Bất kỳ ô nào có giờ sẵn mà màn hình không nói là bản nháp; hay chip 12A tự tick.
- B3 không có dòng đỏ, hoặc dòng đỏ chỉ hiện **sau** khi bấm nút; nút sáng với giờ mở quá khứ.
- Hộp xác nhận đọc sai giờ (lệch 7 tiếng), sai lớp, sai số học sinh hay số câu; hoặc hai mốc thu
  hồi khác nhau; hoặc có chữ `từng lớp`.
- Bấm `Xem lại cài đặt` mà publications đã có dòng.
- Thẻ ghi `Đã phát hành cho 12A`, hoặc mọc thẻ thứ hai thay vì đổi chữ thẻ cũ.
- B8 bấm mà im lặng; `state` vẫn `published`; hoặc dòng 12A bị xoá thay vì có `recalled_at`.
- Lời gọi BE cuối trả 200.

## Ghi lại

- Giờ chạy và giá trị H.
- Nguyên văn dòng đỏ ở B3, và toàn bộ hộp xác nhận ở B5 (câu mở, năm dòng, ba câu luật, nhãn nút).
- Nguyên văn khối `ĐÃ PHÁT HÀNH` và thẻ chat sau B6, thẻ chat và chân panel sau B8.
- Kết quả mọi truy vấn trước / sau B5 / sau B7 / sau B8, và câu 409 của lời gọi BE, dán thẳng.
