from vantacut.models.project import Project
from vantacut.timeline.engine import TimelineEngine
from vantacut.timeline.snapping import SnapCandidate, resolve_snap


def test_snap_logic_prefers_nearest_candidate() -> None:
    result = resolve_snap(
        7900,
        [SnapCandidate(8000, "edge"), SnapCandidate(7600, "marker")],
        threshold=300,
    )
    assert result.time == 8000
    assert result.candidate is not None
    assert result.candidate.label == "edge"


def test_move_clip_snaps_to_neighbor_edge() -> None:
    project = Project.demo()
    engine = TimelineEngine()
    second_clip = project.tracks[0].clips[1]
    preview = engine.move_clip(
        project,
        second_clip.id,
        7850,
        second_clip.track_id,
        playhead=0,
        threshold=300,
    )
    assert preview.start == 8000


def test_trim_clip_left_updates_source_in() -> None:
    project = Project.demo()
    engine = TimelineEngine()
    second_clip = project.tracks[0].clips[1]
    preview = engine.trim_clip_left(
        project,
        second_clip.id,
        8200,
        playhead=0,
        threshold=0,
    )
    assert preview.start == 8200
    assert preview.source_in == 1300
    assert preview.duration == 5200


def test_split_clip_creates_right_segment() -> None:
    project = Project.demo()
    engine = TimelineEngine()
    first_clip = project.tracks[0].clips[0]
    left, right = engine.split_clip(project, first_clip.id, 3000)
    assert left.duration == 3000
    assert right.start == 3000
    assert right.source_in == 3000
    assert right.duration == 5000


def test_ripple_delete_closes_gap() -> None:
    project = Project.demo()
    engine = TimelineEngine()
    first_clip = project.tracks[0].clips[0]
    shifted = engine.ripple_delete(project, first_clip.id)
    second_clip = project.tracks[0].clips[0]
    assert shifted == 8000
    assert second_clip.start == 400
