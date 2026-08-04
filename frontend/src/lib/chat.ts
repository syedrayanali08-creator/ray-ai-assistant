import type { components } from "@/lib/api-types";

/**
 * The browser half of the chat protocol (ADR-0007).
 *
 * `EventSource` is not usable here: it cannot issue a POST and cannot attach a
 * bearer token, so the stream is read from `fetch` with a `ReadableStream` reader.
 */

type Schemas = components["schemas"];

export type Modality = Schemas["Modality"];

/** Mirrors `ray.core.events`. All six are handled, though Phase 2 emits four. */
export type StreamEvent =
  | { event: "trace"; stage: TraceStage; detail: Record<string, unknown> }
  | { event: "token"; text: string }
  | { event: "tool"; tool: string; status: "running" | "completed" | "failed" }
  | { event: "approval"; invocation_id: string; tool: string; payload: Record<string, unknown> }
  | { event: "error"; message: string; retryable: boolean }
  | {
      event: "done";
      conversation_id: string;
      message_id: string;
      agent_name: string;
      speech_text: string;
      duration_ms: number;
    };

export type TraceStage = "routing" | "memory" | "agent" | "tool" | "compose";

export interface SendOptions {
  message: string;
  conversationId: string | null;
  inputModality?: Modality;
  outputModality?: Modality;
  signal?: AbortSignal;
}

/**
 * Parse an SSE byte stream into events.
 *
 * A frame can be split across chunk boundaries at any byte, so the tail of each
 * chunk is buffered until its blank-line terminator arrives. Getting this wrong
 * looks like rare, unreproducible dropped tokens.
 */
export async function* readEventStream(
  body: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  try {
    while (!signal?.aborted) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += value;

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const parsed = parseFrame(frame);
        if (parsed) yield parsed;
        boundary = buffer.indexOf("\n\n");
      }
    }
  } finally {
    // Releasing the lock cancels the underlying request when the caller aborts.
    reader.releaseLock();
  }
}

function parseFrame(frame: string): StreamEvent | null {
  // The event name is also inside the JSON payload, so only `data:` is needed.
  const data = frame
    .split("\n")
    .find((line) => line.startsWith("data: "))
    ?.slice("data: ".length);
  if (!data) return null;
  try {
    return JSON.parse(data) as StreamEvent;
  } catch {
    return null;
  }
}

/**
 * Send a turn through the Next.js proxy.
 *
 * The proxy, not the browser, holds the API token (docs/12).
 */
export async function sendMessage(options: SendOptions): Promise<ReadableStream<Uint8Array>> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: options.message,
      conversation_id: options.conversationId,
      input_modality: options.inputModality ?? "text",
      output_modality: options.outputModality ?? "text",
    }),
    signal: options.signal,
  });

  if (!response.ok || response.body === null) {
    throw new Error(
      response.status === 401
        ? "Ray rejected the request: RAY_API_TOKEN does not match the backend."
        : `Ray could not be reached (HTTP ${response.status}).`,
    );
  }
  return response.body;
}

/** A short, human sentence for one recorded pipeline step. */
export function describeStage(stage: TraceStage, detail: Record<string, unknown>): string {
  switch (stage) {
    case "memory": {
      const count = Number(detail.count ?? 0);
      return count === 0 ? "No memories retrieved" : `Retrieved ${count} memories`;
    }
    case "routing":
      return `Routed to the ${String(detail.agent)} agent`;
    case "agent":
      return `Asking ${String(detail.provider)}`;
    case "tool":
      return `Used ${String(detail.tool)}`;
    case "compose":
      if (detail.degraded_from) {
        return `${String(detail.degraded_from)} unavailable — used the fallback`;
      }
      return `Composed in ${String(detail.duration_ms)}ms`;
  }
}
