"use client";

import { useCallback, useEffect, useState } from "react";

import {
  CATEGORIES,
  createMemory,
  deleteMemory,
  describeScore,
  getStats,
  listMemories,
  looksSemantic,
  relativeDate,
  searchMemories,
  setDisabledCategories,
  toggleCategory,
  updateMemory,
  type Memory,
  type MemoryCategory,
  type MemoryStats,
} from "@/lib/memory";

/**
 * The memory view (docs/05, docs/12).
 *
 * Ray's memory is the user's data, so this screen exists to make it correctable:
 * every row can be edited or deleted, every row shows where it came from, and every
 * category can be switched off. Semantic search shows the retrieval score, because
 * "why does Ray keep bringing that up?" is answered by the ranking, not the text.
 */

type Row = { memory: Memory; score?: number; similarity?: number };

export function MemoryManager() {
  const [rows, setRows] = useState<Row[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [query, setQuery] = useState("");
  const [semantic, setSemantic] = useState(false);
  const [category, setCategory] = useState<MemoryCategory | "all">("all");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const useSemantic = semantic && query.trim() !== "";
      const found: Row[] = useSemantic
        ? (await searchMemories(query)).map((item) => ({
            memory: item.memory,
            score: item.score,
            similarity: item.similarity,
          }))
        : (await listMemories({ q: query, category })).map((memory) => ({ memory }));
      setRows(found);
      setStats(await getStats());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }, [category, query, semantic]);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (action: () => Promise<unknown>) => {
    try {
      await action();
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong.");
    }
  };

  const disabled = stats?.disabled_categories ?? [];

  return (
    <div className="space-y-4">
      <section className="rounded-md border border-hud-border bg-hud-panel p-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              // Suggest the mode rather than switching silently once the query
              // stops looking like a keyword hunt.
              setSemantic(looksSemantic(event.target.value));
            }}
            placeholder="Search Ray's memory…"
            aria-label="Search memories"
            className="min-w-56 flex-1 rounded-md border border-hud-border bg-hud-bg px-3 py-2 text-sm text-hud-text outline-none focus:border-hud-accent"
          />
          <label className="flex items-center gap-2 text-xs text-hud-muted">
            <input
              type="checkbox"
              checked={semantic}
              onChange={(event) => setSemantic(event.target.checked)}
            />
            Semantic
          </label>
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value as MemoryCategory | "all")}
            aria-label="Filter by category"
            disabled={semantic}
            className="rounded-md border border-hud-border bg-hud-bg px-2 py-2 text-sm text-hud-text disabled:opacity-40"
          >
            <option value="all">All categories</option>
            {CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-hud-muted">
          <span className="uppercase tracking-widest">Remember</span>
          {CATEGORIES.map((item) => {
            const off = disabled.includes(item);
            return (
              <button
                key={item}
                type="button"
                onClick={() =>
                  void act(() => setDisabledCategories(toggleCategory(disabled, item)))
                }
                aria-pressed={!off}
                className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest ${
                  off
                    ? "border-hud-border text-hud-muted line-through"
                    : "border-hud-accent/60 text-hud-accent"
                }`}
              >
                {item}
                {stats !== null && ` ${stats.by_category[item] ?? 0}`}
              </button>
            );
          })}
        </div>

        {stats !== null && (
          <p className="mt-2 text-[11px] text-hud-muted">
            {stats.total} live · {stats.superseded} superseded
            {stats.unembedded > 0 && ` · ${stats.unembedded} not searchable`}
          </p>
        )}
      </section>

      <AddMemory onAdd={(body) => act(() => createMemory(body))} />

      {error !== null && (
        <p role="alert" className="text-sm text-hud-danger">
          {error}
        </p>
      )}

      {rows.length === 0 ? (
        <p className="text-sm text-hud-muted">
          {busy ? "Loading…" : "Nothing here yet. Tell Ray to remember something."}
        </p>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <MemoryRow
              key={row.memory.id}
              row={row}
              onSave={(content, importance) =>
                act(() => updateMemory(row.memory.id, { content, importance }))
              }
              onDelete={() => act(() => deleteMemory(row.memory.id))}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function MemoryRow({
  row,
  onSave,
  onDelete,
}: {
  row: Row;
  onSave: (content: string, importance: number) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const { memory } = row;
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(memory.content);
  const [importance, setImportance] = useState(memory.importance);

  return (
    <li className="rounded-md border border-hud-border bg-hud-panel p-3">
      <div className="flex items-start justify-between gap-3">
        <span className="font-mono text-[10px] uppercase tracking-widest text-hud-accent/70">
          {memory.category} · {memory.importance}/5
          {row.score !== undefined && ` · score ${describeScore(row.score)}`}
        </span>
        <div className="flex shrink-0 gap-2 text-[11px]">
          <button
            type="button"
            onClick={() => setEditing((previous) => !previous)}
            className="text-hud-muted hover:text-hud-text"
          >
            {editing ? "Cancel" : "Edit"}
          </button>
          <button type="button" onClick={() => void onDelete()} className="text-hud-danger">
            Delete
          </button>
        </div>
      </div>

      {editing ? (
        <div className="mt-2 space-y-2">
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            aria-label="Memory content"
            rows={3}
            className="w-full rounded-md border border-hud-border bg-hud-bg px-2 py-1 text-sm text-hud-text"
          />
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-hud-muted">
              Importance
              <input
                type="number"
                min={1}
                max={5}
                value={importance}
                onChange={(event) => setImportance(Number(event.target.value))}
                className="w-16 rounded-md border border-hud-border bg-hud-bg px-2 py-1 text-sm text-hud-text"
              />
            </label>
            <button
              type="button"
              onClick={async () => {
                await onSave(content, importance);
                setEditing(false);
              }}
              className="rounded-md border border-hud-accent/60 px-3 py-1 text-xs text-hud-accent"
            >
              Save
            </button>
          </div>
        </div>
      ) : (
        <p className="mt-1 text-sm text-hud-text">{memory.content}</p>
      )}

      {/* Provenance: where this came from, and when Ray last found it useful. */}
      <p className="mt-1 text-[11px] italic text-hud-muted">
        {memory.why !== "" ? `${memory.why} ` : ""}
        <span className="not-italic">
          via {memory.source} · {relativeDate(memory.created_at)} · used {memory.hit_count}×
        </span>
      </p>
    </li>
  );
}

function AddMemory({
  onAdd,
}: {
  onAdd: (body: { content: string; category: MemoryCategory }) => Promise<void>;
}) {
  const [content, setContent] = useState("");
  const [category, setCategory] = useState<MemoryCategory>("user");

  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={async (event) => {
        event.preventDefault();
        if (content.trim() === "") return;
        await onAdd({ content: content.trim(), category });
        setContent("");
      }}
    >
      <input
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder="Teach Ray something directly…"
        aria-label="New memory"
        className="min-w-56 flex-1 rounded-md border border-hud-border bg-hud-bg px-3 py-2 text-sm text-hud-text outline-none focus:border-hud-accent"
      />
      <select
        value={category}
        onChange={(event) => setCategory(event.target.value as MemoryCategory)}
        aria-label="New memory category"
        className="rounded-md border border-hud-border bg-hud-bg px-2 py-2 text-sm text-hud-text"
      >
        {CATEGORIES.map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
      </select>
      <button
        type="submit"
        className="rounded-md border border-hud-accent/60 px-3 py-2 text-xs uppercase tracking-widest text-hud-accent"
      >
        Remember
      </button>
    </form>
  );
}
