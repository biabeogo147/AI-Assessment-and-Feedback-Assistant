import { useEffect, useRef, useState } from "react";

import { go } from "../../App";
import { teacher, type Answered, type TeacherDocument, type Turn } from "../../api";
import ActionCard from "./ActionCard";
import { OPENERS } from "./invented-not-from-be";
import Panel from "./Panel";
import Rail from "./Rail";

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
 * @param openPaper - Đề đang mở trong panel bên phải, hoặc `null`. Nó tới từ **route**, không
 *   từ một cú bấm: nhờ vậy một lần F5 khi panel đang mở dựng lại đúng màn hình đó, và nút back
 *   đóng panel lại thay vì rời khỏi cả đoạn chat.
 */
export default function Chat({ openPaper }: { openPaper: string | null }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  // Câu hỏi lại đang chờ trả lời. Nó giữ **cả** câu hỏi lẫn các phương án, vì hai thứ đó
  // nằm trên cùng một thẻ — và vì câu hỏi ấy cũng nằm trong `turns`, nên giữ nó ở đây là
  // cách để không vẽ nó hai lần.
  const [asked, setAsked] = useState<Answered | null>(null);
  const [documents, setDocuments] = useState<TeacherDocument[]>([]);
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

  useEffect(() => {
    teacher
      .conversation()
      .then((answered: Answered) => setTurns(answered.turns))
      .catch((cause: Error) => setTrouble(cause.message));
    teacher
      .documents()
      .then(setDocuments)
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

    // 100 giây: 90 của BE cộng 10 cho đường truyền. Hết giờ thì **giữ lại chữ đã gõ**, vì
    // bắt gõ lại một yêu cầu dài sau một phút rưỡi chờ là hình phạt cho một lỗi của máy.
    const stop = new AbortController();
    const cut = window.setTimeout(() => stop.abort(), 100_000);
    const later = window.setTimeout(() => setSlow(true), 20_000);

    try {
      const answered = await teacher.say(trimmed, stop.signal);
      // Chỉ các bước CỦA LƯỢT NÀY, nên append chứ không thay: `GET /teacher/chat` mới là
      // đường trả về cả hội thoại.
      setTurns((before) => [...before, ...answered.turns]);
      setAsked(answered.choices.length > 0 ? answered : null);
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
      <Rail documents={documents} />
      <main
        className={`center ${talking ? "talking" : "empty"} ${openPaper !== null ? "with-panel" : ""}`}
      >
        {talking ? (
          <div className="stream">
            {drawn.map((one, index) => (
              <Exchange
                key={index}
                turn={one}
                onOpen={(paper) => go(`/teacher/de/${paper}`)}
                onPublish={(paper) => go(`/teacher/de/${paper}/phat-hanh`)}
              />
            ))}
            {asked !== null && pending === null && (
              <Clarify asked={asked} onPick={(one) => void send(one)} />
            )}
            {pending !== null && (
              <div className="exchange said">
                <div className="said-bubble">{pending}</div>
              </div>
            )}
            {pending !== null && <Thinking slow={slow} />}
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
          <button className="attach" type="button" onClick={() => picker.current?.click()}>
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
          onClose={() => go("/teacher")}
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

/**
 * Một lượt đã lưu.
 *
 * `tool_call` **không** vẽ gì: nó không mang kết quả, và sau khi lượt xong thì nó là tiếng ồn.
 * `tool_result` thì thành một thẻ kết quả — một hành động đã xảy ra mà màn hình không nói gì
 * là đúng thứ ADR-05 ngăn.
 */
function Exchange({
  turn,
  onOpen,
  onPublish,
}: {
  turn: Turn;
  onOpen: (assessmentId: string) => void;
  onPublish: (assessmentId: string) => void;
}) {
  if (turn.kind === "teacher") {
    return (
      <div className="exchange said">
        <div className="said-bubble">{turn.text}</div>
      </div>
    );
  }
  if (turn.kind === "tool_call") return null;
  if (turn.kind === "tool_result") {
    return <ActionCard turn={turn} onOpen={onOpen} onPublish={onPublish} />;
  }
  return (
    <div className="exchange">
      <Who />
      <div className="reply-text">{turn.text}</div>
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
