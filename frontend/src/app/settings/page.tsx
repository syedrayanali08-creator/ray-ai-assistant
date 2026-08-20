"use client";

import { useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Panel, EmptyState, Count } from "@/components/panel";
import {
  checkIntegration,
  createIntegration,
  deleteIntegration,
  INTEGRATION_TYPES,
  listIntegrations,
  providersForType,
  updateIntegration,
  type Integration,
  type IntegrationType,
} from "@/lib/integrations";
import { listPermissions, listTools, MODES, updatePermission, type PermissionMode, type ToolInfo, type ToolPermission } from "@/lib/tools";

const PROVIDER_LABELS: Record<string, string> = {
  github: "GitHub",
  local: "Local",
  google: "Google Calendar",
  obsidian: "Obsidian vault",
  notion: "Notion",
};

const TYPE_LABELS: Record<IntegrationType, string> = {
  github: "GitHub",
  calendar: "Calendar",
  knowledge: "Knowledge",
  files: "Local files",
};

export default function SettingsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [permissions, setPermissions] = useState<ToolPermission[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [type, setType] = useState<IntegrationType>("files");
  const [provider, setProvider] = useState("");
  const [config, setConfig] = useState<Record<string, string>>({});
  const [credentials, setCredentials] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [integrationsData, toolsData, permissionsData] = await Promise.all([
        listIntegrations(),
        listTools(),
        listPermissions(),
      ]);
      setIntegrations(integrationsData);
      setTools(toolsData);
      setPermissions(permissionsData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    setProvider(providersForType(type)[0] ?? "");
    setConfig({});
  }, [type]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await createIntegration({
      type,
      provider,
      enabled: true,
      credentials_reference: credentials.trim() || null,
      config,
    });
    setCredentials("");
    setConfig({});
    await load();
  };

  const handleToggle = async (integration: Integration) => {
    await updateIntegration(integration.id, { enabled: !integration.enabled });
    await load();
  };

  const handleCheck = async (id: string) => {
    await checkIntegration(id);
    await load();
  };

  const handleDelete = async (id: string) => {
    await deleteIntegration(id);
    await load();
  };

  const handlePermissionChange = async (toolName: string, mode: PermissionMode) => {
    await updatePermission(toolName, mode);
    await load();
  };

  const configFields = (selectedProvider: string) => {
    if (type === "files") return [{ key: "allowed_paths", label: "Allowed directories (comma-separated)" }];
    if (type === "knowledge" && selectedProvider === "obsidian") return [{ key: "vault_path", label: "Vault path" }];
    if (type === "github") return [{ key: "owner", label: "Default owner (optional)" }, { key: "repo", label: "Default repo (optional)" }];
    return [];
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-4 p-6">
      <PageHeader title="Settings" />

      {error && <p className="rounded-md bg-hud-danger/10 p-3 text-sm text-hud-danger">{error}</p>}

      <Panel title="Integrations" badge={<Count value={integrations.length} />}>
        <div className="mb-4 rounded-md border border-hud-border bg-hud-panel/50 p-4">
          <h3 className="mb-2 font-mono text-[11px] uppercase tracking-widest text-hud-muted">Add integration</h3>
          <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <select
                value={type}
                onChange={(e) => setType(e.target.value as IntegrationType)}
                className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text"
              >
                {INTEGRATION_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {TYPE_LABELS[t]}
                  </option>
                ))}
              </select>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text"
              >
                {providersForType(type).map((p) => (
                  <option key={p} value={p}>
                    {PROVIDER_LABELS[p] ?? p}
                  </option>
                ))}
              </select>
              <input
                value={credentials}
                onChange={(e) => setCredentials(e.target.value)}
                placeholder="Credentials reference (env var name, optional)"
                className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none placeholder:text-hud-muted focus:border-hud-accent"
              />
            </div>
            {configFields(provider).map(({ key, label }) => (
              <input
                key={key}
                value={config[key] ?? ""}
                onChange={(e) => setConfig({ ...config, [key]: e.target.value })}
                placeholder={label}
                className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none placeholder:text-hud-muted focus:border-hud-accent"
              />
            ))}
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={loading}
                className="rounded-md bg-hud-accent px-4 py-2 text-sm font-medium text-black hover:bg-hud-accent/90 disabled:opacity-50"
              >
                Add integration
              </button>
            </div>
          </form>
        </div>

        {integrations.length === 0 ? (
          <EmptyState>No integrations configured yet.</EmptyState>
        ) : (
          <ul className="space-y-3">
            {integrations.map((integration) => (
              <li
                key={integration.id}
                className="flex flex-col gap-2 rounded-md border border-hud-border bg-hud-panel/50 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`h-2 w-2 rounded-full ${integration.enabled ? "bg-hud-accent" : "bg-hud-muted"}`}
                    />
                    <span className="text-sm font-medium text-hud-text">
                      {TYPE_LABELS[integration.type]} — {PROVIDER_LABELS[integration.provider] ?? integration.provider}
                    </span>
                    <span className="font-mono text-[10px] uppercase text-hud-muted">{integration.status}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-hud-muted">
                    Last sync: {integration.last_sync ? new Date(integration.last_sync).toLocaleString() : "never"}
                    {integration.last_error ? ` · Error: ${integration.last_error}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCheck(integration.id)}
                    className="rounded-md border border-hud-border px-2 py-1 text-xs text-hud-text hover:border-hud-accent hover:text-hud-accent"
                  >
                    Check
                  </button>
                  <button
                    onClick={() => handleToggle(integration)}
                    className="rounded-md border border-hud-border px-2 py-1 text-xs text-hud-text hover:border-hud-accent hover:text-hud-accent"
                  >
                    {integration.enabled ? "Disable" : "Enable"}
                  </button>
                  <button
                    onClick={() => handleDelete(integration.id)}
                    className="rounded-md border border-hud-danger/30 px-2 py-1 text-xs text-hud-danger hover:bg-hud-danger/10"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Tool permissions">
        {tools.length === 0 ? (
          <EmptyState>No tools registered.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {tools.map((tool) => {
              const permission = permissions.find((p) => p.tool_name === tool.name)?.mode ?? "ask";
              return (
                <li
                  key={tool.name}
                  className="flex flex-col justify-between gap-2 rounded-md border border-hud-border bg-hud-panel/50 p-3 sm:flex-row sm:items-center"
                >
                  <div>
                    <p className="text-sm text-hud-text">{tool.name}</p>
                    <p className="text-xs text-hud-muted">{tool.description}</p>
                    {tool.side_effect && (
                      <p className="text-[10px] text-hud-warn">Side-effecting tool — requires approval.</p>
                    )}
                  </div>
                  <select
                    value={permission}
                    disabled={tool.side_effect && !tool.standing_allow_eligible}
                    onChange={(e) => handlePermissionChange(tool.name, e.target.value as PermissionMode)}
                    className="rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-xs text-hud-text disabled:opacity-50"
                  >
                    {MODES.map((mode) => (
                      <option key={mode} value={mode}>
                        {mode}
                      </option>
                    ))}
                  </select>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </main>
  );
}
