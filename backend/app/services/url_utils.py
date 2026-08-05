from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "music.youtube.com",
}

FACEBOOK_HOSTS = {
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "fb.watch",
    "www.fb.watch",
    "web.facebook.com",
}

INSTAGRAM_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
}

# Typical YouTube video id length
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _host(url: str) -> str:
    try:
        return (urlparse(url.strip()).hostname or "").lower()
    except Exception:
        return ""


def detect_platform(url: str) -> str | None:
    host = _host(url)
    if host in YOUTUBE_HOSTS:
        return "youtube"
    if host in FACEBOOK_HOSTS or host.endswith(".facebook.com"):
        return "facebook"
    if host in INSTAGRAM_HOSTS or host.endswith(".instagram.com"):
        return "instagram"
    return None


def extract_video_id(url: str) -> str | None:
    trimmed = url.strip()
    try:
        parsed = urlparse(trimmed)
        host = (parsed.hostname or "").lower()
        if host not in YOUTUBE_HOSTS:
            return None
        if "youtu.be" in host:
            candidate = (parsed.path or "").strip("/").split("/")[0]
            return candidate if _VIDEO_ID_RE.match(candidate) else None

        path = parsed.path or ""
        for prefix in ("/shorts/", "/embed/", "/live/", "/v/"):
            if path.startswith(prefix):
                candidate = path[len(prefix) :].split("/")[0]
                return candidate if _VIDEO_ID_RE.match(candidate) else None

        query = parse_qs(parsed.query)
        if query.get("v"):
            candidate = query["v"][0]
            return candidate if _VIDEO_ID_RE.match(candidate) else None
        return None
    except Exception:
        return None


def canonicalize_youtube_url(url: str) -> str | None:
    """
    Strip Mix/playlist/radio params and normalize to a single-video watch URL.
    Example: watch?v=ID&list=RD…&start_radio=1 → watch?v=ID
    """
    vid = extract_video_id(url)
    if not vid:
        return None
    return f"https://www.youtube.com/watch?v={vid}"


def _is_facebook_url(url: str) -> bool:
    host = _host(url)
    if host not in FACEBOOK_HOSTS and not host.endswith(".facebook.com"):
        return False
    parsed = urlparse(url.strip())
    path = (parsed.path or "").lower()
    query = parse_qs(parsed.query)
    if host in {"fb.watch", "www.fb.watch"}:
        return bool((parsed.path or "").strip("/"))
    if "/watch" in path or "/reel/" in path or "/videos/" in path or "/share/" in path:
        return True
    if query.get("v") or query.get("story_fbid"):
        return True
    return False


def _is_instagram_url(url: str) -> bool:
    host = _host(url)
    if host not in INSTAGRAM_HOSTS and not host.endswith(".instagram.com"):
        return False
    path = (urlparse(url.strip()).path or "").lower()
    return any(p in path for p in ("/reel/", "/p/", "/tv/", "/reels/"))


def canonicalize_media_url(url: str) -> str | None:
    """Normalize supported media URLs (YouTube / Facebook / Instagram)."""
    cleaned = url.strip()
    if not cleaned:
        return None
    platform = detect_platform(cleaned)
    if platform == "youtube":
        return canonicalize_youtube_url(cleaned)
    if platform == "facebook" and _is_facebook_url(cleaned):
        parsed = urlparse(cleaned)
        # Keep path+query; drop fragments
        return parsed._replace(fragment="").geturl()
    if platform == "instagram" and _is_instagram_url(cleaned):
        parsed = urlparse(cleaned)
        # Drop tracking query when possible but keep shortcode path
        path = parsed.path or ""
        return f"https://www.instagram.com{path.split('?')[0]}"
    return None


def is_valid_youtube_url(url: str) -> bool:
    return extract_video_id(url) is not None


def is_valid_media_url(url: str) -> bool:
    return canonicalize_media_url(url) is not None


def looks_like_playlist(url: str) -> bool:
    """True for YouTube playlist hub pages without a specific video id."""
    if detect_platform(url) != "youtube":
        return False
    if extract_video_id(url):
        return False
    parsed = urlparse(url.strip())
    path = parsed.path or ""
    return path.startswith("/playlist") or (
        "list=" in (parsed.query or "") and "/watch" not in path
    )


def strip_ansi(text: str) -> str:
    # Full CSI sequences + leftover bare codes like [0;31m from some terminals
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    text = re.sub(r"\[[0-9;]*m", "", text)
    return text.strip()
