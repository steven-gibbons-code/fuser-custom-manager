import sqlite3
import threading
from datetime import date

import customtkinter as ctk

from db import init_db, get_songs, upsert_songs, get_song_by_id
from downloader import download
from installer import scan_and_sync, install_pairs, uninstall, INSTALL_DIR
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
        scan_and_sync(INSTALL_DIR, self.conn)
        self._build_ui()
        self._refresh_table()

    # ── Layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(2, weight=1)

        # Row 0 — search + actions
        top = ctk.CTkFrame(self, height=48)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Search:").grid(row=0, column=0, padx=6)
        self._search = ctk.StringVar()
        self._search.trace_add("write", lambda *_: self._refresh_table())
        ctk.CTkEntry(top, textvariable=self._search, width=240).grid(
            row=0, column=1, padx=4, sticky="ew")

        self._def_only = ctk.BooleanVar()
        ctk.CTkCheckBox(top, text="Definitive only", variable=self._def_only,
                         command=self._refresh_table).grid(row=0, column=2, padx=6)

        self._refresh_btn = ctk.CTkButton(top, text="Refresh Sources", width=130,
                                           command=self._start_refresh)
        self._refresh_btn.grid(row=0, column=3, padx=6)

        self._updated_lbl = ctk.CTkLabel(top, text="", text_color="#aaaaaa")
        self._updated_lbl.grid(row=0, column=4, padx=6)

        # Row 1 — filter bar
        fbar = ctk.CTkFrame(self, height=40)
        fbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))

        SOURCES = ["All Sources", "fucuco_main", "fucuco_vgm", "fusersoundlab"]
        ctk.CTkLabel(fbar, text="Source:").pack(side="left", padx=6)
        self._source = ctk.StringVar(value="All Sources")
        ctk.CTkOptionMenu(fbar, variable=self._source, values=SOURCES, width=130,
                           command=lambda _: self._refresh_table()).pack(side="left", padx=4)

        ctk.CTkLabel(fbar, text="Genre:").pack(side="left", padx=(10, 4))
        self._genre = ctk.StringVar()
        self._genre.trace_add("write", lambda *_: self._refresh_table())
        ctk.CTkEntry(fbar, textvariable=self._genre, width=100).pack(side="left", padx=2)

        ctk.CTkLabel(fbar, text="BPM:").pack(side="left", padx=(10, 4))
        self._bpm_min = ctk.StringVar()
        self._bpm_max = ctk.StringVar()
        self._bpm_min.trace_add("write", lambda *_: self._refresh_table())
        self._bpm_max.trace_add("write", lambda *_: self._refresh_table())
        ctk.CTkEntry(fbar, textvariable=self._bpm_min, width=55,
                      placeholder_text="min").pack(side="left", padx=2)
        ctk.CTkLabel(fbar, text="–").pack(side="left")
        ctk.CTkEntry(fbar, textvariable=self._bpm_max, width=55,
                      placeholder_text="max").pack(side="left", padx=2)

        # Row 2 — table + detail
        self.song_table = SongTable(self, on_select=self._on_select)
        self.song_table.grid(row=2, column=0, sticky="nsew", padx=(8, 4), pady=8)

        self.detail_panel = DetailPanel(self, conn=self.conn,
                                         on_download=self._on_download,
                                         on_uninstall=self._on_uninstall)
        self.detail_panel.grid(row=2, column=1, sticky="nsew", padx=(4, 8), pady=8)

        # Row 3 — status bar
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=3, column=0, columnspan=2,
                              sticky="ew", padx=8, pady=(0, 8))

    # ── Helpers ───────────────────────────────────────────────────────────
    def _filters(self) -> dict:
        f: dict = {
            "search":         self._search.get(),
            "definitive_only": self._def_only.get(),
        }
        if self._source.get() != "All Sources":
            f["source"] = self._source.get()
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
        return f

    def _refresh_table(self):
        self.song_table.load(get_songs(self.conn, self._filters()))

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
            install_pairs(result, song["id"], song["artist"], INSTALL_DIR, self.conn)
            self.after(0, self._refresh_table)
            self.after(0, lambda: self.status_bar.set_done(song["title"]))
        elif result.status == "manual":
            self.after(0, lambda: self.detail_panel.show_manual_link(result.raw_url))
            self.after(0, self.status_bar.set_idle)
        else:
            self.after(0, lambda: self.status_bar.set_error(result.error_msg or "Unknown error"))

    def _on_uninstall(self, song: dict):
        uninstall(song["id"], INSTALL_DIR, self.conn)
        self._refresh_table()
        self.detail_panel.show(get_song_by_id(self.conn, song["id"]) or {})
