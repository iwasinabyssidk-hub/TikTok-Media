from __future__ import annotations

import textwrap
from pathlib import Path

from core.schemas import CandidateMoment
from utils.ffmpeg_utils import run_command, seconds_to_ass


class VideoMontage:


    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.montage_config = config.get("montage", {})
        self.watermark_config = config.get("watermark", {})
        self.assets_dir = Path(config.get("project", {}).get("assets_dir", "assets"))

    def render_clip(
        self,
        source_video: str,
        candidate: CandidateMoment,
        output_path: str | Path,
        working_dir: str | Path,
        has_audio: bool = True,
    ) -> Path:
        output_path = Path(output_path)
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)

        subtitle_path = working_dir / f"{output_path.stem}.ass"
        self._write_karaoke_ass(candidate, subtitle_path)
        title_card_path = working_dir / f"{output_path.stem}_title.txt"
        self._write_title_card(candidate, title_card_path)

        width = int(self.montage_config.get("width", 1080))
        height = int(self.montage_config.get("height", 1920))
        blur_strength = int(self.montage_config.get("blur_strength", 20))

        music_path = self._pick_music(output_path.stem)
        watermark_path = self._resolve_watermark()

        command = ["ffmpeg", "-y", "-i", str(source_video)]
        music_index = None
        watermark_index = None

        if music_path is not None:
            command.extend(["-stream_loop", "-1", "-i", str(music_path)])
            music_index = 1
        if watermark_path is not None:
            command.extend(["-i", str(watermark_path)])
            watermark_index = 2 if music_index is not None else 1

        video_filters = [
            f"[0:v]trim=start={candidate.start:.3f}:end={candidate.end:.3f},setpts=PTS-STARTPTS,split=2[vmain][vbg]",
            f"[vbg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur={blur_strength}:1[bg]",
            f"[vmain]scale={width}:{height}:force_original_aspect_ratio=decrease[fg]",
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[vcomp]",
            f"[vcomp]subtitles='{self._filter_path(subtitle_path)}'[vsub]",
            (
                f"[vsub]drawbox=x=56:y=56:w={width - 112}:h=150:color=black@0.38:t=fill,"
                f"drawtext=textfile='{self._filter_path(title_card_path)}':fontcolor=white:fontsize=46:"
                "line_spacing=10:borderw=2:bordercolor=black@0.55:x=(w-text_w)/2:y=78[vtitle]"
            ),
        ]

        current_video_label = "[vtitle]"
        if watermark_index is not None:
            scale_width = int(self.watermark_config.get("scale_width", 180))
            margin_right = int(self.watermark_config.get("margin_right", 48))
            margin_top = int(self.watermark_config.get("margin_top", 60))
            video_filters.append(f"[{watermark_index}:v]scale={scale_width}:-1[wm]")
            video_filters.append(
                f"{current_video_label}[wm]overlay=W-w-{margin_right}:{margin_top}[vout]"
            )
            current_video_label = "[vout]"
        else:
            video_filters.append(f"{current_video_label}null[vout]")
            current_video_label = "[vout]"

        audio_filters = []
        duration = candidate.end - candidate.start
        current_audio_label = None
        if has_audio:
            audio_filters.append(
                f"[0:a]atrim=start={candidate.start:.3f}:end={candidate.end:.3f},asetpts=PTS-STARTPTS,volume=1.0[basea]"
            )
            current_audio_label = "[basea]"
        if music_index is not None:
            music_volume = float(self.montage_config.get("music_volume", 0.18))
            audio_filters.append(
                f"[{music_index}:a]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,volume={music_volume}[mixa]"
            )
            if current_audio_label is not None:
                audio_filters.append(f"{current_audio_label}[mixa]amix=inputs=2:duration=first:dropout_transition=2[aout]")
            else:
                audio_filters.append("[mixa]anull[aout]")
            current_audio_label = "[aout]"

        filter_complex = ";".join(video_filters + audio_filters)
        command.extend(["-filter_complex", filter_complex, "-map", current_video_label])

        if current_audio_label is not None:
            command.extend(["-map", current_audio_label, "-c:a", "aac", "-b:a", "192k"])
        else:
            command.append("-an")

        command.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )
        run_command(command)
        return output_path

    def _write_karaoke_ass(self, candidate: CandidateMoment, output_path: str | Path) -> Path:
        width = int(self.montage_config.get("width", 1080))
        height = int(self.montage_config.get("height", 1920))
        font = self.montage_config.get("subtitle_font", "Arial")
        font_size = int(self.montage_config.get("subtitle_font_size", 68))
        margin_bottom = int(self.montage_config.get("subtitle_margin_bottom", 210))
        primary_color = self.montage_config.get("subtitle_primary_color", "&H00FFFFFF")
        secondary_color = self.montage_config.get("subtitle_secondary_color", "&H0000A5FF")

        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "",
            "[V4+ Styles]",
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
            f"Style: TikTok,{font},{font_size},{primary_color},{secondary_color},&H00000000,&H7F000000,1,0,0,0,100,100,0,0,1,6,0,2,80,80,{margin_bottom},1",
            "",
            "[Events]",
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        ]

        if candidate.transcript_words:
            groups = self._group_words(candidate)
            for group in groups:
                start = seconds_to_ass(max(0.0, group[0].start - candidate.start))
                end = seconds_to_ass(max(0.0, group[-1].end - candidate.start + 0.22))
                karaoke_chunks = []
                for idx, word in enumerate(group):
                    next_start = group[idx + 1].start if idx + 1 < len(group) else word.end
                    duration_cs = max(6, int(round((max(word.end, next_start) - word.start) * 100)))
                    karaoke_chunks.append(f"{{\\k{duration_cs}}}{self._escape_ass(word.word)}")
                lines.append(
                    f"Dialogue: 0,{start},{end},TikTok,,0,0,0,,{{\\fad(80,120)}}{' '.join(karaoke_chunks)}"
                )
        elif candidate.transcript:
            end = seconds_to_ass(candidate.duration)
            text = self._escape_ass(candidate.transcript)
            lines.append(f"Dialogue: 0,0:00:00.00,{end},TikTok,,0,0,0,,{{\\fad(80,120)}}{text}")

        output_path = Path(output_path)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    def _write_title_card(self, candidate: CandidateMoment, output_path: str | Path) -> Path:
        raw_title = str(candidate.metadata.get("source_title") or "").strip()
        title = raw_title or "Source Video"
        wrapped = textwrap.wrap(title, width=30)[:2]
        rendered = "\n".join(wrapped) if wrapped else title
        output_path = Path(output_path)
        output_path.write_text(rendered, encoding="utf-8")
        return output_path

    def _group_words(self, candidate: CandidateMoment) -> list[list]:
        groups = []
        current = []
        max_words = 6
        max_span = 2.8
        for word in candidate.transcript_words:
            if not current:
                current.append(word)
                continue
            too_many = len(current) >= max_words
            too_long = word.end - current[0].start > max_span
            punctuation_break = current[-1].word.strip().endswith((".", "!", "?"))
            if too_many or too_long or punctuation_break:
                groups.append(current)
                current = [word]
            else:
                current.append(word)
        if current:
            groups.append(current)
        return groups

    @staticmethod
    def _escape_ass(text: str) -> str:
        return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")

    @staticmethod
    def _filter_path(path: Path) -> str:
        escaped = path.resolve().as_posix().replace(":", "\\:")
        return escaped.replace("'", r"\'")

    def _pick_music(self, clip_seed: str) -> Path | None:
        if not self.assets_dir.exists():
            return None
        candidates = sorted(
            [
                path
                for path in self.assets_dir.iterdir()
                if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac"}
            ]
        )
        if not candidates:
            return None
        return candidates[hash(clip_seed) % len(candidates)]

    def _resolve_watermark(self) -> Path | None:
        if not bool(self.watermark_config.get("enabled", False)):
            return None
        watermark_path = self.watermark_config.get("path")
        if not watermark_path:
            return None
        path = Path(watermark_path)
        return path if path.exists() else None
