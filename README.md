# Fuser Custom Song Manager

A local desktop app for browsing, downloading, and installing custom songs for the game **Fuser** (Harmonix, EGS version).

Pulls song listings from:
- **fucuco.online** — large mainstream catalog backed by a public Google Sheet (3 tabs: main database, VGM, new submissions)
- **fusersoundlab.com** — indie and community releases

Songs install as `.pak` + `.sig` file pairs into your Fuser `Content/Paks` directory, organised by artist.

---

## Requirements

- Python 3.11 or newer
- Fuser installed at `C:\Fuser\` (the fixed game path this app targets)
- Internet connection for fetching catalogs and downloading songs

---

## Setup

```powershell
cd C:\Users\sgibb\Documents\ClaudeCode\fuser-custom-tool
pip install -r requirements.txt
```

---

## Launch

```powershell
python app.py
```

The app opens a ~1200×800 dark-themed window. On first launch the catalog is empty — click **Refresh Sources** to fetch all listings.

---

## Usage

### Refreshing the catalog

Click **Refresh Sources** (top-right). The app fetches all three fucuco Google Sheet tabs and scrapes fusersoundlab.com, then caches everything locally in `~/.fuser_manager/catalog.db`. This takes a few seconds depending on your connection. The "Updated YYYY-MM-DD" label confirms when the cache was last refreshed.

You don't need to refresh every session — the local cache persists between launches.

### Browsing and filtering

| Control | What it does |
|---------|-------------|
| **Search box** | Live filter by artist, title, or creator (modder) name |
| **Definitive only** | Show only songs marked as Definitive (complete with all features) |
| **Source dropdown** | Filter by data source: `fucuco_main`, `fucuco_vgm`, `fucuco_new`, `fusersoundlab` |
| **Genre** | Partial-match filter on genre |
| **BPM min / max** | Filter by BPM range |
| **Column headers** | Click any header to sort ascending; click again to sort descending |

Installed songs appear with a **✓** in the Status column and a green row tint.
Definitive songs display a **★** in the Definitive column.

### Downloading and installing a song

1. Click a row to select it — full metadata appears in the right panel.
2. Click **Download & Install**.
3. The status bar at the bottom shows progress. When complete it reads "Installed: {title}" briefly, then resets.
4. The row turns green and the ✓ badge appears.

Songs are installed to:
```
C:\Fuser\Fuser\Content\Paks\custom_songs\<Artist Name>\<filename>.pak
C:\Fuser\Fuser\Content\Paks\custom_songs\<Artist Name>\<filename>.sig
```

### Manual downloads

Some songs link to **OneDrive, MediaFire, MEGA, or other hosts**. These cannot be downloaded automatically. When you click Download & Install on such a song, the detail panel shows:

> Manual download required. Click the link above to open in browser.

Click the blue link to open the host page in your browser, download the `.pak` and `.sig` files manually, and place them in the appropriate artist folder under `C:\Fuser\Fuser\Content\Paks\custom_songs\`.

Google Drive downloads that succeed but contain unexpected file types also fall back to this notice.

### Uninstalling a song

Select an installed song (green row) and click **Uninstall** (red button). This deletes the `.pak` and `.sig` files from disk and removes the artist folder if it becomes empty. The row reverts to uninstalled state immediately.

### Definitive status explained

Each song has a **Complete** field and a **DE Status** field from the source spreadsheet. The app derives **is_definitive** as follows:

- Complete = `D` (marked Definitive by submitter) → Definitive
- DE Status = `Eligible` and Complete = `C` → Definitive
- DE Status blank, Complete = `C`, no notes → Definitive
- Anything else → not Definitive

The **Notes** field in the detail panel explains why a `C`-rated song isn't yet Definitive (e.g. "Few wrong notes on minor lead").

---

## File locations

| Path | Purpose |
|------|---------|
| `~/.fuser_manager/catalog.db` | Local SQLite cache of all song listings and install records |
| `~/.fuser_manager/staging/` | Temporary download area — cleaned up automatically after install |
| `C:\Fuser\Fuser\Content\Paks\custom_songs\` | Where songs are installed |

---

## Running tests

```powershell
pytest tests\ -v
```

44 tests covering the database layer, source fetchers, downloader, and installer.
