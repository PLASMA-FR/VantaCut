from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from vantacut.models.asset import AssetKind
from vantacut.models.project import Project
from vantacut.models.timeline import TimelineClip, TimelineTrack, TrackKind
from vantacut.timeline.snapping import SnapCandidate, SnapResult, resolve_snap


@dataclass(frozen=True, slots=True)
class ClipPreview:
    clip_id: str
    track_id: str
    start: int
    duration: int
    source_in: int
    snap_result: SnapResult

    @property
    def end(self) -> int:
        return self.start + self.duration


class TimelineEngine:
    def __init__(self, minimum_duration: int = 120) -> None:
        self.minimum_duration = minimum_duration

    def select_clip(self, project: Project, clip_id: str | None) -> None:
        for track in project.tracks:
            for clip in track.clips:
                clip.selected = clip.id == clip_id

    def insert_asset(
        self,
        project: Project,
        asset_id: str,
        at_time: int,
    ) -> TimelineClip:
        asset = project.asset(asset_id)
        if asset is None:
            raise ValueError(f"Unknown asset: {asset_id}")
        track_kind = self._track_kind_for_asset(asset.kind)
        track = project.track(track_kind)
        clip = TimelineClip(
            asset_id=asset.id,
            track_id=track.id,
            start=max(0, at_time),
            duration=asset.duration_ticks or self._default_duration(asset.kind),
        )
        track.clips.append(clip)
        self._sort(track)
        self.select_clip(project, clip.id)
        return clip

    def preview_move(
        self,
        project: Project,
        clip_id: str,
        desired_start: int,
        target_track_id: str | None,
        playhead: int,
        threshold: int,
    ) -> ClipPreview:
        track, clip = self.find_clip(project, clip_id)
        target_track = self.find_track(project, target_track_id or track.id)
        desired_start = max(0, desired_start)
        snap = resolve_snap(
            desired_start,
            self.collect_snap_candidates(
                project,
                target_track.id,
                exclude_clip_id=clip_id,
                playhead=playhead,
            ),
            threshold=threshold,
        )
        return ClipPreview(
            clip_id=clip.id,
            track_id=target_track.id,
            start=max(0, snap.time),
            duration=clip.duration,
            source_in=clip.source_in,
            snap_result=snap,
        )

    def move_clip(
        self,
        project: Project,
        clip_id: str,
        desired_start: int,
        target_track_id: str | None,
        playhead: int,
        threshold: int,
    ) -> ClipPreview:
        track, clip = self.find_clip(project, clip_id)
        preview = self.preview_move(
            project,
            clip_id,
            desired_start,
            target_track_id,
            playhead,
            threshold,
        )
        if preview.track_id != track.id:
            target_track = self.find_track(project, preview.track_id)
            track.clips.remove(clip)
            target_track.clips.append(clip)
        else:
            target_track = track
        clip.track_id = preview.track_id
        clip.start = preview.start
        self._sort(target_track)
        if target_track is not track:
            self._sort(track)
        return preview

    def preview_trim_left(
        self,
        project: Project,
        clip_id: str,
        desired_start: int,
        playhead: int,
        threshold: int,
    ) -> ClipPreview:
        _, clip = self.find_clip(project, clip_id)
        asset = project.asset(clip.asset_id)
        desired_start = min(desired_start, clip.end - self.minimum_duration)
        desired_start = max(0, desired_start)
        snap = resolve_snap(
            desired_start,
            self.collect_snap_candidates(
                project,
                clip.track_id,
                exclude_clip_id=clip.id,
                playhead=playhead,
            ),
            threshold=threshold,
        )
        delta = snap.time - clip.start
        proposed_source_in = clip.source_in + delta
        if asset and asset.duration_ticks:
            proposed_source_in = max(
                0,
                min(proposed_source_in, asset.duration_ticks - self.minimum_duration),
            )
        delta = proposed_source_in - clip.source_in
        start = clip.start + delta
        duration = max(self.minimum_duration, clip.duration - delta)
        return ClipPreview(
            clip_id=clip.id,
            track_id=clip.track_id,
            start=start,
            duration=duration,
            source_in=proposed_source_in,
            snap_result=SnapResult(start, snap.candidate),
        )

    def trim_clip_left(
        self,
        project: Project,
        clip_id: str,
        desired_start: int,
        playhead: int,
        threshold: int,
    ) -> ClipPreview:
        _, clip = self.find_clip(project, clip_id)
        preview = self.preview_trim_left(
            project,
            clip_id,
            desired_start,
            playhead,
            threshold,
        )
        clip.start = preview.start
        clip.duration = preview.duration
        clip.source_in = preview.source_in
        return preview

    def preview_trim_right(
        self,
        project: Project,
        clip_id: str,
        desired_end: int,
        playhead: int,
        threshold: int,
    ) -> ClipPreview:
        _, clip = self.find_clip(project, clip_id)
        asset = project.asset(clip.asset_id)
        desired_end = max(clip.start + self.minimum_duration, desired_end)
        snap = resolve_snap(
            desired_end,
            self.collect_snap_candidates(
                project,
                clip.track_id,
                exclude_clip_id=clip.id,
                playhead=playhead,
            ),
            threshold=threshold,
        )
        end = snap.time
        if asset and asset.duration_ticks:
            end = min(end, clip.start + asset.duration_ticks - clip.source_in)
        end = max(clip.start + self.minimum_duration, end)
        return ClipPreview(
            clip_id=clip.id,
            track_id=clip.track_id,
            start=clip.start,
            duration=end - clip.start,
            source_in=clip.source_in,
            snap_result=SnapResult(end, snap.candidate),
        )

    def trim_clip_right(
        self,
        project: Project,
        clip_id: str,
        desired_end: int,
        playhead: int,
        threshold: int,
    ) -> ClipPreview:
        _, clip = self.find_clip(project, clip_id)
        preview = self.preview_trim_right(
            project,
            clip_id,
            desired_end,
            playhead,
            threshold,
        )
        clip.duration = preview.duration
        return preview

    def split_clip(
        self,
        project: Project,
        clip_id: str,
        split_time: int,
    ) -> tuple[TimelineClip, TimelineClip]:
        track, clip = self.find_clip(project, clip_id)
        split_time = max(clip.start + self.minimum_duration, split_time)
        split_time = min(clip.end - self.minimum_duration, split_time)
        if split_time <= clip.start or split_time >= clip.end:
            raise ValueError("Split time must fall inside the clip body.")
        left_duration = split_time - clip.start
        right_duration = clip.end - split_time
        right_clip = TimelineClip(
            asset_id=clip.asset_id,
            track_id=clip.track_id,
            start=split_time,
            duration=right_duration,
            source_in=clip.source_in + left_duration,
            muted=clip.muted,
            linked=clip.linked,
            transform=deepcopy(clip.transform),
        )
        clip.duration = left_duration
        track.clips.append(right_clip)
        self._sort(track)
        self.select_clip(project, right_clip.id)
        return clip, right_clip

    def ripple_delete(self, project: Project, clip_id: str) -> int:
        track, clip = self.find_clip(project, clip_id)
        shift = clip.duration
        clip_end = clip.end
        track.clips.remove(clip)
        for other in track.clips:
            if other.start >= clip_end:
                other.start -= shift
        self._sort(track)
        return shift

    def collect_snap_candidates(
        self,
        project: Project,
        track_id: str,
        exclude_clip_id: str | None,
        playhead: int | None,
    ) -> list[SnapCandidate]:
        track = self.find_track(project, track_id)
        candidates: list[SnapCandidate] = []
        if playhead is not None:
            candidates.append(SnapCandidate(playhead, "playhead"))
        for marker in project.markers:
            candidates.append(SnapCandidate(marker.time, f"marker:{marker.label}"))
        for clip in track.clips:
            if clip.id == exclude_clip_id:
                continue
            candidates.append(SnapCandidate(clip.start, "clip-start"))
            candidates.append(SnapCandidate(clip.end, "clip-end"))
        return candidates

    def find_track(self, project: Project, track_id: str) -> TimelineTrack:
        return next(track for track in project.tracks if track.id == track_id)

    def find_clip(self, project: Project, clip_id: str) -> tuple[TimelineTrack, TimelineClip]:
        for track in project.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    return track, clip
        raise ValueError(f"Unknown clip: {clip_id}")

    def _sort(self, track: TimelineTrack) -> None:
        track.clips.sort(key=lambda clip: (clip.start, clip.id))

    def _default_duration(self, kind: AssetKind) -> int:
        if kind is AssetKind.IMAGE:
            return 5_000
        if kind is AssetKind.SUBTITLE:
            return 3_000
        return 8_000

    def _track_kind_for_asset(self, kind: AssetKind) -> TrackKind:
        if kind in {AssetKind.VIDEO, AssetKind.IMAGE}:
            return TrackKind.VIDEO
        if kind is AssetKind.AUDIO:
            return TrackKind.AUDIO
        return TrackKind.SUBTITLE

