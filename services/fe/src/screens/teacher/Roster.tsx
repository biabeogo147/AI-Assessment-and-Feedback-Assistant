import { useRef, useState } from "react";

import { teacher, type RosterAccount, type RosterRow } from "../../api";
import { useInert } from "./Veil";

type Via = "type" | "file";

/**
 * *Thêm học sinh* của màn 10 (việc 22, plan `sign-in-and-accounts`): ba bước trong một hộp 760.
 *
 * 1. Nhập (Figma 28 `660:5367`): gõ tên, mỗi dòng một em -- hay tải một tệp `.csv`/`.xlsx` một cột
 *    họ tên (28d `711:5287`).
 * 2. Xem trước (28b `660:5512`): tên đăng nhập sẽ cấp và ghi chú *Mới* / *Trùng tên trong lớp*. Ô
 *    *Xác nhận* chỉ bật ở dòng trùng; dòng trùng chưa xác nhận thì không được tạo.
 * 3. Mật khẩu (28c `660:5677`): hiện **một lần**, kèm *Xuất file Excel (.xlsx)*.
 *
 * Hộp không đóng bằng `Esc` hay bấm ra ngoài: ở bước 3 làm thế là mất mật khẩu không lấy lại được,
 * và một hộp đóng được ở bước này mà không ở bước kia là một hộp khó đoán. Mỗi bước có nút của nó.
 *
 * @param classId - Lớp nào.
 * @param name - Tên lớp như BE gửi (`12A`, hay một tên tự đặt).
 * @param onCreated - Vừa tạo xong: màn đọc lại danh sách lớp.
 * @param onClose - Đóng hộp.
 */
export default function Roster({
  classId,
  name,
  onCreated,
  onClose,
}: {
  classId: string;
  name: string;
  onCreated: () => void;
  onClose: () => void;
}) {
  const [via, setVia] = useState<Via>("type");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [rows, setRows] = useState<RosterRow[] | null>(null);
  const [sure, setSure] = useState<boolean[]>([]);
  const [made, setMade] = useState<RosterAccount[] | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const veil = useRef<HTMLDivElement>(null);
  useInert(veil);

  /**
   * Chạy một lời gọi của hộp: khoá nút trong lúc chờ, bị từ chối thì giữ câu của BE.
   *
   * @param work - Lời gọi và những gì nó ghi vào state.
   */
  async function run(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setRefused(null);
    try {
      await work();
    } catch (cause) {
      setRefused((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  /** Bước 1 → 2: hỏi BE bảng xem trước, từ chữ đã gõ hay từ tệp đã chọn. Không ghi gì ở BE. */
  function preview() {
    void run(async () => {
      const found =
        via === "type"
          ? await teacher.rosterPreview(classId, text.split("\n"))
          : await teacher.rosterPreviewFile(classId, file as File);
      setRows(found.rows);
      setSure(found.rows.map(() => false));
    });
  }

  /**
   * Bước 2 → 3: tạo tài khoản. BE tính lại mọi thứ và chỉ tạo dòng mới hay dòng trùng đã xác nhận.
   *
   * Không tạo được em nào -- lần bấm trước đã tạo rồi mà lời đáp mất, hay một tab khác vừa thêm đúng
   * các em ấy -- thì ở lại bước 2 và nói ra, không sang một bảng mật khẩu rỗng (review pha 4).
   *
   * @param shown - Các dòng đang hiện, cùng thứ tự với ô *Xác nhận*.
   */
  function create(shown: RosterRow[]) {
    void run(async () => {
      const done = await teacher.rosterCreate(
        classId,
        shown.map((row, index) => ({ full_name: row.full_name, confirmed: sure[index] })),
      );
      onCreated();
      if (done.accounts.length === 0) {
        setRefused("Chưa tạo tài khoản nào: các em này đã có trong lớp. Hãy quay lại xem danh sách.");
        return;
      }
      setMade(done.accounts);
    });
  }

  if (made !== null) {
    return (
      <Passwords
        title={`Đã tạo ${made.length} tài khoản`}
        accounts={made}
        onExport={() => teacher.rosterPasswords(classId, made)}
        onClose={onClose}
      />
    );
  }

  if (rows !== null) {
    const keep = rows.filter((row, index) => row.note === "new" || sure[index]).length;
    const waiting = rows.filter((row, index) => row.note === "duplicate" && !sure[index]).length;
    return (
      <div className="veil" role="dialog" aria-modal="true" aria-labelledby="roster-title" ref={veil}>
        <div className="roster">
          <h2 id="roster-title">Kiểm tra lại trước khi tạo tài khoản</h2>
          <div className="roster-table check" role="table">
            <div className="roster-row head" role="row">
              <span>HỌ VÀ TÊN</span>
              <span>TÊN ĐĂNG NHẬP</span>
              <span>GHI CHÚ</span>
              <span className="mid">XÁC NHẬN</span>
            </div>
            <div className={rows.length > 8 ? "roster-body long" : "roster-body"}>
              {rows.map((row, index) => (
                <div className="roster-row" role="row" key={`${index}-${row.full_name}`}>
                  <span className="name">{row.full_name}</span>
                  <span className="mono">{row.username}</span>
                  <span className={row.note === "duplicate" ? "twin" : "fresh"}>
                    {row.note === "duplicate" ? "Trùng tên trong lớp" : "Mới"}
                  </span>
                  <span className="mid">
                    <span
                      className="roster-tip"
                      data-tip={row.note === "duplicate" ? "Xác nhận thêm học sinh" : undefined}
                    >
                      <input
                        className="roster-check"
                        type="checkbox"
                        aria-label={`Xác nhận thêm ${row.full_name}`}
                        disabled={row.note !== "duplicate"}
                        checked={sure[index]}
                        onChange={(event) => {
                          // Câu lỗi cũ đứng chỗ con số *Sẽ tạo N*; đổi ô là con số phải quay lại.
                          setRefused(null);
                          setSure(sure.map((one, at) => (at === index ? event.target.checked : one)));
                        }}
                      />
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="roster-actions">
            <Note
              refused={refused}
              text={[`Sẽ tạo ${keep} tài khoản`, waiting > 0 ? `${waiting} học sinh cần xác nhận` : ""]
                .filter(Boolean)
                .join(" · ")}
            />
            <button
              className="roster-quiet"
              type="button"
              onClick={() => {
                setRefused(null);
                setRows(null);
              }}
              disabled={busy}
            >
              Quay lại
            </button>
            <button
              className="roster-primary"
              type="button"
              disabled={busy || keep === 0}
              autoFocus
              onClick={() => create(rows)}
            >
              Tạo {keep} tài khoản
            </button>
          </div>
        </div>
      </div>
    );
  }

  const ready = via === "type" ? text.trim() !== "" : file !== null;
  return (
    <div className="veil" role="dialog" aria-modal="true" aria-labelledby="roster-title" ref={veil}>
      <div className="roster">
        {/* *vào lớp 12A*; một tên tự đặt thì giữ nguyên, như `classLabel`. */}
        <h2 id="roster-title">Thêm học sinh vào {/^\d/.test(name) ? `lớp ${name}` : name}</h2>
        <div className="sign-tabs roster-tabs" role="radiogroup" aria-label="Cách thêm">
          {(
            [
              ["type", "Gõ tên"],
              ["file", "Tải tệp .csv / .xlsx"],
            ] as const
          ).map(([one, label]) => (
            <button
              key={one}
              type="button"
              role="radio"
              aria-checked={via === one}
              onClick={() => {
                setVia(one);
                setRefused(null);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="roster-hint">
          {via === "type"
            ? "Mỗi dòng một học sinh: họ và tên. Mã học sinh và tên đăng nhập do Kriky tạo."
            : "Một cột họ và tên, dòng tiêu đề có thể có. Mã học sinh và tên đăng nhập do Kriky tạo."}
        </p>
        {via === "type" ? (
          <textarea
            className="roster-names"
            aria-label="Họ và tên, mỗi dòng một học sinh"
            autoFocus
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        ) : (
          <div className="roster-file">
            <input
              ref={picker}
              type="file"
              accept=".csv,.xlsx"
              hidden
              onChange={(event) => {
                // Huỷ hộp chọn tệp thì giữ tệp đã chọn; chọn lại đúng tệp ấy (vừa sửa xong) vẫn phải
                // chạy `onChange`, nên ô được xoá sau mỗi lần chọn (review pha 4).
                const chosen = event.target.files?.[0];
                if (chosen) setFile(chosen);
                event.target.value = "";
                setRefused(null);
              }}
            />
            <button
              className="roster-quiet bordered"
              type="button"
              autoFocus
              onClick={() => picker.current?.click()}
            >
              {file === null ? "Chọn tệp" : "Chọn tệp khác"}
            </button>
            <span className={file === null ? "roster-file-name none" : "roster-file-name"}>
              {file === null ? "Chưa chọn tệp nào · tối đa 1 MB" : file.name}
            </span>
          </div>
        )}
        <div className="roster-actions">
          <Note refused={refused} text="" />
          <button className="roster-quiet" type="button" onClick={onClose} disabled={busy}>
            Đóng
          </button>
          <button className="roster-primary" type="button" disabled={busy || !ready} onClick={preview}>
            Xem trước
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Hộp mật khẩu chỉ hiện một lần: bước 3 của *Thêm học sinh* (28c) và *Đặt lại mật khẩu* (10b
 * `707:5377`). Đóng rồi là hết -- BE không giữ mật khẩu rõ nào để hiện lại.
 *
 * @param title - Tiêu đề hộp.
 * @param accounts - Các tài khoản, theo thứ tự.
 * @param onExport - Tải tệp `.xlsx` mật khẩu; không có thì không có nút (10b).
 * @param onClose - *Đã lưu, đóng*.
 */
export function Passwords({
  title,
  accounts,
  onExport,
  onClose,
}: {
  title: string;
  accounts: RosterAccount[];
  onExport?: () => Promise<void>;
  onClose: () => void;
}) {
  const [refused, setRefused] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const veil = useRef<HTMLDivElement>(null);
  useInert(veil);
  return (
    <div className="veil" role="dialog" aria-modal="true" aria-labelledby="passwords-title" ref={veil}>
      <div className="roster">
        <h2 id="passwords-title">{title}</h2>
        {/* Câu người dùng chốt nguyên văn (18/10/2026). Dòng trùng chưa xác nhận thì bước 2 đã nói
            *"N học sinh cần xác nhận"* ngay trên nút tạo, nên ở đây không nhắc lại. */}
        <p className="roster-lead">Hãy lưu lại mật khẩu — chỉ hiển thị một lần duy nhất.</p>
        <div className="roster-table passwords" role="table">
          <div className="roster-row head" role="row">
            <span>HỌ VÀ TÊN</span>
            <span>TÊN ĐĂNG NHẬP</span>
            <span>MẬT KHẨU</span>
          </div>
          <div className={accounts.length > 8 ? "roster-body long" : "roster-body"}>
            {accounts.map((one) => (
              <div className="roster-row" role="row" key={one.student_id}>
                <span className="name">{one.full_name}</span>
                <span className="mono">{one.username}</span>
                <span className="mono">{one.password}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="roster-actions">
          <Note refused={refused} text="" />
          {onExport !== undefined && (
            <button
              className="roster-quiet bordered"
              type="button"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                setRefused(null);
                onExport()
                  .catch((cause: Error) => setRefused(cause.message))
                  .finally(() => setBusy(false));
              }}
            >
              Xuất file Excel (.xlsx)
            </button>
          )}
          <button className="roster-primary" type="button" autoFocus onClick={onClose}>
            Đã lưu, đóng
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Ô chữ bên trái hàng nút: con số của bước, hay lời từ chối của BE thay chỗ nó.
 *
 * Lời từ chối là một phần tử **mới** mang `role="alert"`, không phải cùng một ô đổi vai: trình đọc
 * màn hình chỉ đọc chắc một vùng thông báo vừa xuất hiện (review pha 4).
 */
function Note({ refused, text }: { refused: string | null; text: string }) {
  return refused === null ? (
    <span className="note">{text}</span>
  ) : (
    <span className="note refused" role="alert">
      {refused}
    </span>
  );
}
