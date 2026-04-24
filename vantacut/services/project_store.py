from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from vantacut.models.project import Project


class ProjectStore:
    def __init__(self, state_dir: str | Path | None = None) -> None:
        self._state_dir = self._resolve_state_dir(state_dir)

    def load(self, path: str | Path) -> Project:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        project = Project.from_dict(raw)
        project.path = str(path)
        self.remember_recent(path)
        return project

    def save(self, project: Project, path: str | Path) -> None:
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        previous_payload = target.read_text(encoding="utf-8") if target.exists() else None
        project.path = str(target)
        payload = json.dumps(project.to_dict(), indent=2, sort_keys=True)
        self._write_atomic(target, payload)
        self._write_progress_snapshots(target, payload, previous_payload)
        self.remember_recent(target)

    def remember_recent(self, path: str | Path) -> None:
        target = str(Path(path).expanduser().resolve())
        entries = [item for item in self.load_recent_projects() if item != target]
        entries.insert(0, target)
        (self._state_dir / "recent_projects.json").write_text(
            json.dumps(entries[:20], indent=2),
            encoding="utf-8",
        )

    def load_recent_projects(self) -> list[str]:
        path = self._state_dir / "recent_projects.json"
        if not path.exists():
            return []
        try:
            return list(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            return []

    def progress_dir_for(self, path: str | Path) -> Path:
        target = Path(path).expanduser().resolve()
        progress_dir = target.parent / ".vantacut-progress"
        progress_dir.mkdir(parents=True, exist_ok=True)
        return progress_dir

    def latest_progress_path(self, path: str | Path) -> Path:
        target = Path(path).expanduser().resolve()
        return self.progress_dir_for(target) / f"{target.stem}.latest.vcut.json"

    def backup_progress_path(self, path: str | Path) -> Path:
        target = Path(path).expanduser().resolve()
        return self.progress_dir_for(target) / f"{target.stem}.previous.vcut.json"

    def _resolve_state_dir(self, state_dir: str | Path | None) -> Path:
        candidates: list[Path] = []
        if state_dir is not None:
            candidates.append(Path(state_dir))
        env_state_dir = os.environ.get("VANTACUT_STATE_DIR")
        if env_state_dir:
            candidates.append(Path(env_state_dir))
        candidates.extend(
            [
                Path.home() / ".local" / "state" / "vantacut",
                Path.cwd() / ".vantacut-state",
                Path(tempfile.gettempdir()) / "vantacut-state",
            ]
        )
        seen: set[str] = set()
        for candidate in candidates:
            normalized = str(candidate.expanduser())
            if normalized in seen:
                continue
            seen.add(normalized)
            resolved = candidate.expanduser()
            try:
                resolved.mkdir(parents=True, exist_ok=True)
                probe = resolved / ".write-test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return resolved.resolve()
            except OSError:
                continue
        raise OSError("No writable state directory available for VantaCut.")

    def _write_atomic(self, target: Path, payload: str) -> None:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=target.parent,
            delete=False,
            prefix=f".{target.stem}.",
            suffix=".tmp",
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        os.replace(temp_path, target)

    def _write_progress_snapshots(
        self,
        target: Path,
        payload: str,
        previous_payload: str | None,
    ) -> None:
        self._write_atomic(self.latest_progress_path(target), payload)
        if previous_payload is not None:
            self._write_atomic(self.backup_progress_path(target), previous_payload)
