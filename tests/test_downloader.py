import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))
from downloader import detect_host, find_pak_sig_pairs, DownloadResult, download

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
    def fake_gdown(url, output, **kwargs):
        # output is a directory path (trailing slash); create a non-pak file inside it
        out_dir = Path(output.rstrip("/\\"))
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "readme.txt").write_text("not a pak")
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
