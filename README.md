# SlopSmith Ultimate Guitar — Enhanced Fork

**Search Ultimate Guitar → select a tab → attach real audio → get professional-grade CDLC with per-note sync and separated stems.**

This fork of [slopsmith-plugin-ug](https://github.com/byrongamatos/slopsmith-plugin-ug) adds real audio support, automatic per-note alignment, and Demucs stem separation to the Ultimate Guitar search and import flow. Search for any song, pick a Guitar Pro tab from UG, pair it with the actual recording, and get a perfectly synced CDLC.

## What's New

| Feature | Original | This Fork |
|---------|----------|-----------|
| Audio source | MIDI only (robot) | Real audio file (mp3/ogg/wav) |
| Chart sync | No sync (offset 0.0) | Automatic per-note alignment |
| Stems | None | Demucs 5-stem separation |
| Build flow | Search → instant build | Search → configure → build |
| Output quality | Practice-grade (MIDI audio) | Professional-grade (real recording) |

## How It Works

### 1. Search
Search Ultimate Guitar for any song. Browse results and pick the best Guitar Pro tab (.gp3/.gp4/.gp5).

### 2. Configure (new)
After selecting a tab, a configure panel appears:
- **Audio mode**: MIDI (default, same as original) or Real Audio
- **Real Audio**: drag and drop an mp3/ogg/wav of the actual song, or enter a local file path
- **Stem Separation**: optionally split into 5 stems via Demucs

### 3. Auto-Sync
When real audio is attached, the plugin automatically aligns every chart note:

1. Downloads the GP tab from Ultimate Guitar
2. Renders MIDI from the tab as a timing reference
3. Cross-correlates MIDI audio against the real recording
4. Detects drift using segment-by-segment analysis
5. Applies per-segment offset correction to every chart note

The result: every note in the chart lands at the exact moment it plays in the real recording.

### 4. Stem Separation (optional)
Demucs AI splits the real audio into 5 stems:
- Guitar, Drums, Vocals, Bass, Other

Use with the [Stem Toggle plugin](https://github.com/rjc25/slopsmith-stems) to mute/unmute any instrument while practicing.

### 5. Output
A professional-grade PSARC with:
- Real audio (the actual studio recording)
- Every note synced to the recording
- Guitar Pro techniques preserved
- Stems alongside (optional)

## Usage

1. Install this plugin in SlopSmith's `plugins/` directory
2. Open SlopSmith and go to the UG search screen
3. Search for a song
4. Click a Guitar Pro tab result
5. Choose MIDI or Real Audio mode
6. If real audio: attach your audio file
7. Optionally enable stem separation
8. Click Build
9. Play your new CDLC

## Flow Diagram

```
Search Ultimate Guitar
    │
    ├── Select Guitar Pro tab
    │
    ├── Configure:
    │   ├── MIDI mode → instant build (same as original)
    │   └── Real Audio mode:
    │       ├── Attach audio file (drag-drop or path)
    │       └── Optional: enable Demucs stems
    │
    ├── Build:
    │   ├── Download GP tab from UG
    │   ├── Generate MIDI audio (timing reference)
    │   ├── If real audio:
    │   │   ├── Cross-correlate for sync offset
    │   │   ├── Segment-by-segment drift detection
    │   │   └── Apply offset to chart conversion
    │   ├── Convert GP → Rocksmith XML
    │   ├── Pack PSARC (with real audio or MIDI)
    │   └── Optional: Demucs stem separation
    │
    └── Result: Professional CDLC ready to play
```

## Requirements

- SlopSmith (Docker)
- numpy (for auto-sync)
- For stems: [Replicate API token](https://replicate.com/account/api-tokens) (~$0.021/song)
- ffmpeg

## Backward Compatibility

The UG search, download, and MIDI build flow works exactly as the original. Real audio and stems are optional additions. If you don't attach audio, you get the same MIDI CDLC as before.

## Related

- [slopsmith-stems](https://github.com/rjc25/slopsmith-stems) — Stem toggle, drum highway, vocal highway, multiplayer, and management dashboard
- [slopsmith-plugin-tabimport (fork)](https://github.com/rjc25/slopsmith-plugin-tabimport) — Same enhancements for drag-and-drop GP import

## Credits

- Original: [byrongamatos/slopsmith-plugin-ug](https://github.com/byrongamatos/slopsmith-plugin-ug)
- Enhanced by [rjc25](https://github.com/rjc25) with real audio sync, drift detection, and Demucs stems
