import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];
export type Diagnostics = Schemas["DiagnosticsResponse"];
export type ExportSnapshot = Schemas["ExportSnapshot"];

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/system${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const text = await response.text().catch(() => `Request failed (${response.status})`);
    throw new Error(text);
  }
  return response.json() as Promise<T>;
}

export const getDiagnostics = () => call<Diagnostics>("/diagnostics");

export const exportData = () => call<ExportSnapshot>("/export");
