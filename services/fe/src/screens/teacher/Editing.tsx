import { useId, useState } from "react";

import { type QuestionEdit, type TeacherQuestion } from "../../api";

/**
 * Thẻ câu hỏi lúc **đang sửa**, và những gì chỉ nó dùng.
 *
 * Tách khỏi `Panel.tsx` ngày 06/10/2026, và lý do là **ranh giới** chứ không phải độ
 * dài: `Panel` là một panel ba khối đọc `state` rồi vẽ, còn đây là một biểu mẫu hai mươi
 * ô với state tầng riêng, luật ADR-18 riêng, và một bộ helper không ai ngoài nó gọi.
 * `Panel.tsx` dài 852 dòng trước lần tách này.
 */
/**
 * Ký tự điều khiển **không bao giờ** có nghĩa trong chữ của một câu hỏi.
 *
 * Trừ đúng hai cái: `\n` (`0x0A`) và `\r` (`0x0D`) là xuống dòng thật, và lời giải nào
 * cũng có chúng. Gộp cả hai vào đây thì mọi ô lời giải mọc một cảnh báo, và một cảnh báo
 * luôn hiện là một cảnh báo không ai đọc.
 */
const MANGLED = /[\u0000-\u0009\u000b\u000c\u000e-\u001f\u007f]/g;

/**
 * In lại một chuỗi với ký tự điều khiển thay bằng ký hiệu nhìn thấy được.
 *
 * **Chuỗi trong ô nhập không được đổi.** Nếu đổi, ký hiệu sẽ theo nút Lưu xuống database
 * và một lỗi hiển thị thành một lỗi dữ liệu. Chỗ này chỉ dựng một bản để đọc.
 *
 * Khối *Control Pictures* của Unicode đặt ký hiệu của ký tự `c` tại `U+2400 + c`, trừ
 * `DEL` nằm riêng ở `U+2421`.
 *
 * @param text - Chuỗi gốc, nguyên byte.
 * @returns Bản để đọc: `0x0C` thành `␌`, `0x09` thành `␉`.
 */
function visible(text: string): string {
  return text.replace(MANGLED, (one) => {
    const code = one.charCodeAt(0);
    return String.fromCharCode(code === 0x7f ? 0x2421 : 0x2400 + code);
  });
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
  namedBy,
}: {
  className: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
  namedBy?: string;
}) {
  const noteId = useId();
  const boxId = useId();
  const fit = (node: HTMLTextAreaElement | null) => {
    if (node === null) return;
    node.style.height = "auto";
    // Cộng phần viền. `box-sizing: border-box` tính chiều cao kể cả viền, còn
    // `scrollHeight` thì không — đặt thẳng `scrollHeight` làm ô hụt đúng 2px, và dòng cuối
    // mất phần chân chữ. Đo được: `scrollHeight` 78 trong một ô `clientHeight` 76.
    const frame = node.offsetHeight - node.clientHeight;
    node.style.height = `${node.scrollHeight + frame}px`;
  };

  const hidden = value.match(MANGLED)?.length ?? 0;

  return (
    // Fragment chứ không bọc `<div>`: các khối chứa ô này đều là cột flex, và một lớp
    // bọc sẽ cướp mất chỗ flex item. Dòng cảnh báo tự xuống hàng bằng `flex-basis: 100%`.
    <>
      {/* Nhãn **nhìn thấy được**, không chỉ `aria-label`.
          Bản phẳng có hai mươi ô nhập và **không** nhãn nào trên màn: trình đọc màn hình
          biết ô nào là ô nào, còn mắt thì không — đo được ngày 06/10/2026, và nó là một
          trong ba lý do đo được của việc vẽ lại màn này.
          `namedBy` cho chỗ gọi nói rằng ô này **đã** có một nhãn nhìn thấy được ở nơi
          khác — chữ `Phương án B` trên hàng đầu của khối, hay tên tầng đang mở. In thêm
          một nhãn thứ hai ngay dưới nó là lặp lại cùng một chữ hai lần trong một cột
          420px. Không ô nào được sống bằng `aria-label` trần. */}
      {namedBy === undefined && (
        <label className="field-label" htmlFor={boxId}>
          {label}
        </label>
      )}
      <textarea
        id={boxId}
        className={className}
        aria-labelledby={namedBy}
        aria-describedby={hidden > 0 ? noteId : undefined}
        ref={fit}
        rows={1}
        value={value}
        onChange={(event) => {
          fit(event.currentTarget);
          onChange(event.target.value);
        }}
      />
      {hidden > 0 && (
        <div className="mangled" id={noteId}>
          {/* Không `role="status"`: vùng sống sẽ đọc lại cả dòng này sau **mỗi** phím gõ.
              Buộc vào ô bằng `aria-describedby` thì nó được đọc đúng một lần, lúc vào ô. */}
          <span className="mangled-head">
            {hidden} ký tự hỏng, không nhìn thấy được trong ô:
          </span>{" "}
          <span className="mangled-body">{visible(value)}</span>
        </div>
      )}
    </>
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

/**
 * Ba tầng của thẻ đang sửa, và tầng nào đang mở.
 *
 * `stem` lúc vào màn: bấm `Sửa` thường là vì đọc thấy một chữ sai trong đề bài, và tầng
 * ấy cũng là tầng nhẹ nhất nên nó không bao giờ bắt ai cuộn ngay cú bấm đầu tiên.
 */
type Tang = "stem" | "options" | "methods";

/**
 * Một thanh đầu tầng: mũi nhọn, tên tầng, và một câu tóm đếm từ **bản đang gõ**.
 *
 * Câu tóm đếm từ `draft` chứ không từ `question`: nó phải đổi theo cái giáo viên vừa gõ,
 * nếu không thì nó là một con số của một phút trước nằm ngay trên chỗ đang sửa.
 *
 * Dùng lại đúng từ vựng của tấm trượt phát hành — `<button>` mang `aria-expanded`, mũi
 * nhọn **quay** chứ không đổi sang ký tự khác. Một hình xoay thì mắt theo được nó.
 *
 * @param open - Tầng này đang mở.
 * @param id - Id của phần chữ, để các ô bên trong trỏ `aria-labelledby` về.
 * @param label - Tên tầng.
 * @param summary - Câu tóm, hoặc chuỗi rỗng.
 * @param onToggle - Bấm vào thanh.
 */
function TangHead({
  open,
  id,
  label,
  summary,
  onToggle,
}: {
  open: boolean;
  id: string;
  label: string;
  summary: string;
  onToggle: () => void;
}) {
  return (
    <button
      className="tang-head"
      type="button"
      aria-expanded={open}
      onClick={onToggle}
    >
      <svg className="caret" viewBox="0 0 8 6" aria-hidden="true">
        <path d="M0 0h8L4 6z" fill="currentColor" />
      </svg>
      <span className="label" id={id}>
        {label}
      </span>
      {summary !== "" && <span className="summary">{summary}</span>}
    </button>
  );
}

export default function Editing({
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
  const [tang, setTang] = useState<Tang>("stem");
  const heads = useId();

  // Phương án nhiễu nào chưa có nhãn lỗi. Tính ở đây chứ không trong `onChange` của
  // radio: nó là một tính chất của **cả bộ phương án** tại mỗi lúc, không phải hậu quả
  // của riêng một cú bấm — thêm một phương án mới cũng rơi vào đúng trạng thái này.
  const missing = draft.options
    .filter((one) => !one.is_correct && (one.error_label ?? "").trim() === "")
    .map((one) => one.label);

  const right = draft.options.find((one) => one.is_correct);

  /** Id của chữ trên thanh đầu một tầng, để ô bên trong mượn làm tên. */
  const headId = (which: Tang) => `${heads}-${which}`;

  /**
   * Mở một tầng, và **thu tầng đang mở**.
   *
   * Một lúc một tầng, và đó là cả luật chứ không phải một sở thích: chiều cao thẻ bị
   * chặn trên bởi tầng nặng nhất, nên nó không vượt khung `panel-questions` được. Đo
   * ngày 06/10/2026 ở density Teacher: bản phẳng **774** trong một khung **658** — tức
   * sửa một câu là chắc chắn không thấy hết thẻ đang gõ, kể cả khi đề chỉ có một câu.
   * Ba tầng cho 226 / 647 / 363. Cho phép mở cả ba là trả về đúng 774.
   */
  function openOnly(which: Tang): void {
    setTang(which);
  }

  return (
    <div className="qcard editing">
      <div className="top">
        <span className="num">Câu {question.order}</span>
        <span className={`source-chip ${source.tone}`}>{source.label}</span>
        <span className="spacer" />
        <span className="edit-mark">Đang sửa</span>
      </div>

      <div className="tang">
        <TangHead
          open={tang === "stem"}
          id={headId("stem")}
          label="Đề bài"
          summary=""
          onToggle={() => openOnly("stem")}
        />
        {tang === "stem" && (
          <div className="tang-body">
            <Field
              className="field stem"
              label="Đề bài"
              namedBy={headId("stem")}
              value={draft.stem}
              onChange={(next) => onChange({ ...draft, stem: next })}
            />
          </div>
        )}
      </div>

      <div className="tang">
        <TangHead
          open={tang === "options"}
          id={headId("options")}
          label="Phương án"
          summary={`· ${draft.options.length}${right ? ` · đúng: ${right.label}` : ""}`}
          onToggle={() => openOnly("options")}
        />
        {tang === "options" && (
          <div className="tang-body">
            {draft.options.map((one, index) => (
              <Option
                key={one.label}
                one={one}
                index={index}
                questionId={question.question_id}
                draft={draft}
                saving={saving}
                onChange={onChange}
              />
            ))}

            <button
              className="add"
              type="button"
              disabled={saving}
              onClick={() =>
                onChange({ ...draft, options: [...draft.options, blankOption(draft)] })
              }
            >
              + Thêm phương án
            </button>
          </div>
        )}
      </div>

      <div className="tang">
        <TangHead
          open={tang === "methods"}
          id={headId("methods")}
          label="Cách giải"
          summary={`· ${draft.methods.length}`}
          onToggle={() => openOnly("methods")}
        />
        {tang === "methods" && (
          <div className="tang-body">
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
                  {/* ADR-18 đòi **hơn một** lời giải: một câu một cách giải dạy được một
                      lối nghĩ, và cả việc này sinh ra là để dạy nhiều lối. */}
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
          </div>
        )}
      </div>

      {/* **Hai lời từ chối đứng NGOÀI ba tầng**, cạnh hàng nút.
          Một lời từ chối nằm trong một tầng đã thu là một lời không ai đọc được — mà nút
          `Lưu` vẫn khoá theo nó, nên màn hình sẽ khoá mà không nói vì sao. Đây là cùng
          một lý lẽ với hộp cảnh báo của biểu mẫu phát hành: nói bằng tiếng Việt, trước
          cú bấm.
          ADR-18 bắt mọi phương án nhiễu có nhãn lỗi, và đổi đáp án đúng biến phương án
          cũ thành một phương án nhiễu — mà nó thường chưa có nhãn, vì BE ghi `null` ở
          đúng dòng đáp án đúng. Để nó đi tới BE thì lời từ chối về là
          `distractors ['A'] carry no error label: <cả đề bài>`: tiếng Anh, kèm `repr` của
          một list Python, kèm nguyên văn câu hỏi. */}
      {missing.length > 0 && (
        <div className="refused">
          {missing.length === 1
            ? `Phương án ${missing[0]} chưa có nhãn lỗi. ADR-18 bắt mọi phương án nhiễu phải có.`
            : `Các phương án ${missing.join(", ")} chưa có nhãn lỗi. ADR-18 bắt mọi phương án nhiễu phải có.`}
        </div>
      )}

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
          disabled={saving || missing.length > 0}
          onClick={onSave}
        >
          Lưu
        </button>
      </div>
    </div>
  );
}

/**
 * Một phương án: hàng nhãn, ô chữ, và ô nhãn lỗi thụt vào dưới nó.
 *
 * Tách thành component riêng vì nó là chỗ **duy nhất** của thẻ có một luật riêng — đúng
 * một đáp án đúng, và mọi phương án nhiễu kèm nhãn lỗi (ADR-18) — chứ không phải vì nó
 * dài.
 *
 * Vỏ của nó (nền chìm, viền) là thứ chữa lỗi đo được của bản phẳng: ở bản ấy ba ô của
 * một phương án chỉ tách khỏi phương án kế tiếp bằng chênh lệch **4px so với 8px**, nên
 * thứ duy nhất nói "ba ô này thuộc cùng một phương án" là một khoảng trắng 4 pixel.
 *
 * @param one - Phương án này.
 * @param index - Chỗ của nó trong `draft.options`.
 * @param questionId - Để nhóm radio theo câu, không theo trang.
 * @param draft - Bản đang gõ.
 * @param saving - Đang gửi.
 * @param onChange - Bản gõ vừa đổi.
 */
function Option({
  one,
  index,
  questionId,
  draft,
  saving,
  onChange,
}: {
  one: QuestionEdit["options"][number];
  index: number;
  questionId: string;
  draft: QuestionEdit;
  saving: boolean;
  onChange: (next: QuestionEdit) => void;
}) {
  const tagId = useId();

  return (
    <div className="edit-option">
      <div className="edit-option-head">
        {/* **Đổi được đáp án đúng.** Trước đợt này phương án đúng chỉ có một cái nhãn và
            không control nào — nên thứ duy nhất hỏng ở một câu model soạn sai lại là thứ
            duy nhất giáo viên không sửa được. Đo được: một câu có đáp án đúng là 1/2,
            bốn phương án không chứa 1/2, và 1/3 đang đeo dấu đúng. Cổng người thứ nhất
            của ADR-05 hở đúng chỗ ấy.

            Radio chứ không phải nút *Đặt làm đáp án đúng*: nó là **một cú bấm** để
            chuyển, và cả nhóm đọc ra như một lựa chọn duy nhất thay vì bốn nút rời.
            Nhưng nó **không tự** giữ ADR-18 — `checked` đi từ state nên nhóm radio của
            trình duyệt không quyết gì cả; thứ bỏ cờ cũ là `onChange` ngay dưới, và một
            đột biến ở đó làm payload ra hai đáp án đúng. `name` theo `question_id` để
            hai thẻ mở cùng lúc không nằm chung một nhóm. */}
        <input
          type="radio"
          className="right-mark"
          name={`correct-${questionId}`}
          checked={one.is_correct}
          disabled={saving}
          aria-label={`Đặt phương án ${one.label} làm đáp án đúng`}
          onChange={() =>
            onChange({
              ...draft,
              // **Chỉ đổi cờ, không đụng tới chữ.** Bản đầu xoá `error_label` của phương
              // án vừa thành đúng, với lý lẽ "payload phải sạch". Lý lẽ sai: `OptionEdit`
              // ở BE nói thẳng rằng nhãn gửi kèm đáp án đúng **bị bỏ, không bị từ chối**,
              // và `models.py` tự đặt `null` ở đúng dòng ấy.
              //
              // Và cái xoá ấy không khôi phục được: A→B xoá nhãn của B, bấm nhầm rồi bấm
              // lại là mất **cả hai** nhãn giáo viên đã gõ tay, không có undo. Giữ chữ
              // lại thì một lần bấm nhầm chỉ tốn một lần bấm nữa.
              options: draft.options.map((other, at) => ({
                ...other,
                is_correct: at === index,
              })),
            })
          }
        />
        {/* Chữ này **là** nhãn của ô ngay dưới, nên ô ấy mượn nó qua `aria-labelledby`
            thay vì in thêm một nhãn thứ hai cùng nội dung.
            Và nó tách làm hai phần có lý do: chỉ phần **tên** nằm trong `tagId`. Gộp cả
            `· đáp án đúng` vào tên thì tên của một ô nhập đổi mỗi lần giáo viên bấm một
            radio ở hàng khác — một ô không được đổi tên vì một thứ ngoài nó. Phần sau là
            **trạng thái**, và trạng thái đã có `aria-checked` của chính nhóm radio. */}
        <span className={one.is_correct ? "tag right" : "tag"}>
          <span id={tagId}>Phương án {one.label}</span>
          {one.is_correct && <span className="right-note"> · đáp án đúng</span>}
        </span>
        <span className="spacer" />
        {/* Đáp án **đúng** không có nút xoá. Xoá nó là bỏ luật tính điểm của câu, và việc
            ấy cần một quyết định riêng về những lượt đã làm — khác hẳn việc sửa chữ. Và
            dưới hai phương án thì câu không còn là một câu trắc nghiệm, nên nút biến mất
            ở đó luôn thay vì để bấm rồi nhận một lời từ chối. */}
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
        namedBy={tagId}
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

      {/* Nhãn lỗi là **bắt buộc** với mọi phương án nhiễu (ADR-18), nên nó phải có ô để
          gõ. Bản trước không có, nên thêm một phương án là tạo ra một câu chắc chắn bị từ
          chối: một nút dẫn thẳng tới một lần 422.
          Thụt vào dưới chữ phương án, vì nó là **chú thích của phương án ngay trên nó**,
          không phải một trường ngang hàng. */}
      {!one.is_correct && (
        <div className="edit-fault">
          <Field
            className="field fault"
            label={`Lỗi của ${one.label}`}
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
        </div>
      )}
    </div>
  );
}
