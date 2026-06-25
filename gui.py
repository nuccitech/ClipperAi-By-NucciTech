import os
import sys
import queue
import threading
import glob

import customtkinter as ctk

# Ensure relative paths (profiles/, cache/) resolve correctly wherever gui.py is launched from
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from main import run_automated_factory
from editor import PLATFORMS


# --------------------------------------------------------------------------- #
# Stdout redirect → queue (captures all pipeline print() calls)
# --------------------------------------------------------------------------- #

class _QueueStream:
    def __init__(self, q):
        self._q = q

    def write(self, text):
        if text:
            self._q.put(text)

    def flush(self):
        pass


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #

class CliperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Cliper")
        self.geometry("620x620")
        self.resizable(False, False)

        self._log_queue = queue.Queue()
        self._running = False

        self._build_ui()
        self._poll_log()

    # ---------------------------------------------------------------------- #
    # UI construction
    # ---------------------------------------------------------------------- #

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(
            self, text="Cliper", font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, padx=24, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            self, text="Automated short-form video pipeline",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).grid(row=1, column=0, padx=24, pady=(0, 16), sticky="w")

        # URL input
        ctk.CTkLabel(self, text="YouTube URL or local file path").grid(
            row=2, column=0, padx=24, pady=(0, 4), sticky="w"
        )
        self._url_entry = ctk.CTkEntry(
            self, placeholder_text="https://www.youtube.com/watch?v=...",
            height=38, font=ctk.CTkFont(size=13)
        )
        self._url_entry.grid(row=3, column=0, padx=24, pady=(0, 16), sticky="ew")

        # Profile + Platform row
        row_frame = ctk.CTkFrame(self, fg_color="transparent")
        row_frame.grid(row=4, column=0, padx=24, pady=(0, 16), sticky="ew")
        row_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(row_frame, text="Profile").grid(
            row=0, column=0, padx=(0, 8), pady=(0, 4), sticky="w"
        )
        ctk.CTkLabel(row_frame, text="Platform").grid(
            row=0, column=1, padx=(8, 0), pady=(0, 4), sticky="w"
        )

        profiles = self._get_profiles()
        self._profile_var = ctk.StringVar(value=profiles[0] if profiles else "test")
        self._profile_menu = ctk.CTkOptionMenu(
            row_frame, values=profiles, variable=self._profile_var,
            height=36, font=ctk.CTkFont(size=13)
        )
        self._profile_menu.grid(row=1, column=0, padx=(0, 8), sticky="ew")

        platforms = list(PLATFORMS.keys())
        self._platform_var = ctk.StringVar(value="tiktok")
        ctk.CTkOptionMenu(
            row_frame, values=platforms, variable=self._platform_var,
            height=36, font=ctk.CTkFont(size=13)
        ).grid(row=1, column=1, padx=(8, 0), sticky="ew")

        # Run button
        self._run_btn = ctk.CTkButton(
            self, text="▶   Run Pipeline", height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_run
        )
        self._run_btn.grid(row=5, column=0, padx=24, pady=(0, 16), sticky="ew")

        # Log area
        ctk.CTkLabel(self, text="Log").grid(
            row=6, column=0, padx=24, pady=(0, 4), sticky="w"
        )
        self._log_box = ctk.CTkTextbox(
            self, height=260, font=ctk.CTkFont(family="Courier New", size=12),
            wrap="word", state="disabled"
        )
        self._log_box.grid(row=7, column=0, padx=24, pady=(0, 12), sticky="ew")

        # Status label
        self._status_var = ctk.StringVar(value="Status: Idle")
        ctk.CTkLabel(
            self, textvariable=self._status_var,
            font=ctk.CTkFont(size=12), text_color="gray"
        ).grid(row=8, column=0, padx=24, pady=(0, 20), sticky="w")

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #

    def _get_profiles(self):
        paths = glob.glob("profiles/*.json")
        return [os.path.splitext(os.path.basename(p))[0] for p in sorted(paths)] or ["default"]

    def _append_log(self, text):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", text)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _poll_log(self):
        try:
            while True:
                text = self._log_queue.get_nowait()
                self._append_log(text)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    # ---------------------------------------------------------------------- #
    # Pipeline execution
    # ---------------------------------------------------------------------- #

    def _on_run(self):
        url = self._url_entry.get().strip()
        if not url:
            self._append_log("ERROR: Please enter a URL or file path.\n")
            return
        if self._running:
            return

        self._running = True
        self._run_btn.configure(state="disabled", text="Running…")
        self._status_var.set("Status: Running…")
        self._append_log(f"\n{'='*50}\n")

        profile = self._profile_var.get()
        platform = self._platform_var.get()

        t = threading.Thread(target=self._worker, args=(url, profile, platform), daemon=True)
        t.start()

    def _worker(self, url, profile, platform):
        old_stdout = sys.stdout
        sys.stdout = _QueueStream(self._log_queue)
        try:
            run_automated_factory(url, profile_name=profile, platform=platform)
            self.after(0, self._on_done, True)
        except Exception as e:
            sys.stdout.write(f"\nFATAL ERROR: {e}\n")
            self.after(0, self._on_done, False)
        finally:
            sys.stdout = old_stdout

    def _on_done(self, success):
        self._running = False
        self._run_btn.configure(state="normal", text="▶   Run Pipeline")
        if success:
            self._status_var.set("Status: Done")
            self._append_log("\n")
        else:
            self._status_var.set("Status: Error — check log above")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    app = CliperApp()
    app.mainloop()
