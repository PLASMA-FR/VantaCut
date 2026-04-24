from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EditorSnapshot:
    project_data: dict[str, object]
    selected_asset_id: str | None
    selected_clip_id: str | None
    selected_cue_id: str | None
    playhead: int


@dataclass(frozen=True, slots=True)
class SnapshotCommand:
    label: str
    before: EditorSnapshot
    after: EditorSnapshot


class CommandStack:
    def __init__(self) -> None:
        self._undo: list[SnapshotCommand] = []
        self._redo: list[SnapshotCommand] = []

    def push(self, label: str, before: EditorSnapshot, after: EditorSnapshot) -> None:
        if before == after:
            return
        self._undo.append(SnapshotCommand(label, before, after))
        self._redo.clear()

    def undo(self) -> EditorSnapshot | None:
        if not self._undo:
            return None
        command = self._undo.pop()
        self._redo.append(command)
        return command.before

    def redo(self) -> EditorSnapshot | None:
        if not self._redo:
            return None
        command = self._redo.pop()
        self._undo.append(command)
        return command.after

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

