import json
import customtkinter as ctk
from tkinter import filedialog

from src.utils.config import (
    ensure_data_dir, SETTINGS_FILE, DEFAULT_DOWNLOAD_DIR,
    DEFAULT_WORKERS, MIN_WORKERS, MAX_WORKERS,
)


def load_settings() -> dict:
    ensure_data_dir()
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_settings(data: dict):
    ensure_data_dir()
    SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_download_dir() -> str:
    settings = load_settings()
    return settings.get("download_dir", DEFAULT_DOWNLOAD_DIR)


def get_workers() -> int:
    settings = load_settings()
    return settings.get("workers", DEFAULT_WORKERS)


class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(1, weight=1)

        settings = load_settings()

        row = 0
        ctk.CTkLabel(self, text="Pasta de Download:").grid(
            row=row, column=0, padx=10, pady=10, sticky="w"
        )
        self.dir_var = ctk.StringVar(value=settings.get("download_dir", DEFAULT_DOWNLOAD_DIR))
        dir_entry = ctk.CTkEntry(self, textvariable=self.dir_var)
        dir_entry.grid(row=row, column=1, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(self, text="...", width=40, command=self._browse_dir).grid(
            row=row, column=2, padx=(0, 10), pady=10
        )

        row += 1
        ctk.CTkLabel(self, text="Workers Padrao:").grid(
            row=row, column=0, padx=10, pady=10, sticky="w"
        )
        self.workers_var = ctk.StringVar(value=str(settings.get("workers", DEFAULT_WORKERS)))
        workers_entry = ctk.CTkEntry(self, textvariable=self.workers_var, width=80)
        workers_entry.grid(row=row, column=1, padx=5, pady=10, sticky="w")

        row += 1
        ctk.CTkButton(self, text="Salvar", command=self._save).grid(
            row=row, column=0, columnspan=3, padx=10, pady=20
        )

    def _browse_dir(self):
        path = filedialog.askdirectory(initialdir=self.dir_var.get())
        if path:
            self.dir_var.set(path)

    def _save(self):
        try:
            workers = int(self.workers_var.get())
            workers = max(MIN_WORKERS, min(MAX_WORKERS, workers))
        except ValueError:
            workers = DEFAULT_WORKERS

        data = {
            "download_dir": self.dir_var.get(),
            "workers": workers,
        }
        save_settings(data)

        self.master.destroy()
