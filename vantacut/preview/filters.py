from __future__ import annotations

from vantacut.models.project import ProjectSettings
from vantacut.models.timeline import ScaleMode, TransformState


def build_preview_filter_chain(
    transform: TransformState,
    settings: ProjectSettings,
) -> str:
    parts: list[str] = []
    if transform.crop_width > 0 and transform.crop_height > 0:
        parts.append(
            f"crop={transform.crop_width}:{transform.crop_height}:{transform.crop_x}:{transform.crop_y}"
        )
    if transform.scale_mode is ScaleMode.FIT:
        parts.append(
            f"scale={settings.width}:{settings.height}:force_original_aspect_ratio=decrease"
        )
    elif transform.scale_mode is ScaleMode.FILL:
        parts.append(
            f"scale={settings.width}:{settings.height}:force_original_aspect_ratio=increase"
        )
    elif transform.scale_mode is ScaleMode.STRETCH:
        parts.append(f"scale={settings.width}:{settings.height}")
    if transform.rotation:
        parts.append(f"rotate={transform.rotation}*PI/180")
    return ",".join(parts)

