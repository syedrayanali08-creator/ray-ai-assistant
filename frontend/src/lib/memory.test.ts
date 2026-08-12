import { describe, expect, it } from "vitest";

import { listQuery, looksSemantic, relativeDate, toggleCategory } from "@/lib/memory";

describe("listQuery", () => {
  it("omits empty filters rather than sending blanks", () => {
    expect(listQuery({})).toBe("");
    expect(listQuery({ q: "   ", category: "all" })).toBe("");
  });

  it("trims and encodes what it does send", () => {
    expect(listQuery({ q: " starfall sprint ", category: "project" })).toBe(
      "q=starfall+sprint&category=project",
    );
  });
});

describe("looksSemantic", () => {
  it("treats a keyword hunt as a substring search", () => {
    expect(looksSemantic("starfall")).toBe(false);
    expect(looksSemantic("processing game")).toBe(false);
  });

  it("treats a question as a semantic search", () => {
    expect(looksSemantic("what am I working on right now")).toBe(true);
  });
});

describe("toggleCategory", () => {
  it("switches a category off and back on", () => {
    expect(toggleCategory([], "project")).toEqual(["project"]);
    expect(toggleCategory(["project", "goal"], "project")).toEqual(["goal"]);
  });
});

describe("relativeDate", () => {
  it("describes age in the coarsest useful unit", () => {
    const day = 86_400_000;
    expect(relativeDate(new Date().toISOString())).toBe("today");
    expect(relativeDate(new Date(Date.now() - day).toISOString())).toBe("yesterday");
    expect(relativeDate(new Date(Date.now() - 5 * day).toISOString())).toBe("5d ago");
    expect(relativeDate(new Date(Date.now() - 70 * day).toISOString())).toBe("2mo ago");
  });
});
