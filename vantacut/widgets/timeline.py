from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group
from rich.text import Text
from textual.events import (
    Click,
    MouseDown,
    MouseMove,
    MouseScrollDown,
    MouseScrollUp,
    MouseUp,
)
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from vantacut.models.project import Project
from vantacut.models.timeline import TimelineClip, TimelineTrack, TrackKind
from vantacut.services.state import EditorState
from vantacut.timeline.engine import ClipPreview, TimelineEngine


TRACK_STYLES = {
    TrackKind.VIDEO: "black on #3a7bff",
    TrackKind.AUDIO: "black on #29b27b",
    TrackKind.SUBTITLE: "black on #d7a044",
}


@dataclass(slots=True)
class HoverInfo:
    track_id: str | None = None
    time: int = 0


@dataclass(slots=True)
class DragState:
    clip_id: str
    mode: str
    anchor_time: int
    origin_start: int
    origin_track_id: str
    origin_track_kind: TrackKind
    preview: ClipPreview | None = None


class TimelineView(Widget, can_focus=True):
    DEFAULT_CSS = """
    TimelineView {
        height: 1fr;
        border: round #39506c;
        background: $surface;
        padding: 0 1;
    }

    TimelineView:hover {
        border: round $accent 60%;
    }

    TimelineView:focus {
        border: round #93d4ff;
    }
    """

    playhead = reactive(0)
    zoom = reactive(12)
    scroll_seconds = reactive(0)

    class PlayheadChanged(Message):
        def __init__(self, timeline: "TimelineView", time: int) -> None:
            self.time = time
            super().__init__()

    class ClipSelected(Message):
        def __init__(self, timeline: "TimelineView", clip_id: str | None) -> None:
            self.clip_id = clip_id
            super().__init__()

    class ClipMoved(Message):
        def __init__(self, timeline: "TimelineView", preview: ClipPreview) -> None:
            self.preview = preview
            super().__init__()

    class ClipTrimmed(Message):
        def __init__(self, timeline: "TimelineView", edge: str, preview: ClipPreview) -> None:
            self.edge = edge
            self.preview = preview
            super().__init__()

    class ClipOpened(Message):
        def __init__(self, timeline: "TimelineView", clip_id: str) -> None:
            self.clip_id = clip_id
            super().__init__()

    def __init__(self, state: EditorState, engine: TimelineEngine, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.state = state
        self.engine = engine
        self.project: Project = state.project
        self.hover = HoverInfo()
        self.drag_state: DragState | None = None

    def set_state(self, state: EditorState) -> None:
        self.state = state
        self.project = state.project
        self.playhead = state.playhead
        self.zoom = state.zoom
        self.scroll_seconds = state.horizontal_scroll
        self.refresh()

    def render(self) -> Group:
        lines = [self._render_ruler()]
        for track in self.project.tracks:
            lines.extend(self._render_track(track))
        return Group(*lines)

    def _timeline_width(self) -> int:
        label_width = 12
        return max(20, self.size.width - label_width - 2)

    def _visible_seconds(self) -> int:
        return max(5, self._timeline_width() // max(1, self.zoom))

    def _render_ruler(self) -> Text:
        width = self._timeline_width()
        chars = [" "] * (width + 12)
        styles: list[tuple[str, int, int]] = []
        chars[:12] = list("Time".ljust(12))
        visible_seconds = self._visible_seconds()
        for second in range(visible_seconds + 1):
            x = 12 + second * self.zoom
            if x >= len(chars):
                break
            tick = self.state.timebase.seconds_to_ticks(self.scroll_seconds + second)
            stamp = self.state.timebase.format_clock(tick)[3:11]
            for index, char in enumerate(stamp):
                if x + index < len(chars):
                    chars[x + index] = char
            if x > 0:
                chars[x - 1] = "┆"
        for marker in self.project.markers:
            marker_x = self._time_to_x(marker.time)
            if 12 <= marker_x < len(chars):
                chars[marker_x] = "▲"
                styles.append(("bold #ffb347", marker_x, marker_x + 1))
        playhead_x = self._time_to_x(self.playhead)
        if 12 <= playhead_x < len(chars):
            chars[playhead_x] = "▼"
            styles.append(("bold #93d4ff", playhead_x, playhead_x + 1))
        if self.drag_state and self.drag_state.preview and self.drag_state.preview.snap_result.did_snap:
            snap_x = self._time_to_x(self.drag_state.preview.snap_result.time)
            if 12 <= snap_x < len(chars):
                chars[snap_x] = "▲"
                styles.append(("bold #ffd17a", snap_x, snap_x + 1))
        line = Text("".join(chars))
        for style, start, end in styles:
            line.stylize(style, start, end)
        line.stylize("bold #4aa6ff", 0, 12)
        return line

    def _render_track(self, track: TimelineTrack) -> list[Text]:
        width = self._timeline_width()
        chars = [" "] * (width + 12)
        chars[:12] = list(track.name.ljust(12)[:12])
        styles: list[tuple[str, int, int]] = [("bold", 0, 12)]
        for clip in track.clips:
            preview = self._preview_for_clip(clip, track)
            render_start = preview.start if preview else clip.start
            render_end = preview.end if preview else clip.end
            render_duration = preview.duration if preview else clip.duration
            block_start = max(12, self._time_to_x(render_start))
            block_end = min(12 + width, max(block_start + 1, self._time_to_x(render_end)))
            if block_start >= block_end:
                continue
            chars[block_start] = "▌"
            if block_end - 1 < len(chars):
                chars[block_end - 1] = "▐"
            title = self._clip_title(clip, render_duration)
            for idx, char in enumerate(title[: max(0, block_end - block_start - 2)], start=block_start + 1):
                if idx >= block_end - 1:
                    break
                chars[idx] = char
            if preview:
                style = "black on #d7ecff"
            elif clip.id == self.state.selected_clip_id:
                style = "black on #f0f6ff"
            else:
                style = TRACK_STYLES[track.kind]
            styles.append((style, block_start, block_end))
        playhead_x = self._time_to_x(self.playhead)
        if 12 <= playhead_x < len(chars):
            chars[playhead_x] = "│"
            styles.append(("bold #93d4ff", playhead_x, playhead_x + 1))
        if self.drag_state and self.drag_state.preview and self.drag_state.preview.snap_result.did_snap:
            snap_x = self._time_to_x(self.drag_state.preview.snap_result.time)
            if 12 <= snap_x < len(chars):
                chars[snap_x] = "┆"
                styles.append(("bold #ffd17a", snap_x, snap_x + 1))
        line = Text("".join(chars))
        line.stylize("dim", 12, len(chars))
        for style, start, end in styles:
            line.stylize(style, start, end)
        footer = Text((" " * 12) + ("─" * width), style="dim #39506c")
        return [line, footer]

    def _preview_for_clip(self, clip: TimelineClip, track: TimelineTrack) -> ClipPreview | None:
        if self.drag_state is None or self.drag_state.preview is None:
            return None
        if self.drag_state.clip_id != clip.id:
            return None
        if self.drag_state.preview.track_id != track.id:
            return None
        return self.drag_state.preview

    def _clip_title(self, clip: TimelineClip, duration: int) -> str:
        asset = self.project.asset(clip.asset_id)
        label = asset.label if asset else clip.asset_id
        flags = []
        if clip.muted:
            flags.append("M")
        if clip.linked:
            flags.append("L")
        suffix = f"{duration / 1000:.1f}s"
        if flags:
            suffix = f"{suffix} {' '.join(flags)}"
        return f"{label} {suffix}"

    def _time_to_x(self, ticks: int) -> int:
        seconds = self.state.timebase.ticks_to_seconds(ticks)
        return 12 + round((seconds - self.scroll_seconds) * self.zoom)

    def _x_to_time(self, x: int) -> int:
        relative = max(0, x - 12)
        seconds = self.scroll_seconds + (relative / max(1, self.zoom))
        return self.state.timebase.seconds_to_ticks(seconds)

    def _pick_track(self, y: int) -> TimelineTrack | None:
        track_index = max(0, (y - 1) // 2)
        if track_index >= len(self.project.tracks):
            return None
        return self.project.tracks[track_index]

    def _pick_clip(self, x: int, y: int) -> TimelineClip | None:
        track = self._pick_track(y)
        if track is None:
            return None
        time = self._x_to_time(x)
        return next((clip for clip in track.clips if clip.start <= time <= clip.end), None)

    def _edge_mode(self, x: int, clip: TimelineClip) -> str:
        if abs(x - self._time_to_x(clip.start)) <= 1:
            return "trim-left"
        if abs(x - self._time_to_x(clip.end)) <= 1:
            return "trim-right"
        return "move"

    def _snap_threshold(self) -> int:
        return self.state.timebase.seconds_to_ticks(0.35)

    def on_mouse_down(self, event: MouseDown) -> None:
        self.focus()
        clip = self._pick_clip(event.x, event.y)
        time = self._x_to_time(event.x)
        if clip is None:
            self.playhead = time
            self.state.playhead = time
            self.post_message(self.PlayheadChanged(self, time))
            self.refresh()
            return
        track = self.engine.find_track(self.project, clip.track_id)
        self.state.selected_clip_id = clip.id
        self.engine.select_clip(self.project, clip.id)
        self.post_message(self.ClipSelected(self, clip.id))
        self.capture_mouse()
        self.drag_state = DragState(
            clip_id=clip.id,
            mode=self._edge_mode(event.x, clip),
            anchor_time=time,
            origin_start=clip.start,
            origin_track_id=clip.track_id,
            origin_track_kind=track.kind,
        )
        self.refresh()

    def on_mouse_move(self, event: MouseMove) -> None:
        track = self._pick_track(event.y)
        self.hover = HoverInfo(
            track_id=track.id if track else None,
            time=self._x_to_time(event.x),
        )
        if self.drag_state is None:
            return
        desired_time = self._x_to_time(event.x)
        threshold = self._snap_threshold()
        if self.drag_state.mode == "move":
            candidate_track = track if track and track.kind == self.drag_state.origin_track_kind else None
            self.drag_state.preview = self.engine.preview_move(
                self.project,
                self.drag_state.clip_id,
                self.drag_state.origin_start + (desired_time - self.drag_state.anchor_time),
                candidate_track.id if candidate_track else self.drag_state.origin_track_id,
                self.state.playhead,
                threshold,
            )
        elif self.drag_state.mode == "trim-left":
            self.drag_state.preview = self.engine.preview_trim_left(
                self.project,
                self.drag_state.clip_id,
                desired_time,
                self.state.playhead,
                threshold,
            )
        else:
            self.drag_state.preview = self.engine.preview_trim_right(
                self.project,
                self.drag_state.clip_id,
                desired_time,
                self.state.playhead,
                threshold,
            )
        self.refresh()

    def on_mouse_up(self, event: MouseUp) -> None:
        if self.drag_state is None:
            return
        self.capture_mouse(False)
        preview = self.drag_state.preview
        mode = self.drag_state.mode
        self.drag_state = None
        if preview is None:
            self.refresh()
            return
        if mode == "move":
            self.post_message(self.ClipMoved(self, preview))
        elif mode == "trim-left":
            self.post_message(self.ClipTrimmed(self, "left", preview))
        else:
            self.post_message(self.ClipTrimmed(self, "right", preview))
        self.refresh()

    def on_click(self, event: Click) -> None:
        if event.chain != 2:
            return
        clip = self._pick_clip(event.x, event.y)
        if clip is not None:
            self.post_message(self.ClipOpened(self, clip.id))

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        if event.ctrl:
            self.zoom = min(32, self.zoom + 1)
            self.state.zoom = self.zoom
        else:
            self.scroll_seconds = max(0, self.scroll_seconds - 1)
            self.state.horizontal_scroll = self.scroll_seconds
        self.refresh()

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        if event.ctrl:
            self.zoom = max(4, self.zoom - 1)
            self.state.zoom = self.zoom
        else:
            self.scroll_seconds += 1
            self.state.horizontal_scroll = self.scroll_seconds
        self.refresh()
