import { useEffect, useState } from "react";

import {
  teacher,
  type AssessmentDetail,
  type QuestionEdit,
  type TeacherQuestion,
} from "../../api";
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
 * @param assessmentId - Đề nào.
 * @param publishing - Đang ở màn cài đặt phát hành. Nó tới từ route, nên một lần F5 giữa lúc
 *   điền sáu tham số vẫn mở lại đúng biểu mẫu — còn những gì đã gõ thì mất, và đó là đúng:
 *   ADR-02 nói biểu mẫu **không gợi sẵn giờ nào**, kể cả giờ của chính người vừa gõ.
 * @param onClose - Đóng panel, quay về đoạn chat.
 * @param onApproved - Dòng lượt nói phải đọc lại. Gọi sau **cả ba** việc ghi của panel:
 *   duyệt, bỏ duyệt, và phát hành — cả ba đều để lại một biên bản trong đoạn chat.
 * @param onPublish - Mở biểu mẫu phát hành. Panel không tự mở được: `publishing` tới từ
 *   route, nên việc mở là một cú điều hướng của màn hình bao ngoài.
 *   `approve` ghi một bước vào hội thoại (ADR-01 đòi thế), và bước đó phải hiện ra.
 */
export default function Panel({
  assessmentId,
  publishing,
  onClose,
  onApproved,
  onPublish,
}: {
  assessmentId: string;
  publishing: boolean;
  onClose: () => void;
  onApproved: () => void;
  onPublish: () => void;
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
      // Duyệt xong là **sang thẳng** cài đặt phát hành. Trước đó cú bấm này chỉ đổi chân
      // panel thành hai nút rồi đứng im — một chặng dừng không có việc gì của riêng nó,
      // và giáo viên phải bấm thêm một lần nữa để tới đúng chỗ họ đang đi tới.
      onPublish();
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

  // **Ba** trạng thái, không hai. Gộp `published` vào `approved` là cách nút `Hoàn tác`
  // hiện ra cho một đề đã tới tay học sinh — và `POST .../unapprove` chỉ nhận đúng
  // `APPROVED`, nên cú bấm ấy chắc chắn trả 409. Đó đúng là khuyết điểm mà đợt này đi
  // sửa, chỉ dịch sang một trạng thái khác: một chỉ dẫn trên màn hình trỏ tới một hành
  // động không làm được. Đường lùi của một đề đã phát hành là **thu hồi**, không phải bỏ
  // duyệt.
  const locked = paper.state === "approved" || paper.state === "published";
  const released = paper.state === "published";

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

      {publishing && locked ? (
        <PublishSettings
          assessmentId={assessmentId}
          onPublished={onApproved}
          undoing={working}
          onUndo={() => void undo()}
        />
      ) : (
        <div className="panel-foot">
          <div className="note">{trouble ?? _note(paper.state)}</div>
          {/* Một nút, không hai. *Hoàn tác* sống ở màn cài đặt phát hành, vì duyệt xong
            là sang thẳng màn ấy — để đường lùi ở cả hai chỗ là một việc có hai chỗ bấm.
            Chân panel ở trạng thái đã duyệt chỉ còn một việc: mở lại màn 7. */}
          <button
            className="cta"
            type="button"
            disabled={working || paper.question_count === 0}
            onClick={() => (locked ? onPublish() : void approve())}
          >
            {released
              ? "Phát hành thêm lớp"
              : locked
                ? "Phát hành đề"
                : "Duyệt đề"}
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
 * Ba, không hai. Một đề **đã phát hành** không nói được câu của một đề mới duyệt: nội dung
 * vẫn khoá, nhưng đường mở lại không còn là bỏ duyệt — nó là thu hồi, vì đề đã ra khỏi tay
 * giáo viên.
 *
 * @param state - Trạng thái đề, nguyên văn từ BE.
 * @returns Câu để in, hoặc câu của trạng thái chưa duyệt khi state lạ.
 */
function _note(state: string): string {
  if (state === "published") {
    return "Đề đã tới học sinh. Muốn sửa thì thu hồi khỏi mọi lớp trước.";
  }
  if (state === "approved") {
    return "Nội dung đã khoá. Muốn sửa một câu thì hoàn tác trước.";
  }
  return "Bạn duyệt xong mới phát hành được. Học sinh chưa nhìn thấy đề này.";
}

/**
 * Một ô soạn **tự giãn theo nội dung**.
 *
 * Một chiều cao cố định nhốt lời giải lại và mọc một thanh cuộn **bên trong ô** — đo được:
 * hai ô lời giải có `scrollHeight` 78 và 95 trong một ô cao 45, tức giáo viên phải cuộn
 * trong một ô để đọc thứ mình đang gõ. Đó là chỗ khó dùng nhất của cả màn này.
 *
 * Cao lại theo `scrollHeight` sau mỗi lần gõ, và một lần lúc gắn vào DOM — chữ có sẵn khi
 * mở ô ra cũng phải vừa.
 *
 * @param className - Lớp CSS, để ô đề bài có chiều cao tối thiểu riêng.
 * @param label - Nhãn cho trình đọc màn hình.
 * @param value - Chữ đang có.
 * @param onChange - Chữ vừa đổi.
 */
function Field({
  className,
  label,
  value,
  onChange,
}: {
  className: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
}) {
  const fit = (node: HTMLTextAreaElement | null) => {
    if (node === null) return;
    node.style.height = "auto";
    // Cộng phần viền. `box-sizing: border-box` tính chiều cao kể cả viền, còn
    // `scrollHeight` thì không — đặt thẳng `scrollHeight` làm ô hụt đúng 2px, và dòng cuối
    // mất phần chân chữ. Đo được: `scrollHeight` 78 trong một ô `clientHeight` 76.
    const frame = node.offsetHeight - node.clientHeight;
    node.style.height = `${node.scrollHeight + frame}px`;
  };

  return (
    <textarea
      className={className}
      aria-label={label}
      ref={fit}
      rows={1}
      value={value}
      onChange={(event) => {
        fit(event.currentTarget);
        onChange(event.target.value);
      }}
    />
  );
}

/**
 * Thẻ câu hỏi lúc đang sửa — bản dựng của component `Question card — đang sửa` (`468:2050`).
 *
 * Mỗi ô là một `textarea` chứ không phải một ô nhập một dòng: đề bài và lời giải xuống
 * dòng được, và một ô một dòng biến một lời giải ba bước thành một dải chữ cuộn ngang.
 *
 * Chữ gõ ở đây là **LaTeX nguồn**, không phải công thức đã dựng hình. Sửa cái đã dựng hình
 * thì cần một trình soạn công thức, và đó là một việc khác hẳn; sửa nguồn thì giáo viên
 * thấy đúng thứ sẽ được lưu, và thứ ấy đúng là thứ `validate_question` sẽ kiểm.
 *
 * @param question - Câu hỏi gốc, để lấy số câu.
 * @param source - Chip nguồn câu hỏi. Nó **ở lại** lúc đang sửa: biết câu này lấy từ đâu là
 *   thứ cần nhất đúng lúc đang sửa nó, không phải thứ bỏ đi được.
 * @param draft - Bản đang gõ.
 * @param refused - Lời từ chối của BE, hoặc chuỗi rỗng.
 * @param saving - Đang gửi; hai nút phải khoá để không lưu hai lần.
 * @param onChange - Bản gõ vừa đổi.
 * @param onCancel - Bỏ, quay về thẻ chỉ đọc.
 * @param onSave - Gửi đi.
 */
/**
 * Một phương án nhiễu mới, với nhãn chữ cái còn trống đầu tiên.
 *
 * Nhãn là **khoá** của phương án trong câu: cột có `UniqueConstraint(question_id, label)`,
 * nên trùng nhãn ra 500 chứ không ra một lời từ chối đọc được. Lấy chữ cái trống đầu tiên
 * chứ không lấy "chữ sau chữ lớn nhất": xoá B rồi thêm lại sẽ cho ra B, không cho ra E.
 *
 * @param draft - Bản đang gõ, để biết nhãn nào đã dùng.
 * @returns Phương án mới, chưa có chữ và chưa có nhãn lỗi.
 */
function blankOption(draft: QuestionEdit): QuestionEdit["options"][number] {
  const used = new Set(draft.options.map((one) => one.label));
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const free = [...letters].find((one) => !used.has(one)) ?? "?";
  return { label: free, text: "", is_correct: false, error_label: "" };
}

function Editing({
  question,
  source,
  draft,
  refused,
  saving,
  onChange,
  onCancel,
  onSave,
}: {
  question: TeacherQuestion;
  source: { tone: string; label: string };
  draft: QuestionEdit;
  refused: string;
  saving: boolean;
  onChange: (next: QuestionEdit) => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  return (
    <div className="qcard editing">
      <div className="top">
        <span className="num">Câu {question.order}</span>
        <span className={`source-chip ${source.tone}`}>{source.label}</span>
        <span className="spacer" />
        <span className="edit-mark">Đang sửa</span>
      </div>

      <Field
        className="field stem"
        label="Đề bài"
        value={draft.stem}
        onChange={(next) => onChange({ ...draft, stem: next })}
      />

      {draft.options.map((one, index) => (
        <div className="edit-option" key={one.label}>
          <div className="edit-option-head">
            <span className={one.is_correct ? "tag right" : "tag"}>
              {one.is_correct ? `${one.label} · đáp án đúng` : `Phương án ${one.label}`}
            </span>
            <span className="spacer" />
            {/* Đáp án **đúng** không có nút xoá. Xoá nó là bỏ luật tính điểm của câu, và
                việc ấy cần một quyết định riêng về những lượt đã làm — khác hẳn việc sửa
                chữ. Và dưới hai phương án thì câu không còn là một câu trắc nghiệm, nên
                nút biến mất ở đó luôn thay vì để bấm rồi nhận một lời từ chối. */}
            {!one.is_correct && draft.options.length > 2 && (
              <button
                className="quiet"
                type="button"
                disabled={saving}
                onClick={() =>
                  onChange({
                    ...draft,
                    options: draft.options.filter((_, at) => at !== index),
                  })
                }
              >
                Xoá
              </button>
            )}
          </div>

          <Field
            className="field"
            label={`Phương án ${one.label}`}
            value={one.text}
            onChange={(next) =>
              onChange({
                ...draft,
                options: draft.options.map((other, at) =>
                  at === index ? { ...other, text: next } : other,
                ),
              })
            }
          />

          {/* Nhãn lỗi là **bắt buộc** với mọi phương án nhiễu (ADR-18), nên nó phải có ô
              để gõ. Bản trước không có, nên thêm một phương án là tạo ra một câu chắc
              chắn bị từ chối: một nút dẫn thẳng tới một lần 422. */}
          {!one.is_correct && (
            <Field
              className="field fault"
              label={`Lỗi của phương án ${one.label}`}
              value={one.error_label ?? ""}
              onChange={(next) =>
                onChange({
                  ...draft,
                  options: draft.options.map((other, at) =>
                    at === index ? { ...other, error_label: next } : other,
                  ),
                })
              }
            />
          )}
        </div>
      ))}

      <button
        className="add"
        type="button"
        disabled={saving}
        onClick={() => onChange({ ...draft, options: [...draft.options, blankOption(draft)] })}
      >
        + Thêm phương án
      </button>

      {draft.methods.map((one, index) => (
        <div className="edit-method" key={index}>
          <div className="edit-method-head">
            <Field
              className="field title"
              label={`Tên cách giải ${index + 1}`}
              value={one.title}
              onChange={(next) =>
                onChange({
                  ...draft,
                  methods: draft.methods.map((other, at) =>
                    at === index ? { ...other, title: next } : other,
                  ),
                })
              }
            />
            {/* ADR-18 đòi **hơn một** lời giải: một câu một cách giải dạy được một lối
                nghĩ, và cả việc này sinh ra là để dạy nhiều lối. */}
            {draft.methods.length > 2 && (
              <button
                className="quiet"
                type="button"
                disabled={saving}
                onClick={() =>
                  onChange({
                    ...draft,
                    methods: draft.methods.filter((_, at) => at !== index),
                  })
                }
              >
                Xoá
              </button>
            )}
          </div>

          <Field
            className="field"
            label={`Lời giải ${index + 1}`}
            value={one.body}
            onChange={(next) =>
              onChange({
                ...draft,
                methods: draft.methods.map((other, at) =>
                  at === index ? { ...other, body: next } : other,
                ),
              })
            }
          />
        </div>
      ))}

      <button
        className="add"
        type="button"
        disabled={saving}
        onClick={() =>
          onChange({
            ...draft,
            methods: [...draft.methods, { title: "", body: "" }],
          })
        }
      >
        + Thêm cách giải
      </button>

      {refused !== "" && <div className="refused">{refused}</div>}

      <div className="edit-actions">
        <button
          className="quiet"
          type="button"
          disabled={saving}
          onClick={onCancel}
        >
          Huỷ
        </button>
        <button
          className="cta"
          type="button"
          disabled={saving}
          onClick={onSave}
        >
          Lưu
        </button>
      </div>
    </div>
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
