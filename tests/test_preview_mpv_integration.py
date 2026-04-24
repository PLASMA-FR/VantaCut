import asyncio
import os
from pathlib import Path
import textwrap

import pytest

from vantacut.core.environment import unix_socket_ipc_supported
from vantacut.preview.mpv import MpvPreviewController


def test_mpv_preview_controller_talks_to_json_ipc_server(
    monkeypatch,
    tmp_path: Path,
) -> None:
    if not unix_socket_ipc_supported(tmp_path):
        pytest.skip("Unix socket IPC is not available in this environment.")

    async def run() -> None:
        fake_mpv = tmp_path / "mpv"
        fake_mpv.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import asyncio
                import json
                import os
                import sys

                socket_path = None
                for arg in sys.argv[1:]:
                    if arg.startswith("--input-ipc-server="):
                        socket_path = arg.split("=", 1)[1]
                        break
                if socket_path is None:
                    raise SystemExit("missing socket path")
                try:
                    os.unlink(socket_path)
                except FileNotFoundError:
                    pass

                state = {"pause": True, "time-pos": 0.0, "path": None, "vf": ""}
                quit_event = asyncio.Event()

                async def handle(reader, writer):
                    raw = await reader.readline()
                    request = json.loads(raw.decode("utf-8"))
                    command = request.get("command", [])
                    response = {"error": "success", "request_id": request.get("request_id")}
                    name = command[0]
                    if name == "loadfile":
                        state["path"] = command[1]
                        state["time-pos"] = 0.0
                        state["pause"] = True
                    elif name == "set_property":
                        state[command[1]] = command[2]
                    elif name == "get_property":
                        response["data"] = state.get(command[1])
                    elif name == "cycle" and command[1] == "pause":
                        state["pause"] = not state["pause"]
                    elif name == "seek":
                        amount = float(command[1])
                        mode = command[2]
                        if mode == "absolute":
                            state["time-pos"] = amount
                        else:
                            state["time-pos"] += amount
                    elif name == "frame-step":
                        state["time-pos"] += 1 / 30
                    elif name == "frame-back-step":
                        state["time-pos"] = max(0.0, state["time-pos"] - (1 / 30))
                    elif name == "vf":
                        state["vf"] = command[2] if len(command) > 2 else ""
                    elif name == "quit":
                        quit_event.set()
                    writer.write((json.dumps(response) + "\\n").encode("utf-8"))
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()

                async def main():
                    server = await asyncio.start_unix_server(handle, path=socket_path)
                    await quit_event.wait()
                    server.close()
                    await server.wait_closed()
                    try:
                        os.unlink(socket_path)
                    except FileNotFoundError:
                        pass

                asyncio.run(main())
                """
            ),
            encoding="utf-8",
        )
        fake_mpv.chmod(0o755)
        monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

        controller = MpvPreviewController()
        await controller.connect()
        assert controller.state.connected is True

        await controller.load_file("/tmp/media/example.mp4")
        assert controller.state.loaded_path == "/tmp/media/example.mp4"

        await controller.seek_absolute(3.5)
        assert controller.state.position_seconds == 3.5

        await controller.toggle()
        assert controller.state.playing is True

        await controller.set_filters("crop=100:100")
        await controller.query_position()
        assert controller.state.position_seconds >= 3.5

        await controller.close()
        assert controller.state.connected is False

    asyncio.run(run())
