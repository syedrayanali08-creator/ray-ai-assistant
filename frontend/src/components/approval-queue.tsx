"use client";

import { useCallback, useEffect, useState } from "react";

import type { components } from "@/lib/api-types";

type Invocation = components["schemas"]["ToolInvocationRead"];

export function ApprovalQueue() {
  const [items, setItems] = useState<Invocation[]>([]);
  const [acting, setActing] = useState<Set<string>>(new Set());

  const fetchPending = useCallback(async () => {
    try {
      const response = await fetch("/api/approvals", { cache: "no-store" });
      if (!response.ok) return;
      const data = (await response.json()) as Invocation[];
      setItems(data);
    } catch {
      // Backend may be starting; retry next interval.
    }
  }, []);

  useEffect(() => {
    fetchPending();
    const interval = setInterval(fetchPending, 3000);
    return () => clearInterval(interval);
  }, [fetchPending]);

  async function decide(id: string, action: "approve" | "reject", alwaysAllow = false) {
    setActing((prev) => new Set(prev).add(id));
    try {
      const response = await fetch(`/api/approvals/${id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ always_allow: alwaysAllow }),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed" }));
        alert(String(error.detail ?? "Failed"));
      }
      await fetchPending();
    } finally {
      setActing((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  if (items.length === 0) return null;

  return (
    <section className="rounded-lg border border-hud-warn/30 bg-hud-panel/60 p-4">
      <h3 className="mb-3 font-mono text-[11px] uppercase tracking-widest text-hud-warn">
        Pending approvals
      </h3>
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={String(item.id)} className="rounded border border-hud-border p-3">
            <p className="text-sm text-hud-text">
              <span className="font-medium">{item.tool_name}</span>
            </p>
            <pre className="mt-2 overflow-x-auto rounded bg-hud-bg p-2 font-mono text-[11px] text-hud-muted">
              {JSON.stringify(item.payload, null, 2)}
            </pre>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={acting.has(String(item.id))}
                onClick={() => void decide(String(item.id), "approve")}
                className="rounded bg-hud-accent px-3 py-1.5 text-xs font-medium text-hud-bg transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                Approve
              </button>
              <button
                type="button"
                disabled={acting.has(String(item.id))}
                onClick={() => void decide(String(item.id), "reject")}
                className="rounded border border-hud-border px-3 py-1.5 text-xs font-medium text-hud-muted transition-colors hover:text-hud-text disabled:opacity-50"
              >
                Reject
              </button>
              {item.side_effect && (
                <button
                  type="button"
                  disabled={acting.has(String(item.id))}
                  onClick={() => void decide(String(item.id), "approve", true)}
                  className="rounded border border-hud-border px-3 py-1.5 text-xs font-medium text-hud-muted transition-colors hover:text-hud-text disabled:opacity-50"
                >
                  Always allow
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
