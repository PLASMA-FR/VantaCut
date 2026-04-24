from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import socket


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    name: str
    path: str | None

    @property
    def available(self) -> bool:
        return self.path is not None

    def summary(self) -> str:
        if self.path is None:
            return f"{self.name}: missing"
        return f"{self.name}: {self.path}"


@dataclass(frozen=True, slots=True)
class RuntimeEnvironment:
    state_dir: str
    unix_socket_ipc: bool
    mpv: DependencyStatus
    ffmpeg: DependencyStatus
    ffprobe: DependencyStatus

    def dependencies(self) -> tuple[DependencyStatus, ...]:
        return (self.mpv, self.ffmpeg, self.ffprobe)

    def missing(self) -> list[str]:
        return [item.name for item in self.dependencies() if not item.available]

    @property
    def mpv_transport_available(self) -> bool:
        return self.unix_socket_ipc and self.mpv.available

    @property
    def terminal_preview_available(self) -> bool:
        return self.ffmpeg.available

    @property
    def graphical_preview_available(self) -> bool:
        return self.mpv_transport_available or self.terminal_preview_available


def detect_runtime_environment(state_dir: str | Path) -> RuntimeEnvironment:
    resolved_state_dir = Path(state_dir).expanduser().resolve()
    return RuntimeEnvironment(
        state_dir=str(resolved_state_dir),
        unix_socket_ipc=unix_socket_ipc_supported(resolved_state_dir),
        mpv=DependencyStatus("mpv", shutil.which("mpv")),
        ffmpeg=DependencyStatus("ffmpeg", shutil.which("ffmpeg")),
        ffprobe=DependencyStatus("ffprobe", shutil.which("ffprobe")),
    )


def unix_socket_ipc_supported(state_dir: str | Path) -> bool:
    target_dir = Path(state_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    socket_path = target_dir / f"socket-capability-{os.getpid()}.sock"
    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server_socket.bind(str(socket_path))
        return True
    except OSError:
        return False
    finally:
        server_socket.close()
        socket_path.unlink(missing_ok=True)
