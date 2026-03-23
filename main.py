from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

BANNER = [
    "████████╗████████╗███╗   ███╗",
    "╚══██╔══╝╚══██╔══╝████╗ ████║",
    "   ██║      ██║   ██╔████╔██║",
    "   ██║      ██║   ██║╚██╔╝██║",
    "   ██║      ██║   ██║ ╚═╝ ██║",
    "   ╚═╝      ╚═╝   ╚═╝     ╚═╝",
]

SUBTITLE = "TTM - TikTok Media"
CREDIT = "Created by Soup / DJ DALBAEB"
FRAME_WIDTH = 78


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def configure_console() -> None:
    if os.name == "nt":
        os.system("chcp 65001 > nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def print_line(char: str = "═") -> None:
    print(char * FRAME_WIDTH)


def print_centered(text: str = "") -> None:
    print(text.center(FRAME_WIDTH))


def print_banner() -> None:
    clear_screen()
    print_line()
    for line in BANNER:
        print_centered(line)
    print()
    print_centered(SUBTITLE)
    print_centered(CREDIT)
    print_line()
    print()


def print_section(title: str) -> None:
    label = f" {title.strip()} "
    border = max(0, FRAME_WIDTH - len(label))
    left = border // 2
    right = border - left
    print(f"{'─' * left}{label}{'─' * right}")


def print_kv(label: str, value: object) -> None:
    print(f"  {label:<24} {value}")


def print_separator() -> None:
    print_line("─")


def load_channels(path: str | Path) -> list[str]:
    channels_path = Path(path)
    return [
        line.strip()
        for line in channels_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def preview_channels_for_prompt(channels: list[str], limit: int | None, config: dict) -> list[str]:
    prepared = [channel.strip() for channel in channels if channel.strip()]
    youtube_config = config.get("youtube", {}) or {}
    if bool(youtube_config.get("randomize_channel_order", True)) and len(prepared) > 1:
        rng = random.Random(youtube_config.get("random_seed"))
        rng.shuffle(prepared)
    if limit and limit > 0:
        return prepared[:limit]
    return prepared


def prompt_optional_limit(default_value: int | None = None, subject_label: str = "channels") -> int | None:
    default_text = "" if default_value in (None, 0) else str(default_value)
    prompt = (
        f"How many {subject_label} should be processed in this run? (Enter = no limit): "
        if not default_text
        else f"How many {subject_label} should be processed in this run? [Enter = {default_text}]: "
    )
    raw = input(prompt).strip()
    if not raw:
        return default_value if default_value not in (None, 0) else None
    try:
        value = int(raw)
    except ValueError:
        print("Invalid number. Continuing with no limit.")
        return default_value if default_value not in (None, 0) else None
    return value if value > 0 else None


def prompt_clip_duration_range(default_min: float, default_max: float) -> tuple[float, float]:
    min_raw = input(f"Minimum clip length in seconds [{default_min:g}]: ").strip()
    max_raw = input(f"Maximum clip length in seconds [{default_max:g}]: ").strip()
    try:
        min_value = float(min_raw) if min_raw else float(default_min)
    except ValueError:
        print("Invalid minimum length. Using the config value.")
        min_value = float(default_min)
    try:
        max_value = float(max_raw) if max_raw else float(default_max)
    except ValueError:
        print("Invalid maximum length. Using the config value.")
        max_value = float(default_max)
    if min_value <= 0:
        min_value = float(default_min)
    if max_value <= 0:
        max_value = float(default_max)
    if max_value < min_value:
        min_value, max_value = max_value, min_value
    print(f"Clip length for this run: {min_value:g}-{max_value:g} sec.")
    return min_value, max_value


def prompt_videos_per_channel(default_value: int) -> int:
    raw = input(f"Default number of source videos per channel [{default_value}]: ").strip()
    if not raw:
        print(f"Default videos per channel: {default_value}")
        return default_value
    try:
        value = int(raw)
    except ValueError:
        print("Invalid number. Using the config value.")
        value = default_value
    value = max(1, value)
    print(f"Default videos per channel: {value}")
    return value


def prompt_channel_video_limits(channels: list[str], default_value: int) -> dict[str, int]:
    print_section("Per-Channel Limits")
    print("Press Enter to keep the default value. Enter 0 to skip a channel.")
    limits: dict[str, int] = {}
    for channel in channels:
        raw = input(f'Videos to use from "{channel}" [{default_value}]: ').strip()
        if not raw:
            limits[channel] = default_value
            continue
        try:
            value = int(raw)
        except ValueError:
            print("Invalid number. Using the default value.")
            limits[channel] = default_value
            continue
        limits[channel] = max(0, value)
    print_separator()
    return limits


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TTM channel pipeline for automatic highlight extraction and vertical clip rendering."
    )
    parser.add_argument("--config", default="config.yaml", help="Path to the YAML configuration file.")
    parser.add_argument(
        "--channels-file",
        default=None,
        help="Path to a txt file with one YouTube channel, handle, or URL per line.",
    )
    parser.add_argument("--output", default=None, help="Override the output directory from config.")
    parser.add_argument("--channels-limit", type=int, default=None, help="How many channels to process in this run.")
    parser.add_argument(
        "--videos-per-channel",
        type=int,
        default=None,
        help="Default number of source videos to process per channel.",
    )
    parser.add_argument("--min-clip", type=float, default=None, help="Override the minimum clip duration.")
    parser.add_argument("--max-clip", type=float, default=None, help="Override the maximum clip duration.")
    return parser


def summarize_run_settings(
    channels_file: Path,
    output_dir: Path,
    channels: list[str],
    runtime_limit: int | None,
    min_clip: float,
    max_clip: float,
    default_video_limit: int,
) -> None:
    print_section("Run Setup")
    print_kv("Channels file", channels_file)
    print_kv("Output directory", output_dir)
    print_kv("Channels loaded", len(channels))
    print_kv("Channels this run", runtime_limit or "all")
    print_kv("Clip duration", f"{min_clip:g}-{max_clip:g} sec")
    print_kv("Videos per channel", default_video_limit)
    print_separator()
    print()


def print_final_summary(report: dict, output_dir: Path) -> None:
    run_subdir = report.get("run_subdir", "")
    report_path = output_dir / run_subdir / "youtube_batch_report.json"
    print()
    print_section("Done")
    print_kv("Processed channels", report.get("total_requested_channels", 0))
    print_kv("Processed videos", report.get("processed_videos", 0))
    print_kv("Run folder", output_dir / run_subdir)
    print_kv("Batch report", report_path)
    print_separator()


def main() -> None:
    args = build_parser().parse_args()

    import yaml

    from core.clip_detector import ClipDetector
    from processing.youtube_batch import YouTubeBatchProcessor

    config_path = Path(args.config)
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    if args.output:
        config.setdefault("project", {})["output_dir"] = args.output

    project_config = config.setdefault("project", {})
    youtube_config = config.setdefault("youtube", {})
    video_config = config.setdefault("video_processing", {})

    channels_file = Path(args.channels_file or project_config.get("channels_file", "data/source_channels.txt"))
    if not channels_file.exists():
        raise SystemExit(f"Channels file not found: {channels_file}")

    channels = load_channels(channels_file)
    if not channels:
        raise SystemExit(f"Channels file is empty: {channels_file}")

    output_dir = Path(project_config.get("output_dir", "output"))
    configured_default_video_limit = int(youtube_config.get("videos_per_channel", 2) or 2)
    runtime_limit = args.channels_limit
    default_video_limit = args.videos_per_channel or configured_default_video_limit

    configure_console()
    print_banner()

    min_clip_default = float(video_config.get("min_clip_duration", 40))
    max_clip_default = float(video_config.get("max_clip_duration", 65))
    if args.min_clip is not None or args.max_clip is not None:
        min_clip = float(args.min_clip if args.min_clip is not None else min_clip_default)
        max_clip = float(args.max_clip if args.max_clip is not None else max_clip_default)
        if max_clip < min_clip:
            min_clip, max_clip = max_clip, min_clip
        print(f"Clip length for this run: {min_clip:g}-{max_clip:g} sec.")
    else:
        min_clip, max_clip = prompt_clip_duration_range(min_clip_default, max_clip_default)
    video_config["min_clip_duration"] = min_clip
    video_config["max_clip_duration"] = max_clip

    if runtime_limit is None:
        runtime_limit = prompt_optional_limit(subject_label="channels from the file")
    default_video_limit = prompt_videos_per_channel(default_video_limit)
    youtube_config["videos_per_channel"] = default_video_limit

    channels_for_prompt = preview_channels_for_prompt(channels, runtime_limit, config)
    channel_limits = prompt_channel_video_limits(channels_for_prompt, default_video_limit)

    summarize_run_settings(
        channels_file=channels_file.resolve(),
        output_dir=output_dir.resolve(),
        channels=channels,
        runtime_limit=runtime_limit,
        min_clip=min_clip,
        max_clip=max_clip,
        default_video_limit=default_video_limit,
    )

    detector = ClipDetector(config=config)
    batch = YouTubeBatchProcessor(config=config, detector=detector, logger=detector.logger)
    report = batch.process_channels(
        channels=channels,
        max_channels=runtime_limit,
        videos_per_channel=channel_limits,
    )
    report["channels_file"] = str(channels_file.resolve())
    print_final_summary(report, output_dir=output_dir.resolve())


if __name__ == "__main__":
    main()
