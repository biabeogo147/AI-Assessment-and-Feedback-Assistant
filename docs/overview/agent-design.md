# Thiết kế AGENT

## Mục đích tài liệu

Tài liệu này dành cho người sắp đọc hoặc sửa `services/agent`. Nó trả lời: AGENT nhận việc từ đâu,
mỗi việc chạy qua graph nào, model được gọi ra sao, và sau mỗi lời model những luật nào sửa hay trả
lại lời ấy.

Ba thứ tài liệu này **không** nói, vì đã có chỗ khác nói:

- vì sao AGENT là một service riêng, không giữ credential database, và không quyết định gì:
  [Architecture](architecture.md), mục *Ranh giới quyền quyết định*; ràng buộc cho người sửa code ở
  `services/agent/AGENTS.md`;
- luật nghiệp vụ mà prompt và luật code phục vụ: các ADR trong [`docs/decisions/`](../decisions/README.md);
- giao diện chat giáo viên hiện những gì AGENT trả về: [Teacher Surface](teacher-surface.md).

Code nằm ở `services/agent/src/agent/`. Mỗi sơ đồ dưới đây ghi tên hàm thật, nên tìm trong code
được ngay.

Ba chữ hay gặp:

- **`known`**: ghi chú model tự viết trong mỗi đề nghị, liệt kê những gì nó đã biết (môn, khối,
  phạm vi, số câu). Không tới tay giáo viên; luật code đọc nó để bắt dàn ý lệch số câu hay câu hỏi
  lại thừa.
- **Lượt kể lại**: sau khi BE chạy xong một plan, nó hỏi AGENT thêm một lượt để Kriky kể lại kết quả
  (ADR-25). Lượt này chỉ có tool đọc, `plannable` rỗng.
- **Chip**: tài liệu giáo viên đính kèm vào câu chat (`attached_document`).

## AGENT đứng ở đâu

Câu hỏi sơ đồ trả lời: *việc tới AGENT bằng đường nào, kết quả đi về đâu, và AGENT gọi ra những gì?*

```mermaid
flowchart LR
    BE["BE<br/>agent_gateway"]
    subgraph redis["Redis"]
        queue[["queue aiafa:grading"]]
        store[("arq result store")]
        pubsub(["pub/sub<br/>aiafa:stream:&lt;uuid&gt;<br/>draft:&lt;assessment_id&gt;"])
    end
    subgraph agent["AGENT (arq worker, không mở cổng)"]
        worker["worker.WorkerSettings<br/>năm task"]
        handlers["handlers.py<br/>đường mock · đường model"]
        graphs["graphs/<br/>propose · authoring · explain · naming"]
        router["skill_router.py"]
        llm["llm.py<br/>with_fallback"]
    end
    provider["Model provider<br/>OpenAI · Anthropic · Google"]
    jev["Jev (TypeSafe AI)"]

    BE -- "enqueue job (payload contracts)" --> queue
    queue --> worker --> handlers --> graphs
    graphs --> llm --> provider
    graphs --> router --> jev
    handlers -- "dict kết quả" --> store
    handlers -- "mảnh chữ, chuông tiến độ" --> pubsub
    store -- "BE chờ hay thu sau" --> BE
    pubsub -- "BE nghe" --> BE
```

Ba điều sơ đồ cho thấy:

- **Đường vào duy nhất là queue.** AGENT không mở cổng nào, và mọi thứ một job cần đi trong payload
  của nó (`packages/contracts`). AGENT không đọc database nào; `tools/check_contract.py` đỏ nếu một
  credential database xuất hiện ở đây.
- **Kết quả là một `dict`, không phải phán quyết.** BE kiểm lại mọi thứ rồi mới ghi.
  `tests/test_no_routing_decision.py` gọi mọi task và đỏ nếu kết quả mang một trường phán xử.
- **Chỉ `llm.py` dựng model,** nên đổi provider là sửa `.env`, không sửa graph nào. Chỉ
  `skill_router.py` import SDK của Jev.

## Năm task

Câu hỏi sơ đồ trả lời: *task nào chạy handler nào, và handler ấy đi qua graph nào?*

```mermaid
flowchart LR
    subgraph tasks["Task (tên ở contracts)"]
        t1["propose_next_step"]
        t2["write_draft_question"]
        t3["generate_retry_question"]
        t4["explain_turn"]
        t5["name_conversation"]
    end
    subgraph handlers["handlers.py"]
        h1["propose_next_step"]
        h2["write_draft_question<br/>+ _arm_bell"]
        h3["generate_retry_question"]
        h4["explain"]
        h5["name_conversation"]
    end
    subgraph graphs["graphs/"]
        g1["propose.propose"]
        g2["authoring.write_question<br/>brief: draft_brief"]
        g3["authoring.write_question<br/>brief: retry_brief"]
        g4["explain.speak"]
        g5["naming.name_it"]
    end
    t1 --> h1 --> g1
    t2 --> h2 --> g2
    t3 --> h3 --> g3
    t4 --> h4 --> g4
    t5 --> h5 --> g5
```

Worker đăng ký task dưới hằng số của `contracts`, không dưới tên hàm Python. Đổi tên một hàm không
làm gãy lời gọi enqueue của BE. Khi nào BE gọi từng task, và nó làm gì với kết quả, xem
[Architecture](architecture.md), bảng ở mục *Đường giao tiếp*.

**Graph là nơi duy nhất gọi model;** handler không chạm `llm`. Vì thế cả `naming` cũng là một graph,
dù nó chỉ có một node.

## Model tắt, model hỏng

Mỗi handler có hai đường:

- **`LLM_ENABLED=false`** (hay `LLM_MODEL` trống): trả nội dung dọn trước, tất định. Luồng chạy được
  đầu tới cuối mà không tốn tiền, và test khẳng định được cùng một điều hai lần.
- **Model bật:** gọi graph.

Model bật mà hỏng thì mỗi task xử một kiểu, theo cái giá của chữ sai ở task ấy:

| Task | Model hỏng thì | Vì sao |
| --- | --- | --- |
| `propose_next_step` | Trả một **thông báo hệ thống** (`notice=True`, *"Kriky chưa trả lời được lúc này…"*), không lùi về mock | Mock đoán việc bằng từ khoá, và chữ của nó sẽ nói dưới giọng Kriky (ADR-30) |
| `write_draft_question` | **Ném lỗi**; job hỏng | Câu dọn trước từng lọt vào đề thật. BE ghi `last_fault` rồi hỏi lại có trần |
| `generate_retry_question` | Lùi về kho biến thể của câu gốc; kho trống thì ném | BE trả 503 trước khi ghi lượt, nên học sinh không mất vòng nào (ADR-17) |
| `explain_turn` | Chưa phát mảnh nào thì trả lượt dọn trước; đã phát thì giữ đúng phần đã phát | Chữ đã lên màn hình học sinh, nên phải lưu đúng thứ ấy |
| `name_conversation` | Trả tên dọn trước | Tên đoạn chat không vào đề nào |

## `llm`: provider và fallback

Câu hỏi sơ đồ trả lời: *một graph xin model thế nào, và model dự phòng chen vào ở đâu?*

```mermaid
flowchart LR
    caller["Graph<br/>llm.with_fallback(shape)"]
    models["chat_models()<br/>dựng một lần, cache suốt đời worker"]
    first["Model chính<br/>LLM_PROVIDER / LLM_MODEL"]
    second["Model dự phòng<br/>LLM_FALLBACK_PROVIDER / LLM_FALLBACK_MODEL"]
    caller --> models
    models --> first
    models -. "chỉ khi có cấu hình" .-> second
    first -- "shape(model)<br/>vd. with_structured_output" --> chain["Runnable<br/>chính, rồi dự phòng khi chính raise"]
    second -- "shape(model)" --> chain
```

Hai chỗ dễ sai, cả hai ghi ở docstring của `llm.py`:

- **Credential được truyền vào** từ `Settings`, không đọc từ biến môi trường của process.
- **`shape` áp lên từng model trước**, rồi mới xâu fallback. Ngược thứ tự thì
  `with_structured_output` đi qua reflection trên type hint và sụp bằng một `NameError` khó đọc.

Có một model thì `with_fallback` trả thẳng runnable của nó, không bọc, nên stream giữ nguyên.

## Chọn skill (Jev)

Câu hỏi sơ đồ trả lời: *lời dặn nào của Kriky được nạp cho lượt này?*

Một **skill** là một file Markdown trong `agent/skills/`. Frontmatter của nó có `name` và
`description` tiếng Anh, chính là `criteria` Jev đọc. Thân file là lời dặn tiếng Việt chèn vào
prompt. Hiện có bốn skill:

- `soan-de`: soạn đề;
- `lop-va-ket-qua`: tra lớp, kết quả, tạo lớp;
- `hoi-tai-lieu`: hỏi nội dung sách;
- `tro-chuyen-chung`: skill bao quát, không bao giờ được hỏi.

```mermaid
flowchart TD
    history["Lịch sử đoạn chat"] --> state["state_of<br/>4 lượt chữ gần nhất, mỗi lượt ≤ 600 ký tự<br/>không có kết quả tool"]
    state --> usable{"Có khoá Jev, có lượt<br/>giáo viên, có skill<br/>chuyên biệt?"}
    usable -- không --> all
    usable -- có --> cached{"Đã chọn cho<br/>state này?"}
    cached -- có --> reuse["Dùng lại lựa chọn cũ<br/>(nhớ 256 state)"]
    cached -- chưa --> ask["Jev system_one<br/>mỗi skill chuyên biệt một câu yes/no<br/>song song, trần SKILL_ROUTER_TIMEOUT_SECONDS"]
    ask -- "trả lời được" --> pick["Giữ skill có P(yes) ≥ SKILL_MIN_YES"]
    pick --> none{"Không skill<br/>nào qua?"}
    none -- đúng --> general["Chỉ tro-chuyen-chung"]
    none -- sai --> chosen["Các skill qua ngưỡng"]
    ask -- "timeout · lỗi mạng · hình dạng lạ" --> all["Nạp MỌI skill<br/>(không nhớ, lượt sau hỏi lại)"]
```

**Luật an toàn không bao giờ nằm trong skill.** Jev chọn sai thì một skill vắng mặt, nên mọi luật mà
vắng nó là nguy hiểm thuộc về `CORE` của `graphs/propose/prompt.py`.

Việc chọn skill còn bật hai luật code:
- `books.opens_library` chỉ mở thư viện tài liệu ở lượt có `soan-de` hay `hoi-tai-lieu`;
- `read_order.answered_unread` chỉ trả lại lời trả lời về sách ở lượt có `hoi-tai-lieu`.

Ở lượt kể lại sau một plan, `propose` cộng thêm skill của chính plan
ấy (`telling_skills`), vì lời cuối có thể là lời mở của plan chứ không phải lời giáo viên.

## Graph `propose`: một bước của lượt chat giáo viên

`propose_next_step` là task phức tạp nhất. Nó không hoàn thành việc gì của riêng nó. BE sở hữu vòng
lặp của một lượt chat, và **mỗi bước** của vòng ấy hỏi AGENT *"làm gì tiếp"* một lần. AGENT trả một
trong năm `kind`:

| `kind` | Nghĩa | BE làm gì |
| --- | --- | --- |
| `say` | Nói một câu | Lưu, kết thúc lượt |
| `ask_clarify` | Hỏi lại, kèm nút (tối đa 3 câu, ADR-32) | Lưu, chờ giáo viên |
| `call_tool` | Gọi một tool **đọc** ngay | Chạy tool, thêm kết quả vào lịch sử, hỏi AGENT bước kế |
| `outline` | Nêu dàn ý đề (ADR-29, ADR-38) | Kiểm số câu và bài nguồn, lưu, chờ giáo viên đồng ý |
| `plan` | Nêu các việc **ghi** cho pha 2 | Kiểm cả plan, chạy từng bước, rồi hỏi AGENT một lượt kể lại |

### Một bước, đầu tới cuối

Câu hỏi sơ đồ trả lời: *một job `propose_next_step` đi qua những gì, theo thứ tự nào?*

```mermaid
sequenceDiagram
    autonumber
    participant BE
    participant H as handlers.propose_next_step
    participant P as graph.propose()
    participant R as skill_router.choose
    participant G as graph (compose → choose)
    participant S as split.split_outline
    participant M as Model

    BE->>H: NextStepRequested<br/>(history, catalog, plannable)
    alt LLM tắt
        H-->>BE: next_step(request): đề nghị mock
    else LLM bật
        H->>P: request
        P->>R: history
        R-->>P: tên các skill
        Note over P: Lượt kể lại: cộng skill của plan vừa chạy
        P->>G: state {request, skills}
        G->>M: messages (structured _Proposal)
        M-->>G: đề nghị
        Note over G: Luật sau model (mục dưới)
        alt Đề nghị hỏng kiểu AskAgain
            G-->>P: raise AskAgain(hint)
            P->>G: chạy lại một lần, kèm hint
            G->>M: messages + ghi chú hệ thống
            M-->>G: đề nghị lần hai
        end
        G-->>P: step
        P->>S: step, request
        opt step là plan soạn (start_drafting, replace_question)
            S->>M: lời dàn ý giáo viên vừa đồng ý
            M-->>S: Split {note, jobs}
        end
        S-->>P: step (kèm split nếu có)
        P-->>H: step, request_id của BE
        H-->>BE: NextStepCompleted
    end
```

Handler chỉ gọi `propose()` và bắt lỗi: provider hỏng ở bất kỳ đâu trong `propose()` thì handler trả
thông báo hệ thống (mục *Model tắt, model hỏng*). Phía BE của vòng này, gồm pha 1 hỏi AGENT, pha 2 chạy plan và chuông
soạn đề, được vẽ ở [Architecture](architecture.md#một-lượt-chat-giáo-viên).

### Prompt được dựng thế nào

Câu hỏi sơ đồ trả lời: *model thấy gì, theo thứ tự nào?* (`propose/compose.py`)

```mermaid
flowchart TD
    subgraph system["SystemMessage, thứ tự cố định"]
        core["CORE<br/>luật an toàn, ít đổi nhất"]
        skills["Thân các skill đã chọn<br/>chỗ {thư viện} thành LIBRARY<br/>(LIBRARY_ASK với hoi-tai-lieu)<br/>khi opens_library"]
        name["Bạn đang nói với &lt;tên giáo viên&gt;"]
        doc["Tài liệu đính kèm<br/>ready · đang xử lý · không đọc được"]
        book["BOOK_PROCEDURE (soan-de)<br/>BOOK_QUESTIONS (hoi-tai-lieu)<br/>khi book_in_view"]
        catalog["Tool dùng ngay (call_tool)<br/>hay: không có tool nào"]
        plannable["Tool nêu được trong plan<br/>hay: không nêu plan được"]
        core --> skills --> name --> doc --> book --> catalog --> plannable
    end
    subgraph turns["Lịch sử: mỗi lượt một message"]
        teacher["teacher → HumanMessage"]
        assistant["assistant → AIMessage<br/>kèm các câu hỏi lại (_asked_back)"]
        call["tool_call → AIMessage<br/>Mình xin gọi &lt;tool&gt; với &lt;args&gt;"]
        result["tool_result, plan → HumanMessage<br/>kết quả dạng dữ liệu (_describe_result)"]
        outline["outline → AIMessage lời dàn ý<br/>+ HumanMessage số câu, bài nguồn"]
        notice["notice → HumanMessage<br/>(Ghi chú của hệ thống…)"]
    end
    hint["Hint của lần hỏi lại<br/>(chỉ ở lần hai)"]
    system --> turns --> hint
```

Thứ tự trong `SystemMessage` có lý do. Phần đứng đầu càng ít đổi giữa hai lượt thì prompt cache của
provider càng dùng lại được nhiều. Skill đứng **sau** `CORE`, nên không skill nào nói trước được một
luật an toàn.

`catalog` và `plannable` tới thành hai danh sách riêng. Model phải phân biệt *gọi được ngay* với
*hẹn làm ở pha 2*; gọi một tool ghi ngay lượt này thì BE từ chối, và vòng lặp mất một bước chỉ để
phát hiện lại đúng điều ấy.

### Luật sau model, theo đúng thứ tự

Câu hỏi sơ đồ trả lời: *sau khi model trả lời, `choose()` làm gì với đề nghị, theo thứ tự nào?*

Có hai loại luật. **Luật sửa** đổi đề nghị thành một đề nghị khác, thường là một lời gọi tool đọc mà
model bỏ qua. **Luật trả lại** ném `AskAgain`, để `propose` hỏi model thêm đúng một lần.

```mermaid
flowchart TD
    start(["Model trả lời"]) --> parsed{"Đọc được<br/>thành _Proposal?"}
    parsed -- không --> agreed0{"approved_plan:<br/>giáo viên vừa<br/>đồng ý dàn ý?"}
    agreed0 -- có --> planA(["plan dựng từ dàn ý"])
    agreed0 -- không --> unparsed["raise Unparsed"]
    parsed -- có --> agreed{"approved_plan:<br/>giáo viên vừa<br/>đồng ý dàn ý?"}
    agreed -- có --> planB(["plan dựng từ dàn ý<br/>lời mở: lời model viết nếu nó chọn plan,<br/>không thì không có lời mở"])
    agreed -- không --> empty{"say / ask_clarify / outline<br/>mà text rỗng?"}
    empty -- "có (trừ câu hỏi có chữ,<br/>trừ lượt kể lại im lặng)" --> nothing["raise NothingToSay"]
    empty -- không --> nooutline{"outline không số câu,<br/>hay gọi tool tên outline,<br/>hay dàn ý sai hình dạng?"}
    nooutline -- có --> noout["raise NoOutline"]
    nooutline -- không --> reads["Chuỗi luật thứ tự đọc (read_order.py)<br/>reads_first → picked_book_first → misfiled_read<br/>→ toc_first → library_first → which_book<br/>→ read_before_outline"]
    reads -- "which_book: câu hỏi lại ngay sau<br/>list_documents không hỏi tài liệu nào" --> wq["raise WrongQuestion"]
    reads --> purpose["right_purpose<br/>dàn ý đúng việc: thay câu N / soạn thêm"]
    purpose --> brief["outline: gắn môn, khối, phạm vi<br/>từ known (brief_in)"]
    brief --> planok{"plan thiếu tham số,<br/>chữ hỏng?"}
    planok -- có --> incomplete["raise IncompletePlan"]
    planok -- không --> revision{"plan soạn ngay sau<br/>lời xin sửa dàn ý?"}
    revision -- có --> over["raise PlanOverRevision"]
    revision -- không --> count{"outline lệch số câu<br/>known, lời giáo viên,<br/>hay thay câu ≠ 1?"}
    count -- có --> uncounted["raise UncountedOutline"]
    count -- không --> unread{"answered_unread:<br/>trả lời về sách<br/>mà chưa mở sách?"}
    unread -- có --> au["raise AnsweredUnread"]
    unread -- không --> clarify{"ask_clarify?"}
    clarify -- "không" --> done(["step"])
    clarify -- "có, nhiều câu (questions)" --> many["Lọc nút giả từng câu (answers):<br/>câu hỏi, tên mục, Khác"]
    many --> tooMany{"Quá 3 câu thật?"}
    tooMany -- có --> tmq["raise TooManyQuestions"]
    tooMany -- không --> fewMany{"Câu nào ít nút hơn cần?<br/>(0 với tên lớp mới, số dòng thật<br/>với câu về dòng, 3 với tham số)"}
    fewMany -- có --> fc1["raise FewChoices"]
    fewMany -- không --> done
    clarify -- "có, một câu" --> one["Lọc nút giả (answers)"]
    one --> known{"Không nút nào, known đủ,<br/>và không phải ngay sau<br/>list_documents?"}
    known -- có --> awk["raise AskedWhatWasKnown"]
    known -- không --> fewOne{"Ít nút hơn<br/>choices_wanted?"}
    fewOne -- có --> fc2["raise FewChoices"]
    fewOne -- không --> done
```

Hai chỗ sơ đồ không vẽ: đề nghị không chuyển được thành `NextStepCompleted` (`ValidationError`) thì
với `outline` là `NoOutline`, với kind khác là lỗi ném thẳng, không hỏi lại, và handler ra thông báo
hệ thống.

`approved_plan` đứng **trước** mọi luật trả lại. Nếu sau lời *"oke"* model trả về một câu rỗng hay
hỏng mà luật biến nó thành câu hỏi lại, thì lời duyệt mất, và lần gõ lại không còn đứng ngay sau dàn
ý (ADR-29).

Luật thứ tự đọc là luật sửa, trừ `which_book` ném `WrongQuestion`. Đề nghị đúng việc mà sai bước thì thành một lời gọi tool đọc; ở
bước kế của vòng BE, model nêu lại với kết quả trong tay. Mỗi luật tự kiểm xem bước đọc đã có chưa,
nên không gọi lại một bước đã đọc.

### Hỏi lại đúng một lần

Câu hỏi sơ đồ trả lời: *một `AskAgain` thì kết thúc bằng gì?* (`propose/graph.py`)

```mermaid
flowchart TD
    first["Lần một: graph ném AskAgain"] --> second["Lần hai: chạy lại graph<br/>kèm hint của lần một"]
    second -- "ra đề nghị không lỗi" --> ok(["Dùng lần hai"])
    second -- "lại Flawed" --> flawed{"Cả hai lần<br/>là FewChoices?"}
    flawed -- có --> better(["Giữ lần có nhiều nút hơn"])
    flawed -- không --> keep2(["Giữ lần hai<br/>BE tự xét plan"])
    second -- "lỗi khác: rỗng, hỏng, provider" --> wasflawed{"Lần một là Flawed<br/>(mang đề nghị theo)?"}
    wasflawed -- có --> keep1(["Giữ đề nghị lần một"])
    wasflawed -- không --> empty{"Lần hai là<br/>NothingToSay / NoOutline?"}
    empty -- có --> unclear(["Thông báo hệ thống _UNCLEAR<br/>Kriky chưa hiểu rõ ý bạn…"])
    empty -- không --> raise(["Ném tiếp → handler<br/>ra thông báo model hỏng"])
```

Luật chung của lưới này: **hỏi lại không bao giờ được làm kết quả tệ hơn lúc chưa có nó.** Một
`Flawed` là đề nghị dùng được nhưng thiếu một thứ, nên nó mang chính đề nghị ấy theo. Lần hai hỏng
kiểu khác thì vẫn còn lần một để dùng.

| Lớp (`ask_again.py`) | Bắn khi | Mang đề nghị theo |
| --- | --- | --- |
| `NothingToSay` | `say`, `ask_clarify`, `outline` mà lời rỗng | không |
| `Unparsed` | Đầu ra không đọc được thành đề nghị (vd. tên tool ghi vào `kind`) | không |
| `NoOutline` | Dàn ý không số câu, sai hình dạng, hay gọi `outline` như một tool | không |
| `IncompletePlan` | Bước plan thiếu tham số bắt buộc, hay chữ hỏng | có |
| `PlanOverRevision` | Plan soạn ngay sau lời giáo viên xin sửa dàn ý | có |
| `UncountedOutline` | Số câu dàn ý khác `known`, khác lời giáo viên, hay thay câu mà khác 1; hint nói đúng số | có |
| `AnsweredUnread` | Trả lời câu hỏi về sách mà chưa mở sách | có |
| `AskedWhatWasKnown` | Hỏi lại không câu, không nút, dù `known` đã đủ bốn mục | có |
| `TooManyQuestions` | Quá 3 câu hỏi một lượt (ADR-32) | có |
| `FewChoices` | Ít nút thật hơn cần (3 cho tham số, số dòng có thật cho câu về dòng, 0 cho câu xin tên lớp mới) | có |
| `WrongQuestion` | Câu hỏi lại ngay sau `list_documents` mà không hỏi *tài liệu nào* | có |

### Dàn ý, đồng ý, chia việc (ADR-29, ADR-38)

Câu hỏi sơ đồ trả lời: *một đề đi từ lời xin tới các câu được soạn qua những lượt nào?*

```mermaid
stateDiagram-v2
    [*] --> Gom: giáo viên xin soạn đề
    Gom --> HoiLai: thiếu môn, khối, phạm vi hay số câu
    HoiLai --> Gom: giáo viên trả lời
    Gom --> DocSach: có sách trong tầm
    DocSach --> Gom: kết quả tool đọc
    Gom --> DanY: đủ bốn mục → kind=outline
    DanY --> Gom: giáo viên xin sửa
    DanY --> Plan: giáo viên đồng ý (AGREES)
    Plan --> ChiaViec: split_outline
    ChiaViec --> Soan: BE guard_drafting đúng số job → mỗi câu một job
    ChiaViec --> ThongBao: chia hỏng sau một lần trả lại (SplitFailed)
    ThongBao --> DanY: giáo viên gõ lại lời đồng ý
    Soan --> KeLai: các câu về (chuông tiến độ)
    KeLai --> [*]
```

- **Dàn ý** là lời Markdown Kriky viết, kèm `outline_questions` (số câu) và `outline_nodes` (bài
  nguồn). BE chỉ kiểm hai thứ ấy, không đọc lời.
- **Đồng ý** được đọc bằng regex (`outline.AGREES`). `approved_plan` dựng plan từ chính lượt dàn ý:
  việc (`for`: `new`, `more`, `replace`), câu bị thay, môn, khối, phạm vi. Model không phải nhớ lại.
- **Chia việc** chạy ở cuối `propose()`, trong cùng job, sau khi plan đã có:

```mermaid
sequenceDiagram
    participant P as propose()
    participant S as split_outline
    participant M as Model

    P->>S: step (plan), request
    Note over S: Không phải plan soạn, đã có split,<br/>không có dàn ý ngay trước lời giáo viên (_shown),<br/>dàn ý không có total, hay việc dàn ý khác việc plan<br/>→ trả step nguyên
    S->>M: SYSTEM + split_prompt(lời xin, lời dàn ý, số câu, câu bị thay)
    M-->>S: _Split {note, jobs}
    Note over S: Đề mới, soạn thêm: thừa job thì cắt đuôi về đúng số câu.<br/>Thay câu: không cắt, thừa là lệch.
    alt Đúng số job, không job trống
        S-->>P: step + Split(note, jobs)
    else Lệch số job, job trống, hay không parse (lần 1)
        S->>M: + lời trả lại (recount hay "job N thiếu…")<br/>không parse thì gửi lại y prompt cũ
        M-->>S: _Split lần hai
        alt Vẫn hỏng
            S-->>P: raise SplitFailed → thông báo hệ thống
        end
    end
```

Mỗi job (`SplitJob`) là lời dặn tự đủ cho đúng một câu: `part`, `knowledge`, `formulas`, `approach`.
Người soạn câu không thấy dàn ý và không thấy các câu khác. Thay câu thì luôn là một job. `note` là
lời Kriky kể nó chia thế nào; BE lưu nó trên lượt `plan`, và FE hiện nó trong khối các bước
([Teacher Surface](teacher-surface.md)).

## Graph `authoring`: soạn một câu

Câu hỏi sơ đồ trả lời: *một câu của đề, hay một câu làm lại ở pha 2, được viết và tự kiểm thế nào?*

```mermaid
flowchart LR
    brief["brief<br/>draft_brief (câu của đề)<br/>retry_brief (câu làm lại)"] --> write
    write["write<br/>model, structured GeneratedQuestion<br/>parsed + unmangled"] --> check
    check["check<br/>faults: đúng 1 phương án đúng,<br/>mọi distractor có error_label,<br/>≥ 2 cách giải, stem không trùng banned"]
    check --> again{"_again"}
    again -- "không lời phàn nàn" --> done(["GeneratedQuestion"])
    again -- "còn phàn nàn,<br/>attempts &lt; LLM_MAX_ATTEMPTS" --> write
    again -- "hết lượt thử" --> fail(["ValueError<br/>câu đề: job hỏng<br/>câu làm lại: lùi về kho biến thể"])
```

Lần thử không đọc được thành câu hỏi (`question` rỗng) cũng là một lời phàn nàn: *"sai hình dạng"*,
kèm lỗi giải mã cắt gọn.

- **Lời phàn nàn đi lại vào prompt** (`complaints`). Đó là điều khác giữa thử lại có lý do và gieo
  lại xúc xắc.
- **Đây không phải nơi ADR-18 được thi hành.** BE kiểm lại mọi câu tới tay nó. Phép kiểm ở đây chỉ
  là tự QC để tiết kiệm một vòng đi về; nếu nó lệch với BE thì BE mới là bên được tính.
- `brief` của câu đề lấy từ một job của dàn ý (ADR-38) và không bao giờ chở chữ tài liệu thô.
  `check_drafting_reads_no_document_text` canh điều này.
- `repair.unmangled` trả lại các dấu gạch chéo LaTeX bị bộ giải mã JSON nuốt (`\f` của `\frac`).

### Chuông tiến độ

Câu hỏi sơ đồ trả lời: *vì sao chuông "một câu xong" rung sau job, không rung trong job?*

```mermaid
sequenceDiagram
    participant BE
    participant J as write_draft_question
    participant A as arq
    participant R as Redis

    BE->>J: DraftQuestionRequested (progress_channel, ordinal)
    J->>J: _arm_bell: có progress_channel thì ghi (channel, ordinal) vào ctx
    J->>J: write_question(...)
    J-->>A: kết quả (hay ném lỗi)
    A->>R: finish_job: ghi kết quả vào result store
    A->>J: after_job_end = ring_bell(ctx)
    J->>R: publish draft:‹assessment_id› ← ordinal
    R-->>BE: chuông
    BE->>R: thu hoạch: kết quả đã đọc được
```

Chuông đặt **trước** khi làm việc, nên nó rung trên cả ba đường ra: model viết được, model hỏng, và
máy không có khoá. Chuông chở **số thứ tự, không chở câu hỏi** (ADR-25), vì pub/sub không bền, và
thứ gì nằm trong chuông là thứ có thể mất hẳn. Lỗi khi rung bị nuốt: câu đã nằm trong store rồi.

## Graph `explain`: lượt kèm học sinh

Câu hỏi sơ đồ trả lời: *chữ của trợ lý tới màn hình học sinh thế nào trong lúc model đang viết?*

```mermaid
flowchart LR
    req["ExplainTurnRequested<br/>câu hỏi, đáp án, phương án đã chọn,<br/>error_label, lịch sử"] --> compose["compose<br/>dựng messages"]
    compose --> speak["speak<br/>model.astream"]
    speak -- "mỗi mảnh" --> publish["publish → Redis<br/>aiafa:stream:&lt;uuid&gt;"]
    publish --> said["said += mảnh<br/>(phát trước, ghi sau)"]
    speak -- "nối hết mảnh" --> text(["ExplainTurnCompleted.text"])
```

Hai luật định hình prompt:

- **Trợ lý giải thích, không kết luận.** Không điểm, không *"em đã hiểu rồi"* (ADR-16, ADR-20).
- **Lỗi đã có tên sẵn.** Trợ lý dùng đúng `error_label` người soạn gắn cho distractor (ADR-18).

`publish` đi qua `config.configurable`, không đi trong state, vì nó là một connection đang sống.

## Graph `naming`: đặt tên đoạn chat

```mermaid
flowchart LR
    first["Câu mở đầu của giáo viên"] --> name["name<br/>một lời gọi model"] --> title(["Tên ngắn"])
    title --> be["BE cắt, dọn,<br/>và kiểm _echoes"]
```

Task nhỏ nhất: không đọc lịch sử, không gọi tool. Prompt có một lối ra cho câu không nhờ việc gì, và
các ví dụ là cặp vào–ra, để model không mượn chữ của ví dụ. BE vẫn có một chốt kiểm thật
(`teacher_chat._echoes`), vì prompt chỉ là một lời nhờ.

## Thêm một skill, một luật, một task

**Một skill mới:**
1. Thêm `agent/skills/<ten>.md`, frontmatter `name` (trùng tên file) và `description` tiếng Anh.
2. Viết `description` như một tiêu chí Jev trả lời có/không được, gồm cả lời đáp ngắn tiếp nối việc
   ấy.
3. Không đặt luật an toàn trong thân skill.
4. `services/agent/tests/test_skills.py` đọc mọi skill. Đo việc chọn bằng `tools/skill_bench`, và
   **hỏi người dùng trước khi chạy bench**.

**Một luật sau model:**
1. Đặt nó trong module theo việc: `read_order.py` (thứ tự đọc), `plan_checks.py` (hình dạng plan),
   `outline.py` (dàn ý), `clarify.py` (nút).
2. Gọi nó trong `choose()` ở đúng chỗ của sơ đồ trên.
3. Luật sửa trả một `NextStepCompleted` khác; luật trả lại thì thêm một lớp con của `AskAgain`
   trong `ask_again.py`, có `hint` nói rõ sai ở đâu, và là `Flawed` nếu đề nghị vẫn dùng được.
4. Viết test trong `services/agent/tests/`. Đo trên model thật bằng `tools/propose_bench`, và hỏi
   người dùng trước khi chạy.

**Một task mới:**
1. Hằng số tên task và hai message `…Requested`, `…Completed` trong `packages/contracts`.
2. Handler `async (ctx, payload) -> dict` có cả đường mock và đường model, cùng cách xử khi model
   hỏng.
3. Một graph trong `graphs/`.
4. Đăng ký trong `WorkerSettings.functions` dưới hằng số.
5. Thêm một payload mẫu vào `PAYLOADS` của `test_no_routing_decision.py`. Thiếu thì
   `test_every_registered_task_has_a_payload_here` đỏ; có rồi thì test gọi task và soi kết quả.
   `check_contract.py` (`timeout-order`) so ngân sách thời gian của task với độ kiên nhẫn của BE.

## Bản đồ module

| Module | Việc |
| --- | --- |
| `worker.py` | Cấu hình arq: năm task, queue, `after_job_end`; log model đang dùng; che khoá trong log |
| `handlers.py` | Cửa vào của từng task; đường mock khi `LLM_ENABLED=false`; cách xử khi model hỏng; chuông |
| `config.py` | `Settings` đọc `.env`: provider, model, fallback, số lần thử, Jev |
| `llm.py` | Dựng model, truyền credential, `with_fallback` |
| `skill_router.py`, `skills.py`, `skills/*.md` | Jev chọn skill; đọc skill từ đĩa |
| `redact.py` | Che khoá API trong mọi log, kể cả traceback |
| `latex_escapes.py` | Trả lại dấu gạch chéo LaTeX bị JSON nuốt |
| `graphs/propose/graph.py` | `propose()`: chọn skill, chạy graph, hỏi lại một lần, chia việc |
| `graphs/propose/compose.py`, `prompt.py` | Dựng messages; chữ của `CORE` và các thủ tục |
| `graphs/propose/choose.py` | Gọi model, áp luật sau model theo thứ tự |
| `graphs/propose/proposal.py` | Khuôn `_Proposal` gửi model, và cách nó thành `NextStepCompleted` |
| `graphs/propose/ask_again.py` | Các lớp `AskAgain` và hint của chúng |
| `graphs/propose/read_order.py`, `books.py`, `history.py` | Luật thứ tự đọc; sách trong tầm; đọc lịch sử từ plan gần nhất |
| `graphs/propose/outline.py`, `plan_checks.py`, `clarify.py` | Dàn ý và lời đồng ý; hình dạng plan; nút của câu hỏi lại |
| `graphs/propose/split.py` | Chia dàn ý đã đồng ý thành job (ADR-38) |
| `graphs/authoring/` | Vòng viết, kiểm, thử lại; `brief.py`, `checks.py`, `repair.py` |
| `graphs/explain/` | Lượt kèm học sinh, stream |
| `graphs/naming/` | Đặt tên đoạn chat |
