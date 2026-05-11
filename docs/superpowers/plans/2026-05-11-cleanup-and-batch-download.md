# Cleanup & Batch Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix six code-quality issues identified in code review, then add explicit batch-download mode (Option A) with a "Batch" toggle button in the pagination bar.

**Architecture:** All GUI code stays in the existing file structure. Cleanup tasks are self-contained; batch download wires `SongTable` selection callbacks into new `MainWindow` methods that manage a `_batch_mode` flag, hide/show the detail panel, and run sequential downloads on a daemon thread.

**Tech Stack:** Python 3.11+, CustomTkinter, tkinter/ttk, SQLite via stdlib `sqlite3`, `threading`, `pytest`

---

## File Map

| File | Change |
|---|---|
| `tests/test_db.py` | Add 4 settings tests |
| `db.py` | Remove redundant `conn.commit()` at line 158 |
| `gui/status_bar.py` | Add `set_message(text)` public method |
| `gui/song_table.py` | Rename `"evenrow"` → `"altrow"`; add `on_selection_change`, `select_all`, `deselect_all`, `get_selected_songs`, `set_selectmode` |
| `gui/main_window.py` | Settings Save: inline `entry`, use `set_message`, add mkdir confirm, background thread. Batch mode: new state + 8 methods + batch controls in pagination bar |

---

## Task 1: Add settings tests to `test_db.py`

**Files:**
- Modify: `tests/test_db.py`

- [ ] **Step 1: Add import and four new tests**

Open `tests/test_db.py`. Add `get_setting, set_setting` to the existing `from db import ...` line at the top, then append these four tests at the end of the file:

```python
# At the top, update the import:
from db import init_db, upsert_songs, get_songs, mark_installed, mark_uninstalled, get_installed, get_setting, set_setting

# Append at end of file:
def test_settings_table_created(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "settings" in tables

def test_get_set_setting(conn):
    set_setting(conn, "my_key", "my_value")
    assert get_setting(conn, "my_key") == "my_value"
    assert get_setting(conn, "nonexistent") is None

def test_init_db_seeds_default_install_path(tmp_path):
    c = init_db(tmp_path / "fresh.db")
    assert get_setting(c, "install_path") is not None

def test_init_db_does_not_overwrite_existing_setting(tmp_path):
    c = init_db(tmp_path / "fresh.db")
    set_setting(c, "install_path", r"C:\custom\path")
    c.close()
    c2 = init_db(tmp_path / "fresh.db")
    assert get_setting(c2, "install_path") == r"C:\custom\path"
```

- [ ] **Step 2: Run the new tests**

```
pytest tests/test_db.py::test_settings_table_created tests/test_db.py::test_get_set_setting tests/test_db.py::test_init_db_seeds_default_install_path tests/test_db.py::test_init_db_does_not_overwrite_existing_setting -v
```

Expected: all 4 PASS (the functions already exist and work correctly).

- [ ] **Step 3: Run the full test suite to confirm no regressions**

```
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```
git add tests/test_db.py
git commit -m "test: add settings table and get/set_setting coverage"
```

---

## Task 2: Remove redundant `conn.commit()` in `db.py`

**Files:**
- Modify: `db.py:158`

Context: `set_setting()` (defined at line 268) already calls `conn.commit()` internally. The call to `conn.commit()` at line 158 of `init_db()` — immediately after `set_setting()` — is therefore redundant.

- [ ] **Step 1: Remove the redundant commit**

In `db.py`, find this block inside `init_db()`:

```python
    # Ensure default install path setting exists
    if get_setting(conn, "install_path") is None:
        set_setting(conn, "install_path", str(Path(r"C:\Fuser\Fuser\Content\Paks\custom_songs")))
    conn.commit()
    return conn
```

Change it to:

```python
    # Ensure default install path setting exists
    if get_setting(conn, "install_path") is None:
        set_setting(conn, "install_path", str(Path(r"C:\Fuser\Fuser\Content\Paks\custom_songs")))
    return conn
```

- [ ] **Step 2: Run tests**

```
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```
git add db.py
git commit -m "fix: remove redundant conn.commit() after set_setting in init_db"
```

---

## Task 3: Add `StatusBar.set_message()` and fix caller in `main_window.py`

**Files:**
- Modify: `gui/status_bar.py`
- Modify: `gui/main_window.py`

- [ ] **Step 1: Add `set_message` to `StatusBar`**

In `gui/status_bar.py`, append this method after `set_idle`:

```python
    def set_message(self, text: str):
        self._lbl.configure(text=text, text_color="white")
        self._bar.grid_remove()
```

- [ ] **Step 2: Fix the Settings Save caller in `main_window.py`**

In `gui/main_window.py`, find this block inside `_open_settings` → `save()`:

```python
        dialog.destroy()
        self.status_bar.set_idle()
        self.status_bar._lbl.configure(text=f"Install path: {new_path}")
```

Replace it with:

```python
        dialog.destroy()
        self.status_bar.set_message(f"Install path: {new_path}")
```

- [ ] **Step 3: Run smoke test**

```
pytest tests/test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```
git add gui/status_bar.py gui/main_window.py
git commit -m "fix: add StatusBar.set_message() and remove private _lbl access from caller"
```

---

## Task 4: Rename `"evenrow"` tag to `"altrow"` in `song_table.py`

**Files:**
- Modify: `gui/song_table.py`

The tag is named `"evenrow"` but is applied to odd-indexed rows (`i % 2 == 1`). Rename it everywhere in the file.

- [ ] **Step 1: Rename in `_build`**

Find:
```python
        self._tree.tag_configure("evenrow", background="#353535")
```
Replace with:
```python
        self._tree.tag_configure("altrow", background="#353535")
```

- [ ] **Step 2: Rename in `load` (tag append and comment)**

Find:
```python
            # Stack tags: evenrow bg first so installed bg overrides it
            tags = []
            if i % 2 == 1:
                tags.append("evenrow")
```
Replace with:
```python
            # Stack tags: altrow bg first so installed bg overrides it
            tags = []
            if i % 2 == 1:
                tags.append("altrow")
```

- [ ] **Step 3: Run smoke test**

```
pytest tests/test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```
git add gui/song_table.py
git commit -m "fix: rename evenrow tag to altrow (was applied to odd-indexed rows)"
```

---

## Task 5: Add batch selection methods to `SongTable`

**Files:**
- Modify: `gui/song_table.py`

- [ ] **Step 1: Add `on_selection_change` parameter to `__init__`**

Find:
```python
    def __init__(self, master, on_select=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
```
Replace with:
```python
    def __init__(self, master, on_select=None, on_selection_change=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._on_selection_change = on_selection_change
```

- [ ] **Step 2: Fire `on_selection_change` from `_on_tree_select`**

Find:
```python
    def _on_tree_select(self, _event):
        sel = self._tree.selection()
        if not sel or not self._on_select:
            return
        song = next((r for r in self._rows if str(r["id"]) == sel[0]), None)
        if song:
            self._on_select(song)
```
Replace with:
```python
    def _on_tree_select(self, _event):
        sel = self._tree.selection()
        if self._on_selection_change:
            self._on_selection_change()
        if not sel or not self._on_select:
            return
        song = next((r for r in self._rows if str(r["id"]) == sel[-1]), None)
        if song:
            self._on_select(song)
```

Note: `sel[-1]` (last-clicked item) is used so that when the table is in extended-select mode and the user single-clicks a row, the detail panel shows that row. In browse mode there is only one item in `sel`, so `sel[-1]` and `sel[0]` are identical.

- [ ] **Step 3: Add the four new public methods**

Insert these methods after `_toggle_sort` and before `_on_tree_select`:

```python
    def set_selectmode(self, mode: str):
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
```

- [ ] **Step 4: Run smoke test**

```
pytest tests/test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add gui/song_table.py
git commit -m "feat: add on_selection_change callback and batch selection methods to SongTable"
```

---

## Task 6: Fix Settings Save in `main_window.py`

**Files:**
- Modify: `gui/main_window.py`

Three fixes in `_open_settings`: inline the unused `entry` variable, add mkdir confirmation dialog, and move `scan_and_sync` to a background thread.

- [ ] **Step 1: Replace the entire `_open_settings` method**

Find the full `_open_settings` method (lines 221–273 in the original file) and replace it with:

```python
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
                self._install_dir = new_path
                scan_and_sync(self._install_dir, self.conn)
                self.after(0, self._refresh_table)
                self.after(0, lambda: self.status_bar.set_message(f"Install path: {new_path}"))
                self.after(0, dialog.destroy)

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
```

- [ ] **Step 2: Run smoke test**

```
pytest tests/test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```
git add gui/main_window.py
git commit -m "fix: Settings Save - background thread, mkdir confirm, remove private _lbl access, inline entry var"
```

---

## Task 7: Add batch mode UI to `main_window.py`

**Files:**
- Modify: `gui/main_window.py`

Add `_batch_mode` state, batch control buttons in the pagination bar, and the enter/exit/selection-change methods. Does not yet wire up the download — that's Task 8.

- [ ] **Step 1: Add `_batch_mode` state to `__init__`**

In `__init__`, after `self._install_dir = ...`, add:

```python
        self._batch_mode: bool = False
```

- [ ] **Step 2: Add batch control buttons to the pagination bar in `_build_ui`**

Find the pagination bar section. It currently ends after `self._next_btn.pack(...)`. Add the batch buttons immediately after:

```python
        # Batch mode controls — only _batch_btn visible initially
        self._download_btn = ctk.CTkButton(
            pbar, text="Download (0)", width=130, fg_color="#1f6e3a",
            hover_color="#28964a", state="disabled",
            command=lambda: self._on_batch_download())
        self._exit_batch_btn = ctk.CTkButton(
            pbar, text="✕ Exit Batch", width=90, fg_color="#555555",
            hover_color="#777777", command=self._exit_batch_mode)
        self._deselect_all_btn = ctk.CTkButton(
            pbar, text="Deselect All", width=90, fg_color="#555555",
            hover_color="#777777", command=lambda: self.song_table.deselect_all())
        self._select_all_btn = ctk.CTkButton(
            pbar, text="Select All", width=80, fg_color="#555555",
            hover_color="#777777", command=lambda: self.song_table.select_all())
        self._batch_btn = ctk.CTkButton(
            pbar, text="Batch", width=70, fg_color="#555555",
            hover_color="#777777", command=self._enter_batch_mode)
        self._batch_btn.pack(side="right", padx=(2, 8))
```

- [ ] **Step 3: Wire `on_selection_change` into the `SongTable` constructor call**

Find:
```python
        self.song_table = SongTable(self, on_select=self._on_select)
```
Replace with:
```python
        self.song_table = SongTable(self, on_select=self._on_select,
                                     on_selection_change=self._on_selection_change)
```

- [ ] **Step 4: Add `_on_selection_change`, `_enter_batch_mode`, `_exit_batch_mode`**

Add these three methods in `main_window.py`, after `_on_select`:

```python
    def _on_selection_change(self):
        count = len(self.song_table.get_selected_songs())
        self._download_btn.configure(
            text=f"Download ({count})",
            state="normal" if count > 0 else "disabled",
        )

    def _enter_batch_mode(self):
        self._batch_mode = True
        self.detail_panel.grid_remove()
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self._batch_btn.pack_forget()
        self._select_all_btn.pack(side="right", padx=2)
        self._deselect_all_btn.pack(side="right", padx=2)
        self._exit_batch_btn.pack(side="right", padx=2)
        self._download_btn.pack(side="right", padx=(2, 8))
        self.song_table.set_selectmode("extended")

    def _exit_batch_mode(self):
        self._batch_mode = False
        self.song_table.deselect_all()
        self.song_table.set_selectmode("browse")
        self.detail_panel.grid()
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=3)
        self._download_btn.pack_forget()
        self._exit_batch_btn.pack_forget()
        self._deselect_all_btn.pack_forget()
        self._select_all_btn.pack_forget()
        self._batch_btn.pack(side="right", padx=(2, 8))
        self._download_btn.configure(text="Download (0)", state="disabled")
```

- [ ] **Step 5: Run smoke test**

```
pytest tests/test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 6: Manual smoke — launch app, click Batch**

```
python app.py
```

Verify:
- "Batch" button appears in the pagination bar (right side)
- Clicking "Batch" hides the detail panel, widens the table, shows Select All / Deselect All / ✕ Exit Batch / Download (0) buttons
- "Download (0)" is disabled
- Clicking "Select All" selects all visible rows; "Download (N)" enables with correct count
- "Deselect All" clears selection; "Download (0)" disables
- "✕ Exit Batch" restores the detail panel and the normal "Batch" button

- [ ] **Step 7: Commit**

```
git add gui/main_window.py
git commit -m "feat: add Batch mode toggle UI with Select All / Deselect All / Download controls"
```

---

## Task 8: Add batch download logic to `main_window.py`

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 1: Add `_on_batch_download`, `_do_batch_download`, `_show_batch_results`**

Add these three methods after `_exit_batch_mode`:

```python
    def _on_batch_download(self):
        songs = self.song_table.get_selected_songs()
        to_download = [s for s in songs if not s.get("pak_path")]
        already_installed = [s for s in songs if s.get("pak_path")]
        if not to_download:
            self._show_batch_results(
                [{"song": s, "status": "skipped", "message": "Already installed"}
                 for s in already_installed]
            )
            return
        self._download_btn.configure(state="disabled", text="Downloading…")
        threading.Thread(
            target=self._do_batch_download,
            args=(to_download, already_installed),
            daemon=True,
        ).start()

    def _do_batch_download(self, to_download: list[dict], already_installed: list[dict]):
        results: list[dict] = [
            {"song": s, "status": "skipped", "message": "Already installed"}
            for s in already_installed
        ]
        n = len(to_download)
        for i, song in enumerate(to_download):
            self.after(0, lambda s=song, idx=i: self.status_bar.set_message(
                f"[{idx + 1}/{n}] Downloading: {s['title']}"))
            result = download(song["link"])
            entry: dict = {"song": song, "result": result}
            if result.status == "ok":
                install_pairs(result, song["id"], song["artist"], self._install_dir, self.conn)
                entry["status"] = "ok"
                entry["message"] = "Installed"
            elif result.status == "manual":
                entry["status"] = "manual"
                entry["message"] = "Manual download required"
            else:
                entry["status"] = "error"
                entry["message"] = result.error_msg or "Unknown error"
            results.append(entry)
        self.after(0, self._refresh_table)
        self.after(0, lambda: self._show_batch_results(results))
        self.after(0, self.status_bar.set_idle)
        self.after(0, self._exit_batch_mode)

    def _show_batch_results(self, results: list[dict]):
        ok_count = sum(1 for r in results if r["status"] == "ok")
        total = len(results)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Batch Download Results")
        dialog.geometry("600x400")
        dialog.transient(self)
        dialog.grab_set()

        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        frame.grid_columnconfigure(0, weight=1)

        summary_color = "#52b788" if ok_count == total else "#f4a261"
        ctk.CTkLabel(
            frame,
            text=f"Batch Download — {ok_count} of {total} succeeded",
            font=ctk.CTkFont(weight="bold", size=14),
            text_color=summary_color,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        result_frame = ctk.CTkScrollableFrame(frame, height=280)
        result_frame.grid(row=1, column=0, sticky="nsew")
        result_frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        for i, entry in enumerate(results):
            song = entry["song"]
            status = entry["status"]
            msg = entry["message"]
            icon = {"ok": "✓", "manual": "⚠", "error": "✗", "skipped": "—"}.get(status, "?")
            color = {"ok": "#52b788", "manual": "#f4a261",
                     "error": "#e76f51", "skipped": "#888888"}.get(status, "white")
            ctk.CTkLabel(
                result_frame, text=icon, text_color=color,
                font=ctk.CTkFont(size=13),
            ).grid(row=i, column=0, padx=(0, 6), sticky="w")
            ctk.CTkLabel(
                result_frame, text=song.get("title", "?"), anchor="w",
            ).grid(row=i, column=1, sticky="w")
            ctk.CTkLabel(
                result_frame, text=msg, text_color="#aaaaaa", anchor="w",
            ).grid(row=i, column=2, sticky="w", padx=(8, 0))

        ctk.CTkButton(
            frame, text="Close", width=80, command=dialog.destroy,
        ).grid(row=2, column=0, pady=(8, 0))
```

- [ ] **Step 2: Run smoke test**

```
pytest tests/test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

```
pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 4: Manual smoke — full batch download flow**

```
python app.py
```

Verify the full flow:
1. Click "Batch" → detail panel hides, batch controls appear
2. Shift-click or use "Select All" to select 2–3 songs that are not yet installed
3. "Download (N)" shows correct count and is enabled
4. Click "Download (N)" → button shows "Downloading…" and disables; status bar shows `[1/N] Downloading: …`
5. After completion: results dialog appears with ✓/⚠/✗ per song; clicking Close exits batch mode and restores the detail panel

Edge cases to check:
- Select only already-installed songs → results dialog shows immediately with "Already installed" for each
- Mix of installed and not-installed → installed shown as "—" skipped in results, others downloaded
- Click "✕ Exit Batch" mid-selection (before clicking Download) → normal mode restores cleanly

- [ ] **Step 5: Commit**

```
git add gui/main_window.py
git commit -m "feat: batch download with sequential download loop and results dialog"
```
