#!/usr/bin/env python3
"""
Phase 1, step 1: say hello to the lidar.

Sends two commands over the serial port and decodes the replies by hand:
  - GET_DEVICE_INFO  (0xA5 0x90): model number, firmware, hardware, serial number
  - GET_HEALTH       (0xA5 0x92): is the lidar OK or reporting an error?

YDLIDAR protocol basics
-----------------------
Every command is 2 bytes: 0xA5 (start flag) + a command byte.
Every reply starts with a 7-byte header:
    A5 5A | 4 bytes: length (low 30 bits) + mode (high 2 bits) | 1 byte: type
followed by `length` bytes of payload.

Run on the Jetson:  python3 ydlidar_probe.py [/dev/rplidar] [512000]
"""
import struct
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/rplidar"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 512000

CMD_STOP = 0x65
CMD_GET_DEVICE_INFO = 0x90
CMD_GET_HEALTH = 0x92


def send(ser, cmd):
    ser.write(bytes([0xA5, cmd]))


def read_reply(ser, timeout=1.0):
    """Scan the incoming bytes for the A5 5A header, then read the payload."""
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        buf += ser.read(1)
        if buf[-2:] == b"\xA5\x5A":
            header = ser.read(5)
            length_and_mode, = struct.unpack("<I", header[:4])
            length = length_and_mode & 0x3FFFFFFF
            mode = length_and_mode >> 30
            reply_type = header[4]
            payload = ser.read(length)
            return reply_type, mode, payload
    raise TimeoutError(f"No reply header. Bytes seen: {buf[-32:].hex(' ')}")


def main():
    print(f"Opening {PORT} at {BAUD} baud")
    with serial.Serial(PORT, BAUD, timeout=0.5) as ser:
        # Make sure the lidar is not already streaming scan data, then flush.
        send(ser, CMD_STOP)
        time.sleep(0.1)
        ser.reset_input_buffer()

        send(ser, CMD_GET_DEVICE_INFO)
        rtype, mode, p = read_reply(ser)
        print(f"\nDEVICE INFO (type=0x{rtype:02X}, {len(p)} bytes): {p.hex(' ')}")
        model = p[0]
        fw_major, fw_minor = p[2], p[1]
        hw = p[3]
        serial_no = "".join(str(b) for b in p[4:20])
        print(f"  model code : {model}")
        print(f"  firmware   : {fw_major}.{fw_minor}")
        print(f"  hardware   : {hw}")
        print(f"  serial     : {serial_no}")

        send(ser, CMD_GET_HEALTH)
        rtype, mode, p = read_reply(ser)
        status = p[0]
        error_code, = struct.unpack("<H", p[1:3])
        print(f"\nHEALTH (type=0x{rtype:02X}): {p.hex(' ')}")
        print(f"  status     : {status} ({'OK' if status == 0 else 'WARNING/ERROR'})")
        print(f"  error code : {error_code}")


if __name__ == "__main__":
    main()
