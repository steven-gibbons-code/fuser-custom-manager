# Fuser Custom Song Manager

A local desktop app for browsing, downloading, and installing custom songs for the game **Fuser** (Harmonix).

Pulls song listings from:
- **fucuco.online** — large mainstream catalog backed by a public Google Sheet
- **fusersoundlab.com** — indie and community releases

Songs install as `.pak` + `.sig` file pairs into your Fuser `Content/Paks` directory, organized by artist.

![App screenshot](docs/screenshot.png)

---

## Features

| Feature | Description |
|---------|-------------|
| **Live search** | Filter by artist, title, or modder name as you type |
| **Quality tiers** | Color-coded badges — purple for Official, platinum for Definitive, gold for Complete |
| **Source filter** | Filter by catalog source (`fucuco_main`, `fucuco_vgm`, `fusersoundlab`) |
| **Genre & BPM filters** | Narrow down by genre text or BPM range |
| **Sort** | By artist, newest first, or BPM ascending/descending |
| **Pagination** | 100 songs per page with prev/next navigation |
| **Auto-download** | Google Drive links download via `gdown` with archive extraction (zip/rar/7z) |
| **Manual install** | Browse for `.pak`/`.sig` files to mark manually-downloaded songs as installed |
| **Uninstall** | Removes files and cleans up empty artist directories |
| **Configurable install path** | Settings dialog to change where songs are installed (no longer hardcoded) |
| **Clear Filters** | One-click reset of all filters and search |
| **Status tracking** | Installed songs show a green row tint and ✓ badge |

---

## Quick Start

### Option 1: Install as a package (recommended)

```powershell
git clone https://github.com/steven-gibbons-code/fuser-custom-manager.git
cd fuser-custom-manager
pip install -e .
fuser-manager
```

### Option 2: Run from source

```powershell
git clone https://github.com/steven-gibbons-code/fuser-custom-manager.git
cd fuser-custom-manager
pip install -r requirements.txt
python app.py
```

---

## Requirements

- **Python 3.11 or newer**
- **Fuser** installed on your system (the app can install songs to any directory you choose via Settings)
- **Internet connection** for fetching catalogs and downloading songs

---

## First Launch

1. The app opens a ~1200×800 dark-themed window
2. Click **Refresh Sources** (top-right) to fetch the song catalog
3. The catalog is cached locally in `~/.fuser_manager/catalog.db` — subsequent launches are instant
4. Click **Settings** (top-right) if you need to change the install directory
5. Browse songs, filter, and click **Download & Install** on any song

---

## Configuration

### Install directory

Click **Settings** in the top toolbar to choose where `.pak`/`.sig` files are installed. The default is:

```
C:\Fuser\Fuser\Content\Paks\custom_songs\
```

You can change this to any path — the app will create the directory if it doesn't exist.

### User data

| Path | Purpose |
|------|---------|
| `~/.fuser_manager/catalog.db` | Local SQLite cache of all song listings and install records |
| `~/.fuser_manager/staging/` | Temporary download area — cleaned up after install |

---

## Manual Downloads

Some songs link to **OneDrive, MediaFire, MEGA**, or other hosts. These cannot be downloaded automatically by the app. When you click **Download & Install** on such a song, the detail panel shows:

> Manual download required. Click the link above to open in browser.

Download the `.pak` and `.sig` files manually, then click **Mark as Installed (browse .pak…)** to register them in the app (files are copied, not moved — your originals are preserved).

---

## Quality Tiers

| Tier | Color | Meaning |
|------|-------|---------|
| **Off** | Purple | Official DLC or base-game content |
| **Def** | Platinum | Definitive — complete with all features |
| **Cmp** | Gold | Complete song with minor notes |
| *(blank)* | Gray | Other / in-progress |

Derived from the sheet's `Complete`, `DE Status`, and `download_type` fields at catalog refresh time.

---

## Development

### Running tests

```powershell
pip install -r dev-requirements.txt
pytest tests\ -v
```

92 tests covering the database layer, source fetchers, downloader, installer, and GUI imports.

### Project structure

```
fuser-custom-manager/
    app.py                  # Entry point
    db.py                   # SQLite catalog & install tracking
    downloader.py           # Automatic downloads (gdrive, archive extraction)
    installer.py            # File placement, uninstall, disk scan
    sources/
        fucuco.py           # Google Sheets CSV fetcher
        fusersoundlab.py    # HTML scraper
    gui/
        main_window.py      # Top-level window, filters, settings
        song_table.py       # Sortable, paginated, zebra-striped table
        detail_panel.py     # Song metadata, download & install buttons
        status_bar.py       # Progress, error, and status messages
    tests/                  # pytest test suite
    docs/
        CHANGELOG.md        # Release changelog
        dev/                # Planning docs and design specs
```

---

## License

This project is open source under the [MIT License](LICENSE).

---

## Contributing

Issues and pull requests are welcome! Check the [changelog](docs/CHANGELOG.md) for recent changes and `docs/dev/` for planning docs.