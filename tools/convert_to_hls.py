#!/usr/bin/env python3
"""
HLS Conversion Script for 360 Virtual Experience

Converts MP4 video files to HLS (HTTP Live Streaming) format using FFmpeg.
This enables efficient streaming with smaller segment files instead of
large monolithic MP4 files.

Usage:
    python convert_to_hls.py

Requirements:
    - FFmpeg installed and available in PATH
"""

import os
import subprocess
import sys
import time
from pathlib import Path


# Configuration
BASE_DIR = Path(__file__).parent.parent
VIDEOS_DIR = BASE_DIR / "videos"
HLS_OUTPUT_DIR = VIDEOS_DIR / "hls"

# Videos to convert (filename without extension -> output folder name)
VIDEOS = [
    "flight_line_1",
    "flight_line_2",
    "flight_line_3",
]

# HLS settings
SEGMENT_DURATION = 10  # seconds per segment
HLS_FLAGS = "independent_segments"  # Each segment can be decoded independently


def check_ffmpeg():
    """Verify FFmpeg is installed and accessible."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            check=True
        )
        version_line = result.stdout.split('\n')[0]
        print(f"[OK] Found {version_line}")
        return True
    except FileNotFoundError:
        print("[ERROR] FFmpeg not found. Please install FFmpeg and add it to PATH.")
        print("  Download from: https://ffmpeg.org/download.html")
        return False
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg error: {e}")
        return False


def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def format_time(seconds):
    """Format seconds as HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_size(bytes_size):
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def convert_video(video_name):
    """Convert a single video to HLS format."""
    input_path = VIDEOS_DIR / f"{video_name}.mp4"
    output_dir = HLS_OUTPUT_DIR / video_name
    playlist_path = output_dir / "playlist.m3u8"
    segment_pattern = output_dir / "segment_%03d.ts"

    # Check input exists
    if not input_path.exists():
        print(f"  [ERROR] Input file not found: {input_path}")
        return False

    # Get video info
    file_size = input_path.stat().st_size
    duration = get_video_duration(input_path)

    print(f"  Input: {input_path}")
    print(f"  Size: {format_size(file_size)}")
    if duration:
        print(f"  Duration: {format_time(duration)}")
        expected_segments = int(duration / SEGMENT_DURATION) + 1
        print(f"  Expected segments: ~{expected_segments}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build FFmpeg command
    # Using stream copy (no re-encoding) for speed
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-c:v", "copy",              # Copy video codec (no re-encode)
        "-c:a", "copy",              # Copy audio codec (no re-encode)
        "-hls_time", str(SEGMENT_DURATION),
        "-hls_list_size", "0",       # Include all segments in playlist
        "-hls_flags", HLS_FLAGS,
        "-hls_segment_filename", str(segment_pattern),
        "-f", "hls",
        "-y",                        # Overwrite output
        str(playlist_path)
    ]

    print(f"  Output: {output_dir}")
    print(f"  Converting... (this may take a few minutes)")

    start_time = time.time()

    try:
        # Run FFmpeg with progress output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for completion
        stdout, stderr = process.communicate()

        elapsed = time.time() - start_time

        if process.returncode != 0:
            print(f"  [ERROR] FFmpeg error (code {process.returncode}):")
            # Show last few lines of error
            error_lines = stderr.strip().split('\n')[-5:]
            for line in error_lines:
                print(f"    {line}")
            return False

        # Verify output
        if not playlist_path.exists():
            print(f"  [ERROR] Playlist not created: {playlist_path}")
            return False

        # Count segments
        segments = list(output_dir.glob("segment_*.ts"))
        total_size = sum(s.stat().st_size for s in segments)

        print(f"  [OK] Conversion complete in {format_time(elapsed)}")
        print(f"  [OK] Created {len(segments)} segments ({format_size(total_size)})")

        return True

    except Exception as e:
        print(f"  [ERROR] Error during conversion: {e}")
        return False


def verify_output():
    """Verify all HLS outputs were created correctly."""
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)

    all_good = True

    for video_name in VIDEOS:
        output_dir = HLS_OUTPUT_DIR / video_name
        playlist_path = output_dir / "playlist.m3u8"

        print(f"\n{video_name}:")

        if not playlist_path.exists():
            print(f"  [ERROR] Missing playlist: {playlist_path}")
            all_good = False
            continue

        segments = list(output_dir.glob("segment_*.ts"))
        if not segments:
            print(f"  [ERROR] No segments found in {output_dir}")
            all_good = False
            continue

        total_size = sum(s.stat().st_size for s in segments)
        print(f"  [OK] Playlist: {playlist_path}")
        print(f"  [OK] Segments: {len(segments)} files ({format_size(total_size)})")

        # Check playlist content
        with open(playlist_path, 'r') as f:
            content = f.read()
            if '#EXTM3U' not in content:
                print(f"  [ERROR] Invalid playlist format")
                all_good = False
            else:
                print(f"  [OK] Valid HLS playlist")

    return all_good


def main():
    print("="*60)
    print("HLS CONVERSION SCRIPT")
    print("360 Virtual Experience")
    print("="*60)

    # Check FFmpeg
    print("\nChecking FFmpeg installation...")
    if not check_ffmpeg():
        sys.exit(1)

    # Check input videos exist
    print("\nChecking input videos...")
    missing = []
    for video_name in VIDEOS:
        input_path = VIDEOS_DIR / f"{video_name}.mp4"
        if input_path.exists():
            size = format_size(input_path.stat().st_size)
            print(f"  [OK] {video_name}.mp4 ({size})")
        else:
            print(f"  [ERROR] {video_name}.mp4 NOT FOUND")
            missing.append(video_name)

    if missing:
        print(f"\nError: {len(missing)} video(s) not found. Aborting.")
        sys.exit(1)

    # Create HLS output directory
    print(f"\nCreating output directory: {HLS_OUTPUT_DIR}")
    HLS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Convert each video
    print("\n" + "="*60)
    print("CONVERTING VIDEOS")
    print("="*60)

    results = []
    total_start = time.time()

    for i, video_name in enumerate(VIDEOS, 1):
        print(f"\n[{i}/{len(VIDEOS)}] Converting {video_name}...")
        success = convert_video(video_name)
        results.append((video_name, success))

    total_elapsed = time.time() - total_start

    # Summary
    print("\n" + "="*60)
    print("CONVERSION SUMMARY")
    print("="*60)
    print(f"Total time: {format_time(total_elapsed)}")

    succeeded = sum(1 for _, s in results if s)
    failed = len(results) - succeeded

    print(f"Succeeded: {succeeded}/{len(results)}")
    if failed > 0:
        print(f"Failed: {failed}")
        for name, success in results:
            if not success:
                print(f"  - {name}")

    # Verify output
    if succeeded > 0:
        all_verified = verify_output()

        if all_verified and succeeded == len(results):
            print("\n" + "="*60)
            print("[OK] ALL CONVERSIONS SUCCESSFUL")
            print("="*60)
            print("\nNext steps:")
            print("1. Update server.py with HLS MIME types")
            print("2. Update multi-view.html to use HLS.js")
            print("3. Test playback")
            return 0

    if failed > 0:
        print("\n" + "="*60)
        print("[FAILED] SOME CONVERSIONS FAILED")
        print("="*60)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
