import sys
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))
from downloader import (
    detect_host, find_pak_sig_pairs, _extract_archives, _archive_suffix,
    _flatten_into, DownloadResult, download,
)

def test_detect_host_gdrive_file():
    assert detect_host("https://drive.google.com/file/d/abc123") == "gdrive"

def test_detect_host_gdrive_folder():
    assert detect_host("https://drive.google.com/drive/folders/xyz") == "gdrive"

def test_detect_host_onedrive():
    assert detect_host("https://1drv.ms/u/abc") == "onedrive"

def test_detect_host_other():
    assert detect_host("https://example.com/file") == "other"

def test_find_pairs_matched(tmp_path):
    (tmp_path / "song.pak").write_text("")
    (tmp_path / "song.sig").write_text("")
    (tmp_path / "readme.txt").write_text("")
    pairs = find_pak_sig_pairs(tmp_path)
    assert len(pairs) == 1
    assert pairs[0][0].name == "song.pak"
    assert pairs[0][1].name == "song.sig"

def test_find_pairs_missing_sig(tmp_path):
    (tmp_path / "song.pak").write_text("")
    pairs = find_pak_sig_pairs(tmp_path)
    assert len(pairs) == 1
    assert pairs[0][0].name == "song.pak"
    assert pairs[0][1] is None

def test_find_pairs_empty_dir(tmp_path):
    assert find_pak_sig_pairs(tmp_path) == []

def test_find_pairs_multiple(tmp_path):
    for name in ["a", "b"]:
        (tmp_path / f"{name}.pak").write_text("")
        (tmp_path / f"{name}.sig").write_text("")
    assert len(find_pak_sig_pairs(tmp_path)) == 2

def test_download_result_fields():
    r = DownloadResult(status="ok", pairs=[], error_msg=None, raw_url="https://x.com")
    assert r.status == "ok"
    assert r.raw_url == "https://x.com"

def test_download_gdrive_error_returns_error(tmp_path):
    with patch("downloader.STAGING_DIR", tmp_path), \
         patch("downloader.gdown.download", side_effect=Exception("quota exceeded")):
        result = download("https://drive.google.com/file/d/abc")
    assert result.status == "error"
    assert "quota exceeded" in result.error_msg

def test_download_gdrive_no_pak_returns_manual(tmp_path):
    def fake_gdown(url, **kwargs):
        # Create a non-pak file in a temp dir — gdown returns the path
        out_file = tmp_path / "readme.txt"
        out_file.write_text("not a pak")
        return str(out_file)
    with patch("downloader.STAGING_DIR", tmp_path), \
         patch("downloader.gdown.download", side_effect=fake_gdown):
        result = download("https://drive.google.com/file/d/abc")
    assert result.status == "manual"
    assert result.error_msg == "No .pak/.sig found in download"

def test_download_non_gdrive_dead_link_returns_error():
    with patch("downloader.requests.head") as mock_head:
        mock_head.return_value.status_code = 404
        result = download("https://1drv.ms/u/abc")
    assert result.status == "error"
    assert "404" in result.error_msg

def test_download_non_gdrive_live_returns_manual():
    with patch("downloader.requests.head") as mock_head:
        mock_head.return_value.status_code = 200
        result = download("https://1drv.ms/u/abc")
    assert result.status == "manual"
    assert result.error_msg is None


# ── Archive extraction helpers ───────────────────────────────────────

def test_archive_suffix_recognises_zip():
    assert _archive_suffix(Path("x.zip")) == ".zip"

def test_archive_suffix_recognises_rar():
    assert _archive_suffix(Path("x.rar")) == ".rar"

def test_archive_suffix_recognises_7z():
    assert _archive_suffix(Path("x.7z")) == ".7z"

def test_archive_suffix_recognises_tar_gz():
    assert _archive_suffix(Path("x.tar.gz")) == ".tar.gz"

def test_archive_suffix_returns_none_for_plain_file():
    assert _archive_suffix(Path("readme.txt")) is None

def test_flatten_into_moves_files(tmp_path):
    src = tmp_path / "sub"
    dst = tmp_path / "out"
    src.mkdir(); dst.mkdir()
    (src / "a.pak").write_text("")
    (src / "b.sig").write_text("")
    _flatten_into(src, dst)
    assert (dst / "a.pak").exists()
    assert (dst / "b.sig").exists()
    assert not (src / "a.pak").exists()

def test_flatten_into_handles_collision(tmp_path):
    src = tmp_path / "sub"
    dst = tmp_path / "out"
    src.mkdir(); dst.mkdir()
    (src / "a.pak").write_text("")
    (dst / "a.pak").write_text("original")
    _flatten_into(src, dst)
    assert (dst / "a_1.pak").exists()

def test_extract_archives_zip_with_pak(tmp_path):
    """A zip containing .pak + .sig should be extracted and pairs found."""
    # Create a zip with a .pak and .sig inside
    (tmp_path / "song.pak").write_text("pak")
    (tmp_path / "song.sig").write_text("sig")
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(tmp_path / "song.pak", "song.pak")
        zf.write(tmp_path / "song.sig", "song.sig")
    # Remove the originals so only the zip remains
    (tmp_path / "song.pak").unlink()
    (tmp_path / "song.sig").unlink()

    _extract_archives(tmp_path)
    pairs = find_pak_sig_pairs(tmp_path)
    assert len(pairs) == 1
    assert pairs[0][0].name == "song.pak"
    assert pairs[0][1].name == "song.sig"
    assert not zip_path.exists()  # archive removed after extraction

def test_extract_archives_zip_no_pak(tmp_path):
    """A zip without .pak/.sig should leave no pairs, archive removed."""
    (tmp_path / "readme.txt").write_text("hello")
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(tmp_path / "readme.txt", "readme.txt")
    (tmp_path / "readme.txt").unlink()

    _extract_archives(tmp_path)
    pairs = find_pak_sig_pairs(tmp_path)
    assert pairs == []
    assert not zip_path.exists()  # archive removed anyway

def test_extract_archives_no_archive_is_noop(tmp_path):
    """Directory with no archives should be untouched."""
    (tmp_path / "readme.txt").write_text("")
    _extract_archives(tmp_path)
    assert (tmp_path / "readme.txt").exists()


# ── End-to-end: download with zip ─────────────────────────────────────

def test_download_gdrive_zip(tmp_path):
    """Mock gdown.download to return a zip file; verify extraction + pair discovery."""
    # Create a zip file with .pak + .sig
    (tmp_path / "song.pak").write_text("pak")
    (tmp_path / "song.sig").write_text("sig")
    zip_path = tmp_path / "song.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(tmp_path / "song.pak", "song.pak")
        zf.write(tmp_path / "song.sig", "song.sig")
    (tmp_path / "song.pak").unlink()
    (tmp_path / "song.sig").unlink()

    def fake_gdown(url, **kwargs):
        return str(zip_path)

    with patch("downloader.STAGING_DIR", tmp_path), \
         patch("downloader.gdown.download", side_effect=fake_gdown):
        result = download("https://drive.google.com/file/d/abc")
    assert result.status == "ok"
    assert len(result.pairs) == 1
    assert result.pairs[0][0].name == "song.pak"
    assert result.pairs[0][1].name == "song.sig"
