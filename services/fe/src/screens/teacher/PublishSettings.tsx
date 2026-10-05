import { useEffect, useState } from "react";

import {
  isoWithOffset,
  moment,
  teacher,
  type ClassResult,
  type ClassSchedule,
  type PublishForm,
  type TimingRules,
  type PublishResult,
} from "../../api";
import Veil from "./Veil";

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
 * @param onUndo - Bỏ duyệt, mở nội dung đề ra sửa lại. Đường lùi sống **ở đây** chứ không
 *   ở chân panel: duyệt xong là sang thẳng màn này, nên đây là chỗ đầu tiên giáo viên
 *   nhìn thấy sau cú bấm duyệt, và cũng là chỗ duy nhất cần một đường lùi.
 * @param undoing - Đang bỏ duyệt. Khoá nút để không bấm hai lần.
 */
export default function PublishSettings({
  assessmentId,
  onPublished,
  onUndo,
  undoing,
}: {
  assessmentId: string;
  onPublished: () => void;
  onUndo: () => void;
  undoing: boolean;
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
  // `phaseOneMinutes` chứ không `minutes !== ""`: một `-15` **có** chữ trong ô nhưng
  // không phải một giá trị dùng được, và coi nó là "đã điền" thì `faultOf` trả chuỗi rỗng
  // — mà rỗng ở đó nghĩa là *dùng được*. Nút sáng lên trên một lời khẳng định sai, rồi BE
  // trả một `ValidationError` của pydantic mà `.detail` là một mảng, và màn hình in ra
  // `[object Object]`. Không bịa ra một câu từ chối cho ca này: BE không có câu nào cho
  // nó, và chưa nói gì còn hơn nói một câu không phải của ai.
  const filled =
    picked.length > 0 &&
    phaseOneMinutes(minutes) !== null &&
    opensAt !== "" &&
    closesAt !== "" &&
    perQuestion !== "" &&
    deadline !== "";

  // Cửa sổ thời gian có dùng được không, **bằng đúng lời BE sẽ nói**.
  //
  // Lặp lại phép so của `_schedule_fault`, không thay nó: cổng thật vẫn ở BE, và hai bản
  // kiểm của một luật thì bản lỏng hơn là bản người ta đi qua. Chỗ này chỉ nói sớm hơn.
  // Chữ thì mượn nguyên, nên không có cách diễn đạt thứ hai nào sinh ra ở đây (ADR-03).
  //
  // Chỉ xét khi đã gõ đủ: một biểu mẫu mới mở mà đã đỏ là một biểu mẫu mắng người chưa
  // làm gì.
  const impossible = !filled ? "" : faultOf(form.rules, opensAt, closesAt, deadline, minutes);

  // Hai câu luật, điền bằng số đang gõ. Khuôn tới từ BE; chỗ này chỉ thay chỗ trống.
  const phaseOneLive = fill(form.rules.phase_one_form, {
    closes: clock(closesAt),
    last: clock(lastSubmission(closesAt, minutes)),
  });
  const phaseTwoLive = fill(form.rules.phase_two_form, {
    deadline: clock(deadline),
    rate: perQuestion === "" ? "--" : perQuestion,
  });

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
              // Nút này là một **toggle**, và `aria-pressed` là cách duy nhất nói ra điều
              // đó. Thiếu nó thì trình đọc màn hình đọc *"12A, button"* y hệt dù đã chọn
              // hay chưa — dấu ✓ đã `aria-hidden`, và `class-chip on` là chuyện của CSS.
              // Đây là nút quyết định **ai nhận đề** (ADR-02), nên nó là chỗ tệ nhất để
              // một người không biết mình vừa chọn gì.
              aria-pressed={picked.includes(one.class_id)}
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
      </div>

      <div className="divider" />

      <div className="group">
        <div className="caps">PHA 1 — LÀM BÀI VÀ NỘP</div>
        <div className="pair">
          <label className="field">
            <span className="label">Làm bài</span>
            <input
              type="number"
              min={1}
              value={minutes}
              onChange={(event) => setMinutes(event.target.value)}
              placeholder="phút"
            />
          </label>
          <label className="field wide">
            <span className="label">Mở lúc</span>
            <input
              type="datetime-local"
              value={opensAt}
              onChange={(event) => setOpensAt(event.target.value)}
            />
          </label>
        </div>
        <div className="pair">
          <label className="field wide">
            <span className="label">Đóng lúc</span>
            <input
              type="datetime-local"
              value={closesAt}
              onChange={(event) => setClosesAt(event.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="divider" />

      <div className="group">
        <div className="caps">PHA 2 — CHỮA BÀI</div>
        <div className="pair">
          <label className="field">
            <span className="label">Phút mỗi câu</span>
            <input
              type="number"
              min={1}
              value={perQuestion}
              onChange={(event) => setPerQuestion(event.target.value)}
              placeholder="phút / câu"
            />
          </label>
          <label className="field wide">
            <span className="label">Hạn chữa xong</span>
            <input
              type="datetime-local"
              value={deadline}
              onChange={(event) => setDeadline(event.target.value)}
            />
          </label>
        </div>
      </div>

      {/* Hai câu luật, điền bằng chính con số đang gõ.
          Bản trước in `form.rules.phase_one` — một câu BE dựng sẵn với `--:--`, tải MỘT
          LẦN lúc mở màn. Nó đứng ngay dưới mấy ô nhập, trông như sắp đổi theo, mà về cấu
          trúc thì không bao giờ đổi được: một câu luật nói sai số ngay cạnh chỗ gõ số tệ
          hơn hẳn một câu luật vắng mặt.
          Chữ nghĩa vẫn chỉ có một nơi — khuôn tới từ BE, và BE dựng câu thật bằng đúng
          khuôn ấy (`publication_wording.py`). Hộp xác nhận và biên bản thì **không** dùng
          khuôn: chúng có số thật và nhận câu đã dựng. */}
      <div className="rules">
        <div>{phaseOneLive}</div>
        <div>{phaseTwoLive}</div>
      </div>

      {/* Cửa sổ thời gian vô lý nói ra **ngay chỗ câu luật**, vì hai câu ngay trên đang
          khẳng định một sự thật bất khả thi bằng giọng bình thản — *"Vào tham gia tới hết
          08:00 - có thể nộp lúc 08:15"* cho một lần mở lúc 20:00. Lời cải chính phải đứng
          cạnh lời nó cải chính, không đợi tới sau cú bấm. Chữ là chữ của BE. */}
      {impossible !== "" && (
        <div className="trouble" role="alert">
          {impossible}
        </div>
      )}

      {trouble !== null && (
        <div className="trouble" role="alert">
          {trouble}
        </div>
      )}

      {done !== null && <Outcome classes={done} />}

      {/* Đường lùi đứng **trên** nút chính, không đứng cạnh: hai nút cạnh nhau đọc ra là
          hai lựa chọn ngang hàng, mà phát hành và bỏ duyệt thì không ngang hàng chút nào. */}
      <button
        className="quiet"
        type="button"
        disabled={working || undoing}
        onClick={onUndo}
      >
        Hoàn tác
      </button>
      {/* Nhãn bỏ con số đầu người. Con số ấy đã nằm ngay trên biểu mẫu, và chỗ nó thật sự
          chịu lực là hộp xác nhận cuối cùng — nơi duy nhất không còn đường lùi nào sau đó. */}
      <button
        className="cta"
        type="button"
        disabled={!form.can_publish || !filled || impossible !== "" || working}
        onClick={() => void ask()}
      >
        {form.can_publish ? "Phát hành đề" : form.reason}
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
    <Veil onClose={onCancel}>
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
    </Veil>
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

/**
 * Một mốc `datetime-local` đọc thành `HH:MM`, hoặc chỗ trống.
 *
 * `--:--` là chỗ trống của BE (`publication_wording._BLANK`), không phải một chuỗi chọn
 * đại ở đây: biểu mẫu lúc chưa gõ gì phải ra **đúng** câu mà BE dựng khi không có tham số
 * nào, nếu không thì hai bên đã là hai câu khác nhau ngay từ trạng thái rỗng.
 *
 * @param local - Giá trị của một `input[type=datetime-local]`, hoặc chuỗi rỗng.
 * @returns `HH:MM`, hoặc `--:--`.
 */
function clock(local: string): string {
  if (local === "") return "--:--";
  const at = new Date(local);
  if (Number.isNaN(at.getTime())) return "--:--";
  return `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
}

/**
 * Giờ bài cuối cùng còn có thể nộp: giờ đóng cộng thời gian làm bài.
 *
 * **Đây là bản thứ hai của một phép tính**, bản kia ở `publication_wording.phase_one_note`.
 * Nó tồn tại vì biểu mẫu phải nói đúng số **ngay lúc giáo viên đang gõ**, mà hỏi BE sau
 * mỗi phím là một request theo nhịp gõ. Cái giá được trả bằng một test ở BE ghim khuôn và
 * câu dựng ra phải khớp — chữ nghĩa chỉ có một bản, chỉ phép cộng này có hai.
 *
 * Con số ấy chính là thứ diễn đạt ra luật của ADR-03: *"đóng 18:00, làm 15 phút, thì bài
 * cuối nộp 18:15"*. Một giáo viên đọc nó **trước** khi gõ thì không đặt giờ đóng 17:45 để
 * bù — đúng cái hiểu nhầm mà ADR-03 dành cả tài liệu để ngăn.
 *
 * @param closes - Giờ đóng, dạng `datetime-local`.
 * @param minutes - Thời gian làm bài, tính bằng phút.
 * @returns Mốc nộp cuối dạng `datetime-local`, hoặc chuỗi rỗng khi thiếu một trong hai.
 */
/**
 * Số phút làm bài, hoặc `null` khi nó nằm ngoài khoảng BE nhận.
 *
 * Cùng khoảng mà BE nhận (`phase1_minutes: gt=0, le=600`). `min={1}` của ô số **không**
 * ngăn người ta gõ `-15`, và khi ấy câu luật in ra *"đóng 18:00 - có thể nộp lúc 17:45"*
 * — một câu tự phản bác, và trớ trêu là đúng con số 17:45 mà ADR-03 dành cả tài liệu để
 * chống.
 *
 * Một hàm riêng vì **hai** chỗ cần đúng phép chặn này: câu luật đang gõ, và phép so
 * "hạn pha 2 phải sau giờ nộp cuối". Bản đầu chỉ chặn ở chỗ thứ nhất, nên `-15` làm mốc
 * nộp cuối lùi về **trước** giờ đóng, một hạn pha 2 vô lý lọt qua, nút sáng lên, và BE
 * trả về một `ValidationError` của pydantic mà `.detail` là một **mảng** — màn hình in
 * ra `[object Object]`. Hai bản kiểm của một con số, bản lỏng hơn là bản người ta đi qua.
 *
 * @param minutes - Chữ thô của ô nhập.
 * @returns Số phút, hoặc `null`.
 */
function phaseOneMinutes(minutes: string): number | null {
  if (minutes === "") return null;
  const span = Number(minutes);
  if (!Number.isInteger(span) || span <= 0 || span > 600) return null;
  return span;
}

function lastSubmission(closes: string, minutes: string): string {
  if (closes === "") return "";
  const span = phaseOneMinutes(minutes);
  // Ngoài khoảng thì để chỗ trống: chưa nói gì còn hơn nói sai.
  if (span === null) return "";
  const at = new Date(closes);
  if (Number.isNaN(at.getTime())) return "";
  at.setMinutes(at.getMinutes() + span);
  // `toISOString` đổi sang UTC và làm lệch giờ đúng bằng offset máy. Ghép tay giữ đúng
  // giờ địa phương, cùng cách `isoWithOffset` ở trên giữ nó.
  const pad = (one: number) => String(one).padStart(2, "0");
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`;
}

/**
 * Điền chỗ trống của một khuôn câu.
 *
 * `replaceAll` chứ không `replace`: Python `.format` ở BE điền **mọi** lần xuất hiện, còn
 * `String.replace` với một chuỗi chỉ điền lần đầu. Hôm nay mỗi chỗ trống xuất hiện đúng
 * một lần nên hai bên trùng nhau — nhưng ngày câu luật nhắc lại một mốc, BE ra câu đúng
 * còn màn hình để lại một `{closes}` thứ hai, và không test nào thấy.
 *
 * Và thay bằng **hàm**, không bằng chuỗi: một chuỗi thay thế hiểu `$&` và `$'` là ký hiệu
 * đặc biệt, mà một trong các giá trị là chữ thô của một ô nhập.
 *
 * @param form - Khuôn, với chỗ trống dạng `{ten}`.
 * @param values - Giá trị cho từng chỗ trống.
 * @returns Câu đã điền.
 */
function fill(form: string, values: Record<string, string>): string {
  let out = form;
  for (const [slot, value] of Object.entries(values)) {
    out = out.replaceAll(`{${slot}}`, () => value);
  }
  return out;
}

/**
 * Lý do bộ sáu tham số đang gõ không dùng được, hoặc chuỗi rỗng.
 *
 * **Bản sao của `_schedule_fault` ở BE, và nó cố ý là bản sao.** Cổng thật vẫn ở BE: một
 * biểu mẫu không bao giờ là nơi duy nhất kiểm, vì request đi tới đó bằng nhiều đường hơn
 * là một cú bấm. Chỗ này chỉ nói **sớm hơn**, bằng đúng chữ BE sẽ dùng nếu cú bấm ấy đi
 * tới nơi — nên khi hai bên lệch nhau, FE nói sai chứ không nói khác.
 *
 * `check_the_form_fills_the_slots_the_wording_declares` trong `tools/check_contract.py`
 * giữ **chữ**: nó đọc tên ba hằng ở `publication_wording.py` và đòi biểu mẫu này đọc đúng
 * ba field ấy, nên không ai chép tay được một câu từ chối. Nó **không** giữ phép so — đo
 * bằng đột biến: đổi mốc nộp cuối thành giờ đóng thì check vẫn xanh. Phép so được giữ bằng
 * test, mỗi lời từ chối một test, và mốc nộp cuối một test riêng.
 *
 * Thứ tự ba phép so khớp thứ tự của BE, vì lời từ chối **đầu tiên** là lời được trả về.
 *
 * Mốc so là `Date.now()` lúc render, nên nó **không tự cập nhật**: ngồi yên không gõ thì
 * một `opens_at` sát hiện tại trôi vào quá khứ mà biểu mẫu chưa đổi. Không vỡ gì — cổng
 * thật ở BE và nó dùng đồng hồ của chính nó — nhưng đừng đọc hàm này như một đồng hồ.
 *
 * @param rules - Câu luật và lời từ chối của lần phát hành này, nguyên văn từ BE.
 * @param opensAt - Giờ mở, dạng `datetime-local`.
 * @param closesAt - Giờ đóng.
 * @param deadline - Hạn chữa xong.
 * @param minutes - Số phút làm bài của pha 1.
 * @returns Câu tiếng Việt, hoặc chuỗi rỗng khi bộ tham số dùng được.
 */
function faultOf(
  rules: TimingRules,
  opensAt: string,
  closesAt: string,
  deadline: string,
  minutes: string,
): string {
  const opens = new Date(opensAt).getTime();
  const closes = new Date(closesAt).getTime();
  const ends = new Date(deadline).getTime();
  if (!Number.isFinite(opens) || !Number.isFinite(closes) || !Number.isFinite(ends)) {
    return "";
  }

  if (opens <= Date.now()) return rules.opens_in_the_past;
  if (closes <= opens) return rules.closes_before_opens;

  // Mốc là giờ **nộp cuối**, không phải giờ đóng: người vào đúng giây giờ đóng vẫn còn cả
  // `phase1_minutes` để làm (ADR-15). So với giờ đóng thì một hạn pha 2 chỉ sau giờ đóng
  // một phút lọt qua, và hai câu luật trong cùng một biểu mẫu tự phủ định nhau — đúng ca
  // mà BE vừa sửa, nên dựng lại nó ở đây là dựng lại một bug đã có tên.
  //
  // Số phút đi qua `phaseOneMinutes` chứ không `Number` trần: một `-15` lọt vào đây sẽ
  // kéo mốc nộp cuối về **trước** giờ đóng, và phép so này thành lỏng hơn của BE.
  const span = phaseOneMinutes(minutes);
  if (span === null) return "";
  if (ends <= closes + span * 60_000) return rules.phase_two_too_early;

  return "";
}
