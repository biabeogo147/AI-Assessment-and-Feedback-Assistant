import { useState } from "react";

import { teacher, type PaperProgress } from "../../api";
import { go } from "../../App";
import { BoardHead, BoardWaiting, classLabel, NONE, useBoard } from "./Board";
import Veil from "./Veil";

/** Ba cột tiến độ: khoá của `ClassRow`/`PaperProgress`, và chữ in hoa của đầu cột và popover. */
// Chữ ngắn để đầu cột nằm một dòng (người dùng chốt 19/10/2026, artboard 9).
const PROGRESS = [
  { key: "not_submitted", head: "CHƯA NỘP BÀI" },
  { key: "phase_one", head: "XONG GIAI ĐOẠN 1" },
  { key: "phase_two", head: "XONG GIAI ĐOẠN 2" },
] as const;

type Progress = (typeof PROGRESS)[number]["key"];

/**
 * Màn 9 · *Danh sách lớp học* (`180:753`), plan `teacher-rail-screens`, việc 18.
 *
 * Mỗi lớp một hàng: sĩ số, *khối / môn*, số đề đang mở, và ba cột tiến độ cộng trên các đề đang mở.
 * Mọi con số do BE đếm theo giờ của BE; lớp không có đề đang mở thì ba cột ghi *"—"*. Rê chuột lên
 * một ô tiến độ thì popover (`Class progress popover`, `665:62`) chia con số ấy theo từng đề.
 *
 * Nút *Tạo lớp* mở hộp nhập tên (plan `tao-lop`, hậu ký ADR-13 27/10/2026); tạo xong thì sang màn
 * 10 của lớp ấy, nơi có *Thêm học sinh*. Chưa có lớp nào thì bảng có một hàng empty state
 * `chua-co-lop` (`179:16`).
 */
export default function Classes() {
  const { data, trouble } = useBoard(() => teacher.classes(), "classes");
  // Ô đang được rê chuột: lớp nào, cột nào. Một popover một lúc.
  const [hover, setHover] = useState<{ classId: string; key: Progress } | null>(null);
  const [creating, setCreating] = useState(false);
  const create = (
    <button className="board-export" type="button" onClick={() => setCreating(true)}>
      Tạo lớp
    </button>
  );
  const dialog = creating && <CreateClass onClose={() => setCreating(false)} />;

  if (data === null) {
    return (
      <div className="board">
        {/* Danh sách đọc lỗi thì vẫn tạo được lớp: nút không chờ bảng. */}
        <BoardHead title="Danh sách lớp học" sub="" action={create} />
        <BoardWaiting trouble={trouble} />
        {dialog}
      </div>
    );
  }

  return (
    <div className="board">
      <BoardHead
        title="Danh sách lớp học"
        sub={`${data.classes.length} lớp · ${data.student_total} học sinh`}
        action={create}
      />
      <div className="board-table classes fill" role="table">
        <div className="board-row head" role="row">
          <span>LỚP</span>
          <span>KHỐI / MÔN</span>
          <span className="num">SĨ SỐ</span>
          <span className="num">ĐỀ ĐANG MỞ</span>
          {PROGRESS.map((one) => (
            <span className="num" key={one.key}>
              {one.head}
            </span>
          ))}
          <span />
        </div>
        {data.classes.length === 0 && (
          // Empty state `chua-co-lop` (`179:16`), cùng cách màn 10 viết *chưa có học sinh*.
          <div className="board-row empty" role="row">
            Chưa có lớp nào. Tạo lớp rồi nhập danh sách học sinh — Kriky sẽ tạo tài khoản cho từng em.
          </div>
        )}
        {data.classes.map((row) => (
          <div
            className="board-row open-able"
            role="row"
            key={row.class_id}
            tabIndex={0}
            onClick={() => go(`/teacher/lop/${row.class_id}`)}
            onKeyDown={(event) => {
              if (event.key === "Enter") go(`/teacher/lop/${row.class_id}`);
            }}
          >
            <span className="name">{classLabel(row.name)}</span>
            <span className="cell-muted">{row.courses || NONE}</span>
            <span className="num">{row.student_count}</span>
            <span className="num">{row.open_count}</span>
            {PROGRESS.map((one) => (
              <span
                className={`num progress ${row[one.key] === null ? "cell-faint" : ""}`}
                key={one.key}
                // Bàn phím cũng mở được popover: ô có focus thì nó hiện, như khi rê chuột.
                tabIndex={row.by_paper.length > 0 ? 0 : undefined}
                onMouseEnter={() => setHover({ classId: row.class_id, key: one.key })}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover({ classId: row.class_id, key: one.key })}
                onBlur={() => setHover(null)}
              >
                {row[one.key] ?? NONE}
                {hover?.classId === row.class_id &&
                  hover.key === one.key &&
                  row.by_paper.length > 0 && (
                    <Popover
                      head={one.head}
                      total={row[one.key] ?? 0}
                      papers={row.by_paper}
                      pick={one.key}
                    />
                  )}
              </span>
            ))}
            <span className="chevron" aria-hidden="true">
              ›
            </span>
          </div>
        ))}
      </div>
      {dialog}
    </div>
  );
}

/**
 * Hộp *Tạo lớp* (artboard 9b, plan `tao-lop`): một ô tên, *Huỷ* / *Tạo lớp*.
 *
 * Luật tên là của BE (`be.classes.create_class`): hộp chỉ in câu BE từ chối -- trùng tên, tên rỗng
 * -- ngay dưới ô, và hộp không đóng. Đang gửi thì nút và Enter đều khoá: hai cú bấm liền không mở hai
 * lớp cùng tên. Tạo xong thì sang màn 10 của lớp mới.
 *
 * @param onClose - Đóng hộp mà không tạo gì.
 */
function CreateClass({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState("");

  async function submit() {
    // Enter đi cùng luật với nút: tên rỗng thì không gửi.
    if (working || name.trim() === "") return;
    setWorking(true);
    setRefused("");
    try {
      const created = await teacher.createClass(name);
      go(`/teacher/lop/${created.class_id}`);
    } catch (cause) {
      setRefused((cause as Error).message);
      setWorking(false);
    }
  }

  return (
    // Đang gửi thì không đóng được: đóng xong mà lời gửi thành công thì giáo viên bị đưa sang một lớp
    // họ tưởng đã huỷ, còn lời từ chối thì mất (review plan `tao-lop`).
    <Veil onClose={() => !working && onClose()} inert className="create-class">
      <h3>Tạo lớp mới</h3>
      <p className="lead">Lớp mới chưa có học sinh. Thêm học sinh ở màn của lớp sau khi tạo.</p>
      <label className="sign-field">
        <span>Tên lớp</span>
        <input
          type="text"
          autoFocus
          maxLength={64}
          placeholder="Ví dụ: 12C"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            setRefused("");
          }}
          onKeyDown={(event) => {
            // Đang gõ dấu (bộ gõ tiếng Việt) thì Enter là của bộ gõ, không phải lệnh tạo.
            if (event.key === "Enter" && !event.nativeEvent.isComposing) void submit();
          }}
        />
      </label>
      {refused !== "" && (
        <p className="refused" role="alert">
          {refused}
        </p>
      )}
      <div className="confirm-actions">
        <button className="btn" type="button" disabled={working} onClick={onClose}>
          Huỷ
        </button>
        <button
          className="btn primary"
          type="button"
          disabled={working || name.trim() === ""}
          onClick={() => void submit()}
        >
          Tạo lớp
        </button>
      </div>
    </Veil>
  );
}

/**
 * Popover chia một ô tiến độ theo từng đề đang mở (`Class progress popover`, `665:62`).
 *
 * @param head - Tên cột, in hoa.
 * @param total - Con số của ô, đúng như BE gửi -- một nguồn, không cộng lại ở đây.
 * @param papers - Các đề đang mở của lớp.
 * @param pick - Con số nào của mỗi đề.
 */
function Popover({
  head,
  total,
  papers,
  pick,
}: {
  head: string;
  total: number;
  papers: PaperProgress[];
  pick: Progress;
}) {
  return (
    <div className="progress-popover" role="tooltip">
      <div className="pop-head">
        {head} · {total}
      </div>
      {papers.map((one) => (
        <div className="pop-row" key={one.assessment_id}>
          <span>{one.title}</span>
          <span className="num">{one[pick]}</span>
        </div>
      ))}
    </div>
  );
}

