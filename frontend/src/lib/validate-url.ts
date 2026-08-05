const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "youtu.be",
  "www.youtu.be",
  "music.youtube.com",
]);

const FACEBOOK_HOSTS = new Set([
  "facebook.com",
  "www.facebook.com",
  "m.facebook.com",
  "web.facebook.com",
  "fb.watch",
  "www.fb.watch",
]);

const INSTAGRAM_HOSTS = new Set([
  "instagram.com",
  "www.instagram.com",
  "m.instagram.com",
]);

const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;

export type MediaPlatform = "youtube" | "facebook" | "instagram";

function hostOf(input: string): string | null {
  try {
    const url = new URL(input.trim());
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return url.hostname.toLowerCase();
  } catch {
    return null;
  }
}

export function detectPlatform(input: string): MediaPlatform | null {
  const host = hostOf(input);
  if (!host) return null;
  if (YOUTUBE_HOSTS.has(host)) return "youtube";
  if (FACEBOOK_HOSTS.has(host) || host.endsWith(".facebook.com")) return "facebook";
  if (INSTAGRAM_HOSTS.has(host) || host.endsWith(".instagram.com")) return "instagram";
  return null;
}

export function extractYouTubeVideoId(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  try {
    const url = new URL(trimmed);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    const host = url.hostname.toLowerCase();
    if (!YOUTUBE_HOSTS.has(host)) return null;

    if (host.includes("youtu.be")) {
      const id = url.pathname.replace(/^\//, "").split("/")[0];
      return VIDEO_ID_RE.test(id) ? id : null;
    }

    for (const prefix of ["/shorts/", "/embed/", "/live/", "/v/"]) {
      if (url.pathname.startsWith(prefix)) {
        const id = url.pathname.slice(prefix.length).split("/")[0];
        return VIDEO_ID_RE.test(id) ? id : null;
      }
    }

    const v = url.searchParams.get("v");
    if (v && VIDEO_ID_RE.test(v)) return v;
    return null;
  } catch {
    return null;
  }
}

export function canonicalizeYouTubeUrl(input: string): string | null {
  const id = extractYouTubeVideoId(input);
  if (!id) return null;
  return `https://www.youtube.com/watch?v=${id}`;
}

function isFacebookUrl(input: string): boolean {
  try {
    const url = new URL(input.trim());
    const host = url.hostname.toLowerCase();
    if (!FACEBOOK_HOSTS.has(host) && !host.endsWith(".facebook.com")) return false;
    const path = url.pathname.toLowerCase();
    if (host.includes("fb.watch")) return path.replace(/^\//, "").length > 0;
    if (
      path.includes("/watch") ||
      path.includes("/reel/") ||
      path.includes("/videos/") ||
      path.includes("/share/")
    ) {
      return true;
    }
    return Boolean(url.searchParams.get("v") || url.searchParams.get("story_fbid"));
  } catch {
    return false;
  }
}

function isInstagramUrl(input: string): boolean {
  try {
    const url = new URL(input.trim());
    const host = url.hostname.toLowerCase();
    if (!INSTAGRAM_HOSTS.has(host) && !host.endsWith(".instagram.com")) return false;
    const path = url.pathname.toLowerCase();
    return ["/reel/", "/p/", "/tv/", "/reels/"].some((p) => path.includes(p));
  } catch {
    return false;
  }
}

/** Normalize YouTube / Facebook / Instagram media URLs. */
export function canonicalizeMediaUrl(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  const platform = detectPlatform(trimmed);
  if (platform === "youtube") return canonicalizeYouTubeUrl(trimmed);
  if (platform === "facebook" && isFacebookUrl(trimmed)) {
    try {
      const url = new URL(trimmed);
      url.hash = "";
      return url.toString();
    } catch {
      return null;
    }
  }
  if (platform === "instagram" && isInstagramUrl(trimmed)) {
    try {
      const url = new URL(trimmed);
      const path = url.pathname.endsWith("/") ? url.pathname : `${url.pathname}/`;
      return `https://www.instagram.com${path}`;
    } catch {
      return null;
    }
  }
  return null;
}

export function isValidMediaUrl(input: string): boolean {
  return canonicalizeMediaUrl(input) !== null;
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;

  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}
