"use client";

import { useEffect, useRef } from "react";

import { AgentTrace } from "@/components/agent-trace";
import { Markdown } from "@/components/markdown";
import type { ChatMessage } from "@/hooks/use-chat";

export function MessageList({
  messages,
  userName,
  onRetry,
}: {
  messages: ChatMessage[];
  userName: string;
  onRetry: () => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const lastContent = messages[messages.length - 1]?.content;

  // Follow the stream, but only while the user is already at the bottom, so
  // scrolling up to read is not fought by every token.
  useEffect(() => {
    const container = endRef.current?.parentElement;
    if (!container) return;
    const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distance < 120) endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, lastContent]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-8 text-center">
        <p className="text-2xl font-light text-hud-text">Good to see you, {userName}.</p>
        <p className="max-w-md text-sm text-hud-muted">
          Ask me anything, or say &ldquo;Ray&rdquo; once voice is armed. I&apos;ll show you which
          agent answered and what it used.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
      {messages.map((message) => (
        <article
          key={message.id}
          data-role={message.role}
          className={message.role === "user" ? "flex justify-end" : ""}
        >
          {message.role === "user" ? (
            <p className="max-w-[80%] rounded-lg rounded-br-sm border border-hud-border bg-hud-panel px-4 py-2 text-sm text-hud-text">
              {message.content}
            </p>
          ) : (
            <div className="max-w-[90%]">
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-hud-accent">
                {message.agentName ?? "Ray"}
              </span>
              <div className="mt-1 text-hud-text">
                {message.content !== "" && <Markdown content={message.content} />}
                {message.streaming && (
                  <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 bg-hud-accent hud-pulse" />
                )}
                {message.content === "" && message.streaming && (
                  <span className="text-sm text-hud-muted">Thinking…</span>
                )}
              </div>

              {message.error !== undefined && (
                <p
                  role="alert"
                  className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-hud-danger/40 bg-hud-danger/10 px-3 py-2 text-xs text-hud-danger"
                >
                  {message.error}
                  {message.retryable !== false && (
                    <button
                      type="button"
                      onClick={onRetry}
                      className="rounded border border-hud-danger/40 px-2 py-0.5 font-mono uppercase tracking-widest hover:bg-hud-danger/20"
                    >
                      Retry
                    </button>
                  )}
                </p>
              )}

              <AgentTrace
                trace={message.trace}
                agentName={message.agentName}
                durationMs={message.durationMs}
              />
            </div>
          )}
        </article>
      ))}
      <div ref={endRef} />
    </div>
  );
}
