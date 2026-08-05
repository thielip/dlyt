"use client";

import { useEffect, useId, useRef } from "react";

interface TrafficExhaustedModalProps {
  open: boolean;
  usedLabel: string;
  limitLabel: string;
  onDismiss: () => void;
}

export function TrafficExhaustedModal({
  open,
  usedLabel,
  limitLabel,
  onDismiss,
}: TrafficExhaustedModalProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const t = window.setTimeout(() => closeRef.current?.focus(), 0);

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onDismiss();
        return;
      }
      if (e.key !== "Tab" || !closeRef.current) return;
      // Single focusable control — keep focus inside dialog
      e.preventDefault();
      closeRef.current.focus();
    }

    document.addEventListener("keydown", onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      window.clearTimeout(t);
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
      previouslyFocused.current?.focus?.();
    };
  }, [open, onDismiss]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-5"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onDismiss();
      }}
    >
      <div
        className="w-full max-w-xl rounded-3xl border-2 border-[var(--accent)] bg-[var(--surface-solid)] px-6 py-10 text-center shadow-[var(--shadow)] sm:px-10 sm:py-12"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <p className="text-sm font-bold uppercase tracking-[0.2em] text-[var(--accent)]">
          巔峰思維 · 流量告急
        </p>
        <h2
          id={titleId}
          className="mt-4 text-3xl font-black leading-tight tracking-tight text-[var(--ink)] sm:text-5xl"
          style={{ fontFamily: "var(--font-display)" }}
        >
          免費流量已使用完畢
        </h2>
        <p className="mt-5 text-lg font-semibold leading-relaxed text-[var(--ink-soft)] sm:text-2xl">
          本月伺服器代理流量已達上限
          <br />
          <span className="font-mono text-[var(--accent-deep)]">
            {usedLabel} / {limitLabel}
          </span>
        </p>
        <p className="mt-4 text-base leading-relaxed text-[var(--muted)] sm:text-lg">
          目前無法再透過本站代理下載高畫質影片。
          <br />
          請下個月額度重置後再試，或改選標示「直連」的畫質（若仍可用）。
        </p>
        <button
          ref={closeRef}
          type="button"
          onClick={onDismiss}
          className="btn-ink mt-8 inline-flex min-h-14 w-full items-center justify-center rounded-2xl px-6 text-lg font-bold sm:w-auto sm:min-w-[220px]"
        >
          我知道了
        </button>
      </div>
    </div>
  );
}
