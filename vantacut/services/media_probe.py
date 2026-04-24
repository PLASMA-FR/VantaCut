from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from vantacut.models.asset import AssetKind, MediaAsset


@dataclass(slots=True)
class ProbeResult:
    path: str
    kind: AssetKind
    duration_ticks: int
    metadata: dict[str, object]

    def to_asset(self) -> MediaAsset:
        return MediaAsset(
            path=self.path,
            kind=self.kind,
            duration_ticks=self.duration_ticks,
            metadata=self.metadata,
        )


class MediaProbeService:
    VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    AUDIO_SUFFIXES = {".wav", ".mp3", ".aac", ".flac", ".m4a", ".ogg"}
    IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    SUBTITLE_SUFFIXES = {".srt", ".ass", ".vtt"}

    async def probe(self, path: str | Path) -> ProbeResult:
        target = Path(path).expanduser().resolve()
        kind = self.detect_kind(target)
        ffprobe = await self._run_ffprobe(target)
        if ffprobe is not None:
            duration_seconds = float(ffprobe.get("format", {}).get("duration", 0.0))
            metadata = {
                "size_bytes": target.stat().st_size if target.exists() else 0,
                "streams": len(ffprobe.get("streams", [])),
            }
            for stream in ffprobe.get("streams", []):
                codec_type = stream.get("codec_type")
                if codec_type == "video":
                    metadata["resolution"] = (
                        f"{stream.get('width', 0)}x{stream.get('height', 0)}"
                    )
                    metadata["fps"] = stream.get("avg_frame_rate")
                if codec_type == "audio":
                    metadata["sample_rate"] = stream.get("sample_rate")
                    metadata["channels"] = stream.get("channels")
            return ProbeResult(
                path=str(target),
                kind=kind,
                duration_ticks=round(duration_seconds * 1000),
                metadata=metadata,
            )

        metadata = {
            "size_bytes": target.stat().st_size if target.exists() else 0,
            "probe": "fallback",
        }
        return ProbeResult(path=str(target), kind=kind, duration_ticks=0, metadata=metadata)

    def detect_kind(self, path: str | Path) -> AssetKind:
        suffix = Path(path).suffix.lower()
        if suffix in self.VIDEO_SUFFIXES:
            return AssetKind.VIDEO
        if suffix in self.AUDIO_SUFFIXES:
            return AssetKind.AUDIO
        if suffix in self.IMAGE_SUFFIXES:
            return AssetKind.IMAGE
        if suffix in self.SUBTITLE_SUFFIXES:
            return AssetKind.SUBTITLE
        return AssetKind.VIDEO

    async def _run_ffprobe(self, path: Path) -> dict[str, object] | None:
        try:
            process = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return None
        stdout, _ = await process.communicate()
        if process.returncode != 0 or not stdout:
            return None
        try:
            return json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError:
            return None
