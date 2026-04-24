import json
from pathlib import Path

from vantacut.models.project import Project
from vantacut.services.autosave import AutosaveService
from vantacut.services.project_store import ProjectStore


def test_project_store_round_trip(tmp_path: Path) -> None:
    store = ProjectStore(state_dir=tmp_path / ".state")
    project = Project.demo()
    target = tmp_path / "roundtrip.vcut.json"
    store.save(project, target)

    loaded = store.load(target)
    assert loaded.name == project.name
    assert len(loaded.assets) == len(project.assets)
    assert len(loaded.tracks) == len(project.tracks)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["path"] == str(target.resolve())


def test_project_store_writes_latest_and_previous_progress_snapshots(tmp_path: Path) -> None:
    store = ProjectStore(state_dir=tmp_path / ".state")
    project = Project.empty("Snapshot Test")
    target = tmp_path / "snapshot-test.vcut.json"

    store.save(project, target)
    latest = store.latest_progress_path(target)
    previous = store.backup_progress_path(target)
    assert latest.exists()
    assert not previous.exists()

    project.name = "Snapshot Test Updated"
    store.save(project, target)

    latest_payload = json.loads(latest.read_text(encoding="utf-8"))
    previous_payload = json.loads(previous.read_text(encoding="utf-8"))
    assert latest_payload["name"] == "Snapshot Test Updated"
    assert previous_payload["name"] == "Snapshot Test"


def test_autosave_uses_project_progress_dir_for_saved_projects(tmp_path: Path) -> None:
    store = ProjectStore(state_dir=tmp_path / ".state")
    autosave = AutosaveService(store)
    target = tmp_path / "projects" / "saved-project.vcut.json"
    target.parent.mkdir(parents=True)
    project = Project.empty("Saved Project", path=str(target))

    autosave.save(project)
    recovery_path = autosave.recovery_path(project)
    assert recovery_path == target.parent / ".vantacut-progress" / "saved-project.vcut.autosave.vcut.json"
    assert recovery_path.exists()

    recovered = autosave.load(project)
    assert recovered.name == project.name
    assert recovered.path == str(target.resolve())
