#!/usr/bin/env python3
"""
Phase 1, step 2: read raw scans from the YDLIDAR (no driver, no ROS).

What happens:
  1. Send START_SCAN (0xA5 0x60). The motor spins up and the lidar starts
     streaming packets forever.
  2. Decode each packet by hand and check its checksum.
  3. Group packets into full 360-degree revolutions.
  4. Save one revolution to CSV, draw it as a picture, print some stats.
  5. Send STOP (0xA5 0x65).

Scan packet layout (all little-endian), "no intensity" mode:
    offset size  field
    0      2     PH   packet header, always 0x55AA (bytes AA 55)
    2      1     CT   bit0 = 1 -> this packet starts a new revolution
                      bits1-7 = scan frequency info (only in start packets)
    3      1     LSN  number of samples in this packet
    4      2     FSA  angle of first sample: (FSA >> 1) / 64 degrees
    6      2     LSA  angle of last sample:  (LSA >> 1) / 64 degrees
    8      2     CS   checksum: XOR of every 16-bit word in the packet
    10     2*LSN samples, one uint16 distance each

Run on the Jetson:  python3 read_scan.py [revolutions] [port] [baud]
"""
import csv
import math
import struct
import sys
import time

import serial

REVS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
PORT = sys.argv[2] if len(sys.argv) > 2 else "/dev/rplidar"
BAUD = int(sys.argv[3]) if len(sys.argv) > 3 else 512000

# The YDLIDAR TOF protocol sends distance as a raw uint16. We store the raw value
# and convert with DIST_SCALE (mm per unit). See the README for how it was checked.
DIST_SCALE = 1.0


def read_exact(ser, n):
    data = ser.read(n)
    if len(data) != n:
        raise TimeoutError(f"wanted {n} bytes, got {len(data)}")
    return data


def packets(ser):
    """Yield (is_start, ct, angles_deg, raw_distances) for every valid packet."""
    bad = 0
    while True:
        # 1. Find the packet header AA 55
        if read_exact(ser, 1) != b"\xAA":
            continue
        if read_exact(ser, 1) != b"\x55":
            continue
        head = read_exact(ser, 8)
        ct, lsn, fsa, lsa, cs = struct.unpack("<BBHHH", head)
        raw = read_exact(ser, 2 * lsn)
        samples = struct.unpack(f"<{lsn}H", raw)

        # 2. Checksum: XOR of PH, (CT|LSN<<8), FSA, LSA and every sample word
        check = 0x55AA ^ (ct | (lsn << 8)) ^ fsa ^ lsa
        for s in samples:
            check ^= s
        if check != cs or not (fsa & 1) or not (lsa & 1):
            bad += 1
            continue

        # 3. Angles: spread the samples evenly between first and last angle
        a_first = (fsa >> 1) / 64.0
        a_last = (lsa >> 1) / 64.0
        span = (a_last - a_first) % 360.0
        step = span / (lsn - 1) if lsn > 1 else 0.0
        angles = [(a_first + i * step) % 360.0 for i in range(lsn)]
        yield bool(ct & 1), ct, angles, samples, bad


def main():
    print(f"Opening {PORT} at {BAUD} baud, collecting {REVS} revolutions")
    # Long timeout: after START_SCAN the lidar is silent while its motor spins up.
    with serial.Serial(PORT, BAUD, timeout=5.0) as ser:
        ser.write(b"\xA5\x65")  # stop, in case it was left running
        time.sleep(0.1)
        ser.reset_input_buffer()

        ser.write(b"\xA5\x60")  # START_SCAN
        hdr = read_exact(ser, 7)
        print(f"start reply header: {hdr.hex(' ')}  (A5 5A = OK)")
        t_start = time.time()
        ser.read(1)  # blocks until the first scan byte arrives
        print(f"motor spin-up        : {time.time() - t_start:.2f} s of silence before data")

        revs = []          # list of revolutions, each a list of (angle, raw)
        current = None
        rev_times = []
        total_bad = 0
        try:
            for is_start, ct, angles, samples, bad in packets(ser):
                total_bad = bad
                if is_start:
                    if current:
                        revs.append(current)
                        rev_times.append(time.time())
                    current = []
                    if len(revs) >= REVS + 1:  # +1: first revolution is often partial
                        break
                    continue  # start packets carry no real measurements
                if current is not None:
                    current.extend(zip(angles, samples))
        finally:
            ser.write(b"\xA5\x65")  # STOP: motor spins down

    revs = revs[1:]  # drop the first, possibly partial revolution
    hz = (len(rev_times) - 2) / (rev_times[-1] - rev_times[1]) if len(rev_times) > 2 else float("nan")
    sizes = [len(r) for r in revs]
    print(f"\nrevolutions          : {len(revs)}")
    print(f"scan rate            : {hz:.2f} Hz")
    print(f"points / revolution  : min {min(sizes)}, max {max(sizes)}")
    print(f"angular resolution   : {360 / (sum(sizes) / len(sizes)):.3f} deg")
    print(f"bad packets dropped  : {total_bad}")

    scan = revs[-1]
    valid = [(a, d) for a, d in scan if d > 0]
    raw_vals = [d for _, d in valid]
    print(f"valid points (d>0)   : {len(valid)} / {len(scan)}")
    print(f"raw distance min/max : {min(raw_vals)} / {max(raw_vals)}")

    # A few sample directions, so we can check against a tape measure.
    for target in (0, 90, 180, 270):
        a, d = min(valid, key=lambda p: min(abs(p[0] - target), 360 - abs(p[0] - target)))
        print(f"  ~{target:3d} deg -> angle {a:7.2f}, raw {d}, = {d * DIST_SCALE / 1000:.3f} m")

    with open("scan.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["angle_deg", "raw", "distance_m", "x_m", "y_m"])
        for a, d in scan:
            r = d * DIST_SCALE / 1000.0
            w.writerow([f"{a:.3f}", d, f"{r:.3f}",
                        f"{r * math.cos(math.radians(a)):.3f}",
                        f"{r * math.sin(math.radians(a)):.3f}"])
    print("\nsaved scan.csv")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        xs = [d * DIST_SCALE / 1000 * math.cos(math.radians(a)) for a, d in valid]
        ys = [d * DIST_SCALE / 1000 * math.sin(math.radians(a)) for a, d in valid]
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.scatter(xs, ys, s=2)
        ax.plot(0, 0, "r^", markersize=10, label="lidar")
        ax.plot([0, 0.4], [0, 0], "r-", label="0 deg direction")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title("One raw lidar revolution (our own decoder)")
        ax.legend()
        fig.savefig("scan.png", dpi=120, bbox_inches="tight")
        print("saved scan.png")
    except ImportError:
        print("matplotlib not installed, skipped plot")


if __name__ == "__main__":
    main()
