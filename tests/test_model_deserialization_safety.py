from vantacut.models.project import ProjectSettings
from vantacut.models.timeline import ScaleMode, TransformState


def test_transform_state_from_dict_coerces_untrusted_numeric_fields() -> None:
    transform = TransformState.from_dict(
        {
            "crop_x": "10",
            "crop_y": "0[vx];[vx]null",
            "crop_width": "640",
            "crop_height": "480",
            "position_x": "2.5",
            "position_y": "bad",
            "rotation": "15",
            "opacity": "2",
            "scale_mode": "invalid",
        }
    )

    assert transform.crop_x == 10
    assert transform.crop_y == 0
    assert transform.crop_width == 640
    assert transform.crop_height == 480
    assert transform.position_x == 2.5
    assert transform.position_y == 0.0
    assert transform.rotation == 15.0
    assert transform.opacity == 1.0
    assert transform.scale_mode is ScaleMode.FIT


def test_project_settings_from_dict_coerces_untrusted_numeric_fields() -> None:
    settings = ProjectSettings.from_dict(
        {
            "width": "1920",
            "height": "foo",
            "fps": 0,
            "sample_rate": "-1",
        }
    )

    assert settings.width == 1920
    assert settings.height == 1080
    assert settings.fps == 1
    assert settings.sample_rate == 1
