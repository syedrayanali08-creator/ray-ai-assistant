import type { Agent, CalendarEvent, Memory, Project, Task } from "@/lib/api";

import { Count, EmptyState, Panel } from "@/components/panel";

const PRIORITY_COLOR: Record<Task["priority"], string> = {
  urgent: "text-hud-danger",
  high: "text-hud-warn",
  medium: "text-hud-muted",
  low: "text-hud-muted",
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDeadline(iso: string): string {
  const date = new Date(iso);
  const days = Math.round((date.getTime() - Date.now()) / 86_400_000);
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return `${days}d`;
}

export function TaskPanel({ tasks, overdue }: { tasks: Task[]; overdue: number }) {
  return (
    <Panel
      title="Tasks"
      badge={
        overdue > 0 ? <Count value={overdue} tone="danger" /> : <Count value={tasks.length} />
      }
    >
      {tasks.length === 0 ? (
        <EmptyState>Nothing outstanding.</EmptyState>
      ) : (
        <ul className="space-y-2.5">
          {tasks.map((task) => (
            <li key={task.id} className="flex items-start justify-between gap-3 text-sm">
              <span className="flex items-start gap-2">
                <span className={`mt-1 text-[10px] ${PRIORITY_COLOR[task.priority]}`}>●</span>
                <span>
                  <span className="text-hud-text">{task.title}</span>
                  {/* A project task and a standalone task are the same row; only
                      the badge differs (ADR-0004). */}
                  {task.project_id !== null && (
                    <span className="ml-2 font-mono text-[10px] uppercase text-hud-accent/70">
                      project
                    </span>
                  )}
                </span>
              </span>
              {task.deadline !== null && (
                <span className="shrink-0 font-mono text-[10px] text-hud-muted">
                  {formatDeadline(task.deadline)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export function SchedulePanel({ events }: { events: CalendarEvent[] }) {
  return (
    <Panel title="Today" badge={<Count value={events.length} />}>
      {events.length === 0 ? (
        <EmptyState>No events scheduled.</EmptyState>
      ) : (
        <ul className="space-y-2.5">
          {events.map((event) => (
            <li key={event.id} className="flex items-baseline gap-3 text-sm">
              <span className="font-mono text-[11px] text-hud-accent">
                {formatTime(event.start_time)}
              </span>
              <span className="text-hud-text">{event.title}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export function ProjectPanel({ projects }: { projects: Project[] }) {
  return (
    <Panel title="Projects" badge={<Count value={projects.length} />}>
      {projects.length === 0 ? (
        <EmptyState>No projects yet.</EmptyState>
      ) : (
        <ul className="space-y-3">
          {projects.map((project) => (
            <li key={project.id}>
              <div className="flex items-baseline justify-between text-sm">
                <span className="text-hud-text">{project.name}</span>
                <span className="font-mono text-[10px] uppercase text-hud-muted">
                  {project.status}
                </span>
              </div>
              {project.progress !== null && (
                <div className="mt-1.5 h-1 w-full rounded-full bg-hud-border">
                  <div
                    className="h-1 rounded-full bg-hud-accent"
                    style={{ width: `${project.progress}%` }}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export function MemoryPanel({ memories }: { memories: Memory[] }) {
  return (
    <Panel title="Memory" badge={<Count value={memories.length} />}>
      {memories.length === 0 ? (
        <EmptyState>Ray has not learned anything yet.</EmptyState>
      ) : (
        <ul className="space-y-3">
          {memories.map((memory) => (
            <li key={memory.id} className="text-sm">
              <span className="font-mono text-[10px] uppercase tracking-widest text-hud-accent/70">
                {memory.category}
              </span>
              <p className="text-hud-text">{memory.content}</p>
              {/* Provenance is shown, not hidden: the user should be able to see
                  why Ray believes something (docs/12). */}
              {memory.why !== "" && (
                <p className="mt-0.5 text-[11px] italic text-hud-muted">{memory.why}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export function AgentPanel({ agents }: { agents: Agent[] }) {
  return (
    <Panel title="Agents" badge={<Count value={agents.filter((a) => a.enabled).length} />}>
      <ul className="space-y-2">
        {agents.map((agent) => (
          <li key={agent.name} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  agent.enabled ? "bg-hud-accent" : "bg-hud-muted"
                }`}
              />
              <span className="text-hud-text">{agent.display_name}</span>
            </span>
            <span className="font-mono text-[10px] text-hud-muted">
              {agent.tools.length} tools
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
