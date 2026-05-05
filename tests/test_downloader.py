import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from downloader import detect_host, find_pak_sig_pairs, DownloadResult

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
