"use client";

import { useEffect, useRef, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Panel, EmptyState, Count } from "@/components/panel";
import { createEvent, deleteEvent, exportICS, importICS, listEvents, updateEvent, type CalendarEvent } from "@/lib/calendar";

function toLocalInput(iso: string): string {
  const date = new Date(iso);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromLocalInput(value: string): string {
  return new Date(value).toISOString();
}

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [location, setLocation] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setEvents(await listEvents());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load calendar");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const resetForm = () => {
    setTitle("");
    setStart("");
    setEnd("");
    setLocation("");
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !start || !end) return;
    await createEvent({
      title: title.trim(),
      description: "",
      start_time: fromLocalInput(start),
      end_time: fromLocalInput(end),
      location: location.trim() || null,
    });
    resetForm();
    await load();
  };

  const handleExport = async () => {
    const ics = await exportICS();
    const blob = new Blob([ics], { type: "text/calendar" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "ray-calendar.ics";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = async (file: File | null) => {
    if (!file) return;
    const text = await file.text();
    await importICS(text);
    await load();
  };

  const handleDelete = async (id: string) => {
    await deleteEvent(id);
    await load();
  };

  const sortedEvents = [...events].sort(
    (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
  );

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-4 p-6">
      <PageHeader title="Calendar" />

      {error && <p className="rounded-md bg-hud-danger/10 p-3 text-sm text-hud-danger">{error}</p>}

      <Panel title="New event">
        <form onSubmit={handleCreate} className="flex flex-col gap-3">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Event title"
            className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none placeholder:text-hud-muted focus:border-hud-accent"
          />
          <div className="grid gap-3 sm:grid-cols-3">
            <input
              type="datetime-local"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none focus:border-hud-accent"
            />
            <input
              type="datetime-local"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none focus:border-hud-accent"
            />
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Location (optional)"
              className="rounded-md border border-hud-border bg-hud-panel px-3 py-2 text-sm text-hud-text outline-none placeholder:text-hud-muted focus:border-hud-accent"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={handleExport}
              className="rounded-md border border-hud-border px-3 py-2 text-xs text-hud-text hover:border-hud-accent hover:text-hud-accent"
            >
              Export ICS
            </button>
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              className="rounded-md border border-hud-border px-3 py-2 text-xs text-hud-text hover:border-hud-accent hover:text-hud-accent"
            >
              Import ICS
            </button>
            <input
              ref={fileInput}
              type="file"
              accept=".ics,text/calendar"
              className="hidden"
              onChange={(e) => {
                void handleImport(e.target.files?.[0] ?? null);
                if (e.target.value) e.target.value = "";
              }}
            />
            <button
              type="submit"
              disabled={loading}
              className="rounded-md bg-hud-accent px-4 py-2 text-sm font-medium text-black hover:bg-hud-accent/90 disabled:opacity-50"
            >
              Add event
            </button>
          </div>
        </form>
      </Panel>

      <Panel title="Upcoming events" badge={<Count value={events.length} />}>
        {sortedEvents.length === 0 ? (
          <EmptyState>No events yet. Add one or import an ICS file.</EmptyState>
        ) : (
          <ul className="space-y-3">
            {sortedEvents.map((event) => (
              <EventRow key={event.id} event={event} onDelete={handleDelete} />
            ))}
          </ul>
        )}
      </Panel>
    </main>
  );
}

function EventRow({ event, onDelete }: { event: CalendarEvent; onDelete: (id: string) => Promise<void> }) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(event.title);
  const [start, setStart] = useState(toLocalInput(event.start_time));
  const [end, setEnd] = useState(toLocalInput(event.end_time));

  const handleSave = async () => {
    await updateEvent(event.id, {
      title,
      start_time: fromLocalInput(start),
      end_time: fromLocalInput(end),
    });
    setIsEditing(false);
  };

  if (isEditing) {
    return (
      <li className="flex flex-wrap items-center gap-2 rounded-md border border-hud-border bg-hud-panel/50 p-3">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="flex-1 rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-sm text-hud-text"
        />
        <input
          type="datetime-local"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          className="rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-xs text-hud-text"
        />
        <input
          type="datetime-local"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          className="rounded-md border border-hud-border bg-hud-panel px-2 py-1 text-xs text-hud-text"
        />
        <button
          onClick={() => void handleSave()}
          className="rounded-md bg-hud-accent px-2 py-1 text-xs font-medium text-black"
        >
          Save
        </button>
        <button onClick={() => setIsEditing(false)} className="rounded-md border border-hud-border px-2 py-1 text-xs text-hud-text">
          Cancel
        </button>
      </li>
    );
  }

  return (
    <li className="flex flex-col gap-1 rounded-md border border-hud-border bg-hud-panel/50 p-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm text-hud-text">{event.title}</p>
        <p className="text-xs text-hud-muted">
          {new Date(event.start_time).toLocaleString()} — {new Date(event.end_time).toLocaleString()}
          {event.location ? ` · ${event.location}` : ""}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsEditing(true)}
          className="rounded-md border border-hud-border px-2 py-1 text-xs text-hud-text hover:border-hud-accent hover:text-hud-accent"
        >
          Edit
        </button>
        <button
          onClick={() => onDelete(event.id)}
          className="rounded-md border border-hud-danger/30 px-2 py-1 text-xs text-hud-danger hover:bg-hud-danger/10"
        >
          Delete
        </button>
      </div>
    </li>
  );
}
