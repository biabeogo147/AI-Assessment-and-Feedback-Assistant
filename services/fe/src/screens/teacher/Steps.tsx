import { useState } from "react";

/** Một bước Kriky đã làm trong một lượt: một lời gọi tool và kết quả của nó. */
export interface Step {
  /** `done` đã xong, `running` đang chạy, `failed` hỏng. */
  mark: "done" | "running" | "failed";
  /** Việc của bước đó, nói bằng tiếng Việt thường. */
  title: string;
  /** Dòng kết quả, chữ của BE. Rỗng thì không in dòng nào. */
  result: string;
}

/**
 * Khối các bước của một lượt — component `Thinking` (`83:76`) của Figma.
 *
 * **Đây không phải hiệu ứng chờ.** Mô tả component nói thẳng: các bước *chính là bằng chứng*
 * cho biết đề được dựng ra thế nào, nên khối này thu gọn được nhưng không bao giờ mất. Giáo
 * viên đứng trước cổng duyệt cần mở lại được nó để biết câu hỏi từ đâu ra (ADR-05).
 *
 * Ba trạng thái, đúng ba variant của Figma:
 *
 * - đang chạy → mở sẵn, header là việc đang làm kèm `bước k/n`;
 * - đã xong → **tự thu lại** còn một dòng `Đã làm n bước`, bấm chevron mở lại;
 * - thất bại → mở sẵn và **không thu được**. Thu một lỗi lại là giấu lỗi.
 *
 * Luật behavior đầy đủ nằm ở `docs/overview/teacher-surface.md`; đừng suy lại từ bố cục.
 *
 * @param steps - Các bước, theo đúng thứ tự đã xảy ra.
 * @param total - Plan có bao nhiêu bước. Trong lúc lượt đang chạy, `steps` mới chỉ có những
 *   bước đã bắt đầu, nên `n` của `bước k/n` phải lấy từ plan — nói được `2/5` chính vì plan
 *   có trước khi chạy (ADR-25). Bỏ trống thì đếm theo `steps`, đúng cho một lượt đã xong.
 */
export default function Steps({ steps, total }: { steps: Step[]; total?: number }) {
  const failed = steps.some((one) => one.mark === "failed");
  const live = steps.some((one) => one.mark === "running");
  // Chỉ là giá trị khởi tạo: sau đó người đọc làm chủ. Một lượt đang chạy mà tự đóng lại
  // dưới tay người đang đọc nó là mất chỗ, nên state không bao giờ bị ép lại theo `live`.
  const [open, setOpen] = useState(live || failed);
  const shown = failed || open;

  const broken = steps.findIndex((one) => one.mark === "failed");
  const doing = steps.find((one) => one.mark === "running");
  // Header **không** nhắc lại câu lỗi: câu ấy đã nằm ở dòng của chính bước hỏng, và thẻ
  // kết quả in nó lần nữa. Ba lần cùng một câu trên một màn hình đọc ra như ba sự cố.
  const head = failed
    ? `Dừng ở bước ${broken + 1}`
    : live
      ? `${doing?.title ?? "Đang làm"}…`
      : `Đã làm ${steps.length} bước`;

  return (
    <div className={`steps-block ${failed ? "broken" : ""}`}>
      <button
        className="steps-head"
        type="button"
        // Thất bại không thu được, nên nút cũng không mời bấm.
        disabled={failed}
        aria-expanded={shown}
        onClick={() => setOpen((before) => !before)}
      >
        {/* Không chevron khi khối không thu được: một tam giác trên một nút không bấm
            được là lời mời bấm vào thứ không nhận. Artboard cũng bỏ nó ở variant này. */}
        {!failed && <span className={`caret ${shown ? "open" : ""}`} aria-hidden="true" />}
        <span className="what">{head}</span>
        {live && (
          <span className="count">
            bước {steps.indexOf(doing!) + 1}/{total ?? steps.length}
          </span>
        )}
      </button>
      {shown && (
        <div className="steps-list">
          {steps.map((one, index) => (
            <div className="step" key={index}>
              <span className={`step-mark ${one.mark}`} aria-hidden="true">
                {one.mark === "done" ? "✓" : one.mark === "failed" ? "✕" : "○"}
              </span>
              <div className="step-said">
                <div className={`title ${one.mark === "running" ? "doing" : ""}`}>{one.title}</div>
                {one.result !== "" && <div className="result">{one.result}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
