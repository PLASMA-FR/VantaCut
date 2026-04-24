from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExportPreset:
    name: str
    label: str
    width: int | None
    height: int | None
    crf: int = 18


PRESETS: dict[str, ExportPreset] = {
    "source-like": ExportPreset("source-like", "Source-like quality", None, None, 18),
    "1080p": ExportPreset("1080p", "1080p", 1920, 1080, 20),
    "720p": ExportPreset("720p", "720p", 1280, 720, 21),
    "1080x1920": ExportPreset("1080x1920", "1080x1920 vertical", 1080, 1920, 20),
}


def get_preset(name: str) -> ExportPreset:
    return PRESETS[name]


def preset_options() -> list[tuple[str, str]]:
    return [(preset.label, preset.name) for preset in PRESETS.values()]

