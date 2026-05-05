import webbrowser
import sqlite3
import customtkinter as ctk

from sources.fucuco import get_sheet_tab_url, SHEET_URL

_FIELDS = [
    ("artist",        "Artist"),
    ("title",         "Title"),
    ("creator",       "Creator"),
    ("bpm",           "BPM"),
    ("key",           "Key"),
    ("genre",         "Genre"),
    ("year",          "Year"),
    ("source",        "Source"),
    ("de_status",     "DE Status"),
    ("complete",      "Complete"),
    ("complete_notes","Notes"),
    ("origin",        "Origin"),
    ("stream_opt",    "Stream-Opt"),
]


class DetailPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, conn: sqlite3.Connection,
                 on_download=None, on_uninstall=None, **kwargs):
        super().__init__(master, **kwargs)
        self._conn = conn
        self._on_download = on_download
        self._on_uninstall = on_uninstall
        self._song: dict | None = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self._value_labels: dict[str, ctk.CTkLabel] = {}

        for i, (field, label) in enumerate(_FIELDS):
            ctk.CTkLabel(self, text=f"{label}:", anchor="w",
                          font=ctk.CTkFont(weight="bold")).grid(
                row=i, column=0, sticky="nw", padx=(10, 4), pady=(4, 0))
            lbl = ctk.CTkLabel(self, text="—", anchor="w", wraplength=220, justify="left")
            lbl.grid(row=i, column=1, sticky="w", padx=4, pady=(4, 0))
            self._value_labels[field] = lbl

        base = len(_FIELDS)

        ctk.CTkLabel(self, text="Link:", anchor="w",
                      font=ctk.CTkFont(weight="bold")).grid(
            row=base, column=0, sticky="nw", padx=(10, 4), pady=(4, 0))
        self._link_btn = ctk.CTkButton(self, text="—", anchor="w", width=220,
                                        fg_color="transparent", text_color="#6ab0f5",
                                        command=self._open_link)
        self._link_btn.grid(row=base, column=1, sticky="w", padx=4)

        self._path_lbl = ctk.CTkLabel(self, text="", anchor="w",
                                       text_color="#aaaaaa", wraplength=240, justify="left")
        self._path_lbl.grid(row=base + 1, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 8))

        self._dl_btn = ctk.CTkButton(self, text="Download & Install", command=self._download)
        self._dl_btn.grid(row=base + 2, column=0, columnspan=2, sticky="ew", padx=10, pady=4)

        self._un_btn = ctk.CTkButton(self, text="Uninstall",
                                      fg_color="#7d1a1a", hover_color="#a32020",
                                      command=self._uninstall)
        self._un_btn.grid(row=base + 3, column=0, columnspan=2, sticky="ew", padx=10, pady=4)

        self._manual_lbl = ctk.CTkLabel(
            self, text="", text_color="#f4a261", wraplength=240, justify="left")
        self._manual_lbl.grid(row=base + 4, column=0, columnspan=2,
                               sticky="w", padx=10, pady=(4, 0))

        # Source sheet link — for packs, new submissions, or browsing the catalog
        self._sheet_btn = ctk.CTkButton(
            self, text="Browse source sheet", anchor="w",
            fg_color="transparent", text_color="#6ab0f5",
            command=self._open_source_sheet)
        self._sheet_btn.grid(row=base + 5, column=0, columnspan=2,
                              sticky="w", padx=10, pady=(4, 0))
        self._sheet_btn.grid_remove()  # hidden by default

        self._sync_buttons()

    def show(self, song: dict):
        self._song = song
        self._manual_lbl.configure(text="")
        for field, lbl in self._value_labels.items():
            val = song.get(field)
            if field == "stream_opt":
                text = "Yes" if val else "No"
            elif field == "complete":
                text = {"D": "Definitive", "C": "Complete"}.get(str(val or ""), str(val or "—"))
            else:
                text = str(val) if val not in (None, "") else "—"
            lbl.configure(text=text)

        link = song.get("link", "")
        has_link = bool(link)
        self._link_btn.configure(text=(link[:38] + "…") if len(link) > 38 else link)
        self._path_lbl.configure(
            text=f"Installed: {song['pak_path']}" if song.get("pak_path") else "")

        # Show "Browse source sheet" for songs without a direct download link (e.g. packs)
        source = song.get("source", "")
        tab_url = get_sheet_tab_url(source)
        if tab_url and not has_link:
            self._sheet_btn.configure(text=f"Browse {source} sheet")
            self._sheet_btn.grid()
        else:
            self._sheet_btn.grid_remove()

        self._sync_buttons()

    def show_manual_link(self, url: str):
        self._manual_lbl.configure(
            text="Manual download required.\nClick the link above to open in browser.")

    def show_no_song_found(self, search_text: str = ""):
        """Show a message when no song is selected / search is empty."""
        self._song = None
        for lbl in self._value_labels.values():
            lbl.configure(text="—")
        self._link_btn.configure(text="—")
        self._path_lbl.configure(text="")
        self._manual_lbl.configure(text="")
        self._sheet_btn.configure(
            text="Browse NEW SUBMISSIONS sheet (latest additions)",
            command=lambda: webbrowser.open(f"{SHEET_URL}#gid=0"))
        self._sheet_btn.grid()
        self._sync_buttons()

    def _sync_buttons(self):
        if not self._song:
            self._dl_btn.configure(state="disabled")
            self._un_btn.configure(state="disabled")
            return
        installed = bool(self._song.get("pak_path"))
        has_link = bool(self._song.get("link", ""))
        if installed:
            self._dl_btn.configure(state="disabled")
            self._un_btn.configure(state="normal")
        elif has_link:
            self._dl_btn.configure(state="normal")
            self._un_btn.configure(state="disabled")
        else:
            # Packs or other songs without a link — disable download
            self._dl_btn.configure(state="disabled")
            self._un_btn.configure(state="disabled")

    def _open_link(self):
        if self._song:
            link = self._song.get("link", "")
            if link:
                webbrowser.open(link)

    def _open_source_sheet(self):
        if self._song:
            source = self._song.get("source", "")
            url = get_sheet_tab_url(source)
            if url:
                webbrowser.open(url)

    def _download(self):
        if self._song and self._on_download:
            self._dl_btn.configure(state="disabled")
            self._on_download(self._song)

    def _uninstall(self):
        if self._song and self._on_uninstall:
            self._on_uninstall(self._song)