"use client";

import { useEffect, useRef } from "react";
import type { TaskProgress } from "@/lib/types";

interface ProgressPanelProps {
  task: TaskProgress;
  onReset: () => void;
}

function triggerBrowserDownload(task: TaskProgress) {
  if (!task.downloadUrl) return;
  const isDirect = task.delivery === "redirect";
  const a = document.createElement("a");
  a.href = task.downloadUrl;
  a.rel = "noopener noreferrer";
  if (isDirect) {
    a.target = "_blank";
  } else {
    a.download = task.filename || "download";
  }
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function ProgressPanel({ task, onReset }: ProgressPanelProps) {
  const done = task.status === "completed";
  const failed = task.status === "failed";
  const isDirect = task.delivery === "redirect";
  const processing = !done && !failed;
  const isAsrWait =
    processing &&
    (task.message.includes("Gemini") ||
      task.message.includes("辨識") ||
      task.message.includes("已等待"));

  const autoStarted = useRef<string | null>(null);

  useEffect(() => {
    if (!done || !task.downloadUrl) return;
    if (autoStarted.current === task.taskId) return;
    autoStarted.current = task.taskId;
    // Let the success UI paint, then start download without a second click
    const downloadUrl = task.downloadUrl;
    const delivery = task.delivery;
    const filename = task.filename;
    const t = window.setTimeout(
      () =>
        triggerBrowserDownload({
          ...task,
          downloadUrl,
          delivery,
          filename,
        }),
      250,
    );
    return () => window.clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- download trigger keyed by taskId + URL fields
  }, [done, task.taskId, task.downloadUrl, task.delivery, task.filename]);

  return (
    <div
      className={`border px-4 py-4 sm:px-5 ${
        done
          ? "border-[var(--success)] bg-[var(--success-soft)]"
          : failed
            ? "border-[var(--border-strong)] bg-[var(--accent-soft)]"
            : "border-[var(--border)] bg-transparent"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--ink)]">
            {done ? "下載完成" : failed ? "下載失敗" : "處理中"}
            {processing && (
              <span
                className="spinner inline-block h-3.5 w-3.5 shrink-0 rounded-full border-2 border-[var(--muted)] border-t-[var(--ink)]"
                aria-hidden
              />
            )}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-[var(--ink-soft)]">
            {task.message}
          </p>
          {done && (
            <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
              已自動開始下載；若瀏覽器沒有跳出，請點下方按鈕重試。
            </p>
          )}
          {isAsrWait && (
            <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
              語音辨識在雲端執行，進度條會緩慢前進；畫面沒有卡住，請稍候。
            </p>
          )}
          {done && isDirect && (
            <p className="mt-2 text-xs text-[var(--muted)]">
              直連模式：檔案由 YouTube CDN 傳送到你的裝置，不經過本站頻寬。
            </p>
          )}
        </div>
        <span className="font-mono text-sm tabular-nums text-[var(--muted)]">
          {Math.round(task.progress)}%
        </span>
      </div>

      <div
        className="mt-3 h-[2px] overflow-hidden"
        style={{ background: "var(--track)" }}
      >
        <div
          className={`h-full transition-[width] duration-500 ease-out ${
            done
              ? "bg-[var(--success)]"
              : failed
                ? "bg-[var(--accent)]"
                : "progress-rainbow"
          } ${processing ? "progress-pulse" : ""}`}
          style={{ width: `${Math.max(4, Math.min(100, task.progress))}%` }}
        />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {done && task.downloadUrl && (
          <button
            type="button"
            onClick={() => triggerBrowserDownload(task)}
            className="btn-float inline-flex min-h-10 items-center justify-center px-4 text-sm"
          >
            {isDirect ? "再次開啟直連下載" : "再次下載檔案"}
            {task.filename ? ` · ${task.filename}` : ""}
          </button>
        )}
        {(done || failed) && (
          <button
            type="button"
            onClick={onReset}
            className="inline-flex min-h-10 items-center justify-center border border-[var(--border-strong)] bg-transparent px-4 text-sm font-medium text-[var(--ink)] transition-colors hover:bg-[var(--accent-soft)]"
          >
            再選一次
          </button>
        )}
      </div>
    </div>
  );
}
