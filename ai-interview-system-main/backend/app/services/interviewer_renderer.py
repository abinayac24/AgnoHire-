from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
import logging
from pathlib import Path
import subprocess
import tempfile
from threading import Lock
from typing import Literal
from uuid import uuid4

import requests
import pyttsx3

from app.config import settings

logger = logging.getLogger(__name__)


RenderMode = Literal["video", "audio", "fallback"]


@dataclass(slots=True)
class RenderResponse:
    mode: RenderMode
    video_token: str = ""
    video_url: str = ""
    audio_token: str = ""
    subtitle: str = ""
    provider: str = "local"
    ready: bool = True


class BinaryCache:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}
        self._lock = Lock()

    def put(self, data: bytes, mime_type: str, ttl_seconds: int = 600) -> str:
        token = uuid4().hex
        with self._lock:
            self._items[token] = {
                "bytes": data,
                "mime_type": mime_type,
                "expires_at": datetime.utcnow() + timedelta(seconds=max(30, ttl_seconds)),
            }
        return token

    def get(self, token: str) -> dict | None:
        with self._lock:
            item = self._items.get(token)
            if not item:
                return None
            if item["expires_at"] < datetime.utcnow():
                self._items.pop(token, None)
                return None
            return item


audio_cache = BinaryCache()
video_cache = BinaryCache()


class InterviewerRenderer:
    def __init__(self) -> None:
        self.timeout = settings.interviewer_timeout_seconds

    def _render_with_did(self, text: str) -> RenderResponse | None:
        if not (settings.did_api_key and settings.did_source_url):
            return None
        try:
            payload = {
                "source_url": settings.did_source_url,
                "script": {
                    "type": "text",
                    "input": text,
                    "provider": {"type": settings.did_voice_provider, "voice_id": settings.did_voice_id},
                },
            }
            headers = {"Authorization": f"Basic {settings.did_api_key}", "Content-Type": "application/json"}
            response = requests.post(
                f"{settings.did_base_url.rstrip('/')}/talks",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            if not response.ok:
                return None
            data = response.json()
            result_url = data.get("result_url", "")
            if not result_url:
                return None
            return RenderResponse(mode="video", video_url=result_url, subtitle=text, provider="d-id")
        except Exception:
            return None

    def _synthesize_with_elevenlabs(self, text: str) -> bytes | None:
        if not (settings.elevenlabs_api_key and settings.elevenlabs_voice_id):
            return None
        try:
            headers = {
                "xi-api-key": settings.elevenlabs_api_key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            }
            payload = {
                "text": text,
                "model_id": settings.elevenlabs_model_id,
                "voice_settings": {"stability": 0.52, "similarity_boost": 0.86, "style": 0.18},
            }
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            if not response.ok or not response.content:
                return None
            return response.content
        except Exception:
            return None

    def _synthesize_with_azure(self, text: str) -> bytes | None:
        if not (settings.azure_tts_key and settings.azure_tts_region):
            return None
        try:
            url = f"https://{settings.azure_tts_region}.tts.speech.microsoft.com/cognitiveservices/v1"
            ssml = (
                "<speak version='1.0' xml:lang='en-US'>"
                f"<voice name='{settings.azure_tts_voice}'>"
                f"<prosody rate='0%' pitch='0%'>{text}</prosody>"
                "</voice></speak>"
            )
            headers = {
                "Ocp-Apim-Subscription-Key": settings.azure_tts_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-16khz-64kbitrate-mono-mp3",
            }
            response = requests.post(url, data=ssml.encode("utf-8"), headers=headers, timeout=self.timeout)
            if not response.ok or not response.content:
                return None
            return response.content
        except Exception:
            return None

    def _synthesize_tts(self, text: str) -> bytes | None:
        return (
            self._synthesize_with_elevenlabs(text)
            or self._synthesize_with_azure(text)
            or self._synthesize_with_local_windows(text)
        )

    def _synthesize_with_local_windows(self, text: str) -> bytes | None:
        try:
            with tempfile.TemporaryDirectory(prefix="local_tts_") as tdir:
                out_wav = Path(tdir) / "tts.wav"
                engine = pyttsx3.init()
                engine.setProperty("rate", 160)
                engine.setProperty("volume", 1.0)
                engine.save_to_file(text, str(out_wav))
                engine.runAndWait()
                if out_wav.exists() and out_wav.stat().st_size > 1024:
                    logger.info("Local Windows TTS generated audio: %s", out_wav)
                    return out_wav.read_bytes()
        except Exception as exc:
            logger.warning("Local Windows TTS failed: %s", exc)
        return None

    def _render_with_sadtalker(self, text: str) -> RenderResponse | None:
        if not settings.sadtalker_enabled:
            logger.info("SadTalker disabled; skipping SadTalker render.")
            return None
        if not (settings.sadtalker_python and settings.sadtalker_inference_script and settings.sadtalker_source_image_path):
            logger.warning("SadTalker config missing (python/script/source image).")
            return None

        audio_bytes = self._synthesize_tts(text)
        if not audio_bytes:
            logger.warning("SadTalker render skipped because TTS audio synthesis failed.")
            return None

        with tempfile.TemporaryDirectory(prefix="sadtalker_") as tmp_dir:
            tmp = Path(tmp_dir)
            inference_script = Path(settings.sadtalker_inference_script)
            if not inference_script.exists():
                logger.warning("SadTalker inference script not found: %s", inference_script)
                return None
            source_image = Path(settings.sadtalker_source_image_path)
            if not source_image.exists():
                logger.warning("SadTalker source image not found: %s", source_image)
                return None
            audio_path = tmp / "question.mp3"
            out_dir = tmp / "result"
            out_dir.mkdir(parents=True, exist_ok=True)
            audio_path.write_bytes(audio_bytes)
            logger.info("SadTalker audio prepared at: %s", audio_path)

            cmd = [
                settings.sadtalker_python,
                settings.sadtalker_inference_script,
                settings.sadtalker_driven_audio_arg,
                str(audio_path),
                settings.sadtalker_source_image_arg,
                str(source_image),
                settings.sadtalker_result_dir_arg,
                str(out_dir),
            ]
            # Ensure SadTalker resolves ./checkpoints and src/config relative to its repository root.
            sadtalker_cwd = str(inference_script.parent)
            logger.info("Running SadTalker command: %s", " ".join(cmd))
            run = subprocess.run(
                cmd,
                cwd=sadtalker_cwd,
                capture_output=True,
                text=True,
                timeout=max(20, self.timeout * 4),
            )
            if run.returncode != 0:
                stderr_tail = (run.stderr or "").strip()[-500:]
                logger.error("SadTalker failed (code=%s): %s", run.returncode, stderr_tail)
                return None

            mp4_files = sorted(out_dir.rglob("*.mp4"))
            if not mp4_files:
                logger.error("SadTalker completed but no mp4 output found in: %s", out_dir)
                return None
            video_bytes = mp4_files[0].read_bytes()
            logger.info("SadTalker output video: %s", mp4_files[0])
            token = video_cache.put(video_bytes, "video/mp4", ttl_seconds=900)
            return RenderResponse(mode="video", video_token=token, subtitle=text, provider="sadtalker")

    def _render_audio_only(self, text: str, provider_hint: str) -> RenderResponse | None:
        audio_bytes = self._synthesize_tts(text)
        if not audio_bytes:
            return None
        token = audio_cache.put(audio_bytes, "audio/mpeg", ttl_seconds=900)
        return RenderResponse(mode="audio", audio_token=token, subtitle=text, provider=provider_hint)

    def render_question(self, text: str) -> RenderResponse:
        clean_text = (text or "").strip()
        if not clean_text:
            return RenderResponse(mode="fallback", subtitle="")

        provider = settings.interviewer_provider

        if provider in {"local", "browser", "fallback"}:
            return RenderResponse(mode="fallback", subtitle=clean_text, provider="browser-tts")

        if provider == "d-id":
            result = self._render_with_did(clean_text)
            if result:
                return result
            audio_fallback = self._render_audio_only(clean_text, "d-id-audio-fallback")
            if audio_fallback:
                return audio_fallback

        if provider in {"elevenlabs", "azure", "d-id"}:
            audio_result = self._render_audio_only(clean_text, provider if provider in {"elevenlabs", "azure"} else "audio")
            if audio_result:
                return audio_result

        return RenderResponse(mode="fallback", subtitle=clean_text, provider="browser-tts")

    @staticmethod
    def get_audio_stream(token: str) -> tuple[BytesIO, str] | None:
        item = audio_cache.get(token)
        if not item:
            return None
        return BytesIO(item["bytes"]), item["mime_type"]

    @staticmethod
    def get_video_stream(token: str) -> tuple[BytesIO, str] | None:
        item = video_cache.get(token)
        if not item:
            return None
        return BytesIO(item["bytes"]), item["mime_type"]


interviewer_renderer = InterviewerRenderer()
