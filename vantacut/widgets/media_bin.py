from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView, Static

from vantacut.models.asset import MediaAsset


class MediaBin(Vertical):
    DEFAULT_CSS = """
    MediaBin {
        height: 1fr;
    }

    MediaBin .panel-title {
        padding: 0 1;
        height: 2;
        content-align: left middle;
        color: $accent;
        background: #202d3d;
        border-bottom: solid #39506c;
    }

    MediaBin ListView {
        height: 1fr;
        background: transparent;
    }

    MediaBin ListItem {
        padding: 0 1;
        border-bottom: solid $background 20%;
    }

    MediaBin ListItem.--highlight,
    MediaBin ListItem:hover {
        background: $primary 15%;
    }

    MediaBin .asset-meta {
        color: #8ea0b9;
    }
    """

    def __init__(self, assets: list[MediaAsset] | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.assets = assets or []

    def compose(self) -> ComposeResult:
        yield Label("Media Bin", classes="panel-title")
        yield ListView(*self._items(), id="media-list")

    def _items(self) -> list[ListItem]:
        items: list[ListItem] = []
        for asset in self.assets:
            info = f"{asset.kind.value.upper()}   {asset.duration_ticks / 1000:.1f}s"
            label = Static(f"{asset.label}\n[{info}]", markup=False)
            label.add_class("asset-row")
            items.append(ListItem(label, id=asset.id))
        if not items:
            items.append(ListItem(Static("No media imported yet.")))
        return items

    def set_assets(self, assets: list[MediaAsset]) -> None:
        self.assets = assets
        list_view = self.query_one("#media-list", ListView)
        current_ids = [child.id for child in list_view.children if isinstance(child, ListItem)]
        next_ids = [asset.id for asset in assets] or [None]
        if current_ids == next_ids:
            return

        async def repopulate() -> None:
            async with list_view.batch():
                await list_view.remove_children()
                await list_view.mount(*self._items())

        list_view.run_worker(repopulate(), group="media-bin-refresh", exclusive=True)
