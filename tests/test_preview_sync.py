from vantacut.models.timeline import TimelineClip
from vantacut.preview.sync import compute_preview_seek_seconds


def test_preview_seek_uses_clip_offset() -> None:
    clip = TimelineClip(asset_id="asset-1", track_id="track-1", start=2_000, duration=4_000, source_in=500)
    assert compute_preview_seek_seconds(clip, 3_500) == 2.0
