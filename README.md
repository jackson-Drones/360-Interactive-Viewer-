# 360 Virtual Experience Viewer

A web-based multi-panel 360-degree video viewer for synchronized panoramic playback. Displays three concurrent 360-degree video streams in a seamless 180-degree field of view, with day/night video switching.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Video Data Setup](#video-data-setup)
- [Running the Viewer](#running-the-viewer)
- [Features](#features)
- [Controls](#controls)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Testing Checklist](#testing-checklist)
- [Troubleshooting](#troubleshooting)
- [Tools](#tools)
- [Technical Specifications](#technical-specifications)

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10 or later |
| **Python** | 3.7 or later ([python.org/downloads](https://www.python.org/downloads/)) |
| **Browser** | Chrome, Firefox, or Edge with WebGL support |
| **RAM** | 16 GB recommended (3 simultaneous video streams) |
| **Disk Space** | ~35 GB for HLS video segments |
| **FFmpeg** | Only needed if converting your own MP4 files to HLS ([ffmpeg.org](https://ffmpeg.org/download.html)) |

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/jackson-Drones/360-virtual-experience.git
cd 360-virtual-experience
```

### 2. Verify Python

```bash
python --version
```

Confirm it shows Python 3.7 or later. No pip packages are required to run the viewer.

### 3. Download Video Data

The video files (~35 GB) are too large for GitHub. Download them from Google Drive:

**[Download Video Data from Google Drive](YOUR_GOOGLE_DRIVE_LINK_HERE)**

See [Video Data Setup](#video-data-setup) below for where to place the files.

### 4. Run

Double-click `start.bat`, or run manually:

```bash
python server.py
```

Then open http://localhost:8080/viewer/multi-view.html

---

## Video Data Setup

### Option 1: Download Pre-Converted HLS Segments (Recommended)

Download the `hls/` folder from the Google Drive link above and place it inside the `videos/` directory. Your folder structure should look like:

```
videos/
└── hls/
    ├── flight_line_1/
    │   ├── playlist.m3u8
    │   └── segment_000.ts ... segment_082.ts
    ├── flight_line_2/
    │   ├── playlist.m3u8
    │   └── segment_000.ts ... segment_082.ts
    ├── flight_line_3/
    │   ├── playlist.m3u8
    │   └── segment_000.ts ... segment_083.ts
    ├── night_flight_line_1/
    │   ├── playlist.m3u8
    │   └── segment_000.ts ... segment_082.ts
    ├── night_flight_line_2/
    │   ├── playlist.m3u8
    │   └── segment_000.ts ... segment_082.ts
    └── night_flight_line_3/
        ├── playlist.m3u8
        └── segment_000.ts ... segment_082.ts
```

Each flight line contains ~84 files (1 playlist + ~83 segments). Total size: ~35 GB.

### Option 2: Convert from Source MP4 Files

If you have the original equirectangular MP4 files:

1. Install FFmpeg and ensure it is in your PATH
2. Place your MP4 files in the `videos/` folder named `flight_line_1.mp4`, `flight_line_2.mp4`, `flight_line_3.mp4`
3. Run the conversion script:
   ```bash
   python tools/convert_to_hls.py
   ```
4. Conversion takes ~5-10 minutes per video (stream copy, no re-encoding)

### Video Requirements

- **Format**: Equirectangular MP4 (exported from Insta360 Studio or similar)
- **Aspect ratio**: 2:1 (e.g., 5760x2880 or 11520x5760)
- **Codec**: H.264 or H.265
- Videos should be pre-synced (trimmed to the same start point)

---

## Running the Viewer

**Option A: start.bat (recommended)**
- Double-click `start.bat`
- The server starts and the viewer opens automatically in your default browser

**Option B: Manual**
```bash
python server.py
```
- Open http://localhost:8080/viewer/multi-view.html
- To use a different port: `python server.py 9090` (then go to http://localhost:9090/viewer/multi-view.html)

**Stopping the server**: Press `Ctrl+C` in the terminal window.

---

## Features

- **3-Panel Panorama View**: Three 360 videos side-by-side creating a 180-degree field of view
- **Synchronized Playback**: All panels play in sync with resync capability
- **Day/Night Toggle**: Switch between day and night footage per panel or all at once
- **Linked Controls**: Pitch and roll adjustments apply to all panels simultaneously
- **Interactive Navigation**: Drag to look around, scroll to zoom
- **Multiple Aspect Ratios**: Standard (16:9, 21:9, 32:9), mid-range (70%, 60%, 50%), and panoramic letterbox modes
- **Performance Monitoring**: Real-time FPS, video stats, and dropped frame tracking
- **Pitch Lock/Sync**: Independent control of pitch locking and synchronization
- **HLS Streaming**: Efficient segment-based streaming for smooth playback of large video files

---

## Controls

### Mouse
- **Drag**: Look around (pan/tilt)
- **Scroll wheel**: Zoom in/out

### Touch (Mobile)
- **Single finger drag**: Look around
- **Pinch**: Zoom in/out

### Keyboard

| Key | Action |
|-----|--------|
| Space | Play/Pause |
| WASD / Arrow keys | Pan and tilt |
| Q / E | Roll left/right |
| + / - | Zoom in/out |
| 1 / 2 / 3 | Toggle panels (FL3/FL2/FL1) |
| G | Toggle controls panel |
| H | Hide/show all UI |
| P | Toggle panorama mode (seamless borders) |
| L | Toggle linked views |
| C | Toggle panel controls (pitch/yaw/roll) |
| F | Toggle performance stats |
| Y | Resync all videos |
| R | Reset all views |
| N | Toggle day/night (all panels) |

### Control Panel Options

- **Panels**: Toggle individual flight line panels on/off
- **Aspect**: Standard aspect ratios (Full, 32:9, 21:9, 16:9)
- **Mid**: Mid-range letterbox modes (70%, 60%, 50% height)
- **Pano**: Panoramic letterbox modes (Wide, Wider, Ultra, Cinema)
- **Panorama**: Toggle seamless panel borders
- **Link Views**: Sync pitch/roll across all panels
- **Pitch Lock**: Lock pitch to prevent changes
- **Pitch Sync**: Sync pitch independently (can be separate from Link Views)
- **Controls**: Show/hide per-panel pitch/yaw/roll controls
- **Sync**: Playback synchronization
- **Stats**: Performance monitoring display

### Performance Stats (Press F)

- **Render FPS**: WebGL rendering frame rate (green 55+, yellow 30+, red <30)
- **Video FPS**: Estimated video playback frame rate
- **Resolution**: Video dimensions
- **Buffered**: Video buffer percentage
- **Dropped**: Dropped frames count and percentage

---

## Configuration

Edit `viewer/multi-view.html` to customize:

```javascript
// Video file paths (HLS playlists)
const videoSets = {
    day: [
        '/videos/hls/flight_line_3/playlist.m3u8',   // Panel 1 (Left)
        '/videos/hls/flight_line_2/playlist.m3u8',   // Panel 2 (Center)
        '/videos/hls/flight_line_1/playlist.m3u8'    // Panel 3 (Right)
    ],
    night: [
        '/videos/hls/night_flight_line_1/playlist.m3u8',
        '/videos/hls/night_flight_line_2/playlist.m3u8',
        '/videos/hls/night_flight_line_3/playlist.m3u8'
    ]
};

// Panorama settings
const panoramaFov = 60;   // FOV per panel (60 x 3 = 180 total)
const baseYaw = -945;     // Base viewing direction
```

---

## Project Structure

```
360-virtual-experience/
├── start.bat                  # Windows launch script
├── server.py                  # HTTP server with range request & HLS support
├── README.md                  # This file
├── SPEC_SHEET.md              # Detailed technical specification
├── requirements.txt           # Dependency documentation
├── .gitignore
├── viewer/
│   ├── multi-view.html        # Main 3-panel panorama viewer (HLS)
│   └── index.html             # Single video viewer
├── videos/
│   └── hls/                   # HLS segments (download separately)
│       ├── flight_line_1/     # Day - Panel 3 (Right)
│       ├── flight_line_2/     # Day - Panel 2 (Center)
│       ├── flight_line_3/     # Day - Panel 1 (Left)
│       ├── night_flight_line_1/
│       ├── night_flight_line_2/
│       └── night_flight_line_3/
└── tools/
    ├── convert_to_hls.py      # MP4 to HLS conversion (requires FFmpeg)
    └── stabilizer/            # Video stabilization tools (optional)
```

---

## Testing Checklist

Use this checklist to verify the application is working correctly after installation.

### 1. Server Startup

- [ ] Run `python server.py` from the project root
- [ ] Startup banner appears with URL and log file path
- [ ] No Python errors in the terminal
- [ ] http://localhost:8080 responds in the browser

### 2. Video File Verification

- [ ] `videos/hls/` directory exists with 6 subdirectories
- [ ] Each subdirectory contains a `playlist.m3u8` and ~83 `segment_XXX.ts` files
- [ ] Opening any `playlist.m3u8` in a text editor shows `#EXTM3U` header

### 3. Viewer Loading

- [ ] Navigate to http://localhost:8080/viewer/multi-view.html
- [ ] Loading spinner appears, then 3 video panels render side by side
- [ ] No errors in browser console (F12 to open dev tools)

### 4. Playback

- [ ] `Space` starts/pauses all 3 panels
- [ ] Seeking via timeline works
- [ ] `Y` resyncs all panels to the same timestamp
- [ ] 30+ seconds of playback with no buffering stalls

### 5. Controls

- [ ] **Pan/Tilt**: Click and drag, or WASD/arrow keys
- [ ] **Zoom**: Scroll wheel or +/- keys
- [ ] **Aspect ratios**: Press `G`, try each mode (Full, 32:9, 21:9, 16:9, etc.)
- [ ] **Panorama**: `P` toggles seamless panel borders
- [ ] **Link Views**: `L` syncs pitch/roll across panels
- [ ] **Panel toggle**: `1`, `2`, `3` show/hide individual panels

### 6. Performance

- [ ] `F` shows performance stats overlay
- [ ] Render FPS is green (55+ fps)
- [ ] Buffered percentage climbs toward 90%+
- [ ] Dropped frames < 1%
- [ ] Stable after 60 seconds of playback

### 7. Night Mode

- [ ] `N` toggles all panels to night footage
- [ ] Night footage loads and plays
- [ ] `N` again returns to day footage
- [ ] Per-panel day/night toggle works independently

### 8. Edge Cases

- [ ] Resize browser window during playback -- panels resize correctly
- [ ] Zoom to min and max FOV -- boundaries respected
- [ ] Rapid key presses -- no crashes
- [ ] Switch aspect ratios during playback -- smooth transitions
- [ ] Second browser tab to same URL -- works independently

### 9. Browser Compatibility

| Browser | Expected Status |
|---------|----------------|
| Chrome (latest) | Fully supported |
| Firefox (latest) | Fully supported |
| Edge (latest) | Fully supported |

---

## Troubleshooting

### Videos not loading / spinner stays forever
- If you see "Video files not found" on the loading screen, the HLS segments are missing
- Download the video data from Google Drive and extract to `videos/hls/`
- Each subdirectory must contain a `playlist.m3u8` file
- Check browser console (F12) for 404 errors on `.m3u8` or `.ts` files

### Port already in use
- The server will tell you if port 8080 is taken
- Use a different port: `python server.py 9090`
- Then open http://localhost:9090/viewer/multi-view.html

### Poor performance
- Press `F` to check render FPS and dropped frames
- Try reducing browser window size
- Close other resource-intensive applications
- Check if video resolution matches your system capabilities

### Videos out of sync
- Press `Y` to resync all videos to the same timestamp
- If videos drift frequently, they may have been exported with different frame rates

### Night videos not loading
- Confirm `videos/hls/night_flight_line_1/`, `night_flight_line_2/`, and `night_flight_line_3/` directories exist
- Each must contain a `playlist.m3u8` and segment files
- Check browser console for HLS loading errors

---

## Tools

### HLS Conversion (`tools/convert_to_hls.py`)

Converts source MP4 files to HLS streaming format using FFmpeg. Uses stream copy mode (no re-encoding) for fast conversion.

**Requires**: FFmpeg installed and in PATH.

```bash
python tools/convert_to_hls.py
```

### Video Stabilizer (`tools/stabilizer/`)

Optional tools for stabilizing Insta360 360-degree drone footage using embedded gyroscope data. See `tools/stabilizer/README.md` for details.

**Requires**:
```bash
pip install -r tools/stabilizer/requirements.txt
```

---

## Technical Specifications

See [SPEC_SHEET.md](SPEC_SHEET.md) for the complete technical specification, including:
- Three.js rendering configuration
- HLS.js buffer settings
- Server architecture
- Video format specifications
- UI display modes and input controls

### Technical Notes

- Uses Three.js (v0.160.0) for WebGL rendering and HLS.js (v1.5.7) for streaming
- Server supports HTTP range requests for streaming large video files
- Threaded request handling for concurrent multi-stream playback
- YXZ rotation order for proper flight dynamics pitch/yaw/roll behavior
- Press-and-hold controls with acceleration for fine adjustments
- Optimized for performance with reduced pixel ratio (max 1.5x)

---

## Authors

- **Jackson Ricketts** — [jackson-Drones](https://github.com/jackson-Drones)
- **Claude** (Anthropic) — AI pair programmer

---

## License

This project is licensed under the [MIT License](LICENSE).
