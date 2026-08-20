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
  /**
   * The assistant turn currently receiving events, or null.
   *
   * Every turn gets a unique id: a shared "pending" id makes a retry or a second
   * send collide with the turn before it, which renders as duplicated answers and
   * duplicate React keys.
   */
  pendingId: string | null;
  /** The turn that just finished, so voice output speaks each answer exactly once. */
  lastCompleted: ChatMessage | null;
}

export type ChatAction = Action;

type Action =
  | { type: "send"; message: string; modality: Modality; turn: number }
  | { type: "stream"; event: StreamEvent; turnId: string }
  | { type: "failed"; message: string; turnId: string }
  | { type: "dropFailed" }
  | { type: "voiceTurn"; message: string; response: { content: string; speechText?: string } }
  | { type: "reset" };

export const EMPTY_CHAT: ChatState = {
  conversationId: null,
  messages: [],
  sending: false,
  pendingId: null,
  lastCompleted: null,
};

export type ChatState = State;

/** Exported for tests: turn bookkeeping is where duplicated answers come from. */
export function chatReducer(state: State, action: Action): State {
  switch (action.type) {
    case "send": {
      const pendingId = `assistant-${action.turn}`;
      return {
        ...state,
        sending: true,
        pendingId,
        lastCompleted: null,
        messages: [
          // An abandoned turn stops streaming; its caret would otherwise blink forever.
          ...state.messages.map((message) =>
            message.streaming === true ? { ...message, streaming: false } : message,
          ),
          {
            id: `user-${action.turn}`,
            role: "user",
            content: action.message,
            trace: [],
          },
          { id: pendingId, role: "assistant", content: "", trace: [], streaming: true },
        ],
      };
    }

    case "stream":
      // A superseded stream must not write into the current turn.
      if (action.turnId !== state.pendingId) return state;
      return applyEvent(state, action.event);

    case "failed":
      if (action.turnId !== state.pendingId) return state;
      return {
        ...patchPending(state, { streaming: false, error: action.message }),
        sending: false,
        pendingId: null,
      };

    case "dropFailed": {
      // Retrying resends the question, so the failed pair is removed rather than
      // left above an identical one.
      const failedAt = state.messages.findIndex((message) => message.error !== undefined);
      if (failedAt === -1) return state;
      const from = state.messages[failedAt - 1]?.role === "user" ? failedAt - 1 : failedAt;
      return { ...state, messages: state.messages.slice(0, from), pendingId: null };
    }

    case "voiceTurn": {
      const userId = `user-voice-${Date.now()}`;
      const assistantId = `assistant-voice-${Date.now()}`;
      const completed: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: action.response.content,
        speechText: action.response.speechText ?? action.response.content,
        agentName: "executive",
        trace: [],
      };
      return {
        ...state,
        sending: false,
        pendingId: null,
        lastCompleted: completed,
        messages: [
          ...state.messages,
          { id: userId, role: "user", content: action.message, trace: [] },
          completed,
        ],
      };
    }

    case "reset":
      return {
        conversationId: null,
        messages: [],
        sending: false,
        pendingId: null,
        lastCompleted: null,
      };
  }
}

/** Update the in-flight assistant turn; every event except `done` narrows to this. */
function patchPending(state: State, patch: Partial<ChatMessage>): State {
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === state.pendingId ? { ...message, ...patch } : message,
    ),
  };
}

function applyEvent(state: State, event: StreamEvent): State {
  const pending = state.messages.find((message) => message.id === state.pendingId);
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
        pendingId: null,
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
        pendingId: null,
        lastCompleted: completed,
        messages: state.messages.map((message) =>
          message.id === state.pendingId ? completed : message,
        ),
      };
    }
  }
}

export function useChat(initial?: { conversationId: string | null; messages: ChatMessage[] }) {
  const [state, dispatch] = useReducer(chatReducer, {
    conversationId: initial?.conversationId ?? null,
    messages: initial?.messages ?? [],
    sending: false,
    pendingId: null,
    lastCompleted: null,
  });

  const abortRef = useRef<AbortController | null>(null);
  const turnRef = useRef(0);
  const lastSentRef = useRef<{ message: string; modality: Modality } | null>(null);
  // Read inside `send` so a stale closure cannot post to the wrong conversation.
  const conversationRef = useRef(state.conversationId);
  conversationRef.current = state.conversationId;

  const send = useCallback(async (message: string, modality: Modality = "text") => {
    const text = message.trim();
    if (text === "") return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    turnRef.current += 1;
    const turn = turnRef.current;
    const turnId = `assistant-${turn}`;
    lastSentRef.current = { message: text, modality };

    dispatch({ type: "send", message: text, modality, turn });

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
        dispatch({ type: "stream", event, turnId });
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      dispatch({
        type: "failed",
        turnId,
        message: error instanceof Error ? error.message : "Something went wrong.",
      });
    }
  }, []);

  const retry = useCallback(() => {
    const last = lastSentRef.current;
    if (last === null) return;
    dispatch({ type: "dropFailed" });
    void send(last.message, last.modality);
  }, [send]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "reset" });
  }, []);

  const appendVoiceResponse = useCallback(
    (message: string, content: string, speechText?: string) => {
      dispatch({ type: "voiceTurn", message, response: { content, speechText } });
    },
    [],
  );

  return { ...state, send, retry, reset, appendVoiceResponse };
}
