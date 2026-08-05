from app.services.rate_limit import TokenBucket
from app.services.ttl_cache import MemoryTtlCache
from app.services.url_utils import (
    canonicalize_youtube_url,
    extract_video_id,
    is_valid_youtube_url,
    looks_like_playlist,
    strip_ansi,
)
from app.services.ytdlp_service import download_dedupe_key, url_cache_key


def test_youtube_url_valid():
    assert is_valid_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert is_valid_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert not is_valid_youtube_url("https://example.com/watch?v=x")
    assert not is_valid_youtube_url("not-a-url")
    # Truncated / invalid id length
    assert not is_valid_youtube_url("https://www.youtube.com/watch?v=P-0rNajlfl")


def test_facebook_instagram_urls():
    from app.services.url_utils import canonicalize_media_url, is_valid_media_url

    fb = "https://www.facebook.com/watch?v=1234567890"
    ig = "https://www.instagram.com/reel/AbCdEfGhIjK/"
    assert is_valid_media_url(fb)
    assert is_valid_media_url(ig)
    assert canonicalize_media_url(ig) == "https://www.instagram.com/reel/AbCdEfGhIjK/"
    assert not is_valid_media_url("https://example.com/video/1")


def test_canonicalize_strips_mix_params():
    raw = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ&start_radio=1"
    assert canonicalize_youtube_url(raw) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert extract_video_id(raw) == "dQw4w9WgXcQ"


def test_playlist_detection():
    assert looks_like_playlist("https://www.youtube.com/playlist?list=PLxxxx")
    assert not looks_like_playlist(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ"
    )


def test_dedupe_key_stable():
    a = download_dedupe_key(
        url="https://www.youtube.com/watch?v=abc",
        mode="video",
        format_id="22",
        subtitle_language=None,
        subtitle_format=None,
    )
    b = download_dedupe_key(
        url="https://www.youtube.com/watch?v=abc",
        mode="video",
        format_id="22",
        subtitle_language=None,
        subtitle_format=None,
    )
    c = download_dedupe_key(
        url="https://www.youtube.com/watch?v=abc",
        mode="video",
        format_id="18",
        subtitle_language=None,
        subtitle_format=None,
    )
    assert a == b
    assert a != c
    assert a.startswith("d")


def test_url_cache_key_stable():
    assert url_cache_key(" https://x ", "webm") == url_cache_key("https://x", "webm")
    assert url_cache_key("https://x", "webm") != url_cache_key("https://x", "mp4")


def test_container_rank_prefers_webm():
    from app.services.ytdlp_service import _container_rank

    assert _container_rank({"ext": "webm", "vcodec": "vp9"}, "webm") == 0
    assert _container_rank({"ext": "mp4", "vcodec": "avc1"}, "webm") == 1
    assert _container_rank({"ext": "mp4", "vcodec": "avc1"}, "mp4") == 0


def test_segments_to_srt():
    from app.services.asr_service import Segment, segments_to_srt, segments_to_vtt, segments_to_txt

    segs = [
        Segment(0.0, 1.5, "你好"),
        Segment(1.5, 3.0, "世界"),
    ]
    srt = segments_to_srt(segs)
    assert "00:00:00,000 --> 00:00:01,500" in srt
    assert "你好" in srt
    vtt = segments_to_vtt(segs)
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.500" in vtt
    assert segments_to_txt(segs).strip() == "你好\n世界"


def test_ensure_audio_accepts_webm_without_ffmpeg(tmp_path, monkeypatch):
    from app.services import asr_service

    audio = tmp_path / "clip.webm"
    audio.write_bytes(b"fake-webm-bytes")
    asr_service._resolve_ffmpeg.cache_clear()
    monkeypatch.setattr(asr_service, "_resolve_ffmpeg", lambda: None)
    out = asr_service.ensure_audio_for_gemini(audio)
    assert out == audio


def test_token_bucket_retry_after():
    bucket = TokenBucket(rate_per_minute=60, burst=1.0)
    ok, _ = bucket.allow("ip1")
    assert ok
    ok2, retry = bucket.allow("ip1")
    assert not ok2
    assert retry >= 1


def test_can_try_direct_delivery():
    from app.services.ytdlp_service import can_try_direct_delivery

    assert can_try_direct_delivery("video", "22")
    assert can_try_direct_delivery("video", "140")
    assert not can_try_direct_delivery("video", "137+bestaudio/b")
    assert not can_try_direct_delivery("video", "bv*[height=1080]+ba")
    assert not can_try_direct_delivery("subtitle", "22")


def test_strip_ansi():
    assert "ERROR" in strip_ansi("[0;31mERROR:[0m boom")
    assert "\x1b" not in strip_ansi("\x1b[31mred\x1b[0m")
    cleaned = strip_ansi("[0;31mERROR:[0m [youtube] x: Requested format is not available")
    assert "[0;31m" not in cleaned
    assert "Requested format" in cleaned


def test_presence_heartbeat(monkeypatch):
    from app.services import presence as presence_mod
    from app.services.ttl_cache import MemoryTtlCache

    cache = MemoryTtlCache()
    monkeypatch.setattr(presence_mod, "get_ttl_cache", lambda: cache)
    presence_mod._online.clear()

    first = presence_mod.heartbeat("visitor-aaaaaaaa", page_hit=True)
    assert first["onlineNow"] == 1
    assert first["pageViewsTotal"] == 1
    assert first["pageViewsToday"] == 1

    second = presence_mod.heartbeat("visitor-aaaaaaaa", page_hit=False)
    assert second["onlineNow"] == 1
    assert second["pageViewsTotal"] == 1

    other = presence_mod.heartbeat("visitor-bbbbbbbb", page_hit=True)
    assert other["onlineNow"] == 2
    assert other["pageViewsTotal"] == 2

    snap = presence_mod.snapshot()
    assert snap["onlineNow"] == 2
    assert snap["pageViewsTotal"] == 2


def _fake_ydl_factory(calls, info):
    class _FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            calls.append(self.opts.get("extractor_args"))
            return info

    return _FakeYDL


def test_extract_stops_probing_clients_when_budget_exhausted(monkeypatch):
    """HQ formats without captions must not burn every player client."""
    from app.services import ytdlp_service as svc

    hq_no_captions = {
        "id": "abcdefghijk",
        "title": "t",
        "formats": [{"vcodec": "avc1", "height": 1080}],
        "subtitles": {},
        "automatic_captions": {},
    }
    calls: list = []
    monkeypatch.setattr(svc.yt_dlp, "YoutubeDL", _fake_ydl_factory(calls, hq_no_captions))
    monkeypatch.setattr(svc, "_store_extract_cache", lambda *a, **k: None)
    monkeypatch.setattr(svc, "get_ttl_cache", lambda: MemoryTtlCache())

    clock = iter([0.0, 30.0, 60.0, 90.0, 120.0])
    monkeypatch.setattr(svc.time, "monotonic", lambda: next(clock))

    info = svc._extract_info_raw("https://www.youtube.com/watch?v=abcdefghijk")

    assert info["id"] == "abcdefghijk"
    assert len(calls) == 1, "budget should stop after the first successful HQ attempt"


def test_extract_keeps_probing_until_captions_found(monkeypatch):
    """Within budget we still hunt for captions across clients."""
    from app.services import ytdlp_service as svc

    with_captions = {
        "id": "abcdefghijk",
        "title": "t",
        "formats": [{"vcodec": "avc1", "height": 1080}],
        "subtitles": {"zh-TW": [{"ext": "vtt", "url": "https://x/1"}]},
        "automatic_captions": {},
    }
    calls: list = []
    monkeypatch.setattr(svc.yt_dlp, "YoutubeDL", _fake_ydl_factory(calls, with_captions))
    monkeypatch.setattr(svc, "_store_extract_cache", lambda *a, **k: None)
    monkeypatch.setattr(svc, "get_ttl_cache", lambda: MemoryTtlCache())
    monkeypatch.setattr(svc.time, "monotonic", lambda: 0.0)

    info = svc._extract_info_raw("https://www.youtube.com/watch?v=abcdefghijk")

    assert svc._subtitle_track_count(info) == 1
    assert len(calls) == 1, "HQ + captions on first client should stop immediately"


def test_egress_pressure_helpers(monkeypatch):
    from app.config import get_settings
    from app.services import egress as egress_mod

    monkeypatch.setattr(egress_mod, "get_monthly_outbound", lambda: 0)
    assert egress_mod.outbound_pressure() == "ok"

    settings = get_settings()
    monkeypatch.setattr(
        egress_mod,
        "get_monthly_outbound",
        lambda: settings.max_monthly_outbound_bytes,
    )
    assert egress_mod.outbound_pressure() == "hard"

