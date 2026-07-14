import { NextRequest, NextResponse } from "next/server";

const backendBaseUrl = (
  process.env.BACKEND_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000/api/v1"
).replace(/\/$/, "");

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

async function proxyRequest(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const targetUrl = `${backendBaseUrl}/${path
    .map((segment) => encodeURIComponent(segment))
    .join("/")}${request.nextUrl.search}`;
  const headers = new Headers(request.headers);

  headers.delete("content-length");
  headers.delete("host");

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  let response: Response;
  try {
    response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "backend_unavailable",
          message: "The backend service is unavailable. Please try again.",
        },
      },
      { status: 503 },
    );
  }

  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");

  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxyRequest;
export const HEAD = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
