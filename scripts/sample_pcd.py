#!/usr/bin/env python3
"""Write a regularly sampled binary PCD without loading the whole map into RAM."""

import argparse
from pathlib import Path
from typing import Tuple

import numpy as np


def sample_pcd(source: Path, destination: Path, every: int) -> Tuple[int, int]:
    with source.open("rb") as src:
        header = []
        while True:
            line = src.readline()
            if not line:
                raise ValueError("PCD header has no DATA line")
            header.append(line)
            if line.startswith(b"DATA "):
                break

        fields = {}
        for line in header:
            parts = line.split()
            if parts:
                fields[parts[0]] = parts[1:]
        if fields.get(b"DATA") != [b"binary"]:
            raise ValueError("only uncompressed binary PCD files are supported")
        if len(fields.get(b"POINTS", [])) != 1:
            raise ValueError("PCD header has no POINTS count")
        point_count = int(fields[b"POINTS"][0])
        sizes = [int(value) for value in fields[b"SIZE"]]
        counts = [int(value) for value in fields.get(b"COUNT", [b"1"] * len(sizes))]
        if len(sizes) != len(counts):
            raise ValueError("SIZE and COUNT fields do not match")
        point_size = sum(size * count for size, count in zip(sizes, counts))
        if point_size <= 0:
            raise ValueError("invalid point size")
        expected_size = src.tell() + point_count * point_size
        if source.stat().st_size != expected_size:
            raise ValueError("PCD payload size does not match the header")

        output_count = (point_count + every - 1) // every
        replacement = {
            b"WIDTH": str(output_count).encode(),
            b"HEIGHT": b"1",
            b"POINTS": str(output_count).encode(),
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as dst:
            for line in header:
                parts = line.split(maxsplit=1)
                if parts and parts[0] in replacement:
                    line = parts[0] + b" " + replacement[parts[0]] + b"\n"
                dst.write(line)

            points_read = 0
            chunk_points = 250_000
            while points_read < point_count:
                count = min(chunk_points, point_count - points_read)
                data = src.read(count * point_size)
                points = np.frombuffer(data, dtype=f"V{point_size}")
                first = (-points_read) % every
                dst.write(points[first::every].tobytes())
                points_read += count
    return point_count, output_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--every", type=int, default=20, help="retain one point in every N (default: 20)")
    args = parser.parse_args()
    if args.every < 1:
        parser.error("--every must be at least 1")
    source_count, output_count = sample_pcd(args.source, args.destination, args.every)
    print(f"{args.destination}: {output_count:,} / {source_count:,} points")


if __name__ == "__main__":
    main()
