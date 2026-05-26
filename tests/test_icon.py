import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_icon_file_exists():
    icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
    assert icon_path.exists(), "assets/icon.ico not found — run: python assets/generate_icon.py"


def test_icon_is_valid_ico():
    from PIL import Image
    icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
    if not icon_path.exists():
        import pytest
        pytest.skip("icon not generated yet")
    img = Image.open(icon_path)
    assert img.format == "ICO"
