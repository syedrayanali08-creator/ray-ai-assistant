import { describe, expect, it } from "vitest";

import { describeStage, readEventStream, type StreamEvent } from "@/lib/chat";

/** Emit the given byte strings as one stream, one chunk at a time. */
function stream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(chunks: string[]): Promise<StreamEvent[]> {
  const events: StreamEvent[] = [];
  for await (const event of readEventStream(stream(chunks))) events.push(event);
  return events;
}

const TURN = [
  'event: trace\ndata: {"event":"trace","stage":"memory","detail":{"count":0}}\n\n',
  'event: token\ndata: {"event":"token","text":"Hello"}\n\n',
  'event: token\ndata: {"event":"token","text":" there"}\n\n',
  'event: done\ndata: {"event":"done","conversation_id":"c1","message_id":"m1",' +
    '"agent_name":"executive","speech_text":"Hello there","duration_ms":12}\n\n',
];

describe("readEventStream", () => {
  it("yields each event in order", async () => {
    const events = await collect(TURN);

    expect(events.map((event) => event.event)).toEqual(["trace", "token", "token", "done"]);
  });

  it("reassembles frames split mid-payload across chunks", async () => {
    // The failure mode this guards is silent: a frame torn at an arbitrary byte
    // shows up as an occasional dropped token, not as an error.
    const whole = TURN.join("");
    const torn = [whole.slice(0, 31), whole.slice(31, 96), whole.slice(96)];

    const events = await collect(torn);

    expect(events.map((event) => event.event)).toEqual(["trace", "token", "token", "done"]);
    const text = events
      .filter((event): event is Extract<StreamEvent, { event: "token" }> => event.event === "token")
      .map((event) => event.text)
      .join("");
    expect(text).toBe("Hello there");
  });

  it("ignores keep-alive comments and unparsable frames", async () => {
    const events = await collect([": keep-alive\n\n", "event: token\ndata: not json\n\n", ...TURN]);

    expect(events).toHaveLength(4);
  });

  it("stops when the caller aborts", async () => {
    const controller = new AbortController();
    controller.abort();

    const events: StreamEvent[] = [];
    for await (const event of readEventStream(stream(TURN), controller.signal)) {
      events.push(event);
    }

    expect(events).toEqual([]);
  });
});

describe("describeStage", () => {
  it("says when nothing was retrieved rather than staying silent", () => {
    expect(describeStage("memory", { count: 0 })).toBe("No memories retrieved");
    expect(describeStage("memory", { count: 3 })).toBe("Retrieved 3 memories");
  });

  it("surfaces a provider fallback in the compose step", () => {
    expect(describeStage("compose", { degraded_from: "gemini", duration_ms: 5 })).toContain(
      "gemini unavailable",
    );
  });
});
