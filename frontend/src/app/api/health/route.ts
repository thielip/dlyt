import { NextResponse } from "next/server";

/**
 * Same-origin health proxy — avoids browser CORS console errors that fail
 * PageSpeed Best Practices when the API is on another origin.
 */
export async function GET() {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
  if (!base) {
    return NextResponse.json({
      status: "ok",
      egressExhausted: false,
      outboundUsedBytes: 0,
      outboundLimitBytes: 90 * 1024 * 1024 * 1024,
    });
  }

  try {
    const res = await fetch(`${base}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.ok ? 200 : 502 });
  } catch {
    return NextResponse.json({
      status: "unreachable",
      egressExhausted: false,
    });
  }
}
