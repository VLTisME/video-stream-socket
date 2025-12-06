#!/usr/bin/env python3
"""
GenerateVariantsSafe.py - OPTIMIZED VERSION

Reads the original MJPEG file (`movie.Mjpeg`) and writes three quality variants:
  - movie_480p.Mjpeg (640x480, JPEG quality 50)  - Low quality, fast
  - movie_720p.Mjpeg (640x480, JPEG quality 75)  - Medium quality
  - movie_1080p.Mjpeg (640x480, JPEG quality 95) - High quality, detailed

ALL output files are 640x480 resolution (same display size)
but different JPEG compression levels for actual quality difference.
This allows:
- Fixed window display in client
- Real quality differences visible (not just zoom)
- Fast playback (no client-side resize needed)
"""
import io
import os
import sys
from typing import Tuple
from PIL import Image

QUALITY_PRESETS = {
    # All output to 640x480, but EXTREME quality difference for maximum visibility
    # (quality, optimize_flag)
    "480p": (640, 480, 8, False),    # HEAVILY COMPRESSED, pixelated but slightly recognizable
    "720p": (640, 480, 15, False),   # Low quality, noticeable compression
    "1080p": (640, 480, 100, True),  # MAXIMUM quality, ultra sharp and crystal clear
}

def process_frame(img_data: bytes, target: Tuple[int, int, int, bool]) -> bytes:
    """Resize to fixed 640x480 and encode with specified quality."""
    width, height, jpeg_quality, optimize = target
    img_io = io.BytesIO(img_data)
    img = Image.open(img_io)
    
    # Resize to fixed size (fast BILINEAR is good enough here)
    img = img.resize((width, height), Image.Resampling.BILINEAR)

    # Use specified quality
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=jpeg_quality, optimize=optimize)
    data = out.getvalue()
    
    # If frame is too large, reduce quality
    q = jpeg_quality
    while len(data) > 99999 and q > 20:
        q -= 5
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=q, optimize=optimize)
        data = out.getvalue()
    
    return data

def generate_variant(input_file: str, output_file: str, preset: Tuple[int, int, int, bool]):
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
