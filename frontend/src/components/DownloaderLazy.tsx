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
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <ThemeToggle />
      </div>
      <section className="panel-glass rainbow-border rounded-2xl border border-[var(--border)] p-5 sm:p-7">
        <form
          className="flex flex-col gap-4"
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
            className="text-sm font-semibold text-[var(--ink-soft)]"
          >
            YouTube／Facebook／Instagram 網址
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id={inputId}
              type="url"
              value={draftUrl}
              onChange={(e) => setDraftUrl(e.target.value)}
              placeholder="貼上 YT／FB／IG 影片網址…"
              className="min-h-12 flex-1 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 text-[15px] text-[var(--ink)] outline-none placeholder:text-[var(--muted)] focus:border-[var(--accent)] focus:shadow-[0_0_0_4px_var(--ring)]"
              autoComplete="off"
              spellCheck={false}
            />
            <button
              type="submit"
              className="btn-float inline-flex min-h-12 items-center justify-center rounded-xl px-6 text-[15px]"
            >
              解析影片
            </button>
          </div>
          {bootError && (
            <p className="text-sm text-[var(--accent)]" role="alert">
              {bootError}
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
