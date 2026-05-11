from pathlib import Path
import sqlite3
import threading
from datetime import date

import customtkinter as ctk

from tkinter import filedialog
from db import init_db, get_songs, upsert_songs, get_song_by_id, count_songs, get_setting, set_setting
from downloader import download
from installer import scan_and_sync, install_pairs, install_manual_files, uninstall, DEFAULT_INSTALL_DIR
from sources.fucuco import fetch_all as fetch_fucuco
from sources.fusersoundlab import fetch_all as fetch_fsl
from gui.song_table import SongTable
from gui.detail_panel import DetailPanel
from gui.status_bar import StatusBar

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class FuserApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Fuser Custom Song Manager")
        self.geometry("1200x800")
        self.conn: sqlite3.Connection = init_db()
        self._page: int = 0
        self._total_songs: int = 0
        path_str = get_setting(self.conn, "install_path")
        self._install_dir = Path(path_str) if path_str else DEFAULT_INSTALL_DIR
        scan_and_sync(self._install_dir, self.conn)
        self._build_ui()
        self._refresh_table()

    # ── Layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(3, weight=1)  # table row is now 3

        # Row 0 — search + actions
        top = ctk.CTkFrame(self, height=48)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Search:").grid(row=0, column=0, padx=6)
        self._search = ctk.StringVar()
        self._search.trace_add("write", lambda *_: self._filter_changed())
        ctk.CTkEntry(top, textvariable=self._search, width=240).grid(
            row=0, column=1, padx=4, sticky="ew")

        self._refresh_btn = ctk.CTkButton(top, text="Refresh Sources", width=130,
                                           command=self._start_refresh)
        self._refresh_btn.grid(row=0, column=3, padx=6)

        self._updated_lbl = ctk.CTkLabel(top, text="", text_color="#aaaaaa")
        self._updated_lbl.grid(row=0, column=4, padx=6)

        ctk.CTkButton(top, text="Settings", width=70, fg_color="#555555",
                       hover_color="#777777",
                       command=self._open_settings).grid(row=0, column=5, padx=6)

        # Row 1 — filter bar
        fbar = ctk.CTkFrame(self, height=40)
        fbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))

        SOURCES = ["All Sources", "fucuco_main", "fucuco_vgm", "fusersoundlab"]
        ctk.CTkLabel(fbar, text="Source:").pack(side="left", padx=6)
        self._source = ctk.StringVar(value="All Sources")
        ctk.CTkOptionMenu(fbar, variable=self._source, values=SOURCES, width=130,
                           command=lambda _: self._filter_changed()).pack(side="left", padx=4)

        QUALITIES = ["All Quality", "Official", "Definitive", "Complete", "Other"]
        ctk.CTkLabel(fbar, text="Quality:").pack(side="left", padx=(10, 4))
        self._quality = ctk.StringVar(value="All Quality")
        ctk.CTkOptionMenu(fbar, variable=self._quality, values=QUALITIES, width=110,
                           command=lambda _: self._filter_changed()).pack(side="left", padx=4)

        INSTALLED_OPTS = ["All", "Installed", "Not installed"]
        ctk.CTkLabel(fbar, text="Status:").pack(side="left", padx=(10, 4))
        self._installed = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(fbar, variable=self._installed, values=INSTALLED_OPTS, width=110,
                           command=lambda _: self._filter_changed()).pack(side="left", padx=4)

        ctk.CTkLabel(fbar, text="Genre:").pack(side="left", padx=(10, 4))
        self._genre = ctk.StringVar()
        self._genre.trace_add("write", lambda *_: self._filter_changed())
        ctk.CTkEntry(fbar, textvariable=self._genre, width=100).pack(side="left", padx=2)

        ctk.CTkLabel(fbar, text="BPM:").pack(side="left", padx=(10, 4))
        self._bpm_min = ctk.StringVar()
        self._bpm_max = ctk.StringVar()
        self._bpm_min.trace_add("write", lambda *_: self._filter_changed())
        self._bpm_max.trace_add("write", lambda *_: self._filter_changed())
        ctk.CTkEntry(fbar, textvariable=self._bpm_min, width=55,
                      placeholder_text="min").pack(side="left", padx=2)
        ctk.CTkLabel(fbar, text="–").pack(side="left")
        ctk.CTkEntry(fbar, textvariable=self._bpm_max, width=55,
                      placeholder_text="max").pack(side="left", padx=2)

        SORT_OPTS = ["Artist A–Z", "Newest First", "BPM ↑", "BPM ↓"]
        ctk.CTkLabel(fbar, text="Sort:").pack(side="left", padx=(10, 4))
        self._sort = ctk.StringVar(value="Artist A–Z")
        ctk.CTkOptionMenu(fbar, variable=self._sort, values=SORT_OPTS, width=120,
                           command=lambda _: self._filter_changed()).pack(side="left", padx=4)

        ctk.CTkButton(fbar, text="Clear Filters", width=80, fg_color="#555555",
                       hover_color="#777777",
                       command=self._clear_filters).pack(side="left", padx=(10, 4))

        # Row 2 — pagination bar
        pbar = ctk.CTkFrame(self, height=36)
        pbar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))

        self._prev_btn = ctk.CTkButton(pbar, text="← Prev", width=70,
                                        command=self._prev_page, state="disabled")
        self._prev_btn.pack(side="left", padx=6)

        self._page_lbl = ctk.CTkLabel(pbar, text="Page 1 of 1  (0 songs)")
        self._page_lbl.pack(side="left", padx=8)

        self._next_btn = ctk.CTkButton(pbar, text="Next →", width=70,
                                        command=self._next_page, state="disabled")
        self._next_btn.pack(side="left", padx=6)

        # Row 3 — table + detail
        self.song_table = SongTable(self, on_select=self._on_select)
        self.song_table.grid(row=3, column=0, sticky="nsew", padx=(8, 4), pady=8)

        self.detail_panel = DetailPanel(self, conn=self.conn,
                                         on_download=self._on_download,
                                         on_uninstall=self._on_uninstall,
                                         on_manual_install=self._on_manual_install)
        self.detail_panel.grid(row=3, column=1, sticky="nsew", padx=(4, 8), pady=8)

        # Row 4 — status bar
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=4, column=0, columnspan=2,
                              sticky="ew", padx=8, pady=(0, 8))

    # ── Helpers ───────────────────────────────────────────────────────────
    _SORT_MAP = {
        "Artist A–Z":   ("s.artist",      False),
        "Newest First": ("s.submit_date", True),
        "BPM ↑":        ("s.bpm",         False),
        "BPM ↓":        ("s.bpm",         True),
    }
    _INSTALLED_MAP = {
        "Installed":     "installed",
        "Not installed": "not_installed",
    }

    def _filters(self) -> dict:
        f: dict = {
            "search": self._search.get(),
            "offset": self._page * 100,
        }
        if self._source.get() != "All Sources":
            f["source"] = self._source.get()
        if self._quality.get() != "All Quality":
            f["quality"] = self._quality.get()
        installed_val = self._INSTALLED_MAP.get(self._installed.get())
        if installed_val:
            f["installed"] = installed_val
        if self._genre.get():
            f["genre"] = self._genre.get()
        try:
            if self._bpm_min.get():
                f["bpm_min"] = int(self._bpm_min.get())
        except ValueError:
            pass
        try:
            if self._bpm_max.get():
                f["bpm_max"] = int(self._bpm_max.get())
        except ValueError:
            pass
        order_by, descending = self._SORT_MAP.get(self._sort.get(), ("s.artist", False))
        f["order_by"] = order_by
        if descending:
            f["descending"] = True
        return f

    def _refresh_table(self):
        filters = self._filters()
        rows = get_songs(self.conn, filters)
        self._total_songs = count_songs(self.conn, filters)
        self.song_table.load(rows)
        total_pages = max(1, (self._total_songs + 99) // 100)
        self._page_lbl.configure(
            text=f"Page {self._page + 1} of {total_pages}  ({self._total_songs:,} songs)")
        self._prev_btn.configure(state="normal" if self._page > 0 else "disabled")
        self._next_btn.configure(
            state="normal" if (self._page + 1) * 100 < self._total_songs else "disabled")

    def _filter_changed(self):
        self._page = 0
        self._refresh_table()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._refresh_table()

    def _next_page(self):
        if (self._page + 1) * 100 < self._total_songs:
            self._page += 1
            self._refresh_table()

    def _clear_filters(self):
        self._search.set("")
        self._source.set("All Sources")
        self._quality.set("All Quality")
        self._installed.set("All")
        self._genre.set("")
        self._bpm_min.set("")
        self._bpm_max.set("")
        self._sort.set("Artist A–Z")
        self._filter_changed()

    def _open_settings(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Settings")
        dialog.geometry("520x220")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frame, text="Song Install Directory",
                      font=ctk.CTkFont(weight="bold", size=13)).pack(anchor="w")
        ctk.CTkLabel(frame, text="Choose where .pak/.sig files are installed:",
                      text_color="#aaaaaa").pack(anchor="w", pady=(2, 8))

        path_var = ctk.StringVar(value=str(self._install_dir))
        ctk.CTkEntry(frame, textvariable=path_var, width=480).pack(fill="x", pady=(0, 4))

        def browse():
            chosen = filedialog.askdirectory(
                title="Select install directory",
                initialdir=path_var.get(),
                parent=dialog,
            )
            if chosen:
                path_var.set(chosen)

        def _do_save(new_path):
            save_btn.configure(state="disabled", text="Saving…")

            def _thread():
                new_path.mkdir(parents=True, exist_ok=True)
                set_setting(self.conn, "install_path", str(new_path))
                scan_and_sync(new_path, self.conn)

                def _finish():
                    self._install_dir = new_path
                    self._refresh_table()
                    self.status_bar.set_message(f"Install path: {new_path}")
                    dialog.destroy()

                self.after(0, _finish)

            threading.Thread(target=_thread, daemon=True).start()

        def _confirm_mkdir(new_path):
            confirm = ctk.CTkToplevel(dialog)
            confirm.title("Create Directory?")
            confirm.geometry("420x130")
            confirm.resizable(False, False)
            confirm.transient(dialog)
            confirm.grab_set()

            ctk.CTkLabel(
                confirm,
                text=f"Directory does not exist:\n{new_path}\n\nCreate it?",
                justify="left",
            ).pack(padx=16, pady=(16, 8))

            btn_row = ctk.CTkFrame(confirm, fg_color="transparent")
            btn_row.pack()

            ctk.CTkButton(
                btn_row, text="Yes", width=80,
                command=lambda: (confirm.destroy(), _do_save(new_path)),
            ).pack(side="left", padx=4)
            ctk.CTkButton(
                btn_row, text="No", width=80, fg_color="#555555", hover_color="#777777",
                command=lambda: (
                    confirm.destroy(),
                    save_btn.configure(state="normal", text="Save"),
                ),
            ).pack(side="left", padx=4)

        def save():
            new_path = Path(path_var.get().strip())
            if not new_path.exists():
                _confirm_mkdir(new_path)
            else:
                _do_save(new_path)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(8, 0))

        ctk.CTkButton(btn_frame, text="Browse…", width=80,
                       command=browse).pack(side="left", padx=(0, 6))
        save_btn = ctk.CTkButton(btn_frame, text="Save", width=80, command=save)
        save_btn.pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Cancel", width=80,
                       fg_color="#555555", hover_color="#777777",
                       command=dialog.destroy).pack(side="left", padx=6)

    def _on_select(self, song: dict):
        self.detail_panel.show(song)

    # ── Refresh sources ───────────────────────────────────────────────────
    def _start_refresh(self):
        self._refresh_btn.configure(state="disabled", text="Refreshing…")
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self):
        try:
            upsert_songs(self.conn, fetch_fucuco() + fetch_fsl())
            self.after(0, lambda: self._updated_lbl.configure(
                text=f"Updated {date.today().isoformat()}"))
            self.after(0, self._refresh_table)
        except Exception as exc:
            import traceback
            msg = f"{type(exc).__name__}: {exc or traceback.format_exc().splitlines()[-1]}"
            self.after(0, lambda: self.status_bar.set_error(msg))
        finally:
            self.after(0, lambda: self._refresh_btn.configure(
                state="normal", text="Refresh Sources"))

    # ── Download / install ────────────────────────────────────────────────
    def _on_download(self, song: dict):
        self.status_bar.start_download(song["title"])
        threading.Thread(target=self._do_download, args=(song,), daemon=True).start()

    def _do_download(self, song: dict):
        result = download(
            song["link"],
            progress_cb=lambda p: self.after(0, lambda: self.status_bar.set_progress(p)),
        )
        if result.status == "ok":
            install_pairs(result, song["id"], song["artist"], self._install_dir, self.conn)
            self.after(0, self._refresh_table)
            self.after(0, lambda: self.status_bar.set_done(song["title"]))
        elif result.status == "manual":
            self.after(0, lambda: self.detail_panel.show_manual_link(result.raw_url))
            self.after(0, self.status_bar.set_idle)
        else:
            self.after(0, lambda: self.status_bar.set_error(result.error_msg or "Unknown error"))

    def _on_manual_install(self, song: dict, pak_path: Path, sig_path: Path | None):
        install_manual_files(song["id"], song["artist"], pak_path, sig_path, self._install_dir, self.conn)
        self._refresh_table()
        self.detail_panel.show(get_song_by_id(self.conn, song["id"]) or {})
        self.status_bar.set_done(song["title"])

    def _on_uninstall(self, song: dict):
        uninstall(song["id"], self._install_dir, self.conn)
        self._refresh_table()
        self.detail_panel.show(get_song_by_id(self.conn, song["id"]) or {})
