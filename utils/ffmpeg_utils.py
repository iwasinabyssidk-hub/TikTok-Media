from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any

import cv2

try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None


def resolve_ffmpeg_binary(tool_name: str) -> str:

    local_bin = Path.cwd() / "bin" / f"{tool_name}.exe"
    if local_bin.exists():
        return str(local_bin)

    path_hit = _which(tool_name)
    if path_hit:
        return path_hit

    if tool_name == "ffmpeg" and imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

    return tool_name


def _which(executable: str) -> str | None:
    paths = os.environ.get("PATH", "").split(os.pathsep)
    extensions = [""]
    if os.name == "nt":
        extensions.extend([".exe", ".cmd", ".bat"])
    for base in paths:
        if not base:
            continue
        for ext in extensions:
            candidate = Path(base) / f"{executable}{ext}"
            if candidate.exists():
                return str(candidate)
    return None


def run_command(cmd: list[str], capture_output: bool = True) -> subprocess.CompletedProcess[str]:

    if cmd:
        if cmd[0] == "ffmpeg":
            cmd = [resolve_ffmpeg_binary("ffmpeg"), *cmd[1:]]
        elif cmd[0] == "ffprobe":
            cmd = [resolve_ffmpeg_binary("ffprobe"), *cmd[1:]]
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "Unknown command failure"
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{stderr}")
    return result


def ffprobe_json(video_path: str | Path) -> dict[str, Any]:
    ffprobe_binary = resolve_ffmpeg_binary("ffprobe")
    if ffprobe_binary == "ffprobe":
        raise FileNotFoundError("ffprobe binary is not available")
    cmd = [
        ffprobe_binary,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(video_path),
    ]
    result = run_command(cmd)
    return json.loads(result.stdout)


def probe_video(video_path: str | Path) -> dict[str, Any]:
    try:
        data = ffprobe_json(video_path)
        format_info = data.get("format", {})
        video_stream = next(
            (stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"),
            {},
        )
        audio_stream = next(
            (stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"),
            {},
        )
        fps_text = video_stream.get("avg_frame_rate", "0/1")
        if "/" in fps_text:
            num, den = fps_text.split("/", 1)
            fps = float(num) / max(float(den), 1.0)
        else:
            fps = float(fps_text or 0.0)
        return {
            "duration": float(format_info.get("duration", 0.0)),
            "bit_rate": int(format_info.get("bit_rate", 0) or 0),
            "width": int(video_stream.get("width", 0) or 0),
            "height": int(video_stream.get("height", 0) or 0),
            "fps": fps,
            "has_audio": bool(audio_stream),
            "sample_rate": int(audio_stream.get("sample_rate", 0) or 0),
        }
    except Exception:
        return probe_video_opencv(video_path)


def probe_video_opencv(video_path: str | Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
    frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = frame_count / fps if fps > 0 else 0.0
    capture.release()
    return {
        "duration": float(duration),
        "bit_rate": 0,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": True,
        "sample_rate": 0,
    }


def extract_audio(
    video_path: str | Path,
    audio_path: str | Path,
    start: float,
    end: float,
    sample_rate: int = 16000,
) -> Path:
    duration = max(end - start, 0.01)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(audio_path),
    ]
    run_command(cmd)
    return Path(audio_path)


def build_visual_proxy(
    video_path: str | Path,
    proxy_path: str | Path,
    *,
    fps: float = 2.0,
    width: int = 160,
    height: int = 90,
    crf: int = 38,
) -> Path:
    proxy_path = Path(proxy_path)
    temp_path = proxy_path.with_name(f"{proxy_path.stem}.tmp{proxy_path.suffix}")
    vf = (
        f"fps={max(fps, 0.2):.3f},"
        f"scale={max(width, 16)}:{max(height, 16)}:force_original_aspect_ratio=decrease,"
        f"pad={max(width, 16)}:{max(height, 16)}:(ow-iw)/2:(oh-ih)/2:black"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel",
        "auto",
        "-i",
        str(video_path),
        "-an",
        "-sn",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        str(temp_path),
    ]
    run_command(cmd)
    temp_path.replace(proxy_path)
    return proxy_path


def capture_frame(video_path: str | Path, timecode: float, output_path: str | Path) -> Path:
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{max(timecode, 0.0):.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    run_command(cmd)
    return Path(output_path)


def cut_video_copy(
    video_path: str | Path,
    output_path: str | Path,
    start: float,
    end: float,
) -> Path:
    duration = max(end - start, 0.01)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(video_path),
        "-c",
        "copy",
        "-avoid_negative_ts",
        "1",
        str(output_path),
    ]
    run_command(cmd)
    return Path(output_path)


def seconds_to_ass(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:d}:{minutes:02d}:{secs:05.2f}"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def gaussian_score(value: float, target: float, spread: float) -> float:
    if spread <= 0:
        return 0.0
    exponent = -((value - target) ** 2) / (2 * (spread**2))
    return math.exp(exponent)
