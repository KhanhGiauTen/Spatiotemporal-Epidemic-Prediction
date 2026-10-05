import snapshot from "../../../data/public-demo.json";
import { predictDemo, validInput } from "../prediction";

type Context = { params: Promise<{ path: string[] }> };

export async function GET(_request: Request, context: Context) {
  const { path } = await context.params;
  if (path.length !== 1) return Response.json({ error: "Not found" }, { status: 404 });
  const key = path[0];
  if (key === "top-risk-nodes") return Response.json({ nodes: [], note: "Individual-level records are excluded from this public demo." });
  if (!Object.prototype.hasOwnProperty.call(snapshot, key)) return Response.json({ error: "Not found" }, { status: 404 });
  return Response.json(snapshot[key as keyof typeof snapshot], { headers: { "Cache-Control": "public, max-age=3600" } });
}

export async function POST(request: Request, context: Context) {
  const { path } = await context.params;
  if (path.length !== 1 || path[0] !== "predict") return Response.json({ error: "Not found" }, { status: 404 });
  if (Number(request.headers.get("content-length")) > 4096) return Response.json({ error: "Request too large" }, { status: 413 });
  try {
    const body = await request.text();
    if (body.length > 4096) return Response.json({ error: "Request too large" }, { status: 413 });
    const input: unknown = JSON.parse(body);
    if (!validInput(input)) return Response.json({ error: "Invalid exposure factors" }, { status: 422 });
    return Response.json(predictDemo(input), { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }
}
