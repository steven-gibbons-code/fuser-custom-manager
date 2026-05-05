import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import gdown
import patoolib
import requests

STAGING_DIR = Path.home() / ".fuser_manager" / "staging"

# Archive extensions we can handle
_ZIP_EXTS = {".zip"}
_PATOOL_EXTS = {".rar", ".7z", ".tar", ".gz", ".tgz", ".tar.gz", ".bz2", ".tar.bz2", ".xz", ".tar.xz"}
_ARCHIVE_EXTS = _ZIP_EXTS | _PATOOL_EXTS


@dataclass
class DownloadResult:
    status:    str            # 'ok' | 'error' | 'manual'
    pairs:     list           # [(pak_path: Path, sig_path: Path | None), ...]
    error_msg: str | None
    raw_url:   str
    work_dir:  Path | None = None   # staging dir to clean up after install (ok only)


def detect_host(url: str) -> str:
    if not url:
        return "other"
    u = url.lower()
    if "drive.google.com" in u:
        return "gdrive"
    if "1drv.ms" in u or "onedrive.live.com" in u:
        return "onedrive"
    if "mediafire.com" in u:
        return "mediafire"
    if "mega.nz" in u or "mega.co.nz" in u:
        return "mega"
    return "other"


def find_pak_sig_pairs(directory: Path) -> list[tuple]:
    pairs = []
    for pak in sorted(directory.rglob("*.pak")):
        sig = pak.with_suffix(".sig")
        pairs.append((pak, sig if sig.exists() else None))
    return pairs


def _extract_archives(work_dir: Path) -> None:
    """Extract any archive files found in work_dir (recursively).

    Supports .zip (stdlib zipfile), .rar, .7z, .tar.*, and other formats
    via patool. Nested archives (archives inside archives) are handled
    by repeated passes until no new archives remain.
    """
    MAX_PASSES = 5
    for _ in range(MAX_PASSES):
        extracted = False
        for path in sorted(work_dir.rglob("*")):
            if not path.is_file():
                continue
            suffix = _archive_suffix(path)
            if suffix is None:
                continue

            extract_dir = work_dir / path.stem
            extract_dir.mkdir(parents=True, exist_ok=True)

            try:
                if suffix in _ZIP_EXTS:
                    with zipfile.ZipFile(path, "r") as zf:
                        zf.extractall(str(extract_dir))
                else:
                    patoolib.extract_archive(
                        str(path), outdir=str(extract_dir), verbosity=-1
                    )
                # Move extracted contents up to work_dir, then remove the
                # now-empty extract_dir.
                _flatten_into(extract_dir, work_dir)
                shutil.rmtree(extract_dir, ignore_errors=True)
            except Exception:
                # If extraction fails, clean up the empty extract dir and
                # continue — don't let a corrupt archive block the whole pass.
                shutil.rmtree(extract_dir, ignore_errors=True)
                continue

            # Remove the original archive file
            path.unlink(missing_ok=True)
            extracted = True

        if not extracted:
            break


def _archive_suffix(path: Path) -> str | None:
    """Return the archive suffix for *path*, or None if it's not an archive."""
    # Check two-part suffixes first (e.g. .tar.gz) before .gz alone
    if path.suffixes and len(path.suffixes) >= 2:
        combined = "".join(s.lower() for s in path.suffixes[-2:])
        if combined in {".tar.gz", ".tar.bz2", ".tar.xz", ".tgz"}:
            return combined
    lower = path.suffix.lower()
    if lower in _ZIP_EXTS | _PATOOL_EXTS:
        return lower
    return None


def _flatten_into(src: Path, dst: Path) -> None:
    """Move all files and dirs from *src* into *dst* (non-recursive, one level)."""
    for child in src.iterdir():
        dest = dst / child.name
        # If a name collision occurs, append a suffix to keep both
        if dest.exists():
            stem, ext = child.stem, child.suffix
            counter = 1
            while dest.exists():
                dest = dst / f"{stem}_{counter}{ext}"
                counter += 1
        shutil.move(str(child), str(dest))


def download(url: str, progress_cb: Callable | None = None) -> DownloadResult:
    host = detect_host(url)
    if host != "gdrive":
        return _non_gdrive(url)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(dir=STAGING_DIR))
    return _gdrive(url, work_dir)


def _gdrive(url: str, work_dir: Path) -> DownloadResult:
    try:
        is_folder = "drive/folders" in url.lower()
        if is_folder:
            gdown.download_folder(url, output=str(work_dir), quiet=False, use_cookies=False)
        else:
            output_file = gdown.download(url, quiet=False, fuzzy=True)
            if output_file:
                src = Path(output_file)
                shutil.move(str(src), str(work_dir / src.name))
    except Exception as exc:
        _rm(work_dir)
        return DownloadResult(status="error", pairs=[], error_msg=str(exc), raw_url=url)

    pairs = find_pak_sig_pairs(work_dir)
    if not pairs:
        # No direct .pak/.sig — maybe gdrive returned a compressed archive
        _extract_archives(work_dir)
        pairs = find_pak_sig_pairs(work_dir)

    if not pairs:
        _rm(work_dir)
        return DownloadResult(
            status="manual", pairs=[], error_msg="No .pak/.sig found in download", raw_url=url
        )
    return DownloadResult(status="ok", pairs=pairs, error_msg=None, raw_url=url, work_dir=work_dir)


def _non_gdrive(url: str) -> DownloadResult:
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        if resp.status_code >= 400:
            return DownloadResult(
                status="error", pairs=[], error_msg=f"HTTP {resp.status_code}", raw_url=url
            )
    except requests.RequestException as exc:
        return DownloadResult(status="error", pairs=[], error_msg=str(exc), raw_url=url)
    return DownloadResult(status="manual", pairs=[], error_msg=None, raw_url=url)


def _rm(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)