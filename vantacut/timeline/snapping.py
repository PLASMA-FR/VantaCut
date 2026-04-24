from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SnapCandidate:
    time: int
    label: str


@dataclass(frozen=True, slots=True)
class SnapResult:
    time: int
    candidate: SnapCandidate | None = None

    @property
    def did_snap(self) -> bool:
        return self.candidate is not None


def resolve_snap(
    desired_time: int,
    candidates: list[SnapCandidate],
    threshold: int,
) -> SnapResult:
    closest: SnapCandidate | None = None
    closest_distance = threshold + 1
    for candidate in candidates:
        distance = abs(candidate.time - desired_time)
        if distance <= threshold and distance < closest_distance:
            closest = candidate
            closest_distance = distance
    if closest is None:
        return SnapResult(time=desired_time, candidate=None)
    return SnapResult(time=closest.time, candidate=closest)

