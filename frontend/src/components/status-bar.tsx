import Link from "next/link";
import type { ReactNode } from "react";

import type { Health, User } from "@/lib/api";

/**
 * Top bar: who Ray is talking to, and whether Ray is actually working.
 *
 * The provider and database state are shown because a silently degraded
 * assistant is worse than an obviously broken one (docs/09).
 */
export function StatusBar({ health, user }: { health: Health | null; user: User | null }) {
  const online = health?.status === "ok";

  return (
    <header className="flex items-center justify-between border-b border-hud-border bg-hud-panel/50 px-6 py-3">
      <div className="flex items-baseline gap-3">
        <Link href="/" className="font-mono text-lg tracking-[0.3em] text-hud-accent">
          RAY
        </Link>
        <span className="text-sm text-hud-muted">
          {user ? `${user.name}'s assistant` : "No user seeded"}
        </span>
      </div>

      <nav className="hidden items-center gap-4 text-xs text-hud-muted sm:flex">
        <NavLink href="/projects">Projects</NavLink>
        <NavLink href="/tasks">Tasks</NavLink>
        <NavLink href="/calendar">Calendar</NavLink>
        <NavLink href="/memory">Memory</NavLink>
        <NavLink href="/settings">Settings</NavLink>
      </nav>

      <div className="flex items-center gap-5 font-mono text-[11px] uppercase tracking-widest">
        <Indicator label={health?.llm_provider ?? "no provider"} state={online ? "ok" : "off"} />
        <Indicator label={`db ${health?.database ?? "unknown"}`} state={online ? "ok" : "error"} />
        <Indicator
          label={online ? "online" : "offline"}
          state={online ? "ok" : "error"}
          pulse={online}
        />
      </div>
    </header>
  );
}

function NavLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="uppercase tracking-widest hover:text-hud-accent">
      {children}
    </Link>
  );
}

function Indicator({
  label,
  state,
  pulse = false,
}: {
  label: string;
  state: "ok" | "off" | "error";
  pulse?: boolean;
}) {
  const color =
    state === "ok" ? "bg-hud-accent" : state === "error" ? "bg-hud-danger" : "bg-hud-muted";
  return (
    <span className="flex items-center gap-2 text-hud-muted">
      <span className={`h-1.5 w-1.5 rounded-full ${color} ${pulse ? "hud-pulse" : ""}`} />
      {label}
    </span>
  );
}
