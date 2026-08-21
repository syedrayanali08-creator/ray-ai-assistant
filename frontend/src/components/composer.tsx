"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

export interface ComposerHandle {
  focus: () => void;
}

export const Composer = forwardRef<ComposerHandle, {
  onSend: (message: string) => void;
  disabled: boolean;
  /** Live speech, shown in place of what the user has typed. */
  transcript: string;
  providerLabel: string;
}>(function Composer({ onSend, disabled, transcript, providerLabel }, ref) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => inputRef.current?.focus(),
  }));

  // Grow to fit a pasted paragraph instead of scrolling a one-line box.
  useEffect(() => {
    const input = inputRef.current;
    if (input === null) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  }, [value]);

  const submit = () => {
    if (value.trim() === "" || disabled) return;
    onSend(value);
    setValue("");
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="border-t border-hud-border p-4"
    >
      <div className="flex items-end gap-3 rounded-md border border-hud-border bg-hud-bg/60 px-4 py-3 focus-within:border-hud-accent/60">
        <textarea
          ref={inputRef}
          rows={1}
          value={transcript !== "" ? transcript : value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends; Shift+Enter is a newline, as in every chat client.
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={transcript !== "" ? "" : "Ask Ray anything… (/)"}
          aria-label="Message Ray"
          readOnly={transcript !== ""}
          className="flex-1 resize-none bg-transparent text-sm text-hud-text outline-none placeholder:text-hud-muted"
        />
        <button
          type="submit"
          disabled={disabled || value.trim() === ""}
          className="rounded border border-hud-accent/40 px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-hud-accent transition-colors hover:bg-hud-accent/10 disabled:cursor-not-allowed disabled:border-hud-border disabled:text-hud-muted"
        >
          {disabled ? "…" : "Send"}
        </button>
      </div>
      <p className="mt-2 text-right font-mono text-[10px] uppercase tracking-widest text-hud-muted">
        {providerLabel}
      </p>
    </form>
  );
});
