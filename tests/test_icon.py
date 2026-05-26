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


def test_icon_contains_three_sizes():
    import struct, pytest
    icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
    if not icon_path.exists():
        pytest.skip("icon not generated yet")
    with open(icon_path, "rb") as f:
        data = f.read()
    # ICO header: 2 bytes reserved, 2 bytes type (1=ICO), 2 bytes count
    _reserved, _ico_type, num_images = struct.unpack("<HHH", data[:6])
    assert num_images == 3, f"ICO should contain 16/32/48px, got {num_images} image(s)"
