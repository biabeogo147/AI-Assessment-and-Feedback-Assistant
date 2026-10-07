import { useEffect, useRef, useState } from "react";

import {
  isoWithOffset,
  moment,
  teacher,
  type ClassResult,
  localInput,
  type Schedule,
  type PublishedTo,
  type PublishForm,
  type TimingRules,
  type PublishResult,
} from "../../api";
import { forget, readFlag, readJson, writeFlag, writeJson } from "./remember";
import Veil from "./Veil";

/** Bản nháp của một đề. Theo đề, vì sáu tham số là của một lần phát hành một đề. */
const DRAFT_KEY = (assessmentId: string) =>
  `kriky.teacher.publish-draft.${assessmentId}`;

/** Nấc thu/bung của tấm trượt, cũng theo đề. */
const OPEN_KEY = (assessmentId: string) =>
  `kriky.teacher.publish-open.${assessmentId}`;

/**
 * Sáu tham số đang gõ dở, cộng mốc gõ.
 *
 * `at` không phải trang trí: nó là thứ cho phép màn hình **nói ra** rằng nó vừa khôi
 * phục một thứ, và nói từ bao giờ. Khôi phục im lặng là khôi phục không hỏi.
 */
interface Draft {
  picked: string[];
  minutes: string;
  opensAt: string;
  closesAt: string;
  perQuestion: string;
  deadline: string;
  at: string;
}

/**
 * Bản nháp đã nhớ của một đề, nếu có.
 *
 * Kiểm hình dạng chứ không tin `JSON.parse`: khoá này do một bản cũ của app cũng có thể
 * đã ghi, và một `picked` không phải mảng sẽ nổ ở `picked.includes` — tức nổ ở giữa lúc
 * render, không nổ ở đây.
 *
 * @param assessmentId - Đề nào.
 * @returns Bản nháp dùng được, hoặc `null`.
 */
function readDraft(assessmentId: string): Draft | null {
  const saved = readJson<Draft>(DRAFT_KEY(assessmentId));
  if (saved === null || typeof saved !== "object") return null;
  if (!Array.isArray(saved.picked)) return null;
  if (typeof saved.at !== "string") return null;
  return saved;
}

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
 * **Và nó là một tấm trượt neo lề dưới, thu được.** Đo trên trình duyệt ngày 06/10/2026:
 * panel cao 911, biểu mẫu ăn 661,5 và `panel-questions` còn **111** — giáo viên thấy 19,5%
 * cái đề mình đang duyệt. Thu lại thì chỉ còn thanh đầu cao 53, và phần câu hỏi **giãn ra
 * lấp chỗ** chứ không bị tấm trượt nổi lên che: hai phương án ấy vẽ cạnh nhau trên Figma
 * (`519:1603`) và phương án che để lại 52px vĩnh viễn nằm sau thanh đầu, nên muốn đọc được
 * dòng cuối thì lại phải đệm đúng 52px — tức vòng về đúng phương án giãn, qua một đường dài
 * hơn. Hình khối lấy từ variant `Trạng thái=thu` (`517:17`), nhưng ở **density Teacher**:
 * 420×52 trên Figma, 420×51,5 đo trên trình duyệt.
 *
 * Đo ngày 06/10/2026 trên đề đã phát hành `d3f40a77`: bung thì vùng câu hỏi **94** trên 911
 * (10,3%) và phải cuộn (`scrollHeight` 569 so `clientHeight` 94); thu thì **720,5** (79,1%)
 * và `scrollHeight` = `clientHeight` = 721 — **không còn phải cuộn**. Tổng ba khối khít
 * đúng 911, nên không khối nào che khối nào.
 *
 * **Và từ 06/10/2026 nó nhớ.** Cả sáu ô lẫn nấc thu/bung sống qua F5, theo từng đề.
 *
 * Lời cũ ở đúng chỗ này nói ngược lại — *"nhớ nấc mà không nhớ giờ là nhớ nửa vời"* — và
 * nó dựa trên một cách đọc ADR-02 quá rộng. ADR-02 cấm **hệ thống tự nghĩ ra** một mốc
 * giờ, vì một giá trị gợi sẵn là một giá trị giáo viên sẽ bấm qua. Khôi phục đúng chữ
 * giáo viên vừa tự gõ không phải một giá trị gợi sẵn: nó không thêm thông tin nào vào
 * biểu mẫu, nó chỉ thôi vứt đi thông tin đã có.
 *
 * Cái giá có thật, và nó có hàng rào sẵn: một bản nháp từ ba hôm trước mang `opens_at`
 * đã quá khứ. `faultOf` so `opens <= Date.now()` và trả `rules.opens_in_the_past` — chữ
 * của BE, hằng `FAULT_OPENS_IN_THE_PAST` — nên biểu mẫu **đỏ ngay** khi bản nháp hết
 * dùng được. Và màn hình **nói ra** rằng nó vừa khôi phục, kèm mốc đã gõ và một nút bỏ:
 * khôi phục im lặng là khôi phục không hỏi.
 *
 * Mở màn là **bung** khi chưa ai thu nó, vì phát hành là việc giáo viên vừa bấm để tới đây.
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
  // Khôi phục trong hàm khởi tạo của `useState`, không trong một `useEffect`: một effect
  // khôi phục sẽ ghi đè lên chữ giáo viên vừa gõ, và nó cũng nháy một khung hình trống.
  const kept = readDraft(assessmentId);

  const [form, setForm] = useState<PublishForm | null>(null);
  const [picked, setPicked] = useState<string[]>(kept?.picked ?? []);
  const [minutes, setMinutes] = useState(kept?.minutes ?? "");
  const [opensAt, setOpensAt] = useState(kept?.opensAt ?? "");
  const [closesAt, setClosesAt] = useState(kept?.closesAt ?? "");
  const [perQuestion, setPerQuestion] = useState(kept?.perQuestion ?? "");
  const [deadline, setDeadline] = useState(kept?.deadline ?? "");
  const [draftAt, setDraftAt] = useState<string | null>(kept?.at ?? null);
  const [live, setLive] = useState<PublishedTo[]>([]);
  // Đếm số lần cần đọc lại `publications`. Một lần phát hành thành công đổi câu trả lời
  // của endpoint ấy, nên màn hình phải hỏi lại — không hỏi thì khối `ĐÃ PHÁT HÀNH` còn
  // kể trạng thái của một phút trước.
  const [reread, setReread] = useState(0);
  const [preview, setPreview] = useState<PublishResult | null>(null);
  const [done, setDone] = useState<ClassResult[] | null>(null);
  const [trouble, setTrouble] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [open, setOpen] = useState(() => readFlag(OPEN_KEY(assessmentId)));

  // `reread` nằm trong deps, không chỉ `assessmentId`.
  //
  // Thiếu nó thì `form.classes[].published` đứng im sau một lần phát hành thành công, nên
  // `locked` không bao giờ bật **trong cùng một phiên**: phát hành cho cả hai lớp xong mà
  // năm ô vẫn gõ được, chip vẫn bấm được, và CTA vẫn mời bấm lần nữa — một cú POST chắc
  // chắn bị BE từ chối. Cái khoá chỉ xuất hiện sau một lần F5, tức đúng lúc không ai nhìn.
  useEffect(() => {
    teacher
      .publishForm(assessmentId)
      .then(setForm)
      .catch((cause: Error) => setTrouble(cause.message));
  }, [assessmentId, reread]);

  // Giờ đã đặt, đọc lại từ BE.
  //
  // Lời gọi **riêng**, và hỏng thì im lặng: nó thêm thông tin chứ không mở cổng nào, nên
  // một lần 500 ở đây không được phép chặn biểu mẫu. `publish-form` chỉ nói lớp nào đang
  // giữ đề, không nói giữ với giờ nào — `PublishedTo` sinh ra đúng để trả lời câu ấy, và
  // cho tới đợt này **không chỗ nào trong FE gọi nó**.
  useEffect(() => {
    teacher
      .publications(assessmentId)
      // Kiểm cả hình dạng, không chỉ bắt lỗi mạng. `.catch` chỉ bắt lời hứa bị từ chối;
      // một response 200 mang hình dạng khác đi thẳng vào `live` và nổ ở `live.length`
      // — tức làm **trắng** cả biểu mẫu vì một lời gọi vốn chỉ thêm thông tin.
      .then((all) => setLive(Array.isArray(all.classes) ? all.classes : []))
      .catch(() => setLive([]));
  }, [assessmentId, reread]);

  // Ghi nháp mỗi khi sáu giá trị đổi.
  //
  // **Chỉ ghi khi có gì để ghi.** Một biểu mẫu trống ghi xuống thì lần mở sau sẽ thấy một
  // dòng *"bản nháp bạn gõ lúc…"* cho một bản nháp rỗng — một câu nói đúng về một thứ
  // không đáng nói. Và nó sẽ chôn mất nháp thật nếu component mount lại trước khi giáo
  // viên kịp gõ.
  // Bản nháp đã khôi phục, giữ nguyên qua mọi lần render để so.
  const restored = useRef(kept);

  useEffect(() => {
    // **Chưa đổi gì thì không ghi lại.**
    //
    // Effect này cũng chạy lúc mount, và lúc ấy sáu giá trị đúng bằng bản vừa khôi phục.
    // Ghi lại ở đó là đóng một mốc `at` mới cho một thứ giáo viên **không** vừa gõ — nên
    // chỉ mở màn ra xem thôi là mốc nhảy, và từ lần F5 thứ hai dòng báo nói một giờ không
    // ai gõ gì. Đúng cái mà dòng ấy sinh ra để nói thật.
    const same =
      restored.current !== null &&
      restored.current.minutes === minutes &&
      restored.current.opensAt === opensAt &&
      restored.current.closesAt === closesAt &&
      restored.current.perQuestion === perQuestion &&
      restored.current.deadline === deadline &&
      restored.current.picked.length === picked.length &&
      restored.current.picked.every((one, at) => one === picked[at]);
    if (same) return;

    const empty =
      picked.length === 0 &&
      minutes === "" &&
      opensAt === "" &&
      closesAt === "" &&
      perQuestion === "" &&
      deadline === "";
    if (empty) return;
    writeJson(DRAFT_KEY(assessmentId), {
      picked,
      minutes,
      opensAt,
      closesAt,
      perQuestion,
      deadline,
      at: new Date().toISOString(),
    });
  }, [assessmentId, picked, minutes, opensAt, closesAt, perQuestion, deadline]);

  /** Bỏ bản nháp: xoá khoá, và trả sáu ô về trống. */
  function dropDraft(): void {
    forget(DRAFT_KEY(assessmentId));
    setPicked([]);
    setMinutes("");
    setOpensAt("");
    setClosesAt("");
    setPerQuestion("");
    setDeadline("");
    setDraftAt(null);
  }

  /**
   * Thanh đầu của tấm trượt: tên, một mũi nhọn, và cả thanh là chỗ bấm.
   *
   * Một `<button>` mang `aria-expanded`, không phải một `div` có `onClick`: nấc thu/bung là
   * thứ trình đọc màn hình phải đọc ra được, và `aria-expanded` là cách duy nhất nói nó.
   * Mũi nhọn **quay**, không đổi sang một ký tự khác — một hình xoay thì mắt theo được nó,
   * cùng lý do `.steps-head .caret` đã quay từ trước.
   *
   * Thanh đầu có mặt ở **cả hai** nấc, và cùng một chỗ bấm: một chỗ bấm mở ra được thì phải
   * đóng lại được ở đúng chỗ ấy.
   */
  const head = (
    <button
      className="sheet-head"
      type="button"
      aria-expanded={open}
      onClick={() =>
        setOpen((before) => {
          writeFlag(OPEN_KEY(assessmentId), !before);
          return !before;
        })
      }
    >
      <span className="settings-title">Cài đặt phát hành</span>
      <svg className="caret" viewBox="0 0 8 6" aria-hidden="true">
        <path d="M0 0h8L4 6z" fill="currentColor" />
      </svg>
    </button>
  );

  // Thu thì chỉ còn thanh đầu, và nó đứng trước cả phép đọc `form`: một tấm trượt đã thu
  // không có gì để nói về một biểu mẫu chưa tải xong.
  if (!open) {
    return <div className="publish-settings thu">{head}</div>;
  }

  if (form === null) {
    return (
      <div className="publish-settings">
        {head}
        <div className="note">{trouble ?? "Đang mở biểu mẫu…"}</div>
      </div>
    );
  }

  const chosen = form.classes.filter((one) => picked.includes(one.class_id));
  const heads = chosen.reduce((total, one) => total + one.student_count, 0);

  /**
   * Mọi lớp của giáo viên này đã giữ đề.
   *
   * Khi ấy không còn lớp nào để phát hành, nên năm ô thôi có việc: chúng khoá lại, và
   * **không có CTA**. Vắng mặt chứ không khoá-kèm-lời-giải-thích — BE không có câu từ
   * chối cho ca này, và ADR-03 giữ chỗ ấy cho BE. Không còn việc để mời thì không mời,
   * đó là cấu trúc chứ không phải một câu tôi tự viết.
   */
  const locked = form.classes.length > 0 && form.classes.every((one) => one.published);

  /**
   * Khung giờ **chung** của mọi lớp đang giữ đề, nếu có một khung chung.
   *
   * Năm ô chỉ điền được khi có đúng một câu trả lời. Hai lớp mở lệch giờ là chuyện bình
   * thường — bảng `publications` khoá theo `(đề, lớp)` đúng để cho phép nó — và khi ấy
   * một bộ ô nhập không diễn tả nổi hai khung giờ. Điền bừa khung của lớp đầu tiên là
   * đặt một con số sai lên màn hình với giọng bình thản; khối `ĐÃ PHÁT HÀNH` ngay trên
   * mới là chỗ nói đủ.
   */
  const shared =
    live.length > 0 &&
    live.every(
      (one) =>
        one.opens_at === live[0].opens_at &&
        one.closes_at === live[0].closes_at &&
        one.phase1_minutes === live[0].phase1_minutes &&
        one.phase2_minutes_per_question === live[0].phase2_minutes_per_question &&
        one.remediation_deadline === live[0].remediation_deadline,
    )
      ? live[0]
      : null;

  // Ô khoá **mang** giá trị đã phát hành. Một ô mờ mà rỗng chỉ nói rằng có một ô, và
  // rằng bạn không được chạm vào nó.
  const show = {
    minutes: locked && shared ? String(shared.phase1_minutes) : minutes,
    opensAt: locked && shared ? localInput(shared.opens_at) : opensAt,
    closesAt: locked && shared ? localInput(shared.closes_at) : closesAt,
    perQuestion:
      locked && shared ? String(shared.phase2_minutes_per_question) : perQuestion,
    deadline: locked && shared ? localInput(shared.remediation_deadline) : deadline,
  };

  /**
   * Năm ô không còn gì để nói, nên chúng **không dựng**.
   *
   * Đo trên trình duyệt ngày 06/10/2026, đề `d3f40a77` đã phát hành cho 12A lúc 14:21 và
   * 12B lúc 15:26 — hai khung giờ khác nhau, nên không có khung chung để điền. Khi ấy
   * năm ô vừa khoá vừa **rỗng**, và chúng ăn mất 805,5 trên 911 của panel: vùng câu hỏi
   * còn **24 pixel**. Ba trăm pixel để nói đúng một điều — *"có năm cái ô, và bạn không
   * được chạm vào"* — trong khi khối `ĐÃ PHÁT HÀNH` ngay trên đã nói đủ cho từng lớp.
   *
   * Đây đúng là thứ mà việc điền giá trị vào ô khoá sinh ra để chống; ca lệch giờ chỉ là
   * ca không điền được. Không điền được thì không dựng, chứ không dựng một cái vỏ rỗng.
   *
   * Hai câu luật cũng đi theo: chúng điền từ **chữ đang gõ**, mà ở đây không ai gõ gì, nên
   * chúng in `--:--` ngay dưới một đề đang thật sự chạy.
   */
  //
  // `live.length > 0` là điều kiện thứ ba, và nó chống đúng một ca: lời gọi `publications`
  // hỏng thì `live` rỗng, `shared` là `null`, và nếu chỉ xét hai điều kiện kia thì cả năm
  // ô **lẫn** khối `ĐÃ PHÁT HÀNH` cùng biến mất — còn lại đúng một hàng chip. Tức một lời
  // gọi vốn chỉ thêm thông tin lại xoá sạch thân biểu mẫu, ngược hẳn lời hứa ở effect đọc
  // nó. Không biết gì thì giữ nguyên biểu mẫu, chỉ là nó khoá.
  const silent = locked && live.length > 0 && shared === null;
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

  /**
   * Đúng khung giờ sẽ được gửi đi — xem trước và phát hành dùng chung nó.
   *
   * **Một** khung giờ, không một bộ cho mỗi lớp. Biểu mẫu chỉ có một bộ ô nhập nên
   * nó vẫn luôn gửi như thế; từ 06/10/2026 hợp đồng nói đúng điều đó.
   */
  function schedule(): Schedule {
    return {
      opens_at: isoWithOffset(opensAt),
      closes_at: isoWithOffset(closesAt),
      phase1_minutes: Number(minutes),
      phase2_minutes_per_question: Number(perQuestion),
      remediation_deadline: isoWithOffset(deadline),
    };
  }

  async function ask() {
    setWorking(true);
    try {
      setPreview(await teacher.publish(assessmentId, schedule(), picked, true));
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
      const result = await teacher.publish(
        assessmentId,
        schedule(),
        picked,
        false,
      );
      setPreview(null);
      setDone(result.classes);
      // Lớp nào trượt thì **giữ nguyên tick**, để sửa giờ rồi gửi lại. Bỏ tick hộ là bắt
      // người ta nhớ lại lớp nào vừa trượt, ngay sau khi vừa đọc một bảng nói đúng điều đó.
      // Nháp hết việc khi đề đã tới ít nhất một lớp: từ lúc này sự thật nằm ở
      // `publications` của BE, và giữ lại một bản nháp là giữ một phiên bản thứ hai của
      // cùng một khung giờ — bản sẽ lệch.
      if (result.classes.some((one) => one.published)) {
        forget(DRAFT_KEY(assessmentId));
        setDraftAt(null);
        setReread((before) => before + 1);
        onPublished();
      }
      setTrouble(null);
    } catch (cause) {
      setTrouble((cause as Error).message);
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="publish-settings">
      {head}

      {/* Màn hình nói ra rằng nó vừa khôi phục một thứ, và nói từ bao giờ. Mốc in bằng
          `moment()` — đúng hàm mọi màn hình khác dùng, nên không có cách định dạng giờ
          thứ hai nào sinh ra ở đây. Nút bỏ là đường lùi: khôi phục mà không bỏ lại được
          thì bản nháp thành một thứ bám vào biểu mẫu. */}
      {draftAt !== null && (
        <div className="draft-mark">
          <span>Bản nháp bạn gõ {moment(draftAt)}.</span>
          <button className="quiet" type="button" onClick={dropDraft}>
            Bỏ bản nháp
          </button>
        </div>
      )}

      {/* Giờ đã đặt, một dòng mỗi lớp.
          Gọn có chủ ý: hai câu luật dài đã nằm sẵn ở khối `rules` bên dưới, nên chép
          chúng vào đây lần nữa cho MỖI lớp là đội tấm trượt lên quá chỗ panel có. Thứ
          không suy ra được từ chỗ khác chỉ có: lớp nào, mấy học sinh, khung giờ nào, và
          thu hồi được tới lúc nào. Giờ in bằng `moment()`, như mọi nơi khác. */}
      {live.length > 0 && (
        <div className="published-to">
          <span className="caps">ĐÃ PHÁT HÀNH</span>
          {live.map((one) => (
            <div className="published-row" key={one.class_id}>
              <span className="lop">
                {one.class_name} · {one.student_count} học sinh
              </span>
              <span className="when">
                {moment(one.opens_at)} → {moment(one.closes_at)} · thu hồi được tới{" "}
                {moment(one.withdrawable_until)}
              </span>
            </div>
          ))}
        </div>
      )}

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
              // Lớp đang giữ đề thì chip **thấy nhưng khoá**, không biến mất: giáo viên
              // cần thấy 12A đang giữ đề, và bỏ chip đi là giấu mất đúng thông tin ấy.
              // Muốn đổi khung giờ của một lớp đang giữ thì đi qua `Hoàn tác` hoặc thu
              // hồi lớp đó — đó là cái giá của việc khoá, và nó được nói ra ở đây.
              disabled={one.published}
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

      {!silent && (
        <>
      <div className="divider" />

      <div className="group">
        <div className="caps">PHA 1 — LÀM BÀI VÀ NỘP</div>
        <div className="pair">
          <label className="field">
            <span className="label">Làm bài</span>
            <input
              type="number"
              min={1}
              value={show.minutes}
              disabled={locked}
              onChange={(event) => setMinutes(event.target.value)}
              placeholder="phút"
            />
          </label>
          <label className="field wide">
            <span className="label">Mở lúc</span>
            <input
              type="datetime-local"
              value={show.opensAt}
              disabled={locked}
              onChange={(event) => setOpensAt(event.target.value)}
            />
          </label>
        </div>
        <div className="pair">
          <label className="field wide">
            <span className="label">Đóng lúc</span>
            <input
              type="datetime-local"
              value={show.closesAt}
              disabled={locked}
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
              value={show.perQuestion}
              disabled={locked}
              onChange={(event) => setPerQuestion(event.target.value)}
              placeholder="phút / câu"
            />
          </label>
          <label className="field wide">
            <span className="label">Hạn chữa xong</span>
            <input
              type="datetime-local"
              value={show.deadline}
              disabled={locked}
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
        </>
      )}

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

      {/* Hết cửa lùi thì nút **hiện nhưng khoá**, kèm câu của BE — cùng khuôn với cách
          biểu mẫu chặn một cửa sổ thời gian vô lý trước cú bấm. Giấu nút đi thì giáo
          viên đi tìm một đường lùi không còn tồn tại; để nó bấm được thì cú bấm nhận
          409, mà `Panel` từng nuốt mất câu ấy nên màn hình im lặng hoàn toàn. */}
      {form.undo_blocked !== "" && (
        <div className="trouble" role="status">
          {form.undo_blocked}
        </div>
      )}
      {/* Đường lùi đứng **trên** nút chính, không đứng cạnh: hai nút cạnh nhau đọc ra là
          hai lựa chọn ngang hàng, mà phát hành và bỏ duyệt thì không ngang hàng chút nào. */}
      <button
        className="quiet"
        type="button"
        disabled={working || undoing || form.undo_blocked !== ""}
        onClick={onUndo}
      >
        Hoàn tác
      </button>
      {/* Nhãn bỏ con số đầu người. Con số ấy đã nằm ngay trên biểu mẫu, và chỗ nó thật sự
          chịu lực là hộp xác nhận cuối cùng — nơi duy nhất không còn đường lùi nào sau đó. */}
      {!locked && (
        <button
          className="cta"
          type="button"
          disabled={!form.can_publish || !filled || impossible !== "" || working}
          onClick={() => void ask()}
        >
          {form.can_publish ? "Phát hành đề" : form.reason}
        </button>
      )}

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
        {/* **Một** mốc thu hồi, không một mốc mỗi lớp. Câu này từng nói "cho tới giờ mở của
            từng lớp" — và nó đứng ngay trên dòng luật của BE nói "cho tới hết giờ mở", cộng
            dòng `Thu hồi` in đúng **một** giờ. Ba chỗ, hai câu chuyện: đo được trên trình
            duyệt ngày 06/10/2026. Một lần phát hành có một khung giờ (ADR-02, sửa đổi cùng
            ngày), nên "từng lớp" không còn thứ gì để chỉ tới. */}
        <p className="lead">
          Đề sẽ hiển thị cho {heads} học sinh của lớp {names}. Bạn còn thu hồi được cho tới giờ
          mở.
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
