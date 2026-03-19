import asyncio
import queue
import threading
import time
import customtkinter as ctk
from tkinter import filedialog

from src.core.models import (
    DownloadOptions, DownloadMode, DownloadStats, DownloadResult, MediaType,
)
from src.core.scraper import EromeScraper
from src.core.downloader import DownloadManager
from src.gui.settings_frame import get_download_dir, get_workers
from src.utils.config import DEFAULT_WORKERS


class DownloadFrame(ctk.CTkFrame):
    def __init__(self, master, tab_name: str = "", app=None, **kwargs):
        super().__init__(master, **kwargs)

        self.tab_name = tab_name
        self.app = app
        self._msg_queue: queue.Queue = queue.Queue()
        self._cancel_event: asyncio.Event | None = None
        self._running = False
        self._start_time = 0.0
        self._phase = "idle"  # idle, scraping, downloading

        self._build_ui()
        self._poll_queue()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # --- Input ---
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="URL:").grid(row=0, column=0, padx=(0, 8), pady=5)
        self.url_var = ctk.StringVar()
        url_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.url_var,
            placeholder_text="URL, termo de busca, ou #hashtag",
        )
        url_entry.grid(row=0, column=1, sticky="ew", pady=5)

        ctk.CTkLabel(input_frame, text="Pasta:").grid(row=1, column=0, padx=(0, 8), pady=5)
        self.dir_var = ctk.StringVar(value=get_download_dir())
        dir_entry = ctk.CTkEntry(input_frame, textvariable=self.dir_var)
        dir_entry.grid(row=1, column=1, sticky="ew", pady=5)
        ctk.CTkButton(input_frame, text="...", width=40, command=self._browse_dir).grid(
            row=1, column=2, padx=(5, 0), pady=5
        )

        # --- Options row 1: tipo + workers + limite ---
        options_frame = ctk.CTkFrame(self, fg_color="transparent")
        options_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 2))

        self.photos_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(options_frame, text="Fotos", variable=self.photos_var).pack(
            side="left", padx=(0, 15)
        )

        self.videos_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(options_frame, text="Videos", variable=self.videos_var).pack(
            side="left", padx=(0, 15)
        )

        ctk.CTkLabel(options_frame, text="Workers:").pack(side="left", padx=(20, 5))
        self.workers_var = ctk.StringVar(value=str(get_workers()))
        ctk.CTkEntry(options_frame, textvariable=self.workers_var, width=50).pack(
            side="left", padx=(0, 15)
        )

        ctk.CTkLabel(options_frame, text="Limite:").pack(side="left", padx=(0, 5))
        self.limit_var = ctk.StringVar(value="0")
        ctk.CTkEntry(options_frame, textvariable=self.limit_var, width=60).pack(
            side="left", padx=(0, 5)
        )
        ctk.CTkLabel(options_frame, text="(0 = sem limite)", text_color="gray60").pack(
            side="left"
        )

        # --- Options row 2: filtro de duracao + rosto ---
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 5))

        ctk.CTkLabel(
            filter_frame, text="Duracao video:", text_color="gray70",
        ).pack(side="left", padx=(0, 5))

        ctk.CTkLabel(filter_frame, text="Min:").pack(side="left", padx=(0, 3))
        self.dur_min_min_var = ctk.StringVar(value="0")
        ctk.CTkEntry(filter_frame, textvariable=self.dur_min_min_var, width=35,
                      placeholder_text="m").pack(side="left")
        ctk.CTkLabel(filter_frame, text="m").pack(side="left", padx=(1, 3))
        self.dur_min_sec_var = ctk.StringVar(value="0")
        ctk.CTkEntry(filter_frame, textvariable=self.dur_min_sec_var, width=35,
                      placeholder_text="s").pack(side="left")
        ctk.CTkLabel(filter_frame, text="s").pack(side="left", padx=(1, 12))

        ctk.CTkLabel(filter_frame, text="Max:").pack(side="left", padx=(0, 3))
        self.dur_max_min_var = ctk.StringVar(value="0")
        ctk.CTkEntry(filter_frame, textvariable=self.dur_max_min_var, width=35,
                      placeholder_text="m").pack(side="left")
        ctk.CTkLabel(filter_frame, text="m").pack(side="left", padx=(1, 3))
        self.dur_max_sec_var = ctk.StringVar(value="0")
        ctk.CTkEntry(filter_frame, textvariable=self.dur_max_sec_var, width=35,
                      placeholder_text="s").pack(side="left")
        ctk.CTkLabel(filter_frame, text="s").pack(side="left", padx=(1, 20))

        self.face_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            filter_frame, text="So videos com rosto na thumb",
            variable=self.face_var,
        ).pack(side="left")

        # --- Buttons ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

        self.start_btn = ctk.CTkButton(
            btn_frame, text="Iniciar Download", command=self._start_download,
            height=36, font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="Parar", command=self._stop_download,
            height=36, fg_color="red", hover_color="darkred", state="disabled",
        )
        self.stop_btn.pack(side="left")

        # --- Scraping progress (search loading) ---
        self.scrape_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.scrape_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(5, 0))
        self.scrape_frame.grid_columnconfigure(1, weight=1)

        self.scrape_status_label = ctk.CTkLabel(
            self.scrape_frame,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#3B8ED0",
        )
        self.scrape_status_label.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.scrape_bar = ctk.CTkProgressBar(self.scrape_frame, height=8)
        self.scrape_bar.grid(row=0, column=1, sticky="ew")
        self.scrape_bar.set(0)

        self.scrape_frame.grid_remove()

        # --- Download progress ---
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=5)
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            progress_frame, text="0%", font=ctk.CTkFont(size=12)
        )
        self.progress_label.grid(row=0, column=1, padx=(10, 0))

        # --- Log ---
        self.grid_rowconfigure(6, weight=1)
        self.log_text = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.grid(row=6, column=0, sticky="nsew", padx=10, pady=5)

        # --- Footer ---
        self.footer_label = ctk.CTkLabel(
            self,
            text="Pronto",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        )
        self.footer_label.grid(row=7, column=0, sticky="ew", padx=10, pady=(0, 10))

    def _browse_dir(self):
        path = filedialog.askdirectory(initialdir=self.dir_var.get())
        if path:
            self.dir_var.set(path)

    # --- Message passing ---

    def _log(self, msg: str):
        self._msg_queue.put(("log", msg))

    def _update_progress(self, stats: DownloadStats):
        self._msg_queue.put(("progress", stats))

    def _update_result(self, result: DownloadResult):
        self._msg_queue.put(("result", result))

    def _update_scrape_progress(self, found: int, albums: int):
        self._msg_queue.put(("scrape_progress", (found, albums)))

    def _poll_queue(self):
        try:
            while True:
                msg_type, data = self._msg_queue.get_nowait()

                if msg_type == "log":
                    self.log_text.insert("end", data + "\n")
                    self.log_text.see("end")

                elif msg_type == "scrape_start":
                    self._phase = "scraping"
                    self.scrape_frame.grid()
                    self.scrape_bar.configure(mode="indeterminate")
                    self.scrape_bar.start()
                    self.scrape_status_label.configure(text="Buscando midias...")
                    self.footer_label.configure(text="Buscando midias...")

                elif msg_type == "scrape_progress":
                    found, albums = data
                    if found == -1:
                        self.scrape_status_label.configure(text="Acessando album...")
                    else:
                        self.scrape_status_label.configure(
                            text=f"Buscando... {found} midias em {albums} albums"
                        )
                        self.footer_label.configure(
                            text=f"Buscando midias... {found} encontradas em {albums} albums"
                        )

                elif msg_type == "scrape_done":
                    total = data
                    self.scrape_bar.stop()
                    self.scrape_bar.configure(mode="determinate")
                    self.scrape_bar.set(1)
                    if total > 0:
                        self.scrape_status_label.configure(
                            text=f"Busca concluida: {total} midias encontradas"
                        )
                    else:
                        self.scrape_status_label.configure(text="Nenhuma midia encontrada")
                    self._phase = "downloading" if total > 0 else "idle"

                elif msg_type == "progress":
                    stats: DownloadStats = data
                    if stats.total > 0:
                        pct = stats.completed / stats.total
                        self.progress_bar.set(pct)
                        self.progress_label.configure(text=f"{pct:.0%}")

                    elapsed = time.time() - self._start_time if self._start_time else 0
                    size_mb = stats.total_bytes / (1024 * 1024)
                    self.footer_label.configure(
                        text=(
                            f"{stats.completed}/{stats.total} arquivos | "
                            f"{size_mb:.1f} MB | "
                            f"{elapsed:.0f}s | "
                            f"{stats.failed} falhas | "
                            f"{stats.skipped} ignorados"
                        )
                    )

                elif msg_type == "result":
                    result: DownloadResult = data
                    icon = "SKIP" if result.skipped else ("OK" if result.success else "X")
                    self.log_text.insert(
                        "end",
                        f"[{icon}] {result.item.filename}"
                        + (f" ({result.file_size / 1024:.0f} KB)" if result.file_size else "")
                        + (f" - {result.error}" if result.error else "")
                        + "\n"
                    )
                    self.log_text.see("end")

                elif msg_type == "done":
                    self._phase = "idle"
                    self._set_running(False)

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)

    # --- Input parsing ---

    def _parse_input(self, raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return ""

        if "erome.com" in raw:
            return raw

        if raw.startswith("#") and len(raw) > 1:
            tag = raw[1:]
            return f"https://www.erome.com/search?q=%23{tag}"

        return f"https://www.erome.com/search?q={raw}"

    # --- Actions ---

    def _start_download(self):
        raw = self.url_var.get().strip()
        if not raw:
            self._log("Insira uma URL, termo de busca, ou #hashtag.")
            return

        url = self._parse_input(raw)
        if not url:
            self._log("Entrada invalida.")
            return

        try:
            workers = int(self.workers_var.get())
            workers = max(1, min(20, workers))
        except ValueError:
            workers = DEFAULT_WORKERS

        try:
            limit = int(self.limit_var.get())
            limit = max(0, limit)
        except ValueError:
            limit = 0

        dur_min = self._parse_int(self.dur_min_min_var.get()) * 60 + self._parse_int(self.dur_min_sec_var.get())
        dur_max = self._parse_int(self.dur_max_min_var.get()) * 60 + self._parse_int(self.dur_max_sec_var.get())

        options = DownloadOptions(
            url=url,
            download_dir=self.dir_var.get(),
            download_photos=self.photos_var.get(),
            download_videos=self.videos_var.get(),
            workers=workers,
            limit=limit,
            video_min_seconds=dur_min,
            video_max_seconds=dur_max,
            face_filter=self.face_var.get(),
        )

        self.log_text.delete("1.0", "end")
        self.progress_bar.set(0)
        self.progress_label.configure(text="0%")
        self.scrape_bar.set(0)
        self.scrape_status_label.configure(text="")
        self.scrape_frame.grid_remove()
        self._start_time = time.time()
        self._set_running(True)

        self._cancel_event = asyncio.Event()
        thread = threading.Thread(target=self._run_download, args=(options,), daemon=True)
        thread.start()

    def _run_download(self, options: DownloadOptions):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_download(options))
        except Exception as e:
            self._log(f"Erro: {e}")
        finally:
            loop.close()
            self._msg_queue.put(("done", None))

    async def _async_download(self, options: DownloadOptions):
        self._msg_queue.put(("scrape_start", None))

        scraper = EromeScraper(
            options=options,
            on_status=self._log,
            on_scrape_progress=self._update_scrape_progress,
            cancel_event=self._cancel_event,
        )

        try:
            items = await scraper.scrape()
            self._msg_queue.put(("scrape_done", len(items)))

            if not items:
                self._log("Nenhuma midia encontrada.")
                return

            self._log(f"\nIniciando download de {len(items)} itens...\n")

            downloader = DownloadManager(
                options=options,
                on_progress=self._update_progress,
                on_result=self._update_result,
                on_status=self._log,
                cancel_event=self._cancel_event,
            )

            await downloader.download_all(items)
        finally:
            await scraper.close()

    def _stop_download(self):
        if self._cancel_event:
            self._cancel_event.set()
        self._log("Cancelando...")

    @staticmethod
    def _parse_int(val: str) -> int:
        try:
            return max(0, int(val))
        except ValueError:
            return 0

    def _set_running(self, running: bool):
        self._running = running
        if running:
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
