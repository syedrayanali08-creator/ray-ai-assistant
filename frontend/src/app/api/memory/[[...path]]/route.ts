import { NextRequest } from "next/server";

/**
 * Server-side memory proxy.
 *
 * The memory view is interactive — search, edit, delete, toggle categories — so
 * unlike the dashboard it cannot be rendered once on the server. Rather than
 * shipping the bearer token to the browser to achieve that, the browser talks to
 * this route and the token stays in the Node process (docs/12).
 */

const API_URL = process.env.RAY_API_URL ?? "http://127.0.0.1:8000";
const API_TOKEN = process.env.RAY_API_TOKEN ?? "";

async function proxy(request: NextRequest, path: string[] | undefined): Promise<Response> {
  const suffix = path === undefined ? "" : `/${path.join("/")}`;
  const url = `${API_URL}/memory${suffix}${new URL(request.url).search}`;
  const body = request.method === "GET" || request.method === "DELETE" ? undefined : await request.text();

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: request.method,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${API_TOKEN}` },
      body,
      cache: "no-store",
    });
  } catch {
    return Response.json({ detail: "Ray's backend is not reachable." }, { status: 502 });
  }

  // 204 has no body, and constructing a Response with one for it throws.
  if (upstream.status === 204) return new Response(null, { status: 204 });

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}

type Context = { params: Promise<{ path?: string[] }> };

export async function GET(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}

export async function POST(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}

export async function PATCH(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}

export async function PUT(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}

export async function DELETE(request: NextRequest, { params }: Context) {
  return proxy(request, (await params).path);
}
