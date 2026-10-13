import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from app.services.llm import get_client

SEGMENT_SECONDS = 600


def run_command(command: list) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-300:] or "Command failed")
    return result.stdout


def media_duration_seconds(file_path: str) -> float:
    try:
        output = run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ]
        )
        return float(output.strip())
    except (RuntimeError, ValueError):
        raise ValueError("Could not read this video file. Try converting it to MP4.")


def split_audio(file_path: str, output_dir: str) -> list:
    pattern = os.path.join(output_dir, "part_%03d.mp3")
    try:
        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                file_path,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "32k",
                "-f",
                "segment",
                "-segment_time",
                str(SEGMENT_SECONDS),
                "-reset_timestamps",
                "1",
                pattern,
            ]
        )
    except RuntimeError as error:
        print("ffmpeg error:", error)
        raise ValueError("Could not read audio from this file. Check that the video has sound.")

    parts = sorted(Path(output_dir).glob("part_*.mp3"))
    if not parts:
        raise ValueError("No audio track found in this file")
    return [str(part) for part in parts]


def transcribe_file(audio_path: str):
    model = os.getenv("TRANSCRIBE_MODEL", "whisper-large-v3-turbo")
    for attempt in range(2):
        try:
            with open(audio_path, "rb") as audio:
                return get_client().audio.transcriptions.create(
                    model=model,
                    file=audio,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
        except Exception:
            if attempt == 1:
                raise
            time.sleep(3)


def read_field(item, name: str, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def transcribe_video(file_path: str):
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg is not installed on the server")

    max_minutes = int(os.getenv("MAX_VIDEO_MINUTES", "30"))
    duration = media_duration_seconds(file_path)
    if duration > max_minutes * 60:
        raise ValueError(f"Video is too long (max {max_minutes} minutes)")

    segments = []
    with tempfile.TemporaryDirectory() as workdir:
        parts = split_audio(file_path, workdir)
        for index, part in enumerate(parts):
            offset = index * SEGMENT_SECONDS
            response = transcribe_file(part)

            found = False
            for item in read_field(response, "segments", None) or []:
                text = str(read_field(item, "text", "") or "").strip()
                if not text:
                    continue
                start = float(read_field(item, "start", 0) or 0)
                segments.append({"start": int(offset + start), "text": text})
                found = True

            if not found:
                text = str(read_field(response, "text", "") or "").strip()
                if text:
                    segments.append({"start": int(offset), "text": text})

    if not segments:
        raise ValueError("No speech could be transcribed from this file")
    return segments