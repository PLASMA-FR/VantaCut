from __future__ import annotations

from dataclasses import dataclass, field

from vantacut.core.timecode import Timebase
from vantacut.models.project import Project
from vantacut.models.subtitles import SubtitleCue
from vantacut.models.timeline import TimelineClip


@dataclass(slots=True)
class EditorState:
    project: Project
    playhead: int = 0
    zoom: int = 12
    horizontal_scroll: int = 0
    selected_asset_id: str | None = None
    selected_clip_id: str | None = None
    selected_cue_id: str | None = None
    status: str = "Ready"
    preview_status: str = "mpv offline"
    follow_playhead: bool = True
    recent_projects: list[str] = field(default_factory=list)
    dirty: bool = False

    @property
    def timebase(self) -> Timebase:
        return Timebase(fps=self.project.settings.fps)

    def selected_clip(self) -> TimelineClip | None:
        for track in self.project.tracks:
            for clip in track.clips:
                if clip.id == self.selected_clip_id:
                    return clip
        return None

    def selected_cue(self) -> SubtitleCue | None:
        return next(
            (cue for cue in self.project.subtitles if cue.id == self.selected_cue_id),
            None,
        )

