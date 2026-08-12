import { describe, expect, it } from "vitest";

import { chatReducer, EMPTY_CHAT, type ChatAction, type ChatState } from "@/hooks/use-chat";

const run = (state: ChatState, ...actions: ChatAction[]): ChatState =>
  actions.reduce(chatReducer, state);

const send = (message: string, turn: number): ChatAction => ({
  type: "send",
  message,
  modality: "text",
  turn,
});

const token = (text: string, turnId: string): ChatAction => ({
  type: "stream",
  turnId,
  event: { event: "token", text },
});

const done = (turnId: string, messageId: string): ChatAction => ({
  type: "stream",
  turnId,
  event: {
    event: "done",
    conversation_id: "c1",
    message_id: messageId,
    agent_name: "executive",
    speech_text: "spoken",
    duration_ms: 5,
  },
});

describe("chatReducer", () => {
  it("keeps every turn's id unique", () => {
    const state = run(
      EMPTY_CHAT,
      send("first", 1),
      done("assistant-1", "m1"),
      send("second", 2),
      done("assistant-2", "m2"),
    );

    const ids = state.messages.map((message) => message.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(state.messages).toHaveLength(4);
  });

  it("ignores events from a superseded turn", () => {
    // Without this, a slow first stream writes its tokens into the second answer.
    const state = run(
      EMPTY_CHAT,
      send("first", 1),
      send("second", 2),
      token("late", "assistant-1"),
      token("current", "assistant-2"),
    );

    expect(state.messages.at(-1)?.content).toBe("current");
    expect(state.messages.map((message) => message.content)).not.toContain("late");
  });

  it("stops the caret on an abandoned turn", () => {
    const state = run(EMPTY_CHAT, send("first", 1), send("second", 2));

    const abandoned = state.messages.filter((message) => message.streaming === true);
    expect(abandoned).toHaveLength(1);
    expect(abandoned[0].id).toBe("assistant-2");
  });

  it("replaces the failed pair on retry instead of duplicating it", () => {
    const failed = run(EMPTY_CHAT, send("hello", 1), {
      type: "failed",
      turnId: "assistant-1",
      message: "Ray could not be reached (HTTP 502).",
    });
    expect(failed.messages.at(-1)?.error).toBeDefined();

    const retried = run(failed, { type: "dropFailed" }, send("hello", 2), done("assistant-2", "m1"));

    expect(retried.messages).toHaveLength(2);
    expect(retried.messages.some((message) => message.error !== undefined)).toBe(false);
    expect(retried.messages[0].content).toBe("hello");
  });

  it("clears the in-flight turn when a stream errors, so a later event cannot revive it", () => {
    const state = run(
      EMPTY_CHAT,
      send("hello", 1),
      {
        type: "stream",
        turnId: "assistant-1",
        event: { event: "error", message: "gemini failed", retryable: true },
      },
      token("ignored", "assistant-1"),
    );

    expect(state.pendingId).toBeNull();
    expect(state.sending).toBe(false);
    expect(state.messages.at(-1)?.content).toBe("");
    expect(state.messages.at(-1)?.retryable).toBe(true);
  });

  it("records the finished turn once, for speech", () => {
    const state = run(EMPTY_CHAT, send("hello", 1), token("hi", "assistant-1"), done("assistant-1", "m1"));

    expect(state.lastCompleted?.id).toBe("m1");
    expect(state.lastCompleted?.speechText).toBe("spoken");
    expect(state.conversationId).toBe("c1");
    expect(state.sending).toBe(false);
  });

  it("forgets the conversation on reset, which is what makes + New new", () => {
    const state = run(
      EMPTY_CHAT,
      send("hello", 1),
      done("assistant-1", "m1"),
      { type: "reset" },
    );

    expect(state).toEqual(EMPTY_CHAT);
  });
});
