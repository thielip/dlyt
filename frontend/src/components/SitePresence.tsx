"use client";

import { useEffect, useState } from "react";
import { postPresence, type SiteStats } from "@/lib/api";
import { useAnalyticsConsent } from "@/components/CookieConsent";

const VISITOR_KEY = "zenith.visitorId";
/** Prevent React Strict Mode double-mount from counting twice within 2s. */
const PAGE_HIT_LOCK = "zenith.pageHitLock";
const HEARTBEAT_MS = 25_000;
const STRICT_MODE_GUARD_MS = 2000;

function ensureVisitorId(): string {
  try {
    const existing = localStorage.getItem(VISITOR_KEY);
    if (existing && existing.length >= 8) return existing;
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID().replace(/-/g, "")
        : `v${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(VISITOR_KEY, id);
    return id;
  } catch {
    return `tmp${Date.now().toString(36)}`;
  }
}

function clearVisitorId(): void {
  try {
    localStorage.removeItem(VISITOR_KEY);
  } catch {
    /* ignore */
  }
}

/** True once per page load; blocks Strict Mode double-fire within 2s. */
function shouldSendPageHit(visitorId: string): boolean {
  try {
    const raw = sessionStorage.getItem(PAGE_HIT_LOCK);
    if (raw) {
      const [vid, ts] = raw.split("|");
      if (vid === visitorId && Date.now() - Number(ts) < STRICT_MODE_GUARD_MS) {
        return false;
      }
    }
    return true;
  } catch {
    return true;
  }
}

function markPageHitSent(visitorId: string): void {
  try {
    sessionStorage.setItem(PAGE_HIT_LOCK, `${visitorId}|${Date.now()}`);
  } catch {
    /* ignore */
  }
}

function formatCount(n: number): string {
  return new Intl.NumberFormat("zh-TW").format(Math.max(0, n));
}

export function SitePresence() {
  const allowed = useAnalyticsConsent();
  const [stats, setStats] = useState<SiteStats | null>(null);

  useEffect(() => {
    if (!allowed) {
      clearVisitorId();
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const visitorId = ensureVisitorId();
    let pageHitPending = shouldSendPageHit(visitorId);

    const tick = async () => {
      try {
        const pageHit = pageHitPending;
        const next = await postPresence(visitorId, pageHit);
        if (pageHit) {
          markPageHitSent(visitorId);
          pageHitPending = false;
        }
        if (!cancelled) setStats(next);
      } catch {
        /* retry later */
      }
      if (!cancelled) {
        timer = setTimeout(tick, HEARTBEAT_MS);
      }
    };

    timer = setTimeout(() => {
      void tick();
    }, 200);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [allowed]);

  if (!allowed) {
    return (
      <p className="mt-8 text-sm tracking-wide text-[var(--muted)]">
        瀏覽統計需同意 Cookie／本機儲存後才會啟用。您可於頁面下方橫幅選擇「全部允許」。
      </p>
    );
  }

  return (
    <div
      className="mt-8 flex flex-wrap items-baseline gap-x-8 gap-y-2 text-sm tracking-wide text-[var(--ink-soft)]"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="inline-flex items-center gap-2.5">
        <span
          className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--success)]"
          aria-hidden
        />
        即時線上{" "}
        <strong className="font-medium tabular-nums text-[var(--ink)]">
          {stats ? formatCount(stats.onlineNow) : "—"}
        </strong>
      </span>
      <span className="text-[var(--border-strong)]" aria-hidden>
        /
      </span>
      <span>
        累計瀏覽{" "}
        <strong className="font-medium tabular-nums text-[var(--ink)]">
          {stats ? formatCount(stats.pageViewsTotal) : "—"}
        </strong>
      </span>
    </div>
  );
}
