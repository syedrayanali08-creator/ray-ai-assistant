"use client";

import { useCallback, useReducer, useRef } from "react";

import {
  readEventStream,
  sendMessage,
  type Modality,
  type StreamEvent,
  type TraceStage,
} from "@/lib/chat";

export interface TraceEntry {
  stage: TraceStage;
  detail: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Present on assistant turns once `done` arrives; what TTS speaks (ADR-0009). */
  speechText?: string;
  agentName?: string;
  trace: TraceEntry[];
  /** True while tokens are still arriving, so the UI can show a caret. */
  streaming?: boolean;
  durationMs?: number;
  error?: string;
  retryable?: boolean;
}

interface State {
  conversationId: string | null;
  messages: ChatMessage[];
  sending: boolean;
  /** The turn that just finished, so voice output speaks each answer exactly once. */
  lastCompleted: ChatMessage | null;
}

type Action =
  | { type: "send"; message: string; modality: Modality }
  | { type: "stream"; event: StreamEvent }
  | { type: "failed"; message: string }
  | { type: "reset" };

const PENDING_ID = "pending";

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "send":
      return {
        ...state,
        sending: true,
        lastCompleted: null,
        messages: [
          ...state.messages,
          {
            id: `local-${state.messages.length}`,
            role: "user",
            content: action.message,
            trace: [],
          },
          { id: PENDING_ID, role: "assistant", content: "", trace: [], streaming: true },
        ],
      };

    case "stream":
      return applyEvent(state, action.event);

    case "failed":
      return {
        ...state,
        sending: false,
        messages: state.messages.map((message) =>
          message.id === PENDING_ID
            ? { ...message, streaming: false, error: action.message }
            : message,
        ),
      };

    case "reset":
      return { conversationId: null, messages: [], sending: false, lastCompleted: null };
  }
}

/** Update the in-flight assistant turn; every event except `done` narrows to this. */
function patchPending(state: State, patch: Partial<ChatMessage>): State {
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === PENDING_ID ? { ...message, ...patch } : message,
    ),
  };
}

function applyEvent(state: State, event: StreamEvent): State {
  const pending = state.messages.find((message) => message.id === PENDING_ID);
  if (pending === undefined) return state;

  switch (event.event) {
    case "token":
      return patchPending(state, { content: pending.content + event.text });

    case "trace":
      return patchPending(state, {
        trace: [...pending.trace, { stage: event.stage, detail: event.detail }],
      });

    case "tool":
      return patchPending(state, {
        trace: [...pending.trace, { stage: "tool", detail: { tool: event.tool } }],
      });

    case "approval":
      // Phase 5 renders an approval card; until then, record that it happened.
      return patchPending(state, {
        trace: [...pending.trace, { stage: "tool", detail: { tool: event.tool } }],
      });

    case "error":
      return {
        ...patchPending(state, {
          streaming: false,
          error: event.message,
          retryable: event.retryable,
        }),
        sending: false,
      };

    case "done": {
      const completed: ChatMessage = {
        ...pending,
        id: event.message_id,
        streaming: false,
        speechText: event.speech_text,
        agentName: event.agent_name,
        durationMs: event.duration_ms,
      };
      return {
        conversationId: event.conversation_id,
        sending: false,
        lastCompleted: completed,
        messages: state.messages.map((message) =>
          message.id === PENDING_ID ? completed : message,
        ),
      };
    }
  }
}

export function useChat(initial?: { conversationId: string | null; messages: ChatMessage[] }) {
  const [state, dispatch] = useReducer(reducer, {
    conversationId: initial?.conversationId ?? null,
    messages: initial?.messages ?? [],
    sending: false,
    lastCompleted: null,
  });

  const abortRef = useRef<AbortController | null>(null);
  // Read inside `send` so a stale closure cannot post to the wrong conversation.
  const conversationRef = useRef(state.conversationId);
  conversationRef.current = state.conversationId;

  const send = useCallback(async (message: string, modality: Modality = "text") => {
    const text = message.trim();
    if (text === "") return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: "send", message: text, modality });

    try {
      const body = await sendMessage({
        message: text,
        conversationId: conversationRef.current,
        inputModality: modality,
        // A voice question gets a spoken answer: the prompt differs, not just the
        // rendering (ADR-0009).
        outputModality: modality,
        signal: controller.signal,
      });
      for await (const event of readEventStream(body, controller.signal)) {
        dispatch({ type: "stream", event });
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      dispatch({
        type: "failed",
        message: error instanceof Error ? error.message : "Something went wrong.",
      });
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "reset" });
  }, []);

  return { ...state, send, reset };
}
