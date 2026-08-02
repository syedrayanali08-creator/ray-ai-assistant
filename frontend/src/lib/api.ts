import "server-only";

import type { components } from "@/lib/api-types";

/**
 * Server-side API client.
 *
 * The bearer token is read here and never sent to the browser: the dashboard is
 * rendered on the server, so the token stays in the Node process (docs/12).
 */

const API_URL = process.env.RAY_API_URL ?? "http://127.0.0.1:8000";
const API_TOKEN = process.env.RAY_API_TOKEN ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${API_TOKEN}` },
    // The dashboard must reflect the database right now, not a cached snapshot.
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`GET ${path} failed`, response.status);
  }
  return (await response.json()) as T;
}

/**
 * Types are generated from the backend's OpenAPI schema (`pnpm generate:api`), so
 * a change to a response shape breaks the build here instead of at runtime.
 */
type Schemas = components["schemas"];

export type User = Schemas["UserRead"];
export type Project = Schemas["ProjectRead"];
export type Task = Schemas["TaskRead"];
export type CalendarEvent = Schemas["CalendarEventRead"];
export type Memory = Schemas["MemoryRead"];
export type Agent = Schemas["AgentRead"];
export type DashboardSummary = Schemas["DashboardSummary"];
export type VoiceCapabilities = Schemas["VoiceCapabilities"];
export type Health = Schemas["HealthResponse"];
export type TaskStatus = Task["status"];
export type TaskPriority = Task["priority"];

export const getDashboard = () => request<DashboardSummary>("/dashboard");

/**
 * Health never throws: a dead backend is a state the HUD renders, not a crash.
 */
export async function getHealth(): Promise<Health | null> {
  try {
    return await request<Health>("/health");
  } catch {
    return null;
  }
}
