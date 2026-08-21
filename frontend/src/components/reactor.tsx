"use client";

import type { VoiceState } from "@/hooks/use-voice";

export type ReactorState = VoiceState | "approval";

interface ReactorProps {
  state: ReactorState;
  className?: string;
}

const LABEL: Record<ReactorState, string> = {
  idle: "Idle",
  armed: "Armed",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  approval: "Approval needed",
};

/**
 * The ambient HUD reactor. It shows Ray's current pipeline state at a glance using
 * motion and colour, while remaining behind the conversation so it never blocks
 * interaction. Animation respects `prefers-reduced-motion`.
 */
export function Reactor({ state, className = "" }: ReactorProps) {
  return (
    <div
      className={`pointer-events-none flex flex-col items-center justify-center ${className}`}
      aria-hidden="true"
      role="img"
      aria-label={`Ray is ${LABEL[state]}`}
    >
      <div className={`reactor reactor-${state}`}>
        <div className="reactor-core" />
        <div className="reactor-ring" />
        <div className="reactor-ripple" />
      </div>
      <span className="reactor-label font-mono text-[10px] uppercase tracking-[0.2em]">
        {LABEL[state]}
      </span>
    </div>
  );
}
