from pathlib import Path

from vantacut.core.environment import detect_runtime_environment
from vantacut.models.project import Project


def test_detect_runtime_environment_reports_missing_tools(monkeypatch, tmp_path: Path) -> None:
    def fake_which(name: str) -> str | None:
        if name == "ffmpeg":
            return "/usr/bin/ffmpeg"
        return None

    monkeypatch.setattr("shutil.which", fake_which)
    monkeypatch.setattr(
        "vantacut.core.environment.unix_socket_ipc_supported",
        lambda state_dir: False,
    )
    environment = detect_runtime_environment(tmp_path)
    assert environment.state_dir == str(tmp_path.resolve())
    assert environment.unix_socket_ipc is False
    assert environment.ffmpeg.available is True
    assert environment.mpv.available is False
    assert environment.ffprobe.available is False
    assert environment.graphical_preview_available is True
    assert environment.terminal_preview_available is True
    assert environment.mpv_transport_available is False
    assert environment.missing() == ["mpv", "ffprobe"]


def test_empty_project_has_required_tracks() -> None:
    project = Project.empty("Untitled Project")
    assert [track.name for track in project.tracks] == [
        "Video 1",
        "Audio 1",
        "Subtitles",
    ]
    assert project.assets == []
