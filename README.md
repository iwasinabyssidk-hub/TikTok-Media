████████╗████████╗███╗   ███╗
╚══██╔══╝╚══██╔══╝████╗ ████║
   ██║      ██║   ██╔████╔██║
   ██║      ██║   ██║╚██╔╝██║
   ██║      ██║   ██║ ╚═╝ ██║
   ╚═╝      ╚═╝   ╚═╝     ╚═╝

TTM - TikTok Media
Created by Soup / DJ DALBAEB

========================================================================
1. Overview
========================================================================

TTM is a console-first Python application for turning long YouTube videos
into vertical short-form clips.

This repository now ships with one workflow only:
- load a list of channels from `data/source_channels.txt`
- pull random long-form videos from those channels
- analyze subtitles and audio
- pick the single strongest clip from each source video
- render a vertical output with subtitles and a source-title header


========================================================================
2. Current Scope
========================================================================

The launcher now exposes one mode only:
- channel list mode

Removed from the launcher:
- movie-title mode
- generic film search mode
- local-file mode
- single-author special modes


========================================================================
3. Features
========================================================================

- single entrypoint: `python main.py`
- single input file: `data/source_channels.txt`
- random channel order
- random source video order
- one best clip per source video
- subtitle-first ranking on CPU
- vertical 1080x1920 rendering
- animated subtitles
- source video title above the video area
- clean GitHub layout with cache/download/output folders ignored


========================================================================
4. Project Structure
========================================================================

- `main.py` - terminal launcher
- `config.yaml` - pipeline configuration
- `data/source_channels.txt` - channel source list
- `core/` - analyzers and ranking logic
- `processing/` - chunk pipeline, batch processing, clip rendering
- `utils/` - ffmpeg helpers, caching, YouTube helpers
- `assets/` - optional music and branding assets
- `output/` - generated clips and reports


========================================================================
5. Installation
========================================================================

Requirements:
- Python 3.11 or newer
- ffmpeg available in PATH, local `bin/`, or via `imageio-ffmpeg`
- packages from `requirements.txt`

Install dependencies:

`pip install -r requirements.txt`


========================================================================
6. Usage
========================================================================

Run the launcher:

`python main.py`

The app will ask for:
- minimum clip length
- maximum clip length
- channel count for the current run
- default number of source videos per channel
- per-channel overrides

Optional CLI arguments:

- `--config config.yaml`
- `--channels-file data/source_channels.txt`
- `--output output`
- `--channels-limit 3`
- `--videos-per-channel 2`
- `--min-clip 40`
- `--max-clip 65`

Example:

`python main.py --channels-limit 2 --videos-per-channel 1 --min-clip 45 --max-clip 75`


========================================================================
7. Channel File Format
========================================================================

File:

`data/source_channels.txt`

Use one source per line. Supported values:
- channel name
- `@handle`
- full YouTube channel or profile URL

Example:

@channel_one
@channel_two
https://www.youtube.com/@channel_three
Daniks


========================================================================
8. Output Layout
========================================================================

Each run creates a folder like:

`output/channels1_MM-DD/`

Inside it you will find:
- channel folders
- source video folders
- `clips/clip_01.mp4`
- `thumbnails/...`
- `report.json`
- `youtube_batch_report.json`


========================================================================
9. Performance Notes
========================================================================

For CPU-focused machines:
- keep `cpu_text_first_mode` enabled
- keep `skip_motion_on_cpu` enabled
- keep `skip_scene_on_cpu` enabled
- start with small batches

Recommended first test:
- 1 or 2 channels
- 1 source video per channel


========================================================================
10. Publishing Notes
========================================================================

The repository is prepared for GitHub:
- `.cache/` is ignored
- `.downloads/` is ignored
- `output/` is ignored except `.gitkeep`
- `__pycache__/` is ignored


========================================================================
11. Credit
========================================================================

TTM - TikTok Media
Created by Soup / DJ DALBAEB
