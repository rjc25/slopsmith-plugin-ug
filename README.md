# Slopsmith Plugin: Create from Tab

A plugin for [Slopsmith](https://github.com/YOUR_USERNAME/slopsmith) that adds the ability to search [Ultimate Guitar](https://www.ultimate-guitar.com/) for Guitar Pro tabs and convert them into playable Rocksmith 2014 CDLC with MIDI audio.

## Features

- Search Ultimate Guitar for Guitar Pro tabs (GP3/GP4/GP5)
- Auto-detect guitar and bass tracks
- Generate MIDI audio from the tab using FluidSynth
- Build a complete PSARC file with SNG compilation
- Real-time progress during build

## Installation

Clone this repository into your Slopsmith `plugins/` directory:

```bash
cd /path/to/slopsmith/plugins
git clone https://github.com/YOUR_USERNAME/slopsmith-plugin-ug.git ultimate_guitar
```

Then restart Slopsmith:

```bash
docker compose restart
```

The "Create from Tab" link will appear in the navigation bar.

## How It Works

1. Search for a song on Ultimate Guitar
2. Click a Guitar Pro tab result
3. The plugin downloads the tab, parses it, generates MIDI audio, converts to Rocksmith XML, compiles SNG, and packs everything into a PSARC
4. The new CDLC appears in your library

## Requirements

The Slopsmith Docker image includes all required dependencies (FluidSynth, ffmpeg, .NET for SNG compilation). No additional setup needed.

## License

MIT
