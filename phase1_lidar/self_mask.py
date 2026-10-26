#!/usr/bin/env python3
"""
Phase 1, step 4: find which lidar angles hit the robot's own body.

Idea: the robot's chassis is always the same distance from the lidar, whatever
room it is in. So a 1-degree slice whose *closest* point is nearer than
NEAR_M in EVERY scan we give it is blocked by the robot itself.

Output: self_mask.json, a list of [start_deg, end_deg] ranges in raw lidar
angles (clockwise, 0 = lidar's zero mark). Later code drops points inside them.

Run:  python3 self_mask.py scan1.csv [scan2.csv ...]
"""
import csv
import json
import sys

NEAR_M = 0.30   # anything closer than this is "on the robot"
MIN_RUN = 2     # ignore blocked runs narrower than this many degrees (noise)
PAD = 1         # widen each range by this many degrees on both sides
MAX_GAP = 5     # join ranges separated by a gap this small (slices with no return)


def nearest_per_degree(path):
    near = [None] * 360
    for r in csv.DictReader(open(path)):
        d = float(r["distance_m"])
        if d <= 0:               # 0 = no return
            continue
        b = int(float(r["angle_deg"])) % 360
        if near[b] is None or d < near[b]:
            near[b] = d
    return near


def runs(flags):
    """Contiguous True runs on a 360-degree circle, as (start, end) inclusive."""
    if all(flags):
        return [(0, 359)]
    start = flags.index(False) + 1  # begin just after a gap so no run is cut at 0
    out, cur = [], None
    for i in range(360):
        b = (start + i) % 360
        if flags[b] and cur is None:
            cur = b
        elif not flags[b] and cur is not None:
            out.append((cur, (b - 1) % 360))
            cur = None
    if cur is not None:
        out.append((cur, (start - 1) % 360))
    return out


def main():
    paths = sys.argv[1:]
    if not paths:
        sys.exit(__doc__)
    scans = [nearest_per_degree(p) for p in paths]
    blocked = [all(s[b] is not None and s[b] < NEAR_M for s in scans) for b in range(360)]

    # Slices with no return at all break a run; bridge small gaps.
    for _ in range(MAX_GAP):
        blocked = [blocked[b] or (blocked[b - 1] and any(blocked[(b + k) % 360]
                   for k in range(1, MAX_GAP + 1))) for b in range(360)]

    ranges = []
    for a, b in runs(blocked):
        width = (b - a) % 360 + 1
        if width < MIN_RUN:
            continue
        ranges.append([(a - PAD) % 360, (b + 1 + PAD) % 360])

    print(f"{len(paths)} scan(s), slices always closer than {NEAR_M} m:")
    for a, b in ranges:
        width = (b - a) % 360
        print(f"  lidar {a:3d}..{b:3d} deg ({width:3d} deg wide)"
              f"  -> robot {(303 - a + 180) % 360 - 180:+4d}..{(303 - b + 180) % 360 - 180:+4d} deg")
    json.dump({"near_m": NEAR_M, "ranges_deg": ranges}, open("self_mask.json", "w"), indent=1)
    print("saved self_mask.json")


if __name__ == "__main__":
    main()
