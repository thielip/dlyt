from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import yt_dlp
from fastapi import HTTPException

from app.config import get_settings
from app.schemas import SubtitleTrack, VideoFormat, VideoInfo
from app.services.ttl_cache import get_ttl_cache
from app.services.url_utils import (
    canonicalize_media_url,
    detect_platform,
    looks_like_playlist,
    strip_ansi,
)
from app.services.egress import outbound_pressure

logger = logging.getLogger(__name__)

LANGUAGE_NAMES: dict[str, str] = {
    "zh-TW": "繁體中文",
    "zh-Hant": "繁體中文",
    "zh-Hans": "简体中文",
    "zh-CN": "简体中文",
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
}

# Prefer android_vr+web: VR alone can hit bot-check; web alone often only 360p.
PLAYER_CLIENT_FALLBACKS: list[list[str]] = [
    ["android_vr", "web"],
    ["tv_embedded", "web_embedded"],
    ["web", "mweb"],
    ["android"],
]

# Clients that typically need Node/Deno + EJS to unlock formats
_JS_CLIENTS = frozenset(
    {
        "web",
        "mweb",
        "tv",
        "tv_embedded",
        "web_embedded",
        "web_safari",
        "web_creator",
        "web_music",
    }
)

# Sentinel format id: best audio → ffmpeg → highest-quality MP3 (never 直連).
AUDIO_MP3_FORMAT_ID = "audio-mp3"


def is_audio_mp3_format(format_id: str | None) -> bool:
    fid = (format_id or "").strip()
    return fid == AUDIO_MP3_FORMAT_ID or fid in {"bestaudio", "bestaudio/b"}


PREFERRED_HEIGHTS = (360, 480, 720, 1080)
ADVANCED_MP4_HEIGHTS = (720, 1080, 2160)


def _resolve_ffmpeg_bin() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and Path(path).exists():
            return path
    except Exception:  # noqa: BLE001
        pass
    return None


def _clients_need_js(clients: list[str] | None) -> bool:
    if not clients:
        return True
    return any(c in _JS_CLIENTS for c in clients)


def _base_opts(player_clients: list[str] | None = None, *, platform: str | None = None) -> dict[str, Any]:
    clients = player_clients or PLAYER_CLIENT_FALLBACKS[0]
    settings = get_settings()
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 1,
        # Allow built-in extractors except the catch-all generic (SSRF-ish) one.
        "allowed_extractors": ["default", "-generic"],
    }

    proxy = (settings.ytdlp_proxy or "").strip()
    if proxy:
        opts["proxy"] = proxy
    else:
        # Prefer IPv4 when going direct — some PaaS dual-stack paths are flaky.
        opts["source_address"] = "0.0.0.0"

    # yt-dlp merge requires ffmpeg — pass full binary path (imageio names are not ffmpeg.exe)
    ffmpeg_bin = _resolve_ffmpeg_bin()
    if ffmpeg_bin:
        opts["ffmpeg_location"] = ffmpeg_bin

    # Only load JS/EJS when the chosen clients actually need challenge solving
    if _clients_need_js(clients):
        node = shutil.which("node")
        deno = shutil.which("deno")
        js_runtimes: dict[str, Any] = {}
        if deno:
            js_runtimes["deno"] = {"path": deno}
        if node:
            js_runtimes["node"] = {"path": node}
        if js_runtimes:
            opts["js_runtimes"] = js_runtimes
            opts["remote_components"] = {"ejs:github"}

    if platform in (None, "youtube"):
        yt_args: dict[str, Any] = {"player_client": clients}
        # Skip redundant webpage scrape for native app clients
        if clients and not _clients_need_js(clients):
            yt_args["player_skip"] = ["webpage", "configs"]
        opts["extractor_args"] = {"youtube": yt_args}
    return opts


def validate_url(url: str) -> str:
    cleaned = url.strip()
    if looks_like_playlist(cleaned):
        raise HTTPException(status_code=400, detail="目前不支援播放清單，請貼單一影片網址")
    canonical = canonicalize_media_url(cleaned)
    if not canonical:
        raise HTTPException(
            status_code=400,
            detail="請輸入有效的 YouTube／Facebook／Instagram 影片網址",
        )
    return canonical


def url_cache_key(url: str, preferred_container: str = "webm") -> str:
    raw = f"v3|{url.strip()}|{preferred_container or 'webm'}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def download_dedupe_key(
    *,
    url: str,
    mode: str,
    format_id: str | None,
    subtitle_language: str | None,
    subtitle_format: str | None,
    container_format: str | None = None,
) -> str:
    raw = "|".join(
        [
            url.strip(),
            mode,
            format_id or "",
            subtitle_language or "",
            subtitle_format or "",
            container_format or "",
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"d{digest}"


def _container_rank(fmt: dict[str, Any], preferred: str) -> int:
    """0 = matches preferred container/codecs, 1 = other."""
    ext = (fmt.get("ext") or "").lower()
    vcodec = (fmt.get("vcodec") or "").lower()
    if preferred == "webm":
        if ext == "webm" or any(x in vcodec for x in ("vp9", "vp09", "av01", "av1")):
            return 0
        return 1
    if ext in {"mp4", "m4v"} or any(x in vcodec for x in ("avc", "h264", "hev1", "hvc1")):
        return 0
    return 1


def _pick_thumbnail(info: dict[str, Any]) -> str:
    thumbs = info.get("thumbnails") or []
    if thumbs:
        return thumbs[-1].get("url") or info.get("thumbnail") or ""
    return info.get("thumbnail") or ""


def _format_label(fmt: dict[str, Any]) -> str:
    height = fmt.get("height")
    if height:
        return f"{height}p"
    if fmt.get("acodec") not in (None, "none") and fmt.get("vcodec") in (None, "none"):
        return "僅音訊"
    return fmt.get("format_note") or fmt.get("format_id") or "unknown"


def _is_progressive(fmt: dict[str, Any]) -> bool:
    return fmt.get("vcodec") not in (None, "none") and fmt.get("acodec") not in (None, "none")


def _pick_best_at_height(
    formats: list[dict[str, Any]],
    height: int,
    *,
    prefer_progressive: bool,
    preferred_container: str,
) -> dict[str, Any] | None:
    candidates = [f for f in formats if int(f.get("height") or 0) == height]
    if not candidates:
        return None
    candidates.sort(
        key=lambda f: (
            0 if (prefer_progressive and _is_progressive(f)) else 1,
            # Only prefer progressive when asked; otherwise prefer adaptive (higher quality)
            (0 if _is_progressive(f) else 1) if prefer_progressive else (1 if _is_progressive(f) else 0),
            _container_rank(f, preferred_container),
            -(f.get("tbr") or 0),
        )
    )
    return candidates[0]


def _pick_best_audio(
    formats: list[dict[str, Any]],
    *,
    prefer_exts: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    audio = [
        f
        for f in formats
        if f.get("acodec") not in (None, "none")
        and f.get("vcodec") in (None, "none")
        and f.get("url")
    ]
    if not audio:
        return None
    prefer = {e.lower() for e in prefer_exts}

    def _rank(f: dict[str, Any]) -> tuple[int, float]:
        ext = (f.get("ext") or "").lower()
        return (0 if ext in prefer else 1, -(f.get("abr") or 0))

    audio.sort(key=_rank)
    return audio[0]


def _adaptive_selector(
    video_fmt: dict[str, Any],
    *,
    height: int,
    preferred_container: str,
    audio_id: str | None,
) -> str:
    """Concrete itag+audio first (matches what we listed), then height selectors — never /b."""
    vid = str(video_fmt["format_id"])
    parts: list[str] = []
    if audio_id:
        parts.append(f"{vid}+{audio_id}")
    parts.append(f"{vid}+bestaudio")
    if preferred_container == "webm":
        parts.extend(
            [
                f"bv*[height={height}][ext=webm]+ba[ext=webm]",
                f"bv*[height={height}][ext=webm]+ba",
                f"bv*[height={height}]+ba",
            ]
        )
    else:
        parts.extend(
            [
                f"bv*[height={height}][vcodec^=avc1]+ba[ext=m4a]",
                f"bv*[height={height}][ext=mp4]+ba",
                f"bv*[height={height}]+ba",
            ]
        )
    return "/".join(parts)


def _to_video_format(
    fmt: dict[str, Any],
    *,
    preferred_container: str,
    force_ext: str | None = None,
    label_suffix: str = "",
    enforce_size_cap: bool = True,
    audio_fmt: dict[str, Any] | None = None,
) -> VideoFormat | None:
    settings = get_settings()
    height = int(fmt.get("height") or 0)
    progressive = _is_progressive(fmt)
    raw_id = str(fmt["format_id"])
    audio_id = str(audio_fmt["format_id"]) if audio_fmt else None

    # Prefer exact listed itags so download matches the format list; no silent /b.
    if progressive:
        format_id = raw_id
    else:
        format_id = _adaptive_selector(
            fmt,
            height=height,
            preferred_container=preferred_container,
            audio_id=audio_id,
        )

    vsize = fmt.get("filesize") or fmt.get("filesize_approx") or 0
    asize = 0
    if audio_fmt and not progressive:
        asize = audio_fmt.get("filesize") or audio_fmt.get("filesize_approx") or 0
    filesize = int(vsize) + int(asize) if (vsize or asize) else None
    if (
        enforce_size_cap
        and settings.max_filesize_bytes > 0
        and filesize
        and filesize > settings.max_filesize_bytes
    ):
        return None

    label = _format_label(fmt)
    if label_suffix:
        label = f"{label}{label_suffix}"
    elif progressive:
        label = f"{label} · 直連"

    ext = force_ext or (fmt.get("ext") or preferred_container).lower()
    if not progressive and not force_ext:
        ext = preferred_container

    return VideoFormat(
        formatId=format_id,
        label=label,
        resolution=f"{fmt.get('width') or '?'}x{height}",
        ext=ext,
        filesizeApprox=filesize,
        hasAudio=True,
        hasVideo=True,
        progressive=progressive,
    )


def _collect_formats(
    info: dict[str, Any],
    *,
    preferred_container: str = "webm",
) -> list[VideoFormat]:
    """List 360/480/720/1080 when available; prefer progressive (直連) per height."""
    settings = get_settings()
    pressure = outbound_pressure()
    max_h = settings.max_proxy_height
    preferred = preferred_container if preferred_container in {"webm", "mp4"} else "webm"
    collected: list[VideoFormat] = []
    all_formats = list(info.get("formats") or [])

    raw = [
        f
        for f in all_formats
        if f.get("vcodec") not in (None, "none")
        and f.get("height")
        and f.get("url")
        and int(f.get("height") or 0) <= max_h
    ]
    prefer_audio_exts = ("webm", "opus") if preferred == "webm" else ("m4a", "mp4")
    best_audio = _pick_best_audio(all_formats, prefer_exts=prefer_audio_exts)

    for height in PREFERRED_HEIGHTS:
        if height > max_h:
            continue
        fmt = _pick_best_at_height(
            raw, height, prefer_progressive=True, preferred_container=preferred
        )
        if not fmt:
            continue
        progressive = _is_progressive(fmt)
        if pressure == "soft" and not progressive and height > 480:
            continue
        if pressure == "hard" and not progressive:
            continue
        item = _to_video_format(
            fmt,
            preferred_container=preferred,
            audio_fmt=None if progressive else best_audio,
        )
        if item:
            collected.append(item)

    # YouTube never serves MP3. Always download bestaudio and convert with
    # ffmpeg to highest-quality MP3 (preferredquality=0). Counts as proxy egress.
    abr = best_audio.get("abr") if best_audio else None
    size_hint = None
    if best_audio:
        size_hint = best_audio.get("filesize") or best_audio.get("filesize_approx")
    label = "僅音訊 · MP3 · 最高音質（320kbps）"
    if abr:
        label = f"僅音訊 · MP3 · 最高音質（320kbps，來源約 {int(abr)} kbps）"
    collected.append(
        VideoFormat(
            formatId=AUDIO_MP3_FORMAT_ID,
            label=label,
            resolution="audio",
            ext="mp3",
            filesizeApprox=int(size_hint) if size_hint else None,
            hasAudio=True,
            hasVideo=False,
            progressive=False,
        )
    )

    if not any(f.hasVideo for f in collected):
        collected.insert(
            0,
            VideoFormat(
                formatId="b",
                label="最佳畫質",
                resolution="best",
                ext=preferred,
                filesizeApprox=None,
                hasAudio=True,
                hasVideo=True,
                progressive=False,
            ),
        )
    return collected


def _collect_advanced_mp4_formats(info: dict[str, Any]) -> list[VideoFormat]:
    """Password-gated advanced list: MP4 720 / 1080 / 2160(4K) by source availability."""
    pressure = outbound_pressure()
    if pressure == "hard":
        return []

    raw = [
        f
        for f in info.get("formats") or []
        if f.get("vcodec") not in (None, "none")
        and f.get("height")
        and f.get("url")
    ]
    best_audio = _pick_best_audio(list(info.get("formats") or []), prefer_exts=("m4a", "mp4"))
    audio_id = str(best_audio["format_id"]) if best_audio else None

    collected: list[VideoFormat] = []
    for height in ADVANCED_MP4_HEIGHTS:
        # Prefer AVC (H.264) for reliable MP4 merge; fall back to any 2160/1080/720
        avc = [
            f
            for f in raw
            if int(f.get("height") or 0) == height
            and any(x in (f.get("vcodec") or "").lower() for x in ("avc", "h264"))
        ]
        fmt = None
        if avc:
            avc.sort(key=lambda f: -(f.get("tbr") or 0))
            fmt = avc[0]
        else:
            fmt = _pick_best_at_height(
                raw, height, prefer_progressive=False, preferred_container="mp4"
            )
        if not fmt:
            continue

        format_id = _adaptive_selector(
            fmt,
            height=height,
            preferred_container="mp4",
            audio_id=audio_id,
        )

        vsize = fmt.get("filesize") or fmt.get("filesize_approx") or 0
        asize = 0
        if best_audio:
            asize = best_audio.get("filesize") or best_audio.get("filesize_approx") or 0
        approx = int(vsize) + int(asize) if (vsize or asize) else None

        suffix = " · MP4"
        if height >= 2160:
            suffix = " · MP4 · 4K"

        collected.append(
            VideoFormat(
                formatId=format_id,
                label=f"{height}p{suffix}",
                resolution=f"{fmt.get('width') or '?'}x{height}",
                ext="mp4",
                filesizeApprox=approx,
                hasAudio=True,
                hasVideo=True,
                progressive=False,
            )
        )
    return collected


def _collect_subtitles(info: dict[str, Any]) -> list[SubtitleTrack]:
    tracks: list[SubtitleTrack] = []
    seen: set[str] = set()

    def add(lang: str, auto: bool) -> None:
        lang = (lang or "").strip()
        if not lang or lang == "live_chat" or lang in seen:
            return
        # Skip obscure auto-translate dumps like "aa-en" unless base lang is useful
        base = lang.split("-")[0].lower()
        if auto and "-" in lang and base not in {
            "zh",
            "en",
            "ja",
            "ko",
            "es",
            "fr",
            "de",
            "pt",
            "vi",
            "th",
            "id",
            "ms",
            "hi",
            "ru",
            "it",
            "tr",
            "ar",
        }:
            # Keep zh-Hant / zh-Hans / pt-BR etc.; drop aa-en style noise later via cap
            pass
        seen.add(lang)
        tracks.append(
            SubtitleTrack(
                language=lang,
                languageName=LANGUAGE_NAMES.get(lang, LANGUAGE_NAMES.get(base, lang)),
                isAutoGenerated=auto,
            )
        )

    for lang in (info.get("subtitles") or {}).keys():
        add(lang, False)
    for lang in (info.get("automatic_captions") or {}).keys():
        add(lang, True)

    priority = [
        "zh-TW",
        "zh-Hant",
        "zh-Hans",
        "zh-CN",
        "zh",
        "en",
        "ja",
        "ko",
        "es",
        "fr",
        "de",
        "pt-BR",
        "vi",
        "th",
    ]

    def _rank(t: SubtitleTrack) -> tuple[int, int, str]:
        # Manual tracks first; then priority langs; prefer plain codes over *-en translates
        manual = 0 if not t.isAutoGenerated else 1
        if t.language in priority:
            pri = priority.index(t.language)
        elif t.language.split("-")[0] in {"zh", "en", "ja", "ko"}:
            pri = 20
        else:
            pri = 50
        translate_noise = 1 if re.match(r"^[a-z]{2,3}-en$", t.language) else 0
        return (manual, pri + translate_noise * 40, t.language)

    tracks.sort(key=_rank)
    # Prefer a useful shortlist over 900 auto-translate langs
    useful = [
        t
        for t in tracks
        if (not t.isAutoGenerated)
        or t.language in priority
        or t.language.startswith("zh")
        or t.language.split("-")[0] in {"en", "ja", "ko", "es", "fr", "de", "pt", "vi", "th"}
    ]
    if useful:
        return useful[:24]
    return tracks[:20]


def _client_attempts(platform: str | None) -> list[list[str] | None]:
    """YouTube tries multiple player clients; FB/IG use a single non-YouTube opts pass."""
    if platform == "youtube" or platform is None:
        return list(PLAYER_CLIENT_FALLBACKS)
    return [None]


def _raw_info_cache_key(url: str) -> str:
    return f"info_raw:v2:{hashlib.sha1(url.strip().encode('utf-8')).hexdigest()}"


def _clients_cache_key(url: str) -> str:
    return f"yt_clients:v2:{hashlib.sha1(url.strip().encode('utf-8')).hexdigest()}"


def _sanitize_info_for_cache(info: dict[str, Any]) -> dict[str, Any]:
    """Drop bulky fields we don't need for download reuse; keep formats+urls."""
    drop = {
        "thumbnails",
        "heatmap",
        "automatic_captions",
        "subtitles",
        "requested_subtitles",
        "comments",
    }
    slim = {k: v for k, v in info.items() if k not in drop}
    # Ensure JSON-roundtrip safe for Redis
    try:
        return json.loads(json.dumps(slim, default=str))
    except Exception:  # noqa: BLE001
        return slim


def _store_extract_cache(url: str, info: dict[str, Any], clients: list[str] | None) -> None:
    settings = get_settings()
    cache = get_ttl_cache()
    ttl = settings.info_cache_ttl_seconds
    cache.set_json(_raw_info_cache_key(url), _sanitize_info_for_cache(info), ttl)
    if clients:
        cache.set_json(_clients_cache_key(url), {"clients": clients}, ttl)


def _get_cached_raw_info(url: str) -> dict[str, Any] | None:
    cached = get_ttl_cache().get_json(_raw_info_cache_key(url))
    return cached if isinstance(cached, dict) else None


def _ordered_client_attempts(url: str, platform: str | None) -> list[list[str] | None]:
    attempts = _client_attempts(platform)
    cached = get_ttl_cache().get_json(_clients_cache_key(url))
    if not isinstance(cached, dict):
        return attempts
    preferred = cached.get("clients")
    if not isinstance(preferred, list) or not preferred:
        return attempts
    preferred_list = [str(c) for c in preferred]
    rest = [c for c in attempts if c != preferred_list]
    return [preferred_list, *rest]


def _max_video_height(info: dict[str, Any]) -> int:
    heights: list[int] = []
    for f in info.get("formats") or []:
        if f.get("vcodec") in (None, "none"):
            continue
        h = int(f.get("height") or 0)
        if h:
            heights.append(h)
    return max(heights) if heights else 0


def _subtitle_track_count(info: dict[str, Any]) -> int:
    n = 0
    for bucket in (info.get("subtitles"), info.get("automatic_captions")):
        for lang in (bucket or {}):
            if lang and lang != "live_chat":
                n += 1
    return n


def _merge_caption_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Copy subtitle / auto-caption maps from source into target when richer."""
    for key in ("subtitles", "automatic_captions"):
        src = source.get(key) or {}
        if not isinstance(src, dict) or not src:
            continue
        dst = dict(target.get(key) or {})
        for lang, val in src.items():
            if lang == "live_chat":
                continue
            if lang not in dst or not dst.get(lang):
                dst[lang] = val
        target[key] = dst


def _extract_info_raw(url: str) -> dict[str, Any]:
    platform = detect_platform(url)
    settings = get_settings()
    last_error: Exception | None = None
    best_info: dict[str, Any] | None = None
    best_clients: list[str] | None = None
    best_height = -1
    best_caption_info: dict[str, Any] | None = None
    best_sub_count = 0
    attempts = _ordered_client_attempts(url, platform)
    budget = max(0, settings.extract_budget_seconds)
    started = time.monotonic()

    for idx, clients in enumerate(attempts):
        opts = {
            **_base_opts(clients, platform=platform),
            "skip_download": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                continue
            height = _max_video_height(info)
            sub_count = _subtitle_track_count(info)
            if height > best_height:
                best_info = info
                best_clients = clients if isinstance(clients, list) else None
                best_height = height
            if sub_count > best_sub_count:
                best_caption_info = info
                best_sub_count = sub_count

            is_last = idx >= len(attempts) - 1
            have_hq = height >= 720 or (best_height >= 720)
            have_caps = best_sub_count > 0
            if is_last or (have_hq and have_caps):
                break

            # Each extra client costs ~15-20s behind the WARP SOCKS proxy, so cap the
            # hunt. Missing formats hurt more than missing captions, so HQ gets the
            # longer budget; a video that genuinely has no 720p (old uploads) would
            # otherwise burn every client looking for something that doesn't exist.
            elapsed = time.monotonic() - started
            caption_deadline = budget
            hq_deadline = budget * 2
            if have_hq and not have_caps:
                if budget and elapsed >= caption_deadline:
                    logger.info(
                        "extract budget reached after %.1fs — returning %sp without captions",
                        elapsed,
                        best_height,
                    )
                    break
                logger.info(
                    "yt-dlp client %s has HQ formats but no captions — trying next (%.1fs)",
                    clients,
                    elapsed,
                )
                continue
            if height < 720:
                if budget and elapsed >= hq_deadline and best_height > 0:
                    logger.info(
                        "extract budget reached after %.1fs — best available is %sp",
                        elapsed,
                        best_height,
                    )
                    break
                logger.info(
                    "yt-dlp client %s only up to %sp — trying next for HQ formats (%.1fs)",
                    clients,
                    height,
                    elapsed,
                )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.info("yt-dlp client %s failed: %s", clients, exc)
            continue

    if best_info is None:
        if last_error:
            raise last_error
        raise RuntimeError("無法取得影片資訊")

    if best_caption_info is not None:
        _merge_caption_fields(best_info, best_caption_info)

    _store_extract_cache(url, best_info, best_clients)
    return best_info


def extract_video_info(
    url: str,
    *,
    use_cache: bool = True,
    preferred_container: str = "webm",
) -> VideoInfo:
    cleaned = validate_url(url)
    settings = get_settings()
    preferred = preferred_container if preferred_container in {"webm", "mp4"} else "webm"
    cache = get_ttl_cache()
    key = f"info:v4:{url_cache_key(cleaned, preferred)}"
    fail_key = f"info_fail:v4:{url_cache_key(cleaned, preferred)}"

    if use_cache:
        cached = cache.get_json(key)
        if cached:
            return VideoInfo.model_validate(cached)
        failed = cache.get_json(fail_key)
        if failed and isinstance(failed, dict):
            detail = str(failed.get("detail") or "暫時無法解析此影片")
            raise HTTPException(status_code=int(failed.get("status") or 400), detail=detail)

    try:
        info = _extract_info_raw(cleaned)
    except yt_dlp.utils.DownloadError as exc:
        detail = f"無法解析影片：{strip_ansi(str(exc))}"
        cache.set_json(
            fail_key,
            {"detail": detail, "status": 400},
            settings.fail_cache_ttl_seconds,
        )
        raise HTTPException(status_code=400, detail=detail) from exc
    except Exception as exc:  # noqa: BLE001
        detail = f"解析失敗：{strip_ansi(str(exc))}"
        cache.set_json(
            fail_key,
            {"detail": detail, "status": 500},
            settings.fail_cache_ttl_seconds,
        )
        raise HTTPException(status_code=500, detail=detail) from exc

    if info.get("_type") == "playlist":
        raise HTTPException(status_code=400, detail="目前不支援播放清單，請貼單一影片網址")

    result = VideoInfo(
        id=str(info.get("id") or ""),
        title=str(info.get("title") or "Untitled"),
        channel=str(info.get("channel") or info.get("uploader") or "Unknown"),
        duration=int(info.get("duration") or 0),
        thumbnail=_pick_thumbnail(info),
        viewCount=int(info["view_count"]) if info.get("view_count") is not None else None,
        formats=_collect_formats(info, preferred_container=preferred),
        advancedFormats=_collect_advanced_mp4_formats(info),
        subtitles=_collect_subtitles(info),
        bandwidthPressure=outbound_pressure(),
        preferredContainer="webm" if preferred == "webm" else "mp4",
    )

    # Optional duration guard (disabled when max_duration_seconds <= 0)
    if (
        settings.max_duration_seconds > 0
        and result.duration
        and result.duration > settings.max_duration_seconds
    ):
        minutes = settings.max_duration_seconds // 60
        detail = f"影片時長超過 {minutes} 分鐘，免費方案暫不支援"
        cache.set_json(
            fail_key,
            {"detail": detail, "status": 400},
            settings.fail_cache_ttl_seconds,
        )
        raise HTTPException(status_code=400, detail=detail)

    # Drop formats whose approx size already exceeds cap (when cap enabled)
    if settings.max_filesize_bytes > 0:
        result.formats = [
            f
            for f in result.formats
            if not f.filesizeApprox or f.filesizeApprox <= settings.max_filesize_bytes
        ] or result.formats

    if use_cache:
        cache.set_json(key, result.model_dump(), settings.info_cache_ttl_seconds)
        cache.delete(fail_key)
    return result


def can_try_direct_delivery(mode: str, format_id: str | None) -> bool:
    """True when we can avoid proxying bytes through our server."""
    if mode != "video" or not format_id:
        return False
    if is_audio_mp3_format(format_id):
        return False
    # Merged / multi-format selectors need ffmpeg / local file
    if (
        "+" in format_id
        or "/" in format_id
        or "bv*" in format_id
        or "bestvideo" in format_id
        or format_id in {"bv*+ba/b", "bestvideo+bestaudio", "b"}
    ):
        return False
    return True


def resolve_direct_media_url(url: str, format_id: str) -> tuple[str, str, int | None, str]:
    """
    Resolve a progressive/audio format to a direct media URL (no local download).
    Returns (media_url, ext, filesize, filename_stem).
    Note: googlevideo URLs may be short-lived / IP-sensitive; caller should allow proxy fallback.
    """
    cleaned = validate_url(url)
    platform = detect_platform(cleaned)
    last_error: Exception | None = None
    for clients in _ordered_client_attempts(cleaned, platform):
        opts = {
            **_base_opts(clients, platform=platform),
            "skip_download": True,
            "format": format_id,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(cleaned, download=False)
            if not info:
                continue
            # requested formats after selection
            requested = info.get("requested_formats") or []
            if requested and len(requested) > 1:
                raise ValueError("此格式需要合併，無法直連")
            fmt = (requested[0] if requested else None) or info
            media_url = fmt.get("url") if isinstance(fmt, dict) else None
            if not media_url and isinstance(info, dict):
                media_url = info.get("url")
            if not media_url:
                # search formats list
                for f in info.get("formats") or []:
                    if str(f.get("format_id")) == str(format_id) and f.get("url"):
                        media_url = f["url"]
                        fmt = f
                        break
            if not media_url:
                raise ValueError("找不到直連網址")
            ext = (fmt.get("ext") if isinstance(fmt, dict) else None) or info.get("ext") or "mp4"
            size = None
            if isinstance(fmt, dict):
                size = fmt.get("filesize") or fmt.get("filesize_approx")
            title = str(info.get("title") or "video")
            safe = re.sub(r'[\\/:*?"<>|]+', "_", title)[:80]
            return str(media_url), str(ext), int(size) if size else None, safe
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    raise last_error or RuntimeError("無法解析直連網址")


def download_media(
    *,
    url: str,
    outtmpl: str,
    mode: str,
    format_id: str | None = None,
    subtitle_language: str | None = None,
    subtitle_format: str | None = None,
    container_format: str | None = "webm",
    progress_hook=None,
) -> str:
    """Download video or subtitle via yt-dlp Python API; returns output path."""
    cleaned = validate_url(url)
    settings = get_settings()
    container = container_format if container_format in {"webm", "mp4"} else "webm"
    platform = detect_platform(cleaned)

    if mode == "subtitle":
        if not subtitle_language or not subtitle_format:
            raise ValueError("缺少字幕語言或格式")
        requested = "srt" if subtitle_format == "txt" else subtitle_format
        last_error: Exception | None = None
        for clients in _client_attempts(platform):
            opts: dict[str, Any] = {
                **_base_opts(clients, platform=platform),
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [subtitle_language],
                "subtitlesformat": requested,
                "outtmpl": outtmpl,
            }
            if progress_hook:
                opts["progress_hooks"] = [progress_hook]
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(cleaned, download=True)
                    requested_subs = info.get("requested_subtitles") or {}
                    sub = requested_subs.get(subtitle_language) or next(
                        iter(requested_subs.values()), None
                    )
                    filepath = (sub or {}).get("filepath")
                    if not filepath:
                        from pathlib import Path

                        parent = Path(outtmpl).parent
                        stem = Path(ydl.prepare_filename(info)).stem
                        matches = list(parent.glob(f"{stem}*.{requested}")) + list(
                            parent.glob(f"*.{requested}")
                        )
                        if not matches:
                            raise FileNotFoundError("找不到字幕檔")
                        filepath = str(matches[0])

                    if subtitle_format == "txt":
                        txt_path = re.sub(r"\.(srt|vtt)$", ".txt", filepath, flags=re.I)
                        if txt_path == filepath:
                            txt_path = filepath + ".txt"
                        _subtitle_to_txt(filepath, txt_path)
                        return txt_path
                    return filepath
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
        raise last_error or RuntimeError("字幕下載失敗")

    # video / audio — prefer given format_id (may already be progressive single id)
    wants_mp3 = is_audio_mp3_format(format_id)
    selected = "bestaudio/b" if wants_mp3 else (format_id or "b")

    needs_merge = (
        not wants_mp3
        and (
            "+" in selected
            or "/" in selected
            or selected in {"bv*+ba/b", "bestvideo+bestaudio", "b"}
            or "bv*" in selected
            or "bestvideo" in selected
        )
    )

    def _finish_download(info: dict[str, Any], ydl: yt_dlp.YoutubeDL) -> str:
        if wants_mp3:
            audio_path = _resolve_audio_download_path(info, ydl)
            return str(
                _convert_audio_to_mp3(
                    audio_path,
                    progress_hook=progress_hook,
                )
            )
        path = _resolve_output_path(info, ydl, preferred_ext=container)
        expected_h = _expected_height_from_selector(selected)
        _assert_real_video_file(
            path,
            info=info,
            expect_merge=needs_merge,
            expected_height=expected_h,
        )
        return str(path)

    def _build_opts(clients: list[str] | None) -> dict[str, Any]:
        opts: dict[str, Any] = {
            **_base_opts(clients, platform=platform),
            "format": selected,
            "outtmpl": outtmpl,
            "merge_output_format": container,
        }
        # MP3 is converted by us after download — do NOT use yt-dlp's FFmpegExtractAudio
        # postprocessor (opaque hang at 96% on weak PaaS CPUs / long tracks).
        if wants_mp3:
            opts.pop("merge_output_format", None)
        if settings.max_filesize_bytes > 0:
            opts["max_filesize"] = settings.max_filesize_bytes
        if not needs_merge:
            opts.pop("merge_output_format", None)
        if progress_hook:
            opts["progress_hooks"] = [progress_hook]
        return opts

    last_error: Exception | None = None

    # Skip cached-info for MP3: googlevideo URLs expire quickly (403), and the
    # failure path left the UI stuck at 96% while every client was retried.
    cached_info = None if wants_mp3 else _get_cached_raw_info(cleaned)
    if cached_info and mode == "video":
        clients_first = _ordered_client_attempts(cleaned, platform)[0]
        try:
            with yt_dlp.YoutubeDL(_build_opts(clients_first)) as ydl:
                info = ydl.process_ie_result(copy.deepcopy(cached_info), download=True)
                return _finish_download(info, ydl)
        except Exception as exc:  # noqa: BLE001
            logger.info("cached-info download failed, re-extracting: %s", strip_ansi(str(exc))[:160])
            last_error = exc

    for clients in _ordered_client_attempts(cleaned, platform):
        try:
            with yt_dlp.YoutubeDL(_build_opts(clients)) as ydl:
                info = ydl.extract_info(cleaned, download=True)
                if info:
                    _store_extract_cache(
                        cleaned, info, clients if isinstance(clients, list) else None
                    )
                return _finish_download(info, ydl)
        except Exception as exc:  # noqa: BLE001
            msg = strip_ansi(str(exc))
            low = msg.lower()
            if "ffmpeg is not installed" in low or (
                "ffmpeg" in low and "not installed" in low
            ):
                last_error = RuntimeError(
                    "伺服器無法合併影音（找不到 ffmpeg）。"
                    "請確認已安裝 imageio-ffmpeg，並重新啟動後端。"
                )
            elif "Requested format is not available" in msg:
                last_error = RuntimeError(
                    "找不到你選的畫質串流（YouTube 目前可能未提供可下載的該解析度）。"
                    "請改選列表中其他畫質，或稍後再試——不會再默默改成低畫質小檔。"
                )
            else:
                last_error = Exception(msg) if msg != str(exc) else exc
            # Audio already on disk + convert failed: do not burn every client again
            if wants_mp3 and ("MP3" in msg or "轉檔" in msg):
                break
            continue
    raise last_error or RuntimeError("下載失敗")


def _resolve_audio_download_path(info: dict[str, Any], ydl: Any) -> Path:
    """Locate the downloaded audio track without ffmpeg video probing."""
    audio_exts = {".m4a", ".webm", ".opus", ".ogg", ".mp3", ".aac", ".wav"}

    for key in ("filepath", "_filename"):
        raw = info.get(key)
        if raw:
            p = Path(str(raw))
            if p.exists() and p.stat().st_size > 0:
                return p

    requested = info.get("requested_downloads") or []
    for item in requested:
        if not isinstance(item, dict):
            continue
        raw = item.get("filepath") or item.get("filename")
        if raw:
            p = Path(str(raw))
            if p.exists() and p.stat().st_size > 0:
                return p

    prepared = Path(ydl.prepare_filename(info))
    if prepared.exists() and prepared.stat().st_size > 0:
        return prepared

    parent = prepared.parent
    stem = prepared.stem
    candidates = [
        p
        for p in parent.glob(f"{stem}.*")
        if p.is_file() and p.suffix.lower() in audio_exts and p.stat().st_size > 0
    ]
    if not candidates:
        candidates = [
            p
            for p in parent.iterdir()
            if p.is_file() and p.suffix.lower() in audio_exts and p.stat().st_size > 0
        ]
    if not candidates:
        raise FileNotFoundError("找不到下載的音訊檔")
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def _convert_audio_to_mp3(
    src: Path,
    *,
    progress_hook=None,
) -> Path:
    """Convert any audio container to highest-quality MP3 (320 kbps CBR)."""
    if not src.exists() or src.stat().st_size <= 0:
        raise RuntimeError("音訊檔不存在或為空，無法轉成 MP3")

    if src.suffix.lower() == ".mp3":
        return src

    ffmpeg = _resolve_ffmpeg_bin()
    if not ffmpeg:
        raise RuntimeError(
            "找不到 ffmpeg，無法轉成 MP3。請確認伺服器已安裝 ffmpeg。"
        )

    dest = src.with_suffix(".mp3")
    if progress_hook:
        progress_hook(
            {
                "status": "converting",
                "progress": 97.0,
                "message": "正在轉成最高音質 MP3（320kbps）…",
            }
        )

    # 320k CBR = highest common MP3 bitrate; much more predictable than VBR q=0
    # on Render Free's tiny CPU (which previously looked "stuck" at 96%).
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "320k",
        str(dest),
    ]
    # Allow ~1s encode budget per 40KB of source, floor 90s, cap 20min
    timeout = max(90, min(1200, int(src.stat().st_size / 40_000) + 90))
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            "MP3 轉檔逾時（影片可能太長）。請改試較短的影片，或稍後再試。"
        ) from exc
    except FileNotFoundError as exc:
        raise RuntimeError("找不到 ffmpeg，無法轉成 MP3") from exc

    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size <= 0:
        err = (proc.stderr or b"").decode("utf-8", errors="ignore").strip()[:240]
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"MP3 轉檔失敗：{err or 'ffmpeg error'}")

    try:
        if src.exists() and src.resolve() != dest.resolve():
            src.unlink(missing_ok=True)
    except OSError:
        pass

    if progress_hook:
        progress_hook(
            {
                "status": "converting",
                "progress": 99.0,
                "message": "MP3 轉檔完成，正在準備下載…",
            }
        )
    return dest


def _expected_height_from_selector(format_id: str | None) -> int | None:
    if not format_id:
        return None
    m = re.search(r"height\s*=\s*(\d+)", format_id)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{3,4})p\b", format_id)
    if m:
        return int(m.group(1))
    return None


def _probe_video_height(path: Path) -> int | None:
    ffmpeg = _resolve_ffmpeg_bin()
    if not ffmpeg:
        return None
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path)],
            capture_output=True,
            timeout=30,
            check=False,
        )
        probe = (proc.stderr or b"").decode("utf-8", errors="ignore")
        m = re.search(
            r"Stream\s+#\d+:\d+.*Video:.*?,\s*(\d{2,5})x(\d{2,5})",
            probe,
            flags=re.I | re.S,
        )
        if m:
            return int(m.group(2))
    except Exception:  # noqa: BLE001
        return None
    return None


def _file_has_video_stream(path: Path) -> bool | None:
    """Return True/False if detectable; None if ffprobe unavailable."""
    ffmpeg = _resolve_ffmpeg_bin()
    if not ffmpeg:
        return None
    # imageio ships ffmpeg; use ffmpeg -i and parse stderr (no separate ffprobe needed)
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path)],
            capture_output=True,
            timeout=30,
            check=False,
        )
        probe = (proc.stderr or b"").decode("utf-8", errors="ignore").lower()
        # Audio-only webm typically has "audio:" but no "video:"
        has_video = "video:" in probe or "video stream" in probe or "stream #0:0: video" in probe
        # ffmpeg prints like: Stream #0:0: Video: ...
        if re.search(r"stream\s+#\d+:\d+.*:\s*video", probe):
            has_video = True
        if re.search(r"stream\s+#\d+:\d+.*:\s*audio", probe) and not re.search(
            r"stream\s+#\d+:\d+.*:\s*video", probe
        ):
            has_video = False
        return has_video
    except Exception:  # noqa: BLE001
        return None


def _resolve_output_path(info: dict[str, Any], ydl: Any, *, preferred_ext: str | None) -> Path:
    """Resolve the real merged media path from yt-dlp info (not audio leftovers)."""
    for key in ("filepath", "_filename"):
        raw = info.get(key)
        if raw:
            p = Path(str(raw))
            if p.exists() and p.stat().st_size > 0:
                return p

    requested = info.get("requested_downloads") or []
    for item in requested:
        if not isinstance(item, dict):
            continue
        raw = item.get("filepath") or item.get("filename")
        if raw:
            p = Path(str(raw))
            if p.exists() and p.stat().st_size > 0:
                return p

    prepared = Path(ydl.prepare_filename(info))
    return _pick_downloaded_media(prepared, preferred_ext=preferred_ext)


def _assert_real_video_file(
    path: Path,
    *,
    info: dict[str, Any],
    expect_merge: bool,
    expected_height: int | None = None,
) -> None:
    size = path.stat().st_size
    if size <= 0:
        raise RuntimeError("下載檔案為空")

    has_video = _file_has_video_stream(path)
    if has_video is False:
        raise RuntimeError(
            "下載結果只有音訊（YouTube 的音訊軌也常是 .webm，先前會被誤當成影片）。"
            "請改選其他畫質後重試"
        )

    req = info.get("requested_formats") or []
    if isinstance(req, list) and req:
        any_video = any(
            isinstance(f, dict) and f.get("vcodec") not in (None, "none") for f in req
        )
        if not any_video:
            raise RuntimeError("下載結果未包含影像軌，請改選其他畫質後重試")

    actual_h = _probe_video_height(path)
    if expected_height and actual_h:
        # Allow small variance (e.g. 1280x720 vs labeled 720)
        if actual_h + 32 < expected_height:
            raise RuntimeError(
                f"你選的是約 {expected_height}p，但實際檔案只有 {actual_h}p"
                f"（{size / (1024 * 1024):.1f} MB）。已中止，避免再交低畫質小檔。"
            )

    if expect_merge and size < 8 * 1024 * 1024:
        raise RuntimeError(
            f"下載結果異常偏小（{size // 1024} KB），影音合併可能失敗。請改選其他畫質或稍後再試"
        )

    # Unknown probe + suspiciously small webm ≈ audio-only leftover
    if has_video is None and expect_merge and path.suffix.lower() == ".webm" and size < 25 * 1024 * 1024:
        raise RuntimeError(
            "下載到的 webm 檔異常偏小，可能是音訊軌。請改選其他畫質或稍後再試"
        )


def _pick_downloaded_media(prepared: Path, *, preferred_ext: str | None = None) -> Path:
    """Prefer the largest real video file in the task folder (skip audio-only webm/m4a)."""
    parent = prepared.parent
    stem = prepared.stem
    video_exts = {".mp4", ".webm", ".mkv", ".mov"}
    audio_exts = {".m4a", ".opus", ".ogg", ".mp3", ".aac"}

    candidates = [p for p in parent.glob(f"{stem}.*") if p.is_file()]
    if not candidates:
        candidates = [p for p in parent.iterdir() if p.is_file()]
    if not candidates:
        raise FileNotFoundError("找不到下載檔案")

    scored: list[tuple[tuple, Path]] = []
    for p in candidates:
        ext = p.suffix.lower()
        probe = _file_has_video_stream(p)
        prefer_match = bool(
            preferred_ext and ext == f".{preferred_ext.lstrip('.').lower()}"
        )
        # Exact preferred container (e.g. .mp3 after FFmpegExtractAudio) wins.
        if prefer_match:
            kind = 0
        elif probe is False or ext in audio_exts:
            kind = 3
        elif probe is True:
            kind = 1
        elif ext in video_exts:
            kind = 2  # unknown — treat as maybe video
        else:
            kind = 4
        pref = 0 if prefer_match else 1
        scored.append(((kind, pref, -p.stat().st_size), p))

    scored.sort(key=lambda x: x[0])
    best = scored[0][1]
    if not best.exists():
        raise FileNotFoundError("找不到下載檔案")
    return best


def download_audio_only(
    *,
    url: str,
    outtmpl: str,
    progress_hook=None,
) -> str:
    """Download best audio track for ASR; returns local path."""
    cleaned = validate_url(url)
    settings = get_settings()
    platform = detect_platform(cleaned)
    last_error: Exception | None = None
    for clients in _client_attempts(platform):
        opts: dict[str, Any] = {
            **_base_opts(clients, platform=platform),
            "format": "bestaudio/b",
            "outtmpl": outtmpl,
        }
        if settings.max_filesize_bytes > 0:
            opts["max_filesize"] = settings.max_filesize_bytes
        if progress_hook:
            opts["progress_hooks"] = [progress_hook]
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(cleaned, download=True)
                filepath = ydl.prepare_filename(info)
                from pathlib import Path

                path = Path(filepath)
                if path.exists():
                    return str(path)
                candidates = sorted(
                    path.parent.glob(f"{path.stem}.*"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if candidates:
                    return str(candidates[0])
                raise FileNotFoundError("找不到音訊檔")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    raise last_error or RuntimeError("音訊下載失敗")


def _subtitle_to_txt(src: str, dest: str) -> None:
    text = open(src, encoding="utf-8", errors="ignore").read()
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.upper().startswith("WEBVTT"):
            continue
        if re.fullmatch(r"\d+", s):
            continue
        if re.search(r"\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->", s):
            continue
        if s.startswith("NOTE") or s.startswith("STYLE"):
            continue
        lines.append(s)
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
