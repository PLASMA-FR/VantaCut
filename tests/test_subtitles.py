from vantacut.models.project import Project
from vantacut.subtitles.engine import SubtitleEngine
from vantacut.subtitles.srt import export_srt, parse_srt


def test_srt_round_trip() -> None:
    cues = parse_srt(
        "1\n00:00:00,500 --> 00:00:02,000\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld\n"
    )
    exported = export_srt(cues)
    assert "00:00:00,500 --> 00:00:02,000" in exported
    assert "World" in exported


def test_subtitle_validation_detects_overlap_and_short_cue() -> None:
    project = Project.demo()
    engine = SubtitleEngine()
    project.subtitles[0].end = 3_000
    issues = engine.validate(project)
    assert any("overlaps" in issue.message.lower() for issue in issues[project.subtitles[1].id])
    assert any("short" in issue.message.lower() for issue in issues[project.subtitles[2].id]) is False


def test_shift_and_merge_cues() -> None:
    project = Project.demo()
    engine = SubtitleEngine()
    cue = project.subtitles[0]
    shifted = engine.shift_cue(project, cue.id, 500)
    assert shifted.start == 900
    merged = engine.merge_with_next(project, shifted.id)
    assert "Cut from interview" in merged.text
