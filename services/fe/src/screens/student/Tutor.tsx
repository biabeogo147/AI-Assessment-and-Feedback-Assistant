import { useCallback, useEffect, useRef, useState } from "react";

import {
  api,
  moment,
  streamReply,
  type ChatHistory,
  type Me,
  type Remediation,
  type Solution,
} from "../../api";
import { go } from "../../App";
import { ErrorStrip, TopBar } from "../../components";
import MathText from "../../MathText";

/**
 * Màn 17, 18, 19, 20 và 24 — hỏi trợ lý, và cửa vào một lượt làm lại.
 *
 * Một component, vì chúng là một màn hình ở năm trạng thái: mới vào, đang mở lời
 * giải, đang mở cửa vào lượt ở hai dạng của nó, và chỉ-đọc sau khi `Attempt` đã
 * kết thúc. Tách ra là nhân bản cái panel thành bốn bản và để bốn bản đó trôi
 * khỏi nhau.
 *
 * Panel liệt kê **mọi** câu làm sai, không phải riêng câu đang được bàn: pha 2
 * nhận một `Assessment`, không phải một `Question` (ADR-14, ADR-17). Nó hiện
 * phương án đã chọn và phương án đúng, không gì khác — tên của cái sai và các
 * lời giải chi tiết nằm cách một lần bấm, trong dialog, để danh sách vẫn là một
 * danh sách.
 */
/**
 * Một lượt nói trong cuộc trò chuyện.
 *
 * Trợ lý có mascot; học sinh có một cột trống rộng y như vậy, nên lời của cả hai
 * bên đều bắt đầu ở cùng một chỗ theo chiều dọc trang, và mắt theo được một mạch
 * thay vì hai.
 *
 * @param role - "student" hoặc "assistant".
 * @param text - Nội dung đã nói.
 */
function Turn({ role, text }: { role: string; text: string }) {
  const student = role === "student";
  return (
    <div className="turn">
      {student ? (
        <span style={{ width: 40, flex: "none" }} />
      ) : (
        <img className="avatar" src="/kriky-face.png" alt="" width={40} height={40} />
      )}
      <div className="said">
        <span className="faint">{student ? "Bạn" : "Kriky"}</span>
        <div className={`bubble ${student ? "student" : ""}`}>
          <MathText>{text}</MathText>
        </div>
      </div>
    </div>
  );
}


export default function Tutor({ me, attemptId }: { me: Me; attemptId: string }) {
  const [panel, setPanel] = useState<Remediation | null>(null);
  const [history, setHistory] = useState<ChatHistory | null>(null);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState("");
  const [solution, setSolution] = useState<Solution | null>(null);
  const [solutionOrder, setSolutionOrder] = useState<number | null>(null);
  const [gateOpen, setGateOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [nextPanel, nextHistory] = await Promise.all([
        api.remediation(attemptId),
        api.chat(attemptId),
      ]);
      setPanel(nextPanel);
      setHistory(nextHistory);
      return nextHistory;
    } catch (cause) {
      setError((cause as Error).message);
      return null;
    }
  }, [attemptId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  /**
   * Xin lượt nói tiếp theo của trợ lý và để nó tự chạy chữ ra.
   *
   * Câu trả lời đã được lưu ở phía server trước khi chunk đầu tiên về tới, nên
   * thứ màn hình tin là lần tải lại ở cuối; phần chữ chạy theo stream chỉ là thứ
   * nó hiện ra trong lúc chờ.
   */
  const pull = useCallback(async () => {
    setStreaming("");
    setBusy(true);
    try {
      await streamReply(attemptId, (chunk) => setStreaming((text) => text + chunk));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setStreaming("");
      setBusy(false);
      await reload();
    }
  }, [attemptId, reload]);

  // Trợ lý nói trước rồi chờ: một lời chào, không phải một bài giảng.
  //
  // Chỉ xin nhiều nhất một lần cho mỗi `Attempt`, và cái chốt này không phải thứ
  // làm cho đẹp. Effect này đọc `history`, mà `pull` thì thay `history`, nên khi
  // không tạo ra được một lượt nói — chẳng hạn BE trả 409 lúc pha 1 chưa nộp —
  // lịch sử về rỗng và effect lại chạy ngay lập tức. Đo được khoảng 1.500 request
  // một giây: một buổi chiều như vậy làm một Vite dev server phình lên 69 GB và
  // lôi luôn bộ nhớ của máy đi theo.
  const askedFor = useRef<string | null>(null);
  useEffect(() => {
    if (history === null || history.locked || busy) return;
    if (history.messages.length > 0) return;
    if (askedFor.current === attemptId) return;
    askedFor.current = attemptId;
    void pull();
  }, [attemptId, history, pull, busy]);

  async function send() {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    try {
      await api.postChat(attemptId, text);
      await reload();
      await pull();
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function openRound() {
    setBusy(true);
    try {
      const round = await api.startRound(attemptId);
      // Các câu hỏi của lượt này chỉ tồn tại trong response này: xin lại một lần
      // nữa là mở thêm một lượt thứ hai và tiêu thêm một trong ba lượt (ADR-17).
      window.sessionStorage.setItem(`round:${round.round_id}`, JSON.stringify(round));
      go(`/round/${attemptId}/${round.round_id}`);
    } catch (cause) {
      setError((cause as Error).message);
      setBusy(false);
    }
  }

  if (panel === null || history === null) {
    return (
      <>
        <TopBar me={me} />
        <main className="page">
          <ErrorStrip message={error} />
          {error === null ? "Đang tải…" : null}
        </main>
      </>
    );
  }

  const locked = history.locked;
  // Cửa này sắp mở vòng thứ mấy, đọc ra từ chính các câu hỏi chứ không tự đếm ở
  // đây: mức trần ba vòng là của BE (ADR-17).
  const nextRound =
    1 + Math.max(0, ...panel.items.filter((item) => !item.closed).map((i) => i.rounds_used));
  // Cuộc trò chuyện đang ở câu nào, lấy từ câu cuối cùng mà **học sinh** hỏi.
  // Lời chào gọi tên mọi câu làm sai, nên nếu đọc bất kỳ tin nhắn nào thì một
  // trong số đó sẽ bị đánh dấu "đang hỏi" trước khi có ai hỏi gì.
  // "câu 5 và câu 6" — cùng một cách nói ở hộp tiến độ và ở cửa vào lượt, vì
  // chúng đang gọi tên cùng một tập.
  const openList = panel.items
    .filter((item) => !item.closed)
    .map((item) => `câu ${item.order}`)
    .join(" và ");
  // Lời cảnh báo ở cửa đếm bằng phút, nên nó phải nêu đúng con số mà học sinh
  // đối chiếu được với đồng hồ, chứ không nói chung chung là "đã gần".
  const minutesLeft = Math.max(
    0,
    Math.round((new Date(panel.deadline).getTime() - Date.now()) / 60000),
  );
  const asking = (() => {
    for (let index = history.messages.length - 1; index >= 0; index -= 1) {
      const message = history.messages[index];
      if (message.role !== "student") continue;
      const named = /câu\s*(\d+)/i.exec(message.text);
      if (named) return Number(named[1]);
    }
    return null;
  })();

  return (
    <>
      <TopBar me={me} />
      <div className="split">
        <section className="chat">
          <div className="banner slim">
            {locked
              ? "Bài đã kết thúc. Em vẫn đọc lại được phần chữa và báo cáo chỗ khó hiểu, nhưng không nhắn thêm được nữa."
              : "Phần này không tính giờ. Hỏi đến khi hiểu rồi hãy bấm làm bài mới."}
          </div>

          <ErrorStrip message={error} />

          {/* Cuộc trò chuyện là phần duy nhất của cột này có cuộn. */}
          <div className="thread">
            {history.messages.map((message) => (
              <Turn key={message.message_id} role={message.role} text={message.text} />
            ))}

            {streaming ? <Turn role="assistant" text={streaming} /> : null}
          </div>

          <div className={`composer ${locked ? "locked" : ""}`}>
            <input
              value={draft}
              disabled={locked || busy}
              placeholder={
                locked
                  ? "Bài đã kết thúc — không nhắn thêm được."
                  : "Hỏi Kriky về bất kỳ câu nào bạn làm sai…"
              }
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void send();
              }}
            />
            <button
              className="btn-quiet"
              type="button"
              disabled={locked || busy}
              onClick={() => void send()}
            >
              Gửi
            </button>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
            {history.messages.filter((message) => message.role === "assistant").length > 1 ||
            locked ? (
            <button
              className="btn-report"
              type="button"
              onClick={() =>
                api
                  .report(attemptId, null)
                  .then(() => setError("Đã gửi báo cáo tới giáo viên."))
                  .catch((cause: Error) => setError(cause.message))
              }
            >
              ⚑ Báo cáo Trợ lý giải thích khó hiểu
            </button>
            ) : null}
            {locked ? null : (
              <button
                className="btn-cta"
                type="button"
                disabled={!panel.can_start_round || busy}
                onClick={() => setGateOpen(true)}
              >
                Làm bài mới · {panel.open_count} câu · {panel.round_budget_minutes} phút
              </button>
            )}
          </div>
        </section>

        <aside className="panel">
          <div className="label-caps">CÁC CÂU EM LÀM SAI</div>

          <div className="panel-cards">
          {panel.items.map((item) => (
            <div
              key={item.question_id}
              className={`panel-card ${asking === item.order ? "asking" : ""}`}
            >
              <div className="title-14" style={{ display: "flex", gap: 8 }}>
                <span>Câu {item.order}</span>
                {asking === item.order ? (
                  <span style={{ color: "var(--accent)", fontSize: "var(--type-caption)" }}>
                    đang hỏi
                  </span>
                ) : null}
              </div>
              <div style={{ fontSize: "var(--type-label)", lineHeight: 1.35 }}>
                <MathText>{item.stem}</MathText>
              </div>
              {item.chosen ? (
                <div
                  className="muted"
                  style={{ color: "var(--answer-incorrect)", fontWeight: 600 }}
                >
                  Em đã chọn {item.chosen.label}. <MathText>{item.chosen.text}</MathText>
                </div>
              ) : (
                <div className="muted">Em chưa chọn phương án nào.</div>
              )}
              <div className="muted" style={{ color: "var(--answer-correct)", fontWeight: 600 }}>
                Đáp án đúng {item.correct.label}. <MathText>{item.correct.text}</MathText>
              </div>
              <button
                className="btn-quiet"
                type="button"
                style={{ alignSelf: "flex-start" }}
                onClick={() =>
                  api
                    .solution(item.question_id)
                    .then((loaded) => {
                      setSolution(loaded);
                      setSolutionOrder(item.order);
                    })
                    .catch((cause: Error) => setError(cause.message))
                }
              >
                Xem lời giải đầy đủ ›
              </button>
            </div>
          ))}

          </div>

          {panel.items.length === 0 ? (
            <div className="muted">Bài này không có câu nào sai.</div>
          ) : null}

          <div className="panel-card plain" style={{ padding: "12px 14px" }}>
            {locked ? (
              <>
                <div className="stat">
                  <span className="key">Kết quả</span>
                  <span className="value">
                    {panel.items
                      .map(
                        (item) =>
                          `câu ${item.order}: ${item.mark === 0.5 ? "0,5" : item.mark}đ`,
                      )
                      .join(" · ")}
                  </span>
                </div>
                <div className="stat">
                  <span className="key">Đã kết thúc</span>
                  <span className="value">{moment(panel.deadline)}</span>
                </div>
              </>
            ) : (
              <>
                <div className="stat">
                  <span className="key">Còn phải làm lại</span>
                  <span className="value">
                    {panel.open_count} câu: {openList}
                  </span>
                </div>
                <div className="stat">
                  <span className="key">Hạn làm lại</span>
                  <span className="value">tới hết {moment(panel.deadline)}</span>
                </div>
              </>
            )}
          </div>
        </aside>
      </div>

      {solution !== null ? (
        <div className="scrim" onClick={() => setSolution(null)}>
          <div className="dialog solution" onClick={(event) => event.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
              <h2 style={{ flex: 1, fontSize: "var(--type-heading)" }}>
                Lời giải — Câu {solutionOrder ?? ""}
              </h2>
              <button className="btn-quiet muted-link" type="button" onClick={() => setSolution(null)}>
                Đóng
              </button>
            </div>

            <p
              style={{
                margin: 0,
                fontSize: "var(--type-label)",
                color: "var(--ink-muted)",
              }}
            >
              <MathText>{solution.stem}</MathText>
            </p>

            <div className="panel-card plain" style={{ gap: 14, padding: 16 }}>
              {solution.methods.map((method) => (
                <div key={method.title}>
                  <div style={{ fontSize: "var(--type-caption)", fontWeight: 600 }}>
                    {method.title}
                  </div>
                  <div className="muted" style={{ marginTop: 4, lineHeight: 1.25 }}>
                    <MathText>{method.body}</MathText>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div className="label-caps">ĐỐI CHIẾU TỪNG PHƯƠNG ÁN</div>
              {solution.options.map((option) => (
                <div key={option.label} style={{ display: "flex", gap: 12, padding: "6px 0" }}>
                  <span
                    style={{
                      width: 120,
                      flex: "none",
                      fontWeight: 600,
                      fontSize: "var(--type-caption)",
                      color: option.is_correct
                        ? "var(--answer-correct)"
                        : "var(--answer-incorrect)",
                    }}
                  >
                    {option.label}. <MathText>{option.text}</MathText>
                  </span>
                  <span className="muted">
                    {option.is_correct ? (
                      "✓ đúng"
                    ) : (
                      <MathText>{option.error_label ?? ""}</MathText>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {gateOpen ? (
        <div className="scrim">
          <div className="dialog gate">
            <h2 style={{ fontSize: "var(--type-heading)" }}>Bắt đầu lượt làm lại?</h2>
            <p
              style={{
                margin: "16px 0",
                lineHeight: 1.25,
                color: "var(--ink-muted)",
              }}
            >
              Bấm là đồng hồ chạy ngay. Đóng trình duyệt cũng không dừng nó.
            </p>

            <div className="panel-card plain" style={{ padding: "12px 14px" }}>
              <div className="stat">
                <span className="key">Lượt này</span>
                <span className="value">
                  {panel.open_count} câu: {openList}
                </span>
              </div>
              <div className="stat">
                <span className="key">Vòng</span>
                <span className="value">
                  vòng {nextRound} — mỗi câu còn {3 - nextRound + 1} vòng
                </span>
              </div>
              <div className="stat">
                <span className="key">Thời gian</span>
                <span className="value">
                  {panel.minutes_per_question} phút mỗi câu — {panel.round_budget_minutes} phút
                </span>
              </div>
              <div className="stat">
                <span className="key">Hạn làm lại</span>
                <span className="value">tới hết {moment(panel.deadline)}</span>
              </div>
            </div>

            {panel.warn_cut ? (
              <div className="warn-strip">
                Còn {minutesLeft} phút tới hạn làm lại. Lượt này {panel.round_budget_minutes} phút,
                nên có thể bị <strong>DỪNG</strong> giữa chừng.
              </div>
            ) : null}

            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 16 }}>
              <button
                className="btn-dialog quiet"
                type="button"
                onClick={() => setGateOpen(false)}
              >
                Để sau
              </button>
              <button
                className="btn-dialog"
                type="button"
                disabled={busy}
                onClick={() => void openRound()}
              >
                Làm bài mới
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
