import type { Health } from "@/lib/api";

import { VoiceControl } from "@/components/voice-control";

/**
 * The conversation surface.
 *
 * Phase 2 replaces the placeholder body with the SSE-streamed message list; the
 * composer and voice control below it are already in their final positions, so
 * that change is additive.
 */
export function Conversation({ health, userName }: { health: Health | null; userName: string }) {
  return (
    <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-hud-border bg-hud-panel/60">
      <header className="flex items-center justify-between border-b border-hud-border px-5 py-3">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.18em] text-hud-muted">
          Conversation
        </h2>
        <VoiceControl capabilities={health?.voice ?? null} />
      </header>

      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-8 text-center">
        <p className="text-2xl font-light text-hud-text">Good to see you, {userName}.</p>
        <p className="max-w-md text-sm text-hud-muted">
          Conversation arrives in Phase 2, streamed over SSE with the agent trace shown as it
          happens. The foundation below is live: this dashboard is reading real data from the API.
        </p>
      </div>

      <div className="border-t border-hud-border p-4">
        <div className="flex items-center gap-3 rounded-md border border-hud-border bg-hud-bg/60 px-4 py-3">
          <input
            disabled
            placeholder="Ask Ray anything… (Phase 2)"
            aria-label="Message Ray"
            className="flex-1 bg-transparent text-sm text-hud-text outline-none placeholder:text-hud-muted disabled:cursor-not-allowed"
          />
          <span className="font-mono text-[10px] uppercase tracking-widest text-hud-muted">
            {health?.llm_provider ?? "offline"}
          </span>
        </div>
      </div>
    </section>
  );
}
