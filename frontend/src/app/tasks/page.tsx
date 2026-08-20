"use client";

import { useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Panel, EmptyState, Count } from "@/components/panel";
import { listProjects, type Project } from "@/lib/projects";
import { createTask, deleteTask, listTasks, TASK_PRIORITIES, TASK_STATUSES, updateTask, type Task, type TaskPriority, type TaskStatus } from "@/lib/tasks";

function fromLocalInput(value: string): string {
  return new Date(value).toISOString();
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [projectId, setProjectId] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [deadline, setDeadline] = useState("");

  const [filterProject, setFilterProject] = useState("");
  const [filterStatus, setFilterStatus] = useState<TaskStatus | "">("");

  const load = async () => {
    setLoading(true);
    try {
      const [tasksData, projectsData] = await Promise.all([
        listTasks({ project_id: filterProject || undefined, status: filterStatus || undefined, include_done: true }),
        listProjects(),
      ]);
      setTasks(tasksData);
      setProjects(projectsData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterProject, filterStatus]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    await createTask({
      title: title.trim(),
      description: "",
      project_id: projectId || null,
      status: "todo",
      priority,
      deadline: deadline ? fromLocalInput(deadline) : null,
    });
    setTitle("");
    setProjectId("");
    setPriority("medium");
    setDeadline("");
    await load();
  };

  const handleStatusChange = async (task: Task, status: TaskStatus) => {
    await updateTask(task.id, { status });
    await load();
  };

  const handleDelete = async (id: string) => {
    await deleteTask(id);
    await load();
  };

  const statusBadge = (status: TaskStatus) => {
    const color =
      status === "done"
        ? "text-hud-accent"
        : status === "blocked"
          ? "text-hud-danger"
          : status === "in_progress"
            ? "text-hud-warn"
            : "text-hud-muted";
    return <span className={`font-mono text-[10px] uppercase ${color}`}>{status}</span>;
  };

  const priorityColor = (priority: TaskPriority) => {
    if (priority === "urgent") return "text-hud-danger";
    if (priority === "high") return "text-hud-warn";
    return "text-hud-muted";
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-4 p-6">
      <PageHeader title="Tasks" />

      {error && <p className="rounded-md bg-hud-danger/10 p-3 text-sm text-hud-danger">{error}</p>}

      <Panel title="New task">
        <form onSubmit={handleCreate} className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Task title"
              className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none placeholder:text-hud-muted focus:border-hud-accent"
            />
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text"
            >
              <option value="">No project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskPriority)}
              className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text"
            >
              {TASK_PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <input
              type="datetime-local"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none focus:border-hud-accent"
            />
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="rounded-md bg-hud-accent px-4 py-2 text-sm font-medium text-black hover:bg-hud-accent/90 disabled:opacity-50"
            >
              Add task
            </button>
          </div>
        </form>
      </Panel>

      <Panel
        title="Task list"
        badge={
          <div className="flex items-center gap-2">
            <select
              value={filterProject}
              onChange={(e) => setFilterProject(e.target.value)}
              className="rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-[10px] text-hud-text"
            >
              <option value="">All projects</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value as TaskStatus | "")}
              className="rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-[10px] text-hud-text"
            >
              <option value="">All statuses</option>
              {TASK_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <Count value={tasks.length} />
          </div>
        }
      >
        {tasks.length === 0 ? (
          <EmptyState>No tasks match the filters.</EmptyState>
        ) : (
          <ul className="space-y-3">
            {tasks.map((task) => (
              <li
                key={task.id}
                className="flex flex-col gap-2 rounded-md border border-hud-border bg-hud-panel/50 p-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs ${priorityColor(task.priority)}`}>●</span>
                    <span className="truncate text-sm text-hud-text">{task.title}</span>
                    {task.project_id && (
                      <span className="font-mono text-[10px] uppercase text-hud-accent/70">
                        {projects.find((p) => p.id === task.project_id)?.name ?? "project"}
                      </span>
                    )}
                  </div>
                  {task.deadline && (
                    <p className="mt-0.5 text-[11px] text-hud-muted">
                      Due {new Date(task.deadline).toLocaleString()}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {statusBadge(task.status)}
                  <select
                    value={task.status}
                    onChange={(e) => handleStatusChange(task, e.target.value as TaskStatus)}
                    className="rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-xs text-hud-text"
                  >
                    {TASK_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => handleDelete(task.id)}
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
    </main>
  );
}
