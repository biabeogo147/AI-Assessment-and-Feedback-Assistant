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
  list_class: "Xem các lớp",
  get_class: "Xem một lớp",
  list_assessment: "Xem các đề của lớp",
  class_assessment_summary: "Xem kết quả một đề",
  create_draft: "Tạo đề trống",
  start_drafting: "Soạn câu hỏi",
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
  if (turn.tool_name === "list_class") {
    const shown = Array.isArray(result.candidates) ? result.candidates.length : 0;
    const cut = Number(result.more ?? 0);
    return cut > 0 ? `${shown} lớp, còn ${cut} lớp nữa` : `${shown} lớp`;
  }
  if (turn.tool_name === "get_class") {
    return `${String(result.name ?? "")}, ${Number(result.student_count ?? 0)} học sinh`;
  }
  if (turn.tool_name === "list_assessment") {
    const shown = Array.isArray(result.assessments) ? result.assessments.length : 0;
    return `${shown} đề`;
  }
  // `create_draft` thôi nói số câu: một đề trống chưa có số câu nào để nói. Con số ấy về
  // `start_drafting`, và dòng dưới đây là chỗ nó được đọc ra.
  if (turn.tool_name === "create_draft") {
    return `đề "${String(result.title ?? "")}"`;
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
  return "";
}

/**
 * Những lượt nào trong một khối được lên thẻ.
 *
 * **Việc của model thì một thẻ cho cả lượt; việc của giáo viên thì một thẻ cho mỗi ĐỀ.**
 * Hai luật khác nhau vì chúng trả lời hai câu hỏi khác nhau.
 *
 * Một lượt của model là *một* việc được nhờ, dù nó đi qua năm bước tool — nên nó có *một*
 * kết quả, và thẻ kể kết quả ấy. Quét **ngược** lấy cái đầu tiên đủ tư cách, vì kết quả là
 * thứ xảy ra sau cùng.
 *
 * Còn việc giáo viên tự làm thì thẻ kể **trạng thái của một đề**, không kể từng cú bấm.
 * Duyệt rồi hoàn tác rồi duyệt lại là một trạng thái đi qua bốn bước, không phải bốn kết
 * quả — vẽ cả bốn cho ra một chồng thẻ nói luân phiên hai câu. Đo được trên hội thoại
 * thật: bốn lượt trong database, bốn thẻ chồng nhau trên màn hình, và không thẻ nào nói
 * thêm gì so với thẻ cuối.
 *
 * **Một thẻ cho cả khối, không hơn**, và đó là luật người dùng chốt: *"thẻ chỉ xuất hiện
 * một lần trong một đợt xử lí, không được phép xuất hiện hai lần liên tiếp"*. Nên cú bấm
 * cuối cùng thắng, kể cả thẻ của model trong cùng khối — đề vừa soạn vẫn vào được, vì cú
 * bấm ấy nằm trên chính đề đó.
 *
 * **Chỗ này còn một giới hạn, và nó có thật:** duyệt đề A rồi phát hành đề B trong cùng
 * một khối cho ra **một** thẻ — thẻ của B — còn A không được kể. Hàm không đọc `entity_id`,
 * nên nó không phân biệt được hai đề. Chưa sửa vì chưa có đường nào tới được cảnh ấy: một
 * khối bị cắt ở mỗi lượt `teacher`, và hai đề khác nhau trong một khối cần giáo viên bấm
 * trên hai panel mà không gõ gì ở giữa.
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
  //
  // **Nhưng một đề thì một thẻ, không phải một thẻ cho mỗi cú bấm.** Duyệt rồi hoàn tác
  // rồi duyệt lại là **một** trạng thái đi qua bốn bước, không phải bốn kết quả — và vẽ
  // cả bốn cho ra một chồng thẻ nói luân phiên hai câu, đo được trên hội thoại thật.
  // Thẻ kể *đề này đang ở đâu*, nên nó là cú bấm **cuối cùng** trên đề ấy.
  //
  // Bản trước giữ cả bốn, viện ADR-24 rằng "biên bản duyệt phải sống sót". Đọc sai:
  // ADR-24 nói biên bản rơi vào **đoạn chat nào**, không nói màn hình vẽ bao nhiêu thẻ.
  // Biên bản sống ở `teacher_turns` và không cú bấm nào xoá nó; cái thẻ là một **ô cửa
  // nhìn vào trạng thái**, không phải cuốn sổ.
  //
  const drafted = modelCardTurn(turns);

  // Cú bấm cuối cùng của giáo viên trong khối. Nó, chứ không phải cả dãy, quyết định đề
  // đang đứng ở nấc nào.
  let acted: Turn | null = null;
  for (const one of turns) {
    if (one.kind === "tool_result" && byTheTeacher(one)) acted = one;
  }

  if (acted === null) return drafted === null ? [] : [drafted];

  // **Bỏ duyệt đưa đề VỀ nấc một**, và nó không cần một nhánh riêng: `cardState` đã dịch
  // `teacher.unapprove` thành `drafted`, nên chính lượt ấy vẽ ra đúng thẻ *Đã tạo đề*.
  //
  // Bản trước có một nhánh riêng trả thẻ của model, và nó **mất thẻ** ở một ca có thật:
  // `blocks()` chỉ cắt khối ở lượt `teacher` gõ tay, nên một giáo viên gõ *"cảm ơn"* rồi
  // mở một đề cũ, bấm Duyệt, bấm Hoàn tác — cả hai cú bấm rơi vào một khối không có việc
  // nào của model, `modelCardTurn` trả `null`, và màn hình còn **0 thẻ**. Thẻ `Đã duyệt
  // đề` biến mất cùng với cửa duy nhất vào panel đề.
  return [acted];
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
    // **Chỉ tool có một nấc mới lên thẻ**, và đó là mặc định an toàn trở lại. Bản trước
    // liệt kê các tool *đọc* để loại chúng ra — một danh sách viết cứng, nên tool đọc thứ
    // năm sẽ lọt qua và mọc ra một thẻ. Mà `cardState` thì mặc định `drafted`, nên cái thẻ
    // ấy khẳng định một cái đề đã tồn tại cho một tool chưa ai biết làm gì.
    //
    // Hỏi `STATE_OF` thì danh sách tự đi theo danh mục: thêm một tool **ghi** là thêm một
    // dòng ở đó, còn một tool **đọc** không cần ai nhớ loại nó ra. Cùng cách `STEP_TITLE`
    // mặc định an toàn — thiếu một dòng thì nó là một bước, mà một bước không hứa gì.
    if (!(turn.tool_name in STATE_OF)) continue;
    return turn;
  }
  return null;
}

/**
 * Ba nấc của một đề, cộng một nấc cho việc **không** xảy ra.
 *
 * `drafted` → `approved` → `published` là đúng ba trạng thái người dùng chốt ngày
 * 06/10/2026, và `failed` không phải nấc thứ tư của đề — nó là *chưa có gì thay đổi*.
 */
export type CardState = "drafted" | "approved" | "published" | "failed";

/**
 * Tool nào đưa đề tới nấc nào.
 *
 * Đây là chỗ duy nhất **dịch tool thành nấc**, và nó là một bảng chứ không phải một cây
 * quyết định: thêm một tool là thêm một dòng ở đây, không phải một nhánh nữa trong phần
 * vẽ. Trước đợt này `ActionCard` có **bảy** nhánh `if (turn.tool_name === …)`, nên mỗi
 * tool mới là một trạng thái mới trên màn hình giáo viên — đúng cái làm bảy đầu đề mọc ra
 * từ một thiết kế ba nấc.
 *
 * Bảng này cũng là **danh sách tool được lên thẻ**: `modelCardTurn` hỏi nó thay vì giữ một
 * danh sách tool đọc viết cứng, nên một tool đọc mới không cần ai nhớ loại nó ra.
 *
 * `teacher.unapprove` về `drafted`: bỏ duyệt đưa đề **về** nấc một, nên nó không có nấc
 * riêng.
 */
const STATE_OF: Record<string, CardState> = {
  create_draft: "drafted",
  start_drafting: "drafted",
  "teacher.approve": "approved",
  "teacher.unapprove": "drafted",
  "teacher.publish": "published",
};

/**
 * Bốn đầu đề, và **chỉ** bốn.
 *
 * Một bảng chứ không phải một dãy `if`: số dòng ở đây là số trạng thái đọc được trên màn
 * hình, nên nó đếm được — `tools/check_contract.py` đọc cây cú pháp của file này và đỏ khi
 * bảng mọc thêm dòng. Một nhánh `if` thì không đếm được bằng cách nào rẻ như thế.
 *
 * `{tên}` chỉ đi với hai nấc đầu. `Đã phát hành` **không** chở tên lớp: danh sách lớp thuộc
 * về hộp xác nhận và bảng kết quả, không thuộc một dòng tiêu đề — một thẻ ghi *"Đã phát
 * hành cho 12A và 12B"* là một trạng thái thứ tư trá hình, vì nó đổi chữ theo dữ liệu.
 */
const HEAD: Record<CardState, (named: string) => string> = {
  drafted: (named) => `Đã tạo đề${named}`,
  approved: (named) => `Đã duyệt đề${named}`,
  published: () => "Đã phát hành",
  failed: () => "Không tạo được đề",
};

/** Câu an toàn của từng nấc: việc vừa xong đã tới tay học sinh chưa, và còn lùi được không. */
const SAFETY: Record<CardState, string> = {
  drafted: "Chưa duyệt · chưa phát hành",
  approved: "Chưa phát hành cho học sinh",
  published: "Thu hồi được cho tới giờ mở, sau giờ mở thì không",
  failed: "Chưa có gì được thay đổi",
};

/**
 * Nấc mà một lượt đưa đề tới.
 *
 * @param turn - Lượt `tool_result` đã được `cardTurns` chọn.
 * @returns Một trong bốn nấc, hoặc `null` khi tool ấy không có nấc nào. `failed` thắng mọi
 *   nấc khác: một việc không xảy ra thì không đưa đề đi đâu cả.
 *
 *   `null` chứ không phải một nấc mặc định, và đó là mặc định **an toàn**: một tool chưa ai
 *   biết làm gì mà cho ra `Đã tạo đề · Chưa duyệt · chưa phát hành` là một thẻ khẳng định
 *   một cái đề đã tồn tại. Không vẽ gì thì tệ hơn hẳn — nhưng tệ theo cách nhìn thấy được.
 */
export function cardState(turn: Turn): CardState | null {
  const reached = STATE_OF[turn.tool_name];
  if (reached === undefined) return null;
  return refusal(turn.tool_result) ? "failed" : reached;
}

/**
 * Biên bản một hành động đã xảy ra, đặt trong luồng chat.
 *
 * Mọi chữ lấy từ `HEAD`/`SAFETY` theo **nấc**, không theo tên tool, và các nhãn nút lấy từ
 * component `Action result card` (`10:63`). Hai luật của cả bốn nấc:
 *
 * - **Mỗi thẻ mang một câu an toàn** nói việc vừa xong chưa tới tay học sinh. ADR-05 đặt ba
 *   cổng cho con người bước qua; một thẻ kể rằng máy vừa làm xong một việc mà im lặng về
 *   phần còn lại là một thẻ mời người ta tưởng là xong.
 * - **Nút mời bước tiếp theo**, không phải `Xem`. Bấm vào chính cái thẻ là mở panel đề.
 *
 * Năm variant của Figma đã thành *(không dùng)*, và lý do nằm ở dữ liệu chứ không ở màn
 * hình: *tạo-lớp* không có tool nào sinh ra; *phát-hành-thất-bại* không bao giờ tới đây vì
 * `_note_publication` chỉ ghi lượt khi phát hành **thành công**; *thiếu-câu* và
 * *đang-soạn-dở* chở con số câu hỏi, mà con số ấy đã nằm ở khối `Thinking` ngay trên thẻ;
 * và *bỏ-duyệt* thì bỏ duyệt đưa đề **về** nấc một nên nó không có nấc riêng.
 *
 * @param turn - Lượt đã được `cardTurns` chọn.
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
  const state = cardState(turn);

  // Không nấc nào thì **không vẽ gì**. `cardTurns` đã lọc, nên đường này không tới được
  // hôm nay; nếu có ngày nó tới thì một thẻ vắng mặt tệ hơn hẳn một thẻ nói sai.
  if (state === null) return null;

  // Một đề vừa mở mà chưa ai đổ câu vào thì nút mời đúng bước tiếp theo. Đây **không** phải
  // một nấc thứ năm: đầu đề vẫn là `Đã tạo đề`, chỉ khác câu an toàn và một cái nút. Figma
  // gọi nó là variant `tạo-đề-trống`, cùng một nấc với `đã-tạo-đề`.
  const empty = state === "drafted" && turn.tool_name === "create_draft";

  const actions =
    state === "failed"
      ? [{ label: "Thử lại", onClick: () => onCompose(""), primary: true }]
      : empty
        ? [
            {
              label: "Thêm câu hỏi",
              onClick: () => onCompose("Soạn câu hỏi cho đề này"),
              primary: true,
            },
          ]
        : [];

  return (
    <Card
      onOpen={paper === "" ? undefined : () => onOpen(paper)}
      tone={state === "failed" ? "refused" : state === "published" ? "settled" : ""}
      head={HEAD[state](named)}
      safety={empty ? "Đề trống, chưa phát hành được" : SAFETY[state]}
      actions={actions}
    />
  );
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
