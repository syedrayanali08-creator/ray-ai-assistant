import { NextRequest } from "next/server";

const API_URL = process.env.RAY_API_URL ?? "http://127.0.0.1:8000";
const API_TOKEN = process.env.RAY_API_TOKEN ?? "";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; action: string }> },
) {
  const { id, action } = await params;
  if (!["approve", "reject"].includes(action)) {
    return Response.json({ detail: "Invalid action" }, { status: 400 });
  }

  let payload = {};
  try {
    payload = await request.json();
  } catch {
    // empty body is fine
  }

  const upstream = await fetch(`${API_URL}/approvals/${id}/${action}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_TOKEN}`,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
