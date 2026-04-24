from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class TrackKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"


class ScaleMode(StrEnum):
    FIT = "fit"
    FILL = "fill"
    STRETCH = "stretch"


@dataclass(slots=True)
class TransformState:
    crop_x: int = 0
    crop_y: int = 0
    crop_width: int = 0
    crop_height: int = 0
    scale_mode: ScaleMode = ScaleMode.FIT
    position_x: float = 0.0
    position_y: float = 0.0
    rotation: float = 0.0
    opacity: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "crop_x": self.crop_x,
            "crop_y": self.crop_y,
            "crop_width": self.crop_width,
            "crop_height": self.crop_height,
            "scale_mode": self.scale_mode.value,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "rotation": self.rotation,
            "opacity": self.opacity,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TransformState":
        return cls(
            crop_x=payload.get("crop_x", 0),
            crop_y=payload.get("crop_y", 0),
            crop_width=payload.get("crop_width", 0),
            crop_height=payload.get("crop_height", 0),
            scale_mode=ScaleMode(payload.get("scale_mode", ScaleMode.FIT.value)),
            position_x=payload.get("position_x", 0.0),
            position_y=payload.get("position_y", 0.0),
            rotation=payload.get("rotation", 0.0),
            opacity=payload.get("opacity", 1.0),
        )


@dataclass(slots=True)
class TimelineClip:
    asset_id: str
    track_id: str
    start: int
    duration: int
    source_in: int = 0
    id: str = field(default_factory=lambda: f"clip-{uuid4().hex[:10]}")
    source_out: int | None = None
    selected: bool = False
    muted: bool = False
    linked: bool = True
    transform: TransformState = field(default_factory=TransformState)

    @property
    def end(self) -> int:
        return self.start + self.duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "track_id": self.track_id,
            "start": self.start,
            "duration": self.duration,
            "source_in": self.source_in,
            "source_out": self.source_out,
            "selected": self.selected,
            "muted": self.muted,
            "linked": self.linked,
            "transform": self.transform.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TimelineClip":
        return cls(
            id=payload["id"],
            asset_id=payload["asset_id"],
            track_id=payload["track_id"],
            start=payload["start"],
            duration=payload["duration"],
            source_in=payload.get("source_in", 0),
            source_out=payload.get("source_out"),
            selected=payload.get("selected", False),
            muted=payload.get("muted", False),
            linked=payload.get("linked", True),
            transform=TransformState.from_dict(payload.get("transform", {})),
        )


@dataclass(slots=True)
class TimelineTrack:
    name: str
    kind: TrackKind
    index: int
    id: str = field(default_factory=lambda: f"track-{uuid4().hex[:10]}")
    clips: list[TimelineClip] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "index": self.index,
            "clips": [clip.to_dict() for clip in self.clips],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TimelineTrack":
        return cls(
            id=payload["id"],
            name=payload["name"],
            kind=TrackKind(payload["kind"]),
            index=payload["index"],
            clips=[TimelineClip.from_dict(item) for item in payload.get("clips", [])],
        )


@dataclass(slots=True)
class Marker:
    time: int
    label: str
    id: str = field(default_factory=lambda: f"marker-{uuid4().hex[:8]}")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "time": self.time, "label": self.label}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Marker":
        return cls(id=payload["id"], time=payload["time"], label=payload["label"])

