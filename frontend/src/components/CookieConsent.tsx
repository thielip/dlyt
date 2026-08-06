"use client";

import { useId, useSyncExternalStore } from "react";
import Link from "next/link";
import {
  analyticsAllowed,
  readConsent,
  writeConsent,
  type ConsentChoice,
} from "@/lib/brand";

function subscribeConsent(onStoreChange: () => void) {
  window.addEventListener("zenith-consent", onStoreChange);
  window.addEventListener("storage", onStoreChange);
  return () => {
    window.removeEventListener("zenith-consent", onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}

/**
 * Cookie / local-storage consent. Analytics (visitor stats) only run after「全部允許」。
 */
export function CookieConsent() {
  const titleId = useId();
  const needsChoice = useSyncExternalStore(
    subscribeConsent,
    () => readConsent() === null,
    () => false,
  );

  function choose(choice: ConsentChoice) {
    writeConsent(choice);
  }

  if (!needsChoice) return null;

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-[90] p-4 sm:p-5"
      role="dialog"
      aria-modal="false"
      aria-labelledby={titleId}
    >
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 border border-[var(--border-strong)] bg-[var(--surface-solid)] p-4 sm:flex-row sm:items-center sm:gap-6 sm:p-5">
        <div className="min-w-0 flex-1 text-sm leading-relaxed text-[var(--ink-soft)]">
          <p id={titleId} className="font-medium tracking-wide text-[var(--ink)]">
            Cookie 與本機儲存說明
          </p>
          <p className="mt-1.5">
            我們使用必要的本機儲存（例如主題偏好）以維持網站運作。若您同意，也會使用匿名訪客識別碼統計瀏覽與線上人數。詳見{" "}
            <Link
              href="/privacy"
              className="font-medium text-[var(--ink)] underline underline-offset-2"
            >
              隱私權政策
            </Link>
            。
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={() => choose("essential")}
            className="inline-flex min-h-11 items-center justify-center border border-[var(--border-strong)] bg-transparent px-4 text-sm font-medium text-[var(--ink)]"
          >
            僅必要功能
          </button>
          <button
            type="button"
            onClick={() => choose("accepted")}
            className="btn-float inline-flex min-h-11 items-center justify-center px-4 text-sm"
          >
            全部允許
          </button>
        </div>
      </div>
    </div>
  );
}

/** Hook helpers for children that depend on consent. */
export function useAnalyticsConsent(): boolean {
  return useSyncExternalStore(
    subscribeConsent,
    () => analyticsAllowed(),
    () => false,
  );
}
