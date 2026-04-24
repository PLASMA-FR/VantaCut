# Example Export Commands

These commands are representative outputs from the ffmpeg builder.

## 1080p with burned subtitles

```bash
PYTHONPATH=.deps python3 -m vantacut
```

Open the export dialog, choose `1080p`, enable subtitle burn-in, and enable
debug mode to see the exact `ffmpeg` command in the Logs panel.

## Source-like quality

Use the `source-like quality` preset to preserve the project resolution while
still running through the deterministic transform and concat pipeline.

