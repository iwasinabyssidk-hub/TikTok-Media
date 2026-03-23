TTM - TikTok Media
Created by Soup / DJ DALBAEB

Overview

TTM is a Python tool for building vertical short-form clips from long YouTube videos.

Current repository scope:
- channel-list workflow only
- one best clip per source video
- subtitle-first ranking on CPU
- vertical output with subtitles and a source title overlay

Main Flow

1. Read channels from `data/source_channels.txt`
2. Search YouTube for long-form videos from those channels
3. Download selected source videos
4. Analyze subtitles and audio
5. Pick the strongest highlight from each source video
6. Render a vertical clip into `output/`

Features

- single launcher: `python main.py`
- random channel order
- random video order
- one best clip per source video
- subtitle-first selection
- vertical 1080x1920 montage
- animated subtitles
- source video title shown above the clip

Installation

Requirements:
- Python 3.11+
- ffmpeg
- dependencies from `requirements.txt`

Install:
`pip install -r requirements.txt`

Usage

Run:
`python main.py`

The launcher asks for:
- minimum clip length
- maximum clip length
- how many channels to process
- default videos per channel
- per-channel overrides

Optional CLI arguments:
- `--config config.yaml`
- `--channels-file data/source_channels.txt`
- `--output output`
- `--channels-limit 3`
- `--videos-per-channel 2`
- `--min-clip 40`
- `--max-clip 65`

Channel Input File

File:
`data/source_channels.txt`

Supported entries:
- channel name
- `@handle`
- full YouTube channel URL

Output

Each run creates a folder like:
`output/channels1_MM-DD/`

Inside:
- channel folders
- source video folders
- `clips/clip_01.mp4`
- `thumbnails/`
- `report.json`
- `youtube_batch_report.json`

Project Structure

- `main.py` - launcher
- `config.yaml` - configuration
- `data/source_channels.txt` - source channels
- `core/` - analyzers and ranking
- `processing/` - batch processing and rendering
- `utils/` - ffmpeg, cache, and YouTube helpers
- `assets/` - optional assets
- `output/` - generated results

GitHub Notes

This repository is prepared for publishing:
- `.cache/` is ignored
- `.downloads/` is ignored
- `output/` is ignored except `.gitkeep`
- `__pycache__/` is ignored

For the best GitHub presentation, see `README.md`.
