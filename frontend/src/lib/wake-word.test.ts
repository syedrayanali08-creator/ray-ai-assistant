import { describe, expect, it } from "vitest";

import { TranscriptWakeWordDetector, stripWakeWord } from "@/lib/wake-word";

describe("TranscriptWakeWordDetector", () => {
  it("fires once for a growing interim transcript", () => {
    const detector = new TranscriptWakeWordDetector(["ray"]);

    expect(detector.feed("hey")).toBeNull();
    expect(detector.feed("hey ray")?.keyword).toBe("ray");
    // Interim results keep arriving; re-firing would restart the turn mid-sentence.
    expect(detector.feed("hey ray what's")).toBeNull();

    detector.reset();
    expect(detector.feed("ray again")?.keyword).toBe("ray");
  });

  it("requires a word boundary", () => {
    const detector = new TranscriptWakeWordDetector(["ray"]);

    expect(detector.feed("array of numbers")).toBeNull();
    expect(detector.feed("betrayed")).toBeNull();
    expect(detector.feed("Ray!")).not.toBeNull();
  });

  it("reports which of several keywords fired", () => {
    // Ray is planned to answer to "Jarvis" too, so the event must name the phrase.
    const detector = new TranscriptWakeWordDetector(["ray", "jarvis"]);

    expect(detector.feed("jarvis, status")?.keyword).toBe("jarvis");
  });
});

describe("stripWakeWord", () => {
  it("removes only a leading wake word", () => {
    expect(stripWakeWord("Ray, what's on my calendar", ["ray"])).toBe("what's on my calendar");
    expect(stripWakeWord("hey Ray add a task", ["ray"])).toBe("add a task");
    expect(stripWakeWord("Jarvis: run the tests", ["ray", "jarvis"])).toBe("run the tests");
  });

  it("leaves the wake word alone mid-sentence", () => {
    expect(stripWakeWord("tell me about Ray", ["ray"])).toBe("tell me about Ray");
  });

  it("returns empty for the wake word on its own, which is an activation", () => {
    expect(stripWakeWord("Ray", ["ray"])).toBe("");
  });
});
