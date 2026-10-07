import katex from "katex";
import "katex/dist/katex.min.css";
import { Fragment } from "react";

/**
 * Một chuỗi của đề bài, dựng hình phần toán và in nguyên phần chữ.
 *
 * Trước component này, **không một chỗ nào** trong app dựng hình toán: 21 vị trí in chữ
 * câu hỏi đều là `{text}` thuần, và React escape mọi thứ — nên giáo viên và học sinh nhìn
 * thấy đúng từng byte model gõ ra. Đo được trên panel thật:
 * `Tính tích phân xác định \int_{0}^{1}(3x^2 - 2x + 1)\, dx.` hiện nguyên văn.
 *
 * Bốn prompt từng **cấm** LaTeX và bắt Unicode, không dòng code nào thi hành, và model cứ
 * viết. Hướng nay ngược lại: toán **được** viết bằng LaTeX và chỗ này dựng hình nó.
 *
 * **Nhận bốn kiểu dấu, không một.** Hợp đồng mới là `$...$`, nhưng dữ liệu đã có trong
 * database thì mang `\(...\)` và `\[...\]` — model viết thế suốt thời gian lệnh cấm không
 * có nơi thi hành. Nhận cả bốn nghĩa là corpus cũ đọc được ngay, không cần một lần chuyển
 * đổi nào; và chuỗi Unicode thuần không có dấu nào thì đi qua nguyên vẹn.
 *
 * **Một công thức hỏng không được làm trắng màn hình.** `throwOnError: false` để KaTeX in
 * chính chuỗi gốc bằng màu lỗi thay vì ném — một câu hỏi xấu vẫn phải đọc được, và một
 * exception ở đây sẽ giết cả panel vì một dấu ngoặc thiếu.
 */

/**
 * Bốn kiểu dấu: `$$…$$`, `$…$`, `\[…\]`, `\(…\)`. Cụm chặn đặt trước cụm thường.
 *
 * **Khuôn này nay chỉ có một bản, và nó ở đây.** `agent_gateway._MATH` ở BE từng là bản
 * thứ hai, và dòng này từng hứa hai bản khớp nhau — nhưng bản ấy đã bị xoá cùng với lưới
 * kiểm cú pháp toán ở BE, nên lời hứa trỏ vào một symbol không còn tồn tại. Một tài liệu
 * trỏ vào hư không còn tệ hơn không có tài liệu: nó mời người đọc đi tìm.
 *
 * Hệ quả của việc chỉ còn một bản: BE **không** phán xét chuỗi toán nữa, nên thứ quyết
 * định một công thức có được dựng hình hay không là đúng cái regex dưới đây.
 *
 * Ba điều kiện quanh dấu `$`, mỗi cái mua bằng một ca hỏng:
 *
 * - **Dấu mở không dính chữ số.** `Một quyển 20$, hai quyển 40$` có hai dấu `$`, số chẵn;
 *   không có luật này thì cả đoạn `, hai quyển 40` bị dựng thành công thức. Đề toán về giá
 *   tiền là ca thường gặp, không phải ca bịa.
 * - **Phần đệm trong cặp dấu được tha.** Luật của pandoc cấm khoảng trắng ngay sau dấu mở
 *   và ngay trước dấu đóng; chỗ này nới đúng một bậc — `$ (1, 8) $` là toán. Lý do là dữ
 *   liệu: ngày 06/10/2026, cả bốn phương án của một câu được model viết là `"$ (1, 8) $"`
 *   trong khi đề bài của **chính câu ấy** viết `$y = -2x^2 + 4x + 6$` không đệm. Luật
 *   nghiêm hơn cho ra 8 dấu đô la in nguyên văn trên màn hình giáo viên, đếm được trong
 *   `.panel-questions`. Sửa prompt thì không có nơi thi hành — bốn prompt từng cấm LaTeX
 *   và model vẫn viết; chỗ thi hành duy nhất là cái regex này.
 *
 *   **Giá phải trả, nói thẳng:** `Giá là 5 $ , còn lại 7 $` từ nay dựng phần giữa thành
 *   công thức. Đệm chỉ nhận **dấu cách và tab**, không nhận xuống dòng, nên thiệt hại
 *   dừng trong một dòng. Ca tiền tệ thường gặp — `Một quyển 20$, hai quyển 40$` — vẫn an
 *   toàn nhờ luật chữ số ngay trên, và đây là app đề toán chứ không phải app hoá đơn.
 * - **Vẫn không nhận cặp dấu rỗng**: sau phần đệm phải có một ký tự thật, nếu không
 *   `$  $` sẽ thành một công thức trống.
 * - **Cho phép xuống dòng bên trong.** Bản đầu dùng `[^$\n]`, nên một công thức model ngắt
 *   dòng ở giữa hiện ra nguyên văn — đúng cái kết cục việc này đi sửa.
 */
const MATH =
  /(?<![0-9A-Za-z])\$\$[ \t]*(?![\s$])([\s\S]+?)(?<![\s$])[ \t]*\$\$(?![0-9])|(?<![0-9A-Za-z$])\$[ \t]*(?![\s$])([^$]+?)(?<![\s$])[ \t]*\$(?![0-9])|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)/g;

/**
 * Dựng một cụm toán thành HTML.
 *
 * @param source - Phần nằm giữa hai dấu, không gồm dấu.
 * @param display - Công thức đứng riêng một dòng hay nằm trong dòng chữ.
 * @returns HTML của KaTeX, hoặc chính chuỗi gốc khi nó không dựng được.
 */
function drawn(source: string, display: boolean): string {
  return katex.renderToString(source, {
    displayMode: display,
    throwOnError: false,
    strict: false,
  });
}

/**
 * In một chuỗi có thể chứa toán.
 *
 * @param children - Chuỗi cần in. Chỗ gọi truyền thẳng giá trị từ API, không dọn trước.
 */
export default function MathText({ children }: { children: string }) {
  const pieces: { kind: "text" | "math"; body: string; display: boolean }[] =
    [];
  let at = 0;
  for (const found of children.matchAll(MATH)) {
    const start = found.index ?? 0;
    if (start > at) {
      pieces.push({
        kind: "text",
        body: children.slice(at, start),
        display: false,
      });
    }
    const block = found[1] ?? found[3];
    const inline = found[2] ?? found[4];
    pieces.push({
      kind: "math",
      body: block ?? inline ?? "",
      display: block !== undefined,
    });
    at = start + found[0].length;
  }
  if (at < children.length) {
    pieces.push({ kind: "text", body: children.slice(at), display: false });
  }

  return (
    <>
      {pieces.map((one, index) =>
        one.kind === "text" ? (
          <Fragment key={index}>{one.body}</Fragment>
        ) : (
          // `dangerouslySetInnerHTML` là đường **duy nhất** đưa output của KaTeX ra màn
          // hình, và nó an toàn ở đây vì chuỗi đi vào là output của KaTeX chứ không phải
          // chuỗi của model: KaTeX escape mọi thứ nó không hiểu. Chuỗi gốc không bao giờ
          // đi thẳng vào đây.
          <span
            key={index}
            className={one.display ? "math display" : "math"}
            dangerouslySetInnerHTML={{ __html: drawn(one.body, one.display) }}
          />
        ),
      )}
    </>
  );
}
