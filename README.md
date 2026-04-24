# VantaCut

VantaCut is a desktop-like TUI nonlinear video editor built with Python and
Textual. The product direction is a terminal-native NLE with a real project
model, timeline engine, subtitle tooling, mpv preview bridge, and ffmpeg export
pipeline.

## Current State

The application boots into an empty real project instead of a fake demo. The
main flows now include:

- `New` project creation into any folder on the machine
- project save/load with recent project tracking
- project-local autosave and progress snapshots under `.vantacut-progress/`
- media import from any folder on the machine
- graphical source preview in-terminal through ffmpeg, with mpv transport when available
- timeline insertion, split, trim, move, ripple delete, and undo/redo
- subtitle editing and SRT import/export
- export planning through ffmpeg

Preview, probing, and export still depend on external tools:

- `ffmpeg` for terminal preview and export
- `mpv` for transport controls when JSON IPC is available
- `ffprobe` for richer media probing
- Unix domain socket support for mpv JSON IPC

If these tools are missing, VantaCut now reports that clearly in the UI and in
the doctor output instead of failing silently.

## Prerequisites

Python dependencies are expected under `.deps`.

System dependencies:

```bash
mpv
ffmpeg
ffprobe
```

On Ubuntu / Debian:

```bash
sudo apt-get update
sudo apt-get install -y mpv ffmpeg
```

## Run

The repo is configured to use a local `.deps` directory for Python
dependencies in constrained environments.

```bash
PYTHONPATH=.deps python3 -m vantacut
```

## Doctor

Run the built-in environment and smoke checker first:

```bash
PYTHONPATH=.deps python3 -m vantacut.doctor
```

It verifies:

- writable VantaCut state directory
- Unix socket IPC capability for mpv preview
- available preview backends
- presence of `mpv`, `ffmpeg`, and `ffprobe`
- project save/load round-trip
- media probe fallback path

The command exits non-zero only if VantaCut has no usable graphical preview
backend or required external tools are missing.

## Test

Automated test suite:

```bash
PYTHONPATH=.deps python3 -m pytest -q
```

## Manual Verification

Use this exact checklist after `vantacut.doctor` passes:

1. Start the app.
   `PYTHONPATH=.deps python3 -m vantacut`
2. Create a project.
   Press `Ctrl+N`, choose an empty folder, and confirm that a `.vcut.json`
   file appears inside that folder.
3. Import media from a different folder.
   Click `Import`, browse to a video, audio, image, or subtitle file outside
   the project folder, and confirm it appears in the Media bin.
4. Verify preview.
   Select imported video, audio, and image assets in turn and confirm mpv
   transport or the terminal preview updates to the beginning of the source. If
   doctor reports `unix_socket_ipc=blocked`, VantaCut will use the terminal
   graphical preview instead of mpv transport.
5. Insert into the timeline.
   Select the asset and press `I`. Confirm the clip appears on the correct
   track.
6. Edit the clip.
   Drag it, trim either edge, split with `S`, and undo/redo with
   `Ctrl+Z` / `Ctrl+Y`.
7. Save, reopen, and recover.
   Click `Save` to write the current project file. Quit, relaunch, then open
   the project either by clicking it under `Project -> Recent Projects` or by
   clicking `Open` and selecting the `.vcut.json` file. If you want to recover
   unsaved progress, press `Ctrl+Shift+R`; VantaCut keeps project-local
   autosave and latest/previous snapshots under the project's
   `.vantacut-progress/` folder.
8. Test subtitles.
   Open the `Subtitles` tab, add a cue, edit text, export SRT, then import it
   back.
9. Test export.
   Open export, choose a preset and output path, and confirm ffmpeg runs
   without freezing the UI.

## Module Layout

See [docs/architecture.md](docs/architecture.md) for the architecture plan,
milestones, and subsystem boundaries.

## Saved Projects

To open a saved project:

1. Start VantaCut with `PYTHONPATH=.deps python3 -m vantacut`.
2. Open it from the left `Project` tab under `Recent Projects`, or click
   `Open` in the toolbar and choose the `.vcut.json` file directly.
3. If the project file is older than the autosave state, press `Ctrl+Shift+R`
   to recover the newer in-progress version from `.vantacut-progress/`.
