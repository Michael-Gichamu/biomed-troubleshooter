"""
raw_dump.py — Protocol identification for MS8250D
Just reads raw bytes and displays them. No parsing, no assumptions.
"""
import serial
import serial.tools.list_ports
import time
import sys

PORT = None  # auto-detect, or set manually e.g. "COM3"
BAUD = 2400

def find_cp2102():
    for p in serial.tools.list_ports.comports():
        if p.vid == 0x10C4 and p.pid == 0xEA60:
            return p.device
        if "CP210" in (p.description or "").upper():
            return p.device
    return None

port = PORT or find_cp2102()
if not port:
    print("No CP2102 found")
    sys.exit(1)

print(f"Opening {port} @ {BAUD} baud")
ser = serial.Serial(port, BAUD, timeout=0.5)
ser.dtr = True
ser.rts = False
time.sleep(0.2)
ser.reset_input_buffer()

print(f"Reading bytes for 10 seconds...\n")

all_bytes = bytearray()
start = time.time()
while time.time() - start < 10:
    chunk = ser.read(ser.in_waiting or 1)
    if chunk:
        all_bytes.extend(chunk)
    time.sleep(0.05)

ser.close()
total = len(all_bytes)
print(f"Captured {total} bytes in 10 seconds")
print(f"Effective rate: ~{total} bytes/10s = ~{total * 8 / 10:.0f} bits/s")
print()

# ── Hex + ASCII dump ────────────────────────────────────────
print("=== HEX DUMP ===")
for off in range(0, min(total, 512), 16):
    row = all_bytes[off:off + 16]
    hx = " ".join(f"{b:02X}" for b in row)
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
    print(f"  {off:04X}: {hx:<48s}  |{asc}|")

# ── Try to find repeating patterns ─────────────────────────
print("\n=== PATTERN ANALYSIS ===")

# Check for common line endings (ASCII protocols)
for marker, name in [(b"\r\n", "CRLF"), (b"\n", "LF"), (b"\r", "CR")]:
    parts = all_bytes.split(marker)
    if len(parts) > 3:
        lengths = [len(p) for p in parts if len(p) > 0]
        if lengths:
            avg = sum(lengths) / len(lengths)
            print(f"  Split by {name}: {len(parts)-1} segments, "
                  f"avg length {avg:.1f} bytes")
            print(f"  First 3 segments:")
            for j, seg in enumerate(parts[:3]):
                if seg:
                    print(f"    [{j}] ({len(seg):2d}B): {seg.hex()}  "
                          f"|{''.join(chr(b) if 32<=b<127 else '.' for b in seg)}|")

# Check for FS9721-style sync (high nibble = position)
fs9721_count = 0
for i in range(total - 14):
    if all((all_bytes[i+j] & 0xF0) == ((j+1) << 4) for j in range(14)):
        fs9721_count += 1
if fs9721_count:
    print(f"  FS9721 frames (14-byte): {fs9721_count} found")
else:
    print(f"  FS9721 frames (14-byte): NONE")

# Try to detect fixed-length repeating frames
print(f"\n  Byte value histogram (top 15):")
from collections import Counter
freq = Counter(all_bytes)
for val, cnt in freq.most_common(15):
    bar = "#" * min(cnt, 40)
    print(f"    0x{val:02X} ({chr(val) if 32<=val<127 else '.'}): "
          f"{cnt:4d}  {bar}")

# Auto-detect frame length by looking for repeating byte at regular intervals
print(f"\n  Candidate frame lengths:")
for flen in range(10, 50):
    if total < flen * 3:
        continue
    matches = 0
    checks = 0
    for i in range(0, total - flen * 2, flen):
        checks += 1
        # Check if first byte repeats at frame boundaries
        if all_bytes[i] == all_bytes[i + flen]:
            matches += 1
    if checks > 0 and matches / checks > 0.7:
        print(f"    {flen} bytes  ({matches}/{checks} = "
              f"{matches/checks:.0%} alignment)")

print(f"\n=== RAW BYTES (first 200) ===")
print(" ".join(f"{b:02X}" for b in all_bytes[:200]))

print(f"\n=== DONE ===")
print(f"Copy everything above and share it so I can identify the protocol.")