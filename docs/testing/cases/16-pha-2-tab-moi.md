# 16. Lượt chữa bài làm tiếp ở tab mới

Nhóm: Học sinh · Lượt model: ~1 mỗi câu sai (câu biến thể) · Chạy sau: một đề đã phát hành có học
sinh làm sai ít nhất hai câu (đề seed sau `db-reset` là đủ)

## Cho người xem thấy gì

Học sinh mở một lượt làm lại, chọn đáp án, rồi đóng tab giữa chừng. Mở lại ở **tab mới** thì vào lại
đúng lượt ấy, đúng các câu, lựa chọn đã chọn vẫn sáng. Không mất lượt nào trong ba lượt được phép
(ADR-17), và nộp lượt có hộp xác nhận như nộp bài. Câu biến thể khác câu gốc, không chỉ thêm đuôi.

## Chuẩn bị

- `db-reset`, khởi động lại BE và AGENT (`model=` trong log AGENT là model của lần chạy).
- Đăng nhập học sinh `HS2026-1204` (header dev mặc định của FE). Làm bài pha 1, cố ý sai **ít nhất
  hai câu**, nộp. Chép `<attempt>` từ địa chỉ `#/attempt/<attempt>/…`.

## Lời chat

Không gõ chat. Chỉ bấm:

1. Ở màn kết quả bấm *Hỏi trợ lý và làm lại dạng bài sai*, rồi *Làm bài mới* ở cổng. Đọc đầu màn
   lượt chữa: `Làm lại dạng bài sai · N câu · M phút`.
2. Chọn đáp án cho **câu đầu**, chưa nộp. Chép `<round>` từ địa chỉ `#/round/<attempt>/<round>`.
3. Đóng tab. Mở tab mới, vào `#/attempt/<attempt>/tutor`.
4. Bấm *Làm tiếp lượt đang mở*.
5. Bấm *Nộp bài* ở cột phải, đọc hộp, bấm *Quay lại làm tiếp*. Bấm *Nộp bài* lần nữa rồi *Nộp bài*
   trong hộp.

## Nếu Kriky rẽ

| Màn làm gì | Phán | Vì sao |
| --- | --- | --- |
| Bước 1 báo *"Chưa soạn được câu cho lượt này"* | Ghi `last_fault`/log AGENT. **Chấp nhận được** nếu `rounds_used` vẫn 0 | Model hỏng thì BE trả 503 trước khi ghi lượt (ADR-17) |
| Bước 3 màn trợ lý chỉ có nút *Làm bài mới* xám | **Không đạt** | Có `open_round_id` thì phải mời làm tiếp |
| Bước 4 vào lượt mà lựa chọn câu đầu không sáng | **Không đạt** | `GET /rounds/{id}` trả `chosen_label` |
| Câu biến thể là câu gốc thêm một đuôi chữ | **Không đạt** | `validate_retry` từ chối câu gốc chứa trọn trong câu mới |

## Đạt khi

- **Bước 1:** `M` là độ dài lượt (số câu × phút mỗi câu, cắt theo hạn), không phải thời gian còn lại.
- **Bước 3:** dòng nhắc nói em đang có một lượt chưa nộp; nút *Làm tiếp lượt đang mở*.
- **Bước 4:** đúng các câu của lượt, đúng thứ tự, câu đầu sáng lựa chọn của bước 2.
- **Bước 5:** hộp *Nộp lượt này?* đếm đúng số câu đã/chưa trả lời; *Quay lại làm tiếp* không nộp gì;
  nộp xong sang màn kết quả, câu làm đúng lên 0,5.
- Database:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select index, started_at, ends_at, submitted_at from rounds where id = '<round>';"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select q.order_index, o.rounds_used, o.mark from question_outcomes o join questions q on q.id = o.question_id where o.attempt_id = '<attempt>' order by 1;"
  ```

  Một hàng lượt, `submitted_at` có sau bước 5; `rounds_used` tăng đúng một cho mỗi câu của lượt.

## Không đạt khi

- Tab mới không vào lại được lượt, hay xin được một lượt **thứ hai** trong khi lượt đầu còn mở.
- Lựa chọn đã lưu mất sau khi đóng tab.
- Nộp lượt không có hộp xác nhận, hay *Quay lại làm tiếp* vẫn nộp.
- Một câu biến thể trùng câu gốc hay câu của lượt trước.

## Ghi lại

- Ảnh: đầu màn lượt chữa (bước 1); màn trợ lý ở tab mới (bước 3); lượt đọc lại (bước 4); hộp nộp
  (bước 5); màn kết quả sau nộp.
- Đề bài câu gốc và câu biến thể của từng câu trong lượt.
- Kết quả hai truy vấn database.
