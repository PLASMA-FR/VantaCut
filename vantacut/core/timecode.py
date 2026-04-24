from __future__ import annotations

from dataclasses import dataclass


DEFAULT_TICKS_PER_SECOND = 1_000


@dataclass(frozen=True)
class Timebase:
    fps: int = 30
    ticks_per_second: int = DEFAULT_TICKS_PER_SECOND

    def seconds_to_ticks(self, seconds: float) -> int:
        return round(seconds * self.ticks_per_second)

    def ticks_to_seconds(self, ticks: int) -> float:
        return ticks / self.ticks_per_second

    def frames_to_ticks(self, frames: int) -> int:
        return round(frames * self.ticks_per_second / self.fps)

    def ticks_to_frames(self, ticks: int) -> int:
        return round(ticks * self.fps / self.ticks_per_second)

    def format_clock(self, ticks: int) -> str:
        total_ms = round(self.ticks_to_seconds(ticks) * 1000)
        hours, remainder = divmod(total_ms, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, milliseconds = divmod(remainder, 1_000)
        return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

    def parse_clock(self, value: str) -> int:
        hours_text, minutes_text, rest = value.strip().split(":")
        seconds_text, milliseconds_text = rest.split(".")
        total_ms = (
            int(hours_text) * 3_600_000
            + int(minutes_text) * 60_000
            + int(seconds_text) * 1_000
            + int(milliseconds_text)
        )
        return total_ms
