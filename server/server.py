import json
import os
import socket
import threading
import time
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.protocol import send_json, recv_line, recv_exact
from shared.checksum import sha256_file
from gpu_engine import render, nvenc_available
from config import HOST, PORT, JOBS_DIR, SOCKET_TIMEOUT, CHUNK_SIZE


BASE = Path(__file__).resolve().parent
JOBS = BASE / JOBS_DIR
JOBS.mkdir(parents=True, exist_ok=True)


def log(message):
    print(time.strftime("[%H:%M:%S]"), message, flush=True)


def send_event(conn, event, **kwargs):
    send_json(conn, {"type": event, **kwargs})


def handle_client(conn, address):
    conn.settimeout(SOCKET_TIMEOUT)
    log(f"Client connected: {address}")

    try:
        hello = recv_line(conn)
        if hello.get("type") != "hello":
            raise ValueError("Invalid handshake.")

        send_event(
            conn,
            "hello_ack",
            server="Distributed GPU Worker",
            version="1.0",
            nvenc=nvenc_available(),
            timestamp=time.time()
        )

        while True:
            request = recv_line(conn)
            rtype = request.get("type")

            if rtype == "ping":
                send_event(conn, "pong", timestamp=request.get("timestamp"), server_time=time.time())

            elif rtype == "job_start":
                job_id = uuid.uuid4().hex[:12]
                filename = Path(request.get("filename", "input.bin")).name
                size = int(request["size"])
                expected_sha = request["sha256"]

                job_dir = JOBS / job_id
                job_dir.mkdir(parents=True, exist_ok=True)
                input_path = job_dir / filename

                send_event(conn, "job_accepted", job_id=job_id)

                received = 0
                with open(input_path, "wb") as f:
                    while received < size:
                        chunk = conn.recv(min(CHUNK_SIZE, size - received))
                        if not chunk:
                            raise ConnectionError("Client disconnected during upload.")
                        f.write(chunk)
                        received += len(chunk)
                        percent = int(received / size * 100) if size else 100
                        send_event(conn, "upload_progress", percent=percent)

                actual_sha = sha256_file(input_path)
                if actual_sha != expected_sha:
                    send_event(conn, "error", message="SHA-256 checksum mismatch after upload.")
                    continue

                send_event(conn, "upload_complete", sha256=actual_sha)

                resolution = request.get("resolution", "Original")
                bitrate = request.get("bitrate", "4M")
                preset = request.get("preset", "medium")
                requested_gpu = bool(request.get("use_gpu", True))

                stem = Path(filename).stem
                output_path = job_dir / f"{stem}_remote_render.mp4"

                send_event(
                    conn,
                    "render_started",
                    job_id=job_id,
                    requested_gpu=requested_gpu,
                    nvenc_available=nvenc_available()
                )

                def server_log(msg):
                    send_event(conn, "log", message=msg)

                def progress(p):
                    send_event(conn, "render_progress", percent=p)

                started = time.perf_counter()
                result = render(
                    input_path, output_path, resolution, bitrate, preset,
                    requested_gpu, server_log, progress
                )
                render_time = time.perf_counter() - started

                output_size = output_path.stat().st_size
                output_sha = sha256_file(output_path)

                send_event(
                    conn,
                    "render_complete",
                    encoder=result["encoder"],
                    gpu_used=result["gpu_used"],
                    render_seconds=round(render_time, 3),
                    output_size=output_size,
                    output_sha256=output_sha,
                    filename=output_path.name
                )

                # Binary output follows a JSON header.
                send_event(conn, "download_start", size=output_size)

                with open(output_path, "rb") as f:
                    sent = 0
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        conn.sendall(chunk)
                        sent += len(chunk)
                        percent = int(sent / output_size * 100) if output_size else 100
                        send_event(conn, "download_progress", percent=percent)

                send_event(conn, "job_complete", job_id=job_id)

            elif rtype == "quit":
                break

            else:
                send_event(conn, "error", message=f"Unknown request type: {rtype}")

    except Exception as exc:
        log(f"Client {address} error: {exc}")
        try:
            send_event(conn, "fatal_error", message=str(exc))
        except Exception:
            pass
    finally:
        conn.close()
        log(f"Client disconnected: {address}")


def main():
    log(f"Starting Distributed GPU Worker on {HOST}:{PORT}")
    log(f"NVENC available: {nvenc_available()}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)
        log("Server is ready. Waiting for clients...")

        while True:
            conn, address = server.accept()
            thread = threading.Thread(
                target=handle_client,
                args=(conn, address),
                daemon=True
            )
            thread.start()


if __name__ == "__main__":
    main()
