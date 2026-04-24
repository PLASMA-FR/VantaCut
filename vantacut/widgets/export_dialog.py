from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select

from vantacut.export.command_builder import ExportOptions
from vantacut.export.presets import preset_options


class ExportDialog(ModalScreen[ExportOptions | None]):
    DEFAULT_CSS = """
    ExportDialog {
        align: center middle;
    }

    #export-dialog {
        width: 72;
        height: 18;
        padding: 1 2;
        background: $panel;
        border: round #93d4ff;
    }

    ExportDialog Input,
    ExportDialog Select,
    ExportDialog Checkbox {
        margin-top: 1;
    }
    """

    def __init__(self, output_path: str) -> None:
        super().__init__()
        self.output_path = output_path

    def compose(self) -> ComposeResult:
        with Vertical(id="export-dialog"):
            yield Label("Export Project")
            yield Input(value=self.output_path, id="export-path", placeholder="output.mp4")
            yield Select(preset_options(), value="1080p", id="export-preset")
            yield Checkbox("Overwrite output", value=True, id="export-overwrite")
            yield Checkbox("Burn in subtitles", value=True, id="export-burn")
            yield Checkbox("Debug command preview", value=True, id="export-debug")
            with Horizontal():
                yield Button("Cancel", id="export-cancel")
                yield Button("Start Export", id="export-start", variant="primary")

    @on(Button.Pressed, "#export-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#export-start")
    def submit(self) -> None:
        self.dismiss(
            ExportOptions(
                output_path=self.query_one("#export-path", Input).value.strip(),
                preset_name=str(self.query_one("#export-preset", Select).value),
                overwrite=self.query_one("#export-overwrite", Checkbox).value,
                burn_subtitles=self.query_one("#export-burn", Checkbox).value,
                debug_mode=self.query_one("#export-debug", Checkbox).value,
            )
        )

