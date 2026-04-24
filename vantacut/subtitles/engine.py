from __future__ import annotations

from dataclasses import dataclass

from vantacut.models.project import Project
from vantacut.models.subtitles import SubtitleCue


@dataclass(frozen=True, slots=True)
class SubtitleIssue:
    cue_id: str
    level: str
    message: str


class SubtitleEngine:
    def add_cue(self, project: Project, start: int, end: int, text: str = "") -> SubtitleCue:
        cue = SubtitleCue(start=max(0, start), end=max(start + 400, end), text=text)
        project.subtitles.append(cue)
        self._sort(project)
        return cue

    def update_cue(self, project: Project, cue_id: str, start: int, end: int, text: str) -> SubtitleCue:
        cue = self.find_cue(project, cue_id)
        cue.start = max(0, start)
        cue.end = max(cue.start + 100, end)
        cue.text = text
        self._sort(project)
        return cue

    def delete_cue(self, project: Project, cue_id: str) -> None:
        cue = self.find_cue(project, cue_id)
        project.subtitles.remove(cue)

    def shift_cue(self, project: Project, cue_id: str, delta_ms: int) -> SubtitleCue:
        cue = self.find_cue(project, cue_id)
        duration = cue.duration
        cue.start = max(0, cue.start + delta_ms)
        cue.end = cue.start + duration
        self._sort(project)
        return cue

    def move_cue_to_playhead(self, project: Project, cue_id: str, playhead: int) -> SubtitleCue:
        cue = self.find_cue(project, cue_id)
        duration = cue.duration
        cue.start = max(0, playhead)
        cue.end = cue.start + duration
        self._sort(project)
        return cue

    def set_cue_start(self, project: Project, cue_id: str, playhead: int) -> SubtitleCue:
        cue = self.find_cue(project, cue_id)
        cue.start = max(0, min(playhead, cue.end - 100))
        self._sort(project)
        return cue

    def set_cue_end(self, project: Project, cue_id: str, playhead: int) -> SubtitleCue:
        cue = self.find_cue(project, cue_id)
        cue.end = max(cue.start + 100, playhead)
        self._sort(project)
        return cue

    def split_cue(self, project: Project, cue_id: str, playhead: int) -> tuple[SubtitleCue, SubtitleCue]:
        cue = self.find_cue(project, cue_id)
        split_time = max(cue.start + 100, min(playhead, cue.end - 100))
        right = SubtitleCue(start=split_time, end=cue.end, text=cue.text)
        cue.end = split_time
        project.subtitles.append(right)
        self._sort(project)
        return cue, right

    def merge_with_next(self, project: Project, cue_id: str) -> SubtitleCue:
        self._sort(project)
        cue = self.find_cue(project, cue_id)
        cues = sorted(project.subtitles, key=lambda item: item.start)
        index = cues.index(cue)
        if index == len(cues) - 1:
            raise ValueError("No following cue to merge with.")
        next_cue = cues[index + 1]
        cue.end = max(cue.end, next_cue.end)
        cue.text = f"{cue.text}\n{next_cue.text}".strip()
        project.subtitles.remove(next_cue)
        self._sort(project)
        return cue

    def validate(self, project: Project) -> dict[str, list[SubtitleIssue]]:
        issues: dict[str, list[SubtitleIssue]] = {}
        cues = sorted(project.subtitles, key=lambda item: item.start)
        for cue in cues:
            issues[cue.id] = []
            if cue.end <= cue.start:
                issues[cue.id].append(
                    SubtitleIssue(cue.id, "error", "End time must be after start time.")
                )
            if cue.duration < 700:
                issues[cue.id].append(
                    SubtitleIssue(cue.id, "warning", "Cue is very short.")
                )
            if not cue.text.strip():
                issues[cue.id].append(
                    SubtitleIssue(cue.id, "warning", "Cue text is empty.")
                )
        for first, second in zip(cues, cues[1:]):
            if second.start < first.end:
                issues[first.id].append(
                    SubtitleIssue(first.id, "warning", "Cue overlaps the next cue.")
                )
                issues[second.id].append(
                    SubtitleIssue(second.id, "warning", "Cue overlaps the previous cue.")
                )
        return issues

    def find_cue(self, project: Project, cue_id: str) -> SubtitleCue:
        return next(cue for cue in project.subtitles if cue.id == cue_id)

    def _sort(self, project: Project) -> None:
        project.subtitles.sort(key=lambda cue: (cue.start, cue.end, cue.id))

