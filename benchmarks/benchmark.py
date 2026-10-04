import argparse
import csv
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Local FFmpeg benchmark helper")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", default="local_benchmark_output.mp4")
    parser.add_argument("--bitrate", default="4M")
    parser.add_argument("--preset", default="medium")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    command = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-b:v", args.bitrate,
        "-preset", args.preset,
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_path)
    ]

    print("Running local CPU benchmark...")
    start = time.perf_counter()
    result = subprocess.run(command)
    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        raise SystemExit("FFmpeg benchmark failed.")

    results_file = Path(__file__).resolve().parent / "results.csv"
    exists = results_file.exists()

    with open(results_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["input", "input_size_bytes", "local_time_seconds"])
        writer.writerow([str(input_path), input_path.stat().st_size, round(elapsed, 3)])

    print(f"Local render time: {elapsed:.3f} seconds")
    print(f"Saved benchmark record to: {results_file}")


if __name__ == "__main__":
    main()
