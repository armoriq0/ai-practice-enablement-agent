import { NextRequest, NextResponse } from "next/server";
import { GoogleAuth } from "google-auth-library";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function cloudRunIdentityHeader(backendUrl: string): Promise<string | null> {
  // Cloud Run removes X-Serverless-Authorization after validating it, leaving the
  // application's Authorization header untouched for tenant/user authentication.
  if (!process.env.K_SERVICE || !backendUrl.startsWith("https://")) return null;
  const audience = process.env.BACKEND_AUDIENCE || new URL(backendUrl).origin;
  const client = await new GoogleAuth().getIdTokenClient(audience);
  const token = await client.idTokenProvider.fetchIdToken(audience);
  return `Bearer ${token}`;
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const base = (process.env.BACKEND_URL || process.env.API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const { path: segments } = await context.params;
  const path = segments.map(encodeURIComponent).join("/");
  const upstream = new URL(`${base}/${path}`);
  upstream.search = request.nextUrl.search;
  const headers = new Headers();
  ["authorization", "content-type", "x-request-id", "x-organization-id"].forEach((key) => {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  });
  if (!headers.has("authorization") && process.env.INTERNAL_API_TOKEN) {
    headers.set("authorization", `Bearer ${process.env.INTERNAL_API_TOKEN}`);
  }
  try {
    const serverlessAuthorization = await cloudRunIdentityHeader(base);
    if (serverlessAuthorization) headers.set("x-serverless-authorization", serverlessAuthorization);
    const response = await fetch(upstream, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      cache: "no-store",
    });
    return new NextResponse(response.body, { status: response.status, headers: response.headers });
  } catch {
    return NextResponse.json({ detail: "The agent control plane is unavailable." }, { status: 503 });
  }
}

export { forward as GET, forward as POST, forward as PATCH, forward as PUT, forward as DELETE };
