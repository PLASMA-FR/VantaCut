from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, ListItem, ListView, Static

from vantacut.models.project import Project


class ProjectBrowser(Vertical):
    class RecentProjectSelected(Message):
        def __init__(self, browser: ProjectBrowser, path: str) -> None:
            super().__init__()
            self.browser = browser
            self.path = path

        @property
        def control(self) -> ProjectBrowser:
            return self.browser

    DEFAULT_CSS = """
    ProjectBrowser {
        padding: 1;
    }

    ProjectBrowser ListView {
        margin-top: 1;
        height: 1fr;
    }

    ProjectBrowser .recent-title {
        margin-top: 1;
        color: $accent;
    }

    ProjectBrowser .recent-empty {
        color: #8ea0b9;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._recent_paths: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static("", id="project-summary")
        yield Label("Recent Projects", classes="recent-title")
        yield ListView(id="recent-projects")

    def set_project(self, project: Project, recent: list[str]) -> None:
        project_path = project.path or "(unsaved)"
        project_folder = str(project_path)
        if project.path is not None:
            project_folder = str(Path(project.path).expanduser().resolve().parent)
        summary = (
            f"Project: {project.name}\n"
            f"Project File: {project_path}\n"
            f"Project Folder: {project_folder}\n"
            f"Resolution: {project.settings.width}x{project.settings.height}\n"
            f"FPS: {project.settings.fps}\n"
            f"Assets: {len(project.assets)}\n"
            f"Tracks: {len(project.tracks)}\n"
            f"Subtitle cues: {len(project.subtitles)}"
        )
        self.query_one("#project-summary", Static).update(summary)
        list_view = self.query_one("#recent-projects", ListView)
        list_view.clear()
        self._recent_paths = recent[:10]
        if not self._recent_paths:
            list_view.append(ListItem(Static("No recent projects.", classes="recent-empty")))
            return
        for path in self._recent_paths:
            list_view.append(ListItem(Static(path)))

    @on(ListView.Selected, "#recent-projects")
    def on_recent_project_selected(self, event: ListView.Selected) -> None:
        if 0 <= event.index < len(self._recent_paths):
            self.post_message(self.RecentProjectSelected(self, self._recent_paths[event.index]))
