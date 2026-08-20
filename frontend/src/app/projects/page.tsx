"use client";

import { useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Panel, EmptyState, Count } from "@/components/panel";
import { createProject, deleteProject, listProjects, PROJECT_STATUSES, updateProject, type Project, type ProjectStatus } from "@/lib/projects";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString();
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setProjects(await listProjects());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createProject({
      name: name.trim(),
      description: "",
      status: "active",
      repo_url: repoUrl.trim() || null,
    });
    setName("");
    setRepoUrl("");
    await load();
  };

  const handleUpdate = async (id: string, status: ProjectStatus, progress: number) => {
    await updateProject(id, { status, progress });
    await load();
  };

  const handleDelete = async (id: string) => {
    await deleteProject(id);
    await load();
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-4 p-6">
      <PageHeader title="Projects" />

      {error && <p className="rounded-md bg-hud-danger/10 p-3 text-sm text-hud-danger">{error}</p>}

      <Panel title="New project">
        <form onSubmit={handleCreate} className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Project name"
              className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none placeholder:text-hud-muted focus:border-hud-accent"
            />
            <input
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="GitHub repo URL (optional)"
              className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none placeholder:text-hud-muted focus:border-hud-accent"
            />
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="rounded-md bg-hud-accent px-4 py-2 text-sm font-medium text-black hover:bg-hud-accent/90 disabled:opacity-50"
            >
              Create project
            </button>
          </div>
        </form>
      </Panel>

      <Panel title="Project dashboard" badge={<Count value={projects.length} />}>
        {projects.length === 0 ? (
          <EmptyState>No projects yet. Create one to see progress and repo context.</EmptyState>
        ) : (
          <ul className="space-y-4">
            {projects.map((project) => (
              <li key={project.id} className="rounded-md border border-hud-border bg-hud-panel/50 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex-1">
                    <div className="flex items-baseline gap-3">
                      <h3 className="text-base font-medium text-hud-text">{project.name}</h3>
                      <span className="font-mono text-[10px] uppercase tracking-widest text-hud-muted">
                        {project.status}
                      </span>
                    </div>
                    {project.repo_url && (
                      <p className="mt-0.5 text-xs text-hud-muted">{project.repo_url}</p>
                    )}
                    <p className="mt-2 text-xs text-hud-muted">Updated {formatDate(project.updated_at)}</p>
                  </div>

                  <ProjectQuickUpdate
                    project={project}
                    onUpdate={handleUpdate}
                    onDelete={handleDelete}
                  />
                </div>

                {project.progress !== null && (
                  <div className="mt-3">
                    <div className="flex items-center justify-between text-xs text-hud-muted">
                      <span>Progress</span>
                      <span className="font-mono text-hud-accent">{project.progress}%</span>
                    </div>
                    <div className="mt-1 h-1.5 w-full rounded-full bg-hud-border">
                      <div
                        className="h-1.5 rounded-full bg-hud-accent"
                        style={{ width: `${project.progress}%` }}
                      />
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </main>
  );
}

function ProjectQuickUpdate({
  project,
  onUpdate,
  onDelete,
}: {
  project: Project;
  onUpdate: (id: string, status: ProjectStatus, progress: number) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [status, setStatus] = useState<ProjectStatus>(project.status);
  const [progress, setProgress] = useState(project.progress ?? 0);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={status}
        onChange={(e) => setStatus(e.target.value as ProjectStatus)}
        className="rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-xs text-hud-text"
      >
        {PROJECT_STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      <input
        type="number"
        min={0}
        max={100}
        value={progress}
        onChange={(e) => setProgress(Number(e.target.value))}
        className="w-16 rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-xs text-hud-text"
      />
      <button
        onClick={() => onUpdate(project.id, status, progress)}
        className="rounded-md border border-hud-border px-2 py-1 text-xs text-hud-text hover:border-hud-accent hover:text-hud-accent"
      >
        Save
      </button>
      <button
        onClick={() => onDelete(project.id)}
        className="rounded-md border border-hud-danger/30 px-2 py-1 text-xs text-hud-danger hover:bg-hud-danger/10"
      >
        Delete
      </button>
    </div>
  );
}
