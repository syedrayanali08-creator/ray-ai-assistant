import { describe, expect, it } from "vitest";

import { parseMarkdown } from "@/components/markdown";

describe("parseMarkdown", () => {
  it("separates fenced code from prose and keeps the language", () => {
    const blocks = parseMarkdown("Try this:\n\n```python\nprint(1)\nprint(2)\n```\n\nDone.");

    expect(blocks).toEqual([
      { kind: "paragraph", text: "Try this:" },
      { kind: "code", language: "python", code: "print(1)\nprint(2)" },
      { kind: "paragraph", text: "Done." },
    ]);
  });

  it("renders an unterminated fence, because that is every stream mid-token", () => {
    const blocks = parseMarkdown("```ts\nconst x = 1;");

    expect(blocks).toEqual([{ kind: "code", language: "ts", code: "const x = 1;" }]);
  });

  it("groups consecutive list items and splits ordered from unordered", () => {
    const blocks = parseMarkdown("- one\n- two\n\n1. first\n2. second");

    expect(blocks).toEqual([
      { kind: "list", ordered: false, items: ["one", "two"] },
      { kind: "list", ordered: true, items: ["first", "second"] },
    ]);
  });

  it("does not treat markdown inside a code fence as markdown", () => {
    const blocks = parseMarkdown("```\n# not a heading\n- not a list\n```");

    expect(blocks).toEqual([{ kind: "code", language: "", code: "# not a heading\n- not a list" }]);
  });

  it("keeps headings out of paragraphs", () => {
    expect(parseMarkdown("## Plan\ndo the thing")).toEqual([
      { kind: "heading", text: "Plan" },
      { kind: "paragraph", text: "do the thing" },
    ]);
  });
});
