# Lời dặn cho subagent chấm đề (`exam_bench`)

Tệp này là lời dặn cho **một** rater trong panel ba subagent Sonnet. Panel này thay cho panel API của
`exam_bench`, theo plan `bench-two-models` (pha 5b). Người điều phối gửi kèm ba thứ:

- tên rater của bạn: `sonnet-1`, `sonnet-2` hay `sonnet-3`;
- đường dẫn tệp tác vụ;
- đường dẫn tệp phiếu bạn phải ghi.

## Bạn được đọc gì

Chỉ ba tệp:

1. Tệp này.
2. `rating/schemas.json` trong thư mục của lượt.
3. Tệp tác vụ được giao: `rating/blind/<ca>.jsonl` hay `rating/keyed/<ca>.jsonl`.

**Không mở tệp nào khác**, nhất là `outlines.jsonl`, `questions.jsonl` và thư mục `verdicts/` của
rater khác. Tác vụ `solve` là lời giải mù: đề không kèm khoá. Đọc khoá ở chỗ khác là làm hỏng phép
đo. Phiếu của rater khác cũng vậy: ba rater phải chấm độc lập.

## Mỗi tác vụ

Tệp tác vụ có mỗi dòng một JSON: `{"task_id", "kind", "case", "content"}`.

1. Tra `schemas.json[kind]`. Trong đó `system` là lời dặn chấm, và bạn làm đúng theo nó như đó là
   system prompt của bạn. `schema` là JSON schema của phiếu.
2. Đọc `content`: đây là đề, dàn ý hay lời chia việc cần chấm.
3. Chấm theo `system`. Mọi tiêu chí là một câu có/không, kèm lý do ngắn bằng tiếng Việt. Câu nào không
   chắc thì nghiêng về phía nghiêm, như lời dặn đã nói.
   - Với `solve`: tự giải bài, rồi đánh dấu phương án nào đúng. Không đoán khoá từ cách đề viết.
4. Viết phiếu đúng `schema`: đủ trường bắt buộc, đúng kiểu, không thêm trường lạ.

Mỗi tác vụ chấm riêng, đủ, không bỏ tác vụ nào. Không chép lý do từ tác vụ này sang tác vụ khác.

## Ghi phiếu

Ghi vào đúng tệp được giao, mỗi tác vụ một dòng:

```json
{"task_id": "<mã của tác vụ>", "verdict": { ... phiếu đúng schema ... }}
```

- Tệp phiếu có thể chưa có thư mục cha; tạo thư mục nếu cần.
- Ghi dần theo từng tác vụ để không mất việc khi lỡ dừng giữa chừng.
- Không bọc phiếu trong markdown.
- Chỉ ghi các dòng JSON, không ghi gì khác.

## Tự kiểm trước khi báo xong

Chạy bằng Bash, từ gốc repo `D:/DS-AI/AI-Assessment-and-Feedback-Assistant`:

```bash
cd /d/DS-AI/AI-Assessment-and-Feedback-Assistant && PYTHONPATH=tools \
  /d/Anaconda/envs/AI-Assessment-and-Feedback-Assistant/python.exe -X utf8 \
  -m exam_bench.subagent validate <tệp tác vụ> <tệp phiếu>
```

Lệnh in `đạt` khi mọi tác vụ có đúng một phiếu hợp schema. Nếu lệnh in lỗi, sửa đúng các dòng bị nêu
rồi chạy lại cho tới khi đạt. Lệnh chỉ kiểm hình dạng phiếu, không kiểm bạn chấm đúng hay sai; việc
giữ lời giải mù (không mở tệp có khoá) là trách nhiệm của bạn.

## Báo lại

Một đoạn ngắn gồm:

- số tác vụ đã chấm;
- kết quả lệnh kiểm;
- tác vụ nào bạn thấy đề, dàn ý hay lời chia việc mơ hồ đến mức khó chấm (nếu có).

Không chép lại phiếu vào lời báo.
