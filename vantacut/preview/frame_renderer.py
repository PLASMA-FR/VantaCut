from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rich.style import Style
from rich.text import Text

from vantacut.core.logging import get_logger
from vantacut.models.asset import AssetKind


@dataclass(slots=True)
class FrameRenderResult:
    frame: Text
    backend: str
    seconds: float
    source_path: str | None
    error: str | None = None


class PreviewFrameRenderer:
    def __init__(self) -> None:
        self.logger = get_logger("vantacut.preview.frame_renderer")

    async def render(
        self,
        path: str | Path,
        kind: AssetKind,
        seconds: float,
        width_cells: int,
        height_cells: int,
        filter_chain: str | None = None,
        fit_mode: str = "contain",
        scale_quality: str = "balanced",
    ) -> FrameRenderResult:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return self._placeholder("Missing media file.", None, seconds, str(target))

        pixel_width = max(16, width_cells)
        pixel_height = max(12, height_cells * 2)
        command = self._build_command(
            target,
            kind,
            max(0.0, seconds),
            pixel_width,
            pixel_height,
            filter_chain,
            fit_mode,
            scale_quality,
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return self._placeholder("ffmpeg not found.", "terminal-unavailable", seconds, str(target))

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=6.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return self._placeholder("Frame rendering timed out.", "terminal-timeout", seconds, str(target))

        expected_bytes = pixel_width * pixel_height * 3
        if process.returncode != 0 or len(stdout) != expected_bytes:
            message = stderr.decode("utf-8", errors="ignore").strip() or "ffmpeg frame render failed."
            self.logger.info(
                "frame_render_failed path=%s kind=%s returncode=%s error=%s",
                target,
                kind.value,
                process.returncode,
                message,
            )
            return self._placeholder(message, "terminal-error", seconds, str(target))

        return FrameRenderResult(
            frame=self._pixels_to_text(stdout, pixel_width, pixel_height),
            backend="terminal-ffmpeg",
            seconds=max(0.0, seconds),
            source_path=str(target),
        )

    def _build_command(
        self,
        target: Path,
        kind: AssetKind,
        seconds: float,
        pixel_width: int,
        pixel_height: int,
        filter_chain: str | None,
        fit_mode: str,
        scale_quality: str,
    ) -> list[str]:
        sws_flags = {
            "fast": "fast_bilinear",
            "balanced": "bicubic",
            "full": "lanczos",
        }.get(scale_quality, "bicubic")
        if kind is AssetKind.AUDIO:
            return [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(target),
                "-filter_complex",
                (
                    f"[0:a]aformat=channel_layouts=mono,"
                    f"showwavespic=s={pixel_width}x{pixel_height}:colors=0x93d4ff[v]"
                ),
                "-map",
                "[v]",
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ]

        vf_parts: list[str] = []
        if filter_chain:
            vf_parts.append(filter_chain)
        if fit_mode == "fill":
            vf_parts.append(
                f"scale={pixel_width}:{pixel_height}:force_original_aspect_ratio=increase"
            )
            vf_parts.append(f"crop={pixel_width}:{pixel_height}")
        else:
            vf_parts.append(
                f"scale={pixel_width}:{pixel_height}:force_original_aspect_ratio=decrease"
            )
            vf_parts.append(
                f"pad={pixel_width}:{pixel_height}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-sws_flags",
            sws_flags,
        ]
        if kind is not AssetKind.IMAGE:
            command.extend(["-ss", f"{seconds:.3f}"])
        command.extend(
            [
                "-i",
                str(target),
                "-an",
                "-sn",
                "-dn",
                "-frames:v",
                "1",
                "-vf",
                ",".join(part for part in vf_parts if part),
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ]
        )
        return command

    def _placeholder(
        self,
        message: str,
        backend: str | None,
        seconds: float,
        source_path: str | None,
    ) -> FrameRenderResult:
        text = Text(justify="center")
        text.append("\n")
        text.append("Preview unavailable\n", style="bold #93d4ff")
        text.append(message, style="dim #8ea0b9")
        return FrameRenderResult(
            frame=text,
            backend=backend or "terminal-placeholder",
            seconds=seconds,
            source_path=source_path,
            error=message,
        )

    def _pixels_to_text(self, buffer: bytes, width: int, height: int) -> Text:
        frame = Text()
        stride = width * 3
        for y in range(0, height, 2):
            for x in range(width):
                top = self._read_rgb(buffer, stride, x, y)
                bottom = self._read_rgb(buffer, stride, x, min(y + 1, height - 1))
                frame.append("▀", style=_style_for(top, bottom))
            if y + 2 < height:
                frame.append("\n")
        return frame

    def _read_rgb(self, buffer: bytes, stride: int, x: int, y: int) -> tuple[int, int, int]:
        offset = y * stride + x * 3
        return buffer[offset], buffer[offset + 1], buffer[offset + 2]


@lru_cache(maxsize=32_768)
def _style_for(
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> Style:
    return Style(
        color=f"rgb({top[0]},{top[1]},{top[2]})",
        bgcolor=f"rgb({bottom[0]},{bottom[1]},{bottom[2]})",
    )
