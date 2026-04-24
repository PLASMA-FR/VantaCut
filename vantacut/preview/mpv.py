from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

from vantacut.core.logging import get_logger
from vantacut.preview.base import PreviewController, PreviewState


class MpvPreviewController(PreviewController):
    def __init__(self) -> None:
        super().__init__()
        self.logger = get_logger("vantacut.preview.mpv")
        self.process: asyncio.subprocess.Process | None = None
        self.socket_path = os.path.join(
            tempfile.gettempdir(),
            f"vantacut-mpv-{os.getpid()}.sock",
        )
        self._request_id = 0

    async def connect(self) -> PreviewState:
        if (
            self.state.last_error == "mpv not found"
            and not self.state.connected
            and not self.state.process_running
        ):
            return self.state
        if self.state.connected and self.process and self.process.returncode is None:
            return self.state
        if self.process and self.process.returncode is not None:
            self.state.connected = False
            self.state.process_running = False
        try:
            await self._spawn_process()
            await self._wait_for_socket()
            self.state.connected = True
            self.state.process_running = True
            self.state.last_error = None
            self.logger.info("mpv_connected socket=%s", self.socket_path)
        except FileNotFoundError:
            self.state.connected = False
            self.state.process_running = False
            self.state.last_error = "mpv not found"
            self.logger.info("mpv_unavailable socket=%s", self.socket_path)
        except Exception as exc:  # noqa: BLE001
            self.state.connected = False
            self.state.process_running = False
            self.state.last_error = str(exc)
            self.logger.info("mpv_connect_error error=%s", exc)
        return self.state

    async def load_file(self, path: str) -> PreviewState:
        await self.connect()
        if not self.state.connected:
            return self.state
        response = await self._send(["loadfile", path, "replace"])
        if response.get("error") == "success":
            self.state.loaded_path = path
            self.state.position_seconds = 0.0
            await self.pause()
        else:
            self.state.last_error = str(response.get("error"))
        return self.state

    async def play(self) -> PreviewState:
        return await self._set_pause(False)

    async def pause(self) -> PreviewState:
        return await self._set_pause(True)

    async def toggle(self) -> PreviewState:
        await self.connect()
        if not self.state.connected:
            return self.state
        await self._send(["cycle", "pause"])
        return await self.query_position()

    async def seek_absolute(self, seconds: float) -> PreviewState:
        await self.connect()
        if not self.state.connected:
            return self.state
        await self._send(["seek", seconds, "absolute", "exact"])
        self.state.position_seconds = max(0.0, seconds)
        return self.state

    async def seek_relative(self, seconds: float) -> PreviewState:
        await self.connect()
        if not self.state.connected:
            return self.state
        await self._send(["seek", seconds, "relative", "exact"])
        return await self.query_position()

    async def frame_step(self) -> PreviewState:
        await self.connect()
        if not self.state.connected:
            return self.state
        await self._send(["frame-step"])
        return await self.query_position()

    async def frame_back_step(self) -> PreviewState:
        await self.connect()
        if not self.state.connected:
            return self.state
        await self._send(["frame-back-step"])
        return await self.query_position()

    async def query_position(self) -> PreviewState:
        await self.connect()
        if not self.state.connected:
            return self.state
        pause = await self._send(["get_property", "pause"])
        position = await self._send(["get_property", "time-pos"])
        path = await self._send(["get_property", "path"])
        if pause.get("error") == "success":
            self.state.playing = not bool(pause.get("data"))
        if position.get("error") == "success" and position.get("data") is not None:
            self.state.position_seconds = float(position["data"])
        if path.get("error") == "success" and path.get("data"):
            self.state.loaded_path = str(path["data"])
        return self.state

    async def set_filters(self, filter_chain: str | None) -> PreviewState:
        await self.connect()
        if not self.state.connected:
            return self.state
        response = await self._send(["vf", "set", filter_chain or ""])
        if response.get("error") not in {"success", None}:
            self.state.last_error = str(response.get("error"))
        return self.state

    async def close(self) -> None:
        if self.process and self.process.returncode is None:
            try:
                await self._send(["quit"])
            except Exception:  # noqa: BLE001
                self.process.terminate()
        if self.process:
            await self.process.wait()
        self.state.connected = False
        self.state.process_running = False

    async def _set_pause(self, paused: bool) -> PreviewState:
        await self.connect()
        if not self.state.connected:
            return self.state
        response = await self._send(["set_property", "pause", paused])
        if response.get("error") == "success":
            self.state.playing = not paused
        return await self.query_position()

    async def _spawn_process(self) -> None:
        if self.process and self.process.returncode is None:
            return
        try:
            Path(self.socket_path).unlink(missing_ok=True)
        except OSError:
            pass
        self.process = await asyncio.create_subprocess_exec(
            "mpv",
            "--idle=yes",
            "--pause=yes",
            "--force-window=yes",
            "--keep-open=yes",
            "--title=VantaCut Preview",
            f"--input-ipc-server={self.socket_path}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def _wait_for_socket(self) -> None:
        for delay in (0.05, 0.1, 0.2, 0.4, 0.8, 1.0, 1.5, 2.0):
            if Path(self.socket_path).exists():
                return
            if self.process and self.process.returncode is not None:
                raise RuntimeError(
                    f"mpv exited before IPC socket appeared (code {self.process.returncode})"
                )
            await asyncio.sleep(delay)
        raise RuntimeError("mpv IPC socket did not appear")

    async def _send(self, command: list[object]) -> dict[str, object]:
        self._request_id += 1
        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            payload = {"command": command, "request_id": self._request_id}
            writer.write((json.dumps(payload) + "\n").encode("utf-8"))
            await writer.drain()
            raw = await reader.readline()
            writer.close()
            await writer.wait_closed()
        except OSError as exc:
            self.state.connected = False
            self.state.process_running = False
            self.state.last_error = str(exc)
            raise RuntimeError(str(exc)) from exc
        if not raw:
            self.state.connected = False
            raise RuntimeError("mpv IPC returned no data")
        response = json.loads(raw.decode("utf-8"))
        if response.get("error") not in {"success", None}:
            self.state.last_error = str(response.get("error"))
        return response
