import { useState } from "react";

import { OPENERS } from "./invented-not-from-be";
import Rail from "./Rail";

/**
 * Artboard `1 · Bắt đầu — đoạn chat mới`: màn hình mở ra khi chưa nói gì.
 *
 * Không có lịch sử nào để vẽ, nên chỗ của cuộc trò chuyện là linh vật và một
 * câu hỏi. Ba gợi ý **điền sẵn vào ô nhập** chứ không gửi đi, đúng như câu ngay
 * trên chúng hứa — một cú bấm gửi thẳng sẽ biến một gợi ý thành một hành động,
 * và hành động của giáo viên là thứ ADR-05 dành ba cổng để bảo vệ.
 *
 * Gửi đi thì chưa làm gì ở bước này: vòng lặp lượt nói là bước sau của plan.
 * Nên nút gửi tắt khi ô nhập rỗng, và `onSend` còn để trống chứ không giả vờ.
 */
export default function Start() {
  const [text, setText] = useState("");

  return (
    <div className="teacher">
      <Rail />
      <main className="center">
        <img className="hero" src="/kriky-hero.png" alt="" width={143} height={240} />

        <div className="intro">
          <h1>Hôm nay bạn muốn làm gì?</h1>
          <p>
            Nói bằng câu bình thường. Kriky sẽ tạo lớp, soạn đề, thêm câu hỏi — nhưng chỉ bạn mới
            phát hành được đề cho học sinh.
          </p>
        </div>

        <div className="hint">Bấm một gợi ý để điền sẵn vào ô nhập, bạn sửa lại trước khi gửi.</div>

        <div className="suggestions">
          {OPENERS.map((one) => (
            <button className="suggestion" key={one} type="button" onClick={() => setText(one)}>
              {one}
            </button>
          ))}
        </div>

        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
          }}
        >
          <button className="attach" type="button">
            ＋ Tài liệu
          </button>
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Nhắn cho Kriky…"
            aria-label="Nhắn cho Kriky"
          />
          <button className="send" type="submit" disabled={text.trim() === ""}>
            Gửi
          </button>
        </form>
      </main>
    </div>
  );
}
