import socket
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.protocol import send_json, recv_line, recv_exact
from shared.checksum import sha256_file

CHUNK_SIZE = 1024 * 1024


class RemoteClient:
    def __init__(self, host, port, event_callback, timeout=30):
        self.host = host
        self.port = int(port)
        self.sock = None
        self.callback = event_callback
        self.timeout = timeout

    def emit(self, event, **kwargs):
        self.callback({"type": event, **kwargs})

    def connect(self):
        start = time.perf_counter()
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)

        send_json(self.sock, {
            "type": "hello",
            "client": "DistributedTaskOffloadingClient",
            "version": "1.0"
        })

        reply = recv_line(self.sock)
        if reply.get("type") != "hello_ack":
            raise ConnectionError("Server handshake failed.")

        latency = (time.perf_counter() - start) * 1000
        self.emit(
            "connected",
            latency_ms=round(latency, 2),
            nvenc=reply.get("nvenc", False),
            server=reply.get("server", "Unknown")
        )

    def ping(self):
        if not self.sock:
            raise ConnectionError("Not connected.")

        start = time.perf_counter()
        send_json(self.sock, {"type": "ping", "timestamp": time.time()})
        reply = recv_line(self.sock)

        if reply.get("type") != "pong":
            raise ConnectionError("Ping failed.")

        latency = (time.perf_counter() - start) * 1000
        self.emit("ping_result", latency_ms=round(latency, 2))
        return latency

    def render(self, input_path, resolution, bitrate, preset, use_gpu=True):
        if not self.sock:
            raise ConnectionError("Not connected.")

        input_path = Path(input_path)
        size = input_path.stat().st_size
        digest = sha256_file(input_path)

        send_json(self.sock, {
            "type": "job_start",
            "filename": input_path.name,
            "size": size,
            "sha256": digest,
            "resolution": resolution,
            "bitrate": bitrate,
            "preset": preset,
            "use_gpu": use_gpu
        })

        reply = recv_line(self.sock)
        self.emit("server_event", data=reply)

        if reply.get("type") != "job_accepted":
            raise RuntimeError("Server did not accept the job.")

        sent = 0
        with open(input_path, "rb") as f:
            while sent < size:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                self.sock.sendall(chunk)
                sent += len(chunk)

                # Server sends upload progress messages while receiving.
                # Read messages periodically so the client does not leave the
                # server's socket buffer full.
                if sent == size or sent % (CHUNK_SIZE * 4) == 0:
                    self._drain_events(nonblocking=False)

        self._wait_for_render_and_download()

    def _drain_events(self, nonblocking=False):
        if nonblocking:
            self.sock.settimeout(0.001)
        else:
            self.sock.settimeout(self.timeout)

        try:
            event = recv_line(self.sock)
            self.emit("server_event", data=event)
            return event
        except socket.timeout:
            return None
        finally:
            self.sock.settimeout(self.timeout)

    def _wait_for_render_and_download(self):
        while True:
            event = recv_line(self.sock)
            self.emit("server_event", data=event)
            event_type = event.get("type")

            if event_type == "download_start":
                size = int(event["size"])
                self._receive_output(size)

            elif event_type == "job_complete":
                return

            elif event_type in ("error", "fatal_error"):
                raise RuntimeError(event.get("message", "Remote server error."))

    def _receive_output(self, size):
        received = 0
        temp_dir = Path(__file__).resolve().parent / "received"
        temp_dir.mkdir(exist_ok=True)

        # We need the filename from the previous render_complete event.
        # Store it from the event callback by asking the GUI; simpler default:
        output_name = f"remote_render_{int(time.time())}.mp4"

        # The protocol announces download_start after render_complete, but
        # the GUI receives that event. The client uses a safe default name.
        output_path = temp_dir / output_name

        with open(output_path, "wb") as f:
            while received < size:
                chunk = self.sock.recv(min(CHUNK_SIZE, size - received))
                if not chunk:
                    raise ConnectionError("Server disconnected during download.")
                f.write(chunk)
                received += len(chunk)

                percent = int(received / size * 100) if size else 100
                self.emit("local_download_progress", percent=percent)

                # Progress JSON from server is sent after each chunk, which
                # cannot be safely interleaved with raw bytes. The server sends
                # download_progress only after all bytes, so no JSON is read here.

        # The next message is the final JSON job_complete.
        final_event = recv_line(self.sock)
        self.emit("server_event", data=final_event)

        self.emit("download_complete", path=str(output_path), size=size)

    def close(self):
        if self.sock:
            try:
                send_json(self.sock, {"type": "quit"})
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
