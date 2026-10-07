import { useEffect, useState } from "react";

import {
  teacher,
  type AssessmentDetail,
  type QuestionEdit,
  type TeacherQuestion,
} from "../../api";
import Editing from "./Editing";
import { provenanceOf } from "./invented-not-from-be";
import PublishSettings from "./PublishSettings";
import Veil from "./Veil";
import MathText from "../../MathText";

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
 * **Đề đã khoá thì panel mở thẳng cài đặt phát hành.** Trước 06/10/2026 còn một chặng ở
 * giữa — panel vẽ nội dung đề cộng một chân panel mời `Phát hành đề` — và chặng ấy thu
 * đúng một cú bấm mà không trả lại gì: thẻ trong chat luôn đi tới `/de/{id}`, không bao
 * giờ tới biểu mẫu, nên mọi lần mở một đề đã duyệt đều mất một nhịp. Nay nấc ấy đọc từ
 * `state` chứ không từ route, và đó là chỗ nó thuộc về: vòng đời là luật của BE (ADR-01),
 * nên một cái URL không được quyền kể một nấc khác với cái BE đang giữ.
 *
 * @param assessmentId - Đề nào.
 * @param onClose - Đóng panel, quay về đoạn chat.
 * @param onApproved - Dòng lượt nói phải đọc lại. Gọi sau **cả ba** việc ghi của panel:
 *   duyệt, bỏ duyệt, và phát hành — cả ba đều để lại một biên bản trong đoạn chat.
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
  // Câu đang mở lời giải. Ở đây chứ không trong từng thẻ: hộp thoại là thứ **một lúc chỉ
  // một cái**, và đó là một luật giữa các thẻ, không phải việc riêng của một thẻ.
  const [solving, setSolving] = useState<TeacherQuestion | null>(null);

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
      // Duyệt xong là **sang thẳng** cài đặt phát hành, và nay việc ấy không cần một cú
      // điều hướng nào: `state` vừa đổi sang `approved`, mà `locked` đọc từ `state`.
    } catch (cause) {
      setTrouble((cause as Error).message);
    } finally {
      setWorking(false);
    }
  }

  /**
   * Lưu chữ vừa sửa của một câu.
   *
   * Trả về lỗi dưới dạng một chuỗi thay vì ném: thẻ đang sửa cần in lời từ chối **ngay
   * dưới ô nhập** để giáo viên sửa tiếp, chứ không đẩy nó lên dòng chung ở chân panel —
   * ở đó nó đứng xa chỗ gõ và không nói nó nói về câu nào.
   *
   * @param questionId - Câu nào.
   * @param edited - Toàn bộ chữ của câu, sau khi sửa.
   * @returns Chuỗi rỗng khi lưu được, ngược lại là câu từ chối của BE.
   */
  async function save(
    questionId: string,
    edited: QuestionEdit,
  ): Promise<string> {
    try {
      await teacher.editQuestion(assessmentId, questionId, edited);
      setPaper(await teacher.assessment(assessmentId));
      return "";
    } catch (cause) {
      return (cause as Error).message;
    }
  }

  /**
   * Bỏ duyệt, mở lại nội dung.
   *
   * Song sinh với `approve` tới từng dòng, và đó là chủ ý: hai nửa của cùng một cổng thì
   * hỏng cùng kiểu, nên chúng nên đọc giống nhau. `teacher.unapprove` có trong `api.ts` từ
   * lâu và **chưa ai gọi một lần nào** — thẻ *Hoàn tác* trong khung chat mở panel, mà panel
   * không có đường bỏ duyệt nào, nên nút ấy dẫn tới hư không.
   */
  async function undo() {
    setWorking(true);
    try {
      await teacher.unapprove(assessmentId);
      setPaper(await teacher.assessment(assessmentId));
      setTrouble(null);
      onApproved();
      // Không còn đường về nào để đi: `state` vừa xuống `has_questions`, nên `locked` tắt
      // và panel tự quay về nội dung đề. Chỗ này từng phải gọi `onUnpublish()` để gỡ hậu
      // tố `/phat-hanh` khỏi hash — một việc chỉ sinh ra vì màn hình đọc nấc từ route.
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

  // `approved` và `published` cùng khoá nội dung, nên chúng cùng mở màn cài đặt phát hành.
  //
  // Trước 06/10/2026 chỗ này phải phân biệt ba trạng thái, vì `POST .../unapprove` chỉ nhận
  // đúng `APPROVED`: một nút `Hoàn tác` hiện ra cho đề đã phát hành là một chỉ dẫn trỏ tới
  // một hành động chắc chắn trả 409. Nay endpoint ấy nhận cả `published` — nó thu hồi mọi
  // lớp rồi hạ hai nấc — nên đường lùi là **một** đường, và màn hình thôi phải kể lại luật
  // của BE bằng một biến riêng. Thứ còn chặn là giờ mở, và câu chặn tới từ
  // `publish-form.undo_blocked`.
  const locked = paper.state === "approved" || paper.state === "published";

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
        {/*
          Một panel trống phải nói vì sao nó trống. Thẻ kết quả trong chat vừa báo *"đã đặt
          chỗ cho 10 câu"* còn panel hiện *"0 câu"* — hai con số đúng cả hai (một cái là số
          đã xin, một cái là số đã viết xong) nhưng đọc cạnh nhau thì như mâu thuẫn, và một
          khoảng trắng cao nửa mét không giải thích gì cả.
        */}
        {paper.questions.length === 0 && (
          <div className="panel-empty">
            {paper.still_drafting > 0
              ? `Đang soạn ${paper.still_drafting} câu. Mở lại sau một lát.`
              : "Chưa có câu hỏi nào trong đề này."}
          </div>
        )}
        {paper.questions.map((one) => (
          <QuestionCard
            key={one.question_id}
            question={one}
            editable={!locked}
            onSolve={() => setSolving(one)}
            onSave={(edited) => save(one.question_id, edited)}
          />
        ))}
      </div>

      {/* Đọc **một** thứ: đề đã khoá hay chưa. Điều kiện này từng là `publishing && locked`
          — `publishing` tới từ hậu tố route `/phat-hanh` — và cái `&&` ấy dựng ra một màn
          hình thứ ba không ai thiết kế: đề đã khoá, nhưng route chưa mang hậu tố, nên panel
          vẽ nội dung đề cộng một nút `Phát hành đề`. Thẻ trong chat luôn đi `/de/{id}`,
          không bao giờ kèm hậu tố, nên **mọi** lần mở một đề đã duyệt đều rơi vào đó. Một
          cú bấm, không mua gì. */}
      {locked ? (
        <>
          {/* Lỗi của `undo()` phải hiện ra **ở đây nữa**, không chỉ ở `panel-foot`.
              `trouble` vốn chỉ sống trong nhánh kia, nên mọi lỗi phát ra ở màn cài đặt
              phát hành đều im lặng: đo được trên trình duyệt thật — bấm `Hoàn tác` trên
              một đề đã phát hành, BE trả 409, và màn hình không nói một chữ nào.

              Nút ấy nay khoá sẵn khi hết cửa lùi (`form.undo_blocked`), nên đường này
              chỉ còn chở những lỗi không đoán trước được — mạng hỏng, một lớp vừa qua
              giờ mở giữa hai lần đọc. Chính vì không đoán trước được mà nó phải nói ra. */}
          {trouble !== null && (
            <div className="trouble" role="alert">
              {trouble}
            </div>
          )}
          {/* `key` theo đề: biểu mẫu khôi phục nháp trong hàm khởi tạo của `useState`,
              nên đổi `assessmentId` mà **không** dựng lại thì sáu ô giữ nguyên giá trị của
              đề cũ — rồi effect ghi nháp (có `assessmentId` trong deps) ghi thẳng chúng
              vào khoá của đề mới. `Panel` sống qua một lần đổi id, nên đường ấy đi được
              thật: mở một đề khác trong khi panel đang mở. */}
          <PublishSettings
            key={assessmentId}
            assessmentId={assessmentId}
            onPublished={onApproved}
            undoing={working}
            onUndo={() => void undo()}
          />
        </>
      ) : (
        <div className="panel-foot">
          <div className="note">{trouble ?? _note(paper.state)}</div>
          {/* Nhánh này nay **chỉ** còn của đề chưa duyệt, nên cái nút thôi phải chọn giữa
            hai nhãn: đề đã khoá thì nhánh trên đã nhận nó. *Hoàn tác* sống ở màn cài đặt
            phát hành — để đường lùi ở cả hai chỗ là một việc có hai chỗ bấm. */}
          <button
            className="cta"
            type="button"
            disabled={working || paper.question_count === 0}
            onClick={() => void approve()}
          >
            Duyệt đề
          </button>
        </div>
      )}

      {solving !== null && (
        <Solution question={solving} onClose={() => setSolving(null)} />
      )}
    </aside>
  );
}

/**
 * Lời giải của một câu, trong một hộp thoại.
 *
 * Mở tại chỗ thì lời giải phải vừa một cột rộng 380, nên hai cách giải và bốn dòng ánh xạ
 * nhiễu không có chỗ đứng — và ánh xạ nhiễu là thứ nói cho giáo viên biết **mỗi phương án
 * sai sai ở đâu**, tức phần đáng đọc nhất. Figma vẽ hộp này rộng 680 (`Solution dialog`
 * `309:41`, artboard `309:1415`); đây là bản dựng của nó.
 *
 * @param question - Câu hỏi, kèm phương án và lời giải.
 * @param onClose - Đóng hộp.
 */
function Solution({
  question,
  onClose,
}: {
  question: TeacherQuestion;
  onClose: () => void;
}) {
  return (
    <Veil onClose={onClose} wide>
      <div className="solution-head">
        <h3>Lời giải — Câu {question.order}</h3>
        <button className="close" type="button" onClick={onClose}>
          Đóng
        </button>
      </div>

      <div className="solution-stem">
        <MathText>{question.stem}</MathText>
      </div>

      <div className="ways">
        {/* `key` theo thứ tự, không theo tên: hai cách giải trùng tên là chuyện BE cho
            qua, và hai key trùng làm React ghép nhầm hai phần tử. */}
        {question.methods.map((one, index) => (
          <div className="way" key={index}>
            <strong>{one.title}</strong>
            <div className="body">
              <MathText>{one.body}</MathText>
            </div>
          </div>
        ))}
      </div>

      <div className="faults">
        <div className="faults-head">MỖI PHƯƠNG ÁN NHIỄU GẮN MỘT LỖI</div>
        {question.options.map((one) => (
          <div className="fault" key={one.label}>
            <span className={`which ${one.is_correct ? "correct" : ""}`}>
              {one.label}. <MathText>{one.text}</MathText>
            </span>
            <span className="why">
              {one.is_correct ? (
                "✓ đúng"
              ) : (
                <MathText>{one.error_label ?? ""}</MathText>
              )}
            </span>
          </div>
        ))}
      </div>
    </Veil>
  );
}

/**
 * Câu dưới chân panel, một câu cho mỗi trạng thái.
 *
 * **Một** nhánh sống, không ba. Chân panel nay chỉ còn của đề chưa duyệt: `approved` và
 * `published` đều đi vào màn cài đặt phát hành, nên hai câu của chúng không có chỗ nào để
 * in ra nữa. Hàm vẫn nhận `state` và vẫn trả chuỗi rỗng cho hai nấc ấy, để nếu một ngày
 * nhánh kia quay lại thì nó không im lặng một cách tình cờ.
 *
 * @param state - Trạng thái đề, nguyên văn từ BE.
 * @returns Câu để in. Chuỗi rỗng cho `approved` và `published` — đường không tới được.
 */
function _note(state: string): string {
  if (state === "approved" || state === "published") return "";
  return "Bạn duyệt xong mới phát hành được. Học sinh chưa nhìn thấy đề này.";
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
      {tally.bank > 0 && (
        <span className="lead">{tally.bank} câu ngân hàng ·</span>
      )}
      {tally.checked > 0 && (
        <span className="source-chip checked">
          {tally.checked} câu thêm mới đã kiểm
        </span>
      )}
      {tally.unchecked > 0 && (
        <span className="source-chip unchecked">
          {tally.unchecked} câu chưa kiểm
        </span>
      )}
    </div>
  );
}

/**
 * Một câu hỏi trong panel.
 *
 * Nút lời giải mở một **hộp thoại**, không mở tại chỗ. *"Lời giải · 2 cách"* vẫn đọc được
 * ngay khi chưa mở, và con số đó là `methods.length` — nó đi kèm trong cùng một response,
 * nên một panel mười thẻ không phải gọi mười request chỉ để đếm.
 *
 * @param question - Câu hỏi, kèm phương án và lời giải.
 * @param editable - Đề còn sửa được hay không. Tới từ `state`, không từ một phép so sánh
 *   ở đây.
 * @param onSolve - Xin mở lời giải của câu này.
 * @param onSave - Gửi bản vừa sửa đi. Trả về chuỗi rỗng khi BE nhận, hoặc lời từ chối để
 *   thẻ hiện ngay tại chỗ — ô nhập **không** đóng lại khi bị từ chối, vì đóng là mất chữ
 *   giáo viên vừa gõ.
 */
function QuestionCard({
  question,
  editable,
  onSolve,
  onSave,
}: {
  question: TeacherQuestion;
  editable: boolean;
  onSolve: () => void;
  onSave: (edited: QuestionEdit) => Promise<string>;
}) {
  const source = provenanceOf(question.question_id);
  const [editing, setEditing] = useState<QuestionEdit | null>(null);
  const [refused, setRefused] = useState("");
  const [saving, setSaving] = useState(false);

  if (editing !== null) {
    return (
      <Editing
        question={question}
        source={source}
        draft={editing}
        refused={refused}
        saving={saving}
        onChange={setEditing}
        onCancel={() => {
          setEditing(null);
          setRefused("");
        }}
        onSave={async () => {
          setSaving(true);
          const wrong = await onSave(editing);
          setSaving(false);
          setRefused(wrong);
          if (!wrong) setEditing(null);
        }}
      />
    );
  }

  return (
    <div className="qcard">
      <div className="top">
        <span className="num">Câu {question.order}</span>
        <span className={`source-chip ${source.tone}`}>{source.label}</span>
        <span className="spacer" />
        {editable && (
          <button
            className="edit"
            type="button"
            onClick={() =>
              setEditing({
                stem: question.stem,
                learning_objective: question.learning_objective,
                options: question.options.map((one) => ({ ...one })),
                methods: question.methods.map((one) => ({ ...one })),
              })
            }
          >
            Sửa
          </button>
        )}
      </div>

      <div className="stem">
        <MathText>{question.stem}</MathText>
      </div>

      <div className="options">
        {question.options.map((one) => (
          <div
            className={`opt ${one.is_correct ? "correct" : ""}`}
            key={one.label}
          >
            {one.label}. <MathText>{one.text}</MathText>
            {one.is_correct && "   ✓"}
          </div>
        ))}
      </div>

      <button className="solution" type="button" onClick={onSolve}>
        <span>Lời giải · {question.methods.length} cách</span>
        <span className="spacer" />
        <span aria-hidden="true">›</span>
      </button>
    </div>
  );
}
