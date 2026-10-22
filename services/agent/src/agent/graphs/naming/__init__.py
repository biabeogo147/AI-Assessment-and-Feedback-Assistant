"""Đặt tên cho một đoạn chat, từ đúng câu mở đầu của nó.

Task nhỏ nhất trong cả AGENT, và nó nhỏ vì nó **được phép** nhỏ: nó không đọc lịch sử,
không gọi tool, không quyết định gì. Nó nhận một chuỗi và trả về một chuỗi ngắn hơn.

Một graph một node thì gần như chỉ là một lời gọi model bọc giấy. Nó vẫn là graph, vì luật
của repo nói graph là nơi **duy nhất** gọi model — handler không bao giờ chạm `llm`. Giữ
đúng ranh giới ấy đáng giá hơn việc tiết kiệm mười lăm dòng: ngày task này cần thêm một
bước, chỗ thêm vào đã có sẵn.

Cái tên là thứ giáo viên đọc trên một hàng rộng 228px, nên prompt đòi ngắn. Nhưng prompt
chỉ là một lời nhờ: BE cắt và dọn lại, vì một model trả ba trăm ký tự hay bọc câu trả lời
trong dấu ngoặc kép là chuyện thường.

**Bản prompt đầu ép model bịa.** Nó nói *"gọi tên VIỆC, không chào hỏi"* và không cho một
đường ra nào cho một câu không chứa việc nào — nên với *"Chào bạn"*, model buộc phải nghĩ
ra một việc, và nguồn chữ duy nhất trong tầm với là chính hai ví dụ của prompt. Đo được
trên trình duyệt thật: *"Chào bạn"* ra *"Tạo đề kiểm tra 15 phút"*, đúng phép trộn hai ví
dụ `"Đề 15 phút — Hàm số 12A"` và `"Tạo đề đạo hàm"`. Cái tên sai ấy **tuân thủ** mọi luật
còn lại — sáu từ, viết thường, không ngoặc kép — nên không có khâu dọn nào bắt được nó.

Nay prompt có đường ra cho câu không nhờ việc gì, và các ví dụ là **cặp vào–ra** chứ không
phải những cái tên đứng một mình: một cái tên đứng một mình là chữ cho sẵn để model mượn
lúc bí. Và BE có một chốt kiểm thật (`teacher_chat._echoes`), vì một prompt vẫn chỉ là một
lời nhờ.

Hai thứ cố ý ở đây, cả hai do review chỉ ra. **Luật nói đúng cái đang được thi hành**: bản
đầu viết *"mọi từ trong tiêu đề phải bắt nguồn từ câu vào"* trong khi `_echoes` chỉ đòi
**một** từ chung — và chính ba ví dụ ngay dưới nó đều thêm chữ mới (*"đề"*, *"Kết quả"*),
tức luật bị ví dụ của mình phủ định, mà model đọc ví dụ chặt hơn đọc luật. **Và ví dụ cho
câu không nhờ việc gì không được là `Chào bạn`**: đó đúng là ca đã đo hỏng, nên để nó ở đây
là in sẵn đáp án — chạy lại ca ấy sau đó chỉ chứng minh model biết nhớ, không chứng minh nó
biết theo luật.
"""

from agent.graphs.naming.graph import name_it

__all__ = ["name_it"]
