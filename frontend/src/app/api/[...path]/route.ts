import { NextRequest } from "next/server";

const API_URL = process.env.RAY_API_URL ?? "http://127.0.0.1:8000";
const API_TOKEN = process.env.RAY_API_TOKEN ?? "";

async function proxy(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const backendPath = `/${path.join("/")}`;
  const search = new URL(request.url).search;
  const url = `${API_URL}${backendPath}${search}`;

  const headers: HeadersInit = { Authorization: `Bearer ${API_TOKEN}` };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;

  let body: BodyInit | undefined;
  if (request.method !== "GET" && request.method !== "DELETE" && request.method !== "HEAD") {
    body = await request.text();
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      // @ts-expect-error Node's fetch needs this for streaming bodies.
      duplex: "half",
    });
  } catch {
    return Response.json({ detail: "Ray's backend is not reachable." }, { status: 502 });
  }

  const responseType = upstream.headers.get("content-type") ?? "application/json";
  const responseBody = responseType.startsWith("text/event-stream")
    ? upstream.body
    : await upstream.text();

  return new Response(responseBody, {
    status: upstream.status,
    headers: { "Content-Type": responseType },
  });
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, context);
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, context);
}
