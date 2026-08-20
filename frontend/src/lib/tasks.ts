import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];
export type Task = Schemas["TaskRead"];
export type TaskCreate = Schemas["TaskCreate"];
export type TaskUpdate = Schemas["TaskUpdate"];
export type TaskStatus = Schemas["TaskStatus"];
export type TaskPriority = Schemas["TaskPriority"];

export const TASK_STATUSES: TaskStatus[] = ["todo", "in_progress", "blocked", "done", "cancelled"];
export const TASK_PRIORITIES: TaskPriority[] = ["low", "medium", "high", "urgent"];

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/tasks${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const text = await response.text().catch(() => `Request failed (${response.status})`);
    throw new Error(text);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const listTasks = (params?: { project_id?: string; status?: TaskStatus; include_done?: boolean }) => {
  const search = new URLSearchParams();
  if (params?.project_id) search.set("project_id", params.project_id);
  if (params?.status) search.set("status", params.status);
  if (params?.include_done) search.set("include_done", "true");
  const query = search.toString();
  return call<Task[]>(`?${query}`);
};

export const createTask = (body: TaskCreate) => call<Task>("", { method: "POST", body: JSON.stringify(body) });

export const updateTask = (id: string, body: TaskUpdate) =>
  call<Task>(`/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteTask = (id: string) => call<void>(`/${id}`, { method: "DELETE" });
