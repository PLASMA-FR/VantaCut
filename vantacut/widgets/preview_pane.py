from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.text import Text
from textual.widgets import Static


class PreviewPane(Static):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.frame: RenderableType = Text(
            "\nImport media or select a clip to render a terminal preview.",
            style="dim #8ea0b9",
            justify="center",
        )
        self.backend = "waiting"
        self.target = "No preview source"
        self.status = "preview offline"
        self.note = "Video and images render directly in the terminal when mpv transport is unavailable."

    def preview_dimensions(self) -> tuple[int, int]:
        width = max(28, self.size.width - 2)
        height = max(8, self.size.height - 3)
        return width, height

    def set_preview(
        self,
        *,
        frame: RenderableType | None = None,
        backend: str,
        target: str,
        status: str,
        note: str,
    ) -> None:
        if frame is not None:
            self.frame = frame
        self.backend = backend
        self.target = target
        self.status = status
        self.note = note
        self.update(self._renderable())

    def _renderable(self) -> Group:
        header = Text()
        header.append(" Terminal Preview", style="bold #d7f1ff")
        header.append(f"   Backend: {self.backend}", style="#8ea0b9")

        footer = Text()
        footer.append(self._clamp(f"Target: {self.target}", 28), style="#d7f1ff")
        footer.append("   ")
        footer.append(self._clamp(self.status, 34), style="#8ea0b9")
        footer.append("   ")
        footer.append(self._clamp(self.note, 48), style="dim #8ea0b9")
        return Group(
            header,
            Align.center(self.frame),
            footer,
        )

    def _clamp(self, value: str, reserve: int) -> str:
        available = max(12, self.size.width - reserve)
        if len(value) <= available:
            return value
        return value[: max(9, available - 1)] + "…"
