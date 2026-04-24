from __future__ import annotations

import json
from pathlib import Path

from vantacut.models.project import Project
from vantacut.services.project_store import ProjectStore


class AutosaveService:
    DEFAULT_FILENAME = "autosave.vcut.json"

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.path = store._state_dir / self.DEFAULT_FILENAME

    def save(self, project: Project) -> None:
        payload = project.to_dict()
        payload["updated_at"] = project.updated_at
        target = self.recovery_path(project)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.store._write_atomic(
            target,
            json.dumps(payload, indent=2, sort_keys=True),
        )

    def has_recovery(self, project: Project | None = None) -> bool:
        return self.recovery_path(project).exists()

    def load(self, project: Project | None = None) -> Project:
        raw = json.loads(self.recovery_path(project).read_text(encoding="utf-8"))
        project = Project.from_dict(raw)
        return project

    def clear(self, project: Project | None = None) -> None:
        self.recovery_path(project).unlink(missing_ok=True)

    def recovery_path(self, project: Project | None = None) -> Path:
        if self.path.name != self.DEFAULT_FILENAME or self.path.parent != self.store._state_dir:
            return self.path
        if project is not None and project.path:
            target = Path(project.path).expanduser().resolve()
            return self.store.progress_dir_for(target) / f"{target.stem}.autosave.vcut.json"
        return self.path
