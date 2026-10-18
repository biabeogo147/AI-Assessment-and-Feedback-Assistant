import { moment, teacher, type PaperRow } from "../../api";
import { go } from "../../App";
import { BoardHead, BoardWaiting, NONE, useBoard } from "./Board";
import { phaseTone } from "./ClassDetail";

/**
 * Màn 21 · *Các bài kiểm tra* (`655:4929`), plan `teacher-rail-screens`, việc 18.
 *
 * Mọi đề của giáo viên, mới nhất trước. Nhãn trạng thái là chữ của BE theo vòng đời và giờ BE
 * (Decision 3); hành động của dòng cũng do BE nói (`shows_results`): đề đã tới giờ mở ở ít nhất một
 * lớp thì *Xem kết quả* (lớp đầu đã qua giờ mở, Decision 4), không thì *Mở đoạn chat* đã sinh ra đề.
 */
export default function Papers() {
  const { data, trouble } = useBoard(() => teacher.papers(), "papers");

  if (data === null) {
    return (
      <div className="board">
        <BoardHead title="Các bài kiểm tra" sub="" />
        <BoardWaiting trouble={trouble} />
      </div>
    );
  }

  return (
    <div className="board">
      <BoardHead
        title="Các bài kiểm tra"
        sub={`${data.papers.length} đề · ${data.running} đang chạy`}
      />
      <div className="board-table papers fill" role="table">
        <div className="board-row head" role="row">
          <span>TÊN ĐỀ</span>
          <span>TRẠNG THÁI</span>
          <span>LỚP</span>
          <span>MỞ LÚC</span>
          <span />
          <span />
        </div>
        {data.papers.length === 0 && (
          <div className="board-row empty" role="row">
            Chưa có đề nào. Nhờ Kriky soạn một đề ở đoạn chat mới.
          </div>
        )}
        {data.papers.map((one) => {
          const to = target(one);
          return (
            <div
              className={`board-row ${to === null ? "" : "open-able"}`}
              role="row"
              key={one.assessment_id}
              tabIndex={to === null ? undefined : 0}
              onClick={to === null ? undefined : () => go(to)}
              onKeyDown={(event) => {
                if (to !== null && event.key === "Enter") go(to);
              }}
            >
              <span className="name" title={one.title}>
                {one.title}
              </span>
              <span className={`phase strong ${phaseTone(one.phase)}`}>{one.status}</span>
              <span className="cell-muted">{one.classes.length > 0 ? one.classes.join(", ") : NONE}</span>
              <span className="when">
                {one.opens_at === null ? (
                  <span className="cell-muted">Chưa phát hành</span>
                ) : (
                  <>
                    <span className="cell-muted">Mở {moment(one.opens_at)}</span>
                    {one.recallable ? (
                      <span className="small">thu hồi được</span>
                    ) : (
                      one.phase !== "over" &&
                      one.remediation_deadline !== null && (
                        <span className="small">chữa tới {moment(one.remediation_deadline)}</span>
                      )
                    )}
                  </>
                )}
              </span>
              <span className="act">
                {to === null ? "" : one.shows_results ? "Xem kết quả" : "Mở đoạn chat"}
              </span>
              <span className="chevron" aria-hidden="true">
                {to === null ? "" : "›"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Route mà một dòng mở, hay `null` khi dòng không mở được gì: đề chưa tới giờ mở mà cũng không sinh
 * từ đoạn chat nào (đề seed, đề tạo tay).
 */
function target(one: PaperRow): string | null {
  if (one.shows_results && one.first_class_id !== "") {
    return `/teacher/lop/${one.first_class_id}/de/${one.assessment_id}`;
  }
  if (one.conversation_id !== "") return `/teacher/chat/${one.conversation_id}/de/${one.assessment_id}`;
  return null;
}
