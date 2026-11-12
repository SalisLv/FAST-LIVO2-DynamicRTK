#!/usr/bin/env python3
"""Plot fixed/dynamic backend replay outputs and per-observation GNSS weights."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison_dir", type=Path, help="Directory containing fixed/ and dynamic/")
    args = parser.parse_args()
    root = args.comparison_dir
    with (root / "dynamic/debug/gnss_quality.csv").open() as stream:
        rows = [r for r in csv.DictReader(stream) if r["used"] == "1"]
    if not rows:
        parser.error("No GNSS factors were used; check alignment and quality logs")
    fig = plt.figure(figsize=(13, 7), constrained_layout=True)
    grid = fig.add_gridspec(2, 2)
    trajectory = fig.add_subplot(grid[:, 0])
    sigma = fig.add_subplot(grid[0, 1])
    correction = fig.add_subplot(grid[1, 1])
    for mode, color in [("fixed", "#2879b8"), ("dynamic", "#dd7d16")]:
        before = np.loadtxt(root / mode / "TUM/livo_trajectory_before.txt")
        after = np.loadtxt(root / mode / "TUM/opt_trajectory_after.txt")
        trajectory.plot(after[:, 1], after[:, 2], color=color, lw=1.2, label=mode)
        correction.plot(after[:, 0] - after[0, 0], np.linalg.norm(after[:, 1:4] - before[:, 1:4], axis=1),
                        color=color, lw=1, label=mode)
    raw = np.loadtxt(root / "dynamic/TUM/rtk_trajectory_time_aligned.txt")
    colors = {2: ("fixed", "#32964a"), 1: ("float", "#d69c15"), 0: ("single", "#bf3d3d")}
    zero = float(rows[0]["time_sec"])
    for carrier, (label, color) in colors.items():
        subset = [r for r in rows if int(r["carr_soln"]) == carrier]
        if not subset:
            continue
        sigma.scatter([float(r["time_sec"]) - zero for r in subset],
                      [float(r["sigma_x_m"]) for r in subset], s=5, color=color, label=label)
    trajectory.scatter(raw[::10, 1], raw[::10, 2], s=3, color="gray", alpha=0.35, label="GNSS (1/10)")
    trajectory.set(xlabel="East (m)", ylabel="North (m)", title="Optimized trajectories")
    trajectory.axis("equal")
    sigma.set(xlabel="Elapsed time (s)", ylabel="X standard deviation (m)",
              yscale="log", title="Dynamic GNSS noise (larger = less trust)")
    correction.set(xlabel="Elapsed time (s)", ylabel="Position change (m)",
                   title="Correction from each mode's aligned LIVO")
    for axis in [trajectory, sigma, correction]:
        axis.grid(alpha=0.2)
        axis.legend(fontsize=8)
    fig.suptitle("GNSS weighting: same LIVO input; GNSS is not independent ground truth")
    path = root / "gnss_weighting_comparison.png"
    fig.savefig(path, dpi=160)
    print(path)


if __name__ == "__main__":
    main()
