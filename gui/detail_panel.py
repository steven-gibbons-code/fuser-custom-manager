from tkinter import filedialog
import webbrowser
from pathlib import Path
import sqlite3
import customtkinter as ctk

_FIELDS = [
    ("artist",        "Artist"),
    ("title",         "Title"),
    ("creator",       "Creator"),
    ("bpm",           "BPM"),
    ("key",           "Key"),
    ("genre",         "Genre"),
    ("year",          "Year"),
    ("submit_date",   "Date"),
    ("source",        "Source"),
    ("de_status",     "DE Status"),
    ("complete",      "Complete"),
    ("complete_notes","Notes"),
    ("origin",        "Origin"),
    ("stream_opt",    "Stream-Opt"),
]


class DetailPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, conn: sqlite3.Connection,
                 on_download=None, on_uninstall=None, on_manual_install=None, **kwargs):
        super().__init__(master, **kwargs)
        self._conn = conn
        self._on_download = on_download
        self._on_uninstall = on_uninstall
        self._on_manual_install = on_manual_install
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

        self._mark_btn = ctk.CTkButton(
            self, text="Mark as Installed (browse .pak…)",
            fg_color="#3a5a7a", hover_color="#4a7a9a",
            command=self._browse_manual_install)
        self._mark_btn.grid(row=base + 3, column=0, columnspan=2, sticky="ew", padx=10, pady=4)

        self._un_btn = ctk.CTkButton(self, text="Uninstall",
                                      fg_color="#7d1a1a", hover_color="#a32020",
                                      command=self._uninstall)
        self._un_btn.grid(row=base + 4, column=0, columnspan=2, sticky="ew", padx=10, pady=4)

        self._manual_lbl = ctk.CTkLabel(
            self, text="", text_color="#f4a261", wraplength=240, justify="left")
        self._manual_lbl.grid(row=base + 5, column=0, columnspan=2,
                               sticky="w", padx=10, pady=(4, 0))

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
        self._link_btn.configure(text=(link[:38] + "…") if len(link) > 38 else link or "—")
        self._path_lbl.configure(
            text=f"Installed: {song['pak_path']}" if song.get("pak_path") else "")
        self._sync_buttons()

    def show_manual_link(self, url: str):
        self._manual_lbl.configure(
            text="Manual download required.\nClick the link above to open in browser.")

    def _sync_buttons(self):
        if not self._song:
            self._dl_btn.configure(state="disabled")
            self._mark_btn.configure(state="disabled")
            self._un_btn.configure(state="disabled")
            return
        installed = bool(self._song.get("pak_path"))
        self._dl_btn.configure(state="disabled" if installed else "normal")
        self._mark_btn.configure(state="disabled" if installed else "normal")
        self._un_btn.configure(state="normal" if installed else "disabled")

    def _open_link(self):
        if self._song:
            link = self._song.get("link", "")
            if link:
                webbrowser.open(link)

    def _download(self):
        if self._song and self._on_download:
            self._dl_btn.configure(state="disabled")
            self._on_download(self._song)

    def _browse_manual_install(self):
        if not self._song or not self._on_manual_install:
            return
        # Hide any previous manual message
        self._manual_lbl.configure(text="")

        pak_path = filedialog.askopenfilename(
            title="Select .pak file to install",
            filetypes=[("PAK files", "*.pak"), ("All files", "*.*")],
            parent=self.winfo_toplevel(),
        )
        if not pak_path:
            return  # user cancelled

        pak = Path(pak_path)

        # Try to find a matching .sig in the same directory
        sig_candidate = pak.with_suffix(".sig")
        sig = sig_candidate if sig_candidate.exists() else None

        self._on_manual_install(self._song, pak, sig)

    def _uninstall(self):
        if self._song and self._on_uninstall:
            self._on_uninstall(self._song)
