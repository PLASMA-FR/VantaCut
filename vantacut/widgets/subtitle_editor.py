from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Input, Label, TextArea


@dataclass(slots=True)
class SubtitleRow:
    cue_id: str
    start: str
    end: str
    text: str
    warning: str


class SubtitleEditor(Vertical):
    DEFAULT_CSS = """
    SubtitleEditor {
        padding: 1;
    }

    SubtitleEditor DataTable {
        height: 1fr;
        margin: 1 0;
    }

    SubtitleEditor Button {
        margin-right: 1;
    }

    #subtitle-warning {
        color: #ffb347;
        margin-top: 1;
    }
    """

    class CueSelected(Message):
        def __init__(self, editor: "SubtitleEditor", cue_id: str) -> None:
            self.cue_id = cue_id
            super().__init__()

    class AddCue(Message):
        pass

    class SaveCue(Message):
        def __init__(self, editor: "SubtitleEditor", cue_id: str | None, start: str, end: str, text: str) -> None:
            self.cue_id = cue_id
            self.start = start
            self.end = end
            self.text = text
            super().__init__()

    class DeleteCue(Message):
        def __init__(self, editor: "SubtitleEditor", cue_id: str | None) -> None:
            self.cue_id = cue_id
            super().__init__()

    class SplitCue(Message):
        def __init__(self, editor: "SubtitleEditor", cue_id: str | None) -> None:
            self.cue_id = cue_id
            super().__init__()

    class MergeCue(Message):
        def __init__(self, editor: "SubtitleEditor", cue_id: str | None) -> None:
            self.cue_id = cue_id
            super().__init__()

    class ShiftCue(Message):
        def __init__(self, editor: "SubtitleEditor", cue_id: str | None, delta_ms: int) -> None:
            self.cue_id = cue_id
            self.delta_ms = delta_ms
            super().__init__()

    class SetCueStart(Message):
        def __init__(self, editor: "SubtitleEditor", cue_id: str | None) -> None:
            self.cue_id = cue_id
            super().__init__()

    class SetCueEnd(Message):
        def __init__(self, editor: "SubtitleEditor", cue_id: str | None) -> None:
            self.cue_id = cue_id
            super().__init__()

    class MoveCueToPlayhead(Message):
        def __init__(self, editor: "SubtitleEditor", cue_id: str | None) -> None:
            self.cue_id = cue_id
            super().__init__()

    class ImportSrt(Message):
        pass

    class ExportSrt(Message):
        pass

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.current_cue_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("Subtitle Cues", classes="panel-title")
        with Horizontal():
            yield Button("Import SRT", id="subtitle-import")
            yield Button("Export SRT", id="subtitle-export")
            yield Button("Add Cue", id="subtitle-add")
            yield Button("Delete", id="subtitle-delete")
        yield DataTable(id="subtitle-table")
        with Horizontal():
            yield Input(placeholder="Start 00:00:00.000", id="subtitle-start")
            yield Input(placeholder="End 00:00:00.000", id="subtitle-end")
            yield Input(value="250", placeholder="Shift ms", id="subtitle-shift")
        yield TextArea("", id="subtitle-text")
        with Horizontal():
            yield Button("Save Cue", id="subtitle-save", variant="primary")
            yield Button("Split", id="subtitle-split")
            yield Button("Merge", id="subtitle-merge")
            yield Button("Start=Playhead", id="subtitle-start-playhead")
            yield Button("End=Playhead", id="subtitle-end-playhead")
            yield Button("Move To Playhead", id="subtitle-move-playhead")
            yield Button("Shift -", id="subtitle-shift-left")
            yield Button("Shift +", id="subtitle-shift-right")
        yield Label("", id="subtitle-warning")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Start", "End", "Text", "Warn")

    def load_cues(self, rows: list[SubtitleRow], selected_cue_id: str | None, warning_text: str) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=False)
        for row in rows:
            table.add_row(row.start, row.end, row.text, row.warning, key=row.cue_id)
        self.current_cue_id = selected_cue_id
        self.query_one("#subtitle-warning", Label).update(warning_text)

    def populate_editor(self, start: str, end: str, text: str) -> None:
        self.query_one("#subtitle-start", Input).value = start
        self.query_one("#subtitle-end", Input).value = end
        self.query_one("#subtitle-text", TextArea).text = text

    @on(DataTable.RowSelected, "#subtitle-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        self.current_cue_id = str(event.row_key)
        self.post_message(self.CueSelected(self, self.current_cue_id))

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        cue_id = self.current_cue_id
        if event.button.id == "subtitle-import":
            self.post_message(self.ImportSrt())
        elif event.button.id == "subtitle-export":
            self.post_message(self.ExportSrt())
        elif event.button.id == "subtitle-add":
            self.post_message(self.AddCue())
        elif event.button.id == "subtitle-delete":
            self.post_message(self.DeleteCue(self, cue_id))
        elif event.button.id == "subtitle-save":
            self.post_message(
                self.SaveCue(
                    self,
                    cue_id,
                    self.query_one("#subtitle-start", Input).value,
                    self.query_one("#subtitle-end", Input).value,
                    self.query_one("#subtitle-text", TextArea).text,
                )
            )
        elif event.button.id == "subtitle-split":
            self.post_message(self.SplitCue(self, cue_id))
        elif event.button.id == "subtitle-merge":
            self.post_message(self.MergeCue(self, cue_id))
        elif event.button.id == "subtitle-start-playhead":
            self.post_message(self.SetCueStart(self, cue_id))
        elif event.button.id == "subtitle-end-playhead":
            self.post_message(self.SetCueEnd(self, cue_id))
        elif event.button.id == "subtitle-move-playhead":
            self.post_message(self.MoveCueToPlayhead(self, cue_id))
        elif event.button.id == "subtitle-shift-left":
            self.post_message(self.ShiftCue(self, cue_id, -self._shift_amount()))
        elif event.button.id == "subtitle-shift-right":
            self.post_message(self.ShiftCue(self, cue_id, self._shift_amount()))

    def _shift_amount(self) -> int:
        raw = self.query_one("#subtitle-shift", Input).value.strip() or "250"
        try:
            return int(raw)
        except ValueError:
            return 250
