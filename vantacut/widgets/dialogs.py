from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static


class FileBrowserDialog(ModalScreen[str | None]):
    DEFAULT_CSS = """
    FileBrowserDialog {
        align: center middle;
    }

    #browser-dialog {
        width: 80%;
        height: 80%;
        background: $panel;
        border: round #93d4ff;
        padding: 1;
    }

    #browser-actions {
        height: 3;
        margin-top: 1;
    }

    #browser-shortcuts {
        height: 3;
        margin-top: 1;
    }

    FileBrowserDialog DirectoryTree {
        height: 1fr;
        border: round #39506c;
        margin-top: 1;
    }

    FileBrowserDialog Input {
        margin-top: 1;
    }

    #browser-feedback {
        margin-top: 1;
        color: #8ea0b9;
        height: auto;
    }
    """

    def __init__(
        self,
        title: str,
        start_path: str | None = None,
        *,
        allow_files: bool = True,
        allow_directories: bool = True,
        project_path: str | None = None,
    ) -> None:
        super().__init__()
        self.title = title
        self.allow_files = allow_files
        self.allow_directories = allow_directories
        self.start_path = self._normalize_start_path(start_path)
        self.project_path = self._normalize_optional_path(project_path)

    def compose(self) -> ComposeResult:
        with Vertical(id="browser-dialog"):
            yield Label(self.title)
            yield Input(str(self.start_path), id="browser-path")
            yield DirectoryTree(str(self.start_path), id="browser-tree")
            with Horizontal(id="browser-shortcuts"):
                yield Button("Home", id="browser-home")
                yield Button("Root", id="browser-root")
                if self.project_path is not None:
                    yield Button("Project", id="browser-project")
            with Horizontal(id="browser-actions"):
                yield Button("Cancel", id="browser-cancel")
                yield Button("Choose", id="browser-choose", variant="primary")
            yield Static(self._selection_hint(), id="browser-feedback")

    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.query_one("#browser-path", Input).value = str(event.path)

    @on(DirectoryTree.DirectorySelected)
    def on_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.query_one("#browser-path", Input).value = str(event.path)

    @on(Button.Pressed, "#browser-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted, "#browser-path")
    def on_path_submitted(self, event: Input.Submitted) -> None:
        self._browse_to(event.value)

    @on(Button.Pressed, "#browser-home")
    def go_home(self) -> None:
        self._browse_to(Path.home())

    @on(Button.Pressed, "#browser-root")
    def go_root(self) -> None:
        self._browse_to(Path("/"))

    @on(Button.Pressed, "#browser-project")
    def go_project(self) -> None:
        if self.project_path is not None:
            self._browse_to(self.project_path)

    @on(Button.Pressed, "#browser-choose")
    def choose(self) -> None:
        raw_value = self.query_one("#browser-path", Input).value.strip()
        if not raw_value:
            self._set_feedback("Enter a path or select an item in the tree.")
            return
        path = Path(raw_value).expanduser()
        try:
            resolved = path.resolve()
        except FileNotFoundError:
            resolved = path
        if not resolved.exists():
            self._set_feedback(f"Path does not exist: {resolved}")
            return
        if resolved.is_file() and not self.allow_files:
            self._set_feedback("Select a folder for this action.")
            return
        if resolved.is_dir() and not self.allow_directories:
            self._set_feedback("Select a file for this action.")
            return
        self.dismiss(str(resolved))

    def _browse_to(self, target: str | Path) -> None:
        path = Path(target).expanduser()
        if not path.exists():
            self._set_feedback(f"Path does not exist: {path}")
            return
        browse_root = path if path.is_dir() else path.parent
        tree = self.query_one("#browser-tree", DirectoryTree)
        tree.path = browse_root.resolve()
        self.query_one("#browser-path", Input).value = str(path.resolve())
        self._set_feedback(self._selection_hint())

    def _selection_hint(self) -> str:
        if self.allow_files and self.allow_directories:
            return "Select a file or folder. Press Enter in the path field to jump there."
        if self.allow_files:
            return "Select a file. Press Enter in the path field to jump there."
        return "Select a folder. Press Enter in the path field to jump there."

    def _set_feedback(self, message: str) -> None:
        self.query_one("#browser-feedback", Static).update(message)

    def _normalize_start_path(self, path: str | None) -> Path:
        raw = Path(path or Path.home()).expanduser()
        return self._normalize_existing_path(raw)

    def _normalize_optional_path(self, path: str | None) -> Path | None:
        if path is None:
            return None
        return self._normalize_existing_path(Path(path).expanduser())

    def _normalize_existing_path(self, path: Path) -> Path:
        candidate = path
        if not candidate.exists():
            candidate = candidate.parent if candidate.parent.exists() else Path.home()
        if candidate.is_file():
            candidate = candidate.parent
        return candidate.resolve()


class TextPromptDialog(ModalScreen[str | None]):
    DEFAULT_CSS = """
    TextPromptDialog {
        align: center middle;
    }

    #prompt-dialog {
        width: 70;
        height: 11;
        background: $panel;
        border: round #93d4ff;
        padding: 1 2;
    }

    #prompt-actions {
        height: 3;
        margin-top: 1;
    }
    """

    def __init__(self, title: str, placeholder: str, value: str = "") -> None:
        super().__init__()
        self.title = title
        self.placeholder = placeholder
        self.value = value

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-dialog"):
            yield Label(self.title)
            yield Input(value=self.value, placeholder=self.placeholder, id="prompt-input")
            with Horizontal(id="prompt-actions"):
                yield Button("Cancel", id="prompt-cancel")
                yield Button("OK", id="prompt-ok", variant="primary")

    @on(Button.Pressed, "#prompt-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#prompt-ok")
    def submit(self) -> None:
        self.dismiss(self.query_one("#prompt-input", Input).value.strip() or None)
