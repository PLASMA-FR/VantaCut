from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from vantacut.models.asset import AssetKind
from vantacut.models.project import Project
from vantacut.models.timeline import ScaleMode, TimelineClip, TrackKind
from vantacut.export.presets import ExportPreset, get_preset


@dataclass(frozen=True, slots=True)
class ExportOptions:
    output_path: str
    preset_name: str
    overwrite: bool = False
    burn_subtitles: bool = False
    debug_mode: bool = False
    subtitle_path: str | None = None


@dataclass(frozen=True, slots=True)
class InputSpec:
    args: list[str]
    source: str | None


@dataclass(frozen=True, slots=True)
class ExportPlan:
    args: list[str]
    filtergraph: str
    output_path: str
    inputs: list[InputSpec]
    command_preview: str


@dataclass(frozen=True, slots=True)
class Segment:
    clip: TimelineClip | None
    start: int
    duration: int


class ExportCommandBuilder:
    def build(self, project: Project, options: ExportOptions) -> ExportPlan:
        preset = get_preset(options.preset_name)
        width = preset.width or project.settings.width
        height = preset.height or project.settings.height
        video_track = project.track(TrackKind.VIDEO)
        audio_track = project.track(TrackKind.AUDIO)
        video_segments = self._segments_for_track(video_track.clips)
        if not video_segments:
            raise ValueError("The project has no video clips to export.")

        inputs: list[InputSpec] = []
        filter_lines: list[str] = []
        video_labels: list[str] = []
        audio_labels: list[str] = []
        video_input_index_by_clip: dict[str, int] = {}
        next_input_index = 0

        for index, segment in enumerate(video_segments):
            if segment.clip is None:
                filter_lines.append(
                    f"color=c=black:s={width}x{height}:d={segment.duration / 1000:.3f},format=yuv420p[vseg{index}]"
                )
                video_labels.append(f"[vseg{index}]")
                continue
            clip = segment.clip
            asset = project.asset(clip.asset_id)
            if asset is None:
                continue
            if asset.kind is AssetKind.IMAGE:
                input_args = [
                    "-loop",
                    "1",
                    "-t",
                    f"{clip.duration / 1000:.3f}",
                    "-i",
                    asset.path,
                ]
            else:
                input_args = ["-i", asset.path]
            inputs.append(InputSpec(args=input_args, source=asset.path))
            video_input_index_by_clip[clip.id] = next_input_index
            filter_lines.extend(
                self._video_filter_lines(
                    next_input_index,
                    index,
                    clip,
                    asset.kind,
                    width,
                    height,
                )
            )
            video_labels.append(f"[vseg{index}]")
            next_input_index += 1

        if audio_track.clips:
            audio_segments = self._segments_for_track(audio_track.clips)
            for index, segment in enumerate(audio_segments):
                if segment.clip is None:
                    filter_lines.append(
                        f"anullsrc=r={project.settings.sample_rate}:cl=stereo:d={segment.duration / 1000:.3f}[aseg{index}]"
                    )
                    audio_labels.append(f"[aseg{index}]")
                    continue
                clip = segment.clip
                asset = project.asset(clip.asset_id)
                if asset is None:
                    continue
                inputs.append(InputSpec(args=["-i", asset.path], source=asset.path))
                filter_lines.append(
                    f"[{next_input_index}:a]atrim=start={clip.source_in / 1000:.3f}:end={(clip.source_in + clip.duration) / 1000:.3f},asetpts=PTS-STARTPTS[aseg{index}]"
                )
                audio_labels.append(f"[aseg{index}]")
                next_input_index += 1
        else:
            audio_labels = self._fallback_audio_labels(
                project,
                video_segments,
                filter_lines,
                video_input_index_by_clip,
            )

        filter_lines.append(
            f"{''.join(video_labels)}concat=n={len(video_labels)}:v=1:a=0[vcat]"
        )
        if audio_labels:
            filter_lines.append(
                f"{''.join(audio_labels)}concat=n={len(audio_labels)}:v=0:a=1[aout]"
            )
        else:
            total_duration = max(segment.start + segment.duration for segment in video_segments)
            filter_lines.append(
                f"anullsrc=r={project.settings.sample_rate}:cl=stereo:d={total_duration / 1000:.3f}[aout]"
            )

        video_output = "[vcat]"
        if options.burn_subtitles and options.subtitle_path:
            subtitle_path = options.subtitle_path.replace("\\", "\\\\").replace(":", "\\:")
            filter_lines.append(
                f"{video_output}subtitles='{subtitle_path}'[vout]"
            )
            video_output = "[vout]"

        args = ["-hide_banner", "-loglevel", "info", "-stats"]
        args.append("-y" if options.overwrite else "-n")
        for spec in inputs:
            args.extend(spec.args)
        filtergraph = ";".join(filter_lines)
        args.extend(
            [
                "-filter_complex",
                filtergraph,
                "-map",
                video_output,
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                str(preset.crf),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                options.output_path,
            ]
        )
        return ExportPlan(
            args=args,
            filtergraph=filtergraph,
            output_path=options.output_path,
            inputs=inputs,
            command_preview="ffmpeg " + shlex.join(args),
        )

    def _segments_for_track(self, clips: list[TimelineClip]) -> list[Segment]:
        ordered = sorted(clips, key=lambda clip: clip.start)
        segments: list[Segment] = []
        cursor = 0
        for clip in ordered:
            if clip.start > cursor:
                segments.append(Segment(None, cursor, clip.start - cursor))
            segments.append(Segment(clip, clip.start, clip.duration))
            cursor = max(cursor, clip.end)
        return segments

    def _video_filter_lines(
        self,
        input_index: int,
        segment_index: int,
        clip: TimelineClip,
        kind: AssetKind,
        width: int,
        height: int,
    ) -> list[str]:
        lines: list[str] = []
        filters: list[str] = []
        source = f"[{input_index}:v]"
        if kind is not AssetKind.IMAGE:
            filters.append(
                f"trim=start={clip.source_in / 1000:.3f}:end={(clip.source_in + clip.duration) / 1000:.3f}"
            )
        filters.append("setpts=PTS-STARTPTS")
        if clip.transform.crop_width > 0 and clip.transform.crop_height > 0:
            filters.append(
                f"crop={clip.transform.crop_width}:{clip.transform.crop_height}:{clip.transform.crop_x}:{clip.transform.crop_y}"
            )
        if clip.transform.rotation:
            filters.append(f"rotate={clip.transform.rotation}*PI/180:c=black")
        if clip.transform.scale_mode is ScaleMode.FIT:
            filters.append(
                f"scale={width}:{height}:force_original_aspect_ratio=decrease"
            )
            overlay_x = f"(main_w-overlay_w)/2+{clip.transform.position_x}"
            overlay_y = f"(main_h-overlay_h)/2+{clip.transform.position_y}"
        elif clip.transform.scale_mode is ScaleMode.FILL:
            filters.append(
                f"scale={width}:{height}:force_original_aspect_ratio=increase"
            )
            overlay_x = f"(main_w-overlay_w)/2+{clip.transform.position_x}"
            overlay_y = f"(main_h-overlay_h)/2+{clip.transform.position_y}"
        else:
            filters.append(f"scale={width}:{height}")
            overlay_x = str(clip.transform.position_x)
            overlay_y = str(clip.transform.position_y)
        lines.append(f"{source}{','.join(filters)}[vscaled{segment_index}]")
        lines.append(
            f"color=c=black:s={width}x{height}:d={clip.duration / 1000:.3f}[vbase{segment_index}]"
        )
        lines.append(
            f"[vbase{segment_index}][vscaled{segment_index}]overlay=x={overlay_x}:y={overlay_y}:shortest=1[vseg{segment_index}]"
        )
        return lines

    def _fallback_audio_labels(
        self,
        project: Project,
        segments: list[Segment],
        filter_lines: list[str],
        input_index_by_clip: dict[str, int],
    ) -> list[str]:
        audio_labels: list[str] = []
        for index, segment in enumerate(segments):
            if segment.clip is None:
                filter_lines.append(
                    f"anullsrc=r={project.settings.sample_rate}:cl=stereo:d={segment.duration / 1000:.3f}[aseg{index}]"
                )
                audio_labels.append(f"[aseg{index}]")
                continue
            clip = segment.clip
            if clip.muted or clip.id not in input_index_by_clip:
                filter_lines.append(
                    f"anullsrc=r={project.settings.sample_rate}:cl=stereo:d={segment.duration / 1000:.3f}[aseg{index}]"
                )
            else:
                input_index = input_index_by_clip[clip.id]
                filter_lines.append(
                    f"[{input_index}:a]atrim=start={clip.source_in / 1000:.3f}:end={(clip.source_in + clip.duration) / 1000:.3f},asetpts=PTS-STARTPTS[aseg{index}]"
                )
            audio_labels.append(f"[aseg{index}]")
        return audio_labels

