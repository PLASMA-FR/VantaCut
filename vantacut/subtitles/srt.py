from __future__ import annotations

import re

from vantacut.models.subtitles import SubtitleCue


TIME_RE = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{3})"
)


def parse_srt_timestamp(value: str) -> int:
    match = TIME_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {value}")
    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    milliseconds = int(match.group("ms"))
    total_ms = (((hours * 60) + minutes) * 60 + seconds) * 1000 + milliseconds
    return total_ms


def format_srt_timestamp(value_ms: int) -> str:
    hours, remainder = divmod(value_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def parse_srt(text: str) -> list[SubtitleCue]:
    blocks = re.split(r"\n\s*\n", text.strip().replace("\r\n", "\n"))
    cues: list[SubtitleCue] = []
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        timing_line = lines[1] if "-->" in lines[1] else lines[0]
        text_lines = lines[2:] if "-->" in lines[1] else lines[1:]
        start_text, end_text = [part.strip() for part in timing_line.split("-->")]
        cues.append(
            SubtitleCue(
                start=parse_srt_timestamp(start_text),
                end=parse_srt_timestamp(end_text),
                text="\n".join(text_lines),
            )
        )
    return cues


def export_srt(cues: list[SubtitleCue]) -> str:
    lines: list[str] = []
    for index, cue in enumerate(sorted(cues, key=lambda item: item.start), start=1):
        lines.extend(
            [
                str(index),
                f"{format_srt_timestamp(cue.start)} --> {format_srt_timestamp(cue.end)}",
                cue.text,
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"

