import { NextResponse } from "next/server";

const base = () =>
  (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

type Stats = {
  onlineNow: number;
  pageViewsToday: number;
  pageViewsTotal: number;
};

declare global {
  var __zenithPresence:
    | {
        online: Map<string, number>;
        total: number;
        day: string;
        today: number;
      }
    | undefined;
}

function localSnapshot(): Stats {
  const store = globalThis.__zenithPresence;
  if (!store) {
    return { onlineNow: 0, pageViewsToday: 0, pageViewsTotal: 0 };
  }
  const now = Date.now();
  for (const [id, seen] of store.online) {
    if (now - seen > 50_000) store.online.delete(id);
  }
  const day = new Date().toISOString().slice(0, 10);
  if (store.day !== day) {
    store.day = day;
    store.today = 0;
  }
  return {
    onlineNow: store.online.size,
    pageViewsToday: store.today,
    pageViewsTotal: store.total,
  };
}

export async function GET() {
  const api = base();
  if (!api) {
    return NextResponse.json(localSnapshot());
  }
  try {
    const res = await fetch(`${api}/api/stats`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    const data = (await res.json().catch(() => null)) as Stats | null;
    if (res.ok && data && typeof data.pageViewsTotal === "number") {
      return NextResponse.json(data);
    }
    return NextResponse.json(localSnapshot());
  } catch {
    return NextResponse.json(localSnapshot());
  }
}
