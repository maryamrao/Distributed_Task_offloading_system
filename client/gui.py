import threading
import time
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox

from network import RemoteClient


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Distributed GPU Render Client")
        self.geometry("1050x720")
        self.minsize(900, 650)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.client = None
        self.input_file = None
        self.connected = False
        self.render_started_at = None
        self.last_output = None
        self.last_encoder = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(7, weight=1)

        title = ctk.CTkLabel(
            self, text="Distributed GPU Render Client",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title.grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 10), sticky="w")

        ctk.CTkLabel(self, text="Server IP").grid(row=1, column=0, padx=20, pady=8, sticky="w")
        self.ip_entry = ctk.CTkEntry(self, placeholder_text="192.168.1.10")
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.grid(row=1, column=1, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(self, text="Port").grid(row=1, column=2, padx=20, pady=8, sticky="w")
        self.port_entry = ctk.CTkEntry(self, width=100)
        self.port_entry.insert(0, "5000")
        self.port_entry.grid(row=1, column=2, padx=(0, 20), pady=8, sticky="e")

        self.connect_btn = ctk.CTkButton(
            self, text="Connect / Ping", command=self.connect_clicked
        )
        self.connect_btn.grid(row=2, column=0, columnspan=3, padx=20, pady=8, sticky="ew")

        self.status_label = ctk.CTkLabel(self, text="Status: Disconnected")
        self.status_label.grid(row=3, column=0, columnspan=3, padx=20, pady=4, sticky="w")

        file_frame = ctk.CTkFrame(self)
        file_frame.grid(row=4, column=0, columnspan=3, padx=20, pady=10, sticky="ew")
        file_frame.grid_columnconfigure(0, weight=1)

        self.file_label = ctk.CTkLabel(file_frame, text="No input video selected", anchor="w")
        self.file_label.grid(row=0, column=0, padx=12, pady=10, sticky="ew")
        ctk.CTkButton(file_frame, text="Browse Video", command=self.choose_file, width=140).grid(
            row=0, column=1, padx=12, pady=10
        )

        settings = ctk.CTkFrame(self)
        settings.grid(row=5, column=0, columnspan=3, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(settings, text="Resolution").grid(row=0, column=0, padx=10, pady=10)
        self.resolution = ctk.CTkComboBox(
            settings, values=["Original", "1920x1080", "1280x720", "854x480"], width=150
        )
        self.resolution.set("Original")
        self.resolution.grid(row=0, column=1, padx=10)

        ctk.CTkLabel(settings, text="Bitrate").grid(row=0, column=2, padx=10)
        self.bitrate = ctk.CTkComboBox(
            settings, values=["2M", "4M", "6M", "8M", "12M"], width=120
        )
        self.bitrate.set("4M")
        self.bitrate.grid(row=0, column=3, padx=10)

        ctk.CTkLabel(settings, text="Preset").grid(row=0, column=4, padx=10)
        self.preset = ctk.CTkComboBox(
            settings,
            values=["fast", "medium", "slow"],
            width=120
        )
        self.preset.set("medium")
        self.preset.grid(row=0, column=5, padx=10)

        self.gpu_switch = ctk.CTkSwitch(settings, text="Use NVIDIA GPU")
        self.gpu_switch.select()
        self.gpu_switch.grid(row=0, column=6, padx=15)

        self.progress = ctk.CTkProgressBar(self)
        self.progress.set(0)
        self.progress.grid(row=6, column=0, columnspan=3, padx=20, pady=8, sticky="ew")

        self.progress_label = ctk.CTkLabel(self, text="Progress: 0%")
        self.progress_label.grid(row=6, column=2, padx=25, sticky="e")

        self.log_box = ctk.CTkTextbox(self, wrap="word")
        self.log_box.grid(row=7, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")

        self.start_btn = ctk.CTkButton(
            self, text="Start Remote Render", command=self.start_render, height=42
        )
        self.start_btn.grid(row=8, column=0, columnspan=3, padx=20, pady=(5, 20), sticky="ew")

    def log(self, message):
        self.after(0, self._log_ui, message)

    def _log_ui(self, message):
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_box.see("end")

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Select video",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.mov *.avi *.webm"),
                ("All files", "*.*")
            ]
        )
        if path:
            self.input_file = path
            self.file_label.configure(text=path)
            self.log(f"Selected input: {path}")

    def connect_clicked(self):
        def worker():
            try:
                if self.client:
                    self.client.close()

                self.client = RemoteClient(
                    self.ip_entry.get().strip(),
                    int(self.port_entry.get().strip()),
                    self.handle_event
                )
                self.client.connect()
                self.client.ping()
            except Exception as exc:
                self.handle_event({"type": "error", "message": str(exc)})

        threading.Thread(target=worker, daemon=True).start()

    def start_render(self):
        if not self.client:
            messagebox.showwarning("Not connected", "Connect to the server first.")
            return
        if not self.input_file:
            messagebox.showwarning("No file", "Select a video first.")
            return

        self.start_btn.configure(state="disabled")
        self.progress.set(0)
        self.progress_label.configure(text="Progress: 0%")
        self.render_started_at = time.perf_counter()

        def worker():
            try:
                self.client.render(
                    self.input_file,
                    self.resolution.get(),
                    self.bitrate.get(),
                    self.preset.get(),
                    bool(self.gpu_switch.get())
                )
            except Exception as exc:
                self.handle_event({"type": "error", "message": str(exc)})
            finally:
                self.after(0, lambda: self.start_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def handle_event(self, event):
        event_type = event.get("type")

        if event_type == "connected":
            self.connected = True
            self.after(0, lambda: self.status_label.configure(
                text=f"Status: Connected | Handshake latency: {event['latency_ms']} ms | "
                     f"Server NVENC: {event['nvenc']}"
            ))
            self.log(f"Connected to {event['server']}")
            self.log(f"Handshake latency: {event['latency_ms']} ms")
            self.log(f"Server NVENC available: {event['nvenc']}")

        elif event_type == "ping_result":
            self.log(f"Ping latency: {event['latency_ms']} ms")

        elif event_type == "server_event":
            self.handle_server_event(event.get("data", {}))

        elif event_type == "local_download_progress":
            self.set_progress(event["percent"], "Download")

        elif event_type == "download_complete":
            self.last_output = event["path"]
            self.set_progress(100, "Complete")
            self.log(f"Rendered output saved to: {event['path']}")
            self.log("Remote render completed successfully.")

        elif event_type == "error":
            self.log("ERROR: " + event.get("message", "Unknown error"))
            self.after(0, lambda: messagebox.showerror("Error", event.get("message", "Unknown error")))

    def handle_server_event(self, event):
        et = event.get("type")

        if et == "job_accepted":
            self.log(f"Job accepted: {event['job_id']}")
            self.log("Uploading input file...")

        elif et == "upload_progress":
            self.set_progress(event["percent"], "Upload")

        elif et == "upload_complete":
            self.log("Upload complete. SHA-256 verified.")

        elif et == "render_started":
            self.log(
                f"Remote rendering started. NVENC available: "
                f"{event.get('nvenc_available')}"
            )

        elif et == "render_progress":
            self.set_progress(event["percent"], "Remote render")

        elif et == "log":
            self.log("SERVER: " + event.get("message", ""))

        elif et == "render_complete":
            self.last_encoder = event.get("encoder")
            self.log(
                f"Render finished using {event.get('encoder')} | "
                f"GPU used: {event.get('gpu_used')} | "
                f"Server render time: {event.get('render_seconds')} sec"
            )
            self.log(f"Output SHA-256: {event.get('output_sha256')}")
            self.log(f"Output size: {event.get('output_size')} bytes")

        elif et == "download_start":
            self.log(f"Downloading rendered output ({event['size']} bytes)...")

        elif et == "download_progress":
            # Server currently sends this after the raw binary stream.
            self.log(f"Server download progress: {event['percent']}%")

        elif et == "job_complete":
            self.log(f"Job {event.get('job_id')} complete.")

        elif et in ("error", "fatal_error"):
            raise RuntimeError(event.get("message", "Server error"))

    def set_progress(self, percent, phase):
        percent = max(0, min(100, int(percent)))
        self.after(0, lambda: self.progress.set(percent / 100))
        self.after(0, lambda: self.progress_label.configure(
            text=f"{phase}: {percent}%"
        ))

    def on_close(self):
        try:
            if self.client:
                self.client.close()
        finally:
            self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
