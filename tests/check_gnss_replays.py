#!/usr/bin/env python3
"""Check clean, outlier, invalid-fix and dropout backend replay artifacts.

Requires fixed/, dynamic/, outlier-fixed/, outlier-dynamic/, invalid/, dropout/.
The outlier runs must differ from their clean inputs by one ~20 m GNSS jump;
the dropout input must remove an interval of observations. No truth is assumed.
"""
import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path


def trajectory(path):
    rows = [[float(x) for x in line.split()] for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")]
    assert rows and all(len(row) == 8 and all(math.isfinite(x) for x in row) for row in rows), path
    assert all(a[0] < b[0] for a, b in zip(rows, rows[1:])), path
    assert all(abs(sum(x*x for x in row[4:8])-1.0) < 1e-4 for row in rows), path
    return rows


def distances(a, b):
    assert len(a) == len(b)
    assert all(abs(x[0]-y[0]) < 1e-6 for x, y in zip(a, b))
    return [math.sqrt(sum((x[i]-y[i])**2 for i in range(1, 4))) for x, y in zip(a, b)]


def quality(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison_dir", type=Path)
    args = parser.parse_args()
    root = args.comparison_dir
    modes = ["fixed", "dynamic", "outlier-fixed", "outlier-dynamic", "invalid", "dropout"]
    results = {m: trajectory(root / m / "TUM/opt_trajectory_after.txt") for m in modes}
    rows = quality(root / "dynamic/debug/gnss_quality.csv")
    active = [r for r in rows if r["used"] == "1"]
    assert active, "Dynamic mode added no GNSS factors"
    assert len({r["keyframe"] for r in active}) == len(active), "Duplicate factors on one keyframe"
    for r in active:
        assert 0.0 < float(r["robust_weight"]) <= 1.0
        assert abs(float(r["time_difference_sec"])) <= 0.06 + 1e-8
        assert all(math.isfinite(float(r[k])) and float(r[k]) > 0.0
                   for k in ["sigma_x_m", "sigma_y_m", "sigma_z_m", "information_x", "information_y", "information_z"])
    groups = {}
    for carrier in sorted({r["carr_soln"] for r in active}):
        subset = [r for r in active if r["carr_soln"] == carrier]
        groups[carrier] = {"used": len(subset),
                           "median_sigma_x_m": statistics.median(float(r["sigma_x_m"]) for r in subset),
                           "median_information_x": statistics.median(float(r["information_x"]) for r in subset)}
    assert groups["2"]["median_information_x"] > groups["1"]["median_information_x"] > groups["0"]["median_information_x"]
    fixed_shift = max(distances(results["fixed"], results["outlier-fixed"]))
    dynamic_shift = max(distances(results["dynamic"], results["outlier-dynamic"]))
    assert dynamic_shift < fixed_shift * 0.2, (fixed_shift, dynamic_shift)
    invalid_before = trajectory(root / "invalid/TUM/livo_trajectory_before.txt")
    invalid_shift = max(distances(invalid_before, results["invalid"]))
    assert invalid_shift < 2e-6, "All-invalid GNSS changed the LIVO trajectory"
    dropout_rows = quality(root / "dropout/debug/gnss_quality.csv")
    raw_times = sorted(float(r["time_sec"]) for r in dropout_rows)
    gap = max(zip(raw_times, raw_times[1:]), key=lambda pair: pair[1]-pair[0])
    assert gap[1] - gap[0] > 5.0, "Dropout fixture has no long gap"
    used_times = {float(r["time_sec"]) for r in dropout_rows if r["used"] == "1"}
    assert not any(gap[0] < t < gap[1] for t in used_times), "A GNSS factor was invented inside the outage"
    assert len(results["dropout"]) == len(results["dynamic"])
    report = {"scope": "Backend replay of identical LIVO input; not absolute accuracy against ground truth",
              "poses_per_mode": {m: len(results[m]) for m in modes},
              "gnss_observations": len(rows), "gnss_factors_used": len(active),
              "associations": dict(Counter(r["association"] for r in rows)),
              "carrier_groups": groups,
              "injected_jump_max_trajectory_change_m": {"fixed": fixed_shift, "dynamic": dynamic_shift},
              "all_invalid_max_trajectory_change_m": invalid_shift,
              "dropout_gap_sec": gap[1]-gap[0],
              "checks_passed": True}
    path = root / "validation_report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
