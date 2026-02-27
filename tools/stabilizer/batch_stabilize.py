#!/usr/bin/env python3
"""
Batch 360 Video Stabilizer

Process multiple Insta360 INSV files for stabilization.
Supports folder input, parallel processing, and various output options.
"""

import argparse
import sys
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Optional
import time

from insta360_parser import is_insta360_file
from stabilizer import stabilize_video, StabilizationConfig


def find_insv_files(input_path: str, recursive: bool = False) -> List[Path]:
    """Find all INSV files in a path"""
    input_path = Path(input_path)

    if input_path.is_file():
        if input_path.suffix.lower() == '.insv' and is_insta360_file(str(input_path)):
            return [input_path]
        else:
            print(f"Warning: {input_path} is not a valid Insta360 file")
            return []

    # Directory
    pattern = '**/*.insv' if recursive else '*.insv'
    files = []

    for f in input_path.glob(pattern):
        if is_insta360_file(str(f)):
            files.append(f)

    # Also check uppercase extension
    pattern_upper = '**/*.INSV' if recursive else '*.INSV'
    for f in input_path.glob(pattern_upper):
        if is_insta360_file(str(f)) and f not in files:
            files.append(f)

    return sorted(files)


def process_single_file(args: tuple) -> tuple:
    """
    Process a single file. Used for parallel processing.

    Args:
        args: Tuple of (input_path, output_path, config)

    Returns:
        Tuple of (input_path, success, message)
    """
    input_path, output_path, config = args

    try:
        success = stabilize_video(str(input_path), str(output_path), config)
        if success:
            return (input_path, True, "OK")
        else:
            return (input_path, False, "Stabilization failed")
    except Exception as e:
        return (input_path, False, str(e))


def main():
    parser = argparse.ArgumentParser(
        description='Batch 360 Video Stabilizer for Insta360 footage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Stabilize a single file
  python batch_stabilize.py video.insv -o stabilized.mp4

  # Stabilize all INSV files in a folder
  python batch_stabilize.py ./input_folder -o ./output_folder

  # Process with custom settings
  python batch_stabilize.py ./videos --smoothness 0.9 --resolution 1920x960

  # Parallel processing (4 workers)
  python batch_stabilize.py ./videos -o ./output -j 4
        """
    )

    parser.add_argument(
        'input',
        help='Input INSV file or folder containing INSV files'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output file or folder (default: same as input with _stabilized suffix)'
    )

    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Search for INSV files recursively in subfolders'
    )

    parser.add_argument(
        '-j', '--jobs',
        type=int,
        default=1,
        help='Number of parallel jobs (default: 1)'
    )

    parser.add_argument(
        '--smoothness',
        type=float,
        default=0.95,
        help='Smoothing factor 0-1 (default: 0.95, higher = smoother)'
    )

    parser.add_argument(
        '--horizon-lock',
        action='store_true',
        default=True,
        help='Lock horizon level (default: on)'
    )

    parser.add_argument(
        '--no-horizon-lock',
        action='store_true',
        help='Disable horizon locking'
    )

    parser.add_argument(
        '--resolution',
        default='3840x1920',
        help='Output resolution WxH (default: 3840x1920)'
    )

    parser.add_argument(
        '--fps',
        type=float,
        default=30.0,
        help='Output frame rate (default: 30)'
    )

    parser.add_argument(
        '--codec',
        default='libx264',
        help='Video codec (default: libx264)'
    )

    parser.add_argument(
        '--crf',
        type=int,
        default=18,
        help='Quality CRF value, lower = better (default: 18)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without actually processing'
    )

    parser.add_argument(
        '--extract-gyro-only',
        action='store_true',
        help='Only extract gyro data to CSV, do not stabilize'
    )

    args = parser.parse_args()

    # Find input files
    print("Scanning for Insta360 files...")
    input_files = find_insv_files(args.input, args.recursive)

    if not input_files:
        print("No valid Insta360 INSV files found.")
        sys.exit(1)

    print(f"Found {len(input_files)} file(s)")

    # Determine output paths
    output_paths = []
    if args.output:
        output_path = Path(args.output)

        if len(input_files) == 1 and not output_path.is_dir():
            # Single file to single output
            output_paths = [output_path]
        else:
            # Multiple files or output is a directory
            output_path.mkdir(parents=True, exist_ok=True)
            for f in input_files:
                out_name = f.stem + '_stabilized.mp4'
                output_paths.append(output_path / out_name)
    else:
        # Default: same folder with _stabilized suffix
        for f in input_files:
            out_name = f.stem + '_stabilized.mp4'
            output_paths.append(f.parent / out_name)

    # Create config
    config = StabilizationConfig(
        smoothness=args.smoothness,
        horizon_lock=not args.no_horizon_lock,
        output_resolution=args.resolution,
        output_fps=args.fps,
        output_codec=args.codec,
        output_crf=args.crf
    )

    # Print summary
    print("\n" + "=" * 60)
    print("Batch Stabilization Configuration")
    print("=" * 60)
    print(f"  Input files:    {len(input_files)}")
    print(f"  Smoothness:     {config.smoothness}")
    print(f"  Horizon lock:   {config.horizon_lock}")
    print(f"  Resolution:     {config.output_resolution}")
    print(f"  FPS:            {config.output_fps}")
    print(f"  Codec:          {config.output_codec}")
    print(f"  Quality (CRF):  {config.output_crf}")
    print(f"  Parallel jobs:  {args.jobs}")
    print("=" * 60)

    if args.dry_run:
        print("\nDry run - files that would be processed:")
        for inp, out in zip(input_files, output_paths):
            print(f"  {inp} -> {out}")
        sys.exit(0)

    # Handle gyro-only extraction
    if args.extract_gyro_only:
        from insta360_parser import extract_imu_data, save_gyro_csv

        print("\nExtracting gyro data only...")
        for f in input_files:
            csv_path = str(f).replace('.insv', '_gyro.csv').replace('.INSV', '_gyro.csv')
            print(f"  {f} -> {csv_path}")

            imu_data = extract_imu_data(str(f))
            if imu_data:
                save_gyro_csv(imu_data, csv_path)
                print(f"    Extracted {len(imu_data.timestamps)} samples")
            else:
                print(f"    Failed to extract IMU data")

        print("\nDone!")
        sys.exit(0)

    # Process files
    print("\nStarting stabilization...")
    start_time = time.time()

    results = []
    failed = []

    if args.jobs == 1:
        # Sequential processing
        for i, (inp, out) in enumerate(zip(input_files, output_paths)):
            print(f"\n[{i + 1}/{len(input_files)}] Processing: {inp.name}")
            success = stabilize_video(str(inp), str(out), config)

            if success:
                results.append(inp)
            else:
                failed.append((inp, "Stabilization failed"))
    else:
        # Parallel processing
        tasks = [(inp, out, config) for inp, out in zip(input_files, output_paths)]

        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures = {executor.submit(process_single_file, task): task[0] for task in tasks}

            for future in as_completed(futures):
                inp, success, message = future.result()
                if success:
                    results.append(inp)
                    print(f"  Completed: {inp.name}")
                else:
                    failed.append((inp, message))
                    print(f"  Failed: {inp.name} - {message}")

    # Summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Processed:  {len(results)}/{len(input_files)} files")
    print(f"  Failed:     {len(failed)}")
    print(f"  Time:       {elapsed:.1f} seconds")

    if failed:
        print("\nFailed files:")
        for f, msg in failed:
            print(f"  {f}: {msg}")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
