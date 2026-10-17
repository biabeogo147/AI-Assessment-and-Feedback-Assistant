"""Các graph LangGraph, mỗi việc soạn nội dung một graph.

Dùng graph thay vì một lần gọi hàm vì vài việc có hình dạng mà một đường thẳng không chứa
nổi: viết một câu hỏi có thể không qua được check của chính nó và cần làm lại (`authoring`),
một đề nghị bước kế có thể hỏng hình dạng và được hỏi lại một lần (`propose`). Các việc còn
lại -- lượt kèm học sinh (`explain`), lời kể sau plan (`reporting`), tên đoạn chat
(`naming`) -- giữ cùng một dạng chỉ tốn vài dòng, và đổi lại người đọc chỉ học một pattern.

Không có gì trong đây biết tới Redis, arq hay queue. Một graph dựng prompt, gọi
model, rồi trả lại thứ nhận được; việc publish là của handler, vì handler mới là
phần được cấp một connection.
"""
