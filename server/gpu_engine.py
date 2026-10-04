import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def nvenc_available() -> bool:
    if not ffmpeg_available():
        return False
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10
        )
        return "h264_nvenc" in result.stdout
    except Exception:
        return False


def build_command(input_file, output_file, resolution, bitrate, preset, use_gpu):
    encoder = "h264_nvenc" if use_gpu else "libx264"

    # FFmpeg scale keeps aspect ratio and pads if requested resolution is explicit.
    vf = []
    if resolution and resolution != "Original":
        width, height = resolution.split("x")
        vf = ["-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease"]

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_file),
        *vf,
        "-c:v", encoder,
        "-b:v", bitrate,
        "-preset", preset,
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_file)
    ]
    return cmd, encoder


def get_duration(input_file):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(input_file)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return float(result.stdout.strip())
    except Exception:
        return None


def render(input_file, output_file, resolution, bitrate, preset, requested_gpu, log_callback, progress_callback):
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg was not found in PATH.")

    gpu = requested_gpu and nvenc_available()
    duration = get_duration(input_file)

    command, encoder = build_command(
        input_file, output_file, resolution, bitrate, preset, gpu
    )

    log_callback(f"FFmpeg encoder selected: {encoder}")
    log_callback("Command: " + " ".join(command))

    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    time_pattern = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
    last_percent = -1

    for line in process.stderr:
        line = line.rstrip()
        if line:
            log_callback(line)

        match = time_pattern.search(line)
        if match and duration and duration > 0:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            current = hours * 3600 + minutes * 60 + seconds
            percent = max(0, min(100, int(current / duration * 100)))
            if percent != last_percent:
                progress_callback(percent)
                last_percent = percent

    return_code = process.wait()

    if return_code != 0:
        raise RuntimeError(f"FFmpeg failed with exit code {return_code}.")

    progress_callback(100)
    return {
        "encoder": encoder,
        "gpu_used": gpu,
        "duration": duration
    }
