import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];
export type CalendarEvent = Schemas["CalendarEventRead"];
export type CalendarEventCreate = Schemas["CalendarEventCreate"];
export type CalendarEventUpdate = Schemas["CalendarEventUpdate"];

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/calendar${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const text = await response.text().catch(() => `Request failed (${response.status})`);
    throw new Error(text);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const listEvents = () => call<CalendarEvent[]>("");

export const createEvent = (body: CalendarEventCreate) =>
  call<CalendarEvent>("/event", { method: "POST", body: JSON.stringify(body) });

export const updateEvent = (id: string, body: CalendarEventUpdate) =>
  call<CalendarEvent>(`/event/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteEvent = (id: string) => call<void>(`/event/${id}`, { method: "DELETE" });

export const exportICS = async (days = 30) => {
  const response = await fetch(`/api/calendar/export.ics?days=${days}`);
  if (!response.ok) throw new Error("ICS export failed");
  return response.text();
};

export const importICS = async (ics: string) => {
  const response = await fetch("/api/calendar/import.ics", {
    method: "POST",
    headers: { "Content-Type": "text/calendar" },
    body: ics,
  });
  if (!response.ok) throw new Error("ICS import failed");
  return (await response.json()) as CalendarEvent[];
};
