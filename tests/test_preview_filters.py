from vantacut.models.project import ProjectSettings
from vantacut.models.timeline import ScaleMode, TransformState
from vantacut.preview.filters import build_preview_filter_chain


def test_preview_filter_chain_includes_crop_scale_rotate() -> None:
    transform = TransformState(
        crop_x=10,
        crop_y=20,
        crop_width=800,
        crop_height=600,
        scale_mode=ScaleMode.FILL,
        rotation=15,
    )
    chain = build_preview_filter_chain(transform, ProjectSettings())
    assert "crop=800:600:10:20" in chain
    assert "force_original_aspect_ratio=increase" in chain
    assert "rotate=15" in chain
