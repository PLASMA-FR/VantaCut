from vantacut.export.command_builder import ExportCommandBuilder, ExportOptions
from vantacut.models.project import Project
from vantacut.models.timeline import ScaleMode


def test_export_builder_generates_concat_and_audio() -> None:
    project = Project.demo()
    builder = ExportCommandBuilder()
    plan = builder.build(
        project,
        ExportOptions(
            output_path="out.mp4",
            preset_name="1080p",
            overwrite=True,
            burn_subtitles=False,
        ),
    )
    assert "concat=n=3:v=1:a=0" in plan.filtergraph
    assert "concat=n=1:v=0:a=1" in plan.filtergraph or "concat=n=3:v=0:a=1" in plan.filtergraph
    assert "-c:v" in plan.args


def test_export_builder_includes_crop_and_subtitles() -> None:
    project = Project.demo()
    project.tracks[0].clips[0].transform.crop_width = 1000
    project.tracks[0].clips[0].transform.crop_height = 700
    project.tracks[0].clips[0].transform.scale_mode = ScaleMode.FILL
    builder = ExportCommandBuilder()
    plan = builder.build(
        project,
        ExportOptions(
            output_path="out.mp4",
            preset_name="1080p",
            overwrite=True,
            burn_subtitles=True,
            subtitle_path="/tmp/captions.srt",
        ),
    )
    assert "crop=1000:700" in plan.filtergraph
    assert "subtitles='/tmp/captions.srt'" in plan.filtergraph
