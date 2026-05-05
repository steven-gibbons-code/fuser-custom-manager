import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import gdown
import requests

STAGING_DIR = Path.home() / ".fuser_manager" / "staging"


@dataclass
class DownloadResult:
    status:    str            # 'ok' | 'error' | 'manual'
    pairs:     list           # [(pak_path: Path, sig_path: Path | None), ...]
    error_msg: str | None
    raw_url:   str


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


def download(url: str, progress_cb: Callable | None = None) -> DownloadResult:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(dir=STAGING_DIR))
    host = detect_host(url)

    if host == "gdrive":
        return _gdrive(url, work_dir)

    # Non-gdrive: check liveness, then return manual prompt
    return _non_gdrive(url, work_dir)


def _gdrive(url: str, work_dir: Path) -> DownloadResult:
    try:
        is_folder = "drive/folders" in url.lower()
        if is_folder:
            gdown.download_folder(url, output=str(work_dir), quiet=False, use_cookies=False)
        else:
            gdown.download(url, str(work_dir / "download"), quiet=False, fuzzy=True)
    except Exception as exc:
        _rm(work_dir)
        return DownloadResult(status="error", pairs=[], error_msg=str(exc), raw_url=url)

    pairs = find_pak_sig_pairs(work_dir)
    if not pairs:
        _rm(work_dir)
        return DownloadResult(
            status="manual", pairs=[], error_msg="No .pak/.sig found in download", raw_url=url
        )
    return DownloadResult(status="ok", pairs=pairs, error_msg=None, raw_url=url)


def _non_gdrive(url: str, work_dir: Path) -> DownloadResult:
    _rm(work_dir)
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
