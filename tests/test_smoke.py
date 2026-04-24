import asyncio

from vantacut.app import VantaCutApp
from vantacut.widgets.media_bin import MediaBin
from vantacut.widgets.timeline import TimelineView


def test_app_smoke() -> None:
    async def run() -> None:
        app = VantaCutApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            assert app.query_one(MediaBin)
            assert app.query_one(TimelineView)
            assert app.query_one("#left-pane")
            assert app.query_one("#right-pane")
            assert app.state.project.name == "Untitled Project"
            assert app.state.project.assets == []
            assert len(app.state.project.tracks) == 3

    asyncio.run(run())
