from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VIDEO_CODEC_ALIASES = {
    "avc": "h264",
    "avc1": "h264",
    "h.264": "h264",
    "x264": "h264",
}
AUDIO_CODEC_ALIASES = {
    "mp4a": "aac",
    "mp4a.40.2": "aac",
}


def _normalize_codec(value: Any, aliases: dict[str, str]) -> str:
    codec = str(value or "").strip().lower()
    return aliases.get(codec, codec)


@dataclass(frozen=True)
class MediaProbe:
    duration: float | None = None
    video_codec: str = ""
    audio_codec: str = ""
    container: str = ""

    @classmethod
    def from_ffprobe(cls, payload: dict[str, Any]) -> MediaProbe:
        if not isinstance(payload, dict):
            return cls()
        streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
        video_codec = ""
        audio_codec = ""
        for stream in streams:
            if not isinstance(stream, dict):
                continue
            codec_type = str(stream.get("codec_type", "")).lower()
            if codec_type == "video" and not video_codec:
                video_codec = _normalize_codec(stream.get("codec_name"), VIDEO_CODEC_ALIASES)
            elif codec_type == "audio" and not audio_codec:
                audio_codec = _normalize_codec(stream.get("codec_name"), AUDIO_CODEC_ALIASES)

        media_format = payload.get("format") if isinstance(payload.get("format"), dict) else {}
        try:
            duration = float(media_format.get("duration"))
        except (TypeError, ValueError):
            duration = None
        if duration is not None and duration < 60:
            duration = None

        return cls(
            duration=duration,
            video_codec=video_codec,
            audio_codec=audio_codec,
            container=str(media_format.get("format_name", "")).strip().lower(),
        )

    @classmethod
    def from_ticket(cls, value: Any) -> MediaProbe:
        if not isinstance(value, dict):
            return cls()
        try:
            duration = float(value.get("duration")) if value.get("duration") is not None else None
        except (TypeError, ValueError):
            duration = None
        return cls(
            duration=duration,
            video_codec=_normalize_codec(value.get("video_codec"), VIDEO_CODEC_ALIASES),
            audio_codec=_normalize_codec(value.get("audio_codec"), AUDIO_CODEC_ALIASES),
            container=str(value.get("container", "")).strip().lower(),
        )

    def to_ticket(self) -> dict[str, Any]:
        return {
            "duration": self.duration,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "container": self.container,
        }


@dataclass(frozen=True)
class PlaybackPlan:
    mode: str
    video_codec: str
    audio_codec: str
    video_copy: bool
    audio_copy: bool

    def video_args(self) -> list[str]:
        if self.video_copy:
            return ["-c:v", "copy"]
        return [
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-profile:v", "main", "-level", "4.0", "-pix_fmt", "yuv420p",
            "-sc_threshold", "0", "-force_key_frames", "expr:gte(t,n_forced*1)",
        ]

    def audio_args(self) -> list[str]:
        if self.audio_copy:
            return ["-c:a", "copy"]
        return [
            "-af", "aresample=async=1000:first_pts=0",
            "-c:a", "aac", "-profile:a", "aac_low",
            "-ar", "48000", "-ac", "2", "-b:a", "128k",
        ]


def choose_playback_plan(probe: MediaProbe) -> PlaybackPlan:
    video_copy = probe.video_codec == "h264"
    audio_copy = probe.audio_codec == "aac"
    if video_copy and audio_copy:
        mode = "remux"
    elif video_copy:
        mode = "audio-transcode"
    else:
        mode = "full-transcode"
    return PlaybackPlan(
        mode=mode,
        video_codec=probe.video_codec or "unknown",
        audio_codec=probe.audio_codec or "unknown",
        video_copy=video_copy,
        audio_copy=audio_copy,
    )
