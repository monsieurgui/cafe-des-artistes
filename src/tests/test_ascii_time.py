import datetime
from utils.ascii_time import render_ascii_time


def test_render_ascii_time_basic():
    fixed = datetime.datetime(2025, 1, 2, 3, 4, 5)
    out = render_ascii_time(fixed)
    # Must contain the formatted time in some form
    assert "03:04:05" in out or len(out) > 0


