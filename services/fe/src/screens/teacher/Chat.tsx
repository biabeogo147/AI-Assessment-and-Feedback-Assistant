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
 * Một câu hỏi lại đang chờ trả lời: câu hỏi, cùng các phương án đi với nó.
 *
 * Không dùng lại `Answered` nữa. Thứ đứng trên thẻ hỏi lại là **một bước** của đoạn chat,
 * không phải kết quả của một request — và từ khi các phương án được lưu cùng bước ấy, một
 * lần đọc lại đoạn chat cho ra đúng cùng một thứ như lúc lượt vừa chạy xong.
 */
interface Question {
  text: string;
  choices: string[];
  more_choices: number;
}

/**
 * Câu hỏi lại đang mở, dựng từ một lần đọc đoạn chat.
 *
 * Các phương án lấy thẳng từ `answered.choices` — **không** tự đi tìm trong `turns`. Luật
 * *"chỉ bước cuối còn bày nút"* là của BE (`_read_back`), và chép nó sang đây là bản thứ
 * hai của cùng một luật, tức bản sẽ lệch. FE chỉ còn lấy **câu hỏi** từ bước cuối, vì một
 * lần đọc không phải một lượt nên `answered.text` rỗng.
 *
 * @param answered - Kết quả một lần đọc đoạn chat.
 * @returns Câu hỏi đang chờ, hoặc `null` khi không có phương án nào.
 */
function questionIn(answered: Answered): Question | null {
  if (answered.choices.length === 0) return null;
  const last = answered.turns[answered.turns.length - 1];
  return {
    text: last === undefined ? "" : last.text,
    choices: answered.choices,
    more_choices: answered.more_choices,
  };
}

/**
 * Bề mặt chat của giáo viên: artboard `1 · Bắt đầu` và `2 · Kèm tài liệu`.
 *
 * Một màn hình ở hai trạng thái, không phải hai màn hình. Chưa nói gì thì chỗ của hội thoại
 * là linh vật và ba gợi ý; nói rồi thì chính chỗ đó là dòng lượt nói. Tách làm hai component
 * sẽ phải nhân đôi rail, ô nhập và cả vòng gửi — ba thứ giống hệt nhau ở hai bên.
 *
 * **Không poll.** `Turn` không có id để dedupe, nên cách hợp lệ duy nhất là thay toàn bộ —
 * tức hai nguồn sự thật cho một dòng, và một lần poll giữa lượt sẽ giật màn hình về trạng
 * thái của một khoảnh khắc khác.
 *
 * F5 giữa lượt thì không mất gì đã xảy ra: BE commit từng bước, và nay cả các phương án của
 * một câu hỏi lại cũng nằm trong row của chính bước đã hỏi — nên các nút còn nguyên sau khi
 * tải lại. Trước đợt này chúng chỉ sống trong response, và một lần F5 bỏ giáo viên lại trước
 * một câu hỏi mà không còn câu trả lời nào bày ra.
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
  // cách để không vẽ nó hai lần. Suy ra từ `turns` bằng `questionIn`, không nhận từ một
  // field rời của response: một luật, một chỗ, và hai đường (vừa chạy xong, và vừa F5) cho
  // ra cùng một màn hình.
  const [asked, setAsked] = useState<Question | null>(null);
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
  // Đoạn chat đang chờ xác nhận xoá. Xoá bên BE là xoá mềm, nhưng với người bấm nút thì nó
  // là một việc một chiều — không có nút hoàn tác nào trên màn hình này — nên nó đi qua hộp
  // xác nhận y như việc phát hành.
  const [erasing, setErasing] = useState<TeacherConversation | null>(null);
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
        setAsked(questionIn(answered));
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

    // Tám phút. Không phải một phép tính từ ngân sách BE — **không có** phép tính nào đóng
    // được: BE đợi theo *sự im lặng* (180 giây kể từ tiếng chuông cuối), nên một vòng soạn
    // dài vẫn hợp lệ và không có trần tổng. Con số này là trần của phía client, và nó phải
    // rộng hơn mọi chuỗi kiên nhẫn của BE: client cắt trước thì lượt mất câu kết, trong khi
    // database đã có đủ câu. Hết giờ thì giữ lại chữ đã gõ.
    const stop = new AbortController();
    const cut = window.setTimeout(() => stop.abort(), 480_000);
    const later = window.setTimeout(() => setSlow(true), 20_000);

    let thread = here;
    try {
      // Một trong hai, không bao giờ cả hai: BE trả 422 cho một request tự mâu thuẫn.
      await teacher.stream(
        trimmed,
        here === null ? { startNew: true } : { conversationId: here },
        (event) => {
          // Lượt gãy sau khi header đã gửi đi thì không còn status code nào để nói, nên BE
          // nói bằng một khung `done` mang `ended_as="error"`. Ném ở đây để nó đi đúng
          // đường lỗi có sẵn: chữ đã gõ được trả lại ô nhập, và câu lỗi hiện ra. Bỏ qua nó
          // thì giáo viên thấy ô nhập trống, không một lời nào, và chữ vừa gõ đã mất.
          if (event.kind === "done" && event.ended_as === "error") {
            throw new Error(event.text);
          }
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
      teacher
        .conversations()
        .then(setThreads)
        .catch(() => undefined);

      // Đọc lại cả đoạn thay vì ghép từ các sự kiện. Sự kiện là thứ để **xem trong lúc
      // chạy**; thứ ở lại trên màn hình phải là thứ database đang giữ, nếu không một lần F5
      // sẽ cho ra một màn hình khác với màn hình vừa rồi — và không ai hiểu vì sao.
      const whole = await teacher.conversation(thread ?? undefined);
      setTurns(whole.turns);
      setAsked(questionIn(whole));
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

  /**
   * Đổi tên một đoạn chat.
   *
   * Đổi nhãn trên rail **trước** khi BE trả lời, rồi lùi lại nếu hỏng. Không phải để trông
   * nhanh hơn: `label` của hàng là một prop, nên chờ response xong mới đổi để lại một khe
   * trong đó hàng vẫn mang tên cũ — gõ tên mới, bấm `⋯` (blur lưu), rồi bấm *Đổi tên* ngay
   * thì ô nhập mở ra với tên **cũ**, và một lần Enter nữa ghi đè mất tên vừa đặt.
   *
   * @param conversationId - Đoạn nào.
   * @param title - Tên giáo viên gõ. BE dọn nó, và câu trả lời của BE mới là tên thật.
   */
  async function rename(conversationId: string, title: string) {
    const was = threads.find((one) => one.conversation_id === conversationId);
    // Thay đúng một hàng chứ không tải lại cả rail: BE trả về hàng đã đổi, và một lần tải
    // lại ở đây sẽ sắp xếp lại danh sách ngay dưới ngón tay người vừa bấm.
    const put = (named: string) =>
      setThreads((before) =>
        before.map((one) =>
          one.conversation_id === conversationId
            ? { ...one, title: named }
            : one,
        ),
      );
    put(title);
    try {
      const renamed = await teacher.renameConversation(conversationId, title);
      // Tên thật là tên BE đã dọn, không phải chuỗi vừa gõ.
      put(renamed.title);
      setTrouble(null);
    } catch (cause) {
      if (was !== undefined) put(was.title);
      setTrouble((cause as Error).message);
    }
  }

  /**
   * Xoá một đoạn chat, sau khi giáo viên đã xác nhận.
   *
   * @param conversationId - Đoạn nào.
   */
  async function erase(conversationId: string) {
    try {
      await teacher.deleteConversation(conversationId);
      setThreads((before) =>
        before.filter((one) => one.conversation_id !== conversationId),
      );
      setErasing(null);
      setTrouble(null);
      // Xoá đoạn **đang mở** thì phải rời khỏi nó: đứng lại là đứng trên một màn hình mà
      // mọi lần đọc lại từ nay sẽ ra 404, và câu gõ tiếp theo cũng bị từ chối.
      if (conversationId === here) go("/teacher/moi");
    } catch (cause) {
      setErasing(null);
      setTrouble((cause as Error).message);
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
  // chỉ khi chính nó là câu đó — nay cả sau một lần F5, vì `asked` không còn rỗng ở đó.
  const last = turns[turns.length - 1];
  const folded =
    asked !== null &&
    last !== undefined &&
    last.kind === "assistant" &&
    last.text === asked.text;
  const drawn = folded ? turns.slice(0, -1) : turns;

  return (
    <div className="teacher">
      <Rail
        conversations={threads}
        current={here}
        documents={documents}
        starting={fresh}
        onOpen={(thread) => go(`/teacher/chat/${thread}`)}
        onRename={(thread, title) => void rename(thread, title)}
        onDelete={(thread) =>
          setErasing(
            threads.find((one) => one.conversation_id === thread) ?? null,
          )
        }
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
                  onOpen={(paper) =>
                    go(`/teacher/chat/${here ?? ""}/de/${paper}`)
                  }
                  onPublish={(paper) =>
                    go(`/teacher/chat/${here ?? ""}/de/${paper}/phat-hanh`)
                  }
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
                    {live.opening !== "" && (
                      <div className="reply-text">{live.opening}</div>
                    )}
                    {live.steps.length > 0 && (
                      <Steps
                        steps={live.steps}
                        total={live.total || undefined}
                      />
                    )}
                    {live.report !== "" && (
                      <div className="reply-text">{live.report}</div>
                    )}
                  </div>
                </div>
              </div>
            )}
            {pending !== null && live === null && <Thinking slow={slow} />}
            <div ref={bottom} />
          </div>
        ) : (
          <>
            <img
              className="hero"
              src="/kriky-hero.png"
              alt=""
              width={143}
              height={240}
            />
            <div className="intro">
              <h1>Hôm nay bạn muốn làm gì?</h1>
              <p>
                Nói bằng câu bình thường. Kriky sẽ tạo lớp, soạn đề, thêm câu
                hỏi — nhưng chỉ bạn mới phát hành được đề cho học sinh.
              </p>
            </div>
            <div className="hint">
              Bấm một gợi ý để điền sẵn vào ô nhập, bạn sửa lại trước khi gửi.
            </div>
            <div className="suggestions">
              {OPENERS.map((one) => (
                <button
                  className="suggestion"
                  key={one}
                  type="button"
                  onClick={() => setText(one)}
                >
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

        {/* Dải này **từng** nói "Đổi phạm vi", và chữ ấy hứa một việc không xảy ra: tệp vừa
            tải lên đi vào thư viện của giáo viên và không rời khỏi màn hình này — thân
            request gửi đi đúng ba field `{text, conversation_id, start_new}`, không có
            `document_id` nào, và chưa đoạn code nào mở tệp ra đọc. Nên dải nói đúng việc đã
            xảy ra, và nói thẳng việc chưa xảy ra. Đọc nội dung tài liệu vào đề là một món
            riêng trong `docs/plans/backlog.md`. */}
        {scope !== null && (
          <div className="scope-strip">
            <span className="kind">{scope.kind}</span>
            <span className="what">Đã tải lên: {scope.filename}</span>
            <button type="button" onClick={() => picker.current?.click()}>
              Tải tệp khác
            </button>
          </div>
        )}
        {scope !== null && (
          <div className="scope-note">
            Tệp đã vào thư viện tài liệu của bạn. Nội dung của nó chưa được dùng
            để soạn đề.
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
            placeholder={
              pending === null ? "Nhắn cho Kriky…" : "Đang chờ Kriky trả lời…"
            }
            disabled={pending !== null}
            aria-label="Nhắn cho Kriky"
          />
          <button
            className="send"
            type="submit"
            disabled={text.trim() === "" || pending !== null}
          >
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
          onClose={() =>
            go(here === null ? "/teacher" : `/teacher/chat/${here}`)
          }
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

      {erasing !== null && (
        <div className="veil" role="dialog" aria-modal="true">
          <div className="confirm">
            <h3>Xoá đoạn chat này?</h3>
            <p className="lead">
              “{erasing.title || "Đoạn chat"}” sẽ không còn trên danh sách, và
              bạn sẽ không mở lại được nó. Các đề đã tạo trong đoạn này thì vẫn
              còn nguyên.
            </p>
            <div className="confirm-actions">
              <button
                className="btn"
                type="button"
                onClick={() => setErasing(null)}
              >
                Giữ lại
              </button>
              <button
                className="btn primary"
                type="button"
                onClick={() => void erase(erasing.conversation_id)}
              >
                Xoá đoạn chat
              </button>
            </div>
          </div>
        </div>
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
      const closed = {
        mark: (event.kind === "step_done" ? "done" : "failed") as Step["mark"],
        title: event.title || (last >= 0 ? steps[last].title : "Một bước nữa"),
        result: event.detail === "" ? "" : `— ${event.detail}`,
      };
      // Không có bước nào đang chạy nghĩa là bước này hỏng **trước khi** nó bắt đầu — BE
      // phát `step_failed` không kèm `step_started` khi một tham chiếu không giải được.
      // Bỏ qua nó thì màn hình sống im lặng về đúng cái bước đã làm lượt dừng lại.
      if (last >= 0) steps[last] = closed;
      else steps.push(closed);
      return { ...now, steps };
    }
    case "progress": {
      // Số câu đã soạn là **dòng kết quả của bước đang chạy**, không phải một con số thứ
      // hai trên header: `bước k/n` đếm bước của plan, và trộn hai sự thật vào một con số
      // là sai với cả hai (ADR-25).
      const last = steps.map((one) => one.mark).lastIndexOf("running");
      if (last >= 0) {
        steps[last] = {
          ...steps[last],
          result: `— đã soạn ${event.index}/${event.total} câu`,
        };
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
          {said.opening !== "" && (
            <div className="reply-text">{said.opening}</div>
          )}
          {steps}
          {said.conclusion !== "" && (
            <div className="reply-text">{said.conclusion}</div>
          )}
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
      <img
        className="face"
        src="/kriky-face.png"
        alt=""
        width={40}
        height={40}
      />
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
          {slow
            ? "Vẫn đang xử lý — yêu cầu này cần nhiều bước hơn thường lệ…"
            : "Đang đọc yêu cầu…"}
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
function Clarify({
  asked,
  onPick,
}: {
  asked: Question;
  onPick: (choice: string) => void;
}) {
  return (
    <div className="clarify">
      <h3>{asked.text}</h3>
      {asked.more_choices > 0 && (
        <div className="cut">
          Còn {asked.more_choices} lựa chọn nữa không nằm trong danh sách.
        </div>
      )}
      <div className="choices">
        {asked.choices.map((one) => (
          <button
            className="choice"
            key={one}
            type="button"
            onClick={() => onPick(one)}
          >
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
