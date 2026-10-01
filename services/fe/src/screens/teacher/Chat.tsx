import { useEffect, useRef, useState } from "react";

import { teacher, type Answered, type TeacherDocument, type Turn } from "../../api";
import { OPENERS } from "./invented-not-from-be";
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
 */
export default function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
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
    setTrouble(null);

    // 100 giây: 90 của BE cộng 10 cho đường truyền. Hết giờ thì **giữ lại chữ đã gõ**, vì
    // bắt gõ lại một yêu cầu dài sau một phút rưỡi chờ là hình phạt cho một lỗi của máy.
    const stop = new AbortController();
    const cut = window.setTimeout(() => stop.abort(), 100_000);
    const later = window.setTimeout(() => setSlow(true), 20_000);

    try {
      const answered = await teacher.say(trimmed, stop.signal);
      // Chỉ các bước CỦA LƯỢT NÀY, nên append chứ không thay: `GET /teacher/chat` mới là
      // đường trả về cả hội thoại. `answered.choices` thuộc về câu hỏi lại, và nó được
      // dựng ở bước sau của plan cùng với artboard 3.
      setTurns((before) => [...before, ...answered.turns]);
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

  return (
    <div className="teacher">
      <Rail documents={documents} />
      <main className={`center ${talking ? "talking" : "empty"}`}>
        {talking ? (
          <div className="stream">
            {turns.map((one, index) => (
              <Exchange key={index} turn={one} />
            ))}
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
    </div>
  );
}

/**
 * Một lượt đã lưu.
 *
 * `tool_call` **không** vẽ gì: nó không mang kết quả, và sau khi lượt xong thì nó là tiếng ồn.
 * `tool_result` thành thẻ kết quả, và thẻ đó là việc của bước dựng artboard 6 — tới lúc đó nó
 * in ra một dòng trần, chứ không im lặng: một hành động đã xảy ra mà màn hình không nói gì là
 * đúng thứ ADR-05 ngăn.
 */
function Exchange({ turn }: { turn: Turn }) {
  if (turn.kind === "teacher") {
    return (
      <div className="exchange said">
        <div className="said-bubble">{turn.text}</div>
      </div>
    );
  }
  if (turn.kind === "tool_call") return null;
  if (turn.kind === "tool_result") {
    return (
      <div className="exchange">
        <div className="reply-text">Đã chạy: {turn.tool_name}</div>
      </div>
    );
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
