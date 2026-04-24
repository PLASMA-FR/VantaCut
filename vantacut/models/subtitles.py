from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class SubtitleCue:
    start: int
    end: int
    text: str
    id: str = field(default_factory=lambda: f"cue-{uuid4().hex[:10]}")

    @property
    def duration(self) -> int:
        return max(0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SubtitleCue":
        return cls(
            id=payload["id"],
            start=payload["start"],
            end=payload["end"],
            text=payload["text"],
        )

