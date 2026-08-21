import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];
export type User = Schemas["UserRead"];
export type UserUpdate = Schemas["UserUpdate"];

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/auth/user${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const text = await response.text().catch(() => `Request failed (${response.status})`);
    throw new Error(text);
  }
  return response.json() as Promise<T>;
}

export const getCurrentUser = () => call<User>("");

export const updateCurrentUser = (body: UserUpdate) =>
  call<User>("", { method: "PATCH", body: JSON.stringify(body) });
