from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, ListItem, ListView, Static


class HelpOverlayScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    HelpOverlayScreen {
        align: center middle;
    }

    #help-overlay {
        width: 90%;
        height: 90%;
        padding: 2;
        background: $panel;
        border: round #93d4ff;
    }
    """

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(
                "VantaCut Controls\n\n"
                "Timeline\n"
                "- Click empty space to move the playhead\n"
                "- Click a clip to select it\n"
                "- Drag clip bodies to move\n"
                "- Drag clip edges to trim\n"
                "- Ctrl+Wheel zooms and Wheel scrolls\n\n"
                "Media + Project\n"
                "- New lets you create a project by choosing a folder\n"
                "- Import media from anywhere on the machine\n"
                "- Selecting media opens a source preview when mpv is available\n"
                "- Select an asset and press I to insert at the playhead\n"
                "- Save and reopen projects from the toolbar\n\n"
                "Environment\n"
                "- Run `PYTHONPATH=.deps python3 -m vantacut.doctor` before manual testing\n"
                "- Install mpv for preview and ffmpeg/ffprobe for export and probing\n\n"
                "Subtitles\n"
                "- Use the Subtitles tab for cue editing, import, and export\n"
                "- Selecting a cue jumps the playhead and syncs preview when possible\n\n"
                "Global\n"
                "- Ctrl+P command palette\n"
                "- Ctrl+Z / Ctrl+Y undo and redo\n"
                "- Ctrl+E export\n"
                "- Ctrl+. cancel export\n"
                "- Ctrl+Shift+R recover autosave\n"
            ),
            Button("Close", id="help-close"),
            id="help-overlay",
        )

    @on(Button.Pressed, "#help-close")
    def close(self) -> None:
        self.dismiss(None)


class CommandPaletteScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    CommandPaletteScreen {
        align: center top;
    }

    #command-palette {
        width: 70;
        height: 24;
        margin-top: 2;
        padding: 1;
        background: $panel;
        border: round #93d4ff;
    }
    """

    def __init__(self, commands: list[tuple[str, str]]) -> None:
        super().__init__()
        self.commands = commands

    def compose(self) -> ComposeResult:
        yield Vertical(
            Input(placeholder="Filter commands", id="command-filter"),
            ListView(id="command-list"),
            Button("Close", id="command-close"),
            id="command-palette",
        )

    def on_mount(self) -> None:
        self._refresh("")

    @on(Input.Changed, "#command-filter")
    def on_filter_changed(self, event: Input.Changed) -> None:
        self._refresh(event.value)

    @on(ListView.Selected, "#command-list")
    def on_command_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            self.dismiss(event.item.id)

    @on(Button.Pressed, "#command-close")
    def close(self) -> None:
        self.dismiss(None)

    def _refresh(self, query: str) -> None:
        list_view = self.query_one("#command-list", ListView)
        list_view.clear()
        lowered = query.lower()
        for label, action in self.commands:
            if lowered and lowered not in label.lower():
                continue
            list_view.append(ListItem(Static(label), id=action))
