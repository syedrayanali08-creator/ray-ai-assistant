"use client";

import { useState } from "react";

import type { VoiceCapabilities } from "@/lib/api";

type VoiceState = "idle" | "armed" | "listening" | "processing" | "speaking";

const LABEL: Record<VoiceState, string> = {
  idle: "Voice off",
  armed: "Say \u201cRay\u201d",
  listening: "Listening\u2026",
  processing: "Thinking\u2026",
  speaking: "Responding\u2026",
};

/**
 * Voice affordance and state machine.
 *
 * The states are the real ones from the pipeline in ADR-0009, wired to the
 * capabilities the backend reports rather than to a hardcoded phase. Phase 2
 * connects the browser speech backends behind exactly this component, so the
 * layout and the state names do not change when voice becomes real.
 */
export function VoiceControl({ capabilities }: { capabilities: VoiceCapabilities | null }) {
  const wakeWordReady = capabilities?.wake_word_enabled ?? false;
  const [state, setState] = useState<VoiceState>(wakeWordReady ? "armed" : "idle");

  const active = state !== "idle";
  const backend = capabilities ? `${capabilities.stt_backend} stt` : "unavailable";

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        // Disabled until Phase 2 wires the browser speech backends. Rendering it
        // now keeps the control in the layout it will ship in.
        disabled
        onClick={() => setState(active ? "idle" : "armed")}
        aria-label="Toggle voice input"
        title="Voice input arrives in Phase 2"
        className="flex items-center gap-2 rounded-full border border-hud-border px-4 py-1.5 text-xs text-hud-muted disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span
          className={`h-2 w-2 rounded-full ${active ? "bg-hud-accent hud-pulse" : "bg-hud-muted"}`}
        />
        {LABEL[state]}
      </button>
      <span className="font-mono text-[10px] uppercase tracking-widest text-hud-muted">
        {backend}
      </span>
    </div>
  );
}
