import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];
export type Project = Schemas["ProjectRead"];
export type ProjectCreate = Schemas["ProjectCreate"];
export type ProjectUpdate = Schemas["ProjectUpdate"];
export type ProjectStatus = Schemas["ProjectStatus"];

export const PROJECT_STATUSES: ProjectStatus[] = ["planning", "active", "paused", "complete", "archived"];

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/projects${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const text = await response.text().catch(() => `Request failed (${response.status})`);
    throw new Error(text);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const listProjects = () => call<Project[]>("");

export const createProject = (body: ProjectCreate) =>
  call<Project>("", { method: "POST", body: JSON.stringify(body) });

export const updateProject = (id: string, body: ProjectUpdate) =>
  call<Project>(`/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteProject = (id: string) => call<void>(`/${id}`, { method: "DELETE" });
