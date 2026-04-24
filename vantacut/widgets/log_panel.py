from __future__ import annotations

from textual.widgets import Static


class LogPanel(Static):
    DEFAULT_CSS = """
    LogPanel {
        padding: 1;
        overflow-y: auto;
    }
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._lines: list[str] = []

    def append_line(self, text: str) -> None:
        self._lines.append(text)
        self.update("\n".join(self._lines))

    def clear_logs(self) -> None:
        self._lines.clear()
        self.update("")
