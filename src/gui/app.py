import os
import sys
import asyncio
import threading
import customtkinter as ctk

from src.gui.download_frame import DownloadFrame
from src.gui.settings_frame import SettingsFrame
from src.core.updater import check_for_update, download_update, apply_update_and_restart
from src.utils.config import APP_NAME, APP_VERSION


def _get_icon_path() -> str | None:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon = os.path.join(base, "assets", "icon.ico")
    if os.path.exists(icon):
        return icon
    icon = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "assets", "icon.ico")
    return icon if os.path.exists(icon) else None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("900x700")
        self.minsize(800, 600)

        icon = _get_icon_path()
        if icon:
            self.iconbitmap(icon)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._tab_count = 0
        self._build_ui()

        # Check for updates in background
        self.after(1500, self._check_update_bg)

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self, corner_radius=8)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))

        self._add_session_tab()

        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom_frame.grid_columnconfigure(1, weight=1)

        add_btn = ctk.CTkButton(
            bottom_frame,
            text="+ Nova Sessao",
            width=130,
            height=32,
            command=self._add_session_tab,
        )
        add_btn.grid(row=0, column=0, padx=(0, 10))

        self.version_label = ctk.CTkLabel(
            bottom_frame,
            text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=11),
            text_color="gray50",
        )
        self.version_label.grid(row=0, column=1)

        settings_btn = ctk.CTkButton(
            bottom_frame,
            text="Configuracoes",
            width=130,
            height=32,
            fg_color="gray30",
            hover_color="gray40",
            command=self._open_settings,
        )
        settings_btn.grid(row=0, column=2)

    def _add_session_tab(self):
        self._tab_count += 1
        tab_name = f"Sessao {self._tab_count}"
        tab = self.tabview.add(tab_name)

        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        frame = DownloadFrame(tab, tab_name=tab_name, app=self)
        frame.grid(row=0, column=0, sticky="nsew")

        self.tabview.set(tab_name)

    def rename_tab(self, old_name: str, new_name: str):
        pass

    def _open_settings(self):
        settings_window = ctk.CTkToplevel(self)
        settings_window.title("Configuracoes")
        settings_window.geometry("500x300")
        settings_window.transient(self)
        settings_window.grab_set()

        settings_window.grid_rowconfigure(0, weight=1)
        settings_window.grid_columnconfigure(0, weight=1)

        frame = SettingsFrame(settings_window)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    # --- Auto Update ---

    def _check_update_bg(self):
        thread = threading.Thread(target=self._run_check_update, daemon=True)
        thread.start()

    def _run_check_update(self):
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(check_for_update())
            if result:
                self.after(0, lambda: self._show_update_dialog(result))
        except Exception:
            pass
        finally:
            loop.close()

    def _show_update_dialog(self, update_info: dict):
        version = update_info["version"]
        size_mb = update_info.get("size", 0) / (1024 * 1024)
        notes = update_info.get("notes", "")

        dialog = ctk.CTkToplevel(self)
        dialog.title("Atualizacao Disponivel")
        dialog.geometry("480x320")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        # Center on parent
        dialog.after(10, lambda: dialog.lift())

        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main_frame,
            text="Nova versao disponivel!",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            main_frame,
            text=f"v{APP_VERSION}  ->  v{version}",
            font=ctk.CTkFont(size=14),
            text_color="#3B8ED0",
        ).pack(pady=(0, 5))

        if size_mb > 0:
            ctk.CTkLabel(
                main_frame,
                text=f"Tamanho: {size_mb:.1f} MB",
                font=ctk.CTkFont(size=12),
                text_color="gray60",
            ).pack(pady=(0, 10))

        if notes:
            notes_box = ctk.CTkTextbox(main_frame, height=80, font=ctk.CTkFont(size=11))
            notes_box.pack(fill="x", pady=(0, 15))
            notes_box.insert("1.0", notes[:500])
            notes_box.configure(state="disabled")

        # Progress bar (hidden initially)
        self._update_progress_bar = ctk.CTkProgressBar(main_frame)
        self._update_progress_label = ctk.CTkLabel(
            main_frame, text="", font=ctk.CTkFont(size=11), text_color="gray60",
        )

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        self._update_btn = ctk.CTkButton(
            btn_frame,
            text="Atualizar Agora",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=38,
            command=lambda: self._start_update(update_info, dialog),
        )
        self._update_btn.pack(side="left", padx=(0, 10))

        skip_btn = ctk.CTkButton(
            btn_frame,
            text="Depois",
            height=38,
            fg_color="gray30",
            hover_color="gray40",
            command=dialog.destroy,
        )
        skip_btn.pack(side="left")

        self._update_dialog = dialog

    def _start_update(self, update_info: dict, dialog):
        self._update_btn.configure(state="disabled", text="Baixando...")

        self._update_progress_bar.pack(fill="x", pady=(0, 5))
        self._update_progress_bar.set(0)
        self._update_progress_label.pack()
        self._update_progress_label.configure(text="Iniciando download...")

        thread = threading.Thread(
            target=self._run_download_update,
            args=(update_info,),
            daemon=True,
        )
        thread.start()

    def _run_download_update(self, update_info: dict):
        loop = asyncio.new_event_loop()
        try:
            def on_progress(pct):
                self.after(0, lambda p=pct: self._on_update_progress(p))

            def on_status(msg):
                self.after(0, lambda m=msg: self._update_progress_label.configure(text=m))

            tmp_path = loop.run_until_complete(
                download_update(
                    update_info["download_url"],
                    on_progress=on_progress,
                    on_status=on_status,
                )
            )

            if tmp_path:
                self.after(0, lambda: self._apply_update(tmp_path))
            else:
                self.after(0, lambda: self._update_failed())

        except Exception as e:
            self.after(0, lambda: self._update_failed())
        finally:
            loop.close()

    def _on_update_progress(self, pct: float):
        self._update_progress_bar.set(pct)
        self._update_progress_label.configure(text=f"Baixando... {pct:.0%}")

    def _apply_update(self, tmp_path: str):
        self._update_progress_label.configure(text="Aplicando atualizacao... reiniciando!")
        self._update_btn.configure(text="Reiniciando...")
        self.after(500, lambda: apply_update_and_restart(tmp_path))

    def _update_failed(self):
        self._update_btn.configure(state="normal", text="Tentar Novamente")
        self._update_progress_label.configure(text="Falha no download. Tente novamente.")
