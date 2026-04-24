from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from vantacut.models.asset import AssetKind, MediaAsset
from vantacut.models.subtitles import SubtitleCue
from vantacut.models.timeline import Marker, TimelineClip, TimelineTrack, TrackKind


@dataclass(slots=True)
class ProjectSettings:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    sample_rate: int = 48_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "sample_rate": self.sample_rate,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectSettings":
        return cls(
            width=payload.get("width", 1920),
            height=payload.get("height", 1080),
            fps=payload.get("fps", 30),
            sample_rate=payload.get("sample_rate", 48_000),
        )


@dataclass(slots=True)
class Project:
    name: str
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    id: str = field(default_factory=lambda: f"project-{uuid4().hex[:10]}")
    assets: list[MediaAsset] = field(default_factory=list)
    tracks: list[TimelineTrack] = field(default_factory=list)
    subtitles: list[SubtitleCue] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "settings": self.settings.to_dict(),
            "assets": [asset.to_dict() for asset in self.assets],
            "tracks": [track.to_dict() for track in self.tracks],
            "subtitles": [cue.to_dict() for cue in self.subtitles],
            "markers": [marker.to_dict() for marker in self.markers],
            "created_at": self.created_at,
            "updated_at": datetime.now(UTC).isoformat(),
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Project":
        return cls(
            id=payload["id"],
            name=payload["name"],
            settings=ProjectSettings.from_dict(payload.get("settings", {})),
            assets=[MediaAsset.from_dict(item) for item in payload.get("assets", [])],
            tracks=[TimelineTrack.from_dict(item) for item in payload.get("tracks", [])],
            subtitles=[
                SubtitleCue.from_dict(item) for item in payload.get("subtitles", [])
            ],
            markers=[Marker.from_dict(item) for item in payload.get("markers", [])],
            created_at=payload.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=payload.get("updated_at", datetime.now(UTC).isoformat()),
            path=payload.get("path"),
        )

    def track(self, kind: TrackKind) -> TimelineTrack:
        return next(track for track in self.tracks if track.kind == kind)

    def asset(self, asset_id: str) -> MediaAsset | None:
        return next((asset for asset in self.assets if asset.id == asset_id), None)

    @classmethod
    def empty(cls, name: str, path: str | None = None) -> "Project":
        return cls(
            name=name,
            tracks=[
                TimelineTrack(name="Video 1", kind=TrackKind.VIDEO, index=0),
                TimelineTrack(name="Audio 1", kind=TrackKind.AUDIO, index=1),
                TimelineTrack(name="Subtitles", kind=TrackKind.SUBTITLE, index=2),
            ],
            path=path,
        )

    @classmethod
    def demo(cls) -> "Project":
        intro = MediaAsset(
            path="media/interview.mp4",
            kind=AssetKind.VIDEO,
            duration_ticks=18_000,
            metadata={"resolution": "3840x2160", "fps": 29.97},
        )
        broll = MediaAsset(
            path="media/city-broll.mp4",
            kind=AssetKind.VIDEO,
            duration_ticks=11_500,
            metadata={"resolution": "1920x1080", "fps": 25},
        )
        music = MediaAsset(
            path="media/score.wav",
            kind=AssetKind.AUDIO,
            duration_ticks=22_000,
            metadata={"channels": 2, "sample_rate": 48_000},
        )
        subtitle_asset = MediaAsset(
            path="media/captions.srt",
            kind=AssetKind.SUBTITLE,
            duration_ticks=18_000,
        )

        video_track = TimelineTrack(name="Video 1", kind=TrackKind.VIDEO, index=0)
        audio_track = TimelineTrack(name="Audio 1", kind=TrackKind.AUDIO, index=1)
        subtitle_track = TimelineTrack(name="Subtitles", kind=TrackKind.SUBTITLE, index=2)

        video_track.clips.extend(
            [
                TimelineClip(
                    asset_id=intro.id,
                    track_id=video_track.id,
                    start=0,
                    duration=8_000,
                    selected=True,
                ),
                TimelineClip(
                    asset_id=broll.id,
                    track_id=video_track.id,
                    start=8_400,
                    duration=5_000,
                    source_in=1_500,
                ),
            ]
        )
        audio_track.clips.append(
            TimelineClip(
                asset_id=music.id,
                track_id=audio_track.id,
                start=0,
                duration=14_000,
            )
        )
        subtitle_track.clips.append(
            TimelineClip(
                asset_id=subtitle_asset.id,
                track_id=subtitle_track.id,
                start=0,
                duration=13_400,
            )
        )

        subtitles = [
            SubtitleCue(start=400, end=2_500, text="The city wakes up before dawn."),
            SubtitleCue(
                start=2_700,
                end=5_100,
                text="Cut from interview to b-roll on the skyline beat.",
            ),
            SubtitleCue(start=6_300, end=8_600, text="Room tone stays under the score."),
        ]

        markers = [
            Marker(time=0, label="In"),
            Marker(time=8_400, label="B-roll swap"),
            Marker(time=12_000, label="Outro"),
        ]

        return cls(
            name="Launch Teaser",
            assets=[intro, broll, music, subtitle_asset],
            tracks=[video_track, audio_track, subtitle_track],
            subtitles=subtitles,
            markers=markers,
        )
