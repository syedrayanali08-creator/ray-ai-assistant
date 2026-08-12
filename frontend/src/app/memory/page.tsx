import Link from "next/link";

import { MemoryManager } from "@/components/memory-manager";

export const dynamic = "force-dynamic";

export default function MemoryPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-4 p-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="font-mono text-sm uppercase tracking-[0.3em] text-hud-accent">Memory</h1>
          <p className="mt-1 text-xs text-hud-muted">
            Everything Ray remembers about you, and where each memory came from.
          </p>
        </div>
        <Link href="/" className="text-xs text-hud-muted hover:text-hud-text">
          ← Back to Ray
        </Link>
      </header>

      <MemoryManager />
    </main>
  );
}
