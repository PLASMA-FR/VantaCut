import asyncio
from pathlib import Path
import shutil
import subprocess

import pytest

from vantacut.models.asset import AssetKind
from vantacut.preview.frame_renderer import PreviewFrameRenderer


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is not available in this environment.")


def test_frame_renderer_renders_video_image_and_audio_previews(tmp_path: Path) -> None:
    _require_ffmpeg()

    video_path = tmp_path / "preview.mp4"
    image_path = tmp_path / "preview.png"
    audio_path = tmp_path / "preview.wav"

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=64x36:d=1",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=#ff5533:s=64x36:d=1",
            "-frames:v",
            "1",
            str(image_path),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=660:duration=1",
            str(audio_path),
        ],
        check=True,
    )

    renderer = PreviewFrameRenderer()

    async def run() -> None:
        video = await renderer.render(video_path, AssetKind.VIDEO, 0.2, 32, 10)
        image = await renderer.render(image_path, AssetKind.IMAGE, 0.0, 32, 10)
        audio = await renderer.render(audio_path, AssetKind.AUDIO, 0.0, 32, 10)

        for result, path in (
            (video, video_path),
            (image, image_path),
            (audio, audio_path),
        ):
            assert result.backend == "terminal-ffmpeg"
            assert result.source_path == str(path.resolve())
            assert "▀" in result.frame.plain
            assert result.error is None

    asyncio.run(run())


def test_frame_renderer_builds_contain_and_fill_commands() -> None:
    renderer = PreviewFrameRenderer()
    target = Path("/tmp/demo.mp4")

    contain = renderer._build_command(  # noqa: SLF001
        target,
        AssetKind.VIDEO,
        1.25,
        80,
        40,
        None,
        "contain",
        "balanced",
    )
    fill = renderer._build_command(  # noqa: SLF001
        target,
        AssetKind.VIDEO,
        1.25,
        80,
        40,
        None,
        "fill",
        "full",
    )

    contain_vf = contain[contain.index("-vf") + 1]
    fill_vf = fill[fill.index("-vf") + 1]

    assert "-sws_flags" in contain
    assert contain[contain.index("-sws_flags") + 1] == "bicubic"
    assert "pad=80:40" in contain_vf
    assert "crop=80:40" not in contain_vf

    assert fill[fill.index("-sws_flags") + 1] == "lanczos"
    assert "crop=80:40" in fill_vf
    assert "force_original_aspect_ratio=increase" in fill_vf
