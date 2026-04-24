# VantaCut Architecture Plan

## Core Principles

1. Correctness before feature count.
2. Timeline logic stays independent from terminal drawing.
3. Background work never blocks the Textual UI thread.
4. State changes flow through clean services and command objects.
5. Performance-sensitive services stay swappable for future Rust ports.

## Package Layout

`vantacut/app.py`
: Textual application shell, screen composition, global bindings, command
  routing, and pane sizing orchestration.

`vantacut/theme.py`
: Theme registry and semantic color variables for the app.

`vantacut/models/`
: Serializable data models for assets, timeline clips/tracks, subtitles, and
  projects.

`vantacut/services/`
: Persistence, session state, autosave, export execution, media probing, and
  notification-oriented services.

`vantacut/timeline/`
: Timebase utilities, snapping, split/ripple logic, and layout-agnostic
  timeline operations.

`vantacut/subtitles/`
: Subtitle editing logic, validation, overlap detection, and SRT I/O.

`vantacut/preview/`
: Preview controller abstraction and mpv JSON IPC implementation.

`vantacut/export/`
: ffmpeg preset definitions, filtergraph generation, and export plan assembly.

`vantacut/widgets/`
: Reusable presentation widgets such as pane splitters, timeline, media bin,
  inspector, dialogs, subtitle editor, toolbar, and status bar.

`vantacut/actions/`
: Command objects and routed editor actions for undo/redo-safe mutations.

`tests/`
: Core engine tests, export generation tests, and Textual smoke tests.

## State Model

The app separates persisted project state from ephemeral editor session state.

### Persisted project state

- project metadata
- media asset catalog
- timeline tracks and clips
- subtitle cues
- markers and settings
- clip transform/effect state

### Ephemeral session state

- current playhead
- selected asset/clip/cue
- zoom and scroll positions
- preview connection state
- dirty/save status
- transient notifications

## Milestones

1. Shell, theme, desktop panes, mouse resize foundation.
2. Project/media model, save/load, asset browser.
3. Timeline engine, playhead, ruler, zoom and scroll.
4. Clip insertion and selection workflow.
5. Drag move, trim, snapping, ripple operations.
6. mpv preview bridge and transport sync.
7. Subtitle editor, cue validation, SRT I/O.
8. Inspector for crop/transform/effect state.
9. ffmpeg export planning and execution.
10. Undo/redo, autosave, crash recovery, command palette, help overlay.

## Portability Plan

The following interfaces are intentionally narrow so they can move to Rust later
without rewriting the UI layer:

- timeline operations
- subtitle validation and transforms
- media probe service
- preview controller transport
- ffmpeg plan generation
- export execution state machine

