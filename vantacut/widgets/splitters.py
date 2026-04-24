from __future__ import annotations

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget


class ResizeHandle(Widget, can_focus=True):
    DEFAULT_CSS = """
    ResizeHandle {
        width: 1;
        background: #39506c;
    }

    ResizeHandle:hover,
    ResizeHandle.-dragging,
    ResizeHandle:focus {
        background: $accent;
    }
    """

    dragging = reactive(False)

    class Delta(Message):
        def __init__(self, handle: "ResizeHandle", delta: int) -> None:
            self.delta = delta
            super().__init__()

    def __init__(self, slot: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.slot = slot
        self._last_x = 0

    def on_mouse_down(self, event) -> None:  # type: ignore[no-untyped-def]
        self.capture_mouse()
        self.dragging = True
        self.add_class("-dragging")
        self._last_x = event.screen_x
        event.stop()

    def on_mouse_move(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self.dragging:
            return
        delta = event.screen_x - self._last_x
        if delta:
            self._last_x = event.screen_x
            self.post_message(self.Delta(self, delta))
        event.stop()

    def on_mouse_up(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.dragging:
            self.capture_mouse(False)
            self.dragging = False
            self.remove_class("-dragging")
        event.stop()
