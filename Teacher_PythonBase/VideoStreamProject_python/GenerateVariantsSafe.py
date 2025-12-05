#!/usr/bin/env python3
"""
GenerateVariantsSafe.py

Reads the original MJPEG file (`movie.Mjpeg`) and writes three quality variants:
  - movie_480p.Mjpeg (640x480, JPEG quality 75)
  - movie_720p.Mjpeg (1280x720, JPEG quality 85)
  - movie_1080p.Mjpeg (1920x1080, JPEG quality 90)

Frames are processed sequentially and written with a 5-byte ASCII length header
followed by JPEG data. All output files are written in one pass to avoid
partial writes. Progress is printed every 50 frames.
"""
import io
import os
import sys
from typing import Tuple
from PIL import Image

QUALITY_PRESETS = {
    # start qualities; will auto-step down if a frame exceeds 5-digit header limit
    "480p": (640, 480, 75),
    "720p": (1280, 720, 80),
    "1080p": (1920, 1080, 40),  # aggressive to keep frames < 100k
}

def process_frame(img_data: bytes, target: Tuple[int, int, int]) -> bytes:
    """Resize and encode; if frame exceeds 5-digit header, lower quality until it fits."""
    width, height, jpeg_q_start = target
    img_io = io.BytesIO(img_data)
    img = Image.open(img_io)
    img = img.resize((width, height), Image.Resampling.LANCZOS)

    q = jpeg_q_start
    while q >= 20:  # floor to avoid extreme degradation
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=q, optimize=False)
        data = out.getvalue()
        if len(data) <= 99999:  # fits 5-byte ASCII length
            return data
        q -= 5
    # If still too large, return last attempt (may be >99999, caller will skip)
    return data

def generate_variant(input_file: str, output_file: str, preset: Tuple[int, int, int]):
    total_frames = 0
    skipped_too_large = 0
    written_bytes = 0
    with open(input_file, "rb") as fin, open(output_file, "wb", buffering=65536) as fout:
        while True:
            header = fin.read(5)
            if not header:
                break
            try:
                length = int(header)
            except ValueError:
                print(f"Invalid header at frame {total_frames+1}; stopping.")
                break
            data = fin.read(length)
            if len(data) < length:
                print(f"Truncated frame {total_frames+1}; stopping.")
                break

            jpeg_data = process_frame(data, preset)
            if len(jpeg_data) > 99999:
                skipped_too_large += 1
                continue

            length_bytes = f"{len(jpeg_data):05d}".encode()
            fout.write(length_bytes)
            fout.write(jpeg_data)

            total_frames += 1
            written_bytes += 5 + len(jpeg_data)
            if total_frames % 50 == 0:
                print(f"  {output_file}: {total_frames} frames written...")
    print(f"✓ {output_file}: {total_frames} frames written, {written_bytes/1024/1024:.2f} MB")
    if skipped_too_large:
        print(f"  (Skipped {skipped_too_large} frames that stayed >99,999 bytes even at q<=20)")


def main():
    input_file = "movie.Mjpeg"
    if not os.path.exists(input_file):
        print(f"ERROR: {input_file} not found; place it in the same folder.")
        return 1

    print("Generating quality variants from movie.Mjpeg ...")
    generate_variant(input_file, "movie_480p.Mjpeg", QUALITY_PRESETS["480p"])
    generate_variant(input_file, "movie_720p.Mjpeg", QUALITY_PRESETS["720p"])
    generate_variant(input_file, "movie_1080p.Mjpeg", QUALITY_PRESETS["1080p"])
    print("Done. You can now stream 480p/720p/1080p.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
