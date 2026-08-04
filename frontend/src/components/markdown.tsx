/**
 * A deliberately small markdown renderer.
 *
 * Ray's answers use a narrow slice of markdown: fenced code, inline code, bold,
 * headings, and lists. That is ~80 lines here versus a parser plus a sanitiser
 * plus a highlighter as dependencies, and it never renders raw HTML, so there is
 * no injection surface to sanitise in the first place. Swap in `react-markdown`
 * if Ray starts emitting tables or footnotes.
 */

type Block =
  | { kind: "code"; language: string; code: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string };

const FENCE = /^```(\w*)\s*$/;
const BULLET = /^\s*[-*]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^#{1,6}\s+(.*)$/;

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  const lines = source.split("\n");
  let paragraph: string[] = [];

  const flush = () => {
    if (paragraph.length > 0) {
      blocks.push({ kind: "paragraph", text: paragraph.join("\n") });
      paragraph = [];
    }
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const fence = FENCE.exec(line);

    if (fence) {
      flush();
      const code: string[] = [];
      index += 1;
      // An unterminated fence is normal mid-stream: render what has arrived.
      while (index < lines.length && !FENCE.test(lines[index])) {
        code.push(lines[index]);
        index += 1;
      }
      blocks.push({ kind: "code", language: fence[1], code: code.join("\n") });
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      flush();
      blocks.push({ kind: "heading", text: heading[1] });
      continue;
    }

    const item = BULLET.exec(line) ?? NUMBERED.exec(line);
    if (item) {
      flush();
      const ordered = BULLET.exec(line) === null;
      const previous = blocks[blocks.length - 1];
      if (previous?.kind === "list" && previous.ordered === ordered) {
        previous.items.push(item[1]);
      } else {
        blocks.push({ kind: "list", ordered, items: [item[1]] });
      }
      continue;
    }

    if (line.trim() === "") flush();
    else paragraph.push(line);
  }

  flush();
  return blocks;
}

/** Bold and inline code, applied to text that is already escaped by React. */
function inline(text: string, keyPrefix: string) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={key} className="font-semibold text-hud-text">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={key} className="rounded bg-hud-bg px-1 py-0.5 font-mono text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={key}>{part}</span>;
  });
}

export function Markdown({ content }: { content: string }) {
  return (
    <div className="space-y-3 text-sm leading-relaxed">
      {parseMarkdown(content).map((block, index) => {
        const key = `${block.kind}-${index}`;
        switch (block.kind) {
          case "code":
            return (
              <pre
                key={key}
                className="overflow-x-auto rounded-md border border-hud-border bg-hud-bg px-4 py-3"
              >
                {block.language !== "" && (
                  <span className="mb-2 block font-mono text-[10px] uppercase tracking-widest text-hud-muted">
                    {block.language}
                  </span>
                )}
                <code className="font-mono text-xs text-hud-text">{block.code}</code>
              </pre>
            );

          case "list": {
            const Tag = block.ordered ? "ol" : "ul";
            return (
              <Tag
                key={key}
                className={`ml-5 space-y-1 ${block.ordered ? "list-decimal" : "list-disc"}`}
              >
                {block.items.map((item, itemIndex) => (
                  <li key={`${key}-${itemIndex}`}>{inline(item, `${key}-${itemIndex}`)}</li>
                ))}
              </Tag>
            );
          }

          case "heading":
            return (
              <h3 key={key} className="text-sm font-semibold text-hud-text">
                {inline(block.text, key)}
              </h3>
            );

          case "paragraph":
            return (
              <p key={key} className="whitespace-pre-wrap">
                {inline(block.text, key)}
              </p>
            );
        }
      })}
    </div>
  );
}
