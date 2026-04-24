from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import time

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Label, ListView, Static, TabPane, TabbedContent

from vantacut.actions.command_stack import CommandStack, EditorSnapshot
from vantacut.core.environment import RuntimeEnvironment, detect_runtime_environment
from vantacut.export.command_builder import ExportCommandBuilder, ExportOptions
from vantacut.export.executor import ExportEvent, ExportExecutor
from vantacut.models.asset import AssetKind, MediaAsset
from vantacut.models.project import Project
from vantacut.models.timeline import ScaleMode, TrackKind, TransformState
from vantacut.preview.frame_renderer import PreviewFrameRenderer
from vantacut.preview.filters import build_preview_filter_chain
from vantacut.preview.mpv import MpvPreviewController
from vantacut.preview.sync import compute_preview_seek_seconds
from vantacut.services.autosave import AutosaveService
from vantacut.services.media_probe import MediaProbeService
from vantacut.services.project_store import ProjectStore
from vantacut.services.state import EditorState
from vantacut.subtitles.engine import SubtitleEngine
from vantacut.subtitles.srt import export_srt, parse_srt
from vantacut.theme import build_theme
from vantacut.timeline.engine import TimelineEngine
from vantacut.widgets.dialogs import FileBrowserDialog, TextPromptDialog
from vantacut.widgets.export_dialog import ExportDialog
from vantacut.widgets.inspector import InspectorPanel
from vantacut.widgets.log_panel import LogPanel
from vantacut.widgets.media_bin import MediaBin
from vantacut.widgets.overlays import CommandPaletteScreen, HelpOverlayScreen
from vantacut.widgets.preview_pane import PreviewPane
from vantacut.widgets.project_browser import ProjectBrowser
from vantacut.widgets.splitters import ResizeHandle
from vantacut.widgets.status_bar import StatusBar
from vantacut.widgets.subtitle_editor import SubtitleEditor, SubtitleRow
from vantacut.widgets.timeline import TimelineView
from vantacut.widgets.toolbar import Toolbar


class VantaCutApp(App[None]):
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+n", "new_project", "New Project"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("space", "toggle_play", "Play/Pause"),
        Binding("left", "step_left", "Step Left"),
        Binding("right", "step_right", "Step Right"),
        Binding("i", "insert_selected_asset", "Insert Clip"),
        Binding("s", "split_selected_clip", "Split"),
        Binding("delete", "ripple_delete_selected_clip", "Ripple Delete"),
        Binding("ctrl+z", "undo", "Undo"),
        Binding("ctrl+y", "redo", "Redo"),
        Binding("f", "toggle_follow_playhead", "Follow Playhead"),
        Binding("ctrl+e", "export_project", "Export"),
        Binding("ctrl+.", "cancel_export", "Cancel Export"),
        Binding("ctrl+p", "open_command_palette", "Command Palette"),
        Binding("f1", "show_help_overlay", "Help Overlay"),
        Binding("ctrl+shift+r", "recover_autosave", "Recover Autosave"),
        Binding("ctrl+shift+f", "toggle_preview_focus", "Focus Preview"),
        Binding("ctrl+1", "preview_quality_fast", "Preview Fast"),
        Binding("ctrl+2", "preview_quality_balanced", "Preview Balanced"),
        Binding("ctrl+3", "preview_quality_full", "Preview Full"),
        Binding("ctrl+shift+v", "toggle_preview_fill", "Fill Preview"),
        Binding("?", "toggle_help", "Help"),
    ]

    TITLE = "VantaCut"
    SUB_TITLE = "Desktop-like terminal video editor"

    def __init__(self) -> None:
        super().__init__()
        self.store = ProjectStore()
        self.autosave = AutosaveService(self.store)
        self.media_probe = MediaProbeService()
        self.timeline_engine = TimelineEngine()
        self.subtitle_engine = SubtitleEngine()
        self.preview = MpvPreviewController()
        self.frame_renderer = PreviewFrameRenderer()
        self.export_builder = ExportCommandBuilder()
        self.export_executor = ExportExecutor()
        self.command_stack = CommandStack()
        self.export_running = False
        self.copied_transform: TransformState | None = None
        self.preview_frame_note = (
            "Import media or select a clip to render a terminal preview."
        )
        self.preview_frame_backend = "waiting"
        self.preview_surface_seconds = 0.0
        self.preview_focus_mode = False
        self.preview_fit_mode = "contain"
        self.preview_quality = "balanced"
        self._preview_last_render_signature: tuple[object, ...] | None = None
        self._preview_last_render_monotonic = 0.0
        self.environment: RuntimeEnvironment = detect_runtime_environment(self.store._state_dir)
        self.state = EditorState(project=Project.empty("Untitled Project"))
        self.state.recent_projects = self.store.load_recent_projects()
        self.state.selected_clip_id = next(
            (
                clip.id
                for track in self.state.project.tracks
                for clip in track.clips
                if clip.selected
            ),
            None,
        )
        self.timeline_engine.select_clip(self.state.project, self.state.selected_clip_id)
        self.left_width = 32
        self.right_width = 34

    def compose(self) -> ComposeResult:
        with Vertical(id="root"):
            yield Toolbar(id="toolbar")
            with Horizontal(id="workspace"):
                with Container(id="left-pane", classes="pane"):
                    with TabbedContent():
                        with TabPane("Media"):
                            yield MediaBin(self.state.project.assets, id="media-bin")
                        with TabPane("Project"):
                            yield ProjectBrowser(id="project-browser")
                yield ResizeHandle(slot="left", id="resize-left")
                with Container(id="center-pane", classes="pane"):
                    with Vertical():
                        yield PreviewPane(id="preview-strip")
                        with Horizontal(id="transport"):
                            yield Button("◀◀", id="transport-back")
                            yield Button("▶", id="transport-play")
                            yield Button("▶▶", id="transport-forward")
                            yield Label(
                                "Scrub timeline or select media to refresh preview",
                                id="transport-label",
                            )
                        yield TimelineView(self.state, self.timeline_engine, id="timeline")
                yield ResizeHandle(slot="right", id="resize-right")
                with Container(id="right-pane", classes="pane"):
                    with TabbedContent():
                        with TabPane("Inspector"):
                            yield InspectorPanel(id="inspector")
                        with TabPane("Subtitles"):
                            yield SubtitleEditor(id="subtitle-editor")
                        with TabPane("Logs"):
                            yield LogPanel(id="log-panel")
                        with TabPane("Properties"):
                            yield Static(self._properties_summary(), id="properties-pane")
            yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.register_theme(build_theme())
        self.theme = "vantacut"
        self._apply_pane_widths()
        self._apply_preview_layout()
        self._refresh_ui()
        self.run_worker(self._start_preview(), group="preview-startup", exclusive=True)
        self.set_interval(0.5, self._request_preview_poll)
        self.set_interval(15, self._autosave_tick)
        self._sync_status("Ready. Press Ctrl+N to create a project or Ctrl+P for commands.")
        self._emit_environment_diagnostics()
        if self.autosave.has_recovery(self.state.project):
            self.notify(
                "Autosave recovery is available. Press Ctrl+Shift+R to load it.",
                title="Recovery available",
            )

    def _apply_pane_widths(self) -> None:
        self.query_one("#left-pane", Container).styles.width = self.left_width
        self.query_one("#right-pane", Container).styles.width = self.right_width
        self.query_one("#resize-left", ResizeHandle).styles.width = 1
        self.query_one("#resize-right", ResizeHandle).styles.width = 1

    def _preview_summary(self) -> str:
        clip_label = "No preview source"
        if self.preview.state.loaded_path:
            clip_label = Path(self.preview.state.loaded_path).name
        elif self.state.selected_asset_id:
            asset = self.state.project.asset(self.state.selected_asset_id)
            clip_label = asset.label if asset else self.state.selected_asset_id
        else:
            selected = self.state.selected_clip()
            if selected:
                asset = self.state.project.asset(selected.asset_id)
                clip_label = asset.label if asset else selected.asset_id
        return (
            "Preview Bridge\n"
            f"State: {self.state.preview_status}\n"
            f"Playhead: {self.state.timebase.format_clock(self.state.playhead)}\n"
            f"Target: {clip_label}\n"
            "Source-relative sync uses mpv JSON IPC."
        )

    def _transport_available(self) -> bool:
        return self.environment.unix_socket_ipc and self.environment.mpv.available

    def _frame_preview_available(self) -> bool:
        return self.environment.ffmpeg.available

    def _current_preview_asset(self) -> tuple[MediaAsset | None, float]:
        clip = self.state.selected_clip()
        if clip is not None:
            asset = self.state.project.asset(clip.asset_id)
            if asset is not None:
                return asset, compute_preview_seek_seconds(clip, self.state.playhead)
        if self.state.selected_asset_id:
            asset = self.state.project.asset(self.state.selected_asset_id)
            if asset is not None:
                return asset, 0.0
        return None, 0.0

    def _preview_target_label(self) -> str:
        asset, _ = self._current_preview_asset()
        return asset.label if asset is not None else "No preview source"

    def _asset_by_loaded_path(self, path: str | None) -> MediaAsset | None:
        if not path:
            return None
        try:
            target = Path(path).expanduser().resolve()
        except OSError:
            return None
        for asset in self.state.project.assets:
            try:
                if Path(asset.path).expanduser().resolve() == target:
                    return asset
            except OSError:
                continue
        return None

    def _transport_preview_target(self) -> tuple[MediaAsset | None, float, str | None]:
        asset = self._asset_by_loaded_path(self.preview.state.loaded_path)
        if asset is None:
            return None, 0.0, None
        filter_chain: str | None = None
        clip = self.state.selected_clip()
        if clip is not None:
            clip_asset = self.state.project.asset(clip.asset_id)
            if clip_asset is not None and clip_asset.id == asset.id:
                filter_chain = build_preview_filter_chain(
                    clip.transform,
                    self.state.project.settings,
                )
        return asset, max(0.0, self.preview.state.position_seconds), filter_chain

    def _preview_render_signature(
        self,
        asset: MediaAsset | None,
        seconds: float,
        filter_chain: str | None,
    ) -> tuple[object, ...]:
        width_cells, height_cells = self._preview_pane().preview_dimensions()
        return (
            asset.id if asset is not None else None,
            round(seconds, 2),
            filter_chain or "",
            width_cells,
            height_cells,
            self.preview_fit_mode,
            self.preview_quality,
        )

    async def _refresh_preview_surface_from_transport(self, force: bool = False) -> None:
        asset, seconds, filter_chain = self._transport_preview_target()
        if asset is None:
            return
        signature = self._preview_render_signature(asset, seconds, filter_chain)
        now = time.monotonic()
        if not force:
            if self._preview_last_render_signature == signature:
                return
            if self.preview.state.playing and now - self._preview_last_render_monotonic < 0.45:
                return
        await self._render_preview_frame(asset, seconds, filter_chain)

    def _compose_preview_status(self) -> str:
        if self.preview.state.connected:
            return self.preview.state.status_text()
        if self.preview_frame_backend.startswith("terminal"):
            return f"terminal preview @ {self.preview_surface_seconds:0.2f}s"
        if self._frame_preview_available():
            return "terminal preview ready"
        return self.preview.state.status_text()

    def _sync_preview_pane(self) -> None:
        backend = self.preview_frame_backend
        if self._transport_available():
            backend = f"{backend} + mpv transport" if backend != "waiting" else "mpv transport"
        self._preview_pane().set_preview(
            backend=backend,
            target=self._preview_target_label(),
            status=self.state.preview_status,
            note=self.preview_frame_note,
        )

    def _preview_placeholder_frame(self, title: str, message: str):
        from rich.text import Text

        frame = Text(justify="center")
        frame.append("\n")
        frame.append(f"{title}\n", style="bold #93d4ff")
        frame.append(message, style="dim #8ea0b9")
        return frame

    def _apply_preview_layout(self) -> None:
        preview = self._preview_pane()
        timeline = self._timeline()
        if self.preview_focus_mode:
            preview.styles.height = "1fr"
            timeline.styles.height = 9
        else:
            preview.styles.height = 18
            timeline.styles.height = "1fr"

    def _properties_summary(self) -> str:
        return (
            "Interaction map\n"
            "- Drag pane dividers to resize\n"
            "- Click empty timeline to move playhead\n"
            "- Drag clip bodies to move and edges to trim\n"
            "- New creates an empty project inside a chosen folder\n"
            "- Select media to preview source material before insertion\n"
            "- Select media then press I to insert at playhead\n"
            "- Ctrl+Shift+F toggles a larger preview-focused layout\n"
            "- Ctrl+Shift+V switches preview between contain and fill\n"
            "- Ctrl+1/2/3 select fast, balanced, or full preview quality\n"
            "- Terminal preview renders video, images, and audio waveforms in TTY sessions\n"
            "- Use the right-side tabs for subtitles, logs, and inspector tools\n"
            "- Ctrl+P opens the command palette\n"
            f"- State dir: {self.environment.state_dir}\n"
            f"- Unix socket IPC: {'ready' if self.environment.unix_socket_ipc else 'blocked'}\n"
            f"- mpv: {'ready' if self.environment.mpv.available else 'missing'}\n"
            f"- ffmpeg: {'ready' if self.environment.ffmpeg.available else 'missing'}\n"
            f"- ffprobe: {'ready' if self.environment.ffprobe.available else 'missing'}"
        )

    def _project_root(self) -> Path:
        if self.state.project.path:
            return Path(self.state.project.path).expanduser().resolve().parent
        return Path.home()

    def _default_project_file(self, folder: str | Path) -> Path:
        target = Path(folder).expanduser().resolve()
        base = "-".join(
            piece for piece in target.name.lower().replace("_", " ").split() if piece
        )
        stem = base or "vantacut-project"
        candidate = target / f"{stem}.vcut.json"
        index = 2
        while candidate.exists():
            candidate = target / f"{stem}-{index}.vcut.json"
            index += 1
        return candidate

    def _timeline(self) -> TimelineView:
        return self.query_one(TimelineView)

    def _preview_pane(self) -> PreviewPane:
        return self.query_one("#preview-strip", PreviewPane)

    def _log_panel(self) -> LogPanel:
        return self.query_one(LogPanel)

    def _sync_status(self, message: str) -> None:
        self.state.status = message
        status_bar = self.query_one(StatusBar)
        status_bar.set_left(message)
        status_bar.set_right(self.state.preview_status)
        self._sync_preview_pane()
        self._sync_project_browser()

    def _sync_project_browser(self) -> None:
        self.query_one(ProjectBrowser).set_project(
            self.state.project,
            self.state.recent_projects,
        )

    def _emit_environment_diagnostics(self) -> None:
        self._log_panel().append_line(f"State dir: {self.environment.state_dir}")
        self._log_panel().append_line(
            "unix_socket_ipc: "
            + ("ready" if self.environment.unix_socket_ipc else "blocked")
        )
        for dependency in self.environment.dependencies():
            self._log_panel().append_line(dependency.summary())
        missing = self.environment.missing()
        if not self.environment.unix_socket_ipc:
            self.notify(
                "Unix socket IPC is blocked here. VantaCut will use terminal frame preview instead of mpv transport.",
                title="Runtime capability",
                severity="warning",
            )
        if missing:
            self.notify(
                "Missing external tools: "
                + ", ".join(missing)
                + ". Install them to enable preview/export/probe.",
                title="Runtime dependencies",
                severity="warning",
            )

    def _sync_inspector(self) -> None:
        clip = self.state.selected_clip()
        self.query_one(InspectorPanel).load_transform(clip.transform if clip else None)

    def _sync_subtitles(self) -> None:
        editor = self.query_one(SubtitleEditor)
        timebase = self.state.timebase
        issues = self.subtitle_engine.validate(self.state.project)
        rows: list[SubtitleRow] = []
        warning_text = "Select a cue to edit timings and text."
        selected_cue = None
        if self.state.selected_cue_id:
            selected_cue = next(
                (
                    cue
                    for cue in self.state.project.subtitles
                    if cue.id == self.state.selected_cue_id
                ),
                None,
            )
        for cue in self.state.project.subtitles:
            cue_issues = issues.get(cue.id, [])
            warning = ", ".join(issue.message for issue in cue_issues[:1])
            rows.append(
                SubtitleRow(
                    cue_id=cue.id,
                    start=timebase.format_clock(cue.start),
                    end=timebase.format_clock(cue.end),
                    text=cue.text.replace("\n", " / "),
                    warning=warning,
                )
            )
        if selected_cue is not None:
            selected_issues = issues.get(selected_cue.id, [])
            if selected_issues:
                warning_text = " | ".join(issue.message for issue in selected_issues)
            editor.populate_editor(
                timebase.format_clock(selected_cue.start),
                timebase.format_clock(selected_cue.end),
                selected_cue.text,
            )
        else:
            editor.populate_editor("", "", "")
        editor.load_cues(rows, self.state.selected_cue_id, warning_text)

    def _refresh_ui(self) -> None:
        self._timeline().set_state(self.state)
        self.query_one(MediaBin).set_assets(self.state.project.assets)
        self._sync_preview_pane()
        self._sync_project_browser()
        self._sync_subtitles()
        self._sync_inspector()
        self.query_one(StatusBar).set_right(self.state.preview_status)

    def _capture_snapshot(self) -> EditorSnapshot:
        project_data = self.state.project.to_dict()
        project_data["updated_at"] = self.state.project.updated_at
        return EditorSnapshot(
            project_data=project_data,
            selected_asset_id=self.state.selected_asset_id,
            selected_clip_id=self.state.selected_clip_id,
            selected_cue_id=self.state.selected_cue_id,
            playhead=self.state.playhead,
        )

    def _restore_snapshot(self, snapshot: EditorSnapshot) -> None:
        self.state.project = Project.from_dict(snapshot.project_data)
        self.state.selected_asset_id = snapshot.selected_asset_id
        self.state.selected_clip_id = snapshot.selected_clip_id
        self.state.selected_cue_id = snapshot.selected_cue_id
        self.state.playhead = snapshot.playhead
        self.timeline_engine.select_clip(self.state.project, self.state.selected_clip_id)
        self.state.dirty = True
        self._refresh_ui()

    def _mutate(self, label: str, mutator):
        before = self._capture_snapshot()
        result = mutator()
        after = self._capture_snapshot()
        self.command_stack.push(label, before, after)
        if before != after:
            self.state.dirty = True
        return result

    def _ensure_preview_clip_for_playhead(self) -> None:
        current = self.state.selected_clip()
        if current and current.start <= self.state.playhead <= current.end:
            return
        try:
            track = self.state.project.track(TrackKind.VIDEO)
        except StopIteration:
            return
        clip = next(
            (item for item in track.clips if item.start <= self.state.playhead <= item.end),
            track.clips[0] if track.clips else None,
        )
        if clip is not None:
            self.state.selected_clip_id = clip.id
            self.timeline_engine.select_clip(self.state.project, clip.id)

    def action_toggle_play(self) -> None:
        self.run_worker(self._preview_toggle(), group="preview", exclusive=False)

    def action_new_project(self) -> None:
        self.run_worker(self._new_project_dialog(), group="dialogs", exclusive=True)

    def action_step_left(self) -> None:
        self.state.playhead = max(
            0, self.state.playhead - self.state.timebase.frames_to_ticks(1)
        )
        self._refresh_ui()
        self._sync_status("Stepped playhead backward by one frame.")
        self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    def action_step_right(self) -> None:
        self.state.playhead += self.state.timebase.frames_to_ticks(1)
        self._refresh_ui()
        self._sync_status("Stepped playhead forward by one frame.")
        self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    def action_insert_selected_asset(self) -> None:
        asset_id = self.state.selected_asset_id
        if not asset_id and self.state.project.assets:
            asset_id = self.state.project.assets[0].id
        if not asset_id:
            self.notify("No asset selected.", title="Insert skipped", severity="warning")
            return
        clip = self._mutate(
            "Insert clip",
            lambda: self.timeline_engine.insert_asset(
                self.state.project,
                asset_id,
                self.state.playhead,
            ),
        )
        self.state.selected_clip_id = clip.id
        self.timeline_engine.select_clip(self.state.project, clip.id)
        self._refresh_ui()
        self._sync_status(
            f"Inserted clip at {self.state.timebase.format_clock(clip.start)}."
        )

    def action_split_selected_clip(self) -> None:
        if not self.state.selected_clip_id:
            self.notify("Select a clip first.", title="Split skipped", severity="warning")
            return
        try:
            _, right = self._mutate(
                "Split clip",
                lambda: self.timeline_engine.split_clip(
                    self.state.project,
                    self.state.selected_clip_id,
                    self.state.playhead,
                ),
            )
        except ValueError as exc:
            self.notify(str(exc), title="Split skipped", severity="warning")
            return
        self.state.selected_clip_id = right.id
        self.timeline_engine.select_clip(self.state.project, right.id)
        self._refresh_ui()
        self._sync_status("Split selected clip at the playhead.")

    def action_ripple_delete_selected_clip(self) -> None:
        if not self.state.selected_clip_id:
            self.notify("Select a clip first.", title="Delete skipped", severity="warning")
            return
        shifted = self._mutate(
            "Ripple delete clip",
            lambda: self.timeline_engine.ripple_delete(
                self.state.project,
                self.state.selected_clip_id,
            ),
        )
        self.state.selected_clip_id = None
        self.timeline_engine.select_clip(self.state.project, None)
        self._refresh_ui()
        self._sync_status(f"Ripple deleted clip and closed {shifted / 1000:.2f}s.")

    def action_undo(self) -> None:
        snapshot = self.command_stack.undo()
        if snapshot is None:
            self._sync_status("Nothing to undo.")
            return
        self._restore_snapshot(snapshot)
        self._sync_status("Undid the last edit.")

    def action_redo(self) -> None:
        snapshot = self.command_stack.redo()
        if snapshot is None:
            self._sync_status("Nothing to redo.")
            return
        self._restore_snapshot(snapshot)
        self._sync_status("Redid the last edit.")

    def action_toggle_follow_playhead(self) -> None:
        self.state.follow_playhead = not self.state.follow_playhead
        mode = "enabled" if self.state.follow_playhead else "disabled"
        self._sync_status(f"Follow playhead {mode}.")

    def action_export_project(self) -> None:
        self.run_worker(self._open_export_dialog(), group="export-dialog", exclusive=True)

    def action_cancel_export(self) -> None:
        if not self.export_running:
            self._sync_status("No export is currently running.")
            return
        self.run_worker(self._cancel_export_async(), group="export-cancel", exclusive=True)

    def action_toggle_preview_focus(self) -> None:
        self.preview_focus_mode = not self.preview_focus_mode
        self._apply_preview_layout()
        self._refresh_ui()
        mode = "focused" if self.preview_focus_mode else "standard"
        self._sync_status(f"Preview layout switched to {mode} mode.")
        self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    def action_preview_quality_fast(self) -> None:
        self._set_preview_quality("fast")

    def action_preview_quality_balanced(self) -> None:
        self._set_preview_quality("balanced")

    def action_preview_quality_full(self) -> None:
        self._set_preview_quality("full")

    def action_toggle_preview_fill(self) -> None:
        self.preview_fit_mode = "fill" if self.preview_fit_mode == "contain" else "contain"
        self._preview_last_render_signature = None
        self._sync_status(f"Preview fit set to {self.preview_fit_mode}.")
        self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    def _set_preview_quality(self, quality: str) -> None:
        if self.preview_quality == quality:
            self._sync_status(f"Preview quality already set to {quality}.")
            return
        self.preview_quality = quality
        self._preview_last_render_signature = None
        self._sync_status(f"Preview quality set to {quality}.")
        self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    def action_toggle_help(self) -> None:
        self.notify(
            "Mouse: resize panes, click clips, drag move/trim, wheel scroll, Ctrl+wheel zoom. "
            "Keyboard: Ctrl+Shift+F focus preview, Ctrl+Shift+V fill preview, Ctrl+1/2/3 quality, Ctrl+P palette.",
            title="VantaCut Controls",
        )

    def action_open_command_palette(self) -> None:
        self.run_worker(self._open_command_palette(), group="command-palette", exclusive=True)

    def action_show_help_overlay(self) -> None:
        self.run_worker(
            self.push_screen_wait(HelpOverlayScreen()),
            group="help-overlay",
            exclusive=True,
        )

    def action_recover_autosave(self) -> None:
        if not self.autosave.has_recovery(self.state.project):
            self._sync_status("No autosave recovery is available.")
            return
        self.state.project = self.autosave.load(self.state.project)
        self.state.selected_clip_id = next(
            (
                clip.id
                for track in self.state.project.tracks
                for clip in track.clips
                if clip.selected
            ),
            None,
        )
        self.state.selected_asset_id = self._default_selected_asset_id()
        self.state.selected_cue_id = None
        self.timeline_engine.select_clip(self.state.project, self.state.selected_clip_id)
        self.command_stack.clear()
        self._refresh_ui()
        self._sync_status("Recovered project from autosave.")

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "action-new":
            self.action_new_project()
            return
        if button_id == "action-open":
            self.run_worker(self._open_project_dialog(), group="dialogs", exclusive=True)
            return
        if button_id == "action-save":
            self.run_worker(self._save_project_dialog(), group="dialogs", exclusive=True)
            return
        if button_id == "action-import":
            self.run_worker(self._import_media_dialog(), group="dialogs", exclusive=True)
            return
        if button_id == "action-preview-focus":
            self.action_toggle_preview_focus()
            return
        if button_id == "action-insert":
            self.action_insert_selected_asset()
            return
        if button_id == "action-split":
            self.action_split_selected_clip()
            return
        if button_id == "action-export":
            self.run_worker(self._open_export_dialog(), group="dialogs", exclusive=True)
            return
        if button_id == "transport-play":
            self.action_toggle_play()
            return
        if button_id == "transport-back":
            self.run_worker(self._preview_frame_back(), group="preview", exclusive=False)
            return
        if button_id == "transport-forward":
            self.run_worker(self._preview_frame_step(), group="preview", exclusive=False)
            return
        mapping = {
            "action-help": "Help overlay is available via F1 or Ctrl+P.",
        }
        if button_id == "action-help":
            self.action_show_help_overlay()
            return
        self._sync_status(mapping.get(button_id, "Action triggered."))

    @on(ResizeHandle.Delta)
    def on_resize_delta(self, event: ResizeHandle.Delta) -> None:
        screen_width = max(120, self.size.width)
        if event.handle.slot == "left":
            self.left_width = min(max(24, self.left_width + event.delta), screen_width - 70)
        else:
            self.right_width = min(
                max(28, self.right_width - event.delta), screen_width - self.left_width - 35
            )
        self._apply_pane_widths()
        self._sync_status(
            f"Panes resized: left {self.left_width} cols, right {self.right_width} cols."
        )

    @on(ListView.Highlighted, "#media-list")
    def on_media_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and event.item.id:
            self.state.selected_asset_id = event.item.id
            asset = self.state.project.asset(event.item.id)
            if asset:
                self._sync_status(f"Selected asset {asset.label} for insertion.")
                if asset.kind is not AssetKind.SUBTITLE:
                    self.run_worker(
                        self._preview_asset(asset),
                        group="preview",
                        exclusive=False,
                    )

    @on(ListView.Selected, "#media-list")
    def on_media_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            asset = self.state.project.asset(event.item.id)
            if asset is not None and asset.kind is not AssetKind.SUBTITLE:
                self.run_worker(
                    self._preview_asset(asset),
                    group="preview",
                    exclusive=False,
                )

    @on(ProjectBrowser.RecentProjectSelected)
    def on_recent_project_selected(self, event: ProjectBrowser.RecentProjectSelected) -> None:
        self._open_project_path(event.path)

    @on(TimelineView.PlayheadChanged)
    def on_timeline_playhead_changed(self, event: TimelineView.PlayheadChanged) -> None:
        self.state.playhead = event.time
        self._refresh_ui()
        self._sync_status(f"Playhead moved to {self.state.timebase.format_clock(event.time)}.")
        if self.state.follow_playhead:
            self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    @on(TimelineView.ClipSelected)
    def on_timeline_clip_selected(self, event: TimelineView.ClipSelected) -> None:
        self.state.selected_clip_id = event.clip_id
        self.timeline_engine.select_clip(self.state.project, event.clip_id)
        self._refresh_ui()
        if event.clip_id:
            self._sync_status(f"Selected clip {event.clip_id}.")
            self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    @on(TimelineView.ClipMoved)
    def on_timeline_clip_moved(self, event: TimelineView.ClipMoved) -> None:
        preview = self._mutate(
            "Move clip",
            lambda: self.timeline_engine.move_clip(
                self.state.project,
                event.preview.clip_id,
                event.preview.start,
                event.preview.track_id,
                self.state.playhead,
                0,
            ),
        )
        self.state.selected_clip_id = preview.clip_id
        self._refresh_ui()
        self._sync_status(
            f"Moved clip to {self.state.timebase.format_clock(preview.start)}."
        )
        if self.state.follow_playhead:
            self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    @on(TimelineView.ClipTrimmed)
    def on_timeline_clip_trimmed(self, event: TimelineView.ClipTrimmed) -> None:
        if event.edge == "left":
            preview = self._mutate(
                "Trim clip left",
                lambda: self.timeline_engine.trim_clip_left(
                    self.state.project,
                    event.preview.clip_id,
                    event.preview.start,
                    self.state.playhead,
                    0,
                ),
            )
            clock = preview.start
        else:
            preview = self._mutate(
                "Trim clip right",
                lambda: self.timeline_engine.trim_clip_right(
                    self.state.project,
                    event.preview.clip_id,
                    event.preview.end,
                    self.state.playhead,
                    0,
                ),
            )
            clock = preview.end
        self._refresh_ui()
        self._sync_status(
            f"Trimmed {event.edge} edge to {self.state.timebase.format_clock(clock)}."
        )
        if self.state.follow_playhead:
            self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    @on(TimelineView.ClipOpened)
    def on_timeline_clip_opened(self, event: TimelineView.ClipOpened) -> None:
        self.state.selected_clip_id = event.clip_id
        self.timeline_engine.select_clip(self.state.project, event.clip_id)
        self._refresh_ui()
        self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)
        self.notify("Loaded selected source into preview.", title="Clip Open")

    @on(InspectorPanel.ApplyTransform)
    def on_inspector_apply(self, event: InspectorPanel.ApplyTransform) -> None:
        clip = self.state.selected_clip()
        if clip is None:
            return

        def mutate() -> None:
            clip.transform.crop_x = int(event.crop_x or 0)
            clip.transform.crop_y = int(event.crop_y or 0)
            clip.transform.crop_width = int(event.crop_width or 0)
            clip.transform.crop_height = int(event.crop_height or 0)
            clip.transform.scale_mode = ScaleMode(event.scale_mode or ScaleMode.FIT.value)
            clip.transform.position_x = float(event.pos_x or 0)
            clip.transform.position_y = float(event.pos_y or 0)
            clip.transform.rotation = float(event.rotation or 0)
            clip.transform.opacity = float(event.opacity or 1)

        try:
            self._mutate("Apply transform", mutate)
        except ValueError:
            self.notify(
                "Inspector fields must contain numeric values.",
                title="Inspector error",
                severity="error",
            )
            return
        self._refresh_ui()
        self._sync_status("Applied clip transform settings.")
        self.run_worker(self._apply_preview_filters(), group="preview", exclusive=False)

    @on(InspectorPanel.ResetTransform)
    def on_inspector_reset(self, event: InspectorPanel.ResetTransform) -> None:
        clip = self.state.selected_clip()
        if clip is None:
            return
        self._mutate("Reset transform", lambda: setattr(clip, "transform", TransformState()))
        self._refresh_ui()
        self._sync_status("Reset clip transform settings.")
        self.run_worker(self._apply_preview_filters(), group="preview", exclusive=False)

    @on(InspectorPanel.CopyTransform)
    def on_inspector_copy(self, event: InspectorPanel.CopyTransform) -> None:
        clip = self.state.selected_clip()
        if clip is None:
            return
        self.copied_transform = deepcopy(clip.transform)
        self._sync_status("Copied transform settings from selected clip.")

    @on(InspectorPanel.PasteTransform)
    def on_inspector_paste(self, event: InspectorPanel.PasteTransform) -> None:
        clip = self.state.selected_clip()
        if clip is None or self.copied_transform is None:
            return
        self._mutate(
            "Paste transform",
            lambda: setattr(clip, "transform", deepcopy(self.copied_transform)),
        )
        self._refresh_ui()
        self._sync_status("Pasted transform settings onto selected clip.")
        self.run_worker(self._apply_preview_filters(), group="preview", exclusive=False)

    @on(InspectorPanel.CropPreset)
    def on_inspector_preset(self, event: InspectorPanel.CropPreset) -> None:
        clip = self.state.selected_clip()
        if clip is None:
            return
        source_w = self.state.project.settings.width
        source_h = self.state.project.settings.height

        def mutate() -> None:
            if event.preset == "16-9":
                ratio = 16 / 9
            elif event.preset == "1-1":
                ratio = 1.0
            elif event.preset == "9-16":
                ratio = 9 / 16
            else:
                clip.transform.crop_x = max(0, (source_w - clip.transform.crop_width) // 2)
                clip.transform.crop_y = max(0, (source_h - clip.transform.crop_height) // 2)
                return
            if source_w / source_h > ratio:
                crop_h = source_h
                crop_w = int(source_h * ratio)
            else:
                crop_w = source_w
                crop_h = int(source_w / ratio)
            clip.transform.crop_width = crop_w
            clip.transform.crop_height = crop_h
            clip.transform.crop_x = max(0, (source_w - crop_w) // 2)
            clip.transform.crop_y = max(0, (source_h - crop_h) // 2)

        self._mutate(f"Apply crop preset {event.preset}", mutate)
        self._refresh_ui()
        self._sync_status(f"Applied crop preset {event.preset.replace('-', ':')}.")
        self.run_worker(self._apply_preview_filters(), group="preview", exclusive=False)

    @on(SubtitleEditor.CueSelected)
    def on_subtitle_cue_selected(self, event: SubtitleEditor.CueSelected) -> None:
        self.state.selected_cue_id = event.cue_id
        cue = self.subtitle_engine.find_cue(self.state.project, event.cue_id)
        self.state.playhead = cue.start
        self._ensure_preview_clip_for_playhead()
        self._refresh_ui()
        self._sync_status(f"Selected subtitle cue at {self.state.timebase.format_clock(cue.start)}.")
        if self.state.follow_playhead:
            self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    @on(SubtitleEditor.AddCue)
    def on_subtitle_add_cue(self, event: SubtitleEditor.AddCue) -> None:
        cue = self._mutate(
            "Add subtitle cue",
            lambda: self.subtitle_engine.add_cue(
                self.state.project,
                self.state.playhead,
                self.state.playhead + 2_000,
            ),
        )
        self.state.selected_cue_id = cue.id
        self._refresh_ui()
        self._sync_status("Added new subtitle cue at the playhead.")

    @on(SubtitleEditor.SaveCue)
    def on_subtitle_save_cue(self, event: SubtitleEditor.SaveCue) -> None:
        try:
            start = self.state.timebase.parse_clock(event.start)
            end = self.state.timebase.parse_clock(event.end)
        except ValueError:
            self.notify(
                "Use HH:MM:SS.mmm timing format.",
                title="Subtitle edit failed",
                severity="error",
            )
            return
        if event.cue_id is None:
            cue = self._mutate(
                "Create subtitle cue",
                lambda: self.subtitle_engine.add_cue(self.state.project, start, end, event.text),
            )
        else:
            cue = self._mutate(
                "Edit subtitle cue",
                lambda: self.subtitle_engine.update_cue(
                    self.state.project, event.cue_id, start, end, event.text
                ),
            )
        self.state.selected_cue_id = cue.id
        self._refresh_ui()
        self._sync_status("Saved subtitle cue changes.")

    @on(SubtitleEditor.DeleteCue)
    def on_subtitle_delete_cue(self, event: SubtitleEditor.DeleteCue) -> None:
        if event.cue_id is None:
            return
        self._mutate(
            "Delete subtitle cue",
            lambda: self.subtitle_engine.delete_cue(self.state.project, event.cue_id),
        )
        if self.state.selected_cue_id == event.cue_id:
            self.state.selected_cue_id = None
        self._refresh_ui()
        self._sync_status("Deleted subtitle cue.")

    @on(SubtitleEditor.SplitCue)
    def on_subtitle_split_cue(self, event: SubtitleEditor.SplitCue) -> None:
        if event.cue_id is None:
            return
        _, right = self._mutate(
            "Split subtitle cue",
            lambda: self.subtitle_engine.split_cue(
                self.state.project, event.cue_id, self.state.playhead
            ),
        )
        self.state.selected_cue_id = right.id
        self._refresh_ui()
        self._sync_status("Split subtitle cue at the playhead.")

    @on(SubtitleEditor.MergeCue)
    def on_subtitle_merge_cue(self, event: SubtitleEditor.MergeCue) -> None:
        if event.cue_id is None:
            return
        try:
            merged = self._mutate(
                "Merge subtitle cue",
                lambda: self.subtitle_engine.merge_with_next(self.state.project, event.cue_id),
            )
        except ValueError as exc:
            self.notify(str(exc), title="Subtitle merge skipped", severity="warning")
            return
        self.state.selected_cue_id = merged.id
        self._refresh_ui()
        self._sync_status("Merged subtitle cue with the next cue.")

    @on(SubtitleEditor.ShiftCue)
    def on_subtitle_shift_cue(self, event: SubtitleEditor.ShiftCue) -> None:
        if event.cue_id is None:
            return
        cue = self._mutate(
            "Shift subtitle cue",
            lambda: self.subtitle_engine.shift_cue(
                self.state.project, event.cue_id, event.delta_ms
            ),
        )
        self.state.selected_cue_id = cue.id
        self.state.playhead = cue.start
        self._refresh_ui()
        self._sync_status(f"Shifted subtitle cue by {event.delta_ms}ms.")

    @on(SubtitleEditor.SetCueStart)
    def on_subtitle_set_start(self, event: SubtitleEditor.SetCueStart) -> None:
        if event.cue_id is None:
            return
        self._mutate(
            "Snap subtitle start",
            lambda: self.subtitle_engine.set_cue_start(
                self.state.project, event.cue_id, self.state.playhead
            ),
        )
        self._refresh_ui()
        self._sync_status("Snapped cue start to playhead.")

    @on(SubtitleEditor.SetCueEnd)
    def on_subtitle_set_end(self, event: SubtitleEditor.SetCueEnd) -> None:
        if event.cue_id is None:
            return
        self._mutate(
            "Snap subtitle end",
            lambda: self.subtitle_engine.set_cue_end(
                self.state.project, event.cue_id, self.state.playhead
            ),
        )
        self._refresh_ui()
        self._sync_status("Snapped cue end to playhead.")

    @on(SubtitleEditor.MoveCueToPlayhead)
    def on_subtitle_move_to_playhead(self, event: SubtitleEditor.MoveCueToPlayhead) -> None:
        if event.cue_id is None:
            return
        cue = self._mutate(
            "Move subtitle cue",
            lambda: self.subtitle_engine.move_cue_to_playhead(
                self.state.project, event.cue_id, self.state.playhead
            ),
        )
        self.state.selected_cue_id = cue.id
        self._refresh_ui()
        self._sync_status("Moved subtitle cue to playhead.")

    @on(SubtitleEditor.ImportSrt)
    def on_subtitle_import_srt(self, event: SubtitleEditor.ImportSrt) -> None:
        self.run_worker(self._subtitle_import_srt_dialog(), group="dialogs", exclusive=True)

    @on(SubtitleEditor.ExportSrt)
    def on_subtitle_export_srt(self, event: SubtitleEditor.ExportSrt) -> None:
        self.run_worker(self._subtitle_export_srt_dialog(), group="dialogs", exclusive=True)

    def on_mouse_move(self) -> None:  # type: ignore[no-untyped-def]
        timeline = self._timeline()
        if timeline.hover.track_id:
            timestamp = self.state.timebase.format_clock(timeline.hover.time)
            self.query_one(StatusBar).set_center(
                f"Hover {timestamp}   Zoom {self.state.zoom} c/s   Scroll {self.state.horizontal_scroll}s"
            )

    def save_demo_project(self) -> Path:
        path = Path("examples/sample_project.vcut.json")
        self.store.save(self.state.project, path)
        return path

    async def _new_project_dialog(self) -> None:
        chosen = await self.push_screen_wait(
            FileBrowserDialog(
                "Choose Project Folder",
                str(self._project_root()),
                allow_files=False,
                allow_directories=True,
                project_path=str(self._project_root()),
            )
        )
        if not chosen:
            self._sync_status("New project cancelled.")
            return
        folder = Path(chosen).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            self.notify(
                f"Folder not found: {folder}",
                title="New project failed",
                severity="error",
            )
            return
        target = self._default_project_file(folder)
        name = folder.name or "VantaCut Project"
        self.state.project = Project.empty(name=name, path=str(target))
        self.state.selected_asset_id = None
        self.state.selected_clip_id = None
        self.state.selected_cue_id = None
        self.state.playhead = 0
        self.command_stack.clear()
        self.store.save(self.state.project, target)
        self.autosave.clear(self.state.project)
        self.state.recent_projects = self.store.load_recent_projects()
        self.state.dirty = False
        self.preview.state.loaded_path = None
        self._refresh_ui()
        self._sync_status(f"Created project {self.state.project.name} in {folder}.")

    def _default_selected_asset_id(self) -> str | None:
        if self.state.selected_clip_id:
            clip = self.state.selected_clip()
            if clip is not None:
                return clip.asset_id
        return self.state.project.assets[0].id if self.state.project.assets else None

    def _open_project_path(self, chosen: str | Path) -> None:
        target = Path(chosen).expanduser().resolve()
        self.state.project = self.store.load(target)
        self.state.selected_clip_id = next(
            (
                clip.id
                for track in self.state.project.tracks
                for clip in track.clips
                if clip.selected
            ),
            None,
        )
        self.state.selected_asset_id = self._default_selected_asset_id()
        self.state.selected_cue_id = None
        self.state.recent_projects = self.store.load_recent_projects()
        self.timeline_engine.select_clip(self.state.project, self.state.selected_clip_id)
        self.state.playhead = 0
        self.state.dirty = False
        self.command_stack.clear()
        self._refresh_ui()
        self._sync_status(f"Opened project {target.name}.")
        if self.autosave.has_recovery(self.state.project):
            self.notify(
                "A newer autosave exists for this project. Press Ctrl+Shift+R to recover it.",
                title="Recovery available",
            )
        self.run_worker(self._sync_preview_with_selection(), group="preview", exclusive=False)

    async def _open_project_dialog(self) -> None:
        chosen = await self.push_screen_wait(
            FileBrowserDialog(
                "Open VantaCut Project",
                self.state.project.path or str(self._project_root()),
                allow_files=True,
                allow_directories=False,
                project_path=str(self._project_root()),
            )
        )
        if not chosen:
            self._sync_status("Open project cancelled.")
            return
        try:
            self._open_project_path(chosen)
        except FileNotFoundError:
            self.notify(f"File not found: {chosen}", title="Open failed", severity="error")
        except Exception as exc:  # noqa: BLE001
            self.notify(str(exc), title="Open failed", severity="error")

    async def _save_project_dialog(self) -> None:
        target = self.state.project.path
        if target is None:
            target = await self.push_screen_wait(
                TextPromptDialog(
                    "Save project as",
                    "examples/my-project.vcut.json",
                    "examples/my-project.vcut.json",
                )
            )
        if not target:
            self._sync_status("Save cancelled.")
            return
        self.store.save(self.state.project, target)
        self.state.recent_projects = self.store.load_recent_projects()
        self.state.dirty = False
        self._sync_status(f"Saved project to {Path(target).name}.")

    async def _import_media_dialog(self) -> None:
        chosen = await self.push_screen_wait(
            FileBrowserDialog(
                "Import Media",
                str(self._project_root()),
                allow_files=True,
                allow_directories=False,
                project_path=str(self._project_root()),
            )
        )
        if not chosen:
            self._sync_status("Import cancelled.")
            return
        try:
            probe = await self.media_probe.probe(chosen)
            asset = self._mutate(
                "Import media",
                lambda: (
                    self.state.project.assets.append(probe.to_asset()),
                    self.state.project.assets[-1],
                )[1],
            )
            self.state.selected_asset_id = asset.id
            self._refresh_ui()
            self._sync_status(f"Imported {asset.label} ({asset.kind.value}).")
            if asset.kind is not AssetKind.SUBTITLE:
                self.run_worker(
                    self._preview_asset(asset),
                    group="preview",
                    exclusive=False,
                )
        except FileNotFoundError:
            self.notify(f"File not found: {chosen}", title="Import failed", severity="error")
        except Exception as exc:  # noqa: BLE001
            self.notify(str(exc), title="Import failed", severity="error")

    async def _subtitle_import_srt_dialog(self) -> None:
        chosen = await self.push_screen_wait(
            FileBrowserDialog(
                "Import SRT",
                str(self._project_root()),
                allow_files=True,
                allow_directories=False,
                project_path=str(self._project_root()),
            )
        )
        if not chosen:
            return
        try:
            text = Path(chosen).read_text(encoding="utf-8")
            self._mutate(
                "Import subtitles",
                lambda: setattr(self.state.project, "subtitles", parse_srt(text)),
            )
            self.state.selected_cue_id = (
                self.state.project.subtitles[0].id if self.state.project.subtitles else None
            )
            self._refresh_ui()
            self._sync_status(f"Imported {len(self.state.project.subtitles)} subtitle cues.")
        except Exception as exc:  # noqa: BLE001
            self.notify(str(exc), title="SRT import failed", severity="error")

    async def _subtitle_export_srt_dialog(self) -> None:
        chosen = await self.push_screen_wait(
            TextPromptDialog(
                "Export SRT",
                "examples/exported-captions.srt",
                "examples/exported-captions.srt",
            )
        )
        if not chosen:
            return
        try:
            Path(chosen).write_text(
                export_srt(self.state.project.subtitles),
                encoding="utf-8",
            )
            self._sync_status(f"Exported subtitles to {Path(chosen).name}.")
        except Exception as exc:  # noqa: BLE001
            self.notify(str(exc), title="SRT export failed", severity="error")

    async def _open_export_dialog(self) -> None:
        default_output = Path("exports") / f"{self.state.project.name.lower().replace(' ', '-')}.mp4"
        options = await self.push_screen_wait(ExportDialog(str(default_output)))
        if options is None:
            self._sync_status("Export cancelled.")
            return
        self.run_worker(self._run_export(options), group="export-run", exclusive=True)

    async def _open_command_palette(self) -> None:
        commands = [
            ("New project", "new"),
            ("Open project", "open"),
            ("Save project", "save"),
            ("Import media", "import"),
            ("Export project", "export"),
            ("Undo", "undo"),
            ("Redo", "redo"),
            ("Recover autosave", "recover"),
            ("Toggle follow playhead", "follow"),
            ("Show help overlay", "help"),
        ]
        action = await self.push_screen_wait(CommandPaletteScreen(commands))
        if action == "new":
            await self._new_project_dialog()
        elif action == "open":
            await self._open_project_dialog()
        elif action == "save":
            await self._save_project_dialog()
        elif action == "import":
            await self._import_media_dialog()
        elif action == "export":
            await self._open_export_dialog()
        elif action == "undo":
            self.action_undo()
        elif action == "redo":
            self.action_redo()
        elif action == "recover":
            self.action_recover_autosave()
        elif action == "follow":
            self.action_toggle_follow_playhead()
        elif action == "help":
            await self.push_screen_wait(HelpOverlayScreen())

    async def _run_export(self, options: ExportOptions) -> None:
        self.export_running = True
        self._log_panel().clear_logs()
        temp_subtitle_path: str | None = None
        try:
            effective_options = options
            if options.burn_subtitles:
                with tempfile.NamedTemporaryFile(
                    "w",
                    suffix=".srt",
                    delete=False,
                    encoding="utf-8",
                ) as handle:
                    handle.write(export_srt(self.state.project.subtitles))
                    temp_subtitle_path = handle.name
                effective_options = replace(options, subtitle_path=temp_subtitle_path)
            plan = self.export_builder.build(self.state.project, effective_options)
            if options.debug_mode:
                self._log_panel().append_line(plan.command_preview)

            async def on_event(event: ExportEvent) -> None:
                self._log_panel().append_line(event.message)
                if event.kind == "log" and event.progress_seconds is not None:
                    self._sync_status(
                        f"Exporting... encoded {event.progress_seconds:0.2f}s"
                    )
                elif event.kind == "start":
                    self._sync_status("Export started.")

            code = await self.export_executor.run(plan, on_event=on_event)
            if code == 0:
                self.notify(
                    f"Export finished: {plan.output_path}",
                    title="Export complete",
                )
                self._sync_status(f"Export completed to {plan.output_path}.")
            else:
                self.notify("Export failed. See Logs.", title="Export failed", severity="error")
                self._sync_status("Export failed. Inspect the Logs tab.")
        except Exception as exc:  # noqa: BLE001
            self._log_panel().append_line(str(exc))
            self.notify(str(exc), title="Export failed", severity="error")
            self._sync_status("Export failed before ffmpeg completed.")
        finally:
            self.export_running = False
            if temp_subtitle_path:
                Path(temp_subtitle_path).unlink(missing_ok=True)

    async def _cancel_export_async(self) -> None:
        await self.export_executor.cancel()
        self.export_running = False
        self._sync_status("Export cancelled.")
        self._log_panel().append_line("Export cancelled by user.")

    def _request_preview_poll(self) -> None:
        if not self._transport_available():
            return
        if not (self.preview.state.connected or self.preview.state.process_running):
            return
        self.run_worker(self._poll_preview_position(), group="preview-poll", exclusive=True)

    async def _start_preview(self) -> None:
        if self._transport_available():
            await self.preview.connect()
        self._apply_preview_state()

    async def _poll_preview_position(self) -> None:
        if not self._transport_available():
            return
        await self.preview.query_position()
        await self._refresh_preview_surface_from_transport()
        self._apply_preview_state()

    async def _preview_toggle(self) -> None:
        if not self._transport_available():
            self._sync_status("Playback transport is unavailable in this terminal session.")
            return
        await self.preview.toggle()
        await self._refresh_preview_surface_from_transport(force=True)
        self._apply_preview_state()

    async def _preview_frame_step(self) -> None:
        if not self._transport_available():
            self.action_step_right()
            return
        await self.preview.frame_step()
        self._apply_preview_state()
        await self._sync_preview_with_selection()

    async def _preview_frame_back(self) -> None:
        if not self._transport_available():
            self.action_step_left()
            return
        await self.preview.frame_back_step()
        self._apply_preview_state()
        await self._sync_preview_with_selection()

    async def _render_preview_frame(
        self,
        asset: MediaAsset | None,
        seconds: float,
        filter_chain: str | None = None,
    ) -> None:
        if asset is None or asset.kind is AssetKind.SUBTITLE:
            self.preview_frame_backend = "idle"
            self.preview_surface_seconds = 0.0
            self._preview_last_render_signature = None
            self.preview_frame_note = (
                "Import media or select a clip to render a terminal preview."
            )
            self._preview_pane().set_preview(
                frame=self._preview_placeholder_frame(
                    "No preview source",
                    "Import media or select a clip to render a terminal preview.",
                ),
                backend=self.preview_frame_backend,
                target="No preview source",
                status=self.state.preview_status,
                note=self.preview_frame_note,
            )
            return
        if not self._frame_preview_available():
            self.preview_frame_backend = "terminal-unavailable"
            self.preview_surface_seconds = seconds
            self._preview_last_render_signature = None
            self.preview_frame_note = "Install ffmpeg to enable terminal preview rendering."
            self._preview_pane().set_preview(
                frame=self._preview_placeholder_frame(
                    "Preview unavailable",
                    "Install ffmpeg to enable terminal preview rendering.",
                ),
                backend=self.preview_frame_backend,
                target=asset.label,
                status=self.state.preview_status,
                note=self.preview_frame_note,
            )
            return
        width_cells, height_cells = self._preview_pane().preview_dimensions()
        result = await self.frame_renderer.render(
            asset.path,
            asset.kind,
            seconds,
            width_cells,
            height_cells,
            filter_chain,
            self.preview_fit_mode,
            self.preview_quality,
        )
        self.preview_frame_backend = result.backend
        self.preview_surface_seconds = result.seconds
        if result.error:
            self.preview_frame_note = result.error
        elif asset.kind is AssetKind.AUDIO:
            self.preview_frame_note = "Audio preview uses an ffmpeg waveform render."
        elif self.preview.state.playing and self._transport_available():
            self.preview_frame_note = "Terminal preview refreshes live while transport plays."
        else:
            self.preview_frame_note = (
                f"{self.preview_quality} quality · {self.preview_fit_mode} mode terminal render."
            )
        self._preview_pane().set_preview(
            frame=result.frame,
            backend=self.preview_frame_backend,
            target=asset.label,
            status=self.state.preview_status,
            note=self.preview_frame_note,
        )
        self._preview_last_render_signature = self._preview_render_signature(
            asset,
            result.seconds,
            filter_chain,
        )
        self._preview_last_render_monotonic = time.monotonic()

    async def _sync_preview_with_selection(self) -> None:
        clip = self.state.selected_clip()
        if clip is None:
            asset = self.state.project.asset(self.state.selected_asset_id or "")
            if asset is None:
                self.preview.state.loaded_path = None
                await self._render_preview_frame(None, 0.0)
            else:
                await self._render_preview_frame(asset, 0.0)
            self._apply_preview_state()
            return
        asset = self.state.project.asset(clip.asset_id)
        if asset is None:
            fallback_asset = self.state.project.asset(self.state.selected_asset_id or "")
            if fallback_asset is None:
                self.preview.state.loaded_path = None
                await self._render_preview_frame(None, 0.0)
            else:
                await self._render_preview_frame(fallback_asset, 0.0)
            self._apply_preview_state()
            return
        preview_seconds = compute_preview_seek_seconds(clip, self.state.playhead)
        filter_chain = build_preview_filter_chain(clip.transform, self.state.project.settings)
        if self._transport_available():
            await self.preview.connect()
            if self.preview.state.connected:
                await self.preview.load_file(asset.path)
                await self.preview.seek_absolute(preview_seconds)
                await self.preview.set_filters(filter_chain)
                await self.preview.pause()
        await self._render_preview_frame(asset, preview_seconds, filter_chain or None)
        self._apply_preview_state()

    async def _preview_asset(self, asset: MediaAsset) -> None:
        if asset.kind is AssetKind.SUBTITLE:
            return
        if self._transport_available():
            await self.preview.connect()
            if self.preview.state.connected:
                await self.preview.load_file(asset.path)
                await self.preview.seek_absolute(0.0)
                await self.preview.set_filters(None)
                await self.preview.pause()
        await self._render_preview_frame(asset, 0.0)
        self._apply_preview_state()

    async def _apply_preview_filters(self) -> None:
        clip = self.state.selected_clip()
        if clip is None:
            return
        filter_chain = build_preview_filter_chain(clip.transform, self.state.project.settings)
        if self._transport_available():
            await self.preview.set_filters(filter_chain)
        asset = self.state.project.asset(clip.asset_id)
        await self._render_preview_frame(
            asset,
            compute_preview_seek_seconds(clip, self.state.playhead),
            filter_chain,
        )
        self._apply_preview_state()

    def _apply_preview_state(self) -> None:
        self.state.preview_status = self._compose_preview_status()
        self._sync_preview_pane()
        self.query_one(StatusBar).set_right(self.state.preview_status)

    def _autosave_tick(self) -> None:
        if not self.state.dirty:
            return
        self.autosave.save(self.state.project)
        self._log_panel().append_line("Autosaved project state.")
