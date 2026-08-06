"use client";

import Image from "next/image";
import type { VideoInfo } from "@/lib/types";
import { formatDuration } from "@/lib/validate-url";

interface VideoPreviewProps {
  info: VideoInfo;
}

function isTrustedThumbnail(src: string): boolean {
  try {
    const u = new URL(src);
    return (
      u.protocol === "https:" &&
      (u.hostname.endsWith("ytimg.com") ||
        u.hostname.endsWith("googleusercontent.com") ||
        u.hostname.endsWith("fbcdn.net") ||
        u.hostname.endsWith("cdninstagram.com") ||
        u.hostname.endsWith("instagram.com"))
    );
  } catch {
    return false;
  }
}

export function VideoPreview({ info }: VideoPreviewProps) {
  const views =
    typeof info.viewCount === "number"
      ? new Intl.NumberFormat("zh-TW", { notation: "compact" }).format(
          info.viewCount,
        )
      : null;
  const useOptimized = Boolean(info.thumbnail && isTrustedThumbnail(info.thumbnail));

  return (
    <div className="slot-preview flex flex-col gap-4 sm:flex-row sm:items-start">
      <div className="relative aspect-video w-full overflow-hidden border border-[var(--hairline)] bg-[var(--bg-deep)] sm:w-56 sm:shrink-0">
        {useOptimized ? (
          <Image
            src={info.thumbnail}
            alt=""
            fill
            sizes="(max-width: 640px) 100vw, 224px"
            className="object-cover"
            unoptimized={false}
          />
        ) : info.thumbnail ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={info.thumbnail}
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
            loading="lazy"
            decoding="async"
          />
        ) : (
          <div className="absolute inset-0 bg-[var(--track)]" aria-hidden />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <h2 className="font-[family-name:var(--font-display)] text-xl font-medium leading-snug tracking-tight text-[var(--ink)] sm:text-2xl">
          {info.title}
        </h2>
        <p className="mt-1.5 text-sm text-[var(--ink-soft)]">{info.channel}</p>
        <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--muted)]">
          <div className="inline-flex gap-1.5">
            <dt className="sr-only">時長</dt>
            <dd className="font-mono">{formatDuration(info.duration)}</dd>
          </div>
          {views && (
            <div className="inline-flex gap-1.5">
              <dt className="sr-only">觀看次數</dt>
              <dd>{views} 次觀看</dd>
            </div>
          )}
        </dl>
      </div>
    </div>
  );
}
