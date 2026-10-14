"""Checks for signal_tools.curves_to_dataframe. Run with: python "Test apps/test_export_curves.py" """
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from generictools import signal_tools  # noqa: E402


def make_curve(name, f_start, f_end, n_points):
    x = np.geomspace(f_start, f_end, n_points)
    curve = signal_tools.Curve((x, 20 * np.log10(x)))
    curve.set_name_base(name)
    return curve


def test_single_curve_without_ppo_is_unmodified():
    curve = make_curve("A", 20, 20000, 50)
    df = signal_tools.curves_to_dataframe([curve])
    assert list(df.columns) == ["A"]
    assert df.index.name == "Frequency"
    np.testing.assert_array_equal(df.index, curve.get_x())
    np.testing.assert_array_equal(df["A"], curve.get_y())


def test_ppo_zero_means_no_interpolation():
    curve = make_curve("A", 20, 20000, 50)
    df = signal_tools.curves_to_dataframe([curve], ppo=0)
    np.testing.assert_array_equal(df.index, curve.get_x())


def test_single_curve_with_ppo_matches_interpolate_to_ppo():
    curve = make_curve("A", 20, 20000, 500)
    df = signal_tools.curves_to_dataframe([curve], ppo=12, must_include_freq=1000)
    x_intp, y_intp = signal_tools.interpolate_to_ppo(*curve.get_xy(), 12, must_include_freq=1000)
    np.testing.assert_array_equal(df.index, x_intp)
    np.testing.assert_allclose(df["A"], y_intp)
    assert not df["A"].isna().any()


def test_shared_grid_has_no_gaps():
    a, b = make_curve("A", 20, 20000, 50), make_curve("B", 20, 20000, 50)
    df = signal_tools.curves_to_dataframe([a, b])
    assert df.shape == (50, 2)
    assert not df.isna().any().any()


def test_different_ranges_with_ppo_share_grid_and_leave_blanks_outside_range():
    a, b = make_curve("A", 20, 20000, 500), make_curve("B", 100, 5000, 500)
    df = signal_tools.curves_to_dataframe([a, b], ppo=12, must_include_freq=1000)
    assert list(df.columns) == ["A", "B"]
    assert not df["A"].isna().any()
    inside = (df.index >= 100) & (df.index <= 5000)
    assert not df.loc[inside, "B"].isna().any()
    assert df.loc[~inside, "B"].isna().all()
    assert 1000 in df.index


def test_mismatched_grids_without_ppo_use_union_of_frequencies():
    a, b = make_curve("A", 20, 20000, 50), make_curve("B", 30, 10000, 40)
    df = signal_tools.curves_to_dataframe([a, b])
    expected_index = np.union1d(a.get_x(), b.get_x())
    np.testing.assert_array_equal(df.index, expected_index)
    assert df["A"].notna().sum() == 50
    assert df["B"].notna().sum() == 40


def test_column_order_follows_input_and_duplicate_names_are_kept():
    a, b, c = make_curve("Z", 20, 20000, 50), make_curve("A", 20, 20000, 50), make_curve("Z", 20, 20000, 50)
    df = signal_tools.curves_to_dataframe([a, b, c])
    assert list(df.columns) == ["Z", "A", "Z"]


def test_empty_list_raises():
    try:
        signal_tools.curves_to_dataframe([])
    except ValueError:
        return
    raise AssertionError("ValueError expected")


if __name__ == "__main__":
    tests = [(name, func) for name, func in globals().items() if name.startswith("test_") and callable(func)]
    for name, func in tests:
        func()
        print("passed:", name)
    print(f"All {len(tests)} tests passed.")
