import { useState } from "react";

import { moment, teacher, type ReportChat } from "../../api";
import { go } from "../../App";
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
        <p>
          Báo cáo giải thích chưa rõ của học sinh, gom theo đề, và câu có tỉ lệ sai cao khi bài đã kết
          thúc.
        </p>
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
        <p>Chỉ tính các đề đã hết hạn chữa bài. Điểm quy về thang 10 trước khi gộp.</p>
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
                    <span className="label" title={one.learning_objective}>
                      {one.learning_objective}
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
                <span className="said">
                  <MathText>{one.text}</MathText>
                </span>
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
          <span className="column-head">PHƯƠNG ÁN · TỈ LỆ CHỌN Ở LẦN LÀM ĐẦU</span>
          {data.options.map((one) => (
            <span className="byline" key={one.label}>
              {one.label}. <MathText>{one.text}</MathText>
              {one.is_correct ? (
                <span className="right-mark">✓ đúng · {one.percent}% chọn</span>
              ) : (
                <>
                  {` · ${one.percent}% chọn`}
                  {one.error_label && (
                    <>
                      {" — "}
                      <MathText>{one.error_label}</MathText>
                    </>
                  )}
                </>
              )}
            </span>
          ))}
          {data.unanswered > 0 && <span className="byline">Bỏ trống · {data.unanswered}%</span>}
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
