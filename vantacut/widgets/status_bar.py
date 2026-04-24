from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label


class StatusBar(Horizontal):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
        background: $surface;
        color: $foreground;
        border-top: solid #39506c;
        padding: 0 1;
    }

    StatusBar > Label {
        width: 1fr;
    }

    #status-center {
        text-align: center;
        color: $accent;
    }

    #status-right {
        text-align: right;
        color: #8ea0b9;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Ready", id="status-left")
        yield Label("Space Play/Pause   Drag Resize   Ctrl+Wheel Zoom", id="status-center")
        yield Label("Preview offline", id="status-right")

    def set_left(self, value: str) -> None:
        self.query_one("#status-left", Label).update(value)

    def set_center(self, value: str) -> None:
        self.query_one("#status-center", Label).update(value)

    def set_right(self, value: str) -> None:
        self.query_one("#status-right", Label).update(value)
