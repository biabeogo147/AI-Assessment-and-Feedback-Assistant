"""*Document agent* của `document-agent-hierarchy`: đọc bản thô trong kho nội dung, dựng cây mục lục
ba cấp, ghi lại.

Riêng với Kriky (`services/agent`): khác prompt, khác model, khác queue. Chia module theo **việc**:

- `features`, `rules`, `assemble`, `chunks` -- hàm thuần, test không cần mạng;
- `jev` -- module duy nhất import `typesafe_sdk`;
- `llm` -- module duy nhất import `langchain`, cho tóm tắt (`gpt-4o-mini`) và đọc banner
  (`gpt-5.6-luna`);
- `graph` -- LangGraph nối các bước lại.
"""
