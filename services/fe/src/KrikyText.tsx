import type { ReactNode } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { drawn, pieces } from "./MathText";

/**
 * In một lời Kriky: Markdown, cùng toán trong `$…$` (ADR-30, `kriky-writes-every-word`).
 *
 * **Toán được tách ra trước khi Markdown đọc chuỗi.** Bộ đọc Markdown hiểu `_`, `*` và `\` của
 * LaTeX thành định dạng — `$a_1 + a_2$` thành chữ nghiêng, `\\` mất một nửa. Nên mỗi cụm toán, tìm
 * bằng đúng khuôn `MATH` của `MathText`, được thay bằng một **chỗ giữ chỗ** không phải cú pháp
 * Markdown (hai ký tự vùng dùng riêng của Unicode bao một con số), Markdown dựng phần còn lại, rồi
 * plugin `withMath` thay chỗ giữ chỗ bằng KaTeX. Nhờ dùng chung khuôn, chỗ nào `MathText` không coi
 * là toán (như giá tiền `20$`, `40$`) thì ở đây cũng không. Chỗ giữ chỗ nằm trong URL của một link
 * hay trong `` `mã` `` thì vẫn bị thay — hiếm, và vô hại.
 *
 * **Không HTML thô, không ảnh.** Không `rehype-raw`, nên một thẻ HTML model viết ra không bao giờ
 * thành phần tử của trang. Markdown vẫn tự sinh `a` và `img`: link mở tab mới và không đổi route
 * của trang; ảnh chỉ in chữ `alt` — một ảnh tự tải về từ một URL model viết là một đường rò dữ liệu
 * không cần ai bấm, khi sách tải lên có thể chèn lệnh vào model. KaTeX là đường duy nhất vào
 * `dangerouslySetInnerHTML`, như ở `MathText`.
 *
 * @param children - Lời Kriky, đúng như API trả.
 * @param inline - Lời nằm trong một phần tử dòng (tiêu đề thẻ hỏi lại): chỉ giữ định dạng trong
 *   dòng, vì một `<h3>` không được chứa đoạn văn, danh sách hay tiêu đề.
 */
export default function KrikyText({
  children,
  inline = false,
}: {
  children: string;
  inline?: boolean;
}) {
  const parts = pieces(children);
  const math = parts.filter((one) => one.kind === "math");
  let next = 0;
  const source = parts
    .map((one) =>
      // Lời đã chứa sẵn ký tự giữ chỗ thì chúng bị bỏ, nếu không chúng thành một công thức khác.
      one.kind === "math" ? `${OPEN}${next++}${CLOSE}` : one.body.replace(STRAY, ""),
    )
    .join("");

  const components: Components = {
    span({ node: _node, ...props }) {
      const at = (props as Record<string, unknown>)["data-math"];
      if (at === undefined) return <span {...props} />;
      const one = math[Number(at)];
      if (one === undefined) return null;
      return (
        <span
          className={one.display ? "math display" : "math"}
          dangerouslySetInnerHTML={{ __html: drawn(one.body, one.display) }}
        />
      );
    },
    img({ alt }) {
      return alt ? <span>{alt}</span> : null;
    },
    a({ href, children: inside }) {
      // Link trong trang (footnote của GFM, `#…`) đổi route hash của SPA: in như chữ.
      if (!href || href.startsWith("#")) return <span>{inside}</span>;
      return (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {inside}
        </a>
      );
    },
  };
  if (inline) components.p = ({ children: inside }) => <>{inside as ReactNode}</>;

  const Wrap = inline ? "span" : "div";
  return (
    <Wrap className="kriky-text">
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[withMath]}
        components={components}
        allowedElements={inline ? INLINE : undefined}
        unwrapDisallowed={inline}
      >
        {source}
      </Markdown>
    </Wrap>
  );
}

/** Hai ký tự vùng dùng riêng (U+E000, U+E001): không bộ đọc Markdown nào coi chúng là cú pháp. */
const OPEN = "\uE000";
const CLOSE = "\uE001";
const HOLE = /\uE000(\d+)\uE001/g;
const STRAY = /[\uE000\uE001]/g;

/** Phần tử giữ được khi lời nằm trong một dòng; mọi thứ khác bị gỡ, chữ bên trong ở lại. */
const INLINE = ["p", "strong", "em", "del", "code", "span", "a", "br"];

interface HastNode {
  type: string;
  value?: string;
  tagName?: string;
  properties?: Record<string, unknown>;
  children?: HastNode[];
}

/**
 * Plugin rehype: thay mỗi chỗ giữ chỗ trong chữ bằng một `span` mang `data-math`, để component
 * `span` ở trên dựng KaTeX vào đó. Cùng lượt, bỏ các node chữ **chỉ có khoảng trắng chứa xuống
 * dòng**: mdast→hast chèn chúng giữa các khối, kể cả trong một mục danh sách và ngay sau một `br`,
 * và `white-space: pre-line` của `.kriky-text li` sẽ in chúng thành dòng trống (review pha 3).
 * Xuống dòng **bên trong** một câu nằm trong node chữ có chữ, nên không bị đụng.
 */
function withMath() {
  return (tree: HastNode) => {
    fill(tree);
  };
}

function fill(node: HastNode): void {
  if (node.children === undefined) return;
  const out: HastNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && child.value !== undefined && /^\s*\n\s*$/.test(child.value)) {
      continue;
    }
    if (child.type !== "text" || child.value === undefined || !child.value.includes(OPEN)) {
      fill(child);
      out.push(child);
      continue;
    }
    let at = 0;
    for (const found of child.value.matchAll(HOLE)) {
      const start = found.index ?? 0;
      if (start > at) out.push({ type: "text", value: child.value.slice(at, start) });
      out.push({
        type: "element",
        tagName: "span",
        properties: { dataMath: found[1] },
        children: [],
      });
      at = start + found[0].length;
    }
    if (at < child.value.length) out.push({ type: "text", value: child.value.slice(at) });
  }
  node.children = out;
}
