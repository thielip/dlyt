"use client";

import dynamic from "next/dynamic";
import { useId, useState } from "react";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ThemeToggle } from "@/components/ThemeToggle";
import { DownloaderSkeleton } from "@/components/DownloaderSkeleton";
import { isValidMediaUrl } from "@/lib/validate-url";

const Downloader = dynamic(
  () =>
    import("@/components/Downloader").then((m) => ({ default: m.Downloader })),
  {
    ssr: false,
    loading: () => <DownloaderSkeleton />,
  },
);

export function DownloaderLazy() {
  return (
    <ThemeProvider>
      <DownloaderLazyInner />
    </ThemeProvider>
  );
}

function DownloaderLazyInner() {
  const inputId = useId();
  const [started, setStarted] = useState(false);
  const [draftUrl, setDraftUrl] = useState("");
  const [bootError, setBootError] = useState<string | null>(null);

  if (started) {
    return <Downloader initialUrl={draftUrl} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--muted)]">
          Archive tool
        </p>
        <ThemeToggle />
      </div>
      <section className="hairline-panel border border-[var(--border)] p-6 sm:p-8">
        <form
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            const next = draftUrl.trim();
            if (!isValidMediaUrl(next)) {
              setBootError("請輸入有效的 YouTube／Facebook／Instagram 影片網址");
              return;
            }
            setBootError(null);
            setStarted(true);
          }}
        >
          <label
            htmlFor={inputId}
            className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--muted)]"
          >
            Media URL
          </label>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-stretch">
            <input
              id={inputId}
              type="url"
              value={draftUrl}
              onChange={(e) => setDraftUrl(e.target.value)}
              placeholder="貼上 YT／FB／IG 影片網址…"
              className="min-h-12 flex-1 border border-[var(--border)] bg-transparent px-4 text-[15px] text-[var(--ink)] outline-none placeholder:text-[var(--muted)] focus:border-[var(--ink)]"
              autoComplete="off"
              spellCheck={false}
            />
            <button
              type="submit"
              className="btn-float inline-flex min-h-12 items-center justify-center px-8 text-[13px] uppercase tracking-[0.14em]"
            >
              解析
            </button>
          </div>
          {bootError && (
            <p className="text-sm text-[var(--warn)]" role="alert">
              {bootError}
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
