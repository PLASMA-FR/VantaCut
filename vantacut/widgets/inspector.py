from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, Label, Select

from vantacut.models.timeline import ScaleMode, TransformState


class InspectorPanel(Vertical):
    DEFAULT_CSS = """
    InspectorPanel {
        padding: 1;
    }

    InspectorPanel Label.section {
        margin-top: 1;
        color: $accent;
    }

    InspectorPanel Button {
        margin-right: 1;
    }
    """

    class ApplyTransform(Message):
        def __init__(
            self,
            panel: "InspectorPanel",
            crop_x: str,
            crop_y: str,
            crop_width: str,
            crop_height: str,
            scale_mode: str,
            pos_x: str,
            pos_y: str,
            rotation: str,
            opacity: str,
        ) -> None:
            self.crop_x = crop_x
            self.crop_y = crop_y
            self.crop_width = crop_width
            self.crop_height = crop_height
            self.scale_mode = scale_mode
            self.pos_x = pos_x
            self.pos_y = pos_y
            self.rotation = rotation
            self.opacity = opacity
            super().__init__()

    class ResetTransform(Message):
        pass

    class CopyTransform(Message):
        pass

    class PasteTransform(Message):
        pass

    class CropPreset(Message):
        def __init__(self, panel: "InspectorPanel", preset: str) -> None:
            self.preset = preset
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("Clip Inspector", classes="panel-title")
        yield Label("Crop", classes="section")
        with Horizontal():
            yield Input(placeholder="x", id="inspector-crop-x")
            yield Input(placeholder="y", id="inspector-crop-y")
            yield Input(placeholder="width", id="inspector-crop-width")
            yield Input(placeholder="height", id="inspector-crop-height")
        with Horizontal():
            yield Button("16:9", id="preset-16-9")
            yield Button("1:1", id="preset-1-1")
            yield Button("9:16", id="preset-9-16")
            yield Button("Center Crop", id="preset-center")
        yield Label("Transform", classes="section")
        with Horizontal():
            yield Select(
                [(mode.value, mode.value) for mode in ScaleMode],
                value=ScaleMode.FIT.value,
                id="inspector-scale-mode",
            )
        with Horizontal():
            yield Input(placeholder="pos x", id="inspector-pos-x")
            yield Input(placeholder="pos y", id="inspector-pos-y")
            yield Input(placeholder="rotation", id="inspector-rotation")
            yield Input(placeholder="opacity", id="inspector-opacity")
        with Horizontal():
            yield Button("Apply", id="inspector-apply", variant="primary")
            yield Button("Reset", id="inspector-reset")
            yield Button("Copy", id="inspector-copy")
            yield Button("Paste", id="inspector-paste")

    def load_transform(self, transform: TransformState | None) -> None:
        transform = transform or TransformState()
        self.query_one("#inspector-crop-x", Input).value = str(transform.crop_x)
        self.query_one("#inspector-crop-y", Input).value = str(transform.crop_y)
        self.query_one("#inspector-crop-width", Input).value = str(transform.crop_width)
        self.query_one("#inspector-crop-height", Input).value = str(transform.crop_height)
        self.query_one("#inspector-scale-mode", Select).value = transform.scale_mode.value
        self.query_one("#inspector-pos-x", Input).value = str(transform.position_x)
        self.query_one("#inspector-pos-y", Input).value = str(transform.position_y)
        self.query_one("#inspector-rotation", Input).value = str(transform.rotation)
        self.query_one("#inspector-opacity", Input).value = str(transform.opacity)

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "inspector-apply":
            self.post_message(
                self.ApplyTransform(
                    self,
                    self.query_one("#inspector-crop-x", Input).value,
                    self.query_one("#inspector-crop-y", Input).value,
                    self.query_one("#inspector-crop-width", Input).value,
                    self.query_one("#inspector-crop-height", Input).value,
                    str(self.query_one("#inspector-scale-mode", Select).value),
                    self.query_one("#inspector-pos-x", Input).value,
                    self.query_one("#inspector-pos-y", Input).value,
                    self.query_one("#inspector-rotation", Input).value,
                    self.query_one("#inspector-opacity", Input).value,
                )
            )
        elif event.button.id == "inspector-reset":
            self.post_message(self.ResetTransform())
        elif event.button.id == "inspector-copy":
            self.post_message(self.CopyTransform())
        elif event.button.id == "inspector-paste":
            self.post_message(self.PasteTransform())
        elif event.button.id and event.button.id.startswith("preset-"):
            preset = event.button.id.replace("preset-", "")
            self.post_message(self.CropPreset(self, preset))

    @on(Input.Submitted)
    def on_input_submitted(self) -> None:
        self.post_message(
            self.ApplyTransform(
                self,
                self.query_one("#inspector-crop-x", Input).value,
                self.query_one("#inspector-crop-y", Input).value,
                self.query_one("#inspector-crop-width", Input).value,
                self.query_one("#inspector-crop-height", Input).value,
                str(self.query_one("#inspector-scale-mode", Select).value),
                self.query_one("#inspector-pos-x", Input).value,
                self.query_one("#inspector-pos-y", Input).value,
                self.query_one("#inspector-rotation", Input).value,
                self.query_one("#inspector-opacity", Input).value,
            )
        )

