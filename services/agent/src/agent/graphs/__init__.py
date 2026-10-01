"""Các graph LangGraph, mỗi việc soạn nội dung một graph.

Dùng graph thay vì một lần gọi hàm vì hai trong số các việc này có hình dạng mà
một đường thẳng không chứa nổi: viết một câu hỏi có thể không qua được check của
chính nó và cần làm lại. Giữ việc thứ ba -- lượt kèm học sinh -- cùng một dạng
chỉ tốn vài dòng, và đổi lại người đọc chỉ phải học một pattern thay vì hai.

Không có gì trong đây biết tới Redis, arq hay queue. Một graph dựng prompt, gọi
model, rồi trả lại thứ nhận được; việc publish là của handler, vì handler mới là
phần được cấp một connection.
"""
