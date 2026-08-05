from __future__ import annotations

import base64
import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

LANGUAGE_HINTS: dict[str, str] = {
    "auto": "Transcribe in the original spoken language.",
    "zh": "以繁體中文轉錄內容。",
    "en": "Transcribe in English.",
    "ja": "日本語で書き起こしてください。",
    "ko": "한국어로 받아적어 주세요.",
}

# Formats Gemini accepts without remux (YouTube bestaudio is often .webm / .m4a)
GEMINI_NATIVE_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".webm", ".mp4", ".aac", ".opus"}

MIME_BY_EXT: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".opus": "audio/ogg",
}


@dataclass
class Segment:
    start_sec: float
    end_sec: float
    text: str


def _mime_for(path: Path) -> str:
    return MIME_BY_EXT.get(path.suffix.lower(), "audio/mpeg")


def _safe_error_message(status_code: int, body: str) -> str:
    lower = body.lower()
    if status_code in {401, 403}:
        return "Gemini API Key 無效或沒有權限，請到 Google AI Studio 確認金鑰"
    if status_code == 429:
        return "Gemini 額度用盡或請求過於頻繁，請稍後再試"
    if "api key" in lower or "permission" in lower:
        return "Gemini API Key 無效或沒有權限"
    if len(body) > 280:
        body = body[:280] + "…"
    # Strip anything that looks like a key
    body = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[redacted]", body)
    return f"Gemini 辨識失敗（{status_code}）：{body}"


@lru_cache
def _resolve_ffmpeg() -> str | None:
    """Locate ffmpeg binary: PATH first, then imageio-ffmpeg bundle."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and Path(path).exists():
            return path
    except Exception:  # noqa: BLE001
        logger.debug("imageio-ffmpeg not available", exc_info=True)
    return None


def ensure_audio_for_gemini(src: Path) -> Path:
    """Prefer compact mp3 for faster Gemini upload when ffmpeg is available."""
    settings = get_settings()
    if not src.exists():
        raise FileNotFoundError("找不到音訊檔")

    size = src.stat().st_size
    ext = src.suffix.lower()
    native = ext in GEMINI_NATIVE_EXTS
    ffmpeg = _resolve_ffmpeg()

    # Compact remux speeds up upload + transcription (YouTube webm/m4a can be large)
    should_compress = bool(
        ffmpeg
        and (size > 1_500_000 or ext not in {".mp3", ".wav"} or size > settings.gemini_inline_max_bytes)
    )
    if should_compress:
        dest = src.with_name(src.stem + ".asr.mp3")
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "48k",
            str(dest),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=180)
            if dest.exists() and dest.stat().st_size > 0:
                logger.info(
                    "compressed audio for asr %s -> %s bytes",
                    size,
                    dest.stat().st_size,
                )
                return dest
        except FileNotFoundError:
            pass
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or b"").decode("utf-8", errors="ignore")[:200]
            logger.warning("audio compress failed, using original: %s", err)
        except subprocess.TimeoutExpired:
            logger.warning("audio compress timed out, using original")

    if native and size <= settings.gemini_inline_max_bytes:
        return src

    if native:
        logger.info("audio oversize for inline; will use Files API without remux (%s bytes)", size)
        return src

    if not ffmpeg:
        raise RuntimeError(
            "音訊格式需轉檔，但找不到 ffmpeg。請安裝 ffmpeg 並加入 PATH，"
            "或 pip install imageio-ffmpeg 後重啟後端"
        )

    dest = src.with_name(src.stem + ".asr.mp3")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "48k",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "找不到 ffmpeg。請安裝並加入 PATH，或 pip install imageio-ffmpeg 後重啟後端"
        ) from exc
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode("utf-8", errors="ignore")[:200]
        raise RuntimeError(f"音訊轉檔失敗：{err or 'ffmpeg error'}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("音訊轉檔逾時") from exc

    if not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError("音訊轉檔後找不到檔案")
    return dest


def _parse_segments(payload: Any) -> list[Segment]:
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("Gemini 回傳格式無法解析")
    raw = payload.get("segments")
    if not isinstance(raw, list) or not raw:
        # Fallback: single block from text field
        text = str(payload.get("text") or "").strip()
        if text:
            return [Segment(0.0, 0.0, text)]
        raise ValueError("Gemini 未回傳可用字幕段落")

    segments: list[Segment] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        try:
            start = float(item.get("start_sec") or 0)
            end = float(item.get("end_sec") or start)
        except (TypeError, ValueError):
            continue
        if end < start:
            end = start
        segments.append(Segment(start_sec=start, end_sec=end, text=text))
    if not segments:
        raise ValueError("Gemini 未回傳可用字幕段落")
    return segments


def _extract_json_text(response_json: dict[str, Any]) -> str:
    candidates = response_json.get("candidates") or []
    if not candidates:
        feedback = response_json.get("promptFeedback") or {}
        raise ValueError(f"Gemini 沒有回傳內容：{feedback or 'empty candidates'}")
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    texts = [str(p.get("text") or "") for p in parts if isinstance(p, dict)]
    joined = "\n".join(t for t in texts if t).strip()
    if not joined:
        raise ValueError("Gemini 回傳空白")
    # Strip markdown fences if model ignores responseMimeType
    if joined.startswith("```"):
        joined = re.sub(r"^```(?:json)?\s*", "", joined)
        joined = re.sub(r"\s*```$", "", joined)
    return joined


def _response_schema() -> dict[str, Any]:
    return {
        "type": "OBJECT",
        "properties": {
            "segments": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "start_sec": {"type": "NUMBER"},
                        "end_sec": {"type": "NUMBER"},
                        "text": {"type": "STRING"},
                    },
                    "required": ["start_sec", "end_sec", "text"],
                },
            }
        },
        "required": ["segments"],
    }


def _build_prompt(language: str) -> str:
    hint = LANGUAGE_HINTS.get(language, LANGUAGE_HINTS["auto"])
    return (
        "你是字幕轉錄工具。請完整轉錄這段音訊為字幕段落。"
        f"{hint}"
        "只輸出 JSON，格式為 "
        '{"segments":[{"start_sec":0.0,"end_sec":1.5,"text":"..."}]}。'
        "時間軸以秒為單位，盡量依語句切段，不要加入說明文字。"
    )


def _upload_file(client: httpx.Client, api_key: str, path: Path) -> dict[str, str]:
    mime = _mime_for(path)
    size = path.stat().st_size
    start = client.post(
        f"{GEMINI_BASE}/files",
        headers={
            "x-goog-api-key": api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(size),
            "X-Goog-Upload-Header-Content-Type": mime,
            "Content-Type": "application/json",
        },
        json={"file": {"display_name": path.name}},
        timeout=60.0,
    )
    if start.status_code >= 400:
        raise RuntimeError(_safe_error_message(start.status_code, start.text))
    upload_url = start.headers.get("x-goog-upload-url") or start.headers.get("X-Goog-Upload-URL")
    if not upload_url:
        raise RuntimeError("Gemini Files API 未回傳上傳網址")

    data = path.read_bytes()
    finished = client.post(
        upload_url,
        headers={
            "x-goog-api-key": api_key,
            "Content-Length": str(size),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
            "Content-Type": mime,
        },
        content=data,
        timeout=180.0,
    )
    if finished.status_code >= 400:
        raise RuntimeError(_safe_error_message(finished.status_code, finished.text))
    meta = finished.json()
    file_obj = meta.get("file") if isinstance(meta.get("file"), dict) else meta
    uri = file_obj.get("uri")
    mime_type = file_obj.get("mimeType") or mime
    if not uri:
        raise RuntimeError("Gemini Files API 上傳成功但缺少 uri")
    return {"uri": uri, "mimeType": mime_type}


def _delete_file(client: httpx.Client, api_key: str, uri: str) -> None:
    # uri like https://generativelanguage.googleapis.com/v1beta/files/xxx
    name = uri.rstrip("/").split("/")[-1]
    if not name:
        return
    try:
        client.delete(
            f"{GEMINI_BASE}/files/{name}",
            headers={"x-goog-api-key": api_key},
            timeout=30.0,
        )
    except Exception:  # noqa: BLE001
        logger.debug("failed to delete gemini file %s", name)


def transcribe_with_gemini(
    *,
    api_key: str,
    audio_path: Path,
    language: str = "zh",
    on_stage: Any | None = None,
) -> list[Segment]:
    settings = get_settings()
    key = (api_key or "").strip()
    if not key:
        raise ValueError("請提供 Gemini API Key")

    def stage(name: str, detail: str = "") -> None:
        if callable(on_stage):
            try:
                on_stage(name, detail)
            except Exception:  # noqa: BLE001
                pass

    stage("prepare", "正在準備音訊…")
    audio = ensure_audio_for_gemini(audio_path)
    mime = _mime_for(audio)
    model = settings.gemini_asr_model
    prompt = _build_prompt(language or "zh")
    size = audio.stat().st_size

    generation_config = {
        "responseMimeType": "application/json",
        "responseSchema": _response_schema(),
        "temperature": 0.1,
    }

    uploaded_uri: str | None = None
    with httpx.Client() as client:
        if size <= settings.gemini_inline_max_bytes:
            stage("encode", "正在編碼音訊…")
            b64 = base64.b64encode(audio.read_bytes()).decode("ascii")
            parts: list[dict[str, Any]] = [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]
        else:
            stage("upload", "正在上傳音訊至 Gemini…")
            meta = _upload_file(client, key, audio)
            uploaded_uri = meta["uri"]
            parts = [
                {"text": prompt},
                {"file_data": {"mime_type": meta["mimeType"], "file_uri": meta["uri"]}},
            ]

        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        stage("waiting", "Gemini 雲端辨識中，請稍候…")
        try:
            res = client.post(
                url,
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json=body,
                timeout=300.0,
            )
        finally:
            if uploaded_uri:
                _delete_file(client, key, uploaded_uri)

        if res.status_code >= 400:
            raise RuntimeError(_safe_error_message(res.status_code, res.text))

        stage("parse", "正在整理字幕…")
        text = _extract_json_text(res.json())
        return _parse_segments(text)


def _format_ts(seconds: float, *, vtt: bool = False) -> str:
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{milli:03d}"


def segments_to_srt(segments: list[Segment]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        end = seg.end_sec if seg.end_sec > seg.start_sec else seg.start_sec + 2.0
        lines.append(str(i))
        lines.append(f"{_format_ts(seg.start_sec)} --> {_format_ts(end)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def segments_to_vtt(segments: list[Segment]) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        end = seg.end_sec if seg.end_sec > seg.start_sec else seg.start_sec + 2.0
        lines.append(f"{_format_ts(seg.start_sec, vtt=True)} --> {_format_ts(end, vtt=True)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def segments_to_txt(segments: list[Segment]) -> str:
    return "\n".join(seg.text for seg in segments if seg.text).rstrip() + "\n"


def write_subtitle_file(
    segments: list[Segment],
    *,
    dest: Path,
    fmt: str,
) -> Path:
    fmt = fmt.lower()
    if fmt == "srt":
        content = segments_to_srt(segments)
    elif fmt == "vtt":
        content = segments_to_vtt(segments)
    elif fmt == "txt":
        content = segments_to_txt(segments)
    else:
        raise ValueError("不支援的字幕格式")
    dest.write_text(content, encoding="utf-8")
    return dest
