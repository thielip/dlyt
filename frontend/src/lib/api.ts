import type {
  ContainerFormat,
  CreateDownloadRequest,
  CreateDownloadResponse,
  TaskProgress,
  VideoInfo,
} from "./types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

const infoCache = new Map<string, { expires: number; data: VideoInfo }>();
const INFO_TTL_MS = 5 * 60 * 1000;

export function apiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${normalized}`;
}

async function parseJson<T>(res: Response): Promise<T> {
  const data = (await res.json()) as T & { detail?: string; error?: string };
  if (!res.ok) {
    const message =
      (data as { detail?: string }).detail ||
      (data as { error?: string }).error ||
      "Request failed";
    const retryAfter = res.headers.get("Retry-After");
    if (res.status === 429 && retryAfter) {
      throw new Error(`${message}（Retry-After: ${retryAfter}s）`);
    }
    throw new Error(message);
  }
  return data;
}

function infoCacheKey(url: string, container: ContainerFormat): string {
  return `v3|${url.trim()}|${container}`;
}

export async function fetchVideoInfo(
  url: string,
  preferredContainer: ContainerFormat = "webm",
): Promise<VideoInfo> {
  const key = infoCacheKey(url, preferredContainer);
  const hit = infoCache.get(key);
  if (hit && hit.expires > Date.now()) {
    return hit.data;
  }

  const res = await fetch(apiUrl("/api/info"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: url.trim(),
      preferredContainer,
    }),
  });
  const data = await parseJson<VideoInfo>(res);
  infoCache.set(key, { expires: Date.now() + INFO_TTL_MS, data });
  return data;
}

export async function createDownload(
  payload: CreateDownloadRequest,
): Promise<CreateDownloadResponse> {
  const res = await fetch(apiUrl("/api/download"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson<CreateDownloadResponse>(res);
}

export async function getTaskProgress(taskId: string): Promise<TaskProgress> {
  const res = await fetch(apiUrl(`/api/tasks/${taskId}`), { cache: "no-store" });
  const task = await parseJson<TaskProgress>(res);
  if (task.downloadUrl) {
    task.downloadUrl = apiUrl(task.downloadUrl);
  }
  return task;
}

export interface HealthInfo {
  status: string;
  outboundUsedBytes?: number;
  outboundLimitBytes?: number;
  egressExhausted?: boolean;
  maintenance?: boolean;
}

export async function fetchHealth(): Promise<HealthInfo> {
  // Always same-origin to avoid CORS console noise in PSI / Best Practices
  const res = await fetch("/api/health", { cache: "no-store" });
  return parseJson<HealthInfo>(res);
}

export interface SiteStats {
  onlineNow: number;
  pageViewsTotal: number;
}

export async function postPresence(
  visitorId: string,
  pageHit: boolean,
): Promise<SiteStats> {
  const res = await fetch("/api/presence", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visitorId, pageHit }),
    cache: "no-store",
  });
  return parseJson<SiteStats>(res);
}

export async function fetchSiteStats(): Promise<SiteStats> {
  const res = await fetch("/api/stats", { cache: "no-store" });
  return parseJson<SiteStats>(res);
}

/** Prefer 360p 直連 (progressive) when available. */
export function pickDefaultFormatId(formats: VideoInfo["formats"]): string {
  if (!formats.length) return "";
  const progressive = formats.filter((f) => f.hasVideo && f.progressive);
  const by360 =
    progressive.find(
      (f) => f.label.includes("360") || f.resolution.includes("360"),
    ) ||
    formats.find(
      (f) => f.hasVideo && (f.label.includes("360") || f.resolution.includes("360")),
    );
  if (by360) return by360.formatId;
  if (progressive.length) return progressive[0].formatId;
  const videos = formats.filter((f) => f.hasVideo);
  if (!videos.length) return formats[0].formatId;
  return videos[0].formatId;
}
