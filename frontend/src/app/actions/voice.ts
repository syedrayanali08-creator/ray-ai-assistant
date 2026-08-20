"use server";

/**
 * Bridge the browser WebSocket to the local backend.
 *
 * WebSockets cannot carry HTTP Authorization headers from the browser, so the
 * server returns the one-time connection URL with the API token in the query
 * string. This is acceptable for a single-user local install where the browser
 * and backend are on the same machine; a production/public Ray would use signed
 * tickets or cookie-based auth instead.
 */
export async function getVoiceStreamUrl(): Promise<string | null> {
  const token = process.env.RAY_API_TOKEN;
  const apiUrl = process.env.RAY_API_URL ?? "http://127.0.0.1:8000";
  if (!token) return null;

  const httpUrl = new URL(apiUrl);
  const protocol = httpUrl.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = new URL("/voice/stream", `${protocol}//${httpUrl.host}`);
  wsUrl.searchParams.set("token", token);
  return wsUrl.toString();
}
