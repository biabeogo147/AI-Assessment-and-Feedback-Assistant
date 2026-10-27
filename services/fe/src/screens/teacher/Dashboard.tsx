import { useState } from "react";

import { moment, teacher, type ReportChat } from "../../api";
import { go } from "../../App";
import KrikyText from "../../KrikyText";
import MathText from "../../MathText";
import { BoardHead, BoardWaiting, classLabel, classesLabel, NONE, useBoard, vn } from "./Board";
import Veil from "./Veil";

/**
 * Màn 20 · *Bảng theo dõi* (`657:3889`), plan `dashboard-review-queue`, việc 19 và 21.
 *
 * Hai phần. *Cần bạn xem*: báo cáo *giải thích chưa rõ* gom theo đề, và câu có tỉ lệ sai cao khi bài
 * đã kết thúc -- cùng trọng lượng, không tô màu loại, không xếp nặng nhẹ (ADR-08); hàng đợi rỗng là
 * tin tốt, không vẽ như lỗi. *Điểm gộp theo lớp*: chỉ đề đã hết hạn chữa, quy về thang 10. Mọi con số
 * và mọi ngưỡng là của BE (`be/teacher_board.py`).
 */
export default function Dashboard() {
  const { data, trouble } = useBoard(() => teacher.board(), "board");

  if (data === null) {
    return (
      <div className="board">
        <BoardHead title="Bảng theo dõi" sub="" />
        <BoardWaiting trouble={trouble} />
      </div>
    );
  }

  return (
    <div className="board dashboard">
      <BoardHead
        title="Bảng theo dõi"
        sub={`${data.queue.length} việc cần bạn xem · ${data.classes.length} lớp có đề đã hết hạn chữa`}
      />

      <div className="board-part">
        <h2>Cần bạn xem</h2>
      </div>
      <div className="board-table queue" role="table">
        <div className="board-row head" role="row">
          <span>LOẠI</span>
          <span>NỘI DUNG</span>
          <span>SỐ LIỆU</span>
          <span />
          <span />
        </div>
        {data.queue.length === 0 && (
          <div className="board-row empty" role="row">
            Không có việc nào cần bạn xem.
          </div>
        )}
        {data.queue.map((one) => {
          const to =
            one.kind === "reports"
              ? `/teacher/theo-doi/bao-cao/${one.assessment_id}`
              : `/teacher/theo-doi/cau/${one.question_id}`;
          return (
            <div
              className="board-row open-able"
              role="row"
              key={`${one.kind}-${one.question_id || one.assessment_id}`}
              tabIndex={0}
              onClick={() => go(to)}
              onKeyDown={(event) => {
                if (event.key === "Enter") go(to);
              }}
            >
              <span className="kind">
                {one.kind === "reports" ? "Giải thích chưa rõ" : "Tỉ lệ sai cao"}
              </span>
              <span className="what">
                <span className="name">
                  <MathText>{one.title}</MathText>
                </span>
                <span className="small">{one.meta}</span>
              </span>
              <span className="cell-muted">{one.figure}</span>
              <span className="act">{one.kind === "reports" ? "Xem báo cáo" : "Xem câu"}</span>
              <span className="chevron" aria-hidden="true">
                ›
              </span>
            </div>
          );
        })}
      </div>

      <div className="board-part">
        <h2>Điểm gộp theo lớp</h2>
      </div>
      {data.classes.length > 0 && (
        <div className="board-charts">
          <div className="chart-card">
            <div className="chart-head">ĐIỂM TRUNG BÌNH THEO LỚP</div>
            <div className="bars">
              {data.classes.map((one) => (
                <div className="bar-col" key={one.class_id}>
                  <span className="bar-count">{one.mean === null ? NONE : vn(one.mean, true)}</span>
                  {/* Thang 10 cố định, không theo lớp cao nhất: cột 7,2 cao như nhau ở mọi màn
                      (artboard 20: 9,6 px một điểm, cột 10 điểm cao 96). Buộc vào `.board-charts
                      .bars { height: 115px }`: 96 cộng số trên đầu cột (15) và khe 4. */}
                  <span className="bar" style={{ height: `${(one.mean ?? 0) * 9.6}px` }} />
                </div>
              ))}
            </div>
            <div className="bars-axis">
              {data.classes.map((one) => (
                <span className="bar-mark" key={one.class_id}>
                  {classLabel(one.name)}
                </span>
              ))}
            </div>
          </div>
          <div className="chart-card objectives">
            <div className="chart-head">TỈ LỆ BÀI SAI THEO MỤC KIẾN THỨC · 5 MỤC CAO NHẤT</div>
            {data.objectives.length === 0 ? (
              <div className="chart-empty">Chưa có lượt trả lời nào.</div>
            ) : (
              <div className="objective-rows">
                {data.objectives.map((one) => (
                  <div className="objective" key={one.learning_objective}>
                    {/* `title` giữ chữ gốc: thuộc tính không dựng được công thức. */}
                    <span className="label" title={one.learning_objective}>
                      <MathText>{flatFractions(one.learning_objective)}</MathText>
                    </span>
                    <span className="track">
                      <span className="fill" style={{ width: `${one.percent}%` }} />
                    </span>
                    <span className="count">{one.percent}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      {/* Không `fill`: artboard 20 để bảng lớp cao theo nội dung. */}
      <div className="board-table class-stats" role="table">
        <div className="board-row head" role="row">
          <span>LỚP</span>
          <span className="num">ĐỀ ĐÃ KẾT THÚC</span>
          <span className="num">TRUNG BÌNH</span>
          <span className="num">CAO NHẤT</span>
          <span className="num">THẤP NHẤT</span>
          <span>DẠNG SAI NHIỀU NHẤT</span>
          <span />
        </div>
        {data.classes.length === 0 && (
          <div className="board-row empty" role="row">
            Chưa có đề nào hết hạn chữa bài.
          </div>
        )}
        {data.classes.map((one) => {
          const to = `/teacher/lop/${one.class_id}`;
          return (
            <div
              className="board-row open-able"
              role="row"
              key={one.class_id}
              tabIndex={0}
              onClick={() => go(to)}
              onKeyDown={(event) => {
                if (event.key === "Enter") go(to);
              }}
            >
              <span className="name">{classLabel(one.name)}</span>
              <span className="num">{one.papers}</span>
              <span className="num">{one.mean === null ? NONE : vn(one.mean, true)}</span>
              <span className="num">{one.highest === null ? NONE : vn(one.highest, true)}</span>
              <span className="num">{one.lowest === null ? NONE : vn(one.lowest, true)}</span>
              <span className="cell-muted">{one.weakest || NONE}</span>
              <span className="chevron" aria-hidden="true">
                ›
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Phân số của một nhãn biểu đồ, viết ngang: `\frac{a}{b}` thành `a/b` (Tier 2 câu 36, hướng A).
 *
 * Nhãn cao 11px; phân số xếp chồng còn tử và mẫu cỡ 6–7px, đọc lướt không ra. Tử có hơn một hạng
 * tử, hay mẫu không phải một ký hiệu đơn, thì thêm ngoặc: `\frac{a+b}{2x}` thành `(a+b)/(2x)`, không
 * thành `a+b/2x`. Phân số có số mũ ngay sau thì cả phân số vào ngoặc. `\dfrac`, `\tfrac` cũng vậy;
 * phân số lồng nhau viết ngang từ trong ra. Hàm thuần, chỉ dùng cho nhãn: đề bài vẫn xếp chồng.
 *
 * @param label - Mục kiến thức như API trả.
 * @returns Nhãn với mọi phân số đã viết ngang. Một `\frac` thiếu ngoặc nhọn thì để nguyên, và các
 *   phân số khác của nhãn vẫn được viết ngang.
 */
export function flatFractions(label: string): string {
  const head = /\\[dt]?frac\s*\{/g;
  let text = label;
  // Chỉ tìm trước mốc này: một `\frac` hỏng thì lùi mốc qua nó và đi tiếp, không bỏ cả nhãn.
  let limit = text.length;
  for (let guard = 0; guard < 40; guard += 1) {
    head.lastIndex = 0;
    let found: RegExpExecArray | null = null;
    let last: RegExpExecArray | null;
    // Phân số trong cùng trước: `\frac{` cuối cùng còn lại trước mốc.
    while ((last = head.exec(text)) !== null && last.index < limit) found = last;
    if (found === null) return text;
    const top = group(text, found.index + found[0].length - 1);
    const opening = top === null ? null : text.slice(top.end).match(/^\s*\{/);
    const bottom =
      top === null || opening === null ? null : group(text, top.end + opening[0].length - 1);
    if (top === null || bottom === null) {
      limit = found.index;
      continue;
    }
    const plain = `${grouped(top.body, false)}/${grouped(bottom.body, true)}`;
    const flat = /^\s*\^/.test(text.slice(bottom.end)) ? `(${plain})` : plain;
    text = text.slice(0, found.index) + flat + text.slice(bottom.end);
    limit = text.length;
  }
  return text;
}

/** Một cặp ngoặc nhọn bắt đầu ở `open`: phần bên trong và chỗ ngay sau ngoặc đóng. */
function group(text: string, open: number): { body: string; end: number } | null {
  let depth = 0;
  for (let at = open; at < text.length; at += 1) {
    if (text[at] === "{") depth += 1;
    if (text[at] === "}") {
      depth -= 1;
      if (depth === 0) return { body: text.slice(open + 1, at), end: at + 1 };
    }
  }
  return null;
}

/**
 * Tử hay mẫu, đã thêm ngoặc khi cần. Tử vào ngoặc khi có hơn một hạng tử (cộng, trừ, chia, nhân,
 * dấu cách). Mẫu chặt hơn: chỉ một ký hiệu đơn mới đứng trần (`2`, `x`, `\pi`, `x^2`), vì `1/2x`
 * đọc được là *(1/2)·x*.
 */
function grouped(part: string, denominator: boolean): string {
  const body = part.trim();
  const single = /^(?:\d+(?:[.,]\d+)?|[A-Za-z]|\\[A-Za-z]+)(?:\^(?:\w|\{\w+\}))?$/.test(body);
  if (denominator) return single ? body : `(${body})`;
  return single || !/[+\-/\s]|\\(?:cdot|times|pm|div)/.test(body) ? body : `(${body})`;
}

/**
 * Màn 25 · *Báo cáo giải thích chưa rõ — một đề* (`657:4265`).
 *
 * Chỉ đọc. Trái: các câu học sinh báo cáo đã làm sai, mỗi câu một link sang bản ngân hàng của nó
 * (22b) -- câu trong đề đã phát hành không bao giờ sửa. Phải: từng báo cáo, mở được đoạn chat hỏi trợ
 * lý. *Đánh dấu đã xem* gửi đúng các báo cáo đang hiện: một báo cáo đến trong lúc đọc thì ở lại.
 *
 * @param assessmentId - Đề nào.
 */
export function BoardReports({ assessmentId }: { assessmentId: string }) {
  const { data, trouble, setData } = useBoard(
    () => teacher.boardReports(assessmentId),
    assessmentId,
  );
  const [reading, setReading] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState("");

  const back = { label: "Bảng theo dõi", to: "/teacher/theo-doi" };
  if (data === null) {
    return (
      <div className="board">
        <BoardHead back={back} title="" sub="" />
        <BoardWaiting trouble={trouble} />
      </div>
    );
  }

  async function seen() {
    if (data === null) return;
    setBusy(true);
    setRefused("");
    try {
      await teacher.seeReports(
        assessmentId,
        data.reports.map((one) => one.report_id),
      );
      go("/teacher/theo-doi");
    } catch (cause) {
      setRefused((cause as Error).message);
      setBusy(false);
      // Như màn 29: đọc lại, để màn nói đúng điều BE đang giữ sau lời từ chối.
      teacher.boardReports(assessmentId).then(setData, () => undefined);
    }
  }

  const reporters = data.reporters;
  return (
    <div className="board">
      <BoardHead
        back={back}
        title={data.title}
        sub={[
          `${data.reports.length} lượt báo cáo chưa xem`,
          classesLabel(data.classes),
        ]
          .filter(Boolean)
          .join(" · ")}
      />
      {data.reports.length === 0 ? (
        <div className="board-wait">Không còn báo cáo nào chưa xem ở đề này.</div>
      ) : (
        <div className="board-split">
          <div className="board-column">
            <div className="column-head">CÁC CÂU HỌC SINH BÁO CÁO ĐÃ LÀM SAI</div>
            {data.questions.map((one) => (
              <div className="board-card" key={one.question_id}>
                <span className="lead">
                  Câu {one.order} · <MathText>{one.stem}</MathText>
                </span>
                <span className="small">
                  {one.wrong_by} trên {reporters} em báo cáo làm sai câu này
                </span>
                {one.bank_id !== "" && (
                  <button
                    className="link"
                    type="button"
                    onClick={() => go(`/teacher/ngan-hang/${one.bank_id}`)}
                  >
                    Chỉnh sửa trong Ngân hàng câu hỏi ›
                  </button>
                )}
              </div>
            ))}
            {refused !== "" && (
              <p className="refused" role="alert">
                {refused}
              </p>
            )}
            <div className="board-actions">
              <button className="btn primary" type="button" disabled={busy} onClick={() => void seen()}>
                Đánh dấu đã xem
              </button>
            </div>
          </div>
          <div className="board-column reports">
            <div className="column-head">BÁO CÁO CỦA HỌC SINH</div>
            {data.reports.map((one) => (
              <div className="board-card" key={one.report_id}>
                <span className="byline">
                  {one.student} · {moment(one.created_at)}
                </span>
                {one.wrong.length > 0 && (
                  <span className="byline">
                    Làm sai: {one.wrong.map((order) => `Câu ${order}`).join(", ")}
                  </span>
                )}
                <span className="lead">{one.note !== "" ? `“${one.note}”` : "Không ghi gì thêm."}</span>
                <button className="link" type="button" onClick={() => setReading(one.report_id)}>
                  Mở hội thoại hỏi trợ lý ›
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      {reading !== null && <ChatDialog reportId={reading} onClose={() => setReading(null)} />}
    </div>
  );
}

/**
 * Hộp đọc đoạn chat hỏi trợ lý (artboard 25b, `699:5916`): đoạn chat pha 2 của lượt có báo cáo,
 * chỉ đọc. Báo cáo trỏ vào cả đoạn chat, không vào một lượt (ADR-19).
 *
 * @param reportId - Báo cáo nào.
 * @param onClose - Đóng hộp.
 */
function ChatDialog({ reportId, onClose }: { reportId: string; onClose: () => void }) {
  const { data, trouble } = useBoard<ReportChat>(() => teacher.reportChat(reportId), reportId);
  return (
    <Veil wide className="chat-read" onClose={onClose}>
      <div className="solution-head">
        <h3>{data === null ? "Hội thoại hỏi trợ lý" : `Hội thoại hỏi trợ lý — ${data.student}`}</h3>
        <button className="close" type="button" onClick={onClose}>
          Đóng
        </button>
      </div>
      {data === null ? (
        <BoardWaiting trouble={trouble} />
      ) : (
        <>
          <div className="chat-meta">
            {data.title} · {classLabel(data.class_name)} · Chỉ đọc
          </div>
          <div className="chat-lines">
            {data.messages.length === 0 && (
              <div className="board-wait">Em ấy chưa hỏi trợ lý câu nào.</div>
            )}
            {data.messages.map((one, index) => (
              <div className={`chat-line ${one.role === "student" ? "student" : ""}`} key={index}>
                <span className="byline">{one.role === "student" ? data.student.toUpperCase() : "KRIKY"}</span>
                {/* Lời Kriky là Markdown (ADR-30), như ở màn học sinh (`Tutor.tsx`); câu học sinh gõ
                    thì in như gõ. Một `div`: Markdown dựng đoạn văn, danh sách. */}
                {one.role === "student" ? (
                  <span className="said">
                    <MathText>{one.text}</MathText>
                  </span>
                ) : (
                  <div className="said">
                    <KrikyText>{one.text}</KrikyText>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </Veil>
  );
}

/**
 * Màn 29 · *Câu có tỉ lệ sai cao* (`699:5667`).
 *
 * Chỉ đọc: đề bài, cách giải, và tỉ lệ chọn từng phương án ở lần đầu. *Đánh dấu đã xem* đưa câu rời
 * hàng đợi mãi; *Chỉnh sửa trong Ngân hàng câu hỏi* mở bản ngân hàng (22b), câu trong đề không đổi.
 *
 * @param questionId - Câu nào.
 */
export function BoardQuestion({ questionId }: { questionId: string }) {
  const { data, trouble, setData } = useBoard(() => teacher.boardQuestion(questionId), questionId);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState("");

  const back = { label: "Bảng theo dõi", to: "/teacher/theo-doi" };
  if (data === null) {
    return (
      <div className="board">
        <BoardHead back={back} title="" sub="" />
        <BoardWaiting trouble={trouble} />
      </div>
    );
  }

  async function seen() {
    setBusy(true);
    setRefused("");
    try {
      await teacher.seeQuestion(questionId);
      go("/teacher/theo-doi");
    } catch (cause) {
      setRefused((cause as Error).message);
      setBusy(false);
      teacher.boardQuestion(questionId).then(setData, () => undefined);
    }
  }

  // Phương án sai được chọn nhiều nhất ở lần làm đầu; không ai chọn sai thì không phương án nào.
  // Hoà thì lấy phương án đứng trước: một dòng đỏ, không hai.
  const topWrong = data.options
    .filter((one) => !one.is_correct && one.percent > 0)
    .reduce<{ label: string; percent: number } | null>(
      (best, one) => (best === null || one.percent > best.percent ? one : best),
      null,
    )?.label;

  return (
    <div className="board">
      <BoardHead
        back={back}
        title={`Câu ${data.order} · ${data.title}`}
        sub={[
          `${data.wrong_percent}% bài sai ở lần làm đầu`,
          `${data.submitted} bài`,
          classesLabel(data.classes),
        ]
          .filter(Boolean)
          .join(" · ")}
      />
      <div className="board-column wide">
        <div className="column-head">CÂU HỎI · CHỈ ĐỌC</div>
        <div className="board-card">
          <span className="lead">
            <MathText>{data.stem}</MathText>
          </span>
          {data.methods.map((one, index) => (
            <span className="byline" key={index}>
              <MathText>{`${one.title} — ${one.body}`}</MathText>
            </span>
          ))}
        </div>
        <div className="board-card">
          <span className="column-head" id="option-rates-head">
            PHƯƠNG ÁN · TỈ LỆ CHỌN Ở LẦN LÀM ĐẦU
          </span>
          {/* Ba cột -- phương án, tỉ lệ canh phải, ghi chú -- để các con số thẳng một cột; phương án
              sai được chọn nhiều nhất bôi đỏ (người dùng chốt 19/10/2026, artboard 29). */}
          <div className="option-rates" role="table" aria-labelledby="option-rates-head">
            {data.options.map((one) => (
              <div
                className={one.label === topWrong ? "option-rate top-wrong" : "option-rate"}
                role="row"
                key={one.label}
              >
                <span className="option-name">
                  {one.label}. <MathText>{one.text}</MathText>
                </span>
                <span className="option-share">{one.percent}% chọn</span>
                <span className={one.is_correct ? "option-note right" : "option-note"}>
                  {one.is_correct ? "✓ đúng" : one.error_label && <MathText>{one.error_label}</MathText>}
                </span>
              </div>
            ))}
            {data.unanswered > 0 && (
              <div className="option-rate" role="row">
                <span className="option-name">Bỏ trống</span>
                <span className="option-share">{data.unanswered}% chọn</span>
                <span className="option-note" />
              </div>
            )}
          </div>
        </div>
        {refused !== "" && (
          <p className="refused" role="alert">
            {refused}
          </p>
        )}
        <div className="board-actions">
          <button
            className="btn primary"
            type="button"
            disabled={busy || data.seen}
            onClick={() => void seen()}
          >
            {data.seen ? "Đã xem" : "Đánh dấu đã xem"}
          </button>
          {data.bank_id !== "" && (
            <button
              className="btn"
              type="button"
              onClick={() => go(`/teacher/ngan-hang/${data.bank_id}`)}
            >
              Chỉnh sửa trong Ngân hàng câu hỏi
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
