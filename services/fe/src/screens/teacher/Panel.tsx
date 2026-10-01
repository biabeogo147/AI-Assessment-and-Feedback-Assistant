import { useEffect, useState } from "react";

import { teacher, type AssessmentDetail, type TeacherQuestion } from "../../api";
import { provenanceOf } from "./invented-not-from-be";

/**
 * Panel bên phải: nội dung một đề, và cổng duyệt.
 *
 * Artboard 6 và 7 là **cùng một panel** ở hai trạng thái, không phải hai màn hình — thuộc
 * tính `Sửa được` của thiết kế tắt khi đề đã duyệt. Trạng thái ấy tới từ `state`, và giao
 * diện **không** tự kết luận: ADR-01 nói vòng đời là luật của BE, nên ở đây chỉ có đọc
 * `state` rồi vẽ, không có phép so sánh nào.
 *
 * Panel tự gọi dữ liệu của mình thay vì nhận qua prop, vì nó mở ra từ một route riêng và
 * một lần F5 trên route ấy phải dựng lại được — mà `turns` thì không mang nội dung đề.
 *
 * @param assessmentId - Đề nào.
 * @param onClose - Đóng panel, quay về đoạn chat.
 * @param onApproved - Được gọi sau khi duyệt xong, để nơi gọi tải lại dòng lượt nói:
 *   `approve` ghi một bước vào hội thoại (ADR-01 đòi thế), và bước đó phải hiện ra.
 */
export default function Panel({
  assessmentId,
  onClose,
  onApproved,
}: {
  assessmentId: string;
  onClose: () => void;
  onApproved: () => void;
}) {
  const [paper, setPaper] = useState<AssessmentDetail | null>(null);
  const [trouble, setTrouble] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    setPaper(null);
    teacher
      .assessment(assessmentId)
      .then(setPaper)
      .catch((cause: Error) => setTrouble(cause.message));
  }, [assessmentId]);

  async function approve() {
    setWorking(true);
    try {
      await teacher.approve(assessmentId);
      setPaper(await teacher.assessment(assessmentId));
      setTrouble(null);
      onApproved();
    } catch (cause) {
      setTrouble((cause as Error).message);
    } finally {
      setWorking(false);
    }
  }

  if (paper === null) {
    return (
      <aside className="panel">
        <div className="panel-head">
          <div className="title-row">
            <h2>{trouble ?? "Đang mở…"}</h2>
            <button className="close" type="button" onClick={onClose}>
              Đóng
            </button>
          </div>
        </div>
      </aside>
    );
  }

  const approved = paper.state === "approved" || paper.state === "published";

  return (
    <aside className="panel">
      <div className="panel-head">
        <div className="title-row">
          <h2>{paper.title}</h2>
          <button className="close" type="button" onClick={onClose}>
            Đóng
          </button>
        </div>
        <div className="meta">
          {paper.question_count} câu · {paper.subject} {paper.grade}
          {paper.topic_scope !== "" && ` · ${paper.topic_scope}`}
        </div>
        <Provenance questions={paper.questions} />
      </div>

      <div className="panel-questions">
        {paper.questions.map((one) => (
          <QuestionCard key={one.question_id} question={one} editable={!approved} />
        ))}
      </div>

      <div className="panel-foot">
        <div className="note">
          {trouble ??
            (approved
              ? "Đã duyệt. Nội dung khoá lại; muốn sửa thì bỏ duyệt trước."
              : "Bạn duyệt xong mới phát hành được. Học sinh chưa nhìn thấy đề này.")}
        </div>
        <button
          className="cta"
          type="button"
          disabled={approved || working || paper.question_count === 0}
          onClick={() => void approve()}
        >
          {approved ? "Đã duyệt" : "Duyệt đề"}
        </button>
      </div>
    </aside>
  );
}

/**
 * Dòng tổng kết nguồn câu hỏi, ngay dưới tên đề.
 *
 * Mọi con số ở đây đếm từ các chip của từng câu, nên dòng này và các thẻ bên dưới không
 * bao giờ nói hai điều khác nhau — kể cả khi cả hai cùng bịa.
 */
function Provenance({ questions }: { questions: TeacherQuestion[] }) {
  const tally = { bank: 0, checked: 0, unchecked: 0 };
  for (const one of questions) {
    const tone = provenanceOf(one.question_id).tone;
    if (tone === "checked") tally.checked += 1;
    else if (tone === "unchecked") tally.unchecked += 1;
    else tally.bank += 1;
  }
  return (
    <div className="provenance">
      {tally.bank > 0 && <span className="lead">{tally.bank} câu ngân hàng ·</span>}
      {tally.checked > 0 && (
        <span className="source-chip checked">{tally.checked} câu thêm mới đã kiểm</span>
      )}
      {tally.unchecked > 0 && (
        <span className="source-chip unchecked">{tally.unchecked} câu chưa kiểm</span>
      )}
    </div>
  );
}

/**
 * Một câu hỏi trong panel.
 *
 * Lời giải mở ra tại chỗ chứ không mở một hộp thoại: *"Lời giải · 2 cách"* đọc được ngay
 * khi còn thu gọn, và con số đó là `methods.length` — nó đi kèm trong cùng một response,
 * nên một panel mười thẻ không phải gọi mười request chỉ để đếm.
 *
 * @param question - Câu hỏi, kèm phương án và lời giải.
 * @param editable - Đề còn sửa được hay không. Tới từ `state`, không từ một phép so sánh
 *   ở đây.
 */
function QuestionCard({
  question,
  editable,
}: {
  question: TeacherQuestion;
  editable: boolean;
}) {
  const [open, setOpen] = useState(false);
  const source = provenanceOf(question.question_id);

  return (
    <div className="qcard">
      <div className="top">
        <span className="num">Câu {question.order}</span>
        <span className={`source-chip ${source.tone}`}>{source.label}</span>
        <span className="spacer" />
        {editable && (
          <button className="edit" type="button">
            Sửa
          </button>
        )}
      </div>

      <div className="stem">{question.stem}</div>

      <div className="options">
        {question.options.map((one) => (
          <div className={`opt ${one.is_correct ? "correct" : ""}`} key={one.label}>
            {one.label}. {one.text}
            {one.is_correct && "   ✓"}
          </div>
        ))}
      </div>

      <button className="solution" type="button" onClick={() => setOpen(!open)}>
        <span>
          Lời giải · {question.methods.length} cách
        </span>
        <span className="spacer" />
        <span aria-hidden="true">{open ? "⌄" : "›"}</span>
      </button>

      {open &&
        question.methods.map((one) => (
          <div className="stem" key={one.title}>
            <strong>{one.title}</strong>
            <div className="opt">{one.body}</div>
          </div>
        ))}
    </div>
  );
}
