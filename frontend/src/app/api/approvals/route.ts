const API_URL = process.env.RAY_API_URL ?? "http://127.0.0.1:8000";
const API_TOKEN = process.env.RAY_API_TOKEN ?? "";

export async function GET() {
  const upstream = await fetch(`${API_URL}/approvals`, {
    headers: { Authorization: `Bearer ${API_TOKEN}` },
    cache: "no-store",
  });
  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
