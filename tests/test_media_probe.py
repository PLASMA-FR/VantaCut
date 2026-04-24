import asyncio
from pathlib import Path

from vantacut.models.asset import AssetKind
from vantacut.services.media_probe import MediaProbeService


def test_detect_kind() -> None:
    probe = MediaProbeService()
    assert probe.detect_kind("clip.mp4") is AssetKind.VIDEO
    assert probe.detect_kind("mix.wav") is AssetKind.AUDIO
    assert probe.detect_kind("frame.png") is AssetKind.IMAGE
    assert probe.detect_kind("captions.srt") is AssetKind.SUBTITLE


def test_probe_falls_back_without_ffprobe(monkeypatch, tmp_path: Path) -> None:
    async def run() -> None:
        target = tmp_path / "clip.mp4"
        target.write_bytes(b"not-a-real-video")
        probe = MediaProbeService()

        async def raise_missing(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise FileNotFoundError

        monkeypatch.setattr(asyncio, "create_subprocess_exec", raise_missing)
        result = await probe.probe(target)
        assert result.kind is AssetKind.VIDEO
        assert result.path == str(target.resolve())
        assert result.duration_ticks == 0
        assert result.metadata["probe"] == "fallback"

    asyncio.run(run())
