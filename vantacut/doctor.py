from __future__ import annotations

import asyncio
import json
from pathlib import Path
import tempfile

from vantacut.core.environment import detect_runtime_environment
from vantacut.models.project import Project
from vantacut.services.media_probe import MediaProbeService
from vantacut.services.project_store import ProjectStore


def main() -> int:
    store = ProjectStore()
    environment = detect_runtime_environment(store._state_dir)
    probe = MediaProbeService()

    print("VantaCut doctor")
    print(f"state_dir={environment.state_dir}")
    print(
        "unix_socket_ipc="
        + ("ready" if environment.unix_socket_ipc else "blocked")
    )
    print(
        "preview_backends="
        + (
            ",".join(
                backend
                for backend, enabled in (
                    ("mpv_transport", environment.mpv_transport_available),
                    ("terminal_ffmpeg", environment.terminal_preview_available),
                )
                if enabled
            )
            or "none"
        )
    )
    for dependency in environment.dependencies():
        print(dependency.summary())

    with tempfile.TemporaryDirectory(prefix="vantacut-doctor-") as temp_dir:
        temp_root = Path(temp_dir)
        project_dir = temp_root / "project"
        project_dir.mkdir()
        project_path = project_dir / "project.vcut.json"

        project = Project.empty("Doctor Project", path=str(project_path))
        store.save(project, project_path)
        loaded = store.load(project_path)
        print(
            "project_round_trip="
            + json.dumps(
                {
                    "name": loaded.name,
                    "path": loaded.path,
                    "track_count": len(loaded.tracks),
                },
                sort_keys=True,
            )
        )

        media_path = temp_root / "probe.mp4"
        media_path.write_bytes(b"doctor-media")
        result = asyncio.run(probe.probe(media_path))
        print(
            "probe_result="
            + json.dumps(
                {
                    "path": result.path,
                    "kind": result.kind.value,
                    "duration_ticks": result.duration_ticks,
                    "metadata": result.metadata,
                },
                sort_keys=True,
            )
        )

    missing = environment.missing()
    if missing:
        print("missing_dependencies=" + ",".join(missing))
    if not environment.unix_socket_ipc:
        print("warning_capabilities=unix_socket_ipc")
    if missing or not environment.graphical_preview_available:
        if not environment.graphical_preview_available:
            print("missing_capabilities=graphical_preview")
        return 1
    print("doctor_status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
