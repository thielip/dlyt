import { NextResponse } from "next/server";

const base = () =>
  (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

type Stats = {
  onlineNow: number;
  pageViewsTotal: number;
};

type LocalStore = {
  online: Map<string, number>;
  total: number;
};

declare global {
  var __zenithPresence: LocalStore | undefined;
}

function localStore(): LocalStore {
  if (!globalThis.__zenithPresence) {
    globalThis.__zenithPresence = {
      online: new Map(),
      total: 0,
    };
  }
  return globalThis.__zenithPresence;
}

function pruneOnline(store: LocalStore, now: number) {
  for (const [id, seen] of store.online) {
    if (now - seen > 50_000) store.online.delete(id);
  }
}

function localHeartbeat(visitorId: string, pageHit: boolean): Stats {
  const store = localStore();
  const now = Date.now();
  store.online.set(visitorId, now);
  pruneOnline(store, now);
  if (pageHit) {
    store.total += 1;
  }
  return {
    onlineNow: store.online.size,
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
      return NextResponse.json({
        onlineNow: data.onlineNow,
        pageViewsTotal: data.pageViewsTotal,
      });
    }
    return NextResponse.json(localHeartbeat(visitorId, pageHit));
  } catch {
    return NextResponse.json(localHeartbeat(visitorId, pageHit));
  }
}
