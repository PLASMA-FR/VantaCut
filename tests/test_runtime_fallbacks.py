import asyncio
from pathlib import Path

from vantacut.app import VantaCutApp
from vantacut.export.command_builder import ExportPlan, InputSpec
from vantacut.export.executor import ExportExecutor
from vantacut.preview.mpv import MpvPreviewController


def test_preview_controller_reports_missing_mpv(monkeypatch) -> None:
    async def run() -> None:
        controller = MpvPreviewController()

        async def raise_missing() -> None:
            raise FileNotFoundError

        monkeypatch.setattr(controller, "_spawn_process", raise_missing)
        state = await controller.connect()
        assert state.connected is False
        assert state.last_error == "mpv not found"

    asyncio.run(run())


def test_export_executor_reports_missing_ffmpeg(monkeypatch) -> None:
    async def run() -> None:
        executor = ExportExecutor()

        async def raise_missing(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise FileNotFoundError

        monkeypatch.setattr(asyncio, "create_subprocess_exec", raise_missing)
        events = []
        code = await executor.run(
            ExportPlan(
                args=["-i", "input.mp4", "out.mp4"],
                filtergraph="",
                output_path="out.mp4",
                inputs=[InputSpec(args=["-i", "input.mp4"], source="input.mp4")],
                command_preview="ffmpeg -i input.mp4 out.mp4",
            ),
            on_event=lambda event: events.append(event),
        )
        assert code == 127
        assert events[-1].message == "ffmpeg not found"

    asyncio.run(run())


def test_autosave_recovery_round_trip(tmp_path: Path) -> None:
    async def run() -> None:
        app = VantaCutApp()
        app.autosave.path = tmp_path / "autosave.vcut.json"

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            original_name = app.state.project.name
            app.state.project.name = "Recovered Project"
            app.state.dirty = True
            app._autosave_tick()
            assert app.autosave.has_recovery()

            app.state.project.name = original_name
            app.action_recover_autosave()
            assert app.state.project.name == "Recovered Project"

    asyncio.run(run())
