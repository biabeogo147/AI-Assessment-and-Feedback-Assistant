import { type Turn } from "../../api";
import { type Step } from "./Steps";

/**
 * Việc mỗi tool hiện thành gì: một **bước** trong khối `Thinking`, hay một **thẻ** kết quả.
 *
 * Đây là bản cài đặt của bảng trong `docs/overview/teacher-surface.md`, và là chỗ duy nhất
 * được phép quyết chuyện đó. Luật có **hai nửa**: một lượt của model sinh ra tối đa một thẻ
 * — chỉ kết quả cuối cùng có hậu quả cho giáo viên mới lên thẻ, mọi bước trung gian ở lại
 * trong `Thinking` — còn **mỗi** việc giáo viên tự làm thì một thẻ, vì ADR-24 đòi từng biên
 * bản sống sót. Cả hai nửa gặp nhau trong cùng một khối; xem `cardTurns`.
 * Thiếu một dòng ở đây thì tool mới chỉ là một bước, và đó là mặc định an toàn: một bước
 * không hứa gì.
 */
const STEP_TITLE: Record<string, string> = {
  find_class: "Tìm lớp",
  class_assessment_summary: "Xem các đề của lớp",
  create_draft: "Tạo đề trống",
  start_drafting: "Soạn câu hỏi",
  draft_progress: "Kiểm tiến độ soạn",
  "teacher.approve": "Duyệt đề",
  "teacher.unapprove": "Bỏ duyệt",
  "teacher.publish": "Phát hành",
};

/**
 * Những tool mà **giáo viên** gọi, không phải model.
 *
 * Ba cái này là nút trên panel đề: bấm *Duyệt đề* là một lượt `teacher.approve` được ghi
 * vào hội thoại, vì ADR-24 đòi biên bản duyệt sống sót. Nhưng ghi lại một việc không có
 * nghĩa là xếp nó vào khối `Thinking` — khối ấy là **bằng chứng model đã làm gì**, và một
 * dòng "Duyệt đề" trong đó nói rằng Kriky tự duyệt đề. Đo được: lượt duyệt hiện **hai
 * lần**, một dòng trong khối bước và một cái thẻ, cho cùng một cú bấm.
 */
const BY_THE_TEACHER = new Set([
  "teacher.approve",
  "teacher.unapprove",
  "teacher.publish",
]);

/**
 * Lượt này có phải một việc giáo viên tự làm không.
 *
 * @param turn - Một lượt bất kỳ.
 * @returns `true` khi nó không thuộc về khối bước của model.
 */
export function byTheTeacher(turn: Turn): boolean {
  return turn.kind === "tool_result" && BY_THE_TEACHER.has(turn.tool_name);
}

/**
 * Một bước đã lưu, đọc thành một dòng trong khối `Thinking`.
 *
 * Dòng kết quả chỉ nói lại những con số **chính `tool_result` ấy mang theo**. Không có con
 * số nào thì không có dòng nào: một bước im lặng vẫn thật, còn một dòng bịa thì không.
 *
 * @param turn - Lượt `tool_result` đã lưu.
 * @returns Bước để vẽ, với dấu `done` hoặc `failed`.
 */
export function stepFor(turn: Turn): Step {
  const result = turn.tool_result;
  const refused = refusal(result);
  return {
    mark: refused ? "failed" : "done",
    // Tool chưa có trong bảng vẫn phải đọc được bằng tiếng người. In `turn.tool_name` ra
    // đây là thả một định danh máy lên bề mặt giáo viên, đúng thứ `teacher-surface.md` cấm.
    title: STEP_TITLE[turn.tool_name] ?? "Một bước nữa",
    result: refused ? dash(why(result)) : dash(outcome(turn)),
  };
}

/**
 * Việc đó đã **không** xảy ra: ba cờ từ chối của tool, và một `error` do BE dựng.
 *
 * `error` phải nằm đây. Một bước ném exception trả về `{"error": …}` và **không** có cờ nào
 * trong ba cờ kia, nên một phép kiểm chỉ nhìn ba cờ đọc nó thành *đã xong*: dấu `✓` cho một
 * việc chưa xảy ra, một dòng kết quả bịa ra từ các field không tồn tại (`đề "", cần 0 câu`),
 * và một thẻ `Đã tạo đề` cho một cái đề không hề được tạo. Đo thấy cả ba trên trình duyệt
 * thật, từ cùng một thiếu sót này.
 */
function refusal(result: Record<string, unknown>): boolean {
  return (
    Boolean(result.error) ||
    result.found === false ||
    result.created === false ||
    result.started === false
  );
}

/** Câu BE viết cho một việc không xảy ra: `reason` của tool, hoặc `error` của vòng chạy. */
function why(result: Record<string, unknown>): string {
  return String(result.reason ?? result.error ?? "");
}

/** `— ` đứng trước dòng kết quả, đúng như thiết kế; chuỗi rỗng thì vẫn rỗng. */
function dash(text: string): string {
  return text === "" ? "" : `— ${text}`;
}

/**
 * Ba con số của một bước soạn đã đóng, đọc thành một dòng.
 *
 * Soi lại `_how_many` của BE từng nhánh một, và đó là chủ ý chứ không phải trùng lặp tình
 * cờ: cùng một bước được vẽ bằng hai đường — `detail` do BE gửi khi lượt đang chạy, và
 * `tool_result` đã lưu sau một lần F5 — nên hai đường phải cho cùng một câu. Lệch một chữ
 * là một lần tải lại làm đổi nghĩa một việc đã xong.
 *
 * @param result - `tool_result` của bước `start_drafting` đã đợi xong.
 * @returns Dòng kết quả, y như BE viết.
 */
function drafted(result: Record<string, unknown>): string {
  const written = Number(result.written ?? 0);
  const asked = Number(result.asked_for ?? 0);
  const running = Number(result.still_drafting ?? 0);
  if (running > 0)
    return `đã soạn ${written}/${asked} câu, còn ${running} câu đang chạy`;
  if (asked > 0 && written < asked) return `dừng ở ${written}/${asked} câu`;
  return `đã soạn ${written}/${asked} câu`;
}

/** Con số của một bước đã xong, lấy từ chính kết quả của nó. */
function outcome(turn: Turn): string {
  const result = turn.tool_result;
  if (turn.tool_name === "find_class") {
    return `${String(result.name ?? "")}, ${Number(result.student_count ?? 0)} học sinh`;
  }
  if (turn.tool_name === "create_draft") {
    return `đề "${String(result.title ?? "")}", cần ${Number(result.question_count ?? 0)} câu`;
  }
  if (turn.tool_name === "start_drafting") {
    // Bước đã đợi xong thì nó mang con số **thật**, và dòng này phải nói đúng câu mà khối
    // bước đang chạy đã nói — nếu không thì một lần F5 đổi `đã soạn 3/3 câu` thành `3 câu
    // bắt đầu soạn`, và giáo viên đọc ra là việc vừa quay về lúc mới bắt đầu.
    if (result.asked_for !== undefined) {
      return drafted(result);
    }
    return `${Number(result.queued ?? 0)} câu bắt đầu soạn`;
  }
  if (turn.tool_name === "draft_progress") {
    const written = Array.isArray(result.written) ? result.written.length : 0;
    const asked = Number(result.asked_for ?? 0);
    const running = Number(result.still_drafting ?? 0);
    const base = `${written}/${asked} câu đã về`;
    return running > 0 ? `${base}, còn ${running} đang soạn` : base;
  }
  return "";
}

/**
 * Những lượt nào trong một khối được lên thẻ.
 *
 * **Việc của model thì một thẻ; việc của giáo viên thì mỗi việc một thẻ.** Hai luật khác
 * nhau vì chúng trả lời hai câu hỏi khác nhau.
 *
 * Một lượt của model là *một* việc được nhờ, dù nó đi qua năm bước tool — nên nó có *một*
 * kết quả, và thẻ kể kết quả ấy. Quét **ngược** lấy cái đầu tiên đủ tư cách, vì kết quả là
 * thứ xảy ra sau cùng.
 *
 * Còn mỗi lần giáo viên tự duyệt hay tự bỏ duyệt là một **biên bản riêng**. ADR-24 đòi biên
 * bản duyệt phải sống sót, và bản trước của hàm này trả đúng một thẻ cho cả khối — nên
 * `unapprove` đè mất `approve`, và màn hình chỉ còn nói *"Đã bỏ duyệt đề"* như thể chưa ai
 * từng duyệt. Đo được trên hội thoại thật: hai lượt trong database, một thẻ trên màn hình.
 *
 * Đáng nói là comment ở `spoken()` lúc ấy đã tự khẳng định *"Nó vẫn lên thẻ, nên biên bản
 * không mất đi đâu (ADR-24)"* — một lời hứa sai nằm ngay cạnh chỗ phá nó.
 *
 * `start_drafting` đủ tư cách **khi và chỉ khi** nó đã đợi hết câu và mang con số thật về;
 * chưa có con số thì một thẻ ở đó nói với giáo viên rằng một việc đã xong trong khi nó vừa
 * mới bắt đầu.
 *
 * @param turns - Các lượt của một khối Kriky, theo thứ tự đã xảy ra.
 * @returns Các lượt được lên thẻ, theo đúng thứ tự thời gian. Rỗng khi không có lượt nào.
 */
export function cardTurns(turns: Turn[]): Turn[] {
  // **Cả hai loại cùng ở lại**, và bản đầu của hàm này sai đúng chỗ ấy: nó trả *chỉ*
  // việc của giáo viên khi khối có một việc như thế, với lý lẽ "khối ấy không có việc
  // nào của model để kể". Lý lẽ sai, vì `blocks()` chỉ cắt khối ở lượt `teacher` — mà
  // bấm *Duyệt đề* trên panel không sinh lượt `teacher` nào. Nên cú duyệt rơi vào **đúng
  // cái khối** model vừa soạn đề, và thẻ *Đã thêm N câu vào đề* biến mất cùng với cửa
  // duy nhất vào đề ấy. Đó là đúng cái bug `2026-10-03-chot-chang-a-plan.md` đã đi sửa.
  const keep = new Set<Turn>(
    turns.filter((one) => one.kind === "tool_result" && byTheTeacher(one)),
  );

  const one = modelCardTurn(turns);
  if (one !== null) keep.add(one);

  // Lọc theo `turns` chứ không ghép hai mảng: thứ tự thời gian là thứ kể đúng chuyện đã
  // xảy ra, và một cái thẻ *Đã duyệt* đứng trước thẻ *Đã soạn xong* đọc ra là duyệt một
  // đề chưa có câu nào.
  return turns.filter((turn) => keep.has(turn));
}

/**
 * Lượt kết quả của **model** trong một khối, hay `null`.
 *
 * @param turns - Các lượt của một khối Kriky, theo thứ tự đã xảy ra.
 * @returns Lượt được lên thẻ, hoặc `null`.
 */
function modelCardTurn(turns: Turn[]): Turn | null {
  // Đề đã bắt đầu được đổ câu vào thì trạng thái "trống" của nó không còn đứng vững: chính
  // bước sau đã thay nó. Một plan "tạo đề 10 câu" vì thế **không** mọc ra thẻ *Chưa có câu
  // hỏi nào* — một thẻ nói với giáo viên rằng việc được nhờ đã xong và cho ra một cái đề
  // rỗng, trong khi việc ấy đang chạy. Đề chưa đủ câu thì ở lại trong khối bước, và câu báo
  // cáo cuối lượt nói nó đang tới đâu (ADR-25).
  const filling = turns.some(
    (one) =>
      one.kind === "tool_result" &&
      one.tool_name === "start_drafting" &&
      one.tool_result.started !== false,
  );

  for (let index = turns.length - 1; index >= 0; index -= 1) {
    const turn = turns[index];
    if (turn.kind !== "tool_result") continue;
    // Việc của giáo viên đã có thẻ riêng, và nó không phải "kết quả của lượt model" —
    // không có nó thì một cú duyệt đứng cuối khối sẽ được chọn làm thẻ của model, rồi
    // `cardTurns` trả hai thẻ giống hệt nhau cho một hành động.
    if (byTheTeacher(turn)) continue;
    // Bước soạn **chưa đợi xong** vẫn không lên thẻ: không có con số nào thì một thẻ ở đó
    // nói một việc đã xong trong khi nó vừa mới bắt đầu. Bước đã đợi xong thì ngược lại —
    // nó là kết quả cuối cùng có hậu quả cho giáo viên, và trước đợt này nó bị loại vô điều
    // kiện. Hệ quả đã đo trên trình duyệt thật: một lượt soạn đề **thành công** kết thúc
    // không thẻ nào, mà panel đề chỉ mở được từ một nút trên thẻ — Kriky nói đã soạn xong và
    // không có cửa nào vào xem.
    if (
      turn.tool_name === "start_drafting" &&
      turn.tool_result.asked_for === undefined
    ) {
      continue;
    }
    if (
      turn.tool_name === "create_draft" &&
      filling &&
      turn.tool_result.created !== false
    ) {
      continue;
    }
    if (
      turn.tool_name === "find_class" ||
      turn.tool_name === "class_assessment_summary"
    )
      continue;
    // Đề chưa có câu nào thì `draft_progress` chưa phải một kết quả, nó mới là một lần ngó.
    if (turn.tool_name === "draft_progress") {
      const written = Array.isArray(turn.tool_result.written)
        ? turn.tool_result.written.length
        : 0;
      if (written === 0) continue;
    }
    return turn;
  }
  return null;
}

/**
 * Biên bản một hành động đã xảy ra, đặt trong luồng chat.
 *
 * Mọi chữ lấy từ **chính `tool_result` ấy**, và mọi nhãn nút lấy từ component
 * `Action result card` (`10:63`). Hai luật của cả tám variant:
 *
 * - **Mỗi thẻ mang một câu an toàn** nói việc vừa xong chưa tới tay học sinh. ADR-05 đặt ba
 *   cổng cho con người bước qua; một thẻ kể rằng máy vừa làm xong một việc mà im lặng về
 *   phần còn lại là một thẻ mời người ta tưởng là xong.
 * - **Nút mời bước tiếp theo**, không phải `Xem`. `Xem` luôn là nút phụ.
 *
 * Hai variant chưa dựng được, và lý do nằm ở dữ liệu chứ không ở màn hình: *tạo-lớp* không
 * có tool nào sinh ra, còn *phát-hành-thất-bại* không bao giờ tới đây vì `_note_publication`
 * chỉ ghi các lớp **thành công** — biểu mẫu phát hành phải tự hiện phần thất bại tại chỗ.
 *
 * @param turn - Bước đã lưu.
 * @param onOpen - Mở panel của một đề. Cửa **duy nhất** của một thẻ: đổi trạng thái đề là
 *   việc của chân panel, không phải của một biên bản đã nằm lại trong dòng chat.
 * @param onCompose - Điền sẵn một câu vào ô nhập. Đây là cách một nút *mời bước tiếp theo*
 *   khi bước ấy làm bằng lời nói chứ không bằng một endpoint — chuỗi rỗng là chỉ đặt con
 *   trỏ vào ô nhập.
 */
export default function ActionCard({
  turn,
  onOpen,
  onCompose,
}: {
  turn: Turn;
  onOpen: (assessmentId: string) => void;
  onCompose: (text: string) => void;
}) {
  const result = turn.tool_result;
  const paper = String(result.assessment_id ?? turn.entity_id ?? "");
  const title = String(result.title ?? "");
  const named = title === "" ? "" : ` "${title}"`;

  // Một tool từ chối: `reason` là câu của BE, in nguyên văn. Viết hoa hay thêm dấu chấm vào
  // đó là viết lại lời người khác, và câu gốc là câu đã được cân nhắc.
  if (refusal(result)) {
    return (
      <Card
        onOpen={paper === "" ? undefined : () => onOpen(paper)}
        tone="refused"
        head="Không tạo được đề"
        safety="Chưa có gì được thay đổi"
        actions={[
          { label: "Thử lại", onClick: () => onCompose(""), primary: true },
        ]}
      />
    );
  }

  if (turn.tool_name === "create_draft") {
    return (
      <Card
        onOpen={paper === "" ? undefined : () => onOpen(paper)}
        tone=""
        head={`Đã tạo đề${named}`}
        safety="Đề trống, chưa phát hành được"
        actions={[
          {
            label: "Thêm câu hỏi",
            onClick: () => onCompose("Soạn câu hỏi cho đề này"),
            primary: true,
          },
        ]}
      />
    );
  }

  if (turn.tool_name === "start_drafting") {
    const written = Number(result.written ?? 0);
    const asked = Number(result.asked_for ?? 0);
    const running = Number(result.still_drafting ?? 0);
    // **Đủ câu** là điều kiện duy nhất để mời duyệt, và nó không nhắc tới `still_drafting`.
    // Bản đầu viết ngược: nó coi "thiếu câu" là `written < asked && running === 0`, nên một
    // đề 3/10 mà bảy câu còn đang chạy rơi vào nhánh *còn lại* — thẻ in `Đã thêm 3 câu vào
    // đề` (không nhắc số 10) và mời **Duyệt đề**. Đường ra ấy có thật: hết hạn im lặng thì
    // `_wait_for_questions` rời vòng nghe với `still_drafting > 0`. Và nó cãi lại chính luật
    // ở `reporting._progress` của AGENT, nơi lời kể trong cùng ca ấy chỉ được nói *"đang
    // soạn"* chứ không mời duyệt — hai câu ngược nhau trên cùng một màn hình.
    const enough = asked > 0 && written >= asked;
    const head = enough
      ? `Đã thêm ${written} câu vào đề`
      : running > 0
        ? `Đã soạn ${written}/${asked} câu`
        : `Dừng ở ${written}/${asked} câu`;
    return (
      <Card
        onOpen={paper === "" ? undefined : () => onOpen(paper)}
        tone=""
        head={head}
        safety="Chưa duyệt · chưa phát hành"
      />
    );
  }

  if (turn.tool_name === "draft_progress") {
    const written = Array.isArray(result.written) ? result.written.length : 0;
    return (
      <Card
        onOpen={paper === "" ? undefined : () => onOpen(paper)}
        tone=""
        head={`Đã thêm ${written} câu vào đề`}
        safety="Chưa duyệt · chưa phát hành"
      />
    );
  }

  if (turn.tool_name === "teacher.approve") {
    return (
      <Card
        onOpen={paper === "" ? undefined : () => onOpen(paper)}
        tone=""
        head={`Đã duyệt đề${named}`}
        safety="Chưa phát hành cho học sinh"
        // Chỉ một cửa vào đề, không nút đổi trạng thái nào. Thẻ này là **biên bản** của một
        // việc giáo viên vừa làm, và chỗ đổi trạng thái của một đề là chân panel — nơi duy
        // nhất nói trạng thái **hiện tại**. Hai thẻ duyệt và bỏ duyệt nằm cạnh nhau trong
        // một đoạn chat cũ mà cả hai đều bấm được thì chúng nói hai chuyện trái nhau.
        //
        // Và ba cái nút cũ ở đây **không chạy**, đo được: duyệt thì bấm từ trong panel, nên
        // lúc thẻ hiện ra route đã là `.../de/{paper}` rồi, mà cả ba đều chỉ gọi `go()` tới
        // đúng route ấy. Gán lại một hash không đổi thì không có `hashchange` nào.
      />
    );
  }

  if (turn.tool_name === "teacher.unapprove") {
    return (
      <Card
        onOpen={paper === "" ? undefined : () => onOpen(paper)}
        tone=""
        head={`Đã bỏ duyệt đề${named}`}
        safety="Chưa duyệt · chưa phát hành"
      />
    );
  }

  if (turn.tool_name === "teacher.publish") {
    const classes = Array.isArray(result.classes)
      ? result.classes.map(String)
      : [];
    return (
      <Card
        onOpen={paper === "" ? undefined : () => onOpen(paper)}
        tone="settled"
        head={`Đã phát hành cho ${classes.length > 0 ? classes.join(" và ") : "lớp đã chọn"}`}
        // Thẻ có hậu quả lớn nhất mà im lặng về hậu quả thì là lỗi nặng nhất trong nhóm
        // này. Thu hồi **chỉ** được cho tới giờ mở của từng lớp (ADR-02), nên câu này nói
        // cả hai nửa: còn thu hồi được, và cái mốc chấm dứt việc đó.
        safety="Thu hồi được cho tới giờ mở của từng lớp, sau giờ mở thì không"
      />
    );
  }

  // Không rơi vào đây được: `cardTurns` đã lọc, và mọi tool còn lại là một bước. Nếu có ngày
  // nó rơi vào thì **không vẽ gì** — một thẻ in tên tool ra màn hình giáo viên là một chuỗi
  // kỹ thuật lọt ra bề mặt, tệ hơn hẳn một thẻ vắng mặt.
  return null;
}

/**
 * Hình dạng chung của mọi variant: một đầu đề có chấm, một câu an toàn, và đôi khi một nút.
 *
 * **Bấm vào thẻ là mở panel đề.** Trước đó mỗi thẻ mang một nút `Duyệt đề` / `Xem đề` /
 * `Xem`, và cả năm nhãn ấy gọi đúng một hàm — `onOpen(paper)`. Năm cách gọi tên cho một
 * việc là năm lời hứa khác nhau về một thứ, nên chúng rút về chính cái thẻ.
 *
 * Nút chỉ còn ở những chỗ làm việc **khác**: `Thử lại` và `Thêm câu hỏi` điền sẵn ô nhập,
 * vì bước ấy làm bằng lời nói chứ không bằng một endpoint. Chúng chặn nổi bọt, nếu không
 * một cú bấm vào chúng vừa điền ô nhập vừa mở panel.
 *
 * @param tone - Sắc thẻ: thường, đã xong, hay bị từ chối.
 * @param head - Việc vừa xảy ra.
 * @param safety - Hậu quả, in thành chip ở mép phải dòng đầu đề.
 * @param actions - Nút làm việc khác với "mở đề". Thường rỗng.
 * @param onOpen - Mở panel đề. Bỏ trống khi thẻ này không có đề nào để mở — một thẻ bấm
 *   được mà chẳng mở gì tệ hơn hẳn một thẻ nằm yên.
 */
function Card({
  tone,
  head,
  safety,
  actions = [],
  onOpen,
}: {
  tone: "" | "settled" | "refused";
  head: string;
  safety?: string;
  actions?: { label: string; onClick: () => void; primary?: boolean }[];
  onOpen?: () => void;
}) {
  const open = onOpen !== undefined;
  return (
    <div
      className={`action-card ${tone} ${open ? "open-able" : ""}`}
      // `role` và `tabIndex` chứ không phải một `<button>` bọc ngoài: thẻ chứa nút, và
      // một nút lồng trong nút là HTML sai — trình duyệt tự gỡ nó ra, và cú bấm rơi vào
      // chỗ không ai đoán được.
      role={open ? "button" : undefined}
      tabIndex={open ? 0 : undefined}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (!open) return;
        if (event.key !== "Enter" && event.key !== " ") return;
        // Space cuộn trang nếu không chặn, và một thẻ mở ra kèm một cú nhảy trang thì
        // giáo viên mất chỗ đang đọc.
        event.preventDefault();
        onOpen();
      }}
    >
      <div className="head">
        {/* Câu an toàn đi **cùng dòng** với đầu đề: cả hai nói về một sự việc — việc gì vừa
            xảy ra, và nó đã tới tay học sinh chưa. Tách làm hai dòng là xé một câu làm đôi,
            và trên một thẻ chỉ còn hai thành phần thì dòng thừa ấy càng rõ. */}
        <span className="dot" aria-hidden="true" />
        <span className="what">{head}</span>
        {safety !== undefined && <span className="safety">{safety}</span>}
      </div>
      {actions.length > 0 && (
        <div className="actions">
          {actions.map((one) => (
            <button
              className={`btn ${one.primary === true ? "primary" : ""}`}
              key={one.label}
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                one.onClick();
              }}
            >
              {one.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
