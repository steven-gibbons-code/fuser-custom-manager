import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.filter_bar import FilterBar


def test_default_filters(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    f = bar.get_filters()
    assert f["search"] == ""
    assert f["order_by"] == "s.artist"
    assert f.get("descending") is None or f.get("descending") is False
    assert "source" not in f
    assert "quality" not in f
    assert "installed" not in f


def test_search_emits_filters_changed(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    with qtbot.waitSignal(bar.filters_changed, timeout=1000) as blocker:
        bar._search.setText("Nirvana")
    assert blocker.args[0]["search"] == "Nirvana"


def test_source_filter_included_when_set(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._source.setCurrentText("fucuco_main")
    f = bar.get_filters()
    assert f["source"] == "fucuco_main"


def test_source_filter_excluded_when_all(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._source.setCurrentText("All Sources")
    f = bar.get_filters()
    assert "source" not in f


def test_sort_newest_first(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._sort.setCurrentText("Newest First")
    f = bar.get_filters()
    assert f["order_by"] == "s.submit_date"
    assert f["descending"] is True


def test_bpm_range(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._bpm_min.setText("100")
    bar._bpm_max.setText("140")
    f = bar.get_filters()
    assert f["bpm_min"] == 100
    assert f["bpm_max"] == 140


def test_invalid_bpm_ignored(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._bpm_min.setText("abc")
    f = bar.get_filters()
    assert "bpm_min" not in f


def test_clear_resets_all_fields(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._search.setText("test")
    bar._source.setCurrentText("fucuco_main")
    bar._bpm_min.setText("100")
    bar.clear()
    f = bar.get_filters()
    assert f["search"] == ""
    assert "source" not in f
    assert "bpm_min" not in f
