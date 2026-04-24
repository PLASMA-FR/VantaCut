from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class PreviewState:
    connected: bool = False
    process_running: bool = False
    playing: bool = False
    loaded_path: str | None = None
    position_seconds: float = 0.0
    last_error: str | None = None

    def status_text(self) -> str:
        if self.last_error and not self.connected:
            return f"preview error: {self.last_error}"
        if not self.connected:
            return "preview offline"
        mode = "playing" if self.playing else "paused"
        return f"preview {mode} @ {self.position_seconds:0.2f}s"


class PreviewController(ABC):
    def __init__(self) -> None:
        self.state = PreviewState()

    @abstractmethod
    async def connect(self) -> PreviewState: ...

    @abstractmethod
    async def load_file(self, path: str) -> PreviewState: ...

    @abstractmethod
    async def play(self) -> PreviewState: ...

    @abstractmethod
    async def pause(self) -> PreviewState: ...

    @abstractmethod
    async def toggle(self) -> PreviewState: ...

    @abstractmethod
    async def seek_absolute(self, seconds: float) -> PreviewState: ...

    @abstractmethod
    async def seek_relative(self, seconds: float) -> PreviewState: ...

    @abstractmethod
    async def frame_step(self) -> PreviewState: ...

    @abstractmethod
    async def frame_back_step(self) -> PreviewState: ...

    @abstractmethod
    async def query_position(self) -> PreviewState: ...

    @abstractmethod
    async def set_filters(self, filter_chain: str | None) -> PreviewState: ...

    @abstractmethod
    async def close(self) -> None: ...
