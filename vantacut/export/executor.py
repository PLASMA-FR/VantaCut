from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from vantacut.export.command_builder import ExportPlan


TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")


@dataclass(frozen=True, slots=True)
class ExportEvent:
    kind: str
    message: str
    progress_seconds: float | None = None


class ExportExecutor:
    def __init__(self) -> None:
        self.process: asyncio.subprocess.Process | None = None

    async def run(
        self,
        plan: ExportPlan,
        on_event: Callable[[ExportEvent], Awaitable[None] | None] | None = None,
    ) -> int:
        async def emit(event: ExportEvent) -> None:
            if on_event is None:
                return
            result = on_event(event)
            if result is not None and hasattr(result, "__await__"):
                await result  # type: ignore[misc]

        try:
            self.process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                *plan.args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            await emit(ExportEvent("error", "ffmpeg not found"))
            return 127

        await emit(ExportEvent("start", plan.command_preview))
        assert self.process.stderr is not None
        while True:
            line = await self.process.stderr.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            progress = self._parse_progress_seconds(text)
            await emit(ExportEvent("log", text, progress))
        code = await self.process.wait()
        await emit(ExportEvent("done" if code == 0 else "error", f"ffmpeg exited with {code}"))
        return code

    async def cancel(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()

    def _parse_progress_seconds(self, line: str) -> float | None:
        match = TIME_RE.search(line)
        if not match:
            return None
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        return hours * 3600 + minutes * 60 + seconds

