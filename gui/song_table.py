import tkinter.font as tkfont
import customtkinter as ctk
from tkinter import ttk

_QUALITY_COLORS = {
    "Official":   "#bb86fc",  # purple
    "Definitive": "#e8e8e8",  # platinum/silver
    "Complete":   "#ffd700",  # gold
    "Other":      "#888888",  # dim gray
}
_QUALITY_ABBR = {"Official": "Off", "Definitive": "Def", "Complete": "Cmp"}

COLUMNS = [
    ("status",  "Status",  25),
    ("quality", "Quality", 35),
    ("artist",  "Artist",  150),
    ("title",   "Title",   220),
    ("creator", "Creator", 80),
    ("bpm",     "BPM",     30),
    ("key",     "Key",     90),
    ("genre",   "Genre",   100),
    ("year",    "Year",    50),
    ("source",  "Source",  95),
]


class SongTable(ctk.CTkFrame):
    def __init__(self, master, on_select=None, on_selection_change=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._on_selection_change = on_selection_change
        self._rows: list[dict] = []
        self._sort_col = "artist"
        self._sort_asc = True
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        base_font = tkfont.nametofont("TkDefaultFont")
        base_font.configure(size=15)
        table_font = (base_font.actual("family"), 15)
        bold_font = (base_font.actual("family"), 15, "bold")

        style.configure("Treeview", background="#2b2b2b", foreground="white",
                         fieldbackground="#2b2b2b", rowheight=28, font=table_font)
        style.configure("Treeview.Heading", background="#1f538d",
                         foreground="white", font=bold_font)
        style.map("Treeview", background=[("selected", "#1f538d")])

        cols = [c[0] for c in COLUMNS]
        self._tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        for col_id, label, width in COLUMNS:
            self._tree.heading(col_id, text=label,
                                command=lambda c=col_id: self._toggle_sort(c))
            self._tree.column(col_id, width=width, minwidth=40)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self._tree.tag_configure("installed", background="#1a3a2a")
        self._tree.tag_configure("altrow", background="#353535")
        for tier, color in _QUALITY_COLORS.items():
            self._tree.tag_configure(f"q_{tier}", foreground=color)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def load(self, rows: list[dict]):
        self._rows = rows
        self._tree.delete(*self._tree.get_children())
        for i, r in enumerate(rows):
            values = (
                "✓" if r.get("pak_path") else "",
                _QUALITY_ABBR.get(r.get("quality", ""), ""),
                r.get("artist", ""),
                r.get("title", ""),
                r.get("creator", ""),
                r.get("bpm", ""),
                r.get("key", ""),
                r.get("genre", ""),
                r.get("year", ""),
                r.get("source", ""),
            )
            quality_key = r.get("quality", "")
            color_tag = f"q_{quality_key}" if quality_key in _QUALITY_COLORS else ""
            installed_tag = "installed" if r.get("pak_path") else ""
            # Stack tags: altrow bg first so installed bg overrides it
            tags = []
            if i % 2 == 1:
                tags.append("altrow")
            if installed_tag:
                tags.append(installed_tag)
            if color_tag:
                tags.append(color_tag)
            self._tree.insert("", "end", iid=str(r["id"]), values=values, tags=tuple(tags))

    def _toggle_sort(self, col: str):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col, self._sort_asc = col, True
        self._rows.sort(key=lambda r: (r.get(col) or ""), reverse=not self._sort_asc)
        self.load(self._rows)

    def set_selectmode(self, mode: str):
        assert mode in ("browse", "extended", "none"), f"Invalid selectmode: {mode!r}"
        self._tree.configure(selectmode=mode)

    def get_selected_songs(self) -> list[dict]:
        sel_ids = set(self._tree.selection())
        return [r for r in self._rows if str(r["id"]) in sel_ids]

    def select_all(self):
        for r in self._rows:
            self._tree.selection_add(str(r["id"]))
        if self._on_selection_change:
            self._on_selection_change()

    def deselect_all(self):
        self._tree.selection_remove(*self._tree.selection())
        if self._on_selection_change:
            self._on_selection_change()

    def _on_tree_select(self, _event):
        sel = self._tree.selection()
        if self._on_selection_change:
            self._on_selection_change()
        if not sel or not self._on_select:
            return
        song = next((r for r in self._rows if str(r["id"]) == sel[-1]), None)
        if song:
            self._on_select(song)
