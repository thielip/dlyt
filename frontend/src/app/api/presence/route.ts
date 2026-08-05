import { NextResponse } from "next/server";

const base = () =>
  (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

type Stats = {
  onlineNow: number;
  pageViewsToday: number;
  pageViewsTotal: number;
};

type LocalStore = {
  online: Map<string, number>;
  total: number;
  day: string;
  today: number;
};

declare global {
  var __zenithPresence: LocalStore | undefined;
}

function localStore(): LocalStore {
  if (!globalThis.__zenithPresence) {
    globalThis.__zenithPresence = {
      online: new Map(),
      total: 0,
      day: new Date().toISOString().slice(0, 10),
      today: 0,
    };
  }
  return globalThis.__zenithPresence;
}

function localHeartbeat(visitorId: string, pageHit: boolean): Stats {
  const store = localStore();
  const now = Date.now();
  const day = new Date().toISOString().slice(0, 10);
  if (store.day !== day) {
    store.day = day;
    store.today = 0;
  }
  store.online.set(visitorId, now);
  for (const [id, seen] of store.online) {
    if (now - seen > 50_000) store.online.delete(id);
  }
  if (pageHit) {
    store.total += 1;
    store.today += 1;
  }
  return {
    onlineNow: store.online.size,
    pageViewsToday: store.today,
    pageViewsTotal: store.total,
  };
}

export async function POST(request: Request) {
  let visitorId = "";
  let pageHit = false;
  try {
    const body = (await request.json()) as {
      visitorId?: string;
      pageHit?: boolean;
    };
    visitorId = String(body.visitorId ?? "").trim();
    pageHit = Boolean(body.pageHit);
  } catch {
    /* empty body */
  }

  if (visitorId.length < 8) {
    return NextResponse.json({ detail: "缺少 visitorId" }, { status: 400 });
  }

  const api = base();
  if (!api) {
    return NextResponse.json(localHeartbeat(visitorId, pageHit));
  }

  try {
    const res = await fetch(`${api}/api/presence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visitorId, pageHit }),
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    const data = (await res.json().catch(() => null)) as Stats | null;
    if (res.ok && data && typeof data.pageViewsTotal === "number") {
      return NextResponse.json(data);
    }
    // Backend missing/old — fall back so counters still work in local UI
    return NextResponse.json(localHeartbeat(visitorId, pageHit));
  } catch {
    return NextResponse.json(localHeartbeat(visitorId, pageHit));
  }
}
