import { useState } from "react";

import type { ClarifyQuestion } from "../../api";
import KrikyText from "../../KrikyText";

/**
 * Câu trả lời gộp của một lượt hỏi nhiều câu (ADR-32): *"Khối: Khối 7 · Số câu: 5 câu"*.
 *
 * Nhãn đi kèm từng câu trả lời để model không phải đoán câu trả lời nào của câu hỏi nào, và giáo
 * viên đọc lại bong bóng của mình hiểu ngay.
 *
 * @param questions - Các câu, theo thứ tự hỏi.
 * @param answers - Câu trả lời của từng câu, cùng thứ tự.
 * @returns Một câu để gửi đi như lời giáo viên.
 */
export function merged(questions: ClarifyQuestion[], answers: string[]): string {
  return questions.map((one, at) => `${one.label}: ${answers[at]}`).join(" · ");
}

/**
 * Thẻ hỏi lại nhiều câu (ADR-32) — variant `nhiều câu — câu k/n` (`629:20`) và `nhiều câu — tóm
 * tắt` (`629:46`) của `Clarify request`.
 *
 * Từng câu một, có `Câu k/n`, *Câu trước* và *Câu sau*. **Không bỏ câu**: chưa trả lời câu đang
 * xem thì không sang câu sau. Trả lời đủ thì có màn tóm tắt, sửa lại được từng câu, rồi mới gửi —
 * **một** tin gộp, vì mỗi lần gửi là một lượt gọi model. Lựa chọn chưa gửi chỉ sống ở đây: F5 thì
 * thẻ hiện lại từ câu đầu.
 *
 * @param lead - Lời mở của Kriky, Markdown.
 * @param questions - Hai tới ba câu, mỗi câu nút của riêng nó.
 * @param other - Chữ của lối tự ghi (`Khác`).
 * @param kept - Các câu trả lời của một lần gửi vừa hỏng: thẻ mở lại ở màn tóm tắt với chúng,
 *   không bắt chọn lại từ đầu.
 * @param onSend - Gửi câu trả lời gộp, kèm từng câu trả lời.
 */
export default function ClarifySteps({
  lead,
  questions,
  other,
  kept,
  onSend,
}: {
  lead: string;
  questions: ClarifyQuestion[];
  other: string;
  kept?: string[] | null;
  onSend: (said: string, answers: string[]) => void;
}) {
  const total = questions.length;
  const restored = kept != null && kept.length === total && kept.every((one) => one !== "");
  // Câu đang xem; `total` là màn tóm tắt.
  const [at, setAt] = useState(restored ? total : 0);
  const [answers, setAnswers] = useState<string[]>(() =>
    restored ? [...kept] : questions.map(() => ""),
  );
  const [writing, setWriting] = useState(false);
  const [draft, setDraft] = useState("");

  function show(next: number) {
    setAt(next);
    setWriting(false);
    setDraft("");
  }

  function answer(said: string) {
    setAnswers((before) => before.map((one, index) => (index === at ? said : one)));
    setWriting(false);
    setDraft("");
  }

  if (at === total) {
    return (
      <div className="clarify several">
        <h3>Kiểm tra lại trước khi gửi</h3>
        <div className="answers">
          {questions.map((one, index) => (
            <button
              className="answer"
              key={index}
              type="button"
              onClick={() => show(index)}
            >
              <span className="what">
                <span className="label">{one.label}</span>
                <span className="value">{answers[index]}</span>
              </span>
              <span className="edit">Sửa</span>
            </button>
          ))}
        </div>
        <div className="pager">
          <button type="button" onClick={() => show(total - 1)}>
            ‹ Câu trước
          </button>
          <button
            className="send-all"
            type="button"
            onClick={() => onSend(merged(questions, answers), answers)}
          >
            Gửi
          </button>
        </div>
      </div>
    );
  }

  const asked = questions[at];
  const chosen = answers[at];
  // Câu trả lời tự ghi qua `Khác…` không nằm trong các nút: hàng `Khác…` mang nó, đánh dấu đã chọn.
  const written = chosen !== "" && !asked.choices.includes(chosen);
  const said = draft.trim();
  return (
    <div className="clarify several">
      {/* Model có thể để mọi chữ trong các câu: không lời mở thì không tiêu đề rỗng. */}
      {lead.trim() !== "" && (
        <h3>
          <KrikyText inline>{lead}</KrikyText>
        </h3>
      )}
      <span className="step-of">
        Câu {at + 1}/{total} · {asked.label}
      </span>
      <p className="question">
        <KrikyText inline>{asked.text}</KrikyText>
      </p>
      <div className="choices">
        {asked.choices.map((one) => (
          <button
            className={one === chosen ? "choice picked" : "choice"}
            key={one}
            type="button"
            aria-pressed={one === chosen}
            onClick={() => answer(one)}
          >
            {one}
          </button>
        ))}
        {writing ? (
          <form
            className="other-field"
            onSubmit={(event) => {
              event.preventDefault();
              if (said !== "") answer(said);
            }}
          >
            <input
              autoFocus
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setWriting(false);
                  setDraft("");
                }
              }}
              placeholder="Ghi rõ lựa chọn khác…"
              aria-label="Lựa chọn khác"
            />
            <button className="send" type="submit" disabled={said === ""}>
              Chọn
            </button>
          </form>
        ) : (
          <button
            className={written ? "choice other picked" : "choice other"}
            type="button"
            aria-pressed={written}
            onClick={() => {
              setWriting(true);
              setDraft(written ? chosen : "");
            }}
          >
            {written ? `${other}: ${chosen}` : `${other}…`}
          </button>
        )}
      </div>
      <div className="pager">
        <button type="button" disabled={at === 0} onClick={() => show(at - 1)}>
          ‹ Câu trước
        </button>
        <button type="button" disabled={chosen === ""} onClick={() => show(at + 1)}>
          {at === total - 1 ? "Xem lại ›" : "Câu sau ›"}
        </button>
      </div>
    </div>
  );
}
