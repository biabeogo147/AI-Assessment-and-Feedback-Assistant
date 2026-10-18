import { useEffect, useState } from "react";

import { teacher, type AssessmentDetail, type PickerRow } from "../../api";
import MathText from "../../MathText";
import Veil from "./Veil";

/**
 * Hộp *Thêm câu từ ngân hàng* (artboard 19b `655:4222`, component `Bank picker` `655:39`), việc 17
 * của plan `question-bank-into-draft`.
 *
 * Mọi câu trong ngân hàng của giáo viên, mới duyệt trước. Ô tìm lọc **tại chỗ** theo đề bài và mục
 * kiến thức: ngân hàng một giáo viên vừa một lần đọc, và lọc qua BE là một request mỗi phím gõ. Câu
 * đã có trong đề đứng mờ và không chọn được (`Bank row`, trạng thái *đã có trong đề*): chép lại là
 * hai câu giống nhau. Câu chọn theo thứ tự bấm, và vào cuối đề theo đúng thứ tự ấy.
 *
 * BE từ chối (đề vừa được duyệt ở tab khác, còn câu đang soạn) thì lời của BE hiện ngay trong hộp,
 * hộp ở lại: đóng là giấu lý do.
 *
 * @param assessmentId - Đề đang mở.
 * @param onClose - Đóng hộp mà không thêm gì.
 * @param onAdded - Câu đã vào đề; nhận lại cả đề BE vừa trả.
 * @param onRefused - BE từ chối: panel đọc lại đề, vì lời từ chối thường nói đề vừa đổi ở nơi khác.
 */
export default function BankPicker({
  assessmentId,
  onClose,
  onAdded,
  onRefused,
}: {
  assessmentId: string;
  onClose: () => void;
  onAdded: (paper: AssessmentDetail) => void;
  onRefused: () => void;
}) {
  const [rows, setRows] = useState<PickerRow[] | null>(null);
  const [trouble, setTrouble] = useState("");
  const [query, setQuery] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState("");

  useEffect(() => {
    let current = true;
    teacher
      .bankPicker(assessmentId)
      .then((found) => {
        if (current) setRows(found.questions);
      })
      .catch((cause: Error) => {
        if (current) setTrouble(cause.message);
      });
    return () => {
      current = false;
    };
  }, [assessmentId]);

  const wanted = fold(query.trim());
  const shown = (rows ?? []).filter(
    (one) =>
      wanted === "" || fold(one.stem).includes(wanted) || fold(one.learning_objective).includes(wanted),
  );

  function toggle(row: PickerRow) {
    if (row.in_this_paper) return;
    setChosen((before) =>
      before.includes(row.bank_id)
        ? before.filter((one) => one !== row.bank_id)
        : [...before, row.bank_id],
    );
  }

  async function add() {
    setRefused("");
    setBusy(true);
    try {
      onAdded(await teacher.addFromBank(assessmentId, chosen));
    } catch (cause) {
      setRefused((cause as Error).message);
      setBusy(false);
      onRefused();
    }
  }

  return (
    <Veil
      className="picker"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <h3>Thêm câu từ ngân hàng</h3>
      <input
        className="picker-search"
        type="search"
        aria-label="Tìm câu trong ngân hàng"
        placeholder="Tìm theo nội dung câu hoặc mục kiến thức…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {rows === null ? (
        <div className="picker-empty" role="status">
          {trouble || "Đang tải…"}
        </div>
      ) : rows.length === 0 ? (
        <div className="picker-empty">Ngân hàng còn trống. Câu vào đây khi bạn duyệt một đề.</div>
      ) : shown.length === 0 ? (
        <div className="picker-empty">Không có câu nào khớp “{query.trim()}”.</div>
      ) : (
        <div className="picker-list" role="list">
          {shown.map((one) => {
            const picked = chosen.includes(one.bank_id);
            return (
              <div role="listitem" key={one.bank_id}>
              <label
                className={`picker-row ${picked ? "chosen" : ""} ${one.in_this_paper ? "taken" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={picked}
                  disabled={one.in_this_paper || busy}
                  onChange={() => toggle(one)}
                />
                <span className="box" aria-hidden="true">
                  {picked ? "✓" : ""}
                </span>
                <span className="text">
                  <span className="stem">
                    <MathText>{one.stem}</MathText>
                  </span>
                  <span className="meta">
                    {one.learning_objective} ·{" "}
                    {one.in_this_paper ? "đã có trong đề này" : one.from_title}
                  </span>
                </span>
              </label>
              </div>
            );
          })}
        </div>
      )}
      {refused !== "" && (
        <p className="refused" role="alert">
          {refused}
        </p>
      )}
      <div className="picker-actions">
        <span className="count">Đã chọn {chosen.length} câu</span>
        <button className="btn ghost" type="button" disabled={busy} onClick={onClose}>
          Đóng
        </button>
        <button
          className="btn primary"
          type="button"
          disabled={busy || chosen.length === 0}
          onClick={() => void add()}
        >
          {chosen.length === 0 ? "Thêm vào đề" : `Thêm ${chosen.length} câu vào đề`}
        </button>
      </div>
    </Veil>
  );
}

/** Chữ để so khi tìm: thường, bỏ dấu -- gõ *"dao ham"* vẫn ra *"Đạo hàm"*. */
function fold(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "d")
    .toLowerCase();
}
