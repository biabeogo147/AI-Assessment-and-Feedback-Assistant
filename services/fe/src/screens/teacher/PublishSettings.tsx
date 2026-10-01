import { useEffect, useState } from "react";

import {
  isoWithOffset,
  moment,
  teacher,
  type ClassResult,
  type ClassSchedule,
  type PublishForm,
  type PublishResult,
} from "../../api";

/**
 * Sáu tham số của một lần phát hành, cộng một hộp xác nhận.
 *
 * Tách thành component riêng dù chỉ dùng một chỗ, và lý do là **ranh giới state** chứ không
 * phải tái dùng: sáu tham số nhân n lớp, một lần xem trước, một hộp thoại và một bảng kết
 * quả từng lớp. Đây là chỗ cố ý lệch khỏi luật *"dùng ≥2 lần mới tách"*.
 *
 * **Agent không điền hộ biểu mẫu này** (ADR-02). Một model điền sáu mốc thời gian từ chữ
 * "chiều mai" sẽ tái tạo đúng hiểu nhầm mà ADR-03 dành cả một tài liệu để ngăn, và giáo viên
 * sẽ bấm xác nhận vì mấy con số trông hợp lý. Nên biểu mẫu **không gợi sẵn giờ nào**: năm ô
 * mở ra trống, và `publish-form` cũng không trả về giá trị nào để điền.
 *
 * Hộp xác nhận gọi `preview: true` rồi in **chỉ** những chuỗi trong response; nút trong hộp
 * POST **cùng một object** với cờ tắt. Byte-identical trừ một cờ — đó là cách duy nhất để
 * "hộp xác nhận đọc lại đúng cái sắp xảy ra" là một tính chất của code chứ không phải một
 * lời hứa.
 *
 * @param assessmentId - Đề nào.
 * @param onPublished - Được gọi sau khi có ít nhất một lớp nhận được đề.
 */
export default function PublishSettings({
  assessmentId,
  onPublished,
}: {
  assessmentId: string;
  onPublished: () => void;
}) {
  const [form, setForm] = useState<PublishForm | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [minutes, setMinutes] = useState("");
  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [perQuestion, setPerQuestion] = useState("");
  const [deadline, setDeadline] = useState("");
  const [preview, setPreview] = useState<PublishResult | null>(null);
  const [done, setDone] = useState<ClassResult[] | null>(null);
  const [trouble, setTrouble] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    teacher
      .publishForm(assessmentId)
      .then(setForm)
      .catch((cause: Error) => setTrouble(cause.message));
  }, [assessmentId]);

  if (form === null) {
    return <div className="publish-settings">{trouble ?? "Đang mở biểu mẫu…"}</div>;
  }

  const chosen = form.classes.filter((one) => picked.includes(one.class_id));
  const heads = chosen.reduce((total, one) => total + one.student_count, 0);
  const filled =
    picked.length > 0 &&
    minutes !== "" &&
    opensAt !== "" &&
    closesAt !== "" &&
    perQuestion !== "" &&
    deadline !== "";

  /** Đúng object sẽ được gửi đi — xem trước và phát hành dùng chung nó. */
  function schedules(): ClassSchedule[] {
    return picked.map((class_id) => ({
      class_id,
      opens_at: isoWithOffset(opensAt),
      closes_at: isoWithOffset(closesAt),
      phase1_minutes: Number(minutes),
      phase2_minutes_per_question: Number(perQuestion),
      remediation_deadline: isoWithOffset(deadline),
    }));
  }

  async function ask() {
    setWorking(true);
    try {
      setPreview(await teacher.publish(assessmentId, schedules(), true));
      setTrouble(null);
    } catch (cause) {
      setTrouble((cause as Error).message);
    } finally {
      setWorking(false);
    }
  }

  async function release() {
    setWorking(true);
    try {
      const result = await teacher.publish(assessmentId, schedules(), false);
      setPreview(null);
      setDone(result.classes);
      // Lớp nào trượt thì **giữ nguyên tick**, để sửa giờ rồi gửi lại. Bỏ tick hộ là bắt
      // người ta nhớ lại lớp nào vừa trượt, ngay sau khi vừa đọc một bảng nói đúng điều đó.
      if (result.classes.some((one) => one.published)) onPublished();
      setTrouble(null);
    } catch (cause) {
      setTrouble((cause as Error).message);
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="publish-settings">
      <div className="settings-title">Cài đặt phát hành</div>

      <div className="field">
        <div className="field-head">
          <span className="caps">LỚP</span>
        </div>
        <div className="class-chips">
          {form.classes.map((one) => (
            <button
              className={`class-chip ${picked.includes(one.class_id) ? "on" : ""}`}
              key={one.class_id}
              type="button"
              onClick={() =>
                setPicked((before) =>
                  before.includes(one.class_id)
                    ? before.filter((id) => id !== one.class_id)
                    : [...before, one.class_id],
                )
              }
            >
              {picked.includes(one.class_id) && <span aria-hidden="true">✓</span>}
              {one.name}
            </button>
          ))}
        </div>
        <div className="field-note">
          Đã chọn {picked.length} trong {form.classes.length} lớp · {heads} học sinh
        </div>
      </div>

      <div className="group">
        <div className="caps">PHA 1 — LÀM BÀI VÀ NỘP</div>
        <div className="pair">
          <label className="field">
            <span className="caps">LÀM BÀI</span>
            <input
              type="number"
              min={1}
              value={minutes}
              onChange={(event) => setMinutes(event.target.value)}
              placeholder="phút"
            />
          </label>
          <label className="field wide">
            <span className="caps">MỞ LÚC</span>
            <input
              type="datetime-local"
              value={opensAt}
              onChange={(event) => setOpensAt(event.target.value)}
            />
          </label>
        </div>
        <div className="pair">
          <label className="field wide">
            <span className="caps">ĐÓNG LÚC</span>
            <input
              type="datetime-local"
              value={closesAt}
              onChange={(event) => setClosesAt(event.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="group">
        <div className="caps">PHA 2 — CHỮA BÀI</div>
        <div className="pair">
          <label className="field">
            <span className="caps">PHÚT MỖI CÂU</span>
            <input
              type="number"
              min={1}
              value={perQuestion}
              onChange={(event) => setPerQuestion(event.target.value)}
              placeholder="phút / câu"
            />
          </label>
          <label className="field wide">
            <span className="caps">HẠN CHỮA XONG</span>
            <input
              type="datetime-local"
              value={deadline}
              onChange={(event) => setDeadline(event.target.value)}
            />
          </label>
        </div>
      </div>

      {/* Ba câu luật, lấy nguyên văn từ BE. Cùng string mà hộp xác nhận và biên bản in ra
          — ADR-03 đòi bốn nơi giống hệt nhau từng chữ, và cách duy nhất chắc chắn đúng là
          không nơi nào tự viết lại. */}
      <div className="rules">
        <div>{form.rules.phase_one}</div>
        <div>{form.rules.phase_two}</div>
      </div>

      {trouble !== null && (
        <div className="trouble" role="alert">
          {trouble}
        </div>
      )}

      {done !== null && <Outcome classes={done} />}

      <button
        className="cta"
        type="button"
        disabled={!form.can_publish || !filled || working}
        onClick={() => void ask()}
      >
        {form.can_publish ? `Phát hành cho ${heads} học sinh` : form.reason}
      </button>

      {preview !== null && (
        <Confirm
          preview={preview}
          paper={`${form.question_count} câu · ${form.title}`}
          heads={heads}
          working={working}
          onCancel={() => setPreview(null)}
          onConfirm={() => void release()}
        />
      )}
    </div>
  );
}

/**
 * Hộp xác nhận.
 *
 * Sáu dòng đọc lại, rồi hai câu luật. Hai câu luật in **nguyên văn** từ response `preview`
 * — tự dựng lại chúng ở đây là bản cài đặt thứ hai của cùng một luật, và bản thứ hai là bản
 * sẽ lệch. Sáu dòng kia thì là **hiển thị**: giờ đổi sang định dạng `HH:MM · DD/MM` bằng
 * đúng hàm mà mọi màn hình học sinh dùng, nên không có cách định dạng thứ hai nào trong app.
 *
 * Nút phát hành gửi **cùng một object** với cờ `preview` tắt. Byte-identical trừ một cờ.
 *
 * @param preview - Response của lần gọi `preview: true`.
 * @param paper - Một dòng mô tả đề, cho hàng đầu tiên.
 * @param heads - Tổng số học sinh của các lớp đã chọn.
 * @param working - Đang gửi; nút phải khoá lại để không phát hành hai lần.
 * @param onCancel - Quay lại biểu mẫu.
 * @param onConfirm - Phát hành thật.
 */
function Confirm({
  preview,
  paper,
  heads,
  working,
  onCancel,
  onConfirm,
}: {
  preview: PublishResult;
  paper: string;
  heads: number;
  working: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const landing = preview.classes.filter((one) => one.published);
  const first = landing[0];
  const names = landing.map((one) => one.class_name || one.class_id).join(" và ");
  const refused = preview.classes.filter((one) => !one.published);

  return (
    <div className="veil" role="dialog" aria-modal="true">
      <div className="confirm">
        <h3>Phát hành đề kiểm tra?</h3>
        <p className="lead">
          Đề sẽ hiển thị cho {heads} học sinh của lớp {names}. Bạn còn thu hồi được cho tới giờ
          mở của từng lớp.
        </p>

        <div className="recap">
          <Line label="Đề" value={paper} />
          <Line label="Lớp" value={`${names} · ${heads} học sinh`} />
          {first !== undefined && (
            <>
              <Line
                label="Thời gian"
                value={`mở ${moment(first.opens_at ?? "")} · đóng ${moment(first.closes_at ?? "")}`}
              />
              <Line label="Hạn chữa" value={`tới hết ${moment(first.remediation_deadline ?? "")}`} />
              <Line
                label="Thu hồi"
                value={`được cho tới ${moment(first.withdrawable_until ?? "")}`}
              />
            </>
          )}
          {refused.length > 0 && (
            <Line label="Chưa nhận" value={refused.map((one) => one.reason).join(" · ")} />
          )}
        </div>

        {first !== undefined && (
          <>
            <div className="rule">{first.phase_one_note}</div>
            <div className="rule">{first.phase_two_note}</div>
          </>
        )}
        <div className="rule">{preview.rules.recall}</div>

        <div className="confirm-actions">
          <button className="btn" type="button" onClick={onCancel}>
            Xem lại cài đặt
          </button>
          <button
            className="btn primary"
            type="button"
            disabled={working || landing.length === 0}
            onClick={onConfirm}
          >
            Phát hành cho {heads} học sinh
          </button>
        </div>
      </div>
    </div>
  );
}

/** Một dòng của phần đọc lại: nhãn cố định bên trái, giá trị bên phải. */
function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="recap-row">
      <span className="what">{label}</span>
      <span className="is">{value}</span>
    </div>
  );
}

/**
 * Kết quả từng lớp sau khi phát hành.
 *
 * Thất bại một phần là một **hàng**, không phải một ngoại lệ (ADR-02): một lớp nhận được
 * trong khi lớp khác không là chuyện biểu diễn được, nên nó được in ra như vậy. `reason` in
 * nguyên văn — không viết hoa, không thêm dấu chấm; đó là câu của BE.
 */
function Outcome({ classes }: { classes: ClassResult[] }) {
  return (
    <div className="outcome">
      {classes.map((one) => (
        <div className={`outcome-row ${one.published ? "" : "refused"}`} key={one.class_id}>
          <span className="who">{one.class_name || one.class_id}</span>
          <span className="line">{one.published ? one.phase_one_note : one.reason}</span>
        </div>
      ))}
    </div>
  );
}
