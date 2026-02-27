"""
Insta360 INSV File Parser
Extracts gyroscope and accelerometer data from Insta360 video files.

Based on gyroflow-python by Elvin Chen and the Gyroflow project.
https://github.com/gyroflow/gyroflow-python

INSV File Format:
- Last 32 bytes: Magic string '8db42d694ccc418790edff439fe026bf'
- Trailer contains record entries (2-byte ID + 4-byte offset)
- Record 0x300: Accelerometer/Gyroscope data
- Record 0x400: Exposure/frame timing data
"""

import struct
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
from scipy import signal


# Insta360 magic string at end of file
INSTA360_MAGIC = b'8db42d694ccc418790edff439fe026bf'

# Record type IDs
RECORD_IMU = 0x300
RECORD_EXPOSURE = 0x400


@dataclass
class IMUData:
    """Container for IMU (Inertial Measurement Unit) data"""
    timestamps: np.ndarray      # Timestamps in seconds
    gyro: np.ndarray           # Gyroscope data [N, 3] (roll, pitch, yaw) in rad/s
    accel: np.ndarray          # Accelerometer data [N, 3] in m/s^2
    sample_rate: float         # Estimated sample rate in Hz


@dataclass
class ExposureData:
    """Container for exposure/frame timing data"""
    timestamps: np.ndarray     # Frame timestamps in seconds
    frame_count: int           # Total number of frames


def is_insta360_file(filepath: str) -> bool:
    """Check if file is a valid Insta360 video file"""
    try:
        with open(filepath, 'rb') as f:
            f.seek(-32, 2)  # Seek to last 32 bytes
            magic = f.read(32)
            return magic == INSTA360_MAGIC
    except Exception:
        return False


def _read_trailer(f) -> Dict[int, Tuple[int, int]]:
    """
    Read the trailer section to find record locations.
    Returns dict mapping record_id -> (offset, size)
    """
    records = {}

    # Seek to end and read backwards to find trailer
    f.seek(-32, 2)  # Skip magic string
    file_end = f.tell()

    # Read trailer entries (work backwards)
    # Each entry: 2-byte ID + 4-byte offset
    f.seek(-32 - 6, 2)

    while True:
        pos = f.tell()
        if pos < 0:
            break

        data = f.read(6)
        if len(data) < 6:
            break

        record_id, offset = struct.unpack('<HI', data)

        # Valid record IDs we care about
        if record_id in (RECORD_IMU, RECORD_EXPOSURE):
            # Read the size from the record header
            f.seek(offset)
            size_data = f.read(4)
            if len(size_data) == 4:
                size = struct.unpack('<I', size_data)[0]
                records[record_id] = (offset + 4, size)  # Skip size field

        # Check for end of trailer
        if record_id == 0x0100:  # Usually marks start
            break

        # Move to previous entry
        f.seek(pos - 6)
        if pos - 6 < 0:
            break

    return records


def _parse_imu_record(f, offset: int, size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse IMU data record.
    Each sample is 56 bytes: Q (8-byte timestamp) + 6d (6 doubles for accel + gyro)

    Returns: (timestamps, accel_data, gyro_data)
    """
    f.seek(offset)
    data = f.read(size)

    sample_size = 56  # 8 + 6*8 bytes
    num_samples = len(data) // sample_size

    timestamps = []
    accel_data = []
    gyro_data = []

    for i in range(num_samples):
        sample = data[i * sample_size:(i + 1) * sample_size]
        if len(sample) < sample_size:
            break

        # Unpack: timestamp (microseconds), then accel (pitch, yaw, roll), then gyro (pitch, yaw, roll)
        values = struct.unpack('<Q6d', sample)

        timestamp_us = values[0]
        acc_pitch, acc_yaw, acc_roll = values[1:4]
        gyro_pitch, gyro_yaw, gyro_roll = values[4:7]

        timestamps.append(timestamp_us / 1e6)  # Convert to seconds

        # Reorder to (roll, pitch, yaw) convention and apply sign corrections
        accel_data.append([acc_roll, -acc_pitch, acc_yaw])
        gyro_data.append([gyro_roll, -gyro_pitch, gyro_yaw])

    return (
        np.array(timestamps),
        np.array(accel_data),
        np.array(gyro_data)
    )


def _parse_exposure_record(f, offset: int, size: int) -> np.ndarray:
    """
    Parse exposure/frame timing record.
    Returns array of frame timestamps in seconds.
    """
    f.seek(offset)
    data = f.read(size)

    # Each entry is 8 bytes (timestamp in microseconds)
    num_frames = len(data) // 8
    timestamps = []

    for i in range(num_frames):
        ts_data = data[i * 8:(i + 1) * 8]
        if len(ts_data) < 8:
            break
        timestamp_us = struct.unpack('<Q', ts_data)[0]
        timestamps.append(timestamp_us / 1e6)

    return np.array(timestamps)


def lowpass_filter(data: np.ndarray, cutoff: float = 0.35, order: int = 2) -> np.ndarray:
    """
    Apply zero-phase Butterworth low-pass filter.

    Args:
        data: Input data array [N, 3]
        cutoff: Cutoff frequency as fraction of Nyquist
        order: Filter order

    Returns:
        Filtered data array
    """
    if len(data) < 10:
        return data

    b, a = signal.butter(order, cutoff, btype='low')

    filtered = np.zeros_like(data)
    for i in range(data.shape[1]):
        filtered[:, i] = signal.filtfilt(b, a, data[:, i])

    return filtered


def extract_imu_data(filepath: str,
                     apply_filter: bool = True,
                     filter_cutoff: float = 0.35) -> Optional[IMUData]:
    """
    Extract IMU data from an Insta360 INSV file.

    Args:
        filepath: Path to INSV file
        apply_filter: Whether to apply low-pass filtering
        filter_cutoff: Filter cutoff frequency (0-1, fraction of Nyquist)

    Returns:
        IMUData object containing timestamps, gyro, and accel data
        Returns None if file is not valid or parsing fails
    """
    filepath = str(filepath)

    if not is_insta360_file(filepath):
        print(f"Error: {filepath} is not a valid Insta360 file")
        return None

    try:
        with open(filepath, 'rb') as f:
            # Find record locations
            records = _read_trailer(f)

            if RECORD_IMU not in records:
                print(f"Error: No IMU data found in {filepath}")
                return None

            # Parse IMU data
            imu_offset, imu_size = records[RECORD_IMU]
            timestamps, accel, gyro = _parse_imu_record(f, imu_offset, imu_size)

            if len(timestamps) == 0:
                print(f"Error: Empty IMU data in {filepath}")
                return None

            # Normalize timestamps to start from 0
            timestamps = timestamps - timestamps[0]

            # Calculate sample rate
            if len(timestamps) > 1:
                dt = np.median(np.diff(timestamps))
                sample_rate = 1.0 / dt if dt > 0 else 200.0
            else:
                sample_rate = 200.0  # Default Insta360 IMU rate

            # Apply filtering if requested
            if apply_filter and len(gyro) > 10:
                gyro = lowpass_filter(gyro, filter_cutoff)
                accel = lowpass_filter(accel, filter_cutoff)

            return IMUData(
                timestamps=timestamps,
                gyro=gyro,
                accel=accel,
                sample_rate=sample_rate
            )

    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_exposure_data(filepath: str) -> Optional[ExposureData]:
    """
    Extract frame timing data from an Insta360 INSV file.

    Args:
        filepath: Path to INSV file

    Returns:
        ExposureData object containing frame timestamps
    """
    filepath = str(filepath)

    if not is_insta360_file(filepath):
        return None

    try:
        with open(filepath, 'rb') as f:
            records = _read_trailer(f)

            if RECORD_EXPOSURE not in records:
                return None

            exp_offset, exp_size = records[RECORD_EXPOSURE]
            timestamps = _parse_exposure_record(f, exp_offset, exp_size)

            # Normalize to start from 0
            if len(timestamps) > 0:
                timestamps = timestamps - timestamps[0]

            return ExposureData(
                timestamps=timestamps,
                frame_count=len(timestamps)
            )

    except Exception as e:
        print(f"Error extracting exposure data: {e}")
        return None


def save_gyro_csv(imu_data: IMUData, output_path: str):
    """
    Save gyro data to CSV format compatible with other tools.

    Format: timestamp, gyro_x, gyro_y, gyro_z, accel_x, accel_y, accel_z
    """
    with open(output_path, 'w') as f:
        f.write("timestamp,gyro_x,gyro_y,gyro_z,accel_x,accel_y,accel_z\n")
        for i in range(len(imu_data.timestamps)):
            f.write(f"{imu_data.timestamps[i]:.6f},"
                    f"{imu_data.gyro[i, 0]:.6f},{imu_data.gyro[i, 1]:.6f},{imu_data.gyro[i, 2]:.6f},"
                    f"{imu_data.accel[i, 0]:.6f},{imu_data.accel[i, 1]:.6f},{imu_data.accel[i, 2]:.6f}\n")


# Command-line interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python insta360_parser.py <input.insv> [output.csv]")
        print("\nExtracts gyroscope data from Insta360 INSV files.")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.insv', '_gyro.csv').replace('.INSV', '_gyro.csv')

    print(f"Parsing: {input_file}")

    # Check if valid
    if not is_insta360_file(input_file):
        print("Error: Not a valid Insta360 file")
        sys.exit(1)

    # Extract IMU data
    imu_data = extract_imu_data(input_file)

    if imu_data is None:
        print("Error: Failed to extract IMU data")
        sys.exit(1)

    print(f"Extracted {len(imu_data.timestamps)} IMU samples")
    print(f"Duration: {imu_data.timestamps[-1]:.2f} seconds")
    print(f"Sample rate: {imu_data.sample_rate:.1f} Hz")

    # Save to CSV
    save_gyro_csv(imu_data, output_file)
    print(f"Saved to: {output_file}")
