# Preview Synchronization Notes

VantaCut now supports two preview backends:

- `mpv` transport over JSON IPC when Unix socket IPC is available
- terminal-native frame rendering through `ffmpeg` when running in pure TTY
  environments without GUI transport

The app keeps these concerns separate:

- `MpvPreviewController` handles transport, playback, pause, and source seeking
- `PreviewFrameRenderer` renders video frames, still images, and audio waveforms
  directly into the Textual preview pane

## How sync works

1. The selected clip or asset determines the preview source.
2. The preview seek position is computed from:

`clip.source_in + max(0, playhead - clip.start)`

3. This means the preview reflects the currently selected source clip at the
   correct source-relative offset for the timeline playhead.
4. If mpv transport is available, VantaCut also loads the source into mpv,
   seeks there, applies preview filters, and pauses.
5. Regardless of mpv availability, VantaCut can render a terminal preview frame
   from the same source/time selection using `ffmpeg`.
6. Because preview reflects source media rather than a fully composited
   timeline, timeline
   effects and multi-track compositing are deferred to export.

## Why this design

- It keeps terminal redraws light.
- It avoids blocking the UI thread with video decoding by using async workers.
- It keeps a usable graphical preview available in SSH and tmux sessions where
  GUI mpv windows are not possible.
- The transport bridge and frame renderer are isolated so performance-sensitive
  pieces can move later into Rust or another preview daemon.
