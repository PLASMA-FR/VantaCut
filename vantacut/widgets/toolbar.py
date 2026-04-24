from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label


class Toolbar(Horizontal):
    DEFAULT_CSS = """
    Toolbar {
        height: 3;
        padding: 0 1;
        align-vertical: middle;
        background: $panel;
        border-bottom: solid #39506c;
    }

    Toolbar Button {
        min-width: 10;
        margin-right: 1;
    }

    Toolbar Label {
        color: #8ea0b9;
        margin-right: 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("VantaCut", classes="toolbar-title")
        yield Button("New", id="action-new", variant="primary")
        yield Button("Open", id="action-open", variant="default")
        yield Button("Save", id="action-save", variant="default")
        yield Button("Import", id="action-import", variant="primary")
        yield Button("Preview", id="action-preview-focus", variant="default")
        yield Button("Insert", id="action-insert", variant="default")
        yield Button("Split", id="action-split", variant="default")
        yield Button("Export", id="action-export", variant="success")
        yield Button("Help", id="action-help", variant="default")
