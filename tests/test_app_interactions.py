import asyncio
from dataclasses import replace
from pathlib import Path

from vantacut.app import VantaCutApp
from vantacut.core.environment import DependencyStatus
from vantacut.models.asset import AssetKind, MediaAsset
from vantacut.models.project import Project
from vantacut.preview.base import PreviewState
from vantacut.preview.frame_renderer import FrameRenderResult
from vantacut.services.autosave import AutosaveService
from vantacut.services.project_store import ProjectStore
from vantacut.widgets.dialogs import FileBrowserDialog, TextPromptDialog
from vantacut.widgets.export_dialog import ExportDialog
from vantacut.widgets.overlays import CommandPaletteScreen, HelpOverlayScreen
from vantacut.widgets.preview_pane import PreviewPane
from vantacut.widgets.subtitle_editor import SubtitleEditor
from rich.text import Text
from textual.widgets import Input, ListView


class FakePreviewController:
    def __init__(self) -> None:
        self.state = PreviewState(connected=True, process_running=True)
        self.loaded_paths: list[str] = []
        self.seeks: list[float] = []
        self.filters: list[str | None] = []

    async def connect(self) -> PreviewState:
        self.state.connected = True
        self.state.process_running = True
        self.state.last_error = None
        return self.state

    async def load_file(self, path: str) -> PreviewState:
        self.loaded_paths.append(path)
        self.state.loaded_path = path
        self.state.position_seconds = 0.0
        return self.state

    async def play(self) -> PreviewState:
        self.state.playing = True
        return self.state

    async def pause(self) -> PreviewState:
        self.state.playing = False
        return self.state

    async def toggle(self) -> PreviewState:
        self.state.playing = not self.state.playing
        return self.state

    async def seek_absolute(self, seconds: float) -> PreviewState:
        self.seeks.append(seconds)
        self.state.position_seconds = seconds
        return self.state

    async def seek_relative(self, seconds: float) -> PreviewState:
        self.state.position_seconds += seconds
        return self.state

    async def frame_step(self) -> PreviewState:
        return self.state

    async def frame_back_step(self) -> PreviewState:
        return self.state

    async def query_position(self) -> PreviewState:
        return self.state

    async def set_filters(self, filter_chain: str | None) -> PreviewState:
        self.filters.append(filter_chain)
        return self.state

    async def close(self) -> None:
        self.state.connected = False
        self.state.process_running = False


def test_open_project_dialog_opens_without_worker_errors(tmp_path: Path) -> None:
    async def run() -> None:
        app = VantaCutApp()
        app.state.project.path = str(tmp_path / "fixture.vcut.json")

        async def fake_push_screen_wait(*args, **kwargs):  # type: ignore[no-untyped-def]
            return None

        app.push_screen_wait = fake_push_screen_wait  # type: ignore[method-assign]
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.click("#action-open")
            await pilot.pause()
            assert app.state.status == "Open project cancelled."

    asyncio.run(run())


def test_save_project_dialog_opens_without_worker_errors() -> None:
    async def run() -> None:
        app = VantaCutApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.click("#action-save")
            await pilot.pause()
            assert isinstance(app.screen, TextPromptDialog)
            app.screen.dismiss(None)
            await pilot.pause()

    asyncio.run(run())


def test_import_dialog_opens_without_worker_errors() -> None:
    async def run() -> None:
        app = VantaCutApp()

        async def fake_push_screen_wait(*args, **kwargs):  # type: ignore[no-untyped-def]
            return None

        app.push_screen_wait = fake_push_screen_wait  # type: ignore[method-assign]
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.click("#action-import")
            await pilot.pause()
            assert app.state.status == "Import cancelled."

    asyncio.run(run())


def test_export_dialog_opens_without_worker_errors() -> None:
    async def run() -> None:
        app = VantaCutApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.click("#action-export")
            await pilot.pause()
            assert isinstance(app.screen, ExportDialog)
            app.screen.dismiss(None)
            await pilot.pause()

    asyncio.run(run())


def test_new_project_and_import_media_from_any_folder_with_preview(tmp_path: Path) -> None:
    async def run() -> None:
        project_dir = tmp_path / "project-home"
        media_dir = tmp_path / "external-media"
        project_dir.mkdir()
        media_dir.mkdir()
        media_path = media_dir / "clip.mp4"
        media_path.write_bytes(b"demo-media")

        app = VantaCutApp()
        preview = FakePreviewController()
        app.preview = preview
        app.environment = replace(
            app.environment,
            unix_socket_ipc=True,
            mpv=DependencyStatus("mpv", "/usr/bin/mpv"),
        )
        app._request_preview_poll = lambda: None  # type: ignore[method-assign]

        selections = iter([str(project_dir), str(media_path)])

        async def fake_push_screen_wait(*args, **kwargs):  # type: ignore[no-untyped-def]
            return next(selections)

        app.push_screen_wait = fake_push_screen_wait  # type: ignore[method-assign]

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.click("#action-new")
            await pilot.pause()

            expected_project_path = project_dir / f"{project_dir.name}.vcut.json"
            assert app.state.project.name == project_dir.name
            assert app.state.project.path == str(expected_project_path)
            assert expected_project_path.exists()
            assert len(app.state.project.assets) == 0
            assert [track.name for track in app.state.project.tracks] == [
                "Video 1",
                "Audio 1",
                "Subtitles",
            ]

            await pilot.click("#action-import")
            for _ in range(10):
                await pilot.pause()
                if app.state.project.assets:
                    break

            imported = app.state.project.assets[-1]
            assert imported.path == str(media_path.resolve())
            assert app.state.selected_asset_id == imported.id
            assert preview.loaded_paths[-1] == str(media_path.resolve())
            assert preview.seeks[-1] == 0.0

    asyncio.run(run())


def test_import_video_audio_and_image_assets_all_route_to_preview(tmp_path: Path) -> None:
    async def run() -> None:
        project_dir = tmp_path / "project-home"
        media_dir = tmp_path / "external-media"
        project_dir.mkdir()
        media_dir.mkdir()

        video_path = media_dir / "clip.mp4"
        audio_path = media_dir / "sound.wav"
        image_path = media_dir / "frame.png"
        video_path.write_bytes(b"video")
        audio_path.write_bytes(b"audio")
        image_path.write_bytes(b"image")

        app = VantaCutApp()
        preview = FakePreviewController()
        app.preview = preview
        app.environment = replace(
            app.environment,
            unix_socket_ipc=True,
            mpv=DependencyStatus("mpv", "/usr/bin/mpv"),
        )
        app._request_preview_poll = lambda: None  # type: ignore[method-assign]

        selections = iter(
            [
                str(project_dir),
                str(video_path),
                str(audio_path),
                str(image_path),
            ]
        )

        async def fake_push_screen_wait(*args, **kwargs):  # type: ignore[no-untyped-def]
            return next(selections)

        app.push_screen_wait = fake_push_screen_wait  # type: ignore[method-assign]

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.click("#action-new")
            await pilot.pause()

            await pilot.click("#action-import")
            for _ in range(10):
                await pilot.pause()
                if len(app.state.project.assets) >= 1:
                    break
            await pilot.click("#action-import")
            for _ in range(10):
                await pilot.pause()
                if len(app.state.project.assets) >= 2:
                    break
            await pilot.click("#action-import")
            for _ in range(10):
                await pilot.pause()
                if len(app.state.project.assets) >= 3:
                    break

            assert [asset.kind.value for asset in app.state.project.assets] == [
                "video",
                "audio",
                "image",
            ]
            assert preview.loaded_paths == [
                str(video_path.resolve()),
                str(audio_path.resolve()),
                str(image_path.resolve()),
            ]
            assert preview.seeks == [0.0, 0.0, 0.0]

    asyncio.run(run())


def test_preview_focus_and_quality_controls_refresh_layout() -> None:
    async def run() -> None:
        app = VantaCutApp()

        async with app.run_test(size=(160, 48)) as pilot:
            preview = app.query_one(PreviewPane)
            timeline = app._timeline()  # noqa: SLF001

            default_preview_height = preview.size.height
            assert app.preview_focus_mode is False
            assert app.preview_quality == "balanced"
            assert app.preview_fit_mode == "contain"

            await pilot.click("#action-preview-focus")
            await pilot.pause()

            assert app.preview_focus_mode is True
            assert preview.size.height > default_preview_height
            assert timeline.size.height <= 10

            await pilot.press("ctrl+3")
            await pilot.pause()
            await pilot.press("ctrl+shift+v")
            await pilot.pause()

            assert app.preview_quality == "full"
            assert app.preview_fit_mode == "fill"

    asyncio.run(run())


def test_preview_focus_keeps_selected_asset_preview_without_clip() -> None:
    async def run() -> None:
        app = VantaCutApp()
        asset = MediaAsset(path="/tmp/demo.mp4", kind=AssetKind.VIDEO, label="demo.mp4")
        app.state.project.assets.append(asset)
        app.state.selected_asset_id = asset.id

        rendered_assets: list[str | None] = []

        async def fake_render_preview_frame(asset_arg, seconds, filter_chain=None):  # type: ignore[no-untyped-def]
            rendered_assets.append(getattr(asset_arg, "id", None))

        app._render_preview_frame = fake_render_preview_frame  # type: ignore[method-assign]

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.click("#action-preview-focus")
            await pilot.pause()
            assert rendered_assets[-1] == asset.id

    asyncio.run(run())


def test_recent_project_list_opens_saved_project(tmp_path: Path) -> None:
    async def run() -> None:
        store = ProjectStore(state_dir=tmp_path / ".state")
        target = tmp_path / "saved-project" / "saved-project.vcut.json"
        target.parent.mkdir()
        project = Project.empty("Saved Project", path=str(target))
        store.save(project, target)

        app = VantaCutApp()
        app.store = store
        app.autosave = AutosaveService(store)
        app.state.project = Project.empty("Working Copy")
        app.state.recent_projects = store.load_recent_projects()

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            recent = app.query_one("#recent-projects", ListView)
            recent.index = 0
            recent.action_select_cursor()
            await pilot.pause()

            assert app.state.project.name == "Saved Project"
            assert app.state.project.path == str(target.resolve())
            assert app.state.status == f"Opened project {target.name}."

    asyncio.run(run())


def test_terminal_preview_updates_widget_when_transport_is_unavailable(tmp_path: Path) -> None:
    async def run() -> None:
        media_path = tmp_path / "frame.png"
        media_path.write_bytes(b"image")
        asset = MediaAsset(path=str(media_path), kind=AssetKind.IMAGE)

        app = VantaCutApp()
        app.environment = replace(app.environment, unix_socket_ipc=False)
        app.state.project.assets = [asset]
        app.state.selected_asset_id = asset.id

        async def fake_render(*args, **kwargs):  # type: ignore[no-untyped-def]
            return FrameRenderResult(
                frame=Text("▀▀\n▀▀"),
                backend="terminal-ffmpeg",
                seconds=0.0,
                source_path=str(media_path.resolve()),
            )

        app.frame_renderer.render = fake_render  # type: ignore[method-assign]

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            await app._preview_asset(asset)
            await pilot.pause()

            pane = app.query_one(PreviewPane)
            assert pane.backend == "terminal-ffmpeg"
            assert pane.target == asset.label
            assert app.state.preview_status.startswith("terminal preview")

    asyncio.run(run())


def test_transport_poll_refreshes_terminal_preview_while_playing(tmp_path: Path) -> None:
    async def run() -> None:
        media_path = tmp_path / "playing.mp4"
        media_path.write_bytes(b"video")
        asset = MediaAsset(path=str(media_path), kind=AssetKind.VIDEO)

        app = VantaCutApp()
        preview = FakePreviewController()
        app.preview = preview
        app.environment = replace(
            app.environment,
            unix_socket_ipc=True,
            mpv=DependencyStatus("mpv", "/usr/bin/mpv"),
        )
        app.state.project.assets = [asset]
        app.state.selected_asset_id = asset.id
        preview.state.loaded_path = str(media_path.resolve())
        preview.state.playing = True
        preview.state.position_seconds = 1.0

        async def fake_query_position() -> PreviewState:
            preview.state.position_seconds = 1.5
            preview.state.playing = True
            return preview.state

        preview.query_position = fake_query_position  # type: ignore[method-assign]
        render_seconds: list[float] = []

        async def fake_render(*args, **kwargs):  # type: ignore[no-untyped-def]
            seconds = float(args[2])
            render_seconds.append(seconds)
            return FrameRenderResult(
                frame=Text("▀▀\n▀▀"),
                backend="terminal-ffmpeg",
                seconds=seconds,
                source_path=str(media_path.resolve()),
            )

        app.frame_renderer.render = fake_render  # type: ignore[method-assign]

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            app._preview_last_render_monotonic = 0.0
            await app._poll_preview_position()
            await pilot.pause()

            pane = app.query_one(PreviewPane)
            assert render_seconds[-1] == 1.5
            assert pane.backend == "terminal-ffmpeg + mpv transport"
            assert "live while transport plays" in pane.note
            assert app.state.preview_status == "preview playing @ 1.50s"

    asyncio.run(run())


def test_subtitle_dialogs_open_from_messages() -> None:
    async def run() -> None:
        app = VantaCutApp()

        async def fake_push_screen_wait(*args, **kwargs):  # type: ignore[no-untyped-def]
            return None

        app.push_screen_wait = fake_push_screen_wait  # type: ignore[method-assign]
        async with app.run_test(size=(160, 48)) as pilot:
            editor = app.query_one(SubtitleEditor)
            editor.post_message(SubtitleEditor.ImportSrt())
            await pilot.pause()

            editor.post_message(SubtitleEditor.ExportSrt())
            await pilot.pause()
            assert app.screen.id == "_default"

    asyncio.run(run())


def test_edit_actions_undo_redo_and_autosave(tmp_path: Path) -> None:
    async def run() -> None:
        app = VantaCutApp()
        app.autosave.path = tmp_path / "autosave.vcut.json"
        app.state.project = Project.demo()
        app.state.selected_asset_id = app.state.project.assets[0].id
        app.state.selected_clip_id = app.state.project.tracks[0].clips[0].id
        app.timeline_engine.select_clip(app.state.project, app.state.selected_clip_id)
        initial_clip_count = len(app.state.project.tracks[0].clips)

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            app.action_insert_selected_asset()
            assert len(app.state.project.tracks[0].clips) == initial_clip_count + 1
            app.action_undo()
            assert len(app.state.project.tracks[0].clips) == initial_clip_count
            app.action_redo()
            assert len(app.state.project.tracks[0].clips) == initial_clip_count + 1

            app._autosave_tick()
            assert app.autosave.path.exists()

    asyncio.run(run())


def test_command_palette_and_help_overlay_open() -> None:
    async def run() -> None:
        app = VantaCutApp()
        async with app.run_test(size=(160, 48)) as pilot:
            app.action_open_command_palette()
            await pilot.pause()
            assert isinstance(app.screen, CommandPaletteScreen)
            app.screen.dismiss(None)
            await pilot.pause()

            app.action_show_help_overlay()
            await pilot.pause()
            assert isinstance(app.screen, HelpOverlayScreen)
            app.screen.dismiss(None)
            await pilot.pause()

    asyncio.run(run())
