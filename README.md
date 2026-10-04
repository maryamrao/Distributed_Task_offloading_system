# Custom Distributed Task Offloading & Remote GPU Rendering System

CSC-334: Parallel and Distributed Computing

A Python client-server system for remotely offloading video transcoding from a client laptop to a worker PC over a LAN/Wi-Fi connection.

## Features

- Client desktop GUI using CustomTkinter
- Server daemon using Python sockets
- Handshake and latency check
- JSON-line control protocol + binary file transfer
- SHA-256 integrity validation
- Remote FFmpeg rendering
- NVIDIA NVENC (`h264_nvenc`) when available
- Automatic CPU (`libx264`) fallback
- Real-time progress streaming
- Upload/download progress
- Server logs displayed in the client
- Timeout and disconnect handling
- Benchmark helper for local vs remote timing

## Architecture

Client -> handshake -> upload input -> server queue -> FFmpeg/NVENC -> download output -> checksum validation

## Requirements

Client:
- Python 3.10+
- Windows/Linux/macOS
- CustomTkinter

Server:
- Python 3.10+
- FFmpeg in PATH
- NVIDIA GPU + supported FFmpeg NVENC for GPU mode (optional; CPU fallback works)

## 1. Install Python

Check:

```bash
python --version
```

## 2. Install Python packages

Client:

```bash
cd client
python -m pip install -r requirements.txt
```

Server:

```bash
cd server
python -m pip install -r requirements.txt
```

## 3. Install FFmpeg on the server

Verify:

```bash
ffmpeg -version
```

For NVIDIA support, also check:

```bash
ffmpeg -hide_banner -encoders | findstr nvenc
```

On Linux:

```bash
ffmpeg -hide_banner -encoders | grep nvenc
```

You should see `h264_nvenc` if NVENC is available.

## 4. Start the server

On the worker PC:

```bash
cd server
python server.py
```

The server listens on port 5000.

Find the worker PC's IP:

Windows:

```bash
ipconfig
```

Linux:

```bash
ip addr
```

Example:

```text
Server IP = 192.168.1.10
```

## 5. Start the client

On the client PC:

```bash
cd client
python app.py
```

Enter the server IP, for example:

```text
192.168.1.10
```

Port:

```text
5000
```

Click `Connect / Ping`.

Select a video, choose resolution/bitrate/preset, then click `Start Remote Render`.

## 6. Network

Both computers should be on the same LAN/Wi-Fi network.

For a direct Ethernet connection, configure addresses such as:

```text
Server: 192.168.1.10
Client: 192.168.1.11
Mask:   255.255.255.0
```

Do not use these addresses if they conflict with your existing network. You can simply use the PCs' existing LAN IPs.

On Windows Firewall, allow Python/server traffic on the private network or create an inbound TCP rule for port 5000.

## 7. Output

Rendered files are stored on the client in:

```text
client/received/
```

Temporary server jobs are stored in:

```text
server/jobs/
```

## 8. Benchmarking

The benchmark helper can measure local FFmpeg rendering:

```bash
cd benchmarks
python benchmark.py --input path/to/video.mp4
```

It creates a CSV-style result in `benchmarks/results.csv`.

For a formal assignment comparison, run the same input and settings locally and remotely and record:

- File size
- Resolution
- Local render time
- Remote total time
- Upload time
- Server render time
- Download time
- Speedup

Formula:

```text
Speedup = Local Time / Remote Total Time
```

## 9. GitHub submission

Create a public GitHub repository and push the complete folder.

Do not upload large videos or generated outputs. Use `.gitignore`.

## Demo checklist

Capture screenshots/GIFs showing:

1. Server running
2. Client connected
3. Ping/latency result
4. Selected video and render settings
5. Upload progress
6. Remote GPU/CPU render progress
7. Completed download
8. Output file
9. Benchmark results

## Notes

The system is intentionally designed to work without an NVIDIA GPU too. If NVENC is unavailable, the server uses `libx264` so you can demonstrate the distributed architecture on ordinary computers.
<img width="1280" height="720" alt="WhatsApp Image 2026-10-04 at 10 00 27 AM" src="https://github.com/user-attachments/assets/aa63a2ae-5bb8-4388-93fa-7d69dc6af50d" />
<img width="1280" height="720" alt="WhatsApp Image 2026-10-04 at 10 00 27 AM" src="https://github.com/user-attachments/assets/be40baa1-dbfa-4d24-a358-6ce4fd56aeeb" />
<img width="1280" height="720" alt="WhatsApp Image 2026-10-04 at 10 08 41 AM" src="https://github.com/user-attachments/assets/b9b44a4a-2532-4f28-a325-0f8a7acb616d" />
<img width="1280" height="720" alt="WhatsApp Image 2026-10-04 at 10 10 45 AM" src="https://github.com/user-attachments/assets/ce0415d0-cc1b-4c86-914c-580df9222c26" />



