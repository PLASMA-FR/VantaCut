from __future__ import annotations

from vantacut.models.timeline import TimelineClip


def compute_preview_seek_seconds(clip: TimelineClip, playhead_ticks: int) -> float:
    offset = max(0, playhead_ticks - clip.start)
    return (clip.source_in + offset) / 1000

