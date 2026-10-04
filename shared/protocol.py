import json
import socket
import struct

MAX_HEADER = 1024 * 1024


def send_json(sock: socket.socket, message: dict) -> None:
    data = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
    sock.sendall(data)


def recv_line(sock: socket.socket, max_bytes: int = MAX_HEADER) -> dict:
    buffer = bytearray()
    while len(buffer) < max_bytes:
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("Connection closed while waiting for JSON message.")
        if chunk == b"\n":
            return json.loads(buffer.decode("utf-8"))
        buffer.extend(chunk)
    raise ValueError("JSON message is too large.")


def send_u64(sock: socket.socket, value: int) -> None:
    sock.sendall(struct.pack("!Q", value))


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        chunk = sock.recv(min(1024 * 1024, remaining))
        if not chunk:
            raise ConnectionError("Connection closed during binary transfer.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
