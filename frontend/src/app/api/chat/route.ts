import { NextRequest } from "next/server";

/**
 * Server-side chat proxy.
 *
 * Its only job is to attach the bearer token and pass the SSE stream through
 * untouched. The browser never sees `RAY_API_TOKEN` (docs/12), and because the
 * body is piped rather than buffered, tokens still arrive one at a time.
 */

const API_URL = process.env.RAY_API_URL ?? "http://127.0.0.1:8000";
const API_TOKEN = process.env.RAY_API_TOKEN ?? "";

export async function POST(request: NextRequest) {
  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}/chat/message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_TOKEN}`,
      },
      body: await request.text(),
      signal: request.signal,
      // Next must not buffer or cache a stream.
      cache: "no-store",
      // @ts-expect-error - Node's fetch needs this to stream a request body.
      duplex: "half",
    });
  } catch {
    return Response.json({ detail: "Ray's backend is not reachable." }, { status: 502 });
  }

  if (!upstream.ok || upstream.body === null) {
    return Response.json(
      { detail: await upstream.text().catch(() => "Upstream error") },
      { status: upstream.status },
    );
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
