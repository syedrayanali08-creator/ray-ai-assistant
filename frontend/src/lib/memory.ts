import type { components } from "@/lib/api-types";

/**
 * Browser-side memory client.
 *
 * Everything goes through `/api/memory/*`, which attaches the token server-side.
 * The pure helpers below are separated from the fetches so the parts with rules in
 * them — which search to run, how to describe a score — are testable without a
 * network or a DOM.
 */

type Schemas = components["schemas"];

export type Memory = Schemas["MemoryRead"];
export type MemoryScored = Schemas["MemoryScored"];
export type MemoryStats = Schemas["MemoryStats"];
export type MemoryCategory = Memory["category"];

export const CATEGORIES: MemoryCategory[] = [
  "user",
  "project",
  "learning",
  "goal",
  "conversation",
];

export class MemoryError extends Error {}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/memory${path}`, {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new MemoryError(await readDetail(response));
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export const listMemories = (params: { q?: string; category?: MemoryCategory | "all" }) =>
  call<Memory[]>(`?${listQuery(params)}`);

export const searchMemories = (query: string) =>
  call<MemoryScored[]>(`/search?q=${encodeURIComponent(query)}`);

export const getStats = () => call<MemoryStats>("/stats");

export const createMemory = (body: { content: string; category: MemoryCategory }) =>
  call<Memory>("", { method: "POST", body: JSON.stringify(body) });

export const updateMemory = (
  id: string,
  body: { content?: string; importance?: number; category?: MemoryCategory },
) => call<Memory>(`/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteMemory = (id: string) => call<void>(`/${id}`, { method: "DELETE" });

export const setDisabledCategories = (disabled: MemoryCategory[]) =>
  call<{ disabled_categories: MemoryCategory[] }>("/categories", {
    method: "PUT",
    body: JSON.stringify({ disabled_categories: disabled }),
  });

// -- pure helpers ---------------------------------------------------------

export function listQuery({
  q,
  category,
}: {
  q?: string;
  category?: MemoryCategory | "all";
}): string {
  const params = new URLSearchParams();
  if (q !== undefined && q.trim() !== "") params.set("q", q.trim());
  if (category !== undefined && category !== "all") params.set("category", category);
  return params.toString();
}

/**
 * Whether a query should use semantic search rather than substring matching.
 *
 * A word or two is almost always someone hunting for a memory they remember
 * writing; a phrase is someone asking a question. Guessing wrong is cheap — the
 * mode is a visible toggle — but guessing right means the common case needs no
 * decision from the user.
 */
export function looksSemantic(query: string): boolean {
  return query.trim().split(/\s+/).length >= 4;
}

export function toggleCategory(
  disabled: MemoryCategory[],
  category: MemoryCategory,
): MemoryCategory[] {
  return disabled.includes(category)
    ? disabled.filter((item) => item !== category)
    : [...disabled, category];
}

/** A score is only meaningful next to the others in the same result set. */
export function describeScore(score: number): string {
  return score.toFixed(2);
}

export function relativeDate(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}
