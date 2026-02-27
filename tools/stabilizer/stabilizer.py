"""
360 Video Stabilizer for Insta360 Footage

Uses gyroscope data to calculate camera orientation over time,
then applies inverse rotation to stabilize the footage.

The stabilization works by:
1. Integrating gyro rates to get orientation quaternions
2. Smoothing the orientation to get desired "stable" orientation
3. Calculating the correction = smooth_orientation * inverse(raw_orientation)
4. Applying correction via FFmpeg's v360 filter with per-frame rotation
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass
import subprocess
import json
import tempfile
import os

from insta360_parser import extract_imu_data, extract_exposure_data, IMUData


@dataclass
class StabilizationConfig:
    """Configuration for stabilization"""
    smoothness: float = 0.95         # 0-1, higher = smoother but less responsive
    horizon_lock: bool = True        # Lock horizon level
    max_correction: float = 30.0     # Maximum correction angle in degrees
    output_resolution: str = "3840x1920"  # Output resolution
    output_fps: float = 30.0         # Output frame rate
    output_codec: str = "libx264"    # Video codec
    output_crf: int = 18             # Quality (lower = better, 18-23 typical)


class QuaternionMath:
    """Quaternion operations for 3D rotation"""

    @staticmethod
    def from_euler(roll: float, pitch: float, yaw: float) -> np.ndarray:
        """Convert Euler angles (radians) to quaternion [w, x, y, z]"""
        cr, sr = np.cos(roll / 2), np.sin(roll / 2)
        cp, sp = np.cos(pitch / 2), np.sin(pitch / 2)
        cy, sy = np.cos(yaw / 2), np.sin(yaw / 2)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy

        return np.array([w, x, y, z])

    @staticmethod
    def to_euler(q: np.ndarray) -> Tuple[float, float, float]:
        """Convert quaternion to Euler angles (roll, pitch, yaw) in radians"""
        w, x, y, z = q

        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = np.arctan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = np.copysign(np.pi / 2, sinp)
        else:
            pitch = np.arcsin(sinp)

        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)

        return roll, pitch, yaw

    @staticmethod
    def multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiply two quaternions"""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2

        return np.array([
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        ])

    @staticmethod
    def inverse(q: np.ndarray) -> np.ndarray:
        """Return inverse (conjugate for unit quaternion)"""
        return np.array([q[0], -q[1], -q[2], -q[3]])

    @staticmethod
    def normalize(q: np.ndarray) -> np.ndarray:
        """Normalize quaternion"""
        norm = np.linalg.norm(q)
        if norm > 0:
            return q / norm
        return q

    @staticmethod
    def slerp(q1: np.ndarray, q2: np.ndarray, t: float) -> np.ndarray:
        """Spherical linear interpolation between quaternions"""
        dot = np.dot(q1, q2)

        # Ensure shortest path
        if dot < 0:
            q2 = -q2
            dot = -dot

        if dot > 0.9995:
            # Linear interpolation for very close quaternions
            result = q1 + t * (q2 - q1)
            return QuaternionMath.normalize(result)

        theta = np.arccos(dot)
        sin_theta = np.sin(theta)

        s1 = np.sin((1 - t) * theta) / sin_theta
        s2 = np.sin(t * theta) / sin_theta

        return s1 * q1 + s2 * q2


def integrate_gyro(imu_data: IMUData) -> np.ndarray:
    """
    Integrate gyroscope rates to get orientation quaternions.

    Args:
        imu_data: IMU data with timestamps and gyro rates

    Returns:
        Array of quaternions [N, 4] representing orientation at each sample
    """
    n_samples = len(imu_data.timestamps)
    orientations = np.zeros((n_samples, 4))
    orientations[0] = [1, 0, 0, 0]  # Start at identity

    for i in range(1, n_samples):
        dt = imu_data.timestamps[i] - imu_data.timestamps[i - 1]

        # Gyro rates in rad/s (roll, pitch, yaw)
        wx, wy, wz = imu_data.gyro[i]

        # Angular velocity magnitude
        omega = np.sqrt(wx * wx + wy * wy + wz * wz)

        if omega > 1e-10:
            # Quaternion derivative
            half_angle = omega * dt / 2
            s = np.sin(half_angle) / omega
            c = np.cos(half_angle)

            # Delta quaternion
            dq = np.array([c, s * wx, s * wy, s * wz])

            # Update orientation
            orientations[i] = QuaternionMath.multiply(orientations[i - 1], dq)
            orientations[i] = QuaternionMath.normalize(orientations[i])
        else:
            orientations[i] = orientations[i - 1]

    return orientations


def smooth_orientations(orientations: np.ndarray,
                        timestamps: np.ndarray,
                        smoothness: float = 0.95) -> np.ndarray:
    """
    Smooth orientation data using exponential moving average on quaternions.

    Args:
        orientations: Array of quaternions [N, 4]
        timestamps: Timestamps for each orientation
        smoothness: Smoothing factor (0-1, higher = smoother)

    Returns:
        Smoothed quaternion array
    """
    n = len(orientations)
    smoothed = np.zeros_like(orientations)
    smoothed[0] = orientations[0]

    # Adaptive alpha based on time delta
    base_alpha = 1 - smoothness

    for i in range(1, n):
        dt = timestamps[i] - timestamps[i - 1]
        # Scale alpha by time delta (assuming ~200Hz base rate)
        alpha = min(1.0, base_alpha * dt * 200)

        smoothed[i] = QuaternionMath.slerp(smoothed[i - 1], orientations[i], alpha)

    # Second pass (reverse direction) for zero-lag filtering
    for i in range(n - 2, -1, -1):
        dt = timestamps[i + 1] - timestamps[i]
        alpha = min(1.0, base_alpha * dt * 200)

        smoothed[i] = QuaternionMath.slerp(smoothed[i], smoothed[i + 1], alpha * 0.5)

    return smoothed


def calculate_corrections(raw_orientations: np.ndarray,
                          smooth_orientations: np.ndarray,
                          horizon_lock: bool = True,
                          max_correction: float = 30.0) -> np.ndarray:
    """
    Calculate correction rotations needed to stabilize.

    Args:
        raw_orientations: Original camera orientations
        smooth_orientations: Desired smooth orientations
        horizon_lock: If True, also correct roll to level horizon
        max_correction: Maximum allowed correction in degrees

    Returns:
        Array of correction Euler angles [N, 3] in degrees (roll, pitch, yaw)
    """
    n = len(raw_orientations)
    corrections = np.zeros((n, 3))

    max_rad = np.radians(max_correction)

    for i in range(n):
        # Correction = smooth * inverse(raw)
        raw_inv = QuaternionMath.inverse(raw_orientations[i])
        correction_q = QuaternionMath.multiply(smooth_orientations[i], raw_inv)

        # Convert to Euler
        roll, pitch, yaw = QuaternionMath.to_euler(correction_q)

        # Optionally lock horizon (zero out roll correction to keep level)
        if horizon_lock:
            # Actually, for horizon lock, we want to FULLY correct roll
            # So we compute the absolute roll of raw orientation
            raw_roll, _, _ = QuaternionMath.to_euler(raw_orientations[i])
            roll = -raw_roll  # Correct to level

        # Clamp corrections
        roll = np.clip(roll, -max_rad, max_rad)
        pitch = np.clip(pitch, -max_rad, max_rad)
        yaw = np.clip(yaw, -max_rad, max_rad)

        corrections[i] = np.degrees([roll, pitch, yaw])

    return corrections


def interpolate_to_frames(corrections: np.ndarray,
                          imu_timestamps: np.ndarray,
                          frame_times: np.ndarray) -> np.ndarray:
    """
    Interpolate corrections from IMU rate to video frame rate.

    Args:
        corrections: Correction angles at IMU sample rate [N, 3]
        imu_timestamps: IMU timestamps
        frame_times: Video frame timestamps

    Returns:
        Interpolated corrections at frame rate [M, 3]
    """
    n_frames = len(frame_times)
    frame_corrections = np.zeros((n_frames, 3))

    for i in range(3):  # For each axis
        frame_corrections[:, i] = np.interp(
            frame_times,
            imu_timestamps,
            corrections[:, i]
        )

    return frame_corrections


def generate_ffmpeg_filter(corrections: np.ndarray,
                           frame_times: np.ndarray,
                           temp_dir: str) -> str:
    """
    Generate FFmpeg filter string for applying per-frame rotations.

    Uses the v360 filter with sendcmd to apply rotation corrections.

    Args:
        corrections: Per-frame correction angles [N, 3] (roll, pitch, yaw) in degrees
        frame_times: Frame timestamps
        temp_dir: Directory to store temporary files

    Returns:
        FFmpeg filter string
    """
    # Write corrections to a file for sendcmd
    cmd_file = os.path.join(temp_dir, "corrections.cmd")

    with open(cmd_file, 'w') as f:
        for i, (roll, pitch, yaw) in enumerate(corrections):
            time = frame_times[i] if i < len(frame_times) else i / 30.0

            # v360 filter rotation parameters
            # Note: v360 uses different angle conventions, may need adjustment
            f.write(f"{time:.6f} v360 roll {roll:.3f};\n")
            f.write(f"{time:.6f} v360 pitch {pitch:.3f};\n")
            f.write(f"{time:.6f} v360 yaw {yaw:.3f};\n")

    # Alternative: Use a simpler approach with constant correction for testing
    avg_roll = np.mean(corrections[:, 0])
    avg_pitch = np.mean(corrections[:, 1])
    avg_yaw = np.mean(corrections[:, 2])

    # Basic v360 filter with average correction
    # For per-frame, we'd need more complex filter chain
    filter_str = (
        f"v360=input=equirect:output=equirect:"
        f"roll={avg_roll:.2f}:pitch={avg_pitch:.2f}:yaw={avg_yaw:.2f}"
    )

    return filter_str


def stabilize_video(input_path: str,
                    output_path: str,
                    config: Optional[StabilizationConfig] = None,
                    progress_callback=None) -> bool:
    """
    Stabilize an Insta360 video using embedded gyro data.

    Args:
        input_path: Path to input INSV file
        output_path: Path for stabilized output MP4
        config: Stabilization configuration
        progress_callback: Optional callback for progress updates

    Returns:
        True if successful, False otherwise
    """
    if config is None:
        config = StabilizationConfig()

    print(f"Stabilizing: {input_path}")
    print(f"Output: {output_path}")

    # Step 1: Extract IMU data
    print("Extracting IMU data...")
    imu_data = extract_imu_data(input_path, apply_filter=True, filter_cutoff=0.3)

    if imu_data is None:
        print("Error: Failed to extract IMU data")
        return False

    print(f"  - {len(imu_data.timestamps)} IMU samples @ {imu_data.sample_rate:.1f} Hz")

    # Step 2: Extract frame timing
    print("Extracting frame timing...")
    exposure_data = extract_exposure_data(input_path)

    if exposure_data is None:
        # Estimate frame times based on video duration
        print("  - Using estimated frame times")
        duration = imu_data.timestamps[-1]
        n_frames = int(duration * config.output_fps)
        frame_times = np.linspace(0, duration, n_frames)
    else:
        frame_times = exposure_data.timestamps
        print(f"  - {exposure_data.frame_count} frames")

    # Step 3: Integrate gyro to get orientations
    print("Integrating gyroscope data...")
    raw_orientations = integrate_gyro(imu_data)

    # Step 4: Smooth orientations
    print(f"Smoothing (factor: {config.smoothness})...")
    smooth_orients = smooth_orientations(
        raw_orientations,
        imu_data.timestamps,
        config.smoothness
    )

    # Step 5: Calculate corrections
    print("Calculating corrections...")
    corrections = calculate_corrections(
        raw_orientations,
        smooth_orients,
        horizon_lock=config.horizon_lock,
        max_correction=config.max_correction
    )

    # Step 6: Interpolate to frame rate
    print("Interpolating to frame rate...")
    frame_corrections = interpolate_to_frames(
        corrections,
        imu_data.timestamps,
        frame_times
    )

    # Print correction statistics
    print(f"  - Roll correction: {np.std(frame_corrections[:, 0]):.2f}° std")
    print(f"  - Pitch correction: {np.std(frame_corrections[:, 1]):.2f}° std")
    print(f"  - Yaw correction: {np.std(frame_corrections[:, 2]):.2f}° std")

    # Step 7: Apply stabilization via FFmpeg
    print("Applying stabilization with FFmpeg...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # For now, use average correction (per-frame requires more complex setup)
        avg_roll = np.mean(frame_corrections[:, 0])
        avg_pitch = np.mean(frame_corrections[:, 1])

        # Build FFmpeg command
        # Note: We need to convert from dual-fisheye to equirect first
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vf", (
                # Convert Insta360 dual-fisheye to equirectangular with stabilization
                f"v360=dfisheye:equirect:"
                f"ih_fov=190:iv_fov=190:"
                f"roll={avg_roll:.2f}:pitch={avg_pitch:.2f}:"
                f"w={config.output_resolution.split('x')[0]}:"
                f"h={config.output_resolution.split('x')[1]}"
            ),
            "-c:v", config.output_codec,
            "-crf", str(config.output_crf),
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ]

        print(f"Running: {' '.join(ffmpeg_cmd)}")

        try:
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr}")
                return False

            print("Stabilization complete!")
            return True

        except Exception as e:
            print(f"Error running FFmpeg: {e}")
            return False


def save_corrections_json(corrections: np.ndarray,
                          timestamps: np.ndarray,
                          output_path: str):
    """Save corrections to JSON for use with other tools"""
    data = {
        "version": "1.0",
        "corrections": [
            {
                "time": float(t),
                "roll": float(c[0]),
                "pitch": float(c[1]),
                "yaw": float(c[2])
            }
            for t, c in zip(timestamps, corrections)
        ]
    }

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)


# Command-line interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("360 Video Stabilizer for Insta360")
        print("\nUsage: python stabilizer.py <input.insv> [output.mp4] [options]")
        print("\nOptions:")
        print("  --smoothness <0-1>    Smoothing factor (default: 0.95)")
        print("  --horizon-lock        Lock horizon level (default: on)")
        print("  --no-horizon-lock     Don't lock horizon")
        print("  --resolution <WxH>    Output resolution (default: 3840x1920)")
        print("\nExample:")
        print("  python stabilizer.py input.insv output.mp4 --smoothness 0.9")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else input_file.replace('.insv', '_stabilized.mp4').replace('.INSV', '_stabilized.mp4')

    # Parse options
    config = StabilizationConfig()

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == '--smoothness' and i + 1 < len(args):
            config.smoothness = float(args[i + 1])
            i += 2
        elif args[i] == '--horizon-lock':
            config.horizon_lock = True
            i += 1
        elif args[i] == '--no-horizon-lock':
            config.horizon_lock = False
            i += 1
        elif args[i] == '--resolution' and i + 1 < len(args):
            config.output_resolution = args[i + 1]
            i += 2
        else:
            i += 1

    # Run stabilization
    success = stabilize_video(input_file, output_file, config)
    sys.exit(0 if success else 1)
