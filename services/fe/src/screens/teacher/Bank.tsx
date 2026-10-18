import { useEffect, useState } from "react";

import { teacher, type BankDetail, type QuestionEdit, type TeacherQuestion } from "../../api";
import { go } from "../../App";
import MathText from "../../MathText";
import { BoardHead, BoardWaiting, useBoard } from "./Board";
import Editing from "./Editing";

/** Sự kiện cửa sổ khi một câu ngân hàng vừa lưu: panel sửa và danh sách là hai component riêng. */
const BANK_SAVED = "kriky:bank-saved";

/**
 * Màn 22 · *Ngân hàng câu hỏi* (`655:5226`), plan `teacher-rail-screens`, việc 18.
 *
 * Mọi câu trong ngân hàng của giáo viên, mới duyệt trước. Bấm một câu là mở panel sửa bên phải (màn
 * 22b, `BankEditor`); câu đang mở sáng lên.
 *
 * @param open - Câu đang mở trong panel, nếu có.
 */
export default function Bank({ open = null }: { open?: string | null }) {
  const { data, trouble, setData } = useBoard(() => teacher.bank(), "bank");

  // Panel sửa (22b) lưu xong thì danh sách đọc lại, để chữ mới hiện ngay ở cột trái.
  useEffect(() => {
    const reread = () => void teacher.bank().then(setData, () => undefined);
    window.addEventListener(BANK_SAVED, reread);
    return () => window.removeEventListener(BANK_SAVED, reread);
  }, [setData]);

  if (data === null) {
    return (
      <div className="board">
        <BoardHead title="Ngân hàng câu hỏi" sub="" />
        <BoardWaiting trouble={trouble} />
      </div>
    );
  }

  return (
    <div className="board">
      <BoardHead
        title="Ngân hàng câu hỏi"
        sub={`${data.questions.length} câu · từ ${data.approvals} lần duyệt đề`}
      />
      <div className="board-table bank fill" role="table">
        <div className="board-row head" role="row">
          <span>CÂU HỎI</span>
          <span>MỤC KIẾN THỨC</span>
          <span>KHỐI / MÔN</span>
          <span />
        </div>
        {data.questions.length === 0 && (
          <div className="board-row empty" role="row">
            Ngân hàng còn trống. Câu vào đây khi bạn duyệt một đề.
          </div>
        )}
        {data.questions.map((one) => (
          <div
            className={`board-row open-able ${open === one.bank_id ? "chosen" : ""}`}
            role="row"
            key={one.bank_id}
            tabIndex={0}
            onClick={() => go(`/teacher/ngan-hang/${one.bank_id}`)}
            onKeyDown={(event) => {
              if (event.key === "Enter") go(`/teacher/ngan-hang/${one.bank_id}`);
            }}
          >
            <span className="name">
              <MathText>{one.stem}</MathText>
            </span>
            <span className="cell-muted">{one.learning_objective}</span>
            <span className="cell-muted">{one.course}</span>
            <span className="chevron" aria-hidden="true">
              ›
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Panel phải của màn 22b (`666:5816`): sửa **bản trong ngân hàng** của một câu.
 *
 * Dùng lại thẻ sửa ba tầng của panel đề (`Editing`), để một câu sửa ở hai nơi theo cùng một cách.
 * Chỉ bản ngân hàng đổi; câu đã nằm trong đề đã phát hành giữ nguyên, và chân panel nói đúng điều ấy
 * (người dùng chốt 18/10/2026).
 *
 * @param bankId - Câu nào.
 */
export function BankEditor({ bankId }: { bankId: string }) {
  const [found, setFound] = useState<BankDetail | null>(null);
  const [draft, setDraft] = useState<QuestionEdit | null>(null);
  const [refused, setRefused] = useState("");
  const [saving, setSaving] = useState(false);
  const [trouble, setTrouble] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    setFound(null);
    setDraft(null);
    setRefused("");
    teacher
      .bankQuestion(bankId)
      .then((one) => {
        if (!current) return;
        setFound(one);
        setDraft(asEdit(one));
      })
      .catch((cause: Error) => {
        if (current) setTrouble(cause.message);
      });
    return () => {
      current = false;
    };
  }, [bankId]);

  async function save() {
    if (draft === null) return;
    setSaving(true);
    setRefused("");
    try {
      const saved = await teacher.editBankQuestion(bankId, draft);
      setFound(saved);
      setDraft(asEdit(saved));
      window.dispatchEvent(new Event(BANK_SAVED));
    } catch (cause) {
      setRefused((cause as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <aside className="panel bank-editor">
      <div className="panel-head">
        <div className="title-row">
          <h2>Sửa câu trong ngân hàng</h2>
          <button className="close" type="button" onClick={() => go("/teacher/ngan-hang")}>
            Đóng
          </button>
        </div>
        <div className="meta">
          {found === null ? "" : [found.learning_objective, found.course].join(" · ")}
        </div>
      </div>
      <div className="panel-questions">
        {found === null || draft === null ? (
          <div className="panel-empty">{trouble ?? "Đang tải…"}</div>
        ) : (
          <Editing
            question={asQuestion(found)}
            title="Câu trong ngân hàng"
            draft={draft}
            refused={refused}
            saving={saving}
            onChange={setDraft}
            onCancel={() => go("/teacher/ngan-hang")}
            onSave={() => void save()}
          />
        )}
      </div>
      <div className="panel-foot">
        <div className="note">
          Chỉ sửa bản trong ngân hàng. Câu đã nằm trong đề đã phát hành không đổi; đề sau lấy câu này
          sẽ dùng bản mới.
        </div>
      </div>
    </aside>
  );
}

function asEdit(one: BankDetail): QuestionEdit {
  return {
    stem: one.stem,
    learning_objective: one.learning_objective,
    options: one.options.map((option) => ({ ...option })),
    methods: one.methods.map((method) => ({ ...method })),
  };
}

/** Hình dạng `Editing` cần: một câu, không vị trí trong đề nào. */
function asQuestion(one: BankDetail): TeacherQuestion {
  return {
    question_id: one.bank_id,
    order: 0,
    stem: one.stem,
    learning_objective: one.learning_objective,
    options: one.options,
    methods: one.methods,
    in_bank: true,
    source: "bank",
  };
}
