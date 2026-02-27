# 360 Video Stabilizer for Insta360

A Python utility for stabilizing Insta360 360° drone footage using embedded gyroscope data.

> **Note**: The Insta360 INSV file format uses a proprietary encoding for gyro data.
> For best results, we recommend using **Insta360 Studio** with FlowState stabilization
> enabled, or **Gyroflow** which has full support for Insta360 cameras.
>
> This utility provides tools for experimentation and custom workflows.

## Recommended Workflow

1. **Use Insta360 Studio** (easiest):
   - Open INSV files in Insta360 Studio
   - Enable "FlowState Stabilization"
   - Enable "360° Horizon Lock"
   - Export as equirectangular MP4

2. **Use Gyroflow** (more control):
   - Download from https://gyroflow.xyz/
   - Has native Insta360 support with lens profiles
   - Offers advanced stabilization options

## How It Works

1. **Extract IMU Data**: Parses the INSV file to extract gyroscope and accelerometer data embedded by the camera
2. **Integrate Orientation**: Converts gyroscope rotation rates into camera orientation over time using quaternion math
3. **Smooth Orientation**: Applies a smoothing filter to create the desired "stable" camera path
4. **Calculate Corrections**: Computes the difference between raw and smooth orientations
5. **Apply via FFmpeg**: Uses FFmpeg's v360 filter to apply rotation corrections to each frame

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Ensure FFmpeg is installed
# Windows: choco install ffmpeg
# Mac: brew install ffmpeg
# Linux: sudo apt install ffmpeg
```

## Usage

### Stabilize a Single File

```bash
python stabilizer.py input.insv output.mp4
```

### Batch Processing

```bash
# Process all INSV files in a folder
python batch_stabilize.py ./input_folder -o ./output_folder

# With custom settings
python batch_stabilize.py ./videos --smoothness 0.9 --resolution 1920x960

# Parallel processing (4 workers)
python batch_stabilize.py ./videos -o ./output -j 4

# Extract gyro data only (no video processing)
python batch_stabilize.py ./videos --extract-gyro-only
```

### Extract Gyro Data Only

```bash
python insta360_parser.py input.insv output.csv
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--smoothness` | 0.95 | Smoothing factor (0-1). Higher = smoother but less responsive |
| `--horizon-lock` | on | Keep horizon level |
| `--no-horizon-lock` | - | Allow horizon tilt |
| `--resolution` | 3840x1920 | Output resolution |
| `--fps` | 30 | Output frame rate |
| `--codec` | libx264 | Video codec |
| `--crf` | 18 | Quality (lower = better, 18-23 typical) |
| `-j, --jobs` | 1 | Number of parallel processing jobs |

## File Structure

```
stabilizer/
├── insta360_parser.py   # INSV file parser, extracts IMU data
├── stabilizer.py        # Main stabilization logic
├── batch_stabilize.py   # Batch processing CLI
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Technical Details

### INSV File Format

Insta360 INSV files contain:
- Dual-fisheye video (two 180° lenses)
- Embedded IMU data at ~200Hz:
  - Gyroscope (rotation rates in rad/s)
  - Accelerometer (acceleration in m/s²)
- Frame timing/exposure data

The IMU data is stored in a trailer section at the end of the file:
- Record `0x300`: IMU samples (timestamp + 6 doubles)
- Record `0x400`: Frame exposure timestamps

### Stabilization Algorithm

1. **Gyro Integration**: Convert angular velocity to orientation using quaternion multiplication
2. **Smoothing**: Apply bidirectional exponential moving average on quaternions (SLERP)
3. **Horizon Lock**: Optionally force roll to zero for level horizon
4. **Correction**: Calculate rotation needed to go from raw to smooth orientation
5. **FFmpeg**: Apply v360 filter with rotation parameters

### Limitations

- Currently applies average correction rather than per-frame (per-frame requires complex FFmpeg filter chain)
- Best results with Insta360 cameras that have good IMU data
- Very fast motion may exceed correction limits

## Credits

- Based on [Gyroflow](https://github.com/gyroflow/gyroflow) and [gyroflow-python](https://github.com/gyroflow/gyroflow-python) by Elvin Chen
- INSV file format research from the Insta360 community

## License

MIT License - Feel free to use and modify for your projects.
