import Link from "next/link";
import type { ReactNode } from "react";

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="mb-6 flex items-baseline justify-between border-b border-hud-border pb-4">
      <div>
        <Link href="/" className="text-[10px] uppercase tracking-widest text-hud-muted hover:text-hud-text">
          ← Back to Ray
        </Link>
        <h1 className="mt-1 font-mono text-lg uppercase tracking-[0.2em] text-hud-accent">{title}</h1>
      </div>
      {children}
    </header>
  );
}
