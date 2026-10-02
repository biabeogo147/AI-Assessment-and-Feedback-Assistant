import { useEffect, useRef, useState } from "react";

import { go } from "../../App";
import {
  teacher,
  type Answered,
  type TeacherConversation,
  type TeacherDocument,
  type Turn,
  type TurnEvent,
} from "../../api";
import ActionCard, { cardTurn, stepFor } from "./ActionCard";
import { OPENERS } from "./invented-not-from-be";
import Panel from "./Panel";
import Rail from "./Rail";
import Steps, { type Step } from "./Steps";

/**
 * Bề mặt chat của giáo viên: artboard `1 · Bắt đầu` và `2 · Kèm tài liệu`.
 *
 * Một màn hình ở hai trạng thái, không phải hai màn hình. Chưa nói gì thì chỗ của hội thoại
 * là linh vật và ba gợi ý; nói rồi thì chính chỗ đó là dòng lượt nói. Tách làm hai component
 * sẽ phải nhân đôi rail, ô nhập và cả vòng gửi — ba thứ giống hệt nhau ở hai bên.
 *
 * **Không poll.** `GET /teacher/chat` trả cả hội thoại nhưng **không** trả `choices`, nên một
 * lần poll giữa lượt sẽ xoá sạch các nút của câu hỏi lại đang hiện. Và `Turn` không có id để
 * dedupe, nên cách hợp lệ duy nhất là thay toàn bộ — tức hai nguồn sự thật cho một dòng.
 *
 * F5 giữa lượt thì không mất gì đã xảy ra: BE commit từng bước. `choices` thì mất, nhưng
 * `choices` là chuỗi đã format sẵn và bấm một nút nghĩa là gửi lại đúng chuỗi đó — gõ tay vẫn
 * trả lời được, nên không ai bị kẹt.
 *
 * @param conversationId - Đoạn chat đang mở, hoặc `null` cho *đoạn đang chạy*. Cũng tới từ
 *   route, cùng một lý do.
 * @param fresh - Màn hình đang ở trạng thái *chưa có đoạn nào*, sau khi bấm **Đoạn chat mới**.
 *   Nó là một route (`#/teacher/moi`) chứ không phải một state cục bộ, và lý do đo được: bấm
 *   nút ấy khi đang đứng ở `#/teacher` không đổi hash, nên không có gì xảy ra — câu gõ tiếp
 *   theo rơi vào đoạn cũ mà màn hình không hề báo.
 * @param openPaper - Đề đang mở trong panel bên phải, hoặc `null`. Nó tới từ **route**, không
 *   từ một cú bấm: nhờ vậy một lần F5 khi panel đang mở dựng lại đúng màn hình đó, và nút back
 *   đóng panel lại thay vì rời khỏi cả đoạn chat.
 */
export default function Chat({
  conversationId,
  fresh,
  openPaper,
  publishing,
}: {
  conversationId: string | null;
  fresh: boolean;
  openPaper: string | null;
  publishing: boolean;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  // Lượt đang chạy, dựng từ các sự kiện SSE. Nó **không** phải nguồn của màn hình sau khi
  // lượt xong: lúc đó cả đoạn được đọc lại từ database.
  const [live, setLive] = useState<Live | null>(null);
  // Câu hỏi lại đang chờ trả lời. Nó giữ **cả** câu hỏi lẫn các phương án, vì hai thứ đó
  // nằm trên cùng một thẻ — và vì câu hỏi ấy cũng nằm trong `turns`, nên giữ nó ở đây là
  // cách để không vẽ nó hai lần.
  const [asked, setAsked] = useState<Answered | null>(null);
  const [documents, setDocuments] = useState<TeacherDocument[]>([]);
  const [threads, setThreads] = useState<TeacherConversation[]>([]);
  // Đoạn chat đang mở, kể cả khi route chưa biết tên nó: bấm *Đoạn chat mới* rồi gửi câu
  // đầu thì id chỉ có sau khi BE trả lời.
  const [here, setHere] = useState<string | null>(conversationId);
  // Đoạn chat đã **tải xong**, khác với đoạn đang hiện trên route. Phải là một ref riêng
  // chứ không phải `here`: lúc mount sạch ở `#/teacher/chat/X` thì `here` đã bằng `X` từ
  // giá trị khởi tạo, nên so với nó là so một con số với chính nó — và effect bỏ qua lần
  // chạy duy nhất có ích. Một lần F5 khi đó cho ra màn mở đầu kèm rail tô sáng đúng đoạn
  // chat ấy: hai thứ nói hai chuyện trái ngược, không lỗi console nào.
  const loaded = useRef<string | null>(null);
  const [scope, setScope] = useState<TeacherDocument | null>(null);
  const [text, setText] = useState("");
  // Bong bóng **tạm** của câu vừa gửi. Nó không nằm trong `turns`, nên lúc lượt thật về tới
  // thì nó biến mất đúng vào khoảnh khắc bong bóng thật xuất hiện — không có khả năng nhân
  // đôi, vì cái tạm chưa bao giờ được append.
  const [pending, setPending] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const [trouble, setTrouble] = useState<string | null>(null);

  const picker = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);

  // Đổi route thì đổi hội thoại. `live` cắt một câu trả lời về muộn của đoạn chat vừa rời
  // đi: không có nó, bấm nhanh qua hai đoạn sẽ vẽ lịch sử của đoạn đầu lên đoạn sau.
  useEffect(() => {
    let live = true;
    // Route vừa gọi tên đúng đoạn **đã tải** — chuyện xảy ra ngay sau câu đầu của một đoạn
    // mới. Không tải lại: dữ liệu đã nằm sẵn trên màn hình, và một lần tải nữa chỉ làm nó
    // nháy rỗng rồi hiện lại y như cũ.
    if (conversationId !== null && conversationId === loaded.current) return;
    setHere(conversationId);
    setTurns([]);
    setAsked(null);
    // Màn hình vừa bị xoá trắng, nên **không còn** đoạn nào đã tải. Thiếu dòng này thì
    // `loaded` nói dối ngay ở một đường đi thường ngày: đang đọc đoạn X, bấm *Đoạn chat
    // mới* (turns bị xoá, `loaded` vẫn là X), rồi bấm lại chính X trong lịch sử — guard
    // trên thấy hai giá trị bằng nhau, kết luận "đã có sẵn trên màn hình" và trả về sớm,
    // để lại một màn trắng. Chọn một đoạn khác thì lại chạy, nên lỗi trông như ngẫu nhiên.
    loaded.current = null;
    if (fresh) return;
    teacher
      .conversation(conversationId ?? undefined)
      .then((answered: Answered) => {
        if (!live) return;
        setTurns(answered.turns);
        loaded.current = answered.conversation_id || conversationId;
        if (answered.conversation_id) setHere(answered.conversation_id);
      })
      .catch((cause: Error) => live && setTrouble(cause.message));
    return () => {
      live = false;
    };
  }, [conversationId, fresh]);

  useEffect(() => {
    teacher
      .documents()
      .then(setDocuments)
      .catch((cause: Error) => setTrouble(cause.message));
    teacher
      .conversations()
      .then(setThreads)
      .catch((cause: Error) => setTrouble(cause.message));
  }, []);

  // Lượt mới đẩy dòng xuống đáy. Chỉ khi có lượt mới, không phải ở mọi render: cuộn lên đọc
  // lại một câu cũ mà bị giật xuống đáy là cách chắc chắn nhất để không ai đọc lại được gì.
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [turns.length, pending]);

  async function send(said: string) {
    const trimmed = said.trim();
    if (trimmed === "" || pending !== null) return;

    setPending(trimmed);
    setText("");
    setAsked(null);
    setTrouble(null);
    setLive(null);

    // Bốn phút: pha 1 của BE là 90 giây, rồi lượt còn **đợi các câu hỏi về** trước khi kể
    // lại (ADR-25), và mười câu mất hàng phút. Hết giờ thì giữ lại chữ đã gõ — bắt gõ lại
    // một yêu cầu dài là hình phạt cho một lỗi của máy.
    const stop = new AbortController();
    const cut = window.setTimeout(() => stop.abort(), 240_000);
    const later = window.setTimeout(() => setSlow(true), 20_000);

    let thread = here;
    try {
      // Một trong hai, không bao giờ cả hai: BE trả 422 cho một request tự mâu thuẫn.
      await teacher.stream(
        trimmed,
        here === null ? { startNew: true } : { conversationId: here },
        (event) => {
          if (event.conversation_id) thread = event.conversation_id;
          // Từ sự kiện đầu tiên là đã có thứ để xem, nên vòng quay chờ nhường chỗ cho
          // việc thật: `setSlow(false)` ở đây chứ không đợi tới lúc lượt xong.
          setSlow(false);
          setLive((before) => grow(before, event));
        },
        stop.signal,
      );

      setHere(thread);
      // Lượt vừa chạy **là** nội dung của đoạn ấy, nên đánh dấu đã tải: route sắp đổi sang
      // tên nó, và effect phải bỏ qua lần đổi đó thay vì nháy rỗng rồi tải lại.
      loaded.current = thread;
      if (here === null && thread !== null) go(`/teacher/chat/${thread}`);
      // Lượt đầu của một đoạn mới vừa đặt tên cho nó, nên rail phải đọc lại.
      teacher.conversations().then(setThreads).catch(() => undefined);

      // Đọc lại cả đoạn thay vì ghép từ các sự kiện. Sự kiện là thứ để **xem trong lúc
      // chạy**; thứ ở lại trên màn hình phải là thứ database đang giữ, nếu không một lần F5
      // sẽ cho ra một màn hình khác với màn hình vừa rồi — và không ai hiểu vì sao.
      const whole = await teacher.conversation(thread ?? undefined);
      setTurns(whole.turns);
      setAsked(whole.choices.length > 0 ? whole : null);
    } catch (cause) {
      setText(trimmed);
      setTrouble(
        stop.signal.aborted
          ? "Kriky chưa trả lời kịp. Chữ bạn gõ vẫn còn ở ô nhập."
          : (cause as Error).message,
      );
    } finally {
      window.clearTimeout(cut);
      window.clearTimeout(later);
      setSlow(false);
      setPending(null);
      setLive(null);
    }
  }

  async function take(file: File) {
    try {
      const saved = await teacher.upload(file);
      setDocuments((before) => [saved, ...before]);
      setScope(saved);
      setTrouble(null);
    } catch (cause) {
      setTrouble((cause as Error).message);
    }
  }

  const talking = turns.length > 0 || pending !== null;

  // Câu hỏi lại đã nằm trong `turns` dưới dạng một lượt của trợ lý, và nó cũng là tiêu đề
  // của thẻ. Vẽ cả hai thì cùng một câu hiện hai lần cách nhau 12px. Bỏ **lượt cuối**, và
  // chỉ khi chính nó là câu đó: sau một lần F5 thì `asked` rỗng, câu hỏi quay về làm một
  // bong bóng bình thường, và đó vẫn là một màn hình đúng.
  const last = turns[turns.length - 1];
  const folded =
    asked !== null && last !== undefined && last.kind === "assistant" && last.text === asked.text;
  const drawn = folded ? turns.slice(0, -1) : turns;

  return (
    <div className="teacher">
      <Rail
        conversations={threads}
        current={here}
        documents={documents}
        starting={fresh}
        onOpen={(thread) => go(`/teacher/chat/${thread}`)}
        onNew={() => go("/teacher/moi")}
      />
      <main
        className={`center ${talking ? "talking" : "empty"} ${openPaper !== null ? "with-panel" : ""}`}
      >
        {talking ? (
          <div className="stream">
            {blocks(drawn).map((block, index) =>
              "said" in block ? (
                <div className="exchange said" key={index}>
                  <div className="said-bubble">{block.said}</div>
                </div>
              ) : (
                <Turnful
                  key={index}
                  said={spoken(block.kriky)}
                  onOpen={(paper) => go(`/teacher/chat/${here ?? ""}/de/${paper}`)}
                  onPublish={(paper) => go(`/teacher/chat/${here ?? ""}/de/${paper}/phat-hanh`)}
                  onCompose={setText}
                />
              ),
            )}
            {asked !== null && pending === null && (
              <Clarify asked={asked} onPick={(one) => void send(one)} />
            )}
            {pending !== null && (
              <div className="exchange said">
                <div className="said-bubble">{pending}</div>
              </div>
            )}
            {/* Lượt đang chạy. Hình dạng y hệt một lượt đã xong — avatar một lần, rồi câu
                mở, khối bước, câu kết — nên không có cú nhảy nào lúc nó chuyển thành lượt
                đã lưu. Chỉ khi chưa có sự kiện nào thì mới là vòng quay chờ. */}
            {pending !== null && live !== null && (
              <div className="exchange">
                <div className="voice">
                  <Who />
                  <div className="turn-body">
                    {live.opening !== "" && <div className="reply-text">{live.opening}</div>}
                    {live.steps.length > 0 && (
                      <Steps steps={live.steps} total={live.total || undefined} />
                    )}
                    {live.report !== "" && <div className="reply-text">{live.report}</div>}
                  </div>
                </div>
              </div>
            )}
            {pending !== null && live === null && <Thinking slow={slow} />}
            <div ref={bottom} />
          </div>
        ) : (
          <>
            <img className="hero" src="/kriky-hero.png" alt="" width={143} height={240} />
            <div className="intro">
              <h1>Hôm nay bạn muốn làm gì?</h1>
              <p>
                Nói bằng câu bình thường. Kriky sẽ tạo lớp, soạn đề, thêm câu hỏi — nhưng chỉ bạn
                mới phát hành được đề cho học sinh.
              </p>
            </div>
            <div className="hint">
              Bấm một gợi ý để điền sẵn vào ô nhập, bạn sửa lại trước khi gửi.
            </div>
            <div className="suggestions">
              {OPENERS.map((one) => (
                <button className="suggestion" key={one} type="button" onClick={() => setText(one)}>
                  {one}
                </button>
              ))}
            </div>
          </>
        )}

        {trouble !== null && (
          <div className="trouble" role="alert">
            {trouble}
          </div>
        )}

        {scope !== null && (
          <div className="scope-strip">
            <span className="kind">{scope.kind}</span>
            <span className="what">{scope.filename}</span>
            <button type="button" onClick={() => picker.current?.click()}>
              Đổi phạm vi
            </button>
          </div>
        )}

        <form
          className="composer-bar"
          onSubmit={(event) => {
            event.preventDefault();
            void send(text);
          }}
        >
          <button
            className="attach"
            type="button"
            disabled={pending !== null}
            onClick={() => picker.current?.click()}
          >
            ＋ Tài liệu
          </button>
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={pending === null ? "Nhắn cho Kriky…" : "Đang chờ Kriky trả lời…"}
            disabled={pending !== null}
            aria-label="Nhắn cho Kriky"
          />
          <button className="send" type="submit" disabled={text.trim() === "" || pending !== null}>
            {pending === null ? "Gửi" : "Đang gửi…"}
          </button>
        </form>

        {/* Ô chọn file thật, ẩn đi: nút "＋ Tài liệu" của thiết kế không phải một input. */}
        <input
          ref={picker}
          type="file"
          hidden
          accept=".pdf,.docx,.doc,.txt,.md"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void take(file);
          }}
        />
      </main>

      {openPaper !== null && (
        <Panel
          assessmentId={openPaper}
          publishing={publishing}
          onClose={() => go(here === null ? "/teacher" : `/teacher/chat/${here}`)}
          onApproved={() => {
            // `approve` ghi một bước vào hội thoại (ADR-01 đòi thế với bỏ duyệt, và duyệt đi
            // cùng cặp), nên dòng lượt nói phải đọc lại — nếu không, thẻ kết quả của chính
            // hành động vừa rồi chỉ xuất hiện sau một lần F5.
            teacher
              .conversation()
              .then((answered: Answered) => setTurns(answered.turns))
              .catch((cause: Error) => setTrouble(cause.message));
          }}
        />
      )}
    </div>
  );
}

/** Một bong bóng của giáo viên, hoặc **cả** một lượt của Kriky. */
type Block = { said: string } | { kriky: Turn[] };

/** Một lượt của Kriky, đã tách thành bốn khối của artboard `5 · Đã có đề nháp`. */
interface Spoken {
  /** Câu Kriky nói trước khi bắt tay làm. Rỗng thì không có khối nào. */
  opening: string;
  /** Các bước tool, vào khối `Thinking`. */
  steps: Step[];
  /** Câu kết sau khi làm xong. */
  conclusion: string;
  /** Lượt được lên thẻ, hoặc `null`. **Tối đa một thẻ cho một lượt.** */
  card: Turn | null;
}

/**
 * Tách một lượt của Kriky thành bốn khối, theo đúng thứ tự của artboard `5 · Đã có đề nháp`:
 * câu mở đầu → khối các bước → câu kết → **một** thẻ kết quả.
 *
 * Trước đây mỗi `tool_result` thành một thẻ ngang hàng, nên một lượt năm bước cho ra năm thẻ
 * và hàng avatar rơi xuống dưới chúng. Thiết kế nói điều ngược lại: các bước là **bằng chứng**
 * nằm trong một khối thu gọn được, còn thẻ là **kết quả** và một lượt chỉ có một kết quả.
 *
 * @param turns - Các lượt không phải của giáo viên, theo thứ tự đã xảy ra.
 */
function spoken(turns: Turn[]): Spoken {
  const steps: Step[] = [];
  let opening = "";
  let conclusion = "";
  for (const one of turns) {
    if (one.kind === "tool_result") {
      steps.push(stepFor(one));
      continue;
    }
    if (one.kind !== "assistant") continue;
    // Câu nói trước bước đầu tiên là lời mở; mọi câu sau đó là câu kết, và câu cuối thắng.
    if (steps.length === 0 && opening === "") opening = one.text;
    else conclusion = one.text;
  }
  if (conclusion === "" && steps.length === 0) {
    conclusion = opening;
    opening = "";
  }
  return { opening, steps, conclusion, card: cardTurn(turns) };
}

/**
 * Gộp các lượt liên tiếp của Kriky thành **một** khối, và xếp trong khối theo thiết kế.
 *
 * Một lượt của Kriky là nhiều dòng trong `turns`: các bước tool trước, câu trả lời sau. Vẽ
 * mỗi dòng thành một khối ngang hàng thì hàng avatar — thứ chỉ gắn vào câu trả lời — rơi
 * xuống **dưới** các thẻ kết quả, và màn hình đọc ra như Kriky nói sau khi đã làm xong,
 * không ai biết các thẻ kia của ai. Avatar mở đầu khối là cách nói *"từ đây là Kriky"*, và
 * nó phải nói điều đó **trước** thứ nó giới thiệu.
 *
 * Việc xếp bên trong một khối là việc của `spoken`: các bước vào khối `Thinking`, câu kết
 * và **một** thẻ đi sau nó — đúng `thread` của artboard `5 · Đã có đề nháp` (`12:46`).
 *
 * `tool_call` không vẽ gì: nó không mang kết quả, và sau khi lượt xong thì nó là tiếng ồn.
 * Nó cũng không mở một khối — một lượt chỉ có `tool_call` sẽ là một avatar giới thiệu một
 * khoảng trống.
 */
function blocks(turns: Turn[]): Block[] {
  const out: Block[] = [];
  for (const one of turns) {
    if (one.kind === "teacher") {
      out.push({ said: one.text });
      continue;
    }
    if (one.kind === "tool_call") continue;
    const open = out[out.length - 1];
    if (open !== undefined && "kriky" in open) open.kriky.push(one);
    else out.push({ kriky: [one] });
  }
  return out;
}

/** Một lượt **đang chạy**, dựng dần từ các sự kiện SSE. */
interface Live {
  /** Câu Kriky nói trước khi bắt tay, nếu có. */
  opening: string;
  /** Các bước đã bắt đầu, theo thứ tự. */
  steps: Step[];
  /** Plan có bao nhiêu bước — `n` của `bước k/n`, biết được vì plan có trước khi chạy. */
  total: number;
  /** Câu kết, có từ lúc model kể lại. */
  report: string;
}

/**
 * Một sự kiện nữa vừa tới: dựng lại lượt đang chạy.
 *
 * Thuần tuý, và trả về một object mới mỗi lần — React so sánh theo tham chiếu, nên sửa tại
 * chỗ là cách chắc chắn nhất để màn hình đứng im trong khi state đã đổi.
 *
 * Màn hình vẽ **theo đúng thứ tự nhận được** (ADR-25): không có khuôn cố định nào, model
 * quyết nói lúc nào và tra lúc nào.
 *
 * @param before - Lượt đang dựng, hoặc null khi đây là sự kiện đầu.
 * @param event - Việc vừa xảy ra.
 * @returns Lượt sau khi đã nhận sự kiện ấy.
 */
export function grow(before: Live | null, event: TurnEvent): Live {
  const now: Live = before ?? { opening: "", steps: [], total: 0, report: "" };
  const steps = [...now.steps];

  switch (event.kind) {
    case "say":
      return { ...now, opening: event.text };
    case "plan":
      return { ...now, total: event.total };
    case "step_started":
      steps.push({ mark: "running", title: event.title, result: "" });
      return { ...now, steps, total: now.total || event.total };
    case "step_done":
    case "step_failed": {
      // Bước đang chạy là bước vừa xong — tìm từ cuối, vì các bước chạy tuần tự và một
      // tiêu đề có thể lặp lại giữa hai lượt.
      const last = steps.map((one) => one.mark).lastIndexOf("running");
      if (last >= 0) {
        steps[last] = {
          mark: event.kind === "step_done" ? "done" : "failed",
          title: event.title || steps[last].title,
          result: event.detail === "" ? "" : `— ${event.detail}`,
        };
      }
      return { ...now, steps };
    }
    case "progress": {
      // Số câu đã soạn là **dòng kết quả của bước đang chạy**, không phải một con số thứ
      // hai trên header: `bước k/n` đếm bước của plan, và trộn hai sự thật vào một con số
      // là sai với cả hai (ADR-25).
      const last = steps.map((one) => one.mark).lastIndexOf("running");
      if (last >= 0) {
        steps[last] = { ...steps[last], result: `— đã soạn ${event.index}/${event.total} câu` };
      }
      return { ...now, steps };
    }
    case "report":
      return { ...now, report: event.text };
    case "clarify":
      return { ...now, report: event.text };
    default:
      return now;
  }
}

/**
 * Một lượt của Kriky trên dòng hội thoại.
 *
 * **Một lượt, một avatar, ở trên cùng.** Nó nói *"từ đây là Kriky"* một lần, rồi mọi thứ
 * thuộc về lượt ấy — câu mở, khối bước, câu kết, thẻ — nằm dưới nó. Bản trước dựng avatar
 * lần thứ hai cho câu kết (artboard 5 vẽ vậy), và trên một hội thoại thật thì cùng một
 * người nói được giới thiệu hai lần trong một lượt: ồn, và sai về nghĩa — hàng avatar là
 * ranh giới giữa hai người nói, không phải một dấu trang trí cho mỗi đoạn văn.
 *
 * @param said - Lượt đã tách thành bốn khối.
 * @param onOpen - Mở panel của một đề.
 * @param onPublish - Mở biểu mẫu phát hành.
 * @param onCompose - Điền sẵn một câu vào ô nhập.
 */
function Turnful({
  said,
  onOpen,
  onPublish,
  onCompose,
}: {
  said: Spoken;
  onOpen: (assessmentId: string) => void;
  onPublish: (assessmentId: string) => void;
  onCompose: (text: string) => void;
}) {
  const steps = said.steps.length > 0 ? <Steps steps={said.steps} /> : null;

  // Một khối duy nhất dưới avatar, nhịp 20 giữa các phần — nhịp 6 chỉ nằm giữa avatar và
  // phần đầu tiên. Nhờ vậy thứ tự đọc của thiết kế giữ nguyên dù lượt thiếu phần nào:
  // câu mở → khối bước → câu kết → thẻ.
  return (
    <div className="exchange">
      <div className="voice">
        <Who />
        <div className="turn-body">
          {said.opening !== "" && <div className="reply-text">{said.opening}</div>}
          {steps}
          {said.conclusion !== "" && <div className="reply-text">{said.conclusion}</div>}
          {said.card !== null && (
            <ActionCard
              turn={said.card}
              onOpen={onOpen}
              onPublish={onPublish}
              onCompose={onCompose}
            />
          )}
        </div>
      </div>
    </div>
  );
}

/** Hàng avatar và tên, dùng chung giữa lượt trả lời và lúc đang nghĩ. */
function Who() {
  return (
    <div className="who">
      <img className="face" src="/kriky-face.png" alt="" width={40} height={40} />
      <span className="who-name">Kriky</span>
    </div>
  );
}

/**
 * Kriky đang nghĩ.
 *
 * Hai variant, và thứ khác nhau giữa chúng là **một lời hứa**, không phải một hiệu ứng: sau
 * 20 giây câu chữ đổi sang "vẫn đang xử lý", vì một dòng chữ đứng im quá lâu đọc ra như một
 * cái treo máy, và lúc đó người ta bấm F5 giữa một lượt đang chạy.
 */
function Thinking({ slow }: { slow: boolean }) {
  return (
    <div className={`thinking ${slow ? "slow" : ""}`}>
      <Who />
      <div className="status-row">
        <span className="dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span className="status">
          {slow ? "Vẫn đang xử lý — yêu cầu này cần nhiều bước hơn thường lệ…" : "Đang đọc yêu cầu…"}
        </span>
      </div>
      <div className="shimmer" aria-hidden="true">
        <i />
      </div>
    </div>
  );
}

/**
 * Thẻ câu hỏi lại.
 *
 * Mỗi phương án là **một chuỗi do BE viết**, và bấm vào nghĩa là gửi lại đúng chuỗi đó như
 * một câu của giáo viên. Không có id nào đi kèm, và đó là chủ ý của ADR-23: model viết câu
 * hỏi, BE viết các câu trả lời, nên không còn văn bản tự do nào để ai đó phải đi soi.
 *
 * @param asked - Câu hỏi và các phương án của nó.
 * @param onPick - Được gọi với đúng chuỗi của phương án vừa bấm.
 */
function Clarify({ asked, onPick }: { asked: Answered; onPick: (choice: string) => void }) {
  return (
    <div className="clarify">
      <h3>{asked.text}</h3>
      {asked.more_choices > 0 && (
        <div className="cut">Còn {asked.more_choices} lựa chọn nữa không nằm trong danh sách.</div>
      )}
      <div className="choices">
        {asked.choices.map((one) => (
          <button className="choice" key={one} type="button" onClick={() => onPick(one)}>
            {one}
          </button>
        ))}
      </div>
      <div className="fallback">
        Không lựa chọn nào đúng ý? Trả lời bằng câu của bạn ở ô nhập bên dưới.
      </div>
    </div>
  );
}
