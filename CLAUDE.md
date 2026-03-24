# TTM — TikTok Media (v1.0.0)

Automated highlight extractor: downloads YouTube videos, analyzes them with multi-modal AI, renders vertical TikTok-format clips.

## Entry Points

| Command | Description |
|---------|-------------|
| `python main.py` | Interactive CLI |
| `cd backend && uvicorn main:app --reload` | REST API server (port 8000) |
| `cd frontend && npm run dev` | React dev server (port 5173) |

## Architecture

```
TikTok-Media/
├── main.py                  # CLI entry point
├── config.yaml              # Master config (all tuneable params)
├── core/
│   ├── clip_detector.py     # ClipDetector — main orchestrator
│   ├── scorer.py            # HighlightScorer — ranking + selection
│   ├── schemas.py           # Dataclasses: FinalClip, CandidateMoment, etc.
│   ├── audio_analyzer.py    # RMS/onset/spectral peak detection
│   ├── text_analyzer.py     # Whisper ASR + emotion scoring
│   ├── motion_analyzer.py   # Optical flow / frame diff
│   ├── scene_detector.py    # Scene cut detection
│   └── face_analyzer.py     # Haar cascade + DeepFace emotions
├── processing/
│   ├── youtube_batch.py     # YouTubeBatchProcessor — channel/video loop
│   ├── chunk_processor.py   # Parallel chunk analysis
│   ├── clip_extractor.py    # Segment extraction
│   └── video_montage.py     # FFmpeg render to 1080x1920
├── utils/
│   ├── youtube_utils.py     # yt-dlp wrapper
│   ├── ffmpeg_utils.py      # FFmpeg helpers
│   ├── cache_manager.py     # Disk cache
│   └── logger.py            # get_logger() — propagate=False per logger
├── backend/                 # FastAPI REST API
└── frontend/                # React + Tailwind SPA
```

## Key Classes

- **`ClipDetector`** (`core/clip_detector.py`) — accepts `config: dict`, orchestrates chunk analysis, scoring, rendering
- **`HighlightScorer`** (`core/scorer.py`) — `select_highlights(chunks, video_duration)` → `list[CandidateMoment]`
- **`YouTubeBatchProcessor`** (`processing/youtube_batch.py`) — `process_channels(channels, max_channels, videos_per_channel)` → `dict`

## num_clips Control Point

`config["video_processing"]["max_selected_clips_per_video"]` (default: `1` in config.yaml)

Capped at `scorer.py:54` after diversity selection. The backend injects the job's `num_clips` value here before constructing `ClipDetector` — **no changes needed to any existing file**.

## Logger Pattern

`utils/logger.py` creates named loggers with `propagate=False`. Logger names in use:
`clip_detector`, `chunk_worker`, `highlight_extractor`, `youtube_batch`, `youtube_source`, `video_montage`, `clip_extractor`

To capture logs in the backend, add a `QueueHandler` to each named logger after `ClipDetector` is constructed.

## Output Structure

```
output/{run_subdir}/{channel_name}/{video_title}/
├── clips/clip_01.mp4
├── thumbnails/clip_01.jpg
├── raw_segments/clip_01_source.mp4
└── report.json
```

## Backend Ports & CORS

- API: `http://localhost:8000`
- Frontend dev: `http://localhost:5173` (proxied to API via Vite)

## Coding Conventions

- `from __future__ import annotations` at top of every Python file
- `pathlib.Path` over `os.path`
- No `print()` in library code — use `self.logger`
- Pydantic v2 models in backend
- React Query for server state, Zustand for UI state
