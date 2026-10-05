# ADR-26 — Chữ sai cú pháp đi tới giáo viên, và giáo viên phải nhìn thấy chỗ sai

- **Trạng thái:** đã chốt
- **Ngày:** 2026-10-06

## Bối cảnh

Model viết toán bằng LaTeX, mà LaTeX mở mọi lệnh bằng dấu gạch chéo. JSON có đúng tám escape
hợp lệ — `\" \\ \/ \b \f \n \r \t \uXXXX` — nên khi model đặt `\frac` vào một chuỗi JSON mà
không nhân đôi dấu gạch chéo, bộ giải mã đọc `\f` thành form-feed và **nuốt luôn chữ `f`**.

Đo được trên database thật ngày 05/10/2026, phương án A của một câu vừa soạn:

```
24 0c 72 61 63 7b 31 7d 7b 36 7d 24      ->  "$" 0x0C "rac{1}{6}" "$"
```

`\int` sống sót vì `\i` không nằm trong tám escape kia.

Pha 5 từng dựng ở BE một lưới từ chối công thức nằm ngoài cặp `$`. Lưới ấy đã bị gỡ, vì nó
chặn nhầm nhiều hơn chặn đúng và một đề bị từ chối là một đề giáo viên không nhìn thấy.
Nhưng gỡ lưới xong thì không còn gì đứng giữa chữ hỏng và màn hình.

Hậu quả **không giống nhau giữa các chỗ**, và đó là lý do nó khó thấy. Đề bài thì `MathText`
vẫn nhận ra là toán và KaTeX in đỏ nguyên văn — xấu nhưng đọc ra được. Phương án thì tệ hơn:
`0x0C` đứng ngay sau `$` **là khoảng trắng** theo `\s` của regex, nên luật pandoc
`\$(?![\s$])` từ chối nhận cả cụm là toán, và dấu đô la lọt thẳng ra màn hình.

Và đường thoát hiểm đã chốt — *"giáo viên tự sửa tay"* — **không đi được**: đo trên trình
duyệt thấy 7 trong 12 ô của form sửa chứa ký tự điều khiển, mà chúng **vô hình** trong
`<textarea>`. Giáo viên nhìn thấy `$rac{1}{6}$`, gõ thêm dấu gạch chéo vào trước, và được
một chuỗi vẫn hỏng y như cũ.

## Quyết định

**Chữ sai cú pháp toán không bị chặn.** Không BE, không AGENT, không FE từ chối một câu hỏi
vì công thức trong nó không dựng hình được. Câu ấy tới tay giáo viên nguyên văn.

**Dấu gạch chéo bị JSON nuốt thì được dựng lại, nhưng chỉ khi chắc chắn.** AGENT khôi phục
một ký tự điều khiển thành `\` + tên lệnh **chỉ khi** phần chữ ngay sau nó ghép thành một
lệnh LaTeX có thật. Không ghép được thì để nguyên.

**Phần không dựng lại được phải nhìn thấy được.** Ô sửa in lại giá trị với ký tự điều khiển
thay bằng ký hiệu Control Pictures (`␈ ␉ ␌ ␡`), kèm số lượng. Giá trị trong ô nhập **không
bị đổi**.

## Vì sao

**Chặn thì giáo viên không thấy, mà không thấy thì không sửa được.** Một lưới cú pháp từ
chối cả câu hỏi sẽ xoá bằng chứng: model viết gì, sai ở đâu, sửa thế nào — tất cả biến mất
cùng câu bị từ chối. Ba cổng người của ADR-05 chỉ có nghĩa khi người **nhìn thấy** thứ họ
đang gác.

**Dựng lại mù thì phá đúng thứ vừa sửa.** `0x0A` và `0x0D` là xuống dòng **thật** trong lời
giải, và một lời giải xuống dòng được là thứ vừa được chữa ở đợt trước. Một phép "thay mọi
ký tự điều khiển" sẽ biến mọi lời giải nhiều bước thành một dải chữ hỏng. Từ điển lệnh là
thứ phân biệt được `0x0A` + `"abla"` (là `\nabla` bị nuốt) với `0x0A` + `"2. Tính..."` (là
một lần xuống dòng).

**Thà bỏ sót còn hơn đoán bừa vào chữ của người khác.** Khi từ điển thiếu một lệnh, hậu quả
là *không chữa* chứ không phải *chữa sai* — ký tự ở lại nguyên chỗ và giáo viên xử lý. Đã
gặp ngay lượt soạn đầu tiên: `\textstyle` bị bỏ sót, và model còn viết `\bigint` — một lệnh
**không tồn tại trong LaTeX**. Đoán ra một lệnh ở đó chỉ đổi một lỗi nhìn thấy được thành
một lỗi ẩn, vì KaTeX cũng không dựng được nó.

**Một chính sách không ai thi hành được thì không phải chính sách.** "Giáo viên tự sửa tay"
đọc như một quyết định đầy đủ cho tới lúc đo: ký tự hỏng vô hình thì không có hành động nào
để giáo viên làm. Ký hiệu nhìn thấy được là thứ biến chính sách ấy thành một việc làm được.

## Hệ quả

- Một đề bài có công thức không dựng hình được **vẫn phát hành được**. Trách nhiệm nằm ở
  cổng duyệt của giáo viên, không ở một phép kiểm tự động.
- `validate_question` chỉ còn giữ ADR-18. Mọi docstring nói nó kiểm cú pháp toán là nói sai.
- Từ điển `LATEX_COMMANDS` là một danh sách **kinh nghiệm** và sẽ còn thiếu. Thêm lệnh vào
  nó là việc thường, không phải việc đổi quyết định.
- Phép khôi phục **không** được đặt ở `packages/contracts`: `be/teacher_routes.py` dựng lại
  chính `GeneratedQuestion` cho đường PATCH, nên một validator ở tầng contract sẽ sửa luôn
  chữ **giáo viên tự gõ** — một bề mặt đoán mò đặt đúng vào cổng người của ADR-05.
- `learning_objective` là field chữ duy nhất **không có ô sửa**, nên nó phải được khôi phục
  tự động; không có đường thủ công nào cho nó.

## Nơi luật này đang được thi hành

- `services/agent/src/agent/latex_escapes.py` — `restore_latex_escapes()`, `LATEX_COMMANDS`,
  luật ranh giới (`_BOUNDARY`) và luật `_MIN_LENGTH_AFTER_NEWLINE`.
- `services/agent/src/agent/graphs/authoring.py` — `_unmangled()`, gọi trong `_write()` ngay
  sau `ainvoke`, phủ cả sáu field chữ của `GeneratedQuestion`.
- `tools/check_contract.py` — `check_the_model_text_passes_through_the_escape_repair()`, đọc
  cây cú pháp của `_write` và đỏ khi lời gọi biến mất.
- `services/agent/tests/test_latex_escapes.py` — 20 test, gồm ba ca "phải giữ nguyên" cho
  xuống dòng thật và hai ca hồi quy đo từ lượt soạn thật.
- `services/agent/tests/test_authoring_graph.py` —
  `test_json_an_mat_dau_gach_cheo_thi_duoc_dung_lai`, khẳng định trên **mọi** field chữ.
- `services/fe/src/screens/teacher/Panel.tsx` — `MANGLED`, `visible()`, và dòng `.mangled`
  trong `Field`.
- `services/fe/src/teacher.test.tsx` — describe *"ký tự điều khiển ẩn trong ô sửa"*, bốn
  test; trong đó một test ghim rằng `textarea.value` **không** bị đổi.
- Figma `mOe2ZmrqOq1Uix45v6PNGD`, component `Question card — đang sửa` (`468:2050`), node
  `mangled` (`493:17`).
