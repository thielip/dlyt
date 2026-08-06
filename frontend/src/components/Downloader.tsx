"use client";

import dynamic from "next/dynamic";
import { useEffect, useId, useState } from "react";
import type {
  AsrLanguage,
  ContainerFormat,
  DownloadMode,
  SubtitleFormat,
  TaskProgress,
  VideoInfo,
} from "@/lib/types";
import {
  isValidMediaUrl,
  canonicalizeMediaUrl,
  formatBytes,
} from "@/lib/validate-url";
import {
  fetchVideoInfo,
  createDownload,
  getTaskProgress,
  pickDefaultFormatId,
  fetchHealth,
} from "@/lib/api";
import { ModeSwitch } from "./ModeSwitch";
import { ThemeToggle } from "./ThemeToggle";

const VideoPreview = dynamic(
  () =>
    import("./VideoPreview").then((m) => ({ default: m.VideoPreview })),
  {
    ssr: false,
    loading: () => (
      <div className="slot-preview bg-[var(--track)]" aria-hidden />
    ),
  },
);

const FormatPicker = dynamic(
  () =>
    import("./FormatPicker").then((m) => ({ default: m.FormatPicker })),
  {
    ssr: false,
    loading: () => (
      <div className="min-h-[8rem] bg-[var(--track)]" aria-hidden />
    ),
  },
);

const SubtitlePicker = dynamic(
  () =>
    import("./SubtitlePicker").then((m) => ({ default: m.SubtitlePicker })),
  {
    ssr: false,
    loading: () => (
      <div className="min-h-[8rem] bg-[var(--track)]" aria-hidden />
    ),
  },
);

const ProgressPanel = dynamic(
  () =>
    import("./ProgressPanel").then((m) => ({ default: m.ProgressPanel })),
  {
    ssr: false,
    loading: () => (
      <div className="slot-progress bg-[var(--track)]" aria-hidden />
    ),
  },
);

const TrafficExhaustedModal = dynamic(
  () =>
    import("./TrafficExhaustedModal").then((m) => ({
      default: m.TrafficExhaustedModal,
    })),
  { ssr: false },
);

type Phase = "idle" | "loading-info" | "ready" | "downloading" | "done" | "error";

const GEMINI_KEY_SESSION = "dlyt.geminiApiKey";

function scheduleIdle(fn: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const ric = window.requestIdleCallback?.bind(window);
  if (ric) {
    const id = ric(() => fn(), { timeout: 4000 });
    return () => window.cancelIdleCallback?.(id);
  }
  const t = window.setTimeout(fn, 2000);
  return () => window.clearTimeout(t);
}

export function Downloader({ initialUrl = "" }: { initialUrl?: string }) {
  const inputId = useId();
  const statusId = useId();
  const hintId = useId();
  const [url, setUrl] = useState(initialUrl);
  const [mode, setMode] = useState<Exclude<DownloadMode, "asr">>("video");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<VideoInfo | null>(null);
  const [formatId, setFormatId] = useState<string>("");
  const [containerFormat, setContainerFormat] = useState<ContainerFormat>("webm");
  const [subtitleLanguage, setSubtitleLanguage] = useState("");
  const [subtitleFormat, setSubtitleFormat] = useState<SubtitleFormat>("srt");
  const [geminiApiKey, setGeminiApiKey] = useState(() => {
    if (typeof window === "undefined") return "";
    try {
      return sessionStorage.getItem(GEMINI_KEY_SESSION) ?? "";
    } catch {
      return "";
    }
  });
  const [asrLanguage, setAsrLanguage] = useState<AsrLanguage>("zh");
  const [task, setTask] = useState<TaskProgress | null>(null);
  const [egressExhausted, setEgressExhausted] = useState(false);
  const [egressUsedLabel, setEgressUsedLabel] = useState("");
  const [egressLimitLabel, setEgressLimitLabel] = useState("90 GB");
  const [showEgressModal, setShowEgressModal] = useState(false);

  const urlValid = isValidMediaUrl(url);
  const urlInvalid = url.length > 0 && !urlValid;

  const taskTerminal =
    task?.status === "completed" || task?.status === "failed";

  // Auto-analyze when opened from the lightweight shell with a URL already filled
  useEffect(() => {
    if (!initialUrl || !isValidMediaUrl(initialUrl)) return;
    let cancelled = false;
    (async () => {
      setPhase("loading-info");
      setError(null);
      try {
        const canonical = canonicalizeMediaUrl(initialUrl.trim());
        if (!canonical) {
          if (!cancelled) {
            setPhase("error");
            setError("請輸入有效的 YouTube／Facebook／Instagram 影片網址");
          }
          return;
        }
        if (!cancelled) setUrl(canonical);
        const data = await fetchVideoInfo(canonical, "webm");
        if (cancelled) return;
        setInfo(data);
        setFormatId(pickDefaultFormatId(data.formats));
        setContainerFormat("webm");
        setSubtitleLanguage(data.subtitles[0]?.language ?? "");
        setPhase("ready");
      } catch (err) {
        if (cancelled) return;
        setPhase("error");
        setError(err instanceof Error ? err.message : "無法解析影片資訊");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initialUrl]);

  useEffect(() => {
    let cancelled = false;
    const cancelIdle = scheduleIdle(() => {
      void (async () => {
        try {
          const health = await fetchHealth();
          if (cancelled) return;
          const used = health.outboundUsedBytes ?? 0;
          const limit =
            health.outboundLimitBytes ?? 90 * 1024 * 1024 * 1024;
          setEgressUsedLabel(formatBytes(used));
          setEgressLimitLabel(formatBytes(limit));
          const exhausted =
            Boolean(health.egressExhausted) || used >= limit;
          setEgressExhausted(exhausted);
          if (exhausted) setShowEgressModal(true);
        } catch {
          /* health optional for UI boot */
        }
      })();
    });
    return () => {
      cancelled = true;
      cancelIdle();
    };
  }, []);

  useEffect(() => {
    try {
      if (geminiApiKey) {
        sessionStorage.setItem(GEMINI_KEY_SESSION, geminiApiKey);
      } else {
        sessionStorage.removeItem(GEMINI_KEY_SESSION);
      }
    } catch {
      /* ignore */
    }
  }, [geminiApiKey]);

  useEffect(() => {
    if (!task || taskTerminal) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const started = Date.now();
    const taskId = task.taskId;
    const MAX_POLL_FAILURES = 15;
    let pollFailures = 0;

    const poll = async () => {
      if (cancelled) return;
      let asrBusy = false;
      try {
        const next = await getTaskProgress(taskId);
        if (cancelled) return;
        pollFailures = 0;
        setTask(next);
        asrBusy =
          next.message.includes("Gemini") ||
          next.message.includes("辨識") ||
          next.message.includes("已等待") ||
          next.message.includes("轉成") ||
          next.message.includes("續");
        if (next.status === "completed") {
          setPhase("done");
          return;
        }
        if (next.status === "failed") {
          setPhase("error");
          setError(next.error ?? "下載失敗，請稍後再試");
          return;
        }
      } catch (e) {
        if (cancelled) return;
        pollFailures += 1;
        if (pollFailures >= MAX_POLL_FAILURES) {
          setPhase("error");
          setError(e instanceof Error ? e.message : "無法取得任務狀態");
          return;
        }
        timer = setTimeout(poll, Math.min(8000, 1000 * pollFailures));
        return;
      }

      const elapsed = Date.now() - started;
      const delay = asrBusy
        ? 800
        : elapsed < 5000
          ? 500
          : elapsed < 20000
            ? 1500
            : 3000;
      timer = setTimeout(poll, delay);
    };

    timer = setTimeout(poll, 400);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // Only re-subscribe when the task identity / terminal state changes.
    // Intentionally omit full `task` to avoid restarting the poll loop on every progress tick.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- poll captures taskId; taskTerminal gates exit
  }, [task?.taskId, taskTerminal]);

  async function loadInfo(canonical: string) {
    const data = await fetchVideoInfo(canonical, "webm");
    setInfo(data);
    setFormatId(pickDefaultFormatId(data.formats));
    setContainerFormat("webm");
    setSubtitleLanguage(data.subtitles[0]?.language ?? "");
    return data;
  }

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!urlValid) {
      setError("請輸入有效的 YouTube／Facebook／Instagram 影片網址");
      return;
    }

    setPhase("loading-info");
    setInfo(null);
    setTask(null);

    try {
      const canonical = canonicalizeMediaUrl(url.trim());
      if (!canonical) {
        setPhase("error");
        setError("請輸入有效的 YouTube／Facebook／Instagram 影片網址");
        return;
      }
      setUrl(canonical);
      await loadInfo(canonical);
      setPhase("ready");
    } catch (err) {
      setPhase("error");
      setError(err instanceof Error ? err.message : "無法解析影片資訊");
    }
  }

  function handleFormatChange(nextId: string, meta?: { advanced: boolean }) {
    setFormatId(nextId);
    setContainerFormat(meta?.advanced ? "mp4" : "webm");
  }

  async function handleDownload() {
    if (!info) return;
    setError(null);
    setPhase("downloading");

    const useAsr = mode === "subtitle" && info.subtitles.length === 0;
    const downloadMode: DownloadMode = useAsr ? "asr" : mode;

    try {
      const { taskId } = await createDownload({
        url: url.trim(),
        mode: downloadMode,
        formatId: downloadMode === "video" ? formatId : undefined,
        containerFormat: downloadMode === "video" ? containerFormat : undefined,
        subtitleLanguage:
          downloadMode === "subtitle" ? subtitleLanguage : undefined,
        subtitleFormat:
          downloadMode === "subtitle" || downloadMode === "asr"
            ? subtitleFormat
            : undefined,
        geminiApiKey: downloadMode === "asr" ? geminiApiKey.trim() : undefined,
        asrLanguage: downloadMode === "asr" ? asrLanguage : undefined,
      });

      const initial = await getTaskProgress(taskId);
      setTask(initial);
    } catch (err) {
      setPhase("error");
      setError(err instanceof Error ? err.message : "無法建立下載任務");
    }
  }

  function handleReset() {
    setPhase(info ? "ready" : "idle");
    setTask(null);
    setError(null);
  }

  const asrReady =
    mode === "subtitle" &&
    info &&
    info.subtitles.length === 0 &&
    Boolean(geminiApiKey.trim()) &&
    Boolean(subtitleFormat);

  const subtitleReady =
    mode === "subtitle" &&
    info &&
    info.subtitles.length > 0 &&
    Boolean(subtitleLanguage) &&
    Boolean(subtitleFormat);

  const downloadDisabled =
    (mode === "video" && !formatId) ||
    (mode === "subtitle" && !(asrReady || subtitleReady));

  const showResult =
    (phase === "ready" ||
      phase === "downloading" ||
      phase === "done" ||
      (phase === "error" && info)) &&
    info;

  return (
    <div className="flex flex-col gap-8">
      {showEgressModal && (
        <TrafficExhaustedModal
          open={showEgressModal}
          usedLabel={egressUsedLabel}
          limitLabel={egressLimitLabel}
          onDismiss={() => setShowEgressModal(false)}
        />
      )}

      <div className="flex justify-end">
        <ThemeToggle />
      </div>

      <section
        className="hairline-panel border border-[var(--border)] p-5 sm:p-7"
        aria-busy={phase === "loading-info" || phase === "downloading"}
      >
        {egressExhausted && (
          <button
            type="button"
            onClick={() => setShowEgressModal(true)}
            className="mb-4 w-full border border-[var(--ink)] bg-[var(--accent-soft)] px-4 py-4 text-left"
          >
            <p className="text-lg font-black text-[var(--accent-deep)] sm:text-xl">
              免費流量已使用完畢
            </p>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">
              本月已用 {egressUsedLabel}／上限 {egressLimitLabel}。點此查看說明。
            </p>
          </button>
        )}
        {info?.bandwidthPressure === "soft" && (
          <div className="mb-4 border border-[var(--warn)]/30 bg-[color-mix(in_srgb,var(--warn)_12%,transparent)] px-4 py-3 text-sm text-[var(--ink-soft)]">
            本月伺服器代理流量偏高，已隱藏部分高畫質。請優先選「直連」畫質或字幕。
          </div>
        )}
        {info?.bandwidthPressure === "hard" && (
          <div className="mb-4 border border-[var(--accent)]/35 bg-[var(--accent-soft)] px-4 py-3 text-sm text-[var(--accent-deep)]">
            本月代理流量吃緊：僅保留直連畫質／字幕。若直連失敗，請稍後再試或下個月再下載高畫質。
          </div>
        )}
        <form onSubmit={handleAnalyze} className="flex flex-col gap-4">
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
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="貼上 YT／FB／IG 影片網址…"
              className="min-h-12 flex-1 border border-[var(--border)] bg-transparent px-4 text-[15px] text-[var(--ink)] outline-none transition-[border-color] placeholder:text-[var(--muted)] focus:border-[var(--ink)]"
              autoComplete="off"
              spellCheck={false}
              aria-invalid={urlInvalid}
              aria-describedby={`${hintId}${urlInvalid ? ` ${statusId}` : ""}`}
            />
            <button
              type="submit"
              disabled={phase === "loading-info"}
              className="btn-float inline-flex min-h-12 items-center justify-center px-6 text-[13px] uppercase tracking-[0.12em] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {phase === "loading-info" ? (
                <span className="inline-flex items-center gap-2">
                  <span
                    className="spinner inline-block h-4 w-4 rounded-full border-2 border-[var(--muted)] border-t-[var(--ink)]"
                    aria-hidden
                  />
                  解析中
                </span>
              ) : (
                "解析影片"
              )}
            </button>
          </div>
          <p id={hintId} className="sr-only">
            支援標準 YouTube、youtu.be、Shorts、Facebook 與 Instagram 影片網址
          </p>
          {urlInvalid && (
            <p id={statusId} className="text-sm text-[var(--accent)]" role="status">
              網址格式看起來不正確
            </p>
          )}
        </form>

        {showResult && (
          <div className="mt-7 flex flex-col gap-6 border-t border-[var(--border)] pt-7">
            <VideoPreview info={info} />

            <ModeSwitch
              mode={mode}
              onChange={setMode}
              disabled={phase === "downloading"}
            />

            {mode === "video" ? (
              <FormatPicker
                formats={info.formats}
                advancedFormats={info.advancedFormats ?? []}
                value={formatId}
                onChange={handleFormatChange}
                disabled={phase === "downloading"}
              />
            ) : (
              <SubtitlePicker
                tracks={info.subtitles}
                language={subtitleLanguage}
                format={subtitleFormat}
                onLanguageChange={setSubtitleLanguage}
                onFormatChange={setSubtitleFormat}
                geminiApiKey={geminiApiKey}
                onGeminiApiKeyChange={setGeminiApiKey}
                asrLanguage={asrLanguage}
                onAsrLanguageChange={setAsrLanguage}
                onSwitchToVideo={() => setMode("video")}
                disabled={phase === "downloading"}
              />
            )}

            {phase !== "downloading" && phase !== "done" && (
              <button
                type="button"
                onClick={handleDownload}
                disabled={downloadDisabled}
                className="btn-ink inline-flex min-h-12 w-full items-center justify-center px-6 text-[13px] font-medium uppercase tracking-[0.12em] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto sm:self-start"
              >
                {mode === "video"
                  ? "開始下載影片"
                  : info.subtitles.length === 0
                    ? "產生字幕"
                    : "開始下載字幕"}
              </button>
            )}

            {(phase === "downloading" || phase === "done") && task && (
              <div className="slot-progress" aria-live="polite" aria-atomic="true">
                <ProgressPanel task={task} onReset={handleReset} />
              </div>
            )}
          </div>
        )}

        <div aria-live="assertive" aria-atomic="true">
          {error && (
            <div
              role="alert"
              className="mt-5 border border-[var(--accent)]/35 bg-[var(--accent-soft)] px-4 py-3 text-sm text-[var(--accent-deep)]"
            >
              {error}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
