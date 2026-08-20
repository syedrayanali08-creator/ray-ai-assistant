export type ToolInfo = {
  name: string;
  description: string;
  side_effect: boolean;
  standing_allow_eligible: boolean;
};

export type ToolPermission = {
  tool_name: string;
  mode: "ask" | "always_allow" | "deny";
};

export type PermissionMode = ToolPermission["mode"];

export const MODES: PermissionMode[] = ["ask", "always_allow", "deny"];

export async function listTools(): Promise<ToolInfo[]> {
  const response = await fetch("/api/tools");
  if (!response.ok) throw new Error("Failed to load tools");
  return (await response.json()) as ToolInfo[];
}

export async function listPermissions(): Promise<ToolPermission[]> {
  const response = await fetch("/api/tools/permissions");
  if (!response.ok) throw new Error("Failed to load permissions");
  return (await response.json()) as ToolPermission[];
}

export async function updatePermission(toolName: string, mode: PermissionMode): Promise<ToolPermission> {
  const response = await fetch(`/api/tools/permissions/${encodeURIComponent(toolName)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "Failed to update permission");
  }
  return (await response.json()) as ToolPermission;
}
