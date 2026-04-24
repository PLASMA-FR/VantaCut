from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class AssetKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    SUBTITLE = "subtitle"


@dataclass(slots=True)
class MediaAsset:
    path: str
    kind: AssetKind
    duration_ticks: int = 0
    id: str = field(default_factory=lambda: f"asset-{uuid4().hex[:10]}")
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.label is None:
            self.label = Path(self.path).name

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MediaAsset":
        return cls(
            id=payload["id"],
            path=payload["path"],
            kind=AssetKind(payload["kind"]),
            duration_ticks=payload.get("duration_ticks", 0),
            label=payload.get("label"),
            metadata=dict(payload.get("metadata", {})),
        )

