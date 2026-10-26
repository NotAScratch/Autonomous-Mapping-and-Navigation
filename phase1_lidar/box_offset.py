#!/usr/bin/env python3
"""
Phase 1, step 5: measure the lidar's front offset with one flat box.

Experiment:
  1. Empty space in front of the robot. Capture:   read_scan.py 10 && mv scan.csv empty.csv
  2. Put a flat box dead ahead, its face square to the robot (use a tape measure
     from the robot's front bumper to the box face, e.g. 1.00 m). Capture:
                                                   read_scan.py 10 && mv scan.csv box.csv
  3. python3 box_offset.py empty.csv box.csv [tape_m]

How it works:
  - Background subtraction (as in Entry 2): keep box-scan points more than
    CHANGE_M closer than the empty scan at the same angle. That is the box.
  - Keep the biggest angular cluster of those points.
  - Two estimates of "straight ahead":
      a) the middle of the box's angular extent (needs the box centred), and
      b) the direction of the face's perpendicular, from a straight-line fit
         (needs the face square to the robot).
    If a) and b) agree within a degree or two, the setup was good.
"""
import csv
import math
import sys

CHANGE_M = 0.15   # point must be this much closer than the background
MAX_GAP_DEG = 3   # points further apart than this start a new cluster


def load(path):
    pts = []
    for r in csv.DictReader(open(path)):
        d = float(r["distance_m"])
        if d > 0:
            pts.append((float(r["angle_deg"]), d))
    return pts


def background(pts):
    """Median distance per 1-degree slice of the empty scan."""
    slices = {}
    for a, d in pts:
        slices.setdefault(int(a) % 360, []).append(d)
    return {b: sorted(v)[len(v) // 2] for b, v in slices.items()}


def clusters(angles):
    """Group sorted angles into runs, joining across 360 -> 0."""
    angles = sorted(angles)
    groups = [[angles[0]]]
    for a in angles[1:]:
        if a - groups[-1][-1] > MAX_GAP_DEG:
            groups.append([])
        groups[-1].append(a)
    if len(groups) > 1 and groups[0][0] + 360 - groups[-1][-1] <= MAX_GAP_DEG:
        groups[0] = groups.pop() + groups[0]
    return groups


def circ_mid(a, b):
    return (a + ((b - a) % 360) / 2) % 360


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    bg = background(load(sys.argv[1]))
    box = load(sys.argv[2])
    tape = float(sys.argv[3]) if len(sys.argv) > 3 else None

    new = [(a, d) for a, d in box if (b := int(a) % 360) in bg and d < bg[b] - CHANGE_M]
    if not new:
        sys.exit("no new object found: is the box in view and the empty scan really empty?")
    by_angle = dict(new)
    group = max(clusters([a for a, _ in new]), key=len)
    pts = [(a, by_angle[a]) for a in group]
    print(f"box cluster: {len(pts)} points, lidar {group[0]:.1f}..{group[-1]:.1f} deg")

    # a) middle of the angular extent
    mid = circ_mid(group[0], group[-1])

    # b) perpendicular of a least-squares line through the face (x, y in the lidar's own frame)
    xy = [(d * math.cos(math.radians(a)), d * math.sin(math.radians(a))) for a, d in pts]
    mx = sum(x for x, _ in xy) / len(xy)
    my = sum(y for _, y in xy) / len(xy)
    sxx = sum((x - mx) ** 2 for x, _ in xy)
    syy = sum((y - my) ** 2 for _, y in xy)
    sxy = sum((x - mx) * (y - my) for x, y in xy)
    face_dir = 0.5 * math.atan2(2 * sxy, sxx - syy)          # direction along the face
    nx, ny = -math.sin(face_dir), math.cos(face_dir)         # face normal
    dist = mx * nx + my * ny                                 # signed distance to the line
    if dist < 0:
        nx, ny, dist = -nx, -ny, -dist
    perp = math.degrees(math.atan2(ny, nx)) % 360
    rms = math.sqrt(sum(((x - mx) * nx + (y - my) * ny) ** 2 for x, y in xy) / len(xy))

    width = math.hypot(xy[0][0] - xy[-1][0], xy[0][1] - xy[-1][1])
    print(f"a) centre of box        : lidar {mid:6.2f} deg")
    print(f"b) face perpendicular   : lidar {perp:6.2f} deg   (line fit rms {rms * 1000:.1f} mm)")
    diff = (perp - mid + 180) % 360 - 180
    print(f"   a) - b) disagree by  : {abs(diff):.2f} deg" + ("   <- check the box is centred and square" if abs(diff) > 2 else ""))
    print(f"box face width seen     : {width:.3f} m")
    print(f"lidar -> face distance  : {dist:.3f} m (perpendicular)")
    if tape is not None:
        print(f"tape (bumper -> face)   : {tape:.3f} m  => lidar sits {dist - tape:.3f} m behind the bumper")
    front = (mid + diff / 2) % 360 if abs(diff) <= 2 else mid
    print(f"\nfront offset            : {front:.1f} deg   (Entry 2 estimate: ~303 deg)")
    print(f"use: angle_robot = {front:.1f} - angle_lidar")


if __name__ == "__main__":
    main()
