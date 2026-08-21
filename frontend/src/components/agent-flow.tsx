"use client";

import type { TraceEntry } from "@/hooks/use-chat";

const NODES = [
  { stage: "routing", label: "Route" },
  { stage: "memory", label: "Recall" },
  { stage: "agent", label: "Agent" },
  { stage: "tool", label: "Tools" },
  { stage: "compose", label: "Reply" },
] as const;

/**
 * A compact flow diagram of what the orchestrator actually did for one turn.
 *
 * Trace stages are rendered as nodes; active nodes are highlighted and connected
 * by a subtle line so the pipeline is readable even when collapsed.
 */
export function AgentFlow({ trace, durationMs }: { trace: TraceEntry[]; durationMs?: number }) {
  const hit = (stage: string) => trace.find((entry) => entry.stage === stage);
  const toolCount = trace.filter((entry) => entry.stage === "tool").length;

  return (
    <div className="mt-3 rounded border border-hud-border/60 bg-hud-bg/40 p-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-hud-muted">
          Pipeline
        </span>
        {durationMs !== undefined && (
          <span className="font-mono text-[10px] text-hud-muted">{durationMs}ms</span>
        )}
      </div>
      <ol className="mt-2 flex items-center gap-1">
        {NODES.map((node, index) => {
          const active = hit(node.stage);
          const isTool = node.stage === "tool";
          const count = isTool && toolCount > 0 ? toolCount : undefined;
          const degraded =
            node.stage === "compose" && trace.some((entry) => entry.detail.degraded_from);

          return (
            <li key={node.stage} className="flex flex-1 items-center">
              <div
                className={`flex flex-1 flex-col items-center gap-1.5 rounded border py-2 transition-colors ${
                  active
                    ? "border-hud-accent/60 bg-hud-accent/10 text-hud-accent"
                    : "border-hud-border/40 bg-hud-panel/40 text-hud-muted"
                }`}
              >
                <span className="font-mono text-[10px] uppercase tracking-widest">
                  {node.label}
                </span>
                {count !== undefined && (
                  <span className="font-mono text-[10px] text-hud-accent">{count}</span>
                )}
                {node.stage === "compose" && degraded && (
                  <span className="font-mono text-[9px] text-hud-warn">fallback</span>
                )}
              </div>
              {index < NODES.length - 1 && (
                <span
                  className={`mx-1 h-px w-3 ${active ? "bg-hud-accent/40" : "bg-hud-border/40"}`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
